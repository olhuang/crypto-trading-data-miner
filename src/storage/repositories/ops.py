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
