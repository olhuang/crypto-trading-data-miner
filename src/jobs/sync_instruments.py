from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from ingestion.binance.public_rest import BinancePublicRestClient
from models.market import InstrumentMetadata
from storage.db import transaction_scope
from storage.repositories.instruments import AssetRepository, InstrumentRepository
from storage.repositories.ops import IngestionJobRepository, SystemLogRecord, SystemLogRepository


@dataclass(slots=True)
class InstrumentSyncResult:
    ingestion_job_id: int
    status: str
    summary: dict[str, int]
    diffs: list[dict[str, Any]]


STABLECOIN_CODES = {"USDT", "USDC", "FDUSD", "TUSD", "BUSD", "USDP", "DAI"}


def _asset_type_for_code(asset_code: str) -> str:
    return "stablecoin" if asset_code.upper() in STABLECOIN_CODES else "coin"


def _asset_name_for_code(asset_code: str) -> str:
    stablecoin_names = {
        "USDT": "Tether USD",
        "USDC": "USD Coin",
        "FDUSD": "First Digital USD",
        "TUSD": "TrueUSD",
        "BUSD": "Binance USD",
        "USDP": "Pax Dollar",
        "DAI": "Dai",
    }
    return stablecoin_names.get(asset_code.upper(), asset_code.upper())


def _ensure_assets_exist(connection, instruments: list[InstrumentMetadata]) -> int:
    repo = AssetRepository()
    asset_codes: set[str] = set()
    for instrument in instruments:
        asset_codes.add(instrument.base_asset)
        asset_codes.add(instrument.quote_asset)
        if instrument.settlement_asset:
            asset_codes.add(instrument.settlement_asset)

    inserted_or_updated = 0
    for asset_code in sorted(asset_codes):
        repo.upsert(
            connection,
            asset_code=asset_code,
            asset_name=_asset_name_for_code(asset_code),
            asset_type=_asset_type_for_code(asset_code),
        )
        inserted_or_updated += 1
    return inserted_or_updated


def _comparable_instrument_payload(model: InstrumentMetadata) -> dict[str, Any]:
    payload = model.model_dump(mode="json", by_alias=True)
    payload.pop("payload_json", None)
    return payload


def _field_diffs(existing: dict[str, Any] | None, model: InstrumentMetadata) -> tuple[str, list[dict[str, Any]]]:
    normalized = _comparable_instrument_payload(model)
    if existing is None:
        return "inserted", []

    diffs: list[dict[str, Any]] = []
    for field_name, new_value in normalized.items():
        old_value = existing.get(field_name)
        old_string = None if old_value is None else str(old_value)
        new_string = None if new_value is None else str(new_value)
        if old_string != new_string:
            diffs.append({"field_name": field_name, "old_value": old_string, "new_value": new_string})
    return ("updated" if diffs else "unchanged"), diffs


def run_instrument_sync(
    *,
    client: BinancePublicRestClient | None = None,
    requested_by: str = "system",
    exchange_code: str = "binance",
) -> InstrumentSyncResult:
    sync_client = client or BinancePublicRestClient()
    started_at = datetime.now(timezone.utc)
    with transaction_scope() as connection:
        job_repo = IngestionJobRepository()
        log_repo = SystemLogRepository()
        job_id = job_repo.create_job(
            connection,
            service_name="instrument_sync",
            data_type="instrument_metadata",
            exchange_code=exchange_code,
            schedule_type="manual",
            status="running",
            requested_by=requested_by,
            window_start=started_at,
            metadata_json={"job_type": "instrument_sync"},
        )
        log_repo.insert(
            connection,
            SystemLogRecord(
                service_name="instrument_sync",
                level="info",
                message=f"starting instrument sync for {exchange_code}",
                context_json={"job_id": job_id, "requested_by": requested_by},
            ),
        )

        try:
            instruments = sync_client.fetch_instruments()
            asset_rows_touched = _ensure_assets_exist(connection, instruments)
            repo = InstrumentRepository()
            summary = {
                "assets_touched": asset_rows_touched,
                "instruments_seen": 0,
                "instruments_inserted": 0,
                "instruments_updated": 0,
                "instruments_unchanged": 0,
            }
            diffs: list[dict[str, Any]] = []

            for instrument in instruments:
                existing = repo.get_by_key(
                    connection,
                    instrument.exchange_code,
                    instrument.venue_symbol,
                    str(instrument.instrument_type),
                )
                change_type, field_diffs = _field_diffs(existing, instrument)
                repo.upsert(connection, instrument)
                summary["instruments_seen"] += 1
                summary[f"instruments_{change_type}"] += 1
                if change_type != "unchanged":
                    diffs.append(
                        {
                            "unified_symbol": instrument.unified_symbol,
                            "venue_symbol": instrument.venue_symbol,
                            "change_type": change_type,
                            "field_diffs": field_diffs,
                        }
                    )

            job_repo.finish_job(
                connection,
                job_id,
                status="succeeded",
                records_written=summary["instruments_inserted"] + summary["instruments_updated"],
                metadata_json={"job_type": "instrument_sync", "summary": summary, "diffs": diffs},
                finished_at=datetime.now(timezone.utc),
            )
            log_repo.insert(
                connection,
                SystemLogRecord(
                    service_name="instrument_sync",
                    level="info",
                    message=f"instrument sync finished for {exchange_code}",
                    context_json={"job_id": job_id, "summary": summary},
                ),
            )
            return InstrumentSyncResult(job_id, "succeeded", summary, diffs)
        except Exception as exc:
            job_repo.finish_job(
                connection,
                job_id,
                status="failed_terminal",
                error_message=str(exc),
                metadata_json={"job_type": "instrument_sync"},
                finished_at=datetime.now(timezone.utc),
            )
            log_repo.insert(
                connection,
                SystemLogRecord(
                    service_name="instrument_sync",
                    level="error",
                    message=f"instrument sync failed for {exchange_code}",
                    context_json={"job_id": job_id, "error": str(exc)},
                ),
            )
            raise
