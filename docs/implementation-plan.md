# Implementation Plan

## Purpose

This document turns the current product spec, data catalog, API contracts, and database schema into a phased delivery plan.

The plan is designed so that each phase can be implemented and delivered independently, while still fitting into the long-term architecture of the project.

---

## 1. Current Project Status

The repository already has a strong design foundation and is now design-complete enough to begin systematic implementation for the early phases.

### Completed
- product definition and scope in `docs/product-spec.md`
- data collection scope in `docs/data-catalog.md`
- additional operational data scope in `docs/data-catalog-addendum.md`
- internal payload contracts in `docs/api-contracts.md`
- PostgreSQL base schema in `db/init/001_schema.sql`
- market microstructure and audit extensions in `db/init/002_extend_market_and_audit.sql`
- treasury, deployment audit, financing, latency, and allocation extensions in `db/init/003_extend_audit_treasury_latency.sql`
- initial reference-data seed in `db/init/004_seed.sql`
- execution fill dedup bootstrap hardening in `db/init/005_execution_fill_dedup.sql`
- strategy/account bootstrap defaults in `db/init/006_seed_strategy_and_accounts.sql`
- local runtime scaffold with `docker-compose.yml`, `.env.example`, and minimal `src/` bootstrap
- Phase 1 bootstrap verification artifacts and scripts
- Phase 1 end-to-end verification against a clean bootstrap
- complete Phase 2 model coverage across market, strategy, execution, and risk contracts in `src/models/`
- Phase 2 DB/storage helpers, lookup resolution, retry policy, and repositories in `src/storage/`
- Phase 2 validation/store service and minimal FastAPI endpoints in `src/services/` and `src/api/`
- automated tests for the current Phase 2 models, repositories, DB retry helper, seeds, and minimal API slice
- initial Phase 3 Binance public ingestion foundation in `src/ingestion/`, `src/jobs/`, and `src/runtime/`
- Phase 3 ingestion and market-query API endpoints in `src/api/`
- automated tests for the Phase 3 instrument sync, bar backfill, funding/open-interest refresh, and trade-stream slice
- the existing bar-backfill path now supports both Binance perp and spot historical bars
- instrument sync now also auto-upserts newly discovered Binance assets into `ref.assets` before instrument writes
- historical funding/open-interest/mark/index windows are now supported through the current market-snapshot refresh path
- the current Binance historical fetch paths now paginate through multi-page REST windows for bars, funding, OI, mark, and index history
- Phase 4 data-quality jobs for gap, freshness, and duplicate checks in `src/jobs/data_quality.py`
- the current Phase 4 quality path now aligns requested bar windows to minute boundaries and treats spot symbols as ineligible for perp-only funding/OI/mark/index checks
- Phase 4 quality, raw-event traceability, and replay-readiness API endpoints in `src/api/`
- replay and hot-retention baseline documented in `docs/replay-retention-policy.md`
- automated tests for the current Phase 4 quality, traceability, and replay-readiness slice
- dev-only startup gap-remediation support for recent bars windows in local app runs
- a minimal static Monitoring Console under `frontend/monitoring/` for Overview, Jobs, Quality, and Traceability views backed by the existing Phase 3/4 APIs
- quality summary/check inspection now supports a latest-only monitoring mode so dashboards can focus on current effective dataset health instead of cumulative historical runs
- `docs/position-management-spec.md` now freezes the intended extensible architecture for Phase 5-8 position management, execution ownership, protection state, and reporting
- `docs/strategy-taxonomy-and-versioning-spec.md` now freezes the intended family/variant/version identity model for strategy registration, research comparison, and future promotion
- `docs/strategy-input-and-feature-pipeline-spec.md` now freezes the intended long-lived plan for multi-dataset strategy inputs, feature alignment, and no-look-ahead handling
- `docs/strategy-research-and-evaluation-spec.md` now freezes the intended long-lived plan for strategy development, research, testing, and comparative evaluation
- `docs/strategy-risk-assumption-management-spec.md` now freezes the intended management model for strategy identity, risk policy identity, assumption bundles, and effective run snapshots
- `docs/backtest-and-replay-diagnostics-spec.md` now freezes the intended plan for run reporting, debug traces, replay diagnostics, and UI inspection needs
- `docs/debug-trace-rollout-plan.md` now tracks the concrete staged rollout for Level 1 / Level 2 / Level 3 debug-trace work and the next recommended resume slice
- `docs/backtest-risk-guardrails-spec.md` now freezes the intended shared pre-trade guardrail model for Phase 5 backtests and later paper/live reuse
- `docs/ai-memory-and-handoff-spec.md` now freezes the intended repo-local memory, summary, and cross-session handoff workflow for long-running AI-assisted implementation work
- reusable session-start, session-stop, and CLI/editor memory-workflow templates now exist under `docs/agent-memory/`
- repo-provided VS Code tasks and PowerShell helper scripts now exist for applying the memory workflow consistently
- initial Phase 5 strategy/session/backtest skeleton now exists under `src/models/backtest.py`, `src/strategy/`, and `src/backtest/`
- Phase 5 bars loading, bar-by-bar strategy evaluation, canonical signal normalization, and optional signal persistence now exist under `src/backtest/` and `src/storage/repositories/strategy.py`
- automated tests now cover the current Phase 5 session, registry, example strategy, and lifecycle-planning skeleton
- automated tests now also cover the current Phase 5 bar-stream loop and target-position-to-signal normalization path
- the current Phase 5 runner now also includes a first shared backtest-risk-guardrail layer with session-level risk policy, blocked-intent diagnostics summary, and minimal UI launch controls
- the current Phase 5 run/session model now also supports run-level risk overrides, effective risk-policy snapshot persistence, and assumption-bundle metadata linkage without requiring a future schema redesign
- the current Phase 5 slice now also includes a code-seeded named risk-policy registry foundation plus API/UI selection support for reusable backtest guardrail profiles

