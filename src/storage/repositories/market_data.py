from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.engine import Connection

from models.market import (
    BarEvent,
    FundingRateEvent,
    GlobalLongShortAccountRatioEvent,
    IndexPriceEvent,
    LiquidationEvent,
    MarkPriceEvent,
    OpenInterestEvent,
    OrderBookDeltaEvent,
    OrderBookSnapshotEvent,
    RawMarketEvent,
    TakerLongShortRatioEvent,
    TopTraderLongShortAccountRatioEvent,
    TopTraderLongShortPositionRatioEvent,
    TradeEvent,
)
from storage.lookups import resolve_exchange_id, resolve_instrument_id


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

    def list_window(
        self,
        connection: Connection,
        *,
        exchange_code: str,
        unified_symbol: str,
        start_time,
        end_time,
        limit: int | None = None,
    ) -> list[BarEvent]:
        rows = connection.execute(
            text(
                """
                select
                    e.exchange_code,
                    i.unified_symbol,
                    b.bar_time,
                    b.open,
                    b.high,
                    b.low,
                    b.close,
                    b.volume,
                    b.quote_volume,
                    b.trade_count
                from md.bars_1m b
                join ref.instruments i on i.instrument_id = b.instrument_id
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = :exchange_code
                  and i.unified_symbol = :unified_symbol
                  and b.bar_time >= :start_time
                  and b.bar_time < :end_time
                order by b.bar_time asc
                limit coalesce(:limit, 2147483647)
                """
            ),
            {
                "exchange_code": exchange_code,
                "unified_symbol": unified_symbol,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit,
            },
        ).mappings()
        return [
            BarEvent.model_validate(
                {
                    "exchange_code": row["exchange_code"],
                    "unified_symbol": row["unified_symbol"],
                    "bar_interval": "1m",
                    "bar_time": row["bar_time"],
                    "event_time": row["bar_time"],
                    "ingest_time": row["bar_time"],
                    "open": row["open"],
                    "high": row["high"],
                    "low": row["low"],
                    "close": row["close"],
                    "volume": row["volume"],
                    "quote_volume": row["quote_volume"],
                    "trade_count": row["trade_count"],
                }
            )
            for row in rows
        ]


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


class GlobalLongShortAccountRatioRepository:
    def upsert(self, connection: Connection, event: GlobalLongShortAccountRatioEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.global_long_short_account_ratios (
                    instrument_id,
                    ts,
                    period_code,
                    long_short_ratio,
                    long_account_ratio,
                    short_account_ratio,
                    ingest_time
                ) values (
                    :instrument_id,
                    :ts,
                    :period_code,
                    :long_short_ratio,
                    :long_account_ratio,
                    :short_account_ratio,
                    :ingest_time
                )
                on conflict (instrument_id, ts, period_code) do update
                set
                    long_short_ratio = excluded.long_short_ratio,
                    long_account_ratio = excluded.long_account_ratio,
                    short_account_ratio = excluded.short_account_ratio,
                    ingest_time = excluded.ingest_time
                """
            ),
            {
                "instrument_id": instrument_id,
                "ts": event.event_time,
                "period_code": event.period_code,
                "long_short_ratio": event.long_short_ratio,
                "long_account_ratio": event.long_account_ratio,
                "short_account_ratio": event.short_account_ratio,
                "ingest_time": event.ingest_time,
            },
        )


class TopTraderLongShortAccountRatioRepository:
    def upsert(self, connection: Connection, event: TopTraderLongShortAccountRatioEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.top_trader_long_short_account_ratios (
                    instrument_id,
                    ts,
                    period_code,
                    long_short_ratio,
                    long_account_ratio,
                    short_account_ratio,
                    ingest_time
                ) values (
                    :instrument_id,
                    :ts,
                    :period_code,
                    :long_short_ratio,
                    :long_account_ratio,
                    :short_account_ratio,
                    :ingest_time
                )
                on conflict (instrument_id, ts, period_code) do update
                set
                    long_short_ratio = excluded.long_short_ratio,
                    long_account_ratio = excluded.long_account_ratio,
                    short_account_ratio = excluded.short_account_ratio,
                    ingest_time = excluded.ingest_time
                """
            ),
            {
                "instrument_id": instrument_id,
                "ts": event.event_time,
                "period_code": event.period_code,
                "long_short_ratio": event.long_short_ratio,
                "long_account_ratio": event.long_account_ratio,
                "short_account_ratio": event.short_account_ratio,
                "ingest_time": event.ingest_time,
            },
        )


