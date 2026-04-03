# Spec Index and Docs Map

## Purpose

This document is the entry point to the repository's design and specification system.

It helps future developers understand:
- which documents exist
- what each document is for
- which document is the source of truth for each topic
- what order to read the docs in
- how the docs map to implementation phases

This repository now contains a large and intentionally layered specification set.
Without a map, it becomes hard for new contributors to know where to start.

---

## 1. How to Use This Document

Use this file in one of three ways:

### A. New to the Repo
Read the **recommended reading order** in Section 3.

### B. Looking for a Specific Topic
Use the **topic-to-document map** in Section 4.

### C. Starting Implementation
Use the **phase-to-doc map** in Section 5.

---

## 2. Design Document Layers

The repo documentation is organized into these layers:

### Layer 1: Product and Core Direction
Defines what the product is and what it should do.

### Layer 2: Data and Contract Design
Defines what data exists and how systems communicate.

### Layer 3: Delivery / Phase Planning
Defines what order to build things in.

### Layer 4: UI / Frontend Planning
Defines what users can operate and inspect.

### Layer 5: System-Operability Architecture
Defines how the system becomes runnable, safe, observable, and scalable.

A contributor usually does **not** need to read every document before starting. They need the right subset.

---

## 3. Recommended Reading Order

## 3.1 For Any New Contributor

Read in this order:
1. `README.md`
2. `docs/product-spec.md`
3. `docs/architecture.md`
4. `docs/implementation-plan.md`
5. `docs/spec-index.md`

This gives the fastest high-level understanding.

## 3.2 For Backend Engineers

Read in this order:
1. `docs/product-spec.md`
2. `docs/architecture.md`
3. `docs/implementation-plan.md`
4. `docs/api-contracts.md`
5. `docs/backend-system-design.md`
6. `docs/job-orchestration-spec.md`
7. `docs/data-storage-performance-spec.md`
8. `docs/execution-and-risk-engine-spec.md`
9. `docs/position-management-spec.md`
10. `docs/strategy-input-and-feature-pipeline-spec.md`
11. `docs/strategy-taxonomy-and-versioning-spec.md`
12. `docs/strategy-research-and-evaluation-spec.md`
13. `docs/pnl-and-accounting-spec.md`
14. `docs/testing-strategy-spec.md`

## 3.3 For Data / Platform Engineers

Read in this order:
1. `docs/data-catalog.md`
2. `docs/data-catalog-addendum.md`
3. `db/init/*.sql`
4. `docs/backend-system-design.md`
5. `docs/job-orchestration-spec.md`
6. `docs/data-storage-performance-spec.md`
7. `docs/observability-spec.md`
8. `docs/testing-strategy-spec.md`

## 3.4 For Frontend Engineers

Read in this order:
1. `docs/ui-spec.md`
2. `docs/ui-api-spec.md`
3. `docs/ui-phase-checklists.md`
4. `docs/ui-information-architecture.md`
5. `docs/frontend-architecture-spec.md`
6. `docs/frontend-foundation-spec.md`

## 3.5 For Operators / Trading Runtime Contributors

Read in this order:
1. `docs/backend-system-design.md`
2. `docs/execution-and-risk-engine-spec.md`
3. `docs/position-management-spec.md`
4. `docs/security-and-secrets-spec.md`
5. `docs/observability-spec.md`
6. `docs/pnl-and-accounting-spec.md`
7. `docs/testing-strategy-spec.md`

---

## 4. Topic-to-Document Map

## 4.1 Product Scope and Goals
- `README.md`
- `docs/product-spec.md`
- `docs/architecture.md`

### Source of Truth
- product scope: `docs/product-spec.md`
- high-level architecture: `docs/architecture.md`

---

## 4.2 Delivery Plan and Build Order
- `docs/implementation-plan.md`
- `docs/phase-1-checklist.md`
- `docs/phases-2-to-9-checklists.md`

### Source of Truth
- overall phase roadmap: `docs/implementation-plan.md`
- phase-level implementation tasks: checklist docs

---

## 4.3 Database Schema and Seed
- `db/init/001_schema.sql`
- `db/init/002_extend_market_and_audit.sql`
- `db/init/003_extend_audit_treasury_latency.sql`
- `db/init/004_seed.sql`
- `db/init/005_execution_fill_dedup.sql`
- `db/init/006_seed_strategy_and_accounts.sql`
- `docs/database-bootstrap.md`
- `docs/phase-1-checklist.md`
- `docs/strategy-account-seed-extension.md`
- `db/verify/phase_1_verification.sql`

### Source of Truth
- actual schema: `db/init/*.sql`
- bootstrap procedure: `docs/database-bootstrap.md`
- Phase 1 acceptance: `docs/phase-1-checklist.md`

---

## 4.4 Data Collection Scope
- `docs/data-catalog.md`
- `docs/data-catalog-addendum.md`

### Source of Truth
- data scope and collection inventory: these two docs together

---

