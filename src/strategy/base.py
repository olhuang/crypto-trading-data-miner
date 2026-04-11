from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from models.backtest import BacktestRunConfig, StrategySessionConfig
from models.market import BarEvent
from models.strategy import Signal, TargetPosition


StrategyDecision = Signal | TargetPosition | None


@dataclass(slots=True)
class StrategyMarketContext:
    feature_input_version: str
    funding_rate: dict[str, Any] | None = None
    open_interest: dict[str, Any] | None = None
    mark_price: dict[str, Any] | None = None
    index_price: dict[str, Any] | None = None
    global_long_short_account_ratio: dict[str, Any] | None = None
    top_trader_long_short_account_ratio: dict[str, Any] | None = None
    top_trader_long_short_position_ratio: dict[str, Any] | None = None
    taker_long_short_ratio: dict[str, Any] | None = None
    minutes_to_next_funding: int | None = None
    oi_change_pct_window: Decimal | None = None
    price_change_pct_window: Decimal | None = None
    weak_price_oi_push: bool | None = None


@dataclass(slots=True)
class StrategyEvaluationInput:
    session: StrategySessionConfig
    run_config: BacktestRunConfig
    bar: BarEvent
    recent_bars: Sequence[BarEvent]
    current_positions: Mapping[str, Decimal]
    current_cash: Decimal
    market_context: StrategyMarketContext | None = None


class StrategyBase(ABC):
    strategy_code: str
    strategy_version: str
    required_bar_history: int | None = None

    @abstractmethod
    def evaluate(self, evaluation: StrategyEvaluationInput) -> StrategyDecision:
        """Return a canonical strategy decision for the current bar."""
