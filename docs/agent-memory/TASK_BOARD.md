# Task Board

## Current Focus
- make the repository more usable as a complete strategy development / backtest / replay / diagnostics / reporting tool
- keep long-running AI-assisted work resumable without relying on fragile chat-only memory
- keep local Binance BTC data maintenance usable through backfill, cleanup, and dataset-integrity validation workflows

## In Progress
- connect the new memory workflow to future strategy workbench annotations, compare/review state, and replay investigation surfaces
- advance step-level debug traces from the completed Level 2 linkage/UI/anchor/filter slices into replay investigation linkage
- keep the debug-trace rollout explicitly tracked so future sessions can resume from the right slice
- continue the `/monitoring` usability cleanup after the completed launch-form slice so the current research UI becomes easier to operate before larger workbench expansion
- keep the current `/monitoring` console on a deliberate keep/evolve path while reserving the future primary frontend for the replace path
- provide a local runnable BTC history backfill path with visible progress/state because direct Binance execution is blocked in the current harness
- keep the new `/monitoring` integrity-validation surface aligned to the broader Quality workspace plan while deciding whether the next follow-up is dataset-detail polish or BTC backfill status

## Blocked
- none currently recorded

## Next
- integrate memory workflow with future strategy workbench annotation / review surfaces
- continue `UI Phase B` from `docs/frontend-ui-usability-improvement-plan.md` and keep separating launch / compare / runs / investigate work inside Backtests
- keep future product-grade frontend work aligned to `docs/frontend-keep-evolve-replace-strategy.md` instead of expanding `/monitoring` without boundaries
- connect the current trace substrate into replay investigation linkage
- improve compare/analyze maturity with persisted compare-set workflows
- align cooldown semantics to future explicit protection-trigger events
- expose dataset-integrity validation and/or BTC backfill status inside `/monitoring` if the data-quality line becomes the next active slice
- continue the Quality workspace from `docs/quality-integrity-ui-plan.md`, most likely with `UI Slice 4C: BTC Backfill Status Panel`

## Recently Done
- added `docs/quality-integrity-ui-plan.md` to define how bounded integrity validation and BTC backfill status should land inside the current `/monitoring` Quality workspace
- implemented `UI Slice 4A` for the Quality workspace so `/monitoring` now supports bounded integrity validation, quick ranges, dataset summary rows, selected dataset detail, and collapsible raw payload review
- added typed dataset-integrity validation for `gap / duplicate / missing / corrupt` checks, plus persisted integrity findings into `ops.data_quality_checks` and `ops.data_gaps`
- added `POST /api/v1/quality/integrity` plus local `scripts/validate_dataset_integrity.py` and `scripts/validate_dataset_integrity.ps1` entrypoints
- tightened Phase 4 quality tests so integrity fixtures clean up after themselves and no longer leave future-dated contamination behind in the local DB
- added and used a reusable cleanup tool for future-dated local Binance BTC market-data contamination, restoring the raw DB coverage horizon to real timestamps
- added a Windows-friendly `scripts/binance_btc_history_backfill.ps1` wrapper for bootstrap/resume/incremental/status operations on the BTC history backfill tool
- hardened the BTC history incremental mode against future-dated local test rows so checkpoint planning now uses bounded safe coverage instead of raw future timestamps
- upgraded the local BTC history backfill tool with an explicit `--incremental` catch-up mode that derives per-dataset checkpoints from DB coverage
- updated the local BTC history backfill tool so futures `open_interest` is handled as a separately available dataset and failed long runs can resume from `tmp/binance_btc_history_backfill_status.json`
- added `scripts/binance_btc_history_backfill.py` for chunked local backfill of `BTCUSDT_SPOT` and `BTCUSDT_PERP` from `2020-01-01` to YTD, plus rolling status output in `tmp/binance_btc_history_backfill_status.json`
- added a one-click copy icon to the persistent JSON panels across `/monitoring`, covering run payloads, diagnostics, artifacts, compare-note detail, trace detail, and traceability payloads
- moved the Backtests `Signals / Orders / Fills / Timeseries` sections to after the `Investigate` workspace so the page flow reaches diagnostics and traces before execution detail tables
- cleaned up the selected Backtests run detail so the main run payload is now labeled and split into named sections for strategy parameters, execution/protection, risk, assumptions, and runtime metadata before the raw API payload
- added targeted debug-trace filters for blocked-only, risk-code, signal-only, order-only, and fill-only investigation in the API and internal `/monitoring` viewer
- landed the first front-end usability cleanup slice for Backtests: visible launch labels, grouped sections, preset helpers, better boolean controls, workspace headers, and a summary-first selected-run panel
- added a launch-status indicator for Backtests so run submission now shows staged progress, disables the form while running, and auto-focuses the created run on success
- collapsed the launch-page assumption-bundle and risk-policy reference tables behind details panels so the form stays readable by default
- added a dedicated front-end usability improvement plan for cleaning up the current `/monitoring` Backtests experience in phased slices
- added a dedicated keep/evolve/replace frontend strategy so `/monitoring` can be improved without being treated as the final frontend architecture
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
