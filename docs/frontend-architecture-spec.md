# Frontend Architecture Spec

## Purpose

This document defines the frontend architecture for the internal console described in:
- `docs/ui-spec.md`
- `docs/ui-phase-checklists.md`
- `docs/ui-information-architecture.md`
- `docs/ui-api-spec.md`

It turns the UI planning documents into an implementation-oriented frontend architecture specification.

This spec defines:
- route structure
- page hierarchy
- state management approach
- shared component ownership
- data fetching pattern
- module boundaries
- recommended directory structure
- phased rollout rules

---

## 1. Frontend Architecture Goals

The frontend must support the project in all phases from bootstrap through live trading and operations.

The frontend architecture should:
1. support phased delivery without major rewrites
2. keep routes stable as features expand
3. isolate domains cleanly
4. make data-heavy operational pages easy to build
5. make frontend/backend integration predictable
6. support both polling and streaming views
7. minimize coupling between pages and backend table structure

---

## 2. Recommended Frontend Style

### 2.1 Application Type
The frontend is an **internal operator / developer / researcher console**.

It should be built as a:
- client-side web app with route-based modules
- admin-style, data-dense console
- componentized SPA with strong domain boundaries

### 2.2 UI Characteristics
The frontend should prioritize:
- inspection
- filtering
- drill-down details
- operational control
- status visibility
- structured data viewing

It does not need to prioritize:
- marketing-style design
- public-facing onboarding
- consumer-grade visual polish in early phases

---

## 3. Route Structure

The route structure should follow the IA defined in `docs/ui-information-architecture.md`.

### 3.1 Top-Level Route Groups

```text
/
/system/*
/reference/*
/market/*
/quality/*
/ops/*
/strategies/*
/strategy-versions/*
/backtests/*
/paper/*
/live/*
/risk/*
/treasury/*
/reconciliation/*
/admin/*
```

### 3.2 Route Design Rules

1. Top-level route names must map to user-facing domains, not DB schemas.
2. Route paths should remain stable across phases.
3. Detail views should use route params for bookmarkable entities.
4. List pages should remain separate from detail pages when detail complexity is high.
5. Fast-inspection pages may also support detail drawers in addition to nested routes.

### 3.3 Detail Route Pattern

Recommended route parameter style:
- `/reference/instruments/:instrumentId`
- `/backtests/runs/:runId`
- `/paper/orders/:orderId`
- `/live/orders/:orderId`
- `/treasury/events/:treasuryEventId`

### 3.4 Route Metadata

Each route should carry metadata such as:
- `title`
- `navLabel`
- `breadcrumbLabel`
- `requiredRole`
- `phaseIntroduced`
- `featureOwner`

Example:

```ts
{
  path: "/live/orders/:orderId",
  title: "Live Order Detail",
  navLabel: "Orders",
  breadcrumbLabel: "Order Detail",
  requiredRole: "operator",
  phaseIntroduced: 7,
  featureOwner: "live-trading"
}
```

---

## 4. Page Hierarchy

### 4.1 Hierarchy Rules

Every domain should follow a predictable page structure:
- dashboard or list page
- detail page or detail drawer
- action page when user-triggered workflows exist

Examples:
- `Market Data -> Explorer`, `Ingestion Jobs`, `Bar Backfill`
- `Backtests -> Runs`, `Run Detail`, `Run Builder`
- `Live Trading -> Console`, `Orders`, `Order Detail`, `Manual Order Ticket`

### 4.2 Standard Page Composition

Recommended composition pattern:

```text
Page
├── PageHeader
│   ├── title
│   ├── subtitle
│   └── primary actions
├── SummarySection
│   └── status cards / KPIs
├── FilterSection
│   └── filters / selectors / time range controls
├── MainContent
│   ├── table / chart / event timeline
│   └── contextual side panels
└── DetailSurface
    └── drawer or nested detail view
```

### 4.3 Page Types

Overview Pages:
- System Overview
- Data Quality Dashboard
- Reliability Dashboard

Explorer Pages:
- Instruments Explorer
- Market Data Explorer
- Treasury Explorer
- Orders Explorer

Detail Pages:
- Instrument Detail
- Backtest Run Detail
- Live Order Detail
- Treasury Event Detail

Action Pages:
- Backtest Run Builder
- Bar Backfill Runner
- Manual Order Ticket

Console Pages:
- Paper Trading Console
- Live Trading Console

---

## 5. State Management

### 5.1 State Categories

The frontend state should be divided into four categories:
1. **server state**
2. **UI state**
3. **session/runtime state**
4. **form state**

