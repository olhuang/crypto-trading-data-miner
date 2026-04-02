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

from config import settings
from api.app import ValidatePayloadRequest, create_app, require_actor, resolve_current_actor


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

    def test_system_health_returns_success_envelope(self) -> None:
        response = self.__class__.health_endpoint()

        self.assertTrue(response.success)
        self.assertEqual(response.data["app"]["status"], "ok")
        self.assertIn("request_id", response.meta)

    def test_payload_types_includes_trade_event(self) -> None:
        response = self.__class__.payload_types_endpoint()

        self.assertTrue(response.success)
        self.assertIn("trade_event", response.data["payload_types"])
        self.assertIn("order_request", response.data["payload_types"])
        self.assertEqual(response.meta["current_actor"]["auth_mode"], "local_bypass")

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
        self.assertTrue(response.data["valid"])
        self.assertEqual(response.data["model_name"], "TradeEvent")
        self.assertEqual(response.data["normalized_payload"]["payload_json"], {"source": "api_validate"})
        self.assertEqual(response.meta["current_actor"]["role"], "admin")

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
        self.assertTrue(response.data["stored"])
        self.assertEqual(response.data["entity_type"], "trade_event")
        self.assertEqual(
            response.data["record_locator"],
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
        self.assertEqual(response.meta["current_actor"]["auth_mode"], "bearer")
        self.assertEqual(response.meta["current_actor"]["role"], "developer")
        self.assertEqual(response.meta["current_actor"]["user_id"], "u_123")

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


if __name__ == "__main__":
    unittest.main()
