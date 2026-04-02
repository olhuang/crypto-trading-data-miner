# API Contracts

## Purpose

This document defines the normalized internal payloads used between modules of the trading platform.

These are canonical internal contracts for:
- market data ingestion
- strategy engine
- paper trading
- live trading
- reconciliation and audit

All timestamps are UTC ISO 8601 strings at the API boundary.
All numeric values should be sent as strings in JSON and parsed internally as Decimal.

This document should be read together with:
- `docs/contract-naming-conventions.md`
- `docs/internal-id-resolution-spec.md`
- `docs/execution-and-risk-engine-spec.md`

---

## Canonical JSON Blob Naming

Use these field names consistently in active canonical contracts:
- `payload_json` for raw or semi-raw source payload blobs
- `detail_json` for structured detail or reason metadata blobs
- `metadata_json` for structured contextual metadata that is not the primary raw payload

Avoid introducing parallel names such as:
- `raw_payload`
- `detail`

Compatibility aliases may still exist in implementation code when needed, but the canonical contract names in this document should remain the `*_json` forms.

---

## Common Enums

### Environment
- `backtest`
- `paper`
- `live`

### Instrument Type
- `spot`
- `perp`
- `future`

### Order Side
- `buy`
- `sell`

### Order Type
- `market`
- `limit`
- `stop`
- `stop_market`
- `take_profit`

### Time In Force
- `gtc`
- `ioc`
- `fok`

### Execution Instruction
- `post_only`
- `reduce_only`
- `close_position`

### Order Status
- `new`
- `submitted`
- `acknowledged`
- `partial`
- `filled`
- `canceled`
- `rejected`
- `expired`

### Liquidity Flag
- `maker`
- `taker`
- `unknown`

### Signal Type
- `entry`
- `exit`
- `reduce`
- `reverse`
- `rebalance`

### Direction
- `long`
- `short`
- `flat`

### Ledger Type
- `deposit`
- `withdrawal`
- `trade_fee`
- `funding_payment`
- `funding_receipt`
- `realized_pnl`
- `transfer_in`
- `transfer_out`
- `rebate`
- `adjustment`

---

## Common Timestamp Guidance

Use these rules across canonical payloads:
- `event_time` for the primary business/event timestamp when a payload represents a discrete event
- `ingest_time` for externally observed payloads collected from exchanges
- domain-specific times such as `bar_time`, `funding_time`, `snapshot_time`, `signal_time`, `target_time`, `submit_time`, `ack_time`, and `fill_time` are allowed when they express a distinct semantic time
- avoid generic `ts` in new or cleaned-up canonical contracts

---

## Order Lifecycle Semantics

### State Transition Guidance

Recommended normalized order lifecycle transitions:
- `new -> submitted`
- `submitted -> acknowledged`
- `submitted -> rejected`
- `acknowledged -> partial`
- `acknowledged -> filled`
- `acknowledged -> canceled`
- `acknowledged -> expired`
- `partial -> filled`
- `partial -> canceled`
- `partial -> expired`

### Terminal States
Terminal states are:
- `filled`
- `canceled`
- `rejected`
- `expired`

### Notes
- `submitted` and `acknowledged` are both retained in the canonical model even if some venues collapse them operationally
- paper and live should both use the same canonical status vocabulary even when the underlying transport/source differs

---

## 1. Market Data Contracts

## 1.1 Instrument Metadata