## 4.5 Internal Payload and Domain Contracts
- `docs/api-contracts.md`
- `docs/strategy-taxonomy-and-versioning-spec.md`
- `docs/strategy-input-and-feature-pipeline-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`

### Source of Truth
- canonical internal payload contracts: `docs/api-contracts.md`
- strategy family/variant/version identity and naming: `docs/strategy-taxonomy-and-versioning-spec.md`
- strategy-input and future feature/alignment architecture: `docs/strategy-input-and-feature-pipeline-spec.md`
- strategy development, research, testing, and comparison workflow: `docs/strategy-research-and-evaluation-spec.md`

---

## 4.6 Backend Runtime Architecture
- `docs/architecture.md`
- `docs/backend-system-design.md`
- `docs/job-orchestration-spec.md`
- `docs/data-storage-performance-spec.md`

### Source of Truth
- high-level layer model: `docs/architecture.md`
- runnable backend topology: `docs/backend-system-design.md`
- async job behavior: `docs/job-orchestration-spec.md`
- storage/performance rules: `docs/data-storage-performance-spec.md`

---

## 4.7 Execution, Risk, and Accounting
- `docs/execution-and-risk-engine-spec.md`
- `docs/position-management-spec.md`
- `docs/pnl-and-accounting-spec.md`
- `docs/security-and-secrets-spec.md`

### Source of Truth
- execution and risk semantics: `docs/execution-and-risk-engine-spec.md`
- position-management, strategy/account book separation, protection, and phased rollout: `docs/position-management-spec.md`
- accounting/PnL semantics: `docs/pnl-and-accounting-spec.md`
- live control security model: `docs/security-and-secrets-spec.md`

---

## 4.8 Observability and Reliability
- `docs/observability-spec.md`
- `docs/data-storage-performance-spec.md`
- `docs/testing-strategy-spec.md`

### Source of Truth
- logs/metrics/traces/alerts: `docs/observability-spec.md`
- performance/storage boundaries: `docs/data-storage-performance-spec.md`
- validation and regression protection: `docs/testing-strategy-spec.md`

---

## 4.9 UI and Frontend Design
- `docs/ui-spec.md`
- `docs/ui-phase-checklists.md`
- `docs/ui-api-spec.md`
- `docs/ui-information-architecture.md`
- `docs/frontend-architecture-spec.md`
- `docs/frontend-foundation-spec.md`

### Source of Truth
- UI intent and phase mapping: `docs/ui-spec.md`
- UI implementation checklist: `docs/ui-phase-checklists.md`
- frontend/backend contract: `docs/ui-api-spec.md`
- page/route/IA structure: `docs/ui-information-architecture.md`
- long-term frontend architecture: `docs/frontend-architecture-spec.md`
- first frontend slice: `docs/frontend-foundation-spec.md`

---

## 4.10 Testing and Verification
- `docs/testing-strategy-spec.md`
- `docs/phase-1-checklist.md`
- `db/verify/phase_1_verification.sql`
- `scripts/verify_phase1.sh`

### Source of Truth
- overall testing model: `docs/testing-strategy-spec.md`
- current bootstrap verification: Phase 1 verification docs/scripts

---

## 5. Phase-to-Document Map

## Phase 0: Repository and Runtime Bootstrap
Primary docs:
- `README.md`
- `docs/implementation-plan.md`
- `docs/backend-system-design.md`
- `docs/frontend-foundation-spec.md`

## Phase 1: Database Bootstrap and Seed Data
Primary docs:
- `docs/phase-1-checklist.md`
- `docs/database-bootstrap.md`
- `db/init/004_seed.sql`
- `db/verify/phase_1_verification.sql`

## Phase 2: Domain Models and Storage Layer
Primary docs:
- `docs/phases-2-to-9-checklists.md`
- `docs/api-contracts.md`
- `docs/backend-system-design.md`
- `docs/testing-strategy-spec.md`
- `docs/strategy-account-seed-extension.md`

## Phase 3: Public Market Data Ingestion
Primary docs:
- `docs/phases-2-to-9-checklists.md`
- `docs/data-catalog.md`
- `docs/api-contracts.md`
- `docs/job-orchestration-spec.md`
- `docs/data-storage-performance-spec.md`
- `docs/observability-spec.md`

## Phase 4: Market Data Quality and Replay Readiness
Primary docs:
- `docs/phases-2-to-9-checklists.md`
- `docs/job-orchestration-spec.md`
- `docs/observability-spec.md`
- `docs/data-storage-performance-spec.md`
- `docs/replay-retention-policy.md`

## Phase 5: Strategy Runner and Bars-Based Backtest
Primary docs:
- `docs/phases-2-to-9-checklists.md`
- `docs/api-contracts.md`
- `docs/position-management-spec.md`
- `docs/strategy-taxonomy-and-versioning-spec.md`
- `docs/strategy-input-and-feature-pipeline-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`
- `docs/pnl-and-accounting-spec.md`
- `docs/testing-strategy-spec.md`