### 5.2 Server State

Server state includes data fetched from backend APIs, such as:
- exchanges
- instruments
- bars
- ingestion jobs
- backtest runs
- orders
- fills
- balances
- risk events
- treasury events

Recommended approach:
- use a query/cache layer for server state
- support caching, background refetch, polling, and invalidation

Recommended behaviors:
- list endpoints cached by filter set
- detail endpoints cached by ID
- mutation endpoints invalidate affected lists/details
- polling enabled only where operationally needed

Examples:
- `/reference/instruments` list
- `/market/ingestion-jobs` list with polling
- `/paper/sessions/:sessionId` console summary with refresh
- `/live/orders/:orderId` detail refetch after cancel action

### 5.3 UI State

UI state includes transient client-only concerns such as:
- selected tab
- open/closed drawer
- active filters before apply
- table column visibility
- modal visibility
- selected rows

Recommended approach:
- keep local UI state close to page/component when possible
- use shared/global UI state only when multiple route segments need the same state

### 5.4 Session / Runtime State

This includes app-wide frontend runtime state such as:
- current environment label
- authenticated user role
- navigation permissions
- websocket connection presence at app level if needed

Recommended approach:
- use app-level provider or lightweight global store
- keep it minimal

### 5.5 Form State

Forms include:
- backfill job trigger
- bootstrap verification trigger
- backtest run builder
- paper session start form
- manual order ticket

Recommended approach:
- use dedicated form state local to each page
- pair with schema-based validation when possible
- separate form presentation from submit logic

### 5.6 Global Store Use Rules

A global store should be used only for:
- auth/user role
- environment/app metadata
- persistent UI preferences
- cross-route app shell state if needed

Do **not** use a global store as the primary storage for server data. Server data should live in the query/cache layer.

---

## 6. Data Fetching Pattern

### 6.1 Core Principle

The frontend should use a **query-driven data fetching pattern**.

This means:
- pages declare the data they need
- data fetching is colocated with page containers or domain hooks
- server state is cached and invalidated predictably
- mutations trigger targeted invalidation or optimistic updates only when appropriate

### 6.2 Query Layer Responsibilities

The query layer should handle:
- request execution
- caching
- loading/error state
- background refetch
- polling for operational pages
- mutation lifecycle state

### 6.3 Query Key Convention

Use domain-prefixed query keys.

Examples:
- `system.health`
- `bootstrap.status`
- `reference.exchanges`
- `reference.instruments.list`
- `reference.instruments.detail`
- `market.bars`
- `market.trades`
- `quality.summary`
- `backtests.run.detail`
- `paper.orders`
- `live.positions`
- `reconciliation.mismatches`
- `admin.deployments`

### 6.4 Polling Strategy

Polling should be enabled only for pages that need live-ish operational visibility.

Recommended candidates:
- System Overview
- Ingestion Jobs Dashboard
- WebSocket Monitor
- Paper Trading Console
- Live Trading Console
- Live Orders Explorer
- Reconciliation Dashboard
- Reliability Dashboard

Polling intervals should be page/domain specific, not globally forced.

### 6.5 Streaming Pattern

For future real-time requirements, websocket or SSE support should be added behind a domain service layer.

Use streaming only when justified, such as:
- live trade updates
- live order event updates
- stream connection status
- runtime console updates

Fallback should always exist via HTTP refetch or polling.

### 6.6 Mutation Pattern

Mutations should be separated into action hooks/services.

Examples:
- `runBootstrapVerification()`
- `triggerBarBackfill()`
- `createBacktestRun()`
- `startPaperSession()`
- `submitLiveOrder()`
- `cancelLiveOrder()`
- `markMismatchReviewed()`

Mutation response handling should:
- show success/error feedback
- update or invalidate related query keys
- preserve server-returned job/run IDs for follow-up navigation

### 6.7 List vs Detail Fetching

List pages:
- fetch summary metrics and list results
- support pagination, filters, and sorting

Detail pages:
- fetch entity detail by ID
- fetch related tabs separately if needed to reduce page load complexity

Example:
- `GET /live/orders/:orderId`
- `GET /live/orders/:orderId/events`
- `GET /live/orders/:orderId/fills`

---

## 7. Shared Component Ownership

### 7.1 Platform-Owned Shared Components

These components should belong to a shared platform layer.

