# Debug Trace Rollout Plan

## Purpose

This document tracks the phased implementation path for backtest step-level debug traces so future sessions can quickly answer:
- what is already in place
- what is still missing
- what the next safe implementation slice should be
- where to resume work without re-deriving the plan from chat history

This document is a tracking and handoff companion to:
- `docs/backtest-and-replay-diagnostics-spec.md`
- `docs/object-level-notes-and-annotations-spec.md`
- `docs/strategy-workbench-spec.md`
- `docs/implementation-plan.md`
- `docs/phases-2-to-9-checklists.md`

---

## Why This Exists

The repository already has:
- persisted bars-based backtest runs
- run-level diagnostics summary
- orders / fills / timeseries / signals inspection
- compare-set persistence
- compare-review notes in API and internal UI

The major missing evidence layer is step-level traceability for:
- strategy decisions
- execution intents
- risk guardrail outcomes
- created orders / fills
- per-step portfolio state transitions

Without this layer:
- compare/review notes cannot cite step-level evidence cleanly
- replay investigation notes have no durable per-step substrate
- backtest diagnosis still relies too heavily on aggregate outputs

---

## Current Status

### Implemented Before Debug Traces
- [x] bars-based backtest runner and persistence
- [x] run-level diagnostics summary
- [x] period breakdown and artifact outputs
- [x] run detail endpoints for orders / fills / timeseries / signals
- [x] compare-set persistence
- [x] compare-review note backend
- [x] compare-review note UI in `/monitoring`
- [x] Level 1 backend foundation for persisted compact debug traces
- [x] Level 1 internal debug-trace table/detail in `/monitoring`
- [x] Level 2 richer trace linkage for order/fill refs plus basic position/cash/equity/exposure deltas
- [x] Level 2 richer UI drill-down for structured summary, linkage, and state-delta inspection in `/monitoring`
- [x] Level 2 diagnostics-to-trace anchors across diagnostics API output and the internal trace viewer

### Not Yet Implemented
- [ ] replay investigation trace linkage

### Current Recommended Resume Point
- Continue with `Level 3` replay investigation trace linkage on top of the completed Level 2 filterable trace viewer and diagnostics-anchor foundation.

---

## Phased Rollout

## Level 1: Step-Level Debug Trace Foundation

### Goal
Persist a compact per-step trace row for selected backtest runs so strategy, execution, and risk decisions can be inspected without reconstructing them from aggregate outputs.

### Scope
Each trace row should be compact and queryable, not a full replay engine payload.

### Recommended Stored Fields
- `run_id`
- `step_index`
- `bar_time`
- `unified_symbol`
- `close_price`
- `current_position_qty`
- `signal_count`
- `intent_count`
- `blocked_intent_count`
- `created_order_count`
- `fill_count`
- `cash`
- `equity`
- `drawdown`
- `decision_json`
- `risk_outcomes_json`

### First Implementation Tasks
- [x] add DB schema for persisted backtest debug traces
- [x] add trace repository for insert/list
- [x] project `BacktestStepResult` into compact trace rows
- [x] persist traces from the runner for persisted runs
- [x] add `GET /api/v1/backtests/runs/{run_id}/debug-traces`
- [x] support `limit`
- [x] support `unified_symbol`
- [x] support `bar_time_from`
- [x] support `bar_time_to`
- [x] add a minimal `/monitoring` debug-trace table and detail JSON view
- [x] add automated tests for projection, persistence, and API shape

### Acceptance Checks
- [x] a persisted run can return trace rows from API
- [x] trace rows show strategy/execution/risk evidence per bar
- [x] the internal UI can inspect trace rows without SQL
- [x] the trace payload stays compact enough for normal development use

### Guardrails
- do not store full recent-bar windows in Level 1
- do not try to model intrabar replay in Level 1
- do not block progress on future replay engine details

---

## Level 2: Rich Backtest Trace

### Goal
Expand debug traces from compact per-step facts into richer diagnostic evidence for causal analysis and research comparison.

