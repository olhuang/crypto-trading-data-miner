from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ingestion.binance.public_rest import BinancePublicRestClient
from storage.db import transaction_scope
from storage.repositories.market_data import (
    FundingRateRepository,
    GlobalLongShortAccountRatioRepository,
    IndexPriceRepository,
    MarkPriceRepository,
    OpenInterestRepository,
    TakerLongShortRatioRepository,
    TopTraderLongShortAccountRatioRepository,
    TopTraderLongShortPositionRatioRepository,
)
from storage.repositories.ops import IngestionJobRepository, SystemLogRecord, SystemLogRepository


@dataclass(slots=True)
class MarketSnapshotRefreshResult:
    ingestion_job_id: int
    status: str
    records_written: int
    history_rows_written: int


RETENTION_LIMITED_INTERVAL = timedelta(minutes=5)
DEFAULT_RETENTION_HISTORY_LOOKBACK_MINUTES = 60


def _floor_to_interval(timestamp: datetime, interval: timedelta) -> datetime:
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    interval_seconds = int(interval.total_seconds())
    elapsed_seconds = int((timestamp - epoch).total_seconds())
    floored_seconds = elapsed_seconds - (elapsed_seconds % interval_seconds)
    return epoch + timedelta(seconds=floored_seconds)


def _recent_retention_history_window(
    *,
    observed_at: datetime,
    lookback_minutes: int,
) -> tuple[datetime, datetime]:
    aligned_end = _floor_to_interval(observed_at, RETENTION_LIMITED_INTERVAL)
    aligned_start = aligned_end - timedelta(minutes=lookback_minutes)
    if aligned_start > aligned_end:
        aligned_start = aligned_end
    return aligned_start, aligned_end


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
    sentiment_ratio_period: str = "5m",
    include_funding: bool = True,
    include_open_interest: bool = True,
    include_mark_price: bool = True,
    include_index_price: bool = True,
    include_global_long_short_account_ratio: bool = False,
    include_top_trader_long_short_account_ratio: bool = False,
    include_top_trader_long_short_position_ratio: bool = False,
    include_taker_long_short_ratio: bool = False,
    observed_at: datetime | None = None,
    use_recent_history_for_retention_limited: bool = False,
    retention_history_lookback_minutes: int = DEFAULT_RETENTION_HISTORY_LOOKBACK_MINUTES,
) -> MarketSnapshotRefreshResult:
    snapshot_client = client or BinancePublicRestClient()
    observed_at = observed_at or datetime.now(timezone.utc)
    job_window_start = min(
        (value for value in (funding_start_time, history_start_time) if value is not None),
        default=None,
    )
    job_window_end = max(
        (value for value in (funding_end_time, history_end_time) if value is not None),
        default=None,
    )
    with transaction_scope() as connection:
        job_repo = IngestionJobRepository()
        log_repo = SystemLogRepository()
        job_id = job_repo.create_job(
            connection,
            service_name="market_snapshot_refresh",
            data_type="funding_open_interest_mark_index_sentiment",
            exchange_code=exchange_code,
            unified_symbol=unified_symbol,
            schedule_type="poll",
            status="running",
            requested_by=requested_by,
            window_start=job_window_start,
            window_end=job_window_end,
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
                global_long_short_account_ratio_events = (
                    snapshot_client.normalize_global_long_short_account_ratios(
                        symbol,
                        snapshot_client.fetch_global_long_short_account_ratio_history(
                            symbol,
                            period=sentiment_ratio_period,
                            start_time=history_start_time,
                            end_time=history_end_time,
                        ),
                        period=sentiment_ratio_period,
                        unified_symbol=unified_symbol,
                    )
                    if include_global_long_short_account_ratio
                    else []
                )
                top_trader_long_short_account_ratio_events = (
                    snapshot_client.normalize_top_trader_long_short_account_ratios(
                        symbol,
                        snapshot_client.fetch_top_trader_long_short_account_ratio_history(
                            symbol,
                            period=sentiment_ratio_period,
                            start_time=history_start_time,
                            end_time=history_end_time,
                        ),
                        period=sentiment_ratio_period,
                        unified_symbol=unified_symbol,
                    )
                    if include_top_trader_long_short_account_ratio
                    else []
                )
                top_trader_long_short_position_ratio_events = (
                    snapshot_client.normalize_top_trader_long_short_position_ratios(
                        symbol,
                        snapshot_client.fetch_top_trader_long_short_position_ratio_history(
                            symbol,
                            period=sentiment_ratio_period,
                            start_time=history_start_time,
                            end_time=history_end_time,
                        ),
                        period=sentiment_ratio_period,
                        unified_symbol=unified_symbol,
                    )
                    if include_top_trader_long_short_position_ratio
                    else []
                )
                taker_long_short_ratio_events = (
                    snapshot_client.normalize_taker_long_short_ratios(
                        symbol,
                        snapshot_client.fetch_taker_long_short_ratio_history(
                            symbol,
                            period=sentiment_ratio_period,
                            start_time=history_start_time,
                            end_time=history_end_time,
                        ),
                        period=sentiment_ratio_period,
                        unified_symbol=unified_symbol,
                    )
                    if include_taker_long_short_ratio
                    else []
                )
            else:
                recent_retention_start: datetime | None = None
                recent_retention_end: datetime | None = None
                if use_recent_history_for_retention_limited:
                    recent_retention_start, recent_retention_end = _recent_retention_history_window(
                        observed_at=observed_at,
                        lookback_minutes=retention_history_lookback_minutes,
                    )
                open_interest_events = (
                    snapshot_client.normalize_open_interest_history(
                        symbol,
                        snapshot_client.fetch_open_interest_history(
                            symbol,
                            period=open_interest_period,
                            start_time=recent_retention_start,
                            end_time=recent_retention_end,
                        ),
                        unified_symbol=unified_symbol,
                    )
                    if include_open_interest and use_recent_history_for_retention_limited
                    else (
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
                global_long_short_account_ratio_events = (
                    snapshot_client.normalize_global_long_short_account_ratios(
                        symbol,
                        snapshot_client.fetch_global_long_short_account_ratio_history(
                            symbol,
                            period=sentiment_ratio_period,
                            start_time=recent_retention_start,
                            end_time=recent_retention_end,
                        ),
                        period=sentiment_ratio_period,
                        unified_symbol=unified_symbol,
                    )
                    if include_global_long_short_account_ratio and use_recent_history_for_retention_limited
                    else []
                )
                top_trader_long_short_account_ratio_events = (
                    snapshot_client.normalize_top_trader_long_short_account_ratios(
                        symbol,
                        snapshot_client.fetch_top_trader_long_short_account_ratio_history(
                            symbol,
                            period=sentiment_ratio_period,
                            start_time=recent_retention_start,
                            end_time=recent_retention_end,
                        ),
                        period=sentiment_ratio_period,
                        unified_symbol=unified_symbol,
                    )
                    if include_top_trader_long_short_account_ratio and use_recent_history_for_retention_limited
                    else []
                )
                top_trader_long_short_position_ratio_events = (
                    snapshot_client.normalize_top_trader_long_short_position_ratios(
                        symbol,
                        snapshot_client.fetch_top_trader_long_short_position_ratio_history(
                            symbol,
                            period=sentiment_ratio_period,
                            start_time=recent_retention_start,
                            end_time=recent_retention_end,
                        ),
                        period=sentiment_ratio_period,
                        unified_symbol=unified_symbol,
                    )
                    if include_top_trader_long_short_position_ratio and use_recent_history_for_retention_limited
                    else []
                )
                taker_long_short_ratio_events = (
                    snapshot_client.normalize_taker_long_short_ratios(
                        symbol,
                        snapshot_client.fetch_taker_long_short_ratio_history(
                            symbol,
                            period=sentiment_ratio_period,
                            start_time=recent_retention_start,
                            end_time=recent_retention_end,
                        ),
                        period=sentiment_ratio_period,
                        unified_symbol=unified_symbol,
                    )
                    if include_taker_long_short_ratio and use_recent_history_for_retention_limited
                    else []
                )

            for event in funding_events:
                FundingRateRepository().upsert(connection, event)
            for event in open_interest_events:
                OpenInterestRepository().upsert(connection, event)
            for event in mark_events:
                MarkPriceRepository().upsert(connection, event)
            for event in index_events:
                IndexPriceRepository().upsert(connection, event)
            for event in global_long_short_account_ratio_events:
                GlobalLongShortAccountRatioRepository().upsert(connection, event)
            for event in top_trader_long_short_account_ratio_events:
                TopTraderLongShortAccountRatioRepository().upsert(connection, event)
            for event in top_trader_long_short_position_ratio_events:
                TopTraderLongShortPositionRatioRepository().upsert(connection, event)
            for event in taker_long_short_ratio_events:
                TakerLongShortRatioRepository().upsert(connection, event)

            history_rows_written = (
                len(open_interest_events)
                + len(mark_events)
                + len(index_events)
                + len(global_long_short_account_ratio_events)
                + len(top_trader_long_short_account_ratio_events)
                + len(top_trader_long_short_position_ratio_events)
                + len(taker_long_short_ratio_events)
            )
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
                    "recent_retention_history_mode": bool(use_recent_history_for_retention_limited and not (history_start_time or history_end_time)),
                    "retention_history_lookback_minutes": retention_history_lookback_minutes,
                    "history_start_time": history_start_time.isoformat() if history_start_time else None,
                    "history_end_time": history_end_time.isoformat() if history_end_time else None,
                    "history_rows_written": history_rows_written,
                    "funding_rows_written": len(funding_events),
                    "sentiment_ratio_period": sentiment_ratio_period,
                    "include_funding": include_funding,
                    "include_open_interest": include_open_interest,
                    "include_mark_price": include_mark_price,
                    "include_index_price": include_index_price,
                    "include_global_long_short_account_ratio": include_global_long_short_account_ratio,
                    "include_top_trader_long_short_account_ratio": include_top_trader_long_short_account_ratio,
                    "include_top_trader_long_short_position_ratio": include_top_trader_long_short_position_ratio,
                    "include_taker_long_short_ratio": include_taker_long_short_ratio,
                    "use_recent_history_for_retention_limited": use_recent_history_for_retention_limited,
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
                    "recent_retention_history_mode": bool(use_recent_history_for_retention_limited and not (history_start_time or history_end_time)),
                    "retention_history_lookback_minutes": retention_history_lookback_minutes,
                    "history_start_time": history_start_time.isoformat() if history_start_time else None,
                    "history_end_time": history_end_time.isoformat() if history_end_time else None,
                    "sentiment_ratio_period": sentiment_ratio_period,
                    "include_funding": include_funding,
                    "include_open_interest": include_open_interest,
                    "include_mark_price": include_mark_price,
                    "include_index_price": include_index_price,
                    "include_global_long_short_account_ratio": include_global_long_short_account_ratio,
                    "include_top_trader_long_short_account_ratio": include_top_trader_long_short_account_ratio,
                    "include_top_trader_long_short_position_ratio": include_top_trader_long_short_position_ratio,
                    "include_taker_long_short_ratio": include_taker_long_short_ratio,
                    "use_recent_history_for_retention_limited": use_recent_history_for_retention_limited,
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
