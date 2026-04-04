# Crypto Trading Data Miner

A design-first repository for building a crypto quantitative trading platform covering:

- market data collection
- backtest / paper trading / live trading workflows
- strategy, execution, risk, treasury, and reconciliation models
- internal operator UI and frontend/backend API design
- system architecture, performance, observability, security, and testing strategy

This repository is no longer just an early scaffold. It now contains a fairly complete specification system for turning the platform into a runnable product.

---

## What Is In This Repo

### Product and planning
- product scope and goals
- phased implementation plan
- phase-by-phase delivery checklists

### Data and schema
- data catalog
- canonical internal API contracts
- PostgreSQL schema and seed data
- bootstrap verification scripts

### Backend architecture
- backend system design
- job orchestration model
- storage and performance strategy
- observability design
- security and secrets model
- execution/risk semantics
- position-management and protection architecture
- PnL and accounting semantics
- testing strategy

### UI and frontend architecture
- UI spec by phase
- frontend/backend API spec
- UI information architecture
- frontend architecture spec
- first frontend foundation slice spec

---

## Current Repo Status

The repository is currently:
- strong in product, data, system, UI, and architecture planning
- implemented through Phase 1 database bootstrap and seed verification
- implemented through the full planned Phase 2 backend foundation, including models, repositories, validation/store service, automated tests, and a minimal models API
- implemented through the first planned Phase 3 Binance public-ingestion slice, including sync/backfill/refresh/stream processing and ingestion-focused API endpoints
- implemented through the planned Phase 4 market-data quality and replay-readiness baseline, including quality jobs, traceability/replay helpers, and quality/replay API endpoints
- now started on Phase 5 with an architecture-aligned strategy/session/backtest skeleton under `src/strategy/`, `src/backtest/`, and `src/models/backtest.py`

Major design areas already covered include:
- product requirements
- implementation phases
- database schema and seed plan
- internal payload contracts
- backend runtime architecture
- async job orchestration
- storage/performance planning
- observability
- security/secrets
- execution/risk behavior
- shared backtest risk-guardrail planning
- extensible position-management and protection architecture
- strategy taxonomy and family/variant/version planning
- strategy/risk/assumption management planning
- backtest/replay reporting and diagnostics planning
- staged backtest/replay diagnostics rollout and future period-level (`year` / `quarter` / `month`) analysis planning
- strategy-lab/workbench planning for parameter sets, assumption bundles, artifacts, compare/analyze, replay scenarios, and review workflow
- repo-local AI memory, session-summary, and cross-session handoff workflow planning for long-running agent-assisted work
- object-level compare/review notes, replay investigation notes, and future workbench annotation planning
- debug-trace staged rollout tracking and resume guidance
- PnL/accounting methodology
- testing strategy
- UI and frontend architecture