Examples:
- `AppShell`
- `SidebarNav`
- `TopHeader`
- `EnvironmentBadge`
- `PageHeader`
- `SummaryCard`
- `StatusBadge`
- `DataTable`
- `FilterBar`
- `DetailDrawer`
- `JsonViewer`
- `ConfirmationModal`
- `LoadingState`
- `ErrorState`
- `EmptyState`
- `PaginationControls`
- `TimeRangePicker`
- `Timeline`

Responsibilities:
- consistent styling
- accessibility baseline
- common interaction patterns
- composability across features

### 7.2 Domain-Owned Components

Feature teams or domains own components with domain-specific semantics.

Examples:
- `BootstrapVerificationPanel`
- `InstrumentRulesPanel`
- `BackfillRunnerForm`
- `WsConnectionStatusPanel`
- `BacktestRunSummaryPanel`
- `PaperSessionControls`
- `ManualOrderTicketForm`
- `TreasuryEventMetadataPanel`
- `DeploymentConfigDiffPanel`
- `LatencyMetricsPanel`

Responsibilities:
- map shared components to domain workflows
- contain domain-specific rendering logic
- remain inside feature boundaries unless deliberately generalized later

### 7.3 Chart Component Ownership

Shared chart wrappers should be platform-owned. Domain-specific chart panels should be domain-owned.

Shared wrappers:
- `LineChart`
- `BarChart`
- `TimeSeriesChart`

Domain panels:
- `EquityCurvePanel`
- `IngestionFreshnessPanel`
- `LatencyBreakdownPanel`

---

## 8. Module Boundaries and Feature Ownership

The frontend should be organized by feature domains rather than technical layers only.

### 8.1 Recommended Domain Modules
- `system`
- `bootstrap`
- `reference-data`
- `market-data`
- `ingestion`
- `quality`
- `ops`
- `strategies`
- `backtests`
- `paper-trading`
- `live-trading`
- `risk`
- `treasury`
- `reconciliation`
- `admin`

### 8.2 Allowed Dependency Direction

Recommended dependency rule:
- feature modules may depend on shared platform modules
- feature modules may depend on shared domain-agnostic services/types
- feature modules should not depend heavily on each other directly

Example:
- `live-trading` may reuse shared execution components from `execution-shared`
- `backtests` should not directly import `paper-trading` internals
- `reference-data` should not depend on `reconciliation`

### 8.3 Optional Shared Execution Layer

Because paper and live trading share visual patterns, a shared execution UI layer is recommended.

Examples:
- order table columns
- order timeline component
- fill table component
- position summary component
- balance summary component

Suggested module:
- `frontend/src/features/execution-shared/`

---

## 9. Recommended Frontend Directory Structure

```text
frontend/
  src/
    app/
      routes/
      providers/
      store/
      metadata/
    layout/
      AppShell/
      SidebarNav/
      TopHeader/
    components/
      primitives/
      shared/
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
      execution-shared/
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
    hooks/
    types/
    utils/
    styles/
```

Folder responsibility summary:
- `app/` = app bootstrapping, providers, route definitions
- `layout/` = shell/layout primitives
- `components/` = shared reusable UI components
- `features/` = domain modules
- `services/api/` = API client and endpoint wrappers
- `services/query/` = query hooks/configuration helpers
- `services/websocket/` = stream client logic
- `types/` = shared types aligned with API contracts

---

## 10. API Client Architecture

### 10.1 API Client Layer

The frontend should not fetch directly inside components with ad hoc `fetch()` calls.

Use a thin API client layer with:
- base request helper
- typed endpoint wrappers by domain
- standard error normalization
- auth/header injection
- environment-aware base URL config

Suggested structure:

```text
services/api/
  client.ts
  system.ts
  bootstrap.ts
  reference.ts
  market.ts
  quality.ts
  strategies.ts
  backtests.ts
  paper.ts
  live.ts
  risk.ts
  treasury.ts
  reconciliation.ts
  admin.ts
```

### 10.2 API Client Rules
- endpoint wrappers should reflect backend resource names
- components should call hooks/services, not raw endpoints
- request/response typing should be explicit
- standard envelope parsing should be centralized

---

## 11. Hook Pattern

### 11.1 Query Hooks

Each domain should expose hooks like:
- `useSystemHealth()`
- `useBootstrapStatus()`
- `useInstruments(filters)`
- `useIngestionJobs(filters)`
- `useBacktestRun(runId)`
- `usePaperOrders(filters)`
- `useLiveOrder(orderId)`

### 11.2 Mutation Hooks

