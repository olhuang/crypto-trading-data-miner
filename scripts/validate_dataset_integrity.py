from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
import sys
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from jobs.data_quality import validate_dataset_integrity


def _parse_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"object of type {type(value).__name__} is not JSON serializable")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate dataset integrity for one symbol/window.")
    parser.add_argument("--exchange-code", default="binance")
    parser.add_argument("--unified-symbol", required=True)
    parser.add_argument("--start-time", required=True, type=_parse_datetime)
    parser.add_argument("--end-time", required=True, type=_parse_datetime)
    parser.add_argument("--observed-at", type=_parse_datetime)
    parser.add_argument("--data-type", dest="data_types", action="append", help="Repeat to validate specific datasets only.")
    parser.add_argument("--raw-event-channel")
    parser.add_argument("--no-persist", action="store_true", help="Do not persist integrity checks/gaps into ops tables.")
    parser.add_argument("--output", help="Optional path to write the JSON report.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = validate_dataset_integrity(
        exchange_code=args.exchange_code,
        unified_symbol=args.unified_symbol,
        start_time=args.start_time,
        end_time=args.end_time,
        observed_at=args.observed_at,
        data_types=args.data_types,
        raw_event_channel=args.raw_event_channel,
        persist_findings=not args.no_persist,
    )
    payload = asdict(result)
    rendered = json.dumps(payload, indent=2, default=_json_default)
    print(rendered)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
