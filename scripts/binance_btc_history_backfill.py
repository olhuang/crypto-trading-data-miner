from __future__ import annotations

import argparse
import calendar
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from jobs.backfill_bars import run_bar_backfill
from jobs.refresh_market_snapshots import run_market_snapshot_refresh
from storage.db import connection_scope
from storage.lookups import resolve_instrument_id


UTC = timezone.utc
DEFAULT_STATUS_FILE = REPO_ROOT / "tmp" / "binance_btc_history_backfill_status.json"


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    dataset_key: str
    label: str
    symbol: str
    unified_symbol: str
    task_kind: str
    chunk_months: int = 1


@dataclass(frozen=True, slots=True)
class ChunkTask:
    dataset_key: str
    label: str
    symbol: str
    unified_symbol: str
    task_kind: str
    chunk_index: int
    chunk_total: int
    start_time: datetime
    end_time: datetime


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Backfill Binance BTCUSDT spot/perp history from 2020-01-01 to YTD. "
            "If a dataset was not yet listed during early windows, the script continues "
            "and the final coverage summary reflects the actual available start time."
        )
    )
    parser.add_argument("--start-date", default="2020-01-01", help="UTC date in YYYY-MM-DD format")
    parser.add_argument(
        "--end-date",
        default=None,
        help="UTC date in YYYY-MM-DD format. Defaults to current UTC timestamp when omitted.",
    )
    parser.add_argument(
        "--status-file",
        default=str(DEFAULT_STATUS_FILE),
        help="JSON file updated after every chunk with current progress and final coverage summary.",
    )
    parser.add_argument(
        "--requested-by",
        default="binance_btc_history_backfill_script",
        help="requested_by value stored on ingestion jobs created by this script.",
    )
    return parser.parse_args()


def parse_utc_date(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def utc_now() -> datetime:
    return datetime.now(UTC)


def add_months(value: datetime, months: int) -> datetime:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return datetime(year, month, day, value.hour, value.minute, value.second, value.microsecond, tzinfo=value.tzinfo)


def build_month_windows(start_time: datetime, end_time: datetime, *, chunk_months: int) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    cursor = start_time
    while cursor <= end_time:
        next_cursor = add_months(cursor, chunk_months)
        window_end = min(next_cursor - timedelta(milliseconds=1), end_time)
        windows.append((cursor, window_end))
        cursor = next_cursor
    return windows


def build_dataset_specs() -> list[DatasetSpec]:
    return [
        DatasetSpec(
            dataset_key="btc_spot_bars_1m",
            label="BTCUSDT_SPOT bars_1m",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_SPOT",
            task_kind="bars",
        ),
        DatasetSpec(
            dataset_key="btc_perp_bars_1m",
            label="BTCUSDT_PERP bars_1m",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="bars",
        ),
        DatasetSpec(
            dataset_key="btc_perp_snapshot_history",
            label="BTCUSDT_PERP funding/open_interest/mark/index",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="perp_snapshots",
        ),
    ]


def build_chunk_tasks(start_time: datetime, end_time: datetime) -> list[ChunkTask]:
    tasks: list[ChunkTask] = []
    for spec in build_dataset_specs():
        windows = build_month_windows(start_time, end_time, chunk_months=spec.chunk_months)
        for index, (window_start, window_end) in enumerate(windows, start=1):
            tasks.append(
                ChunkTask(
                    dataset_key=spec.dataset_key,
                    label=spec.label,
                    symbol=spec.symbol,
                    unified_symbol=spec.unified_symbol,
                    task_kind=spec.task_kind,
                    chunk_index=index,
                    chunk_total=len(windows),
                    start_time=window_start,
                    end_time=window_end,
                )
            )
    return tasks


def isoformat_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def make_dataset_status(tasks: list[ChunkTask]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for task in tasks:
        grouped.setdefault(
            task.dataset_key,
            {
                "dataset_key": task.dataset_key,
                "label": task.label,
                "unified_symbol": task.unified_symbol,
                "chunk_total": task.chunk_total,
                "chunks_completed": 0,
                "rows_written": 0,
                "first_nonzero_window_start": None,
                "last_nonzero_window_end": None,
                "last_result": None,
            },
        )
    return grouped


def write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def coverage_row(connection, *, exchange_code: str, unified_symbol: str, table_name: str, time_column: str) -> dict[str, Any]:
    instrument_id = resolve_instrument_id(connection, exchange_code, unified_symbol)
    row = connection.execute(
        text(
            f"""
            select
                count(*) as row_count,
                min({time_column}) as available_from,
                max({time_column}) as available_to
            from {table_name}
            where instrument_id = :instrument_id
            """
        ),
        {"instrument_id": instrument_id},
    ).mappings().one()
    return {
        "table_name": table_name,
        "time_column": time_column,
        "instrument_id": instrument_id,
        "row_count": int(row["row_count"] or 0),
        "available_from": isoformat_or_none(row["available_from"]),
        "available_to": isoformat_or_none(row["available_to"]),
    }


def collect_coverage_summary() -> dict[str, Any]:
    with connection_scope() as connection:
        return {
            "BTCUSDT_SPOT": {
                "bars_1m": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_SPOT",
                    table_name="md.bars_1m",
                    time_column="bar_time",
                ),
            },
            "BTCUSDT_PERP": {
                "bars_1m": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.bars_1m",
                    time_column="bar_time",
                ),
                "funding_rates": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.funding_rates",
                    time_column="funding_time",
                ),
                "open_interest": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.open_interest",
                    time_column="ts",
                ),
                "mark_prices": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.mark_prices",
                    time_column="ts",
                ),
                "index_prices": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.index_prices",
                    time_column="ts",
                ),
            },
        }


