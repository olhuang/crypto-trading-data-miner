# Job Orchestration Spec

## Purpose

This document defines the orchestration model for asynchronous jobs in the trading platform.

It covers:
- job types
- scheduling rules
- queue and worker behavior
- idempotency rules
- retry and dead-letter handling
- concurrency controls
- cancellation and recovery semantics

This spec complements:
- `docs/backend-system-design.md`
- `docs/implementation-plan.md`
- `docs/data-storage-performance-spec.md`

---

## 1. Goals

The orchestration layer must support:
1. repeatable batch work
2. periodic sync work
3. safe retries
4. observable progress and failures
5. concurrency control for data and trading safety
6. future extension to more exchanges and more jobs

---

## 2. Job Categories

## 2.1 Reference Data Jobs
Examples:
- instrument metadata sync
- fee schedule sync
- margin tier sync

## 2.2 Market Data Backfill Jobs
Examples:
- bar backfill
- trade history backfill
- funding history backfill
- OI backfill
- mark/index history backfill

## 2.3 Market Data Maintenance Jobs
Examples:
- freshness checks
- gap detection
- duplicate checks
- raw data reprocessing

## 2.4 Research Jobs
Examples:
- backtest run execution
- report generation
- dataset export

## 2.5 Reconciliation Jobs
Examples:
- order reconciliation
- fill reconciliation
- funding reconciliation
- ledger reconciliation
- treasury reconciliation

## 2.6 Operational Jobs
Examples:
- cleanup/archive jobs
- retention enforcement
- replay preparation
- alert generation

---

## 2.7 Current Backfill Capability Snapshot

This section records the implemented backfill/remediation state as of the current local development baseline.

It exists to prevent ambiguity about:
- what data is collected automatically during a long-running app/runtime process
- what data can be backfilled manually today
- what data has dev-only startup remediation support
- what data does **not** yet have continuous auto catch-up

### Capability Matrix

| Data type | Live auto collect | Historical manual backfill | Startup remediation | Continuous auto catch-up |
| --- | --- | --- | --- | --- |
| `md.bars_1m` | No | Yes | Yes, dev-only, recent window | No |
| `md.trades` | Yes, when trade-stream runtime is running | No | No | No |
| `md.funding_rates` | Yes, when market snapshot refresh runs | Yes | No | No |
| `md.open_interest` | Yes, when market snapshot refresh runs | Yes | No | No |
| `md.mark_prices` | Yes, when market snapshot refresh or stream path runs | Yes | No | No |
| `md.index_prices` | Yes, when market snapshot refresh runs | Yes | No | No |
| `md.liquidations` | Yes, when trade-stream runtime is running | No | No | No |
| `md.raw_market_events` | Yes, for currently received live stream events | No | No | No |
| `md.orderbook_snapshots` | No | No | No | No |
| `md.orderbook_deltas` | No | No | No | No |

### Recorded Decision: Historical Trades Backfill Policy

The current project decision is:
- historical `md.trades` support should remain **manual-trigger only**
- historical trade backfill should **not** be wired into app-startup remediation
- historical trade backfill should **not** be wired into a continuous auto catch-up loop in the current implementation phase

Reasons:
- trade volume is materially larger than bars and would make startup behavior unpredictable
- long-window trade backfill needs chunking, stronger checkpointing, and stricter DB/rate-limit controls than the current lightweight remediation path
- the near-term goal is to preserve an operator-triggered way to fetch bounded historical trade windows without silently expanding background system load

### Meaning of Each Column

#### Live auto collect
The system continuously receives **new** data while the relevant runtime/job is operating.

#### Historical manual backfill
The system has an explicit backfill path today, but only when the developer/operator triggers it.

#### Startup remediation
The system may perform a one-time catch-up/remediation pass during app startup.

#### Continuous auto catch-up
The system continuously detects missing history and remediates it without manual triggers or startup-only hooks.

### Current Constraints by Mode

#### Why some data is not covered by `Live auto collect`
- `bars_1m` currently come from explicit historical kline backfill, not from a continuously running candle collector.
- order book datasets are not yet wired into runtime ingestion.

#### Why some data is not covered by `Historical manual backfill`
- `trades` do not yet have a dedicated historical trade-backfill job.
- `liquidations` do not yet have a dedicated historical liquidation-backfill path.
- `raw_market_events` represent stored live raw payloads; a complete historical raw replay source is not currently available from the implemented venue path.
- order book snapshot/delta history is not yet implemented due to higher replay/state-merge complexity.

