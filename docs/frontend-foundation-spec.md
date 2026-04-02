# Frontend Foundation Spec

## Purpose

This document defines the **first frontend implementation slice** to build after the planning stage.

It focuses on the minimum architecture and module structure needed to support:
- Phase 0 UI
- Phase 1 UI
- future expansion without restructuring core frontend foundations

This document is intentionally limited to the first frontend foundation layer, not the full long-term UI surface.

It should be used together with:
- `docs/frontend-architecture-spec.md`
- `docs/ui-information-architecture.md`
- `docs/ui-phase-checklists.md`
- `docs/ui-api-spec.md`

---

## 1. Goal

The goal of this foundation slice is to define the first production-worthy frontend structure for:
- route registration
- app shell
- API client layer
- query layer conventions
- feature ownership for early pages
- Phase 0 and Phase 1 page scaffolding

At the end of this slice, the project should be ready to start implementing actual pages without needing to redesign core frontend boundaries.

---

## 2. Scope

This foundation spec covers only the modules that should be established first:

### In Scope
- `frontend/src/app/routes`
- `frontend/src/app/providers`
- `frontend/src/layout`
- `frontend/src/services/api`
- `frontend/src/services/query`
- `frontend/src/features/system`
- `frontend/src/features/bootstrap`
- `frontend/src/features/reference-data`
- shared UI primitives needed by these domains

### Out of Scope
- market data feature implementation
- backtest feature implementation
- paper/live trading implementation
- advanced charting
- websocket-heavy views beyond initial system structure

---

## 3. Why This Slice Comes First

This slice should be built first because the frontend architecture spec already establishes that the product depends on:
- stable route structure
- a shared app shell
- standardized API client usage
- a query-driven server-state pattern
- domain-based module ownership

If actual pages are built before these foundations are in place, the project is likely to accumulate:
- unstable routes
- duplicated fetch logic
- inconsistent page layouts
- cross-feature coupling
- repeated refactors during later phases

---

## 4. First Frontend Build Targets

The first frontend build should produce the following architectural base:

### 4.1 App Shell
A consistent shell that includes:
- left navigation
- top header
- environment badge
- content outlet
- global loading/error support

### 4.2 Route Registry
A single route definition system that supports:
- nested routes
- metadata per route
- phase-aware route rollout
- future route guards

### 4.3 API Client Layer
A domain-based API wrapper layer for:
- system endpoints
- bootstrap endpoints
- reference-data endpoints

### 4.4 Query Layer Pattern
A consistent query layer for:
- list queries
- detail queries
- mutation hooks
- invalidation rules

### 4.5 Phase 0–1 Feature Modules
Initial feature modules for:
- system
- bootstrap
- reference-data

---

## 5. Recommended Initial Directory Structure

```text
frontend/
  src/
    app/
      routes/
        index.ts
        route-metadata.ts
        protected-route.tsx
      providers/
        app-providers.tsx
        query-provider.tsx
        auth-provider.tsx
        environment-provider.tsx
      metadata/
        nav-items.ts
    layout/
      AppShell/
        AppShell.tsx
      SidebarNav/
        SidebarNav.tsx
      TopHeader/
        TopHeader.tsx
    components/
      shared/
        PageHeader.tsx
        SummaryCard.tsx
        StatusBadge.tsx
        DataTable.tsx
        FilterBar.tsx
        DetailDrawer.tsx
        JsonViewer.tsx
        LoadingState.tsx
        ErrorState.tsx
        EmptyState.tsx
      primitives/
      charts/
    services/
      api/
        client.ts
        system.ts
        bootstrap.ts
        reference.ts
      query/
        keys.ts
        utils.ts
    features/
      system/
        pages/
          SystemOverviewPage.tsx
          EnvironmentConfigPage.tsx
        api/
        hooks/
        components/
      bootstrap/
        pages/
          DatabaseBootstrapPage.tsx
        api/
        hooks/
        components/
      reference-data/
        pages/
          ExchangesExplorerPage.tsx
          AssetsExplorerPage.tsx
          InstrumentsExplorerPage.tsx
          InstrumentDetailPage.tsx
          FeeSchedulesPage.tsx
        api/
        hooks/
        components/
    types/
    utils/
    styles/
```

