from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from storage.db import transaction_scope
from storage.lookups import resolve_instrument_id
from storage.repositories.ops import (
    DataGapRecord,
    DataGapRepository,
    DataQualityCheckRecord,
    DataQualityCheckRepository,
    SystemLogRecord,
    SystemLogRepository,
)


@dataclass(slots=True)
class DataQualityRunResult:
    checks_written: int
    gaps_written: int


@dataclass(slots=True)
class DatasetIntegrityFinding:
    category: str
    severity: str
    status: str
    message: str
    related_count: int
    detail_json: dict[str, Any]


@dataclass(slots=True)
class DatasetIntegrityDatasetReport:
    data_type: str
    status: str
    row_count: int
    expected_interval_seconds: int | None
    expected_points: int | None
    available_from: datetime | None
    available_to: datetime | None
    safe_available_to: datetime | None
    missing_count: int
    coverage_shortfall_count: int
    internal_missing_count: int
    tail_missing_count: int
    gap_count: int
    duplicate_count: int
    corrupt_count: int
    future_row_count: int
    findings: list[DatasetIntegrityFinding]


@dataclass(slots=True)
class DatasetIntegritySummary:
    dataset_count: int
    passed_datasets: int
    warning_datasets: int
    failed_datasets: int
    total_gap_count: int
    total_missing_count: int
    total_coverage_shortfall_count: int
    total_internal_missing_count: int
    total_tail_missing_count: int
    total_duplicate_count: int
    total_corrupt_count: int
    total_future_row_count: int


@dataclass(slots=True)
class DatasetIntegrityValidationResult:
    exchange_code: str
    unified_symbol: str
    start_time: datetime
    end_time: datetime
    observed_at: datetime
    persisted_checks_written: int
    persisted_gaps_written: int
    summary: DatasetIntegritySummary
    datasets: list[DatasetIntegrityDatasetReport]


BAR_FRESHNESS_SLA = timedelta(minutes=2)
TRADE_FRESHNESS_SLA = timedelta(minutes=2)
FUNDING_FRESHNESS_SLA = timedelta(hours=12)
OPEN_INTEREST_FRESHNESS_SLA = timedelta(minutes=10)
MARK_PRICE_FRESHNESS_SLA = timedelta(minutes=10)
INDEX_PRICE_FRESHNESS_SLA = timedelta(minutes=10)
FUNDING_CONTINUITY_INTERVAL = timedelta(hours=8)
OPEN_INTEREST_CONTINUITY_INTERVAL = timedelta(minutes=5)
MARK_INDEX_CONTINUITY_INTERVAL = timedelta(minutes=1)
EPOCH_UTC = datetime(1970, 1, 1, tzinfo=timezone.utc)
INTEGRITY_DATASET_SPECS: dict[str, dict[str, Any]] = {
    "bars_1m": {
        "table_name": "md.bars_1m",
        "time_column": "bar_time",
        "interval": timedelta(minutes=1),
        "duplicate_key": "bar_time",
        "corrupt_where": """
            (
                bar_time > %s
                or open <= 0
                or high <= 0
                or low <= 0
                or close <= 0
                or volume < 0
                or coalesce(quote_volume, 0) < 0
                or coalesce(trade_count, 0) < 0
                or high < open
                or high < close
                or high < low
                or low > open
                or low > close
                or low > high
            )
        """,
        "corrupt_sample_columns": "bar_time as ts, open, high, low, close, volume, quote_volume, trade_count",
    },
    "trades": {
        "table_name": "md.trades",
        "time_column": "event_time",
        "interval": None,
        "duplicate_key": "exchange_trade_id",
        "corrupt_where": """
            (
                event_time > %s
                or price <= 0
                or qty <= 0
            )
        """,
        "corrupt_sample_columns": "event_time as ts, exchange_trade_id, price, qty, aggressor_side",
    },
    "funding_rates": {
        "table_name": "md.funding_rates",
        "time_column": "funding_time",
        "interval": FUNDING_CONTINUITY_INTERVAL,
        "duplicate_key": "funding_time",
        "corrupt_where": """
            (
                funding_time > %s
                or coalesce(mark_price, 1) <= 0
                or coalesce(index_price, 1) <= 0
            )
        """,
        "corrupt_sample_columns": "funding_time as ts, funding_rate, mark_price, index_price",
    },
    "open_interest": {
        "table_name": "md.open_interest",
        "time_column": "ts",
        "interval": OPEN_INTEREST_CONTINUITY_INTERVAL,
        "profile_aligned_only": True,
        "duplicate_key": "ts",
        "corrupt_where": """
            (
                ts > %s
                or open_interest <= 0
            )
        """,
        "corrupt_sample_columns": "ts, open_interest",
    },
    "mark_prices": {
        "table_name": "md.mark_prices",
        "time_column": "ts",
        "interval": MARK_INDEX_CONTINUITY_INTERVAL,
        "duplicate_key": "ts",
        "corrupt_where": """
            (
                ts > %s
                or mark_price <= 0
            )
        """,
        "corrupt_sample_columns": "ts, mark_price, funding_basis_bps",
    },
    "index_prices": {
        "table_name": "md.index_prices",
        "time_column": "ts",
        "interval": MARK_INDEX_CONTINUITY_INTERVAL,
        "duplicate_key": "ts",
        "corrupt_where": """
            (
                ts > %s
                or index_price <= 0
            )
        """,
        "corrupt_sample_columns": "ts, index_price",
    },
    "raw_market_events": {
        "table_name": "md.raw_market_events",
        "time_column": "coalesce(event_time, ingest_time)",
        "interval": None,
        "duplicate_key": "coalesce(source_message_id, '')",
        "corrupt_where": """
            (
                coalesce(event_time, ingest_time) > %s
                or event_time is null
            )
        """,
        "corrupt_sample_columns": "coalesce(event_time, ingest_time) as ts, channel, event_type, source_message_id",
    },
}


def _is_spot_symbol(unified_symbol: str) -> bool:
    return unified_symbol.upper().endswith("_SPOT")