#### Why some data is not covered by `Startup remediation`
- startup remediation is intentionally limited to recent `bars_1m` windows in local/dev to keep app startup predictable.
- `trades`, `liquidations`, and `raw_market_events` do not follow a simple fixed-cadence gap model like bars.
- `funding_rates`, `open_interest`, `mark_prices`, and `index_prices` are backfillable today, but are not yet connected to startup remediation because the current startup hook is intentionally minimal and bars-focused.
- large/high-volume datasets are not appropriate for automatic app-startup catch-up because they would slow startup and blur the boundary between local convenience and real orchestration.

#### Why most data is not covered by `Continuous auto catch-up`
- there is no recurring remediation worker yet that scans `ops.data_gaps`, schedules follow-up backfills, and marks gaps resolved continuously.
- current remediation is either manual or dev-only startup behavior, not a long-running scheduler-driven control loop.
- production-safe controls such as retry policies, concurrency guards, checkpointing, and remediation prioritization have not yet been built for a full catch-up engine.

### Technical Limitations to Preserve for Future Work

#### Bars
- bars have the cleanest remediation shape because they have a fixed cadence and idempotent writes by `(instrument_id, bar_time)`.
- this is why bars were the first and only dataset connected to startup remediation.

#### Trades
- historical trade backfill would be much heavier than bars and needs chunking, dedupe discipline, and stricter DB/query safety.
- trade volume makes startup-time catch-up a poor default.
- even after historical trade backfill is implemented, the intended default is manual/operator-triggered bounded windows rather than automatic remediation.

#### Funding / OI / Mark / Index
- these now support bounded historical backfill windows.
- they are good candidates for future scheduler-driven catch-up, but they are not yet wired into a continuous remediation loop.

#### Raw Events
- raw live events can be captured only from currently observed streams.
- historical raw events are not assumed to be fully recoverable from the venue in the same way normalized historical datasets may be.

#### Order Book Data
- order book replay requires more than persistence; it requires a consistent snapshot/delta merge and replay model.
- this is intentionally deferred until replay/microstructure needs justify the complexity.

### Current Recommended Interpretation

- If the goal is **keep receiving new live data**, the current runtime/refresh paths are sufficient for trades and snapshot-style market data.
- If the goal is **repair missed recent bars during local development**, use the dev-only startup remediation hook.
- If the goal is **repair broader historical gaps**, use explicit backfill jobs today.
- If the goal is **prepare funding/OI/mark/index remediation for future scheduling**, use the scheduler-ready market-snapshot remediation job and keep actual scheduling/manual triggering separate from the remediation logic.
- If the goal is **fully automatic catch-up without manual intervention**, that remains future work and should be implemented as a scheduler/worker remediation flow rather than expanded app-startup behavior.

### Recommended Remediation Pattern by Data Type

This table records which remediation model best fits each currently relevant dataset.

| Data type | Best-fit remediation pattern | Current implemented status | Why this pattern fits | Why other patterns are a bad fit right now |
| --- | --- | --- | --- | --- |
| `md.bars_1m` | gap remediation | manual backfill + dev startup remediation | bars have fixed cadence and clear missing-interval detection | snapshot freshness alone is not enough; trade-style heavy backfill logic is unnecessary |
| `md.trades` | manual bounded backfill | live auto collect only; historical backfill still pending | trade history is high volume and should stay operator-triggered with chunking/checkpoint control | startup remediation would slow app startup; continuous catch-up needs stronger orchestration and capacity controls |
| `md.funding_rates` | scheduler-ready snapshot remediation | bounded history refresh + scheduler-ready remediation job | low-frequency periodic series with stable timestamp semantics and bounded fetch windows | bars-style gap segmentation is less natural; startup remediation is unnecessary and too coupled to app lifecycle |
| `md.open_interest` | scheduler-ready snapshot remediation | bounded history refresh + scheduler-ready remediation job | periodic snapshot-like data with a straightforward freshness/window policy | startup remediation adds little value; historical depth is venue-limited so a full generic catch-up engine is overkill today |
| `md.mark_prices` | scheduler-ready snapshot remediation | bounded history refresh + scheduler-ready remediation job | periodic price series with timestamped windows and idempotent upserts | bars-style cadence checks are less important than freshness; startup remediation would blur local-vs-operational behavior |
| `md.index_prices` | scheduler-ready snapshot remediation | bounded history refresh + scheduler-ready remediation job | same operational shape as mark prices and open interest | same limits as mark prices; no need for startup remediation |
| `md.liquidations` | manual backfill or future event-stream remediation | live auto collect only | liquidation events are irregular event-stream data, not fixed cadence or simple snapshots | snapshot freshness logic does not model them well; startup remediation is not a natural fit |
| `md.raw_market_events` | retain live only; not assumed replay-backfillable | live auto collect only | raw events exist mainly for observed-stream traceability and debugging | historical replay source is not assumed to exist in the same recoverable form |
| `md.orderbook_snapshots` | future specialized replay remediation | not implemented | order book state needs snapshot/delta coordination and replay semantics | neither simple gap remediation nor simple snapshot freshness is enough |
| `md.orderbook_deltas` | future specialized replay remediation | not implemented | deltas only make sense with ordered replay, checkpointing, and merge correctness | startup/manual generic remediation would be misleading without replay guarantees |

