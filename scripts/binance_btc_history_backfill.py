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
OPEN_INTEREST_LOOKBACK_DAYS = 30


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    dataset_key: str
    label: str
    symbol: str
    unified_symbol: str
    task_kind: str
    chunk_months: int = 1
    table_name: str | None = None
    time_column: str | None = None


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
    parser.add_argument(
        "--resume-from-status",
        action="store_true",
        help="Resume from the existing status file by skipping already completed chunk tasks.",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Use DB coverage as the source of truth and only catch up each dataset from its latest stored timestamp onward.",
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
            table_name="md.bars_1m",
            time_column="bar_time",
        ),
        DatasetSpec(
            dataset_key="btc_perp_bars_1m",
            label="BTCUSDT_PERP bars_1m",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="bars",
            table_name="md.bars_1m",
            time_column="bar_time",
        ),
        DatasetSpec(
            dataset_key="btc_perp_snapshot_history",
            label="BTCUSDT_PERP funding/open_interest/mark/index",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="perp_snapshots",
        ),
    ]


def build_incremental_dataset_specs() -> list[DatasetSpec]:
    return [
        DatasetSpec(
            dataset_key="btc_spot_bars_1m",
            label="BTCUSDT_SPOT bars_1m",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_SPOT",
            task_kind="bars",
            table_name="md.bars_1m",
            time_column="bar_time",
        ),
        DatasetSpec(
            dataset_key="btc_perp_bars_1m",
            label="BTCUSDT_PERP bars_1m",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="bars",
            table_name="md.bars_1m",
            time_column="bar_time",
        ),
        DatasetSpec(
            dataset_key="btc_perp_funding_rates",
            label="BTCUSDT_PERP funding_rates",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="funding_rates",
            table_name="md.funding_rates",
            time_column="funding_time",
        ),
        DatasetSpec(
            dataset_key="btc_perp_open_interest",
            label="BTCUSDT_PERP open_interest",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="open_interest",
            table_name="md.open_interest",
            time_column="ts",
        ),
        DatasetSpec(
            dataset_key="btc_perp_mark_prices",
            label="BTCUSDT_PERP mark_prices",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="mark_prices",
            table_name="md.mark_prices",
            time_column="ts",
        ),
        DatasetSpec(
            dataset_key="btc_perp_index_prices",
            label="BTCUSDT_PERP index_prices",
            symbol="BTCUSDT",
            unified_symbol="BTCUSDT_PERP",
            task_kind="index_prices",
            table_name="md.index_prices",
            time_column="ts",
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


def make_dataset_status(dataset_specs: list[DatasetSpec], tasks: list[ChunkTask]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    chunk_totals: dict[str, int] = {}
    for task in tasks:
        chunk_totals[task.dataset_key] = chunk_totals.get(task.dataset_key, 0) + 1

    for spec in dataset_specs:
        grouped[spec.dataset_key] = {
            "dataset_key": spec.dataset_key,
            "label": spec.label,
            "unified_symbol": spec.unified_symbol,
            "chunk_total": chunk_totals.get(spec.dataset_key, 0),
            "chunks_completed": 0,
            "rows_written": 0,
            "first_nonzero_window_start": None,
            "last_nonzero_window_end": None,
            "last_result": None,
        }
    return grouped


def write_status(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def coverage_row(
    connection,
    *,
    exchange_code: str,
    unified_symbol: str,
    table_name: str,
    time_column: str,
    safe_upper_bound: datetime | None = None,
) -> dict[str, Any]:
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
    safe_latest_to = None
    future_row_count = 0
    if safe_upper_bound is not None:
        safe_latest_to = connection.execute(
            text(
                f"""
                select max({time_column}) as safe_latest_to
                from {table_name}
                where instrument_id = :instrument_id
                  and {time_column} <= :safe_upper_bound
                """
            ),
            {"instrument_id": instrument_id, "safe_upper_bound": safe_upper_bound},
        ).scalar_one_or_none()
        future_row_count = int(
            connection.execute(
                text(
                    f"""
                    select count(*) as future_row_count
                    from {table_name}
                    where instrument_id = :instrument_id
                      and {time_column} > :safe_upper_bound
                    """
                ),
                {"instrument_id": instrument_id, "safe_upper_bound": safe_upper_bound},
            ).scalar_one()
        )

    payload = {
        "table_name": table_name,
        "time_column": time_column,
        "instrument_id": instrument_id,
        "row_count": int(row["row_count"] or 0),
        "available_from": isoformat_or_none(row["available_from"]),
        "available_to": isoformat_or_none(row["available_to"]),
    }
    if safe_upper_bound is not None:
        payload["safe_upper_bound"] = safe_upper_bound.isoformat()
        payload["safe_available_to"] = isoformat_or_none(safe_latest_to)
        payload["future_row_count"] = future_row_count
    return payload


def parse_iso_datetime_or_none(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def next_start_from_coverage(spec: DatasetSpec, *, default_start: datetime, coverage: dict[str, Any]) -> datetime:
    available_to = parse_iso_datetime_or_none(coverage.get("safe_available_to") or coverage.get("available_to"))
    if available_to is None:
        next_start = default_start
    else:
        next_start = available_to + timedelta(milliseconds=1)

    if spec.task_kind == "open_interest":
        next_start = max(next_start, open_interest_available_from())
    return next_start


def build_incremental_tasks(start_time: datetime, end_time: datetime) -> tuple[list[DatasetSpec], list[ChunkTask]]:
    dataset_specs = build_incremental_dataset_specs()
    tasks: list[ChunkTask] = []
    with connection_scope() as connection:
        for spec in dataset_specs:
            assert spec.table_name is not None
            assert spec.time_column is not None
            coverage = coverage_row(
                connection,
                exchange_code="binance",
                unified_symbol=spec.unified_symbol,
                table_name=spec.table_name,
                time_column=spec.time_column,
                safe_upper_bound=end_time,
            )
            dataset_start = next_start_from_coverage(spec, default_start=start_time, coverage=coverage)
            if dataset_start > end_time:
                continue

            windows = build_month_windows(dataset_start, end_time, chunk_months=spec.chunk_months)
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
    return dataset_specs, tasks


def collect_coverage_summary(*, safe_upper_bound: datetime | None = None) -> dict[str, Any]:
    with connection_scope() as connection:
        return {
            "BTCUSDT_SPOT": {
                "bars_1m": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_SPOT",
                    table_name="md.bars_1m",
                    time_column="bar_time",
                    safe_upper_bound=safe_upper_bound,
                ),
            },
            "BTCUSDT_PERP": {
                "bars_1m": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.bars_1m",
                    time_column="bar_time",
                    safe_upper_bound=safe_upper_bound,
                ),
                "funding_rates": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.funding_rates",
                    time_column="funding_time",
                    safe_upper_bound=safe_upper_bound,
                ),
                "open_interest": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.open_interest",
                    time_column="ts",
                    safe_upper_bound=safe_upper_bound,
                ),
                "mark_prices": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.mark_prices",
                    time_column="ts",
                    safe_upper_bound=safe_upper_bound,
                ),
                "index_prices": coverage_row(
                    connection,
                    exchange_code="binance",
                    unified_symbol="BTCUSDT_PERP",
                    table_name="md.index_prices",
                    time_column="ts",
                    safe_upper_bound=safe_upper_bound,
                ),
            },
        }


