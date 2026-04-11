from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from heapq import merge
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from models.backtest import BacktestRunConfig
from models.market import BarEvent
from storage.lookups import resolve_instrument_id
from storage.repositories.market_data import BarRepository
from strategy.base import StrategyMarketContext


FEATURE_INPUT_BARS_ONLY_V1 = "bars_only_v1"
FEATURE_INPUT_BARS_PERP_CONTEXT_V1 = "bars_perp_context_v1"
FEATURE_INPUT_BARS_PERP_BREAKOUT_CONTEXT_V1 = "bars_perp_breakout_context_v1"
DEFAULT_SENTIMENT_RATIO_PERIOD = "5m"
BREAKOUT_CONTEXT_WINDOW = timedelta(hours=4)

PERP_CONTEXT_DATASET_SPECS: dict[str, dict[str, Any]] = {
    "funding_rate": {
        "table_name": "md.funding_rates",
        "time_column": "funding_time",
        "select_columns": "funding_time as event_time, funding_rate, mark_price, index_price",
        "period_code": None,
    },
    "open_interest": {
        "table_name": "md.open_interest",
        "time_column": "ts",
        "select_columns": "ts as event_time, open_interest",
        "period_code": None,
    },
    "mark_price": {
        "table_name": "md.mark_prices",
        "time_column": "ts",
        "select_columns": "ts as event_time, mark_price, funding_basis_bps",
        "period_code": None,
    },
    "index_price": {
        "table_name": "md.index_prices",
        "time_column": "ts",
        "select_columns": "ts as event_time, index_price",
        "period_code": None,
    },
    "global_long_short_account_ratio": {
        "table_name": "md.global_long_short_account_ratios",
        "time_column": "ts",
        "select_columns": "ts as event_time, period_code, long_short_ratio, long_account_ratio, short_account_ratio",
        "period_code": DEFAULT_SENTIMENT_RATIO_PERIOD,
    },
    "top_trader_long_short_account_ratio": {
        "table_name": "md.top_trader_long_short_account_ratios",
        "time_column": "ts",
        "select_columns": "ts as event_time, period_code, long_short_ratio, long_account_ratio, short_account_ratio",
        "period_code": DEFAULT_SENTIMENT_RATIO_PERIOD,
    },
    "top_trader_long_short_position_ratio": {
        "table_name": "md.top_trader_long_short_position_ratios",
        "time_column": "ts",
        "select_columns": "ts as event_time, period_code, long_short_ratio, long_account_ratio, short_account_ratio",
        "period_code": DEFAULT_SENTIMENT_RATIO_PERIOD,
    },
    "taker_long_short_ratio": {
        "table_name": "md.taker_long_short_ratios",
        "time_column": "ts",
        "select_columns": "ts as event_time, period_code, buy_sell_ratio, buy_vol, sell_vol",
        "period_code": DEFAULT_SENTIMENT_RATIO_PERIOD,
    },
}


@dataclass(slots=True)
class BacktestPerpContextSeries:
    funding_rate: list[dict[str, Any]] = field(default_factory=list)
    open_interest: list[dict[str, Any]] = field(default_factory=list)
    mark_price: list[dict[str, Any]] = field(default_factory=list)
    index_price: list[dict[str, Any]] = field(default_factory=list)
    global_long_short_account_ratio: list[dict[str, Any]] = field(default_factory=list)
    top_trader_long_short_account_ratio: list[dict[str, Any]] = field(default_factory=list)
    top_trader_long_short_position_ratio: list[dict[str, Any]] = field(default_factory=list)
    taker_long_short_ratio: list[dict[str, Any]] = field(default_factory=list)

    def has_any_values(self) -> bool:
        return any(getattr(self, dataset_name) for dataset_name in PERP_CONTEXT_DATASET_SPECS)


