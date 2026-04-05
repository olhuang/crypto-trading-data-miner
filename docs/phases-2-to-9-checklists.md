# Phases 2 to 9 Checklists

## Purpose

This document expands the implementation roadmap for all phases after Phase 1 into concrete execution checklists.

Each phase includes:
- goal
- scope
- deliverables
- detailed task checklist
- acceptance checks
- handoff criteria to the next phase

This file is intended to be used together with:
- `docs/implementation-plan.md`
- `docs/phase-1-checklist.md`
- `docs/product-spec.md`
- `docs/data-catalog.md`
- `docs/data-catalog-addendum.md`
- `docs/api-contracts.md`
- `docs/position-management-spec.md` for all Phase 5-8 position/execution/protection/reporting work
- `docs/strategy-taxonomy-and-versioning-spec.md` for stable family/variant/version strategy identity
- `docs/strategy-input-and-feature-pipeline-spec.md` for all future multi-dataset strategy-input and feature work
- `docs/strategy-research-and-evaluation-spec.md` for strategy development, research, testing, and comparison workflow
- `docs/strategy-risk-assumption-management-spec.md` for strategy/risk/assumption separation, effective run snapshots, and future registry governance
- `docs/backtest-and-replay-diagnostics-spec.md` for report outputs, debug traces, replay diagnostics, and research-facing UI expectations
- `docs/debug-trace-rollout-plan.md` for the concrete staged rollout and current resume point for step-level debug traces
- `docs/backtest-risk-guardrails-spec.md` for shared backtest guardrails, staged risk-policy rollout, and paper/live reuse expectations
- `docs/strategy-workbench-spec.md` for the broader strategy-lab, replay-workbench, artifact, compare/analyze, and review facilities
- `docs/ai-memory-and-handoff-spec.md` for repo-local stable/task/session memory layers and cross-session handoff workflow
- `docs/object-level-notes-and-annotations-spec.md` for compare/review notes, replay investigation notes, and future workbench annotation direction

---

# Phase 2: Domain Models and Storage Layer

## Goal
Turn the documented contracts into validated Python models and a reusable PostgreSQL storage layer.

## Scope
- Pydantic models for canonical payloads
- DB connection management
- repository layer for inserts, upserts, and reads
- idempotent persistence patterns

## Required Deliverables
- `src/models/market.py`
- `src/models/strategy.py`
- `src/models/execution.py`
- `src/models/risk.py`
- `src/storage/db.py`
- `src/storage/repositories/`

## Task Checklist

## Task 2.1: Create model package structure
### Tasks
- [x] create `src/models/__init__.py`
- [x] create `src/models/market.py`
- [x] create `src/models/strategy.py`
- [x] create `src/models/execution.py`
- [x] create `src/models/risk.py`
- [x] create shared type/util module if needed

### Acceptance Checks
- [x] all implemented model modules import successfully
- [x] project has a clear model namespace for market, strategy, execution, and risk

---

## Task 2.2: Implement shared validation conventions
### Tasks
- [x] define Decimal parsing policy for numeric strings
- [x] define timestamp parsing policy for UTC values
- [x] define common enum representations
- [x] define base model settings for strict validation where appropriate

### Acceptance Checks
- [x] numeric string payloads validate consistently
- [x] malformed timestamps fail validation predictably
- [x] enums match `docs/api-contracts.md`

---

## Task 2.3: Implement market data models
### Tasks
- [x] implement model for instrument metadata
- [x] implement model for bar event
- [x] implement model for trade event
- [x] implement model for funding rate event
- [x] implement model for open interest event
- [x] implement model for order book snapshot
- [x] implement model for order book delta
- [x] implement model for mark price
- [x] implement model for index price
- [x] implement model for liquidation event
- [x] implement model for raw market event

### Acceptance Checks
- [x] core implemented market payload examples validate successfully
- [x] required fields are enforced for the implemented market models
- [x] invalid payloads fail with understandable errors for the implemented market models

---

## Task 2.4: Implement strategy and execution models
### Tasks
- [x] implement signal model
- [x] implement target position model
- [x] implement order request model
- [x] implement order state model
- [x] implement order event model
- [x] implement fill model
- [x] implement position snapshot model
- [x] implement balance snapshot model
- [x] implement account ledger model
- [x] implement funding pnl model

### Acceptance Checks
- [x] implemented execution payload examples validate successfully
- [x] order-type rules are enforced for the implemented order models
- [x] required fields vary correctly by implemented payload type

---

## Task 2.5: Implement DB connection layer
### Tasks
- [x] create `src/storage/db.py`
- [x] add PostgreSQL connection builder using environment config
- [x] define transaction handling pattern
- [x] define retry/error handling policy for transient DB failures

### Acceptance Checks
- [x] local app can open a PostgreSQL connection
- [x] connection settings are read from environment
- [x] DB helper can be reused by repositories

---

## Task 2.6: Implement repositories for reference and market data
### Tasks
- [x] create repository for exchanges/assets/instruments
- [x] create repository for bars
- [x] create repository for trades
- [x] create repository for funding rates
- [x] create repository for open interest
- [x] create repository for mark/index prices
- [x] create repository for raw market events

### Acceptance Checks
- [x] validated implemented market models can be persisted through repositories
- [x] market repositories support idempotent writes where needed
- [x] reference repositories can resolve instrument ids from canonical keys

---

## Task 2.7: Implement repositories for execution and risk data
### Tasks
- [x] create repository for orders
- [x] create repository for order events
- [x] create repository for fills
- [x] create repository for positions
- [x] create repository for balances
- [x] create repository for risk events
- [x] create repository for ops logs / ingestion metadata

### Acceptance Checks
- [x] execution payloads can be persisted through repositories
- [x] order lifecycle data can be stored without manual SQL
- [x] repositories expose predictable interfaces for later phases

---

## Task 2.8: Add validation and repository tests
### Tasks
- [x] add tests for payload validation
- [x] add tests for idempotent inserts/upserts
- [x] add tests for instrument resolution
- [x] add tests for duplicate fill handling

### Acceptance Checks
- [x] model tests pass locally
- [x] repository tests pass against local PostgreSQL

---

## Phase 2 Current Implementation Snapshot
- [x] canonical payloads validate through code for the implemented market and execution foundation slice
- [x] DB connection layer works locally
- [x] repositories exist for the current reference, market, and execution foundation slice
- [x] idempotent persistence patterns are implemented for the current bars/trades/funding/open-interest paths
- [x] automated tests exist for the current model, repository, and minimal models API foundation slice
- [x] minimal auth contract is implemented for the current models API slice
- [x] typed response/resource models exist for the current implemented API endpoints
- [x] starter strategy/version/account seed defaults exist for later phase handoff needs
- [x] lookup helpers now resolve strategy/version/account identifiers for the current seed-backed workflow
- [x] strategy signal and target-position models now exist for the current Phase 2 contract slice
- [x] initial risk limit and risk event models now exist for the current Phase 2 contract slice
- [x] remaining Phase 2 market, execution, risk, reference, and ops foundation slices now have implementation coverage
- [x] DB retry policy is implemented for transient connection failures
- [x] validate-and-store supports the current storable Phase 2 market, execution, and risk entities

## Phase 2 Final Acceptance Summary
- [x] canonical payloads validate through code
- [x] DB connection layer works locally
- [x] repositories exist for core entities
- [x] idempotent persistence patterns are implemented
- [x] model and repository tests pass

