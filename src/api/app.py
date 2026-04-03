from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Generic, TypeVar
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, ValidationError
from fastapi.responses import JSONResponse

from config import settings
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
from storage.repositories.ops import DataGapRepository, DataQualityCheckRepository, IngestionJobRepository


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
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[QualitySummaryResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        with connection_scope() as connection:
            summary = DataQualityCheckRepository().summary(
                connection,
                data_type=data_type,
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
            )
        return SuccessEnvelope[QualitySummaryResource](
            data=QualitySummaryResource(**summary),
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
