# UI Information Architecture

## Purpose

This document translates the UI roadmap into a frontend-ready information architecture.

It defines:
- page hierarchy
- route structure
- navigation model
- page ownership boundaries
- shared component ownership
- data-domain alignment with backend APIs
- phase-by-phase rollout mapping

This document is intended to make frontend implementation directly actionable.

It should be used together with:
- `docs/ui-spec.md`
- `docs/ui-phase-checklists.md`
- `docs/ui-api-spec.md`
- `docs/implementation-plan.md`

---

## 1. IA Design Principles

### 1.1 One Product, Multiple Work Modes
The product should behave like one internal console with different operating modes:
- system setup
- data operations
- research
- paper trading
- live trading
- operational control

### 1.2 Route Stability
Routes should remain stable as features expand.
Early-phase pages should keep the same route paths later, even if content becomes richer.

### 1.3 Domain-Oriented Navigation
Navigation should reflect user tasks and backend domains, not raw table names.
For example:
- use `Market Data` instead of `md.*`
- use `Reference Data` instead of `ref.*`
- use `Backtests` instead of `backtest.*`

### 1.4 Progressive Expansion
The IA should support phased rollout.
Early phases expose only the routes needed at that stage.
Later phases extend the tree without breaking earlier paths.

### 1.5 Inspectability First
The page hierarchy should prioritize inspection and verification over cosmetic UX.
Every major operational domain should have:
- list / dashboard page
- detail page or detail drawer
- actionable controls where applicable

---

## 2. Top-Level Navigation Structure

The final information architecture should expose these top-level navigation groups:

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
13. **Admin**

### Recommended left-nav grouping

```text
Home
System
  Overview
  Environment
  Database Bootstrap

Reference Data
  Exchanges
  Assets
  Instruments
  Fee Schedules

Market Data
  Explorer
  Ingestion Jobs
  Instrument Sync
  Bar Backfill
  WebSocket Monitor
  Raw Events

Quality & Ops
  Data Quality
  Data Gaps
  Replay Readiness
  System Logs

Strategies
  Registry
  Versions

Backtests
  Run Builder
  Runs
  Run Detail

Paper Trading
  Sessions
  Console
  Orders
  Positions
  Balances
  Risk Events

Live Trading
  Accounts
  Console
  Manual Order Ticket
  Orders
  Positions
  Balances
  Funding
  Ledger

Risk
  Limits
  Events
  Exchange Status
  Forced Reduction Events

Treasury
  Deposits & Withdrawals

Reconciliation
  Dashboard
  Mismatches

Admin
  Deployments
  Config Changes
  Alerts
  Reliability
  CI Status
  Storage Policies
```

---

## 3. Route Map

## 3.1 Global Routes

| Route | Page | Purpose |
|---|---|---|
| `/` | Home | landing dashboard |
| `/system` | System Overview | runtime health and startup state |
| `/system/environment` | Environment Config | runtime config and metadata |
| `/system/bootstrap` | Database Bootstrap | bootstrap and Phase 1 verification |

---

## 3.2 Reference Data Routes

| Route | Page | Purpose |
|---|---|---|
| `/reference/exchanges` | Exchanges Explorer | view supported exchanges |
| `/reference/assets` | Assets Explorer | view canonical assets |
| `/reference/instruments` | Instruments Explorer | browse and filter instruments |
| `/reference/instruments/:instrumentId` | Instrument Detail | inspect instrument mappings and rules |
| `/reference/fee-schedules` | Fee Schedule Explorer | inspect fee assumptions |

---

## 3.3 Market Data Routes

| Route | Page | Purpose |
|---|---|---|
| `/market/explorer` | Market Data Explorer | query bars, trades, funding, OI, mark/index, liquidations |
| `/market/ingestion-jobs` | Ingestion Jobs Dashboard | inspect and trigger ingestion workflows |
| `/market/instrument-sync` | Instrument Sync | run and inspect metadata sync |
| `/market/bar-backfill` | Bar Backfill Runner | launch historical bar ingestion |
| `/market/ws-monitor` | WebSocket Monitor | inspect stream health |
| `/market/raw-events` | Raw Event Explorer | inspect raw market payloads |
| `/market/raw-events/:rawEventId` | Raw Event Detail | inspect raw payload and linked normalized data |

---

## 3.4 Quality & Ops Routes

| Route | Page | Purpose |
|---|---|---|
| `/quality/dashboard` | Data Quality Dashboard | summarize checks and anomalies |
| `/quality/gaps` | Data Gaps Explorer | inspect missing windows |
| `/quality/replay-readiness` | Replay Readiness | inspect replay coverage |
| `/ops/logs` | System Logs | inspect app/system logs |

