from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Generic, TypeVar
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, ValidationError, model_validator
from fastapi.responses import JSONResponse

from config import settings
from backtest.assumption_registry import UnknownAssumptionBundleError, build_default_assumption_bundle_registry
from backtest.artifacts import BacktestArtifactCatalogProjector
from backtest.risk_registry import UnknownRiskPolicyError, build_default_risk_policy_registry
from backtest.runner import BacktestRunnerSkeleton
from backtest.compare import BacktestCompareNotFoundError, BacktestCompareProjector, BacktestCompareValidationError
from backtest.diagnostics import BacktestDiagnosticsProjector
from backtest.periods import BacktestPeriodBreakdownProjector
from models.backtest import BacktestRunConfig
from jobs.backfill_bars import run_bar_backfill
from jobs.data_quality import run_phase4_quality_suite
from jobs.remediate_market_snapshots import run_market_snapshot_remediation
from jobs.refresh_market_snapshots import run_market_snapshot_refresh
from jobs.sync_instruments import run_instrument_sync
from services.startup_remediation import run_startup_gap_remediation
from services.traceability import get_raw_event_detail, normalized_links_for_raw_event, replay_readiness_summary
from services.validate_and_store import (
    UnsupportedPayloadTypeError,
    supported_payload_types,
    validate_and_store,
    validate_payload,
)
from storage.db import connection_scope, transaction_scope
from storage.repositories.backtest import BacktestRunRepository
from storage.repositories.ops import DataGapRepository, DataQualityCheckRepository, IngestionJobRepository
from strategy import UnknownStrategyError


class ApiRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidatePayloadRequest(ApiRequestModel):
    payload_type: str
    payload: dict[str, Any]


class InstrumentSyncRequest(ApiRequestModel):
    exchange_code: str = "binance"


class BarBackfillRequest(ApiRequestModel):
    exchange_code: str = "binance"
    symbol: str
    unified_symbol: str
    interval: str = "1m"
    start_time: datetime
    end_time: datetime


class MarketSnapshotRefreshRequest(ApiRequestModel):
    exchange_code: str = "binance"
    symbol: str
    unified_symbol: str
    funding_start_time: datetime | None = None
    funding_end_time: datetime | None = None
    history_start_time: datetime | None = None
    history_end_time: datetime | None = None
    open_interest_period: str = "5m"
    price_interval: str = "1m"


class MarketSnapshotRemediationRequest(ApiRequestModel):
    exchange_code: str = "binance"
    symbol: str
    unified_symbol: str
    datasets: list[str] | None = None
    observed_at: datetime | None = None
    lookback_hours: int = 24
    open_interest_period: str = "5m"
    price_interval: str = "1m"


class Phase4QualityRunRequest(ApiRequestModel):
    exchange_code: str = "binance"
    unified_symbol: str
    gap_start_time: datetime
    gap_end_time: datetime
    observed_at: datetime | None = None
    raw_event_channel: str | None = None


class BacktestCompareSetRequest(ApiRequestModel):
    run_ids: list[int]
    benchmark_run_id: int | None = None
    compare_name: str | None = None

    @model_validator(mode="after")
    def validate_compare_request(self) -> "BacktestCompareSetRequest":
        self.run_ids = list(dict.fromkeys(self.run_ids))
        if len(self.run_ids) < 2:
            raise ValueError("compare request requires at least two unique run_ids")
        if self.benchmark_run_id is not None and self.benchmark_run_id not in self.run_ids:
            raise ValueError("benchmark_run_id must be included in run_ids")
        return self


class BacktestRunStartRequest(BacktestRunConfig):
    persist_signals: bool = True


TData = TypeVar("TData")


class CurrentActor(BaseModel):
    user_id: str
    user_name: str
    role: str
    auth_mode: str


class ApiMeta(BaseModel):
    request_id: str
    timestamp: str
    current_actor: CurrentActor | None = None


class AppHealthResource(BaseModel):
    status: str
    checked_at: str


class SystemHealthData(BaseModel):
    app: AppHealthResource


class PayloadTypesResource(BaseModel):
    payload_types: list[str]


class JobActionResource(BaseModel):
    job_id: int
    status: str


class IngestionJobDetailResource(BaseModel):
    job_id: int
    service_name: str
    data_type: str
    status: str
    exchange_code: str | None = None
    unified_symbol: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    records_expected: int | None = None
    records_written: int | None = None
    error_message: str | None = None
    metadata_json: dict[str, Any] | None = None
    summary: dict[str, Any] | None = None
    diffs: list[dict[str, Any]] | None = None


class RecordsResource(BaseModel):
    records: list[dict[str, Any]]


class WsStatusResource(BaseModel):
    streams: list[dict[str, Any]]


class QualitySummaryResource(BaseModel):
    total_checks: int
    passed_checks: int
    failed_checks: int
    severe_checks: int
    latest_only: bool = False


class RawEventDetailResource(BaseModel):
    raw_event_id: int
    exchange_code: str
    unified_symbol: str | None = None
    channel: str
    event_type: str | None = None
    event_time: str | None = None
    ingest_time: str
    source_message_id: str | None = None
    payload_json: dict[str, Any]


class NormalizedLinksResource(BaseModel):
    raw_event_id: int
    links: list[dict[str, str]]


class ReplayReadinessResource(BaseModel):
    raw_coverage_status: str
    normalized_coverage_status: str
    retained_streams: list[str]
    known_gaps: int
    retention_policy: dict[str, str]
    replay_ready_datasets: dict[str, bool]


class DiagnosticFlagResource(BaseModel):
    code: str
    severity: str
    message: str
    related_count: int | None = None


class BacktestRunIntegrityResource(BaseModel):
    run_status: str
    start_time: str
    end_time: str
    timepoints_observed: int
    expected_timepoints: int | None = None
    missing_timepoints: int


class BacktestStrategyActivityResource(BaseModel):
    signal_count: int
    entry_signals: int
    exit_signals: int
    reduce_signals: int
    reverse_signals: int
    rebalance_signals: int


class BacktestExecutionSummaryResource(BaseModel):
    simulated_order_count: int
    simulated_fill_count: int
    expired_order_count: int
    unlinked_order_count: int
    blocked_intent_count: int = 0
    fill_rate_pct: str | None = None


class BacktestPnlSummaryResource(BaseModel):
    total_return: str | None = None
    max_drawdown: str | None = None
    turnover: str | None = None
    fee_cost: str | None = None
    slippage_cost: str | None = None


class BacktestDiagnosticsSummaryResource(BaseModel):
    run_id: int
    diagnostic_status: str
    has_errors: bool
    has_warnings: bool
    error_count: int
    warning_count: int
    run_integrity: BacktestRunIntegrityResource
    strategy_activity: BacktestStrategyActivityResource
    execution_summary: BacktestExecutionSummaryResource
    pnl_summary: BacktestPnlSummaryResource
    diagnostic_flags: list[DiagnosticFlagResource]