## Handoff Criteria to Phase 3
- [x] public exchange adapter can use repositories without raw SQL
- [x] instrument resolution is available from code
- [x] canonical payloads can be validated before persistence

---

# Phase 3: Public Market Data Ingestion

## Goal
Start collecting usable market data from the first exchange into the database.

## Scope
- first public exchange adapter
- historical backfill
- real-time collection
- ingestion monitoring

## Required Deliverables
- `src/ingestion/base.py`
- `src/ingestion/binance/public_rest.py`
- `src/ingestion/binance/public_ws.py`
- `src/jobs/sync_instruments.py`
- `src/jobs/backfill_bars.py`

## Task Checklist

## Task 3.1: Create ingestion package structure
### Tasks
- [x] create `src/ingestion/__init__.py`
- [x] create `src/ingestion/base.py`
- [x] create `src/ingestion/binance/__init__.py`
- [x] create public REST and WS client modules
- [x] create `src/jobs/` package

### Acceptance Checks
- [x] ingestion package imports cleanly
- [x] project has clear separation between REST and websocket ingestion

---

## Task 3.2: Implement instrument metadata sync
### Tasks
- [x] fetch exchange instrument metadata from Binance public endpoint
- [x] normalize payload to canonical instrument model
- [x] map exchange symbols to `ref.instruments`
- [x] update trading rules when metadata changes
- [x] record sync job status in `ops.ingestion_jobs`
- [x] auto-upsert newly discovered Binance assets required by synced instruments

### Acceptance Checks
- [x] instrument sync runs end-to-end
- [x] changed metadata can update or insert instruments safely
- [x] ingestion job status is persisted
- [x] sync no longer fails when Binance returns tradable symbols whose assets were not present in Phase 1 seed defaults

---

## Task 3.3: Implement historical bar backfill
### Tasks
- [x] fetch Binance kline history
- [x] normalize to canonical bar model
- [x] persist to `md.bars_1m`
- [x] support configurable symbol and time window
- [x] record row counts and status in `ops.ingestion_jobs`
- [x] support both Binance perp and spot bar windows through the shared backfill path
- [x] paginate historical bar windows beyond the first REST page

### Acceptance Checks
- [x] historical bars are backfilled into `md.bars_1m`
- [x] rerunning the same backfill does not create duplicate bars
- [x] failures and row counts are visible in ops tables
- [x] spot bars can be backfilled through the same job/API shape used for perp bars

---

## Task 3.4: Implement live trade ingestion
### Tasks
- [x] subscribe to Binance trade websocket stream
- [x] normalize trade payloads
- [x] persist to `md.trades`
- [x] preserve `event_time` and `ingest_time`
- [x] record websocket lifecycle into `ops.ws_connection_events`

### Acceptance Checks
- [x] live trades are written continuously to `md.trades`
- [x] duplicate trade ids are not inserted
- [x] websocket connect/disconnect events are logged

---

## Task 3.5: Implement funding and open interest polling
### Tasks
- [x] fetch funding history / latest funding data
- [x] normalize to canonical funding model
- [x] fetch open interest data
- [x] persist to `md.funding_rates` and `md.open_interest`
- [x] schedule periodic refresh job
- [x] support historical open-interest windows for backfill-style runs
- [x] paginate historical funding/open-interest windows beyond the first REST page

### Acceptance Checks
- [x] funding rates are persisted successfully
- [x] open interest is persisted successfully
- [x] periodic jobs can run without manual SQL
- [x] historical open-interest windows can be persisted through the existing refresh job

---

## Task 3.6: Implement mark/index price ingestion
### Tasks
- [x] subscribe or poll mark price data
- [x] subscribe or poll index price data
- [x] normalize to canonical models
- [x] persist to `md.mark_prices` and `md.index_prices`
- [x] support historical mark/index windows for backfill-style runs
- [x] paginate historical mark/index windows beyond the first REST page and use the correct Binance pair parameter for index-price history

### Acceptance Checks
- [x] mark price data is stored continuously or on refresh
- [x] index price data is stored continuously or on refresh
- [x] instrument mapping resolves correctly
- [x] historical mark/index windows can be persisted through the existing refresh job

---

## Task 3.7: Implement raw event capture
### Tasks
- [x] persist raw websocket payloads to `md.raw_market_events`
- [x] tag payloads with channel and event type
- [x] preserve source message ids where available

### Acceptance Checks
- [x] raw events can be traced to normalized market writes
- [x] ingestion debugging is possible from stored payloads

---

## Task 3.8: Add ingestion job and basic monitoring support
### Tasks
- [x] insert job rows into `ops.ingestion_jobs`
- [x] update status on success/failure
- [x] log row counts and windows
- [x] add basic app logs to `ops.system_logs`

### Acceptance Checks
- [x] each ingestion run leaves a job record
- [x] failed runs are visible in DB
- [x] successful runs include window and row count metadata

---

## Phase 3 Current Implementation Snapshot
- [x] Binance public REST and websocket normalization code exists under `src/ingestion/binance/`
- [x] instrument sync, bar backfill, and market snapshot refresh jobs exist under `src/jobs/`
- [x] the bar backfill path now supports both Binance perp and spot historical bars
- [x] scheduler-ready market snapshot remediation job now exists for manual/API-triggered funding/OI/mark/index catch-up planning
- [x] runtime trade-stream processing exists under `src/runtime/`
- [x] `/api/v1/ingestion/jobs/*`, `/api/v1/market/*`, and `/api/v1/streams/*` foundation endpoints now exist in the minimal API slice
- [x] `GET /api/v1/ingestion/jobs` now supports recent jobs listing/filtering for monitoring
- [x] ingestion job detail now exposes summary/diff metadata for instrument sync
- [x] market snapshot refresh now supports historical funding/OI/mark/index windows for the current Binance slice
- [x] automated tests cover instrument sync, bar backfill, funding/open-interest refresh, trade stream processing, and scheduler planning
- [x] the current Phase 3 slice has been validated once against real Binance for `BTCUSDT_SPOT`/`BTCUSDT_PERP` collection, excluding historical trades

## Phase 3 Final Acceptance Summary
- [x] instrument sync works
- [x] bar backfill works
- [x] live trade ingestion works
- [x] funding and open interest work
- [x] mark/index ingestion works
- [x] raw event capture works
- [x] ingestion monitoring works

## Handoff Criteria to Phase 4
- [x] market data is being persisted continuously enough to validate quality
- [x] raw and normalized data can be related
- [x] ops tables have enough metadata for data quality checks

---

# Phase 4: Market Data Quality and Replay Readiness

## Goal
Make the collected market data reliable enough for research, backtest, and replay-oriented debugging.

## Scope
- gap checks
- freshness checks
- duplicate checks
- raw-to-normalized traceability
- retention / replay readiness

## Required Deliverables
- quality validation jobs
- data gap detection jobs
- replay/readiness notes or utilities

## Task Checklist

## Task 4.1: Implement bar gap checks
### Tasks
- [x] define expected bar cadence rules
- [x] detect missing 1m bars by instrument and interval
- [x] write results to `ops.data_gaps`
- [x] write summary checks to `ops.data_quality_checks`

### Acceptance Checks
- [x] missing bar windows are detected automatically
- [x] detected gaps are persisted to ops tables

---

## Task 4.2: Implement freshness checks
### Tasks
- [x] define freshness SLA for bars
- [x] define freshness SLA for trades
- [x] define freshness SLA for funding/open interest
- [x] define freshness SLA for mark/index prices
- [x] record pass/fail results in `ops.data_quality_checks`

