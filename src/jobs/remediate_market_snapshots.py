from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from ingestion.binance.public_rest import BinancePublicRestClient
from jobs.data_quality import (
    FUNDING_FRESHNESS_SLA,
    OPEN_INTEREST_CONTINUITY_INTERVAL,
    OPEN_INTEREST_FRESHNESS_SLA,
    SENTIMENT_RATIO_CONTINUITY_INTERVAL,
    SENTIMENT_RATIO_DATA_TYPES,
    _dataset_availability_floor,
    _floor_to_interval,
    _is_timestamp_on_interval_boundary,
    _profile_interval_timestamps,
    _query_dataset_timestamps,
)
from jobs.refresh_market_snapshots import run_market_snapshot_refresh
from storage.db import connection_scope, transaction_scope
from storage.lookups import resolve_instrument_id
from storage.repositories.ops import IngestionJobRepository, SystemLogRecord, SystemLogRepository


MARK_PRICE_FRESHNESS_SLA = timedelta(minutes=10)
INDEX_PRICE_FRESHNESS_SLA = timedelta(minutes=10)
SENTIMENT_RATIO_FRESHNESS_SLA = timedelta(minutes=15)
DEFAULT_SENTIMENT_RATIO_PERIOD = "5m"
RETENTION_HISTORY_CHUNK_DAYS = 1
RETENTION_LIMITED_DATASETS = frozenset({"open_interest", *SENTIMENT_RATIO_DATA_TYPES})

SUPPORTED_SNAPSHOT_DATASETS = (
    "funding_rates",
    "open_interest",
    "mark_prices",
    "index_prices",
    "global_long_short_account_ratios",
    "top_trader_long_short_account_ratios",
    "top_trader_long_short_position_ratios",
    "taker_long_short_ratios",
)

SNAPSHOT_DATASET_SPECS = {
    "funding_rates": {"table_name": "md.funding_rates", "timestamp_column": "funding_time", "period_code": None},
    "open_interest": {"table_name": "md.open_interest", "timestamp_column": "ts", "period_code": None},
    "mark_prices": {"table_name": "md.mark_prices", "timestamp_column": "ts", "period_code": None},
    "index_prices": {"table_name": "md.index_prices", "timestamp_column": "ts", "period_code": None},
    "global_long_short_account_ratios": {
        "table_name": "md.global_long_short_account_ratios",
        "timestamp_column": "ts",
        "period_code": DEFAULT_SENTIMENT_RATIO_PERIOD,
    },
    "top_trader_long_short_account_ratios": {
        "table_name": "md.top_trader_long_short_account_ratios",
        "timestamp_column": "ts",
        "period_code": DEFAULT_SENTIMENT_RATIO_PERIOD,
    },
    "top_trader_long_short_position_ratios": {
        "table_name": "md.top_trader_long_short_position_ratios",
        "timestamp_column": "ts",
        "period_code": DEFAULT_SENTIMENT_RATIO_PERIOD,
    },
    "taker_long_short_ratios": {
        "table_name": "md.taker_long_short_ratios",
        "timestamp_column": "ts",
        "period_code": DEFAULT_SENTIMENT_RATIO_PERIOD,
    },
}


@dataclass(slots=True)
class SnapshotDatasetPlan:
    data_type: str
    latest_timestamp: datetime | None
    freshness_sla_seconds: int
    remediation_required: bool
    remediation_reason: str
    planned_start_time: datetime | None
    planned_end_time: datetime | None
    profile_window_start: datetime | None = None
    coverage_shortfall_count: int = 0
    internal_missing_count: int = 0
    tail_missing_count: int = 0
    gap_count: int = 0


@dataclass(slots=True)
class MarketSnapshotRemediationResult:
    ingestion_job_id: int
    status: str
    records_written: int
    refresh_job_id: int | None
    refresh_job_ids: list[int]
    remediation_actions: list[dict[str, Any]]


def _normalize_datasets(datasets: list[str] | None) -> list[str]:
    if not datasets:
        return list(SUPPORTED_SNAPSHOT_DATASETS)
    normalized = []
    for data_type in datasets:
        if data_type not in SUPPORTED_SNAPSHOT_DATASETS:
            raise ValueError(f"unsupported snapshot remediation dataset: {data_type}")
        if data_type not in normalized:
            normalized.append(data_type)
    return normalized