def initial_status_payload(
    *,
    start_time: datetime,
    end_time: datetime,
    status_path: Path,
    dataset_specs: list[DatasetSpec],
    tasks: list[ChunkTask],
    mode: str,
) -> dict[str, Any]:
    return {
        "state": "running",
        "mode": mode,
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
        "datasets": make_dataset_status(dataset_specs, tasks),
        "current_task": None,
        "last_result": None,
        "coverage_summary": None,
        "error": None,
    }


def progress_pct(completed: int, total: int) -> float:
    if total <= 0:
        return 100.0
    return round(completed * 100.0 / total, 2)


def iter_future_row_anomalies(coverage_summary: dict[str, Any]) -> list[str]:
    anomalies: list[str] = []
    for symbol, datasets in coverage_summary.items():
        for dataset_name, payload in datasets.items():
            future_row_count = int(payload.get("future_row_count", 0) or 0)
            if future_row_count <= 0:
                continue
            anomalies.append(
                f"{symbol}.{dataset_name}: future_row_count={future_row_count}, "
                f"raw_available_to={payload.get('available_to')}, safe_available_to={payload.get('safe_available_to')}"
            )
    return anomalies


def format_chunk_window(task: ChunkTask) -> str:
    return f"{task.start_time.isoformat()} -> {task.end_time.isoformat()}"


