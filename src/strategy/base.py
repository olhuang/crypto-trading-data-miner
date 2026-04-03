from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from models.backtest import BacktestRunConfig, StrategySessionConfig
from models.market import BarEvent
from models.strategy import Signal, TargetPosition


StrategyDecision = Signal | TargetPosition | None


@dataclass(slots=True)
class StrategyEvaluationInput:
    session: StrategySessionConfig
    run_config: BacktestRunConfig
    bar: BarEvent
    recent_bars: Sequence[BarEvent]
    current_positions: Mapping[str, Decimal]
    current_cash: Decimal


class StrategyBase(ABC):
    strategy_code: str
    strategy_version: str
    required_bar_history: int | None = None

    @abstractmethod
    def evaluate(self, evaluation: StrategyEvaluationInput) -> StrategyDecision:
        """Return a canonical strategy decision for the current bar."""
