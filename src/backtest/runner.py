from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from models.backtest import BacktestRunConfig
from models.market import BarEvent
from strategy import StrategyBase, StrategyEvaluationInput, StrategyRegistry, build_default_registry

from .lifecycle import BacktestLifecycle, BacktestStepPlan


@dataclass(slots=True)
class BacktestStepResult:
    bar_time: str
    plan: BacktestStepPlan


class BacktestRunnerSkeleton:
    def __init__(
        self,
        run_config: BacktestRunConfig,
        *,
        registry: StrategyRegistry | None = None,
        strategy: StrategyBase | None = None,
    ) -> None:
        self.run_config = run_config
        self.registry = registry or build_default_registry()
        self.strategy = strategy or self.registry.create(
            run_config.session.strategy_code,
            run_config.session.strategy_version,
            run_config.strategy_params_json,
        )
        self.lifecycle = BacktestLifecycle(run_config)

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
        return BacktestStepResult(bar_time=bar.bar_time.isoformat(), plan=plan)