This structure is enough to support the first pages while still aligning with the full future architecture.

---

## 6. Route Structure for the First Slice

The initial route set should include:

```text
/
/system
/system/environment
/system/bootstrap
/reference/exchanges
/reference/assets
/reference/instruments
/reference/instruments/:instrumentId
/reference/fee-schedules
```

## 6.1 Route Ownership

### `app/routes`
Owns:
- route declarations
- route metadata registration
- route nesting
- route guard wrappers
- lazy-loading boundaries

### `features/*/pages`
Owns:
- page container components used by routes
- page-level data fetching hooks
- page composition and local state

## 6.2 Route Metadata Contract

Each initial route should define:
- `path`
- `title`
- `navLabel`
- `breadcrumbLabel`
- `requiredRole`
- `phaseIntroduced`
- `featureOwner`

Example:

```ts
{
  path: "/system/bootstrap",
  title: "Database Bootstrap",
  navLabel: "Database Bootstrap",
  breadcrumbLabel: "Database Bootstrap",
  requiredRole: "developer",
  phaseIntroduced: 1,
  featureOwner: "bootstrap"
}
```

---

## 7. App Shell Contract

## 7.1 AppShell Responsibilities

`AppShell` should own:
- top-level layout frame
- sidebar layout region
- top header region
- route outlet placement
- environment visibility
- page-level scroll/frame consistency

## 7.2 Sidebar Responsibilities

`SidebarNav` should own:
- navigation section grouping
- active route highlighting
- collapsed/expanded nav behavior if added later
- display of only currently enabled routes/modules

## 7.3 Top Header Responsibilities

`TopHeader` should own:
- current page title region
- environment badge
- optional user/session region
- optional global actions region

## 7.4 First Shell Acceptance Criteria
- [ ] all first-slice routes render inside one consistent shell
- [ ] environment label is visible from every page
- [ ] navigation is stable and reusable for later phase routes

---

## 8. API Client Specification for First Slice

## 8.1 Required API Domains

The initial API client layer should expose wrappers for:
- system
- bootstrap
- reference data

Suggested files:

```text
services/api/client.ts
services/api/system.ts
services/api/bootstrap.ts
services/api/reference.ts
```

## 8.2 `client.ts` Responsibilities

The base API client should own:
- base URL configuration
- standard headers
- response envelope parsing
- error normalization
- request helper functions
- auth injection later if needed

## 8.3 Domain API Wrapper Responsibilities

### `system.ts`
Should wrap:
- `GET /api/v1/system/health`
- `GET /api/v1/system/runtime`
- `GET /api/v1/system/logs`

### `bootstrap.ts`
Should wrap:
- `GET /api/v1/bootstrap/status`
- `POST /api/v1/bootstrap/verify`
- `GET /api/v1/bootstrap/verification-runs/{verification_run_id}`

### `reference.ts`
Should wrap:
- `GET /api/v1/reference/exchanges`
- `GET /api/v1/reference/assets`
- `GET /api/v1/reference/instruments`
- `GET /api/v1/reference/instruments/{instrument_id}`
- `GET /api/v1/reference/fee-schedules`

## 8.4 API Client Rules
- components must not call `fetch()` directly
- page containers and hooks must use domain API wrappers
- API response envelope parsing must be centralized
- error objects should be normalized before reaching UI components

## 8.5 First Slice Acceptance Criteria
- [ ] all first-slice pages can load data through domain API wrappers
- [ ] no page contains ad hoc raw HTTP request logic
- [ ] standard API envelope parsing is shared

---

## 9. Query Layer Specification for First Slice

## 9.1 Required Query Infrastructure