### Practical Decision Rules

- Use **gap remediation** for fixed-cadence series where missing intervals are the main failure mode.
- Use **scheduler-ready snapshot remediation** for bounded periodic datasets where freshness and recent-window catch-up matter more than exact per-interval continuity.
- Use **manual bounded backfill** for high-volume or operator-sensitive datasets where automatic catch-up would create too much DB, startup, or rate-limit risk.
- Use **specialized replay remediation later** for order book and other stateful stream datasets that cannot be safely modeled by simple freshness or gap checks.

---

## 3. Orchestration Model

## 3.1 Recommended Runtime Model

Use a queue-backed worker model with:
- scheduler for recurring jobs
- workers for execution
- DB/Redis-backed visibility for job ownership and status

## 3.2 Scheduler Responsibilities

The scheduler should:
- enqueue cron-like recurring jobs
- enforce phase/environment-specific schedules
- avoid duplicate enqueue for singleton jobs in the same schedule window

## 3.3 Worker Responsibilities

Workers should:
- claim jobs
- update status lifecycle
- emit structured progress metadata
- retry retryable failures
- route terminal failures to dead-letter storage or equivalent review path

---

## 4. Job Lifecycle

Every job should move through a defined lifecycle.

Recommended statuses:
- `queued`
- `claimed`
- `running`
- `succeeded`
- `failed_retryable`
- `failed_terminal`
- `canceled`
- `dead_lettered`

Optional progress states:
- `partially_completed`
- `waiting_on_dependency`

---

## 5. Job Identity and Idempotency

## 5.1 Job Identity

Every enqueued job should have:
- `job_id`
- `job_type`
- `job_key`
- `created_at`
- `requested_by`
- `environment`
- `payload_json`

## 5.2 Job Key

`job_key` should be a deterministic identifier for duplicate suppression when appropriate.

Examples:
- `instrument_sync:binance:2026-04-02T00:00Z`
- `bar_backfill:binance:BTCUSDT_PERP:1m:2026-03-01:2026-03-02`
- `reconcile_orders:binance_live_01:2026-04-02T12:00Z`

## 5.3 Idempotency Rules

A job must be safe to retry if:
- it writes using idempotent upserts, or
- it tracks checkpoint progress and can resume safely

Jobs that trigger side effects must define stronger safety rules.

Examples:
- metadata sync: safe to retry
- bar backfill: safe if writes are idempotent
- live order placement: not a general-purpose retryable background job without explicit idempotency protection

---

## 6. Queue Design

## 6.1 Recommended Queue Classes

Use separate logical queues or priorities for:
- `critical_runtime`
- `market_ingestion`
- `reference_sync`
- `backfill`
- `quality_checks`
- `backtests`
- `reconciliation`
- `maintenance`

## 6.2 Priority Guidance

Highest priority:
- runtime-critical reconciliation supporting live state integrity
- exchange status or protective jobs

Medium priority:
- reference sync
- quality checks
- scheduled reconciliation

Low priority:
- large historical backfills
- archival/maintenance jobs
- long report generation

## 6.3 Queue Isolation Principle

Large backfills must not starve runtime-critical work.
Backfill queues should be isolated from runtime and operational safety queues.

---

## 7. Retry Policy

## 7.1 Retryable Failures

Examples:
- transient network error
- exchange timeout
- rate-limit cooldown
- temporary DB connectivity loss
- lock acquisition timeout

## 7.2 Non-Retryable Failures

Examples:
- invalid payload definition
- unsupported symbol mapping
- malformed request parameters
- permanent authorization failure
- invariant violation caused by code or config bug

## 7.3 Retry Strategy

Recommended defaults:
- exponential backoff with jitter
- max attempts by job type
- retry metadata persisted with the job

Suggested initial defaults:
- metadata sync: 5 retries
- small polling sync: 5 retries
- bar backfill chunk: 8 retries
- reconciliation task: 5 retries
- long-running backtest run: 2 retries or manual rerun

---

## 8. Dead-Letter Handling

Jobs should be dead-lettered when:
- max retry attempts are exceeded
- terminal failure classification occurs
- repeated partial progress failures imply human intervention is needed