def _latest_timestamp_for_dataset(
    *,
    exchange_code: str,
    unified_symbol: str,
    data_type: str,
) -> datetime | None:
    specs = SNAPSHOT_DATASET_SPECS[data_type]
    table_name = specs["table_name"]
    timestamp_column = specs["timestamp_column"]
    period_code = specs["period_code"]
    with connection_scope() as connection:
        instrument_id = resolve_instrument_id(connection, exchange_code, unified_symbol)
        if period_code is None:
            return connection.exec_driver_sql(
                f"select max({timestamp_column}) from {table_name} where instrument_id = %s",
                (instrument_id,),
            ).scalar_one()
        return connection.exec_driver_sql(
            f"select max({timestamp_column}) from {table_name} where instrument_id = %s and period_code = %s",
            (instrument_id, period_code),
        ).scalar_one()


def _freshness_sla_for_dataset(data_type: str) -> timedelta:
    return {
        "funding_rates": FUNDING_FRESHNESS_SLA,
        "open_interest": OPEN_INTEREST_FRESHNESS_SLA,
        "mark_prices": MARK_PRICE_FRESHNESS_SLA,
        "index_prices": INDEX_PRICE_FRESHNESS_SLA,
        "global_long_short_account_ratios": SENTIMENT_RATIO_FRESHNESS_SLA,
        "top_trader_long_short_account_ratios": SENTIMENT_RATIO_FRESHNESS_SLA,
        "top_trader_long_short_position_ratios": SENTIMENT_RATIO_FRESHNESS_SLA,
        "taker_long_short_ratios": SENTIMENT_RATIO_FRESHNESS_SLA,
    }[data_type]


def _continuity_interval_for_dataset(data_type: str) -> timedelta | None:
    if data_type == "open_interest":
        return OPEN_INTEREST_CONTINUITY_INTERVAL
    if data_type in SENTIMENT_RATIO_DATA_TYPES:
        return SENTIMENT_RATIO_CONTINUITY_INTERVAL
    return None


def _build_day_windows(start_time: datetime, end_time: datetime, *, chunk_days: int) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    cursor = start_time
    while cursor <= end_time:
        next_cursor = cursor + timedelta(days=chunk_days)
        window_end = min(next_cursor - timedelta(milliseconds=1), end_time)
        windows.append((cursor, window_end))
        cursor = next_cursor
    return windows


def _retention_limited_plan(
    *,
    exchange_code: str,
    unified_symbol: str,
    data_type: str,
    observed_at: datetime,
) -> SnapshotDatasetPlan:
    profile_window_start = _dataset_availability_floor(data_type, observed_at)
    interval = _continuity_interval_for_dataset(data_type)
    if profile_window_start is None or interval is None:
        raise ValueError(f"unsupported retention-limited dataset: {data_type}")

    aligned_window_end = _floor_to_interval(observed_at, interval)
    specs = SNAPSHOT_DATASET_SPECS[data_type]
    with connection_scope() as connection:
        instrument_id = resolve_instrument_id(connection, exchange_code, unified_symbol)
        timestamps = _query_dataset_timestamps(
            connection,
            table_name=specs["table_name"],
            time_column=specs["timestamp_column"],
            instrument_id=instrument_id,
            start_time=profile_window_start,
            end_time=observed_at,
            period_code=specs["period_code"],
        )

    safe_timestamps = [
        timestamp for timestamp in timestamps if _is_timestamp_on_interval_boundary(timestamp, interval)
    ]
    coverage_profile = _profile_interval_timestamps(
        timestamps=safe_timestamps,
        aligned_start_time=profile_window_start,
        aligned_end_time=aligned_window_end,
        interval=interval,
    )
    latest_timestamp = safe_timestamps[-1] if safe_timestamps else None
    remediation_required = (
        coverage_profile.coverage_shortfall_count > 0
        or coverage_profile.internal_missing_count > 0
        or coverage_profile.tail_missing_count > 0
    )
    remediation_reason = "fresh"
    planned_start_time: datetime | None = None
    if remediation_required:
        if not safe_timestamps:
            remediation_reason = "missing"
            planned_start_time = profile_window_start
        elif coverage_profile.coverage_shortfall_count > 0:
            remediation_reason = "coverage_shortfall"
            planned_start_time = profile_window_start
        elif coverage_profile.internal_gap_segments:
            remediation_reason = "continuity_gap"
            planned_start_time = coverage_profile.internal_gap_segments[0]["gap_start"]
        else:
            remediation_reason = "tail_shortfall"
            planned_start_time = max(profile_window_start, latest_timestamp - timedelta(days=1))

    return SnapshotDatasetPlan(
        data_type=data_type,
        latest_timestamp=latest_timestamp,
        freshness_sla_seconds=int(_freshness_sla_for_dataset(data_type).total_seconds()),
        remediation_required=remediation_required,
        remediation_reason=remediation_reason,
        planned_start_time=planned_start_time,
        planned_end_time=observed_at if remediation_required else None,
        profile_window_start=profile_window_start,
        coverage_shortfall_count=coverage_profile.coverage_shortfall_count,
        internal_missing_count=coverage_profile.internal_missing_count,
        tail_missing_count=coverage_profile.tail_missing_count,
        gap_count=len(coverage_profile.internal_gap_segments),
    )