Initial query layer must support:
- simple list queries
- detail queries
- bootstrap verification mutation
- cache invalidation
- optional polling for system pages

Suggested files:

```text
services/query/keys.ts
services/query/utils.ts
```

## 9.2 Query Key Conventions for First Slice

Use the following initial key set:
- `system.health`
- `system.runtime`
- `system.logs`
- `bootstrap.status`
- `bootstrap.verification.detail`
- `reference.exchanges`
- `reference.assets`
- `reference.instruments.list`
- `reference.instruments.detail`
- `reference.feeSchedules`

## 9.3 Recommended Hook Structure

Each feature should expose hooks under its own domain.

### `features/system/hooks`
Examples:
- `useSystemHealth()`
- `useSystemRuntime()`
- `useSystemLogs()`

### `features/bootstrap/hooks`
Examples:
- `useBootstrapStatus()`
- `useRunBootstrapVerification()`
- `useBootstrapVerificationResult(verificationRunId)`

### `features/reference-data/hooks`
Examples:
- `useExchanges()`
- `useAssets()`
- `useInstruments(filters)`
- `useInstrumentDetail(instrumentId)`
- `useFeeSchedules(filters)`

## 9.4 Query Layer Rules
- query hooks should hide API client details from page components
- mutation hooks should invalidate affected query keys
- operational polling should be opt-in per hook
- pages should not own manual cache logic directly

## 9.5 First Slice Acceptance Criteria
- [ ] page containers consume hooks, not raw API wrappers directly where repeated logic exists
- [ ] bootstrap verification mutation invalidates or refreshes status queries
- [ ] list/detail query boundaries are consistent across reference-data pages

---

## 10. State Management Specification for First Slice

## 10.1 Global State Scope

For the first slice, global state should remain minimal.

Allowed global state:
- current environment label
- authenticated user role or placeholder auth state
- app-shell UI preferences if needed

Not allowed in global state:
- exchanges list
- instrument list
- bootstrap status
- system logs

These belong in the query/server-state layer.

## 10.2 Local UI State

Local page state should handle:
- active filters
- selected rows
- detail drawer open/close
- selected tab
- modal visibility

## 10.3 Form State

The only initial action form that matters in Phase 0–1 is bootstrap verification.
It should:
- use local form state
- keep validation near the page
- expose success/error feedback clearly

## 10.4 First Slice Acceptance Criteria
- [ ] no server-fetched list/detail data is stored in a custom global store
- [ ] page-level filters live in the page/component layer
- [ ] environment and auth placeholders are available app-wide

---

## 11. Shared Component Specification for First Slice

The first slice should implement only the shared components needed for Phase 0–1.

## 11.1 Must-Have Shared Components
- `PageHeader`
- `SummaryCard`
- `StatusBadge`
- `DataTable`
- `FilterBar`
- `DetailDrawer`
- `JsonViewer`
- `LoadingState`
- `ErrorState`
- `EmptyState`

## 11.2 Shared Component Ownership

Owned by the platform/shared layer:
- layout consistency
- common table/empty/loading/error states
- status rendering standards
- detail inspection shell patterns

## 11.3 Domain Components for First Slice

### `features/system/components`
- `HealthStatusCards`
- `RuntimeMetadataPanel`
- `RecentLogsTable`

### `features/bootstrap/components`
- `BootstrapSummaryCards`
- `BootstrapVerificationPanel`
- `BootstrapResultPanel`

### `features/reference-data/components`
- `ExchangesTable`
- `AssetsTable`
- `InstrumentsTable`
- `InstrumentDetailPanel`
- `FeeSchedulesTable`

## 11.4 First Slice Acceptance Criteria
- [ ] shared components are reusable across system/bootstrap/reference-data pages
- [ ] domain components compose shared primitives instead of duplicating them
- [ ] loading/error/empty state behavior is consistent across pages

---

## 12. Feature Module Specification

## 12.1 `features/system`

