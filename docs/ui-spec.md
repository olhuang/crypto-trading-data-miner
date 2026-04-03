# UI Spec

## Purpose

This document defines the internal product UI needed to support implementation, operation, and verification across all project phases.

The UI in this document is **not** a polished retail end-user frontend.
It is an **internal operator / developer / researcher console** designed to:
- make each phase observable
- allow manual operation where needed
- allow user validation that the phase is working
- reduce reliance on raw SQL and log inspection

This design intentionally aligns with the current project roadmap so that each phase has a corresponding UI surface that can be built and validated independently.

---

## 1. Product Positioning for the UI

### 1.1 UI Type
This UI is an **internal console** for:
- developers
- quant researchers
- operators
- traders
- system maintainers

### 1.2 UI Objectives
The UI must allow users to:
1. inspect system state
2. trigger phase-specific workflows
3. validate outputs without direct DB access
4. investigate failures and anomalies
5. confirm readiness before moving to the next phase

### 1.3 What This UI Is Not
This UI is not intended to be:
- a consumer trading terminal
- a full portfolio management SaaS frontend
- a public-facing website
- a comprehensive charting workstation in early phases

---

## 2. Design Principles

### 2.1 Phase-Aligned
Every implementation phase must have at least one corresponding UI surface for:
- operation
- inspection
- validation

### 2.2 Minimal but Useful
Early phases should use simple admin-style screens rather than polished visual design.
A basic table, form, and status panel is acceptable if it makes the phase operable.

### 2.3 Progressive Disclosure
Users should see a simple overview first, then be able to drill into details:
- summary metrics
- recent activity
- detailed records
- raw payloads / logs

### 2.4 Operational Traceability
Every important action should lead to an inspectable result.
Examples:
- seed DB -> view seeded rows
- run backfill -> view job status and written rows
- place paper order -> view order event chain
- deploy strategy -> view deployment record

### 2.5 One Console, Many Modes
The UI should feel like a single product with multiple modules, not unrelated tools.

---

## 3. Primary User Roles

### 3.1 Developer
Needs:
- inspect DB/bootstrap status
- run jobs manually
- inspect raw and normalized data
- validate payload behavior

### 3.2 Quant Researcher
Needs:
- inspect historical market data
- configure strategy versions
- run backtests
- inspect performance outputs

### 3.3 Operator / Trader
Needs:
- monitor ingestion health
- inspect order/fill/position state
- monitor paper/live strategy runtime
- review risk and reconciliation alerts

### 3.4 Admin
Needs:
- manage reference data
- manage deployments/config changes
- inspect treasury movements
- verify operational readiness

---

## 4. Global Information Architecture

The UI should eventually be organized into these top-level sections:

1. **Home**
2. **System**
3. **Reference Data**
4. **Market Data**
5. **Quality & Ops**
6. **Strategies**
7. **Backtests**
8. **Paper Trading**
9. **Live Trading**
10. **Risk**
11. **Treasury**
12. **Reconciliation**
13. **Admin / Deployments**

---

## 5. Shared UI Components

These components should be reusable across all phases:

### 5.1 Global Layout
- left navigation sidebar
- top header with environment label
- content area
- right-side optional detail drawer

### 5.2 Shared Page Patterns
- summary cards
- searchable data tables
- filter bars
- detail drawer / detail page
- status badges
- structured JSON viewer
- action buttons with confirmation modals

### 5.3 Standard State Colors
- success
- warning
- error
- running
- idle
- disabled

### 5.4 Standard Detail Tabs
Where relevant, detail views should expose tabs such as:
- Overview
- Records
- Events
- Logs
- Raw Payload
- Metrics

---

## 6. Phase-to-UI Mapping Overview

| Phase | Core UI Goal | Primary UI Surface |
|---|---|---|
| Phase 0 | make local runtime visible | System / Environment page |
| Phase 1 | validate DB bootstrap and seed data | Database Bootstrap page + Reference Data pages |
| Phase 2 | validate canonical payloads and storage | Model Validation page + Repository Explorer |
| Phase 3 | operate and inspect ingestion | Ingestion Jobs page + Market Data Explorer |
| Phase 4 | inspect data quality and replay readiness | Data Quality page + Raw Event Explorer |
| Phase 5 | run and inspect backtests | Strategy Lab + Backtest Runs page |
| Phase 6 | operate and monitor paper trading | Paper Trading Console |
| Phase 7 | operate and inspect live trading | Live Trading Console |
| Phase 8 | inspect reconciliation and treasury operations | Reconciliation page + Treasury page + Deployment Audit |
| Phase 9 | inspect reliability and control signals | Reliability Dashboard + Admin Settings |