def _run_open_interest_remediation_window(
    *,
    symbol: str,
    unified_symbol: str,
    client: BinancePublicRestClient,
    requested_by: str,
    start_time: datetime,
    end_time: datetime,
    exchange_code: str,
    open_interest_period: str,
) -> dict[str, Any]:
    windows = _build_day_windows(start_time, end_time, chunk_days=RETENTION_HISTORY_CHUNK_DAYS)
    refresh_job_ids: list[int] = []
    total_rows_written = 0
    chunk_results: list[dict[str, Any]] = []
    for window_start, window_end in windows:
        result = run_market_snapshot_refresh(
            symbol=symbol,
            unified_symbol=unified_symbol,
            client=client,
            requested_by=requested_by,
            exchange_code=exchange_code,
            history_start_time=window_start,
            history_end_time=window_end,
            open_interest_period=open_interest_period,
            include_funding=False,
            include_open_interest=True,
            include_mark_price=False,
            include_index_price=False,
        )
        refresh_job_ids.append(result.ingestion_job_id)
        total_rows_written += result.records_written
        chunk_results.append(
            {
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "status": result.status,
                "rows_written": result.records_written,
                "history_rows_written": result.history_rows_written,
                "ingestion_job_id": result.ingestion_job_id,
            }
        )
    return {
        "rows_written": total_rows_written,
        "refresh_job_ids": refresh_job_ids,
        "chunk_results": chunk_results,
    }


def _run_sentiment_ratio_remediation_window(
    *,
    symbol: str,
    unified_symbol: str,
    client: BinancePublicRestClient,
    requested_by: str,
    start_time: datetime,
    end_time: datetime,
    exchange_code: str,
    sentiment_ratio_period: str,
    include_global_long_short_account_ratio: bool,
    include_top_trader_long_short_account_ratio: bool,
    include_top_trader_long_short_position_ratio: bool,
    include_taker_long_short_ratio: bool,
) -> dict[str, Any]:
    windows = _build_day_windows(start_time, end_time, chunk_days=RETENTION_HISTORY_CHUNK_DAYS)
    refresh_job_ids: list[int] = []
    total_rows_written = 0
    chunk_results: list[dict[str, Any]] = []
    for window_start, window_end in windows:
        result = run_market_snapshot_refresh(
            symbol=symbol,
            unified_symbol=unified_symbol,
            client=client,
            requested_by=requested_by,
            exchange_code=exchange_code,
            history_start_time=window_start,
            history_end_time=window_end,
            sentiment_ratio_period=sentiment_ratio_period,
            include_funding=False,
            include_open_interest=False,
            include_mark_price=False,
            include_index_price=False,
            include_global_long_short_account_ratio=include_global_long_short_account_ratio,
            include_top_trader_long_short_account_ratio=include_top_trader_long_short_account_ratio,
            include_top_trader_long_short_position_ratio=include_top_trader_long_short_position_ratio,
            include_taker_long_short_ratio=include_taker_long_short_ratio,
        )
        refresh_job_ids.append(result.ingestion_job_id)
        total_rows_written += result.records_written
        chunk_results.append(
            {
                "window_start": window_start.isoformat(),
                "window_end": window_end.isoformat(),
                "status": result.status,
                "rows_written": result.records_written,
                "history_rows_written": result.history_rows_written,
                "ingestion_job_id": result.ingestion_job_id,
            }
        )
    return {
        "rows_written": total_rows_written,
        "refresh_job_ids": refresh_job_ids,
        "chunk_results": chunk_results,
    }


