from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from ingestion.binance.public_rest import BinancePublicRestClient


UTC = timezone.utc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Debug Binance open-interest history coverage across bounded windows."
    )
    parser.add_argument("--symbol", default="BTCUSDT", help="Raw Binance futures symbol.")
    parser.add_argument("--start-time", required=True, help="UTC ISO timestamp.")
    parser.add_argument("--end-time", required=True, help="UTC ISO timestamp.")
    parser.add_argument("--period", default="5m", help="Open-interest history period.")
    parser.add_argument("--chunk-days", type=int, default=1, help="Days per probe window.")
    parser.add_argument("--limit", type=int, default=500, help="Endpoint page limit.")
    parser.add_argument(
        "--output-json",
        action="store_true",
        help="Print the final summary as JSON instead of plain text.",
    )
    return parser.parse_args()


def parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def build_day_windows(start_time: datetime, end_time: datetime, *, chunk_days: int) -> list[tuple[datetime, datetime]]:
    windows: list[tuple[datetime, datetime]] = []
    cursor = start_time
    while cursor <= end_time:
        next_cursor = cursor + timedelta(days=chunk_days)
        window_end = min(next_cursor - timedelta(milliseconds=1), end_time)
        windows.append((cursor, window_end))
        cursor = next_cursor
    return windows


def iso_or_none(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def summarize_window(
    client: BinancePublicRestClient,
    *,
    symbol: str,
    period: str,
    limit: int,
    start_time: datetime,
    end_time: datetime,
) -> dict[str, Any]:
    rows = client.fetch_open_interest_history(
        symbol,
        period=period,
        start_time=start_time,
        end_time=end_time,
        limit=limit,
    )
    timestamps = sorted(
        datetime.fromtimestamp(int(row["timestamp"]) / 1000, tz=UTC)
        for row in rows
        if row.get("timestamp") is not None
    )
    unique_timestamps = sorted(set(timestamps))
    deltas = [
        int((current - previous).total_seconds())
        for previous, current in zip(unique_timestamps, unique_timestamps[1:])
    ]
    return {
        "requested_start": start_time.isoformat(),
        "requested_end": end_time.isoformat(),
        "row_count": len(rows),
        "unique_timestamp_count": len(unique_timestamps),
        "first_timestamp": iso_or_none(unique_timestamps[0] if unique_timestamps else None),
        "last_timestamp": iso_or_none(unique_timestamps[-1] if unique_timestamps else None),
        "min_delta_seconds": min(deltas) if deltas else None,
        "max_delta_seconds": max(deltas) if deltas else None,
        "sample_first_timestamps": [timestamp.isoformat() for timestamp in unique_timestamps[:5]],
        "sample_last_timestamps": [timestamp.isoformat() for timestamp in unique_timestamps[-5:]],
    }


def main() -> int:
    args = parse_args()
    start_time = parse_utc_timestamp(args.start_time)
    end_time = parse_utc_timestamp(args.end_time)
    if end_time < start_time:
        raise ValueError("end_time must be greater than or equal to start_time")

    client = BinancePublicRestClient()
    windows = build_day_windows(start_time, end_time, chunk_days=max(1, args.chunk_days))
    results = [
        summarize_window(
            client,
            symbol=args.symbol,
            period=args.period,
            limit=args.limit,
            start_time=window_start,
            end_time=window_end,
        )
        for window_start, window_end in windows
    ]

    summary = {
        "symbol": args.symbol,
        "period": args.period,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "chunk_days": args.chunk_days,
        "window_count": len(results),
        "windows": results,
    }

    if args.output_json:
        print(json.dumps(summary, indent=2))
        return 0

    print("Open Interest History Debug")
    print(f"Symbol: {args.symbol}")
    print(f"Period: {args.period}")
    print(f"Window: {start_time.isoformat()} -> {end_time.isoformat()}")
    print(f"Chunk Days: {args.chunk_days}")
    print()
    for index, result in enumerate(results, start=1):
        print(
            f"[{index}/{len(results)}] {result['requested_start']} -> {result['requested_end']} | "
            f"rows={result['row_count']} unique={result['unique_timestamp_count']} | "
            f"first={result['first_timestamp']} last={result['last_timestamp']} | "
            f"delta={result['min_delta_seconds']}..{result['max_delta_seconds']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
