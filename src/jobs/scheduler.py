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


def phase4_schedule_plan() -> list[ScheduledJobDefinition]:
    return [
        ScheduledJobDefinition(
            job_id="binance_market_snapshot_remediation",
            trigger="interval:600s",
            kwargs={
                "job_type": "market_snapshot_remediation",
                "exchange_code": "binance",
                "datasets": [
                    "funding_rates",
                    "open_interest",
                    "mark_prices",
                    "index_prices",
                    "global_long_short_account_ratios",
                    "top_trader_long_short_account_ratios",
                    "top_trader_long_short_position_ratios",
                    "taker_long_short_ratios",
                ],
            },
        )
    ]


def register_phase3_jobs(scheduler: Any) -> None:
    for definition in phase3_schedule_plan():
        scheduler.add_job(id=definition.job_id, trigger=definition.trigger, kwargs=definition.kwargs)


def register_phase4_jobs(scheduler: Any) -> None:
    for definition in phase4_schedule_plan():
        scheduler.add_job(id=definition.job_id, trigger=definition.trigger, kwargs=definition.kwargs)