class BacktestPeriodBreakdownEntryResource(BaseModel):
    period_type: str
    period_start: str
    period_end: str
    start_equity: str
    end_equity: str
    total_return: str
    max_drawdown: str
    turnover: str
    fee_cost: str
    slippage_cost: str
    signal_count: int
    fill_count: int


class BacktestPeriodBreakdownResource(BaseModel):
    run_id: int
    period_type: str
    entries: list[BacktestPeriodBreakdownEntryResource]


class ArtifactReferenceResource(BaseModel):
    artifact_type: str
    status: str
    record_count: int | None = None
    description: str | None = None


class BacktestArtifactBundleResource(BaseModel):
    run_id: int
    artifacts: list[ArtifactReferenceResource]


class BacktestComparedRunResource(BaseModel):
    run_id: int
    run_name: str
    strategy_code: str
    strategy_version: str
    account_code: str | None = None
    environment: str | None = None
    status: str
    start_time: str
    end_time: str
    universe: list[str]
    diagnostic_status: str | None = None
    total_return: str | None = None
    annualized_return: str | None = None
    max_drawdown: str | None = None
    turnover: str | None = None
    win_rate: str | None = None
    fee_cost: str | None = None
    slippage_cost: str | None = None


class ComparisonAssumptionValueResource(BaseModel):
    run_id: int
    value: Any


class BacktestAssumptionDiffResource(BaseModel):
    field_name: str
    distinct_value_count: int
    values_by_run: list[ComparisonAssumptionValueResource]


class BacktestBenchmarkDeltaResource(BaseModel):
    run_id: int
    benchmark_run_id: int
    total_return_delta: str | None = None
    annualized_return_delta: str | None = None
    max_drawdown_delta: str | None = None
    turnover_delta: str | None = None
    win_rate_delta: str | None = None


class BacktestComparisonFlagResource(BaseModel):
    code: str
    severity: str
    message: str


class BacktestCompareSetResource(BaseModel):
    compare_name: str | None = None
    run_ids: list[int]
    benchmark_run_id: int | None = None
    persisted: bool
    available_period_types: list[str]
    compared_runs: list[BacktestComparedRunResource]
    assumption_diffs: list[BacktestAssumptionDiffResource]
    benchmark_deltas: list[BacktestBenchmarkDeltaResource]
    comparison_flags: list[BacktestComparisonFlagResource]


class BacktestRunListItemResource(BaseModel):
    run_id: int
    run_name: str
    strategy_code: str
    strategy_version: str
    account_code: str | None = None
    environment: str | None = None
    status: str
    start_time: str
    end_time: str
    created_at: str
    universe: list[str]
    bar_interval: str | None = None
    initial_cash: str | None = None
    total_return: str | None = None
    annualized_return: str | None = None
    max_drawdown: str | None = None
    turnover: str | None = None
    win_rate: str | None = None
    fee_cost: str | None = None
    slippage_cost: str | None = None


class BacktestRunListResource(BaseModel):
    runs: list[BacktestRunListItemResource]


class BacktestRiskPolicyResource(BaseModel):
    policy_code: str
    display_name: str
    description: str
    market_scope: str
    risk_policy: dict[str, Any]


class BacktestRiskPolicyListResource(BaseModel):
    risk_policies: list[BacktestRiskPolicyResource]


class BacktestAssumptionBundleResource(BaseModel):
    assumption_bundle_code: str
    assumption_bundle_version: str
    display_name: str
    description: str
    market_scope: str
    assumptions: dict[str, Any]


class BacktestAssumptionBundleListResource(BaseModel):
    assumption_bundles: list[BacktestAssumptionBundleResource]


class BacktestRunDetailResource(BaseModel):
    run_id: int
    run_name: str
    strategy_code: str
    strategy_version: str
    account_code: str | None = None
    environment: str | None = None
    session_code: str | None = None
    status: str
    start_time: str
    end_time: str
    created_at: str
    universe: list[str]
    market_data_version: str | None = None
    fee_model_version: str | None = None
    slippage_model_version: str | None = None
    fill_model_version: str | None = None
    latency_model_version: str | None = None
    feature_input_version: str | None = None
    benchmark_set_code: str | None = None
    assumption_bundle_code: str | None = None
    assumption_bundle_version: str | None = None
    bar_interval: str | None = None
    initial_cash: str | None = None
    netting_mode: str | None = None
    total_return: str | None = None
    annualized_return: str | None = None
    max_drawdown: str | None = None
    turnover: str | None = None
    win_rate: str | None = None
    fee_cost: str | None = None
    slippage_cost: str | None = None
    strategy_params_json: dict[str, Any]
    execution_policy: dict[str, Any]
    protection_policy: dict[str, Any]
    session_risk_policy: dict[str, Any]
    risk_overrides_json: dict[str, Any]
    risk_policy: dict[str, Any]
    assumption_bundle_json: dict[str, Any]
    assumption_overrides_json: dict[str, Any]
    effective_assumptions_json: dict[str, Any]
    run_metadata_json: dict[str, Any]
    runtime_metadata_json: dict[str, Any]
    session_metadata_json: dict[str, Any]


class BacktestOrderRecordResource(BaseModel):
    sim_order_id: int
    signal_id: int | None = None
    unified_symbol: str
    order_time: str
    side: str
    order_type: str
    price: str | None = None
    qty: str
    status: str


class BacktestOrderRecordsResource(BaseModel):
    run_id: int
    orders: list[BacktestOrderRecordResource]


class BacktestFillRecordResource(BaseModel):
    sim_fill_id: int
    sim_order_id: int
    unified_symbol: str
    fill_time: str
    price: str
    qty: str
    fee: str | None = None
    slippage_cost: str | None = None


class BacktestFillRecordsResource(BaseModel):
    run_id: int
    fills: list[BacktestFillRecordResource]


class BacktestSignalRecordResource(BaseModel):
    signal_id: int
    unified_symbol: str
    signal_time: str
    signal_type: str
    direction: str | None = None
    target_qty: str | None = None
    target_notional: str | None = None
    reason_code: str | None = None


class BacktestSignalRecordsResource(BaseModel):
    run_id: int
    signals: list[BacktestSignalRecordResource]


class BacktestTimeseriesPointResource(BaseModel):
    ts: str
    equity: str
    cash: str | None = None
    gross_exposure: str | None = None
    net_exposure: str | None = None
    drawdown: str | None = None


class BacktestTimeseriesResource(BaseModel):
    run_id: int
    points: list[BacktestTimeseriesPointResource]


class ValidationResultResource(BaseModel):
    valid: bool
    model_name: str
    normalized_payload: dict[str, Any]
    validation_errors: list[Any]


class ValidateAndStoreResultResource(BaseModel):
    valid: bool
    stored: bool
    entity_type: str
    model_name: str
    record_locator: str
    normalized_payload: dict[str, Any]
    duplicate_handled: bool