def initial_status_payload(*, start_time: datetime, end_time: datetime, status_path: Path, tasks: list[ChunkTask]) -> dict[str, Any]:
    return {
        "state": "running",
        "started_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
        "requested_window": {
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
        "status_file": str(status_path),
        "overall": {
            "tasks_total": len(tasks),
            "tasks_completed": 0,
            "progress_pct": 0.0,
        },
        "datasets": make_dataset_status(tasks),
        "current_task": None,
        "last_result": None,
        "coverage_summary": None,
        "error": None,
    }


def progress_pct(completed: int, total: int) -> float:
    if total <= 0:
        return 100.0
    return round(completed * 100.0 / total, 2)


def format_chunk_window(task: ChunkTask) -> str:
    return f"{task.start_time.isoformat()} -> {task.end_time.isoformat()}"


def execute_task(task: ChunkTask, *, requested_by: str) -> dict[str, Any]:
    if task.task_kind == "bars":
        result = run_bar_backfill(
            symbol=task.symbol,
            unified_symbol=task.unified_symbol,
            interval="1m",
            start_time=task.start_time,
            end_time=task.end_time,
            requested_by=requested_by,
            exchange_code="binance",
        )
        return {
            "dataset_key": task.dataset_key,
            "label": task.label,
            "status": result.status,
            "rows_written": result.rows_written,
            "ingestion_job_id": result.ingestion_job_id,
            "window_start": task.start_time.isoformat(),
            "window_end": task.end_time.isoformat(),
        }

    result = run_market_snapshot_refresh(
        symbol=task.symbol,
        unified_symbol=task.unified_symbol,
        requested_by=requested_by,
        exchange_code="binance",
        funding_start_time=task.start_time,
        funding_end_time=task.end_time,
        history_start_time=task.start_time,
        history_end_time=task.end_time,
        open_interest_period="5m",
        price_interval="1m",
        include_funding=True,
        include_open_interest=True,
        include_mark_price=True,
        include_index_price=True,
    )
    return {
        "dataset_key": task.dataset_key,
        "label": task.label,
        "status": result.status,
        "rows_written": result.records_written,
        "history_rows_written": result.history_rows_written,
        "ingestion_job_id": result.ingestion_job_id,
        "window_start": task.start_time.isoformat(),
        "window_end": task.end_time.isoformat(),
    }


def update_dataset_status(status_payload: dict[str, Any], task: ChunkTask, result: dict[str, Any]) -> None:
    dataset_status = status_payload["datasets"][task.dataset_key]
    dataset_status["chunks_completed"] += 1
    dataset_status["rows_written"] += int(result.get("rows_written", 0))
    dataset_status["last_result"] = result
    if int(result.get("rows_written", 0)) > 0:
        if dataset_status["first_nonzero_window_start"] is None:
            dataset_status["first_nonzero_window_start"] = task.start_time.isoformat()
        dataset_status["last_nonzero_window_end"] = task.end_time.isoformat()


def print_status_line(prefix: str, task: ChunkTask, *, task_number: int, total_tasks: int) -> None:
    print(f"{prefix} [{task_number}/{total_tasks}] {task.label} | chunk {task.chunk_index}/{task.chunk_total} | {format_chunk_window(task)}")


def main() -> int:
    args = parse_args()
    start_time = parse_utc_date(args.start_date)
    end_time = parse_utc_date(args.end_date) if args.end_date else utc_now()
    if end_time < start_time:
        raise ValueError("end_date must be greater than or equal to start_date")

    status_path = Path(args.status_file)
    tasks = build_chunk_tasks(start_time, end_time)
    status_payload = initial_status_payload(start_time=start_time, end_time=end_time, status_path=status_path, tasks=tasks)
    write_status(status_path, status_payload)

    print(f"Status file: {status_path}")
    print(f"Requested window: {start_time.isoformat()} -> {end_time.isoformat()}")
    print(f"Total chunk tasks: {len(tasks)}")

    try:
        for task_number, task in enumerate(tasks, start=1):
            status_payload["current_task"] = {
                "task_number": task_number,
                "task_total": len(tasks),
                "dataset_key": task.dataset_key,
                "label": task.label,
                "chunk_index": task.chunk_index,
                "chunk_total": task.chunk_total,
                "window_start": task.start_time.isoformat(),
                "window_end": task.end_time.isoformat(),
            }
            status_payload["updated_at"] = utc_now().isoformat()
            write_status(status_path, status_payload)

            print_status_line("START", task, task_number=task_number, total_tasks=len(tasks))
            result = execute_task(task, requested_by=args.requested_by)
            print(
                "DONE  "
                f"[{task_number}/{len(tasks)}] {task.label} | rows_written={result.get('rows_written', 0)} | status={result['status']}"
            )

            status_payload["overall"]["tasks_completed"] = task_number
            status_payload["overall"]["progress_pct"] = progress_pct(task_number, len(tasks))
            status_payload["last_result"] = result
            status_payload["updated_at"] = utc_now().isoformat()
            update_dataset_status(status_payload, task, result)
            write_status(status_path, status_payload)

        status_payload["coverage_summary"] = collect_coverage_summary()
        status_payload["state"] = "finished"
        status_payload["current_task"] = None
        status_payload["updated_at"] = utc_now().isoformat()
        write_status(status_path, status_payload)

        print("")
        print("Final coverage summary:")
        print(json.dumps(status_payload["coverage_summary"], indent=2, ensure_ascii=False))
        print("")
        print(f"Finished. Status file written to {status_path}")
        return 0
    except Exception as exc:
        status_payload["state"] = "failed"
        status_payload["error"] = {
            "message": str(exc),
            "failed_at": utc_now().isoformat(),
        }
        status_payload["updated_at"] = utc_now().isoformat()
        write_status(status_path, status_payload)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
