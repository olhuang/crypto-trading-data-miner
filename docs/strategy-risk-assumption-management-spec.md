# Strategy, Risk, and Assumption Management Spec

## Purpose

This document defines how the project should manage:
- strategy identity
- risk policy identity
- assumption bundle identity
- their linkage to sessions, runs, compare/analyze, and later paper/live reuse

It exists because a usable strategy-development and replay/backtest tool needs more than:
- strategy code
- a few run parameters
- one-off risk knobs

Without a clear management model, the system drifts into:
- strategy versions being overloaded to mean fee/risk changes
- risk logic being copied into individual strategies
- assumption differences being hidden inside ad hoc run payloads
- compare/analyze becoming noisy or misleading

This spec complements:
- `docs/strategy-taxonomy-and-versioning-spec.md`
- `docs/backtest-risk-guardrails-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`
- `docs/strategy-workbench-spec.md`
- `docs/position-management-spec.md`
- `docs/ui-api-spec.md`

---

## 1. Core Rule

The platform should treat these as separate managed objects:

1. `strategy`
2. `risk policy`
3. `assumption bundle`
4. `parameter set`

They are related, but they are not interchangeable.

The practical rule is:
- `strategy` defines alpha logic and intended position behavior
- `risk policy` defines hard or semi-hard execution/session guardrails
- `assumption bundle` defines the environment assumptions under which a run is evaluated
- `parameter set` defines strategy-tunable values inside one strategy line

---

## 2. Separation of Concerns

### 2.1 Strategy

Strategy answers:
- what signal or target position should be emitted
- what family / variant / version this logic belongs to
- what input features are required

Strategy should not answer:
- what the global session drawdown stop is
- what the account-level leverage ceiling is
- what fee/slippage assumptions are used for this research run

### 2.2 Risk Policy

Risk policy answers:
- whether a proposed execution intent is allowed
- whether new entries should be blocked after a drawdown, loss, or leverage breach
- whether only reduce-only behavior is allowed in some conditions

Risk policy should not answer:
- what alpha logic the strategy uses
- which family or variant the strategy belongs to
- which fee/slippage/latency bundle is being studied

### 2.3 Assumption Bundle

Assumption bundle answers:
- what fee/slippage/fill/latency assumptions apply
- what risk-policy template or snapshot applies
- what market-data or feature assumptions apply
- what benchmark or compare context applies

Assumption bundle should not answer:
- what alpha logic is inside the strategy
- what immutable strategy version is being promoted

### 2.4 Parameter Set

Parameter set answers:
- how one strategy variant/version is tuned for a run or experiment

Parameter set should not be used as:
- a replacement for version identity
- a replacement for risk policy
- a replacement for assumption bundles

---

## 3. Canonical Object Model

The intended long-lived object model is:

### 3.1 Strategy Registry
- `family`
- `variant`
- `version`

For the current repo:
- current `strategy_code` should continue to mean `variant_code`
- current `strategy_version` should continue to mean immutable `version_code`

### 3.2 Risk Policy Registry

Risk policy should become a named, versionable object.

Recommended identity:
- `risk_policy_code`
- optional `risk_policy_version`

Examples:
- `spot_conservative_v1`
- `perp_medium_v1`
- `perp_aggressive_v1`
- `stress_protection_v1`

Typical contents:
- `max_position_qty`
- `max_order_qty`
- `max_order_notional`
- `max_gross_exposure_multiple`
- `max_drawdown_pct`
- `max_daily_loss_pct`
- `max_leverage`
- `cooldown_bars_after_stop`
- `allow_reduce_only_when_blocked`

### 3.3 Assumption Bundle Registry

Assumption bundles should become named, versionable research templates.

Recommended identity:
- `assumption_bundle_code`
- optional `assumption_bundle_version`

Examples:
- `baseline_perp_research_v1`
- `stress_costs_v1`
- `conservative_execution_v1`

Typical contents:
- `fee_model_version`
- `slippage_model_version`
- `fill_model_version`
- `latency_model_version`
- `risk_policy_reference` or `risk_policy_snapshot`
- `market_data_assumptions`
- `feature/input assumptions`
- `benchmark set`
- `notes / provenance`

### 3.4 Parameter Set

Parameter sets should remain separate research objects.

Examples:
- `short_window=5,long_window=20,target_qty=0.1`
- `tp_bps=80,sl_bps=40`

---

## 4. Binding Model

The system should eventually bind these objects like this:

```text
StrategySession
  -> strategy variant/version
  -> execution policy
  -> protection policy
  -> default risk policy
  -> optional default assumption bundle

Backtest/Paper/Live Run
  -> session snapshot
  -> parameter set
  -> assumption bundle
  -> optional run-level risk overrides
  -> optional run-level assumption overrides
```

This means:
- a session defines the reusable defaults
- a run defines the concrete experiment instance
- the run must persist the final effective snapshot

---

## 5. Precedence Rule

The intended precedence for effective risk/assumption resolution is:

1. system defaults
2. session defaults
3. assumption bundle
4. explicit run-level overrides

The effective snapshot after merge should be:
- deterministic
- persisted with the run
- visible in run detail and compare/analyze output

