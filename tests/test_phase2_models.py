from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
import sys
import unittest

from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from models.execution import OrderEvent, OrderRequest
from models.market import InstrumentMetadata, TradeEvent


class Phase2ModelValidationTests(unittest.TestCase):
    def test_trade_event_uses_canonical_payload_json_name(self) -> None:
        model = TradeEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "exchange_trade_id": "trade_test_001",
                "event_time": "2026-04-02T12:34:56Z",
                "ingest_time": "2026-04-02T12:34:57Z",
                "price": "84250.12",
                "qty": "0.01",
                "raw_payload": {"source": "legacy_alias"},
            }
        )

        self.assertEqual(model.payload_json["source"], "legacy_alias")
        self.assertEqual(
            model.model_dump(mode="json", by_alias=True)["payload_json"],
            {"source": "legacy_alias"},
        )

    def test_order_event_uses_canonical_detail_json_name(self) -> None:
        model = OrderEvent.model_validate(
            {
                "order_id": "1001",
                "event_type": "acknowledged",
                "event_time": "2026-04-02T12:34:56Z",
                "detail": {"raw_status": "NEW"},
            }
        )

        self.assertEqual(model.detail_json["raw_status"], "NEW")
        self.assertEqual(
            model.model_dump(mode="json", by_alias=True)["detail_json"],
            {"raw_status": "NEW"},
        )

    def test_order_request_requires_price_for_limit(self) -> None:
        with self.assertRaises(ValidationError):
            OrderRequest.model_validate(
                {
                    "environment": "paper",
                    "account_code": "paper_main",
                    "exchange_code": "binance",
                    "unified_symbol": "BTCUSDT_PERP",
                    "client_order_id": "ord_missing_price",
                    "side": "buy",
                    "order_type": "limit",
                    "qty": "0.5",
                }
            )

    def test_spot_instrument_rejects_contract_size(self) -> None:
        with self.assertRaises(ValidationError):
            InstrumentMetadata.model_validate(
                {
                    "exchange_code": "binance",
                    "venue_symbol": "BTCUSDT",
                    "unified_symbol": "BTCUSDT_SPOT",
                    "instrument_type": "spot",
                    "base_asset": "BTC",
                    "quote_asset": "USDT",
                    "contract_size": "1",
                    "status": "trading",
                }
            )

    def test_decimal_and_timestamp_parsing_are_normalized(self) -> None:
        model = TradeEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "exchange_trade_id": "trade_test_002",
                "event_time": "2026-04-02T20:34:56+08:00",
                "ingest_time": "2026-04-02T20:34:57+08:00",
                "price": "84250.12",
                "qty": "0.01",
            }
        )

        self.assertEqual(model.price, Decimal("84250.12"))
        self.assertEqual(model.event_time, datetime.fromisoformat("2026-04-02T12:34:56+00:00"))


if __name__ == "__main__":
    unittest.main()
