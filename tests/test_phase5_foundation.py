from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backtest.artifacts import BacktestArtifactCatalogProjector
from backtest.assumption_registry import build_default_assumption_bundle_registry
from backtest.compare import BacktestCompareProjector
from backtest.compare_review import CompareReviewService
from backtest.fills import DeterministicBarsFillModel, FixedBpsSlippageModel, SimulatedFill, StaticFeeModel
from backtest.diagnostics import BacktestDiagnosticsProjector
from backtest.lifecycle import BacktestLifecycle, LifecyclePlanningError
from backtest.periods import build_period_breakdown
from backtest.performance import PerformancePoint
from backtest.risk_registry import build_default_risk_policy_registry
from backtest.runner import BacktestRunnerSkeleton
from backtest.state import PortfolioState
from backtest.signals import build_signals_from_target_position
from models.backtest import BacktestRunConfig, RiskPolicyConfig, RiskPolicyOverrideConfig, StrategySessionConfig
from models.common import LiquidityFlag, OrderSide, OrderType, RiskDecision, SignalType
from models.market import BarEvent, GlobalLongShortAccountRatioEvent, TakerLongShortRatioEvent
from models.strategy import Signal, TargetPosition
from storage.db import get_engine, transaction_scope
from storage.repositories.backtest import BacktestRunRepository
from storage.repositories.market_data import BarRepository, GlobalLongShortAccountRatioRepository, TakerLongShortRatioRepository
from strategy import (
    MovingAverageCrossStrategy,
    SentimentAwareMovingAverageStrategy,
    StrategyBase,
    StrategyEvaluationInput,
    StrategyMarketContext,
    UnknownStrategyError,
    build_default_registry,
)


def build_bar(symbol: str, offset_minutes: int, close: str) -> BarEvent:
    base_time = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
    bar_time = base_time + timedelta(minutes=offset_minutes)
    return BarEvent.model_validate(
        {
            "exchange_code": "binance",
            "unified_symbol": symbol,
            "bar_interval": "1m",
            "bar_time": bar_time.isoformat(),
            "event_time": bar_time.isoformat(),
            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": "10",
        }
    )


def build_bar_at(symbol: str, bar_time: datetime, close: str) -> BarEvent:
    return BarEvent.model_validate(
        {
            "exchange_code": "binance",
            "unified_symbol": symbol,
            "bar_interval": "1m",
            "bar_time": bar_time.isoformat(),
            "event_time": bar_time.isoformat(),
            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": "10",
        }
    )