---

# 7. Detailed UI Spec by Phase

# Phase 0 UI: Repository and Runtime Bootstrap

## Goal
Let the user verify that the local runtime environment is up and reachable.

## Required UI Surfaces

### 7.0.1 System Overview Page
Displays:
- application environment
- API service status
- PostgreSQL connection status
- Redis connection status
- build/version info
- recent startup logs

### 7.0.2 Environment Config Page
Displays:
- current environment variables used by the app
- masked secrets
- runtime dependency status

## Primary User Actions
- view whether services are up
- refresh health checks
- inspect startup configuration
- inspect recent application logs

## Validation Criteria
A user must be able to confirm without shell access that:
- app is running
- DB is reachable
- Redis is reachable
- environment is correctly loaded

## Suggested Acceptance UI Checks
- [ ] System Overview shows green status for DB and Redis
- [ ] recent startup logs are visible
- [ ] environment label is visible in header

---

# Phase 1 UI: Database Bootstrap and Seed Data

## Goal
Let the user initialize, inspect, and validate seeded database state.

## Required UI Surfaces

### 7.1.1 Database Bootstrap Page
Displays:
- migration file list
- migration execution order
- bootstrap status
- latest bootstrap timestamp
- latest bootstrap result
- verification checklist status

Actions:
- run bootstrap verification
- show expected seed scope
- view validation results

### 7.1.2 Reference Data: Exchanges Page
Displays:
- exchange table
- exchange metadata
- row count

Actions:
- view details
- search/filter by exchange code

### 7.1.3 Reference Data: Assets Page
Displays:
- asset table
- asset type
- row count

### 7.1.4 Reference Data: Instruments Page
Displays:
- exchange
- venue symbol
- unified symbol
- instrument type
- base / quote / settlement asset
- tick size / lot size / min qty / min notional / status

Actions:
- filter by exchange
- filter by instrument type
- inspect detail view

### 7.1.5 Fee Schedule Page
Displays:
- exchange
- instrument type
- maker/taker fee
- effective date

## Primary User Actions
- confirm bootstrap completion
- inspect seeded exchanges/assets/instruments
- verify spot and perp coverage per exchange
- verify starter fee schedules exist

## Validation Criteria
A user must be able to confirm from the UI that:
- schemas and seed completed
- Binance and Bybit exist
- BTC, ETH, USDT, USDC exist
- each exchange has spot and perp instruments
- fee schedule rows exist if included

## Suggested Acceptance UI Checks
- [ ] Database Bootstrap page shows latest verification result
- [ ] Instruments page shows seeded spot/perp rows for both exchanges
- [ ] Instrument detail page resolves base/quote/settlement correctly
- [ ] Fee Schedule page shows starter rows

---

# Phase 2 UI: Domain Models and Storage Layer

## Goal
Let the user validate canonical payloads and inspect storage behavior without direct code debugging.

## Required UI Surfaces

### 7.2.1 Model Validation Playground
Displays:
- payload input area
- payload type selector
- validation result panel
- normalized parsed output panel
- validation error panel

Supported payload types:
- instrument metadata
- bar event
- trade event
- funding rate
- signal
- order request
- fill
- position snapshot
- balance snapshot

Actions:
- paste JSON payload
- run validation
- inspect parsed model output

### 7.2.2 Repository Explorer
Displays:
- repository/entity selector
- query filters
- record table
- record detail drawer

Actions:
- inspect DB writes by entity type
- search by canonical key
- verify deduplicated rows

### 7.2.3 DB Write Test Page
Displays:
- sample payload templates
- write-to-DB action
- write result
- duplicate handling result

## Primary User Actions
- paste payloads and verify validation
- write validated payloads to storage in test mode
- inspect whether deduplication/upsert behavior works

## Validation Criteria
A user must be able to confirm that:
- canonical payloads validate successfully
- invalid payloads return readable errors
- storage writes succeed
- duplicates are handled safely