Owns:
- `SystemOverviewPage`
- `EnvironmentConfigPage`
- health/runtime/log hooks
- system-specific display components

Should not own:
- bootstrap verification logic
- reference-data explorers

## 12.2 `features/bootstrap`

Owns:
- `DatabaseBootstrapPage`
- bootstrap verification trigger logic
- bootstrap status/result display components

Should not own:
- generic system health UI
- reference-data browsing

## 12.3 `features/reference-data`

Owns:
- exchanges/assets/instruments/fee-schedules pages
- list/detail hooks for reference data
- reference-data tables and detail panels

Should not own:
- app shell
- bootstrap verification workflow
- system runtime pages

## 12.4 Module Boundary Rule

In the first slice:
- `system`, `bootstrap`, and `reference-data` may depend on shared platform components
- they may depend on shared API/query infrastructure
- they should not import internal UI components from one another except through deliberately shared primitives

---

## 13. Phase 0–1 Page Specifications

## 13.1 Phase 0 Pages

### `SystemOverviewPage`
Must include:
- app/postgres/redis health summary
- runtime metadata block
- recent logs section

### `EnvironmentConfigPage`
Must include:
- environment label
- loaded config metadata
- masked or summarized config display

## 13.2 Phase 1 Pages

### `DatabaseBootstrapPage`
Must include:
- bootstrap status
- migration list
- verification action
- verification results

### `ExchangesExplorerPage`
Must include:
- exchanges table
- row count summary
- exchange detail inspection

### `AssetsExplorerPage`
Must include:
- assets table
- asset type filter
- detail inspection

### `InstrumentsExplorerPage`
Must include:
- exchange filter
- instrument type filter
- status filter
- instruments table
- instrument detail entry point

### `InstrumentDetailPage`
Must include:
- symbol identifiers
- base/quote/settlement mapping
- trading-rule fields
- status display

### `FeeSchedulesPage`
Must include:
- fee schedules table
- exchange and instrument-type filters

---

## 14. First-Slice Implementation Order

Recommended exact order:

1. define route registry and route metadata
2. build app shell
3. build base API client
4. build domain API wrappers (`system`, `bootstrap`, `reference`)
5. build query hooks for first-slice pages
6. build shared page primitives (`PageHeader`, `SummaryCard`, `StatusBadge`, `DataTable`, `LoadingState`, `ErrorState`, `EmptyState`)
7. build Phase 0 pages
8. build Phase 1 pages
9. wire detail flows and filters
10. run Phase 0–1 UI acceptance checks

This order minimizes rework because route, shell, data access, and shared primitives are established before feature pages expand.

---

## 15. Definition of Done for This Foundation Slice

The first frontend foundation slice is complete when:
- route registry exists for Phase 0–1 routes
- app shell is implemented
- system/bootstrap/reference-data modules exist
- API client wrappers exist for system/bootstrap/reference APIs
- query hooks exist for first-slice pages
- shared components support all Phase 0–1 pages
- Phase 0 pages render from live backend responses or mocked equivalents
- Phase 1 pages render from live backend responses or mocked equivalents
- no page bypasses the agreed architecture with ad hoc routing or fetching

---

## 16. Handoff to Next Frontend Slice

Once this slice is complete, the project can safely proceed to the next frontend slice:
- model validation
- repository explorer
- market data explorer
- ingestion dashboards
- data quality views

That next slice should reuse the same:
- app shell
- route metadata pattern
- API client layer
- query hook conventions
- table/detail page patterns

---

## 17. Final Summary

This document defines the first frontend implementation foundation as a deliberately narrow but stable architecture slice.

It answers the question:
**what should be built first before building more frontend pages?**

Answer:
- route registry
- app shell
- API client base
- query layer conventions
- shared page primitives
- `system`, `bootstrap`, and `reference-data` feature modules

That is the cleanest path to start frontend implementation while preserving the long-term phase-aligned architecture.
