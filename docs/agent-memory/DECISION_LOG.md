# Decision Log

## 2026-04-04

### Decision
Adopt a repo-local AI memory workflow based on explicit files under `docs/agent-memory/` rather than relying on chat history or hidden tool state.

### Reason
- this repository already has many layered specs and long-running phased work
- Phase 5 research/backtest work frequently spans multiple sessions
- a visible handoff workflow is more reliable than implicit transcript continuity

### Impact
- future sessions should start by reading stable docs plus the `docs/agent-memory/` files
- important decisions and handoffs should remain visible in the repo

## 2026-04-04

### Decision
Treat AI memory as a layered system: stable project state, active task state, session summary, and explicit handoff.

### Reason
- different information changes at different frequencies
- mixing everything into one file causes stale memory and context pollution

### Impact
- `PROJECT_STATE.md` should stay low-frequency
- `TASK_BOARD.md` / `SESSION_SUMMARY.md` / `HANDOFF.md` should carry the active working state

## 2026-04-04

### Decision
Ship reusable start/stop/operator templates with the repo-local memory workflow instead of leaving the process only as prose in the main spec.

### Reason
- a workflow that exists only as theory is easy to skip
- long-running AI-assisted work becomes more consistent when operators can reuse the same start and stop packets every session

### Impact
- `docs/agent-memory/SESSION_START_PROMPT.md` is the default session-start packet
- `docs/agent-memory/SESSION_STOP_CHECKLIST.md` is the default stop packet
- `docs/agent-memory/WORKFLOW_AUTOMATION_TEMPLATE.md` is the baseline CLI/editor launch reference

## 2026-04-04

### Decision
Ship repo-owned VS Code tasks and PowerShell helper scripts for the memory start/stop workflow instead of leaving execution entirely up to local ad hoc setup.

### Reason
- this makes the workflow immediately usable on this project
- it reduces the chance that operators skip the process because setup is inconvenient
- it preserves a simple local baseline without forcing a specific external AI CLI path

### Impact
- `.vscode/tasks.json` now exposes `Memory: Start Session` and `Memory: Stop Session`
- `scripts/start_memory_session.ps1` and `scripts/stop_memory_session.ps1` are the baseline local workflow helpers

## 2026-04-04

### Decision
Treat compare/review notes and replay investigation notes as object-level memory that complements repo-level handoff rather than replacing it.

### Reason
- repo-level handoff is too coarse once many runs, compare sets, and replay investigations exist
- object-linked notes let research conclusions stay attached to the exact object they describe

### Impact
- repo-level memory remains the session/handoff layer
- future compare/replay/workbench notes should use a shared annotation model and be linked from repo-level handoff when relevant

## 2026-04-04

### Decision
Implement compare-review notes as persisted compare-set identity plus a seeded system review draft before building replay notes or full annotation UI.

### Reason
- compare work already exists in Phase 5, so it is the lowest-risk place to introduce object-linked memory
- seeding a system-fact note first keeps machine facts separate from later human/agent conclusions
- durable compare-set identity is needed before review memory can be resumed across sessions

### Impact
- `POST /api/v1/backtests/compare-sets` now returns a durable `compare_set_id`
- compare creation now seeds a system review note in the generic annotation store
- replay investigation notes can later reuse the same object-level annotation direction instead of inventing a separate notes path

## 2026-04-04

### Decision
Implement Level 1 backtest debug traces as compact, opt-in persisted rows rather than storing full per-step state for every run by default.

### Reason
- persisted runs are already useful without full traces, so trace capture should not make every run materially heavier
- replay/investigation requirements are still evolving, so Level 1 should focus on durable compact evidence instead of prematurely designing a replay engine payload
- compact trace rows are enough to support the next UI/debug slice and future note linkage

### Impact
- persisted runs now support `persist_debug_traces` as an explicit opt-in
- `backtest.debug_traces` stores compact per-step evidence plus small JSON payloads
- the next trace slice should focus on internal UI inspection, not on widening the schema into a replay payload too early

## 2026-04-04

### Decision
Expose Level 1 debug traces in the internal Backtests UI as a compact table plus selected-trace JSON detail instead of skipping directly to charts, anchors, or replay-style timeline controls.

### Reason
- the immediate goal is to make persisted trace evidence inspectable without SQL or raw API calls
- keeping the first UI slice compact preserves the Level 1 design boundary and avoids pulling replay concerns into the current monitoring console too early
- a table/detail pattern is enough to validate the trace substrate before investing in richer drill-down UX

### Impact
- `/monitoring` Backtests run detail now surfaces persisted debug traces with minimal filters
- the next debug-trace slice should focus on richer linkage and diagnostics anchors, not on replacing the current compact UI with a heavy timeline view

## 2026-04-04

### Decision
Implement Level 2 debug-trace linkage by enriching persisted trace rows with linked simulated order/fill ids and compact state-delta fields instead of introducing a second trace table or replay-specific schema.

### Reason
- the existing Level 1 trace table is already the durable substrate for run-level evidence
- linked order/fill ids and small deltas provide immediate diagnostic value without widening the model into a replay engine payload
- keeping Level 2 in the same table preserves compatibility with the current API and internal trace viewer while future diagnostics anchors are still pending

### Impact
- `/api/v1/backtests/runs/{run_id}/debug-traces` now carries linkage/delta evidence that can be reused by later diagnostics anchors and replay-note flows
- the next trace slice should focus on richer UI drill-down and diagnostics anchors rather than another backend-schema redesign

## 2026-04-04

### Decision
Implement the next trace UI slice as a structured drill-down with summary, linkage, state-delta, decision, risk, and raw-trace sections instead of leaving the viewer as a single raw JSON blob.

### Reason
- the Level 2 backend already exposes richer linkage/delta fields, but they are hard to scan when buried in a single payload dump
- a structured detail layout gives immediate diagnostic value without prematurely turning the monitoring console into a replay timeline
- the same sections can become the future landing point for diagnostics anchors and replay-linked evidence

### Impact
- `/monitoring` now exposes Level 2 trace evidence in a more readable per-step drill-down
- the next trace slice should connect diagnostics outputs to these structured sections rather than redesigning the viewer again
