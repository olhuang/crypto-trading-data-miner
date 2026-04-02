from __future__ import annotations

from dataclasses import dataclass
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
