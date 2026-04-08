from __future__ import annotations

from datetime import datetime

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
        self.required_bar_history = long_window

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


class SentimentAwareMovingAverageStrategy(MovingAverageCrossStrategy):
    strategy_code = "btc_sentiment_momentum"
    strategy_version = "v1.0.0"

    def __init__(
        self,
        *,
        short_window: int = 5,
        long_window: int = 20,
        target_qty: Decimal = Decimal("1"),
        allow_short: bool = False,
        max_global_long_short_ratio: Decimal = Decimal("2.25"),
        min_taker_buy_sell_ratio: Decimal = Decimal("0.95"),
    ) -> None:
        super().__init__(
            short_window=short_window,
            long_window=long_window,
            target_qty=target_qty,
            allow_short=allow_short,
        )
        self.max_global_long_short_ratio = Decimal(str(max_global_long_short_ratio))
        self.min_taker_buy_sell_ratio = Decimal(str(min_taker_buy_sell_ratio))
        if self.max_global_long_short_ratio <= 0:
            raise ValueError("max_global_long_short_ratio must be positive")
        if self.min_taker_buy_sell_ratio <= 0:
            raise ValueError("min_taker_buy_sell_ratio must be positive")

    def evaluate(self, evaluation: StrategyEvaluationInput) -> TargetPosition | None:
        decision = super().evaluate(evaluation)
        if decision is None:
            return None

        market_context = evaluation.market_context
        if market_context is None:
            return None

        target_item = decision.positions[0]
        target_qty = Decimal(str(target_item.target_qty or "0"))
        if target_qty <= 0:
            return decision

        global_ratio = market_context.global_long_short_account_ratio or {}
        taker_ratio = market_context.taker_long_short_ratio or {}
        long_short_ratio = global_ratio.get("long_short_ratio")
        buy_sell_ratio = taker_ratio.get("buy_sell_ratio")
        if long_short_ratio is None or buy_sell_ratio is None:
            return None

        if Decimal(str(long_short_ratio)) > self.max_global_long_short_ratio:
            return None
        if Decimal(str(buy_sell_ratio)) < self.min_taker_buy_sell_ratio:
            return None

        decision.metadata_json.update(
            {
                "strategy_name": self.__class__.__name__,
                "market_context_version": market_context.feature_input_version,
                "global_long_short_ratio": str(long_short_ratio),
                "taker_buy_sell_ratio": str(buy_sell_ratio),
                "max_global_long_short_ratio": str(self.max_global_long_short_ratio),
                "min_taker_buy_sell_ratio": str(self.min_taker_buy_sell_ratio),
            }
        )
        return decision


class HourlyMovingAverageCrossStrategy(StrategyBase):
    strategy_code = "btc_hourly_momentum"
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
        
        # We only need a tiny buffer from the engine now because we manage our own history!
        # But we keep it to long_window * 60 for the very first cold-start calculation.
        self.required_bar_history = long_window * 60 + 60
        
        # Incremental state
        self._hourly_history: list[Decimal] = [] 
        self._last_hour_key: datetime | None = None

    def evaluate(self, evaluation: StrategyEvaluationInput) -> TargetPosition | None:
        if not evaluation.recent_bars:
            return None

        current_bar = evaluation.bar
        hour_key = current_bar.bar_time.replace(minute=0, second=0, microsecond=0)

        # 1. Handle initialization or Hour-boundary crossing
        if self._last_hour_key is None:
            # Cold start: perform the one-time expensive aggregation
            temp_hourly: dict[datetime, Decimal] = {}
            for bar in evaluation.recent_bars:
                hk = bar.bar_time.replace(minute=0, second=0, microsecond=0)
                temp_hourly[hk] = bar.close
            sorted_hours = sorted(temp_hourly.keys())
            self._hourly_history = [temp_hourly[h] for h in sorted_hours]
            self._last_hour_key = hour_key
        
        elif self._last_hour_key != hour_key:
            # A new hour has just started. 
            # The previous last element in our history is now a "closed" hour.
            # We add a placeholder for the new current hour.
            self._hourly_history.append(current_bar.close)
            self._last_hour_key = hour_key
            # Keep only what we need
            if len(self._hourly_history) > self.long_window + 1:
                self._hourly_history.pop(0)
        else:
            # Still in the same hour, just update the latest price (incremental update)
            if self._hourly_history:
                self._hourly_history[-1] = current_bar.close

        # 2. MA Calculation
        if len(self._hourly_history) < self.long_window:
            return None
            
        # Standard MA usually uses "completed" bars. 
        # Here we use the latest N bars (including the forming current hour).
        closes = self._hourly_history[-self.long_window:]
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
                "hourly_groups": len(self._hourly_history),
                "incremental_mode": True
            },
        )
