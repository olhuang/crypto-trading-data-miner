from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from models.market import InstrumentMetadata
from storage.lookups import resolve_asset_id, resolve_exchange_id


class ExchangeRepository:
    def list_all(self, connection: Connection) -> list[dict[str, Any]]:
        rows = connection.execute(
            text(
                """
                select exchange_id, exchange_code, exchange_name, timezone
                from ref.exchanges
                order by exchange_code
                """
            )
        )
        return [dict(row._mapping) for row in rows]


class AssetRepository:
    def list_all(self, connection: Connection) -> list[dict[str, Any]]:
        rows = connection.execute(
            text(
                """
                select asset_id, asset_code, asset_name, asset_type
                from ref.assets
                order by asset_code
                """
            )
        )
        return [dict(row._mapping) for row in rows]

    def upsert(self, connection: Connection, *, asset_code: str, asset_name: str, asset_type: str) -> None:
        connection.execute(
            text(
                """
                insert into ref.assets (
                    asset_code,
                    asset_name,
                    asset_type
                ) values (
                    :asset_code,
                    :asset_name,
                    :asset_type
                )
                on conflict (asset_code) do update
                set
                    asset_name = excluded.asset_name,
                    asset_type = excluded.asset_type
                """
            ),
            {
                "asset_code": asset_code,
                "asset_name": asset_name,
                "asset_type": asset_type,
            },
        )


class InstrumentRepository:
    def get_by_key(
        self,
        connection: Connection,
        exchange_code: str,
        venue_symbol: str,
        instrument_type: str,
    ) -> dict[str, Any] | None:
        row = connection.execute(
            text(
                """
                select
                    e.exchange_code,
                    i.venue_symbol,
                    i.unified_symbol,
                    i.instrument_type,
                    base_asset.asset_code as base_asset,
                    quote_asset.asset_code as quote_asset,
                    settlement_asset.asset_code as settlement_asset,
                    i.tick_size,
                    i.lot_size,
                    i.min_qty,
                    i.min_notional,
                    i.contract_size,
                    i.status,
                    i.launch_time,
                    i.delist_time
                from ref.instruments i
                join ref.exchanges e on e.exchange_id = i.exchange_id
                join ref.assets base_asset on base_asset.asset_id = i.base_asset_id
                join ref.assets quote_asset on quote_asset.asset_id = i.quote_asset_id
                left join ref.assets settlement_asset on settlement_asset.asset_id = i.settlement_asset_id
                where e.exchange_code = :exchange_code
                  and i.venue_symbol = :venue_symbol
                  and i.instrument_type = :instrument_type
                """
            ),
            {
                "exchange_code": exchange_code,
                "venue_symbol": venue_symbol,
                "instrument_type": instrument_type,
            },
        ).mappings().first()
        return None if row is None else dict(row)

    def upsert(self, connection: Connection, instrument: InstrumentMetadata) -> None:
        exchange_id = resolve_exchange_id(connection, instrument.exchange_code)
        base_asset_id = resolve_asset_id(connection, instrument.base_asset)
        quote_asset_id = resolve_asset_id(connection, instrument.quote_asset)
        settlement_asset_id = (
            resolve_asset_id(connection, instrument.settlement_asset)
            if instrument.settlement_asset
            else None
        )

        connection.execute(
            text(
                """
                insert into ref.instruments (
                    exchange_id,
                    venue_symbol,
                    unified_symbol,
                    instrument_type,
                    base_asset_id,
                    quote_asset_id,
                    settlement_asset_id,
                    tick_size,
                    lot_size,
                    min_qty,
                    min_notional,
                    contract_size,
                    status,
                    launch_time,
                    delist_time
                ) values (
                    :exchange_id,
                    :venue_symbol,
                    :unified_symbol,
                    :instrument_type,
                    :base_asset_id,
                    :quote_asset_id,
                    :settlement_asset_id,
                    :tick_size,
                    :lot_size,
                    :min_qty,
                    :min_notional,
                    :contract_size,
                    :status,
                    :launch_time,
                    :delist_time
                )
                on conflict (exchange_id, venue_symbol, instrument_type) do update
                set
                    unified_symbol = excluded.unified_symbol,
                    base_asset_id = excluded.base_asset_id,
                    quote_asset_id = excluded.quote_asset_id,
                    settlement_asset_id = excluded.settlement_asset_id,
                    tick_size = excluded.tick_size,
                    lot_size = excluded.lot_size,
                    min_qty = excluded.min_qty,
                    min_notional = excluded.min_notional,
                    contract_size = excluded.contract_size,
                    status = excluded.status,
                    launch_time = excluded.launch_time,
                    delist_time = excluded.delist_time
                """
            ),
            {
                "exchange_id": exchange_id,
                "venue_symbol": instrument.venue_symbol,
                "unified_symbol": instrument.unified_symbol,
                "instrument_type": instrument.instrument_type,
                "base_asset_id": base_asset_id,
                "quote_asset_id": quote_asset_id,
                "settlement_asset_id": settlement_asset_id,
                "tick_size": instrument.tick_size,
                "lot_size": instrument.lot_size,
                "min_qty": instrument.min_qty,
                "min_notional": instrument.min_notional,
                "contract_size": instrument.contract_size,
                "status": instrument.status,
                "launch_time": instrument.launch_time,
                "delist_time": instrument.delist_time,
            },
        )

    def list_by_exchange(self, connection: Connection, exchange_code: str) -> list[dict[str, Any]]:
        rows = connection.execute(
            text(
                """
                select
                    i.instrument_id,
                    e.exchange_code,
                    i.venue_symbol,
                    i.unified_symbol,
                    i.instrument_type,
                    i.status
                from ref.instruments i
                join ref.exchanges e on e.exchange_id = i.exchange_id
                where e.exchange_code = :exchange_code
                order by i.instrument_type, i.venue_symbol
                """
            ),
            {"exchange_code": exchange_code},
        )
        return [dict(row._mapping) for row in rows]
