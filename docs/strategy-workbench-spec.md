# Strategy Workbench Spec

## Purpose

This document defines the product-level facilities needed to make this repository a
usable internal tool for:
- strategy development
- reproducible backtesting
- replay-based investigation
- diagnostics and reporting
- comparison and promotion review

The existing specs already define:
- strategy taxonomy
- strategy input pipeline
- backtest/replay diagnostics
- position and execution architecture

What is still needed is a clear plan for the surrounding **research workbench**
facilities that make those engines practical for daily use.

This spec complements:
- `docs/implementation-plan.md`
- `docs/strategy-taxonomy-and-versioning-spec.md`
- `docs/strategy-input-and-feature-pipeline-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`
- `docs/backtest-and-replay-diagnostics-spec.md`
- `docs/ui-spec.md`
- `docs/ui-api-spec.md`

---

## 1. Core Goal

The project should evolve into an internal strategy workbench where a user can:
1. develop or register a strategy variant/version
2. define parameter sets and assumption bundles
3. launch backtests and replay runs reproducibly
4. inspect reports, diagnostics, and traces
5. compare runs across windows, variants, and assumptions
6. annotate findings and make promotion decisions

The primary success condition is not just that a backtest engine exists.
It is that the user can move from:

```text
idea
  -> implementation
  -> experiment
  -> diagnosis
  -> comparison
  -> replay investigation
  -> review decision
```

without falling back to ad hoc scripts or spreadsheets as the canonical workflow.

---

## 2. Workbench Facilities That Must Exist

To be a good tool for strategy development and replay/backtest diagnostics, the
platform should eventually include all of these facility classes:

### 2.1 Strategy Development Workspace
- draft strategy registration
- local validation and smoke-test workflow
- parameter-set management
- assumption bundle management
- expected-input and expected-output fixtures

### 2.2 Reproducible Run Management
- backtest run creation
- replay run creation
- stable run configuration
- run lineage
- deterministic rerun capability

### 2.3 Diagnostics and Artifact Management
- report outputs
- debug traces
- downloadable/exportable artifact bundle
- anomaly flags
- trace-linked diagnostics

### 2.4 Compare and Analyze Workflow
- run groups
- comparison sets
- period breakdowns
- benchmark comparison
- assumption-diff inspection

### 2.5 Replay Investigation Workflow
- replay scenarios
- bookmarks and event anchors
- expected-vs-observed replay review
- incident replay and golden-case regression

### 2.6 Review and Promotion Workflow
- researcher notes and annotations
- review status
- promotion candidate tracking
- paper/live readiness evidence

---

## 3. Strategy Development Workspace

The workbench should support a clear lifecycle before a strategy becomes a promoted version.

### 3.1 Draft Lifecycle

The platform should preserve room for:
- `draft`
- `candidate`
- `released`
- `archived`

`draft` and `candidate` are research workflow states.
They are not the same as immutable released versions.

### 3.2 Parameter Sets

Named parameter sets should be first-class research objects.

Examples:
- `fast_ma_10_slow_ma_30`
- `tp_80_sl_40`
- `vol_filter_enabled`

Parameter sets should be attachable to:
- runs
- experiments
- compare sets

Parameter sets should not automatically become official released versions.

### 3.3 Assumption Bundles

The workbench should support named assumption bundles covering:
- fee model version
- slippage model version
- fill model version
- feature/input version
- protection rule mode
- benchmark set

This keeps research comparison readable and reproducible.

### 3.4 Validation Fixtures

Strategy development should eventually support:
- small deterministic smoke windows
- synthetic-pattern fixtures
- expected signal snapshots
- golden regression cases

These are essential for diagnosing whether a strategy change is intentional or accidental.

---

## 4. Run Lineage and Reproducibility

Backtest and replay runs should carry enough metadata to be rerun and audited.

### 4.1 Minimum Run Lineage

Each run should eventually preserve:
- strategy family / variant / version
- parameter set identity
- experiment identity
- data window
- symbol/universe
- feature/input version
- fee/slippage/fill model versions
- code commit or build identifier
- environment
- deterministic seed where relevant

### 4.2 Data Snapshot Identity

The workbench should preserve room for a future `data_snapshot_id` or equivalent
lineage field even if the first implementation uses direct DB windows.

This is important because:
- market data changes over time
- quality remediation can rewrite or fill windows
- replay/backtest comparison becomes hard without stable input identity

### 4.3 Rerun Rule

The system should be able to answer:
- can this run be rerun exactly
- if not, what assumption or data lineage changed

---

## 5. Artifact Bundle

Every meaningful run should eventually produce an artifact bundle, not just DB rows.

### 5.1 Artifact Bundle Contents

The bundle should preserve room for:
- run metadata
- KPI summary
- period breakdown summary
- signals extract
- simulated orders/fills extract
- diagnostics summary
- debug trace references or files
- anomaly flags
- optional rendered charts or exported tables

### 5.2 Why This Matters

The artifact bundle becomes the portable evidence package for:
- research review
- replay investigation
- promotion decisions
- regression comparisons

### 5.3 Storage Direction

Short-term:
- DB-backed summary rows plus JSON-heavy artifacts is acceptable

Mid-term:
- explicit artifact references or object-store paths should be supported

---

## 6. Compare and Analyze Workflow

The workbench must make comparison a first-class action, not a manual spreadsheet step.

### 6.1 Research Objects

The platform should preserve room for:
- `experiment`
- `run_group`
- `compare_set`
- `benchmark_set`
- `promotion_review`

### 6.2 Comparison Dimensions

Users should eventually be able to compare by:
- family
- variant
- version
- parameter set
- window
- symbol
- assumption bundle
- benchmark

