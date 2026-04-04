# Task Board

## Current Focus
- make the repository more usable as a complete strategy development / backtest / replay / diagnostics / reporting tool
- keep long-running AI-assisted work resumable without relying on fragile chat-only memory

## In Progress
- connect the new memory workflow to future strategy workbench annotations, compare/review state, and replay investigation surfaces
- advance step-level debug traces from the completed Level 2 linkage/UI/anchor/filter slices into replay investigation linkage
- keep the debug-trace rollout explicitly tracked so future sessions can resume from the right slice

## Blocked
- none currently recorded

## Next
- integrate memory workflow with future strategy workbench annotation / review surfaces
- connect the current trace substrate into replay investigation linkage
- improve compare/analyze maturity with persisted compare-set workflows
- align cooldown semantics to future explicit protection-trigger events

## Recently Done
- added targeted debug-trace filters for blocked-only, risk-code, signal-only, order-only, and fill-only investigation in the API and internal `/monitoring` viewer
- connected diagnostics outputs back to concrete trace rows and evidence windows through typed trace anchors plus anchor-driven trace focus in `/monitoring`
- completed the richer Level 2 trace viewer drill-down in `/monitoring` with structured summary, linkage, state-delta, decision, risk, and raw-trace sections
- enriched persisted debug traces with linked simulated order/fill ids, blocked codes, and basic position/cash/equity/exposure deltas for Level 2 backend linkage
- exposed persisted backtest debug traces in the internal `/monitoring` Backtests run detail with a compact table, selected-trace JSON detail, and UI fetch wiring to `/debug-traces`
- implemented Level 1 backend debug traces with schema, repository, runner projection, persisted run support, artifact inventory, and `GET /api/v1/backtests/runs/{run_id}/debug-traces`
- created `docs/debug-trace-rollout-plan.md` to track debug-trace maturity levels, next slice, and resume guidance
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