### Acceptance Checks
- [x] stale data conditions can be detected and persisted
- [x] check severity is recorded in a structured form

---

## Task 4.3: Implement duplicate checks
### Tasks
- [x] validate duplicate trade detection
- [x] validate duplicate bar detection
- [x] validate duplicate mark/index detection
- [x] validate duplicate raw event detection where possible
- [x] persist findings to `ops.data_quality_checks`

### Acceptance Checks
- [x] duplicate anomalies can be measured and reported
- [x] duplicate counts can be inspected after ingestion runs

---

## Task 4.3a: Implement dataset-level snapshot sanity checks
### Tasks
- [x] add funding continuity checks
- [x] add open-interest continuity checks
- [x] add mark-price continuity checks
- [x] add index-price continuity checks
- [x] add typed dataset-integrity validation for one symbol/window across the currently maintained backfill datasets
- [x] add explicit corrupt/future-dated row detection to the integrity validator
- [x] add CLI/PowerShell entrypoints for post-backfill integrity validation

### Acceptance Checks
- [x] funding/OI/mark/index sanity checks are persisted to `ops.data_quality_checks`
- [x] quality summary and inspection APIs can surface these checks
- [x] one symbol/window can now be validated through a single typed report covering gaps, missing rows, duplicates, and corrupt/future-dated rows

---

## Task 4.4: Implement raw-to-normalized traceability
### Tasks
- [x] define linking or matching strategy between raw events and normalized data
- [x] document how reprocessing should work
- [x] verify sample replay path for at least one data type

### Acceptance Checks
- [x] a normalized record can be traced back to its raw source event or source message pattern
- [x] at least one reprocessing path is documented or demonstrated

---

## Task 4.5: Define retention and replay policy
### Tasks
- [x] define retention policy for raw market events
- [x] define retention policy for order book deltas and snapshots
- [x] define minimum replay-ready datasets for future phases

### Acceptance Checks
- [x] retention assumptions are documented
- [x] replay readiness expectations are documented

---

## Phase 4 Current Implementation Snapshot
- [x] quality jobs exist for bar gaps, freshness checks, duplicate checks, and combined suite execution
- [x] `ops.data_quality_checks` and `ops.data_gaps` now have repository support and API inspection endpoints
- [x] `/api/v1/quality/*` endpoints now expose checks, summaries, gaps, and a direct quality-run trigger
- [x] raw-event detail and normalized-link endpoints now support traceability debugging for the current Binance public-data slice
- [x] replay-readiness summary is exposed at `/api/v1/replay/readiness`
- [x] replay/retention policy is documented in `docs/replay-retention-policy.md`
- [x] automated tests now cover Phase 4 jobs, traceability helpers, and API endpoints
- [x] local/dev startup can optionally remediate recent bar gaps through an explicit config flag without requiring a continuous remediation scheduler
- [x] historical trades are explicitly documented as a future manual bounded-backfill path, not a startup or continuous auto-remediation path
- [x] funding/OI/mark/index now have a scheduler-ready remediation job path without turning on continuous auto catch-up
- [x] funding/OI/mark/index now also have dataset-level sanity checks for freshness, duplicates, and bounded continuity
- [x] the Phase 4 quality path now also includes a typed dataset-integrity validator plus CLI/PowerShell wrappers for post-backfill verification
- [x] bar gap checks now align non-minute requested windows to minute boundaries before evaluating 1m completeness
- [x] spot quality runs now skip perp-only funding/OI/mark/index checks to avoid false snapshot failures on `_SPOT` symbols
- [x] a minimal internal Monitoring Console now exists for Overview, Jobs, Quality, and Traceability views using the implemented Phase 3/4 APIs
- [x] quality summary/check APIs now support a latest-only monitoring mode, and bar gap rechecks can resolve overlapping stale open gaps from earlier runs
- [ ] future Phase 4 enhancement: add cross-dataset diagnostic checks such as funding-to-mark/index alignment, mark-vs-index spread sanity, and raw-to-normalized coverage correlation

## Phase 4 Final Acceptance Summary
- [x] bar gaps are detectable
- [x] freshness checks exist
- [x] duplicate checks exist
- [x] raw and normalized data can be related
- [x] replay/retention policy is documented

## Handoff Criteria to Phase 5
- [x] historical data quality is good enough to run first backtests
- [x] data issues are visible through ops tables before strategy logic is introduced

---

# Phase 5: Strategy Runner and Bars-Based Backtest

## Architecture Alignment Note
Phase 5 should follow `docs/position-management-spec.md` as the planning backbone for:
- strategy book vs account book separation
- fill-level execution truth
- position/protection/reporting extensibility
- future paper/live/reconciliation reuse

Phase 5 should also follow `docs/strategy-input-and-feature-pipeline-spec.md` as the planning backbone for:
- bars-only MVP scope
- future aligned funding/OI/mark/index inputs
- time alignment and no-look-ahead rules
- later feature-pipeline expansion beyond bars

Phase 5 should also follow `docs/strategy-research-and-evaluation-spec.md` as the planning backbone for:
- new strategy development workflow
- multi-window evaluation expectations
- multi-strategy and multi-parameter comparison planning
- promotion-oriented research evidence

Phase 5 should also follow `docs/strategy-taxonomy-and-versioning-spec.md` as the planning backbone for:
- family vs variant vs version classification
- stable meaning of current `strategy_code` and `strategy_version`
- future comparison and promotion grouping semantics

Phase 5 should also follow `docs/strategy-risk-assumption-management-spec.md` as the planning backbone for:
- strategy / risk / assumption separation of concerns
- effective snapshot precedence for sessions and runs
- named risk-policy and assumption-bundle registry direction
- future compare/analyze and paper/live reuse

Phase 5 should also follow `docs/backtest-and-replay-diagnostics-spec.md` as the planning backbone for:
- backtest report outputs vs debug trace outputs
- run diagnostics visibility
- future replay run/result inspection

## Goal
Provide the first end-to-end research workflow using historical bar data.

## Scope
- strategy registration/loading
- signal generation interface
- bars-based execution model
- fee and slippage model support
- backtest persistence and reporting

## Required Deliverables
- `src/strategy/`
- `src/backtest/`
- simple strategy runner
- results writer to `backtest.*`

## Task Checklist

## Task 5.0: Freeze Phase 5 architecture boundaries
### Tasks
- [x] confirm the first Phase 5 slice follows `docs/position-management-spec.md`
- [x] keep fill-level execution truth as the canonical source for later projections
- [x] keep Phase 5 scoped to isolated strategy sessions and position-level protection
- [x] avoid introducing a backtest-only lifecycle vocabulary that would diverge from future paper/live work
- [x] freeze strategy family/variant/version semantics before expanding strategy registration and research flows

### Acceptance Checks
- [x] Phase 5 implementation choices remain compatible with later paper/live reuse
- [x] strategy/account ownership, protection, and reporting assumptions are explicit before coding deeper execution logic
- [x] current `strategy_code` and `strategy_version` meaning is explicit enough to support future compare/analyze and promotion workflows

---

## Task 5.1: Create strategy package structure
### Tasks
- [x] create `src/strategy/__init__.py`
- [x] create strategy base interface
- [x] create simple example strategy implementation
- [x] define strategy loading or registration pattern
- [ ] define how new strategy implementations move from local development to research evaluation