class TopTraderLongShortPositionRatioRepository:
    def upsert(self, connection: Connection, event: TopTraderLongShortPositionRatioEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.top_trader_long_short_position_ratios (
                    instrument_id,
                    ts,
                    period_code,
                    long_short_ratio,
                    long_account_ratio,
                    short_account_ratio,
                    ingest_time
                ) values (
                    :instrument_id,
                    :ts,
                    :period_code,
                    :long_short_ratio,
                    :long_account_ratio,
                    :short_account_ratio,
                    :ingest_time
                )
                on conflict (instrument_id, ts, period_code) do update
                set
                    long_short_ratio = excluded.long_short_ratio,
                    long_account_ratio = excluded.long_account_ratio,
                    short_account_ratio = excluded.short_account_ratio,
                    ingest_time = excluded.ingest_time
                """
            ),
            {
                "instrument_id": instrument_id,
                "ts": event.event_time,
                "period_code": event.period_code,
                "long_short_ratio": event.long_short_ratio,
                "long_account_ratio": event.long_account_ratio,
                "short_account_ratio": event.short_account_ratio,
                "ingest_time": event.ingest_time,
            },
        )


class TakerLongShortRatioRepository:
    def upsert(self, connection: Connection, event: TakerLongShortRatioEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.taker_long_short_ratios (
                    instrument_id,
                    ts,
                    period_code,
                    buy_sell_ratio,
                    buy_vol,
                    sell_vol,
                    ingest_time
                ) values (
                    :instrument_id,
                    :ts,
                    :period_code,
                    :buy_sell_ratio,
                    :buy_vol,
                    :sell_vol,
                    :ingest_time
                )
                on conflict (instrument_id, ts, period_code) do update
                set
                    buy_sell_ratio = excluded.buy_sell_ratio,
                    buy_vol = excluded.buy_vol,
                    sell_vol = excluded.sell_vol,
                    ingest_time = excluded.ingest_time
                """
            ),
            {
                "instrument_id": instrument_id,
                "ts": event.event_time,
                "period_code": event.period_code,
                "buy_sell_ratio": event.buy_sell_ratio,
                "buy_vol": event.buy_vol,
                "sell_vol": event.sell_vol,
                "ingest_time": event.ingest_time,
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


class OrderBookSnapshotRepository:
    def upsert(self, connection: Connection, event: OrderBookSnapshotEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.orderbook_snapshots (
                    instrument_id,
                    snapshot_time,
                    ingest_time,
                    depth_levels,
                    bids_json,
                    asks_json,
                    checksum,
                    source
                ) values (
                    :instrument_id,
                    :snapshot_time,
                    :ingest_time,
                    :depth_levels,
                    cast(:bids_json as jsonb),
                    cast(:asks_json as jsonb),
                    :checksum,
                    :source
                )
                on conflict (instrument_id, snapshot_time) do update
                set
                    ingest_time = excluded.ingest_time,
                    depth_levels = excluded.depth_levels,
                    bids_json = excluded.bids_json,
                    asks_json = excluded.asks_json,
                    checksum = excluded.checksum,
                    source = excluded.source
                """
            ),
            {
                "instrument_id": instrument_id,
                "snapshot_time": event.snapshot_time,
                "ingest_time": event.ingest_time,
                "depth_levels": event.depth_levels,
                "bids_json": json.dumps(event.bids, default=str),
                "asks_json": json.dumps(event.asks, default=str),
                "checksum": event.checksum,
                "source": event.source,
            },
        )


class OrderBookDeltaRepository:
    def insert(self, connection: Connection, event: OrderBookDeltaEvent) -> int:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        return int(
            connection.execute(
                text(
                    """
                    insert into md.orderbook_deltas (
                        instrument_id,
                        event_time,
                        ingest_time,
                        first_update_id,
                        final_update_id,
                        bids_json,
                        asks_json,
                        checksum,
                        source
                    ) values (
                        :instrument_id,
                        :event_time,
                        :ingest_time,
                        :first_update_id,
                        :final_update_id,
                        cast(:bids_json as jsonb),
                        cast(:asks_json as jsonb),
                        :checksum,
                        :source
                    )
                    returning delta_id
                    """
                ),
                {
                    "instrument_id": instrument_id,
                    "event_time": event.event_time,
                    "ingest_time": event.ingest_time,
                    "first_update_id": event.first_update_id,
                    "final_update_id": event.final_update_id,
                    "bids_json": json.dumps(event.bids, default=str),
                    "asks_json": json.dumps(event.asks, default=str),
                    "checksum": event.checksum,
                    "source": event.source,
                },
            ).scalar_one()
        )


class MarkPriceRepository:
    def upsert(self, connection: Connection, event: MarkPriceEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.mark_prices (
                    instrument_id,
                    ts,
                    mark_price,
                    funding_basis_bps,
                    ingest_time
                ) values (
                    :instrument_id,
                    :ts,
                    :mark_price,
                    :funding_basis_bps,
                    :ingest_time
                )
                on conflict (instrument_id, ts) do update
                set
                    mark_price = excluded.mark_price,
                    funding_basis_bps = excluded.funding_basis_bps,
                    ingest_time = excluded.ingest_time
                """
            ),
            {
                "instrument_id": instrument_id,
                "ts": event.event_time,
                "mark_price": event.mark_price,
                "funding_basis_bps": event.funding_basis_bps,
                "ingest_time": event.ingest_time,
            },
        )


