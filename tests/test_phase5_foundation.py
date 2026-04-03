from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from backtest.lifecycle import BacktestLifecycle, LifecyclePlanningError
from backtest.runner import BacktestRunnerSkeleton
from models.backtest import BacktestRunConfig, StrategySessionConfig
from models.common import OrderSide
from models.market import BarEvent
from models.strategy import Signal, TargetPosition
from strategy import MovingAverageCrossStrategy, StrategyEvaluationInput, UnknownStrategyError, build_default_registry


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
        runner = BacktestRunnerSkeleton(run_config)

        result = runner.evaluate_bar(
            bars[-1],
            bars,
            current_positions={"BTCUSDT_PERP": Decimal("0")},
            current_cash=Decimal("10000"),
        )

        self.assertIsInstance(result.plan.decision, TargetPosition)
        self.assertEqual(len(result.plan.execution_intents), 1)
        self.assertEqual(result.plan.execution_intents[0].delta_qty, Decimal("1"))

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
