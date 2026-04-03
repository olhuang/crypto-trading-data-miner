from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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


BAR_FRESHNESS_SLA = timedelta(minutes=2)
TRADE_FRESHNESS_SLA = timedelta(minutes=2)
FUNDING_FRESHNESS_SLA = timedelta(hours=12)
OPEN_INTEREST_FRESHNESS_SLA = timedelta(minutes=10)
MARK_PRICE_FRESHNESS_SLA = timedelta(minutes=10)
INDEX_PRICE_FRESHNESS_SLA = timedelta(minutes=10)
FUNDING_CONTINUITY_INTERVAL = timedelta(hours=8)
OPEN_INTEREST_CONTINUITY_INTERVAL = timedelta(minutes=5)
MARK_INDEX_CONTINUITY_INTERVAL = timedelta(minutes=1)


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
    expected_points = 0
    current = start_time
    expected_timestamps: set[datetime] = set()
    while current <= end_time:
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
            (instrument_id, start_time, end_time),
        ).all()
        observed_timestamps = {row[0] for row in rows}
        missing_timestamps = sorted(expected_timestamps - observed_timestamps)

        quality_repo = DataQualityCheckRepository()
        gap_repo = DataGapRepository()
        log_repo = SystemLogRepository()

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
                detail_json={"missing_timestamps": [ts.isoformat() for ts in missing_timestamps]},
            ),
        )
        checks_written += 1
        log_repo.insert(
            connection,
            SystemLogRecord(
                service_name="data_quality",
                level="warning" if missing_timestamps else "info",
                message=f"bar gap check completed for {unified_symbol}",
                context_json={"gaps_written": gaps_written, "checks_written": checks_written},
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
            ("funding_rates", "funding_time", "md.funding_rates", FUNDING_FRESHNESS_SLA),
            ("open_interest", "ts", "md.open_interest", OPEN_INTEREST_FRESHNESS_SLA),
            ("mark_prices", "ts", "md.mark_prices", MARK_PRICE_FRESHNESS_SLA),
            ("index_prices", "ts", "md.index_prices", INDEX_PRICE_FRESHNESS_SLA),
        ]

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
        continuity_specs = [
            ("funding_rates", "md.funding_rates", "funding_time", FUNDING_CONTINUITY_INTERVAL),
            ("open_interest", "md.open_interest", "ts", OPEN_INTEREST_CONTINUITY_INTERVAL),
            ("mark_prices", "md.mark_prices", "ts", MARK_INDEX_CONTINUITY_INTERVAL),
            ("index_prices", "md.index_prices", "ts", MARK_INDEX_CONTINUITY_INTERVAL),
        ]

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
