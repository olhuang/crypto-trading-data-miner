# Data Storage and Performance Spec

## Purpose

This document defines the storage architecture and performance rules for the trading platform.

It focuses on:
- storage tiering
- PostgreSQL usage boundaries
- high-volume dataset handling
- partitioning and indexing strategy
- retention and archival
- performance targets
- migration triggers for future analytical storage

This spec complements:
- `docs/backend-system-design.md`
- `docs/job-orchestration-spec.md`
- `docs/architecture.md`

---

## 1. Goals

The storage design must support:
1. correctness and auditability for transactional data
2. efficient write-heavy ingestion for market data
3. predictable reads for UI and strategy workflows
4. future migration of very high-volume datasets
5. retention control for raw and replay-oriented data

---

## 2. Storage Tiers

## 2.1 Tier 1: PostgreSQL (Primary System of Record)

Use PostgreSQL for:
- reference data
- strategy metadata
- orders, fills, positions, balances
- risk events
- backtest metadata and summary outputs
- ops and audit data
- moderate-volume market series during early phases

## 2.2 Tier 2: Redis (Ephemeral / Coordination)

Use Redis for:
- short-lived latest-state cache
- locks
- runtime session coordination
- optional near-real-time UI summary cache

Do not use Redis as the audit/system of record.

## 2.3 Tier 3: Analytical or Archive Storage (Future)

Use ClickHouse and/or object storage later for:
- very high-volume trades
- order book deltas
- large raw event archives
- replay datasets
- large historical exports

---

## 3. Dataset Classes

## 3.1 Transactional / Audit-Critical
Examples:
- `execution.orders`
- `execution.order_events`
- `execution.fills`
- `execution.positions`
- `execution.balances`
- `execution.account_ledger`
- `risk.risk_events`
- `strategy.deployments`

Rules:
- remain in PostgreSQL as source of truth
- prioritize correctness and auditability over raw write throughput

## 3.2 Medium-Volume Analytical / Research Data
Examples:
- `md.bars_1m`
- `md.funding_rates`
- `md.open_interest`
- `md.mark_prices`
- `md.index_prices`

Rules:
- start in PostgreSQL
- tune with indexes and partitions as needed
- likely remain in PostgreSQL longer than tick/order-book datasets

## 3.3 High-Volume Tick / Stream Data
Examples:
- `md.trades`
- `md.orderbook_deltas`
- `md.raw_market_events`
- `md.orderbook_snapshots`

Rules:
- may begin in PostgreSQL for early-stage simplicity
- require explicit retention and scaling thresholds
- should be the first candidates for migration to analytical/object storage

---

## 4. PostgreSQL Role and Boundaries

## 4.1 PostgreSQL Must Be Good At
- transactional integrity
- relational joins for reference/execution data
- small to medium range time-series reads
- UI list/detail queries for operational entities
- reliable audit storage

## 4.2 PostgreSQL Should Not Be Forced To Do Forever
- unbounded order-book delta retention
- very large raw event archive scanning
- unlimited full-history tick analytics mixed with live workload
- heavy backtest scans that compete with live write paths at scale

---

## 5. Table-by-Table Storage Policy Guidance

## 5.1 Keep in PostgreSQL Long-Term
Recommended long-term PostgreSQL tables:
- `ref.*`
- `strategy.*`
- `execution.*`
- `risk.*`
- `ops.*`
- `backtest.runs`
- `backtest.performance_summary`
- `backtest.performance_timeseries` (unless volume becomes extreme)

## 5.2 Start in PostgreSQL, Reevaluate Later
- `md.bars_1m`
- `md.funding_rates`
- `md.open_interest`
- `md.mark_prices`
- `md.index_prices`
- `md.liquidations`

## 5.3 Highest-Priority Migration Candidates
- `md.trades`
- `md.orderbook_deltas`
- `md.raw_market_events`
- large-scale `md.orderbook_snapshots`

---

## 6. Partitioning Strategy

## 6.1 Partitioning Principle

High-volume time-series tables should not remain as one endlessly growing heap.

Use partitioning when:
- table growth is continuous and time-based
- reads are mostly time-window scoped
- retention/archival is needed by time window

## 6.2 Recommended Partition Candidates
Primary candidates:
- `md.trades`
- `md.orderbook_deltas`
- `md.raw_market_events`
- `md.orderbook_snapshots`
- possibly `md.bars_1m` at larger scale

## 6.3 Partition Keys

Recommended defaults:
- partition by event/record time (monthly or daily depending on write volume)
- optionally combine with exchange/instrument considerations at higher scale

## 6.4 Initial Simplicity Rule

Do not over-partition too early.

Suggested progression:
1. no partitioning at tiny scale
2. monthly partitions for high-growth tables
3. reevaluate daily partitions only if monthly partitions become too large or maintenance-heavy

---

## 7. Indexing Strategy

## 7.1 Index Principles

- index only common query paths
- prefer compound indexes aligned with filters/order-by patterns
- avoid over-indexing high-write tables

## 7.2 Common Read Patterns

### Reference and Execution
Common patterns:
- by `exchange_id`
- by `account_id`
- by `instrument_id`
- by status
- by time descending

### Market Data
Common patterns:
- by `instrument_id` + time range
- by `exchange_id` + channel + time
- by event time descending for recent views

## 7.3 Example Index Guidance