### Acceptance Checks
- [x] strategy interface is clear and reusable
- [x] at least one example strategy can be instantiated from code

---

## Task 5.1B: Plan strategy-lab and research-workbench facilities
### Tasks
- [x] define draft/candidate/released strategy workflow
- [x] define parameter-set workflow
- [x] define assumption-bundle workflow
- [x] define benchmark/baseline library expectations

### Acceptance Checks
- [x] repository has an explicit strategy-lab/workbench plan beyond raw strategy registry rows
- [x] future strategy development can progress without relying on ad hoc notebook-only workflow

---

## Task 5.1D: Plan AI memory and cross-session handoff workflow
### Tasks
- [x] define stable vs task vs session memory layers for repo-visible AI-assisted work
- [x] define canonical repo-local memory artifacts for project state, task board, decision log, handoff, and rolling session summary
- [x] define a session start/stop workflow for loading stable memory, choosing one subtask, summarizing progress, and writing handoff state
- [x] define source-of-truth precedence so repo-visible memory complements specs/checklists without replacing them
- [x] define how the memory workflow should later connect to workbench annotations, replay investigation, and review surfaces
- [x] provide reusable session-start, session-stop, and operator automation templates so the workflow can be applied consistently from CLI/editor tooling
- [x] provide repo-owned VS Code tasks and local helper scripts for the baseline start/stop workflow

### Acceptance Checks
- [x] repository has an explicit source of truth for resumable AI-assisted long-running work
- [x] future sessions can resume from repo-visible handoff files instead of relying on transcript continuity alone
- [x] the memory workflow remains compatible with future strategy workbench and replay-diagnostics facilities
- [x] operators have a minimal start/stop/template toolkit instead of only a prose process description
- [x] the repo includes a ready-to-run local entrypoint for the start/stop workflow instead of requiring each contributor to invent one

---

## Task 5.1C: Plan strategy, risk, and assumption governance
### Tasks
- [x] define how strategy identity, risk policy, assumption bundle, and parameter set differ
- [x] define how session defaults, assumption bundles, and run-level overrides merge into one effective snapshot
- [x] define how future registries should support named risk policies and named assumption bundles
- [x] define how compare/analyze should surface strategy, risk, and assumption differences separately
- [x] define how paper/live should reuse the same governance model instead of inventing a separate vocabulary

### Acceptance Checks
- [x] repository has an explicit source of truth for strategy/risk/assumption management
- [x] the Phase 5 run/session model has a documented direction for future registry and override expansion without redesign

---

## Task 5.2: Implement signal generation loop
### Tasks
- [x] load bar data from `md.bars_1m`
- [x] evaluate strategy over historical bars
- [x] emit canonical signals
- [x] optionally persist signals to `strategy.signals`
- [x] keep the first loop compatible with future `StrategyInputSnapshot` expansion from `docs/strategy-input-and-feature-pipeline-spec.md`

### Acceptance Checks
- [x] backtest run can generate signals from historical bars
- [x] signals follow canonical payload structure

---

## Task 5.3: Implement bars-based fill model
### Tasks
- [x] define order simulation logic for market orders
- [x] define order simulation logic for limit orders
- [x] implement fee model using `ref.fee_schedules`
- [x] implement slippage model abstraction

### Acceptance Checks
- [x] simulated fills can be generated deterministically
- [x] fee and slippage are reflected in results

---

## Task 5.3A: Implement minimal shared backtest risk guardrails
### Tasks
- [x] add session-level `RiskPolicyConfig` to the Phase 5 backtest models
- [x] implement a shared pre-trade guardrail engine between lifecycle planning and fill simulation
- [x] enforce first-wave checks for equity floor, spot cash sufficiency, max position qty, max order qty, max order notional, and max gross exposure multiple
- [x] allow already reduce-only intents to bypass blocking when policy permits
- [x] persist blocked-intent summary into run/runtime metadata and diagnostics-friendly output
- [x] expose first-wave risk-policy fields through the current backtest run API surface and minimal internal Backtests launch UI

### Acceptance Checks
- [x] clearly disallowed new entries are blocked deterministically before order creation
- [x] reduce-only exits can still proceed when configured even if another guardrail would otherwise block them
- [x] persisted run detail and diagnostics now expose risk-policy assumptions and blocked-intent summary for later research comparison

---

## Task 5.3B: Implement run-level risk overrides and effective snapshot baseline
### Tasks
- [x] add run-level risk overrides to the Phase 5 backtest run model
- [x] merge session default risk policy with run-level overrides into one effective risk snapshot
- [x] persist session risk policy, run-level overrides, and effective risk policy separately in run metadata/detail
- [x] preserve assumption-bundle metadata linkage at the run level without requiring a registry yet
- [x] extend compare/analyze assumptions so risk-policy defaults, overrides, and effective snapshots can diverge visibly
- [x] expose the current assumption-bundle and risk-override baseline through the internal Backtests launch/request path

### Acceptance Checks
- [x] one run can override session default risk knobs without redefining the strategy variant/version
- [x] persisted run detail can explain the difference between session default risk policy, run-level overrides, and effective risk policy
- [x] compare/analyze output remains compatible with later named risk-policy and assumption-bundle registries

---

## Task 5.3C: Implement named risk-policy registry foundation
### Tasks
- [x] add a reusable named risk-policy registry for the current Phase 5 backtest slice
- [x] resolve `session.risk_policy.policy_code` through the registry before effective snapshot merge
- [x] allow run-level overrides to switch to another named risk-policy base when a known override code is selected
- [x] expose available named risk policies through a dedicated API surface
- [x] expose available named risk policies in the current internal Backtests UI launch flow

### Acceptance Checks
- [x] a run can select a named risk policy without copying every guardrail field into the request body
- [x] persisted session/effective risk snapshots reflect registry resolution rather than only raw request knobs
- [x] API and UI users can inspect the currently available named risk policies without raw code inspection

---

## Task 5.3D: Implement named assumption-bundle registry foundation
### Tasks
- [x] add a reusable named assumption-bundle registry for the current Phase 5 backtest slice
- [x] resolve `assumption_bundle_code` / optional `assumption_bundle_version` through the registry before persisting run metadata
- [x] merge named bundle defaults with explicit run-level assumption fields into one effective assumption snapshot
- [x] let bundle defaults contribute a risk-policy layer between session defaults and explicit run-level risk overrides
- [x] persist selected bundle identity, resolved bundle snapshot, explicit assumption overrides, and effective assumption snapshot separately in run metadata/detail
- [x] expose available named assumption bundles through a dedicated API surface
- [x] expose available named assumption bundles in the current internal Backtests UI launch flow
- [x] extend compare/analyze assumptions so bundle identity, bundle snapshot, explicit assumption overrides, and effective assumptions can diverge visibly

### Acceptance Checks
- [x] a run can select a named assumption bundle without copying every research assumption into the request body
- [x] persisted run detail can explain the difference between selected bundle identity, bundle defaults, explicit run-level assumption overrides, and effective assumptions
- [x] compare/analyze output remains compatible with later DB-normalized assumption-bundle registries and richer workbench review flows

---

## Task 5.3E: Implement richer stateful backtest guardrails
### Tasks
- [x] extend `RiskPolicyConfig` and `RiskPolicyOverrideConfig` with:
  - `max_drawdown_pct`
  - `max_daily_loss_pct`
  - `max_leverage`
  - `cooldown_bars_after_stop`
- [x] add shared risk-session state for:
  - peak equity
  - daily-start equity
  - cooldown tracking
