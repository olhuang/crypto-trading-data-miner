# UI Phase Checklists

## Purpose

This document turns `docs/ui-spec.md` into a phased UI implementation checklist.

For each phase, it defines:
- UI goal
- required pages
- required components
- user events / actions
- data dependencies
- acceptance checks
- handoff criteria to the next UI phase

This file is intended to be used together with:
- `docs/implementation-plan.md`
- `docs/ui-spec.md`
- `docs/ui-api-spec.md`
- `docs/phase-1-checklist.md`
- `docs/phases-2-to-9-checklists.md`

---

## Global UI Rules

These rules apply to every phase.

### Shared Layout
- [ ] left navigation is present
- [ ] environment label is visible in header
- [ ] page title and page-level status are visible
- [ ] loading, empty, error, and success states are implemented

### Shared Components
- [ ] table component supports filtering and sorting where needed
- [ ] detail drawer or detail page exists for inspectable entities
- [ ] JSON viewer exists for payload/debug views
- [ ] status badges are consistent across modules
- [ ] confirmation modal exists for dangerous actions

### Shared UX Requirements
- [ ] user can identify current environment from any page
- [ ] user can inspect latest relevant state without raw SQL
- [ ] error messages are understandable and actionable
- [ ] timestamps are consistently displayed in UTC or clearly labeled timezone

---

# Phase 0 UI Checklist: Repository and Runtime Bootstrap

## Goal
Allow the user to verify that the local runtime is up and correctly configured.

## Required Pages

### Page 0.1: System Overview
Purpose:
- show service readiness and startup state

Required sections:
- [ ] app health summary
- [ ] PostgreSQL health summary
- [ ] Redis health summary
- [ ] runtime metadata summary
- [ ] recent startup logs panel

### Page 0.2: Environment Config
Purpose:
- show loaded runtime configuration

Required sections:
- [ ] environment name
- [ ] version/build metadata
- [ ] loaded config keys summary
- [ ] masked secret indicators

## Required Components
- [ ] health status cards
- [ ] recent logs table
- [ ] config key-value table
- [ ] refresh action button

## Required User Events
- [ ] user opens System Overview
- [ ] user refreshes health checks
- [ ] user opens Environment Config
- [ ] user inspects recent logs

## Data Dependencies
- `/api/v1/system/health`
- `/api/v1/system/runtime`
- `/api/v1/system/logs`

## Acceptance Checks
- [ ] System Overview renders app/postgres/redis status
- [ ] runtime metadata is visible without shell access
- [ ] recent logs are inspectable in UI

## Handoff Criteria to Phase 1 UI
- [ ] the environment can be visually confirmed healthy
- [ ] the UI shell is usable for subsequent admin-style pages

---

# Phase 1 UI Checklist: Database Bootstrap and Seed Data

## Goal
Allow the user to verify database bootstrap and inspect seeded reference data.

## Required Pages

### Page 1.1: Database Bootstrap
Purpose:
- show migration/verification state

Required sections:
- [ ] migration file list
- [ ] latest bootstrap status summary
- [ ] latest verification run summary
- [ ] verification result details
- [ ] bootstrap guidance / next steps panel

### Page 1.2: Exchanges Explorer
Required sections:
- [ ] exchanges table
- [ ] row count summary
- [ ] exchange detail drawer

### Page 1.3: Assets Explorer
Required sections:
- [ ] assets table
- [ ] asset type filter
- [ ] asset detail drawer

### Page 1.4: Instruments Explorer
Required sections:
- [ ] instruments table
- [ ] exchange filter
- [ ] instrument type filter
- [ ] status filter
- [ ] instrument detail drawer/page

### Page 1.5: Fee Schedule Explorer
Required sections:
- [ ] fee schedules table
- [ ] exchange filter
- [ ] instrument type filter
- [ ] fee detail view

## Required Components
- [ ] verification summary cards
- [ ] migration status list
- [ ] searchable reference tables
- [ ] instrument detail panel with base/quote/settlement display

## Required User Events
- [ ] user opens Database Bootstrap page
- [ ] user triggers bootstrap verification
- [ ] user filters instruments by exchange
- [ ] user filters instruments by spot/perp
- [ ] user opens instrument detail
- [ ] user opens fee schedule detail

