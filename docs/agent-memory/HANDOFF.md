# Handoff

## Current Focus
- use the new AI memory workflow as the default long-horizon repo workflow and connect it to future research/workbench surfaces
- extend object-level notes from compare-review into step traces, replay investigation notes, and future workbench annotation surfaces

## Verified Findings
- the repo already has enough design density that chat-only continuity is not reliable
- `README.md`, `docs/spec-index.md`, `docs/implementation-plan.md`, and `docs/phases-2-to-9-checklists.md` are the stable memory backbone
- `docs/repo-self-review-tracker.md` is the current durable location for repo-wide findings/follow-ups
- a repo-local process spec and canonical memory files now exist under `docs/ai-memory-and-handoff-spec.md` and `docs/agent-memory/`
- reusable operator templates now exist for session start, session stop, and CLI/VS Code launch patterns
- repo-owned VS Code tasks and helper scripts now exist for `Memory: Start Session` and `Memory: Stop Session`
- object-linked compare/review notes and replay investigation notes now have a dedicated planning spec
- compare sets now persist durable identity in runtime code and seed a system review draft on creation
- compare-review notes now have first object-linked API surfaces at `GET/POST /api/v1/backtests/compare-sets/{compare_set_id}/notes`
- compare-review notes are now exposed in the internal `/monitoring` Backtests research slice, including system-note inspection and human/agent note entry
- `docs/debug-trace-rollout-plan.md` now exists as the dedicated resume document for the next debug-trace slice

## Open Problems
- the memory workflow is currently file-based and process-driven, not yet API/UI-backed
- replay/debug trace and richer saved-compare workflow are still future work
- replay investigation notes and unified annotation service remain future work

## Files To Inspect Next
- `docs/ai-memory-and-handoff-spec.md`
- `docs/agent-memory/PROJECT_STATE.md`
- `docs/agent-memory/TASK_BOARD.md`
- `docs/agent-memory/SESSION_START_PROMPT.md`
- `docs/agent-memory/SESSION_STOP_CHECKLIST.md`
- `docs/agent-memory/WORKFLOW_AUTOMATION_TEMPLATE.md`
- `.vscode/tasks.json`
- `scripts/start_memory_session.ps1`
- `scripts/stop_memory_session.ps1`
- `docs/object-level-notes-and-annotations-spec.md`
- `docs/strategy-workbench-spec.md`
- `docs/strategy-risk-assumption-management-spec.md`
- `docs/backtest-and-replay-diagnostics-spec.md`
- `docs/debug-trace-rollout-plan.md`
- `docs/repo-self-review-tracker.md`
- `src/backtest/compare_review.py`
- `src/storage/repositories/research.py`
- `db/init/008_compare_sets_and_annotations.sql`
- `frontend/monitoring/index.html`
- `frontend/monitoring/app.js`
- `frontend/monitoring/styles.css`

## Recommended Next Action
- when continuing this line, start from `docs/debug-trace-rollout-plan.md` and implement only `Level 1 backend foundation` before moving on to replay-note linkage
