# Testing Strategy Spec

## Purpose

This document defines the testing strategy for the trading platform.

It covers:
- backend tests
- frontend tests
- API contract tests
- database/bootstrap tests
- exchange adapter test strategy
- runtime and reconciliation test strategy

This spec complements:
- `docs/implementation-plan.md`
- `docs/ui-api-spec.md`
- `docs/frontend-architecture-spec.md`
- `docs/backend-system-design.md`

---

## 1. Goals

The test strategy must ensure:
1. schema/bootstrap remains reproducible
2. canonical models and contracts stay stable
3. ingestion and execution logic are validated before live use
4. API and UI remain aligned
5. regressions are caught early by automation

---

## 2. Test Layers

## 2.1 Unit Tests

Use unit tests for:
- model validation
- small pure functions
- normalization logic
- fee/slippage calculations
- PnL/accounting calculations
- risk-decision functions

## 2.2 Integration Tests

Use integration tests for:
- DB persistence/repository behavior
- API endpoint behavior
- job orchestration behavior
- exchange adapter request/response handling against mocks or sandboxes

## 2.3 End-to-End / Workflow Tests

Use end-to-end style tests for:
- bootstrap flow
- ingestion flow from trigger to persisted records
- backtest flow from run request to persisted results
- paper session flow from start to orders/fills/positions
- selected live/sandbox flows where possible

## 2.4 Contract Tests

Use contract tests for:
- UI API response shapes
- canonical payload validation expectations
- backend/frontend integration assumptions

---

## 3. Backend Testing Strategy

## 3.1 Model and Contract Tests

Must cover:
- Pydantic/domain model validation
- required field enforcement
- enum enforcement
- invalid payload rejection behavior

## 3.2 Repository Tests

Must cover:
- inserts and upserts
- deduplication behavior
- uniqueness constraints
- instrument and account lookup behavior

## 3.3 Business Logic Tests

Must cover:
- signal-to-order translation
- pre-trade risk decisions
- order state transitions
- fill processing
- position updates
- accounting/PnL rules

## 3.4 API Tests

Must cover:
- success envelope shape
- error envelope shape
- authorization behavior where applicable
- pagination/filter behavior
- action endpoints returning run/job/session IDs correctly

---

## 4. Database and Bootstrap Testing

## 4.1 Migration Tests

Must verify:
- all schema files apply from empty state
- no migration ordering issues break bootstrap
- repeated local resets do not fail

## 4.2 Seed Tests

Must verify:
- seed file loads successfully
- expected exchanges/assets/instruments exist
- seed is idempotent
- no duplicate rows appear after re-run

## 4.3 Verification Tests

The Phase 1 verification SQL/script should be part of automated validation when practical.

---

## 5. Ingestion Testing Strategy

## 5.1 Normalization Tests

For each exchange payload type, test:
- raw payload to canonical normalized payload mapping
- malformed payload handling
- missing-field error classification

## 5.2 Persistence Tests

Test that normalized ingestion results persist correctly into:
- raw event tables
- normalized market tables
- ops tracking tables

## 5.3 Job Tests

Test:
- successful job execution
- retryable failure handling
- duplicate suppression or idempotent rerun behavior
- progress/status persistence

## 5.4 Data Quality Tests

Test:
- gap detection logic
- freshness check logic
- duplicate anomaly detection logic

---

## 6. Backtest Testing Strategy

## 6.1 Engine Determinism

Backtests must be reproducible with the same:
- strategy version
- parameters
- market data
- fee/slippage settings

## 6.2 Scenario Tests

Test cases should include:
- simple entry/exit scenarios
- partial fill simulations where supported
- fee-only impact validation
- slippage impact validation
- equity curve consistency

## 6.3 Persistence Tests

Verify that backtest outputs persist to all required `backtest.*` tables.

---

## 7. Paper Trading Testing Strategy

## 7.1 Runtime Session Tests

Test:
- session start
- session pause
- session resume
- session stop

## 7.2 Execution Flow Tests

Test:
- signal becomes order
- order events are emitted
- simulated fills update positions and balances
- risk violations block orders correctly

## 7.3 Timing Tests

Test:
- latency metrics are recorded
- session state transitions are visible to API/UI layers

---

## 8. Live Trading and Exchange Adapter Testing Strategy