## Data Dependencies
- `/api/v1/bootstrap/status`
- `/api/v1/bootstrap/verify`
- `/api/v1/bootstrap/verification-runs/{verification_run_id}`
- `/api/v1/reference/exchanges`
- `/api/v1/reference/assets`
- `/api/v1/reference/instruments`
- `/api/v1/reference/instruments/{instrument_id}`
- `/api/v1/reference/fee-schedules`

## Acceptance Checks
- [ ] Database Bootstrap page shows latest verification result
- [ ] Exchanges Explorer shows Binance and Bybit
- [ ] Assets Explorer shows BTC, ETH, USDT, USDC
- [ ] Instruments Explorer shows seeded spot and perp instruments
- [ ] instrument detail resolves base/quote/settlement correctly
- [ ] Fee Schedule Explorer shows starter fee rows

## Handoff Criteria to Phase 2 UI
- [ ] user can visually confirm seeded reference data without direct DB access
- [ ] reference entity explorer pattern is reusable for later phases

---

# Phase 2 UI Checklist: Domain Models and Storage Layer

## Goal
Allow the user to validate canonical payloads and inspect repository persistence behavior.

## Required Pages

### Page 2.1: Model Validation Playground
Required sections:
- [ ] payload type selector
- [ ] JSON input editor
- [ ] validation result panel
- [ ] normalized payload panel
- [ ] validation error panel

### Page 2.2: Repository Explorer
Required sections:
- [ ] entity selector
- [ ] query filters
- [ ] records table
- [ ] detail drawer/page

### Page 2.3: DB Write Test
Required sections:
- [ ] sample payload templates
- [ ] validate-and-store action area
- [ ] write result summary
- [ ] duplicate-handling result summary

## Required Components
- [ ] code/JSON editor
- [ ] validation badge/output block
- [ ] entity table explorer
- [ ] record detail JSON viewer
- [ ] write action confirmation block

## Required User Events
- [ ] user selects payload type
- [ ] user pastes payload JSON
- [ ] user runs validation
- [ ] user runs validate-and-store
- [ ] user browses stored records by entity type
- [ ] user inspects stored record detail

## Data Dependencies
- `/api/v1/models/payload-types`
- `/api/v1/models/validate`
- `/api/v1/models/validate-and-store`
- `/api/v1/storage/{entity_type}`
- `/api/v1/storage/{entity_type}/{id}`

## Acceptance Checks
- [ ] payload validation works from UI for at least one market and one execution entity
- [ ] invalid payloads show readable field-level or structured errors
- [ ] Repository Explorer shows newly stored rows
- [ ] duplicate-safe behavior is visible after repeated writes

## Handoff Criteria to Phase 3 UI
- [ ] user can validate and inspect canonical data objects before ingestion UI is built
- [ ] generic explorer pattern is ready for market data pages

---

# Phase 3 UI Checklist: Public Market Data Ingestion

## Goal
Allow the user to operate ingestion and inspect incoming market data.

## Required Pages

### Page 3.1: Ingestion Jobs Dashboard
Required sections:
- [ ] job summary cards
- [ ] recent jobs table
- [ ] status filter
- [ ] exchange filter
- [ ] data type filter
- [ ] job detail drawer/page

### Page 3.2: Instrument Sync
Required sections:
- [ ] latest sync summary
- [ ] metadata diff list
- [ ] manual sync action

### Page 3.3: Bar Backfill Runner
Required sections:
- [ ] exchange selector
- [ ] symbol selector
- [ ] interval selector
- [ ] time range inputs
- [ ] trigger backfill action
- [ ] recent backfill result panel

### Page 3.4: Market Data Explorer
Tabs:
- [ ] Bars
- [ ] Trades
- [ ] Funding
- [ ] Open Interest
- [ ] Mark Price
- [ ] Index Price
- [ ] Liquidations

Each tab should include:
- [ ] exchange filter
- [ ] symbol filter
- [ ] time range filter
- [ ] data table
- [ ] simple preview chart where useful

### Page 3.5: Websocket Stream Monitor
Required sections:
- [ ] connection status cards
- [ ] channel list
- [ ] last message timestamp
- [ ] message rate panel
- [ ] recent connection events table

## Required Components
- [ ] ingestion job table
- [ ] job status badge
- [ ] backfill form
- [ ] market data explorer table
- [ ] lightweight chart component
- [ ] websocket status panel