class SuccessEnvelope(BaseModel, Generic[TData]):
    success: bool = True
    data: TData
    error: None = None
    meta: ApiMeta


class ErrorEnvelope(BaseModel):
    success: bool = False
    data: None = None
    error: dict[str, Any]
    meta: ApiMeta


def _meta(actor: CurrentActor | None = None) -> ApiMeta:
    return ApiMeta(
        request_id=f"req_{uuid4().hex[:12]}",
        timestamp=datetime.now(timezone.utc).isoformat(),
        current_actor=actor,
    )


def resolve_current_actor(authorization: str | None = None) -> CurrentActor:
    if not authorization:
        if settings.app_env == "local" and settings.enable_local_auth_bypass:
            return CurrentActor(
                user_id=settings.local_auth_user_id,
                user_name=settings.local_auth_user_name,
                role=settings.local_auth_role,
                auth_mode="local_bypass",
            )
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "missing Authorization header", "details": {}},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Authorization header must use Bearer token", "details": {}},
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "bearer token is empty", "details": {}},
        )

    token_parts = token.split(":", 2)
    role = "operator"
    user_id = "token-user"
    user_name = "Bearer User"
    if len(token_parts) >= 1 and token_parts[0]:
        role = token_parts[0]
    if len(token_parts) >= 2 and token_parts[1]:
        user_id = token_parts[1]
        user_name = token_parts[1]
    if len(token_parts) == 3 and token_parts[2]:
        user_name = token_parts[2]

    return CurrentActor(
        user_id=user_id,
        user_name=user_name,
        role=role,
        auth_mode="bearer",
    )


def require_actor(
    authorization: str | None = None,
    *,
    allowed_roles: set[str] | None = None,
) -> CurrentActor:
    actor = resolve_current_actor(authorization)
    if allowed_roles is not None and actor.role not in allowed_roles:
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN", "message": "actor role does not allow this action", "details": {}},
        )
    return actor


def _records_response(query: str, params: tuple[Any, ...], actor: CurrentActor) -> SuccessEnvelope[RecordsResource]:
    with connection_scope() as connection:
        rows = connection.exec_driver_sql(query, params).mappings().all()
    normalized_records = [_normalize_mapping(dict(row)) for row in rows]
    return SuccessEnvelope[RecordsResource](
        data=RecordsResource(records=normalized_records),
        meta=_meta(actor),
    )


