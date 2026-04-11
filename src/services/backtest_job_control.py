from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock, Thread
import time
from typing import Any

from backtest.assumption_registry import UnknownAssumptionBundleError
from backtest.risk_registry import UnknownRiskPolicyError
from backtest.runner import BacktestRunCancelledError, BacktestRunnerSkeleton
from models.backtest import BacktestRunConfig
from storage.db import transaction_scope
from storage.lookups import LookupResolutionError
from storage.repositories.ops import IngestionJobRepository
from strategy import UnknownStrategyError


_ACTIVE_THREADS: dict[int, Thread] = {}
_ACTIVE_THREADS_LOCK = Lock()
_CANCEL_REQUESTED_JOB_IDS: set[int] = set()
_CANCEL_REQUESTED_LOCK = Lock()
UTC = timezone.utc
STALE_JOB_THRESHOLD = timedelta(seconds=30)


@dataclass(slots=True)
class BacktestRunJobResult:
    job_id: int
    status: str


def start_backtest_run_job(
    run_config: BacktestRunConfig,
    *,
    requested_by: str,
    persist_signals: bool = True,
    persist_debug_traces: bool = False,
) -> BacktestRunJobResult:
    BacktestRunnerSkeleton(run_config)
    with transaction_scope() as connection:
        repository = IngestionJobRepository()
        job_id = repository.insert_requested_by(
            connection,
            requested_by=requested_by,
            service_name="backtest_runner",
            data_type="backtest_run",
            status="queued",
            exchange_code=run_config.session.exchange_code,
            unified_symbol=run_config.session.universe[0] if run_config.session.universe else None,
            schedule_type="manual",
            window_start=run_config.start_time,
            window_end=run_config.end_time,
            metadata_json=_build_job_metadata(
                run_config,
                requested_by=requested_by,
                status="queued",
                persist_signals=persist_signals,
                persist_debug_traces=persist_debug_traces,
            ),
        )

    thread = Thread(
        target=_run_backtest_job,
        args=(job_id, run_config, requested_by, persist_signals, persist_debug_traces),
        name=f"backtest-job:{job_id}",
        daemon=True,
    )
    with _ACTIVE_THREADS_LOCK:
        _ACTIVE_THREADS[job_id] = thread
    thread.start()
    return BacktestRunJobResult(job_id=job_id, status="queued")


def get_backtest_run_job(job_id: int) -> dict[str, Any] | None:
    with transaction_scope() as connection:
        repository = IngestionJobRepository()
        job = repository.get_job(connection, job_id)
        if job is not None and _job_should_be_marked_stale(job):
            stale_message = "job remained queued/running but no active worker heartbeat was observed"
            repository.finish_job(
                connection,
                job_id,
                status="stale",
                finished_at=datetime.now(UTC),
                error_message=stale_message,
                metadata_json=_merge_job_metadata(
                    job.get("metadata_json"),
                    status="stale",
                    error_message=stale_message,
                ),
            )
            job = repository.get_job(connection, job_id)
    if job is None:
        return None
    return _normalize_job_payload(job)


def cancel_backtest_run_job(job_id: int, *, requested_by: str) -> BacktestRunJobResult | None:
    with transaction_scope() as connection:
        repository = IngestionJobRepository()
        job = repository.get_job(connection, job_id)
        if job is None or str(job.get("data_type")) != "backtest_run":
            return None
        current_status = str(job.get("status") or "").lower()
        if current_status in {"completed", "failed", "stale", "canceled"}:
            return BacktestRunJobResult(job_id=job_id, status=current_status)

        metadata = dict(job.get("metadata_json") or {})
        metadata["cancel_requested"] = True
        metadata["cancel_requested_by"] = requested_by
        metadata["cancel_requested_at"] = datetime.now(UTC).isoformat()
        metadata["status"] = "cancel_requested"
        metadata["heartbeat_at"] = datetime.now(UTC).isoformat()
        repository.finish_job(
            connection,
            job_id,
            status="cancel_requested",
            finished_at=None,
            error_message=None,
            metadata_json=metadata,
        )
    with _CANCEL_REQUESTED_LOCK:
        _CANCEL_REQUESTED_JOB_IDS.add(job_id)
    return BacktestRunJobResult(job_id=job_id, status="cancel_requested")