## Required User Events
- [ ] user triggers instrument sync
- [ ] user triggers bar backfill
- [ ] user filters market data by exchange/symbol/time
- [ ] user inspects job detail
- [ ] user inspects websocket health

## Data Dependencies
- `/api/v1/ingestion/jobs`
- `/api/v1/ingestion/jobs/instrument-sync`
- `/api/v1/ingestion/jobs/bar-backfill`
- `/api/v1/market/bars`
- `/api/v1/market/trades`
- `/api/v1/market/funding-rates`
- `/api/v1/market/open-interest`
- `/api/v1/market/mark-prices`
- `/api/v1/market/index-prices`
- `/api/v1/market/liquidations`
- `/api/v1/streams/ws-status`
- `/api/v1/streams/ws-events`

## Acceptance Checks
- [ ] Ingestion Jobs Dashboard shows successful and failed jobs
- [ ] user can trigger and monitor bar backfill from UI
- [ ] Market Data Explorer shows persisted data in each implemented tab
- [ ] Websocket Stream Monitor shows active status and recent events

## Handoff Criteria to Phase 4 UI
- [ ] user can operate and inspect ingestion without shell scripts
- [ ] market data explorer pattern is stable enough for data quality diagnostics

---

# Phase 4 UI Checklist: Market Data Quality and Replay Readiness

## Goal
Allow the user to inspect data quality, gaps, and raw-to-normalized traceability.

## Required Pages

### Page 4.1: Data Quality Dashboard
Required sections:
- [ ] summary cards by severity/status
- [ ] freshness summary
- [ ] duplicate summary
- [ ] gap summary by data type
- [ ] recent checks table

### Page 4.2: Data Gaps Explorer
Required sections:
- [ ] gap table
- [ ] open/resolved filter
- [ ] exchange/symbol/data type filters
- [ ] gap detail view

### Page 4.3: Raw Event Explorer
Required sections:
- [ ] raw event table
- [ ] channel/event type filters
- [ ] payload detail viewer
- [ ] normalized-link panel if available

### Page 4.4: Replay Readiness
Required sections:
- [ ] replay readiness summary cards
- [ ] retained datasets list
- [ ] known gaps panel
- [ ] reprocessing notes section

## Required Components
- [ ] quality summary cards
- [ ] data gaps table
- [ ] JSON payload viewer
- [ ] raw-to-normalized linkage panel
- [ ] replay readiness checklist block

## Required User Events
- [ ] user filters quality checks by severity/status
- [ ] user opens a gap detail
- [ ] user opens raw payload JSON
- [ ] user inspects normalized links from raw event
- [ ] user reviews replay readiness summary

## Data Dependencies
- `/api/v1/quality/checks`
- `/api/v1/quality/summary`
- `/api/v1/quality/gaps`
- `/api/v1/market/raw-events`
- `/api/v1/market/raw-events/{raw_event_id}`
- `/api/v1/market/raw-events/{raw_event_id}/normalized-links`
- `/api/v1/replay/readiness`

## Acceptance Checks
- [ ] Data Quality Dashboard shows pass/fail summaries
- [ ] Data Gaps Explorer lists open gaps when present
- [ ] Raw Event Explorer displays payload JSON correctly
- [ ] replay readiness summary is visible without reading docs directly

## Handoff Criteria to Phase 5 UI
- [ ] user can visually determine whether data is trustworthy enough to backtest
- [ ] traceability views exist for debugging downstream strategy issues

---

# Phase 5 UI Checklist: Strategy Runner and Bars-Based Backtest

## Goal
Allow the user to configure, launch, and inspect backtests.

## Required Pages

### Page 5.1: Strategy Registry
Required sections:
- [ ] strategies table
- [ ] versions table or nested panel
- [ ] parameter summary viewer
- [ ] active/inactive state display

### Page 5.2: Backtest Run Builder
Required sections:
- [ ] strategy selector
- [ ] strategy version selector
- [ ] exchange/universe selector
- [ ] time range picker
- [ ] fee model selector
- [ ] slippage model selector
- [ ] parameter override editor
- [ ] run action button

### Page 5.3: Backtest Runs
Required sections:
- [ ] run list table
- [ ] status filter
- [ ] strategy filter
- [ ] time range filter
- [ ] compare selection support