Major implementation areas now present include:
- Phase 1 schema bootstrap, seed, and verification flow
- canonical market, strategy, execution, and risk models under `src/models/`
- DB connection, retry, and lookup helpers under `src/storage/`
- repositories for reference, market, execution, risk, and ops persistence paths
- smoke-test scripts for Phase 2 persistence flow
- Binance public ingestion foundation under `src/ingestion/`, `src/jobs/`, and `src/runtime/`
- spot historical bar backfill support through the existing Binance bar-backfill job path
- instrument sync now auto-upserts newly discovered reference assets needed by Binance symbol metadata before instrument writes
- historical funding/OI/mark/index window support through the current market-snapshot refresh path
- historical bars/funding/OI/mark/index fetches now paginate across Binance REST windows instead of only taking the first page
- Phase 4 quality jobs under `src/jobs/data_quality.py`
- dataset-level sanity checks for funding/OI/mark/index under the Phase 4 quality path
- bars gap checks now align requested windows to minute boundaries before calculating expected 1m candles
- spot quality runs now skip perp-only funding/OI/mark/index checks so spot bars can be validated without false snapshot failures
- optional dev-only startup gap remediation under `src/services/startup_remediation.py`
- scheduler-ready market snapshot remediation job under `src/jobs/remediate_market_snapshots.py` for manual/API-triggered funding/OI/mark/index catch-up planning
- minimal FastAPI app with `/api/v1/system/health`, `/api/v1/models/*`, `/api/v1/ingestion/jobs/*`, `/api/v1/quality/*`, `/api/v1/market/*`, `/api/v1/streams/*`, and `/api/v1/replay/readiness`
- a minimal static Monitoring Console under `frontend/monitoring/`, mounted by the API app at `/monitoring`
- Monitoring Console quality cards/tables now read the latest effective check state instead of aggregating every historical quality run
- minimal auth handling for the current models API slice
- replay/retention guidance in `docs/replay-retention-policy.md`
- initial Phase 5 strategy session, execution-policy, protection-policy, and backtest run models under `src/models/backtest.py`
- strategy base interface, registry, and seeded example strategy under `src/strategy/`
- Phase 5 backtest lifecycle/runner skeleton under `src/backtest/`
- Phase 5 bars loader, bar-stream evaluation loop, canonical signal normalization, and optional signal persistence under `src/backtest/` and `src/storage/repositories/strategy.py`
- Phase 5 deterministic bars-based market/limit fill simulation with fee/slippage handling under `src/backtest/`
- Phase 5 first-wave shared risk guardrails with session-level risk policy and blocked-intent runtime summary under `src/backtest/`
- Phase 5 run-level risk overrides, effective risk-policy snapshot persistence, and assumption-bundle metadata linkage under `src/models/backtest.py`, `src/backtest/`, and `src/storage/repositories/backtest.py`
- Phase 5 code-seeded named risk-policy registry foundation plus `/api/v1/backtests/risk-policies` and Backtests UI selection support under `src/backtest/`, `src/api/app.py`, and `frontend/monitoring/`
- Phase 5 code-seeded named assumption-bundle registry foundation plus `/api/v1/backtests/assumption-bundles`, bundle-aware run snapshot persistence, and Backtests UI selection support under `src/backtest/`, `src/api/app.py`, and `frontend/monitoring/`
- richer stateful backtest guardrails for drawdown, daily-loss, leverage, and cooldown are now part of the current Phase 5 shared backtest guardrail baseline
- self-review findings and follow-up issues are tracked in `docs/repo-self-review-tracker.md`
- Phase 5 aggregate portfolio/equity projection plus DB-backed run/order/fill/performance persistence under `src/backtest/` and `src/storage/repositories/backtest.py`
- Phase 5 run-level diagnostics summary projection plus `/api/v1/backtests/runs/{run_id}/diagnostics` under `src/backtest/diagnostics.py` and `src/api/app.py`
- Phase 5 derived `year` / `quarter` / `month` period breakdown plus baseline artifact catalog endpoints under `src/backtest/periods.py`, `src/backtest/artifacts.py`, and `src/api/app.py`
- Phase 5 compare/analyze foundation now includes persisted compare-set identity plus `POST /api/v1/backtests/compare-sets` under `src/backtest/compare.py`, `src/backtest/compare_review.py`, and `src/api/app.py`
- Phase 5 compare-review note foundation now includes seeded system review drafts and `GET/POST /api/v1/backtests/compare-sets/{compare_set_id}/notes` under `src/backtest/compare_review.py`, `src/storage/repositories/research.py`, and `src/api/app.py`
- the current internal Backtests research slice now surfaces compare-set tables plus compare-review notes, including seeded system facts and editable human/agent review notes
- Phase 5 backtest run launch/list/detail API surfaces under `src/api/app.py` and `src/storage/repositories/backtest.py`
- Phase 5 run detail endpoints for simulated orders, fills, signals, and recent timeseries under `src/api/app.py` and `src/storage/repositories/backtest.py`
- bounded recent-bar history plus no-step-cache persisted-run defaults in the current Phase 5 runner to keep longer windows more practical
- automated tests for the current Phase 2/Phase 3/Phase 4 model, storage, API, ingestion, and quality foundation
- automated tests for the current Phase 5 session/strategy/lifecycle skeleton, first bar-stream signal loop, compare/analyze foundation, and compare-review note persistence/API baseline
- automated tests for the current Phase 5 run launch/list/detail API slice and bounded-history runner behavior

