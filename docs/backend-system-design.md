# Backend System Design

## Purpose

This document defines the backend system architecture required to turn the project from a schema-and-docs repository into a runnable trading platform.

It complements:
- `docs/architecture.md`
- `docs/implementation-plan.md`
- `docs/ui-api-spec.md`
- database schema files under `db/init/`

This spec focuses on:
- backend service boundaries
- synchronous vs asynchronous workflow design
- runtime topology
- deployment units
- failure domains
- evolution path from local development to production

---

## 1. Architectural Goals

The backend must support the following without major redesign:
1. market data collection
2. research and backtesting
3. paper trading
4. live trading
5. reconciliation and audit
6. internal UI/API support

The system must also support:
- reproducibility
- idempotent ingestion
- operational visibility
- safe live-trading controls
- progressive scaling of high-volume datasets

---

## 2. Recommended Architectural Style

## 2.1 Phase 0-4: Modular Monolith with Workers

The recommended initial architecture is a **modular monolith plus background workers**.

Why:
- simpler local development
- fewer deployment units early
- easier debugging while contracts stabilize
- lower operational burden before live trading scale exists

In this mode, the project should still maintain strong module boundaries in code even if processes are shared.

## 2.2 Phase 5+: Controlled Process Split

As runtime pressure increases, split the monolith into distinct runtime processes while keeping the same code domains.

Recommended progression:
1. API server
2. background worker(s)
3. scheduler
4. real-time market collector(s)
5. paper/live runtime executor(s)

## 2.3 Long-Term Direction

Long term, the system may evolve into a small set of cooperating services, but it should avoid premature microservice fragmentation.

---

## 3. Backend Runtime Topology

## 3.1 Core Runtime Units

### A. API Server
Responsibilities:
- serve internal UI APIs
- expose health endpoints
- provide reference-data, market, backtest, paper/live inspection APIs
- accept user-triggered actions such as backfills, backtests, paper session start, live order submit

Should not:
- run long backfills inline
- hold long-running strategy loops inline
- process high-volume websocket ingestion inline

### B. Scheduler
Responsibilities:
- trigger periodic jobs
- enqueue recurring sync/backfill/quality/reconciliation tasks
- manage cron-like orchestration

Examples:
- instrument metadata sync
- funding/OI refresh
- gap detection jobs
- reconciliation jobs

### C. Worker
Responsibilities:
- execute asynchronous jobs
- process backfills
- process quality checks
- process reconciliation tasks
- process long-running report generation

### D. Market Collector Runtime
Responsibilities:
- maintain websocket connections to public exchange streams
- normalize inbound payloads
- write raw and normalized market data
- emit collector health and connection events

### E. Strategy / Execution Runtime
Responsibilities:
- run paper sessions
- run live strategy sessions
- translate signals to orders
- enforce runtime execution and risk workflow

### F. Exchange Adapter Layer
Responsibilities:
- encapsulate exchange-specific REST/WS behavior
- normalize payloads to internal contracts
- handle auth/signing for private endpoints

### G. Database Layer
Responsibilities:
- store transactional and metadata records in PostgreSQL
- store high-volume data in PostgreSQL initially, with future tier split

### H. Redis Layer
Responsibilities:
- short-lived state
- distributed locks if needed
- runtime coordination
- cache of latest market state where appropriate

---

## 4. Logical Module Boundaries

The codebase should be organized around these backend modules:

- `config`
- `api`
- `models`
- `storage`
- `reference_data`
- `ingestion`
- `market_data`
- `strategy`
- `backtest`
- `execution`
- `exchange`
- `risk`
- `reconciliation`
- `ops`
- `jobs`

## 4.1 Dependency Direction

Recommended dependency direction:
- `api` depends on domain services, not raw storage details
- domain services depend on repositories and adapters
- repositories depend on DB connection layer
- exchange adapters depend on shared contracts and infra utilities
- runtime modules should not directly depend on UI concerns

Example:
- `execution` may depend on `risk`, `exchange`, `storage`, `models`
- `risk` should not depend on UI or API modules
- `backtest` should reuse canonical models but not private exchange adapters

---

## 5. Synchronous vs Asynchronous Flows

## 5.1 Synchronous Flows

These should generally be request/response flows:
- health checks
- reference-data queries
- market data list/detail queries
- backtest run detail retrieval
- paper/live order detail retrieval
- small admin actions that only enqueue jobs

## 5.2 Asynchronous Flows

These should be job-based:
- instrument sync
- bar backfill
- large trade backfills
- quality checks
- reconciliation tasks
- backtest run execution
- report generation

## 5.3 Long-Running Runtime Flows

These should be separate managed runtimes, not simple API-triggered request handlers:
- websocket collectors
- paper strategy sessions
- live strategy sessions

---

## 6. Request Handling Model

## 6.1 API Request Lifecycle

Recommended flow:
1. request enters API server
2. request is authenticated/authorized
3. request is validated
4. domain service executes immediate logic or enqueues a job
5. response returns standard envelope with request id
6. logs/metrics are emitted

## 6.2 Action Endpoints

For actions like backfills/backtests/session start:
- API validates request
- writes an audit/system log where appropriate
- enqueues job or starts managed runtime
- returns job/session/run identifier immediately

---

## 7. Runtime Session Model

## 7.1 Paper Session

A paper session should be a managed runtime entity with:
- session id
- strategy version
- account/environment
- runtime status
- start/pause/resume/stop lifecycle