### Page 5.4: Backtest Run Detail
Required sections:
- [ ] run metadata block
- [ ] KPI summary cards
- [ ] equity curve chart
- [ ] exposure chart or table
- [ ] simulated orders table
- [ ] simulated fills table
- [ ] signal table if available

## Required Components
- [ ] strategy/version selector components
- [ ] backtest launch form
- [ ] run status badges
- [ ] KPI summary cards
- [ ] equity curve chart
- [ ] orders/fills explorer tables

## Required User Events
- [ ] user opens strategy detail
- [ ] user selects strategy version
- [ ] user launches backtest
- [ ] user opens completed run
- [ ] user inspects run KPIs
- [ ] user inspects simulated orders/fills
- [ ] user compares runs if compare view is available

## Data Dependencies
- `/api/v1/strategies`
- `/api/v1/strategies/{strategy_id}`
- `/api/v1/strategy-versions`
- `/api/v1/backtests/runs`
- `/api/v1/backtests/runs/{run_id}`
- `/api/v1/backtests/runs/{run_id}/orders`
- `/api/v1/backtests/runs/{run_id}/fills`
- `/api/v1/backtests/runs/{run_id}/timeseries`
- `/api/v1/backtests/runs/{run_id}/signals`

## Acceptance Checks
- [ ] Backtest Run Builder can launch a run from UI
- [ ] Backtest Runs page lists completed run status
- [ ] Backtest Run Detail shows KPIs and equity curve
- [ ] simulated orders/fills can be filtered and inspected

## Handoff Criteria to Phase 6 UI
- [ ] user can operate a research workflow fully from UI
- [ ] run detail patterns are reusable for paper/live session detail pages

---

# Phase 6 UI Checklist: Paper Trading Engine

## Goal
Allow the user to operate and monitor paper trading sessions.

## Required Pages

### Page 6.1: Paper Trading Console
Required sections:
- [ ] session summary card
- [ ] strategy/version display
- [ ] runtime status badge
- [ ] recent signals panel
- [ ] open orders panel
- [ ] recent fills panel
- [ ] positions panel
- [ ] balances panel
- [ ] PnL summary

### Page 6.2: Paper Sessions List
Required sections:
- [ ] sessions table
- [ ] status filter
- [ ] strategy filter
- [ ] environment/session detail navigation

### Page 6.3: Paper Orders Explorer
Required sections:
- [ ] orders table
- [ ] status filter
- [ ] symbol filter
- [ ] session filter
- [ ] order detail link

### Page 6.4: Paper Order Detail
Required sections:
- [ ] order state block
- [ ] event timeline
- [ ] fills table
- [ ] latency metrics block
- [ ] linked signal summary

### Page 6.5: Paper Risk Panel
Required sections:
- [ ] configured limits summary
- [ ] blocked orders list
- [ ] risk events table

## Required Components
- [ ] session control bar (start/stop/pause/resume)
- [ ] live-updating summary cards or polling equivalents
- [ ] event timeline component
- [ ] position/balance summary tables
- [ ] risk event table

## Required User Events
- [ ] user starts paper session
- [ ] user pauses paper session
- [ ] user resumes paper session
- [ ] user stops paper session
- [ ] user inspects order timeline
- [ ] user inspects positions/balances
- [ ] user inspects risk violations

## Data Dependencies
- `/api/v1/paper/sessions`
- `/api/v1/paper/sessions/{session_id}`
- `/api/v1/paper/sessions/{session_id}/stop`
- `/api/v1/paper/sessions/{session_id}/pause`
- `/api/v1/paper/sessions/{session_id}/resume`
- `/api/v1/paper/orders`
- `/api/v1/paper/orders/{order_id}`
- `/api/v1/paper/orders/{order_id}/events`
- `/api/v1/paper/orders/{order_id}/fills`
- `/api/v1/paper/positions`
- `/api/v1/paper/balances`
- `/api/v1/paper/risk-events`
- `/api/v1/paper/latency-metrics`

## Acceptance Checks
- [ ] Paper Trading Console shows running session state
- [ ] user can control session lifecycle from UI
- [ ] Paper Orders Explorer shows status transitions
- [ ] Paper Order Detail shows events, fills, and latency metrics
- [ ] Paper Risk Panel shows blocked orders and risk events

