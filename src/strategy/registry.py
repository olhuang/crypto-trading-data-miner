from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import StrategyBase
from .examples import MovingAverageCrossStrategy, SentimentAwareMovingAverageStrategy, HourlyMovingAverageCrossStrategy


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
    return registry
