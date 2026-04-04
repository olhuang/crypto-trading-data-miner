# Task Board

## Current Focus
- make the repository more usable as a complete strategy development / backtest / replay / diagnostics / reporting tool
- keep long-running AI-assisted work resumable without relying on fragile chat-only memory

## In Progress
- connect the new memory workflow to future strategy workbench annotations, compare/review state, and replay investigation surfaces

## Blocked
- none currently recorded

## Next
- integrate memory workflow with future strategy workbench annotation / review surfaces
- add step-level debug trace foundation for replay/backtest diagnosis
- improve compare/analyze maturity with persisted compare-set workflows
- align cooldown semantics to future explicit protection-trigger events

## Recently Done
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