### Planned Additions
- explicit order-id and fill-id linkage
- protection state deltas
- position delta / exposure delta
- trace filters by signal type, risk code, and fill presence
- diagnostics-flag anchors to specific trace ranges
- more detailed state snapshots where justified

### Tasks
- [x] enrich trace schema with linked entity refs and state deltas
- [x] support filtering by risk code and signal/fill presence
- [x] add diagnostics-to-trace anchors
- [x] surface richer drill-down in UI

### Acceptance Checks
- [ ] a drawdown or cost spike can be traced back to concrete step ranges
- [x] blocked-intent diagnostics can be tied to matching trace rows
- [ ] compare analysis can cite richer trace evidence instead of only aggregate deltas

---

## Level 3: Replay / Investigation Trace

### Goal
Turn backtest traces into the substrate for replay investigation, expected-vs-observed analysis, and future workbench annotation surfaces.

### Planned Additions
- replay timeline objects
- raw/normalized event references
- expected vs observed fields
- trace bookmarks / anchors
- replay investigation note linkage
- scenario/range-based annotation support

### Tasks
- [ ] reuse or extend trace model for replay runs
- [ ] attach trace anchors to replay timelines
- [ ] attach replay investigation notes to trace ranges or bookmarks
- [ ] support expected-vs-observed overlays
- [ ] surface replay investigation trace UI

### Acceptance Checks
- [ ] replay investigations can cite step/timeline evidence directly
- [ ] object-level replay notes link to durable trace anchors
- [ ] future workbench annotation UI has a concrete evidence layer to attach to

---

## Recommended Implementation Order

1. [x] `Level 1 backend foundation`
2. [x] `Level 1 internal UI table/detail`
3. [x] `Level 2 richer trace linkage`
4. [x] `Level 2 richer UI drill-down`
5. [x] `Level 2 diagnostics-to-trace anchors`
6. [x] `Level 2 targeted trace filters`
7. `Level 3 replay/investigation trace integration`

Do not skip directly to Level 3.

---

## Recommended Next Slice

If resuming from here, implement only this slice:

### Slice
`Level 3 replay/investigation trace linkage`

### Exact Work
- reuse the existing debug-trace evidence model for replay investigations
- attach replay-oriented note/linkage objects to concrete trace anchors or time windows
- keep the next slice grounded in the current compact trace substrate instead of redesigning the trace schema again

### Leave For Immediately After
- richer replay timeline polish and follow-up annotation surfaces

### Explicitly Defer
- replay note integration
- rich state-delta model

---

## Files To Inspect When Resuming

### Specs and Tracking
- `docs/backtest-and-replay-diagnostics-spec.md`
- `docs/debug-trace-rollout-plan.md`
- `docs/object-level-notes-and-annotations-spec.md`
- `docs/implementation-plan.md`
- `docs/phases-2-to-9-checklists.md`
- `docs/agent-memory/HANDOFF.md`

### Runtime Code
- `src/backtest/runner.py`
- `src/backtest/diagnostics.py`
- `src/storage/repositories/backtest.py`
- `src/api/app.py`
- `frontend/monitoring/index.html`
- `frontend/monitoring/app.js`
- `frontend/monitoring/styles.css`
- `tests/test_phase5_foundation.py`
- `tests/test_api_models.py`

### UI Follow-On
- `frontend/monitoring/index.html`
- `frontend/monitoring/app.js`
- `frontend/monitoring/styles.css`

---

## Resume Checklist

When returning to this work:
- read this document first
- confirm the next slice is replay investigation trace linkage, not another backend-schema redesign
- inspect `runner.py` and current run-detail APIs before editing schema
- keep Level 1 compact; do not over-design replay fields yet
- update `docs/agent-memory/HANDOFF.md` when stopping

---

## Summary

The repository now has `Level 1` backend/UI debug traces plus the first Level 2 linkage, richer drill-down, diagnostics-anchor slices, and targeted trace filters in place.

The correct next move is:
- connect trace rows to replay-note work and investigation linkage
- then grow that into fuller replay timeline and annotation surfaces later

This keeps the path aligned with future compare/review notes, replay investigation notes, and workbench annotations without forcing a replay-engine redesign too early.