## 8.1 Adapter Unit and Integration Tests

Test:
- request signing
- parameter normalization
- response normalization
- retryable vs non-retryable failure classification

## 8.2 Sandbox / Testnet Strategy

Where available, prefer exchange sandbox/testnet for:
- order placement test
- cancel test
- balance/position read tests
- execution report handling tests

## 8.3 Mock Strategy

Where sandboxes are unavailable or unreliable, maintain deterministic mocks for:
- REST responses
- private order updates
- fill events
- account state sync

## 8.4 Live Safety Rule

No production-live test should exist that can run accidentally from default local CI or default local commands.

---

## 9. Reconciliation and Accounting Tests

## 9.1 Reconciliation Logic Tests

Test:
- order mismatch detection
- fill mismatch detection
- funding mismatch detection
- ledger mismatch detection

## 9.2 Accounting Tests

Test:
- realized PnL calculation
- unrealized PnL calculation
- fee handling
- funding handling
- position basis updates
- ledger classification rules

---

## 10. Frontend Testing Strategy

## 10.1 Component Tests

Test shared components such as:
- tables
- status badges
- detail drawers
- loading/error/empty states
- form validation behaviors

## 10.2 Page Tests

Test key pages for:
- rendering data states
- form submit flows
- error rendering
- filter interactions
- route parameter handling

## 10.3 Hook / Query Tests

Test:
- query key behavior
- invalidation behavior
- mutation success/error handling
- polling behavior where relevant

---

## 11. API Contract Testing

Because UI and backend are both spec-driven, contract testing is important.

## 11.1 Contract Scope

Test that backend responses match:
- expected envelope shape
- required fields for each endpoint
- consistent status/error conventions

## 11.2 Consumer Safety Goal

Frontend pages should fail less often due to drift between backend response shapes and UI assumptions.

---

## 12. CI Strategy

CI should validate, at minimum:
- lint/format/type checks
- unit tests
- selected integration tests
- DB bootstrap smoke test
- frontend test suite where available

Later, CI may add:
- mock-based end-to-end smoke flows
- API contract validation

---

## 13. Test Data Strategy

Recommended test data layers:
- small deterministic unit-test fixtures
- integration fixtures for DB/repository tests
- canonical example payloads matching `docs/api-contracts.md`
- exchange mock payload fixtures for adapter tests

Avoid fragile tests that depend on unstable public live data.

---

## 14. Environment Separation for Tests

Recommended test environments:
- local unit-test environment
- local integration-test environment with disposable DB
- CI environment with disposable DB/services
- optional sandbox/testnet environment for exchange tests

Production credentials must never be used in default automated tests.

---

## 15. Minimum Critical Test Matrix

At a minimum, the following must eventually be covered:
- bootstrap from empty DB
- seed idempotency
- canonical payload validation
- repository deduplication
- bar backfill happy path
- data quality gap detection
- one reproducible backtest path
- one paper session path
- one exchange adapter order submit/cancel path via mock or sandbox
- PnL/accounting correctness for representative scenarios
- UI rendering of critical operational pages

---

## 16. Ownership Model

Recommended ownership:
- each backend domain owns its unit/integration tests
- shared platform owns CI/bootstrap smoke tests
- frontend domain owners own page/component/hook tests
- exchange adapter owners own sandbox/mock coverage

---

## 17. Test Execution Prioritization

Build coverage in this order:
1. schema/bootstrap tests
2. model/repository tests
3. ingestion normalization/persistence tests
4. backtest determinism tests
5. paper execution tests
6. accounting/risk tests
7. live adapter mock/sandbox tests
8. frontend component/page/API-contract tests

This order aligns with delivery phases and reduces highest-risk regressions first.

---

## 18. Minimum Acceptance Criteria

The testing strategy is sufficiently specified when:
- test layers are defined
- critical backend, frontend, and DB paths are identified
- sandbox/mock strategy for exchange testing is defined
- CI expectations are defined
- minimum critical test matrix is explicit

---

## 19. Final Summary

The recommended testing strategy is layered:
- unit tests for contracts and logic
- integration tests for DB/API/adapter behavior
- workflow tests for major phase-level flows
- contract tests for UI/backend alignment
- CI automation for continuous validation

This is required before the system can be trusted as a live-operable product.