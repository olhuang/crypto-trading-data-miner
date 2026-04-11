from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import StrategyBase
from .examples import (
    FourHourBreakoutPerpStrategy,
    HourlyMovingAverageCrossStrategy,
    MovingAverageCrossStrategy,
    SentimentAwareMovingAverageStrategy,
)


StrategyFactory = Callable[[dict[str, Any]], StrategyBase]


class UnknownStrategyError(LookupError):
    """Raised when a strategy/version pair is not registered."""


class StrategyRegistry:
    def __init__(self) -> None:
        self._factories: dict[tuple[str, str], StrategyFactory] = {}

    def register(self, strategy_code: str, strategy_version: str, factory: StrategyFactory) -> None:
        self._factories[(strategy_code, strategy_version)] = factory

    def create(self, strategy_code: str, strategy_version: str, params: dict[str, Any] | None = None) -> StrategyBase:
        key = (strategy_code, strategy_version)
        try:
            factory = self._factories[key]
        except KeyError as exc:
            raise UnknownStrategyError(
                f"unknown strategy registration for strategy_code={strategy_code} strategy_version={strategy_version}"
            ) from exc
        return factory(params or {})


def build_default_registry() -> StrategyRegistry:
    registry = StrategyRegistry()
    registry.register(
        "btc_momentum",
        "v1.0.0",
        lambda params: MovingAverageCrossStrategy(
            short_window=int(params.get("short_window", 5)),
            long_window=int(params.get("long_window", 20)),
            target_qty=params.get("target_qty", "1"),
            allow_short=bool(params.get("allow_short", False)),
        ),
    )
    registry.register(
        "btc_sentiment_momentum",
        "v1.0.0",
        lambda params: SentimentAwareMovingAverageStrategy(
            short_window=int(params.get("short_window", 5)),
            long_window=int(params.get("long_window", 20)),
            target_qty=params.get("target_qty", "1"),
            allow_short=bool(params.get("allow_short", False)),
            max_global_long_short_ratio=params.get("max_global_long_short_ratio", "2.25"),
            min_taker_buy_sell_ratio=params.get("min_taker_buy_sell_ratio", "0.95"),
        ),
    )
    registry.register(
        "btc_hourly_momentum",
        "v1.0.0",
        lambda params: HourlyMovingAverageCrossStrategy(
            short_window=int(params.get("short_window", 5)),
            long_window=int(params.get("long_window", 20)),
            target_qty=params.get("target_qty", "1"),
            allow_short=bool(params.get("allow_short", False)),
        ),
    )
    registry.register(
        "btc_4h_breakout_perp",
        "v0.1.0",
        lambda params: FourHourBreakoutPerpStrategy(
            trend_fast_ema=int(params.get("trend_fast_ema", 20)),
            trend_slow_ema=int(params.get("trend_slow_ema", 50)),
            breakout_lookback_bars=int(params.get("breakout_lookback_bars", 20)),
            atr_window=int(params.get("atr_window", 14)),
            initial_stop_atr=params.get("initial_stop_atr", "2"),
            trailing_stop_atr=params.get("trailing_stop_atr", "1.5"),
            exit_on_ema20_cross=bool(params.get("exit_on_ema20_cross", True)),
            risk_per_trade_pct=params.get("risk_per_trade_pct", "0.005"),
            volatility_floor_atr_pct=params.get("volatility_floor_atr_pct", "0.008"),
            volatility_ceiling_atr_pct=params.get("volatility_ceiling_atr_pct", "0.08"),
            max_funding_rate_long=params.get("max_funding_rate_long", "0.0005"),
            oi_change_pct_window=params.get("oi_change_pct_window", "0.05"),
            min_price_change_pct_for_oi_confirmation=params.get(
                "min_price_change_pct_for_oi_confirmation",
                "0.01",
            ),
            skip_entries_within_minutes_of_funding=int(
                params.get("skip_entries_within_minutes_of_funding", 30)
            ),
            max_consecutive_losses=int(params.get("max_consecutive_losses", 3)),
            max_daily_r_multiple_loss=params.get("max_daily_r_multiple_loss", "2"),
        ),
    )
    return registry