## 7.2 Live Session

A live session should be a managed runtime entity with:
- strategy version
- account binding
- explicit environment label
- runtime status
- emergency-stop integration
- auditable lifecycle changes

## 7.3 Session Supervision

Long-running sessions should be supervised by a runtime manager or process runner, not only in-memory API state.

---

## 8. Data Ownership and Write Responsibility

To reduce corruption and race conditions, each major record type should have a primary write owner.

### Reference Data
Primary owner:
- seed scripts
- metadata sync jobs

### Raw Market Events
Primary owner:
- market collector runtime

### Normalized Market Data
Primary owner:
- ingestion normalization pipeline

### Orders / Order Events / Fills
Primary owner:
- execution engine and exchange reconciliation/update consumers

### Positions / Balances
Primary owner:
- execution state updater and periodic reconciliation

### Backtest Records
Primary owner:
- backtest engine

### Risk Events
Primary owner:
- risk engine

### Reconciliation Mismatches
Primary owner:
- reconciliation jobs

---

## 9. Concurrency and Locking Strategy

## 9.1 Required Principles

- avoid duplicate collectors for the same stream unless intentionally sharded
- avoid multiple live runtimes trading the same account/strategy pair simultaneously
- avoid overlapping backfill jobs for identical symbol/window unless explicitly allowed

## 9.2 Recommended Controls

- Redis or DB-backed distributed locks for runtime ownership
- unique job keys for idempotent backfills
- account/strategy session uniqueness constraints at runtime-manager layer
- DB uniqueness constraints where natural keys exist

---

## 10. Failure Domain Design

The backend should isolate failures as much as possible.

### Good failure isolation examples
- bar backfill failure does not kill live runtime
- websocket disconnect does not block API server
- one exchange adapter failure does not stop all jobs
- UI API slowdown does not stop collector writes

### Required boundaries
- API process
- workers
- collectors
- live runtime
- paper runtime

must be separable at process level even if initially launched from one codebase.

---

## 11. Deployment Units by Phase

## 11.1 Local Development
Recommended units:
- PostgreSQL
- Redis
- backend app
- optional worker
- optional frontend app

## 11.2 Mid-Stage Development
Recommended units:
- API server
- scheduler
- worker
- public market collector
- paper runtime

## 11.3 Live Trading Stage
Recommended units:
- API server
- scheduler
- worker pool
- public collector(s)
- live runtime
- reconciliation worker
- frontend
- observability stack

---

## 12. Backend API Server Design Expectations

The API server should:
- be stateless where possible
- delegate heavy work to jobs or managed runtimes
- use a standard response envelope
- propagate request ids to logs and downstream operations
- enforce role-aware action policies for live controls

---

## 13. Exchange Adapter Contract

Each exchange adapter should implement a consistent internal interface for:
- public REST metadata/history fetches
- public websocket stream consumption
- private auth/signing
- order submit/cancel/query
- execution report normalization
- account balance/position retrieval

Adapter responsibilities:
- isolate exchange quirks
- preserve raw identifiers
- map to canonical internal contracts
- classify retryable vs non-retryable failures

---

## 14. Caching and Latest-State Strategy

Redis should be used only for short-lived or coordination-oriented state, such as:
- latest market snapshot cache
- runtime session state cache
- distributed lock state
- ephemeral UI summary cache if needed

Redis should not be treated as the system of record.
PostgreSQL remains the source of truth for persisted audit and transactional data.

---

## 15. Read Path Strategy

Recommended read-path separation:
- API/UI reads mostly from PostgreSQL
- high-frequency runtime decisions may use latest-state cache
- large historical analytics should eventually move to a dedicated analytical path when scale requires it

For backtesting, prefer read paths that avoid competing with live transactional writes once scale grows.

---

## 16. Operational Control Surface

The backend must support operational control primitives:
- start/stop paper session
- start/stop live session
- emergency stop
- cancel all open orders for a scope where supported
- force reconciliation run
- retry failed ingestion job

Each control action must be auditable.

---

## 17. Evolution Path

## Stage A
Modular monolith + PostgreSQL + Redis + single worker

## Stage B
Separate API server, scheduler, worker, collector processes

## Stage C
Split high-volume data path and add stronger runtime isolation for live trading

## Stage D
Introduce analytical storage separation and richer observability stack

---

## 18. Minimum Architecture Acceptance Criteria

This backend architecture is considered sufficiently specified when:
- API server responsibilities are distinct from worker/collector/runtime responsibilities
- sync vs async workflows are explicitly separated
- module boundaries are clear enough for implementation
- deployment units can be introduced without architectural rewrite
- failure isolation goals are explicit
- exchange adapter responsibilities are explicit

---

## 19. Recommended Next Technical Consequences

After adopting this spec, the repository should implement toward:
- `src/api/`
- `src/jobs/`
- `src/runtime/`
- `src/ingestion/`
- `src/exchange/`
- `src/reconciliation/`
- `src/risk/`

and local runtime should eventually expose:
- api server
- worker
- scheduler
- postgres
- redis

---

## 20. Final Summary

The recommended backend architecture is:
- modular monolith in code
- process-separated runtimes as complexity grows
- API for control/query
- workers for async jobs
- collectors for streaming market data
- dedicated runtime loops for paper/live execution
- PostgreSQL as source of truth
- Redis as coordination/cache layer

This is the most practical path to a runnable product without premature microservices.