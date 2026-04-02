from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.engine import Connection


@dataclass(slots=True)
class TraceabilityLink:
    resource_type: str
    record_locator: str
    match_strategy: str


def get_raw_event_detail(connection: Connection, raw_event_id: int) -> dict[str, Any] | None:
    row = connection.exec_driver_sql(
        """
        select
            raw.raw_event_id,
            exchange.exchange_code,
            instrument.unified_symbol,
            raw.channel,
            raw.event_type,
            raw.event_time,
            raw.ingest_time,
            raw.source_message_id,
            raw.payload_json
        from md.raw_market_events raw
        join ref.exchanges exchange on exchange.exchange_id = raw.exchange_id
        left join ref.instruments instrument on instrument.instrument_id = raw.instrument_id
        where raw.raw_event_id = %s
        """,
        (raw_event_id,),
    ).mappings().first()
    return None if row is None else dict(row)


def normalized_links_for_raw_event(connection: Connection, raw_event_id: int) -> list[TraceabilityLink]:
    raw_event = get_raw_event_detail(connection, raw_event_id)
    if raw_event is None or raw_event.get("unified_symbol") is None:
        return []

    event_type = raw_event.get("event_type")
    instrument_symbol = raw_event["unified_symbol"]
    event_time = raw_event.get("event_time")
    source_message_id = raw_event.get("source_message_id")
    links: list[TraceabilityLink] = []

    if event_type == "trade":
        trade = connection.exec_driver_sql(
            """
            select trade.exchange_trade_id
            from md.trades trade
            join ref.instruments instrument on instrument.instrument_id = trade.instrument_id
            where instrument.unified_symbol = %s
              and (
                    trade.exchange_trade_id = %s
                    or (trade.event_time = %s and trade.exchange_trade_id = %s)
                  )
            order by trade.event_time desc
            limit 1
            """,
            (instrument_symbol, source_message_id, event_time, source_message_id),
        ).first()
        if trade is not None:
            links.append(
                TraceabilityLink(
                    resource_type="trade",
                    record_locator=f"trade:{instrument_symbol}:{trade[0]}",
                    match_strategy="exchange_trade_id",
                )
            )

    if event_type == "markPriceUpdate":
        mark_price = connection.exec_driver_sql(
            """
            select price.mark_price_id
            from md.mark_prices price
            join ref.instruments instrument on instrument.instrument_id = price.instrument_id
            where instrument.unified_symbol = %s
              and price.ts = %s
            order by price.mark_price_id desc
            limit 1
            """,
            (instrument_symbol, event_time),
        ).first()
        if mark_price is not None:
            links.append(
                TraceabilityLink(
                    resource_type="mark_price",
                    record_locator=f"mark_price_id:{mark_price[0]}",
                    match_strategy="instrument_id+event_time",
                )
            )

    if event_type == "forceOrder":
        liquidation = connection.exec_driver_sql(
            """
            select liq.liquidation_id
            from md.liquidations liq
            join ref.instruments instrument on instrument.instrument_id = liq.instrument_id
            where instrument.unified_symbol = %s
              and liq.event_time = %s
            order by liq.liquidation_id desc
            limit 1
            """,
            (instrument_symbol, event_time),
        ).first()
        if liquidation is not None:
            links.append(
                TraceabilityLink(
                    resource_type="liquidation",
                    record_locator=f"liquidation_id:{liquidation[0]}",
                    match_strategy="instrument_id+event_time",
                )
            )

    return links


def replay_readiness_summary(connection: Connection) -> dict[str, Any]:
    raw_event_count = int(connection.exec_driver_sql("select count(*) from md.raw_market_events").scalar_one())
    trade_count = int(connection.exec_driver_sql("select count(*) from md.trades").scalar_one())
    mark_price_count = int(connection.exec_driver_sql("select count(*) from md.mark_prices").scalar_one())
    liquidation_count = int(connection.exec_driver_sql("select count(*) from md.liquidations").scalar_one())
    open_gap_count = int(connection.exec_driver_sql("select count(*) from ops.data_gaps where status = 'open'").scalar_one())
    retained_streams = [
        row[0]
        for row in connection.exec_driver_sql(
            """
            select distinct channel
            from md.raw_market_events
            where channel is not null
            order by channel
            """
        ).all()
    ]

    raw_coverage_status = "ready" if raw_event_count > 0 else "not_ready"
    normalized_coverage_status = (
        "ready" if trade_count > 0 and mark_price_count > 0 and liquidation_count > 0 else "partial"
    )
    return {
        "raw_coverage_status": raw_coverage_status,
        "normalized_coverage_status": normalized_coverage_status,
        "retained_streams": retained_streams,
        "known_gaps": open_gap_count,
        "retention_policy": {
            "raw_market_events": "retain recent hot data in PostgreSQL, archive colder partitions later",
            "orderbook_deltas": "retain only as long as replay and modeling needs justify",
            "orderbook_snapshots": "retain managed recent coverage in PostgreSQL and archive older snapshots later",
        },
        "replay_ready_datasets": {
            "trade_stream": trade_count > 0 and raw_event_count > 0,
            "mark_price_stream": mark_price_count > 0 and raw_event_count > 0,
            "liquidation_stream": liquidation_count > 0 and raw_event_count > 0,
        },
    }