def _align_bar_window(start_time: datetime, end_time: datetime) -> tuple[datetime, datetime]:
    aligned_start = start_time.replace(second=0, microsecond=0)
    if aligned_start < start_time:
        aligned_start += timedelta(minutes=1)

    aligned_end = end_time.replace(second=0, microsecond=0)
    return aligned_start, aligned_end


def _default_integrity_data_types(*, unified_symbol: str, raw_event_channel: str | None = None) -> list[str]:
    data_types = ["bars_1m"]
    if not _is_spot_symbol(unified_symbol):
        data_types.extend(["funding_rates", "open_interest", "mark_prices", "index_prices"])
    if raw_event_channel is not None:
        data_types.append("raw_market_events")
    return data_types


def _ensure_supported_integrity_data_types(data_types: list[str]) -> list[str]:
    normalized = list(dict.fromkeys(data_types))
    unsupported = sorted(set(normalized) - set(INTEGRITY_DATASET_SPECS))
    if unsupported:
        raise ValueError(f"unsupported integrity data_type(s): {', '.join(unsupported)}")
    return normalized


def _ceil_to_interval(timestamp: datetime, interval: timedelta) -> datetime:
    interval_microseconds = int(interval.total_seconds() * 1_000_000)
    delta_microseconds = int((timestamp - EPOCH_UTC).total_seconds() * 1_000_000)
    remainder = delta_microseconds % interval_microseconds
    if remainder == 0:
        return timestamp.replace(microsecond=0)
    return (EPOCH_UTC + timedelta(microseconds=(delta_microseconds + (interval_microseconds - remainder)))).replace(microsecond=0)


def _floor_to_interval(timestamp: datetime, interval: timedelta) -> datetime:
    interval_microseconds = int(interval.total_seconds() * 1_000_000)
    delta_microseconds = int((timestamp - EPOCH_UTC).total_seconds() * 1_000_000)
    floored_microseconds = delta_microseconds - (delta_microseconds % interval_microseconds)
    return (EPOCH_UTC + timedelta(microseconds=floored_microseconds)).replace(microsecond=0)


def _align_window_for_interval(start_time: datetime, end_time: datetime, interval: timedelta) -> tuple[datetime, datetime]:
    return _ceil_to_interval(start_time, interval), _floor_to_interval(end_time, interval)


def _expected_points_in_interval_window(
    aligned_start_time: datetime,
    aligned_end_time: datetime,
    interval: timedelta,
) -> int:
    if aligned_end_time < aligned_start_time:
        return 0
    return int(((aligned_end_time - aligned_start_time) / interval)) + 1


@dataclass(slots=True)
class IntervalCoverageProfile:
    total_missing_count: int
    coverage_shortfall_count: int
    internal_missing_count: int
    tail_missing_count: int
    internal_gap_segments: list[dict[str, Any]]


def _profile_interval_timestamps(
    *,
    timestamps: list[datetime],
    aligned_start_time: datetime,
    aligned_end_time: datetime,
    interval: timedelta,
) -> IntervalCoverageProfile:
    if aligned_end_time < aligned_start_time:
        return IntervalCoverageProfile(
            total_missing_count=0,
            coverage_shortfall_count=0,
            internal_missing_count=0,
            tail_missing_count=0,
            internal_gap_segments=[],
        )

    if not timestamps:
        expected_points = _expected_points_in_interval_window(aligned_start_time, aligned_end_time, interval)
        return IntervalCoverageProfile(
            total_missing_count=expected_points,
            coverage_shortfall_count=expected_points,
            internal_missing_count=0,
            tail_missing_count=0,
            internal_gap_segments=[],
        )

    internal_gap_segments: list[dict[str, Any]] = []
    coverage_shortfall_count = 0
    internal_missing_count = 0
    tail_missing_count = 0
    first_timestamp = timestamps[0]
    if first_timestamp > aligned_start_time:
        coverage_shortfall_count = int((first_timestamp - aligned_start_time) / interval)

    for previous_timestamp, current_timestamp in zip(timestamps, timestamps[1:]):
        delta = current_timestamp - previous_timestamp
        delta_points = int(delta / interval)
        if delta_points <= 1:
            continue
        missing_points = delta_points - 1
        internal_gap_segments.append(
            {
                "gap_start": previous_timestamp + interval,
                "gap_end": current_timestamp - interval,
                "missing_points": missing_points,
            }
        )
        internal_missing_count += missing_points

    last_timestamp = timestamps[-1]
    if last_timestamp < aligned_end_time:
        tail_missing_count = int((aligned_end_time - last_timestamp) / interval)

    return IntervalCoverageProfile(
        total_missing_count=coverage_shortfall_count + internal_missing_count + tail_missing_count,
        coverage_shortfall_count=coverage_shortfall_count,
        internal_missing_count=internal_missing_count,
        tail_missing_count=tail_missing_count,
        internal_gap_segments=internal_gap_segments,
    )


def _is_timestamp_on_interval_boundary(timestamp: datetime, interval: timedelta) -> bool:
    if timestamp.microsecond != 0:
        return False
    return _floor_to_interval(timestamp, interval) == timestamp


def _status_for_count(count: int, *, fail_severity: str = "error") -> tuple[str, str]:
    return ("fail", fail_severity) if count > 0 else ("pass", "info")


def _warning_status_for_count(count: int) -> tuple[str, str]:
    return ("warning", "warning") if count > 0 else ("pass", "info")


def _dataset_status_from_findings(findings: list[DatasetIntegrityFinding]) -> str:
    statuses = {finding.status for finding in findings}
    if "fail" in statuses:
        return "fail"
    if "warning" in statuses:
        return "warning"
    return "pass"


def _normalize_json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {key: _normalize_json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize_json_value(item) for item in value]
    if isinstance(value, tuple):
        return [_normalize_json_value(item) for item in value]
    return value


def _dataset_interval_window(
    *,
    data_type: str,
    start_time: datetime,
    end_time: datetime,
    interval: timedelta | None,
) -> tuple[datetime, datetime]:
    if interval is None:
        return start_time, end_time
    if data_type == "bars_1m":
        return _align_bar_window(start_time, end_time)
    return _align_window_for_interval(start_time, end_time, interval)


