from __future__ import annotations

from decimal import Decimal

from models.strategy import TargetPosition, TargetPositionItem

from .base import StrategyBase, StrategyEvaluationInput


class MovingAverageCrossStrategy(StrategyBase):
    strategy_code = "btc_momentum"
    strategy_version = "v1.0.0"

    def __init__(
        self,
        *,
        short_window: int = 5,
        long_window: int = 20,
        target_qty: Decimal = Decimal("1"),
        allow_short: bool = False,
    ) -> None:
        target_qty = Decimal(str(target_qty))
        if short_window <= 0:
            raise ValueError("short_window must be positive")
        if long_window <= short_window:
            raise ValueError("long_window must be greater than short_window")
        if target_qty <= 0:
            raise ValueError("target_qty must be positive")

        self.short_window = short_window
        self.long_window = long_window
        self.target_qty = target_qty
        self.allow_short = allow_short

    def evaluate(self, evaluation: StrategyEvaluationInput) -> TargetPosition | None:
        if len(evaluation.recent_bars) < self.long_window:
            return None

        relevant_bars = list(evaluation.recent_bars)[-self.long_window :]
        closes = [bar.close for bar in relevant_bars]
        short_average = sum(closes[-self.short_window :], Decimal("0")) / Decimal(self.short_window)
        long_average = sum(closes, Decimal("0")) / Decimal(self.long_window)

        current_qty = evaluation.current_positions.get(evaluation.bar.unified_symbol, Decimal("0"))
        target_qty = current_qty

        if short_average > long_average:
            target_qty = self.target_qty
        elif short_average < long_average:
            target_qty = -self.target_qty if self.allow_short else Decimal("0")

        if target_qty == current_qty:
            return None

        return TargetPosition(
            strategy_code=evaluation.session.strategy_code,
            strategy_version=evaluation.session.strategy_version,
            target_time=evaluation.bar.bar_time,
            positions=[
                TargetPositionItem(
                    exchange_code=evaluation.bar.exchange_code,
                    unified_symbol=evaluation.bar.unified_symbol,
                    target_qty=target_qty,
                )
            ],
            metadata_json={
                "strategy_name": self.__class__.__name__,
                "short_window": self.short_window,
                "long_window": self.long_window,
                "allow_short": self.allow_short,
            },
        )
