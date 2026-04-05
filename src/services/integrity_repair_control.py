from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Any

from jobs.backfill_bars import run_bar_backfill


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

    for index, window in enumerate(windows, start=1):
        start_time = window["start_time"]
        end_time = window["end_time"]
        if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
            raise ValueError("repair windows must include datetime start_time and end_time values")

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