@dataclass(slots=True)
class BacktestPerpContextCursor:
    feature_input_version: str
    series: BacktestPerpContextSeries
    _positions: dict[str, int] = field(default_factory=dict)
    _latest_values: dict[str, dict[str, Any]] = field(default_factory=dict)

    def context_at(self, decision_time: datetime) -> StrategyMarketContext | None:
        for dataset_name in PERP_CONTEXT_DATASET_SPECS:
            rows = getattr(self.series, dataset_name)
            current_index = self._positions.get(dataset_name, 0)
            while current_index < len(rows) and rows[current_index]["event_time"] <= decision_time:
                self._latest_values[dataset_name] = rows[current_index]
                current_index += 1
            self._positions[dataset_name] = current_index

        if not self._latest_values:
            return None

        derived_fields = self._build_derived_breakout_fields(decision_time)

        return StrategyMarketContext(
            feature_input_version=self.feature_input_version,
            funding_rate=self._latest_values.get("funding_rate"),
            open_interest=self._latest_values.get("open_interest"),
            mark_price=self._latest_values.get("mark_price"),
            index_price=self._latest_values.get("index_price"),
            global_long_short_account_ratio=self._latest_values.get("global_long_short_account_ratio"),
            top_trader_long_short_account_ratio=self._latest_values.get("top_trader_long_short_account_ratio"),
            top_trader_long_short_position_ratio=self._latest_values.get("top_trader_long_short_position_ratio"),
            taker_long_short_ratio=self._latest_values.get("taker_long_short_ratio"),
            minutes_to_next_funding=derived_fields["minutes_to_next_funding"],
            oi_change_pct_window=derived_fields["oi_change_pct_window"],
            price_change_pct_window=derived_fields["price_change_pct_window"],
            weak_price_oi_push=derived_fields["weak_price_oi_push"],
        )

    def _build_derived_breakout_fields(self, decision_time: datetime) -> dict[str, Any]:
        derived_fields = {
            "minutes_to_next_funding": None,
            "oi_change_pct_window": None,
            "price_change_pct_window": None,
            "weak_price_oi_push": None,
        }
        if self.feature_input_version != FEATURE_INPUT_BARS_PERP_BREAKOUT_CONTEXT_V1:
            return derived_fields

        derived_fields["minutes_to_next_funding"] = self._minutes_to_next_funding(decision_time)
        oi_change_pct = self._percentage_change_over_window(
            self.series.open_interest,
            value_field="open_interest",
            decision_time=decision_time,
        )
        price_change_pct = self._percentage_change_over_window(
            self.series.mark_price,
            value_field="mark_price",
            decision_time=decision_time,
        )
        if price_change_pct is None:
            price_change_pct = self._percentage_change_over_window(
                self.series.index_price,
                value_field="index_price",
                decision_time=decision_time,
            )

        derived_fields["oi_change_pct_window"] = oi_change_pct
        derived_fields["price_change_pct_window"] = price_change_pct
        if oi_change_pct is not None and price_change_pct is not None:
            derived_fields["weak_price_oi_push"] = oi_change_pct > abs(price_change_pct)
        return derived_fields

    @staticmethod
    def _minutes_to_next_funding(decision_time: datetime) -> int:
        normalized = decision_time.replace(second=0, microsecond=0)
        next_hour = ((normalized.hour // 8) + 1) * 8
        next_funding = normalized.replace(minute=0)
        if next_hour >= 24:
            next_funding = next_funding.replace(hour=0) + timedelta(days=1)
        else:
            next_funding = next_funding.replace(hour=next_hour)
        return int((next_funding - normalized).total_seconds() // 60)

    @staticmethod
    def _percentage_change_over_window(
        rows: list[dict[str, Any]],
        *,
        value_field: str,
        decision_time: datetime,
    ) -> Decimal | None:
        latest_row = BacktestPerpContextCursor._latest_row_before_or_at(rows, decision_time)
        prior_row = BacktestPerpContextCursor._latest_row_before_or_at(rows, decision_time - BREAKOUT_CONTEXT_WINDOW)
        if latest_row is None or prior_row is None:
            return None
        latest_value = Decimal(str(latest_row.get(value_field) or "0"))
        prior_value = Decimal(str(prior_row.get(value_field) or "0"))
        if prior_value == 0:
            return None
        return (latest_value - prior_value) / prior_value

    @staticmethod
    def _latest_row_before_or_at(rows: list[dict[str, Any]], ts: datetime) -> dict[str, Any] | None:
        latest: dict[str, Any] | None = None
        for row in rows:
            if row["event_time"] <= ts:
                latest = row
            else:
                break
        return latest


class BacktestBarLoader:
    def __init__(self, bar_repository: BarRepository | None = None) -> None:
        self.bar_repository = bar_repository or BarRepository()

    def load_bars(
        self,
        connection: Connection,
        run_config: BacktestRunConfig,
        *,
        required_bar_history: int | None = None,
    ) -> list[BarEvent]:
        return list(
            self.iter_bars(
                connection,
                run_config,
                required_bar_history=required_bar_history,
            )
        )

    def iter_bars(
        self,
        connection: Connection,
        run_config: BacktestRunConfig,
        *,
        required_bar_history: int | None = None,
    ):
        history_minutes = max(required_bar_history or 0, 0)
        adjusted_start = run_config.start_time - timedelta(minutes=history_minutes)

        iterables = []
        for unified_symbol in run_config.session.universe:
            iterables.append(
                self.bar_repository.iter_window(
                    connection,
                    exchange_code=run_config.session.exchange_code,
                    unified_symbol=unified_symbol,
                    start_time=adjusted_start,
                    end_time=run_config.end_time,
                )
            )
        return merge(*iterables, key=lambda bar: (bar.bar_time, bar.unified_symbol))


class BacktestPerpContextLoader:
    def load_contexts(
        self,
        connection: Connection,
        run_config: BacktestRunConfig,
    ) -> dict[str, BacktestPerpContextCursor]:
        if run_config.feature_input_version not in (
            FEATURE_INPUT_BARS_PERP_CONTEXT_V1,
            FEATURE_INPUT_BARS_PERP_BREAKOUT_CONTEXT_V1,
        ):
            return {}

        contexts: dict[str, BacktestPerpContextCursor] = {}
        for unified_symbol in run_config.session.universe:
            if unified_symbol.upper().endswith("_SPOT"):
                continue
            instrument_id = resolve_instrument_id(connection, run_config.session.exchange_code, unified_symbol)
            series = BacktestPerpContextSeries(
                **{
                    dataset_name: self._load_series(
                        connection,
                        instrument_id=instrument_id,
                        start_time=run_config.start_time,
                        end_time=run_config.end_time,
                        **spec,
                    )
                    for dataset_name, spec in PERP_CONTEXT_DATASET_SPECS.items()
                }
            )
            if series.has_any_values():
                contexts[unified_symbol] = BacktestPerpContextCursor(
                    feature_input_version=run_config.feature_input_version,
                    series=series,
                )
        return contexts

    @staticmethod
    def _load_series(
        connection: Connection,
        *,
        instrument_id: int,
        table_name: str,
        time_column: str,
        select_columns: str,
        start_time: datetime,
        end_time: datetime,
        period_code: str | None = None,
    ) -> list[dict[str, Any]]:
        prior_period_filter = "and period_code = :period_code" if period_code is not None else ""
        window_period_filter = "and period_code = :period_code" if period_code is not None else ""
        rows = connection.execute(
            text(
                f"""
                with prior_row as (
                    select {select_columns}
                    from {table_name}
                    where instrument_id = :instrument_id
                      and {time_column} < :start_time
                      {prior_period_filter}
                    order by {time_column} desc
                    limit 1
                ),
                window_rows as (
                    select {select_columns}
                    from {table_name}
                    where instrument_id = :instrument_id
                      and {time_column} between :start_time and :end_time
                      {window_period_filter}
                )
                select *
                from (
                    select * from prior_row
                    union all
                    select * from window_rows
                ) rows
                order by event_time asc
                """
            ),
            {
                "instrument_id": instrument_id,
                "start_time": start_time,
                "end_time": end_time,
                "period_code": period_code,
            },
        ).mappings()
        return [dict(row) for row in rows]
