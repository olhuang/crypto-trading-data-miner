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
    CompareReviewNoteWriteRequest,
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
        cls.backtest_risk_policies_endpoint = _resolve_route(cls.app, "/api/v1/backtests/risk-policies", "GET")
        cls.backtest_assumption_bundles_endpoint = _resolve_route(cls.app, "/api/v1/backtests/assumption-bundles", "GET")
        cls.backtest_runs_list_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs", "GET")
        cls.backtest_run_detail_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}", "GET")
        cls.backtest_run_orders_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/orders", "GET")
        cls.backtest_run_fills_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/fills", "GET")
        cls.backtest_run_timeseries_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/timeseries", "GET")
        cls.backtest_run_signals_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/signals", "GET")
        cls.backtest_run_debug_traces_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/debug-traces", "GET")
        cls.backtest_diagnostics_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/diagnostics", "GET")
        cls.backtest_period_breakdown_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/period-breakdown", "GET")
        cls.backtest_artifacts_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/artifacts", "GET")
        cls.backtest_compare_sets_endpoint = _resolve_route(cls.app, "/api/v1/backtests/compare-sets", "POST")
        cls.backtest_compare_notes_list_endpoint = _resolve_route(cls.app, "/api/v1/backtests/compare-sets/{compare_set_id}/notes", "GET")
        cls.backtest_compare_notes_write_endpoint = _resolve_route(cls.app, "/api/v1/backtests/compare-sets/{compare_set_id}/notes", "POST")

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
                        blocked_intent_count=3,
                        fill_rate_pct="0.8333",
                    ),
                    risk_summary=SimpleNamespace(
                        blocked_intent_count=3,
                        block_counts_by_code={"max_drawdown_pct_breach": 2, "cooldown_active": 1},
                        outcome_counts_by_code={
                            "allowed": 9,
                            "max_drawdown_pct_breach": 2,
                            "cooldown_active": 1,
                        },
                        state_snapshot={
                            "policy_code": "perp_medium_v1",
                            "trading_timezone": "Asia/Taipei",
                            "peak_equity": "101000",
                            "daily_start_equity": "99500",
                            "active_trading_day": "2026-04-01",
                            "cooldown_bars_remaining": 0,
                        },
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
                      trace_anchors=[
                          SimpleNamespace(
                              source_kind="diagnostic_flag",
                              source_code="risk_blocks_present",
                              title="Latest blocked intent trace",
                              message="Latest trace row where a backtest risk guardrail blocked an execution intent.",
                              anchor_type="step",
                              debug_trace_id=8801,
                              step_index=321,
                              bar_time=datetime.fromisoformat("2026-04-01T10:00:00+00:00"),
                              unified_symbol="BTCUSDT_PERP",
                              related_count=3,
                              matched_block_code="max_drawdown_pct_breach",
                              bar_time_from=datetime.fromisoformat("2026-04-01T09:58:00+00:00"),
                              bar_time_to=datetime.fromisoformat("2026-04-01T10:02:00+00:00"),
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
        self.assertEqual(response.data.execution_summary.blocked_intent_count, 3)
        self.assertEqual(response.data.risk_summary.block_counts_by_code["max_drawdown_pct_breach"], 2)
        self.assertEqual(response.data.risk_summary.state_snapshot["policy_code"], "perp_medium_v1")
        self.assertEqual(response.data.risk_summary.state_snapshot["trading_timezone"], "Asia/Taipei")
        self.assertEqual(response.data.diagnostic_flags[0].code, "expired_orders_present")
        self.assertEqual(response.data.trace_anchors[0].source_code, "risk_blocks_present")
        self.assertEqual(response.data.trace_anchors[0].debug_trace_id, 8801)
        self.assertEqual(response.data.trace_anchors[0].matched_block_code, "max_drawdown_pct_breach")

    def test_backtest_risk_policies_endpoint_lists_named_registry_entries(self) -> None:
        response = self.__class__.backtest_risk_policies_endpoint(
            authorization="Bearer developer:u_123:Alice",
        )

        self.assertTrue(response.success)
        self.assertGreaterEqual(len(response.data.risk_policies), 3)
        policy_codes = [resource.policy_code for resource in response.data.risk_policies]
        self.assertIn("default", policy_codes)
        self.assertIn("perp_medium_v1", policy_codes)
        self.assertIn("spot_conservative_v1", policy_codes)

    def test_backtest_assumption_bundles_endpoint_lists_named_registry_entries(self) -> None:
        response = self.__class__.backtest_assumption_bundles_endpoint(
            authorization="Bearer developer:u_123:Alice",
        )

        self.assertTrue(response.success)
        self.assertGreaterEqual(len(response.data.assumption_bundles), 3)
        bundle_keys = {
            (resource.assumption_bundle_code, resource.assumption_bundle_version)
            for resource in response.data.assumption_bundles
        }
        self.assertIn(("baseline_perp_research", "v1"), bundle_keys)
        self.assertIn(("baseline_spot_research", "v1"), bundle_keys)
        self.assertIn(("stress_costs", "v1"), bundle_keys)

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
                "trading_timezone": "Asia/Taipei",
                "netting_mode": "isolated_strategy_session",
                "bar_interval": "1m",
                "initial_cash": "100000",
                "assumption_bundle_code": "baseline_perp_research",
                "assumption_bundle_version": "v1",
                "assumption_bundle": {
                    "assumption_bundle_code": "baseline_perp_research",
                    "assumption_bundle_version": "v1",
                    "market_data_version": "md.bars_1m",
                    "fee_model_version": "ref_fee_schedule_v1",
                    "slippage_model_version": "fixed_bps_v1",
                    "fill_model_version": "deterministic_bars_v1",
                    "latency_model_version": "bars_next_open_v1",
                    "feature_input_version": "bars_only_v1",
                    "benchmark_set_code": "btc_perp_baseline_v1",
                    "risk_policy": {"policy_code": "perp_medium_v1"},
                },
                "assumption_overrides": {},
                "effective_assumptions": {
                    "assumption_bundle_code": "baseline_perp_research",
                    "assumption_bundle_version": "v1",
                    "market_data_version": "md.bars_1m",
                    "fee_model_version": "ref_fee_schedule_v1",
                    "slippage_model_version": "fixed_bps_v1",
                    "fill_model_version": "deterministic_bars_v1",
                    "latency_model_version": "bars_next_open_v1",
                    "feature_input_version": "bars_only_v1",
                    "benchmark_set_code": "btc_perp_baseline_v1",
                    "risk_policy": {"policy_code": "perp_medium_v1"},
                },
                "strategy_params": {"short_window": 5, "long_window": 20, "target_qty": "1"},
                "run_metadata": {"source": "ui"},
                "runtime_metadata": {"risk_summary": {"blocked_intent_count": 1}},
                "session_metadata": {"slice": "research"},
                "execution_policy": {"policy_code": "default"},
                "protection_policy": {"policy_code": "default"},
                "session_risk_policy": {"policy_code": "perp_medium_v1", "max_position_qty": "1"},
                "risk_overrides": {"max_order_notional": "5000"},
                "risk_policy": {"policy_code": "perp_medium_v1", "max_position_qty": "1"},
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

            def load_run_and_persist(self, connection, *, persist_signals=True, persist_debug_traces=False):
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
                            "trading_timezone": "Asia/Taipei",
                            "universe": ["BTCUSDT_PERP"],
                            "risk_policy": {
                                "policy_code": "perp_medium_v1",
                                "max_position_qty": "1",
                            }
                        },
                        "start_time": "2026-03-01T00:00:00Z",
                        "end_time": "2026-03-31T00:00:00Z",
                        "initial_cash": "100000",
                        "assumption_bundle_code": "baseline_perp_research",
                        "assumption_bundle_version": "v1",
                        "risk_overrides": {
                            "max_order_notional": "5000",
                        },
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
        self.assertEqual(detail_response.data.trading_timezone, "Asia/Taipei")
        self.assertEqual(detail_response.data.assumption_bundle_code, "baseline_perp_research")
        self.assertEqual(detail_response.data.assumption_bundle_version, "v1")
        self.assertEqual(detail_response.data.fill_model_version, "deterministic_bars_v1")
        self.assertEqual(detail_response.data.feature_input_version, "bars_only_v1")
        self.assertEqual(detail_response.data.benchmark_set_code, "btc_perp_baseline_v1")
        self.assertEqual(detail_response.data.session_risk_policy["policy_code"], "perp_medium_v1")
        self.assertEqual(detail_response.data.risk_overrides_json["max_order_notional"], "5000")
        self.assertEqual(detail_response.data.risk_policy["policy_code"], "perp_medium_v1")
        self.assertEqual(detail_response.data.assumption_bundle_json["assumption_bundle_code"], "baseline_perp_research")
        self.assertEqual(detail_response.data.effective_assumptions_json["benchmark_set_code"], "btc_perp_baseline_v1")
        self.assertEqual(detail_response.data.run_metadata_json["source"], "ui")
        self.assertEqual(detail_response.data.runtime_metadata_json["risk_summary"]["blocked_intent_count"], 1)

    def test_backtest_run_create_rejects_unknown_named_risk_policy(self) -> None:
        original_runner = app_module.BacktestRunnerSkeleton

        class StubRunner:
            def __init__(self, run_config):
                self.run_config = run_config

            def load_run_and_persist(self, connection, *, persist_signals=True, persist_debug_traces=False):
                self.run_config.build_effective_risk_policy()
                return SimpleNamespace(run_id=999, loop_result=SimpleNamespace())

        app_module.BacktestRunnerSkeleton = StubRunner
        try:
            with self.assertRaises(HTTPException) as exc:
                self.__class__.backtest_runs_create_endpoint(
                    BacktestRunStartRequest.model_validate(
                        {
                            "run_name": "btc_unknown_risk_policy",
                            "session": {
                                "session_code": "bt_unknown_risk_policy",
                                "environment": "backtest",
                                "account_code": "paper_main",
                                "strategy_code": "btc_momentum",
                                "strategy_version": "v1.0.0",
                                "exchange_code": "binance",
                                "universe": ["BTCUSDT_PERP"],
                                "risk_policy": {
                                    "policy_code": "perp_typo_v1",
                                },
                            },
                            "start_time": "2026-03-01T00:00:00Z",
                            "end_time": "2026-03-31T00:00:00Z",
                            "initial_cash": "100000",
                        }
                    ),
                    "Bearer developer:u_123:Alice",
                )
        finally:
            app_module.BacktestRunnerSkeleton = original_runner

        self.assertEqual(exc.exception.status_code, 422)
        self.assertEqual(exc.exception.detail["code"], "VALIDATION_ERROR")

    def test_backtest_run_create_rejects_unknown_named_assumption_bundle(self) -> None:
        original_runner = app_module.BacktestRunnerSkeleton

        class StubRunner:
            def __init__(self, run_config):
                self.run_config = run_config

            def load_run_and_persist(self, connection, *, persist_signals=True, persist_debug_traces=False):
                self.run_config.build_effective_assumption_snapshot()
                return SimpleNamespace(run_id=999, loop_result=SimpleNamespace())

        app_module.BacktestRunnerSkeleton = StubRunner
        try:
            with self.assertRaises(HTTPException) as exc:
                self.__class__.backtest_runs_create_endpoint(
                    BacktestRunStartRequest.model_validate(
                        {
                            "run_name": "btc_unknown_assumption_bundle",
                            "session": {
                                "session_code": "bt_unknown_assumption_bundle",
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
                            "assumption_bundle_code": "typo_bundle",
                        }
                    ),
                    "Bearer developer:u_123:Alice",
                )
        finally:
            app_module.BacktestRunnerSkeleton = original_runner

        self.assertEqual(exc.exception.status_code, 422)
        self.assertEqual(exc.exception.detail["code"], "VALIDATION_ERROR")

    def test_backtest_run_detail_endpoints_return_orders_fills_timeseries_and_signals(self) -> None:
        original_repository = app_module.BacktestRunRepository

        class StubRepository:
            def get_run(self, connection, run_id: int):
                if run_id != 601:
                    return None
                return {
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
                    "params_json": {},
                    "status": "finished",
                    "created_at": datetime.fromisoformat("2026-04-03T09:30:00+00:00"),
                }

            def list_order_records(self, connection, *, run_id: int, limit: int | None = None):
                return [
                    {
                        "sim_order_id": 11,
                        "signal_id": 101,
                        "unified_symbol": "BTCUSDT_PERP",
                        "order_time": datetime.fromisoformat("2026-03-05T00:05:00+00:00"),
                        "side": "buy",
                        "order_type": "market",
                        "price": Decimal("102.5"),
                        "qty": Decimal("1"),
                        "status": "filled",
                    }
                ]

            def list_fill_records(self, connection, *, run_id: int, limit: int | None = None):
                return [
                    {
                        "sim_fill_id": 21,
                        "sim_order_id": 11,
                        "unified_symbol": "BTCUSDT_PERP",
                        "fill_time": datetime.fromisoformat("2026-03-05T00:06:00+00:00"),
                        "price": Decimal("102.55"),
                        "qty": Decimal("1"),
                        "fee": Decimal("0.12"),
                        "slippage_cost": Decimal("0.05"),
                    }
                ]

            def list_timeseries(self, connection, *, run_id: int, limit: int | None = None):
                return [
                    {
                        "ts": datetime.fromisoformat("2026-03-05T00:06:00+00:00"),
                        "equity": Decimal("100100"),
                        "cash": Decimal("99897.33"),
                        "gross_exposure": Decimal("102.55"),
                        "net_exposure": Decimal("102.55"),
                        "drawdown": Decimal("0.01"),
                    }
                ]

            def list_signal_records(self, connection, *, run_id: int, limit: int | None = None):
                return [
                    {
                        "signal_id": 101,
                        "unified_symbol": "BTCUSDT_PERP",
                        "signal_time": datetime.fromisoformat("2026-03-05T00:05:00+00:00"),
                        "signal_type": "entry",
                        "direction": "long",
                        "target_qty": Decimal("1"),
                        "target_notional": None,
                        "reason_code": "ma_cross_up",
                    }
                ]

            def list_debug_trace_records(
                self,
                connection,
                *,
                run_id: int,
                limit: int | None = None,
                unified_symbol: str | None = None,
                bar_time_from: datetime | None = None,
                bar_time_to: datetime | None = None,
            ):
                return [
                    {
                        "debug_trace_id": 31,
                        "step_index": 1,
                        "unified_symbol": "BTCUSDT_PERP",
                        "bar_time": datetime.fromisoformat("2026-03-05T00:05:00+00:00"),
                        "close_price": Decimal("102.5"),
                        "current_position_qty": Decimal("0"),
                        "position_qty_delta": Decimal("0"),
                        "signal_count": 1,
                        "intent_count": 1,
                        "blocked_intent_count": 0,
                        "blocked_codes_json": [],
                        "created_order_count": 1,
                        "sim_order_ids_json": [11],
                        "fill_count": 0,
                        "sim_fill_ids_json": [],
                        "cash": Decimal("100000"),
                        "cash_delta": Decimal("0"),
                        "equity": Decimal("100000"),
                        "equity_delta": Decimal("0"),
                        "gross_exposure": Decimal("0"),
                        "net_exposure": Decimal("0"),
                        "drawdown": Decimal("0"),
                        "decision_json": {
                            "decision_type": "target_position",
                            "execution_intents": [{"delta_qty": "1"}],
                        },
                        "risk_outcomes_json": [{"code": "allowed", "decision": "allow"}],
                    }
                ]

        app_module.BacktestRunRepository = StubRepository
        try:
            orders_response = self.__class__.backtest_run_orders_endpoint(601, 50, "Bearer developer:u_123:Alice")
            fills_response = self.__class__.backtest_run_fills_endpoint(601, 50, "Bearer developer:u_123:Alice")
            timeseries_response = self.__class__.backtest_run_timeseries_endpoint(601, 120, "Bearer developer:u_123:Alice")
            signals_response = self.__class__.backtest_run_signals_endpoint(601, 50, "Bearer developer:u_123:Alice")
            debug_traces_response = self.__class__.backtest_run_debug_traces_endpoint(
                601,
                200,
                None,
                None,
                None,
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.BacktestRunRepository = original_repository

        self.assertTrue(orders_response.success)
        self.assertEqual(orders_response.data.orders[0].sim_order_id, 11)
        self.assertEqual(orders_response.data.orders[0].status, "filled")

        self.assertTrue(fills_response.success)
        self.assertEqual(fills_response.data.fills[0].sim_fill_id, 21)
        self.assertEqual(fills_response.data.fills[0].slippage_cost, "0.05")

        self.assertTrue(timeseries_response.success)
        self.assertEqual(timeseries_response.data.points[0].equity, "100100")

        self.assertTrue(signals_response.success)
        self.assertEqual(signals_response.data.signals[0].signal_type, "entry")
        self.assertEqual(signals_response.data.signals[0].reason_code, "ma_cross_up")

        self.assertTrue(debug_traces_response.success)
        self.assertEqual(debug_traces_response.data.traces[0].debug_trace_id, 31)
        self.assertEqual(debug_traces_response.data.traces[0].decision_json["decision_type"], "target_position")
        self.assertEqual(debug_traces_response.data.traces[0].risk_outcomes_json[0]["code"], "allowed")
        self.assertEqual(debug_traces_response.data.traces[0].sim_order_ids, [11])
        self.assertEqual(debug_traces_response.data.traces[0].sim_fill_ids, [])
        self.assertEqual(debug_traces_response.data.traces[0].position_qty_delta, "0")
        self.assertEqual(debug_traces_response.data.traces[0].gross_exposure, "0")

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
        original_compare_review_service = app_module.CompareReviewService

        class StubProjector:
            def build(self, connection, *, run_ids, compare_name=None, benchmark_run_id=None):
                return SimpleNamespace(
                    compare_set_id=None,
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

        class StubCompareReviewService:
            def persist_compare_set(self, connection, *, compare_set, actor_name: str):
                compare_set.compare_set_id = 9001
                compare_set.persisted = True
                return compare_set

        app_module.BacktestCompareProjector = StubProjector
        app_module.CompareReviewService = StubCompareReviewService
        try:
            response = self.__class__.backtest_compare_sets_endpoint(
                BacktestCompareSetRequest(run_ids=[501, 502], benchmark_run_id=501, compare_name="btc_compare_set"),
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.BacktestCompareProjector = original_projector
            app_module.CompareReviewService = original_compare_review_service

        self.assertTrue(response.success)
        self.assertEqual(response.data.compare_set_id, 9001)
        self.assertEqual(response.data.compare_name, "btc_compare_set")
        self.assertEqual(response.data.run_ids, [501, 502])
        self.assertTrue(response.data.persisted)
        self.assertEqual(response.data.benchmark_deltas[0].run_id, 502)
        self.assertEqual(response.data.assumption_diffs[0].field_name, "strategy_version")
        self.assertEqual(response.data.comparison_flags[0].code, "diagnostic_warnings_present")

    def test_backtest_compare_notes_endpoints_return_seeded_and_human_notes(self) -> None:
        original_compare_review_service = app_module.CompareReviewService

        class StubCompareReviewService:
            def list_compare_notes(self, connection, *, compare_set_id: int):
                return (
                    {"compare_set_id": compare_set_id, "compare_name": "btc_compare_set"},
                    [
                        {
                            "annotation_id": 301,
                            "entity_type": "compare_set",
                            "entity_id": str(compare_set_id),
                            "annotation_type": "review",
                            "status": "draft",
                            "title": "btc_compare_set review",
                            "summary": "System-seeded compare review draft.",
                            "note_source": "system",
                            "verification_state": "system_fact",
                            "verified_findings_json": [],
                            "open_questions_json": [],
                            "next_action": "Review KPI diff.",
                            "source_refs_json": {"compare_set_id": compare_set_id, "run_ids": [501, 502]},
                            "facts_snapshot_json": {"compare_name": "btc_compare_set"},
                            "created_by": "system",
                            "updated_by": "system",
                            "created_at": datetime.fromisoformat("2026-04-04T12:00:00+00:00"),
                            "updated_at": datetime.fromisoformat("2026-04-04T12:00:00+00:00"),
                        }
                    ],
                )

            def create_or_update_compare_note(
                self,
                connection,
                *,
                compare_set_id: int,
                annotation_id: int | None,
                annotation_type: str,
                status: str,
                title: str,
                summary: str | None,
                note_source: str,
                verification_state: str,
                verified_findings: list[str],
                open_questions: list[str],
                next_action: str | None,
                actor_name: str,
            ):
                return {
                    "annotation_id": 302 if annotation_id is None else annotation_id,
                    "entity_type": "compare_set",
                    "entity_id": str(compare_set_id),
                    "annotation_type": annotation_type,
                    "status": status,
                    "title": title,
                    "summary": summary,
                    "note_source": note_source,
                    "verification_state": verification_state,
                    "verified_findings_json": verified_findings,
                    "open_questions_json": open_questions,
                    "next_action": next_action,
                    "source_refs_json": {"compare_set_id": compare_set_id, "run_ids": [501, 502]},
                    "facts_snapshot_json": {"compare_name": "btc_compare_set"},
                    "created_by": actor_name,
                    "updated_by": actor_name,
                    "created_at": datetime.fromisoformat("2026-04-04T12:05:00+00:00"),
                    "updated_at": datetime.fromisoformat("2026-04-04T12:05:00+00:00"),
                }

        app_module.CompareReviewService = StubCompareReviewService
        try:
            list_response = self.__class__.backtest_compare_notes_list_endpoint(
                9001,
                "Bearer developer:u_123:Alice",
            )
            write_response = self.__class__.backtest_compare_notes_write_endpoint(
                9001,
                CompareReviewNoteWriteRequest(
                    title="Human compare review",
                    summary="Run 502 looks better but assumptions differ.",
                    verified_findings=["run 502 has higher total return"],
                    open_questions=["rerun with matched assumptions"],
                    next_action="rerun with aligned assumption bundle",
                ),
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.CompareReviewService = original_compare_review_service

        self.assertTrue(list_response.success)
        self.assertEqual(list_response.data.compare_set_id, 9001)
        self.assertEqual(list_response.data.compare_name, "btc_compare_set")
        self.assertEqual(list_response.data.notes[0].note_source, "system")
        self.assertEqual(list_response.data.notes[0].verification_state, "system_fact")

        self.assertTrue(write_response.success)
        self.assertEqual(write_response.data.entity_id, "9001")
        self.assertEqual(write_response.data.note_source, "human")
        self.assertEqual(write_response.data.verified_findings[0], "run 502 has higher total return")
        self.assertEqual(write_response.data.next_action, "rerun with aligned assumption bundle")


if __name__ == "__main__":
    unittest.main()
