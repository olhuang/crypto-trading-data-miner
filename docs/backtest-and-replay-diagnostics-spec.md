# Backtest and Replay Diagnostics Spec

## Purpose

This document defines the long-lived plan for:
- backtest result reporting
- replay result reporting
- debug trace capture
- diagnostic inspection workflows
- UI support for backtest/replay execution and result analysis

The platform should not treat a backtest or replay run as just:
- one summary row
- one equity curve

Researchers and operators also need:
- explainability
- execution-path visibility
- reproducible diagnostics
- enough trace detail to debug why a run behaved a certain way

This spec complements:
- `docs/implementation-plan.md`
- `docs/position-management-spec.md`
- `docs/strategy-input-and-feature-pipeline-spec.md`
- `docs/strategy-research-and-evaluation-spec.md`
- `docs/object-level-notes-and-annotations-spec.md`
- `docs/ui-spec.md`
- `docs/ui-api-spec.md`

---

## 1. Core Goal

Every backtest or replay workflow should eventually produce two distinct output layers:

1. `report outputs`
2. `debug trace outputs`

Both are required.

The practical rule is:
- reports answer whether a strategy performed well
- debug traces answer why it behaved that way

---

## 2. Why Both Layers Are Required

### 2.1 Report Outputs

Reports are needed for:
- performance review
- comparison
- promotion decisions
- portfolio-level summaries

### 2.2 Debug Trace Outputs

Debug traces are needed for:
- signal-path debugging
- execution-path debugging
- replay-path diagnostics
- mismatch investigation
- explaining surprising PnL or protection behavior

---

## 3. Report Output Model

At minimum, a report-capable run should expose:
- strategy variant/version
- window and universe
- assumptions/versions
- summary KPIs
- timeseries outputs
- order/fill/signal views

Future reporting should also support:
- compare/analyze workflows
- replay-vs-backtest comparison
- object-linked review/investigation notes

---

## 4. Debug Trace Model

Debug traces should be separate from summary reporting.

They should answer:
- what input the strategy saw
- what decision it made
- what execution intent was planned
- what fill/protection logic did next
- how portfolio state changed

Minimum trace stages should eventually include:
- `input_snapshot`
- `feature_snapshot`
- `strategy_decision`
- `execution_intent`
- `fill_decision`
- `protection_state_change`
- `portfolio_projection`

Trace capture should be:
- deterministic
- reproducible
- optional by run configuration

Recommended modes:
- `off`
- `normal`
- `verbose`

Current implementation note:
- the current Phase 5 trace substrate already persists compact step-level trace rows, supports diagnostics anchors plus targeted trace filters, and is used by the internal `/monitoring` Backtests viewer
- the most immediate follow-up is to surface the aligned strategy market context that drove feature-aware or sentiment-aware decisions inside trace inspection

---

## 5. Replay Diagnostics

Replay should answer questions like:
- what happened on this exact historical window if we replay strategy logic
- did the strategy react correctly to a known market event
- did the runtime/protection logic behave as expected

Replay diagnostics should emphasize:
- event ordering
- signal timing
- protection trigger timing
- fill/projection timing
- divergence from expected strategy behavior

Replay outputs should eventually include:
- replay run metadata
- signal timeline
- order/fill timeline
- position/equity timeline
- exception/warning timeline
- step-level debug traces
- object-linked investigation notes and expected-vs-observed review state

---

## 6. Storage Direction

Short-term:
- keep Phase 5 reporting grounded in existing `backtest.*` tables
- allow debug traces to start as optional JSON-heavy outputs or trace artifacts

Mid-term:
- add explicit run-trace persistence or artifact references

Possible future objects:
- `backtest.run_debug_traces`
- `backtest.run_diagnostics`
- `backtest.replay_runs`
- `backtest.replay_debug_traces`

---

## 7. UI Expectations

The UI should eventually support both:
- `run reporting`
- `run diagnostics`