- [x] enforce drawdown-based no-new-entry guardrails using current run peak equity
- [x] enforce daily-loss-based no-new-entry guardrails using current trading-day starting equity
- [x] make daily-loss trading-day boundaries follow `session.trading_timezone` instead of fixed UTC-only dates
- [x] enforce leverage-based blocking using resulting gross exposure relative to current equity
- [x] implement first-wave cooldown behavior using a documented shared proxy trigger before full protection lifecycle exists
- [x] persist richer runtime risk summary and state snapshot in run metadata/detail
- [x] extend diagnostics flags and internal Backtests launch form to expose the richer guardrail fields

### Acceptance Checks
- [x] runs can block new exposure when drawdown or daily loss limits are breached without changing strategy code
- [x] leverage breaches are visible and deterministic in persisted risk outcomes
- [x] cooldown behavior is inspectable through runtime metadata and diagnostics rather than hidden inside the runner
- [x] API/UI users can configure and inspect the richer guardrail fields without raw SQL or code edits

---

## Task 5.4: Implement portfolio/account state in backtest
### Tasks
- [x] maintain cash state
- [x] maintain position state
- [x] maintain equity curve
- [x] calculate realized/unrealized PnL
- [x] calculate exposure series

### Acceptance Checks
- [x] positions and cash evolve consistently across a run
- [x] equity curve is reproducible for the same inputs

---

## Task 5.5: Persist backtest outputs
### Tasks
- [x] write run metadata to `backtest.runs`
- [x] write simulated orders to `backtest.simulated_orders`
- [x] write simulated fills to `backtest.simulated_fills`
- [x] write summary stats to `backtest.performance_summary`
- [x] write equity/exposure series to `backtest.performance_timeseries`
- [x] add backtest run create/list/detail API surfaces over persisted outputs
- [x] preserve enough output structure to support later diagnostics and replay comparison views
- [x] preserve enough output structure to support later artifact bundles and benchmark comparison

### Acceptance Checks
- [x] all core backtest tables are populated after a run
- [x] run metadata contains assumptions and versions
- [x] persisted runs can now be launched and inspected through API without ad hoc SQL
- [x] stored outputs are compatible with later diagnostics/reporting surfaces
- [x] stored outputs preserve enough lineage for future compare/analyze and replay scenario surfaces

---

## Task 5.6: Implement example report workflow
### Tasks
- [x] compute total return
- [ ] compute Sharpe
- [x] compute max drawdown
- [x] compute turnover and fee costs
- [x] expose a simple run summary through the current API/UI detail surfaces
- [x] define or emit a first diagnostic summary separate from KPI-only output

### Acceptance Checks
- [x] at least one run produces interpretable performance output
- [x] performance summary matches timeseries-derived results
- [x] report output and debug/diagnostic output are not conflated

---

## Task 5.6A: Plan diagnostic traces and replay inspection
### Tasks
- [x] define run-level diagnostic summary shape
- [x] define step-level debug trace shape
- [x] define how replay runs will expose event/state timelines
- [x] define how UI should inspect backtest and replay diagnostics
- [x] define staged rollout from diagnostics summary baseline to full replay diagnostics

### Acceptance Checks
- [x] repository has a documented plan for backtest diagnostics and replay debugging
- [x] future UI/API work has explicit report/trace surfaces to build against

---

## Task 5.6B: Stage diagnostics, reporting, and replay implementation
### Tasks
- [x] Stage A: implement run-level diagnostics summary baseline
- [x] Stage B backend foundation: implement compact persisted step-level debug traces plus read API
- [x] Stage B UI surface: expose debug traces in the internal research console
- [x] Stage B extension: add targeted trace filters for blocked/risk/signal/order/fill investigation
- [x] Stage B.5: surface strategy market context inside diagnostics/debug-trace inspection for feature-driven runs
- [ ] Stage C: implement full backtest diagnostics and period-level analysis
- [ ] Stage D: implement replay diagnostics, replay timelines, and replay UI inspection support
- [x] create a dedicated debug-trace rollout tracking document with current status, staged scope, and resume guidance

### Acceptance Checks
- [x] diagnostics/reporting/replay work is broken into explicit implementation stages
- [x] the internal debug-trace viewer can narrow into blocked, risk-specific, signal, order, or fill evidence without manual table scanning
- [x] later replay/UI work can build on earlier report/trace surfaces without redesign

---

## Task 5.7: Plan comparative research workflow
### Tasks
- [x] define multi-window evaluation workflow
- [x] define multi-parameter comparison workflow
- [x] define multi-strategy comparison workflow
- [x] define benchmark and promotion-review expectations
- [x] define how one long run will support `per year` / `per quarter` / `per month` analysis

### Acceptance Checks
- [x] the repository has a documented path from new strategy code to comparative research evidence
- [x] Phase 5 work remains compatible with future run-group and compare/analyze flows

---

## Task 5.7A: Implement period-level research outputs
### Tasks
- [x] define run-period summary projection for `year`
- [x] define run-period summary projection for `quarter`
- [x] define run-period summary projection for `month`
- [x] preserve enough run-level reporting facts to derive period metrics consistently

### Acceptance Checks
- [x] long-window backtests can be analyzed by year, quarter, and month
- [x] period-level outputs are compatible with future compare/analyze and promotion-review workflows

---

## Task 5.7B: Plan experiment, compare-set, and review workflow
### Tasks
- [x] define experiment and run-group workflow
- [x] define compare-set workflow
- [x] define artifact-bundle expectations
- [x] define notes/annotations/review decision workflow

### Acceptance Checks
- [x] repository has an explicit plan for experiment organization and review evidence
- [x] compare/analyze work has a planned home beyond ad hoc run lists

---

## Task 5.7E: Plan object-level notes and annotation workflow
### Tasks
- [x] define how repo-level memory and object-level notes differ
- [x] define canonical object types for notes, including compare sets and replay objects
- [x] define the annotation resource shape, note types, source types, and verification-state handling
- [x] define the three-layer generation flow: seed note, system fact enrichment, and human/agent review enrichment
- [x] define how future workbench UI should expose compare review notes and replay investigation notes

### Acceptance Checks
- [x] the repository has an explicit source of truth for object-linked research/review notes
- [x] compare/analyze and replay workflows no longer rely on ad hoc note handling as their only planned path
- [x] object-level notes remain compatible with repo-level handoff workflow instead of replacing it

---

## Task 5.7D: Implement compare/analyze foundation
### Tasks
- [x] implement ad hoc compare-set projector over selected run ids
- [x] expose side-by-side run KPIs, diagnostic status, and optional benchmark deltas
- [x] expose assumption diffs for run metadata, execution assumptions, and strategy params
- [x] add `POST /api/v1/backtests/compare-sets`
- [x] expose the current compare/analyze baseline in the internal research UI
- [x] add automated tests for compare/analyze projection and API surface

### Acceptance Checks
- [x] selected runs can be compared without ad hoc SQL
- [x] compare responses include KPI comparison, assumption diffs, and benchmark overlays
- [x] compare/analyze output remains compatible with future saved compare-set and review workflow

---

## Task 5.7F: Implement compare/review note foundation
### Tasks
- [x] persist compare-set review notes as first-class object-linked annotations
- [x] seed compare review drafts from compare-set identity and compared run ids
- [x] enrich seeded review drafts with KPI, benchmark, assumption-diff, and diagnostics-diff facts
- [x] expose compare-review note list/create/update API surfaces
- [x] expose compare-review notes in the internal research UI

