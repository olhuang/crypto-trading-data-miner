# Peer Review Follow-Ups

## Purpose

This document captures the **valid follow-up items** from the recent peer review and converts them into a practical implementation checklist.

It is intentionally filtered.

It does **not** include peer review findings that are already addressed by newer specs or that are not true blockers for the relevant phase.

This file is organized by the latest phase gate before the issue must be fixed:
- must fix before Phase 2/3
- must fix before Phase 5
- must fix before Phase 8

This document should be used together with:
- `docs/spec-index.md`
- `docs/implementation-lock.md`
- `docs/ui-api-spec.md`
- `docs/execution-and-risk-engine-spec.md`
- `docs/pnl-and-accounting-spec.md`

---

## 1. Review Scope Notes

The peer review identified a mix of:
- still-valid implementation gaps
- issues already addressed by newer repository docs
- issues that are real but belong to later phases rather than current implementation start

This document keeps only the items that still need explicit follow-up.

Examples of peer review findings that are **not** treated as active blockers here:
- “no API endpoints defined” — superseded by `docs/ui-api-spec.md`
- “Phase 1 scope unclear about 002/003” — superseded by `docs/phase-1-checklist.md`
- “execution.deposits_withdrawals not modeled” — superseded by `docs/data-catalog-addendum.md`

---

# 2. Must Fix Before Phase 2/3

These items should be addressed before implementation proceeds through the first real backend slice (models, storage, and public ingestion).

## 2.1 Schema / Contract Naming Alignment

### Status
Resolved for the active Phase 2 contract set.

The review correctly identified earlier naming drift such as:
- `raw_payload` vs `payload_json`
- `detail` vs `detail_json`

The repository now has:
- locked naming rules in `docs/contract-naming-conventions.md`
- active canonical examples in `docs/api-contracts.md` using `payload_json` / `detail_json`
- Phase 2 implementation code that prefers the `*_json` names

### Ongoing Rule
Keep enforcing one consistent rule for JSON-bearing fields across:
- models
- repositories
- APIs
- UI payload handling

### Maintenance Action
- keep new contracts and resource docs aligned to `payload_json` / `detail_json`
- avoid reintroducing `raw_payload` or plain `detail` as canonical JSON blob names in new active specs

### Acceptance Criteria
- no unresolved `raw_payload` / `payload_json` naming split remains in active contracts
- no unresolved `detail` / `detail_json` naming split remains in active contracts

---

## 2.2 Required vs Nullable Contract Alignment

### Status
Resolved for the currently implemented Phase 2 market and execution contract slice.

The active implementation now makes the early contract rules explicit in code, including:
- required market `ingest_time` fields for the implemented bar, trade, and open-interest payloads
- canonical `event_time` usage for the implemented open-interest contract
- conditional order lifecycle requirements such as `ack_time`, `reject_reason`, and `cancel_time`
- priced-order and `post_only` validation rules for implemented order payloads

### Ongoing Rule
Continue treating required/null alignment as an active review item for any newly implemented contract set, especially:
- strategy models
- risk models
- later ingestion-only market payloads that are not yet coded
- schema areas where NULL is allowed for storage flexibility but contract behavior is lifecycle-dependent

### Acceptance Criteria
- the first implemented model set has no unresolved required/null ambiguity
- lifecycle-dependent optional fields are documented explicitly

---

## 2.3 Minimal Authentication Contract

### Status
Resolved for the initial Phase 2 models API slice.

The repository now has:
- a dedicated `docs/minimal-auth-contract.md`
- environment-driven local bypass behavior
- a fixed `Authorization: Bearer <token>` header convention for non-local requests
- current-actor resolution and role checks in the implemented models API
- automated tests covering local bypass, bearer auth, 401 behavior, and 403 behavior

### Ongoing Rule
Keep using one consistent auth middleware/dependency pattern for future protected routes, and keep the current actor shape stable unless the auth contract is intentionally revised.

### Acceptance Criteria
- backend API implementation can apply one consistent auth middleware strategy
- frontend and API tests know what header/auth shape to assume in shared environments

---

## 2.4 Missing Canonical Resource / Response Models for Early APIs

