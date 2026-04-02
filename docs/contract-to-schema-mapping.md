# Contract-to-Schema Mapping

## Purpose

This document maps canonical contract fields to database persistence targets.

It exists to reduce ambiguity when implementing:
- Pydantic/domain models
- repository writes
- idempotent upserts
- lookup and deduplication logic

This spec complements:
- `docs/api-contracts.md`
- `docs/internal-id-resolution-spec.md`
- `docs/contract-naming-conventions.md`
- `db/init/*.sql`

---

## 1. Mapping Principles

## 1.1 Contract vs Schema

Canonical contracts define normalized payload semantics.
Database schema defines implemented persistence layout.

Implementation should explicitly map:
- contract field
- target table
- target column
- lookup key / uniqueness key
- idempotency behavior

## 1.2 Repository Rule

Repositories are responsible for applying the mapping.
Do not scatter schema-mapping logic across API handlers or runtime loops.

## 1.3 Authority Rule

If this mapping document and implemented SQL schema differ, the actual SQL schema remains the authority for current implemented state.
This document should then be updated promptly.

---

## 2. Instrument Metadata Mapping

Canonical contract:
- Instrument Metadata

Primary target:
- `ref.instruments`

Supporting lookups:
- `ref.exchanges`
- `ref.assets`

### Field Mapping
- `exchange_code` -> resolve `exchange_id`
- `venue_symbol` -> `venue_symbol`
- `unified_symbol` -> `unified_symbol`
- `instrument_type` -> `instrument_type`
- `base_asset` -> resolve `base_asset_id`
- `quote_asset` -> resolve `quote_asset_id`
- `settlement_asset` -> resolve `settlement_asset_id` when applicable
- `tick_size` -> `tick_size`
- `lot_size` -> `lot_size`
- `min_qty` -> `min_qty`
- `min_notional` -> `min_notional`
- `contract_size` -> `contract_size`
- `status` -> `status`
- `launch_time` -> `launch_time`
- `delist_time` -> `delist_time`
- `payload_json` -> not necessarily stored directly in `ref.instruments`; if retained, store in metadata/audit field or sync-result blob according to implementation choice

### Natural Uniqueness
Recommended natural uniqueness path:
- `exchange_id + venue_symbol`
- `exchange_id + unified_symbol` must also remain logically unique for normalized use

### Idempotency Rule
Instrument sync should behave as upsert/merge by natural key, not blind insert.

---

## 3. Bar Event Mapping

Canonical contract:
- Bar Event

Primary target:
- `md.bars_1m`

### Field Mapping
- `exchange_code` -> resolve `exchange_id` if needed for validation/context
- `unified_symbol` -> resolve `instrument_id`
- `bar_interval` -> `bar_interval`
- `bar_time` -> `bar_time`
- `open` -> `open`
- `high` -> `high`
- `low` -> `low`
- `close` -> `close`
- `volume` -> `volume`
- `quote_volume` -> `quote_volume`
- `trade_count` -> `trade_count`
- `event_time` -> event/close reference time if separately retained in schema or metadata
- `ingest_time` -> `ingest_time` if supported in schema or retained in companion ops/raw structure
- `payload_json` -> optional raw retention path, not necessarily the primary bars table

### Uniqueness / Idempotency
Natural uniqueness:
- `instrument_id + bar_interval + bar_time`

Idempotency behavior:
- upsert by natural key

---

## 4. Trade Event Mapping

Canonical contract:
- Trade Event

Primary target:
- `md.trades`

### Field Mapping
- `exchange_code` -> resolve `exchange_id`
- `unified_symbol` -> resolve `instrument_id`
- `exchange_trade_id` -> `exchange_trade_id`
- `event_time` -> `event_time`
- `ingest_time` -> `ingest_time`
- `price` -> `price`
- `qty` -> `qty`
- `aggressor_side` -> `aggressor_side`
- `payload_json` -> optional raw blob path if retained in same table or raw table

### Uniqueness / Idempotency
Preferred natural uniqueness:
- `exchange_id + instrument_id + exchange_trade_id`

If exchange trade id is unreliable or absent for a source, define a fallback dedupe key explicitly in implementation.

---

## 5. Funding Rate Mapping

Primary target:
- `md.funding_rates`

### Field Mapping
- `exchange_code` -> resolve `exchange_id`
- `unified_symbol` -> resolve `instrument_id`
- `funding_time` -> `funding_time`
- `funding_rate` -> `funding_rate`
- `mark_price` -> `mark_price` when schema supports it
- `index_price` -> `index_price` when schema supports it
- `ingest_time` -> `ingest_time` if supported

### Uniqueness / Idempotency
Natural key:
- `instrument_id + funding_time`

---

## 6. Open Interest Mapping

Primary target:
- `md.open_interest`

### Field Mapping
- `exchange_code` -> resolve `exchange_id`
- `unified_symbol` -> resolve `instrument_id`
- `event_time` -> `event_time`
- `open_interest` -> `open_interest`
- `ingest_time` -> `ingest_time` if supported

### Uniqueness / Idempotency
Natural key:
- `instrument_id + event_time`

---

## 7. Raw Market Event Mapping

Primary target:
- `md.raw_market_events`

### Field Mapping
- `exchange_code` -> resolve `exchange_id`
- `unified_symbol` -> resolve `instrument_id` when available
- `channel` -> `channel`
- `event_type` -> `event_type`
- `event_time` -> `event_time`
- `ingest_time` -> `ingest_time`
- `source_message_id` -> `source_message_id`
- `payload_json` -> `payload_json`

### Idempotency Guidance
If `source_message_id` is available and reliable, use it in dedupe logic within source scope.
Otherwise use a carefully defined fallback hash or composite key.