def build_market_snapshot_remediation_plan(
    *,
    exchange_code: str,
    unified_symbol: str,
    datasets: list[str] | None = None,
    observed_at: datetime | None = None,
    lookback_hours: int = 24,
) -> list[SnapshotDatasetPlan]:
    now = observed_at or datetime.now(timezone.utc)
    normalized_datasets = _normalize_datasets(datasets)
    lookback_start = now - timedelta(hours=lookback_hours)
    plans: list[SnapshotDatasetPlan] = []

    for data_type in normalized_datasets:
        if data_type in RETENTION_LIMITED_DATASETS:
            plans.append(
                _retention_limited_plan(
                    exchange_code=exchange_code,
                    unified_symbol=unified_symbol,
                    data_type=data_type,
                    observed_at=now,
                )
            )
            continue

        latest_timestamp = _latest_timestamp_for_dataset(
            exchange_code=exchange_code,
            unified_symbol=unified_symbol,
            data_type=data_type,
        )
        freshness_sla = _freshness_sla_for_dataset(data_type)

        if latest_timestamp is None:
            plans.append(
                SnapshotDatasetPlan(
                    data_type=data_type,
                    latest_timestamp=None,
                    freshness_sla_seconds=int(freshness_sla.total_seconds()),
                    remediation_required=True,
                    remediation_reason="missing",
                    planned_start_time=lookback_start,
                    planned_end_time=now,
                )
            )
            continue

        lag = now - latest_timestamp
        if lag > freshness_sla:
            plans.append(
                SnapshotDatasetPlan(
                    data_type=data_type,
                    latest_timestamp=latest_timestamp,
                    freshness_sla_seconds=int(freshness_sla.total_seconds()),
                    remediation_required=True,
                    remediation_reason="stale",
                    planned_start_time=max(latest_timestamp, lookback_start),
                    planned_end_time=now,
                )
            )
            continue

        plans.append(
            SnapshotDatasetPlan(
                data_type=data_type,
                latest_timestamp=latest_timestamp,
                freshness_sla_seconds=int(freshness_sla.total_seconds()),
                remediation_required=False,
                remediation_reason="fresh",
                planned_start_time=None,
                planned_end_time=None,
            )
        )

    return plans


