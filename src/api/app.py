from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, ValidationError
from fastapi.responses import JSONResponse

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


class SuccessEnvelope(BaseModel):
    success: bool = True
    data: dict[str, Any]
    error: None = None
    meta: dict[str, Any]


class ErrorEnvelope(BaseModel):
    success: bool = False
    data: None = None
    error: dict[str, Any]
    meta: dict[str, Any]


def _meta() -> dict[str, Any]:
    return {
        "request_id": f"req_{uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def create_app() -> FastAPI:
    app = FastAPI(title="Crypto Trading Data Miner API", version="0.1.0")

    @app.get("/api/v1/system/health")
    def system_health() -> SuccessEnvelope:
        return SuccessEnvelope(
            data={
                "app": {
                    "status": "ok",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                }
            },
            meta=_meta(),
        )

    @app.get("/api/v1/models/payload-types")
    def model_payload_types() -> SuccessEnvelope:
        return SuccessEnvelope(
            data={"payload_types": supported_payload_types()},
            meta=_meta(),
        )

    @app.post("/api/v1/models/validate")
    def model_validate(request: ValidatePayloadRequest) -> SuccessEnvelope:
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

        return SuccessEnvelope(
            data={
                "valid": True,
                "model_name": model_name,
                "normalized_payload": normalized_payload,
                "validation_errors": [],
            },
            meta=_meta(),
        )

    @app.post("/api/v1/models/validate-and-store")
    def model_validate_and_store(request: ValidatePayloadRequest) -> SuccessEnvelope:
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

        return SuccessEnvelope(
            data={
                "valid": True,
                "stored": result.stored,
                "entity_type": result.payload_type,
                "model_name": result.model_name,
                "record_locator": result.record_locator,
                "normalized_payload": result.normalized_payload,
                "duplicate_handled": True,
            },
            meta=_meta(),
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
