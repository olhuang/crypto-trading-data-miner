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
    history_rows_written: int


def run_market_snapshot_refresh(
    *,
    symbol: str,
    unified_symbol: str,
    client: BinancePublicRestClient | None = None,
    requested_by: str = "system",
    exchange_code: str = "binance",
    funding_start_time: datetime | None = None,
    funding_end_time: datetime | None = None,
    history_start_time: datetime | None = None,
    history_end_time: datetime | None = None,
    open_interest_period: str = "5m",
    price_interval: str = "1m",
    include_funding: bool = True,
    include_open_interest: bool = True,
    include_mark_price: bool = True,
    include_index_price: bool = True,
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
            funding_events = []
            if include_funding:
                funding_rows = snapshot_client.fetch_funding_rate_history(
                    symbol,
                    start_time=funding_start_time,
                    end_time=funding_end_time,
                )
                funding_events = snapshot_client.normalize_funding_rates(symbol, funding_rows, unified_symbol=unified_symbol)
            if history_start_time or history_end_time:
                open_interest_events = (
                    snapshot_client.normalize_open_interest_history(
                        symbol,
                        snapshot_client.fetch_open_interest_history(
                            symbol,
                            period=open_interest_period,
                            start_time=history_start_time,
                            end_time=history_end_time,
                        ),
                        unified_symbol=unified_symbol,
                    )
                    if include_open_interest
                    else []
                )
                mark_events = (
                    snapshot_client.normalize_mark_price_klines(
                        symbol,
                        snapshot_client.fetch_mark_price_klines(
                            symbol,
                            interval=price_interval,
                            start_time=history_start_time,
                            end_time=history_end_time,
                        ),
                        unified_symbol=unified_symbol,
                    )
                    if include_mark_price
                    else []
                )
                index_events = (
                    snapshot_client.normalize_index_price_klines(
                        symbol,
                        snapshot_client.fetch_index_price_klines(
                            symbol,
                            interval=price_interval,
                            start_time=history_start_time,
                            end_time=history_end_time,
                        ),
                        unified_symbol=unified_symbol,
                    )
                    if include_index_price
                    else []
                )
            else:
                open_interest_events = (
                    [
                        snapshot_client.normalize_open_interest(
                            symbol,
                            snapshot_client.fetch_open_interest(symbol),
                            observed_at=observed_at,
                            unified_symbol=unified_symbol,
                        )
                    ]
                    if include_open_interest
                    else []
                )
                if include_mark_price or include_index_price:
                    mark_event, index_event = snapshot_client.normalize_premium_index(
                        symbol,
                        snapshot_client.fetch_premium_index(symbol),
                        observed_at=observed_at,
                        unified_symbol=unified_symbol,
                    )
                    mark_events = [mark_event] if include_mark_price else []
                    index_events = [index_event] if include_index_price else []
                else:
                    mark_events = []
                    index_events = []

            for event in funding_events:
                FundingRateRepository().upsert(connection, event)
            for event in open_interest_events:
                OpenInterestRepository().upsert(connection, event)
            for event in mark_events:
                MarkPriceRepository().upsert(connection, event)
            for event in index_events:
                IndexPriceRepository().upsert(connection, event)

            history_rows_written = len(open_interest_events) + len(mark_events) + len(index_events)
            rows_written = len(funding_events) + history_rows_written
            job_repo.finish_job(
                connection,
                job_id,
                status="succeeded",
                records_expected=rows_written,
                records_written=rows_written,
                finished_at=datetime.now(timezone.utc),
                metadata_json={
                    "job_type": "market_snapshot_refresh",
                    "history_mode": bool(history_start_time or history_end_time),
                    "history_start_time": history_start_time.isoformat() if history_start_time else None,
                    "history_end_time": history_end_time.isoformat() if history_end_time else None,
                    "history_rows_written": history_rows_written,
                    "funding_rows_written": len(funding_events),
                    "include_funding": include_funding,
                    "include_open_interest": include_open_interest,
                    "include_mark_price": include_mark_price,
                    "include_index_price": include_index_price,
                },
            )
            log_repo.insert(
                connection,
                SystemLogRecord(
                    service_name="market_snapshot_refresh",
                    level="info",
                    message=f"market snapshot refresh finished for {unified_symbol}",
                    context_json={"job_id": job_id, "rows_written": rows_written, "history_rows_written": history_rows_written},
                ),
            )
            return MarketSnapshotRefreshResult(job_id, "succeeded", rows_written, history_rows_written)
        except Exception as exc:
            job_repo.finish_job(
                connection,
                job_id,
                status="failed_terminal",
                error_message=str(exc),
                finished_at=datetime.now(timezone.utc),
                metadata_json={
                    "job_type": "market_snapshot_refresh",
                    "history_mode": bool(history_start_time or history_end_time),
                    "history_start_time": history_start_time.isoformat() if history_start_time else None,
                    "history_end_time": history_end_time.isoformat() if history_end_time else None,
                    "include_funding": include_funding,
                    "include_open_interest": include_open_interest,
                    "include_mark_price": include_mark_price,
                    "include_index_price": include_index_price,
                },
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