## Handoff Criteria to Phase 7 UI
- [ ] user can operate a trading session safely in paper mode
- [ ] trading console patterns are ready to extend to live trading

---

# Phase 7 UI Checklist: Private Exchange Adapter and Live Trading MVP

## Goal
Allow the user to inspect and operate the first live exchange path safely.

## Required Pages

### Page 7.1: Live Trading Console
Required sections:
- [ ] live account status card
- [ ] auth/connection status block
- [ ] strategy runtime status block
- [ ] recent live orders panel
- [ ] recent fills panel
- [ ] live positions panel
- [ ] balances/equity panel
- [ ] latency summary panel

### Page 7.2: Manual Order Ticket
Required sections:
- [ ] account selector
- [ ] symbol selector
- [ ] side selector
- [ ] order type selector
- [ ] qty input
- [ ] price input when applicable
- [ ] tif input
- [ ] submit button
- [ ] cancel action entry point for selected order

### Page 7.3: Live Orders Explorer
Required sections:
- [ ] live orders table
- [ ] status filter
- [ ] account filter
- [ ] symbol filter
- [ ] order detail navigation

### Page 7.4: Live Order Detail
Required sections:
- [ ] order summary
- [ ] exchange order id
- [ ] order event timeline
- [ ] fill timeline/table
- [ ] raw exchange payload block if available

### Page 7.5: Live Account State
Required sections:
- [ ] balances table
- [ ] positions table
- [ ] funding PnL summary
- [ ] ledger summary

## Required Components
- [ ] account connection status badge
- [ ] manual order form with inline validation
- [ ] emergency stop button with confirmation modal
- [ ] live order timeline component
- [ ] live balances/positions tables

## Required User Events
- [ ] user enables live strategy
- [ ] user disables live strategy
- [ ] user invokes emergency stop
- [ ] user submits live order manually
- [ ] user cancels live order
- [ ] user inspects live order detail
- [ ] user inspects live balances/positions

## Data Dependencies
- `/api/v1/live/accounts`
- `/api/v1/live/strategies/start`
- `/api/v1/live/strategies/stop`
- `/api/v1/live/emergency-stop`
- `/api/v1/live/orders`
- `/api/v1/live/orders/{order_id}`
- `/api/v1/live/orders/{order_id}/cancel`
- `/api/v1/live/orders/{order_id}/events`
- `/api/v1/live/orders/{order_id}/fills`
- `/api/v1/live/positions`
- `/api/v1/live/balances`
- `/api/v1/live/funding-pnl`
- `/api/v1/live/ledger`
- `/api/v1/live/latency-metrics`

## Acceptance Checks
- [ ] Live Trading Console shows connected account status
- [ ] Manual Order Ticket validates inputs and submits order
- [ ] Live Orders Explorer shows recent orders
- [ ] Live Order Detail shows event and fill history
- [ ] Live Account State shows balances, positions, funding, and ledger summaries

## Handoff Criteria to Phase 8 UI
- [ ] live trading operations are inspectable enough to support reconciliation and ops workflows
- [ ] emergency and exception controls are visible in UI

---

# Phase 8 UI Checklist: Reconciliation, Treasury, and Operational Controls

## Goal
Allow the user to inspect mismatches, treasury records, deployment history, and exchange exception events.

## Required Pages

### Page 8.1: Reconciliation Dashboard
Required sections:
- [ ] mismatch summary cards
- [ ] mismatches table
- [ ] mismatch type filter
- [ ] severity filter
- [ ] mismatch detail drawer/page
- [ ] review action

### Page 8.2: Treasury Explorer
Required sections:
- [ ] deposits/withdrawals table
- [ ] asset filter
- [ ] network filter
- [ ] status filter
- [ ] treasury event detail page

### Page 8.3: Deployment Audit
Required sections:
- [ ] deployments table
- [ ] deployment detail panel
- [ ] config changes table
- [ ] config diff / snapshot viewer

### Page 8.4: Exchange Status and Exception Events
Required sections:
- [ ] exchange status events table
- [ ] forced reduction events table
- [ ] event detail view

### Page 8.5: Operator Controls / Runbook Panel
Required sections:
- [ ] incident workflow summary
- [ ] manual stop guidance
- [ ] mismatch handling notes