### Not Yet Implemented
- backtest engine
- paper trading engine
- live trading adapter
- reconciliation jobs
- CI

### Overall Assessment
The project is currently strong on design and still weak on executable implementation.
For upcoming work, the repo should be treated as architecture-ready for Phase 5-8 as long as implementation follows `docs/position-management-spec.md` instead of inventing separate backtest, paper, and live lifecycle models.
However, the repository is now sufficiently specified to begin real implementation work for Phase 1–3 without another major architecture-planning round.

### Latest Local Validation Note
- the current Binance ingestion slice has now been exercised against the real venue path for:
  - `BTCUSDT_SPOT` historical bars
  - `BTCUSDT_PERP` historical bars
  - `BTCUSDT_PERP` funding/open-interest/mark/index history windows
- this validation is intentionally narrower than full-universe or all-history collection, but it confirms that the current Phase 3 collection path works against real Binance responses for the first target symbol pair

---

## 2. Delivery Principles

Each phase in this plan should satisfy all of the following:

1. be independently implementable
2. produce a concrete deliverable
3. have clear acceptance criteria
4. leave the repository in a usable state
5. avoid blocking later phases through premature overengineering

The recommended build order is:

1. database bootstrap
2. core models and storage
3. market data ingestion
4. market data quality baseline
5. backtest engine
6. paper trading
7. live trading
8. reconciliation and operations hardening
9. production hardening

---

## 3. Phase Plan

## Phase 0: Repository and Runtime Bootstrap

### Goal
Make the repository runnable locally and prepare the development environment.

### Scope
- confirm local Docker runtime
- confirm PostgreSQL and Redis startup
- confirm Python environment and dependency installation
- make repository bootstrap reproducible

### Deliverables
- working `docker-compose.yml`
- working `.env.example`
- developer bootstrap steps in `README.md` or a dedicated setup doc
- optional `Makefile` or `scripts/` helpers

### Suggested Tasks
- add `Makefile` targets such as `up`, `down`, `logs`, `reset-db`
- add `scripts/wait_for_postgres.sh` or equivalent helper
- verify minimal app startup using `src/main.py`

### Acceptance Criteria
- developer can clone repo and run local services successfully
- PostgreSQL is reachable from local app code
- Redis is reachable from local app code

### Dependencies
- none

### Recommended Status
- partially started

---

## Phase 1: Database Bootstrap and Seed Data

### Goal
Make the database schema installable and usable with a real initial dataset.

### Scope
- initialize all current migrations
- seed exchanges, assets, and instruments
- define schema initialization workflow

### Deliverables
- `db/init/004_seed.sql`
- repeatable DB initialization process
- first exchange and instrument seed set