def open_interest_available_from() -> datetime:
    return utc_now() - timedelta(days=OPEN_INTEREST_LOOKBACK_DAYS)


def run_perp_snapshot_window(task: ChunkTask, *, requested_by: str) -> dict[str, Any]:
    component_results: list[dict[str, Any]] = []
    total_rows_written = 0
    total_history_rows_written = 0
    job_ids: list[int] = []

    funding_result = run_market_snapshot_refresh(
        symbol=task.symbol,
        unified_symbol=task.unified_symbol,
        requested_by=requested_by,
        exchange_code="binance",
        funding_start_time=task.start_time,
        funding_end_time=task.end_time,
        include_funding=True,
        include_open_interest=False,
        include_mark_price=False,
        include_index_price=False,
    )
    component_results.append(
        {
            "component": "funding_rates",
            "status": funding_result.status,
            "rows_written": funding_result.records_written,
            "history_rows_written": funding_result.history_rows_written,
            "ingestion_job_id": funding_result.ingestion_job_id,
            "window_start": task.start_time.isoformat(),
            "window_end": task.end_time.isoformat(),
        }
    )
    total_rows_written += funding_result.records_written
    total_history_rows_written += funding_result.history_rows_written
    job_ids.append(funding_result.ingestion_job_id)

    open_interest_floor = open_interest_available_from()
    if task.end_time < open_interest_floor:
        component_results.append(
            {
                "component": "open_interest",
                "status": "skipped_unavailable",
                "rows_written": 0,
                "history_rows_written": 0,
                "ingestion_job_id": None,
                "window_start": task.start_time.isoformat(),
                "window_end": task.end_time.isoformat(),
                "availability_note": (
                    f"Binance open interest history endpoint is treated as available only from "
                    f"{open_interest_floor.isoformat()} onward"
                ),
            }
        )
    else:
        effective_start = max(task.start_time, open_interest_floor)
        open_interest_result = run_market_snapshot_refresh(
            symbol=task.symbol,
            unified_symbol=task.unified_symbol,
            requested_by=requested_by,
            exchange_code="binance",
            history_start_time=effective_start,
            history_end_time=task.end_time,
            include_funding=False,
            include_open_interest=True,
            include_mark_price=False,
            include_index_price=False,
        )
        component_results.append(
            {
                "component": "open_interest",
                "status": open_interest_result.status,
                "rows_written": open_interest_result.records_written,
                "history_rows_written": open_interest_result.history_rows_written,
                "ingestion_job_id": open_interest_result.ingestion_job_id,
                "window_start": effective_start.isoformat(),
                "window_end": task.end_time.isoformat(),
                "availability_note": (
                    "window start adjusted to current open-interest availability floor"
                    if effective_start != task.start_time
                    else None
                ),
            }
        )
        total_rows_written += open_interest_result.records_written
        total_history_rows_written += open_interest_result.history_rows_written
        job_ids.append(open_interest_result.ingestion_job_id)

    mark_index_result = run_market_snapshot_refresh(
        symbol=task.symbol,
        unified_symbol=task.unified_symbol,
        requested_by=requested_by,
        exchange_code="binance",
        history_start_time=task.start_time,
        history_end_time=task.end_time,
        include_funding=False,
        include_open_interest=False,
        include_mark_price=True,
        include_index_price=True,
    )
    component_results.append(
        {
            "component": "mark_index_prices",
            "status": mark_index_result.status,
            "rows_written": mark_index_result.records_written,
            "history_rows_written": mark_index_result.history_rows_written,
            "ingestion_job_id": mark_index_result.ingestion_job_id,
            "window_start": task.start_time.isoformat(),
            "window_end": task.end_time.isoformat(),
        }
    )
    total_rows_written += mark_index_result.records_written
    total_history_rows_written += mark_index_result.history_rows_written
    job_ids.append(mark_index_result.ingestion_job_id)

    return {
        "dataset_key": task.dataset_key,
        "label": task.label,
        "status": "succeeded",
        "rows_written": total_rows_written,
        "history_rows_written": total_history_rows_written,
        "ingestion_job_ids": job_ids,
        "window_start": task.start_time.isoformat(),
        "window_end": task.end_time.isoformat(),
        "component_results": component_results,
    }


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

    if task.task_kind == "funding_rates":
        result = run_market_snapshot_refresh(
            symbol=task.symbol,
            unified_symbol=task.unified_symbol,
            requested_by=requested_by,
            exchange_code="binance",
            funding_start_time=task.start_time,
            funding_end_time=task.end_time,
            include_funding=True,
            include_open_interest=False,
            include_mark_price=False,
            include_index_price=False,
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

    if task.task_kind == "open_interest":
        result = run_market_snapshot_refresh(
            symbol=task.symbol,
            unified_symbol=task.unified_symbol,
            requested_by=requested_by,
            exchange_code="binance",
            history_start_time=task.start_time,
            history_end_time=task.end_time,
            include_funding=False,
            include_open_interest=True,
            include_mark_price=False,
            include_index_price=False,
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

    if task.task_kind == "mark_prices":
        result = run_market_snapshot_refresh(
            symbol=task.symbol,
            unified_symbol=task.unified_symbol,
            requested_by=requested_by,
            exchange_code="binance",
            history_start_time=task.start_time,
            history_end_time=task.end_time,
            include_funding=False,
            include_open_interest=False,
            include_mark_price=True,
            include_index_price=False,
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

    if task.task_kind == "index_prices":
        result = run_market_snapshot_refresh(
            symbol=task.symbol,
            unified_symbol=task.unified_symbol,
            requested_by=requested_by,
            exchange_code="binance",
            history_start_time=task.start_time,
            history_end_time=task.end_time,
            include_funding=False,
            include_open_interest=False,
            include_mark_price=False,
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

    return run_perp_snapshot_window(task, requested_by=requested_by)


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
    if args.incremental and args.resume_from_status:
        raise ValueError("--incremental and --resume-from-status cannot be used together")

    status_path = Path(args.status_file)
    if args.resume_from_status:
        dataset_specs = build_dataset_specs()
        tasks = build_chunk_tasks(start_time, end_time)
        if not status_path.exists():
            raise FileNotFoundError(f"status file not found for resume: {status_path}")
        status_payload = json.loads(status_path.read_text(encoding="utf-8"))
        completed_tasks = int(status_payload.get("overall", {}).get("tasks_completed", 0))
        status_payload["state"] = "running"
        status_payload["error"] = None
        status_payload["resumed_at"] = utc_now().isoformat()
        status_payload["updated_at"] = utc_now().isoformat()
        mode = str(status_payload.get("mode") or "bootstrap")
    else:
        if args.incremental:
            dataset_specs, tasks = build_incremental_tasks(start_time, end_time)
            mode = "incremental"
        else:
            dataset_specs = build_dataset_specs()
            tasks = build_chunk_tasks(start_time, end_time)
            mode = "bootstrap"
        status_payload = initial_status_payload(
            start_time=start_time,
            end_time=end_time,
            status_path=status_path,
            dataset_specs=dataset_specs,
            tasks=tasks,
            mode=mode,
        )
        completed_tasks = 0
    write_status(status_path, status_payload)

    print(f"Status file: {status_path}")
    print(f"Mode: {status_payload.get('mode', mode)}")
    print(f"Requested window: {start_time.isoformat()} -> {end_time.isoformat()}")
    print(f"Total chunk tasks: {len(tasks)}")
    if completed_tasks:
        print(f"Resuming after completed tasks: {completed_tasks}")

    try:
        for task_number, task in enumerate(tasks[completed_tasks:], start=completed_tasks + 1):
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

        status_payload["coverage_summary"] = collect_coverage_summary(safe_upper_bound=end_time)
        status_payload["state"] = "finished"
        status_payload["current_task"] = None
        status_payload["updated_at"] = utc_now().isoformat()
        write_status(status_path, status_payload)

        print("")
        print("Final coverage summary:")
        print(json.dumps(status_payload["coverage_summary"], indent=2, ensure_ascii=False))
        anomalies = list(iter_future_row_anomalies(status_payload["coverage_summary"]))
        if anomalies:
            print("")
            print("Future-row anomalies detected:")
            for line in anomalies:
                print(f"- {line}")
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