## Required Components
- [ ] mismatch severity badges
- [ ] review/acknowledge action control
- [ ] treasury detail metadata panel
- [ ] config diff viewer or JSON compare block
- [ ] exception event table

## Required User Events
- [ ] user filters mismatches
- [ ] user marks mismatch reviewed
- [ ] user inspects treasury event detail
- [ ] user opens deployment detail
- [ ] user inspects config change snapshot/diff
- [ ] user inspects exchange status or forced reduction event

## Data Dependencies
- `/api/v1/reconciliation/summary`
- `/api/v1/reconciliation/mismatches`
- `/api/v1/reconciliation/mismatches/{mismatch_id}/review`
- `/api/v1/treasury/events`
- `/api/v1/treasury/events/{treasury_event_id}`
- `/api/v1/admin/deployments`
- `/api/v1/admin/deployments/{deployment_id}`
- `/api/v1/admin/config-changes`
- `/api/v1/risk/exchange-status-events`
- `/api/v1/risk/forced-reduction-events`

## Acceptance Checks
- [ ] Reconciliation Dashboard shows mismatch summaries and list
- [ ] user can mark a mismatch reviewed from UI
- [ ] Treasury Explorer shows tx/network metadata in detail view
- [ ] Deployment Audit shows rollout history and config changes
- [ ] Exchange Status and Exception Events page shows operational exception records

## Handoff Criteria to Phase 9 UI
- [ ] operational and audit workflows are visible enough to harden the system
- [ ] review workflows exist for mismatches and exceptional events

---

# Phase 9 UI Checklist: Production Hardening and Scale Improvements

## Goal
Allow the user to inspect reliability, alerts, CI status, and retention/scaling policy.

## Required Pages

### Page 9.1: Reliability Dashboard
Required sections:
- [ ] ingestion failure summary
- [ ] stale data summary
- [ ] websocket disconnect summary
- [ ] reconciliation mismatch summary
- [ ] uptime/health summary

### Page 9.2: Alerts Explorer
Required sections:
- [ ] active alerts table
- [ ] alert history table
- [ ] severity/status filters
- [ ] alert detail drawer/page

### Page 9.3: CI and Test Status
Required sections:
- [ ] latest test run summary
- [ ] lint/type-check summary
- [ ] recent CI workflow history

### Page 9.4: Retention and Storage Policy
Required sections:
- [ ] current retention policy summary
- [ ] archive policy summary
- [ ] high-volume tables summary
- [ ] future scaling notes panel

## Required Components
- [ ] reliability metric cards
- [ ] alerts table with status badges
- [ ] CI run summary cards
- [ ] storage/retention policy information panels

## Required User Events
- [ ] user inspects reliability summary
- [ ] user filters active alerts
- [ ] user opens alert detail
- [ ] user inspects CI/test health
- [ ] user reviews retention and scaling settings

## Data Dependencies
- `/api/v1/reliability/summary`
- `/api/v1/alerts`
- `/api/v1/ci/status`
- `/api/v1/storage/policies`
- `/api/v1/storage/high-volume-status`

## Acceptance Checks
- [ ] Reliability Dashboard shows core health metrics
- [ ] Alerts Explorer shows active and historical alerts
- [ ] CI and Test Status page shows latest validation results
- [ ] Retention and Storage Policy page shows current policy and scale notes

## Project-Level UI Completion Criteria
- [ ] user can inspect health, data, research, trading, reconciliation, and reliability from UI
- [ ] no critical operational workflow requires raw DB inspection as the default path
- [ ] each project phase has a corresponding usable UI surface and acceptance path

---

## Recommended UI Build Order

### Foundation UI
- [ ] Phase 0 pages
- [ ] Phase 1 pages

### Data UI
- [ ] Phase 2 pages
- [ ] Phase 3 pages
- [ ] Phase 4 pages

### Research and Trading UI
- [ ] Phase 5 pages
- [ ] Phase 6 pages
- [ ] Phase 7 pages

### Operations UI
- [ ] Phase 8 pages
- [ ] Phase 9 pages

---

## Final Summary

A UI phase should only be considered complete when:
- the required pages exist
- the required components exist
- the defined user events are operable
- the corresponding backend APIs are integrated
- the acceptance checks pass

This keeps the UI implementation aligned with the backend phases and ensures the product remains operable and verifiable throughout development.