---

## 3.5 Strategy Routes

| Route | Page | Purpose |
|---|---|---|
| `/strategies` | Strategy Registry | list strategies |
| `/strategies/:strategyId` | Strategy Detail | inspect strategy metadata |
| `/strategy-versions` | Strategy Versions | inspect strategy version records |
| `/strategy-versions/:strategyVersionId` | Strategy Version Detail | inspect params and version metadata |

---

## 3.6 Backtest Routes

| Route | Page | Purpose |
|---|---|---|
| `/backtests/builder` | Backtest Run Builder | configure and launch backtests |
| `/backtests/runs` | Backtest Runs | list backtest runs |
| `/backtests/runs/:runId` | Backtest Run Detail | inspect metadata, KPIs, equity curve |
| `/backtests/runs/:runId/orders` | Backtest Orders | inspect simulated orders |
| `/backtests/runs/:runId/fills` | Backtest Fills | inspect simulated fills |
| `/backtests/runs/:runId/signals` | Backtest Signals | inspect optional signal output |

---

## 3.7 Paper Trading Routes

| Route | Page | Purpose |
|---|---|---|
| `/paper/sessions` | Paper Sessions | list paper sessions |
| `/paper/sessions/:sessionId` | Paper Trading Console | monitor running paper session |
| `/paper/orders` | Paper Orders Explorer | inspect paper orders |
| `/paper/orders/:orderId` | Paper Order Detail | inspect order timeline and fills |
| `/paper/positions` | Paper Positions | inspect paper positions |
| `/paper/balances` | Paper Balances | inspect paper balances |
| `/paper/risk-events` | Paper Risk Events | inspect paper risk incidents |
| `/paper/latency` | Paper Latency Metrics | inspect paper timing data |

---

## 3.8 Live Trading Routes

| Route | Page | Purpose |
|---|---|---|
| `/live/accounts` | Live Accounts | inspect account connectivity |
| `/live/console` | Live Trading Console | inspect live trading runtime |
| `/live/order-ticket` | Manual Order Ticket | submit and cancel live orders |
| `/live/orders` | Live Orders Explorer | inspect live orders |
| `/live/orders/:orderId` | Live Order Detail | inspect live order lifecycle |
| `/live/positions` | Live Positions | inspect live positions |
| `/live/balances` | Live Balances | inspect live balances |
| `/live/funding` | Live Funding PnL | inspect funding history |
| `/live/ledger` | Live Ledger | inspect account ledger history |
| `/live/latency` | Live Latency Metrics | inspect live order timing |

---

## 3.9 Risk Routes

| Route | Page | Purpose |
|---|---|---|
| `/risk/limits` | Risk Limits | inspect configured limits |
| `/risk/events` | Risk Events | inspect risk incidents |
| `/risk/exchange-status` | Exchange Status Events | inspect pauses/maintenance/delist events |
| `/risk/forced-reductions` | Forced Reduction Events | inspect ADL-like or forced reduction events |

---

## 3.10 Treasury Routes

| Route | Page | Purpose |
|---|---|---|
| `/treasury/events` | Treasury Explorer | inspect deposits and withdrawals |
| `/treasury/events/:treasuryEventId` | Treasury Event Detail | inspect transaction metadata |

---

## 3.11 Reconciliation Routes

| Route | Page | Purpose |
|---|---|---|
| `/reconciliation` | Reconciliation Dashboard | mismatch summary |
| `/reconciliation/mismatches` | Mismatch Explorer | list and filter mismatches |
| `/reconciliation/mismatches/:mismatchId` | Mismatch Detail | inspect one mismatch |

---

## 3.12 Admin Routes

| Route | Page | Purpose |
|---|---|---|
| `/admin/deployments` | Deployment Audit | inspect strategy deployments |
| `/admin/deployments/:deploymentId` | Deployment Detail | inspect rollout/config snapshot |
| `/admin/config-changes` | Config Changes | inspect historical changes |
| `/admin/alerts` | Alerts Explorer | inspect active/historical alerts |
| `/admin/reliability` | Reliability Dashboard | inspect health metrics |
| `/admin/ci-status` | CI Status | inspect validation pipeline health |
| `/admin/storage-policies` | Storage Policies | inspect retention and scale plans |

---

## 4. Page Hierarchy

### 4.1 Hierarchy Tree