## Suggested Acceptance UI Checks
- [ ] Model Validation Playground accepts at least one sample payload per major entity
- [ ] invalid payload produces visible validation error
- [ ] Repository Explorer shows recently written records
- [ ] duplicate write shows safe handling behavior

---

# Phase 3 UI: Public Market Data Ingestion

## Goal
Let the user run, monitor, and inspect market data ingestion.

## Required UI Surfaces

### 7.3.1 Ingestion Jobs Dashboard
Displays:
- current and recent jobs
- job type
- exchange
- instrument
- window start/end
- status
- records expected / written
- error message

Actions:
- trigger job manually
- retry failed job
- filter by status/data type/exchange

### 7.3.2 Instrument Sync Page
Displays:
- latest sync job
- changed instruments
- metadata differences

Actions:
- run instrument sync
- inspect metadata changes

### 7.3.3 Market Data Explorer
Tabs:
- Bars
- Trades
- Funding
- Open Interest
- Mark Price
- Index Price
- Liquidations

Displays:
- filter by exchange / symbol / time range
- table view
- simple chart preview where useful

### 7.3.4 Websocket Stream Monitor
Displays:
- connection status
- subscription channels
- last message time
- message rate
- recent connect/disconnect events

## Primary User Actions
- backfill bars
- run instrument sync
- inspect live trade ingestion
- inspect funding / OI refresh
- view websocket health

## Validation Criteria
A user must be able to confirm that:
- backfill jobs run and complete
- live trades are arriving
- funding and OI are refreshed
- stream connectivity is visible

## Suggested Acceptance UI Checks
- [ ] Ingestion Jobs Dashboard shows successful bar backfill job
- [ ] Market Data Explorer shows newly ingested bars and trades
- [ ] Websocket Stream Monitor shows active connection and last message time
- [ ] failed jobs show readable error info

---

# Phase 4 UI: Market Data Quality and Replay Readiness

## Goal
Let the user inspect data quality issues and raw-to-normalized traceability.

## Required UI Surfaces

### 7.4.1 Data Quality Dashboard
Displays:
- freshness status
- duplicate status
- gap counts
- severity summary
- checks by data type

### 7.4.2 Data Gaps Page
Displays:
- exchange
- instrument
- data type
- gap window
- expected vs actual count
- status

Actions:
- filter by open/resolved
- inspect affected range

### 7.4.3 Raw Event Explorer
Displays:
- channel
- event type
- event time
- ingest time
- payload JSON
- matching normalized records if available

Actions:
- inspect raw payload
- trace to normalized data

### 7.4.4 Replay Readiness Page
Displays:
- raw data coverage
- retained datasets
- readiness checklist for replay

## Primary User Actions
- inspect data gaps
- inspect stale datasets
- inspect duplicate anomalies
- trace normalized rows back to raw events

## Validation Criteria
A user must be able to confirm that:
- gaps and freshness issues are visible
- quality checks are stored and inspectable
- raw payloads can be reviewed for debugging

## Suggested Acceptance UI Checks
- [ ] Data Quality Dashboard shows pass/fail counts
- [ ] Data Gaps page lists missing windows when they exist
- [ ] Raw Event Explorer can open raw payload JSON
- [ ] a normalized market record can be traced from UI to a raw event or source pattern

---

# Phase 5 UI: Strategy Runner and Bars-Based Backtest

## Goal
Let the user configure, run, and inspect backtests.

## Required UI Surfaces

### 7.5.1 Strategy Registry Page
Displays:
- strategies
- versions
- parameter sets
- active/inactive state

Actions:
- inspect strategy versions
- compare parameter sets

### 7.5.2 Backtest Run Builder
Form inputs:
- strategy
- strategy version
- exchange / universe
- instrument set
- time range
- fee model version
- slippage model version
- optional parameters override

Actions:
- launch backtest

### 7.5.3 Backtest Runs Page
Displays:
- run id
- strategy version
- time range
- status
- created time
- summary KPIs

Actions:
- open run detail
- compare runs

### 7.5.4 Backtest Run Detail Page
Sections:
- run metadata
- equity curve
- performance summary
- simulated orders
- simulated fills
- exposure series
- optional signals
- diagnostic summary
- debug trace viewer

## Primary User Actions
- choose strategy and time range
- run bars-based backtest
- inspect summary KPIs
- inspect simulated orders and fills
- inspect diagnostics and debug traces
- compare runs