Users should be able to:
- launch a backtest
- inspect run summary
- inspect signals
- inspect orders/fills
- inspect equity/exposure timeseries
- inspect a run-specific diagnostic/debug trace view
- launch or open a replay run
- inspect replay event/state timelines
- inspect replay step traces

The UI should not force users to infer behavior from summary numbers alone.

---

## 8. API Expectations

The backend API should eventually expose:

### Backtest
- run create
- run list
- run detail
- signal list
- order list
- fill list
- timeseries
- diagnostics summary
- debug trace detail/list

### Replay
- replay run create
- replay run list
- replay run detail
- replay event timeline
- replay diagnostics summary
- replay debug trace detail/list

---

## 9. Phase Guidance

### Phase 5

Should provide:
- backtest run reporting baseline
- optional signal inspection
- a plan for debug trace capture
- UI path for run launch and run inspection

It does not need to deliver full replay tooling yet, but it must preserve room for it.

### Phase 6-7

Should extend diagnostics to:
- paper session behavior
- live session behavior
- protection and execution investigation

### Phase 8+

Should align diagnostics with:
- reconciliation
- incident review
- deployment audit

---

## 10. Period Breakdown Expectations

Long-window backtest or replay evaluation should not stop at one aggregate run summary.

The platform should eventually support period-level views for at least:
- `per year`
- `per quarter`
- `per month`

These views are needed to answer:
- whether performance is concentrated in one year or one short regime
- whether recent quarters behave differently from earlier quarters
- whether monthly stability is strong enough for promotion decisions

Future report outputs should preserve enough underlying facts to project:
- return by period
- pnl by period
- drawdown by period
- turnover by period
- fee/slippage cost by period
- signal/fill counts by period

This capability does not need a full UI implementation in the first slice, but it should be
planned explicitly so long-window run analysis does not become an afterthought.

---

## 11. Staged Implementation Rollout

The complete diagnostics/reporting/replay surface should be implemented in stages.

### Stage A: Diagnostics Summary Baseline

Deliver:
- run-level diagnostics summary
- separation between KPI output and diagnostics output
- basic anomaly flags
- enough metadata to support future trace linking

This stage should land inside early Phase 5.

### Stage B: Step Trace Foundation

Deliver:
- step-level trace schema
- trace capture modes (`off`, `normal`, `verbose`)
- trace list/detail API surfaces
- UI drill-down entry from summary flags into traces

This stage should follow once deterministic fills and state projection are stable enough to trace.

Stage B implementation note:
- the compact trace foundation, UI drill-down, diagnostics anchors, and targeted filters are now in place
- the next trace-side extension is a focused `Stage B.5` slice to expose strategy market context in diagnostics/debug-trace inspection before moving deeper into replay linkage

### Stage C: Full Backtest Diagnostics and Period Analysis

Deliver:
- richer fill/protection/portfolio diagnostics
- period-level research outputs:
  - `per year`
  - `per quarter`
  - `per month`
- compare/analyze support for run groups and period-level views
- more opinionated anomaly flags for research/debug use
- compare-review note integration points

This stage completes the backtest-side diagnostics surface.

### Stage D: Replay Diagnostics and UI Completion

Deliver:
- replay run model and replay result persistence
- replay timeline/event/state inspection
- replay-specific diagnostics summary and debug traces
- replay investigation note integration points
- UI support to launch replay runs and inspect replay outputs
- eventual backtest-vs-replay comparison surfaces

This stage completes the replay-specific diagnostic path and the first full UI-backed
inspection flow.

---

## 12. Final Summary

The platform should treat:
- report outputs
- debug trace outputs

as separate but equally important deliverables for backtest and replay workflows.

Backtest/replay result visibility should eventually be available both:
- in stored backend outputs
- in the UI

So users can:
- evaluate performance
- debug behavior
- diagnose anomalies
- trust promotion decisions