Current auth behavior for the implemented API slice:
- `GET /api/v1/system/health` is public
- `/api/v1/models/*` allows local bypass only when `APP_ENV=local` and `ENABLE_LOCAL_AUTH_BYPASS=true`
- outside local bypass mode, `/api/v1/models/*` expects `Authorization: Bearer <token>`
- the current placeholder bearer parser supports `Bearer <role>:<user_id>[:<user_name>]` for early local/shared testing

Auth reference:
- `docs/minimal-auth-contract.md`

Current API response/resource reference:
- `docs/api-resource-contracts.md`

Current local remediation behavior:
- when `APP_ENV=local` and `ENABLE_STARTUP_GAP_REMEDIATION=true`, app startup can run a one-time recent bars gap detection/remediation pass
- this is intended for local/dev only and is not the production remediation model

Current monitoring UI behavior:
- `/monitoring` provides a lightweight internal console for Overview, Backtests, Jobs, Quality, and Traceability views
- it is intentionally an internal monitoring/diagnostic UI, not the full long-term frontend architecture
- the current console now includes a minimal research slice for launching backtests, listing runs, inspecting diagnostics/artifacts/month breakdown, inspecting signals/orders/fills/timeseries, and calling ad hoc compare-set analysis
- the current console now also surfaces compare-review notes for persisted compare sets, including seeded system facts and human/agent review-write flow
- the current console now also surfaces available named backtest risk policies so reusable guardrail profiles can be selected before applying run-level overrides
- the current console depends on the existing API slice and local/shared auth behavior; it does not replace the future React app foundation described in the frontend specs

Current AI memory/handoff workflow behavior:
- repo-visible working memory now has a dedicated home under `docs/agent-memory/`
- the intended stable/task/session/handoff workflow is documented in `docs/ai-memory-and-handoff-spec.md`
- for long-running AI-assisted work, durable state should live in repo files rather than chat history alone
- reusable operator templates now exist for session start, session stop, and CLI/VS Code launch patterns under `docs/agent-memory/`
- repo-provided VS Code tasks now exist for `Memory: Start Session` and `Memory: Stop Session`

Recent local collection validation:
- a real local Binance collection run has been completed for `BTCUSDT_SPOT` and `BTCUSDT_PERP`
- validated data types in that run:
  - `BTCUSDT_SPOT`: instrument sync, historical bars
  - `BTCUSDT_PERP`: instrument sync, historical bars, funding rates, open interest, mark prices, index prices
- `trades` remain intentionally out of the default historical collection flow

---

## Recommended Starting Points

### New to the repo
Read in this order:
1. `docs/spec-index.md`
2. `docs/product-spec.md`
3. `docs/architecture.md`
4. `docs/implementation-plan.md`

### Starting backend work
Read:
1. `docs/backend-system-design.md`
2. `docs/api-contracts.md`
3. `docs/implementation-plan.md`
4. the relevant phase checklist

### Starting frontend work
Read:
1. `docs/frontend-foundation-spec.md`
2. `docs/ui-information-architecture.md`
3. `docs/ui-api-spec.md`
4. `docs/ui-phase-checklists.md`

### Starting data ingestion work
Read:
1. `docs/data-catalog.md`
2. `docs/api-contracts.md`
3. `docs/job-orchestration-spec.md`
4. `docs/data-storage-performance-spec.md`

---

## Docs Entry Point

The main documentation entry point is:

- `docs/spec-index.md`

Use it to understand:
- which specs exist
- which doc is source of truth for each topic
- what order to read docs in
- which docs matter for each implementation phase

---

## Most Important Docs

### Core direction
- `docs/product-spec.md`
- `docs/architecture.md`
- `docs/implementation-plan.md`
- `docs/spec-index.md`
- `docs/ai-memory-and-handoff-spec.md`
- `docs/object-level-notes-and-annotations-spec.md`
- `docs/debug-trace-rollout-plan.md`

### Data and contracts
- `docs/data-catalog.md`
- `docs/data-catalog-addendum.md`
- `docs/api-contracts.md`
- `db/init/*.sql`