def _query_dataset_window_stats(
    connection,
    *,
    table_name: str,
    time_column: str,
    instrument_id: int,
    start_time: datetime,
    end_time: datetime,
    raw_event_channel: str | None = None,
) -> dict[str, Any]:
    where_clauses = [f"instrument_id = %s", f"{time_column} between %s and %s"]
    params: list[Any] = [instrument_id, start_time, end_time]
    if table_name == "md.raw_market_events" and raw_event_channel is not None:
        where_clauses.append("channel = %s")
        params.append(raw_event_channel)
    where_sql = " and ".join(where_clauses)
    row = connection.exec_driver_sql(
        f"""
        select
            count(*) as row_count,
            min({time_column}) as available_from,
            max({time_column}) as available_to
        from {table_name}
        where {where_sql}
        """,
        tuple(params),
    ).mappings().first()
    return dict(row or {})


def _query_dataset_timestamps(
    connection,
    *,
    table_name: str,
    time_column: str,
    instrument_id: int,
    start_time: datetime,
    end_time: datetime,
    raw_event_channel: str | None = None,
) -> list[datetime]:
    where_clauses = [f"instrument_id = %s", f"{time_column} between %s and %s"]
    params: list[Any] = [instrument_id, start_time, end_time]
    if table_name == "md.raw_market_events" and raw_event_channel is not None:
        where_clauses.append("channel = %s")
        params.append(raw_event_channel)
    where_sql = " and ".join(where_clauses)
    rows = connection.exec_driver_sql(
        f"""
        select {time_column} as ts
        from {table_name}
        where {where_sql}
        order by {time_column} asc
        """,
        tuple(params),
    ).all()
    return [row[0] for row in rows if row[0] is not None]