### Acceptance Checks
- [x] compare work can leave durable review state without relying on repo-level markdown or chat transcripts alone
- [x] system facts and human/agent review conclusions remain distinguishable in compare-review notes
- [x] compare-review notes are compatible with future saved compare sets and promotion review workflow

---

## Task 5.7C: Plan replay-scenario and golden-case workflow
### Tasks
- [x] define replay scenario library workflow
- [x] define bookmarks/expected-behavior notes
- [x] define golden replay or incident replay expectations
- [x] define expected-vs-observed replay review output

### Acceptance Checks
- [x] repository has an explicit replay-workbench plan beyond generic replay runs
- [x] future replay investigations have a planned home for saved scenarios and regression cases

---

## Task 5.6C: Implement replay investigation note foundation
### Tasks
- [ ] persist replay-run or replay-scenario investigation notes as first-class object-linked annotations
- [ ] seed investigation note drafts from replay metadata and scenario identity
- [ ] enrich seeded notes with diagnostics flags, expected-vs-observed placeholders, and trace/timeline references
- [ ] expose replay-investigation note list/detail/create/update API surfaces
- [ ] expose replay investigation notes in future replay UI surfaces

### Acceptance Checks
- [ ] replay investigations can accumulate durable expected/observed findings without relying only on repo-level handoff or chat history
- [ ] replay investigation notes preserve the distinction between system facts, assumptions, and verified findings
- [ ] replay notes remain compatible with future replay scenario libraries and incident review workflow

## Phase 5 Current Implementation Snapshot
- [x] `src/models/backtest.py` now defines strategy session, execution-policy, protection-policy, and backtest run config models
- [x] `src/strategy/` now contains a base strategy interface, default registry, and seeded example strategy implementation
- [x] `src/backtest/` now contains a lifecycle-planning and runner skeleton aligned to `docs/position-management-spec.md`
- [x] automated tests now validate session config, default strategy loading, example strategy output, and initial lifecycle planning
- [x] a dedicated strategy-input/feature-pipeline planning spec now exists for future non-bar strategy inputs
- [x] a dedicated strategy-research/evaluation planning spec now exists for future multi-window and multi-strategy research workflows
- [x] a dedicated strategy taxonomy/versioning planning spec now exists for family, variant, and version identity
- [x] a dedicated strategy/risk/assumption management planning spec now exists for effective snapshot governance and future registries
- [x] a dedicated backtest/replay diagnostics planning spec now exists for report outputs, debug traces, and replay inspection
- [x] a dedicated backtest risk-guardrails planning spec now exists for shared pre-trade guardrails and later paper/live reuse
- [x] the diagnostics planning spec now also defines staged implementation rollout and future `per year` / `per quarter` / `per month` breakdown expectations
- [x] a dedicated strategy workbench planning spec now exists for strategy-lab, artifact, compare/analyze, replay-scenario, and review facilities
- [x] a dedicated AI memory/handoff planning spec now exists for repo-local stable/task/session memory and cross-session continuation
- [x] a dedicated object-level notes/annotations planning spec now exists for compare-review notes, replay investigation notes, and future workbench annotation UI
- [x] reusable session-start, session-stop, and CLI/VS Code workflow templates now exist under `docs/agent-memory/`
- [x] the Phase 5 skeleton now includes a `md.bars_1m` loader, bar-stream evaluation loop, canonical signal normalization, and optional signal persistence
- [x] the Phase 5 skeleton now includes a deterministic bars-based fill model with market/limit simulation plus fee/slippage handling
- [x] the Phase 5 skeleton now includes a first shared pre-trade risk-guardrail engine with session risk policy and blocked-intent runtime summary
- [x] the Phase 5 skeleton now includes run-level risk overrides, effective risk-policy snapshot persistence, and assumption-bundle metadata linkage
- [x] the Phase 5 skeleton now includes aggregate portfolio state, reproducible equity/exposure projection, and a DB-backed run writer for `backtest.*`
- [x] the Phase 5 skeleton now includes a run-level diagnostics summary projector and the first `/api/v1/backtests/runs/{run_id}/diagnostics` API surface
- [x] the Phase 5 skeleton now includes `year` / `quarter` / `month` period-breakdown projection and a baseline artifact catalog for run outputs
- [x] the Phase 5 skeleton now includes an ad hoc compare/analyze API surface for selected runs and optional benchmark overlays
- [x] the Phase 5 skeleton now includes persisted compare-set identity plus seeded compare-review note APIs for durable compare workflow memory
- [x] the Phase 5 skeleton now includes `POST /api/v1/backtests/runs`, `GET /api/v1/backtests/runs`, and `GET /api/v1/backtests/runs/{run_id}` for run launch and inspection
- [x] the Phase 5 skeleton now includes run-detail APIs for persisted signals, simulated orders, simulated fills, and recent performance timeseries inspection
- [x] the current internal `/monitoring` console now includes a minimal Backtests view for launching runs and inspecting diagnostics/artifacts/month breakdown plus signals/orders/fills/timeseries detail
- [x] the current internal Backtests launch form now exposes first-wave risk-policy fields for the shared backtest guardrails
- [x] the current internal Backtests launch form now also exposes and loads named risk policies from the current registry foundation
- [x] the current internal Backtests launch form now also exposes and loads named assumption bundles from the current registry foundation
- [x] the current Phase 5 runner now supports `feature_input_version = bars_perp_context_v1`, loading latest-as-of funding/OI/mark/index plus Binance futures sentiment-ratio context into strategy evaluation
- [x] the current seeded strategy registry now includes `btc_sentiment_momentum@v1.0.0` and the named assumption-bundle registry now includes `baseline_perp_sentiment_research@v1`
- [x] the current internal Backtests launch form now exposes the sentiment-aware research path through a `Sentiment Perp` preset, real strategy selector, and strategy-aware threshold inputs
- [x] the current shared backtest guardrail engine now includes a first stateful richer-guardrail wave for drawdown, daily-loss, leverage, and cooldown controls
- [x] the current runner now caps recent bar history when a strategy declares a finite requirement and avoids persisting full step caches by default for persisted runs
- [x] the current Phase 5 planning baseline now explicitly preserves room for named risk policies, assumption bundles, and run-level effective snapshot precedence
- [x] the current Phase 5 run metadata now persists selected assumption-bundle identity, resolved bundle snapshot, explicit assumption overrides, and effective assumption snapshot for later compare/analyze and review work
- [x] the current Phase 5 diagnostics/trace surfaces now expose the strategy market context that drove feature-aware or sentiment-aware decisions

---

## Phase 5 Final Acceptance Summary
- [x] one strategy can run end-to-end on historical bars
- [x] signals are produced
- [x] simulated orders and fills are produced
- [x] run metadata and results persist to DB
- [x] core KPIs are computed

## Handoff Criteria to Phase 6
- [x] research workflow exists from bars to persisted backtest results
- [ ] execution and portfolio abstractions are stable enough for paper trading reuse
- [x] Phase 5 internals are still aligned to `docs/position-management-spec.md`

---

# Phase 6: Paper Trading Engine

