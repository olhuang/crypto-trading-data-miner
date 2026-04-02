from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Any, Generic, TypeVar
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from fastapi.responses import JSONResponse

from config import settings
from services.validate_and_store import (
    UnsupportedPayloadTypeError,
    supported_payload_types,
    validate_and_store,
    validate_payload,
)
from storage.db import transaction_scope


class ApiRequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ValidatePayloadRequest(ApiRequestModel):
    payload_type: str
    payload: dict[str, Any]


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