Rule:
- later layers may override earlier layers explicitly
- hidden implicit overrides are discouraged

---

## 6. System Responsibilities

### 6.1 Registry Layer

The system should eventually provide:
- strategy registry
- risk policy registry
- assumption bundle registry

These registries should support:
- stable identity
- versioning
- metadata and notes
- archival status

### 6.2 Session Layer

`StrategySession` should hold reusable defaults for:
- strategy variant/version
- execution policy
- protection policy
- risk policy
- optional assumption bundle

### 6.3 Run Layer

Each run should persist:
- selected strategy variant/version
- selected or effective risk policy
- selected or effective assumption bundle
- parameter set
- explicit overrides
- resulting diagnostics/artifacts

### 6.4 Compare/Analyze Layer

The system should be able to compare runs by:
- strategy family/variant/version
- risk policy
- assumption bundle
- parameter set
- period/window

This is essential to answer:
- is the result difference caused by alpha
- or by risk
- or by cost/fill assumptions

---

## 7. Persistence Direction

The minimum persistence direction should be:

### Phase 5 / Early Foundation
- persist effective risk-policy snapshot inside run metadata
- preserve assumption-related model versions in run metadata
- keep current ad hoc compare/analyze compatible with future named registries

### Later Foundation
- normalize named risk-policy objects
- normalize named assumption-bundle objects
- store references plus immutable snapshot-at-run-time

Rule:
- the run should preserve both identity and effective snapshot when possible
- mutable registry objects alone are not enough for reproducibility

---

## 8. UI / API Implications

The strategy workbench should eventually expose:

### 8.1 Strategy Selection
- family filter
- variant selection
- version selection

### 8.2 Risk Policy Selection
- choose named risk policy
- inspect policy fields
- optionally override selected fields for one run

### 8.3 Assumption Bundle Selection
- choose named bundle
- inspect included fee/slippage/fill/risk assumptions
- optionally compare bundles across runs

### 8.4 Compare/Analyze

Compare views should eventually show:
- strategy diffs
- risk-policy diffs
- assumption-bundle diffs
- parameter-set diffs

This is required for a usable research tool.

---

## 9. Anti-Patterns To Avoid

Do not:
- encode risk rules inside strategy logic as the canonical place
- create a new strategy version only because fee/risk assumptions changed
- hide assumption changes inside unstructured run notes
- use assumption bundles as a substitute for strategy identity
- let compare/analyze assume two runs are comparable when their assumptions differ materially

---

## 10. Phased Implementation Plan

### Phase A: Spec and Metadata Freeze

Define and freeze:
- strategy / risk / assumption separation
- precedence rule
- required run snapshots
- compare/analyze expectations

Minimum result:
- the docs and checklist define the intended architecture clearly

### Phase B: Run-Snapshot Foundation

Implement:
- effective risk-policy snapshot persistence
- assumption-related model version visibility in run detail
- compare/analyze output remains compatible with risk/assumption diffs

Minimum result:
- the current Phase 5 run model preserves enough metadata to avoid later redesign

### Phase C: Named Risk Policy Registry

Implement:
- named risk-policy registry
- selection by `risk_policy_code`
- optional policy versioning
- UI/API selection surface

Minimum result:
- users can choose and reuse named risk policies instead of copying raw knobs each run

Current foundation status:
- implemented as a code-seeded named risk-policy registry for the current Phase 5 backtest slice
- current API/UI can list available named policies and use `risk_policy_code` as a reusable selection surface
- current runs still persist immutable session/effective risk snapshots so later DB-normalized registry work does not break reproducibility
- optional policy versioning and DB-backed registry normalization remain future work

### Phase D: Assumption Bundle Foundation

Implement:
- named assumption-bundle registry
- bundle linkage to runs
- bundle-aware compare/analyze
- run-level overrides over bundle defaults

Minimum result:
- users can launch and compare runs using reusable research templates

### Phase E: Workbench Compare/Review Maturity

Implement:
- diff surfaces for strategy / risk / assumption / parameter-set
- saved compare sets
- review/promotion evidence grouped by bundle and risk profile

Minimum result:
- the system behaves like a real strategy-development workbench, not a collection of ad hoc run screens

### Phase F: Paper/Live Reuse

Reuse:
- risk-policy semantics
- assumption lineage
- strategy identity

for:
- paper sessions
- live sessions
- reconciliation and deployment audit

Minimum result:
- paper/live do not invent a separate configuration model

---

## 11. Minimum Acceptance Criteria

This spec is actionable when:
- strategy, risk, and assumption responsibilities are explicitly separated
- session/run binding is explicitly defined
- effective snapshot precedence is explicit
- phased implementation is explicit
- compare/analyze implications are explicit

---

## 12. Final Summary

The intended system model is:
- strategy defines alpha behavior
- risk policy defines session/run execution guardrails
- assumption bundle defines research environment assumptions
- sessions bind reusable defaults
- runs persist the final effective snapshot
- compare/analyze explains differences across all three dimensions

This keeps the project extensible and prevents future paper/live/replay work from becoming a patchwork of incompatible configuration paths.