def _run_backtest_job(
    job_id: int,
    run_config: BacktestRunConfig,
    requested_by: str,
    persist_signals: bool,
    persist_debug_traces: bool,
) -> None:
    try:
        if _job_cancel_is_requested(job_id):
            raise BacktestRunCancelledError("async backtest job was canceled before execution started")
        with transaction_scope() as connection:
            repository = IngestionJobRepository()
            repository.finish_job(
                connection,
                job_id,
                status="running",
                finished_at=None,
                metadata_json=_build_job_metadata(
                    run_config,
                    requested_by=requested_by,
                    status="running",
                    persist_signals=persist_signals,
                    persist_debug_traces=persist_debug_traces,
                    progress_pct=0.0,
                ),
            )

        runner = BacktestRunnerSkeleton(run_config)
        progress_state = {"last_emit": 0.0}

        def _report_progress(bar_time: datetime) -> None:
            if _job_cancel_is_requested(job_id):
                raise BacktestRunCancelledError("async backtest job was canceled")
            now = time.monotonic()
            if now - progress_state["last_emit"] < 0.75 and bar_time < run_config.end_time:
                return
            progress_state["last_emit"] = now
            progress_pct = _progress_pct_for_bar_time(
                start_time=run_config.start_time,
                end_time=run_config.end_time,
                current_bar_time=bar_time,
            )
            with transaction_scope() as progress_connection:
                IngestionJobRepository().finish_job(
                    progress_connection,
                    job_id,
                    status="running",
                    finished_at=None,
                    metadata_json=_build_job_metadata(
                        run_config,
                        requested_by=requested_by,
                        status="running",
                        persist_signals=persist_signals,
                        persist_debug_traces=persist_debug_traces,
                        progress_pct=progress_pct,
                        current_bar_time=bar_time,
                    ),
                )

        with transaction_scope() as connection:
            persisted = runner.load_run_and_persist(
                connection,
                persist_signals=persist_signals,
                persist_debug_traces=persist_debug_traces,
                progress_callback=_report_progress,
            )
            final_metadata = _build_job_metadata(
                run_config,
                requested_by=requested_by,
                status="completed",
                persist_signals=persist_signals,
                persist_debug_traces=persist_debug_traces,
                progress_pct=100.0,
                current_bar_time=run_config.end_time,
                run_id=persisted.run_id,
                debug_trace_count=persisted.loop_result.debug_trace_count,
            )
            IngestionJobRepository().finish_job(
                connection,
                job_id,
                status="completed",
                finished_at=datetime.now(timezone.utc),
                records_written=persisted.loop_result.debug_trace_count,
                metadata_json=final_metadata,
            )
    except BacktestRunCancelledError as exc:
        _mark_job_canceled(job_id, run_config, requested_by, persist_signals, persist_debug_traces, str(exc))
    except (
        UnknownStrategyError,
        UnknownRiskPolicyError,
        UnknownAssumptionBundleError,
        LookupResolutionError,
        ValueError,
    ) as exc:
        _mark_job_failed(job_id, run_config, requested_by, persist_signals, persist_debug_traces, exc)
    except Exception as exc:  # noqa: BLE001
        _mark_job_failed(job_id, run_config, requested_by, persist_signals, persist_debug_traces, exc)
    finally:
        with _ACTIVE_THREADS_LOCK:
            _ACTIVE_THREADS.pop(job_id, None)
        with _CANCEL_REQUESTED_LOCK:
            _CANCEL_REQUESTED_JOB_IDS.discard(job_id)


def _mark_job_failed(
    job_id: int,
    run_config: BacktestRunConfig,
    requested_by: str,
    persist_signals: bool,
    persist_debug_traces: bool,
    error: Exception,
) -> None:
    with transaction_scope() as connection:
        IngestionJobRepository().finish_job(
            connection,
            job_id,
            status="failed",
            finished_at=datetime.now(timezone.utc),
            error_message=str(error),
            metadata_json=_build_job_metadata(
                run_config,
                requested_by=requested_by,
                status="failed",
                persist_signals=persist_signals,
                persist_debug_traces=persist_debug_traces,
                error_message=str(error),
            ),
        )


def _mark_job_canceled(
    job_id: int,
    run_config: BacktestRunConfig,
    requested_by: str,
    persist_signals: bool,
    persist_debug_traces: bool,
    reason: str,
) -> None:
    with transaction_scope() as connection:
        IngestionJobRepository().finish_job(
            connection,
            job_id,
            status="canceled",
            finished_at=datetime.now(UTC),
            error_message=reason,
            metadata_json=_build_job_metadata(
                run_config,
                requested_by=requested_by,
                status="canceled",
                persist_signals=persist_signals,
                persist_debug_traces=persist_debug_traces,
                error_message=reason,
            ),
        )


