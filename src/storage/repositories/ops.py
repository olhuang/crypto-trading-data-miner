from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

from storage.lookups import resolve_exchange_id, resolve_instrument_id


@dataclass(slots=True)
class SystemLogRecord:
    service_name: str
    level: str
    message: str
    context_json: dict[str, Any] | None = None


@dataclass(slots=True)
class IngestionJobRecord:
    service_name: str
    data_type: str
    status: str
    exchange_code: str | None = None
    unified_symbol: str | None = None
    schedule_type: str | None = None
    window_start: Any | None = None
    window_end: Any | None = None
    records_expected: int | None = None
    records_written: int | None = None
    finished_at: Any | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] | None = None


@dataclass(slots=True)
class WsConnectionEventRecord:
    service_name: str
    event_type: str
    event_time: datetime
    exchange_code: str | None = None
    channel: str | None = None
    connection_id: str | None = None
    detail_json: dict[str, Any] | None = None


@dataclass(slots=True)
class DataQualityCheckRecord:
    data_type: str
    check_name: str
    severity: str
    status: str
    exchange_code: str | None = None
    unified_symbol: str | None = None
    check_time: Any | None = None
    expected_value: str | None = None
    observed_value: str | None = None
    detail_json: dict[str, Any] | None = None


@dataclass(slots=True)
class DataGapRecord:
    data_type: str
    gap_start: Any
    gap_end: Any
    status: str = "open"
    exchange_code: str | None = None
    unified_symbol: str | None = None
    expected_count: int | None = None
    actual_count: int | None = None
    resolved_at: Any | None = None
    detail_json: dict[str, Any] | None = None


class SystemLogRepository:
    def insert(self, connection: Connection, record: SystemLogRecord) -> int:
        return int(
            connection.execute(
                text(
                    """
                    insert into ops.system_logs (
                        service_name,
                        level,
                        message,
                        context_json
                    ) values (
                        :service_name,
                        :level,
                        :message,
                        cast(:context_json as jsonb)
                    )
                    returning log_id
                    """
                ),
                {
                    "service_name": record.service_name,
                    "level": record.level,
                    "message": record.message,
                    "context_json": json.dumps(record.context_json or {}),
                },
            ).scalar_one()
        )


