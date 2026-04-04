# Backtest Risk Guardrails Spec

## Purpose

This document defines the shared pre-trade guardrail model for backtest runs.

It exists to prevent Phase 5 from drifting into unrealistic replay/backtest behavior where:
- strategies continue opening exposure after equity has effectively failed
- spot runs buy assets with cash they do not have
- gross exposure or order size grows beyond a configured research envelope
- each strategy embeds private risk logic instead of reusing a common execution gate

This spec complements:
- `docs/execution-and-risk-engine-spec.md`
- `docs/position-management-spec.md`
- `docs/risk-limit-fallback-policy.md`
- `docs/strategy-workbench-spec.md`

---

## 1. Goals

The backtest risk-guardrail layer must:
1. sit outside strategy alpha logic
2. run before simulated order creation and fill simulation
3. be configurable per strategy session / run
4. preserve later reuse for paper and live trading
5. expose enough diagnostics that blocked intents are inspectable after a run

---

## 2. Placement in the Phase 5 Pipeline

Recommended order:

1. market data / feature snapshot available
2. strategy emits `signal` and/or `target_position`
3. lifecycle/planner builds `ExecutionIntent`
4. **backtest risk guardrails evaluate each intent**
5. allowed intents become simulated orders
6. fill model simulates fills
7. portfolio/projector updates positions, cash, equity, and reporting

Rule:
- guardrails are a shared execution component
- they are not strategy-owned logic
- they are not part of the fill model

---

## 3. Configuration Model

The first-wave guardrail config belongs to the strategy session:

- `policy_code`
- `enforce_spot_cash_check`
- `block_new_entries_below_equity`
- `max_position_qty`
- `max_order_qty`
- `max_order_notional`
- `max_gross_exposure_multiple`
- `allow_reduce_only_when_blocked`

Recommended placement:
- `StrategySessionConfig.risk_policy`
- optional run-level override later through run config / assumption bundles

Rule:
- session-level policy is the default
- research runs may override it explicitly
- silent implicit strategy-specific risk behavior is discouraged

---

## 4. First-Wave Guardrails

These are the minimum Phase 5 guardrails that should be enforced before simulated order creation.

### 4.1 Equity Floor for New Entries

Field:
- `block_new_entries_below_equity`

Behavior:
- when current equity is at or below the configured floor, new exposure is blocked
- reduce-only exits may still proceed when policy allows

Purpose:
- prevents runs from continuing to open fresh risk after the simulated account is effectively broken

### 4.2 Spot Cash Sufficiency Check

Field:
- `enforce_spot_cash_check`

Behavior:
- for `_SPOT` buy intents that increase exposure, estimated notional plus estimated fees must fit inside current cash
- if not, the intent is blocked

Purpose:
- prevents spot backtests from buying inventory with unavailable cash

First-wave approximation:
- estimate uses current-bar pricing inputs and the configured fee/slippage models
- exact future next-bar execution price is not known at pre-trade time

### 4.3 Max Position Quantity

Field:
- `max_position_qty`

Behavior:
- block intents whose resulting target position exceeds the configured signed-quantity limit

Purpose:
- caps strategy/session size in a simple, deterministic way

### 4.4 Max Order Quantity

Field:
- `max_order_qty`

Behavior:
- block intents whose requested delta quantity exceeds the configured per-order limit

Purpose:
- prevents single-step order bursts that are inconsistent with intended sizing policy

### 4.5 Max Order Notional

Field:
- `max_order_notional`

Behavior:
- block intents whose estimated order notional exceeds the configured limit

Purpose:
- keeps order sizing stable across different price levels

### 4.6 Max Gross Exposure Multiple

Field:
- `max_gross_exposure_multiple`

Behavior:
- block intents whose resulting gross exposure would exceed:
  - `max(current_equity, 0) * max_gross_exposure_multiple`

Purpose:
- gives the first Phase 5 slice a simple leverage / sizing envelope without pretending to be a full venue margin engine

### 4.7 Reduce-Only Bypass

Field:
- `allow_reduce_only_when_blocked`

Behavior:
- if an intent is truly reduce-only, it may be allowed even when another configured limit would otherwise block it

Examples:
- position is above a configured size limit and the strategy is trying to reduce it
- equity floor blocks fresh entries, but exit/reduce orders should still be permitted

First-wave rule:
- the bypass applies only to already reduce-only intents
- the first-wave engine does **not** auto-transform a blocked entry into a reduce-only intent
- auto-clipping and auto-transformation are later-phase behavior

---

## 5. First-Wave Decision Outcomes

Phase 5 first wave supports:
- `allow`
- `block`

The long-term shared vocabulary remains:
- `allow`
- `modify`
- `block`

Rule:
- `modify` is reserved for later clipping / safe-transformation policies
- the first implementation should not silently resize or reshape intent without an explicit later policy

---

