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
