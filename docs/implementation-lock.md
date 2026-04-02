# Implementation Lock

## Purpose

This document freezes the remaining concrete implementation decisions needed to start coding with minimal churn.

The repository already has strong architecture and planning coverage. This file exists to answer the final practical question:

**What are the default implementation choices the team should now treat as fixed unless explicitly revised later?**

This document complements:
- `docs/spec-index.md`
- `docs/implementation-plan.md`
- `docs/backend-system-design.md`
- `docs/frontend-foundation-spec.md`
- `docs/ui-api-spec.md`

---

## 1. Decision Policy

The choices in this file are **implementation defaults**.

Contributors should assume they are locked for the first implementation wave unless one of the following happens:
- a later spec explicitly replaces them
- an implementation blocker proves the choice unworkable
- the team intentionally approves a change

This document is intended to reduce churn, not to invite constant re-selection of tools.

---

## 2. Locked Initial Stack

## 2.1 Backend

Use:
- **Python 3.12**
- **FastAPI** for internal HTTP APIs
- **Pydantic v2** for request and domain validation
- **Uvicorn** for local API serving

Reason:
- aligns with the existing Python repository shape
- fits internal API and background job workflow well
- works cleanly with structured validation and UI-oriented JSON APIs

## 2.2 Database Access

Use:
- **PostgreSQL** as primary system of record
- **psycopg 3** as the DB driver
- **SQLAlchemy Core / SQLAlchemy 2.x query layer**, but **not ORM-first domain modeling**

Rule:
- database schema remains **schema-first** and **SQL-first**
- domain contracts are defined in Pydantic / internal models
- repositories own SQL/query behavior

Do **not** treat SQLAlchemy ORM models as the main source of truth for schema design.

## 2.3 Redis and Jobs

Use:
- **Redis** for locks, coordination, and job queue backend
- **RQ** for the first job queue implementation
- **APScheduler** for the first recurring scheduler implementation

Why this lock:
- simple operational model
- compatible with current Redis runtime
- enough for sync jobs, backfills, quality checks, and early reconciliation

This does **not** rule out a later move to a heavier orchestration stack if needed.

## 2.4 Frontend

Use:
- **React + TypeScript**
- **Vite** for frontend development/build
- **React Router** for routing
- **TanStack Query** for server-state/query layer
- **React Hook Form + Zod** for forms and frontend validation

These choices align with the existing frontend architecture and foundation specs.

---

## 3. Locked Schema and Migration Strategy

## 3.1 Schema Source of Truth

The source of truth for implemented DB structure is:
- `db/init/*.sql` for bootstrap/base state
- future ordered migration SQL files for incremental changes

Rule:
- **SQL files remain the authoritative schema definition**
- code must adapt to schema, not replace it as primary truth

## 3.2 Migration Approach

For the first implementation wave:
- keep using **ordered SQL migration files**
- do **not** introduce Alembic or ORM-generated migrations yet

Recommended structure:
- keep bootstrap files under `db/init/`
- add future incremental migration files under a dedicated path such as `db/migrations/`
- provide a script/command to apply incremental migrations in order

## 3.3 Migration Naming Rule

Use monotonic numeric prefixes:
- `005_add_jobs_table.sql`
- `006_add_api_request_log.sql`

Rule:
- one file per coherent schema change set
- never modify old migration intent silently once the migration sequence is in active use

---

## 4. Locked Local Runtime Topology

## 4.1 Local Development Topology

For the first implementation wave, local development should use:
- Docker Compose for infrastructure services
- local Python processes for app runtimes during early implementation
- local frontend dev server for UI work

### Docker services
Required:
- postgres
- redis

To be added next:
- api
- worker
- scheduler
- optional frontend

## 4.2 Early Runtime Rule

Until a fuller containerized dev setup is added, the default local startup model is:
- Postgres + Redis via Docker
- API via local Python command
- Worker via local Python command
- Scheduler via local Python command
- Frontend via local Vite dev server

This is the locked default for initial implementation simplicity.

---

## 5. Locked Backend Module Layout

The first backend code expansion should follow this structure:

```text
src/
  config/
  api/
  models/
  storage/
  services/
  ingestion/
  jobs/
  runtime/
  exchange/
  execution/
  risk/
  reconciliation/
  ops/
```

## 5.1 Boundary Rules

- `api/` exposes HTTP handlers and request/response coordination
- `models/` owns canonical internal typed models
- `storage/` owns repositories and DB access helpers
- `services/` owns domain orchestration not tied to transport
- `jobs/` owns asynchronous job entrypoints
- `runtime/` owns long-running loops such as collectors and paper/live sessions
- `exchange/` owns venue-specific adapter code

Avoid mixing these responsibilities during first implementation.

---

## 6. Locked Async Job Model

## 6.1 Queue Model

Use **RQ** backed by Redis for the first job implementation.

Initial job types to support:
- instrument metadata sync
- bar backfill
- quality checks
- reconciliation jobs
- backtest execution

## 6.2 Scheduler Model

Use **APScheduler** to enqueue recurring jobs into the RQ queue.

## 6.3 Job Tracking Rule

In the first implementation wave:
- continue using existing domain-specific ops tables where practical
- do **not** block Phase 2–3 on designing a perfect universal jobs table

However, every async job must still expose:
- job id
- job type
- current status
- requested_by when user-triggered
- started/finished timestamps
- error metadata if failed

## 6.4 Concurrency Defaults

Lock these defaults:
- only one instrument sync per exchange at a time
- no overlapping bar backfill window for the same exchange + symbol + interval
- runtime-critical tasks must not share the same queue priority as large backfills

---

## 7. Locked API Conventions