### Suggested Seed Data
- exchanges: Binance, Bybit
- assets: BTC, ETH, USDT, USDC
- instruments:
  - BTCUSDT spot
  - ETHUSDT spot
  - BTCUSDT perp
  - ETHUSDT perp

### Suggested Tasks
- add seed inserts for `ref.exchanges`
- add seed inserts for `ref.assets`
- add seed inserts for `ref.instruments`
- optionally add starter `ref.fee_schedules`
- document seed assumptions

### Acceptance Criteria
- database boots from empty state
- all migrations apply successfully
- seed data can be queried immediately after bootstrap
- at least one spot and one perp instrument per exchange are available

### Dependencies
- Phase 0

### Recommended Status
- implemented and verified from a clean bootstrap flow

---

## Phase 2: Domain Models and Storage Layer

### Goal
Turn documented contracts into validated code and a consistent database access layer.

### Scope
- Pydantic models for core entities
- database connection layer
- repository layer for inserts/upserts/queries

### Deliverables
- `src/models/`
- `src/storage/`
- database session / connection utilities
- repository interfaces for core tables

### Suggested Module Layout
- `src/models/market.py`
- `src/models/strategy.py`
- `src/models/execution.py`
- `src/models/risk.py`
- `src/storage/db.py`
- `src/storage/repositories/`

### Suggested Tasks
- implement Pydantic models aligned with `docs/api-contracts.md`
- create PostgreSQL connection helper
- implement repositories for:
  - instruments
  - bars
  - trades
  - funding rates
  - open interest
  - orders
  - fills
  - positions
  - balances
- add upsert patterns for idempotent ingestion

### Acceptance Criteria
- canonical payloads validate through models
- validated payloads can be persisted to PostgreSQL
- duplicate records are safely handled for market data and fills
- storage layer is reusable by ingestion, backtest, and execution code

### Dependencies
- Phase 1

### Recommended Status
- implemented for the Phase 2 scope
- validated locally with automated tests for model validation, repository persistence, DB retry behavior, and minimal API flows
- completed and serving as the stable foundation for the implemented Phase 3 ingestion slice

---

## Phase 3: Public Market Data Ingestion

### Goal
Start collecting usable exchange market data into the database.

### Scope
- first exchange public adapter
- historical backfill
- basic real-time collection
- ingestion monitoring

### Deliverables
- `src/ingestion/`
- first exchange public REST client
- first exchange public websocket client
- ingestion jobs for bars, trades, funding, and open interest

### Suggested First Exchange
- Binance

### Suggested Data Collection Order
1. instruments metadata
2. bars_1m
3. trades
4. funding_rates
5. open_interest
6. mark_prices
7. index_prices
8. orderbook snapshot/delta
9. raw market events

### Suggested Tasks
- implement `src/ingestion/base.py`
- implement `src/ingestion/binance/public_rest.py`
- implement `src/ingestion/binance/public_ws.py`
- implement backfill job for bars
- implement sync job for instruments
- persist ingestion job status to `ops.ingestion_jobs`
- persist quality checks to `ops.data_quality_checks`

### Acceptance Criteria
- system can backfill historical bars into `md.bars_1m`
- the current bar-backfill job can now backfill both Binance perp and spot bars through the same endpoint/path
- system can ingest live trades from websocket into `md.trades`
- funding and open interest can be periodically refreshed
- funding, open interest, mark prices, and index prices can also be backfilled for bounded historical windows through the existing refresh job
- ingestion failures and gaps are recorded in ops tables

### Dependencies
- Phase 2

### Recommended Status
- implemented for the first Binance public-data slice
- validated locally with mocked Binance transport, real repository writes, and automated tests for sync, backfill, refresh, and websocket-processing flows
- ready for Phase 4 market-data quality and replay-readiness work

---

## Phase 4: Market Data Quality and Replay Readiness

### Goal
Make collected market data reliable enough for research and downstream execution testing.

### Scope
- gap detection
- freshness checks
- duplicate detection
- raw payload retention
- replay readiness

### Deliverables
- quality validation jobs
- gap remediation workflow
- raw payload retention policy
- replayable market data baseline

### Suggested Tasks
- implement data gap detection job
- implement duplicate and freshness checks
- add reprocessing workflow from `md.raw_market_events`
- define retention policy for raw events and order book data

### Acceptance Criteria
- bars, trades, and funding data have automated gap checks
- raw market events can be traced back to normalized tables
- quality checks are visible in `ops.data_quality_checks`
- missing intervals are visible in `ops.data_gaps`