## Validation Criteria
A user must be able to confirm that:
- backtest can be launched from UI
- run metadata is persisted
- KPIs and timeseries are visible
- simulated orders/fills can be inspected
- diagnostics/debug traces can be inspected

## Suggested Acceptance UI Checks
- [ ] Backtest Run Builder can launch a run
- [ ] Backtest Runs page lists completed run
- [ ] Backtest Run Detail shows equity curve and summary stats
- [ ] simulated orders and fills are inspectable from the UI
- [ ] diagnostics/debug traces are inspectable from the UI

---

# Phase 6 UI: Paper Trading Engine

## Goal
Let the user start, stop, and monitor paper trading sessions.

## Required UI Surfaces

### 7.6.1 Paper Trading Console
Displays:
- selected strategy and version
- runtime status
- environment label
- recent signals
- open paper orders
- recent fills
- current positions
- account balances
- PnL summary

Actions:
- start session
- stop session
- pause strategy
- resume strategy

### 7.6.2 Paper Orders Page
Displays:
- order table
- status
- side/type/qty/price
- timestamps
- source signal id

### 7.6.3 Paper Order Detail Page
Displays:
- order state
- order event timeline
- related fills
- latency metrics
- linked signal details

### 7.6.4 Paper Risk Panel
Displays:
- configured limits
- blocked orders
- risk events

## Primary User Actions
- run a strategy in paper mode
- monitor signals, orders, fills, positions, balances
- inspect blocked orders and risk events

## Validation Criteria
A user must be able to confirm that:
- paper strategy can run continuously
- signals become orders
- orders become simulated fills
- positions and balances update
- risk violations are visible

## Suggested Acceptance UI Checks
- [ ] Paper Trading Console shows running session state
- [ ] Paper Orders page shows lifecycle transitions
- [ ] Paper Order Detail shows event timeline and fills
- [ ] Paper Risk Panel shows blocked actions if limits are exceeded

---

# Phase 7 UI: Private Exchange Adapter and Live Trading MVP

## Goal
Let the user operate and inspect the first live exchange path safely.

## Required UI Surfaces

### 7.7.1 Live Trading Console
Displays:
- connected exchange account
- connection/auth status
- strategy runtime status
- recent live orders
- recent live fills
- current live positions
- balances/equity
- latency summary

Actions:
- enable live strategy
- disable live strategy
- emergency stop

### 7.7.2 Manual Order Ticket
Inputs:
- exchange account
- symbol
- side
- type
- qty
- price
- tif

Actions:
- submit order
- cancel order

### 7.7.3 Live Order Detail Page
Displays:
- current order state
- exchange order id
- event timeline
- fill timeline
- raw exchange events if available

### 7.7.4 Live Account State Page
Displays:
- balances
- positions
- funding history summary
- ledger summary

## Primary User Actions
- inspect live connectivity
- submit test order
- cancel order
- monitor order state/fills/positions
- inspect latency and account state

## Validation Criteria
A user must be able to confirm that:
- live adapter is connected and authenticated
- a live order can be placed and canceled from UI
- order events and fills are visible
- balances and positions reflect live state

## Suggested Acceptance UI Checks
- [ ] Live Trading Console shows connected account status
- [ ] Manual Order Ticket can submit a live order
- [ ] Live Order Detail shows exchange ack and fills
- [ ] Live Account State page shows current balances and positions

---

# Phase 8 UI: Reconciliation, Treasury, and Operational Controls

## Goal
Let the user inspect mismatches, treasury movements, deployment history, and exceptional events.

## Required UI Surfaces

### 7.8.1 Reconciliation Dashboard
Displays:
- open order mismatches
- fill mismatches
- funding mismatches
- ledger mismatches
- mismatch severity summary

Actions:
- filter mismatches
- inspect details
- mark reviewed

### 7.8.2 Treasury Page
Displays:
- deposits
- withdrawals
- network
- tx hash
- wallet address
- amount / fee
- status

Actions:
- filter by asset/network/status
- inspect detail record

### 7.8.3 Deployment Audit Page
Displays:
- strategy deployments
- deployment status
- rollout time / stop time
- git commit / image tag
- config snapshot

Actions:
- inspect deployment details
- compare config changes

### 7.8.4 Exchange Status / Exception Events Page
Displays:
- exchange pauses
- maintenance windows
- forced reduction events
- ADL-like events