```text
/
├── /system
│   ├── /system/environment
│   └── /system/bootstrap
├── /reference
│   ├── /reference/exchanges
│   ├── /reference/assets
│   ├── /reference/instruments
│   │   └── /reference/instruments/:instrumentId
│   └── /reference/fee-schedules
├── /market
│   ├── /market/explorer
│   ├── /market/ingestion-jobs
│   ├── /market/instrument-sync
│   ├── /market/bar-backfill
│   ├── /market/ws-monitor
│   ├── /market/raw-events
│   │   └── /market/raw-events/:rawEventId
├── /quality
│   ├── /quality/dashboard
│   ├── /quality/gaps
│   └── /quality/replay-readiness
├── /ops
│   └── /ops/logs
├── /strategies
│   └── /strategies/:strategyId
├── /strategy-versions
│   └── /strategy-versions/:strategyVersionId
├── /backtests
│   ├── /backtests/builder
│   ├── /backtests/runs
│   │   └── /backtests/runs/:runId
│   │       ├── /backtests/runs/:runId/orders
│   │       ├── /backtests/runs/:runId/fills
│   │       └── /backtests/runs/:runId/signals
├── /paper
│   ├── /paper/sessions
│   │   └── /paper/sessions/:sessionId
│   ├── /paper/orders
│   │   └── /paper/orders/:orderId
│   ├── /paper/positions
│   ├── /paper/balances
│   ├── /paper/risk-events
│   └── /paper/latency
├── /live
│   ├── /live/accounts
│   ├── /live/console
│   ├── /live/order-ticket
│   ├── /live/orders
│   │   └── /live/orders/:orderId
│   ├── /live/positions
│   ├── /live/balances
│   ├── /live/funding
│   ├── /live/ledger
│   └── /live/latency
├── /risk
│   ├── /risk/limits
│   ├── /risk/events
│   ├── /risk/exchange-status
│   └── /risk/forced-reductions
├── /treasury
│   └── /treasury/events
│       └── /treasury/events/:treasuryEventId
├── /reconciliation
│   └── /reconciliation/mismatches
│       └── /reconciliation/mismatches/:mismatchId
└── /admin
    ├── /admin/deployments
    │   └── /admin/deployments/:deploymentId
    ├── /admin/config-changes
    ├── /admin/alerts
    ├── /admin/reliability
    ├── /admin/ci-status
    └── /admin/storage-policies
```

---

## 5. Route-to-Phase Mapping

| Phase | Required Routes |
|---|---|
| Phase 0 | `/system`, `/system/environment` |
| Phase 1 | `/system/bootstrap`, `/reference/exchanges`, `/reference/assets`, `/reference/instruments`, `/reference/fee-schedules` |
| Phase 2 | add model validation and repository test surfaces, recommended under `/system` or `/ops` extension paths such as `/system/model-validation` and `/system/repository-explorer` |
| Phase 3 | `/market/ingestion-jobs`, `/market/instrument-sync`, `/market/bar-backfill`, `/market/explorer`, `/market/ws-monitor` |
| Phase 4 | `/quality/dashboard`, `/quality/gaps`, `/market/raw-events`, `/quality/replay-readiness` |
| Phase 5 | `/strategies`, `/strategy-versions`, `/backtests/builder`, `/backtests/runs`, `/backtests/runs/:runId` |
| Phase 6 | `/paper/sessions`, `/paper/sessions/:sessionId`, `/paper/orders`, `/paper/orders/:orderId`, `/paper/positions`, `/paper/balances`, `/paper/risk-events` |
| Phase 7 | `/live/accounts`, `/live/console`, `/live/order-ticket`, `/live/orders`, `/live/orders/:orderId`, `/live/positions`, `/live/balances`, `/live/funding`, `/live/ledger` |
| Phase 8 | `/reconciliation`, `/reconciliation/mismatches`, `/treasury/events`, `/admin/deployments`, `/admin/config-changes`, `/risk/exchange-status`, `/risk/forced-reductions` |
| Phase 9 | `/admin/reliability`, `/admin/alerts`, `/admin/ci-status`, `/admin/storage-policies` |

---

## 6. Page Ownership Model

To make frontend implementation scalable, ownership should be split by domain.

## 6.1 Layout and Platform Ownership
Owned by: **Frontend Platform / Shell layer**

Responsible for:
- app layout
- sidebar navigation
- header/environment badge
- route guards
- global loading/error states
- toast/notification system
- modal framework
- shared table primitives
- shared detail drawer
- shared JSON viewer

