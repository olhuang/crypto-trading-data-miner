from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ingestion.binance.public_rest import BinancePublicRestClient
from storage.db import transaction_scope
from storage.repositories.market_data import BarRepository
from storage.repositories.ops import IngestionJobRepository, SystemLogRecord, SystemLogRepository


@dataclass(slots=True)
class BarBackfillResult:
    ingestion_job_id: int
    status: str
    rows_written: int


def run_bar_backfill(
    *,
    symbol: str,
    unified_symbol: str,
    interval: str,
    start_time: datetime,
    end_time: datetime,
    client: BinancePublicRestClient | None = None,
    requested_by: str = "system",
    exchange_code: str = "binance",
) -> BarBackfillResult:
    backfill_client = client or BinancePublicRestClient()
    with transaction_scope() as connection:
        job_repo = IngestionJobRepository()
        log_repo = SystemLogRepository()
        job_id = job_repo.create_job(
            connection,
            service_name="bar_backfill",
            data_type="bars_1m",
            exchange_code=exchange_code,
            unified_symbol=unified_symbol,
            schedule_type="manual",
            status="running",
            requested_by=requested_by,
            window_start=start_time,
            window_end=end_time,
            metadata_json={"job_type": "bar_backfill", "interval": interval},
        )
        log_repo.insert(
            connection,
            SystemLogRecord(
                service_name="bar_backfill",
                level="info",
                message=f"starting bar backfill for {unified_symbol}",
                context_json={"job_id": job_id, "interval": interval},
            ),
        )

        try:
            rows = backfill_client.fetch_klines(symbol, interval=interval, start_time=start_time, end_time=end_time)
            events = backfill_client.normalize_klines(symbol, rows, unified_symbol=unified_symbol, interval=interval)
            repo = BarRepository()
            for event in events:
                repo.upsert(connection, event)

            job_repo.finish_job(
                connection,
                job_id,
                status="succeeded",
                records_expected=len(rows),
                records_written=len(events),
                finished_at=datetime.now(timezone.utc),
                metadata_json={"job_type": "bar_backfill", "interval": interval},
            )
            log_repo.insert(
                connection,
                SystemLogRecord(
                    service_name="bar_backfill",
                    level="info",
                    message=f"bar backfill finished for {unified_symbol}",
                    context_json={"job_id": job_id, "rows_written": len(events)},
                ),
            )
            return BarBackfillResult(job_id, "succeeded", len(events))
        except Exception as exc:
            job_repo.finish_job(
                connection,
                job_id,
                status="failed_terminal",
                error_message=str(exc),
                finished_at=datetime.now(timezone.utc),
                metadata_json={"job_type": "bar_backfill", "interval": interval},
            )
            log_repo.insert(
                connection,
                SystemLogRecord(
                    service_name="bar_backfill",
                    level="error",
                    message=f"bar backfill failed for {unified_symbol}",
                    context_json={"job_id": job_id, "error": str(exc)},
                ),
            )
            raise
