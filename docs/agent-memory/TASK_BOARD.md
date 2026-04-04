# Task Board

## Current Focus
- make the repository more usable as a complete strategy development / backtest / replay / diagnostics / reporting tool
- keep long-running AI-assisted work resumable without relying on fragile chat-only memory

## In Progress
- connect the new memory workflow to future strategy workbench annotations, compare/review state, and replay investigation surfaces
- add step-level debug trace foundation for replay/backtest diagnosis

## Blocked
- none currently recorded

## Next
- integrate memory workflow with future strategy workbench annotation / review surfaces
- improve compare/analyze maturity with persisted compare-set workflows
- align cooldown semantics to future explicit protection-trigger events

## Recently Done
- exposed compare-review notes in the internal research UI with seeded system-fact inspection plus human/agent note write flow
- implemented the first compare-review note foundation with persisted compare sets, seeded system review drafts, and compare note APIs
- added a dedicated object-level notes/annotations planning spec for compare-review and replay investigation workflows
- added repo-owned VS Code tasks and local PowerShell helpers for memory-session start/stop
- added reusable session-start, session-stop, and CLI/VS Code workflow templates under `docs/agent-memory/`
- formalized the repo-local AI memory and cross-session handoff workflow
- added `docs/agent-memory/` memory artifacts for stable state, task state, decisions, handoff, and session summary
- wired the memory workflow into README, spec index, implementation plan, and Phase 5 checklist
- self-review tracker added and first review findings fixed
- daily-loss guardrail upgraded to session-timezone-aware behavior
- named risk-policy registry foundation added
- named assumption-bundle registry foundation added

## Rule
- keep `In Progress` small
- move durable decisions into `DECISION_LOG.md`
- move cross-session continuation into `HANDOFF.md`
