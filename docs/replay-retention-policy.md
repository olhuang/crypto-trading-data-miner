# Replay Retention Policy

## Purpose

This document fixes the current Phase 4 rules for:
- raw-to-normalized traceability
- replay-ready dataset expectations
- hot retention expectations for early PostgreSQL storage

It complements:
- `docs/data-storage-performance-spec.md`
- `docs/job-orchestration-spec.md`
- `docs/phases-2-to-9-checklists.md`

---

## 1. Traceability Rule

For the current implementation slice:
- every stored raw market event must preserve `channel`
- every stored raw market event should preserve `event_type`
- every stored raw market event should preserve `source_message_id` when the venue supplies a stable source identifier
- raw events may optionally resolve to `instrument_id` when symbol mapping is available at ingest time

The current matching strategies are:
- trade raw event -> `md.trades` via `exchange_trade_id`
- mark-price raw event -> `md.mark_prices` via `instrument_id + event_time`
- liquidation raw event -> `md.liquidations` via `instrument_id + event_time`

These strategies are sufficient for the current Binance public-data slice and should be extended, not replaced, when richer replay flows arrive later.

---

## 2. Sample Reprocessing Path

Current demonstrated replay/debug path for the trade stream:
1. inspect the raw event in `md.raw_market_events`
2. use `channel`, `event_type`, `source_message_id`, `instrument_id`, and `event_time` to locate the normalized record
3. verify the normalized write in `md.trades`
4. rerun normalization logic against the stored `payload_json` if the mapping needs to be debugged or corrected

The current API support for this path is:
- `GET /api/v1/market/raw-events`
- `GET /api/v1/market/raw-events/{raw_event_id}`
- `GET /api/v1/market/raw-events/{raw_event_id}/normalized-links`

---

## 3. Hot Retention Policy

For the current PostgreSQL-first implementation:
- `md.bars_1m`: retain long-term in PostgreSQL
- `md.funding_rates`: retain long-term in PostgreSQL
- `md.open_interest`: retain long-term in PostgreSQL
- `md.mark_prices`: retain long-term in PostgreSQL
- `md.index_prices`: retain long-term in PostgreSQL
- `md.trades`: retain in PostgreSQL during early phases, but treat as a first migration candidate when growth hurts operational performance
- `md.raw_market_events`: retain recent hot data in PostgreSQL and archive colder windows later
- `md.orderbook_deltas`: retain only the windows justified by replay/modeling needs
- `md.orderbook_snapshots`: retain managed recent snapshots in PostgreSQL and archive older snapshots later

This is intentionally aligned with `docs/data-storage-performance-spec.md`.

---

## 4. Replay-Ready Minimum Dataset

The minimum replay-ready dataset for the current Phase 4 baseline is:
- raw trade events for the target stream
- normalized trades for the same stream
- enough reference data to resolve `exchange_code` and `unified_symbol`
- enough ops visibility to identify gaps and stale periods

For the current implementation, the replay-readiness summary reports:
- raw coverage status
- normalized coverage status
- retained streams
- known open gaps

This is enough to support debugging and early replay-readiness inspection before full historical replay engines exist.

---

## 5. Follow-On Maintenance Rule

When retention or replay semantics change:
- update this document
- update `docs/ui-api-spec.md`
- update `docs/api-resource-contracts.md` if response shapes change
- update the Phase 4 checklist status

This keeps Phase 4 docs, API behavior, and operational expectations aligned.
