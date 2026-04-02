from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Generic, TypeVar
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from fastapi.responses import JSONResponse

from config import settings
from jobs.backfill_bars import run_bar_backfill
from jobs.refresh_market_snapshots import run_market_snapshot_refresh
from jobs.sync_instruments import run_instrument_sync
from services.validate_and_store import (
    UnsupportedPayloadTypeError,
    supported_payload_types,
    validate_and_store,
    validate_payload,
)
from storage.db import connection_scope, transaction_scope
from storage.repositories.ops import IngestionJobRepository


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
    normalized_records: list[dict[str, Any]] = []
    for row in rows:
        record: dict[str, Any] = {}
        for key, value in dict(row).items():
            record[key] = value.isoformat() if isinstance(value, datetime) else value
        normalized_records.append(record)
    return SuccessEnvelope[RecordsResource](
        data=RecordsResource(records=normalized_records),
        meta=_meta(actor),
    )


def create_app() -> FastAPI:
    app = FastAPI(title="Crypto Trading Data Miner API", version="0.1.0")

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
        )
        return SuccessEnvelope[JobActionResource](
            data=JobActionResource(job_id=result.ingestion_job_id, status=result.status),
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
        channel: str | None = None,
        limit: int = 100,
        authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    ) -> SuccessEnvelope[RecordsResource]:
        actor = require_actor(authorization, allowed_roles={"developer", "admin"})
        if channel:
            query = """
                select raw_event_id, channel, event_type, event_time, ingest_time, source_message_id, payload_json
                from md.raw_market_events
                where channel = %s
                order by ingest_time desc
                limit %s
            """
            params = (channel, limit)
        else:
            query = """
                select raw_event_id, channel, event_type, event_time, ingest_time, source_message_id, payload_json
                from md.raw_market_events
                order by ingest_time desc
                limit %s
            """
            params = (limit,)
        return _records_response(query, params, actor)

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
