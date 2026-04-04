# Handoff

## Current Focus
- use the new AI memory workflow as the default long-horizon repo workflow and connect it to future research/workbench surfaces
- define how object-level notes should carry compare/review and replay investigation memory

## Verified Findings
- the repo already has enough design density that chat-only continuity is not reliable
- `README.md`, `docs/spec-index.md`, `docs/implementation-plan.md`, and `docs/phases-2-to-9-checklists.md` are the stable memory backbone
- `docs/repo-self-review-tracker.md` is the current durable location for repo-wide findings/follow-ups
- a repo-local process spec and canonical memory files now exist under `docs/ai-memory-and-handoff-spec.md` and `docs/agent-memory/`
- reusable operator templates now exist for session start, session stop, and CLI/VS Code launch patterns
- repo-owned VS Code tasks and helper scripts now exist for `Memory: Start Session` and `Memory: Stop Session`
- object-linked compare/review notes and replay investigation notes now have a dedicated planning spec

## Open Problems
- the memory workflow is currently file-based and process-driven, not yet API/UI-backed
- replay/debug trace and compare-set persistence are still future work
- no explicit annotation/review/handoff storage model exists in runtime code yet

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
- `docs/repo-self-review-tracker.md`

## Recommended Next Action
- when continuing this line, implement compare-review note foundation first, then replay investigation notes, and only after that push notes into the future workbench UI