### Backend system design
- `docs/backend-system-design.md`
- `docs/job-orchestration-spec.md`
- `docs/data-storage-performance-spec.md`
- `docs/observability-spec.md`
- `docs/security-and-secrets-spec.md`
- `docs/execution-and-risk-engine-spec.md`
- `docs/backtest-risk-guardrails-spec.md`
- `docs/position-management-spec.md`
- `docs/strategy-taxonomy-and-versioning-spec.md`
- `docs/strategy-risk-assumption-management-spec.md`
- `docs/strategy-input-and-feature-pipeline-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`
- `docs/backtest-and-replay-diagnostics-spec.md`
- `docs/strategy-workbench-spec.md`
- `docs/ai-memory-and-handoff-spec.md`
- `docs/object-level-notes-and-annotations-spec.md`
- `docs/pnl-and-accounting-spec.md`
- `docs/testing-strategy-spec.md`

### UI and frontend
- `docs/ui-spec.md`
- `docs/ui-phase-checklists.md`
- `docs/ui-api-spec.md`
- `docs/ui-information-architecture.md`
- `docs/frontend-architecture-spec.md`
- `docs/frontend-foundation-spec.md`

---

## Database Bootstrap

Relevant files:
- `db/init/001_schema.sql`
- `db/init/002_extend_market_and_audit.sql`
- `db/init/003_extend_audit_treasury_latency.sql`
- `db/init/004_seed.sql`
- `db/init/005_execution_fill_dedup.sql`
- `db/init/006_seed_strategy_and_accounts.sql`
- `db/init/007_update_starter_fee_schedule_defaults.sql`
- `db/init/008_compare_sets_and_annotations.sql`
- `docs/database-bootstrap.md`
- `db/verify/phase_1_verification.sql`
- `scripts/verify_phase1.sh`
- `Makefile`

For Phase 1 database bootstrap and verification, start with:
- `docs/phase-1-checklist.md`
- `docs/database-bootstrap.md`

---

## Implementation Progress Model

The repository follows phased delivery from:
1. runtime/bootstrap
2. DB bootstrap and seed
3. models and storage
4. market ingestion
5. data quality
6. backtest
7. paper trading
8. live trading
9. reconciliation/ops
10. production hardening

Phase planning docs:
- `docs/implementation-plan.md`
- `docs/phase-1-checklist.md`
- `docs/phases-2-to-9-checklists.md`

---

## Frontend Progress Model

Frontend planning is also phase-aligned.

Main frontend docs:
- `docs/ui-spec.md`
- `docs/ui-phase-checklists.md`
- `docs/ui-api-spec.md`
- `docs/ui-information-architecture.md`
- `docs/frontend-architecture-spec.md`
- `docs/frontend-foundation-spec.md`

The recommended first frontend slice is:
- route registry
- app shell
- API client base
- query layer conventions
- shared page primitives
- `system`, `bootstrap`, and `reference-data` feature modules

---

## Suggested Next Steps

### If continuing design work
- keep `docs/spec-index.md` updated as the doc entrypoint
- align README whenever major new specs are added

### If starting implementation now
Recommended backend-first sequence:
1. use the Phase 4 quality and replay APIs to validate current Binance data flows
2. begin Phase 5 strategy/backtest work on top of the quality-gated market data and the phased architecture freeze in `docs/position-management-spec.md`
3. keep checklist and replay docs in sync as the first backtest slice lands

Recommended frontend-first sequence:
1. use `/monitoring` as the current operational console for data-flow monitoring
2. build the longer-term frontend foundation slice when product UI work begins
3. implement Phase 0 and Phase 1 product pages on top of that foundation

---

## Repository Mental Model

A simple way to think about this repo:

- `product-spec` says what to build
- `implementation-plan` says what order to build it in
- `data-catalog` and `api-contracts` define the system data model
- `db/init/*.sql` defines implemented DB shape
- backend architecture specs define how the system runs safely
- UI/frontend specs define how users inspect and operate it
- testing strategy defines how to trust it

---

## Contribution Guidance

When adding or changing major design decisions:
- update the relevant spec
- update `docs/spec-index.md` if a major spec is added
- update `README.md` if repo entry guidance changes materially

When doing long-running AI-assisted work:
- use `docs/ai-memory-and-handoff-spec.md` as the process guide
- keep `docs/agent-memory/` updated instead of relying on chat history as the only memory layer

When there is a conflict:
- implementation SQL beats schema description docs for current DB state
- deeper architecture/system spec beats checklist wording unless intentionally revised later
- more specific topic doc beats README