class IndexPriceRepository:
    def upsert(self, connection: Connection, event: IndexPriceEvent) -> None:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        connection.execute(
            text(
                """
                insert into md.index_prices (
                    instrument_id,
                    ts,
                    index_price,
                    ingest_time
                ) values (
                    :instrument_id,
                    :ts,
                    :index_price,
                    :ingest_time
                )
                on conflict (instrument_id, ts) do update
                set
                    index_price = excluded.index_price,
                    ingest_time = excluded.ingest_time
                """
            ),
            {
                "instrument_id": instrument_id,
                "ts": event.event_time,
                "index_price": event.index_price,
                "ingest_time": event.ingest_time,
            },
        )


class LiquidationRepository:
    def insert(self, connection: Connection, event: LiquidationEvent) -> int:
        instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        return int(
            connection.execute(
                text(
                    """
                    insert into md.liquidations (
                        instrument_id,
                        event_time,
                        ingest_time,
                        side,
                        price,
                        qty,
                        notional,
                        source,
                        metadata_json
                    ) values (
                        :instrument_id,
                        :event_time,
                        :ingest_time,
                        :side,
                        :price,
                        :qty,
                        :notional,
                        :source,
                        cast(:metadata_json as jsonb)
                    )
                    returning liquidation_id
                    """
                ),
                {
                    "instrument_id": instrument_id,
                    "event_time": event.event_time,
                    "ingest_time": event.ingest_time,
                    "side": event.side,
                    "price": event.price,
                    "qty": event.qty,
                    "notional": event.notional,
                    "source": event.source,
                    "metadata_json": json.dumps(event.metadata_json),
                },
            ).scalar_one()
        )


class RawMarketEventRepository:
    def insert(self, connection: Connection, event: RawMarketEvent) -> int:
        exchange_id = resolve_exchange_id(connection, event.exchange_code)
        instrument_id = None
        if event.unified_symbol:
            instrument_id = resolve_instrument_id(connection, event.exchange_code, event.unified_symbol)
        return int(
            connection.execute(
                text(
                    """
                    insert into md.raw_market_events (
                        exchange_id,
                        instrument_id,
                        channel,
                        event_type,
                        event_time,
                        ingest_time,
                        source_message_id,
                        payload_json
                    ) values (
                        :exchange_id,
                        :instrument_id,
                        :channel,
                        :event_type,
                        :event_time,
                        :ingest_time,
                        :source_message_id,
                        cast(:payload_json as jsonb)
                    )
                    returning raw_event_id
                    """
                ),
                {
                    "exchange_id": exchange_id,
                    "instrument_id": instrument_id,
                    "channel": event.channel,
                    "event_type": event.event_type,
                    "event_time": event.event_time,
                    "ingest_time": event.ingest_time,
                    "source_message_id": event.source_message_id,
                    "payload_json": json.dumps(event.payload_json),
                },
            ).scalar_one()
        )
