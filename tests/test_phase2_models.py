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

from models.execution import AccountLedgerEvent, FundingPnlEvent, OrderEvent, OrderRequest, OrderState
from models.market import (
    IndexPriceEvent,
    InstrumentMetadata,
    MarkPriceEvent,
    OpenInterestEvent,
    OrderBookSnapshotEvent,
    RawMarketEvent,
    TradeEvent,
)
from models.risk import RiskEvent, RiskLimit
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

    def test_risk_limit_requires_at_least_one_threshold(self) -> None:
        with self.assertRaises(ValidationError):
            RiskLimit.model_validate(
                {
                    "account_code": "paper_main",
                }
            )

    def test_risk_limit_requires_full_instrument_scope_pair(self) -> None:
        with self.assertRaises(ValidationError):
            RiskLimit.model_validate(
                {
                    "account_code": "paper_main",
                    "exchange_code": "binance",
                    "max_notional": "10000",
                }
            )

    def test_risk_event_supports_detail_alias_and_scope_validation(self) -> None:
        event = RiskEvent.model_validate(
            {
                "account_code": "paper_main",
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "event_time": "2026-04-02T12:34:00Z",
                "event_type": "pre_trade_check_blocked",
                "severity": "warning",
                "decision": "block",
                "detail": {"reason_code": "max_notional"},
            }
        )

        self.assertEqual(event.detail_json["reason_code"], "max_notional")
        self.assertEqual(event.model_dump(mode="json", by_alias=True)["detail_json"], {"reason_code": "max_notional"})

    def test_orderbook_snapshot_parses_decimal_levels(self) -> None:
        snapshot = OrderBookSnapshotEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "snapshot_time": "2026-04-02T12:34:00Z",
                "ingest_time": "2026-04-02T12:34:00.100Z",
                "depth_levels": 2,
                "bids": [["84250.10", "3.12"]],
                "asks": [["84250.20", "2.65"]],
            }
        )

        self.assertEqual(snapshot.bids[0][0], Decimal("84250.10"))
        self.assertEqual(snapshot.asks[0][1], Decimal("2.65"))

    def test_mark_and_index_price_use_event_time_canonically(self) -> None:
        mark_event = MarkPriceEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "ts": "2026-04-02T12:34:02Z",
                "ingest_time": "2026-04-02T12:34:02.100Z",
                "mark_price": "84244.18",
            }
        )
        index_event = IndexPriceEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "ts": "2026-04-02T12:34:02Z",
                "ingest_time": "2026-04-02T12:34:02.100Z",
                "index_price": "84240.01",
            }
        )

        self.assertEqual(mark_event.model_dump(mode="json", by_alias=True)["event_time"], "2026-04-02T12:34:02Z")
        self.assertEqual(index_event.model_dump(mode="json", by_alias=True)["event_time"], "2026-04-02T12:34:02Z")

    def test_raw_market_event_uses_canonical_payload_json_name(self) -> None:
        event = RawMarketEvent.model_validate(
            {
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "channel": "depth",
                "event_type": "depth_update",
                "ingest_time": "2026-04-02T12:34:01.320Z",
                "raw_payload": {"u": 10005},
            }
        )

        self.assertEqual(event.payload_json["u"], 10005)
        self.assertEqual(event.model_dump(mode="json", by_alias=True)["payload_json"], {"u": 10005})

    def test_account_ledger_and_funding_pnl_support_detail_alias(self) -> None:
        ledger_event = AccountLedgerEvent.model_validate(
            {
                "environment": "live",
                "account_code": "paper_main",
                "asset": "USDT",
                "event_time": "2026-04-02T08:00:01Z",
                "ledger_type": "funding_payment",
                "amount": "-12.45",
                "detail": {"source": "exchange_history"},
            }
        )
        funding_event = FundingPnlEvent.model_validate(
            {
                "environment": "live",
                "account_code": "paper_main",
                "exchange_code": "binance",
                "unified_symbol": "BTCUSDT_PERP",
                "funding_time": "2026-04-02T08:00:00Z",
                "position_qty": "0.5000",
                "funding_rate": "0.00010000",
                "funding_payment": "-4.21",
                "asset": "USDT",
                "detail": {"settlement_batch": "funding_0800"},
            }
        )

        self.assertEqual(ledger_event.detail_json["source"], "exchange_history")
        self.assertEqual(funding_event.detail_json["settlement_batch"], "funding_0800")

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
