from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

from models.market import BarEvent, FundingRateEvent, OpenInterestEvent, TradeEvent
from storage.lookups import resolve_instrument_id


class BarRepository:
    def upsert(self, connection: Connection, event: BarEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.bars_1m (
                    instrument_id,
                    bar_time,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    quote_volume,
                    trade_count
                ) values (
                    :instrument_id,
                    :bar_time,
                    :open,
                    :high,
                    :low,
                    :close,
                    :volume,
                    :quote_volume,
                    :trade_count
                )
                on conflict (instrument_id, bar_time) do update
                set
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    quote_volume = excluded.quote_volume,
                    trade_count = excluded.trade_count
                """
            ),
            {
                "instrument_id": instrument_id,
                "bar_time": event.bar_time,
                "open": event.open,
                "high": event.high,
                "low": event.low,
                "close": event.close,
                "volume": event.volume,
                "quote_volume": event.quote_volume,
                "trade_count": event.trade_count,
            },
        )


class TradeRepository:
    def upsert(self, connection: Connection, event: TradeEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.trades (
                    instrument_id,
                    exchange_trade_id,
                    event_time,
                    ingest_time,
                    price,
                    qty,
                    aggressor_side
                ) values (
                    :instrument_id,
                    :exchange_trade_id,
                    :event_time,
                    coalesce(:ingest_time, now()),
                    :price,
                    :qty,
                    :aggressor_side
                )
                on conflict (instrument_id, exchange_trade_id) do update
                set
                    event_time = excluded.event_time,
                    ingest_time = excluded.ingest_time,
                    price = excluded.price,
                    qty = excluded.qty,
                    aggressor_side = excluded.aggressor_side
                """
            ),
            {
                "instrument_id": instrument_id,
                "exchange_trade_id": event.exchange_trade_id,
                "event_time": event.event_time,
                "ingest_time": event.ingest_time,
                "price": event.price,
                "qty": event.qty,
                "aggressor_side": event.aggressor_side,
            },
        )


class FundingRateRepository:
    def upsert(self, connection: Connection, event: FundingRateEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.funding_rates (
                    instrument_id,
                    funding_time,
                    funding_rate,
                    mark_price,
                    index_price
                ) values (
                    :instrument_id,
                    :funding_time,
                    :funding_rate,
                    :mark_price,
                    :index_price
                )
                on conflict (instrument_id, funding_time) do update
                set
                    funding_rate = excluded.funding_rate,
                    mark_price = excluded.mark_price,
                    index_price = excluded.index_price
                """
            ),
            {
                "instrument_id": instrument_id,
                "funding_time": event.funding_time,
                "funding_rate": event.funding_rate,
                "mark_price": event.mark_price,
                "index_price": event.index_price,
            },
        )


class OpenInterestRepository:
    def upsert(self, connection: Connection, event: OpenInterestEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.open_interest (
                    instrument_id,
                    ts,
                    open_interest
                ) values (
                    :instrument_id,
                    :ts,
                    :open_interest
                )
                on conflict (instrument_id, ts) do update
                set
                    open_interest = excluded.open_interest
                """
            ),
            {
                "instrument_id": instrument_id,
                "ts": event.event_time,
                "open_interest": event.open_interest,
            },
        )
