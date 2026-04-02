from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from ingestion.binance.public_rest import BinancePublicRestClient
from models.market import InstrumentMetadata
from storage.db import transaction_scope
from storage.repositories.instruments import InstrumentRepository
from storage.repositories.ops import IngestionJobRepository, SystemLogRecord, SystemLogRepository


@dataclass(slots=True)
class InstrumentSyncResult:
    ingestion_job_id: int
    status: str
    summary: dict[str, int]
    diffs: list[dict[str, Any]]


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
            repo = InstrumentRepository()
            summary = {"instruments_seen": 0, "instruments_inserted": 0, "instruments_updated": 0, "instruments_unchanged": 0}
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
