from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ingestion.binance.public_rest import BinancePublicRestClient
from storage.db import transaction_scope
from storage.repositories.market_data import (
    FundingRateRepository,
    IndexPriceRepository,
    MarkPriceRepository,
    OpenInterestRepository,
)
from storage.repositories.ops import IngestionJobRepository, SystemLogRecord, SystemLogRepository


@dataclass(slots=True)
class MarketSnapshotRefreshResult:
    ingestion_job_id: int
    status: str
    records_written: int


def run_market_snapshot_refresh(
    *,
    symbol: str,
    unified_symbol: str,
    client: BinancePublicRestClient | None = None,
    requested_by: str = "system",
    exchange_code: str = "binance",
    funding_start_time: datetime | None = None,
    funding_end_time: datetime | None = None,
) -> MarketSnapshotRefreshResult:
    snapshot_client = client or BinancePublicRestClient()
    observed_at = datetime.now(timezone.utc)
    with transaction_scope() as connection:
        job_repo = IngestionJobRepository()
        log_repo = SystemLogRepository()
        job_id = job_repo.create_job(
            connection,
            service_name="market_snapshot_refresh",
            data_type="funding_open_interest_mark_index",
            exchange_code=exchange_code,
            unified_symbol=unified_symbol,
            schedule_type="poll",
            status="running",
            requested_by=requested_by,
            window_start=funding_start_time,
            window_end=funding_end_time,
            metadata_json={"job_type": "market_snapshot_refresh"},
        )
        log_repo.insert(
            connection,
            SystemLogRecord(
                service_name="market_snapshot_refresh",
                level="info",
                message=f"starting market snapshot refresh for {unified_symbol}",
                context_json={"job_id": job_id},
            ),
        )

        try:
            funding_rows = snapshot_client.fetch_funding_rate_history(
                symbol,
                start_time=funding_start_time,
                end_time=funding_end_time,
            )
            funding_events = snapshot_client.normalize_funding_rates(symbol, funding_rows, unified_symbol=unified_symbol)
            open_interest_event = snapshot_client.normalize_open_interest(
                symbol,
                snapshot_client.fetch_open_interest(symbol),
                observed_at=observed_at,
                unified_symbol=unified_symbol,
            )
            mark_event, index_event = snapshot_client.normalize_premium_index(
                symbol,
                snapshot_client.fetch_premium_index(symbol),
                observed_at=observed_at,
                unified_symbol=unified_symbol,
            )

            for event in funding_events:
                FundingRateRepository().upsert(connection, event)
            OpenInterestRepository().upsert(connection, open_interest_event)
            MarkPriceRepository().upsert(connection, mark_event)
            IndexPriceRepository().upsert(connection, index_event)

            rows_written = len(funding_events) + 3
            job_repo.finish_job(
                connection,
                job_id,
                status="succeeded",
                records_expected=rows_written,
                records_written=rows_written,
                finished_at=datetime.now(timezone.utc),
                metadata_json={"job_type": "market_snapshot_refresh"},
            )
            log_repo.insert(
                connection,
                SystemLogRecord(
                    service_name="market_snapshot_refresh",
                    level="info",
                    message=f"market snapshot refresh finished for {unified_symbol}",
                    context_json={"job_id": job_id, "rows_written": rows_written},
                ),
            )
            return MarketSnapshotRefreshResult(job_id, "succeeded", rows_written)
        except Exception as exc:
            job_repo.finish_job(
                connection,
                job_id,
                status="failed_terminal",
                error_message=str(exc),
                finished_at=datetime.now(timezone.utc),
                metadata_json={"job_type": "market_snapshot_refresh"},
            )
            log_repo.insert(
                connection,
                SystemLogRecord(
                    service_name="market_snapshot_refresh",
                    level="error",
                    message=f"market snapshot refresh failed for {unified_symbol}",
                    context_json={"job_id": job_id, "error": str(exc)},
                ),
            )
            raise