## 6. Diagnostics and Reporting Expectations

Blocked risk behavior must not disappear inside the runner.

At minimum, a persisted backtest run should expose:
- evaluated intent count
- allowed intent count
- blocked intent count
- block counts by rule code

Recommended first-wave codes:
- `equity_floor_breach`
- `spot_cash_insufficient`
- `max_position_qty_breach`
- `max_order_qty_breach`
- `max_order_notional_breach`
- `max_gross_exposure_breach`
- `allowed_reduce_only_bypass`

First-wave reporting rule:
- blocked-intent summary belongs in persisted run metadata and diagnostics summary
- full step-level risk traces can wait for later diagnostics stages

---

## 7. Relationship to Strategy, Execution Policy, and Protection

### 7.1 Strategy
- decides desired exposure
- does not own canonical account/session risk enforcement

### 7.2 Execution Policy
- decides how an allowed intent should be turned into orders
- does not replace shared risk guardrails

### 7.3 Protection Policy
- governs TP / SL / related exit logic
- does not replace shared pre-trade sizing and solvency guardrails

Rule:
- strategy, execution policy, protection policy, and risk guardrails are separate concerns

---

## 8. Phase-Aligned Implementation Plan

### Phase 5A: Minimal Shared Backtest Guardrails

Implement:
- `RiskPolicyConfig`
- equity-floor block for new entries
- spot cash sufficiency check
- max position qty
- max order qty
- max order notional
- max gross exposure multiple
- reduce-only bypass for already reduce-only intents
- runtime blocked-intent summary in run diagnostics

### Phase 5B: Session-Level Research Controls

Add:
- run-level risk overrides
- assumption-bundle linkage for risk policy
- explicit run metadata and compare/analyze support for risk assumptions

Current implementation status:
- implemented for run-level risk overrides on the current bars-based backtest path
- implemented for effective risk-policy snapshot persistence in run detail
- implemented for assumption-bundle metadata linkage at the run level
- compare/analyze now preserves room to diff session default risk policy, run-level overrides, and effective risk policy separately
- implemented for a code-seeded named risk-policy registry foundation plus `GET /api/v1/backtests/risk-policies`
- the current internal Backtests UI can inspect and select those named policies before applying run-level overrides
- named assumption-bundle registry and fuller registry normalization remain future work

### Phase 5C / 6A: Richer Session Guardrails

Add:
- `max_drawdown_pct`
- `max_daily_loss_pct`
- `max_leverage`
- `cooldown_bars_after_stop`
- session pause / no-new-entry mode

### Phase 6B / 7A: Shared Risk Reuse for Paper and Live

Reuse the same shared guardrail semantics for:
- paper order creation
- live order creation

Allow environment-specific enrichments such as:
- exchange margin health
- session/runtime pause state
- account trading eligibility

### Later Hardening

Add:
- size clipping / `modify` behavior where explicitly allowed
- concentration limits
- portfolio correlation limits
- shared-account portfolio limits
- environment-specific strict mode

---

## 9. Fallback and Missing-Config Rules

This spec follows `docs/risk-limit-fallback-policy.md`.

Locked first-wave rule:
- missing / null optional limit fields mean "not configured", not zero
- configured rule violations still block
- missing configuration may generate warnings or notes
- strict mandatory-config mode is a later hardening feature

---

## 10. UI and API Implications

Backtest run creation and inspection should expose:
- risk policy snapshot in run detail
- session default risk-policy snapshot where different from effective policy
- run-level risk overrides where present
- assumption-bundle identity where present
- runtime risk summary in run detail / diagnostics
- later compare/analyze should include risk-policy assumption diffs

Recommended UI phases:
- first: API + JSON/detail visibility
- next: run-builder form fields for first-wave risk knobs plus named policy selection
- later: named risk profiles / assumption bundles / compare-set deltas

---

## 11. Anti-Patterns To Avoid

Do not:
- hard-code capital/risk checks inside each strategy
- let backtest runs continue opening fresh exposure after equity failure
- silently resize blocked orders in the first implementation wave
- make backtest risk semantics diverge from future paper/live semantics
- hide blocked intents so diagnostics cannot explain "why no order happened"

---

## 12. Minimum Acceptance Criteria

This spec is actionable when:
- the first-wave guardrails are explicit
- configuration placement is explicit
- diagnostics/reporting expectations are explicit
- Phase 5 through later phases rollout is explicit
- the shared-vs-strategy-owned responsibility boundary is explicit

---

## 13. Final Summary

The intended model is:
- strategy emits desired exposure
- lifecycle/planner creates execution intent
- shared backtest risk guardrails decide whether intent may proceed
- fill simulation happens only after that decision
- blocked intent outcomes remain inspectable through run diagnostics

This lets Phase 5 become more realistic immediately without inventing a separate risk architecture that later paper/live work would need to undo.
