# Handoff

## Current Focus
- use the new AI memory workflow as the default long-horizon repo workflow and connect it to future research/workbench surfaces
- extend object-level notes from compare-review into trace-backed investigation flows, replay investigation notes, and future workbench annotation surfaces
- continue the debug-trace rollout from the completed Level 2 linkage/UI/anchor/filter slices into replay investigation linkage
- continue cleaning up the current `/monitoring` Backtests UX now that the first launch-form cleanup slice has landed
- keep the current internal `/monitoring` console on a clear keep/evolve path without confusing it with the future route-based frontend replacement path

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
- diagnostics summaries now also project typed trace anchors, and the internal UI can use those anchors to focus the trace viewer on matching evidence windows
- the debug-trace API and internal viewer now support targeted investigation filters for blocked-only traces, specific risk codes, signal presence, order presence, and fill presence
- `docs/debug-trace-rollout-plan.md` now exists as the dedicated resume document for the next debug-trace slice
- `docs/frontend-ui-usability-improvement-plan.md` now exists as the dedicated resume document for cleaning up the current Backtests UX in phased slices
- `docs/frontend-keep-evolve-replace-strategy.md` now exists as the dedicated source of truth for how `/monitoring` should be kept, evolved, and eventually complemented by a replacement-grade frontend foundation
- the current `/monitoring` Backtests launch flow now uses visible labels, grouped sections, preset helpers, checkbox/select controls, and a summary-first selected-run panel instead of relying as heavily on placeholder-only inputs and raw JSON first
- the current `/monitoring` Backtests launch flow now also shows an honest launch-status indicator with disabled form state, staged progress, and automatic run selection after a successful launch
- the current `/monitoring` Backtests launch flow now keeps `Available Assumption Bundles` and `Available Risk Policies` in collapsed details panels by default to reduce visual clutter
- the selected Backtests run detail now breaks the run payload into named sections for strategy parameters, execution/protection, risk, assumptions, and runtime metadata before exposing the raw API payload

## Open Problems
- the memory workflow is currently file-based and process-driven, not yet API/UI-backed
- replay/debug trace linkage is still missing
- the current Backtests page is less confusing than before, but it still mixes launch, compare, run inspection, and trace investigation into one larger page instead of a fully separated workspace
- the selected-run workspace is clearer, but the broader page still needs stronger separation between launch, compare, run inspection, and investigation flows
- richer saved-compare workflow remains future work
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
- `docs/frontend-ui-usability-improvement-plan.md`
- `docs/frontend-keep-evolve-replace-strategy.md`
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
- when continuing the UI line, first align with `docs/frontend-keep-evolve-replace-strategy.md`, then continue from `docs/frontend-ui-usability-improvement-plan.md` at `UI Phase B: Backtest Workspace Restructure`, now that selected-run metadata has been split into named summary sections
