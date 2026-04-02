from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from services.validate_and_store import supported_payload_types, validate_and_store
from storage.db import transaction_scope


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and store a canonical payload")
    parser.add_argument("payload_type", choices=supported_payload_types())
    parser.add_argument("payload_json", help="JSON string or @path/to/file.json")
    return parser


def load_payload(argument: str) -> dict:
    if argument.startswith("@"):
        payload_path = Path(argument[1:]).resolve()
        return json.loads(payload_path.read_text(encoding="utf-8"))
    return json.loads(argument)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    payload = load_payload(args.payload_json)

    with transaction_scope() as connection:
        result = validate_and_store(connection, args.payload_type, payload)

    print(json.dumps(
        {
            "payload_type": result.payload_type,
            "model_name": result.model_name,
            "stored": result.stored,
            "record_locator": result.record_locator,
            "normalized_payload": result.normalized_payload,
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
