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
from backtest.compare import BacktestCompareProjector
from backtest.fills import DeterministicBarsFillModel, FixedBpsSlippageModel, SimulatedFill, StaticFeeModel
from backtest.diagnostics import BacktestDiagnosticsProjector
from backtest.lifecycle import BacktestLifecycle, LifecyclePlanningError
from backtest.periods import build_period_breakdown
from backtest.performance import PerformancePoint
from backtest.runner import BacktestRunnerSkeleton
from backtest.state import PortfolioState
from backtest.signals import build_signals_from_target_position
from models.backtest import BacktestRunConfig, StrategySessionConfig
from models.common import LiquidityFlag, OrderSide, OrderType, SignalType
from models.market import BarEvent
from models.strategy import Signal, TargetPosition
from storage.db import get_engine
from storage.repositories.market_data import BarRepository
from strategy import (
    MovingAverageCrossStrategy,
    StrategyBase,
    StrategyEvaluationInput,
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

        session = StrategySessionConfig.model_validate(
            {
                "session_code": "bt_btc",
                "environment": "backtest",
                "account_code": "paper_main",
                "strategy_code": "btc_momentum",
                "strategy_version": "v1.0.0",
                "exchange_code": "binance",
                "universe": ["BTCUSDT_PERP", "BTCUSDT_PERP", "ETHUSDT_PERP"],
            }
        )

        self.assertEqual(session.universe, ["BTCUSDT_PERP", "ETHUSDT_PERP"])

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

    def test_default_registry_loads_seeded_example_strategy(self) -> None:
        registry = build_default_registry()
        strategy = registry.create("btc_momentum", "v1.0.0", {"short_window": 3, "long_window": 5, "target_qty": "2"})
        self.assertIsInstance(strategy, MovingAverageCrossStrategy)
        self.assertEqual(strategy.target_qty, Decimal("2"))

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
            self.assertIsNotNone(diagnostics)
            assert diagnostics is not None
            self.assertEqual(diagnostics.diagnostic_status, "ok")
            self.assertEqual(diagnostics.execution_summary.simulated_order_count, 1)
            self.assertEqual(diagnostics.strategy_activity.signal_count, 1)
            self.assertIsNotNone(artifact_bundle)
            assert artifact_bundle is not None
            self.assertEqual(artifact_bundle.artifacts[0].artifact_type, "run_metadata")
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

            self.assertEqual(compare_set.compare_name, "target_qty_compare")
            self.assertFalse(compare_set.persisted)
            self.assertEqual([run.run_id for run in compare_set.compared_runs], [persisted_one.run_id, persisted_two.run_id])
            diff_fields = {diff.field_name for diff in compare_set.assumption_diffs}
            self.assertIn("strategy_params", diff_fields)
            self.assertEqual(len(compare_set.benchmark_deltas), 1)
            self.assertEqual(compare_set.benchmark_deltas[0].run_id, persisted_two.run_id)
            self.assertIsNotNone(compare_set.benchmark_deltas[0].total_return_delta)
            flag_codes = {flag.code for flag in compare_set.comparison_flags}
            self.assertIn("execution_assumption_mismatch", flag_codes)
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