def _cleanup_strategy_market_context_window(*, start_time: datetime, end_time: datetime) -> None:
    with transaction_scope() as connection:
        for table_name, time_column in (
            ("md.taker_long_short_ratios", "ts"),
            ("md.global_long_short_account_ratios", "ts"),
            ("md.bars_1m", "bar_time"),
        ):
            connection.execute(
                text(
                    f"""
                    delete from {table_name}
                    where instrument_id = (
                        select instrument.instrument_id
                        from ref.instruments instrument
                        join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                        where exchange.exchange_code = :exchange_code
                          and instrument.unified_symbol = :unified_symbol
                        limit 1
                    )
                      and {time_column} between :start_time and :end_time
                    """
                ),
                {
                    "exchange_code": "binance",
                    "unified_symbol": "BTCUSDT_PERP",
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )


class OneShotTargetStrategy(StrategyBase):
    strategy_code = "test_strategy"
    strategy_version = "v1.0.0"

    def __init__(self, *, target_qty: DecimalLike = "1") -> None:
        self.target_qty = Decimal(str(target_qty))
        self._has_fired = False

    def evaluate(self, evaluation: StrategyEvaluationInput) -> TargetPosition | None:
        if self._has_fired:
            return None
        self._has_fired = True
        return TargetPosition.model_validate(
            {
                "strategy_code": evaluation.session.strategy_code,
                "strategy_version": evaluation.session.strategy_version,
                "target_time": evaluation.bar.bar_time,
                "positions": [
                    {
                        "exchange_code": evaluation.bar.exchange_code,
                        "unified_symbol": evaluation.bar.unified_symbol,
                        "target_qty": str(self.target_qty),
                    }
                ],
            }
        )


class HistoryBoundAssertionStrategy(StrategyBase):
    strategy_code = "history_bound_strategy"
    strategy_version = "v1.0.0"
    required_bar_history = 3

    def evaluate(self, evaluation: StrategyEvaluationInput) -> TargetPosition | None:
        if len(evaluation.recent_bars) > self.required_bar_history:
            raise AssertionError("recent_bars exceeded configured required_bar_history")
        return None


DecimalLike = Decimal | str | int | float


class ScheduledTargetStrategy(StrategyBase):
    strategy_code = "test_strategy"
    strategy_version = "v1.0.0"

    def __init__(self, scheduled_targets: list[DecimalLike | None]) -> None:
        self._scheduled_targets = [
            None if value is None else Decimal(str(value))
            for value in scheduled_targets
        ]
        self._index = 0

    def evaluate(self, evaluation: StrategyEvaluationInput) -> TargetPosition | None:
        if self._index >= len(self._scheduled_targets):
            return None
        target = self._scheduled_targets[self._index]
        self._index += 1
        if target is None:
            return None
        return TargetPosition.model_validate(
            {
                "strategy_code": evaluation.session.strategy_code,
                "strategy_version": evaluation.session.strategy_version,
                "target_time": evaluation.bar.bar_time,
                "positions": [
                    {
                        "exchange_code": evaluation.bar.exchange_code,
                        "unified_symbol": evaluation.bar.unified_symbol,
                        "target_qty": str(target),
                    }
                ],
            }
        )


class MarketContextEntryStrategy(StrategyBase):
    strategy_code = "market_context_strategy"
    strategy_version = "v1.0.0"

    def __init__(self) -> None:
        self._has_fired = False

    def evaluate(self, evaluation: StrategyEvaluationInput) -> TargetPosition | None:
        if self._has_fired:
            return None
        market_context = evaluation.market_context
        if market_context is None:
            return None
        ratio_snapshot = market_context.global_long_short_account_ratio
        taker_snapshot = market_context.taker_long_short_ratio
        if ratio_snapshot is None or taker_snapshot is None:
            return None
        if Decimal(str(ratio_snapshot["long_short_ratio"])) < Decimal("1.20"):
            return None
        if Decimal(str(taker_snapshot["buy_sell_ratio"])) < Decimal("1.05"):
            return None
        self._has_fired = True
        return TargetPosition.model_validate(
            {
                "strategy_code": evaluation.session.strategy_code,
                "strategy_version": evaluation.session.strategy_version,
                "target_time": evaluation.bar.bar_time,
                "positions": [
                    {
                        "exchange_code": evaluation.bar.exchange_code,
                        "unified_symbol": evaluation.bar.unified_symbol,
                        "target_qty": "1",
                    }
                ],
            }
        )


class Phase5FoundationTests(unittest.TestCase):
    def test_strategy_session_requires_non_empty_universe_and_dedupes_values(self) -> None:
        with self.assertRaises(ValidationError):
            StrategySessionConfig.model_validate(
                {
                    "session_code": "bt_empty",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": [],
                }
            )

        with self.assertRaises(ValidationError):
            StrategySessionConfig.model_validate(
                {
                    "session_code": "bt_bad_tz",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "trading_timezone": "Mars/Phobos",
                    "universe": ["BTCUSDT_PERP"],
                }
            )

        session = StrategySessionConfig.model_validate(
            {
                "session_code": "bt_btc",
                "environment": "backtest",
                "account_code": "paper_main",
                "strategy_code": "btc_momentum",
                "strategy_version": "v1.0.0",
                "exchange_code": "binance",
                "trading_timezone": "Asia/Taipei",
                "universe": ["BTCUSDT_PERP", "BTCUSDT_PERP", "ETHUSDT_PERP"],
            }
        )

        self.assertEqual(session.universe, ["BTCUSDT_PERP", "ETHUSDT_PERP"])
        self.assertEqual(session.trading_timezone, "Asia/Taipei")

    def test_backtest_run_config_requires_backtest_environment(self) -> None:
        with self.assertRaises(ValidationError):
            BacktestRunConfig.model_validate(
                {
                    "run_name": "invalid_env",
                    "session": {
                        "session_code": "paper_btc",
                        "environment": "paper",
                        "account_code": "paper_main",
                        "strategy_code": "btc_momentum",
                        "strategy_version": "v1.0.0",
                        "exchange_code": "binance",
                        "universe": ["BTCUSDT_PERP"],
                    },
                    "start_time": "2026-04-01T00:00:00Z",
                    "end_time": "2026-04-02T00:00:00Z",
                    "initial_cash": "10000",
                }
            )

    def test_risk_policy_config_validates_thresholds(self) -> None:
        with self.assertRaises(ValidationError):
            RiskPolicyConfig.model_validate({"block_new_entries_below_equity": "-1"})

        with self.assertRaises(ValidationError):
            RiskPolicyConfig.model_validate({"max_position_qty": "0"})

        with self.assertRaises(ValidationError):
            RiskPolicyConfig.model_validate({"max_drawdown_pct": "1.1"})

        with self.assertRaises(ValidationError):
            RiskPolicyConfig.model_validate({"max_daily_loss_pct": "0"})

        with self.assertRaises(ValidationError):
            RiskPolicyConfig.model_validate({"cooldown_bars_after_stop": 0})

        policy = RiskPolicyConfig.model_validate(
            {
                "policy_code": "spot_conservative_v1",
                "block_new_entries_below_equity": "0",
                "max_position_qty": "1",
                "max_order_notional": "10000",
                "max_drawdown_pct": "0.20",
                "max_daily_loss_pct": "0.05",
                "max_leverage": "1.5",
                "cooldown_bars_after_stop": 10,
            }
        )

        self.assertEqual(policy.policy_code, "spot_conservative_v1")
        self.assertEqual(policy.max_position_qty, Decimal("1"))
        self.assertEqual(policy.max_drawdown_pct, Decimal("0.20"))
        self.assertEqual(policy.max_daily_loss_pct, Decimal("0.05"))
        self.assertEqual(policy.max_leverage, Decimal("1.5"))
        self.assertEqual(policy.cooldown_bars_after_stop, 10)

    def test_risk_policy_override_config_and_effective_policy_merge(self) -> None:
        with self.assertRaises(ValidationError):
            RiskPolicyOverrideConfig.model_validate({"max_order_notional": "0"})

        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_risk_override_merge",
                "session": {
                    "session_code": "bt_btc_risk_override_merge",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "perp_medium_v1",
                        "max_position_qty": "1",
                        "max_order_notional": "10000",
                        "metadata": {"source": "session_default"},
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
                "assumption_bundle_code": "baseline_perp_research",
                "assumption_bundle_version": "v1",
                "risk_overrides": {
                    "policy_code": "perp_medium_override_v1",
                    "max_order_notional": "5000",
                    "allow_reduce_only_when_blocked": False,
                    "metadata": {"source": "run_override"},
                },
            }
        )

        effective = run_config.build_effective_risk_policy()

        self.assertEqual(effective.policy_code, "perp_medium_override_v1")
        self.assertEqual(effective.max_position_qty, Decimal("1"))
        self.assertEqual(effective.max_order_notional, Decimal("5000"))
        self.assertFalse(effective.allow_reduce_only_when_blocked)
        self.assertEqual(effective.metadata_json["source"], "run_override")

    def test_named_risk_policy_registry_resolves_session_policy_code(self) -> None:
        registry = build_default_risk_policy_registry()
        policy_codes = [entry.policy_code for entry in registry.list_entries()]

        self.assertIn("default", policy_codes)
        self.assertIn("spot_conservative_v1", policy_codes)
        self.assertIn("perp_medium_v1", policy_codes)

        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_named_session_risk_policy",
                "session": {
                    "session_code": "bt_btc_named_session_risk_policy",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "perp_medium_v1",
                        "max_order_notional": "75000",
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )

        resolved = run_config.resolve_session_risk_policy()

        self.assertEqual(resolved.policy_code, "perp_medium_v1")
        self.assertEqual(resolved.max_position_qty, Decimal("1"))
        self.assertEqual(resolved.max_order_qty, Decimal("1"))
        self.assertEqual(resolved.max_order_notional, Decimal("75000"))
        self.assertEqual(resolved.max_gross_exposure_multiple, Decimal("1.5"))
        self.assertEqual(resolved.max_drawdown_pct, Decimal("0.25"))
        self.assertEqual(resolved.max_daily_loss_pct, Decimal("0.05"))
        self.assertEqual(resolved.max_leverage, Decimal("1.5"))
        self.assertEqual(resolved.cooldown_bars_after_stop, 10)

    def test_named_risk_policy_override_code_can_switch_effective_base_policy(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_named_override_policy",
                "session": {
                    "session_code": "bt_btc_named_override_policy",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "perp_medium_v1",
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
                "risk_overrides": {
                    "policy_code": "perp_aggressive_v1",
                    "max_order_notional": "125000",
                },
            }
        )

        effective = run_config.build_effective_risk_policy()

        self.assertEqual(effective.policy_code, "perp_aggressive_v1")
        self.assertEqual(effective.max_position_qty, Decimal("2"))
        self.assertEqual(effective.max_order_qty, Decimal("2"))
        self.assertEqual(effective.max_order_notional, Decimal("125000"))
        self.assertEqual(effective.max_gross_exposure_multiple, Decimal("3.0"))
        self.assertEqual(effective.max_drawdown_pct, Decimal("0.35"))
        self.assertEqual(effective.max_daily_loss_pct, Decimal("0.08"))
        self.assertEqual(effective.max_leverage, Decimal("3.0"))
        self.assertEqual(effective.cooldown_bars_after_stop, 5)

    def test_named_assumption_bundle_registry_resolves_effective_snapshot(self) -> None:
        registry = build_default_assumption_bundle_registry()
        bundle_keys = {
            (entry.assumption_bundle_code, entry.assumption_bundle_version)
            for entry in registry.list_entries()
        }

        self.assertIn(("baseline_perp_research", "v1"), bundle_keys)
        self.assertIn(("baseline_perp_sentiment_research", "v1"), bundle_keys)
        self.assertIn(("baseline_spot_research", "v1"), bundle_keys)
        self.assertIn(("stress_costs", "v1"), bundle_keys)

        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_assumption_bundle_resolution",
                "session": {
                    "session_code": "bt_btc_assumption_bundle_resolution",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
                "assumption_bundle_code": "baseline_perp_research",
                "slippage_model_version": "fixed_bps_v2",
            }
        )

        effective_assumptions = run_config.build_effective_assumption_snapshot()
        effective_risk = run_config.build_effective_risk_policy()

        self.assertEqual(effective_assumptions.assumption_bundle_code, "baseline_perp_research")
        self.assertEqual(effective_assumptions.assumption_bundle_version, "v1")
        self.assertEqual(effective_assumptions.fill_model_version, "deterministic_bars_v1")
        self.assertEqual(effective_assumptions.feature_input_version, "bars_only_v1")
        self.assertEqual(effective_assumptions.benchmark_set_code, "btc_perp_baseline_v1")
        self.assertEqual(effective_assumptions.slippage_model_version, "fixed_bps_v2")
        self.assertEqual(effective_risk.policy_code, "perp_medium_v1")
        self.assertEqual(effective_risk.max_gross_exposure_multiple, Decimal("1.5"))

        sentiment_run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_assumption_bundle_sentiment_resolution",
                "session": {
                    "session_code": "bt_btc_assumption_bundle_sentiment_resolution",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
                "assumption_bundle_code": "baseline_perp_sentiment_research",
                "assumption_bundle_version": "v1",
            }
        )
        sentiment_assumptions = sentiment_run_config.build_effective_assumption_snapshot()
        self.assertEqual(sentiment_assumptions.feature_input_version, "bars_perp_context_v1")

    def test_default_registry_loads_seeded_example_strategy(self) -> None:
        registry = build_default_registry()
        strategy = registry.create("btc_momentum", "v1.0.0", {"short_window": 3, "long_window": 5, "target_qty": "2"})
        self.assertIsInstance(strategy, MovingAverageCrossStrategy)
        self.assertEqual(strategy.target_qty, Decimal("2"))

        sentiment_strategy = registry.create(
            "btc_sentiment_momentum",
            "v1.0.0",
            {"short_window": 3, "long_window": 5, "target_qty": "2"},
        )
        self.assertIsInstance(sentiment_strategy, SentimentAwareMovingAverageStrategy)
        self.assertEqual(sentiment_strategy.target_qty, Decimal("2"))

        with self.assertRaises(UnknownStrategyError):
            registry.create("unknown_strategy", "v1.0.0")

    def test_example_strategy_emits_target_position_for_uptrend(self) -> None:
        session = StrategySessionConfig.model_validate(
            {
                "session_code": "bt_btc",
                "environment": "backtest",
                "account_code": "paper_main",
                "strategy_code": "btc_momentum",
                "strategy_version": "v1.0.0",
                "exchange_code": "binance",
                "universe": ["BTCUSDT_PERP"],
            }
        )
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_momentum_test",
                "session": session.model_dump(mode="json", by_alias=True),
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        bars = [build_bar("BTCUSDT_PERP", index, str(100 + index)) for index in range(20)]
        strategy = MovingAverageCrossStrategy(short_window=3, long_window=5)

        decision = strategy.evaluate(
            StrategyEvaluationInput(
                session=session,
                run_config=run_config,
                bar=bars[-1],
                recent_bars=bars,
                current_positions={},
                current_cash=Decimal("10000"),
            )
        )

        self.assertIsInstance(decision, TargetPosition)
        self.assertEqual(decision.positions[0].target_qty, Decimal("1"))

    def test_sentiment_strategy_requires_market_context_for_long_entry(self) -> None:
        session = StrategySessionConfig.model_validate(
            {
                "session_code": "bt_btc_sentiment",
                "environment": "backtest",
                "account_code": "paper_main",
                "strategy_code": "btc_sentiment_momentum",
                "strategy_version": "v1.0.0",
                "exchange_code": "binance",
                "universe": ["BTCUSDT_PERP"],
            }
        )
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_sentiment_test",
                "session": session.model_dump(mode="json", by_alias=True),
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
                "feature_input_version": "bars_perp_context_v1",
            }
        )
        bars = [build_bar("BTCUSDT_PERP", index, str(100 + index)) for index in range(20)]
        strategy = SentimentAwareMovingAverageStrategy(short_window=3, long_window=5)

        no_context_decision = strategy.evaluate(
            StrategyEvaluationInput(
                session=session,
                run_config=run_config,
                bar=bars[-1],
                recent_bars=bars,
                current_positions={},
                current_cash=Decimal("10000"),
            )
        )
        self.assertIsNone(no_context_decision)

        context_decision = strategy.evaluate(
            StrategyEvaluationInput(
                session=session,
                run_config=run_config,
                bar=bars[-1],
                recent_bars=bars,
                current_positions={},
                current_cash=Decimal("10000"),
                market_context=StrategyMarketContext(
                    feature_input_version="bars_perp_context_v1",
                    global_long_short_account_ratio={
                        "event_time": bars[-1].bar_time,
                        "period_code": "5m",
                        "long_short_ratio": Decimal("1.50"),
                    },
                    taker_long_short_ratio={
                        "event_time": bars[-1].bar_time,
                        "period_code": "5m",
                        "buy_sell_ratio": Decimal("1.10"),
                    },
                ),
            )
        )

        self.assertIsInstance(context_decision, TargetPosition)
        self.assertEqual(context_decision.positions[0].target_qty, Decimal("1"))

    def test_lifecycle_generates_reduce_only_exit_and_blocks_flip_when_disabled(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_lifecycle",
                "session": {
                    "session_code": "bt_btc",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "execution_policy": {
                        "allow_position_flip": False,
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        lifecycle = BacktestLifecycle(run_config)

        exit_signal = Signal.model_validate(
            {
                "strategy_code": "btc_momentum",
                "strategy_version": "v1.0.0",
                "signal_id": "sig_exit",
                "signal_time": "2026-04-02T00:00:00Z",
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "signal_type": "reduce",
                "direction": "flat",
                "target_qty": "0",
            }
        )

        exit_intents = lifecycle.plan_from_signal(exit_signal, {"BTCUSDT_PERP": Decimal("1")})
        self.assertEqual(len(exit_intents), 1)
        self.assertTrue(exit_intents[0].reduce_only)
        self.assertEqual(exit_intents[0].side, OrderSide.SELL)

        reverse_target = TargetPosition.model_validate(
            {
                "strategy_code": "btc_momentum",
                "strategy_version": "v1.0.0",
                "target_time": "2026-04-02T00:01:00Z",
                "positions": [
                    {
                        "exchange_code": "binance",
                        "unified_symbol": "BTCUSDT_PERP",
                        "target_qty": "-1",
                    }
                ],
            }
        )
        with self.assertRaises(LifecyclePlanningError):
            lifecycle.plan_from_target_position(reverse_target, {"BTCUSDT_PERP": Decimal("1")})

    def test_runner_skeleton_returns_decision_and_execution_intent(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_runner",
                "session": {
                    "session_code": "bt_btc",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
                "strategy_params": {
                    "short_window": 3,
                    "long_window": 5,
                    "target_qty": "1",
                },
            }
        )
        bars = [build_bar("BTCUSDT_PERP", index, str(100 + index)) for index in range(20)]
        runner = BacktestRunnerSkeleton(
            run_config,
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="5.5"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
            ),
        )

        result = runner.evaluate_bar(
            bars[-1],
            bars,
            current_positions={"BTCUSDT_PERP": Decimal("0")},
            current_cash=Decimal("10000"),
        )

        self.assertIsInstance(result.plan.decision, TargetPosition)
        self.assertEqual(len(result.signals), 1)
        self.assertEqual(result.signals[0].signal_type, SignalType.ENTRY)
        self.assertEqual(len(result.plan.execution_intents), 1)
        self.assertEqual(result.plan.execution_intents[0].delta_qty, Decimal("1"))

    def test_target_position_is_normalized_to_canonical_signal(self) -> None:
        target = TargetPosition.model_validate(
            {
                "strategy_code": "btc_momentum",
                "strategy_version": "v1.0.0",
                "target_time": "2026-04-02T00:01:00Z",
                "positions": [
                    {
                        "exchange_code": "binance",
                        "unified_symbol": "BTCUSDT_PERP",
                        "target_qty": "-1",
                    }
                ],
            }
        )

        signals = build_signals_from_target_position(
            target,
            {"BTCUSDT_PERP": Decimal("0")},
            session_code="bt_btc",
        )

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].signal_type, SignalType.ENTRY)
        self.assertEqual(signals[0].direction, "short")
        self.assertEqual(signals[0].target_qty, Decimal("1"))

    def test_runner_loop_generates_signals_over_bar_stream(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_runner_loop",
                "session": {
                    "session_code": "bt_btc",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
                "strategy_params": {
                    "short_window": 3,
                    "long_window": 5,
                    "target_qty": "1",
                },
            }
        )
        bars = [build_bar("BTCUSDT_PERP", index, str(100 + index)) for index in range(20)]
        runner = BacktestRunnerSkeleton(
            run_config,
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="5.5"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
            ),
        )

        result = runner.run_bars(bars)

        generated_signals = [signal for step in result.steps for signal in step.signals]
        self.assertGreaterEqual(len(generated_signals), 1)
        self.assertEqual(generated_signals[0].unified_symbol, "BTCUSDT_PERP")
        self.assertEqual(result.final_positions["BTCUSDT_PERP"], Decimal("1"))
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.fills[0].fill_price, bars[5].open + Decimal("0.0105"))

    def test_runner_load_and_run_surfaces_perp_market_context_to_strategy(self) -> None:
        start_time = datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2026, 4, 1, 0, 5, tzinfo=timezone.utc)
        self.addCleanup(
            _cleanup_strategy_market_context_window,
            start_time=start_time,
            end_time=end_time,
        )
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_runner_context",
                "session": {
                    "session_code": "bt_btc_context",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "market_context_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "initial_cash": "10000",
                "feature_input_version": "bars_perp_context_v1",
            }
        )

        with transaction_scope() as connection:
            connection.execute(
                text(
                    """
                    delete from md.taker_long_short_ratios
                    where instrument_id = (
                        select instrument.instrument_id
                        from ref.instruments instrument
                        join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                        where exchange.exchange_code = :exchange_code
                          and instrument.unified_symbol = :unified_symbol
                        limit 1
                    )
                      and ts between :start_time and :end_time
                    """
                ),
                {
                    "exchange_code": "binance",
                    "unified_symbol": "BTCUSDT_PERP",
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )
            connection.execute(
                text(
                    """
                    delete from md.global_long_short_account_ratios
                    where instrument_id = (
                        select instrument.instrument_id
                        from ref.instruments instrument
                        join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                        where exchange.exchange_code = :exchange_code
                          and instrument.unified_symbol = :unified_symbol
                        limit 1
                    )
                      and ts between :start_time and :end_time
                    """
                ),
                {
                    "exchange_code": "binance",
                    "unified_symbol": "BTCUSDT_PERP",
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )
            connection.execute(
                text(
                    """
                    delete from md.bars_1m
                    where instrument_id = (
                        select instrument.instrument_id
                        from ref.instruments instrument
                        join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                        where exchange.exchange_code = :exchange_code
                          and instrument.unified_symbol = :unified_symbol
                        limit 1
                    )
                      and bar_time between :start_time and :end_time
                    """
                ),
                {
                    "exchange_code": "binance",
                    "unified_symbol": "BTCUSDT_PERP",
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )

            bar_repo = BarRepository()
            for index in range(5):
                bar_time = start_time + timedelta(minutes=index)
                close = Decimal("100") + Decimal(index)
                bar_repo.upsert(
                    connection,
                    BarEvent.model_validate(
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                            "bar_interval": "1m",
                            "bar_time": bar_time.isoformat(),
                            "event_time": bar_time.isoformat(),
                            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                            "open": str(close),
                            "high": str(close),
                            "low": str(close),
                            "close": str(close),
                            "volume": "10",
                        }
                    ),
                )

            GlobalLongShortAccountRatioRepository().upsert(
                connection,
                GlobalLongShortAccountRatioEvent(
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    ingest_time=start_time + timedelta(minutes=2),
                    event_time=start_time + timedelta(minutes=2),
                    period_code="5m",
                    long_short_ratio=Decimal("1.30"),
                    long_account_ratio=Decimal("0.56"),
                    short_account_ratio=Decimal("0.44"),
                ),
            )
            TakerLongShortRatioRepository().upsert(
                connection,
                TakerLongShortRatioEvent(
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    ingest_time=start_time + timedelta(minutes=2),
                    event_time=start_time + timedelta(minutes=2),
                    period_code="5m",
                    buy_sell_ratio=Decimal("1.08"),
                    buy_vol=Decimal("125"),
                    sell_vol=Decimal("116"),
                ),
            )

            runner = BacktestRunnerSkeleton(
                run_config,
                strategy=MarketContextEntryStrategy(),
                fill_model=DeterministicBarsFillModel(
                    fee_model=StaticFeeModel(taker_fee_bps="5.5"),
                    slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
                ),
            )
            result = runner.load_and_run(connection)

        generated_signals = [signal for step in result.steps for signal in step.signals]
        self.assertEqual(len(generated_signals), 1)
        self.assertEqual(generated_signals[0].signal_time, start_time + timedelta(minutes=2))
        self.assertEqual(result.final_positions["BTCUSDT_PERP"], Decimal("1"))
        self.assertEqual(len(result.fills), 1)

    def test_runner_blocks_new_entries_when_equity_floor_is_breached(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_runner_risk_floor",
                "session": {
                    "session_code": "bt_btc_risk_floor",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "equity_floor_v1",
                        "block_new_entries_below_equity": "0",
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        bars = [build_bar("BTCUSDT_PERP", 0, "100"), build_bar("BTCUSDT_PERP", 1, "105")]
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="1"),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="4.5"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
            ),
        )

        result = runner.run_bars(bars, initial_cash=Decimal("0"))

        self.assertEqual(len(result.orders), 0)
        self.assertEqual(len(result.fills), 0)
        self.assertEqual(result.risk_outcomes[0].decision, RiskDecision.BLOCK)
        self.assertEqual(result.risk_outcomes[0].code, "equity_floor_breach")

    def test_runner_blocks_spot_buys_when_cash_is_insufficient(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_spot_cash_guard",
                "session": {
                    "session_code": "bt_btc_spot_guard",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_SPOT"],
                    "risk_policy": {
                        "policy_code": "spot_cash_guard_v1",
                        "enforce_spot_cash_check": True,
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        bars = [build_bar("BTCUSDT_SPOT", 0, "100"), build_bar("BTCUSDT_SPOT", 1, "101")]
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="1"),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="7.5"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
            ),
        )

        result = runner.run_bars(bars, initial_cash=Decimal("50"))

        self.assertEqual(len(result.orders), 0)
        self.assertEqual(result.risk_outcomes[0].decision, RiskDecision.BLOCK)
        self.assertEqual(result.risk_outcomes[0].code, "spot_cash_insufficient")

    def test_reduce_only_exit_can_bypass_position_limit(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_reduce_only_bypass",
                "session": {
                    "session_code": "bt_btc_reduce_only",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "perp_size_limit_v1",
                        "max_position_qty": "0.5",
                        "allow_reduce_only_when_blocked": True,
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        bars = [build_bar("BTCUSDT_PERP", 0, "100"), build_bar("BTCUSDT_PERP", 1, "101")]
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="1"),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="4.5"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
            ),
        )

        result = runner.run_bars(
            bars,
            initial_positions={"BTCUSDT_PERP": Decimal("2")},
            initial_cash=Decimal("0"),
        )

        self.assertEqual(len(result.orders), 1)
        self.assertEqual(result.risk_outcomes[0].decision, RiskDecision.ALLOW)
        self.assertEqual(result.risk_outcomes[0].code, "allowed_reduce_only_bypass")
        self.assertEqual(result.final_positions["BTCUSDT_PERP"], Decimal("1"))

    def test_runner_blocks_entries_exceeding_max_gross_exposure_multiple(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_gross_exposure_guard",
                "session": {
                    "session_code": "bt_btc_gross_guard",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "perp_gross_guard_v1",
                        "max_gross_exposure_multiple": "1",
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        bars = [build_bar("BTCUSDT_PERP", 0, "100"), build_bar("BTCUSDT_PERP", 1, "101")]
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="2"),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="4.5"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
            ),
        )

        result = runner.run_bars(bars, initial_cash=Decimal("100"))

        self.assertEqual(len(result.orders), 0)
        self.assertEqual(result.risk_outcomes[0].code, "max_gross_exposure_breach")

    def test_runner_blocks_new_entries_when_max_drawdown_pct_is_breached(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_drawdown_guard",
                "session": {
                    "session_code": "bt_btc_drawdown_guard",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "drawdown_guard_v1",
                        "max_drawdown_pct": "0.20",
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "100",
            }
        )
        bars = [build_bar("BTCUSDT_PERP", 0, "100"), build_bar("BTCUSDT_PERP", 1, "50")]
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=ScheduledTargetStrategy([None, "2"]),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="0"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="0"),
            ),
        )

        result = runner.run_bars(
            bars,
            initial_positions={"BTCUSDT_PERP": Decimal("1")},
            initial_cash=Decimal("100"),
        )

        self.assertEqual(len(result.orders), 0)
        self.assertEqual(result.risk_outcomes[-1].decision, RiskDecision.BLOCK)
        self.assertEqual(result.risk_outcomes[-1].code, "max_drawdown_pct_breach")

    def test_runner_blocks_new_entries_when_max_daily_loss_pct_is_breached(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_daily_loss_guard",
                "session": {
                    "session_code": "bt_btc_daily_loss_guard",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "daily_loss_guard_v1",
                        "max_daily_loss_pct": "0.20",
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "100",
            }
        )
        bars = [build_bar("BTCUSDT_PERP", 0, "100"), build_bar("BTCUSDT_PERP", 1, "50")]
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=ScheduledTargetStrategy([None, "2"]),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="0"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="0"),
            ),
        )

        result = runner.run_bars(
            bars,
            initial_positions={"BTCUSDT_PERP": Decimal("1")},
            initial_cash=Decimal("100"),
        )

        self.assertEqual(len(result.orders), 0)
        self.assertEqual(result.risk_outcomes[-1].decision, RiskDecision.BLOCK)
        self.assertEqual(result.risk_outcomes[-1].code, "max_daily_loss_pct_breach")

    def test_runner_uses_session_trading_timezone_for_daily_loss_boundaries(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_daily_loss_timezone_guard",
                "session": {
                    "session_code": "bt_btc_daily_loss_timezone_guard",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "trading_timezone": "Asia/Taipei",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "daily_loss_guard_tz_v1",
                        "max_daily_loss_pct": "0.20",
                    },
                },
                "start_time": "2026-04-01T15:59:00Z",
                "end_time": "2026-04-01T16:01:00Z",
                "initial_cash": "100",
            }
        )
        bars = [
            build_bar_at("BTCUSDT_PERP", datetime(2026, 4, 1, 15, 59, tzinfo=timezone.utc), "100"),
            build_bar_at("BTCUSDT_PERP", datetime(2026, 4, 1, 16, 0, tzinfo=timezone.utc), "50"),
        ]
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=ScheduledTargetStrategy([None, "2"]),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="0"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="0"),
            ),
        )

        result = runner.run_bars(
            bars,
            initial_positions={"BTCUSDT_PERP": Decimal("1")},
            initial_cash=Decimal("100"),
        )

        self.assertEqual(len(result.orders), 1)
        self.assertEqual(result.risk_outcomes[-1].decision, RiskDecision.ALLOW)
        self.assertEqual(
            runner.risk_guardrails.build_runtime_state_snapshot()["active_trading_day"],
            "2026-04-02",
        )

    def test_runner_blocks_entries_exceeding_max_leverage(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_leverage_guard",
                "session": {
                    "session_code": "bt_btc_leverage_guard",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "leverage_guard_v1",
                        "max_leverage": "1.5",
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "100",
            }
        )
        bars = [build_bar("BTCUSDT_PERP", 0, "100"), build_bar("BTCUSDT_PERP", 1, "101")]
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="2"),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="0"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="0"),
            ),
        )

        result = runner.run_bars(bars, initial_cash=Decimal("100"))

        self.assertEqual(len(result.orders), 0)
        self.assertEqual(result.risk_outcomes[-1].decision, RiskDecision.BLOCK)
        self.assertEqual(result.risk_outcomes[-1].code, "max_leverage_breach")

    def test_runner_activates_cooldown_after_losing_close_and_blocks_reentry(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_cooldown_guard",
                "session": {
                    "session_code": "bt_btc_cooldown_guard",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "cooldown_guard_v1",
                        "cooldown_bars_after_stop": 2,
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "100",
            }
        )
        bars = [
            build_bar("BTCUSDT_PERP", 0, "100"),
            build_bar("BTCUSDT_PERP", 1, "90"),
            build_bar("BTCUSDT_PERP", 2, "80"),
        ]
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=ScheduledTargetStrategy([None, "0", "1"]),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="0"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="0"),
            ),
        )

        result = runner.run_bars(
            bars,
            initial_positions={"BTCUSDT_PERP": Decimal("1")},
            initial_cash=Decimal("100"),
        )

        self.assertEqual(len(result.orders), 1)
        self.assertEqual(result.fills[0].fill_price, Decimal("80"))
        self.assertEqual(result.risk_outcomes[-1].decision, RiskDecision.BLOCK)
        self.assertEqual(result.risk_outcomes[-1].code, "cooldown_active")
        runtime_state = runner.risk_guardrails.build_runtime_state_snapshot()
        self.assertEqual(runtime_state["activation_counts_by_code"]["cooldown_activated_after_loss_close"], 1)

    def test_runner_caps_recent_bar_history_when_strategy_declares_requirement(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_runner_history_cap",
                "session": {
                    "session_code": "bt_btc",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "history_bound_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        bars = [build_bar("BTCUSDT_PERP", index, str(100 + index)) for index in range(10)]
        runner = BacktestRunnerSkeleton(run_config, strategy=HistoryBoundAssertionStrategy())

        result = runner.run_bars(bars)

        self.assertEqual(result.final_positions, {})

    def test_market_fill_model_fills_on_next_bar_open_with_fee_and_slippage(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_market_fill",
                "session": {
                    "session_code": "bt_btc",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        bars = [
            build_bar("BTCUSDT_PERP", 0, "100"),
            build_bar("BTCUSDT_PERP", 1, "105"),
        ]
        fill_model = DeterministicBarsFillModel(
            fee_model=StaticFeeModel(taker_fee_bps="5.5"),
            slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
        )
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="1"),
            fill_model=fill_model,
        )

        result = runner.run_bars(bars)

        self.assertEqual(len(result.orders), 1)
        self.assertEqual(len(result.fills), 1)
        self.assertEqual(result.orders[0].status, "filled")
        self.assertEqual(result.orders[0].order_type, OrderType.MARKET)
        self.assertEqual(result.fills[0].fill_price, Decimal("105.0105"))
        self.assertEqual(result.fills[0].slippage_cost, Decimal("0.0105"))
        self.assertEqual(result.fills[0].fee.quantize(Decimal("0.00000001")), Decimal("0.05775578"))
        self.assertEqual(result.final_positions["BTCUSDT_PERP"], Decimal("1"))

    def test_limit_fill_model_requires_price_touch(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_limit_fill",
                "session": {
                    "session_code": "bt_btc",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "test_strategy",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "execution_policy": {
                        "order_type_preference": "limit",
                    },
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        first_bar = BarEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "bar_interval": "1m",
                "bar_time": "2026-04-01T00:00:00Z",
                "event_time": "2026-04-01T00:00:00Z",
                "ingest_time": "2026-04-01T00:00:01Z",
                "open": "100",
                "high": "100",
                "low": "100",
                "close": "100",
                "volume": "10",
            }
        )
        touched_bar = BarEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "bar_interval": "1m",
                "bar_time": "2026-04-01T00:01:00Z",
                "event_time": "2026-04-01T00:01:00Z",
                "ingest_time": "2026-04-01T00:01:01Z",
                "open": "101",
                "high": "102",
                "low": "99",
                "close": "101",
                "volume": "10",
            }
        )
        untouched_bar = BarEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "bar_interval": "1m",
                "bar_time": "2026-04-01T00:01:00Z",
                "event_time": "2026-04-01T00:01:00Z",
                "ingest_time": "2026-04-01T00:01:01Z",
                "open": "101",
                "high": "102",
                "low": "100.5",
                "close": "101",
                "volume": "10",
            }
        )

        fill_model = DeterministicBarsFillModel(
            fee_model=StaticFeeModel(maker_fee_bps="2"),
            slippage_model=FixedBpsSlippageModel(market_order_bps="0", limit_order_bps="0"),
        )
        runner_touched = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="1"),
            fill_model=fill_model,
        )
        touched_result = runner_touched.run_bars([first_bar, touched_bar])

        self.assertEqual(len(touched_result.fills), 1)
        self.assertEqual(touched_result.orders[0].order_type, OrderType.LIMIT)
        self.assertEqual(touched_result.fills[0].fill_price, Decimal("100"))
        self.assertEqual(touched_result.fills[0].fee, Decimal("0.02"))

        runner_untouched = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="1"),
            fill_model=fill_model,
        )
        untouched_result = runner_untouched.run_bars([first_bar, untouched_bar])

        self.assertEqual(len(untouched_result.fills), 0)
        self.assertEqual(len(untouched_result.open_orders), 1)
        self.assertEqual(untouched_result.open_orders[0].status, "expired")
        self.assertEqual(untouched_result.final_positions, {})

    def test_portfolio_state_tracks_equity_and_realized_pnl(self) -> None:
        portfolio = PortfolioState(cash=Decimal("1000"))
        portfolio.apply_fill(
            SimulatedFill(
                fill_id="fill_buy",
                order_id="order_buy",
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                fill_time=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
                side=OrderSide.BUY,
                liquidity_flag=LiquidityFlag.TAKER,
                reference_price=Decimal("100"),
                fill_price=Decimal("100"),
                qty=Decimal("1"),
                fee=Decimal("1"),
                slippage_cost=Decimal("0.5"),
            )
        )
        mark_after_entry = portfolio.mark_to_market({"BTCUSDT_PERP": Decimal("105")})
        self.assertEqual(mark_after_entry.equity, Decimal("1004"))
        self.assertEqual(mark_after_entry.unrealized_pnl, Decimal("5"))

        portfolio.apply_fill(
            SimulatedFill(
                fill_id="fill_sell",
                order_id="order_sell",
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                fill_time=datetime(2026, 4, 1, 0, 1, tzinfo=timezone.utc),
                side=OrderSide.SELL,
                liquidity_flag=LiquidityFlag.TAKER,
                reference_price=Decimal("110"),
                fill_price=Decimal("110"),
                qty=Decimal("1"),
                fee=Decimal("1"),
                slippage_cost=Decimal("0.5"),
            )
        )
        mark_after_exit = portfolio.mark_to_market({})
        self.assertEqual(mark_after_exit.realized_pnl, Decimal("10"))
        self.assertEqual(mark_after_exit.equity, Decimal("1008"))
        self.assertEqual(portfolio.positions, {})

    def test_load_run_and_persist_populates_backtest_tables(self) -> None:
        run_start = datetime(2036, 1, 1, 0, 0, tzinfo=timezone.utc)
        bars = [
            build_bar_at("BTCUSDT_PERP", run_start + timedelta(minutes=offset), close)
            for offset, close in enumerate(["100", "105", "110"])
        ]
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_runner_persist",
                "session": {
                    "session_code": "bt_btc_persist",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": run_start.isoformat(),
                "end_time": (run_start + timedelta(minutes=3)).isoformat(),
                "initial_cash": "10000",
                "strategy_params": {
                    "target_qty": "1",
                },
            }
        )
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="1"),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="5.5"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
            ),
        )
        bar_repository = BarRepository()
        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            for bar in bars:
                bar_repository.upsert(connection, bar)

            persisted = runner.load_run_and_persist(connection)

            order_count = connection.execute(
                text("select count(*) from backtest.simulated_orders where run_id = :run_id"),
                {"run_id": persisted.run_id},
            ).scalar_one()
            fill_count = connection.execute(
                text("select count(*) from backtest.simulated_fills where run_id = :run_id"),
                {"run_id": persisted.run_id},
            ).scalar_one()
            timeseries_count = connection.execute(
                text("select count(*) from backtest.performance_timeseries where run_id = :run_id"),
                {"run_id": persisted.run_id},
            ).scalar_one()
            summary_row = connection.execute(
                text(
                    """
                    select total_return, fee_cost, slippage_cost
                    from backtest.performance_summary
                    where run_id = :run_id
                    """
                ),
                {"run_id": persisted.run_id},
            ).mappings().one()
            run_row = connection.execute(
                text(
                    """
                    select params_json
                    from backtest.runs
                    where run_id = :run_id
                    """
                ),
                {"run_id": persisted.run_id},
            ).mappings().one()
            signal_link_count = connection.execute(
                text(
                    """
                    select count(*)
                    from backtest.simulated_orders
                    where run_id = :run_id
                      and signal_id is not null
                    """
                ),
                {"run_id": persisted.run_id},
            ).scalar_one()
            diagnostics = BacktestDiagnosticsProjector().build_summary(connection, persisted.run_id)
            artifact_bundle = BacktestArtifactCatalogProjector().build(connection, run_id=persisted.run_id)

            self.assertGreater(persisted.run_id, 0)
            self.assertEqual(persisted.loop_result.steps, [])
            self.assertEqual(order_count, 1)
            self.assertEqual(fill_count, 1)
            self.assertEqual(timeseries_count, 3)
            self.assertEqual(signal_link_count, 1)
            self.assertIsNotNone(summary_row["total_return"])
            self.assertEqual(Decimal(summary_row["fee_cost"]), persisted.loop_result.performance_summary.fee_cost)
            self.assertEqual(Decimal(summary_row["slippage_cost"]), persisted.loop_result.performance_summary.slippage_cost)
            params_json = run_row["params_json"] or {}
            self.assertEqual(params_json["risk_policy"]["policy_code"], "default")
            self.assertEqual(params_json["session_risk_policy"]["policy_code"], "default")
            self.assertEqual(params_json["risk_overrides"], {})
            self.assertIn("state_snapshot", params_json["runtime_metadata"]["risk_summary"])
            self.assertIsNotNone(diagnostics)
            assert diagnostics is not None
            self.assertEqual(diagnostics.diagnostic_status, "ok")
            self.assertEqual(diagnostics.execution_summary.simulated_order_count, 1)
            self.assertEqual(diagnostics.execution_summary.blocked_intent_count, 0)
            self.assertEqual(diagnostics.strategy_activity.signal_count, 1)
            self.assertIsNotNone(artifact_bundle)
            assert artifact_bundle is not None
            self.assertEqual(artifact_bundle.artifacts[0].artifact_type, "run_metadata")
        finally:
            transaction.rollback()
            connection.close()

    def test_load_run_and_persist_can_persist_compact_debug_traces(self) -> None:
        run_start = datetime(2036, 1, 2, 0, 0, tzinfo=timezone.utc)
        bars = [
            build_bar_at("BTCUSDT_PERP", run_start + timedelta(minutes=offset), close)
            for offset, close in enumerate(["100", "105", "110"])
        ]
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_runner_debug_traces",
                "session": {
                    "session_code": "bt_btc_debug_traces",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": run_start.isoformat(),
                "end_time": (run_start + timedelta(minutes=3)).isoformat(),
                "initial_cash": "10000",
                "strategy_params": {"target_qty": "1"},
            }
        )
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="1"),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="5.5"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
            ),
        )
        bar_repository = BarRepository()
        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            for bar in bars:
                bar_repository.upsert(connection, bar)

            persisted = runner.load_run_and_persist(
                connection,
                persist_signals=False,
                persist_debug_traces=True,
            )

            debug_trace_rows = connection.execute(
                text(
                    """
                    select
                        step_index,
                        bar_time,
                        signal_count,
                        intent_count,
                        blocked_intent_count,
                        blocked_codes_json,
                        created_order_count,
                        sim_order_ids_json,
                        fill_count,
                        sim_fill_ids_json,
                        close_price,
                        current_position_qty,
                        position_qty_delta,
                        cash,
                        cash_delta,
                        equity,
                        equity_delta,
                        gross_exposure,
                        net_exposure,
                        decision_json,
                        risk_outcomes_json
                    from backtest.debug_traces
                    where run_id = :run_id
                    order by step_index asc
                    """
                ),
                {"run_id": persisted.run_id},
            ).mappings().all()
            artifact_bundle = BacktestArtifactCatalogProjector().build(connection, run_id=persisted.run_id)
            repository = BacktestRunRepository()
            signal_only_rows = repository.list_debug_trace_records(
                connection,
                run_id=persisted.run_id,
                signals_only=True,
            )
            order_only_rows = repository.list_debug_trace_records(
                connection,
                run_id=persisted.run_id,
                orders_only=True,
            )
            fill_only_rows = repository.list_debug_trace_records(
                connection,
                run_id=persisted.run_id,
                fills_only=True,
            )

            self.assertEqual(len(persisted.loop_result.debug_traces), 3)
            self.assertEqual(len(debug_trace_rows), 3)
            self.assertEqual(debug_trace_rows[0]["step_index"], 1)
            self.assertEqual(debug_trace_rows[0]["signal_count"], 1)
            self.assertEqual(debug_trace_rows[0]["intent_count"], 1)
            self.assertEqual(debug_trace_rows[0]["blocked_intent_count"], 0)
            self.assertEqual(debug_trace_rows[0]["created_order_count"], 1)
            self.assertEqual(debug_trace_rows[0]["fill_count"], 0)
            self.assertEqual(Decimal(debug_trace_rows[0]["close_price"]), Decimal("100"))
            self.assertEqual(Decimal(debug_trace_rows[0]["current_position_qty"]), Decimal("0"))
            self.assertEqual(Decimal(debug_trace_rows[0]["position_qty_delta"]), Decimal("0"))
            self.assertEqual(Decimal(debug_trace_rows[0]["cash_delta"]), Decimal("0"))
            self.assertEqual(Decimal(debug_trace_rows[0]["equity_delta"]), Decimal("0"))
            self.assertEqual(Decimal(debug_trace_rows[0]["gross_exposure"]), Decimal("0"))
            self.assertEqual(Decimal(debug_trace_rows[0]["net_exposure"]), Decimal("0"))
            self.assertEqual(debug_trace_rows[0]["blocked_codes_json"], [])
            self.assertEqual(len(debug_trace_rows[0]["sim_order_ids_json"]), 1)
            self.assertEqual(debug_trace_rows[0]["sim_fill_ids_json"], [])
            self.assertEqual(debug_trace_rows[0]["decision_json"]["decision_type"], "target_position")
            self.assertEqual(
                debug_trace_rows[0]["decision_json"]["execution_intents"][0]["delta_qty"],
                "1",
            )
            self.assertEqual(debug_trace_rows[0]["risk_outcomes_json"][0]["code"], "allowed")
            self.assertEqual(Decimal(debug_trace_rows[1]["current_position_qty"]), Decimal("1"))
            self.assertEqual(Decimal(debug_trace_rows[1]["position_qty_delta"]), Decimal("1"))
            self.assertEqual(len(debug_trace_rows[1]["sim_fill_ids_json"]), 1)
            self.assertLess(Decimal(debug_trace_rows[1]["cash_delta"]), Decimal("0"))
            self.assertLess(Decimal(debug_trace_rows[1]["equity_delta"]), Decimal("0"))
            self.assertEqual(Decimal(debug_trace_rows[1]["gross_exposure"]), Decimal("105"))
            self.assertEqual(Decimal(debug_trace_rows[1]["net_exposure"]), Decimal("105"))
            self.assertEqual([row["step_index"] for row in signal_only_rows], [1])
            self.assertEqual([row["step_index"] for row in order_only_rows], [1])
            self.assertEqual([row["step_index"] for row in fill_only_rows], [2])
            assert artifact_bundle is not None
            debug_trace_artifact = next(
                artifact for artifact in artifact_bundle.artifacts if artifact.artifact_type == "debug_traces"
            )
            self.assertEqual(debug_trace_artifact.status, "available")
            self.assertEqual(debug_trace_artifact.record_count, 3)
        finally:
            transaction.rollback()
            connection.close()

    def test_load_run_and_persist_can_persist_market_context_snapshot(self) -> None:
        start_time = datetime(2036, 1, 4, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2036, 1, 4, 0, 5, tzinfo=timezone.utc)
        self.addCleanup(
            _cleanup_strategy_market_context_window,
            start_time=start_time,
            end_time=end_time,
        )
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_runner_market_context_trace",
                "session": {
                    "session_code": "bt_btc_context_trace",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "initial_cash": "10000",
                "feature_input_version": "bars_perp_context_v1",
            }
        )
        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            for table_name, time_column in (
                ("md.taker_long_short_ratios", "ts"),
                ("md.global_long_short_account_ratios", "ts"),
                ("md.bars_1m", "bar_time"),
            ):
                connection.execute(
                    text(
                        f"""
                        delete from {table_name}
                        where instrument_id = (
                            select instrument.instrument_id
                            from ref.instruments instrument
                            join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                            where exchange.exchange_code = :exchange_code
                              and instrument.unified_symbol = :unified_symbol
                            limit 1
                        )
                          and {time_column} between :start_time and :end_time
                        """
                    ),
                    {
                        "exchange_code": "binance",
                        "unified_symbol": "BTCUSDT_PERP",
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )

            bar_repo = BarRepository()
            for index in range(5):
                bar_time = start_time + timedelta(minutes=index)
                close = Decimal("100") + Decimal(index)
                bar_repo.upsert(
                    connection,
                    BarEvent.model_validate(
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                            "bar_interval": "1m",
                            "bar_time": bar_time.isoformat(),
                            "event_time": bar_time.isoformat(),
                            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                            "open": str(close),
                            "high": str(close),
                            "low": str(close),
                            "close": str(close),
                            "volume": "10",
                        }
                    ),
                )

            GlobalLongShortAccountRatioRepository().upsert(
                connection,
                GlobalLongShortAccountRatioEvent(
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    ingest_time=start_time + timedelta(minutes=2),
                    event_time=start_time + timedelta(minutes=2),
                    period_code="5m",
                    long_short_ratio=Decimal("1.30"),
                    long_account_ratio=Decimal("0.56"),
                    short_account_ratio=Decimal("0.44"),
                ),
            )
            TakerLongShortRatioRepository().upsert(
                connection,
                TakerLongShortRatioEvent(
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    ingest_time=start_time + timedelta(minutes=2),
                    event_time=start_time + timedelta(minutes=2),
                    period_code="5m",
                    buy_sell_ratio=Decimal("1.08"),
                    buy_vol=Decimal("125"),
                    sell_vol=Decimal("116"),
                ),
            )

            runner = BacktestRunnerSkeleton(
                run_config,
                strategy=MarketContextEntryStrategy(),
                fill_model=DeterministicBarsFillModel(
                    fee_model=StaticFeeModel(taker_fee_bps="5.5"),
                    slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
                ),
            )
            persisted = runner.load_run_and_persist(
                connection,
                persist_signals=False,
                persist_debug_traces=True,
            )

            debug_trace_rows = connection.execute(
                text(
                    """
                    select step_index, market_context_json
                    from backtest.debug_traces
                    where run_id = :run_id
                    order by step_index asc
                    """
                ),
                {"run_id": persisted.run_id},
            ).mappings().all()
            repository = BacktestRunRepository()
            listed_rows = repository.list_debug_trace_records(connection, run_id=persisted.run_id)

            self.assertEqual(len(debug_trace_rows), 5)
            self.assertEqual(
                debug_trace_rows[2]["market_context_json"]["feature_input_version"],
                "bars_perp_context_v1",
            )
            self.assertEqual(
                Decimal(
                    debug_trace_rows[2]["market_context_json"]["global_long_short_account_ratio"][
                        "long_short_ratio"
                    ]
                ),
                Decimal("1.30"),
            )
            self.assertEqual(
                Decimal(debug_trace_rows[2]["market_context_json"]["taker_long_short_ratio"]["buy_sell_ratio"]),
                Decimal("1.08"),
            )
            self.assertEqual(
                debug_trace_rows[2]["market_context_json"]["global_long_short_account_ratio"]["event_time"],
                (start_time + timedelta(minutes=2)).isoformat(),
            )
            self.assertEqual(
                listed_rows[2]["market_context_json"]["taker_long_short_ratio"]["period_code"],
                "5m",
            )
        finally:
            transaction.rollback()
            connection.close()

    def test_diagnostics_summary_projects_trace_anchors_for_blocked_codes(self) -> None:
        run_start = datetime(2036, 1, 3, 0, 0, tzinfo=timezone.utc)
        bars = [
            build_bar_at("BTCUSDT_PERP", run_start + timedelta(minutes=offset), close)
            for offset, close in enumerate(["100", "101"])
        ]
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_diagnostics_trace_anchor",
                "session": {
                    "session_code": "bt_btc_diag_anchor",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                    "risk_policy": {
                        "policy_code": "diag_anchor_guard_v1",
                        "max_gross_exposure_multiple": "1",
                    },
                },
                "start_time": run_start.isoformat(),
                "end_time": (run_start + timedelta(minutes=2)).isoformat(),
                "initial_cash": "100",
            }
        )
        runner = BacktestRunnerSkeleton(
            run_config,
            strategy=OneShotTargetStrategy(target_qty="2"),
            fill_model=DeterministicBarsFillModel(
                fee_model=StaticFeeModel(taker_fee_bps="4.5"),
                slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
            ),
        )
        bar_repository = BarRepository()
        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            for bar in bars:
                bar_repository.upsert(connection, bar)

            persisted = runner.load_run_and_persist(connection, persist_debug_traces=True)
            diagnostics = BacktestDiagnosticsProjector().build_summary(connection, persisted.run_id)
            repository = BacktestRunRepository()

            self.assertIsNotNone(diagnostics)
            assert diagnostics is not None
            anchor_codes = {anchor.source_code for anchor in diagnostics.trace_anchors}
            self.assertIn("risk_blocks_present", anchor_codes)
            self.assertIn("max_gross_exposure_breach", anchor_codes)
            overall_anchor = next(
                anchor for anchor in diagnostics.trace_anchors if anchor.source_code == "risk_blocks_present"
            )
            self.assertEqual(overall_anchor.anchor_type, "step")
            self.assertEqual(overall_anchor.step_index, 1)
            self.assertEqual(overall_anchor.unified_symbol, "BTCUSDT_PERP")
            self.assertIsNotNone(overall_anchor.bar_time_from)
            self.assertIsNotNone(overall_anchor.bar_time_to)
            blocked_rows = repository.list_debug_trace_records(
                connection,
                run_id=persisted.run_id,
                blocked_only=True,
            )
            risk_code_rows = repository.list_debug_trace_records(
                connection,
                run_id=persisted.run_id,
                risk_code="max_gross_exposure_breach",
            )
            self.assertEqual([row["step_index"] for row in blocked_rows], [1])
            self.assertEqual([row["step_index"] for row in risk_code_rows], [1])
        finally:
            transaction.rollback()
            connection.close()

    def test_period_breakdown_supports_month_quarter_and_year(self) -> None:
        points = [
            PerformancePoint(
                ts=datetime(2026, 1, 31, 23, 59, tzinfo=timezone.utc),
                cash=Decimal("1000"),
                equity=Decimal("1010"),
                gross_exposure=Decimal("0"),
                net_exposure=Decimal("0"),
                realized_pnl=Decimal("10"),
                unrealized_pnl=Decimal("0"),
                fee_cost=Decimal("1"),
                slippage_cost=Decimal("0.5"),
                turnover_notional=Decimal("100"),
                drawdown=Decimal("0"),
            ),
            PerformancePoint(
                ts=datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
                cash=Decimal("1000"),
                equity=Decimal("1025"),
                gross_exposure=Decimal("0"),
                net_exposure=Decimal("0"),
                realized_pnl=Decimal("25"),
                unrealized_pnl=Decimal("0"),
                fee_cost=Decimal("2"),
                slippage_cost=Decimal("0.5"),
                turnover_notional=Decimal("200"),
                drawdown=Decimal("0"),
            ),
            PerformancePoint(
                ts=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
                cash=Decimal("1000"),
                equity=Decimal("1030"),
                gross_exposure=Decimal("0"),
                net_exposure=Decimal("0"),
                realized_pnl=Decimal("30"),
                unrealized_pnl=Decimal("0"),
                fee_cost=Decimal("3"),
                slippage_cost=Decimal("1.0"),
                turnover_notional=Decimal("300"),
                drawdown=Decimal("0"),
            ),
        ]
        fill_records = [
            {"fill_time": points[0].ts, "price": Decimal("100"), "qty": Decimal("1"), "fee": Decimal("1"), "slippage_cost": Decimal("0.5")},
            {"fill_time": points[1].ts, "price": Decimal("110"), "qty": Decimal("1"), "fee": Decimal("1"), "slippage_cost": Decimal("0")},
            {"fill_time": points[2].ts, "price": Decimal("120"), "qty": Decimal("1"), "fee": Decimal("1"), "slippage_cost": Decimal("0.5")},
        ]
        signal_records = [
            {"signal_time": points[0].ts, "signal_type": "entry"},
            {"signal_time": points[1].ts, "signal_type": "reduce"},
            {"signal_time": points[2].ts, "signal_type": "rebalance"},
        ]

        monthly = build_period_breakdown(
            performance_points=points,
            fill_records=fill_records,
            signal_records=signal_records,
            initial_cash=Decimal("1000"),
            period_type="month",
        )
        quarterly = build_period_breakdown(
            performance_points=points,
            fill_records=fill_records,
            signal_records=signal_records,
            initial_cash=Decimal("1000"),
            period_type="quarter",
        )
        yearly = build_period_breakdown(
            performance_points=points,
            fill_records=fill_records,
            signal_records=signal_records,
            initial_cash=Decimal("1000"),
            period_type="year",
        )

        self.assertEqual(len(monthly), 3)
        self.assertEqual(len(quarterly), 2)
        self.assertEqual(len(yearly), 1)
        self.assertEqual(monthly[0].signal_count, 1)
        self.assertEqual(monthly[1].fill_count, 1)
        self.assertEqual(quarterly[0].period_type, "quarter")
        self.assertEqual(yearly[0].end_equity, Decimal("1030"))

    def test_compare_projector_supports_side_by_side_run_analysis(self) -> None:
        run_start = datetime(2036, 2, 1, 0, 0, tzinfo=timezone.utc)
        bars = [
            build_bar_at("BTCUSDT_PERP", run_start + timedelta(minutes=offset), close)
            for offset, close in enumerate(["100", "105", "110"])
        ]
        base_session = {
            "session_code": "bt_btc_compare",
            "environment": "backtest",
            "account_code": "paper_main",
            "strategy_code": "btc_momentum",
            "strategy_version": "v1.0.0",
            "exchange_code": "binance",
            "universe": ["BTCUSDT_PERP"],
        }
        run_config_1 = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_compare_1x",
                "session": base_session,
                "start_time": run_start.isoformat(),
                "end_time": (run_start + timedelta(minutes=3)).isoformat(),
                "initial_cash": "10000",
                "strategy_params": {"target_qty": "1"},
            }
        )
        run_config_2 = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_compare_2x",
                "session": {**base_session, "session_code": "bt_btc_compare_2"},
                "start_time": run_start.isoformat(),
                "end_time": (run_start + timedelta(minutes=3)).isoformat(),
                "initial_cash": "10000",
                "assumption_bundle_code": "stress_costs",
                "assumption_bundle_version": "v1",
                "risk_overrides": {"max_order_notional": "150"},
                "strategy_params": {"target_qty": "2"},
            }
        )
        bar_repository = BarRepository()
        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            for bar in bars:
                bar_repository.upsert(connection, bar)

            runner_one = BacktestRunnerSkeleton(
                run_config_1,
                strategy=OneShotTargetStrategy(target_qty="1"),
                fill_model=DeterministicBarsFillModel(
                    fee_model=StaticFeeModel(taker_fee_bps="5.5"),
                    slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
                ),
            )
            runner_two = BacktestRunnerSkeleton(
                run_config_2,
                strategy=OneShotTargetStrategy(target_qty="2"),
                fill_model=DeterministicBarsFillModel(
                    fee_model=StaticFeeModel(taker_fee_bps="5.5"),
                    slippage_model=FixedBpsSlippageModel(market_order_bps="1"),
                ),
            )

            persisted_one = runner_one.load_run_and_persist(connection)
            persisted_two = runner_two.load_run_and_persist(connection)
            compare_set = BacktestCompareProjector().build(
                connection,
                run_ids=[persisted_one.run_id, persisted_two.run_id],
                benchmark_run_id=persisted_one.run_id,
                compare_name="target_qty_compare",
            )
            persisted_compare = CompareReviewService().persist_compare_set(
                connection,
                compare_set=compare_set,
                actor_name="Phase5FoundationTests",
            )
            compare_row, compare_notes = CompareReviewService().list_compare_notes(
                connection,
                compare_set_id=int(persisted_compare.compare_set_id or 0),
            )

            self.assertEqual(compare_set.compare_name, "target_qty_compare")
            self.assertFalse(compare_set.persisted)
            self.assertEqual([run.run_id for run in compare_set.compared_runs], [persisted_one.run_id, persisted_two.run_id])
            diff_fields = {diff.field_name for diff in compare_set.assumption_diffs}
            self.assertIn("strategy_params", diff_fields)
            self.assertIn("assumption_bundle_code", diff_fields)
            self.assertIn("risk_overrides", diff_fields)
            self.assertIn("effective_risk_policy", diff_fields)
            self.assertEqual(len(compare_set.benchmark_deltas), 1)
            self.assertEqual(compare_set.benchmark_deltas[0].run_id, persisted_two.run_id)
            self.assertIsNotNone(compare_set.benchmark_deltas[0].total_return_delta)
            flag_codes = {flag.code for flag in compare_set.comparison_flags}
            self.assertIn("execution_assumption_mismatch", flag_codes)
            self.assertTrue(persisted_compare.persisted)
            self.assertIsNotNone(persisted_compare.compare_set_id)
            self.assertEqual(compare_row["compare_name"], "target_qty_compare")
            self.assertEqual(list(compare_row["run_ids_json"]), [persisted_one.run_id, persisted_two.run_id])
            self.assertEqual(len(compare_notes), 1)
            self.assertEqual(compare_notes[0]["annotation_type"], "review")
            self.assertEqual(compare_notes[0]["note_source"], "system")
            self.assertEqual(compare_notes[0]["verification_state"], "system_fact")
            self.assertEqual(compare_notes[0]["source_refs_json"]["run_ids"], [persisted_one.run_id, persisted_two.run_id])
            self.assertEqual(compare_notes[0]["facts_snapshot_json"]["compare_name"], "target_qty_compare")
        finally:
            transaction.rollback()
            connection.close()

    def test_runner_rejects_bar_outside_session_universe(self) -> None:
        run_config = BacktestRunConfig.model_validate(
            {
                "run_name": "btc_runner_scope",
                "session": {
                    "session_code": "bt_btc",
                    "environment": "backtest",
                    "account_code": "paper_main",
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "exchange_code": "binance",
                    "universe": ["BTCUSDT_PERP"],
                },
                "start_time": "2026-04-01T00:00:00Z",
                "end_time": "2026-04-02T00:00:00Z",
                "initial_cash": "10000",
            }
        )
        runner = BacktestRunnerSkeleton(run_config)

        with self.assertRaises(ValueError):
            runner.evaluate_bar(
                build_bar("ETHUSDT_PERP", 0, "100"),
                [build_bar("ETHUSDT_PERP", 0, "100")],
            )


if __name__ == "__main__":
    unittest.main()