## Primary User Actions
- inspect system mismatches
- inspect treasury movement history
- inspect config/deployment changes
- inspect exchange outage/forced reduction events

## Validation Criteria
A user must be able to confirm that:
- reconciliation mismatches can be discovered in UI
- treasury records include enough metadata for review
- deployments/config changes are historically traceable
- exchange exception events are visible

## Suggested Acceptance UI Checks
- [ ] Reconciliation Dashboard shows mismatches when they exist
- [ ] Treasury Page shows deposit/withdrawal records with tx/network metadata
- [ ] Deployment Audit page shows rollout history
- [ ] Exchange Status page shows outage or exception records

---

# Phase 9 UI: Production Hardening and Scale Improvements

## Goal
Let the user inspect reliability, alerting, and long-term operational health.

## Required UI Surfaces

### 7.9.1 Reliability Dashboard
Displays:
- ingestion failure rate
- stale data alerts
- system uptime summary
- queue/job health summary
- DB/storage health summary if available

### 7.9.2 Alerts Page
Displays:
- active alerts
- alert history
- severity
- routing status
- acknowledged / unresolved state

### 7.9.3 Test and CI Status Page
Displays:
- latest test results
- lint/type-check status
- CI workflow history

### 7.9.4 Retention / Storage Policy Page
Displays:
- raw data retention settings
- archive policy summary
- high-volume table status
- scaling recommendations

## Primary User Actions
- inspect reliability trends
- inspect active alerts
- verify CI health
- inspect retention/scaling configuration

## Validation Criteria
A user must be able to confirm that:
- reliability signals are visible
- alerts are reviewable
- CI health is visible to maintainers
- retention/scaling policy is inspectable

## Suggested Acceptance UI Checks
- [ ] Reliability Dashboard shows core operational health metrics
- [ ] Alerts Page shows active and historical alerts
- [ ] CI Status page reflects recent test/check runs
- [ ] Retention / Storage Policy page shows current policy and scaling notes

---

## 8. Shared Navigation Evolution by Phase

The navigation can expand gradually.

### Phase 0-1
- Home
- System
- Database Bootstrap
- Reference Data

### Phase 2-4
- Home
- System
- Reference Data
- Market Data
- Quality & Ops
- Model Validation

### Phase 5-6
- Home
- System
- Reference Data
- Market Data
- Quality & Ops
- Strategies
- Backtests
- Paper Trading
- Risk

### Phase 7-9
- Home
- System
- Reference Data
- Market Data
- Quality & Ops
- Strategies
- Backtests
- Paper Trading
- Live Trading
- Risk
- Treasury
- Reconciliation
- Admin / Deployments

---

## 9. Cross-Phase UI Acceptance Rules

Regardless of phase, each UI surface should satisfy these rules:

1. the user can inspect the latest state without opening the DB manually
2. the user can identify failure state from the UI
3. the user can access supporting details such as events, logs, or raw payloads
4. the user can tell which environment is being viewed
5. the user can filter by exchange, symbol, strategy, and time where relevant

---

## 10. Recommended UI Build Order

The UI should be built in the same order as the backend phases.

### UI Track A: Foundation UI
1. System Overview
2. Database Bootstrap
3. Reference Data Explorer

### UI Track B: Data UI
4. Model Validation Playground
5. Ingestion Jobs Dashboard
6. Market Data Explorer
7. Data Quality Dashboard
8. Raw Event Explorer

### UI Track C: Research and Execution UI
9. Strategy Registry
10. Backtest Run Builder / Backtest Runs / Run Detail
11. Paper Trading Console
12. Live Trading Console
13. Manual Order Ticket

### UI Track D: Operational UI
14. Reconciliation Dashboard
15. Treasury Page
16. Deployment Audit Page
17. Reliability Dashboard
18. Alerts Page

---

## 11. Future Technical Notes

This spec does not force a frontend framework.
However, a practical implementation should support:
- reusable admin-style table/detail pages
- structured JSON display
- charting for time series and PnL curves
- action forms with validation and confirmation
- environment-aware layouts

---

## 12. Final Summary

The UI plan is intentionally mapped one-to-one with the project phases.

That means each phase can be considered complete only when:
1. the backend capability exists, and
2. the corresponding UI allows a user to operate or verify that capability.

This prevents the project from becoming a backend-only system that is difficult to inspect, validate, or operate safely.