## Architecture Alignment Note
Phase 6 should reuse the same lifecycle, ownership model, and protection concepts already planned in `docs/position-management-spec.md`.
Phase 6 should also reuse the shared risk-policy and guardrail semantics planned in `docs/backtest-risk-guardrails-spec.md` rather than inventing a paper-only pre-trade gate.
Phase 6 should also reuse the strategy/risk/assumption governance model planned in `docs/strategy-risk-assumption-management-spec.md` rather than inventing a separate paper-session configuration vocabulary.
Phase 6 should also preserve the family/variant/version identity model planned in `docs/strategy-taxonomy-and-versioning-spec.md` so paper sessions, fills, and reports do not invent a separate strategy naming scheme.

## Goal
Run strategy logic continuously in simulated real time using live market data and execution logic.

## Scope
- runtime strategy loop
- signal to order translation
- simulated fill logic
- position and balance maintenance
- pre-trade risk checks

## Required Deliverables
- `src/execution/paper_executor.py`
- runtime loop for paper trading
- simulated execution path

## Task Checklist

## Task 6.1: Build runtime strategy loop
### Tasks
- [ ] define loop for loading latest market state
- [ ] evaluate strategy on live/polled data
- [ ] emit signals at configured cadence
- [ ] support graceful stop/start behavior
- [ ] keep session metadata attributable to stable `strategy_code` (variant) and `strategy_version`

### Acceptance Checks
- [ ] paper runtime can run continuously for a session
- [ ] strategy loop produces signals in real time or near real time

---

## Task 6.2: Implement signal-to-order translation
### Tasks
- [ ] translate signal into order request
- [ ] enforce instrument trading rules
- [ ] assign canonical `client_order_id`
- [ ] record initial order state
- [ ] preserve stable strategy variant/version identity on order and signal-linked records

### Acceptance Checks
- [ ] orders are generated consistently from signals
- [ ] invalid order requests are rejected before execution

---

## Task 6.3: Implement paper fill simulation
### Tasks
- [ ] simulate fills using latest market data
- [ ] support basic market and limit order behavior
- [ ] persist order events and fills
- [ ] record fees and liquidity flags where modeled

### Acceptance Checks
- [ ] paper orders transition through lifecycle states
- [ ] fills update order status correctly
- [ ] fill outcomes are persisted

---

## Task 6.4: Maintain positions and balances
### Tasks
- [ ] update positions on fills
- [ ] update balances on fills and fees
- [ ] generate snapshots for positions and balances
- [ ] record PnL evolution
- [ ] keep reporting and snapshots attributable to the originating strategy variant/version

### Acceptance Checks
- [ ] positions and balances remain internally consistent
- [ ] snapshots can be inspected historically

---

## Task 6.5: Implement pre-trade risk checks
### Tasks
- [ ] load `risk.risk_limits`
- [ ] reuse the shared Phase 5 guardrail semantics where a paper-session risk policy is equivalent
- [ ] validate order size and notional before simulated submission
- [ ] record risk events on violations
- [ ] prevent invalid orders from proceeding

### Acceptance Checks
- [ ] oversized or disallowed orders are blocked
- [ ] paper pre-trade risk behavior remains compatible with the Phase 5 backtest guardrail model
- [ ] blocked actions create `risk.risk_events`

---

## Task 6.6: Record timing and monitoring data
### Tasks
- [ ] capture signal time
- [ ] capture simulated submit and fill timing
- [ ] write `execution.execution_latency_metrics`
- [ ] log paper runtime lifecycle events

### Acceptance Checks
- [ ] paper lifecycle timing can be analyzed after a run
- [ ] runtime events are visible in logs and/or metrics

---

## Phase 6 Final Acceptance Summary
- [ ] paper runtime loop works
- [ ] signals become orders
- [ ] orders become simulated fills
- [ ] positions and balances update correctly
- [ ] risk checks are enforced
- [ ] timing metrics are recorded
- [ ] paper-path records preserve stable strategy variant/version identity

## Handoff Criteria to Phase 7
- [ ] execution flow is stable enough to swap simulated routing for exchange routing
- [ ] canonical order lifecycle is already proven in paper mode
- [ ] paper-path position/protection/reporting behavior remains compatible with `docs/position-management-spec.md`
- [ ] paper sessions and reports remain attributable by stable strategy variant/version identity

---

# Phase 7: Private Exchange Adapter and Live Trading MVP

## Architecture Alignment Note
Phase 7 should continue the same shared lifecycle and ownership model from `docs/position-management-spec.md`, especially if shared-account execution or future fill allocation is introduced.
Phase 7 should also continue the strategy family/variant/version semantics from `docs/strategy-taxonomy-and-versioning-spec.md`, especially for deployment, live session ownership, and later reporting.

## Goal
Support the first real trading path on one exchange account.

## Scope
- authenticated private exchange adapter
- real order submission and cancel
- execution report ingestion
- private account state sync

## Required Deliverables
- `src/exchange/`
- `src/execution/live_executor.py`
- authenticated REST and websocket clients

## Task Checklist

## Task 7.1: Implement authenticated REST client
### Tasks
- [ ] create exchange private REST client module
- [ ] implement request signing/authentication
- [ ] load credentials from environment securely
- [ ] handle retries and error normalization

### Acceptance Checks
- [ ] authenticated API calls succeed in local testing
- [ ] invalid credential paths fail safely

---

## Task 7.2: Implement order placement and cancel flow
### Tasks
- [ ] submit live order request to exchange
- [ ] persist initial order state before or at submission
- [ ] persist exchange ack and exchange order id
- [ ] implement cancel path
- [ ] normalize exchange errors into order events
- [ ] preserve stable strategy variant/version identity on all live order lifecycle records

### Acceptance Checks
- [ ] system can place an order on one live account
- [ ] system can cancel an order on one live account
- [ ] order states are persisted correctly

---

## Task 7.3: Implement private execution/fill ingestion
### Tasks
- [ ] subscribe to private execution or order update stream
- [ ] normalize order updates to canonical order events
- [ ] normalize fills to canonical fill model
- [ ] persist order events and fills

### Acceptance Checks
- [ ] live order lifecycle transitions are persisted
- [ ] exchange fills are captured without manual intervention

---

## Task 7.4: Implement private balance and position sync
### Tasks
- [ ] fetch or stream balances
- [ ] fetch or stream positions
- [ ] write snapshots to execution tables
- [ ] reconcile state after fills or periodic sync
- [ ] preserve attribution needed for future variant/version-level reporting and fill allocation

### Acceptance Checks
- [ ] balances can be retrieved and persisted
- [ ] positions can be retrieved and persisted
- [ ] live state reflects exchange state within acceptable lag

---

## Task 7.5: Record ledger, funding, and latency data
### Tasks
- [ ] fetch funding history where available
- [ ] write `execution.funding_pnl`
- [ ] fetch account history for ledger entries where available
- [ ] record `execution.execution_latency_metrics`
- [ ] keep ledger/funding traces attributable to the deployed strategy variant/version where model scope allows

### Acceptance Checks
- [ ] funding events can be stored for live account activity
- [ ] at least baseline ledger records can be persisted
- [ ] latency metrics are available for live orders

---

## Phase 7 Final Acceptance Summary
- [ ] authenticated private adapter works
- [ ] live order placement works
- [ ] live cancel works
- [ ] order events and fills persist correctly
- [ ] positions and balances sync correctly
- [ ] funding/ledger/latency baseline exists
- [ ] live-path records remain attributable to stable strategy variant/version identity

## Handoff Criteria to Phase 8
- [ ] one live trading path is functional end to end
- [ ] exchange state and DB state can now be compared for reconciliation
- [ ] live execution and accounting records preserve enough strategy identity for later deployment audit and reconciliation reporting

