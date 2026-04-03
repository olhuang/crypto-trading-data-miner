from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sys
from types import SimpleNamespace
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
    BacktestCompareSetRequest,
    BacktestRunStartRequest,
    BarBackfillRequest,
    InstrumentSyncRequest,
    MarketSnapshotRemediationRequest,
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
        cls.market_remediation_endpoint = _resolve_route(cls.app, "/api/v1/ingestion/jobs/market-snapshot-remediation", "POST")
        cls.jobs_list_endpoint = _resolve_route(cls.app, "/api/v1/ingestion/jobs", "GET")
        cls.job_detail_endpoint = _resolve_route(cls.app, "/api/v1/ingestion/jobs/{job_id}", "GET")
        cls.backtest_runs_create_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs", "POST")
        cls.backtest_runs_list_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs", "GET")
        cls.backtest_run_detail_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}", "GET")
        cls.backtest_diagnostics_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/diagnostics", "GET")
        cls.backtest_period_breakdown_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/period-breakdown", "GET")
        cls.backtest_artifacts_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/artifacts", "GET")
        cls.backtest_compare_sets_endpoint = _resolve_route(cls.app, "/api/v1/backtests/compare-sets", "POST")

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
        original_remediation = app_module.run_market_snapshot_remediation

        class _Result:
            def __init__(self, job_id: int, status: str) -> None:
                self.ingestion_job_id = job_id
                self.status = status

        try:
            app_module.run_instrument_sync = lambda **_: _Result(101, "succeeded")
            app_module.run_bar_backfill = lambda **_: _Result(202, "succeeded")
            app_module.run_market_snapshot_refresh = lambda **_: _Result(303, "succeeded")
            app_module.run_market_snapshot_remediation = lambda **_: _Result(404, "succeeded")

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
            remediation_response = self.__class__.market_remediation_endpoint(
                MarketSnapshotRemediationRequest(
                    exchange_code="binance",
                    symbol="BTCUSDT",
                    unified_symbol="BTCUSDT_PERP",
                )
            )

            self.assertEqual(instrument_response.data.job_id, 101)
            self.assertEqual(backfill_response.data.job_id, 202)
            self.assertEqual(refresh_response.data.job_id, 303)
            self.assertEqual(remediation_response.data.job_id, 404)
        finally:
            app_module.run_instrument_sync = original_sync
            app_module.run_bar_backfill = original_backfill
            app_module.run_market_snapshot_refresh = original_refresh
            app_module.run_market_snapshot_remediation = original_remediation

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

    def test_jobs_list_endpoint_supports_filters(self) -> None:
        with transaction_scope() as connection:
            repo = IngestionJobRepository()
            sync_job_id = repo.create_job(
                connection,
                service_name="instrument_sync",
                data_type="instrument_metadata",
                status="succeeded",
                requested_by="u_123",
                exchange_code="binance",
                metadata_json={"job_type": "instrument_sync"},
            )
            remediation_job_id = repo.create_job(
                connection,
                service_name="market_snapshot_remediation",
                data_type="funding_open_interest_mark_index",
                status="failed_terminal",
                requested_by="u_123",
                exchange_code="binance",
                unified_symbol="BTCUSDT_PERP",
                metadata_json={"job_type": "market_snapshot_remediation"},
            )

        filtered_response = self.__class__.jobs_list_endpoint(
            status="failed_terminal",
            service_name="market_snapshot_remediation",
            exchange_code="binance",
            unified_symbol="BTCUSDT_PERP",
            limit=20,
        )

        self.assertTrue(filtered_response.success)
        returned_ids = {record["job_id"] for record in filtered_response.data.records}
        self.assertIn(remediation_job_id, returned_ids)
        self.assertNotIn(sync_job_id, returned_ids)

    def test_backtest_diagnostics_endpoint_returns_typed_summary(self) -> None:
        original_projector = app_module.BacktestDiagnosticsProjector

        class StubProjector:
            def build_summary(self, connection, run_id: int):
                return SimpleNamespace(
                    run_id=run_id,
                    diagnostic_status="warning",
                    has_errors=False,
                    has_warnings=True,
                    error_count=0,
                    warning_count=1,
                    run_integrity=SimpleNamespace(
                        run_status="finished",
                        start_time=datetime.fromisoformat("2026-04-01T00:00:00+00:00"),
                        end_time=datetime.fromisoformat("2026-04-02T00:00:00+00:00"),
                        timepoints_observed=100,
                        expected_timepoints=120,
                        missing_timepoints=20,
                    ),
                    strategy_activity=SimpleNamespace(
                        signal_count=12,
                        entry_signals=4,
                        exit_signals=4,
                        reduce_signals=2,
                        reverse_signals=1,
                        rebalance_signals=1,
                    ),
                    execution_summary=SimpleNamespace(
                        simulated_order_count=12,
                        simulated_fill_count=10,
                        expired_order_count=2,
                        unlinked_order_count=0,
                        fill_rate_pct="0.8333",
                    ),
                    pnl_summary=SimpleNamespace(
                        total_return="0.1234",
                        max_drawdown="0.0456",
                        turnover="1.2345",
                        fee_cost="12.34",
                        slippage_cost="5.67",
                    ),
                    diagnostic_flags=[
                        SimpleNamespace(
                            code="expired_orders_present",
                            severity="warning",
                            message="one or more simulated orders expired without filling",
                            related_count=2,
                        )
                    ],
                )

        app_module.BacktestDiagnosticsProjector = StubProjector
        try:
            response = self.__class__.backtest_diagnostics_endpoint(501, "Bearer developer:u_123:Alice")
        finally:
            app_module.BacktestDiagnosticsProjector = original_projector

        self.assertTrue(response.success)
        self.assertEqual(response.data.run_id, 501)
        self.assertEqual(response.data.diagnostic_status, "warning")
        self.assertEqual(response.data.execution_summary.expired_order_count, 2)
        self.assertEqual(response.data.diagnostic_flags[0].code, "expired_orders_present")

    def test_backtest_runs_endpoint_supports_create_list_and_detail(self) -> None:
        original_runner = app_module.BacktestRunnerSkeleton
        original_repository = app_module.BacktestRunRepository

        run_row = {
            "run_id": 601,
            "strategy_code": "btc_momentum",
            "strategy_version": "v1.0.0",
            "account_code": "paper_main",
            "run_name": "btc_ui_demo",
            "universe_json": ["BTCUSDT_PERP"],
            "start_time": datetime.fromisoformat("2026-03-01T00:00:00+00:00"),
            "end_time": datetime.fromisoformat("2026-03-31T00:00:00+00:00"),
            "market_data_version": "md.bars_1m",
            "fee_model_version": "ref_fee_schedule_v1",
            "slippage_model_version": "fixed_bps_v1",
            "latency_model_version": "bars_next_open_v1",
            "params_json": {
                "session_code": "bt_ui_demo",
                "environment": "backtest",
                "netting_mode": "isolated_strategy_session",
                "bar_interval": "1m",
                "initial_cash": "100000",
                "strategy_params": {"short_window": 5, "long_window": 20, "target_qty": "1"},
                "run_metadata": {"source": "ui"},
                "session_metadata": {"slice": "research"},
                "execution_policy": {"policy_code": "default"},
                "protection_policy": {"policy_code": "default"},
            },
            "status": "finished",
            "created_at": datetime.fromisoformat("2026-04-03T09:30:00+00:00"),
            "total_return": Decimal("0.12"),
            "annualized_return": Decimal("0.48"),
            "max_drawdown": Decimal("0.04"),
            "turnover": Decimal("1.20"),
            "win_rate": Decimal("0.58"),
            "fee_cost": Decimal("12.34"),
            "slippage_cost": Decimal("5.67"),
        }

        class StubRunner:
            def __init__(self, run_config):
                self.run_config = run_config

            def load_run_and_persist(self, connection, *, persist_signals=True):
                return SimpleNamespace(run_id=601, loop_result=SimpleNamespace())

        class StubRepository:
            def get_run(self, connection, run_id: int):
                return dict(run_row) if run_id == 601 else None

            def get_performance_summary(self, connection, *, run_id: int):
                if run_id != 601:
                    return None
                return {
                    "total_return": Decimal("0.12"),
                    "annualized_return": Decimal("0.48"),
                    "max_drawdown": Decimal("0.04"),
                    "turnover": Decimal("1.20"),
                    "win_rate": Decimal("0.58"),
                    "fee_cost": Decimal("12.34"),
                    "slippage_cost": Decimal("5.67"),
                }

            def list_runs(self, connection, **kwargs):
                return [dict(run_row)]

        app_module.BacktestRunnerSkeleton = StubRunner
        app_module.BacktestRunRepository = StubRepository
        try:
            create_response = self.__class__.backtest_runs_create_endpoint(
                BacktestRunStartRequest.model_validate(
                    {
                        "run_name": "btc_ui_demo",
                        "session": {
                            "session_code": "bt_ui_demo",
                            "environment": "backtest",
                            "account_code": "paper_main",
                            "strategy_code": "btc_momentum",
                            "strategy_version": "v1.0.0",
                            "exchange_code": "binance",
                            "universe": ["BTCUSDT_PERP"],
                        },
                        "start_time": "2026-03-01T00:00:00Z",
                        "end_time": "2026-03-31T00:00:00Z",
                        "initial_cash": "100000",
                        "strategy_params": {"short_window": 5, "long_window": 20, "target_qty": "1"},
                    }
                ),
                "Bearer developer:u_123:Alice",
            )
            list_response = self.__class__.backtest_runs_list_endpoint(
                strategy_code="btc_momentum",
                status="finished",
                limit=20,
                authorization="Bearer developer:u_123:Alice",
            )
            detail_response = self.__class__.backtest_run_detail_endpoint(601, "Bearer developer:u_123:Alice")
        finally:
            app_module.BacktestRunnerSkeleton = original_runner
            app_module.BacktestRunRepository = original_repository

        self.assertTrue(create_response.success)
        self.assertEqual(create_response.data.run_id, 601)
        self.assertEqual(create_response.data.strategy_params_json["short_window"], 5)

        self.assertTrue(list_response.success)
        self.assertEqual(len(list_response.data.runs), 1)
        self.assertEqual(list_response.data.runs[0].run_id, 601)
        self.assertEqual(list_response.data.runs[0].total_return, "0.12")

        self.assertTrue(detail_response.success)
        self.assertEqual(detail_response.data.run_id, 601)
        self.assertEqual(detail_response.data.session_code, "bt_ui_demo")
        self.assertEqual(detail_response.data.run_metadata_json["source"], "ui")

    def test_backtest_period_breakdown_endpoint_returns_entries(self) -> None:
        original_projector = app_module.BacktestPeriodBreakdownProjector

        class StubProjector:
            def build(self, connection, *, run_id: int, period_type: str):
                return [
                    SimpleNamespace(
                        period_type=period_type,
                        period_start=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                        period_end=datetime.fromisoformat("2026-01-31T23:59:00+00:00"),
                        start_equity=Decimal("100000"),
                        end_equity=Decimal("101000"),
                        total_return=Decimal("0.01"),
                        max_drawdown=Decimal("0.02"),
                        turnover=Decimal("1.2"),
                        fee_cost=Decimal("12.3"),
                        slippage_cost=Decimal("4.5"),
                        signal_count=10,
                        fill_count=8,
                    )
                ]

        app_module.BacktestPeriodBreakdownProjector = StubProjector
        try:
            response = self.__class__.backtest_period_breakdown_endpoint(
                501,
                "month",
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.BacktestPeriodBreakdownProjector = original_projector

        self.assertTrue(response.success)
        self.assertEqual(response.data.period_type, "month")
        self.assertEqual(response.data.entries[0].signal_count, 10)
        self.assertEqual(response.data.entries[0].total_return, "0.01")

    def test_backtest_artifacts_endpoint_returns_catalog(self) -> None:
        original_projector = app_module.BacktestArtifactCatalogProjector

        class StubProjector:
            def build(self, connection, *, run_id: int):
                return SimpleNamespace(
                    run_id=run_id,
                    artifacts=[
                        SimpleNamespace(
                            artifact_type="run_metadata",
                            status="available",
                            record_count=1,
                            description="canonical persisted run metadata and lineage baseline",
                        ),
                        SimpleNamespace(
                            artifact_type="period_breakdown",
                            status="available",
                            record_count=3,
                            description="derived year/quarter/month performance breakdown projections",
                        ),
                    ],
                )

        app_module.BacktestArtifactCatalogProjector = StubProjector
        try:
            response = self.__class__.backtest_artifacts_endpoint(501, "Bearer developer:u_123:Alice")
        finally:
            app_module.BacktestArtifactCatalogProjector = original_projector

        self.assertTrue(response.success)
        self.assertEqual(response.data.run_id, 501)
        self.assertEqual(response.data.artifacts[0].artifact_type, "run_metadata")
        self.assertEqual(response.data.artifacts[1].record_count, 3)

    def test_backtest_compare_sets_endpoint_returns_compare_projection(self) -> None:
        original_projector = app_module.BacktestCompareProjector

        class StubProjector:
            def build(self, connection, *, run_ids, compare_name=None, benchmark_run_id=None):
                return SimpleNamespace(
                    compare_name=compare_name,
                    run_ids=run_ids,
                    benchmark_run_id=benchmark_run_id,
                    persisted=False,
                    available_period_types=["year", "quarter", "month"],
                    compared_runs=[
                        SimpleNamespace(
                            run_id=501,
                            run_name="btc_compare_a",
                            strategy_code="btc_momentum",
                            strategy_version="v1.0.0",
                            account_code="paper_main",
                            environment="backtest",
                            status="finished",
                            start_time=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                            end_time=datetime.fromisoformat("2026-03-31T23:59:00+00:00"),
                            universe=["BTCUSDT_PERP"],
                            diagnostic_status="ok",
                            total_return=Decimal("0.10"),
                            annualized_return=Decimal("0.40"),
                            max_drawdown=Decimal("0.05"),
                            turnover=Decimal("1.20"),
                            win_rate=Decimal("0.55"),
                            fee_cost=Decimal("12.34"),
                            slippage_cost=Decimal("5.67"),
                        ),
                        SimpleNamespace(
                            run_id=502,
                            run_name="btc_compare_b",
                            strategy_code="btc_momentum",
                            strategy_version="v1.1.0",
                            account_code="paper_main",
                            environment="backtest",
                            status="finished",
                            start_time=datetime.fromisoformat("2026-01-01T00:00:00+00:00"),
                            end_time=datetime.fromisoformat("2026-03-31T23:59:00+00:00"),
                            universe=["BTCUSDT_PERP"],
                            diagnostic_status="warning",
                            total_return=Decimal("0.12"),
                            annualized_return=Decimal("0.48"),
                            max_drawdown=Decimal("0.04"),
                            turnover=Decimal("1.50"),
                            win_rate=Decimal("0.58"),
                            fee_cost=Decimal("15.00"),
                            slippage_cost=Decimal("7.00"),
                        ),
                    ],
                    assumption_diffs=[
                        SimpleNamespace(
                            field_name="strategy_version",
                            distinct_value_count=2,
                            values_by_run=[
                                SimpleNamespace(run_id=501, value="v1.0.0"),
                                SimpleNamespace(run_id=502, value="v1.1.0"),
                            ],
                        )
                    ],
                    benchmark_deltas=[
                        SimpleNamespace(
                            run_id=502,
                            benchmark_run_id=501,
                            total_return_delta=Decimal("0.02"),
                            annualized_return_delta=Decimal("0.08"),
                            max_drawdown_delta=Decimal("-0.01"),
                            turnover_delta=Decimal("0.30"),
                            win_rate_delta=Decimal("0.03"),
                        )
                    ],
                    comparison_flags=[
                        SimpleNamespace(
                            code="diagnostic_warnings_present",
                            severity="warning",
                            message="one or more selected runs already carry diagnostics warnings or errors",
                        )
                    ],
                )

        app_module.BacktestCompareProjector = StubProjector
        try:
            response = self.__class__.backtest_compare_sets_endpoint(
                BacktestCompareSetRequest(run_ids=[501, 502], benchmark_run_id=501, compare_name="btc_compare_set"),
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.BacktestCompareProjector = original_projector

        self.assertTrue(response.success)
        self.assertEqual(response.data.compare_name, "btc_compare_set")
        self.assertEqual(response.data.run_ids, [501, 502])
        self.assertEqual(response.data.benchmark_deltas[0].run_id, 502)
        self.assertEqual(response.data.assumption_diffs[0].field_name, "strategy_version")
        self.assertEqual(response.data.comparison_flags[0].code, "diagnostic_warnings_present")


if __name__ == "__main__":
    unittest.main()