### 6.3 Comparison Views

At minimum, the future workbench should support:
- side-by-side KPI compare
- assumption diff
- `per year` compare
- `per quarter` compare
- `per month` compare
- benchmark overlay
- diagnostics flag diff

---

## 7. Benchmark and Baseline Library

The workbench should explicitly support benchmark and baseline references.

### 7.1 Baseline Strategy Benchmarks

Examples:
- buy-and-hold
- flat/no-trade baseline
- simple momentum baseline

### 7.2 Market Benchmarks

Examples:
- BTC buy-and-hold
- perp carry benchmark
- passive spot benchmark

### 7.3 Rule

Strategy evaluation should be able to compare:
- against prior versions
- against peer variants
- against baseline/benchmark references

Without this, promotion decisions become too subjective.

---

## 8. Replay Scenario Library

Replay should not be treated only as “run the engine again on old data”.

The workbench should eventually support a scenario library.

### 8.1 Scenario Types

Examples:
- volatility spike
- liquidation cascade
- gap open
- protection-trigger event
- funding flip window
- regime-change sample

### 8.2 Replay Bookmarks

Scenarios should preserve:
- scenario name
- symbol/universe
- time window
- reason for interest
- expected behavior notes
- linked bug or incident if any

### 8.3 Golden Replays

The platform should preserve room for “golden replay” cases:
- known windows
- known expected strategy behavior
- used for regression and incident verification

---

## 9. Diagnostics, Notes, and Review Workflow

Research work is not complete when the run ends.

The workbench should preserve room for:
- annotations on a run
- notes on diagnostics findings
- promotion-review comments
- replay investigation notes
- explicit decision state

Examples:
- `needs_followup`
- `candidate_for_paper`
- `blocked_by_diagnostics`
- `rejected`

This allows the workbench to become a real decision-support tool, not only a run launcher.

---

## 10. UI Expectations

The internal UI should eventually expose a strategy workbench with dedicated surfaces for:

### 10.1 Strategy Lab
- draft strategies
- released variants/versions
- parameter sets
- assumption bundles
- validation fixtures

### 10.2 Experiment Builder
- create experiment
- choose windows/symbols/assumptions
- attach strategy variants/versions
- launch grouped runs

### 10.3 Compare and Analyze
- compare selected runs
- inspect period breakdowns
- inspect benchmark overlays
- inspect diagnostics differences

### 10.4 Replay Scenario Library
- list saved scenarios
- launch replay on scenario
- inspect expected vs observed behavior

### 10.5 Artifact and Diagnostics Explorer
- open run artifact bundle
- inspect diagnostics summary
- inspect traces
- inspect review notes

---

## 11. API Expectations

The backend API should preserve room for future endpoints such as:

### Strategy Workbench
- `GET /api/v1/strategy-drafts`
- `POST /api/v1/strategy-drafts`
- `GET /api/v1/strategy-parameter-sets`
- `GET /api/v1/assumption-bundles`

### Research Orchestration
- `POST /api/v1/backtests/experiments`
- `GET /api/v1/backtests/experiments`
- `GET /api/v1/backtests/run-groups/{group_id}`
- `POST /api/v1/backtests/compare-sets`

### Artifacts and Reviews
- `GET /api/v1/backtests/runs/{run_id}/artifacts`
- `GET /api/v1/backtests/runs/{run_id}/period-breakdown`
- `POST /api/v1/backtests/runs/{run_id}/annotations`
- `POST /api/v1/backtests/reviews`

### Replay Workbench
- `GET /api/v1/replays/scenarios`
- `POST /api/v1/replays/scenarios`
- `GET /api/v1/replays/runs/{run_id}/artifacts`
- `GET /api/v1/replays/runs/{run_id}/expected-vs-observed`

These are planning-level surfaces and do not all need immediate implementation.

---

## 12. Recommended Phase Rollout

### Phase 5A: Workbench Foundation
Implement or plan:
- strategy lab metadata
- parameter sets
- assumption bundles
- run lineage
- artifact bundle baseline
- benchmark/baseline references

### Phase 5B: Research Compare Layer
Add:
- experiment and run-group model
- compare-set workflow
- period breakdown views
- benchmark overlays
- annotations and review state

### Phase 5C: Replay Workbench
Add:
- replay scenario library
- replay bookmarks
- golden replay cases
- expected-vs-observed diagnostics

### Phase 6-7
Reuse:
- review model
- artifact bundle model
- compare/analyze patterns
- variant/version attribution

### Phase 8+
Extend into:
- deployment review
- incident review
- reconciliation-linked replay analysis

---

## 13. Anti-Patterns To Avoid

Do not:
- treat the workbench as only a backtest launcher
- rely on manual spreadsheets as the canonical comparison system
- store important diagnostics only in transient console logs
- let replay scenarios live only in developer memory
- make promotion decisions without artifact-backed evidence
- tie strategy research identity only to raw code file names

---

## 14. Minimum Acceptance Criteria

This plan is actionable when:
- strategy development workflow is separated from released-version identity
- run lineage and artifact expectations are explicit
- comparison and benchmark workflows are first-class
- replay scenarios and golden cases have a planned home
- UI/API expectations for the workbench are explicit

---

## 15. Final Summary

To make this project a genuinely useful strategy-development and replay/backtest
tool, it must provide more than engines and tables.

It also needs a workbench around those engines:
- strategy lab facilities
- reproducible runs
- artifact bundles
- comparison and benchmark workflow
- replay scenarios
- diagnostics and review workflow

This spec should be treated as the planning backbone for making the repository
useful as a complete internal research and diagnostic tool.
