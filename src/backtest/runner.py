from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable, Mapping, Sequence

from models.backtest import BacktestRunConfig
from models.market import BarEvent
from models.strategy import Signal, TargetPosition
from sqlalchemy.engine import Connection
from storage.repositories.strategy import StrategySignalRepository
from strategy import StrategyBase, StrategyEvaluationInput, StrategyRegistry, build_default_registry

from .data import BacktestBarLoader
from .lifecycle import BacktestLifecycle, BacktestStepPlan
from .signals import build_signals_from_target_position


@dataclass(slots=True)
class BacktestStepResult:
    bar_time: str
    plan: BacktestStepPlan
    signals: list[Signal]


@dataclass(slots=True)
class BacktestRunLoopResult:
    steps: list[BacktestStepResult]
    final_positions: dict[str, Decimal]
    persisted_signal_ids: list[int]


class BacktestRunnerSkeleton:
    def __init__(
        self,
        run_config: BacktestRunConfig,
        *,
        registry: StrategyRegistry | None = None,
        strategy: StrategyBase | None = None,
        signal_repository: StrategySignalRepository | None = None,
    ) -> None:
        self.run_config = run_config
        self.registry = registry or build_default_registry()
        self.strategy = strategy or self.registry.create(
            run_config.session.strategy_code,
            run_config.session.strategy_version,
            run_config.strategy_params_json,
        )
        self.lifecycle = BacktestLifecycle(run_config)
        self.signal_repository = signal_repository or StrategySignalRepository()

    def evaluate_bar(
        self,
        bar: BarEvent,
        recent_bars: Sequence[BarEvent],
        *,
        current_positions: Mapping[str, Decimal] | None = None,
        current_cash: Decimal = Decimal("0"),
    ) -> BacktestStepResult:
        if bar.unified_symbol not in self.run_config.session.universe:
            raise ValueError("bar unified_symbol must belong to the configured strategy session universe")
        positions = current_positions or {}
        decision = self.strategy.evaluate(
            StrategyEvaluationInput(
                session=self.run_config.session,
                run_config=self.run_config,
                bar=bar,
                recent_bars=recent_bars,
                current_positions=positions,
                current_cash=current_cash,
            )
        )
        plan = self.lifecycle.plan_from_decision(decision, positions)
        signals = self._build_signals(decision, positions)
        return BacktestStepResult(bar_time=bar.bar_time.isoformat(), plan=plan, signals=signals)

    def run_bars(
        self,
        bars: Iterable[BarEvent],
        *,
        initial_positions: Mapping[str, Decimal] | None = None,
        initial_cash: Decimal | None = None,
        persist_signals: bool = False,
        connection: Connection | None = None,
    ) -> BacktestRunLoopResult:
        current_positions: dict[str, Decimal] = {
            symbol: Decimal(value) for symbol, value in (initial_positions or {}).items()
        }
        current_cash = initial_cash if initial_cash is not None else self.run_config.initial_cash
        recent_bars_by_symbol: dict[str, list[BarEvent]] = {}
        step_results: list[BacktestStepResult] = []
        persisted_signal_ids: list[int] = []

        for bar in sorted(bars, key=lambda item: (item.bar_time, item.unified_symbol)):
            recent_bars = recent_bars_by_symbol.setdefault(bar.unified_symbol, [])
            recent_bars.append(bar)
            step_result = self.evaluate_bar(
                bar,
                recent_bars,
                current_positions=current_positions,
                current_cash=current_cash,
            )
            if persist_signals:
                if connection is None:
                    raise ValueError("connection is required when persist_signals is true")
                for signal in step_result.signals:
                    persisted_signal_ids.append(self.signal_repository.insert(connection, signal))
            for intent in step_result.plan.execution_intents:
                current_positions[intent.unified_symbol] = intent.target_qty
            step_results.append(step_result)

        return BacktestRunLoopResult(
            steps=step_results,
            final_positions=current_positions,
            persisted_signal_ids=persisted_signal_ids,
        )

    def load_and_run(
        self,
        connection: Connection,
        *,
        bar_loader: BacktestBarLoader | None = None,
        persist_signals: bool = False,
    ) -> BacktestRunLoopResult:
        loader = bar_loader or BacktestBarLoader()
        bars = loader.load_bars(connection, self.run_config)
        return self.run_bars(bars, persist_signals=persist_signals, connection=connection)

    def _build_signals(
        self,
        decision: Signal | TargetPosition | None,
        current_positions: Mapping[str, Decimal],
    ) -> list[Signal]:
        if isinstance(decision, Signal):
            return [decision]
        if isinstance(decision, TargetPosition):
            return build_signals_from_target_position(
                decision,
                current_positions,
                session_code=self.run_config.session.session_code,
            )
        return []
