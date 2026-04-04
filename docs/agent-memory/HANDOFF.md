# Handoff

## Current Focus
- use the new AI memory workflow as the default long-horizon repo workflow and connect it to future research/workbench surfaces
- extend object-level notes from compare-review into trace-backed investigation flows, replay investigation notes, and future workbench annotation surfaces
- continue the debug-trace rollout from the completed Level 2 linkage/UI slice into diagnostics anchors and later replay investigation linkage

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
- Level 1 backend debug traces now exist end-to-end: schema, runner projection, persisted run support, artifact inventory, and `GET /api/v1/backtests/runs/{run_id}/debug-traces`
- Level 1 debug traces are now also exposed in the internal `/monitoring` Backtests run detail through a compact table, selected-trace JSON detail, and minimal trace filters
- Level 2 backend trace linkage now adds linked simulated order/fill ids, blocked codes, and basic position/cash/equity/exposure deltas to persisted trace rows and the trace API
- the internal trace viewer now exposes Level 2 trace evidence through structured summary/linkage/state/decision/risk/raw sections instead of only raw JSON
- `docs/debug-trace-rollout-plan.md` now exists as the dedicated resume document for the next debug-trace slice

## Open Problems
- the memory workflow is currently file-based and process-driven, not yet API/UI-backed
- diagnostics-to-trace anchors are still missing
- replay/debug trace linkage and richer saved-compare workflow are still future work
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
- `db/init/009_backtest_debug_traces.sql`
- `db/init/010_backtest_debug_trace_level2.sql`
- `src/backtest/traces.py`
- `src/backtest/runner.py`
- `src/backtest/artifacts.py`
- `src/storage/repositories/backtest.py`
- `src/api/app.py`
- `docs/repo-self-review-tracker.md`
- `src/backtest/compare_review.py`
- `src/storage/repositories/research.py`
- `db/init/008_compare_sets_and_annotations.sql`
- `frontend/monitoring/index.html`
- `frontend/monitoring/app.js`
- `frontend/monitoring/styles.css`

## Recommended Next Action
- when continuing this line, start from `docs/debug-trace-rollout-plan.md` and implement only the `Level 2` diagnostics-to-trace anchors slice before moving on to replay-note linkage