### Status
Resolved for the currently implemented early API slice.

The repository now has:
- `docs/api-resource-contracts.md` covering both the earlier planned resources and the currently implemented `/system/health` and `/models/*` resources
- typed response/resource models in `src/api/app.py` for the implemented endpoints
- explicit auth-aware meta shape for protected route responses

### Ongoing Rule
As additional endpoints are implemented, extend `docs/api-resource-contracts.md` and typed response models together so route definitions and response resources stay aligned.

### Acceptance Criteria
- all first-implemented endpoints have concrete response/resource definitions, not only route descriptions

---

## 2.5 Instrument Sync Diff Contract

### Status
Resolved for the current Phase 3 ingestion slice.

The repository now has:
- a dedicated `docs/instrument-sync-diff-contract.md`
- implemented `POST /api/v1/ingestion/jobs/instrument-sync`
- implemented `GET /api/v1/ingestion/jobs/{job_id}`
- instrument-sync jobs persisting `summary` and `diffs` metadata into `ops.ingestion_jobs`
- API job-detail responses exposing `summary` and `diffs` directly for the current implementation slice

### Ongoing Rule
Keep the diff payload anchored to job detail unless a later phase introduces a stronger need for a dedicated diff-only endpoint.

### Acceptance Criteria
- UI can display instrument metadata changes without inventing its own interpretation layer

---

## 2.6 Strategy / Account / Strategy Version Seed Defaults

### Status
Resolved for the current bootstrap baseline.

The repository now has:
- `db/init/006_seed_strategy_and_accounts.sql`
- one starter strategy row
- one starter strategy version row
- one paper account row
- one live-placeholder account row
- updated seed-extension documentation aligned to the implemented schema

### Ongoing Rule
Keep these rows minimal and bootstrap-oriented. Do not treat seed reruns as the long-term operational source of truth for strategy/account configuration drift.

### Acceptance Criteria
- repository has a documented plan for how strategy/account/version rows will exist before Phase 5 begins

---

## 2.7 Internal ID Mapping Convention

### Status
Resolved for the currently implemented lookup slice.

The repository now has:
- a dedicated `docs/internal-id-resolution-spec.md`
- implemented lookup helpers for `exchange_code`, `asset_code`, `account_code`, `strategy_code`, `strategy_code + strategy_version`, and `exchange_code + unified_symbol`
- bootstrap seed defaults that make the early strategy/account lookups resolvable in practice
- integration tests covering the implemented strategy/version resolution path

### Ongoing Rule
Add new lookup helpers only when a new human-readable identifier pair is actually introduced in a service/API flow, and keep repositories operating on internal IDs after resolution.

### Acceptance Criteria
- no service implementation needs to guess how to resolve code/version strings into DB IDs

---

# 3. Must Fix Before Phase 5

These items must be resolved before backtest and strategy-performance features are considered trustworthy.

## 3.1 KPI Methodology for Backtest Performance Metrics

### Problem
Metrics such as Sharpe ratio, Sortino, and max drawdown are named but not fully specified at formula level.

### Why This Must Be Fixed Before Phase 5
Backtest outputs are only meaningful if metrics are reproducible.
Different implementations could otherwise produce materially different results.

### Required Action
Define, for each KPI:
- input data source
- formula
- annualization convention
- sampling frequency assumption
- risk-free rate treatment
- edge-case handling

### Acceptance Criteria
- one developer-independent calculation method exists for each exposed KPI

---

## 3.2 Exact Balance Column Semantics

### Problem
Balance fields are described semantically, but not yet with exact enough operational semantics.

Key fields needing exact interpretation:
- `wallet_balance`
- `available_balance`
- `margin_balance`
- `equity`

### Why This Must Be Fixed Before Phase 5
Backtest, paper, and live views must eventually share accounting vocabulary.
Backtest result interpretation depends on balance/equity meaning.

### Required Action
Add a dedicated section defining:
- exact meaning of each balance field
- product/account-type assumptions
- whether open-order margin effects are included where relevant

### Acceptance Criteria
- balance-related fields can be computed and displayed consistently across environments

---

## 3.3 Risk Limit NULL Fallback Policy