Dead-letter records should include:
- original job payload
- final error class/message
- retry history
- worker id
- timestamps
- suggested remediation category

---

## 9. Scheduling Rules

## 9.1 Recurring Jobs

Examples and guidance:
- instrument sync: hourly or daily depending on venue
- funding refresh: aligned to funding event cadence
- OI refresh: every few minutes
- data freshness checks: every few minutes
- reconciliation: periodic, with higher frequency for live accounts
- archival/retention jobs: daily or weekly

## 9.2 Manual Jobs

Manual jobs may be triggered by UI or API.
Examples:
- bar backfill
- replay preparation
- forced reconciliation run

Manual jobs must record:
- `requested_by`
- trigger source
- request parameters

## 9.3 Singleton Scheduling

Some recurring jobs should be singleton per scope.
Examples:
- one instrument sync per exchange at a time
- one reconciliation job per account/scope/window at a time

---

## 10. Concurrency Controls

## 10.1 General Concurrency Rules

- prevent duplicate jobs for same scope/window when not intended
- limit concurrent backfill chunks per exchange/symbol if rate-limit sensitive
- prevent conflicting jobs from updating the same logical state simultaneously

## 10.2 Examples

### Bar Backfill
Allow chunked concurrency by symbol and non-overlapping window.
Disallow overlapping window jobs for same symbol+interval.

### Instrument Sync
Allow only one sync per exchange at a time.

### Reconciliation
Allow one reconciliation job per account/scope at a time unless split by clear partition.

### Backtest Runs
Allow multiple backtests concurrently, but control CPU/memory quota.

---

## 11. Checkpointing and Resume Semantics

Long-running jobs should support checkpoints where practical.

Recommended checkpoint fields:
- `last_processed_key`
- `last_processed_time`
- `completed_chunks`
- `remaining_chunks`
- `partial_row_counts`

Good candidates:
- trade backfill
- bar backfill
- reconciliation over large history windows
- report generation over large datasets

---

## 12. Cancellation Rules

Jobs should support cancellation where safe.

Cancelable examples:
- queued backfill
- running backfill chunk if checkpoint/resume safe
- report generation

Not easily cancelable or requiring special handling:
- live side-effecting workflows already sent to exchange
- critical reconciliation in final commit phase

Canceled jobs must persist cancellation metadata.

---

## 13. Job Observability Requirements

Every job must produce:
- start time
- finish time
- duration
- queue latency
- status transitions
- worker id
- row counts or work counts where relevant
- structured error metadata on failure

Primary persistence targets:
- `ops.ingestion_jobs`
- `ops.data_quality_checks`
- `ops.system_logs`
- future generic job table if introduced later

---

## 14. API / UI Integration Pattern

Long-running jobs should follow this pattern:
1. user triggers action via API
2. API validates and enqueues job
3. API returns `job_id`
4. UI polls job status endpoint or a domain list endpoint
5. final status is visible with error/progress metadata

This pattern should be consistent for:
- backfills
- instrument sync
- backtests
- reconciliation runs

---

## 15. Recommended Future Generic Job Tables

The current schema already includes `ops.ingestion_jobs`, but as orchestration grows, consider a more general-purpose job tracking layer with:
- `ops.jobs`
- `ops.job_attempts`
- `ops.dead_letter_jobs`

This is not required immediately if domain-specific tracking remains sufficient early on.

---

## 16. Performance Rules for Jobs

- chunk historical backfills by time window and symbol
- avoid giant all-history jobs in one worker transaction
- limit write batch size to avoid oversized DB transactions
- use queue isolation to keep large jobs from starving critical ones
- prefer resumable jobs over monolithic jobs

---

## 17. Security and Safety Rules

- manual UI-triggered jobs must record actor identity
- production live-related jobs require stricter authorization
- destructive maintenance jobs should require explicit confirmation and audit record
- jobs affecting exchange state should never be silently retried without idempotency guarantees

---

## 18. Minimum Acceptance Criteria

The orchestration model is sufficiently specified when:
- job categories are defined
- lifecycle statuses are standardized
- retry and dead-letter policy is defined
- concurrency/isolation rules are defined
- long-running job checkpoint guidance exists
- UI/API trigger and status model is clear

---

## 19. Final Summary

The recommended orchestration design is:
- scheduler for recurring work
- queue-backed workers for asynchronous execution
- deterministic job identity where duplicate suppression matters
- isolated queues by priority and workload type
- explicit retry, checkpoint, and dead-letter handling
- observable status/progress for UI and operations

This is the required foundation for reliable ingestion, backfills, backtests, and reconciliation.