Each domain should expose hooks like:
- `useRunBootstrapVerification()`
- `useTriggerBarBackfill()`
- `useCreateBacktestRun()`
- `useStartPaperSession()`
- `useSubmitLiveOrder()`
- `useCancelLiveOrder()`
- `useMarkMismatchReviewed()`

### 11.3 Hook Rules
- hooks should be colocated with domains
- hooks should hide API envelope handling from components
- hooks should expose loading, success, and error states clearly

---

## 12. Table Pattern

Many pages are explorer/list pages, so table architecture matters.

### 12.1 Shared Table Requirements

All major tables should support, where relevant:
- pagination
- sorting
- filter integration
- row click to detail view
- empty state
- loading state
- error state

### 12.2 Table Strategy

Recommended pattern:
- shared `DataTable` component
- domain-level column configuration per page
- domain-specific row actions

Example separation:
- shared table handles rendering, paging, sorting UI
- `InstrumentsExplorer` owns instrument columns
- `LiveOrdersExplorer` owns order-specific columns and actions

---

## 13. Form Pattern

### 13.1 Shared Form Principles

Forms should use:
- schema-based validation when possible
- explicit submit lifecycle states
- inline field-level errors
- confirmation dialogs for high-risk actions

### 13.2 High-Risk Form Actions

Actions requiring confirmation modal or explicit review step:
- emergency stop
- live order submit
- live order cancel
- strategy enable or disable in live mode
- potentially destructive admin actions

### 13.3 Examples of Major Forms
- bootstrap verification form
- bar backfill form
- backtest run builder form
- paper session start form
- manual order ticket form

---

## 14. Error Handling Pattern

### 14.1 Error Levels

Frontend should distinguish:
- page load error
- partial section error
- mutation/action error
- validation error
- empty state

### 14.2 Error UX Rules
- page-level failure should render a dedicated error state
- mutation failure should preserve form input when reasonable
- validation errors should stay close to the relevant fields
- operational pages should show backend-provided error context when available

---

## 15. Auth and Authorization Pattern

### 15.1 Auth State

Frontend should support internal authenticated access.

Minimum frontend requirements:
- authenticated app shell
- current user role available to route guards
- protected routes for restricted actions

### 15.2 Role-Gated UI

Examples:
- researchers may run backtests but not submit live orders
- operators/admins can access live trading actions
- admins can access deployment/config/admin routes

Route guards should hide or disable unavailable actions appropriately.

---

## 16. Phase-Aligned Frontend Rollout

### Phase 0-1
Build:
- app shell
- system pages
- bootstrap page
- reference data explorers

Focus:
- stable routes
- shared table/detail patterns
- environment and status visibility

### Phase 2-4
Build:
- model validation playground
- repository explorer
- market data explorers
- ingestion dashboards
- data quality views

Focus:
- query layer maturity
- explorer patterns
- JSON viewer and detail surfaces

### Phase 5-6
Build:
- strategy registry
- backtest run pages
- paper trading console and explorers

Focus:
- charting
- timeline components
- action forms and runtime session views

### Phase 7-9
Build:
- live trading console
- manual order ticket
- treasury/reconciliation/admin pages
- reliability and alert views

Focus:
- operational controls
- role gating
- mutation safety
- polling or streaming runtime visibility

---

## 17. Recommended Technical Decisions

These are recommendations, not hard requirements.

### Router
Use a router with:
- nested routes
- route metadata support
- lazy loading
- protected route wrappers

### Query Layer
Use a query/caching library with:
- query invalidation
- mutation lifecycle support
- polling support
- background refresh support

### Forms
Use a form solution with:
- schema integration
- field-level errors
- controlled submission states

### Charts
Use a small chart abstraction layer so chart implementation details do not leak into domain pages.

---

## 18. Definition of Done for Frontend Architecture

The frontend architecture is considered established when:
- route structure is implemented and stable
- domain modules exist with clear ownership
- shared component layer exists
- query/data-fetching pattern is standardized
- API client layer is standardized
- page composition patterns are consistent
- role and environment awareness are supported at the shell level

---

## 19. Final Summary

This document defines the frontend as a phased, domain-oriented internal console.

Its core architectural decisions are:
- stable route structure
- domain-based module ownership
- query-driven server state management
- minimal global state
- platform-owned shared components
- feature-owned domain components
- predictable page composition
- phase-aligned rollout

Use this file as the implementation architecture reference for frontend development, while using:
- `docs/ui-information-architecture.md` for route/page structure
- `docs/ui-phase-checklists.md` for delivery checklists
- `docs/ui-api-spec.md` for backend integration contracts