Suggested directories:
```text
frontend/src/app/
frontend/src/layout/
frontend/src/components/shared/
frontend/src/components/primitives/
```

## 6.2 System Domain Ownership
Owned by: **System / Admin frontend domain**

Responsible for:
- System Overview
- Environment Config
- Database Bootstrap
- model validation playground
- repository explorer

Suggested directories:
```text
frontend/src/features/system/
frontend/src/features/bootstrap/
frontend/src/features/model-validation/
```

## 6.3 Reference Data Domain Ownership
Owned by: **Reference Data frontend domain**

Responsible for:
- Exchanges Explorer
- Assets Explorer
- Instruments Explorer
- Fee Schedule Explorer

Suggested directories:
```text
frontend/src/features/reference-data/
```

## 6.4 Market Data Domain Ownership
Owned by: **Market Data frontend domain**

Responsible for:
- Market Data Explorer
- Ingestion Jobs
- Instrument Sync
- Bar Backfill
- WebSocket Monitor
- Raw Event Explorer

Suggested directories:
```text
frontend/src/features/market-data/
frontend/src/features/ingestion/
```

## 6.5 Quality & Ops Domain Ownership
Owned by: **Quality/Ops frontend domain**

Responsible for:
- Data Quality Dashboard
- Data Gaps Explorer
- Replay Readiness
- System Logs

Suggested directories:
```text
frontend/src/features/quality/
frontend/src/features/ops/
```

## 6.6 Research Domain Ownership
Owned by: **Research frontend domain**

Responsible for:
- Strategy Registry
- Strategy Versions
- Backtest Builder
- Backtest Runs
- Backtest Run Detail

Suggested directories:
```text
frontend/src/features/strategies/
frontend/src/features/backtests/
```

## 6.7 Trading Domain Ownership
Owned by: **Execution frontend domain**

Responsible for:
- Paper Trading pages
- Live Trading pages
- Manual Order Ticket
- position/balance/order/fill visualizations

Suggested directories:
```text
frontend/src/features/paper-trading/
frontend/src/features/live-trading/
frontend/src/features/execution-shared/
```

## 6.8 Risk / Treasury / Reconciliation Domain Ownership
Owned by: **Operations frontend domain**

Responsible for:
- Risk pages
- Treasury pages
- Reconciliation pages
- Deployment Audit
- Alerts and reliability

Suggested directories:
```text
frontend/src/features/risk/
frontend/src/features/treasury/
frontend/src/features/reconciliation/
frontend/src/features/admin/
```

---

## 7. Component Ownership Model

## 7.1 Shared Components
Owned by: **Platform / shared UI team or shared layer**

Examples:
- `AppShell`
- `SidebarNav`
- `TopHeader`
- `EnvironmentBadge`
- `PageHeader`
- `StatusBadge`
- `DataTable`
- `FilterBar`
- `DetailDrawer`
- `JsonViewer`
- `ConfirmationModal`
- `EmptyState`
- `ErrorState`
- `LoadingState`
- `SummaryCard`
- `KeyValuePanel`
- `Timeline`

## 7.2 Domain Components
Owned by the corresponding feature domain.

Examples:
- `BootstrapVerificationPanel`
- `InstrumentRulesPanel`
- `BackfillRunForm`
- `WsConnectionStatusPanel`
- `BacktestRunSummary`
- `PaperSessionControls`
- `LiveOrderTicketForm`
- `ReconciliationMismatchTable`
- `TreasuryEventDetailPanel`
- `DeploymentDiffViewer`

## 7.3 Data Visualization Components
Ownership depends on reuse level.

Shared if generic:
- line chart wrapper
- time-series chart wrapper
- PnL summary cards

Domain-owned if highly contextual:
- equity curve panel
- ingestion freshness panel
- latency breakdown panel

---

## 8. Recommended Frontend Directory Structure

```text
frontend/
  src/
    app/
      routes/
      providers/
      store/
    layout/
      AppShell/
      SidebarNav/
      TopHeader/
    components/
      shared/
      primitives/
      charts/
    features/
      system/
      bootstrap/
      reference-data/
      market-data/
      ingestion/
      quality/
      ops/
      strategies/
      backtests/
      paper-trading/
      live-trading/
      risk/
      treasury/
      reconciliation/
      admin/
    services/
      api/
      query/
      websocket/
    types/
    utils/
```

---

## 9. Page Composition Pattern

Each feature page should follow a predictable structure.

### Recommended page composition

