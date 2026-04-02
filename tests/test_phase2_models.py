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

from models.execution import OrderEvent, OrderRequest, OrderState
from models.market import InstrumentMetadata, OpenInterestEvent, TradeEvent
from models.strategy import Signal, TargetPosition


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

    def test_order_request_post_only_requires_limit(self) -> None:
        with self.assertRaises(ValidationError):
            OrderRequest.model_validate(
                {
                    "environment": "paper",
                    "account_code": "paper_main",
                    "exchange_code": "binance",
                    "unified_symbol": "BTCUSDT_PERP",
                    "client_order_id": "ord_post_only_market",
                    "side": "buy",
                    "order_type": "market",
                    "execution_instructions": ["post_only"],
                    "qty": "0.5",
                }
            )

    def test_order_state_requires_ack_time_for_acknowledged(self) -> None:
        with self.assertRaises(ValidationError):
            OrderState.model_validate(
                {
                    "order_id": "1002",
                    "environment": "live",
                    "account_code": "binance_live_01",
                    "exchange_code": "binance",
                    "unified_symbol": "BTCUSDT_PERP",
                    "side": "buy",
                    "order_type": "limit",
                    "price": "84240.00",
                    "qty": "0.5",
                    "status": "acknowledged",
                }
            )

    def test_open_interest_uses_event_time_canonically_and_accepts_ts_alias(self) -> None:
        model = OpenInterestEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "ts": "2026-04-02T12:34:00Z",
                "ingest_time": "2026-04-02T12:34:01Z",
                "open_interest": "18542.991",
            }
        )

        dumped = model.model_dump(mode="json", by_alias=True)
        self.assertEqual(dumped["event_time"], "2026-04-02T12:34:00Z")
        self.assertNotIn("ts", dumped)

    def test_signal_requires_target_for_tradable_signal_types(self) -> None:
        with self.assertRaises(ValidationError):
            Signal.model_validate(
                {
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "signal_id": "sig_missing_target",
                    "signal_time": "2026-04-02T12:34:00Z",
                    "exchange_code": "binance",
                    "unified_symbol": "BTCUSDT_PERP",
                    "signal_type": "entry",
                    "direction": "long",
                }
            )

    def test_signal_exit_allows_flat_direction_and_metadata_alias(self) -> None:
        signal = Signal.model_validate(
            {
                "strategy_code": "btc_momentum",
                "strategy_version": "v1.0.0",
                "signal_id": "sig_exit_001",
                "signal_time": "2026-04-02T12:34:00Z",
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "signal_type": "exit",
                "direction": "flat",
                "metadata": {"reason": "risk_off"},
            }
        )

        self.assertEqual(signal.metadata_json["reason"], "risk_off")
        self.assertEqual(signal.model_dump(mode="json", by_alias=True)["metadata_json"], {"reason": "risk_off"})

    def test_target_position_requires_at_least_one_position_item(self) -> None:
        with self.assertRaises(ValidationError):
            TargetPosition.model_validate(
                {
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "target_time": "2026-04-02T12:35:00Z",
                    "positions": [],
                }
            )

    def test_target_position_item_requires_some_target_value(self) -> None:
        with self.assertRaises(ValidationError):
            TargetPosition.model_validate(
                {
                    "strategy_code": "btc_momentum",
                    "strategy_version": "v1.0.0",
                    "target_time": "2026-04-02T12:35:00Z",
                    "positions": [
                        {
                            "exchange_code": "binance",
                            "unified_symbol": "BTCUSDT_PERP",
                        }
                    ],
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
