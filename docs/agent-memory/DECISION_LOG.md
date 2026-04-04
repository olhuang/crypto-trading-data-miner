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