## 7.1 API Base

Use:
- `/api/v1/` as the base path
- standard response envelope already defined in `docs/ui-api-spec.md`

## 7.2 Pagination Default

For the first implementation wave:
- use **offset + limit** pagination for list endpoints
- do **not** introduce cursor pagination unless a specific high-volume endpoint requires it later

## 7.3 Timestamp Rule

All API timestamps must be:
- ISO-8601
- UTC
- explicitly timezone-aware in payloads

## 7.4 Error Contract

Use a common error shape with:
- `code`
- `message`
- `details`

Recommended first error codes:
- `VALIDATION_ERROR`
- `NOT_FOUND`
- `UNAUTHORIZED`
- `FORBIDDEN`
- `CONFLICT`
- `RATE_LIMITED`
- `INTERNAL_ERROR`
- `DEPENDENCY_ERROR`

## 7.5 Async Action Contract

All async action endpoints should return immediately with:
- `success`
- `job_id` or `run_id` or `session_id`
- `status`

This is locked for:
- backfills
- backtests
- paper session start
- verification runs
- reconciliation runs

---

## 8. Locked Config and Environment Contract

## 8.1 Required Environment Names

Use these canonical environment labels:
- `local`
- `staging`
- `production`

Do not invent parallel names such as `dev`, `prod-live`, or `sandbox-main` unless explicitly documented.

## 8.2 Required Backend Config Variables

The first implementation wave should standardize around variables like:
- `APP_ENV`
- `APP_DEBUG`
- `DATABASE_URL`
- `REDIS_URL`
- `LOG_LEVEL`
- `ENABLE_LOCAL_AUTH_BYPASS`
- `ENABLE_LIVE_TRADING`

Exchange credentials should use structured naming by exchange/account/environment.

Example convention:
- `BINANCE_LIVE_MAIN_API_KEY`
- `BINANCE_LIVE_MAIN_API_SECRET`
- `BYBIT_STAGING_MAIN_API_KEY`
- `BYBIT_STAGING_MAIN_API_SECRET`

## 8.3 Safety Rule

`ENABLE_LIVE_TRADING` must default to **false** outside explicitly configured live environments.

---

## 9. Locked First Vertical Slice

The first implementation slice is locked as:

## 9.1 Backend First

Prioritize backend implementation before broad frontend expansion.

## 9.2 Scope

Implement in this order:
1. finish Phase 1 verification
2. Phase 2 models and storage
3. Phase 3 public Binance ingestion
4. minimal UI/API support only where needed to inspect that work

## 9.3 First Exchange Scope

Lock first exchange scope to:
- **Binance public market data only**

Do not start first with:
- multiple exchanges
- private exchange trading
- full live runtime
- full reconciliation stack

## 9.4 First Data Scope

Lock first implemented market data to:
- instruments metadata
- `bars_1m`
- trades
- funding rates
- open interest

Order book and raw-event depth paths may come immediately after this slice, but should not block the first end-to-end ingestion milestone.

---

## 10. Locked Runtime Supervision Model

## 10.1 Early Runtime Rule

In the first implementation wave:
- collectors and paper/live sessions are **separate long-running processes or worker-managed runtimes**
- they are **not** implemented as long-running loops inside API request handlers

## 10.2 Ownership Rule

Use Redis-backed locks or equivalent coordination to ensure:
- one collector owner per stream scope
- one paper/live runtime owner per account/strategy scope

## 10.3 Session Management Rule

API starts/stops sessions by:
- validating request
- writing status/audit records
- handing off to job/runtime control layer
- returning session identifier immediately

This rule is locked even if the exact process runner evolves later.

---

## 11. Locked Risk Behavior Defaults

To avoid ambiguity during early implementation:
- pre-trade risk default action is **block**, not modify
- `modify` behavior is allowed only when explicitly implemented for a specific rule
- emergency stop prevents new live order submission immediately
- cancel-all / stop / pause semantics must remain explicit and auditable

---

## 12. Locked Accounting Defaults

For first implementation:
- use **average-cost position accounting**
- perpetual unrealized PnL uses **mark price**
- fees and funding remain separate accounting components
- net PnL views may aggregate them, but storage and attribution must preserve separation

These choices are already aligned with the existing accounting spec and are now considered implementation defaults.

---

## 13. Deferred Decisions

The following are intentionally **not** blockers for first implementation:
- migration to ClickHouse
- cursor pagination for high-volume endpoints
- microservice split beyond process separation
- advanced tracing stack choice
- portfolio-level multi-strategy attribution
- tax-lot accounting variants

Do not delay Phase 2–3 waiting for these.

---

## 14. Immediate Implementation Start Checklist

Implementation can now begin if the team follows these locked defaults:
- [ ] use FastAPI + Pydantic v2 for backend API
- [ ] use psycopg 3 + SQLAlchemy Core style repositories
- [ ] keep schema-first SQL migration strategy
- [ ] use Redis + RQ + APScheduler for first async stack
- [ ] use React + TypeScript + Vite + React Router + TanStack Query for frontend
- [ ] keep first vertical slice backend-first and Binance-public-only
- [ ] keep long-running runtimes outside API request handlers
- [ ] keep live trading disabled by default

---

## 15. Final Summary

This document locks the final concrete defaults needed to start implementation safely.

The most important locked choices are:
- FastAPI backend
- schema-first SQL migrations
- psycopg/SQLAlchemy Core repository style
- Redis + RQ + APScheduler async model
- React/TypeScript frontend stack
- backend-first first slice
- Binance public data as first exchange scope
- long-running runtimes outside request handlers

These decisions should be treated as the implementation baseline until a later spec explicitly replaces them.