### Dependencies
- Phase 3

### Recommended Status
- implemented for the current Phase 4 baseline
- validated locally with automated checks for gap detection, freshness checks, duplicate detection, raw-event traceability, and replay-readiness APIs
- funding/open-interest/mark/index dataset-level sanity checks now exist within the Phase 4 quality path
- current quality runs now avoid false bar gap off-by-one results from non-minute windows and avoid false spot snapshot failures by skipping perp-only datasets for `_SPOT` symbols
- complete enough to support Phase 5 bars-based research on quality-gated market data
- local development can optionally remediate recent bar gaps during app startup without introducing a continuous scheduler dependency yet
- historical trades should remain manual bounded backfill work when introduced, rather than being added to startup remediation or continuous auto catch-up by default
- funding/open-interest/mark/index now also have a scheduler-ready remediation job shape for manual/API-triggered catch-up planning without enabling a continuous remediation loop yet
- future enhancement still pending: cross-dataset diagnostic checks such as funding vs nearby mark/index alignment, mark-vs-index spread sanity, and raw-to-normalized coverage correlation summaries
- current monitoring UI is intentionally a lightweight internal console, not the final long-term product frontend foundation
- the Phase 5 backtest path now includes deterministic bars-based market/limit fill simulation, aggregate portfolio/equity projection, DB-backed persisted runs, run launch/list/detail API surfaces, run detail endpoints for signals/orders/fills/timeseries, a first run-level diagnostics summary API, derived year/quarter/month period-breakdown plus artifact-catalog outputs, a persisted compare-set baseline for side-by-side run KPI comparison/assumption diffs/benchmark overlays, and the first compare-review note foundation across API and internal UI; it still needs step traces, replay-note workflow, and a fuller research UI

---

## Phase 5: Strategy Runner and Bars-Based Backtest

### Architecture Prerequisite
Before implementing Phase 5 internals, treat `docs/position-management-spec.md` as the planning backbone for:
- strategy book vs account book separation
- fill-level execution truth
- phased TP / SL and protection rollout
- future compatibility with paper/live/reconciliation work

Also treat `docs/strategy-input-and-feature-pipeline-spec.md` as the planning backbone for:
- bars-only MVP scope
- future funding/OI/mark/index strategy inputs
- time alignment and no-look-ahead rules
- future feature-pipeline expansion beyond bars

Also treat `docs/strategy-research-and-evaluation-spec.md` as the planning backbone for:
- strategy development workflow
- multi-window evaluation
- multi-strategy and multi-parameter comparison
- promotion-oriented research evidence

Also treat `docs/strategy-taxonomy-and-versioning-spec.md` as the planning backbone for:
- family vs variant vs version identity
- stable interpretation of current `strategy_code` and `strategy_version`
- future compare/analyze grouping and promotion semantics

Also treat `docs/backtest-and-replay-diagnostics-spec.md` as the planning backbone for:
- backtest report outputs
- debug trace outputs
- replay diagnostics and future replay UI/API surfaces
- `docs/debug-trace-rollout-plan.md` should be treated as the implementation tracking companion for the debug-trace portion of this work

Also treat `docs/backtest-risk-guardrails-spec.md` as the planning backbone for:
- shared pre-trade guardrails in backtest
- session-level risk-policy configuration
- phased reuse of guardrail semantics in paper/live
- blocked-intent diagnostics and research inspection

Also treat `docs/strategy-risk-assumption-management-spec.md` as the planning backbone for:
- strategy/risk/assumption separation of concerns
- risk-policy and assumption-bundle governance
- effective snapshot precedence for sessions and runs
- future registry, compare/analyze, and paper/live reuse

Also treat `docs/strategy-workbench-spec.md` as the planning backbone for:
- strategy lab facilities
- assumption bundles and parameter-set workflow
- run lineage and artifact bundle expectations
- compare/analyze workflow
- replay scenario library and review workflow

Also treat `docs/object-level-notes-and-annotations-spec.md` as the planning backbone for:
- compare/review note generation and lifecycle
- replay investigation note generation and lifecycle
- object-linked annotation storage/API/UI direction
- future linkage between repo-level handoff and workbench object notes