def run_market_snapshot_remediation(
    *,
    symbol: str,
    unified_symbol: str,
    client: BinancePublicRestClient | None = None,
    requested_by: str = "system",
    exchange_code: str = "binance",
    datasets: list[str] | None = None,
    observed_at: datetime | None = None,
    lookback_hours: int = 24,
    open_interest_period: str = "5m",
    price_interval: str = "1m",
    sentiment_ratio_period: str = DEFAULT_SENTIMENT_RATIO_PERIOD,
) -> MarketSnapshotRemediationResult:
    snapshot_client = client or BinancePublicRestClient()
    now = observed_at or datetime.now(timezone.utc)
    plans = build_market_snapshot_remediation_plan(
        exchange_code=exchange_code,
        unified_symbol=unified_symbol,
        datasets=datasets,
        observed_at=now,
        lookback_hours=lookback_hours,
    )
    remediation_actions = [
        {
            "data_type": plan.data_type,
            "latest_timestamp": plan.latest_timestamp.isoformat() if plan.latest_timestamp else None,
            "freshness_sla_seconds": plan.freshness_sla_seconds,
            "remediation_required": plan.remediation_required,
            "remediation_reason": plan.remediation_reason,
            "planned_start_time": plan.planned_start_time.isoformat() if plan.planned_start_time else None,
            "planned_end_time": plan.planned_end_time.isoformat() if plan.planned_end_time else None,
            "profile_window_start": plan.profile_window_start.isoformat() if plan.profile_window_start else None,
            "coverage_shortfall_count": plan.coverage_shortfall_count,
            "internal_missing_count": plan.internal_missing_count,
            "tail_missing_count": plan.tail_missing_count,
            "gap_count": plan.gap_count,
        }
        for plan in plans
    ]

    with transaction_scope() as connection:
        job_repo = IngestionJobRepository()
        log_repo = SystemLogRepository()
        job_id = job_repo.create_job(
            connection,
            service_name="market_snapshot_remediation",
            data_type="funding_open_interest_mark_index_sentiment",
            exchange_code=exchange_code,
            unified_symbol=unified_symbol,
            schedule_type="manual_scheduler_ready",
            status="running",
            requested_by=requested_by,
            window_start=min(
                (plan.planned_start_time for plan in plans if plan.planned_start_time is not None),
                default=None,
            ),
            window_end=max(
                (plan.planned_end_time for plan in plans if plan.planned_end_time is not None),
                default=None,
            ),
            metadata_json={
                "job_type": "market_snapshot_remediation",
                "scheduler_ready": True,
                "requested_datasets": _normalize_datasets(datasets),
                "remediation_actions": remediation_actions,
                "lookback_hours": lookback_hours,
                "sentiment_ratio_period": sentiment_ratio_period,
            },
        )
        log_repo.insert(
            connection,
            SystemLogRecord(
                service_name="market_snapshot_remediation",
                level="info",
                message=f"starting market snapshot remediation for {unified_symbol}",
                context_json={"job_id": job_id, "datasets": _normalize_datasets(datasets)},
            ),
        )

    funding_plan = next((plan for plan in plans if plan.data_type == "funding_rates"), None)
    standard_history_plans = [
        plan
        for plan in plans
        if plan.data_type
        in {"mark_prices", "index_prices"}
        and plan.remediation_required
    ]
    open_interest_plan = next((plan for plan in plans if plan.data_type == "open_interest" and plan.remediation_required), None)
    sentiment_plans = [
        plan for plan in plans if plan.data_type in SENTIMENT_RATIO_DATA_TYPES and plan.remediation_required
    ]
    refresh_job_id: int | None = None
    refresh_job_ids: list[int] = []
    records_written = 0

    try:
        if (funding_plan and funding_plan.remediation_required) or standard_history_plans:
            history_start = min(
                (plan.planned_start_time for plan in standard_history_plans if plan.planned_start_time),
                default=None,
            )
            history_end = max(
                (plan.planned_end_time for plan in standard_history_plans if plan.planned_end_time),
                default=None,
            )
            refresh_result = run_market_snapshot_refresh(
                symbol=symbol,
                unified_symbol=unified_symbol,
                client=snapshot_client,
                requested_by=requested_by,
                exchange_code=exchange_code,
                funding_start_time=funding_plan.planned_start_time if funding_plan and funding_plan.remediation_required else None,
                funding_end_time=funding_plan.planned_end_time if funding_plan and funding_plan.remediation_required else None,
                history_start_time=history_start,
                history_end_time=history_end,
                open_interest_period=open_interest_period,
                price_interval=price_interval,
                sentiment_ratio_period=sentiment_ratio_period,
                include_funding=bool(funding_plan and funding_plan.remediation_required),
                include_open_interest=False,
                include_mark_price=any(plan.data_type == "mark_prices" for plan in standard_history_plans),
                include_index_price=any(plan.data_type == "index_prices" for plan in standard_history_plans),
                include_global_long_short_account_ratio=False,
                include_top_trader_long_short_account_ratio=False,
                include_top_trader_long_short_position_ratio=False,
                include_taker_long_short_ratio=False,
                observed_at=now,
            )
            refresh_job_id = refresh_result.ingestion_job_id
            refresh_job_ids.append(refresh_result.ingestion_job_id)
            records_written += refresh_result.records_written

        if open_interest_plan and open_interest_plan.planned_start_time and open_interest_plan.planned_end_time:
            open_interest_result = _run_open_interest_remediation_window(
                symbol=symbol,
                unified_symbol=unified_symbol,
                client=snapshot_client,
                requested_by=requested_by,
                start_time=open_interest_plan.planned_start_time,
                end_time=open_interest_plan.planned_end_time,
                exchange_code=exchange_code,
                open_interest_period=open_interest_period,
            )
            if refresh_job_id is None and open_interest_result["refresh_job_ids"]:
                refresh_job_id = open_interest_result["refresh_job_ids"][0]
            refresh_job_ids.extend(open_interest_result["refresh_job_ids"])
            records_written += open_interest_result["rows_written"]

        if sentiment_plans:
            sentiment_start = min(plan.planned_start_time for plan in sentiment_plans if plan.planned_start_time)
            sentiment_end = max(plan.planned_end_time for plan in sentiment_plans if plan.planned_end_time)
            sentiment_result = _run_sentiment_ratio_remediation_window(
                symbol=symbol,
                unified_symbol=unified_symbol,
                client=snapshot_client,
                requested_by=requested_by,
                start_time=sentiment_start,
                end_time=sentiment_end,
                exchange_code=exchange_code,
                sentiment_ratio_period=sentiment_ratio_period,
                include_global_long_short_account_ratio=any(
                    plan.data_type == "global_long_short_account_ratios" for plan in sentiment_plans
                ),
                include_top_trader_long_short_account_ratio=any(
                    plan.data_type == "top_trader_long_short_account_ratios" for plan in sentiment_plans
                ),
                include_top_trader_long_short_position_ratio=any(
                    plan.data_type == "top_trader_long_short_position_ratios" for plan in sentiment_plans
                ),
                include_taker_long_short_ratio=any(plan.data_type == "taker_long_short_ratios" for plan in sentiment_plans),
            )
            if refresh_job_id is None and sentiment_result["refresh_job_ids"]:
                refresh_job_id = sentiment_result["refresh_job_ids"][0]
            refresh_job_ids.extend(sentiment_result["refresh_job_ids"])
            records_written += sentiment_result["rows_written"]

        with transaction_scope() as connection:
            job_repo = IngestionJobRepository()
            log_repo = SystemLogRepository()
            job_repo.finish_job(
                connection,
                job_id,
                status="succeeded",
                finished_at=datetime.now(timezone.utc),
                records_expected=records_written,
                records_written=records_written,
                metadata_json={
                    "job_type": "market_snapshot_remediation",
                    "scheduler_ready": True,
                    "requested_datasets": _normalize_datasets(datasets),
                    "remediation_actions": remediation_actions,
                    "refresh_job_id": refresh_job_id,
                    "refresh_job_ids": refresh_job_ids,
                    "lookback_hours": lookback_hours,
                    "sentiment_ratio_period": sentiment_ratio_period,
                },
            )
            log_repo.insert(
                connection,
                SystemLogRecord(
                    service_name="market_snapshot_remediation",
                    level="info",
                    message=f"market snapshot remediation finished for {unified_symbol}",
                    context_json={
                        "job_id": job_id,
                        "refresh_job_id": refresh_job_id,
                        "refresh_job_ids": refresh_job_ids,
                        "records_written": records_written,
                    },
                ),
            )

        return MarketSnapshotRemediationResult(
            ingestion_job_id=job_id,
            status="succeeded",
            records_written=records_written,
            refresh_job_id=refresh_job_id,
            refresh_job_ids=refresh_job_ids,
            remediation_actions=remediation_actions,
        )
    except Exception as exc:
        with transaction_scope() as connection:
            job_repo = IngestionJobRepository()
            log_repo = SystemLogRepository()
            job_repo.finish_job(
                connection,
                job_id,
                status="failed_terminal",
                finished_at=datetime.now(timezone.utc),
                error_message=str(exc),
                metadata_json={
                    "job_type": "market_snapshot_remediation",
                    "scheduler_ready": True,
                    "requested_datasets": _normalize_datasets(datasets),
                    "remediation_actions": remediation_actions,
                    "refresh_job_id": refresh_job_id,
                    "refresh_job_ids": refresh_job_ids,
                    "lookback_hours": lookback_hours,
                    "sentiment_ratio_period": sentiment_ratio_period,
                },
            )
            log_repo.insert(
                connection,
                SystemLogRecord(
                    service_name="market_snapshot_remediation",
                    level="error",
                    message=f"market snapshot remediation failed for {unified_symbol}",
                    context_json={"job_id": job_id, "error": str(exc)},
                ),
            )
        raise