class IngestionJobRepository:
    def create_job(
        self,
        connection: Connection,
        *,
        service_name: str,
        data_type: str,
        status: str,
        requested_by: str,
        exchange_code: str | None = None,
        unified_symbol: str | None = None,
        schedule_type: str | None = None,
        window_start: Any | None = None,
        window_end: Any | None = None,
        records_expected: int | None = None,
        records_written: int | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> int:
        return self.insert(
            connection,
            IngestionJobRecord(
                service_name=service_name,
                data_type=data_type,
                status=status,
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
                schedule_type=schedule_type,
                window_start=window_start,
                window_end=window_end,
                records_expected=records_expected,
                records_written=records_written,
                metadata_json={**(metadata_json or {}), "requested_by": requested_by},
            ),
        )

    def insert(self, connection: Connection, record: IngestionJobRecord) -> int:
        exchange_id = resolve_exchange_id(connection, record.exchange_code) if record.exchange_code else None
        instrument_id = None
        if record.exchange_code and record.unified_symbol:
            instrument_id = resolve_instrument_id(connection, record.exchange_code, record.unified_symbol)

        return int(
            connection.execute(
                text(
                    """
                    insert into ops.ingestion_jobs (
                        service_name,
                        exchange_id,
                        instrument_id,
                        data_type,
                        schedule_type,
                        window_start,
                        window_end,
                        status,
                        records_expected,
                        records_written,
                        finished_at,
                        error_message,
                        metadata_json
                    ) values (
                        :service_name,
                        :exchange_id,
                        :instrument_id,
                        :data_type,
                        :schedule_type,
                        :window_start,
                        :window_end,
                        :status,
                        :records_expected,
                        :records_written,
                        :finished_at,
                        :error_message,
                        cast(:metadata_json as jsonb)
                    )
                    returning ingestion_job_id
                    """
                ),
                {
                    "service_name": record.service_name,
                    "exchange_id": exchange_id,
                    "instrument_id": instrument_id,
                    "data_type": record.data_type,
                    "schedule_type": record.schedule_type,
                    "window_start": record.window_start,
                    "window_end": record.window_end,
                    "status": record.status,
                    "records_expected": record.records_expected,
                    "records_written": record.records_written,
                    "finished_at": record.finished_at,
                    "error_message": record.error_message,
                    "metadata_json": json.dumps(record.metadata_json or {}),
                },
            ).scalar_one()
        )

    def finish_job(
        self,
        connection: Connection,
        ingestion_job_id: int,
        *,
        status: str,
        finished_at: Any,
        records_expected: int | None = None,
        records_written: int | None = None,
        error_message: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> None:
        if metadata_json is None:
            connection.execute(
                text(
                    """
                    update ops.ingestion_jobs
                    set
                        status = :status,
                        finished_at = :finished_at,
                        records_expected = coalesce(:records_expected, records_expected),
                        records_written = coalesce(:records_written, records_written),
                        error_message = :error_message
                    where ingestion_job_id = :ingestion_job_id
                    """
                ),
                {
                    "ingestion_job_id": ingestion_job_id,
                    "status": status,
                    "finished_at": finished_at,
                    "records_expected": records_expected,
                    "records_written": records_written,
                    "error_message": error_message,
                },
            )
            return

        connection.execute(
            text(
                """
                update ops.ingestion_jobs
                set
                    status = :status,
                    finished_at = :finished_at,
                    records_expected = coalesce(:records_expected, records_expected),
                    records_written = coalesce(:records_written, records_written),
                    error_message = :error_message,
                    metadata_json = cast(:metadata_json as jsonb)
                where ingestion_job_id = :ingestion_job_id
                """
            ),
            {
                "ingestion_job_id": ingestion_job_id,
                "status": status,
                "finished_at": finished_at,
                "records_expected": records_expected,
                "records_written": records_written,
                "error_message": error_message,
                "metadata_json": json.dumps(metadata_json),
            },
        )

    def get_job(self, connection: Connection, ingestion_job_id: int) -> dict[str, Any] | None:
        row = connection.execute(
            text(
                """
                select
                    job.ingestion_job_id as job_id,
                    job.service_name,
                    job.data_type,
                    job.status,
                    job.started_at,
                    job.finished_at,
                    job.records_expected,
                    job.records_written,
                    job.error_message,
                    job.metadata_json,
                    exchange.exchange_code,
                    instrument.unified_symbol
                from ops.ingestion_jobs job
                left join ref.exchanges exchange on exchange.exchange_id = job.exchange_id
                left join ref.instruments instrument on instrument.instrument_id = job.instrument_id
                where job.ingestion_job_id = :ingestion_job_id
                """
            ),
            {"ingestion_job_id": ingestion_job_id},
        ).mappings().first()
        return None if row is None else dict(row)

    def list_recent(
        self,
        connection: Connection,
        *,
        limit: int = 100,
        status: str | None = None,
        service_name: str | None = None,
        data_type: str | None = None,
        exchange_code: str | None = None,
        unified_symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            filters.append("job.status = :status")
            params["status"] = status
        if service_name is not None:
            filters.append("job.service_name = :service_name")
            params["service_name"] = service_name
        if data_type is not None:
            filters.append("job.data_type = :data_type")
            params["data_type"] = data_type
        if exchange_code is not None:
            filters.append("exchange.exchange_code = :exchange_code")
            params["exchange_code"] = exchange_code
        if unified_symbol is not None:
            filters.append("instrument.unified_symbol = :unified_symbol")
            params["unified_symbol"] = unified_symbol
        where_clause = f"where {' and '.join(filters)}" if filters else ""
        rows = connection.execute(
            text(
                f"""
                select
                    job.ingestion_job_id as job_id,
                    job.service_name,
                    job.data_type,
                    job.status,
                    job.started_at,
                    job.finished_at,
                    job.records_expected,
                    job.records_written,
                    job.error_message,
                    job.metadata_json,
                    exchange.exchange_code,
                    instrument.unified_symbol
                from ops.ingestion_jobs job
                left join ref.exchanges exchange on exchange.exchange_id = job.exchange_id
                left join ref.instruments instrument on instrument.instrument_id = job.instrument_id
                {where_clause}
                order by job.started_at desc, job.ingestion_job_id desc
                limit :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]


class WsConnectionEventRepository:
    def insert(self, connection: Connection, record: WsConnectionEventRecord) -> int:
        exchange_id = resolve_exchange_id(connection, record.exchange_code) if record.exchange_code else None
        return int(
            connection.execute(
                text(
                    """
                    insert into ops.ws_connection_events (
                        service_name,
                        exchange_id,
                        channel,
                        event_time,
                        event_type,
                        connection_id,
                        detail_json
                    ) values (
                        :service_name,
                        :exchange_id,
                        :channel,
                        :event_time,
                        :event_type,
                        :connection_id,
                        cast(:detail_json as jsonb)
                    )
                    returning ws_event_id
                    """
                ),
                {
                    "service_name": record.service_name,
                    "exchange_id": exchange_id,
                    "channel": record.channel,
                    "event_time": record.event_time,
                    "event_type": record.event_type,
                    "connection_id": record.connection_id,
                    "detail_json": json.dumps(record.detail_json or {}),
                },
            ).scalar_one()
        )


class DataQualityCheckRepository:
    def insert(self, connection: Connection, record: DataQualityCheckRecord) -> int:
        exchange_id = resolve_exchange_id(connection, record.exchange_code) if record.exchange_code else None
        instrument_id = None
        if record.exchange_code and record.unified_symbol:
            instrument_id = resolve_instrument_id(connection, record.exchange_code, record.unified_symbol)
        return int(
            connection.execute(
                text(
                    """
                    insert into ops.data_quality_checks (
                        exchange_id,
                        instrument_id,
                        data_type,
                        check_time,
                        check_name,
                        severity,
                        status,
                        expected_value,
                        observed_value,
                        detail_json
                    ) values (
                        :exchange_id,
                        :instrument_id,
                        :data_type,
                        coalesce(:check_time, now()),
                        :check_name,
                        :severity,
                        :status,
                        :expected_value,
                        :observed_value,
                        cast(:detail_json as jsonb)
                    )
                    returning check_id
                    """
                ),
                {
                    "exchange_id": exchange_id,
                    "instrument_id": instrument_id,
                    "data_type": record.data_type,
                    "check_time": record.check_time,
                    "check_name": record.check_name,
                    "severity": record.severity,
                    "status": record.status,
                    "expected_value": record.expected_value,
                    "observed_value": record.observed_value,
                    "detail_json": json.dumps(record.detail_json or {}),
                },
            ).scalar_one()
        )

    def list_recent(
        self,
        connection: Connection,
        *,
        limit: int = 100,
        data_type: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        exchange_code: str | None = None,
        unified_symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        params: dict[str, Any] = {"limit": limit}
        if data_type is not None:
            filters.append("checks.data_type = :data_type")
            params["data_type"] = data_type
        if status is not None:
            filters.append("checks.status = :status")
            params["status"] = status
        if severity is not None:
            filters.append("checks.severity = :severity")
            params["severity"] = severity
        if exchange_code is not None:
            filters.append("exchange.exchange_code = :exchange_code")
            params["exchange_code"] = exchange_code
        if unified_symbol is not None:
            filters.append("instrument.unified_symbol = :unified_symbol")
            params["unified_symbol"] = unified_symbol
        where_clause = f"where {' and '.join(filters)}" if filters else ""
        rows = connection.execute(
            text(
                f"""
                select
                    checks.check_id,
                    exchange.exchange_code,
                    instrument.unified_symbol,
                    checks.data_type,
                    checks.check_time,
                    checks.check_name,
                    checks.severity,
                    checks.status,
                    checks.expected_value,
                    checks.observed_value,
                    checks.detail_json
                from ops.data_quality_checks checks
                left join ref.exchanges exchange on exchange.exchange_id = checks.exchange_id
                left join ref.instruments instrument on instrument.instrument_id = checks.instrument_id
                {where_clause}
                order by checks.check_time desc
                limit :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def summary(
        self,
        connection: Connection,
        *,
        data_type: str | None = None,
        exchange_code: str | None = None,
        unified_symbol: str | None = None,
    ) -> dict[str, int]:
        filters = []
        params: dict[str, Any] = {}
        if data_type is not None:
            filters.append("checks.data_type = :data_type")
            params["data_type"] = data_type
        if exchange_code is not None:
            filters.append("exchange.exchange_code = :exchange_code")
            params["exchange_code"] = exchange_code
        if unified_symbol is not None:
            filters.append("instrument.unified_symbol = :unified_symbol")
            params["unified_symbol"] = unified_symbol
        where_clause = f"where {' and '.join(filters)}" if filters else ""
        row = connection.execute(
            text(
                f"""
                select
                    count(*) as total_checks,
                    count(*) filter (where checks.status = 'pass') as passed_checks,
                    count(*) filter (where checks.status = 'fail') as failed_checks,
                    count(*) filter (where checks.severity in ('error', 'critical')) as severe_checks
                from ops.data_quality_checks checks
                left join ref.exchanges exchange on exchange.exchange_id = checks.exchange_id
                left join ref.instruments instrument on instrument.instrument_id = checks.instrument_id
                {where_clause}
                """
            ),
            params,
        ).mappings().first()
        return dict(row or {"total_checks": 0, "passed_checks": 0, "failed_checks": 0, "severe_checks": 0})


class DataGapRepository:
    def insert(self, connection: Connection, record: DataGapRecord) -> int:
        exchange_id = resolve_exchange_id(connection, record.exchange_code) if record.exchange_code else None
        instrument_id = None
        if record.exchange_code and record.unified_symbol:
            instrument_id = resolve_instrument_id(connection, record.exchange_code, record.unified_symbol)
        return int(
            connection.execute(
                text(
                    """
                    insert into ops.data_gaps (
                        exchange_id,
                        instrument_id,
                        data_type,
                        gap_start,
                        gap_end,
                        expected_count,
                        actual_count,
                        status,
                        resolved_at,
                        detail_json
                    ) values (
                        :exchange_id,
                        :instrument_id,
                        :data_type,
                        :gap_start,
                        :gap_end,
                        :expected_count,
                        :actual_count,
                        :status,
                        :resolved_at,
                        cast(:detail_json as jsonb)
                    )
                    returning gap_id
                    """
                ),
                {
                    "exchange_id": exchange_id,
                    "instrument_id": instrument_id,
                    "data_type": record.data_type,
                    "gap_start": record.gap_start,
                    "gap_end": record.gap_end,
                    "expected_count": record.expected_count,
                    "actual_count": record.actual_count,
                    "status": record.status,
                    "resolved_at": record.resolved_at,
                    "detail_json": json.dumps(record.detail_json or {}),
                },
            ).scalar_one()
        )

    def list_recent(
        self,
        connection: Connection,
        *,
        limit: int = 100,
        data_type: str | None = None,
        status: str | None = None,
        exchange_code: str | None = None,
        unified_symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        filters = []
        params: dict[str, Any] = {"limit": limit}
        if data_type is not None:
            filters.append("gaps.data_type = :data_type")
            params["data_type"] = data_type
        if status is not None:
            filters.append("gaps.status = :status")
            params["status"] = status
        if exchange_code is not None:
            filters.append("exchange.exchange_code = :exchange_code")
            params["exchange_code"] = exchange_code
        if unified_symbol is not None:
            filters.append("instrument.unified_symbol = :unified_symbol")
            params["unified_symbol"] = unified_symbol
        where_clause = f"where {' and '.join(filters)}" if filters else ""
        rows = connection.execute(
            text(
                f"""
                select
                    gaps.gap_id,
                    exchange.exchange_code,
                    instrument.unified_symbol,
                    gaps.data_type,
                    gaps.gap_start,
                    gaps.gap_end,
                    gaps.expected_count,
                    gaps.actual_count,
                    gaps.status,
                    gaps.detected_at,
                    gaps.resolved_at,
                    gaps.detail_json
                from ops.data_gaps gaps
                left join ref.exchanges exchange on exchange.exchange_id = gaps.exchange_id
                left join ref.instruments instrument on instrument.instrument_id = gaps.instrument_id
                {where_clause}
                order by gaps.detected_at desc
                limit :limit
                """
            ),
            params,
        ).mappings().all()
        return [dict(row) for row in rows]

    def resolve_gap(
        self,
        connection: Connection,
        gap_id: int,
        *,
        detail_json: dict[str, Any] | None = None,
        resolved_at: Any | None = None,
    ) -> None:
        if detail_json is None:
            connection.execute(
                text(
                    """
                    update ops.data_gaps
                    set
                        status = 'resolved',
                        resolved_at = coalesce(:resolved_at, now())
                    where gap_id = :gap_id
                    """
                ),
                {"gap_id": gap_id, "resolved_at": resolved_at},
            )
            return

        connection.execute(
            text(
                """
                update ops.data_gaps
                set
                    status = 'resolved',
                    resolved_at = coalesce(:resolved_at, now()),
                    detail_json = cast(:detail_json as jsonb)
                where gap_id = :gap_id
                """
            ),
            {
                "gap_id": gap_id,
                "resolved_at": resolved_at,
                "detail_json": json.dumps(detail_json),
            },
        )