Also treat `docs/ai-memory-and-handoff-spec.md` as the planning backbone for:
- repo-visible stable/task/session memory layers
- cross-session handoff discipline for long-running Phase 5-8 work
- compact summary-first continuation instead of transcript-only continuity
- future workbench annotation/review/handoff integration points

### Goal
Provide the first end-to-end research workflow using historical data.

### Scope
- strategy registration
- signal generation
- bars-based backtest engine
- fee and slippage model support
- shared backtest risk guardrails
- strategy/risk/assumption snapshot governance
- performance output
- diagnostics/reporting visibility
- research workbench facilities around development, comparison, replay, and review
- repo-visible memory and handoff workflow for long-horizon AI-assisted implementation and research work
- object-level compare/review notes, replay investigation notes, and future workbench annotations

### Deliverables
- `src/strategy/`
- `src/backtest/`
- simple strategy runner
- bars-based fill model
- shared backtest risk-guardrail engine
- run/session metadata model that can later host named risk policies and assumption bundles without redesign
- backtest results writer
- run diagnostics and trace-friendly inspection path
- staged diagnostics/reporting rollout from summary baseline to replay inspection
- period-level research outputs for long-window runs (`year` / `quarter` / `month`)
- strategy workbench metadata for parameter sets, assumption bundles, artifacts, and comparison workflow

### Suggested Tasks
- implement strategy registration and loading
- implement signal generation interface
- implement backtest engine using `md.bars_1m`
- implement fee model using `ref.fee_schedules`
- implement slippage model abstraction
- implement shared backtest risk guardrails using session risk policy
- preserve room for future named risk policies, assumption bundles, and run-level overrides in the Phase 5 run/session model
- write run metadata and results into `backtest.*`
- stage diagnostics implementation as:
  - summary baseline
  - step trace foundation
  - full backtest diagnostics with period breakdown
  - replay diagnostics and UI completion
- preserve enough run output structure to support later `per year` / `per quarter` / `per month` analysis without redesign
- preserve enough metadata to support:
  - parameter sets
  - assumption bundles
  - benchmark references
  - artifact bundles
  - replay scenarios
  - review decisions
- preserve room for object-level annotations on compare sets, replay runs, and replay scenarios

### Acceptance Criteria
- at least one simple strategy can run from historical bars to performance output
- backtest results persist to `backtest.runs`, `backtest.simulated_orders`, `backtest.simulated_fills`, `backtest.performance_summary`, and `backtest.performance_timeseries`
- run metadata captures versions and assumptions for reproducibility
- run metadata and diagnostics expose risk-policy assumptions and blocked-intent summary for later research comparison
- Phase 5 metadata and compare/analyze outputs remain compatible with future named risk-policy and assumption-bundle registries
- the first Phase 5 slice stays compatible with the phased position/protection/reporting architecture in `docs/position-management-spec.md`
- the phased diagnostics/reporting plan is explicit enough that later replay/UI work does not require redesign
- the research tool plan is explicit enough that later compare/analyze and replay-scenario work does not require redesign
- the repo now has an explicit AI memory/handoff workflow so long-running implementation work can be resumed without transcript-only continuity
- the repo now has an explicit object-level notes/annotation direction so compare/replay review state does not have to live only in chat or markdown

### Dependencies
- Phase 2
- Phase 3
- minimum Phase 4 data-quality baseline for bars-based research inputs

### Recommended Status
- started with an architecture-aligned session/strategy/lifecycle skeleton, the first bar-stream signal-generation loop, a deterministic bars-based fill model with fee/slippage support, DB-backed run/order/fill/performance persistence, create/list/detail run APIs, a diagnostics-summary surface, baseline period/artifact outputs, a persisted compare-set API foundation for research-side run comparison, and a first compare-review note API baseline
- now also has first-wave shared backtest risk guardrails, including session-level risk policy, blocked-intent diagnostics summary, and minimal UI launch controls for the first configurable risk knobs
- now also has Phase 5B baseline support for run-level risk overrides, effective risk-policy snapshot persistence, assumption-bundle metadata linkage, and compare/analyze-compatible risk assumption diffs
- now also has a first Phase 5C foundation for named risk-policy selection through a code-seeded registry, dedicated API list surface, and Backtests UI launch support
- now also has a first Phase 5D foundation for named assumption-bundle selection through a code-seeded registry, dedicated API list surface, bundle-aware run snapshot persistence, and Backtests UI launch support
- now also has the first richer stateful guardrail wave: `max_drawdown_pct`, `max_daily_loss_pct`, `max_leverage`, and `cooldown_bars_after_stop`, plus runtime state snapshot persistence and diagnostics flags
- current daily-loss guardrail semantics now respect `session.trading_timezone`, with `UTC` remaining the default when no alternate trading timezone is provided
- now also has a minimal internal UI slice for launching backtests, browsing recent runs, inspecting diagnostics/artifacts/month breakdown, inspecting signals/orders/fills/timeseries, and invoking compare-set analysis without raw SQL or inline Python
- now also has a repo-local AI memory/handoff workflow baseline under `docs/agent-memory/`, with a dedicated process spec for resumable long-running design and implementation work
- object-level notes/annotations are now design-specified for future compare-review, replay investigation, and workbench annotation work