---

## 8. Signal Mapping

Primary target:
- `strategy.signals`

### Field Mapping
- `strategy_code` -> resolve `strategy_id`
- `strategy_version` -> resolve `strategy_version_id`
- `signal_id` -> `signal_id` or equivalent unique signal reference
- `signal_time` -> `signal_time`
- `exchange_code` -> resolve exchange scope if needed
- `unified_symbol` -> resolve `instrument_id`
- `signal_type` -> `signal_type`
- `direction` -> `direction`
- `score` -> `score`
- `target_qty` -> `target_qty`
- `target_notional` -> `target_notional`
- `reason_code` -> `reason_code`
- `metadata_json` -> `metadata_json`

### Uniqueness
Natural uniqueness guidance:
- `strategy_version_id + signal_id`

---

## 9. Order Request / Order State Mapping

Primary target:
- `execution.orders`

Supporting targets:
- `execution.order_events`

### Field Mapping
- `environment` -> `environment`
- `account_code` -> resolve `account_id`
- `strategy_code` -> resolve `strategy_id` when stored
- `strategy_version` -> resolve `strategy_version_id` when stored
- `signal_id` -> resolve/store signal linkage
- `exchange_code` -> resolve exchange scope
- `unified_symbol` -> resolve `instrument_id`
- `client_order_id` -> `client_order_id`
- `exchange_order_id` -> `exchange_order_id`
- `side` -> `side`
- `order_type` -> `order_type`
- `time_in_force` -> `time_in_force`
- `execution_instructions` -> dedicated field(s) or metadata representation depending on implemented schema
- `price` -> `price`
- `qty` -> `qty`
- `status` -> `status`
- `submit_time` -> `submit_time`
- `ack_time` -> `ack_time`
- `cancel_time` -> `cancel_time`
- `reject_reason` -> `reject_reason`
- `metadata_json` -> `metadata_json`

### Uniqueness / Idempotency
Recommended request-side idempotency key:
- `account_id + client_order_id`

### Repository Rule
- `execution.orders` stores canonical latest order state
- `execution.order_events` stores append-only state transitions/events

---

## 10. Fill Mapping

Primary target:
- `execution.fills`

### Field Mapping
- `fill_id` -> internal fill identifier if generated internally
- `order_id` -> resolve canonical order FK
- `exchange_trade_id` -> `exchange_trade_id`
- `exchange_code` -> resolve exchange scope
- `unified_symbol` -> resolve `instrument_id`
- `fill_time` -> `fill_time`
- `price` -> `price`
- `qty` -> `qty`
- `notional` -> `notional`
- `fee` -> `fee`
- `fee_asset` -> `fee_asset`
- `liquidity_flag` -> `liquidity_flag`
- `metadata_json` -> `metadata_json`

### Uniqueness / Idempotency
Preferred natural key:
- `exchange_scope + exchange_trade_id`

Where exchange trade id is insufficient alone, include order or symbol scope explicitly.

---

## 11. Position Snapshot Mapping

Primary target:
- `execution.positions`

### Field Mapping
- `environment` -> `environment`
- `account_code` -> resolve `account_id`
- `exchange_code` -> resolve exchange scope
- `unified_symbol` -> resolve `instrument_id`
- `snapshot_time` -> `updated_at` or snapshot field depending on schema design
- `position_qty` -> `position_qty`
- `avg_entry_price` -> `avg_entry_price`
- `mark_price` -> `mark_price`
- `unrealized_pnl` -> `unrealized_pnl`
- `realized_pnl` -> `realized_pnl`

### Rule
`execution.positions` is typically current-state oriented. Historical snapshots, if needed, should use an additional history path rather than overloading current-state semantics.

---

## 12. Balance Snapshot Mapping

Primary target:
- `execution.balances`

### Field Mapping
- `environment` -> `environment`
- `account_code` -> resolve `account_id`
- `asset` -> `asset`
- `snapshot_time` -> `updated_at` or snapshot field depending on schema
- `wallet_balance` -> `wallet_balance`
- `available_balance` -> `available_balance`
- `margin_balance` -> `margin_balance`
- `equity` -> `equity`

---

## 13. Ledger and Funding Mapping

### Account Ledger Event
Primary target:
- `execution.account_ledger`

### Funding PnL Event
Primary targets:
- `execution.funding_pnl`
- and/or related ledger event path where accounting requires both

Repository implementations must preserve source linkage so accounting and reconciliation can explain balances and funding history.

---

## 14. Job / Ops Mapping Guidance

Long-running or async contract outputs should map to ops tracking tables where relevant.
Examples:
- ingestion runs -> `ops.ingestion_jobs`
- quality checks -> `ops.data_quality_checks`
- gaps -> `ops.data_gaps`

This mapping may be domain-specific first; a universal jobs table is not required for initial implementation.

---

## 15. Mapping Checklist for New Contracts

When adding a new contract, define:
1. target table
2. target columns
3. FK resolution path
4. natural key or uniqueness key
5. idempotency key
6. current-state vs append-only write behavior
7. whether raw payload retention is also required

---

## 16. Minimum Acceptance Criteria

This mapping spec is sufficiently useful when:
- repository authors can implement writes without guessing target columns or keys
- natural uniqueness and idempotency rules are explicit for first-wave entities
- contract fields map cleanly to schema and supporting lookups

---

## 17. Final Summary

The main implementation rule is:
- canonical contracts define payload meaning
- repositories explicitly map those contracts into SQL schema
- natural keys and idempotency keys must be defined per entity
- FK resolution happens before repository writes

This document should be used as the bridge between Phase 2 models and the actual PostgreSQL schema.