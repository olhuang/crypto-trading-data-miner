from __future__ import annotations

from collections import deque
from datetime import datetime
from decimal import Decimal
from typing import Any

from models.strategy import TargetPosition, TargetPositionItem

from .base import StrategyBase, StrategyEvaluationInput, StrategyMarketContext


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


class FourHourBreakoutPerpStrategy(StrategyBase):
    strategy_code = "btc_4h_breakout_perp"
    strategy_version = "v0.1.0"

    def __init__(
        self,
        *,
        trend_fast_ema: int = 20,
        trend_slow_ema: int = 50,
        breakout_lookback_bars: int = 20,
        atr_window: int = 14,
        initial_stop_atr: Decimal = Decimal("2"),
        trailing_stop_atr: Decimal = Decimal("1.5"),
        exit_on_ema20_cross: bool = True,
        risk_per_trade_pct: Decimal = Decimal("0.005"),
        volatility_floor_atr_pct: Decimal = Decimal("0.008"),
        volatility_ceiling_atr_pct: Decimal = Decimal("0.08"),
        max_funding_rate_long: Decimal = Decimal("0.0005"),
        oi_change_pct_window: Decimal = Decimal("0.05"),
        min_price_change_pct_for_oi_confirmation: Decimal = Decimal("0.01"),
        skip_entries_within_minutes_of_funding: int = 30,
        max_consecutive_losses: int = 3,
        max_daily_r_multiple_loss: Decimal = Decimal("2"),
    ) -> None:
        self.trend_fast_ema = int(trend_fast_ema)
        self.trend_slow_ema = int(trend_slow_ema)
        self.breakout_lookback_bars = int(breakout_lookback_bars)
        self.atr_window = int(atr_window)
        self.initial_stop_atr = Decimal(str(initial_stop_atr))
        self.trailing_stop_atr = Decimal(str(trailing_stop_atr))
        self.exit_on_ema20_cross = bool(exit_on_ema20_cross)
        self.risk_per_trade_pct = Decimal(str(risk_per_trade_pct))
        self.volatility_floor_atr_pct = Decimal(str(volatility_floor_atr_pct))
        self.volatility_ceiling_atr_pct = Decimal(str(volatility_ceiling_atr_pct))
        self.max_funding_rate_long = Decimal(str(max_funding_rate_long))
        self.oi_change_pct_window = Decimal(str(oi_change_pct_window))
        self.min_price_change_pct_for_oi_confirmation = Decimal(str(min_price_change_pct_for_oi_confirmation))
        self.skip_entries_within_minutes_of_funding = int(skip_entries_within_minutes_of_funding)
        self.max_consecutive_losses = int(max_consecutive_losses)
        self.max_daily_r_multiple_loss = Decimal(str(max_daily_r_multiple_loss))
        self._open_position_metadata: dict[str, Any] | None = None
        self._last_bucket_key: datetime | None = None
        self._last_evaluated_bucket_key: datetime | None = None
        self._four_hour_history: list[dict[str, Decimal | datetime]] = []

        if self.trend_fast_ema <= 0:
            raise ValueError("trend_fast_ema must be positive")
        if self.trend_slow_ema <= self.trend_fast_ema:
            raise ValueError("trend_slow_ema must be greater than trend_fast_ema")
        if self.breakout_lookback_bars <= 0:
            raise ValueError("breakout_lookback_bars must be positive")
        if self.atr_window <= 0:
            raise ValueError("atr_window must be positive")
        if self.initial_stop_atr <= 0:
            raise ValueError("initial_stop_atr must be positive")
        if self.trailing_stop_atr <= 0:
            raise ValueError("trailing_stop_atr must be positive")
        if not (Decimal("0") < self.risk_per_trade_pct <= Decimal("1")):
            raise ValueError("risk_per_trade_pct must be within (0, 1]")
        if self.volatility_floor_atr_pct <= 0:
            raise ValueError("volatility_floor_atr_pct must be positive")
        if self.volatility_ceiling_atr_pct <= self.volatility_floor_atr_pct:
            raise ValueError("volatility_ceiling_atr_pct must be greater than volatility_floor_atr_pct")
        if self.max_funding_rate_long <= 0:
            raise ValueError("max_funding_rate_long must be positive")
        if self.oi_change_pct_window < 0:
            raise ValueError("oi_change_pct_window must be non-negative")
        if self.min_price_change_pct_for_oi_confirmation < 0:
            raise ValueError("min_price_change_pct_for_oi_confirmation must be non-negative")
        if self.skip_entries_within_minutes_of_funding < 0:
            raise ValueError("skip_entries_within_minutes_of_funding must be non-negative")
        if self.max_consecutive_losses <= 0:
            raise ValueError("max_consecutive_losses must be positive")
        if self.max_daily_r_multiple_loss <= 0:
            raise ValueError("max_daily_r_multiple_loss must be positive")

        self.required_bar_history = (
            max(
                self.trend_slow_ema,
                self.breakout_lookback_bars + 1,
                self.atr_window + 1,
            )
            * 240
        )
        self._history_cap_buckets = max(
            self.trend_slow_ema,
            self.breakout_lookback_bars + 1,
            self.atr_window + 1,
        ) + 1

    def evaluate(self, evaluation: StrategyEvaluationInput) -> TargetPosition | None:
        bucket_key = self._build_bucket_key(evaluation.bar.bar_time)
        self._update_four_hour_history(evaluation)
        if not self._is_bucket_close(evaluation.bar.bar_time):
            return None
        if self._last_evaluated_bucket_key == bucket_key:
            return None

        required_closed_bars = max(
            self.trend_slow_ema,
            self.breakout_lookback_bars + 1,
            self.atr_window + 1,
        )
        if len(self._four_hour_history) < required_closed_bars:
            return None

        current_bar = self._four_hour_history[-1]
        previous_bars = self._four_hour_history[:-1]
        close_price = current_bar["close"]
        fast_ema = self._calculate_ema(
            [bar["close"] for bar in self._four_hour_history[-self.trend_fast_ema :]],
            self.trend_fast_ema,
        )
        slow_ema = self._calculate_ema(
            [bar["close"] for bar in self._four_hour_history[-self.trend_slow_ema :]],
            self.trend_slow_ema,
        )
        atr = self._calculate_atr(self._four_hour_history[-(self.atr_window + 1) :], self.atr_window)
        if atr is None or close_price <= 0:
            return None
        atr_pct = atr / close_price
        breakout_high = max(bar["high"] for bar in previous_bars[-self.breakout_lookback_bars :])
        current_qty = evaluation.current_positions.get(evaluation.bar.unified_symbol, Decimal("0"))

        if current_qty > 0:
            should_exit = close_price < self._open_position_metadata.get("trailing_stop", Decimal("-1")) if self._open_position_metadata else False
            if self.exit_on_ema20_cross and close_price < fast_ema:
                should_exit = True
            if should_exit:
                self._last_evaluated_bucket_key = bucket_key
                self._open_position_metadata = None
                return self._build_target_position(evaluation, target_qty=Decimal("0"), metadata={
                    "strategy_name": self.__class__.__name__,
                    "bucket_time": bucket_key.isoformat(),
                    "action": "exit",
                    "close_price": str(close_price),
                    "fast_ema": str(fast_ema),
                })

            if self._open_position_metadata is not None:
                next_trailing_stop = max(
                    Decimal(str(self._open_position_metadata.get("trailing_stop", "0"))),
                    close_price - (atr * self.trailing_stop_atr),
                )
                self._open_position_metadata["trailing_stop"] = next_trailing_stop
            self._last_evaluated_bucket_key = bucket_key
            return None

        if fast_ema <= slow_ema:
            return None
        if close_price <= breakout_high:
            return None
        if atr_pct < self.volatility_floor_atr_pct or atr_pct > self.volatility_ceiling_atr_pct:
            return None
        if not self._passes_perp_context_filters(evaluation.market_context):
            return None

        stop_distance = atr * self.initial_stop_atr
        if stop_distance <= 0:
            return None
        risk_budget = evaluation.current_cash * self.risk_per_trade_pct
        target_qty = risk_budget / stop_distance
        if target_qty <= 0:
            return None

        initial_stop = close_price - stop_distance
        self._open_position_metadata = {
            "entry_price": close_price,
            "initial_stop": initial_stop,
            "trailing_stop": close_price - (atr * self.trailing_stop_atr),
            "atr": atr,
        }
        self._last_evaluated_bucket_key = bucket_key
        return self._build_target_position(
            evaluation,
            target_qty=target_qty,
            metadata={
                "strategy_name": self.__class__.__name__,
                "bucket_time": bucket_key.isoformat(),
                "action": "enter_long",
                "close_price": str(close_price),
                "breakout_high": str(breakout_high),
                "fast_ema": str(fast_ema),
                "slow_ema": str(slow_ema),
                "atr": str(atr),
                "atr_pct": str(atr_pct),
                "risk_per_trade_pct": str(self.risk_per_trade_pct),
                "initial_stop_price": str(initial_stop),
                "trailing_stop_price": str(self._open_position_metadata["trailing_stop"]),
            },
        )

    @staticmethod
    def _build_bucket_key(bar_time: datetime) -> datetime:
        return bar_time.replace(hour=bar_time.hour - (bar_time.hour % 4), minute=0, second=0, microsecond=0)

    @staticmethod
    def _is_bucket_close(bar_time: datetime) -> bool:
        return bar_time.minute == 59 and (bar_time.hour % 4) == 3

    @staticmethod
    def _aggregate_4h_bars(recent_bars) -> list[dict[str, Decimal | datetime]]:
        aggregated: dict[datetime, dict[str, Decimal | datetime]] = {}
        for bar in recent_bars:
            bucket_key = FourHourBreakoutPerpStrategy._build_bucket_key(bar.bar_time)
            bucket = aggregated.get(bucket_key)
            if bucket is None:
                aggregated[bucket_key] = {
                    "bucket_time": bucket_key,
                    "open": bar.open,
                    "high": bar.high,
                    "low": bar.low,
                    "close": bar.close,
                }
                continue
            bucket["high"] = max(Decimal(str(bucket["high"])), bar.high)
            bucket["low"] = min(Decimal(str(bucket["low"])), bar.low)
            bucket["close"] = bar.close
        return [aggregated[key] for key in sorted(aggregated)]

    def _update_four_hour_history(self, evaluation: StrategyEvaluationInput) -> None:
        bucket_key = self._build_bucket_key(evaluation.bar.bar_time)
        if not self._four_hour_history:
            self._four_hour_history = self._aggregate_4h_bars(evaluation.recent_bars)
            self._last_bucket_key = bucket_key
            self._trim_four_hour_history()
            return

        latest_bucket = self._four_hour_history[-1]
        latest_bucket_key = latest_bucket["bucket_time"]
        if latest_bucket_key != bucket_key:
            if latest_bucket_key > bucket_key:
                self._four_hour_history = self._aggregate_4h_bars(evaluation.recent_bars)
                self._last_bucket_key = bucket_key
                self._trim_four_hour_history()
                return
            self._four_hour_history.append(
                {
                    "bucket_time": bucket_key,
                    "open": evaluation.bar.open,
                    "high": evaluation.bar.high,
                    "low": evaluation.bar.low,
                    "close": evaluation.bar.close,
                }
            )
            self._last_bucket_key = bucket_key
            self._trim_four_hour_history()
            return

        latest_bucket["high"] = max(Decimal(str(latest_bucket["high"])), evaluation.bar.high)
        latest_bucket["low"] = min(Decimal(str(latest_bucket["low"])), evaluation.bar.low)
        latest_bucket["close"] = evaluation.bar.close
        self._last_bucket_key = bucket_key

    def _trim_four_hour_history(self) -> None:
        if len(self._four_hour_history) > self._history_cap_buckets:
            self._four_hour_history = self._four_hour_history[-self._history_cap_buckets :]

    @staticmethod
    def _calculate_ema(closes: list[Decimal], window: int) -> Decimal:
        if len(closes) < window:
            raise ValueError("not enough closes to calculate EMA")
        smoothing = Decimal("2") / Decimal(window + 1)
        ema = closes[0]
        for close in closes[1:]:
            ema = (close - ema) * smoothing + ema
        return ema

    @staticmethod
    def _calculate_atr(bars: list[dict[str, Decimal | datetime]], window: int) -> Decimal | None:
        if len(bars) < window + 1:
            return None
        true_ranges: deque[Decimal] = deque(maxlen=window)
        for previous_bar, current_bar in zip(bars, bars[1:]):
            current_high = Decimal(str(current_bar["high"]))
            current_low = Decimal(str(current_bar["low"]))
            previous_close = Decimal(str(previous_bar["close"]))
            true_ranges.append(
                max(
                    current_high - current_low,
                    abs(current_high - previous_close),
                    abs(current_low - previous_close),
                )
            )
        return sum(true_ranges, Decimal("0")) / Decimal(window)

    def _build_target_position(
        self,
        evaluation: StrategyEvaluationInput,
        *,
        target_qty: Decimal,
        metadata: dict[str, Any],
    ) -> TargetPosition:
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
            metadata_json=metadata,
        )

    def _passes_perp_context_filters(self, market_context: StrategyMarketContext | None) -> bool:
        if market_context is None:
            return True

        funding_snapshot = market_context.funding_rate
        if funding_snapshot is not None and funding_snapshot.get("funding_rate") is not None:
            funding_rate = Decimal(str(funding_snapshot["funding_rate"]))
            if funding_rate > self.max_funding_rate_long:
                return False

        if market_context.minutes_to_next_funding is not None:
            if market_context.minutes_to_next_funding <= self.skip_entries_within_minutes_of_funding:
                return False

        if (
            market_context.oi_change_pct_window is not None
            and market_context.price_change_pct_window is not None
            and market_context.oi_change_pct_window >= self.oi_change_pct_window
            and abs(market_context.price_change_pct_window) < self.min_price_change_pct_for_oi_confirmation
        ):
            return False

        return True