---

## Phase 6: Paper Trading Engine

### Architecture Prerequisite
Phase 6 should reuse and extend the same lifecycle described in `docs/position-management-spec.md` rather than introducing a paper-only position or protection model.
Phase 6 should also reuse the shared guardrail semantics staged in `docs/backtest-risk-guardrails-spec.md` rather than inventing a paper-only pre-trade risk gate.
Phase 6 should also reuse the strategy/risk/assumption governance model staged in `docs/strategy-risk-assumption-management-spec.md` rather than inventing a separate paper-session configuration vocabulary.
Phase 6 should also preserve the stable family/variant/version identity described in `docs/strategy-taxonomy-and-versioning-spec.md` so paper sessions and reports remain attributable by variant/version.

### Goal
Run a strategy in simulated real time using live market data and execution logic.

### Scope
- strategy loop
- signal to order flow
- simulated fills
- positions and balances update
- pre-trade risk checks
- shared canonical execution model with future live trading path

### Deliverables
- `src/execution/paper_executor.py`
- strategy runtime loop
- simulated execution engine
- risk guard for paper trading

### Suggested Tasks
- implement signal-to-order translation
- implement paper execution fill logic
- update `execution.orders`, `execution.order_events`, `execution.fills`
- maintain `execution.positions` and `execution.balances`
- record latency metrics where possible
- implement risk checks using `risk.risk_limits`

### Acceptance Criteria
- one strategy can run continuously in paper mode
- order lifecycle records are persisted
- fills update positions and balances consistently
- risk violations are recorded as `risk.risk_events`
- paper path uses the same canonical order/fill/position contracts intended for live trading
- paper-path position/protection/reporting logic remains compatible with the phased strategy-book/account-book model in `docs/position-management-spec.md`
- paper sessions and reports remain attributable by stable strategy variant/version identity

### Dependencies
- Phase 5

### Recommended Status
- not started

---

## Phase 7: Private Exchange Adapter and Live Trading MVP

### Architecture Prerequisite
Phase 7 should continue the same shared lifecycle and ownership model from `docs/position-management-spec.md`, especially if shared-account execution or future fill allocation is introduced.
Phase 7 should also preserve the stable family/variant/version identity described in `docs/strategy-taxonomy-and-versioning-spec.md` for live deployments, fills, and later reporting.

### Goal
Support the first real trading path on one exchange.

### Scope
- authenticated exchange adapter
- order submission
- order status sync
- fill ingestion
- private account state sync

### Deliverables
- `src/exchange/`
- `src/execution/live_executor.py`
- private REST and websocket clients
- reconciliation baseline

### Suggested Tasks
- implement private REST auth and request signing
- implement order placement and cancel endpoints
- implement order query and execution report sync
- persist live orders, fills, balances, positions
- record account ledger and funding pnl where available
- record execution latency metrics

### Acceptance Criteria
- system can place and cancel an order on one exchange account
- order state transitions are persisted correctly
- fills reconcile into positions and balances
- funding and ledger data are recoverable from exchange history
- live path reuses the shared canonical execution model already established in paper mode
- live execution stays compatible with future fill allocation, protection-rule persistence, and reporting layers defined in `docs/position-management-spec.md`
- live-path records remain attributable to stable strategy variant/version identity

### Dependencies
- Phase 6

### Recommended Status
- not started

---

## Phase 8: Reconciliation, Treasury, and Operational Controls

