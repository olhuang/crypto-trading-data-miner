from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import time
from types import SimpleNamespace
import unittest
from uuid import uuid4
from dataclasses import dataclass

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from fastapi import HTTPException
from fastapi.routing import APIRoute
from pydantic import ValidationError
from sqlalchemy import text

import api.app as app_module
import services.backtest_job_control as backtest_job_module
from config import settings
from api.app import (
    BacktestCompareSetRequest,
    CompareReviewNoteWriteRequest,
    BacktestRunStartRequest,
    BarBackfillRequest,
    InstrumentSyncRequest,
    MarketSnapshotRemediationRequest,
    MarketSnapshotRefreshRequest,
    TraceInvestigationNoteWriteRequest,
    TraceInvestigationAnchorWriteRequest,
    ValidatePayloadRequest,
    create_app,
    require_actor,
    resolve_current_actor,
)
from models.market import BarEvent
from storage.db import get_engine, transaction_scope
from storage.lookups import LookupResolutionError
from storage.repositories.market_data import BarRepository
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
        cls.backtest_run_jobs_create_endpoint = _resolve_route(cls.app, "/api/v1/backtests/run-jobs", "POST")
        cls.backtest_run_job_detail_endpoint = _resolve_route(cls.app, "/api/v1/backtests/run-jobs/{job_id}", "GET")
        cls.backtest_run_job_cancel_endpoint = _resolve_route(cls.app, "/api/v1/backtests/run-jobs/{job_id}/cancel", "POST")
        cls.backtest_risk_policies_endpoint = _resolve_route(cls.app, "/api/v1/backtests/risk-policies", "GET")
        cls.backtest_assumption_bundles_endpoint = _resolve_route(cls.app, "/api/v1/backtests/assumption-bundles", "GET")
        cls.backtest_runs_list_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs", "GET")
        cls.backtest_run_detail_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}", "GET")
        cls.backtest_run_orders_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/orders", "GET")
        cls.backtest_run_fills_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/fills", "GET")
        cls.backtest_run_timeseries_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/timeseries", "GET")
        cls.backtest_run_signals_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/signals", "GET")
        cls.backtest_run_debug_traces_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/debug-traces", "GET")
        cls.backtest_trace_investigation_anchor_write_endpoint = _resolve_route(
            cls.app,
            "/api/v1/backtests/runs/{run_id}/debug-traces/{debug_trace_id}/investigation-anchors",
            "POST",
        )
        cls.backtest_trace_notes_list_endpoint = _resolve_route(
            cls.app,
            "/api/v1/backtests/runs/{run_id}/debug-traces/{debug_trace_id}/notes",
            "GET",
        )
        cls.backtest_trace_notes_write_endpoint = _resolve_route(
            cls.app,
            "/api/v1/backtests/runs/{run_id}/debug-traces/{debug_trace_id}/notes",
            "POST",
        )
        cls.backtest_expected_observed_endpoint = _resolve_route(
            cls.app,
            "/api/v1/backtests/runs/{run_id}/expected-vs-observed",
            "GET",
        )
        cls.backtest_diagnostics_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/diagnostics", "GET")
        cls.backtest_period_breakdown_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/period-breakdown", "GET")
        cls.backtest_artifacts_endpoint = _resolve_route(cls.app, "/api/v1/backtests/runs/{run_id}/artifacts", "GET")
        cls.backtest_compare_sets_endpoint = _resolve_route(cls.app, "/api/v1/backtests/compare-sets", "POST")
        cls.backtest_compare_notes_list_endpoint = _resolve_route(cls.app, "/api/v1/backtests/compare-sets/{compare_set_id}/notes", "GET")
        cls.backtest_compare_notes_write_endpoint = _resolve_route(cls.app, "/api/v1/backtests/compare-sets/{compare_set_id}/notes", "POST")

    def test_trace_investigation_anchor_request_requires_non_empty_content(self) -> None:
        with self.assertRaises(ValidationError):
            TraceInvestigationAnchorWriteRequest()

        with self.assertRaises(ValidationError):
            TraceInvestigationAnchorWriteRequest(
                scenario_id="   ",
                expected_behavior="",
                observed_behavior="   ",
            )

        request = TraceInvestigationAnchorWriteRequest(
            scenario_id=" scenario_alpha ",
            expected_behavior=" expected move ",
            observed_behavior="   ",
        )

        self.assertEqual(request.scenario_id, "scenario_alpha")
        self.assertEqual(request.expected_behavior, "expected move")
        self.assertIsNone(request.observed_behavior)

    def test_backtest_run_job_create_returns_job_action(self) -> None:
        original_starter = app_module.start_backtest_run_job

        @dataclass
        class _Result:
            job_id: int
            status: str

        captured = {}

        def _stub_start(run_config, *, requested_by, persist_signals=True, persist_debug_traces=False):
            captured["strategy_code"] = run_config.session.strategy_code
            captured["requested_by"] = requested_by
            captured["persist_signals"] = persist_signals
            captured["persist_debug_traces"] = persist_debug_traces
            return _Result(job_id=9001, status="queued")

        app_module.start_backtest_run_job = _stub_start
        try:
            response = self.__class__.backtest_run_jobs_create_endpoint(
                BacktestRunStartRequest.model_validate(
                    {
                        "run_name": "btc_async_job_demo",
                        "session": {
                            "session_code": "bt_async_job_demo",
                            "environment": "backtest",
                            "account_code": "paper_main",
                            "strategy_code": "btc_momentum",
                            "strategy_version": "v1.0.0",
                            "exchange_code": "binance",
                            "trading_timezone": "UTC",
                            "universe": ["BTCUSDT_PERP"],
                        },
                        "start_time": "2026-03-01T00:00:00Z",
                        "end_time": "2026-03-02T00:00:00Z",
                        "initial_cash": "100000",
                        "persist_debug_traces": True,
                        "debug_trace_level": "full_compressed",
                    }
                ),
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.start_backtest_run_job = original_starter

        self.assertTrue(response.success)
        self.assertEqual(response.data.job_id, 9001)
        self.assertEqual(response.data.status, "queued")
        self.assertEqual(captured["strategy_code"], "btc_momentum")
        self.assertEqual(captured["requested_by"], "u_123")
        self.assertTrue(captured["persist_signals"])
        self.assertTrue(captured["persist_debug_traces"])

    def test_backtest_run_job_detail_returns_progress_summary(self) -> None:
        original_getter = app_module.get_backtest_run_job

        def _stub_get(job_id: int):
            return {
                "job_id": job_id,
                "service_name": "backtest_runner",
                "data_type": "backtest_run",
                "status": "running",
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "started_at": datetime.fromisoformat("2026-04-11T08:00:00+00:00"),
                "finished_at": None,
                "records_expected": None,
                "records_written": None,
                "error_message": None,
                "process_alive": True,
                "metadata_json": {
                    "start_time": "2026-01-01T00:00:00+00:00",
                    "end_time": "2026-12-31T23:59:00+00:00",
                    "current_bar_time": "2026-06-01T00:00:00+00:00",
                    "progress_pct": 41.5,
                },
                "summary": {
                    "run_id": None,
                    "progress_pct": 41.5,
                    "current_bar_time": "2026-06-01T00:00:00+00:00",
                    "start_time": "2026-01-01T00:00:00+00:00",
                    "end_time": "2026-12-31T23:59:00+00:00",
                    "debug_trace_count": None,
                },
            }

        app_module.get_backtest_run_job = _stub_get
        try:
            response = self.__class__.backtest_run_job_detail_endpoint(
                9001,
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.get_backtest_run_job = original_getter

        self.assertTrue(response.success)
        self.assertEqual(response.data.job_id, 9001)
        self.assertEqual(response.data.status, "running")
        self.assertTrue(response.data.process_alive)
        self.assertEqual(response.data.summary.progress_pct, 41.5)
        self.assertEqual(response.data.summary.current_bar_time, "2026-06-01T00:00:00+00:00")

    def test_backtest_run_job_cancel_returns_job_action(self) -> None:
        original_canceler = app_module.cancel_backtest_run_job

        @dataclass
        class _Result:
            job_id: int
            status: str

        captured = {}

        def _stub_cancel(job_id: int, *, requested_by: str):
            captured["job_id"] = job_id
            captured["requested_by"] = requested_by
            return _Result(job_id=job_id, status="cancel_requested")

        app_module.cancel_backtest_run_job = _stub_cancel
        try:
            response = self.__class__.backtest_run_job_cancel_endpoint(
                9001,
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.cancel_backtest_run_job = original_canceler

        self.assertTrue(response.success)
        self.assertEqual(response.data.job_id, 9001)
        self.assertEqual(response.data.status, "cancel_requested")
        self.assertEqual(captured["job_id"], 9001)
        self.assertEqual(captured["requested_by"], "u_123")

    def test_backtest_run_job_control_completes_and_persists_progress_summary(self) -> None:
        original_transaction_scope = backtest_job_module.transaction_scope
        original_repository = backtest_job_module.IngestionJobRepository
        original_runner = backtest_job_module.BacktestRunnerSkeleton

        jobs: dict[int, dict[str, object]] = {}
        next_job_id = {"value": 7001}

        @contextmanager
        def _stub_transaction_scope():
            yield object()

        class StubRepository:
            def insert_requested_by(
                self,
                connection,
                *,
                requested_by,
                service_name,
                data_type,
                status,
                exchange_code,
                unified_symbol,
                schedule_type,
                window_start,
                window_end,
                metadata_json=None,
                **_,
            ):
                job_id = next_job_id["value"]
                next_job_id["value"] += 1
                jobs[job_id] = {
                    "job_id": job_id,
                    "service_name": service_name,
                    "data_type": data_type,
                    "status": status,
                    "exchange_code": exchange_code,
                    "unified_symbol": unified_symbol,
                    "started_at": datetime.now(timezone.utc),
                    "finished_at": None,
                    "records_expected": None,
                    "records_written": None,
                    "error_message": None,
                    "metadata_json": dict(metadata_json or {}),
                }
                return job_id

            def finish_job(
                self,
                connection,
                ingestion_job_id,
                *,
                status,
                finished_at,
                records_expected=None,
                records_written=None,
                error_message=None,
                metadata_json=None,
            ):
                job = jobs[ingestion_job_id]
                job["status"] = status
                job["finished_at"] = finished_at
                if records_expected is not None:
                    job["records_expected"] = records_expected
                if records_written is not None:
                    job["records_written"] = records_written
                if error_message is not None:
                    job["error_message"] = error_message
                if metadata_json is not None:
                    job["metadata_json"] = dict(metadata_json)

            def get_job(self, connection, ingestion_job_id):
                job = jobs.get(ingestion_job_id)
                return None if job is None else dict(job)

        class StubRunner:
            def __init__(self, run_config):
                self.run_config = run_config

            def load_run_and_persist(
                self,
                connection,
                *,
                persist_signals=True,
                persist_debug_traces=False,
                progress_callback=None,
            ):
                midpoint = self.run_config.start_time + (self.run_config.end_time - self.run_config.start_time) / 2
                if progress_callback is not None:
                    progress_callback(midpoint)
                    progress_callback(self.run_config.end_time)
                return SimpleNamespace(
                    run_id=8123,
                    loop_result=SimpleNamespace(debug_trace_count=7),
                )

        backtest_job_module.transaction_scope = _stub_transaction_scope
        backtest_job_module.IngestionJobRepository = StubRepository
        backtest_job_module.BacktestRunnerSkeleton = StubRunner
        try:
            result = backtest_job_module.start_backtest_run_job(
                BacktestRunStartRequest.model_validate(
                    {
                        "run_name": "btc_async_job_control",
                        "session": {
                            "session_code": "bt_async_job_control",
                            "environment": "backtest",
                            "account_code": "paper_main",
                            "strategy_code": "btc_momentum",
                            "strategy_version": "v1.0.0",
                            "exchange_code": "binance",
                            "trading_timezone": "UTC",
                            "universe": ["BTCUSDT_PERP"],
                        },
                        "start_time": "2026-01-01T00:00:00Z",
                        "end_time": "2026-01-02T00:00:00Z",
                        "initial_cash": "100000",
                        "persist_debug_traces": True,
                        "debug_trace_level": "full_compressed",
                    }
                ),
                requested_by="u_123",
                persist_signals=True,
                persist_debug_traces=True,
            )

            final_job = None
            for _ in range(30):
                current = backtest_job_module.get_backtest_run_job(result.job_id)
                if current is not None and current["status"] == "completed":
                    final_job = current
                    break
                time.sleep(0.02)
        finally:
            backtest_job_module.transaction_scope = original_transaction_scope
            backtest_job_module.IngestionJobRepository = original_repository
            backtest_job_module.BacktestRunnerSkeleton = original_runner
            with backtest_job_module._ACTIVE_THREADS_LOCK:
                backtest_job_module._ACTIVE_THREADS.clear()

        self.assertIsNotNone(final_job)
        assert final_job is not None
        self.assertEqual(final_job["status"], "completed")
        self.assertEqual(final_job["summary"]["run_id"], 8123)
        self.assertEqual(final_job["summary"]["debug_trace_count"], 7)
        self.assertEqual(final_job["summary"]["progress_pct"], 100.0)
        self.assertEqual(final_job["summary"]["current_bar_time"], "2026-01-02T00:00:00+00:00")

    def test_backtest_run_job_control_marks_orphaned_running_job_stale(self) -> None:
        original_transaction_scope = backtest_job_module.transaction_scope
        original_repository = backtest_job_module.IngestionJobRepository

        stale_heartbeat = datetime.now(timezone.utc) - timedelta(minutes=5)
        jobs = {
            7001: {
                "job_id": 7001,
                "service_name": "backtest_runner",
                "data_type": "backtest_run",
                "status": "running",
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "started_at": stale_heartbeat,
                "finished_at": None,
                "records_expected": None,
                "records_written": None,
                "error_message": None,
                "metadata_json": {
                    "status": "running",
                    "start_time": "2026-01-01T00:00:00+00:00",
                    "end_time": "2026-01-02T00:00:00+00:00",
                    "progress_pct": 37.5,
                    "current_bar_time": "2026-01-01T09:00:00+00:00",
                    "heartbeat_at": stale_heartbeat.isoformat(),
                },
            }
        }

        @contextmanager
        def _stub_transaction_scope():
            yield object()

        class StubRepository:
            def get_job(self, connection, ingestion_job_id):
                job = jobs.get(ingestion_job_id)
                return None if job is None else dict(job)

            def finish_job(
                self,
                connection,
                ingestion_job_id,
                *,
                status,
                finished_at,
                records_expected=None,
                records_written=None,
                error_message=None,
                metadata_json=None,
            ):
                job = jobs[ingestion_job_id]
                job["status"] = status
                job["finished_at"] = finished_at
                job["error_message"] = error_message
                if metadata_json is not None:
                    job["metadata_json"] = dict(metadata_json)

        backtest_job_module.transaction_scope = _stub_transaction_scope
        backtest_job_module.IngestionJobRepository = StubRepository
        try:
            with backtest_job_module._ACTIVE_THREADS_LOCK:
                backtest_job_module._ACTIVE_THREADS.clear()
            payload = backtest_job_module.get_backtest_run_job(7001)
        finally:
            backtest_job_module.transaction_scope = original_transaction_scope
            backtest_job_module.IngestionJobRepository = original_repository
            with backtest_job_module._ACTIVE_THREADS_LOCK:
                backtest_job_module._ACTIVE_THREADS.clear()

        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["status"], "stale")
        self.assertFalse(payload["process_alive"])
        self.assertIn("no active worker heartbeat", payload["error_message"])
        self.assertEqual(payload["metadata_json"]["status"], "stale")
        self.assertIn("heartbeat_at", payload["metadata_json"])

    def test_cancel_backtest_run_job_marks_job_cancel_requested(self) -> None:
        original_transaction_scope = backtest_job_module.transaction_scope
        original_repository = backtest_job_module.IngestionJobRepository

        jobs = {
            7002: {
                "job_id": 7002,
                "service_name": "backtest_runner",
                "data_type": "backtest_run",
                "status": "running",
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "started_at": datetime.now(timezone.utc),
                "finished_at": None,
                "records_expected": None,
                "records_written": None,
                "error_message": None,
                "metadata_json": {
                    "status": "running",
                    "progress_pct": 24.0,
                },
            }
        }

        @contextmanager
        def _stub_transaction_scope():
            yield object()

        class StubRepository:
            def get_job(self, connection, ingestion_job_id):
                job = jobs.get(ingestion_job_id)
                return None if job is None else dict(job)

            def finish_job(
                self,
                connection,
                ingestion_job_id,
                *,
                status,
                finished_at,
                records_expected=None,
                records_written=None,
                error_message=None,
                metadata_json=None,
            ):
                job = jobs[ingestion_job_id]
                job["status"] = status
                job["finished_at"] = finished_at
                job["error_message"] = error_message
                if metadata_json is not None:
                    job["metadata_json"] = dict(metadata_json)

        backtest_job_module.transaction_scope = _stub_transaction_scope
        backtest_job_module.IngestionJobRepository = StubRepository
        try:
            result = backtest_job_module.cancel_backtest_run_job(7002, requested_by="u_123")
        finally:
            backtest_job_module.transaction_scope = original_transaction_scope
            backtest_job_module.IngestionJobRepository = original_repository
            with backtest_job_module._CANCEL_REQUESTED_LOCK:
                backtest_job_module._CANCEL_REQUESTED_JOB_IDS.clear()

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.status, "cancel_requested")
        self.assertEqual(jobs[7002]["status"], "cancel_requested")
        self.assertTrue(jobs[7002]["metadata_json"]["cancel_requested"])
        self.assertEqual(jobs[7002]["metadata_json"]["cancel_requested_by"], "u_123")

    def test_trace_investigation_note_request_validates_allowed_fields(self) -> None:
        with self.assertRaises(ValidationError):
            TraceInvestigationNoteWriteRequest(title="  ")

        with self.assertRaises(ValidationError):
            TraceInvestigationNoteWriteRequest(title="x", annotation_type="review")

        request = TraceInvestigationNoteWriteRequest(
            title=" Trace investigation ",
            annotation_type="expected_vs_observed",
            status="confirmed",
            note_source="agent",
            verification_state="assumption",
        )

        self.assertEqual(request.annotation_type, "expected_vs_observed")
        self.assertEqual(request.status, "confirmed")
        self.assertEqual(request.note_source, "agent")
        self.assertEqual(request.verification_state, "assumption")

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
        job_id = None
        try:
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
        finally:
            if job_id is not None:
                with transaction_scope() as connection:
                    connection.exec_driver_sql(
                        "delete from ops.ingestion_jobs where ingestion_job_id = %s",
                        (job_id,),
                    )

    def test_jobs_list_endpoint_supports_filters(self) -> None:
        sync_job_id = None
        remediation_job_id = None
        try:
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
        finally:
            with transaction_scope() as connection:
                if remediation_job_id is not None:
                    connection.exec_driver_sql(
                        "delete from ops.ingestion_jobs where ingestion_job_id = %s",
                        (remediation_job_id,),
                    )
                if sync_job_id is not None:
                    connection.exec_driver_sql(
                        "delete from ops.ingestion_jobs where ingestion_job_id = %s",
                        (sync_job_id,),
                    )

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
        self.assertGreaterEqual(len(response.data.assumption_bundles), 4)
        bundle_keys = {
            (resource.assumption_bundle_code, resource.assumption_bundle_version)
            for resource in response.data.assumption_bundles
        }
        self.assertIn(("baseline_perp_research", "v1"), bundle_keys)
        self.assertIn(("breakout_perp_research", "v1"), bundle_keys)
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

    def test_backtest_run_create_accepts_hourly_strategy_request(self) -> None:
        original_runner = app_module.BacktestRunnerSkeleton
        original_repository = app_module.BacktestRunRepository
        captured_run_config: dict[str, object] = {}

        class StubRunner:
            def __init__(self, run_config):
                captured_run_config["strategy_code"] = run_config.session.strategy_code
                captured_run_config["strategy_version"] = run_config.session.strategy_version
                captured_run_config["short_window"] = run_config.strategy_params_json.get("short_window")
                captured_run_config["long_window"] = run_config.strategy_params_json.get("long_window")
                captured_run_config["target_qty"] = run_config.strategy_params_json.get("target_qty")
                captured_run_config["persist_debug_traces"] = None
                captured_run_config["persist_signals"] = None

            def load_run_and_persist(self, connection, *, persist_signals=True, persist_debug_traces=False):
                captured_run_config["persist_debug_traces"] = persist_debug_traces
                captured_run_config["persist_signals"] = persist_signals
                return SimpleNamespace(run_id=602, loop_result=SimpleNamespace())

        class StubRepository:
            def get_run(self, connection, run_id: int):
                if run_id != 602:
                    return None
                return {
                    "run_id": 602,
                    "strategy_code": "btc_hourly_momentum",
                    "strategy_version": "v1.0.0",
                    "account_code": "paper_main",
                    "run_name": "btc_hourly_ui_demo",
                    "universe_json": ["BTCUSDT_PERP"],
                    "start_time": datetime.fromisoformat("2026-03-01T00:00:00+00:00"),
                    "end_time": datetime.fromisoformat("2026-03-31T00:00:00+00:00"),
                    "market_data_version": "md.bars_1m",
                    "fee_model_version": "ref_fee_schedule_v1",
                    "slippage_model_version": "fixed_bps_v1",
                    "latency_model_version": "bars_next_open_v1",
                    "params_json": {
                        "session_code": "bt_hourly_ui_demo",
                        "environment": "backtest",
                        "trading_timezone": "UTC",
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
                        "strategy_params": {"short_window": 3, "long_window": 8, "target_qty": "0.05"},
                        "run_metadata": {"source": "ui"},
                        "runtime_metadata": {},
                        "session_metadata": {},
                        "execution_policy": {"policy_code": "default"},
                        "protection_policy": {"policy_code": "default"},
                        "session_risk_policy": {"policy_code": "perp_medium_v1"},
                        "risk_overrides": {},
                        "risk_policy": {"policy_code": "perp_medium_v1"},
                    },
                    "status": "finished",
                    "created_at": datetime.fromisoformat("2026-04-08T09:30:00+00:00"),
                }

            def get_performance_summary(self, connection, *, run_id: int):
                return {
                    "total_return": Decimal("0.05"),
                    "annualized_return": Decimal("0.20"),
                    "max_drawdown": Decimal("0.03"),
                    "turnover": Decimal("0.80"),
                    "win_rate": Decimal("0.52"),
                    "fee_cost": Decimal("8.50"),
                    "slippage_cost": Decimal("3.20"),
                }

        app_module.BacktestRunnerSkeleton = StubRunner
        app_module.BacktestRunRepository = StubRepository
        try:
            response = self.__class__.backtest_runs_create_endpoint(
                BacktestRunStartRequest.model_validate(
                    {
                        "run_name": "btc_hourly_ui_demo",
                        "session": {
                            "session_code": "bt_hourly_ui_demo",
                            "environment": "backtest",
                            "account_code": "paper_main",
                            "strategy_code": "btc_hourly_momentum",
                            "strategy_version": "v1.0.0",
                            "exchange_code": "binance",
                            "trading_timezone": "UTC",
                            "universe": ["BTCUSDT_PERP"],
                            "risk_policy": {"policy_code": "perp_medium_v1"},
                        },
                        "start_time": "2026-03-01T00:00:00Z",
                        "end_time": "2026-03-31T00:00:00Z",
                        "initial_cash": "100000",
                        "assumption_bundle_code": "baseline_perp_research",
                        "assumption_bundle_version": "v1",
                        "strategy_params": {"short_window": 3, "long_window": 8, "target_qty": "0.05"},
                        "persist_debug_traces": True,
                    }
                ),
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.BacktestRunnerSkeleton = original_runner
            app_module.BacktestRunRepository = original_repository

        self.assertTrue(response.success)
        self.assertEqual(response.data.run_id, 602)
        self.assertEqual(response.data.strategy_code, "btc_hourly_momentum")
        self.assertEqual(response.data.strategy_params_json["short_window"], 3)
        self.assertEqual(response.data.strategy_params_json["long_window"], 8)
        self.assertEqual(captured_run_config["strategy_code"], "btc_hourly_momentum")
        self.assertEqual(captured_run_config["strategy_version"], "v1.0.0")
        self.assertEqual(captured_run_config["short_window"], 3)
        self.assertEqual(captured_run_config["long_window"], 8)
        self.assertEqual(captured_run_config["target_qty"], "0.05")
        self.assertTrue(captured_run_config["persist_signals"])
        self.assertTrue(captured_run_config["persist_debug_traces"])

    def test_backtest_run_create_accepts_breakout_strategy_request(self) -> None:
        original_runner = app_module.BacktestRunnerSkeleton
        original_repository = app_module.BacktestRunRepository
        captured_run_config: dict[str, object] = {}

        class StubRunner:
            def __init__(self, run_config):
                captured_run_config["strategy_code"] = run_config.session.strategy_code
                captured_run_config["strategy_version"] = run_config.session.strategy_version
                captured_run_config["feature_input_version"] = run_config.build_effective_assumption_snapshot().feature_input_version
                captured_run_config["trend_fast_ema"] = run_config.strategy_params_json.get("trend_fast_ema")
                captured_run_config["trend_slow_ema"] = run_config.strategy_params_json.get("trend_slow_ema")
                captured_run_config["breakout_lookback_bars"] = run_config.strategy_params_json.get("breakout_lookback_bars")
                captured_run_config["debug_trace_level"] = run_config.debug_trace_level
                captured_run_config["debug_trace_stride"] = run_config.debug_trace_stride
                captured_run_config["debug_trace_activity_only"] = run_config.debug_trace_activity_only
                captured_run_config["persist_debug_traces"] = None
                captured_run_config["persist_signals"] = None

            def load_run_and_persist(self, connection, *, persist_signals=True, persist_debug_traces=False):
                captured_run_config["persist_debug_traces"] = persist_debug_traces
                captured_run_config["persist_signals"] = persist_signals
                return SimpleNamespace(run_id=603, loop_result=SimpleNamespace())

        class StubRepository:
            def get_run(self, connection, run_id: int):
                if run_id != 603:
                    return None
                return {
                    "run_id": 603,
                    "strategy_code": "btc_4h_breakout_perp",
                    "strategy_version": "v0.1.0",
                    "account_code": "paper_main",
                    "run_name": "btc_breakout_ui_demo",
                    "universe_json": ["BTCUSDT_PERP"],
                    "start_time": datetime.fromisoformat("2026-03-01T00:00:00+00:00"),
                    "end_time": datetime.fromisoformat("2026-03-31T00:00:00+00:00"),
                    "market_data_version": "md.bars_1m",
                    "fee_model_version": "ref_fee_schedule_v1",
                    "slippage_model_version": "fixed_bps_v1",
                    "latency_model_version": "bars_next_open_v1",
                    "params_json": {
                        "session_code": "bt_breakout_ui_demo",
                        "environment": "backtest",
                        "trading_timezone": "UTC",
                        "netting_mode": "isolated_strategy_session",
                        "bar_interval": "1m",
                        "initial_cash": "100000",
                        "assumption_bundle_code": "breakout_perp_research",
                        "assumption_bundle_version": "v1",
                        "assumption_bundle": {
                            "assumption_bundle_code": "breakout_perp_research",
                            "assumption_bundle_version": "v1",
                            "market_data_version": "md.bars_1m",
                            "fee_model_version": "ref_fee_schedule_v1",
                            "slippage_model_version": "fixed_bps_v1",
                            "fill_model_version": "deterministic_bars_v1",
                            "latency_model_version": "bars_next_open_v1",
                            "feature_input_version": "bars_perp_breakout_context_v1",
                            "benchmark_set_code": "btc_perp_baseline_v1",
                            "risk_policy": {"policy_code": "perp_medium_v1"},
                        },
                        "assumption_overrides": {},
                        "effective_assumptions": {
                            "assumption_bundle_code": "breakout_perp_research",
                            "assumption_bundle_version": "v1",
                            "market_data_version": "md.bars_1m",
                            "fee_model_version": "ref_fee_schedule_v1",
                            "slippage_model_version": "fixed_bps_v1",
                            "fill_model_version": "deterministic_bars_v1",
                            "latency_model_version": "bars_next_open_v1",
                            "feature_input_version": "bars_perp_breakout_context_v1",
                            "benchmark_set_code": "btc_perp_baseline_v1",
                            "risk_policy": {"policy_code": "perp_medium_v1"},
                        },
                        "strategy_params": {
                            "trend_fast_ema": 20,
                            "trend_slow_ema": 50,
                            "breakout_lookback_bars": 20,
                            "atr_window": 14,
                            "risk_per_trade_pct": "0.005",
                        },
                        "run_metadata": {"source": "ui"},
                        "runtime_metadata": {},
                        "session_metadata": {},
                        "execution_policy": {"policy_code": "default"},
                        "protection_policy": {"policy_code": "default"},
                        "session_risk_policy": {"policy_code": "perp_medium_v1"},
                        "risk_overrides": {},
                        "risk_policy": {"policy_code": "perp_medium_v1"},
                    },
                    "status": "finished",
                    "created_at": datetime.fromisoformat("2026-04-11T09:30:00+00:00"),
                }

            def get_performance_summary(self, connection, *, run_id: int):
                return {
                    "total_return": Decimal("0.06"),
                    "annualized_return": Decimal("0.18"),
                    "max_drawdown": Decimal("0.04"),
                    "turnover": Decimal("0.35"),
                    "win_rate": Decimal("0.55"),
                    "fee_cost": Decimal("7.00"),
                    "slippage_cost": Decimal("2.50"),
                }

        app_module.BacktestRunnerSkeleton = StubRunner
        app_module.BacktestRunRepository = StubRepository
        try:
            response = self.__class__.backtest_runs_create_endpoint(
                BacktestRunStartRequest.model_validate(
                    {
                        "run_name": "btc_breakout_ui_demo",
                        "session": {
                            "session_code": "bt_breakout_ui_demo",
                            "environment": "backtest",
                            "account_code": "paper_main",
                            "strategy_code": "btc_4h_breakout_perp",
                            "strategy_version": "v0.1.0",
                            "exchange_code": "binance",
                            "trading_timezone": "UTC",
                            "universe": ["BTCUSDT_PERP"],
                            "risk_policy": {"policy_code": "perp_medium_v1"},
                        },
                        "start_time": "2026-03-01T00:00:00Z",
                        "end_time": "2026-03-31T00:00:00Z",
                        "initial_cash": "100000",
                        "assumption_bundle_code": "breakout_perp_research",
                        "assumption_bundle_version": "v1",
                        "strategy_params": {
                            "trend_fast_ema": 20,
                            "trend_slow_ema": 50,
                            "breakout_lookback_bars": 20,
                            "atr_window": 14,
                            "risk_per_trade_pct": "0.005",
                        },
                        "persist_debug_traces": True,
                        "debug_trace_level": "compact",
                        "debug_trace_stride": 24,
                        "debug_trace_activity_only": True,
                    }
                ),
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.BacktestRunnerSkeleton = original_runner
            app_module.BacktestRunRepository = original_repository

        self.assertTrue(response.success)
        self.assertEqual(response.data.run_id, 603)
        self.assertEqual(response.data.strategy_code, "btc_4h_breakout_perp")
        self.assertEqual(response.data.feature_input_version, "bars_perp_breakout_context_v1")
        self.assertEqual(response.data.strategy_params_json["trend_fast_ema"], 20)
        self.assertEqual(response.data.strategy_params_json["trend_slow_ema"], 50)
        self.assertEqual(captured_run_config["strategy_code"], "btc_4h_breakout_perp")
        self.assertEqual(captured_run_config["strategy_version"], "v0.1.0")
        self.assertEqual(captured_run_config["feature_input_version"], "bars_perp_breakout_context_v1")
        self.assertEqual(captured_run_config["trend_fast_ema"], 20)
        self.assertEqual(captured_run_config["trend_slow_ema"], 50)
        self.assertEqual(captured_run_config["breakout_lookback_bars"], 20)
        self.assertEqual(captured_run_config["debug_trace_level"], "compact")
        self.assertEqual(captured_run_config["debug_trace_stride"], 24)
        self.assertTrue(captured_run_config["debug_trace_activity_only"])
        self.assertTrue(captured_run_config["persist_signals"])
        self.assertTrue(captured_run_config["persist_debug_traces"])

    def test_backtest_run_create_can_launch_persisted_hourly_run_end_to_end(self) -> None:
        original_transaction_scope = app_module.transaction_scope
        original_connection_scope = app_module.connection_scope
        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            run_start = datetime(2036, 1, 3, 0, 0, tzinfo=timezone.utc)
            bar_repository = BarRepository()
            for offset in range(60):
                bar_time = run_start + timedelta(minutes=offset)
                bar_repository.upsert(
                    connection,
                    BarEvent.model_validate(
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                            "bar_interval": "1m",
                            "bar_time": bar_time.isoformat(),
                            "event_time": bar_time.isoformat(),
                            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                            "open": "100",
                            "high": "100",
                            "low": "100",
                            "close": "100",
                            "volume": "10",
                        }
                    ),
                )
            for offset in range(60, 120):
                bar_time = run_start + timedelta(minutes=offset)
                bar_repository.upsert(
                    connection,
                    BarEvent.model_validate(
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                            "bar_interval": "1m",
                            "bar_time": bar_time.isoformat(),
                            "event_time": bar_time.isoformat(),
                            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                            "open": "110",
                            "high": "110",
                            "low": "110",
                            "close": "110",
                            "volume": "10",
                        }
                    ),
                )
            for offset in range(120, 124):
                bar_time = run_start + timedelta(minutes=offset)
                bar_repository.upsert(
                    connection,
                    BarEvent.model_validate(
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                            "bar_interval": "1m",
                            "bar_time": bar_time.isoformat(),
                            "event_time": bar_time.isoformat(),
                            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                            "open": "90",
                            "high": "90",
                            "low": "90",
                            "close": "90",
                            "volume": "10",
                        }
                    ),
                )

            @contextmanager
            def _stub_transaction_scope():
                yield connection

            @contextmanager
            def _stub_connection_scope():
                yield connection

            app_module.transaction_scope = _stub_transaction_scope
            app_module.connection_scope = _stub_connection_scope

            create_response = self.__class__.backtest_runs_create_endpoint(
                BacktestRunStartRequest.model_validate(
                    {
                        "run_name": "btc_hourly_api_integration",
                        "session": {
                            "session_code": "bt_hourly_api_integration",
                            "environment": "backtest",
                            "account_code": "paper_main",
                            "strategy_code": "btc_hourly_momentum",
                            "strategy_version": "v1.0.0",
                            "exchange_code": "binance",
                            "trading_timezone": "UTC",
                            "universe": ["BTCUSDT_PERP"],
                            "risk_policy": {"policy_code": "perp_medium_v1"},
                        },
                        "start_time": run_start.isoformat(),
                        "end_time": (run_start + timedelta(minutes=124)).isoformat(),
                        "initial_cash": "10000",
                        "assumption_bundle_code": "baseline_perp_research",
                        "assumption_bundle_version": "v1",
                        "strategy_params": {"short_window": 1, "long_window": 2, "target_qty": "1"},
                    }
                ),
                "Bearer developer:u_123:Alice",
            )

            run_id = create_response.data.run_id
            detail_response = self.__class__.backtest_run_detail_endpoint(run_id, "Bearer developer:u_123:Alice")
            orders_response = self.__class__.backtest_run_orders_endpoint(run_id, 20, "Bearer developer:u_123:Alice")
            fills_response = self.__class__.backtest_run_fills_endpoint(run_id, 20, "Bearer developer:u_123:Alice")
            signals_response = self.__class__.backtest_run_signals_endpoint(run_id, 20, "Bearer developer:u_123:Alice")
            timeseries_response = self.__class__.backtest_run_timeseries_endpoint(run_id, 200, "Bearer developer:u_123:Alice")

        finally:
            app_module.transaction_scope = original_transaction_scope
            app_module.connection_scope = original_connection_scope
            transaction.rollback()
            connection.close()

        self.assertTrue(create_response.success)
        self.assertEqual(create_response.data.strategy_code, "btc_hourly_momentum")
        self.assertEqual(create_response.data.strategy_params_json["short_window"], 1)
        self.assertEqual(create_response.data.strategy_params_json["long_window"], 2)
        self.assertEqual(create_response.data.total_return is not None, True)

        self.assertTrue(detail_response.success)
        self.assertEqual(detail_response.data.run_id, run_id)
        self.assertEqual(detail_response.data.strategy_code, "btc_hourly_momentum")
        self.assertEqual(detail_response.data.session_code, "bt_hourly_api_integration")

        self.assertTrue(orders_response.success)
        self.assertEqual(len(orders_response.data.orders), 2)
        self.assertEqual(orders_response.data.orders[0].side, "buy")
        self.assertEqual(orders_response.data.orders[1].side, "sell")

        self.assertTrue(fills_response.success)
        self.assertEqual(len(fills_response.data.fills), 2)
        self.assertEqual(Decimal(fills_response.data.fills[0].qty), Decimal("1"))

        self.assertTrue(signals_response.success)
        self.assertEqual(len(signals_response.data.signals), 2)
        self.assertEqual(signals_response.data.signals[0].signal_type, "entry")
        self.assertEqual(signals_response.data.signals[1].signal_type, "exit")

        self.assertTrue(timeseries_response.success)
        self.assertGreater(len(timeseries_response.data.points), 100)

    def test_backtest_run_job_can_launch_persisted_hourly_run_end_to_end(self) -> None:
        run_start = datetime(2036, 1, 5, 0, 0, tzinfo=timezone.utc)
        run_end = run_start + timedelta(minutes=124)
        job_id = None
        run_id = None

        with transaction_scope() as connection:
            bar_repository = BarRepository()
            for offset in range(60):
                bar_time = run_start + timedelta(minutes=offset)
                bar_repository.upsert(
                    connection,
                    BarEvent.model_validate(
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                            "bar_interval": "1m",
                            "bar_time": bar_time.isoformat(),
                            "event_time": bar_time.isoformat(),
                            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                            "open": "100",
                            "high": "100",
                            "low": "100",
                            "close": "100",
                            "volume": "10",
                        }
                    ),
                )
            for offset in range(60, 120):
                bar_time = run_start + timedelta(minutes=offset)
                bar_repository.upsert(
                    connection,
                    BarEvent.model_validate(
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                            "bar_interval": "1m",
                            "bar_time": bar_time.isoformat(),
                            "event_time": bar_time.isoformat(),
                            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                            "open": "110",
                            "high": "110",
                            "low": "110",
                            "close": "110",
                            "volume": "10",
                        }
                    ),
                )
            for offset in range(120, 124):
                bar_time = run_start + timedelta(minutes=offset)
                bar_repository.upsert(
                    connection,
                    BarEvent.model_validate(
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                            "bar_interval": "1m",
                            "bar_time": bar_time.isoformat(),
                            "event_time": bar_time.isoformat(),
                            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                            "open": "90",
                            "high": "90",
                            "low": "90",
                            "close": "90",
                            "volume": "10",
                        }
                    ),
                )

        try:
            create_response = self.__class__.backtest_run_jobs_create_endpoint(
                BacktestRunStartRequest.model_validate(
                    {
                        "run_name": "btc_hourly_async_api_integration",
                        "session": {
                            "session_code": "bt_hourly_async_api_integration",
                            "environment": "backtest",
                            "account_code": "paper_main",
                            "strategy_code": "btc_hourly_momentum",
                            "strategy_version": "v1.0.0",
                            "exchange_code": "binance",
                            "trading_timezone": "UTC",
                            "universe": ["BTCUSDT_PERP"],
                            "risk_policy": {"policy_code": "perp_medium_v1"},
                        },
                        "start_time": run_start.isoformat(),
                        "end_time": run_end.isoformat(),
                        "initial_cash": "10000",
                        "assumption_bundle_code": "baseline_perp_research",
                        "assumption_bundle_version": "v1",
                        "strategy_params": {"short_window": 1, "long_window": 2, "target_qty": "1"},
                        "persist_signals": False,
                        "persist_debug_traces": True,
                        "debug_trace_level": "full_compressed",
                    }
                ),
                "Bearer developer:u_123:Alice",
            )
            self.assertTrue(create_response.success)
            job_id = create_response.data.job_id

            job_response = None
            for _ in range(100):
                job_response = self.__class__.backtest_run_job_detail_endpoint(job_id, "Bearer developer:u_123:Alice")
                self.assertTrue(job_response.success)
                if job_response.data.status == "completed":
                    break
                if job_response.data.status == "failed":
                    self.fail(job_response.data.error_message or "async backtest job failed")
                time.sleep(0.1)

            self.assertIsNotNone(job_response)
            assert job_response is not None
            self.assertEqual(job_response.data.status, "completed")
            self.assertEqual(job_response.data.summary.progress_pct, 100.0)
            self.assertEqual(job_response.data.summary.current_bar_time, run_end.isoformat())
            self.assertFalse(job_response.data.process_alive)

            run_id = job_response.data.summary.run_id
            self.assertIsNotNone(run_id)

            detail_response = self.__class__.backtest_run_detail_endpoint(run_id, "Bearer developer:u_123:Alice")
            timeseries_response = self.__class__.backtest_run_timeseries_endpoint(run_id, 200, "Bearer developer:u_123:Alice")

            self.assertTrue(detail_response.success)
            self.assertEqual(detail_response.data.run_id, run_id)
            self.assertEqual(detail_response.data.strategy_code, "btc_hourly_momentum")
            self.assertEqual(detail_response.data.session_code, "bt_hourly_async_api_integration")

            self.assertTrue(timeseries_response.success)
            self.assertGreater(len(timeseries_response.data.points), 100)
        finally:
            with transaction_scope() as cleanup_connection:
                if run_id is not None:
                    cleanup_connection.execute(
                        text("delete from backtest.simulated_fills where run_id = :run_id"),
                        {"run_id": run_id},
                    )
                    cleanup_connection.execute(
                        text("delete from backtest.simulated_orders where run_id = :run_id"),
                        {"run_id": run_id},
                    )
                    cleanup_connection.execute(
                        text("delete from backtest.performance_timeseries where run_id = :run_id"),
                        {"run_id": run_id},
                    )
                    cleanup_connection.execute(
                        text("delete from backtest.performance_summary where run_id = :run_id"),
                        {"run_id": run_id},
                    )
                    cleanup_connection.execute(
                        text("delete from backtest.debug_traces where run_id = :run_id"),
                        {"run_id": run_id},
                    )
                    cleanup_connection.execute(
                        text("delete from backtest.runs where run_id = :run_id"),
                        {"run_id": run_id},
                    )
                if job_id is not None:
                    cleanup_connection.execute(
                        text("delete from ops.ingestion_jobs where ingestion_job_id = :job_id"),
                        {"job_id": job_id},
                    )
                cleanup_connection.execute(
                    text(
                        """
                        delete from md.bars_1m
                        where instrument_id = (
                            select instrument.instrument_id
                            from ref.instruments instrument
                            join ref.exchanges exchange on exchange.exchange_id = instrument.exchange_id
                            where exchange.exchange_code = :exchange_code
                              and instrument.unified_symbol = :unified_symbol
                            limit 1
                        )
                          and bar_time between :start_time and :end_time
                        """
                    ),
                    {
                        "exchange_code": "binance",
                        "unified_symbol": "BTCUSDT_PERP",
                        "start_time": run_start,
                        "end_time": run_end,
                    },
                )

    def test_backtest_run_create_can_launch_persisted_breakout_run_end_to_end(self) -> None:
        original_transaction_scope = app_module.transaction_scope
        original_connection_scope = app_module.connection_scope
        connection = get_engine().connect()
        transaction = connection.begin()
        try:
            run_start = datetime(2036, 1, 1, 0, 0, tzinfo=timezone.utc)
            bar_repository = BarRepository()
            block_closes = ["100", "102", "104", "106", "112"]
            for block_index, close in enumerate(block_closes):
                block_start = run_start + timedelta(hours=block_index * 4)
                for minute in range(240):
                    bar_time = block_start + timedelta(minutes=minute)
                    bar_repository.upsert(
                        connection,
                        BarEvent.model_validate(
                            {
                                "exchange_code": "binance",
                                "unified_symbol": "BTCUSDT_PERP",
                                "bar_interval": "1m",
                                "bar_time": bar_time.isoformat(),
                                "event_time": bar_time.isoformat(),
                                "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                                "open": close,
                                "high": close,
                                "low": close,
                                "close": close,
                                "volume": "10",
                            }
                        ),
                    )
            final_bar_time = run_start + timedelta(hours=20, minutes=2)
            for offset in range(3):
                bar_time = run_start + timedelta(hours=20, minutes=offset)
                bar_repository.upsert(
                    connection,
                    BarEvent.model_validate(
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                            "bar_interval": "1m",
                            "bar_time": bar_time.isoformat(),
                            "event_time": bar_time.isoformat(),
                            "ingest_time": (bar_time + timedelta(seconds=1)).isoformat(),
                            "open": "112",
                            "high": "112",
                            "low": "112",
                            "close": "112",
                            "volume": "10",
                        }
                    ),
                )

            @contextmanager
            def _stub_transaction_scope():
                yield connection

            @contextmanager
            def _stub_connection_scope():
                yield connection

            app_module.transaction_scope = _stub_transaction_scope
            app_module.connection_scope = _stub_connection_scope

            create_response = self.__class__.backtest_runs_create_endpoint(
                BacktestRunStartRequest.model_validate(
                    {
                        "run_name": "btc_breakout_api_integration",
                        "session": {
                            "session_code": "bt_breakout_api_integration",
                            "environment": "backtest",
                            "account_code": "paper_main",
                            "strategy_code": "btc_4h_breakout_perp",
                            "strategy_version": "v0.1.0",
                            "exchange_code": "binance",
                            "trading_timezone": "UTC",
                            "universe": ["BTCUSDT_PERP"],
                            "risk_policy": {"policy_code": "perp_medium_v1"},
                        },
                        "start_time": run_start.isoformat(),
                        "end_time": final_bar_time.isoformat(),
                        "initial_cash": "10000",
                        "assumption_bundle_code": "breakout_perp_research",
                        "assumption_bundle_version": "v1",
                        "risk_overrides": {
                            "max_position_qty": "25",
                            "max_order_qty": "25",
                        },
                        "strategy_params": {
                            "trend_fast_ema": 3,
                            "trend_slow_ema": 5,
                            "breakout_lookback_bars": 3,
                            "atr_window": 3,
                            "risk_per_trade_pct": "0.01",
                            "volatility_floor_atr_pct": "0.005",
                            "volatility_ceiling_atr_pct": "0.20",
                        },
                    }
                ),
                "Bearer developer:u_123:Alice",
            )

            run_id = create_response.data.run_id
            detail_response = self.__class__.backtest_run_detail_endpoint(run_id, "Bearer developer:u_123:Alice")
            orders_response = self.__class__.backtest_run_orders_endpoint(run_id, 20, "Bearer developer:u_123:Alice")
            fills_response = self.__class__.backtest_run_fills_endpoint(run_id, 20, "Bearer developer:u_123:Alice")
            signals_response = self.__class__.backtest_run_signals_endpoint(run_id, 20, "Bearer developer:u_123:Alice")
        finally:
            app_module.transaction_scope = original_transaction_scope
            app_module.connection_scope = original_connection_scope
            transaction.rollback()
            connection.close()

        self.assertTrue(create_response.success)
        self.assertEqual(create_response.data.strategy_code, "btc_4h_breakout_perp")
        self.assertEqual(create_response.data.feature_input_version, "bars_perp_breakout_context_v1")
        self.assertEqual(create_response.data.strategy_params_json["trend_fast_ema"], 3)

        self.assertTrue(detail_response.success)
        self.assertEqual(detail_response.data.run_id, run_id)
        self.assertEqual(detail_response.data.strategy_code, "btc_4h_breakout_perp")

        self.assertTrue(orders_response.success)
        self.assertEqual(len(orders_response.data.orders), 1)
        self.assertEqual(orders_response.data.orders[0].side, "buy")

        self.assertTrue(fills_response.success)
        self.assertEqual(len(fills_response.data.fills), 1)
        self.assertGreater(Decimal(fills_response.data.fills[0].qty), Decimal("0"))

        self.assertTrue(signals_response.success)
        self.assertEqual(len(signals_response.data.signals), 1)
        self.assertEqual(signals_response.data.signals[0].signal_type, "entry")

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

    def test_backtest_run_create_rejects_missing_strategy_version_lookup(self) -> None:
        original_runner = app_module.BacktestRunnerSkeleton

        class StubRunner:
            def __init__(self, run_config):
                self.run_config = run_config

            def load_run_and_persist(self, connection, *, persist_signals=True, persist_debug_traces=False):
                raise LookupResolutionError(
                    "unknown strategy version for strategy_code=btc_sentiment_momentum strategy_version=v1.0.0"
                )

        app_module.BacktestRunnerSkeleton = StubRunner
        try:
            with self.assertRaises(HTTPException) as exc:
                self.__class__.backtest_runs_create_endpoint(
                    BacktestRunStartRequest.model_validate(
                        {
                            "run_name": "btc_missing_strategy_seed",
                            "session": {
                                "session_code": "bt_missing_strategy_seed",
                                "environment": "backtest",
                                "account_code": "paper_main",
                                "strategy_code": "btc_sentiment_momentum",
                                "strategy_version": "v1.0.0",
                                "exchange_code": "binance",
                                "universe": ["BTCUSDT_PERP"],
                            },
                            "start_time": "2026-03-01T00:00:00Z",
                            "end_time": "2026-03-31T00:00:00Z",
                            "initial_cash": "100000",
                            "assumption_bundle_code": "baseline_perp_sentiment_research",
                            "assumption_bundle_version": "v1",
                        }
                    ),
                    "Bearer developer:u_123:Alice",
                )
        finally:
            app_module.BacktestRunnerSkeleton = original_runner

        self.assertEqual(exc.exception.status_code, 422)
        self.assertEqual(exc.exception.detail["code"], "VALIDATION_ERROR")
        self.assertEqual(exc.exception.detail["details"]["field"], "strategy_version")

    def test_backtest_run_detail_endpoints_return_orders_fills_timeseries_and_signals(self) -> None:
        original_repository = app_module.BacktestRunRepository
        captured_debug_trace_filters: dict[str, object] = {}

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
                blocked_only: bool = False,
                risk_code: str | None = None,
                cooldown_state_only: bool = False,
                signals_only: bool = False,
                fills_only: bool = False,
                orders_only: bool = False,
            ):
                captured_debug_trace_filters.update(
                    {
                        "run_id": run_id,
                        "limit": limit,
                        "unified_symbol": unified_symbol,
                        "bar_time_from": bar_time_from,
                        "bar_time_to": bar_time_to,
                        "blocked_only": blocked_only,
                        "risk_code": risk_code,
                        "cooldown_state_only": cooldown_state_only,
                        "signals_only": signals_only,
                        "fills_only": fills_only,
                        "orders_only": orders_only,
                    }
                )
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
                        "investigation_anchors_json": [
                            {
                                "anchor_id": 71,
                                "debug_trace_id": 31,
                                "scenario_id": "scenario_alpha",
                                "expected_behavior": "expected long entry",
                                "observed_behavior": "entry delayed one bar",
                                "created_at": datetime.fromisoformat("2026-03-05T00:06:30+00:00"),
                                "updated_at": datetime.fromisoformat("2026-03-05T00:06:30+00:00"),
                            }
                        ],
                    }
                ]

        app_module.BacktestRunRepository = StubRepository
        try:
            orders_response = self.__class__.backtest_run_orders_endpoint(601, 50, "Bearer developer:u_123:Alice")
            fills_response = self.__class__.backtest_run_fills_endpoint(601, 50, "Bearer developer:u_123:Alice")
            timeseries_response = self.__class__.backtest_run_timeseries_endpoint(601, 120, "Bearer developer:u_123:Alice")
            signals_response = self.__class__.backtest_run_signals_endpoint(601, 50, "Bearer developer:u_123:Alice")
            debug_traces_response = self.__class__.backtest_run_debug_traces_endpoint(
                run_id=601,
                limit=150,
                unified_symbol="BTCUSDT_PERP",
                bar_time_from=datetime.fromisoformat("2026-03-05T00:00:00+00:00"),
                bar_time_to=datetime.fromisoformat("2026-03-05T01:00:00+00:00"),
                blocked_only=True,
                risk_code="cooldown_active",
                cooldown_state_only=True,
                signals_only=True,
                fills_only=False,
                orders_only=True,
                authorization="Bearer developer:u_123:Alice",
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
        self.assertEqual(debug_traces_response.data.traces[0].investigation_anchors[0].anchor_id, 71)
        self.assertEqual(
            debug_traces_response.data.traces[0].investigation_anchors[0].scenario_id,
            "scenario_alpha",
        )
        self.assertEqual(captured_debug_trace_filters["run_id"], 601)
        self.assertEqual(captured_debug_trace_filters["limit"], 150)
        self.assertEqual(captured_debug_trace_filters["unified_symbol"], "BTCUSDT_PERP")
        self.assertEqual(captured_debug_trace_filters["risk_code"], "cooldown_active")
        self.assertTrue(captured_debug_trace_filters["blocked_only"])
        self.assertTrue(captured_debug_trace_filters["cooldown_state_only"])
        self.assertTrue(captured_debug_trace_filters["signals_only"])
        self.assertFalse(captured_debug_trace_filters["fills_only"])
        self.assertTrue(captured_debug_trace_filters["orders_only"])

    def test_trace_investigation_anchor_endpoint_validates_run_trace_relationship(self) -> None:
        original_repository = app_module.BacktestRunRepository

        class StubRepository:
            def get_debug_trace_run_id(self, connection, *, debug_trace_id: int):
                return 777 if debug_trace_id == 31 else None

            def upsert_investigation_anchor(
                self,
                connection,
                *,
                debug_trace_id: int,
                scenario_id: str | None,
                expected_behavior: str | None,
                observed_behavior: str | None,
                actor_name: str,
            ):
                raise AssertionError("upsert_investigation_anchor should not be called for mismatched runs")

        app_module.BacktestRunRepository = StubRepository
        try:
            with self.assertRaises(HTTPException) as exc:
                self.__class__.backtest_trace_investigation_anchor_write_endpoint(
                    601,
                    31,
                    TraceInvestigationAnchorWriteRequest(expected_behavior="expected move"),
                    "Bearer developer:u_123:Alice",
                )
        finally:
            app_module.BacktestRunRepository = original_repository

        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(exc.exception.detail["code"], "NOT_FOUND")

    def test_trace_investigation_anchor_endpoint_returns_typed_anchor_resource(self) -> None:
        original_repository = app_module.BacktestRunRepository
        captured_call: dict[str, object] = {}

        class StubRepository:
            def get_debug_trace_run_id(self, connection, *, debug_trace_id: int):
                return 601

            def upsert_investigation_anchor(
                self,
                connection,
                *,
                debug_trace_id: int,
                scenario_id: str | None,
                expected_behavior: str | None,
                observed_behavior: str | None,
                actor_name: str,
            ):
                captured_call.update(
                    {
                        "debug_trace_id": debug_trace_id,
                        "scenario_id": scenario_id,
                        "expected_behavior": expected_behavior,
                        "observed_behavior": observed_behavior,
                        "actor_name": actor_name,
                    }
                )
                return {
                    "anchor_id": 71,
                    "debug_trace_id": debug_trace_id,
                    "scenario_id": scenario_id,
                    "expected_behavior": expected_behavior,
                    "observed_behavior": observed_behavior,
                    "created_at": datetime.fromisoformat("2026-03-05T00:06:30+00:00"),
                    "updated_at": datetime.fromisoformat("2026-03-05T00:06:30+00:00"),
                }

        app_module.BacktestRunRepository = StubRepository
        try:
            response = self.__class__.backtest_trace_investigation_anchor_write_endpoint(
                601,
                31,
                TraceInvestigationAnchorWriteRequest(
                    scenario_id=" scenario_alpha ",
                    expected_behavior=" expected long entry ",
                    observed_behavior="observed delayed entry",
                ),
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.BacktestRunRepository = original_repository

        self.assertTrue(response.success)
        self.assertEqual(response.data.anchor_id, 71)
        self.assertEqual(response.data.debug_trace_id, 31)
        self.assertEqual(response.data.scenario_id, "scenario_alpha")
        self.assertEqual(response.data.expected_behavior, "expected long entry")
        self.assertEqual(response.data.observed_behavior, "observed delayed entry")
        self.assertEqual(captured_call["actor_name"], "Alice")

    def test_trace_investigation_notes_endpoints_return_seeded_and_human_notes(self) -> None:
        original_service = app_module.TraceInvestigationNoteService

        class StubTraceInvestigationNoteService:
            def list_trace_notes(self, connection, *, run_id: int, debug_trace_id: int, actor_name: str):
                return (
                    {
                        "run_id": run_id,
                        "debug_trace_id": debug_trace_id,
                        "step_index": 7,
                        "unified_symbol": "BTCUSDT_PERP",
                        "bar_time": datetime.fromisoformat("2026-04-04T00:07:00+00:00"),
                    },
                    [
                        {
                            "annotation_id": 901,
                            "entity_type": "debug_trace",
                            "entity_id": str(debug_trace_id),
                            "annotation_type": "investigation",
                            "status": "draft",
                            "title": "Trace 7 investigation",
                            "summary": "System-seeded trace investigation draft.",
                            "note_source": "system",
                            "verification_state": "system_fact",
                            "verified_findings_json": [],
                            "open_questions_json": [],
                            "next_action": "Review trace evidence.",
                            "source_refs_json": {"run_id": run_id, "debug_trace_id": debug_trace_id},
                            "facts_snapshot_json": {"step_index": 7},
                            "created_by": "system",
                            "updated_by": "system",
                            "created_at": datetime.fromisoformat("2026-04-04T12:00:00+00:00"),
                            "updated_at": datetime.fromisoformat("2026-04-04T12:00:00+00:00"),
                        }
                    ],
                )

            def create_or_update_trace_note(
                self,
                connection,
                *,
                run_id: int,
                debug_trace_id: int,
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
                    "annotation_id": 902 if annotation_id is None else annotation_id,
                    "entity_type": "debug_trace",
                    "entity_id": str(debug_trace_id),
                    "annotation_type": annotation_type,
                    "status": status,
                    "title": title,
                    "summary": summary,
                    "note_source": note_source,
                    "verification_state": verification_state,
                    "verified_findings_json": verified_findings,
                    "open_questions_json": open_questions,
                    "next_action": next_action,
                    "source_refs_json": {"run_id": run_id, "debug_trace_id": debug_trace_id},
                    "facts_snapshot_json": {"step_index": 7},
                    "created_by": actor_name,
                    "updated_by": actor_name,
                    "created_at": datetime.fromisoformat("2026-04-04T12:05:00+00:00"),
                    "updated_at": datetime.fromisoformat("2026-04-04T12:05:00+00:00"),
                }

        app_module.TraceInvestigationNoteService = StubTraceInvestigationNoteService
        try:
            list_response = self.__class__.backtest_trace_notes_list_endpoint(
                601,
                31,
                "Bearer developer:u_123:Alice",
            )
            write_response = self.__class__.backtest_trace_notes_write_endpoint(
                601,
                31,
                TraceInvestigationNoteWriteRequest(
                    title="Expected vs observed note",
                    annotation_type="expected_vs_observed",
                    summary="Expected no entry; observed a delayed fill.",
                    verified_findings=["entry occurred one bar late"],
                    open_questions=["is context alignment lagging one bar"],
                    next_action="inspect context alignment around step 7",
                ),
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.TraceInvestigationNoteService = original_service

        self.assertTrue(list_response.success)
        self.assertEqual(list_response.data.run_id, 601)
        self.assertEqual(list_response.data.debug_trace_id, 31)
        self.assertEqual(list_response.data.step_index, 7)
        self.assertEqual(list_response.data.notes[0].note_source, "system")
        self.assertEqual(list_response.data.notes[0].verification_state, "system_fact")

        self.assertTrue(write_response.success)
        self.assertEqual(write_response.data.entity_type, "debug_trace")
        self.assertEqual(write_response.data.entity_id, "31")
        self.assertEqual(write_response.data.annotation_type, "expected_vs_observed")
        self.assertEqual(write_response.data.note_source, "human")
        self.assertEqual(write_response.data.verified_findings[0], "entry occurred one bar late")

    def test_expected_vs_observed_endpoint_returns_aggregated_run_view(self) -> None:
        original_service = app_module.TraceInvestigationNoteService

        class StubTraceInvestigationNoteService:
            def build_expected_vs_observed_overview(self, connection, *, run_id: int):
                return {
                    "run_id": run_id,
                    "run_name": "btc_trace_review",
                    "total_trace_count": 12,
                    "trace_count_with_notes": 3,
                    "total_note_count": 4,
                    "expected_vs_observed_note_count": 2,
                    "unresolved_note_count": 3,
                    "status_counts": {"draft": 1, "in_review": 2, "resolved": 1},
                    "annotation_type_counts": {"investigation": 2, "expected_vs_observed": 2},
                    "note_source_counts": {"system": 1, "human": 2, "agent": 1},
                    "scenario_counts": {"cooldown_guard": 2, "delayed_entry": 1},
                    "items": [
                        {
                            "annotation_id": 901,
                            "debug_trace_id": 31,
                            "step_index": 7,
                            "bar_time": "2026-04-04T00:07:00+00:00",
                            "unified_symbol": "BTCUSDT_PERP",
                            "annotation_type": "expected_vs_observed",
                            "status": "in_review",
                            "note_source": "human",
                            "verification_state": "verified",
                            "title": "Expected vs observed entry timing",
                            "summary": "Entry happened later than expected.",
                            "verified_findings": ["entry occurred one bar late"],
                            "open_questions": ["is context alignment lagging one bar"],
                            "next_action": "inspect context alignment",
                            "scenario_ids": ["delayed_entry"],
                            "source_refs_json": {"run_id": run_id, "debug_trace_id": 31},
                            "facts_snapshot_json": {"step_index": 7},
                            "created_at": "2026-04-04T12:05:00+00:00",
                            "updated_at": "2026-04-04T12:05:00+00:00",
                        }
                    ],
                }

        app_module.TraceInvestigationNoteService = StubTraceInvestigationNoteService
        try:
            response = self.__class__.backtest_expected_observed_endpoint(
                601,
                "Bearer developer:u_123:Alice",
            )
        finally:
            app_module.TraceInvestigationNoteService = original_service

        self.assertTrue(response.success)
        self.assertEqual(response.data.run_id, 601)
        self.assertEqual(response.data.total_note_count, 4)
        self.assertEqual(response.data.expected_vs_observed_note_count, 2)
        self.assertEqual(response.data.status_counts["in_review"], 2)
        self.assertEqual(response.data.items[0].debug_trace_id, 31)
        self.assertEqual(response.data.items[0].scenario_ids, ["delayed_entry"])

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
                            diagnostic_error_count=0,
                            diagnostic_warning_count=0,
                            blocked_intent_count=0,
                            block_counts_by_code={},
                            outcome_counts_by_code={},
                            state_snapshot={"policy_code": "perp_medium_v1"},
                            diagnostic_flag_codes=[],
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
                            diagnostic_error_count=0,
                            diagnostic_warning_count=2,
                            blocked_intent_count=3,
                            block_counts_by_code={"max_drawdown_pct_breach": 2, "cooldown_active": 1},
                            outcome_counts_by_code={"blocked": 3},
                            state_snapshot={"policy_code": "perp_medium_v1", "trading_timezone": "Asia/Taipei"},
                            diagnostic_flag_codes=["risk_blocks_present", "drawdown_guard_triggered"],
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
                    diagnostics_diffs=[
                        SimpleNamespace(
                            field_name="blocked_intent_count",
                            distinct_value_count=2,
                            values_by_run=[
                                SimpleNamespace(run_id=501, value=0),
                                SimpleNamespace(run_id=502, value=3),
                            ],
                        ),
                        SimpleNamespace(
                            field_name="diagnostic_flag_codes",
                            distinct_value_count=2,
                            values_by_run=[
                                SimpleNamespace(run_id=501, value=[]),
                                SimpleNamespace(run_id=502, value=["risk_blocks_present", "drawdown_guard_triggered"]),
                            ],
                        ),
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
        self.assertEqual(response.data.diagnostics_diffs[0].field_name, "blocked_intent_count")
        self.assertEqual(response.data.compared_runs[1].blocked_intent_count, 3)
        self.assertEqual(response.data.compared_runs[1].diagnostic_flag_codes[0], "risk_blocks_present")
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
