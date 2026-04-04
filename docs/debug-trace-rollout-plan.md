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

### Not Yet Implemented
- [ ] persisted step-level debug traces
- [ ] backtest debug-trace API
- [ ] backtest debug-trace UI surface
- [ ] trace-to-diagnostics anchors
- [ ] replay investigation trace linkage

### Current Recommended Resume Point
- Start with `Level 1 / Stage B` compact step-level debug trace foundation.

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
- [ ] add DB schema for persisted backtest debug traces
- [ ] add trace repository for insert/list
- [ ] project `BacktestStepResult` into compact trace rows
- [ ] persist traces from the runner for persisted runs
- [ ] add `GET /api/v1/backtests/runs/{run_id}/debug-traces`
- [ ] support `limit`
- [ ] support `unified_symbol`
- [ ] support `bar_time_from`
- [ ] support `bar_time_to`
- [ ] add a minimal `/monitoring` debug-trace table and detail JSON view
- [ ] add automated tests for projection, persistence, and API shape

### Acceptance Checks
- [ ] a persisted run can return trace rows from API
- [ ] trace rows show strategy/execution/risk evidence per bar
- [ ] the internal UI can inspect trace rows without SQL
- [ ] the trace payload stays compact enough for normal development use

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
- [ ] enrich trace schema with linked entity refs and state deltas
- [ ] support filtering by risk code and signal/fill presence
- [ ] add diagnostics-to-trace anchors
- [ ] surface richer drill-down in UI

### Acceptance Checks
- [ ] a drawdown or cost spike can be traced back to concrete step ranges
- [ ] blocked-intent diagnostics can be tied to matching trace rows
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

1. `Level 1 backend foundation`
2. `Level 1 internal UI table/detail`
3. `Level 2 richer trace linkage`
4. `Level 2 richer UI drill-down`
5. `Level 3 replay/investigation trace integration`

Do not skip directly to Level 3.

---

## Recommended Next Slice

If resuming from here, implement only this slice:

### Slice
`Level 1 backend foundation`

### Exact Work
- schema
- repository
- runner projection
- debug-trace read API

### Leave For Immediately After
- internal UI table/detail

### Explicitly Defer
- replay note integration
- diagnostics anchor linking
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
- confirm Level 1 is still the intended next slice
- inspect `runner.py` and current run-detail APIs before editing schema
- keep Level 1 compact; do not over-design replay fields yet
- update `docs/agent-memory/HANDOFF.md` when stopping

---

## Summary

The repository is ready to start `Level 1` step-level debug traces now.

The correct next move is:
- persist compact trace rows for backtest runs
- expose them through API
- then add the first internal UI surface

This keeps the path aligned with future compare/review notes, replay investigation notes, and workbench annotations without forcing a replay-engine redesign too early.
