from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from jobs.backfill_bars import run_bar_backfill
from jobs.data_quality import validate_dataset_integrity


UTC = timezone.utc
DEFAULT_AUTO_DETECT_START_TIME = "2020-01-01T00:00:00+00:00"

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Repair Binance spot/perp bar integrity windows by re-fetching bounded 1m kline "
            "history from Binance."
        )
    )
    parser.add_argument("--symbol", default="BTCUSDT", help="Venue symbol. Default: BTCUSDT")
    parser.add_argument(
        "--unified-symbol",
        default="BTCUSDT_PERP",
        help="Unified symbol. Default: BTCUSDT_PERP",
    )
    parser.add_argument(
        "--interval",
        default="1m",
        help="Bar interval. Default: 1m",
    )
    parser.add_argument(
        "--requested-by",
        default="repair_bars_integrity_windows_script",
        help="requested_by value stored on the resulting ingestion job(s).",
    )
    parser.add_argument(
        "--start-time",
        default=None,
        help="Optional UTC ISO timestamp. When supplied with --end-time, repairs only one custom window.",
    )
    parser.add_argument(
        "--end-time",
        default=None,
        help=(
            "Optional UTC ISO timestamp. When supplied with --start-time, repairs only one custom "
            "window. If omitted, the script now defaults to auto-detect."
        ),
    )
    parser.add_argument(
        "--auto-detect",
        action="store_true",
        help=(
            "Run a bounded bars_1m integrity profile first, then repair every detected internal gap "
            "and corrupt minute inside the selected window."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the intended repair windows without executing any backfill.",
    )
    return parser.parse_args()


def parse_utc_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _minute_window(timestamp: datetime) -> tuple[datetime, datetime]:
    minute_start = timestamp.replace(second=0, microsecond=0)
    return minute_start, minute_start + timedelta(seconds=59)


def _merge_windows(windows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not windows:
        return []

    ordered = sorted(windows, key=lambda item: (item["start_time"], item["end_time"]))
    merged: list[dict[str, Any]] = [ordered[0].copy()]
    for window in ordered[1:]:
        current = merged[-1]
        if window["start_time"] <= current["end_time"] + timedelta(seconds=1):
            current["end_time"] = max(current["end_time"], window["end_time"])
            current["sources"].extend(window["sources"])
            continue
        merged.append(window.copy())
    return merged


def _build_detected_windows(validation_result: Any) -> list[dict[str, str]]:
    bars_report = next(report for report in validation_result.datasets if report.data_type == "bars_1m")
    candidate_windows: list[dict[str, Any]] = []

    for finding in bars_report.findings:
        if finding.category == "gap":
            for segment in finding.detail_json.get("segments", []):
                start_time = parse_utc_timestamp(segment["gap_start"])
                end_time = parse_utc_timestamp(segment["gap_end"]).replace(second=59, microsecond=0)
                candidate_windows.append(
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                        "sources": [f"gap:{segment['gap_start']}->{segment['gap_end']}"],
                    }
                )
        elif finding.category == "corrupt":
            for example in finding.detail_json.get("corrupt_examples", []):
                start_time, end_time = _minute_window(parse_utc_timestamp(example["ts"]))
                candidate_windows.append(
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                        "sources": [f"corrupt:{example['ts']}"],
                    }
                )

    rendered: list[dict[str, str]] = []
    for index, window in enumerate(_merge_windows(candidate_windows), start=1):
        rendered.append(
            {
                "label": f"auto_detected_window_{index}",
                "start_time": window["start_time"].isoformat(),
                "end_time": window["end_time"].isoformat(),
                "source_summary": ", ".join(window["sources"]),
            }
        )
    return rendered


def _auto_detect_profile_window(args: argparse.Namespace) -> tuple[datetime, datetime]:
    if bool(args.start_time) ^ bool(args.end_time):
        raise ValueError("start_time and end_time must be supplied together")
    if args.start_time and args.end_time:
        return parse_utc_timestamp(args.start_time), parse_utc_timestamp(args.end_time)
    return parse_utc_timestamp(DEFAULT_AUTO_DETECT_START_TIME), datetime.now(UTC)


def build_windows(args: argparse.Namespace) -> tuple[list[dict[str, str]], dict[str, Any] | None]:
    if args.auto_detect or (not args.start_time and not args.end_time):
        profile_start_time, profile_end_time = _auto_detect_profile_window(args)
        validation_result = validate_dataset_integrity(
            exchange_code="binance",
            unified_symbol=args.unified_symbol,
            start_time=profile_start_time,
            end_time=profile_end_time,
            data_types=["bars_1m"],
            persist_findings=False,
        )
        windows = _build_detected_windows(validation_result)
        bars_report = next(report for report in validation_result.datasets if report.data_type == "bars_1m")
        return windows, {
            "profile_start_time": profile_start_time.isoformat(),
            "profile_end_time": profile_end_time.isoformat(),
            "gap_count": bars_report.gap_count,
            "corrupt_count": bars_report.corrupt_count,
            "internal_missing_count": bars_report.internal_missing_count,
            "tail_missing_count": bars_report.tail_missing_count,
        }

    if args.start_time and args.end_time:
        return [
            {
                "label": "custom_window",
                "start_time": args.start_time,
                "end_time": args.end_time,
            }
        ], None
    raise ValueError("start_time and end_time must be supplied together")


def main() -> int:
    args = parse_args()
    windows, auto_detect_summary = build_windows(args)
    print("Binance bars integrity repair")
    payload: dict[str, Any] = {
        "symbol": args.symbol,
        "unified_symbol": args.unified_symbol,
        "interval": args.interval,
        "requested_by": args.requested_by,
        "dry_run": args.dry_run,
        "auto_detect": args.auto_detect,
        "windows": windows,
    }
    if auto_detect_summary is not None:
        payload["auto_detect_summary"] = auto_detect_summary
    print(json.dumps(payload, indent=2))

    if args.dry_run:
        print("Dry run only. No backfill executed.")
        return 0
    if not windows:
        print("No repair windows detected. Nothing to backfill.")
        return 0

    results = []
    for window in windows:
        start_time = parse_utc_timestamp(window["start_time"])
        end_time = parse_utc_timestamp(window["end_time"])
        result = run_bar_backfill(
            symbol=args.symbol,
            unified_symbol=args.unified_symbol,
            interval=args.interval,
            start_time=start_time,
            end_time=end_time,
            requested_by=args.requested_by,
            exchange_code="binance",
        )
        payload = asdict(result)
        payload["label"] = window["label"]
        payload["start_time"] = start_time.isoformat()
        payload["end_time"] = end_time.isoformat()
        results.append(payload)

    print("")
    print("Repair results:")
    print(json.dumps(results, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
