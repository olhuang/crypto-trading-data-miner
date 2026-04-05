from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


UTC = timezone.utc
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STATUS_FILE = REPO_ROOT / "tmp" / "binance_btc_history_backfill_status.json"
DEFAULT_LOG_FILE = REPO_ROOT / "tmp" / "binance_btc_history_backfill_latest.log"
BACKFILL_SCRIPT = REPO_ROOT / "scripts" / "binance_btc_history_backfill.py"


def _iso_now() -> str:
    return datetime.now(UTC).isoformat()


def _process_is_running(process_id: int | None) -> bool:
    if not process_id or process_id <= 0:
        return False
    try:
        os.kill(process_id, 0)
    except OSError:
        return False
    return True


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _recently_updated(payload: dict[str, Any], *, threshold: timedelta = timedelta(minutes=10)) -> bool:
    updated_at = _parse_iso_datetime(payload.get("updated_at"))
    if updated_at is None:
        return False
    return datetime.now(UTC) - updated_at <= threshold


def _default_status_payload(status_file: Path, log_file: Path) -> dict[str, Any]:
    return {
        "state": "not_started",
        "mode": None,
        "started_at": None,
        "updated_at": None,
        "requested_by": None,
        "process_id": None,
        "process_alive": False,
        "requested_window": None,
        "status_file": str(status_file),
        "log_file": str(log_file),
        "overall": {
            "tasks_total": 0,
            "tasks_completed": 0,
            "progress_pct": 0.0,
        },
        "datasets": {},
        "current_task": None,
        "last_result": None,
        "coverage_summary": None,
        "error": None,
    }


def load_binance_btc_backfill_status(
    *,
    status_file: Path = DEFAULT_STATUS_FILE,
    log_file: Path = DEFAULT_LOG_FILE,
) -> dict[str, Any]:
    if not status_file.exists():
        return _default_status_payload(status_file, log_file)

    try:
        payload = json.loads(status_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        payload = _default_status_payload(status_file, log_file)
        payload["state"] = "status_unreadable"
        payload["updated_at"] = _iso_now()
        payload["error"] = {
            "code": "STATUS_FILE_UNREADABLE",
            "message": "backfill status file could not be decoded cleanly",
        }
    payload.setdefault("state", "unknown")
    payload.setdefault("mode", None)
    payload.setdefault("started_at", None)
    payload.setdefault("updated_at", None)
    payload.setdefault("requested_by", None)
    payload.setdefault("process_id", None)
    payload.setdefault("requested_window", None)
    payload.setdefault("status_file", str(status_file))
    payload.setdefault("log_file", str(log_file))
    payload.setdefault("overall", {"tasks_total": 0, "tasks_completed": 0, "progress_pct": 0.0})
    payload.setdefault("datasets", {})
    payload.setdefault("current_task", None)
    payload.setdefault("last_result", None)
    payload.setdefault("coverage_summary", None)
    payload.setdefault("error", None)
    payload["process_alive"] = _process_is_running(payload.get("process_id"))
    if payload.get("state") == "running" and not payload["process_alive"]:
        payload["state"] = "stale"
        payload["error"] = payload.get("error") or {
            "code": "STALE_STATUS",
            "message": "backfill status file still reports running, but the recorded process is no longer alive",
        }
    return payload


def trigger_binance_btc_incremental_backfill(
    requested_by: str,
    *,
    status_file: Path = DEFAULT_STATUS_FILE,
    log_file: Path = DEFAULT_LOG_FILE,
) -> dict[str, Any]:
    current_status = load_binance_btc_backfill_status(status_file=status_file, log_file=log_file)
    if current_status.get("state") == "running" and (
        current_status.get("process_alive") or _recently_updated(current_status)
    ):
        return {
            "job_id": current_status.get("process_id"),
            "status": "already_running",
            "already_running": True,
            "status_file": str(status_file),
            "log_file": str(log_file),
            "process_alive": bool(current_status.get("process_alive")),
        }

    status_file.parent.mkdir(parents=True, exist_ok=True)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(BACKFILL_SCRIPT),
        "--status-file",
        str(status_file),
        "--requested-by",
        requested_by,
        "--incremental",
    ]

    popen_kwargs: dict[str, Any] = {
        "cwd": str(REPO_ROOT),
        "stdin": subprocess.DEVNULL,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        popen_kwargs["start_new_session"] = True

    with log_file.open("ab") as log_handle:
        process = subprocess.Popen(command, stdout=log_handle, **popen_kwargs)

    return {
        "job_id": process.pid,
        "status": "started",
        "already_running": False,
        "status_file": str(status_file),
        "log_file": str(log_file),
        "process_alive": True,
        "started_at": _iso_now(),
    }