## Phase 6: Paper Trading Engine
Primary docs:
- `docs/phases-2-to-9-checklists.md`
- `docs/execution-and-risk-engine-spec.md`
- `docs/position-management-spec.md`
- `docs/pnl-and-accounting-spec.md`
- `docs/observability-spec.md`

## Phase 7: Live Trading MVP
Primary docs:
- `docs/phases-2-to-9-checklists.md`
- `docs/execution-and-risk-engine-spec.md`
- `docs/position-management-spec.md`
- `docs/security-and-secrets-spec.md`
- `docs/observability-spec.md`
- `docs/pnl-and-accounting-spec.md`

## Phase 8: Reconciliation, Treasury, and Operational Controls
Primary docs:
- `docs/phases-2-to-9-checklists.md`
- `docs/job-orchestration-spec.md`
- `docs/security-and-secrets-spec.md`
- `docs/observability-spec.md`
- `docs/pnl-and-accounting-spec.md`

## Phase 9: Production Hardening and Scale Improvements
Primary docs:
- `docs/phases-2-to-9-checklists.md`
- `docs/data-storage-performance-spec.md`
- `docs/observability-spec.md`
- `docs/testing-strategy-spec.md`

---

## 6. Current Best Starting Points by Work Type

### If you want to start coding backend now
Start with:
1. `docs/implementation-plan.md`
2. `docs/backend-system-design.md`
3. `docs/api-contracts.md`
4. the relevant phase checklist

### If you want to start coding frontend now
Start with:
1. `docs/frontend-foundation-spec.md`
2. `docs/ui-information-architecture.md`
3. `docs/ui-api-spec.md`
4. `docs/ui-phase-checklists.md`

### If you want to start on data ingestion now
Start with:
1. `docs/data-catalog.md`
2. `docs/api-contracts.md`
3. `docs/job-orchestration-spec.md`
4. `docs/data-storage-performance-spec.md`
5. Phase 3 checklist

### If you want to start on live trading now
Start with:
1. `docs/backend-system-design.md`
2. `docs/execution-and-risk-engine-spec.md`
3. `docs/position-management-spec.md`
4. `docs/security-and-secrets-spec.md`
5. `docs/pnl-and-accounting-spec.md`
6. `docs/observability-spec.md`

---

## 7. Source-of-Truth Rules

Because many docs reference similar concepts, contributors should follow these rules.

### Rule 1
If there is a conflict between a checklist and a system architecture spec, the architecture/system spec wins unless the checklist is explicitly newer and intended to change it.

### Rule 2
If there is a conflict between a schema doc and actual SQL schema, the actual SQL schema wins for implemented state.

### Rule 3
If there is a conflict between UI behavior and UI API contract, the API contract and backend safety constraints win until UI spec is updated.

### Rule 4
If there is a conflict between README and a more specific design doc, the more specific design doc wins.

---

## 8. Suggested Future Maintenance Rules

To keep the docs set healthy:

- update `README.md` whenever repo maturity changes materially
- update `docs/spec-index.md` whenever a major new spec is added
- keep checklist docs focused on delivery steps
- keep architecture/system docs focused on long-lived design rules
- keep actual implemented behavior reflected in schema, code, and API specs

---

## 9. Documents That Future Contributors Should Expect To Change Frequently

Higher-change documents:
- `docs/implementation-plan.md`
- phase checklist docs
- UI checklist docs
- frontend foundation spec
- README

Lower-change documents:
- `docs/api-contracts.md`
- `docs/backend-system-design.md`
- `docs/execution-and-risk-engine-spec.md`
- `docs/position-management-spec.md`
- `docs/strategy-input-and-feature-pipeline-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`
- `docs/pnl-and-accounting-spec.md`
- `docs/security-and-secrets-spec.md`

---

## 10. Quick Repo Mental Model

If you want a simple mental model of the repo:

- `product-spec` says **what product to build**
- `implementation-plan` says **what order to build it in**
- `data-catalog` and `api-contracts` say **what data and contracts exist**
- `db/init/*.sql` says **what is actually in the DB**
- `backend-system-design` and related specs say **how it runs safely and scales**
- `ui-*` and `frontend-*` docs say **how users interact with it**
- `testing-strategy-spec` says **how to trust that it still works**

---

## 11. Final Summary

This repository now has a deliberately layered documentation system.

Current implementation reality:
- Phase 1 DB bootstrap, seed, and verification are complete
- Phase 2 is complete for the planned model/storage layer, with working foundations in `src/models/`, `src/storage/`, `src/services/`, and `src/api/`
- Phase 3 now has a working first Binance public-ingestion slice in `src/ingestion/`, `src/jobs/`, `src/runtime/`, and the minimal API
- Phase 4 now has working data-quality jobs, raw-event traceability, replay-readiness policy, and supporting API endpoints
- checklist docs should be treated as live implementation tracking and updated whenever a phase slice lands

The simplest way to navigate it is:
- start with `README.md`
- read `docs/product-spec.md`
- read `docs/implementation-plan.md`
- use `docs/spec-index.md` to branch into the topic you are implementing

This file should be maintained as the documentation entry point for all future contributors.
