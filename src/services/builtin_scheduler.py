from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from config import settings
from jobs.refresh_market_snapshots import run_market_snapshot_refresh
from jobs.remediate_market_snapshots import run_market_snapshot_remediation
from jobs.scheduler import ScheduledJobDefinition, phase3_schedule_plan, phase4_schedule_plan
from jobs.sync_instruments import run_instrument_sync


LOGGER = logging.getLogger(__name__)
BUILTIN_SCHEDULER_REQUESTED_BY = "builtin_scheduler"


@dataclass(slots=True)
class BuiltinSchedulerHandle:
    tasks: list[asyncio.Task[Any]]
    job_ids: list[str]

    async def stop(self) -> None:
        for task in self.tasks:
            task.cancel()
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)


def _normalize_job_groups(value: str) -> list[str]:
    normalized = [item.strip().lower() for item in value.split(",") if item.strip()]
    if not normalized:
        return []
    unsupported = sorted(set(normalized) - {"phase3", "phase4"})
    if unsupported:
        raise ValueError(f"unsupported builtin scheduler job group(s): {', '.join(unsupported)}")
    deduped: list[str] = []
    for item in normalized:
        if item not in deduped:
            deduped.append(item)
    return deduped


def enabled_builtin_scheduler_definitions() -> list[ScheduledJobDefinition]:
    definitions: list[ScheduledJobDefinition] = []
    selected_groups = _normalize_job_groups(settings.builtin_scheduler_job_groups)
    if "phase3" in selected_groups:
        definitions.extend(phase3_schedule_plan())
    if "phase4" in selected_groups:
        definitions.extend(phase4_schedule_plan())

    deduped: list[ScheduledJobDefinition] = []
    seen_job_ids: set[str] = set()
    for definition in definitions:
        if definition.job_id in seen_job_ids:
            continue
        seen_job_ids.add(definition.job_id)
        deduped.append(definition)
    return deduped


def _next_run_time(trigger: str, *, now: datetime) -> datetime:
    if trigger.startswith("interval:") and trigger.endswith("s"):
        seconds = int(trigger.removeprefix("interval:").removesuffix("s"))
        return now + timedelta(seconds=seconds)
    if trigger.startswith("cron:"):
        cron_body = trigger.removeprefix("cron:")
        minute, hour, day, month, weekday = cron_body.split()
        if (hour, day, month, weekday) != ("*", "*", "*", "*") or not minute.isdigit():
            raise ValueError(f"unsupported builtin scheduler cron trigger: {trigger}")
        scheduled_minute = int(minute)
        candidate = now.replace(minute=scheduled_minute, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(hours=1)
        return candidate
    raise ValueError(f"unsupported builtin scheduler trigger: {trigger}")


def _definition_runner_kwargs(definition: ScheduledJobDefinition) -> dict[str, Any]:
    kwargs = dict(definition.kwargs)
    job_type = kwargs.pop("job_type")
    exchange_code = kwargs.get("exchange_code", settings.builtin_scheduler_exchange_code)
    shared_market_kwargs = {
        "exchange_code": exchange_code,
        "symbol": settings.builtin_scheduler_symbol,
        "unified_symbol": settings.builtin_scheduler_unified_symbol,
        "requested_by": BUILTIN_SCHEDULER_REQUESTED_BY,
    }
    if job_type == "instrument_sync":
        return {
            "runner": run_instrument_sync,
            "kwargs": {
                "exchange_code": exchange_code,
                "requested_by": BUILTIN_SCHEDULER_REQUESTED_BY,
            },
        }
    if job_type == "market_snapshot_refresh":
        return {
            "runner": run_market_snapshot_refresh,
            "kwargs": {
                **shared_market_kwargs,
                **{key: value for key, value in kwargs.items() if key != "exchange_code"},
            },
        }
    if job_type == "market_snapshot_remediation":
        return {
            "runner": run_market_snapshot_remediation,
            "kwargs": {
                **shared_market_kwargs,
                **{key: value for key, value in kwargs.items() if key != "exchange_code"},
            },
        }
    raise ValueError(f"unsupported builtin scheduler job_type: {job_type}")


async def _run_definition_once(definition: ScheduledJobDefinition) -> None:
    runner_payload = _definition_runner_kwargs(definition)
    runner = runner_payload["runner"]
    kwargs = runner_payload["kwargs"]
    LOGGER.info("builtin scheduler starting job %s", definition.job_id)
    await asyncio.to_thread(runner, **kwargs)
    LOGGER.info("builtin scheduler finished job %s", definition.job_id)


async def _run_definition_loop(definition: ScheduledJobDefinition) -> None:
    while True:
        now = datetime.now(timezone.utc)
        next_run_at = _next_run_time(definition.trigger, now=now)
        sleep_seconds = max((next_run_at - now).total_seconds(), 0.0)
        try:
            await asyncio.sleep(sleep_seconds)
            await _run_definition_once(definition)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOGGER.exception("builtin scheduler job failed: %s", definition.job_id)


def start_builtin_scheduler() -> BuiltinSchedulerHandle | None:
    if not settings.enable_builtin_scheduler:
        return None
    definitions = enabled_builtin_scheduler_definitions()
    if not definitions:
        return None
    tasks = [
        asyncio.create_task(_run_definition_loop(definition), name=f"builtin-scheduler:{definition.job_id}")
        for definition in definitions
    ]
    return BuiltinSchedulerHandle(tasks=tasks, job_ids=[definition.job_id for definition in definitions])