def _query_duplicate_profile(
    connection,
    *,
    table_name: str,
    duplicate_key: str,
    time_column: str,
    instrument_id: int,
    start_time: datetime,
    end_time: datetime,
    raw_event_channel: str | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    where_clauses = [f"instrument_id = %s", f"{time_column} between %s and %s"]
    params: list[Any] = [instrument_id, start_time, end_time]
    if table_name == "md.raw_market_events":
        where_clauses.append(f"{duplicate_key} <> ''")
        if raw_event_channel is not None:
            where_clauses.append("channel = %s")
            params.append(raw_event_channel)
    where_sql = " and ".join(where_clauses)
    rows = connection.exec_driver_sql(
        f"""
        select duplicate_key, row_count
        from (
            select {duplicate_key} as duplicate_key, count(*) as row_count
            from {table_name}
            where {where_sql}
            group by {duplicate_key}
            having count(*) > 1
        ) duplicates
        order by row_count desc, duplicate_key asc
        limit 10
        """,
        tuple(params),
    ).mappings().all()
    duplicate_examples = [dict(row) for row in rows]
    duplicate_count = int(sum(int(row["row_count"]) - 1 for row in duplicate_examples))
    if duplicate_examples:
        duplicate_count = int(
            connection.exec_driver_sql(
                f"""
                select coalesce(sum(row_count - 1), 0)
                from (
                    select count(*) as row_count
                    from {table_name}
                    where {where_sql}
                    group by {duplicate_key}
                    having count(*) > 1
                ) duplicates
                """,
                tuple(params),
            ).scalar_one()
        )
    return duplicate_count, duplicate_examples


def _query_corrupt_profile(
    connection,
    *,
    table_name: str,
    corrupt_where: str,
    corrupt_sample_columns: str,
    time_column: str,
    instrument_id: int,
    start_time: datetime,
    end_time: datetime,
    observed_at: datetime,
    raw_event_channel: str | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    where_clauses = [f"instrument_id = %s", f"{time_column} between %s and %s", corrupt_where]
    params: list[Any] = [instrument_id, start_time, end_time, observed_at]
    if table_name == "md.raw_market_events" and raw_event_channel is not None:
        where_clauses.insert(2, "channel = %s")
        params.insert(3, raw_event_channel)
    where_sql = " and ".join(f"({clause.strip()})" for clause in where_clauses)
    corrupt_count = int(
        connection.exec_driver_sql(
            f"""
            select count(*)
            from {table_name}
            where {where_sql}
            """,
            tuple(params),
        ).scalar_one()
    )
    corrupt_examples = [
        dict(row)
        for row in connection.exec_driver_sql(
            f"""
            select {corrupt_sample_columns}
            from {table_name}
            where {where_sql}
            order by {time_column} asc
            limit 10
            """,
            tuple(params),
        ).mappings().all()
    ]
    return corrupt_count, corrupt_examples


def _query_future_row_profile(
    connection,
    *,
    table_name: str,
    time_column: str,
    instrument_id: int,
    observed_at: datetime,
    raw_event_channel: str | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    where_clauses = [f"instrument_id = %s", f"{time_column} > %s"]
    params: list[Any] = [instrument_id, observed_at]
    if table_name == "md.raw_market_events" and raw_event_channel is not None:
        where_clauses.append("channel = %s")
        params.append(raw_event_channel)
    where_sql = " and ".join(where_clauses)
    future_row_count = int(
        connection.exec_driver_sql(
            f"""
            select count(*)
            from {table_name}
            where {where_sql}
            """,
            tuple(params),
        ).scalar_one()
    )
    future_examples = [
        dict(row)
        for row in connection.exec_driver_sql(
            f"""
            select {time_column} as ts
            from {table_name}
            where {where_sql}
            order by {time_column} asc
            limit 10
            """,
            tuple(params),
        ).mappings().all()
    ]
    return future_row_count, future_examples


def _persist_integrity_check(
    *,
    quality_repo: DataQualityCheckRepository,
    connection,
    exchange_code: str,
    unified_symbol: str,
    data_type: str,
    check_name: str,
    expected_value: str | None,
    observed_value: str | None,
    related_count: int,
    detail_json: dict[str, Any],
    status_override: str | None = None,
    severity_override: str | None = None,
) -> int:
    status, severity = _status_for_count(related_count)
    if status_override is not None:
        status = status_override
    if severity_override is not None:
        severity = severity_override
    quality_repo.insert(
        connection,
        DataQualityCheckRecord(
            exchange_code=exchange_code,
            unified_symbol=unified_symbol,
            data_type=data_type,
            check_name=check_name,
            severity=severity,
            status=status,
            expected_value=expected_value,
            observed_value=observed_value,
            detail_json=_normalize_json_value(detail_json),
        ),
    )
    return 1


def validate_dataset_integrity(
    *,
    exchange_code: str,
    unified_symbol: str,
    start_time: datetime,
    end_time: datetime,
    observed_at: datetime | None = None,
    data_types: list[str] | None = None,
    raw_event_channel: str | None = None,
    persist_findings: bool = True,
) -> DatasetIntegrityValidationResult:
    effective_observed_at = observed_at or datetime.now(timezone.utc)
    selected_data_types = _ensure_supported_integrity_data_types(
        data_types or _default_integrity_data_types(unified_symbol=unified_symbol, raw_event_channel=raw_event_channel)
    )
    persisted_checks_written = 0
    persisted_gaps_written = 0
    dataset_reports: list[DatasetIntegrityDatasetReport] = []

    with transaction_scope() as connection:
        instrument_id = resolve_instrument_id(connection, exchange_code, unified_symbol)
        quality_repo = DataQualityCheckRepository()
        gap_repo = DataGapRepository()

        for data_type in selected_data_types:
            spec = INTEGRITY_DATASET_SPECS[data_type]
            table_name = spec["table_name"]
            time_column = spec["time_column"]
            interval = spec["interval"]
            aligned_start_time, aligned_end_time = _dataset_interval_window(
                data_type=data_type,
                start_time=start_time,
                end_time=end_time,
                interval=interval,
            )
            window_stats = _query_dataset_window_stats(
                connection,
                table_name=table_name,
                time_column=time_column,
                instrument_id=instrument_id,
                start_time=aligned_start_time,
                end_time=aligned_end_time,
                raw_event_channel=raw_event_channel,
            )
            row_count = int(window_stats.get("row_count") or 0)
            available_from = window_stats.get("available_from")
            available_to = window_stats.get("available_to")
            timestamps = []
            expected_points: int | None = None
            missing_count = 0
            coverage_shortfall_count = 0
            internal_missing_count = 0
            tail_missing_count = 0
            gap_segments: list[dict[str, Any]] = []
            if interval is not None:
                timestamps = _query_dataset_timestamps(
                    connection,
                    table_name=table_name,
                    time_column=time_column,
                    instrument_id=instrument_id,
                    start_time=aligned_start_time,
                    end_time=aligned_end_time,
                    raw_event_channel=raw_event_channel,
                )
                coverage_timestamps = (
                    [timestamp for timestamp in timestamps if _is_timestamp_on_interval_boundary(timestamp, interval)]
                    if spec.get("profile_aligned_only")
                    else timestamps
                )
                expected_points = _expected_points_in_interval_window(aligned_start_time, aligned_end_time, interval)
                safe_timestamps = [timestamp for timestamp in coverage_timestamps if timestamp <= effective_observed_at]
                coverage_profile = _profile_interval_timestamps(
                    timestamps=safe_timestamps,
                    aligned_start_time=aligned_start_time,
                    aligned_end_time=aligned_end_time,
                    interval=interval,
                )
                missing_count = coverage_profile.total_missing_count
                coverage_shortfall_count = coverage_profile.coverage_shortfall_count
                internal_missing_count = coverage_profile.internal_missing_count
                tail_missing_count = coverage_profile.tail_missing_count
                gap_segments = coverage_profile.internal_gap_segments
            elif row_count == 0:
                missing_count = 1

            duplicate_count, duplicate_examples = _query_duplicate_profile(
                connection,
                table_name=table_name,
                duplicate_key=spec["duplicate_key"],
                time_column=time_column,
                instrument_id=instrument_id,
                start_time=aligned_start_time,
                end_time=aligned_end_time,
                raw_event_channel=raw_event_channel,
            )
            corrupt_count, corrupt_examples = _query_corrupt_profile(
                connection,
                table_name=table_name,
                corrupt_where=spec["corrupt_where"],
                corrupt_sample_columns=spec["corrupt_sample_columns"],
                time_column=time_column,
                instrument_id=instrument_id,
                start_time=aligned_start_time,
                end_time=aligned_end_time,
                observed_at=effective_observed_at,
                raw_event_channel=raw_event_channel,
            )
            future_row_count, future_examples = _query_future_row_profile(
                connection,
                table_name=table_name,
                time_column=time_column,
                instrument_id=instrument_id,
                observed_at=effective_observed_at,
                raw_event_channel=raw_event_channel,
            )
            total_corrupt_count = corrupt_count + future_row_count
            safe_available_to = available_to
            if interval is not None and safe_timestamps:
                safe_available_to = safe_timestamps[-1]
            elif future_row_count > 0:
                safe_available_to_row = connection.exec_driver_sql(
                    f"""
                    select max({time_column})
                    from {table_name}
                    where instrument_id = %s
                      and {time_column} <= %s
                    """,
                    (instrument_id, effective_observed_at),
                ).scalar_one()
                safe_available_to = safe_available_to_row

            findings: list[DatasetIntegrityFinding] = []
            if interval is not None:
                gap_status, gap_severity = _status_for_count(len(gap_segments))
                findings.append(
                    DatasetIntegrityFinding(
                        category="gap",
                        severity=gap_severity,
                        status=gap_status,
                        message="interval gap segments detected" if gap_segments else "no interval gaps detected",
                        related_count=len(gap_segments),
                        detail_json=_normalize_json_value({
                            "aligned_window_start": aligned_start_time.isoformat(),
                            "aligned_window_end": aligned_end_time.isoformat(),
                            "expected_points": expected_points,
                            "segments": [
                                {
                                    "gap_start": segment["gap_start"].isoformat(),
                                    "gap_end": segment["gap_end"].isoformat(),
                                    "missing_points": segment["missing_points"],
                                }
                                for segment in gap_segments[:20]
                            ],
                        }),
                    )
                )
                coverage_status, coverage_severity = _warning_status_for_count(coverage_shortfall_count)
                findings.append(
                    DatasetIntegrityFinding(
                        category="coverage",
                        severity=coverage_severity,
                        status=coverage_status,
                        message=(
                            "selected window starts before current local dataset coverage"
                            if coverage_shortfall_count
                            else "no coverage shortfall at window start"
                        ),
                        related_count=coverage_shortfall_count,
                        detail_json=_normalize_json_value({
                            "aligned_window_start": aligned_start_time.isoformat(),
                            "first_record_in_window": (
                                safe_timestamps[0].isoformat() if safe_timestamps else (available_from.isoformat() if available_from else None)
                            ),
                            "coverage_shortfall_count": coverage_shortfall_count,
                        }),
                    )
                )
                tail_status, tail_severity = _warning_status_for_count(tail_missing_count)
                findings.append(
                    DatasetIntegrityFinding(
                        category="tail",
                        severity=tail_severity,
                        status=tail_status,
                        message=(
                            "selected window extends beyond current local coverage tail"
                            if tail_missing_count
                            else "no tail shortfall detected"
                        ),
                        related_count=tail_missing_count,
                        detail_json=_normalize_json_value({
                            "aligned_window_end": aligned_end_time.isoformat(),
                            "last_safe_record_in_window": safe_available_to.isoformat() if safe_available_to else None,
                            "tail_missing_count": tail_missing_count,
                        }),
                    )
                )
            else:
                missing_status, missing_severity = _warning_status_for_count(missing_count)
                findings.append(
                    DatasetIntegrityFinding(
                        category="missing",
                        severity=missing_severity,
                        status=missing_status,
                        message="expected rows missing inside validation window" if missing_count else "no missing rows detected",
                        related_count=missing_count,
                        detail_json=_normalize_json_value({
                            "row_count": row_count,
                            "expected_points": expected_points,
                            "available_from": available_from.isoformat() if available_from else None,
                            "available_to": available_to.isoformat() if available_to else None,
                        }),
                    )
                )
            duplicate_status, duplicate_severity = _status_for_count(duplicate_count)
            findings.append(
                DatasetIntegrityFinding(
                    category="duplicate",
                    severity=duplicate_severity,
                    status=duplicate_status,
                    message="duplicate records detected" if duplicate_count else "no duplicates detected",
                    related_count=duplicate_count,
                    detail_json=_normalize_json_value({"examples": duplicate_examples}),
                )
            )
            corrupt_status, corrupt_severity = _status_for_count(total_corrupt_count)
            findings.append(
                DatasetIntegrityFinding(
                    category="corrupt",
                    severity=corrupt_severity,
                    status=corrupt_status,
                    message="corrupt or future-dated records detected" if total_corrupt_count else "no corrupt records detected",
                    related_count=total_corrupt_count,
                    detail_json=_normalize_json_value({
                        "corrupt_examples": corrupt_examples,
                        "future_examples": future_examples,
                        "future_row_count": future_row_count,
                        "safe_available_to": safe_available_to.isoformat() if safe_available_to else None,
                    }),
                )
            )

            dataset_status = _dataset_status_from_findings(findings)
            report = DatasetIntegrityDatasetReport(
                data_type=data_type,
                status=dataset_status,
                row_count=row_count,
                expected_interval_seconds=int(interval.total_seconds()) if interval is not None else None,
                expected_points=expected_points,
                available_from=available_from,
                available_to=available_to,
                safe_available_to=safe_available_to,
                missing_count=missing_count,
                coverage_shortfall_count=coverage_shortfall_count,
                internal_missing_count=internal_missing_count,
                tail_missing_count=tail_missing_count,
                gap_count=len(gap_segments),
                duplicate_count=duplicate_count,
                corrupt_count=total_corrupt_count,
                future_row_count=future_row_count,
                findings=findings,
            )
            dataset_reports.append(report)

            if persist_findings:
                if interval is not None:
                    persisted_checks_written += _persist_integrity_check(
                        quality_repo=quality_repo,
                        connection=connection,
                        exchange_code=exchange_code,
                        unified_symbol=unified_symbol,
                        data_type=data_type,
                        check_name="integrity_gap_check",
                        expected_value="0",
                        observed_value=str(len(gap_segments)),
                        related_count=len(gap_segments),
                        detail_json=report.findings[0].detail_json,
                        status_override=report.findings[0].status,
                        severity_override=report.findings[0].severity,
                    )
                    resolved_gap_count = gap_repo.resolve_overlapping_open_gaps(
                        connection,
                        data_type=data_type,
                        exchange_code=exchange_code,
                        unified_symbol=unified_symbol,
                        gap_start=aligned_start_time,
                        gap_end=aligned_end_time,
                        detail_json={
                            "resolved_by": "dataset_integrity_validate",
                            "aligned_window_start": aligned_start_time.isoformat(),
                            "aligned_window_end": aligned_end_time.isoformat(),
                        },
                    )
                    if gap_segments:
                        for segment in gap_segments:
                            gap_repo.insert(
                                connection,
                                DataGapRecord(
                                    exchange_code=exchange_code,
                                    unified_symbol=unified_symbol,
                                    data_type=data_type,
                                    gap_start=segment["gap_start"],
                                    gap_end=segment["gap_end"],
                                    expected_count=segment["missing_points"],
                                    actual_count=0,
                                    detail_json={
                                        "source": "dataset_integrity_validate",
                                        "expected_interval_seconds": int(interval.total_seconds()),
                                    },
                                ),
                            )
                            persisted_gaps_written += 1
                    elif resolved_gap_count:
                        persisted_gaps_written += 0
                persisted_checks_written += _persist_integrity_check(
                    quality_repo=quality_repo,
                    connection=connection,
                    exchange_code=exchange_code,
                    unified_symbol=unified_symbol,
                    data_type=data_type,
                    check_name="integrity_missing_check",
                    expected_value="0",
                    observed_value=str(missing_count),
                    related_count=missing_count,
                    detail_json=_normalize_json_value({
                        "missing_count": missing_count,
                        "coverage_shortfall_count": coverage_shortfall_count,
                        "internal_missing_count": internal_missing_count,
                        "tail_missing_count": tail_missing_count,
                        "available_from": available_from.isoformat() if available_from else None,
                        "safe_available_to": safe_available_to.isoformat() if safe_available_to else None,
                        "aligned_window_start": aligned_start_time.isoformat(),
                        "aligned_window_end": aligned_end_time.isoformat(),
                    }),
                    status_override=(
                        "fail"
                        if internal_missing_count > 0
                        else ("warning" if missing_count > 0 else "pass")
                    ),
                    severity_override=(
                        "error"
                        if internal_missing_count > 0
                        else ("warning" if missing_count > 0 else "info")
                    ),
                )
                persisted_checks_written += _persist_integrity_check(
                    quality_repo=quality_repo,
                    connection=connection,
                    exchange_code=exchange_code,
                    unified_symbol=unified_symbol,
                    data_type=data_type,
                    check_name="integrity_duplicate_check",
                    expected_value="0",
                    observed_value=str(duplicate_count),
                    related_count=duplicate_count,
                    detail_json=next(f.detail_json for f in findings if f.category == "duplicate"),
                )
                persisted_checks_written += _persist_integrity_check(
                    quality_repo=quality_repo,
                    connection=connection,
                    exchange_code=exchange_code,
                    unified_symbol=unified_symbol,
                    data_type=data_type,
                    check_name="integrity_corrupt_check",
                    expected_value="0",
                    observed_value=str(total_corrupt_count),
                    related_count=total_corrupt_count,
                    detail_json=next(f.detail_json for f in findings if f.category == "corrupt"),
                )

        summary = DatasetIntegritySummary(
            dataset_count=len(dataset_reports),
            passed_datasets=sum(1 for report in dataset_reports if report.status == "pass"),
            warning_datasets=sum(1 for report in dataset_reports if report.status == "warning"),
            failed_datasets=sum(1 for report in dataset_reports if report.status == "fail"),
            total_gap_count=sum(report.gap_count for report in dataset_reports),
            total_missing_count=sum(report.missing_count for report in dataset_reports),
            total_coverage_shortfall_count=sum(report.coverage_shortfall_count for report in dataset_reports),
            total_internal_missing_count=sum(report.internal_missing_count for report in dataset_reports),
            total_tail_missing_count=sum(report.tail_missing_count for report in dataset_reports),
            total_duplicate_count=sum(report.duplicate_count for report in dataset_reports),
            total_corrupt_count=sum(report.corrupt_count for report in dataset_reports),
            total_future_row_count=sum(report.future_row_count for report in dataset_reports),
        )

    return DatasetIntegrityValidationResult(
        exchange_code=exchange_code,
        unified_symbol=unified_symbol,
        start_time=start_time,
        end_time=end_time,
        observed_at=effective_observed_at,
        persisted_checks_written=persisted_checks_written,
        persisted_gaps_written=persisted_gaps_written,
        summary=summary,
        datasets=dataset_reports,
    )


def run_bar_gap_checks(
    *,
    exchange_code: str,
    unified_symbol: str,
    start_time: datetime,
    end_time: datetime,
    interval_minutes: int = 1,
) -> DataQualityRunResult:
    checks_written = 0
    gaps_written = 0
    aligned_start_time, aligned_end_time = _align_bar_window(start_time, end_time)
    expected_points = 0
    current = aligned_start_time
    expected_timestamps: set[datetime] = set()
    while current <= aligned_end_time:
        expected_timestamps.add(current)
        expected_points += 1
        current += timedelta(minutes=interval_minutes)

    with transaction_scope() as connection:
        instrument_id = resolve_instrument_id(connection, exchange_code, unified_symbol)
        rows = connection.exec_driver_sql(
            """
            select bar_time
            from md.bars_1m
            where instrument_id = %s
              and bar_time between %s and %s
            order by bar_time asc
            """,
            (instrument_id, aligned_start_time, aligned_end_time),
        ).all()
        observed_timestamps = {row[0] for row in rows}
        missing_timestamps = sorted(expected_timestamps - observed_timestamps)

        quality_repo = DataQualityCheckRepository()
        gap_repo = DataGapRepository()
        log_repo = SystemLogRepository()

        resolved_gap_count = gap_repo.resolve_overlapping_open_gaps(
            connection,
            data_type="bars_1m",
            exchange_code=exchange_code,
            unified_symbol=unified_symbol,
            gap_start=start_time,
            gap_end=end_time,
            detail_json={
                "resolved_by": "bar_gap_check",
                "requested_window_start": start_time.isoformat(),
                "requested_window_end": end_time.isoformat(),
                "aligned_window_start": aligned_start_time.isoformat(),
                "aligned_window_end": aligned_end_time.isoformat(),
            },
        )

        if missing_timestamps:
            segments: list[tuple[datetime, datetime, int]] = []
            segment_start = missing_timestamps[0]
            segment_end = missing_timestamps[0]
            segment_count = 1
            for ts in missing_timestamps[1:]:
                if ts == segment_end + timedelta(minutes=interval_minutes):
                    segment_end = ts
                    segment_count += 1
                    continue
                segments.append((segment_start, segment_end, segment_count))
                segment_start = ts
                segment_end = ts
                segment_count = 1
            segments.append((segment_start, segment_end, segment_count))

            for gap_start, gap_end, count in segments:
                gap_repo.insert(
                    connection,
                    DataGapRecord(
                        exchange_code=exchange_code,
                        unified_symbol=unified_symbol,
                        data_type="bars_1m",
                        gap_start=gap_start,
                        gap_end=gap_end,
                        expected_count=count,
                        actual_count=0,
                        detail_json={"interval_minutes": interval_minutes},
                    ),
                )
                gaps_written += 1

        quality_repo.insert(
            connection,
            DataQualityCheckRecord(
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
                data_type="bars_1m",
                check_name="bar_gap_check",
                severity="error" if missing_timestamps else "info",
                status="fail" if missing_timestamps else "pass",
                expected_value=str(expected_points),
                observed_value=str(len(observed_timestamps)),
                detail_json={
                    "requested_window_start": start_time.isoformat(),
                    "requested_window_end": end_time.isoformat(),
                    "aligned_window_start": aligned_start_time.isoformat(),
                    "aligned_window_end": aligned_end_time.isoformat(),
                    "missing_timestamps": [ts.isoformat() for ts in missing_timestamps],
                },
            ),
        )
        checks_written += 1
        log_repo.insert(
            connection,
            SystemLogRecord(
                service_name="data_quality",
                level="warning" if missing_timestamps else "info",
                message=f"bar gap check completed for {unified_symbol}",
                context_json={
                    "gaps_written": gaps_written,
                    "checks_written": checks_written,
                    "resolved_gap_count": resolved_gap_count,
                },
            ),
        )

    return DataQualityRunResult(checks_written=checks_written, gaps_written=gaps_written)


def run_freshness_checks(
    *,
    exchange_code: str,
    unified_symbol: str,
    observed_at: datetime | None = None,
) -> DataQualityRunResult:
    now = observed_at or datetime.now(timezone.utc)
    checks_written = 0
    with transaction_scope() as connection:
        instrument_id = resolve_instrument_id(connection, exchange_code, unified_symbol)
        quality_repo = DataQualityCheckRepository()

        freshness_specs = [
            ("bars_1m", "bar_time", "md.bars_1m", BAR_FRESHNESS_SLA),
            ("trades", "event_time", "md.trades", TRADE_FRESHNESS_SLA),
        ]
        if not _is_spot_symbol(unified_symbol):
            freshness_specs.extend(
                [
                    ("funding_rates", "funding_time", "md.funding_rates", FUNDING_FRESHNESS_SLA),
                    ("open_interest", "ts", "md.open_interest", OPEN_INTEREST_FRESHNESS_SLA),
                    ("mark_prices", "ts", "md.mark_prices", MARK_PRICE_FRESHNESS_SLA),
                    ("index_prices", "ts", "md.index_prices", INDEX_PRICE_FRESHNESS_SLA),
                ]
            )

        for data_type, timestamp_column, table_name, sla in freshness_specs:
            latest = connection.exec_driver_sql(
                f"select max({timestamp_column}) from {table_name} where instrument_id = %s",
                (instrument_id,),
            ).scalar_one()
            if latest is None:
                status = "fail"
                severity = "error"
                observed_value = "missing"
                lag_seconds = None
            else:
                lag = now - latest
                lag_seconds = int(lag.total_seconds())
                status = "pass" if lag <= sla else "fail"
                severity = "info" if status == "pass" else "warning"
                observed_value = str(lag_seconds)

            quality_repo.insert(
                connection,
                DataQualityCheckRecord(
                    exchange_code=exchange_code,
                    unified_symbol=unified_symbol,
                    data_type=data_type,
                    check_name="freshness_check",
                    severity=severity,
                    status=status,
                    expected_value=str(int(sla.total_seconds())),
                    observed_value=observed_value,
                    detail_json={"observed_at": now.isoformat(), "latest_timestamp": latest.isoformat() if latest else None},
                ),
            )
            checks_written += 1

    return DataQualityRunResult(checks_written=checks_written, gaps_written=0)


def run_duplicate_checks(
    *,
    exchange_code: str,
    unified_symbol: str,
    raw_event_channel: str | None = None,
) -> DataQualityRunResult:
    checks_written = 0
    with transaction_scope() as connection:
        instrument_id = resolve_instrument_id(connection, exchange_code, unified_symbol)
        quality_repo = DataQualityCheckRepository()

        bar_duplicates = connection.exec_driver_sql(
            """
            select count(*)
            from (
                select bar_time, count(*) as row_count
                from md.bars_1m
                where instrument_id = %s
                group by bar_time
                having count(*) > 1
            ) duplicates
            """,
            (instrument_id,),
        ).scalar_one()
        quality_repo.insert(
            connection,
            DataQualityCheckRecord(
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
                data_type="bars_1m",
                check_name="duplicate_check",
                severity="info" if bar_duplicates == 0 else "error",
                status="pass" if bar_duplicates == 0 else "fail",
                expected_value="0",
                observed_value=str(bar_duplicates),
                detail_json={},
            ),
        )
        checks_written += 1

        trade_duplicates = connection.exec_driver_sql(
            """
            select count(*)
            from (
                select exchange_trade_id, count(*) as row_count
                from md.trades
                where instrument_id = %s
                group by exchange_trade_id
                having count(*) > 1
            ) duplicates
            """,
            (instrument_id,),
        ).scalar_one()
        quality_repo.insert(
            connection,
            DataQualityCheckRecord(
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
                data_type="trades",
                check_name="duplicate_check",
                severity="info" if trade_duplicates == 0 else "error",
                status="pass" if trade_duplicates == 0 else "fail",
                expected_value="0",
                observed_value=str(trade_duplicates),
                detail_json={},
            ),
        )
        checks_written += 1

        if not _is_spot_symbol(unified_symbol):
            mark_duplicates = connection.exec_driver_sql(
                """
                select count(*)
                from (
                    select ts, count(*) as row_count
                    from md.mark_prices
                    where instrument_id = %s
                    group by ts
                    having count(*) > 1
                ) duplicates
                """,
                (instrument_id,),
            ).scalar_one()
            quality_repo.insert(
                connection,
                DataQualityCheckRecord(
                    exchange_code=exchange_code,
                    unified_symbol=unified_symbol,
                    data_type="mark_prices",
                    check_name="duplicate_check",
                    severity="info" if mark_duplicates == 0 else "error",
                    status="pass" if mark_duplicates == 0 else "fail",
                    expected_value="0",
                    observed_value=str(mark_duplicates),
                    detail_json={},
                ),
            )
            checks_written += 1

            index_duplicates = connection.exec_driver_sql(
                """
                select count(*)
                from (
                    select ts, count(*) as row_count
                    from md.index_prices
                    where instrument_id = %s
                    group by ts
                    having count(*) > 1
                ) duplicates
                """,
                (instrument_id,),
            ).scalar_one()
            quality_repo.insert(
                connection,
                DataQualityCheckRecord(
                    exchange_code=exchange_code,
                    unified_symbol=unified_symbol,
                    data_type="index_prices",
                    check_name="duplicate_check",
                    severity="info" if index_duplicates == 0 else "error",
                    status="pass" if index_duplicates == 0 else "fail",
                    expected_value="0",
                    observed_value=str(index_duplicates),
                    detail_json={},
                ),
            )
            checks_written += 1

        raw_filters = ["raw.instrument_id = %s"]
        params: list[object] = [instrument_id]
        if raw_event_channel is not None:
            raw_filters.append("raw.channel = %s")
            params.append(raw_event_channel)
        raw_where = " and ".join(raw_filters)
        raw_duplicates = connection.exec_driver_sql(
            f"""
            select count(*)
            from (
                select coalesce(source_message_id, ''), count(*) as row_count
                from md.raw_market_events raw
                where {raw_where}
                group by coalesce(source_message_id, '')
                having coalesce(source_message_id, '') <> '' and count(*) > 1
            ) duplicates
            """,
            tuple(params),
        ).scalar_one()
        quality_repo.insert(
            connection,
            DataQualityCheckRecord(
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
                data_type="raw_market_events",
                check_name="duplicate_check",
                severity="info" if raw_duplicates == 0 else "warning",
                status="pass" if raw_duplicates == 0 else "fail",
                expected_value="0",
                observed_value=str(raw_duplicates),
                detail_json={"channel": raw_event_channel},
            ),
        )
        checks_written += 1

    return DataQualityRunResult(checks_written=checks_written, gaps_written=0)


def run_snapshot_continuity_checks(
    *,
    exchange_code: str,
    unified_symbol: str,
    start_time: datetime,
    end_time: datetime,
) -> DataQualityRunResult:
    checks_written = 0
    with transaction_scope() as connection:
        instrument_id = resolve_instrument_id(connection, exchange_code, unified_symbol)
        quality_repo = DataQualityCheckRepository()
        continuity_specs: list[tuple[str, str, str, timedelta]] = []
        if not _is_spot_symbol(unified_symbol):
            continuity_specs.extend(
                [
                    ("funding_rates", "md.funding_rates", "funding_time", FUNDING_CONTINUITY_INTERVAL),
                    ("open_interest", "md.open_interest", "ts", OPEN_INTEREST_CONTINUITY_INTERVAL),
                    ("mark_prices", "md.mark_prices", "ts", MARK_INDEX_CONTINUITY_INTERVAL),
                    ("index_prices", "md.index_prices", "ts", MARK_INDEX_CONTINUITY_INTERVAL),
                ]
            )

        for data_type, table_name, timestamp_column, expected_interval in continuity_specs:
            rows = connection.exec_driver_sql(
                f"""
                select {timestamp_column}
                from {table_name}
                where instrument_id = %s
                  and {timestamp_column} between %s and %s
                order by {timestamp_column} asc
                """,
                (instrument_id, start_time, end_time),
            ).all()
            timestamps = [row[0] for row in rows]
            continuity_breaks: list[dict[str, str | int]] = []
            for previous, current in zip(timestamps, timestamps[1:]):
                delta = current - previous
                if delta > expected_interval * 2:
                    continuity_breaks.append(
                        {
                            "previous_timestamp": previous.isoformat(),
                            "current_timestamp": current.isoformat(),
                            "delta_seconds": int(delta.total_seconds()),
                        }
                    )

            quality_repo.insert(
                connection,
                DataQualityCheckRecord(
                    exchange_code=exchange_code,
                    unified_symbol=unified_symbol,
                    data_type=data_type,
                    check_name="continuity_check",
                    severity="warning" if continuity_breaks else "info",
                    status="fail" if continuity_breaks else "pass",
                    expected_value=str(int(expected_interval.total_seconds())),
                    observed_value=str(len(continuity_breaks)),
                    detail_json={
                        "window_start": start_time.isoformat(),
                        "window_end": end_time.isoformat(),
                        "breaks": continuity_breaks,
                    },
                ),
            )
            checks_written += 1

    return DataQualityRunResult(checks_written=checks_written, gaps_written=0)


def run_phase4_quality_suite(
    *,
    exchange_code: str,
    unified_symbol: str,
    gap_start_time: datetime,
    gap_end_time: datetime,
    observed_at: datetime | None = None,
    raw_event_channel: str | None = None,
) -> DataQualityRunResult:
    gap_result = run_bar_gap_checks(
        exchange_code=exchange_code,
        unified_symbol=unified_symbol,
        start_time=gap_start_time,
        end_time=gap_end_time,
    )
    freshness_result = run_freshness_checks(
        exchange_code=exchange_code,
        unified_symbol=unified_symbol,
        observed_at=observed_at,
    )
    duplicate_result = run_duplicate_checks(
        exchange_code=exchange_code,
        unified_symbol=unified_symbol,
        raw_event_channel=raw_event_channel,
    )
    continuity_result = run_snapshot_continuity_checks(
        exchange_code=exchange_code,
        unified_symbol=unified_symbol,
        start_time=gap_start_time,
        end_time=gap_end_time,
    )
    return DataQualityRunResult(
        checks_written=(
            gap_result.checks_written
            + freshness_result.checks_written
            + duplicate_result.checks_written
            + continuity_result.checks_written
        ),
        gaps_written=(
            gap_result.gaps_written
            + freshness_result.gaps_written
            + duplicate_result.gaps_written
            + continuity_result.gaps_written
        ),
    )
