from __future__ import annotations

from pathlib import Path
import sys
import unittest
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi import HTTPException
from fastapi.routing import APIRoute

import api.app as app_module
from config import settings
from api.app import (
    BarBackfillRequest,
    InstrumentSyncRequest,
    MarketSnapshotRefreshRequest,
    ValidatePayloadRequest,
    create_app,
    require_actor,
    resolve_current_actor,
)
from storage.db import transaction_scope
from storage.repositories.ops import IngestionJobRepository


def _resolve_route(app, path: str, method: str):
    for route in app.routes:
        if isinstance(route, APIRoute) and route.path == path and method in route.methods:
            return route.endpoint
    raise AssertionError(f"route not found: {method} {path}")


class ModelsApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_app_env = settings.app_env
        self.original_bypass = settings.enable_local_auth_bypass

    def tearDown(self) -> None:
        settings.app_env = self.original_app_env
        settings.enable_local_auth_bypass = self.original_bypass

    @classmethod
    def setUpClass(cls) -> None:
        cls.app = create_app()
        cls.health_endpoint = _resolve_route(cls.app, "/api/v1/system/health", "GET")
        cls.payload_types_endpoint = _resolve_route(cls.app, "/api/v1/models/payload-types", "GET")
        cls.validate_endpoint = _resolve_route(cls.app, "/api/v1/models/validate", "POST")
        cls.validate_and_store_endpoint = _resolve_route(cls.app, "/api/v1/models/validate-and-store", "POST")
        cls.instrument_sync_endpoint = _resolve_route(cls.app, "/api/v1/ingestion/jobs/instrument-sync", "POST")
        cls.bar_backfill_endpoint = _resolve_route(cls.app, "/api/v1/ingestion/jobs/bar-backfill", "POST")
        cls.market_refresh_endpoint = _resolve_route(cls.app, "/api/v1/ingestion/jobs/market-snapshot-refresh", "POST")
        cls.job_detail_endpoint = _resolve_route(cls.app, "/api/v1/ingestion/jobs/{job_id}", "GET")

    def test_system_health_returns_success_envelope(self) -> None:
        response = self.__class__.health_endpoint()

        self.assertTrue(response.success)
        self.assertEqual(response.data.app.status, "ok")
        self.assertTrue(response.meta.request_id.startswith("req_"))

    def test_payload_types_includes_trade_event(self) -> None:
        response = self.__class__.payload_types_endpoint()

        self.assertTrue(response.success)
        self.assertIn("trade_event", response.data.payload_types)
        self.assertIn("order_request", response.data.payload_types)
        self.assertIn("mark_price", response.data.payload_types)
        self.assertIn("risk_limit", response.data.payload_types)
        self.assertEqual(response.meta.current_actor.auth_mode, "local_bypass")

    def test_validate_endpoint_normalizes_payload(self) -> None:
        request = ValidatePayloadRequest(
            payload_type="trade_event",
            payload={
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "exchange_trade_id": f"api_validate_{uuid4().hex[:10]}",
                "event_time": "2026-04-02T12:34:56Z",
                "ingest_time": "2026-04-02T12:34:57Z",
                "price": "84250.12",
                "qty": "0.01",
                "raw_payload": {"source": "api_validate"},
            },
        )

        response = self.__class__.validate_endpoint(request)

        self.assertTrue(response.success)
        self.assertTrue(response.data.valid)
        self.assertEqual(response.data.model_name, "TradeEvent")
        self.assertEqual(response.data.normalized_payload["payload_json"], {"source": "api_validate"})
        self.assertEqual(response.meta.current_actor.role, "admin")

    def test_validate_endpoint_rejects_invalid_payload(self) -> None:
        request = ValidatePayloadRequest(
            payload_type="order_request",
            payload={
                "environment": "paper",
                "account_code": "paper_main",
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "client_order_id": f"api_invalid_{uuid4().hex[:10]}",
                "side": "buy",
                "order_type": "limit",
                "qty": "0.1",
            },
        )

        with self.assertRaises(HTTPException) as exc:
            self.__class__.validate_endpoint(request)

        self.assertEqual(exc.exception.status_code, 422)
        self.assertEqual(exc.exception.detail["code"], "VALIDATION_ERROR")

    def test_validate_and_store_endpoint_persists_trade_event(self) -> None:
        trade_id = f"api_store_{uuid4().hex[:10]}"
        request = ValidatePayloadRequest(
            payload_type="trade_event",
            payload={
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "exchange_trade_id": trade_id,
                "event_time": "2026-04-02T12:34:56Z",
                "ingest_time": "2026-04-02T12:34:57Z",
                "price": "84250.12",
                "qty": "0.01",
                "raw_payload": {"source": "api_store"},
            },
        )

        response = self.__class__.validate_and_store_endpoint(request)

        self.assertTrue(response.success)
        self.assertTrue(response.data.stored)
        self.assertEqual(response.data.entity_type, "trade_event")
        self.assertEqual(
            response.data.record_locator,
            f"binance:BTCUSDT_PERP:{trade_id}",
        )

    def test_non_local_requests_require_authorization_header(self) -> None:
        settings.app_env = "staging"
        settings.enable_local_auth_bypass = False

        with self.assertRaises(HTTPException) as exc:
            self.__class__.payload_types_endpoint()

        self.assertEqual(exc.exception.status_code, 401)
        self.assertEqual(exc.exception.detail["code"], "UNAUTHORIZED")

    def test_bearer_token_allows_protected_route_with_developer_role(self) -> None:
        settings.app_env = "staging"
        settings.enable_local_auth_bypass = False

        response = self.__class__.payload_types_endpoint("Bearer developer:u_123:Alice")

        self.assertTrue(response.success)
        self.assertEqual(response.meta.current_actor.auth_mode, "bearer")
        self.assertEqual(response.meta.current_actor.role, "developer")
        self.assertEqual(response.meta.current_actor.user_id, "u_123")

    def test_operator_role_is_forbidden_for_models_route(self) -> None:
        settings.app_env = "staging"
        settings.enable_local_auth_bypass = False

        with self.assertRaises(HTTPException) as exc:
            self.__class__.payload_types_endpoint("Bearer operator:u_456:Bob")

        self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(exc.exception.detail["code"], "FORBIDDEN")

    def test_auth_helpers_resolve_local_and_bearer_modes(self) -> None:
        settings.app_env = "local"
        settings.enable_local_auth_bypass = True
        local_actor = resolve_current_actor()
        self.assertEqual(local_actor.auth_mode, "local_bypass")

        bearer_actor = require_actor("Bearer admin:u_999:Root", allowed_roles={"admin"})
        self.assertEqual(bearer_actor.auth_mode, "bearer")
        self.assertEqual(bearer_actor.role, "admin")

    def test_ingestion_job_endpoints_return_job_acknowledgements(self) -> None:
        original_sync = app_module.run_instrument_sync
        original_backfill = app_module.run_bar_backfill
        original_refresh = app_module.run_market_snapshot_refresh

        class _Result:
            def __init__(self, job_id: int, status: str) -> None:
                self.ingestion_job_id = job_id
                self.status = status

        try:
            app_module.run_instrument_sync = lambda **_: _Result(101, "succeeded")
            app_module.run_bar_backfill = lambda **_: _Result(202, "succeeded")
            app_module.run_market_snapshot_refresh = lambda **_: _Result(303, "succeeded")

            instrument_response = self.__class__.instrument_sync_endpoint(InstrumentSyncRequest(exchange_code="binance"))
            backfill_response = self.__class__.bar_backfill_endpoint(
                BarBackfillRequest(
                    exchange_code="binance",
                    symbol="BTCUSDT",
                    unified_symbol="BTCUSDT_PERP",
                    start_time="2026-04-02T12:34:00Z",
                    end_time="2026-04-02T12:35:00Z",
                )
            )
            refresh_response = self.__class__.market_refresh_endpoint(
                MarketSnapshotRefreshRequest(
                    exchange_code="binance",
                    symbol="BTCUSDT",
                    unified_symbol="BTCUSDT_PERP",
                )
            )

            self.assertEqual(instrument_response.data.job_id, 101)
            self.assertEqual(backfill_response.data.job_id, 202)
            self.assertEqual(refresh_response.data.job_id, 303)
        finally:
            app_module.run_instrument_sync = original_sync
            app_module.run_bar_backfill = original_backfill
            app_module.run_market_snapshot_refresh = original_refresh

    def test_job_detail_endpoint_exposes_summary_and_diffs(self) -> None:
        with transaction_scope() as connection:
            repo = IngestionJobRepository()
            job_id = repo.create_job(
                connection,
                service_name="instrument_sync",
                data_type="instrument_metadata",
                status="running",
                requested_by="u_123",
                exchange_code="binance",
                metadata_json={"job_type": "instrument_sync"},
            )
            repo.finish_job(
                connection,
                job_id,
                status="succeeded",
                finished_at="2026-04-02T12:00:03Z",
                records_written=2,
                metadata_json={
                    "job_type": "instrument_sync",
                    "summary": {"instruments_seen": 2, "instruments_inserted": 1, "instruments_updated": 1, "instruments_unchanged": 0},
                    "diffs": [{"unified_symbol": "BTCUSDT_PERP", "change_type": "updated", "field_diffs": []}],
                },
            )

        response = self.__class__.job_detail_endpoint(job_id)

        self.assertTrue(response.success)
        self.assertEqual(response.data.job_id, job_id)
        self.assertEqual(response.data.summary["instruments_seen"], 2)
        self.assertEqual(response.data.diffs[0]["unified_symbol"], "BTCUSDT_PERP")


if __name__ == "__main__":
    unittest.main()