def _normalize_mapping(row: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        normalized[key] = value.isoformat() if isinstance(value, datetime) else value
    return normalized


def _stringify_decimal(value: Any) -> str | None:
    return None if value is None else str(value)


def _build_backtest_risk_policy_resource(entry) -> BacktestRiskPolicyResource:
    return BacktestRiskPolicyResource(
        policy_code=entry.policy_code,
        display_name=entry.display_name,
        description=entry.description,
        market_scope=entry.market_scope,
        risk_policy=entry.risk_policy.model_dump(mode="json", by_alias=True),
    )


def _build_backtest_assumption_bundle_resource(entry) -> BacktestAssumptionBundleResource:
    return BacktestAssumptionBundleResource(
        assumption_bundle_code=entry.assumption_bundle_code,
        assumption_bundle_version=entry.assumption_bundle_version,
        display_name=entry.display_name,
        description=entry.description,
        market_scope=entry.market_scope,
        assumptions=entry.assumptions.model_dump(mode="json", by_alias=True),
    )


def _build_backtest_run_resource(
    run_row: dict[str, Any],
    summary_row: dict[str, Any] | None = None,
) -> BacktestRunDetailResource:
    params_json = run_row.get("params_json") or {}
    effective_assumptions = dict(params_json.get("effective_assumptions") or {})
    summary = summary_row or {}
    return BacktestRunDetailResource(
        run_id=int(run_row["run_id"]),
        run_name=str(run_row["run_name"] or ""),
        strategy_code=str(run_row["strategy_code"]),
        strategy_version=str(run_row["strategy_version"]),
        account_code=run_row.get("account_code"),
        environment=params_json.get("environment"),
        session_code=params_json.get("session_code"),
        status=str(run_row["status"]),
        start_time=run_row["start_time"].isoformat(),
        end_time=run_row["end_time"].isoformat(),
        created_at=run_row["created_at"].isoformat(),
        universe=list(run_row.get("universe_json") or []),
        market_data_version=run_row.get("market_data_version"),
        fee_model_version=run_row.get("fee_model_version"),
        slippage_model_version=run_row.get("slippage_model_version"),
        fill_model_version=effective_assumptions.get("fill_model_version"),
        latency_model_version=run_row.get("latency_model_version"),
        feature_input_version=effective_assumptions.get("feature_input_version"),
        benchmark_set_code=effective_assumptions.get("benchmark_set_code"),
        assumption_bundle_code=params_json.get("assumption_bundle_code"),
        assumption_bundle_version=params_json.get("assumption_bundle_version"),
        bar_interval=params_json.get("bar_interval"),
        initial_cash=_stringify_decimal(params_json.get("initial_cash")),
        netting_mode=params_json.get("netting_mode"),
        total_return=_stringify_decimal(summary.get("total_return")),
        annualized_return=_stringify_decimal(summary.get("annualized_return")),
        max_drawdown=_stringify_decimal(summary.get("max_drawdown")),
        turnover=_stringify_decimal(summary.get("turnover")),
        win_rate=_stringify_decimal(summary.get("win_rate")),
        fee_cost=_stringify_decimal(summary.get("fee_cost")),
        slippage_cost=_stringify_decimal(summary.get("slippage_cost")),
        strategy_params_json=dict(params_json.get("strategy_params") or {}),
        execution_policy=dict(params_json.get("execution_policy") or {}),
        protection_policy=dict(params_json.get("protection_policy") or {}),
        session_risk_policy=dict(params_json.get("session_risk_policy") or params_json.get("risk_policy") or {}),
        risk_overrides_json=dict(params_json.get("risk_overrides") or {}),
        risk_policy=dict(params_json.get("risk_policy") or {}),
        assumption_bundle_json=dict(params_json.get("assumption_bundle") or {}),
        assumption_overrides_json=dict(params_json.get("assumption_overrides") or {}),
        effective_assumptions_json=effective_assumptions,
        run_metadata_json=dict(params_json.get("run_metadata") or {}),
        runtime_metadata_json=dict(params_json.get("runtime_metadata") or {}),
        session_metadata_json=dict(params_json.get("session_metadata") or {}),
    )


def _build_backtest_run_list_item(run_row: dict[str, Any]) -> BacktestRunListItemResource:
    detail = _build_backtest_run_resource(run_row, run_row)
    return BacktestRunListItemResource(
        run_id=detail.run_id,
        run_name=detail.run_name,
        strategy_code=detail.strategy_code,
        strategy_version=detail.strategy_version,
        account_code=detail.account_code,
        environment=detail.environment,
        status=detail.status,
        start_time=detail.start_time,
        end_time=detail.end_time,
        created_at=detail.created_at,
        universe=detail.universe,
        bar_interval=detail.bar_interval,
        initial_cash=detail.initial_cash,
        total_return=detail.total_return,
        annualized_return=detail.annualized_return,
        max_drawdown=detail.max_drawdown,
        turnover=detail.turnover,
        win_rate=detail.win_rate,
        fee_cost=detail.fee_cost,
        slippage_cost=detail.slippage_cost,
    )


def _build_backtest_order_resource(record: dict[str, Any]) -> BacktestOrderRecordResource:
    return BacktestOrderRecordResource(
        sim_order_id=int(record["sim_order_id"]),
        signal_id=None if record.get("signal_id") is None else int(record["signal_id"]),
        unified_symbol=str(record["unified_symbol"]),
        order_time=record["order_time"].isoformat(),
        side=str(record["side"]),
        order_type=str(record["order_type"]),
        price=_stringify_decimal(record.get("price")),
        qty=str(record["qty"]),
        status=str(record["status"]),
    )


def _build_backtest_fill_resource(record: dict[str, Any]) -> BacktestFillRecordResource:
    return BacktestFillRecordResource(
        sim_fill_id=int(record["sim_fill_id"]),
        sim_order_id=int(record["sim_order_id"]),
        unified_symbol=str(record["unified_symbol"]),
        fill_time=record["fill_time"].isoformat(),
        price=str(record["price"]),
        qty=str(record["qty"]),
        fee=_stringify_decimal(record.get("fee")),
        slippage_cost=_stringify_decimal(record.get("slippage_cost")),
    )


def _build_backtest_signal_resource(record: dict[str, Any]) -> BacktestSignalRecordResource:
    return BacktestSignalRecordResource(
        signal_id=int(record["signal_id"]),
        unified_symbol=str(record["unified_symbol"]),
        signal_time=record["signal_time"].isoformat(),
        signal_type=str(record["signal_type"]),
        direction=record.get("direction"),
        target_qty=_stringify_decimal(record.get("target_qty")),
        target_notional=_stringify_decimal(record.get("target_notional")),
        reason_code=record.get("reason_code"),
    )


def _build_backtest_timeseries_point_resource(record: dict[str, Any]) -> BacktestTimeseriesPointResource:
    return BacktestTimeseriesPointResource(
        ts=record["ts"].isoformat(),
        equity=str(record["equity"]),
        cash=_stringify_decimal(record.get("cash")),
        gross_exposure=_stringify_decimal(record.get("gross_exposure")),
        net_exposure=_stringify_decimal(record.get("net_exposure")),
        drawdown=_stringify_decimal(record.get("drawdown")),
    )


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if settings.app_env != "local" or not settings.enable_startup_gap_remediation:
            yield
            return
        run_startup_gap_remediation()
        yield

    app = FastAPI(title="Crypto Trading Data Miner API", version="0.1.0", lifespan=lifespan)
    monitoring_dir = Path(__file__).resolve().parents[2] / "frontend" / "monitoring"
    if monitoring_dir.exists():
        app.mount("/monitoring", StaticFiles(directory=monitoring_dir, html=True), name="monitoring")

    @app.get("/api/v1/system/health")
    def system_health() -> SuccessEnvelope[SystemHealthData]:
        return SuccessEnvelope[SystemHealthData](
            data=SystemHealthData(
                app=AppHealthResource(
                    status="ok",
                    checked_at=datetime.now(timezone.utc).isoformat(),
                )
            ),
            meta=_meta(),
        )

    @app.get("/api/v1/models/payload-types")
    def model_payload_types(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[PayloadTypesResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        return SuccessEnvelope[PayloadTypesResource](
            data=PayloadTypesResource(payload_types=supported_payload_types()),
            meta=_meta(actor),
        )

    @app.post("/api/v1/models/validate")
    def model_validate(
        request: ValidatePayloadRequest,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[ValidationResultResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        try:
            model_name, normalized_payload = validate_payload(request.payload_type, request.payload)
        except UnsupportedPayloadTypeError as exc:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc), "details": {}}) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "payload validation failed",
                    "details": exc.errors(),
                },
            ) from exc

        return SuccessEnvelope[ValidationResultResource](
            data=ValidationResultResource(
                valid=True,
                model_name=model_name,
                normalized_payload=normalized_payload,
                validation_errors=[],
            ),
            meta=_meta(actor),
        )

    @app.post("/api/v1/models/validate-and-store")
    def model_validate_and_store(
        request: ValidatePayloadRequest,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[ValidateAndStoreResultResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        try:
            with transaction_scope() as connection:
                result = validate_and_store(connection, request.payload_type, request.payload)
        except UnsupportedPayloadTypeError as exc:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": str(exc), "details": {}}) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "payload validation failed",
                    "details": exc.errors(),
                },
            ) from exc

        return SuccessEnvelope[ValidateAndStoreResultResource](
            data=ValidateAndStoreResultResource(
                valid=True,
                stored=result.stored,
                entity_type=result.payload_type,
                model_name=result.model_name,
                record_locator=result.record_locator,
                normalized_payload=result.normalized_payload,
                duplicate_handled=True,
            ),
            meta=_meta(actor),
        )

    @app.post("/api/v1/ingestion/jobs/instrument-sync")
    def trigger_instrument_sync(
        request: InstrumentSyncRequest,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[JobActionResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        result = run_instrument_sync(exchange_code=request.exchange_code, requested_by=actor.user_id)
        return SuccessEnvelope[JobActionResource](
            data=JobActionResource(job_id=result.ingestion_job_id, status=result.status),
            meta=_meta(actor),
        )

    @app.post("/api/v1/ingestion/jobs/bar-backfill")
    def trigger_bar_backfill(
        request: BarBackfillRequest,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[JobActionResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        result = run_bar_backfill(
            symbol=request.symbol,
            unified_symbol=request.unified_symbol,
            interval=request.interval,
            start_time=request.start_time,
            end_time=request.end_time,
            exchange_code=request.exchange_code,
            requested_by=actor.user_id,
        )
        return SuccessEnvelope[JobActionResource](
            data=JobActionResource(job_id=result.ingestion_job_id, status=result.status),
            meta=_meta(actor),
        )

    @app.post("/api/v1/ingestion/jobs/market-snapshot-refresh")
    def trigger_market_snapshot_refresh(
        request: MarketSnapshotRefreshRequest,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[JobActionResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        result = run_market_snapshot_refresh(
            symbol=request.symbol,
            unified_symbol=request.unified_symbol,
            exchange_code=request.exchange_code,
            requested_by=actor.user_id,
            funding_start_time=request.funding_start_time,
            funding_end_time=request.funding_end_time,
            history_start_time=request.history_start_time,
            history_end_time=request.history_end_time,
            open_interest_period=request.open_interest_period,
            price_interval=request.price_interval,
        )
        return SuccessEnvelope[JobActionResource](
            data=JobActionResource(job_id=result.ingestion_job_id, status=result.status),
            meta=_meta(actor),
        )

    @app.post("/api/v1/ingestion/jobs/market-snapshot-remediation")
    def trigger_market_snapshot_remediation(
        request: MarketSnapshotRemediationRequest,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[JobActionResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        result = run_market_snapshot_remediation(
            symbol=request.symbol,
            unified_symbol=request.unified_symbol,
            exchange_code=request.exchange_code,
            requested_by=actor.user_id,
            datasets=request.datasets,
            observed_at=request.observed_at,
            lookback_hours=request.lookback_hours,
            open_interest_period=request.open_interest_period,
            price_interval=request.price_interval,
        )
        return SuccessEnvelope[JobActionResource](
            data=JobActionResource(job_id=result.ingestion_job_id, status=result.status),
            meta=_meta(actor),
        )

    @app.get("/api/v1/ingestion/jobs")
    def ingestion_jobs(
        status: str | None = None,
        service_name: str | None = None,
        data_type: str | None = None,
        exchange_code: str | None = None,
        unified_symbol: str | None = None,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            records = IngestionJobRepository().list_recent(
                connection,
                limit=limit,
                status=status,
                service_name=service_name,
                data_type=data_type,
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
            )
        return SuccessEnvelope[RecordsResource](
            data=RecordsResource(records=[_normalize_mapping(record) for record in records]),
            meta=_meta(actor),
        )

    @app.get("/api/v1/ingestion/jobs/{job_id}")
    def ingestion_job_detail(
        job_id: int,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[IngestionJobDetailResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            job = IngestionJobRepository().get_job(connection, job_id)
        if job is None:
            raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"job not found: {job_id}", "details": {}})
        return SuccessEnvelope[IngestionJobDetailResource](
            data=IngestionJobDetailResource(
                job_id=job["job_id"],
                service_name=job["service_name"],
                data_type=job["data_type"],
                status=job["status"],
                exchange_code=job.get("exchange_code"),
                unified_symbol=job.get("unified_symbol"),
                started_at=job["started_at"].isoformat() if job.get("started_at") else None,
                finished_at=job["finished_at"].isoformat() if job.get("finished_at") else None,
                records_expected=job.get("records_expected"),
                records_written=job.get("records_written"),
                error_message=job.get("error_message"),
                metadata_json=job.get("metadata_json"),
                summary=(job.get("metadata_json") or {}).get("summary"),
                diffs=(job.get("metadata_json") or {}).get("diffs"),
            ),
            meta=_meta(actor),
        )

    @app.post("/api/v1/quality/run")
    def trigger_quality_run(
        request: Phase4QualityRunRequest,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[JobActionResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        result = run_phase4_quality_suite(
            exchange_code=request.exchange_code,
            unified_symbol=request.unified_symbol,
            gap_start_time=request.gap_start_time,
            gap_end_time=request.gap_end_time,
            observed_at=request.observed_at,
            raw_event_channel=request.raw_event_channel,
        )
        synthetic_job_id = int(datetime.now(timezone.utc).timestamp())
        return SuccessEnvelope[JobActionResource](
            data=JobActionResource(job_id=synthetic_job_id, status=f"checks:{result.checks_written}/gaps:{result.gaps_written}"),
            meta=_meta(actor),
        )

    @app.get("/api/v1/quality/checks")
    def quality_checks(
        data_type: str | None = None,
        status: str | None = None,
        severity: str | None = None,
        exchange_code: str | None = None,
        unified_symbol: str | None = None,
        latest_only: bool = False,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            records = DataQualityCheckRepository().list_recent(
                connection,
                limit=limit,
                data_type=data_type,
                status=status,
                severity=severity,
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
                latest_only=latest_only,
            )
        return SuccessEnvelope[RecordsResource](
            data=RecordsResource(records=[_normalize_mapping(record) for record in records]),
            meta=_meta(actor),
        )

    @app.get("/api/v1/quality/summary")
    def quality_summary(
        data_type: str | None = None,
        exchange_code: str | None = None,
        unified_symbol: str | None = None,
        latest_only: bool = False,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[QualitySummaryResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            summary = DataQualityCheckRepository().summary(
                connection,
                data_type=data_type,
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
                latest_only=latest_only,
            )
        return SuccessEnvelope[QualitySummaryResource](
            data=QualitySummaryResource(**summary, latest_only=latest_only),
            meta=_meta(actor),
        )

    @app.get("/api/v1/quality/gaps")
    def quality_gaps(
        data_type: str | None = None,
        status: str | None = None,
        exchange_code: str | None = None,
        unified_symbol: str | None = None,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            records = DataGapRepository().list_recent(
                connection,
                limit=limit,
                data_type=data_type,
                status=status,
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
            )
        return SuccessEnvelope[RecordsResource](
            data=RecordsResource(records=[_normalize_mapping(record) for record in records]),
            meta=_meta(actor),
        )

    @app.get("/api/v1/market/bars")
    def market_bars(
        unified_symbol: str,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        return _records_response(
            """
            select instrument.unified_symbol, bar_time, open, high, low, close, volume, quote_volume, trade_count
            from md.bars_1m bar
            join ref.instruments instrument on instrument.instrument_id = bar.instrument_id
            where instrument.unified_symbol = %s
            order by bar_time desc
            limit %s
            """,
            (unified_symbol, limit),
            actor,
        )

    @app.get("/api/v1/market/trades")
    def market_trades(
        unified_symbol: str,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        return _records_response(
            """
            select instrument.unified_symbol, exchange_trade_id, event_time, ingest_time, price, qty, aggressor_side
            from md.trades trade
            join ref.instruments instrument on instrument.instrument_id = trade.instrument_id
            where instrument.unified_symbol = %s
            order by event_time desc
            limit %s
            """,
            (unified_symbol, limit),
            actor,
        )

    @app.get("/api/v1/market/funding-rates")
    def market_funding_rates(
        unified_symbol: str,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        return _records_response(
            """
            select instrument.unified_symbol, funding_time, funding_rate, mark_price, index_price
            from md.funding_rates rate
            join ref.instruments instrument on instrument.instrument_id = rate.instrument_id
            where instrument.unified_symbol = %s
            order by funding_time desc
            limit %s
            """,
            (unified_symbol, limit),
            actor,
        )

    @app.get("/api/v1/market/open-interest")
    def market_open_interest(
        unified_symbol: str,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        return _records_response(
            """
            select instrument.unified_symbol, ts, open_interest
            from md.open_interest oi
            join ref.instruments instrument on instrument.instrument_id = oi.instrument_id
            where instrument.unified_symbol = %s
            order by ts desc
            limit %s
            """,
            (unified_symbol, limit),
            actor,
        )

    @app.get("/api/v1/market/mark-prices")
    def market_mark_prices(
        unified_symbol: str,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        return _records_response(
            """
            select instrument.unified_symbol, ts, mark_price, funding_basis_bps, ingest_time
            from md.mark_prices price
            join ref.instruments instrument on instrument.instrument_id = price.instrument_id
            where instrument.unified_symbol = %s
            order by ts desc
            limit %s
            """,
            (unified_symbol, limit),
            actor,
        )

    @app.get("/api/v1/market/index-prices")
    def market_index_prices(
        unified_symbol: str,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        return _records_response(
            """
            select instrument.unified_symbol, ts, index_price, ingest_time
            from md.index_prices price
            join ref.instruments instrument on instrument.instrument_id = price.instrument_id
            where instrument.unified_symbol = %s
            order by ts desc
            limit %s
            """,
            (unified_symbol, limit),
            actor,
        )

    @app.get("/api/v1/market/liquidations")
    def market_liquidations(
        unified_symbol: str,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        return _records_response(
            """
            select instrument.unified_symbol, event_time, ingest_time, side, price, qty, notional, source
            from md.liquidations liq
            join ref.instruments instrument on instrument.instrument_id = liq.instrument_id
            where instrument.unified_symbol = %s
            order by event_time desc
            limit %s
            """,
            (unified_symbol, limit),
            actor,
        )

    @app.get("/api/v1/market/raw-events")
    def market_raw_events(
        exchange_code: str | None = None,
        channel: str | None = None,
        event_type: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        filters = []
        params: list[Any] = []
        if exchange_code is not None:
            filters.append("exchange.exchange_code = %s")
            params.append(exchange_code)
        if channel is not None:
            filters.append("raw.channel = %s")
            params.append(channel)
        if event_type is not None:
            filters.append("raw.event_type = %s")
            params.append(event_type)
        if start_time is not None:
            filters.append("raw.event_time >= %s")
            params.append(start_time)
        if end_time is not None:
            filters.append("raw.event_time <= %s")
            params.append(end_time)
        where_clause = f"where {' and '.join(filters)}" if filters else ""
        return _records_response(
            f"""
            select raw.raw_event_id, exchange.exchange_code, instrument.unified_symbol, raw.channel, raw.event_type, raw.event_time, raw.ingest_time, raw.source_message_id, raw.payload_json
            from md.raw_market_events raw
            join ref.exchanges exchange on exchange.exchange_id = raw.exchange_id
            left join ref.instruments instrument on instrument.instrument_id = raw.instrument_id
            {where_clause}
            order by raw.ingest_time desc
            limit %s
            """,
            tuple([*params, limit]),
            actor,
        )

    @app.get("/api/v1/market/raw-events/{raw_event_id}")
    def market_raw_event_detail(
        raw_event_id: int,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RawEventDetailResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            record = get_raw_event_detail(connection, raw_event_id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"raw event not found: {raw_event_id}", "details": {}},
            )
        return SuccessEnvelope[RawEventDetailResource](
            data=RawEventDetailResource(**_normalize_mapping(record)),
            meta=_meta(actor),
        )

    @app.get("/api/v1/market/raw-events/{raw_event_id}/normalized-links")
    def market_raw_event_links(
        raw_event_id: int,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[NormalizedLinksResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            raw_event = get_raw_event_detail(connection, raw_event_id)
            if raw_event is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "NOT_FOUND", "message": f"raw event not found: {raw_event_id}", "details": {}},
                )
            links = normalized_links_for_raw_event(connection, raw_event_id)
        return SuccessEnvelope[NormalizedLinksResource](
            data=NormalizedLinksResource(
                raw_event_id=raw_event_id,
                links=[
                    {
                        "resource_type": link.resource_type,
                        "record_locator": link.record_locator,
                        "match_strategy": link.match_strategy,
                    }
                    for link in links
                ],
            ),
            meta=_meta(actor),
        )

    @app.post("/api/v1/backtests/runs")
    def create_backtest_run(
        request: BacktestRunStartRequest,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestRunDetailResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        try:
            runner = BacktestRunnerSkeleton(request)
            with transaction_scope() as connection:
                persisted = runner.load_run_and_persist(connection, persist_signals=request.persist_signals)
                run_repository = BacktestRunRepository()
                run_row = run_repository.get_run(connection, persisted.run_id)
                summary_row = run_repository.get_performance_summary(connection, run_id=persisted.run_id)
        except UnknownStrategyError as exc:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": str(exc), "details": {}},
            ) from exc
        except UnknownRiskPolicyError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                    "details": {"field": "risk_policy_code"},
                },
            ) from exc
        except UnknownAssumptionBundleError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": str(exc),
                    "details": {"field": "assumption_bundle_code"},
                },
            ) from exc
        except ValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "backtest request validation failed",
                    "details": exc.errors(),
                },
            ) from exc

        assert run_row is not None
        return SuccessEnvelope[BacktestRunDetailResource](
            data=_build_backtest_run_resource(run_row, summary_row),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/assumption-bundles")
    def list_backtest_assumption_bundles(
        market_scope: str | None = None,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestAssumptionBundleListResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        entries = build_default_assumption_bundle_registry().list_entries()
        if market_scope is not None:
            entries = [
                entry
                for entry in entries
                if entry.market_scope == market_scope or entry.market_scope == "shared"
            ]
        return SuccessEnvelope[BacktestAssumptionBundleListResource](
            data=BacktestAssumptionBundleListResource(
                assumption_bundles=[_build_backtest_assumption_bundle_resource(entry) for entry in entries]
            ),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/risk-policies")
    def list_backtest_risk_policies(
        market_scope: str | None = None,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestRiskPolicyListResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        entries = build_default_risk_policy_registry().list_entries()
        if market_scope is not None:
            entries = [
                entry
                for entry in entries
                if entry.market_scope == market_scope or entry.market_scope == "shared"
            ]
        return SuccessEnvelope[BacktestRiskPolicyListResource](
            data=BacktestRiskPolicyListResource(
                risk_policies=[_build_backtest_risk_policy_resource(entry) for entry in entries]
            ),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/runs")
    def list_backtest_runs(
        strategy_code: str | None = None,
        strategy_version: str | None = None,
        account_code: str | None = None,
        unified_symbol: str | None = None,
        status: str | None = None,
        limit: int = 20,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestRunListResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            rows = BacktestRunRepository().list_runs(
                connection,
                strategy_code=strategy_code,
                strategy_version=strategy_version,
                account_code=account_code,
                unified_symbol=unified_symbol,
                status=status,
                limit=limit,
            )
        return SuccessEnvelope[BacktestRunListResource](
            data=BacktestRunListResource(runs=[_build_backtest_run_list_item(row) for row in rows]),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/runs/{run_id}")
    def get_backtest_run(
        run_id: int,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestRunDetailResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            repository = BacktestRunRepository()
            run_row = repository.get_run(connection, run_id)
            summary_row = repository.get_performance_summary(connection, run_id=run_id)
        if run_row is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"backtest run not found: {run_id}", "details": {}},
            )
        return SuccessEnvelope[BacktestRunDetailResource](
            data=_build_backtest_run_resource(run_row, summary_row),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/runs/{run_id}/orders")
    def backtest_run_orders(
        run_id: int,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestOrderRecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            repository = BacktestRunRepository()
            run_row = repository.get_run(connection, run_id)
            if run_row is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "NOT_FOUND", "message": f"backtest run not found: {run_id}", "details": {}},
                )
            records = repository.list_order_records(connection, run_id=run_id, limit=limit)
        return SuccessEnvelope[BacktestOrderRecordsResource](
            data=BacktestOrderRecordsResource(
                run_id=run_id,
                orders=[_build_backtest_order_resource(record) for record in records],
            ),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/runs/{run_id}/fills")
    def backtest_run_fills(
        run_id: int,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestFillRecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            repository = BacktestRunRepository()
            run_row = repository.get_run(connection, run_id)
            if run_row is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "NOT_FOUND", "message": f"backtest run not found: {run_id}", "details": {}},
                )
            records = repository.list_fill_records(connection, run_id=run_id, limit=limit)
        return SuccessEnvelope[BacktestFillRecordsResource](
            data=BacktestFillRecordsResource(
                run_id=run_id,
                fills=[_build_backtest_fill_resource(record) for record in records],
            ),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/runs/{run_id}/timeseries")
    def backtest_run_timeseries(
        run_id: int,
        limit: int = 200,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestTimeseriesResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            repository = BacktestRunRepository()
            run_row = repository.get_run(connection, run_id)
            if run_row is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "NOT_FOUND", "message": f"backtest run not found: {run_id}", "details": {}},
                )
            records = repository.list_timeseries(connection, run_id=run_id, limit=limit)
        return SuccessEnvelope[BacktestTimeseriesResource](
            data=BacktestTimeseriesResource(
                run_id=run_id,
                points=[_build_backtest_timeseries_point_resource(record) for record in records],
            ),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/runs/{run_id}/signals")
    def backtest_run_signals(
        run_id: int,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestSignalRecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            repository = BacktestRunRepository()
            run_row = repository.get_run(connection, run_id)
            if run_row is None:
                raise HTTPException(
                    status_code=404,
                    detail={"code": "NOT_FOUND", "message": f"backtest run not found: {run_id}", "details": {}},
                )
            records = repository.list_signal_records(connection, run_id=run_id, limit=limit)
        return SuccessEnvelope[BacktestSignalRecordsResource](
            data=BacktestSignalRecordsResource(
                run_id=run_id,
                signals=[_build_backtest_signal_resource(record) for record in records],
            ),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/runs/{run_id}/diagnostics")
    def backtest_run_diagnostics(
        run_id: int,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestDiagnosticsSummaryResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            summary = BacktestDiagnosticsProjector().build_summary(connection, run_id)
        if summary is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"backtest run not found: {run_id}", "details": {}},
            )
        return SuccessEnvelope[BacktestDiagnosticsSummaryResource](
            data=BacktestDiagnosticsSummaryResource(
                run_id=summary.run_id,
                diagnostic_status=summary.diagnostic_status,
                has_errors=summary.has_errors,
                has_warnings=summary.has_warnings,
                error_count=summary.error_count,
                warning_count=summary.warning_count,
                run_integrity=BacktestRunIntegrityResource(
                    run_status=summary.run_integrity.run_status,
                    start_time=summary.run_integrity.start_time.isoformat(),
                    end_time=summary.run_integrity.end_time.isoformat(),
                    timepoints_observed=summary.run_integrity.timepoints_observed,
                    expected_timepoints=summary.run_integrity.expected_timepoints,
                    missing_timepoints=summary.run_integrity.missing_timepoints,
                ),
                strategy_activity=BacktestStrategyActivityResource(
                    signal_count=summary.strategy_activity.signal_count,
                    entry_signals=summary.strategy_activity.entry_signals,
                    exit_signals=summary.strategy_activity.exit_signals,
                    reduce_signals=summary.strategy_activity.reduce_signals,
                    reverse_signals=summary.strategy_activity.reverse_signals,
                    rebalance_signals=summary.strategy_activity.rebalance_signals,
                ),
                execution_summary=BacktestExecutionSummaryResource(
                    simulated_order_count=summary.execution_summary.simulated_order_count,
                    simulated_fill_count=summary.execution_summary.simulated_fill_count,
                    expired_order_count=summary.execution_summary.expired_order_count,
                    unlinked_order_count=summary.execution_summary.unlinked_order_count,
                    blocked_intent_count=summary.execution_summary.blocked_intent_count,
                    fill_rate_pct=summary.execution_summary.fill_rate_pct,
                ),
                pnl_summary=BacktestPnlSummaryResource(
                    total_return=summary.pnl_summary.total_return,
                    max_drawdown=summary.pnl_summary.max_drawdown,
                    turnover=summary.pnl_summary.turnover,
                    fee_cost=summary.pnl_summary.fee_cost,
                    slippage_cost=summary.pnl_summary.slippage_cost,
                ),
                diagnostic_flags=[
                    DiagnosticFlagResource(
                        code=flag.code,
                        severity=flag.severity,
                        message=flag.message,
                        related_count=flag.related_count,
                    )
                    for flag in summary.diagnostic_flags
                ],
            ),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/runs/{run_id}/period-breakdown")
    def backtest_period_breakdown(
        run_id: int,
        period_type: str = "month",
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestPeriodBreakdownResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        if period_type not in {"year", "quarter", "month"}:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "VALIDATION_ERROR",
                    "message": "period_type must be one of year, quarter, or month",
                    "details": {"period_type": period_type},
                },
            )
        with connection_scope() as connection:
            entries = BacktestPeriodBreakdownProjector().build(connection, run_id=run_id, period_type=period_type)
        if entries is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"backtest run not found: {run_id}", "details": {}},
            )
        return SuccessEnvelope[BacktestPeriodBreakdownResource](
            data=BacktestPeriodBreakdownResource(
                run_id=run_id,
                period_type=period_type,
                entries=[
                    BacktestPeriodBreakdownEntryResource(
                        period_type=entry.period_type,
                        period_start=entry.period_start.isoformat(),
                        period_end=entry.period_end.isoformat(),
                        start_equity=str(entry.start_equity),
                        end_equity=str(entry.end_equity),
                        total_return=str(entry.total_return),
                        max_drawdown=str(entry.max_drawdown),
                        turnover=str(entry.turnover),
                        fee_cost=str(entry.fee_cost),
                        slippage_cost=str(entry.slippage_cost),
                        signal_count=entry.signal_count,
                        fill_count=entry.fill_count,
                    )
                    for entry in entries
                ],
            ),
            meta=_meta(actor),
        )

    @app.get("/api/v1/backtests/runs/{run_id}/artifacts")
    def backtest_artifact_bundle(
        run_id: int,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestArtifactBundleResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            artifact_bundle = BacktestArtifactCatalogProjector().build(connection, run_id=run_id)
        if artifact_bundle is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "NOT_FOUND", "message": f"backtest run not found: {run_id}", "details": {}},
            )
        return SuccessEnvelope[BacktestArtifactBundleResource](
            data=BacktestArtifactBundleResource(
                run_id=artifact_bundle.run_id,
                artifacts=[
                    ArtifactReferenceResource(
                        artifact_type=artifact.artifact_type,
                        status=artifact.status,
                        record_count=artifact.record_count,
                        description=artifact.description,
                    )
                    for artifact in artifact_bundle.artifacts
                ],
            ),
            meta=_meta(actor),
        )

    @app.post("/api/v1/backtests/compare-sets")
    def create_backtest_compare_set(
        request: BacktestCompareSetRequest,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[BacktestCompareSetResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        try:
            with connection_scope() as connection:
                compare_set = BacktestCompareProjector().build(
                    connection,
                    run_ids=request.run_ids,
                    compare_name=request.compare_name,
                    benchmark_run_id=request.benchmark_run_id,
                )
        except BacktestCompareValidationError as exc:
            raise HTTPException(
                status_code=422,
                detail={"code": "VALIDATION_ERROR", "message": str(exc), "details": {}},
            ) from exc
        except BacktestCompareNotFoundError as exc:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "NOT_FOUND",
                    "message": str(exc),
                    "details": {"missing_run_ids": exc.missing_run_ids},
                },
            ) from exc

        return SuccessEnvelope[BacktestCompareSetResource](
            data=BacktestCompareSetResource(
                compare_name=compare_set.compare_name,
                run_ids=compare_set.run_ids,
                benchmark_run_id=compare_set.benchmark_run_id,
                persisted=compare_set.persisted,
                available_period_types=compare_set.available_period_types,
                compared_runs=[
                    BacktestComparedRunResource(
                        run_id=run.run_id,
                        run_name=run.run_name,
                        strategy_code=run.strategy_code,
                        strategy_version=run.strategy_version,
                        account_code=run.account_code,
                        environment=run.environment,
                        status=run.status,
                        start_time=run.start_time.isoformat(),
                        end_time=run.end_time.isoformat(),
                        universe=run.universe,
                        diagnostic_status=run.diagnostic_status,
                        total_return=None if run.total_return is None else str(run.total_return),
                        annualized_return=None if run.annualized_return is None else str(run.annualized_return),
                        max_drawdown=None if run.max_drawdown is None else str(run.max_drawdown),
                        turnover=None if run.turnover is None else str(run.turnover),
                        win_rate=None if run.win_rate is None else str(run.win_rate),
                        fee_cost=None if run.fee_cost is None else str(run.fee_cost),
                        slippage_cost=None if run.slippage_cost is None else str(run.slippage_cost),
                    )
                    for run in compare_set.compared_runs
                ],
                assumption_diffs=[
                    BacktestAssumptionDiffResource(
                        field_name=diff.field_name,
                        distinct_value_count=diff.distinct_value_count,
                        values_by_run=[
                            ComparisonAssumptionValueResource(run_id=value.run_id, value=value.value)
                            for value in diff.values_by_run
                        ],
                    )
                    for diff in compare_set.assumption_diffs
                ],
                benchmark_deltas=[
                    BacktestBenchmarkDeltaResource(
                        run_id=delta.run_id,
                        benchmark_run_id=delta.benchmark_run_id,
                        total_return_delta=None if delta.total_return_delta is None else str(delta.total_return_delta),
                        annualized_return_delta=None if delta.annualized_return_delta is None else str(delta.annualized_return_delta),
                        max_drawdown_delta=None if delta.max_drawdown_delta is None else str(delta.max_drawdown_delta),
                        turnover_delta=None if delta.turnover_delta is None else str(delta.turnover_delta),
                        win_rate_delta=None if delta.win_rate_delta is None else str(delta.win_rate_delta),
                    )
                    for delta in compare_set.benchmark_deltas
                ],
                comparison_flags=[
                    BacktestComparisonFlagResource(
                        code=flag.code,
                        severity=flag.severity,
                        message=flag.message,
                    )
                    for flag in compare_set.comparison_flags
                ],
            ),
            meta=_meta(actor),
        )

    @app.get("/api/v1/replay/readiness")
    def replay_readiness(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[ReplayReadinessResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            summary = replay_readiness_summary(connection)
        return SuccessEnvelope[ReplayReadinessResource](
            data=ReplayReadinessResource(**summary),
            meta=_meta(actor),
        )

    @app.get("/api/v1/streams/ws-events")
    def ws_events(
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        return _records_response(
            """
            select
                event.ws_event_id,
                event.service_name,
                exchange.exchange_code,
                event.channel,
                event.event_time,
                event.event_type,
                event.connection_id,
                event.detail_json
            from ops.ws_connection_events event
            left join ref.exchanges exchange on exchange.exchange_id = event.exchange_id
            order by event.event_time desc
            limit %s
            """,
            (limit,),
            actor,
        )

    @app.get("/api/v1/streams/ws-status")
    def ws_status(
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[WsStatusResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            rows = connection.exec_driver_sql(
                """
                with ranked as (
                    select
                        event.service_name,
                        exchange.exchange_code,
                        event.channel,
                        event.event_type,
                        event.event_time,
                        row_number() over (
                            partition by event.service_name, coalesce(exchange.exchange_code, ''), coalesce(event.channel, '')
                            order by event.event_time desc
                        ) as rn
                    from ops.ws_connection_events event
                    left join ref.exchanges exchange on exchange.exchange_id = event.exchange_id
                )
                select service_name, exchange_code, channel, event_type as connection_status, event_time as last_message_time
                from ranked
                where rn = 1
                order by service_name, exchange_code, channel
                """
            ).mappings().all()
        return SuccessEnvelope[WsStatusResource](
            data=WsStatusResource(
                streams=[
                    {
                        **dict(row),
                        "last_message_time": row["last_message_time"].isoformat() if row.get("last_message_time") else None,
                    }
                    for row in rows
                ]
            ),
            meta=_meta(actor),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_, exc: HTTPException) -> JSONResponse:
        payload = ErrorEnvelope(
            error=exc.detail if isinstance(exc.detail, dict) else {
                "code": "INTERNAL_ERROR",
                "message": str(exc.detail),
                "details": {},
            },
            meta=_meta(),
        )
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    return app


app = create_app()