### Architecture Prerequisite
Phase 8 should treat `docs/position-management-spec.md` as the intended backbone for fill truth, strategy/account ownership, protection history, and reporting traceability.
Phase 8 should also treat `docs/strategy-taxonomy-and-versioning-spec.md` as the intended backbone for variant/version attribution and future family-aware reporting.

### Goal
Make the live system safe and auditable enough for sustained operation.

### Scope
- reconciliation jobs
- treasury tracking
- deployment audit
- exchange status awareness
- operational controls

### Deliverables
- reconciliation jobs
- deployment tracking flow
- treasury sync jobs
- operational dashboards or reports

### Suggested Tasks
- reconcile exchange open orders vs database orders
- reconcile fills vs ledger and funding entries
- ingest deposits and withdrawals into `execution.deposits_withdrawals`
- record strategy deployments and config changes
- ingest exchange status events and forced reduction events

### Acceptance Criteria
- mismatches between exchange state and DB state can be detected
- treasury movements are recorded with enough metadata to audit
- deployments and config changes are traceable historically
- exchange outages or pauses can be represented in the system
- reconciliation and audit outputs preserve strategy variant/version attribution where applicable

### Dependencies
- Phase 7

### Recommended Status
- not started

---

## Phase 9: Production Hardening and Scale Improvements

### Goal
Improve reliability, performance, and maintainability after the end-to-end flow is working.

### Scope
- CI/CD
- automated tests
- alerting
- retention policies
- storage optimization
- scaling high-volume market data

### Deliverables
- test suite
- lint/format/type-check pipeline
- CI workflow
- retention policies for raw data
- storage scaling proposal or implementation

### Suggested Tasks
- add unit and integration tests
- add migration test or DB bootstrap test
- add alerts for ingestion failures and stale data
- define archival strategy for raw market events and order book data
- evaluate splitting high-volume data to ClickHouse or object storage

### Acceptance Criteria
- pull requests are validated automatically
- critical pipelines have tests
- stale data and ingestion failures can trigger alerts
- repository has an agreed scaling strategy for high-volume tables

### Dependencies
- Phase 8

### Recommended Status
- not started

---

## 4. Recommended Immediate Execution Order

If implementation begins now, use this sequence:

### Track A: Foundation
1. Phase 1
2. Phase 2
3. Phase 3

### Track B: Research
4. Phase 4
5. Phase 5

### Track C: Trading
6. Phase 6
7. Phase 7
8. Phase 8

### Track D: Reliability
9. Phase 9

This order minimizes risk because it ensures:
- database and models exist before ingestion
- ingestion exists before backtests
- minimum data-quality baseline exists before trusting backtest results
- backtests exist before paper trading
- paper trading exists before live trading
- reconciliation and hardening come after live basics work

---

## 5. Suggested Task Breakdown by Repository Area

### Database
- `db/init/004_seed.sql`
- future schema migrations as separate ordered files

### Models
- `src/models/market.py`
- `src/models/strategy.py`
- `src/models/execution.py`
- `src/models/risk.py`

### Storage
- `src/storage/db.py`
- `src/storage/repositories/`

### Ingestion
- `src/ingestion/base.py`
- `src/ingestion/binance/public_rest.py`
- `src/ingestion/binance/public_ws.py`
- `src/jobs/`

### Strategy and Backtest
- `src/strategy/`
- `src/backtest/`

### Execution
- `src/execution/paper_executor.py`
- `src/execution/live_executor.py`
- `src/exchange/`

### Ops and Reconciliation
- `src/reconciliation/`
- `src/risk/`
- `src/ops/`

---

## 6. Definition of Done for the Project

The project reaches the first meaningful delivery milestone when all of the following are true:

1. database can be initialized and seeded from scratch
2. first exchange market data can be collected continuously
3. one strategy can run a reproducible backtest
4. one strategy can run continuously in paper mode
5. one exchange account can place and reconcile live orders
6. key audit, treasury, and risk events are persisted

---

## 7. Next Action

The next recommended implementation step is:

### Begin Phase 5 strategy and backtest work
- implement the first strategy registration/loading slice
- extend the current strategy/session/lifecycle skeleton into a deterministic bars-based backtest loop on top of the Phase 4 quality baseline
- persist run metadata and results into `backtest.*`
- keep the Phase 5 execution/position/protection design aligned to `docs/position-management-spec.md` so later paper/live work does not require a lifecycle redesign

The completed Phase 4 quality baseline is now the intended base for all Phase 5 work.