def _build_job_metadata(
    run_config: BacktestRunConfig,
    *,
    requested_by: str,
    status: str,
    persist_signals: bool,
    persist_debug_traces: bool,
    progress_pct: float = 0.0,
    current_bar_time: datetime | None = None,
    run_id: int | None = None,
    debug_trace_count: int | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
        "job_kind": "backtest_run",
        "requested_by": requested_by,
        "status": status,
        "run_name": run_config.run_name,
        "strategy_code": run_config.session.strategy_code,
        "strategy_version": run_config.session.strategy_version,
        "exchange_code": run_config.session.exchange_code,
        "unified_symbol": run_config.session.universe[0] if run_config.session.universe else None,
        "start_time": run_config.start_time.isoformat(),
        "end_time": run_config.end_time.isoformat(),
        "progress_pct": progress_pct,
        "current_bar_time": current_bar_time.isoformat() if current_bar_time is not None else None,
        "persist_signals": persist_signals,
        "persist_debug_traces": persist_debug_traces,
        "heartbeat_at": datetime.now(UTC).isoformat(),
    }
    if run_id is not None:
        metadata["run_id"] = run_id
    if debug_trace_count is not None:
        metadata["debug_trace_count"] = debug_trace_count
    if error_message:
        metadata["error_message"] = error_message
    with _CANCEL_REQUESTED_LOCK:
        if run_id is None and metadata.get("status") in {"queued", "running", "cancel_requested"}:
            metadata["cancel_requested"] = False
    return metadata


def _merge_job_metadata(
    metadata_json: dict[str, Any] | None,
    *,
    status: str,
    error_message: str | None = None,
) -> dict[str, Any]:
    metadata = dict(metadata_json or {})
    metadata["status"] = status
    metadata["heartbeat_at"] = datetime.now(UTC).isoformat()
    if error_message:
        metadata["error_message"] = error_message
    return metadata


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _job_should_be_marked_stale(job: dict[str, Any]) -> bool:
    status = str(job.get("status") or "").lower()
    if status not in {"queued", "running", "cancel_requested"}:
        return False
    with _ACTIVE_THREADS_LOCK:
        thread = _ACTIVE_THREADS.get(int(job["job_id"]))
    if thread and thread.is_alive():
        return False
    metadata = dict(job.get("metadata_json") or {})
    heartbeat_at = _parse_iso_datetime(metadata.get("heartbeat_at"))
    if heartbeat_at is None:
        heartbeat_at = _parse_iso_datetime(job.get("started_at"))
    if heartbeat_at is None:
        return False
    return datetime.now(UTC) - heartbeat_at > STALE_JOB_THRESHOLD


def _job_cancel_is_requested(job_id: int) -> bool:
    with _CANCEL_REQUESTED_LOCK:
        if job_id in _CANCEL_REQUESTED_JOB_IDS:
            return True
    with transaction_scope() as connection:
        job = IngestionJobRepository().get_job(connection, job_id)
    if job is None:
        return False
    metadata = dict(job.get("metadata_json") or {})
    return bool(metadata.get("cancel_requested")) or str(job.get("status") or "").lower() == "cancel_requested"


def _normalize_job_payload(job: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(job.get("metadata_json") or {})
    with _ACTIVE_THREADS_LOCK:
        thread = _ACTIVE_THREADS.get(int(job["job_id"]))
    current_bar_time = metadata.get("current_bar_time")
    progress_pct = float(metadata.get("progress_pct") or 0.0)
    start_time = metadata.get("start_time")
    end_time = metadata.get("end_time")
    return {
        **job,
        "process_alive": bool(thread and thread.is_alive()),
        "metadata_json": metadata,
        "summary": {
            "run_id": metadata.get("run_id"),
            "progress_pct": progress_pct,
            "current_bar_time": current_bar_time,
            "start_time": start_time,
            "end_time": end_time,
            "debug_trace_count": metadata.get("debug_trace_count"),
        },
    }


def _progress_pct_for_bar_time(*, start_time: datetime, end_time: datetime, current_bar_time: datetime) -> float:
    total_seconds = max((end_time - start_time).total_seconds(), 0.0)
    if total_seconds <= 0:
        return 100.0
    completed_seconds = min(max((current_bar_time - start_time).total_seconds(), 0.0), total_seconds)
    return round((completed_seconds / total_seconds) * 100.0, 2)