### Problem
Risk limit tables allow nullable values, but the exact behavior of missing values is not yet fixed.

### Why This Must Be Fixed Before Phase 5
As soon as execution and risk logic exists, the engine must know whether NULL means:
- no limit configured
- invalid config
- block until configured

### Required Action
Add a documented fallback policy, for example:
- NULL = no configured limit for that field, allow with warning
or
- NULL = invalid production config, block in strict mode

### Acceptance Criteria
- risk evaluation code can implement one deterministic rule for missing limit values

---

## 3.4 Numeric Data Quality Thresholds

### Problem
Data quality language exists, but not yet with explicit numbers for alerting/acceptance.

### Why This Must Be Fixed Before Phase 5
Backtesting should not proceed on data quality assumptions that are only qualitative.

### Required Action
Define numeric thresholds for at least:
- acceptable bar gap rate
- acceptable freshness lag by data type
- duplicate rate tolerance
- missing funding/OI tolerance where relevant

### Acceptance Criteria
- quality checks can produce pass/fail outcomes using numeric thresholds, not only descriptive wording

---

# 4. Must Fix Before Phase 8

These items can wait until later phases, but must be explicit before reconciliation and mature operations are implemented.

## 4.1 Order Book JSON Format Specification

### Status
Resolved for the currently implemented Phase 2 order-book contract slice.

The repository now has:
- canonical snapshot and delta examples in `docs/api-contracts.md`
- implemented `OrderBookSnapshotEvent` and `OrderBookDeltaEvent` models in `src/models/market.py`
- repository support for `md.orderbook_snapshots` and `md.orderbook_deltas`
- automated tests that validate the currently implemented payload format

### Current Canonical Rule
- `bids` and `asks` use array-of-arrays pairs in `[price, qty]` form
- `depth_levels` is explicit on snapshots
- deltas are append-only stored events; replay/merge behavior remains a later-phase concern
- `checksum` is optional and stored when supplied by the venue

### Ongoing Rule
If replay logic later requires richer merge semantics, extend the docs and code together rather than introducing an alternate wire shape.

### Acceptance Criteria
- order-book snapshot/delta payloads have a single canonical stored shape for the current implementation slice

---

## 4.2 Reconciliation Tolerance and Severity Rules

### Problem
Reconciliation intent is specified, but mismatch tolerance and severity logic is not yet concrete.

### Required Action
Define:
- numeric tolerances for common mismatches
- severity levels
- mismatch categories
- review/remediation workflow expectations

### Acceptance Criteria
- reconciliation implementation can classify and escalate mismatches deterministically

---

## 4.3 Canonical Review / Resolution Semantics for Mismatches

### Problem
Review actions are described at route level, but the underlying operational semantics need tightening.

### Required Action
Define:
- what “reviewed” means
- who may mark reviewed
- whether review can resolve a mismatch or only acknowledge it
- whether repair and review are separate actions

### Acceptance Criteria
- mismatch review workflow is auditable and not ambiguous

---

# 5. Not Included as Active Follow-Ups

The following peer review findings are intentionally **not** tracked here as current blockers because newer docs already address them or they are not phase-appropriate blockers:

- no API endpoints defined
- Phase 1 unclear whether 002/003 run
- execution latency metrics table only exists in Phase 7
- treasury movement table not modeled

These were valid concerns against earlier repo state, but are no longer the best follow-up targets.

---

# 6. Recommended Follow-Up Order

## Immediate
1. schema/contract naming alignment
2. required vs nullable alignment
3. minimal auth contract
4. missing canonical response/resource models
5. instrument sync diff contract
6. internal ID mapping convention

## Before Backtesting / Paper Trading
7. KPI methodology
8. balance semantics
9. risk limit NULL fallback policy
10. numeric data quality thresholds
11. strategy/account/version seed extension

## Before Reconciliation / Mature Ops
12. order-book format spec
13. reconciliation tolerances and severity
14. mismatch review/resolution semantics

---

# 7. Final Summary

The peer review surfaced a useful set of remaining cleanup items.

The most important conclusion is:
- implementation can begin now
- but these follow-ups should be resolved before the corresponding phase gates

This document keeps those remaining gaps explicit, phase-aligned, and actionable.