- `md.bars_1m`: `(instrument_id, bar_time)` primary access path
- `md.trades`: `(instrument_id, event_time desc)` and unique dedupe key on exchange trade id scope
- `execution.orders`: `(account_id, submit_time desc)`, `(status, submit_time desc)`
- `execution.fills`: `(order_id, fill_time asc)`, `(account_id, fill_time desc)` if frequently queried
- `ops.ingestion_jobs`: `(status, started_at desc)`

---

## 8. Retention Policy

## 8.1 Retention Classes

### Permanent / Long-Term Retention
Examples:
- orders
- fills
- positions history where required
- balances history where required
- risk events
- deployments/config audits
- treasury events

### Long but Managed Retention
Examples:
- bars
- funding rates
- OI
- mark/index price
- backtest outputs

### Shorter / Managed Retention
Examples:
- raw market events
- order book deltas
- high-frequency snapshots

## 8.2 Recommended Initial Retention Guidance

Initial guidance, subject to refinement later:
- orders/fills/ledger/risk/audit: retain indefinitely or according to business policy
- bars/funding/OI/mark/index: retain long-term in primary store if cost is acceptable
- raw market events: retain shorter in hot PostgreSQL path, archive longer-term if replay needs require it
- order book deltas: retain only as long as replay or modeling use cases justify

## 8.3 Retention Enforcement

Retention policies should be enforced by explicit maintenance jobs, not manual cleanup.

---

## 9. Hot / Warm / Cold Strategy

## 9.1 Hot Data

Definition:
- recent operationally important data used for UI, live monitoring, and active jobs

Examples:
- current orders/fills/positions
- recent bars/trades
- current jobs and alerts

## 9.2 Warm Data

Definition:
- historical data still queried regularly for research or investigations

Examples:
- recent months of bars/trades
- recent raw event history
- recent backtests and reconciliation runs

## 9.3 Cold Data

Definition:
- rarely queried archival data retained for replay, audit, or long-range research

Examples:
- old raw payload archives
- old order book delta archives
- large historical tick exports

---

## 10. Performance Targets

These are initial engineering targets, not hard SLAs.

## 10.1 UI Query Targets
- reference-data list pages: typically sub-second
- order/position/fill explorers: typically sub-second to low seconds under moderate load
- market time-window list pages: seconds-level acceptable for large windows, but defaults should stay small

## 10.2 Write Path Targets
- public trade ingestion should support sustained burst writes for chosen symbol scope without blocking transactional tables
- live order/fill writes should prioritize reliability and low latency over throughput extremes

## 10.3 Runtime Targets
- paper/live runtime reads should not depend on expensive historical scans
- latest-state access should use efficient recent queries or cache where justified

---

## 11. API Query Constraints for Performance Safety

High-volume endpoints must not be left unconstrained.

Recommended controls:
- default `limit`
- maximum time window size
- pagination required for large result sets
- server-side sorting only on approved fields
- optional aggregation or sampling for UI views of large datasets

Primary candidates:
- `/api/v1/market/trades`
- `/api/v1/market/raw-events`
- future order-book endpoints

---

## 12. Backtest and Research Read Path Guidance

At small scale, backtests may read PostgreSQL directly.

At moderate scale:
- prefer exported snapshots, cached datasets, or analytical read paths
- avoid large research scans on the same hot path used by live trading and ingestion

Long-term guidance:
- backtest/research should migrate away from contention with live transactional workloads when practical

---

## 13. Migration Triggers to Analytical Storage

Move a dataset out of hot PostgreSQL when several of the following occur:
- table growth becomes operationally painful
- write amplification hurts primary workloads
- queries require very large scans over tick data
- retention needs become expensive in PostgreSQL
- UI/API needs aggregated views rather than raw scans
- backtests/research compete with live operational workloads

Highest-probability first movers:
- trades
- raw market events
- order book deltas

---

## 14. Compression and Archival Strategy

When moving data out of hot storage:
- preserve canonical identifiers
- preserve partition/time boundaries
- preserve enough metadata for replay or traceability
- prefer append-only archive formats for cold history

Archival workflow should be:
1. identify cold partitions/windows
2. export to archive tier
3. verify export
4. mark archive metadata
5. delete or prune hot storage if policy allows

---

## 15. Operational DB Protection Rules

To protect live correctness:
- large backfills should run in chunked transactions
- maintenance jobs should not monopolize DB resources
- analytical queries should be rate-limited or redirected if needed
- API/UI default views should avoid full-table scans

---

## 16. Recommended Future Deliverables

After adopting this spec, likely follow-up deliverables include:
- explicit partition migration plan for high-volume tables
- archive metadata catalog
- read replica or analytical export design for backtesting
- API window/limit constraints implementation

---

## 17. Minimum Acceptance Criteria

This storage/performance plan is sufficiently specified when:
- storage tiers are defined
- table classes are grouped by retention and scale profile
- PostgreSQL boundaries are explicit
- partition/index guidance exists
- retention and archival principles are defined
- migration triggers to future analytical storage are explicit

---

## 18. Final Summary

The recommended storage strategy is:
- keep transactional and audit-critical data in PostgreSQL
- keep moderate-volume research series in PostgreSQL initially
- treat trades/raw events/order-book data as first migration candidates
- use retention, partitioning, and controlled query windows to keep PostgreSQL healthy
- move very high-volume historical datasets to analytical or object storage when workload justifies it

This provides a practical path to scale without prematurely overcomplicating the stack.