```json
{
  "exchange_code": "binance",
  "venue_symbol": "BTCUSDT",
  "unified_symbol": "BTCUSDT_SPOT",
  "instrument_type": "spot",
  "base_asset": "BTC",
  "quote_asset": "USDT",
  "settlement_asset": null,
  "tick_size": "0.01",
  "lot_size": "0.00001",
  "min_qty": "0.0001",
  "min_notional": "10",
  "contract_size": null,
  "status": "trading",
  "launch_time": "2026-01-01T00:00:00Z",
  "delist_time": null,
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `venue_symbol`
- `unified_symbol`
- `instrument_type`
- `base_asset`
- `quote_asset`
- `status`

## 1.2 Bar Event

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "bar_interval": "1m",
  "bar_time": "2026-04-02T12:34:00Z",
  "open": "84210.10",
  "high": "84255.00",
  "low": "84190.50",
  "close": "84250.12",
  "volume": "152.2301",
  "quote_volume": "12824611.91",
  "trade_count": 1289,
  "event_time": "2026-04-02T12:34:59.999Z",
  "ingest_time": "2026-04-02T12:35:00.100Z",
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `unified_symbol`
- `bar_interval`
- `bar_time`
- `open`
- `high`
- `low`
- `close`
- `volume`
- `event_time`
- `ingest_time`

## 1.3 Trade Event

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "exchange_trade_id": "1234567890",
  "event_time": "2026-04-02T12:34:56.789Z",
  "ingest_time": "2026-04-02T12:34:56.900Z",
  "price": "84250.12",
  "qty": "0.015",
  "aggressor_side": "buy",
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `unified_symbol`
- `exchange_trade_id`
- `event_time`
- `ingest_time`
- `price`
- `qty`

## 1.4 Funding Rate

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "funding_time": "2026-04-02T08:00:00Z",
  "funding_rate": "0.00010000",
  "mark_price": "84195.22",
  "index_price": "84190.02",
  "ingest_time": "2026-04-02T08:00:01Z",
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `unified_symbol`
- `funding_time`
- `funding_rate`

## 1.5 Open Interest

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "event_time": "2026-04-02T12:34:00Z",
  "open_interest": "18542.991",
  "ingest_time": "2026-04-02T12:34:00.050Z",
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `unified_symbol`
- `event_time`
- `open_interest`

## 1.6 Order Book Snapshot

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "snapshot_time": "2026-04-02T12:34:00Z",
  "ingest_time": "2026-04-02T12:34:00.100Z",
  "depth_levels": 20,
  "bids": [["84250.10", "3.12"]],
  "asks": [["84250.20", "2.65"]],
  "checksum": "abc123",
  "source": "rest_snapshot",
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `unified_symbol`
- `snapshot_time`
- `ingest_time`
- `depth_levels`
- `bids`
- `asks`

## 1.7 Order Book Delta

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "event_time": "2026-04-02T12:34:01.250Z",
  "ingest_time": "2026-04-02T12:34:01.320Z",
  "first_update_id": 10001,
  "final_update_id": 10005,
  "bids": [["84250.10", "0.00"]],
  "asks": [["84250.20", "1.10"]],
  "checksum": "def456",
  "source": "ws_depth",
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `unified_symbol`
- `event_time`
- `ingest_time`

## 1.8 Mark Price

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "event_time": "2026-04-02T12:34:02Z",
  "mark_price": "84244.18",
  "funding_basis_bps": "0.82",
  "ingest_time": "2026-04-02T12:34:02.100Z",
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `unified_symbol`
- `event_time`
- `mark_price`

## 1.9 Index Price

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "event_time": "2026-04-02T12:34:02Z",
  "index_price": "84240.01",
  "ingest_time": "2026-04-02T12:34:02.100Z",
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `unified_symbol`
- `event_time`
- `index_price`

## 1.10 Liquidation Event

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "event_time": "2026-04-02T12:34:05.100Z",
  "ingest_time": "2026-04-02T12:34:05.150Z",
  "side": "sell",
  "price": "84110.50",
  "qty": "12.50",
  "notional": "1051381.25",
  "metadata_json": {},
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `unified_symbol`
- `event_time`
- `ingest_time`

## 1.11 Raw Market Event

```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "channel": "depth",
  "event_type": "depth_update",
  "event_time": "2026-04-02T12:34:01.250Z",
  "ingest_time": "2026-04-02T12:34:01.320Z",
  "source_message_id": "10001-10005",
  "payload_json": {}
}
```

Required:
- `exchange_code`
- `channel`
- `ingest_time`
- `payload_json`

---

## 2. Strategy Contracts

## 2.1 Signal

```json
{
  "strategy_code": "btc_momentum",
  "strategy_version": "v1.0.0",
  "signal_id": "sig_20260402_123400_0001",
  "signal_time": "2026-04-02T12:34:00Z",
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "signal_type": "entry",
  "direction": "long",
  "score": "0.82",
  "target_qty": "0.5000",
  "target_notional": "42125.00",
  "reason_code": "ema_cross_up",
  "metadata_json": {
    "fast_ema": "84190.10",
    "slow_ema": "84170.55"
  }
}
```

Required:
- `strategy_code`
- `strategy_version`
- `signal_id`
- `signal_time`
- `exchange_code`
- `unified_symbol`
- `signal_type`

Rules:
- tradable signals should include at least one of `target_qty` or `target_notional`
- `direction` may be omitted or set to `flat` for exits

## 2.2 Target Position

```json
{
  "strategy_code": "multi_asset_carry",
  "strategy_version": "v2.1.0",
  "target_time": "2026-04-02T12:35:00Z",
  "positions": [
    {
      "exchange_code": "binance",
      "unified_symbol": "BTCUSDT_PERP",
      "target_qty": "0.50",
      "target_weight": "0.25",
      "target_notional": "42125"
    }
  ],
  "metadata_json": {}
}
```

Required:
- `strategy_code`
- `strategy_version`
- `target_time`
- `positions`

---

## 3. Execution Contracts

## 3.1 Order Request

```json
{
  "environment": "paper",
  "account_code": "paper_main",
  "strategy_code": "btc_momentum",
  "strategy_version": "v1.0.0",
  "signal_id": "sig_20260402_123400_0001",
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "client_order_id": "ord_20260402_123401_0001",
  "side": "buy",
  "order_type": "limit",
  "time_in_force": "gtc",
  "execution_instructions": ["post_only"],
  "price": "84240.00",
  "qty": "0.5000",
  "metadata_json": {
    "source": "strategy_signal"
  }
}
```

Required:
- `environment`
- `account_code`
- `exchange_code`
- `unified_symbol`
- `client_order_id`
- `side`
- `order_type`
- `qty`

Rules:
- `price` is required for `limit`, `stop`, and `take_profit`
- `price` should be omitted for plain `market` orders unless a venue requires otherwise
- if `execution_instructions` contains `post_only`, `order_type` must be `limit`

## 3.2 Order State

```json
{
  "order_id": "1000001",
  "environment": "live",
  "account_code": "binance_live_01",
  "strategy_code": "btc_momentum",
  "strategy_version": "v1.0.0",
  "signal_id": "sig_20260402_123400_0001",
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "client_order_id": "ord_20260402_123401_0001",
  "exchange_order_id": "987654321",
  "side": "buy",
  "order_type": "limit",
  "time_in_force": "gtc",
  "execution_instructions": ["post_only"],
  "price": "84240.00",
  "qty": "0.5000",
  "status": "acknowledged",
  "event_time": "2026-04-02T12:34:01.100Z",
  "submit_time": "2026-04-02T12:34:01.010Z",
  "ack_time": "2026-04-02T12:34:01.100Z",
  "cancel_time": null,
  "reject_reason": null,
  "metadata_json": {}
}
```

Required:
- `order_id`
- `environment`
- `account_code`
- `exchange_code`
- `unified_symbol`
- `side`
- `order_type`
- `qty`
- `status`

Conditional required rules:
- if `status = acknowledged`, `ack_time` is required
- if `status = partial`, `ack_time` is recommended and should exist when the venue supplied an acknowledgement path
- if `status = rejected`, `reject_reason` is required
- if `status = canceled`, `cancel_time` is required
- if `status in {acknowledged, partial, filled, canceled}` and the venue supplies one, `exchange_order_id` should be present

## 3.3 Order Event

```json
{
  "order_id": "1000001",
  "client_order_id": "ord_20260402_123401_0001",
  "exchange_order_id": "987654321",
  "event_type": "acknowledged",
  "event_time": "2026-04-02T12:34:01.100Z",
  "status_before": "submitted",
  "status_after": "acknowledged",
  "reason_code": null,
  "detail_json": {
    "raw_status": "NEW"
  }
}
```

Required:
- `order_id`
- `event_type`
- `event_time`

## 3.4 Fill

```json
{
  "fill_id": "5000001",
  "order_id": "1000001",
  "exchange_trade_id": "1234567891",
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "fill_time": "2026-04-02T12:34:02.120Z",
  "price": "84240.00",
  "qty": "0.2500",
  "notional": "21060.00",
  "fee": "4.2120",
  "fee_asset": "USDT",
  "liquidity_flag": "maker",
  "metadata_json": {}
}
```

Required:
- `order_id`
- `exchange_code`
- `unified_symbol`
- `fill_time`
- `price`
- `qty`

## 3.5 Position Snapshot

```json
{
  "environment": "live",
  "account_code": "binance_live_01",
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "snapshot_time": "2026-04-02T12:35:00Z",
  "position_qty": "0.5000",
  "avg_entry_price": "84240.00",
  "mark_price": "84244.18",
  "unrealized_pnl": "2.09",
  "realized_pnl": "15.34"
}
```

Required:
- `environment`
- `account_code`
- `exchange_code`
- `unified_symbol`
- `snapshot_time`
- `position_qty`

## 3.6 Balance Snapshot

```json
{
  "environment": "live",
  "account_code": "binance_live_01",
  "asset": "USDT",
  "snapshot_time": "2026-04-02T12:35:00Z",
  "wallet_balance": "100000.00",
  "available_balance": "82000.00",
  "margin_balance": "100120.55",
  "equity": "100135.89"
}
```

Required:
- `environment`
- `account_code`
- `asset`
- `snapshot_time`
- `wallet_balance`
- `available_balance`

## 3.7 Account Ledger Event

```json
{
  "environment": "live",
  "account_code": "binance_live_01",
  "asset": "USDT",
  "event_time": "2026-04-02T08:00:01Z",
  "ledger_type": "funding_payment",
  "amount": "-12.45",
  "balance_after": "100120.55",
  "reference_type": "funding",
  "reference_id": "BTCUSDT_PERP_20260402_0800",
  "external_reference_id": "ext_12345",
  "detail_json": {}
}
```

Required:
- `environment`
- `account_code`
- `asset`
- `event_time`
- `ledger_type`
- `amount`

## 3.8 Funding PnL Event

```json
{
  "environment": "live",
  "account_code": "binance_live_01",
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "funding_time": "2026-04-02T08:00:00Z",
  "position_qty": "0.5000",
  "funding_rate": "0.00010000",
  "funding_payment": "-4.21",
  "asset": "USDT",
  "detail_json": {}
}
```

Required:
- `environment`
- `account_code`
- `exchange_code`
- `unified_symbol`
- `funding_time`
- `position_qty`
- `funding_rate`
- `funding_payment`

---

## 4. Mapping Rules

### Exchange Adapter Responsibilities
1. Translate exchange-native payloads into these canonical contracts.
2. Preserve native identifiers and raw payloads whenever possible, using `payload_json` as the canonical blob field name when retained.
3. Attach `ingest_time` as close to receipt time as possible.
4. Reject or quarantine malformed payloads rather than silently dropping fields.

### Strategy Engine Responsibilities
1. Emit normalized `Signal` and `Target Position` payloads.
2. Use stable `strategy_code` and `strategy_version` values.
3. Include enough metadata for later audit.

### Execution Engine Responsibilities
1. Convert signals into canonical `Order Request` payloads.
2. Persist lifecycle changes as `Order State` and `Order Event` payloads.
3. Emit `Fill`, `Position Snapshot`, and `Balance Snapshot` payloads after execution updates.

---

## 5. Validation Recommendations

1. Reject messages with missing required fields.
2. Validate enum fields against the allowed values in this document.
3. Validate decimal strings before persistence.
4. Ensure timestamps are parseable and in UTC.
5. Deduplicate market events using exchange identifiers where available.
6. Deduplicate orders by `client_order_id` within account and venue scope.
7. Deduplicate fills by `exchange_trade_id` where available.
8. Apply conditional required field checks for order lifecycle states.
