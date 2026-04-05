from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from jobs.backfill_bars import run_bar_backfill
from storage.db import transaction_scope
from storage.lookups import resolve_instrument_id


def _delete_bar_rows_in_window(
    *,
    exchange_code: str,
    unified_symbol: str,
    start_time: datetime,
    end_time: datetime,
) -> int:
    with transaction_scope() as connection:
        instrument_id = resolve_instrument_id(connection, exchange_code, unified_symbol)
        result = connection.execute(
            text(
                """
                delete from md.bars_1m
                where instrument_id = :instrument_id
                  and bar_time between :start_time and :end_time
                """
            ),
            {
                "instrument_id": instrument_id,
                "start_time": start_time,
                "end_time": end_time,
            },
        )
        return int(result.rowcount or 0)


def repair_bars_integrity_windows(
    *,
    symbol: str,
    unified_symbol: str,
    interval: str,
    windows: list[dict[str, Any]],
    requested_by: str,
    exchange_code: str = "binance",
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    observed_at = datetime.now(timezone.utc)

    for index, window in enumerate(windows, start=1):
        start_time = window["start_time"]
        end_time = window["end_time"]
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            raise ValueError("repair windows must include datetime start_time and end_time values")

        if start_time > observed_at:
            rows_deleted = _delete_bar_rows_in_window(
                exchange_code=exchange_code,
                unified_symbol=unified_symbol,
                start_time=start_time,
                end_time=end_time,
            )
            payload = {
                "ingestion_job_id": 0,
                "status": "deleted_future_rows",
                "rows_written": rows_deleted,
            }
        else:
            backfill_result = run_bar_backfill(
                symbol=symbol,
                unified_symbol=unified_symbol,
                interval=interval,
                start_time=start_time,
                end_time=end_time,
                requested_by=requested_by,
                exchange_code=exchange_code,
            )
            payload = asdict(backfill_result)
        payload["label"] = window.get("label") or f"repair_window_{index}"
        payload["start_time"] = start_time.isoformat()
        payload["end_time"] = end_time.isoformat()
        results.append(payload)

    return {
        "exchange_code": exchange_code,
        "symbol": symbol,
        "unified_symbol": unified_symbol,
        "interval": interval,
        "windows_requested": len(windows),
        "windows_completed": len(results),
        "total_rows_written": sum(int(result.get("rows_written") or 0) for result in results),
        "results": results,
    }