```text
Page
├── PageHeader
│   ├── title
│   ├── description
│   └── primary actions
├── SummarySection
│   └── summary cards / KPIs
├── FilterSection
│   └── filters / query controls
├── MainContent
│   ├── table / chart / timeline
│   └── supporting panels
└── DetailView
    └── drawer or nested page
```

### Why this matters
This consistency reduces implementation complexity and makes the console feel coherent even as domains expand.

---

## 10. Detail View Strategy

Use a mix of:
- nested route detail pages for major entities
- detail drawers for fast inspection from list pages

### Use full page detail when:
- entity has multiple subsections
- entity needs charts/tables/timelines
- user may bookmark/share the page

Examples:
- backtest run detail
- live order detail
- treasury event detail
- deployment detail

### Use detail drawer when:
- entity is mostly metadata
- fast compare/inspect is important

Examples:
- exchange detail
- asset detail
- simple instrument detail from explorer

---

## 11. Data Fetching Ownership

## 11.1 Page-level data fetching
Owned by page container.

Examples:
- list page fetches list and summary metrics
- detail page fetches entity detail and related tabs

## 11.2 Component-level data fetching
Allowed only when the component is reusable and clearly scoped.

Examples:
- `EnvironmentBadge` may fetch or receive app env from shared context
- `WsConnectionStatusPanel` may fetch/poll a dedicated endpoint

## 11.3 Query key conventions
Recommended key prefixes:
- `system.*`
- `bootstrap.*`
- `reference.*`
- `market.*`
- `quality.*`
- `strategy.*`
- `backtest.*`
- `paper.*`
- `live.*`
- `risk.*`
- `treasury.*`
- `reconciliation.*`
- `admin.*`

---

## 12. Phase-by-Phase IA Rollout

## Phase 0-1
Expose only:
- `/system`
- `/system/environment`
- `/system/bootstrap`
- `/reference/exchanges`
- `/reference/assets`
- `/reference/instruments`
- `/reference/fee-schedules`

## Phase 2-4
Add:
- `/system/model-validation`
- `/system/repository-explorer`
- `/market/*`
- `/quality/*`
- `/ops/logs`

## Phase 5-6
Add:
- `/strategies/*`
- `/strategy-versions/*`
- `/backtests/*`
- `/paper/*`

## Phase 7-9
Add:
- `/live/*`
- `/risk/*`
- `/treasury/*`
- `/reconciliation/*`
- `/admin/*`

---

## 13. Breadcrumb Strategy

Use breadcrumbs for nested routes.

Examples:
- `Reference Data / Instruments / BTCUSDT_PERP`
- `Backtests / Runs / Run 12345`
- `Live Trading / Orders / Order 1000001`
- `Treasury / Events / Event 889`

Breadcrumbs should be generated from route metadata where possible.

---

## 14. Route Metadata Model

Each route should carry metadata like:
- page title
- nav label
- breadcrumb label
- required role
- phase introduced
- feature domain owner

Example route metadata:

```json
{
  "path": "/live/orders/:orderId",
  "title": "Live Order Detail",
  "navLabel": "Orders",
  "breadcrumbLabel": "Order Detail",
  "requiredRole": "operator",
  "phaseIntroduced": 7,
  "featureOwner": "live-trading"
}
```

---

## 15. Access and Visibility Model

Recommended future visibility rules:

### Developer
Can access:
- system
- bootstrap
- model validation
- repository explorer
- market
- quality
- logs

### Researcher
Can access:
- reference data
- market data
- strategies
- backtests
- paper trading read access

### Operator
Can access:
- paper trading
- live trading
- risk
- treasury
- reconciliation
- alerts
- reliability

### Admin
Can access all routes, especially:
- bootstrap actions
- live controls
- emergency stop
- deployments/config changes
- storage/retention settings

---

## 16. Implementation Notes for Frontend Routing

Recommended implementation features:
- nested route support
- route metadata registry
- protected route wrapper
- lazy loading by feature domain
- consistent page shell wrapper

Recommended non-functional goals:
- route-level code splitting
- domain-based module boundaries
- minimal cross-domain imports

---

## 17. Final Summary

This information architecture makes the UI implementation directly actionable by defining:
- what pages exist
- where those pages live in the route tree
- how navigation should be grouped
- which domain owns which pages and components
- how phased rollout should expose the route tree over time

A frontend implementation should treat this file as the structural map for the UI, while using:
- `docs/ui-spec.md` for behavior and validation intent
- `docs/ui-phase-checklists.md` for delivery checklist
- `docs/ui-api-spec.md` for backend API integration
