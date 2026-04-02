# UI API Spec

## Purpose

This document defines the backend API surfaces required for the frontend UI described in `docs/ui-spec.md`.

The goal is to map each project phase to:
- corresponding UI pages
- backend API endpoints required by those pages
- request and response contracts
- validation and acceptance rules

This spec is intentionally phase-aligned so that frontend and backend can evolve together.

---

## 1. API Design Principles

### 1.1 Scope
These APIs are intended for the internal operator / developer / researcher console.
They are not public APIs.

### 1.2 Protocol
Recommended default:
- HTTP JSON APIs for CRUD, queries, actions, and status pages
- WebSocket or server-sent events for streaming runtime status where needed

### 1.3 Naming Style
Recommended endpoint style:
- resource-oriented
- versioned under `/api/v1/`
- action endpoints only where workflow semantics require them

Examples:
- `GET /api/v1/system/health`
- `POST /api/v1/bootstrap/verify`
- `GET /api/v1/reference/instruments`
- `POST /api/v1/backtests/runs`

### 1.4 Standard Response Envelope
Recommended response shape:

```json
{
  "success": true,
  "data": {},
  "error": null,
  "meta": {
    "request_id": "req_123",
    "timestamp": "2026-04-02T12:00:00Z"
  }
}
```

Error example:

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "instrument_type is required",
    "details": {}
  },
  "meta": {
    "request_id": "req_124",
    "timestamp": "2026-04-02T12:00:01Z"
  }
}
```

### 1.5 Common Query Parameters
Where relevant, list/query endpoints should support:
- `limit`
- `offset`
- `sort_by`
- `sort_order`
- `start_time`
- `end_time`
- `exchange_code`
- `unified_symbol`
- `environment`
- `status`

### 1.6 Standard Action Semantics
For action endpoints:
- use `POST` for actions that create or trigger workflows
- return immediate acknowledgment and job/run id when execution is asynchronous
- return validation errors in structured form

### 1.7 Environment Awareness
All runtime-sensitive endpoints should either:
- embed the environment in the resource, or
- accept an `environment` field explicitly

---

## 2. Shared Types

## 2.1 Health Status
```json
{
  "status": "ok",
  "service": "postgres",
  "latency_ms": 8,
  "checked_at": "2026-04-02T12:00:00Z"
}
```

## 2.2 Pagination Meta
```json
{
  "limit": 50,
  "offset": 0,
  "returned": 50,
  "total": 1200
}
```

## 2.3 Status Badge Values
Recommended normalized values:
- `ok`
- `warning`
- `error`
- `running`
- `idle`
- `paused`
- `stopped`
- `disabled`

---

# 3. Phase-to-API Mapping

# Phase 0 API: Repository and Runtime Bootstrap

## UI Surfaces Supported
- System Overview Page
- Environment Config Page

## Required Endpoints

### GET `/api/v1/system/health`
Purpose:
- return service health for app, postgres, redis

Implementation note:
- minimal backend implementation now exists in `src/api/app.py`
- current implementation returns app health only; postgres/redis detail remains future work

Response:
```json
{
  "success": true,
  "data": {
    "app": {"status": "ok", "checked_at": "2026-04-02T12:00:00Z"},
    "postgres": {"status": "ok", "latency_ms": 8, "checked_at": "2026-04-02T12:00:00Z"},
    "redis": {"status": "ok", "latency_ms": 2, "checked_at": "2026-04-02T12:00:00Z"}
  },
  "error": null,
  "meta": {}
}
```

### GET `/api/v1/system/runtime`
Purpose:
- return app runtime metadata and environment info

Response fields:
- app_env
- version
- git_commit_sha
- started_at
- config_loaded

### GET `/api/v1/system/logs`
Purpose:
- return recent startup or runtime logs

Query params:
- `limit`
- `level`
- `service_name`

## Phase 0 Acceptance via UI/API
- [ ] UI can call `/system/health` successfully
- [ ] UI can display DB and Redis health
- [ ] UI can display runtime metadata

---

# Phase 1 API: Database Bootstrap and Seed Data

## UI Surfaces Supported
- Database Bootstrap Page
- Exchanges Page
- Assets Page
- Instruments Page
- Fee Schedule Page

## Required Endpoints

### GET `/api/v1/bootstrap/status`
Purpose:
- show current bootstrap state and latest verification summary

Response fields:
- migration_files
- bootstrap_completed
- latest_bootstrap_time
- latest_verification_time
- verification_status

### POST `/api/v1/bootstrap/verify`
Purpose:
- trigger Phase 1 bootstrap verification

Request:
```json
{
  "run_duplicate_checks": true
}
```

Response:
```json
{
  "success": true,
  "data": {
    "verification_run_id": "verify_001",
    "status": "running"
  },
  "error": null,
  "meta": {}
}
```

### GET `/api/v1/bootstrap/verification-runs/{verification_run_id}`
Purpose:
- fetch verification result details

Response fields:
- schemas_ok
- exchanges_ok
- assets_ok
- instruments_ok
- fee_schedules_ok
- duplicate_checks_ok
- failures[]

### GET `/api/v1/reference/exchanges`
Purpose:
- list exchanges

### GET `/api/v1/reference/assets`
Purpose:
- list assets

### GET `/api/v1/reference/instruments`
Purpose:
- list instruments

Query params:
- `exchange_code`
- `instrument_type`
- `status`
- `limit`
- `offset`

### GET `/api/v1/reference/instruments/{instrument_id}`
Purpose:
- instrument detail view

### GET `/api/v1/reference/fee-schedules`
Purpose:
- list fee schedules

Query params:
- `exchange_code`
- `instrument_type`

## Phase 1 Acceptance via UI/API
- [ ] UI can display seeded exchanges
- [ ] UI can display seeded assets
- [ ] UI can filter spot vs perp instruments
- [ ] UI can run verification and display pass/fail

---

# Phase 2 API: Domain Models and Storage Layer

## UI Surfaces Supported
- Model Validation Playground
- Repository Explorer
- DB Write Test Page

## Required Endpoints

### GET `/api/v1/models/payload-types`
Purpose:
- list supported canonical payload types for validation playground

Implementation note:
- implemented in `src/api/app.py`
- canonical response resource defined in `docs/api-resource-contracts.md`

Response example:
```json
{
  "success": true,
  "data": {
    "payload_types": [
      "instrument_metadata",
      "bar_event",
      "trade_event",
      "funding_rate",
      "open_interest",
      "orderbook_snapshot",
      "orderbook_delta",
      "mark_price",
      "index_price",
      "raw_market_event",
      "order_request",
      "fill",
      "account_ledger_event",
      "funding_pnl_event",
      "risk_limit",
      "risk_event",
      "position_snapshot",
      "balance_snapshot"
    ]
  },
  "error": null,
  "meta": {}
}
```

### POST `/api/v1/models/validate`
Purpose:
- validate arbitrary payload against canonical model

Implementation note:
- implemented in `src/api/app.py`
- canonical response resource defined in `docs/api-resource-contracts.md`

Request:
```json
{
  "payload_type": "trade_event",
  "payload": {
    "exchange_code": "binance",
    "unified_symbol": "BTCUSDT_PERP",
    "exchange_trade_id": "123",
    "event_time": "2026-04-02T12:34:56Z",
    "ingest_time": "2026-04-02T12:34:57Z",
    "price": "84250.12",
    "qty": "0.01"
  }
}
```

Response fields:
- valid
- normalized_payload
- validation_errors

### POST `/api/v1/models/validate-and-store`
Purpose:
- validate payload then persist using repository layer

Implementation note:
- implemented in `src/api/app.py` using `src/services/validate_and_store.py`
- canonical response resource defined in `docs/api-resource-contracts.md`

Request:
```json
{
  "payload_type": "trade_event",
  "payload": {}
}
```

Response fields:
- valid
- stored
- entity_type
- record_locator
- duplicate_handled

### GET `/api/v1/storage/{entity_type}`
Purpose:
- generic repository explorer endpoint for supported entities

Supported entity types may include:
- instruments
- bars
- trades
- funding_rates
- orders
- fills
- positions
- balances

### GET `/api/v1/storage/{entity_type}/{id}`
Purpose:
- record detail view

## Phase 2 Acceptance via UI/API
- [ ] UI can fetch payload types
- [ ] UI can validate sample payloads
- [ ] UI can store sample payloads through API
- [ ] UI can inspect stored rows

Backend status note:
- backend implementations now exist for `/api/v1/models/payload-types`, `/api/v1/models/validate`, `/api/v1/models/validate-and-store`
- the current implemented payload-types list now covers the full planned Phase 2 storable market, execution, and risk slice
- current implemented response resources are defined in `docs/api-resource-contracts.md`
- generic `/api/v1/storage/*` explorer endpoints are still pending

---

# Phase 3 API: Public Market Data Ingestion

## UI Surfaces Supported
- Ingestion Jobs Dashboard
- Instrument Sync Page
- Market Data Explorer
- Websocket Stream Monitor

## Required Endpoints

### GET `/api/v1/ingestion/jobs`
Purpose:
- list ingestion jobs

Query params:
- `status`
- `data_type`
- `exchange_code`
- `instrument_id`
- `limit`
- `offset`

### POST `/api/v1/ingestion/jobs/instrument-sync`
Purpose:
- trigger instrument metadata sync

Request:
```json
{
  "exchange_code": "binance"
}
```

Response fields:
- ingestion_job_id
- status

### POST `/api/v1/ingestion/jobs/bar-backfill`
Purpose:
- trigger bar backfill

Request:
```json
{
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "interval": "1m",
  "start_time": "2026-03-01T00:00:00Z",
  "end_time": "2026-03-02T00:00:00Z"
}
```

### GET `/api/v1/market/bars`
Purpose:
- query bars

### GET `/api/v1/market/trades`
Purpose:
- query trades

### GET `/api/v1/market/funding-rates`
Purpose:
- query funding rates

### GET `/api/v1/market/open-interest`
Purpose:
- query open interest

### GET `/api/v1/market/mark-prices`
Purpose:
- query mark prices

### GET `/api/v1/market/index-prices`
Purpose:
- query index prices

### GET `/api/v1/market/liquidations`
Purpose:
- query liquidation events

### GET `/api/v1/streams/ws-status`
Purpose:
- websocket stream health summary

Response fields:
- exchange_code
- channel
- connection_status
- last_message_time
- message_rate

### GET `/api/v1/streams/ws-events`
Purpose:
- list recent websocket connection events

## Phase 3 Acceptance via UI/API
- [ ] UI can trigger instrument sync
- [ ] UI can trigger bar backfill
- [ ] UI can query newly ingested market data
- [ ] UI can inspect websocket health and connection events

---

# Phase 4 API: Market Data Quality and Replay Readiness

## UI Surfaces Supported
- Data Quality Dashboard
- Data Gaps Page
- Raw Event Explorer
- Replay Readiness Page

## Required Endpoints

### GET `/api/v1/quality/checks`
Purpose:
- list data quality checks

Query params:
- `data_type`
- `status`
- `severity`
- `exchange_code`
- `unified_symbol`

### GET `/api/v1/quality/summary`
Purpose:
- return aggregated pass/fail counts for dashboard cards

### GET `/api/v1/quality/gaps`
Purpose:
- list data gaps

### GET `/api/v1/market/raw-events`
Purpose:
- browse raw market events

Query params:
- `exchange_code`
- `channel`
- `event_type`
- `start_time`
- `end_time`

### GET `/api/v1/market/raw-events/{raw_event_id}`
Purpose:
- raw payload detail view

### GET `/api/v1/market/raw-events/{raw_event_id}/normalized-links`
Purpose:
- show linked normalized records where available

### GET `/api/v1/replay/readiness`
Purpose:
- return replay coverage / readiness status

Response fields:
- raw_coverage_status
- normalized_coverage_status
- retained_streams
- known_gaps

## Phase 4 Acceptance via UI/API
- [ ] UI can show aggregated quality results
- [ ] UI can show open data gaps
- [ ] UI can inspect raw events and payloads
- [ ] UI can show replay readiness summary

---

# Phase 5 API: Strategy Runner and Bars-Based Backtest

## UI Surfaces Supported
- Strategy Registry Page
- Backtest Run Builder
- Backtest Runs Page
- Backtest Run Detail Page

## Required Endpoints

### GET `/api/v1/strategies`
Purpose:
- list strategies

### GET `/api/v1/strategies/{strategy_id}`
Purpose:
- strategy detail

### GET `/api/v1/strategy-versions`
Purpose:
- list strategy versions

Query params:
- `strategy_code`
- `is_active`

### POST `/api/v1/backtests/runs`
Purpose:
- create and start a backtest run

Request:
```json
{
  "strategy_code": "btc_momentum",
  "strategy_version": "v1.0.0",
  "exchange_code": "binance",
  "universe": ["BTCUSDT_PERP"],
  "start_time": "2026-01-01T00:00:00Z",
  "end_time": "2026-02-01T00:00:00Z",
  "fee_model_version": "default",
  "slippage_model_version": "default",
  "params_override": {}
}
```

Response fields:
- run_id
- status

### GET `/api/v1/backtests/runs`
Purpose:
- list backtest runs

### GET `/api/v1/backtests/runs/{run_id}`
Purpose:
- run metadata and summary

### GET `/api/v1/backtests/runs/{run_id}/orders`
Purpose:
- list simulated orders

### GET `/api/v1/backtests/runs/{run_id}/fills`
Purpose:
- list simulated fills

### GET `/api/v1/backtests/runs/{run_id}/timeseries`
Purpose:
- equity / exposure series

### GET `/api/v1/backtests/runs/{run_id}/signals`
Purpose:
- optional signal inspection for a run

## Phase 5 Acceptance via UI/API
- [ ] UI can launch backtest from form
- [ ] UI can show run list and run detail
- [ ] UI can inspect simulated orders/fills/timeseries

---

# Phase 6 API: Paper Trading Engine

## UI Surfaces Supported
- Paper Trading Console
- Paper Orders Page
- Paper Order Detail Page
- Paper Risk Panel

## Required Endpoints

### POST `/api/v1/paper/sessions`
Purpose:
- start paper trading session

Request:
```json
{
  "account_code": "paper_main",
  "strategy_code": "btc_momentum",
  "strategy_version": "v1.0.0",
  "exchange_code": "binance",
  "universe": ["BTCUSDT_PERP"]
}
```

Response fields:
- session_id
- status

### POST `/api/v1/paper/sessions/{session_id}/stop`
Purpose:
- stop paper session

### POST `/api/v1/paper/sessions/{session_id}/pause`
Purpose:
- pause paper session

### POST `/api/v1/paper/sessions/{session_id}/resume`
Purpose:
- resume paper session

### GET `/api/v1/paper/sessions`
Purpose:
- list paper sessions

### GET `/api/v1/paper/sessions/{session_id}`
Purpose:
- session summary

### GET `/api/v1/paper/orders`
Purpose:
- list paper orders

Query params:
- `session_id`
- `status`
- `unified_symbol`

### GET `/api/v1/paper/orders/{order_id}`
Purpose:
- paper order detail

### GET `/api/v1/paper/orders/{order_id}/events`
Purpose:
- order event timeline

### GET `/api/v1/paper/orders/{order_id}/fills`
Purpose:
- linked fills

### GET `/api/v1/paper/positions`
Purpose:
- current paper positions

### GET `/api/v1/paper/balances`
Purpose:
- current paper balances

### GET `/api/v1/paper/risk-events`
Purpose:
- list paper risk events

### GET `/api/v1/paper/latency-metrics`
Purpose:
- list paper execution timing metrics

## Phase 6 Acceptance via UI/API
- [ ] UI can start/stop/pause/resume paper sessions
- [ ] UI can inspect paper orders and order timelines
- [ ] UI can inspect paper positions and balances
- [ ] UI can inspect paper risk events

---

# Phase 7 API: Private Exchange Adapter and Live Trading MVP

## UI Surfaces Supported
- Live Trading Console
- Manual Order Ticket
- Live Order Detail Page
- Live Account State Page

## Required Endpoints

### GET `/api/v1/live/accounts`
Purpose:
- list configured live accounts and connection status

### POST `/api/v1/live/strategies/start`
Purpose:
- enable live strategy runtime

### POST `/api/v1/live/strategies/stop`
Purpose:
- disable live strategy runtime

### POST `/api/v1/live/emergency-stop`
Purpose:
- emergency stop live trading activity

Request:
```json
{
  "account_code": "binance_live_01",
  "reason": "manual emergency stop"
}
```

### POST `/api/v1/live/orders`
Purpose:
- submit live order from Manual Order Ticket

Request:
```json
{
  "account_code": "binance_live_01",
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "side": "buy",
  "order_type": "limit",
  "time_in_force": "gtc",
  "price": "84240.00",
  "qty": "0.01"
}
```

### POST `/api/v1/live/orders/{order_id}/cancel`
Purpose:
- cancel live order

### GET `/api/v1/live/orders`
Purpose:
- list live orders

### GET `/api/v1/live/orders/{order_id}`
Purpose:
- live order detail

### GET `/api/v1/live/orders/{order_id}/events`
Purpose:
- live order event timeline

### GET `/api/v1/live/orders/{order_id}/fills`
Purpose:
- live order fills

### GET `/api/v1/live/positions`
Purpose:
- live positions

### GET `/api/v1/live/balances`
Purpose:
- live balances

### GET `/api/v1/live/funding-pnl`
Purpose:
- live funding history

### GET `/api/v1/live/ledger`
Purpose:
- live ledger history

### GET `/api/v1/live/latency-metrics`
Purpose:
- live execution timing metrics

## Phase 7 Acceptance via UI/API
- [ ] UI can show live account status
- [ ] UI can place and cancel live order
- [ ] UI can inspect order state/fills
- [ ] UI can inspect positions, balances, funding, and ledger data

---

# Phase 8 API: Reconciliation, Treasury, and Operational Controls

## UI Surfaces Supported
- Reconciliation Dashboard
- Treasury Page
- Deployment Audit Page
- Exchange Status / Exception Events Page

## Required Endpoints

### GET `/api/v1/reconciliation/summary`
Purpose:
- aggregated mismatch counts for dashboard

### GET `/api/v1/reconciliation/mismatches`
Purpose:
- list mismatches

Query params:
- `mismatch_type`
- `severity`
- `status`
- `account_code`

### POST `/api/v1/reconciliation/mismatches/{mismatch_id}/review`
Purpose:
- mark mismatch reviewed

### GET `/api/v1/treasury/events`
Purpose:
- list deposits and withdrawals

Query params:
- `asset`
- `network`
- `status`
- `event_type`

### GET `/api/v1/treasury/events/{treasury_event_id}`
Purpose:
- treasury event detail

### GET `/api/v1/admin/deployments`
Purpose:
- list strategy deployments

### GET `/api/v1/admin/deployments/{deployment_id}`
Purpose:
- deployment detail

### GET `/api/v1/admin/config-changes`
Purpose:
- list config changes

### GET `/api/v1/risk/exchange-status-events`
Purpose:
- list exchange pauses, maintenance, resumes, delist notices

### GET `/api/v1/risk/forced-reduction-events`
Purpose:
- list forced reductions / ADL-like events

## Phase 8 Acceptance via UI/API
- [ ] UI can show reconciliation summary and mismatch list
- [ ] UI can show treasury event history
- [ ] UI can show deployment and config audit history
- [ ] UI can show exchange status and forced reduction events

---

# Phase 9 API: Production Hardening and Scale Improvements

## UI Surfaces Supported
- Reliability Dashboard
- Alerts Page
- Test and CI Status Page
- Retention / Storage Policy Page

## Required Endpoints

### GET `/api/v1/reliability/summary`
Purpose:
- aggregated operational health metrics

Response fields may include:
- ingestion_failure_rate
- stale_data_alert_count
- open_reconciliation_mismatches
- ws_disconnect_count
- app_uptime

### GET `/api/v1/alerts`
Purpose:
- list active and historical alerts

Query params:
- `severity`
- `status`
- `alert_type`

### GET `/api/v1/ci/status`
Purpose:
- show latest test/lint/type-check/CI results

### GET `/api/v1/storage/policies`
Purpose:
- show retention policy and archive/scaling settings

### GET `/api/v1/storage/high-volume-status`
Purpose:
- summarize heavy tables and storage pressure signals

## Phase 9 Acceptance via UI/API
- [ ] UI can show reliability summary
- [ ] UI can list alerts
- [ ] UI can show CI status
- [ ] UI can show retention and storage policy state

---

## 4. Cross-Phase API Requirements

These requirements apply to all phases.

### 4.1 Authentication
Internal UI APIs should require authenticated access.
Recommended future modes:
- local developer auth bypass in dev
- session or token auth in shared environments

Current implementation status:
- `GET /api/v1/system/health` is public
- current `/api/v1/models/*` endpoints use the minimal auth contract
- in `APP_ENV=local` with `ENABLE_LOCAL_AUTH_BYPASS=true`, protected routes may use local bypass
- in non-local environments, protected routes expect `Authorization: Bearer <token>`

### 4.2 Authorization
Recommended future role scopes:
- developer
- researcher
- operator
- admin

Example policy:
- only admins/operators can invoke destructive or live-trading actions
- researchers can run backtests but not place live orders

### 4.3 Auditability
All action endpoints should generate auditable records where relevant.
Examples:
- bootstrap verification run
- backfill trigger
- backtest run create
- paper session start/stop
- live order place/cancel
- emergency stop
- mismatch review

### 4.4 Async Workflow Pattern
For long-running workflows, use:
- `POST` to trigger
- return job/run/session id immediately
- `GET` status endpoint to poll progress

### 4.5 Time-Series Query Pattern
For bar/trade/event/time-series endpoints, support:
- `start_time`
- `end_time`
- `limit`
- stable ordering

### 4.6 Structured Detail Links
List endpoints should return IDs and enough metadata for detail drill-down.

---

## 5. Recommended API Build Order

Build APIs in this order:

### API Track A: Foundation APIs
1. `/system/*`
2. `/bootstrap/*`
3. `/reference/*`

### API Track B: Data APIs
4. `/models/*`
5. `/storage/*`
6. `/ingestion/*`
7. `/market/*`
8. `/quality/*`

### API Track C: Research APIs
9. `/strategies/*`
10. `/backtests/*`

### API Track D: Trading APIs
11. `/paper/*`
12. `/live/*`
13. `/risk/*`
14. `/treasury/*`
15. `/reconciliation/*`
16. `/admin/*`

### API Track E: Reliability APIs
17. `/reliability/*`
18. `/alerts/*`
19. `/ci/*`
20. `/storage/policies`

---

## 6. Final Summary

This spec makes the UI plan implementable by defining the backend API contract phase by phase.

That means each phase now has three aligned layers:
1. backend implementation phase
2. corresponding UI surfaces
3. corresponding UI-to-server API endpoints

A phase should only be considered fully usable when all three are present.
