from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class ScheduledJobDefinition:
    job_id: str
    trigger: str
    kwargs: dict[str, Any]


def phase3_schedule_plan() -> list[ScheduledJobDefinition]:
    return [
        ScheduledJobDefinition(
            job_id="binance_instrument_sync_hourly",
            trigger="cron:0 * * * *",
            kwargs={"job_type": "instrument_sync", "exchange_code": "binance"},
        ),
        ScheduledJobDefinition(
            job_id="binance_market_snapshot_refresh",
            trigger="interval:300s",
            kwargs={"job_type": "market_snapshot_refresh", "exchange_code": "binance"},
        ),
    ]


def register_phase3_jobs(scheduler: Any) -> None:
    for definition in phase3_schedule_plan():
        scheduler.add_job(id=definition.job_id, trigger=definition.trigger, kwargs=definition.kwargs)
