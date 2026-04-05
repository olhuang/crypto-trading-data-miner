from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from ingestion.binance.public_rest import BinancePublicRestClient
from jobs.data_quality import FUNDING_FRESHNESS_SLA, OPEN_INTEREST_FRESHNESS_SLA
from jobs.refresh_market_snapshots import run_market_snapshot_refresh
from storage.db import connection_scope, transaction_scope
from storage.lookups import resolve_instrument_id
from storage.repositories.ops import IngestionJobRepository, SystemLogRecord, SystemLogRepository


MARK_PRICE_FRESHNESS_SLA = timedelta(minutes=10)
INDEX_PRICE_FRESHNESS_SLA = timedelta(minutes=10)
SENTIMENT_RATIO_FRESHNESS_SLA = timedelta(minutes=15)
DEFAULT_SENTIMENT_RATIO_PERIOD = "5m"

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


@dataclass(slots=True)
class MarketSnapshotRemediationResult:
    ingestion_job_id: int
    status: str
    records_written: int
    refresh_job_id: int | None
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
    history_plans = [
        plan
        for plan in plans
        if plan.data_type
        in {
            "open_interest",
            "mark_prices",
            "index_prices",
            "global_long_short_account_ratios",
            "top_trader_long_short_account_ratios",
            "top_trader_long_short_position_ratios",
            "taker_long_short_ratios",
        }
        and plan.remediation_required
    ]
    refresh_job_id: int | None = None
    records_written = 0

    try:
        if funding_plan and funding_plan.remediation_required or history_plans:
            history_start = min((plan.planned_start_time for plan in history_plans if plan.planned_start_time), default=None)
            history_end = max((plan.planned_end_time for plan in history_plans if plan.planned_end_time), default=None)
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
                include_open_interest=any(plan.data_type == "open_interest" for plan in history_plans),
                include_mark_price=any(plan.data_type == "mark_prices" for plan in history_plans),
                include_index_price=any(plan.data_type == "index_prices" for plan in history_plans),
                include_global_long_short_account_ratio=any(
                    plan.data_type == "global_long_short_account_ratios" for plan in history_plans
                ),
                include_top_trader_long_short_account_ratio=any(
                    plan.data_type == "top_trader_long_short_account_ratios" for plan in history_plans
                ),
                include_top_trader_long_short_position_ratio=any(
                    plan.data_type == "top_trader_long_short_position_ratios" for plan in history_plans
                ),
                include_taker_long_short_ratio=any(plan.data_type == "taker_long_short_ratios" for plan in history_plans),
            )
            refresh_job_id = refresh_result.ingestion_job_id
            records_written = refresh_result.records_written

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
                    context_json={"job_id": job_id, "refresh_job_id": refresh_job_id, "records_written": records_written},
                ),
            )

        return MarketSnapshotRemediationResult(
            ingestion_job_id=job_id,
            status="succeeded",
            records_written=records_written,
            refresh_job_id=refresh_job_id,
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