---

# Phase 8: Reconciliation, Treasury, and Operational Controls

## Architecture Alignment Note
Phase 8 reconciliation and audit work should treat `docs/position-management-spec.md` as the intended backbone for fill truth, strategy/account ownership, protection history, and reporting traceability.
Phase 8 should also treat `docs/strategy-taxonomy-and-versioning-spec.md` as the intended backbone for variant/version attribution and future family-aware reporting.

## Goal
Make the live system auditable and safe enough for ongoing operation.

## Scope
- reconciliation jobs
- treasury sync
- deployment and config audit
- exchange status awareness
- operational controls

## Required Deliverables
- reconciliation jobs
- treasury sync path
- deployment audit path
- operational visibility for exchange status and forced reduction events

## Task Checklist

## Task 8.1: Reconcile open orders and order states
### Tasks
- [ ] compare exchange open orders with DB orders
- [ ] detect missing or stale order states
- [ ] record reconciliation mismatches
- [ ] define remediation workflow for mismatches

### Acceptance Checks
- [ ] order mismatches can be detected automatically
- [ ] mismatches are recorded for review

---

## Task 8.2: Reconcile fills, balances, and ledger
### Tasks
- [ ] compare exchange fills to `execution.fills`
- [ ] compare funding history to `execution.funding_pnl`
- [ ] compare exchange account history to `execution.account_ledger`
- [ ] define process for backfilling missed events

### Acceptance Checks
- [ ] fill and funding mismatches can be detected
- [ ] ledger inconsistencies can be surfaced

---

## Task 8.3: Implement treasury movement sync
### Tasks
- [ ] fetch deposit history
- [ ] fetch withdrawal history
- [ ] normalize treasury events
- [ ] persist to `execution.deposits_withdrawals`
- [ ] preserve network and tx metadata where available

### Acceptance Checks
- [ ] deposits and withdrawals are queryable historically
- [ ] treasury events include enough metadata for audit

---

## Task 8.4: Implement deployment and config audit flow
### Tasks
- [ ] write strategy deployment records into `strategy.deployments`
- [ ] write parameter/config changes into `strategy.config_change_audit`
- [ ] link deployments to strategy versions and environments
- [ ] keep deployment and config audit records aligned to stable variant/version identity rather than broad family labels

### Acceptance Checks
- [ ] deployments are historically traceable
- [ ] config changes are historically traceable
- [ ] performance regressions can be tied back to config/deployment history
- [ ] deployment audit records are attributable at strategy variant/version granularity

---

## Task 8.5: Implement exchange status and forced reduction ingestion
### Tasks
- [ ] ingest exchange/system status changes
- [ ] write `risk.exchange_status_events`
- [ ] ingest forced reduction / ADL / exception position events where available
- [ ] write `risk.forced_reduction_events`

### Acceptance Checks
- [ ] exchange pauses or maintenance can be represented in DB
- [ ] forced reduction or exceptional position changes can be persisted

---

## Task 8.6: Define operational control workflow
### Tasks
- [ ] define manual stop/disable workflow for strategy runtime
- [ ] define incident logging path
- [ ] define basic runbook for mismatch handling

### Acceptance Checks
- [ ] operators have a documented workflow for critical incidents
- [ ] runtime shutdown or trading halt process is documented

---

## Phase 8 Final Acceptance Summary
- [ ] order reconciliation exists
- [ ] fill/ledger/funding reconciliation exists
- [ ] treasury sync exists
- [ ] deployment/config audit exists
- [ ] exchange status and forced reduction events exist
- [ ] operational control workflow is documented
- [ ] reconciliation and audit outputs preserve strategy variant/version attribution where applicable

## Handoff Criteria to Phase 9
- [ ] the live system is operationally traceable enough to harden and scale
- [ ] major production mismatches can be detected and reviewed

---

# Phase 9: Production Hardening and Scale Improvements

## Goal
Improve reliability, maintainability, and scalability once the end-to-end system works.

## Scope
- tests
- CI
- lint/format/type checking
- alerts
- retention policy
- storage scaling

## Required Deliverables
- test suite
- CI workflow
- code quality pipeline
- alerting baseline
- data retention/scaling plan

## Task Checklist

## Task 9.1: Add unit and integration tests
### Tasks
- [ ] add model validation tests
- [ ] add repository tests
- [ ] add ingestion tests
- [ ] add backtest tests
- [ ] add paper execution tests
- [ ] add selected live adapter integration tests or mocks

### Acceptance Checks
- [ ] core modules have automated test coverage
- [ ] regression failures can be caught before merge

---

## Task 9.2: Add lint, formatting, and type checks
### Tasks
- [ ] add formatter configuration
- [ ] add linter configuration
- [ ] add type checker configuration
- [ ] add commands to run them locally

### Acceptance Checks
- [ ] repository has a standard code quality toolchain
- [ ] developers can run checks consistently before commits

---

## Task 9.3: Add CI workflow
### Tasks
- [ ] add GitHub workflow for tests
- [ ] add GitHub workflow for lint/type checks
- [ ] optionally add DB bootstrap smoke test

### Acceptance Checks
- [ ] pull requests are validated automatically
- [ ] failures are visible before merge

---

## Task 9.4: Add alerting baseline
### Tasks
- [ ] define alerts for ingestion failures
- [ ] define alerts for stale data
- [ ] define alerts for failed live orders or reconciliation mismatches
- [ ] document how alerts are routed

### Acceptance Checks
- [ ] critical operational failures have defined alert conditions
- [ ] alert routing is documented

---

## Task 9.5: Define retention policy and archival strategy
### Tasks
- [ ] define retention for raw market events
- [ ] define retention for order book deltas
- [ ] define archival policy for large historical datasets
- [ ] document cleanup/archival workflow

### Acceptance Checks
- [ ] retention policy is explicit
- [ ] project has a strategy for preventing uncontrolled table growth

---

## Task 9.6: Evaluate high-volume data scaling path
### Tasks
- [ ] identify highest-volume tables
- [ ] evaluate whether to keep them in PostgreSQL short term
- [ ] evaluate splitting to ClickHouse or object storage
- [ ] document recommended future architecture

### Acceptance Checks
- [ ] high-volume scaling decision is documented
- [ ] repository has a clear plan for future storage evolution

---

## Phase 9 Final Acceptance Summary
- [ ] automated tests exist
- [ ] CI exists
- [ ] lint/format/type checks exist
- [ ] alerting baseline exists
- [ ] retention policy exists
- [ ] scaling path is documented

## Project-Level Completion Criteria After Phase 9
- [ ] DB initializes and seeds from scratch
- [ ] market data ingestion works
- [ ] data quality checks work
- [ ] reproducible backtests work
- [ ] paper trading works
- [ ] first live trading path works
- [ ] reconciliation and treasury tracking work
- [ ] tests and CI protect ongoing development

---

# Suggested Execution Order Summary

## Foundation
- Phase 2
- Phase 3

## Research
- Phase 4
- Phase 5

## Trading
- Phase 6
- Phase 7
- Phase 8

## Hardening
- Phase 9

---

# Recommended Immediate Next Action

Current recommended next action:
- surface strategy market context inside diagnostics / debug-trace inspection for feature-driven and sentiment-aware runs
- keep broader sentiment feature-pipeline formalization deferred until trace/debug surfaces can explain context-gated decisions
- continue keeping the Phase 5 phase/task/checklist docs aligned as the diagnostics evidence layer expands
