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
- continue the Binance futures sentiment-ratio rollout now that data collection/quality are landed and the first strategy/backtest research-consumption slice is in place

## Blocked
- none currently recorded

## Next
- integrate memory workflow with future strategy workbench annotation / review surfaces
- continue `UI Phase B` from `docs/frontend-ui-usability-improvement-plan.md` and keep separating launch / compare / runs / investigate work inside Backtests
- keep future product-grade frontend work aligned to `docs/frontend-keep-evolve-replace-strategy.md` instead of expanding `/monitoring` without boundaries
- connect the current trace substrate into replay investigation linkage
- improve compare/analyze maturity with persisted compare-set workflows
- align cooldown semantics to future explicit protection-trigger events
- decide whether the next sentiment-ratio follow-up is trace/diagnostics context visibility or broader feature-pipeline formalization

## Recently Done
- added `docs/quality-integrity-ui-plan.md` to define how bounded integrity validation and BTC backfill status should land inside the current `/monitoring` Quality workspace
- implemented `UI Slice 4A` for the Quality workspace so `/monitoring` now supports bounded integrity validation, quick ranges, dataset summary rows, selected dataset detail, and collapsible raw payload review
- added typed dataset-integrity validation for `gap / duplicate / missing / corrupt` checks, plus persisted integrity findings into `ops.data_quality_checks` and `ops.data_gaps`
- added `POST /api/v1/quality/integrity` plus local `scripts/validate_dataset_integrity.py` and `scripts/validate_dataset_integrity.ps1` entrypoints
- tightened Phase 4 quality tests so integrity fixtures clean up after themselves and no longer leave future-dated contamination behind in the local DB
- added and used a reusable cleanup tool for future-dated local Binance BTC market-data contamination, restoring the raw DB coverage horizon to real timestamps
- added and used a reusable cleanup tool for legacy off-grid `mark_prices / index_prices` rows, removing 67 polluted rows from each BTC perp dataset and making integrity results interpretable again
- investigated the remaining BTC perp `mark/index` integrity gap, confirmed it was caused by earlier off-grid checkpoint pollution, and added a bounded repair tool plus minute-series checkpoint hardening to prevent recurrence
- investigated the remaining BTC perp `bars_1m` integrity failure, traced it to one corrupt candle plus tail-gap windows, and confirmed the repo-side contamination source was `tests/test_startup_remediation.py`
- fixed `tests/test_startup_remediation.py` so its inserted BTC perp fixture bars now clean themselves up instead of persisting in the local DB
- added and used `scripts/cleanup_startup_remediation_fixture_bars.py`, removing 24 contaminated `BTCUSDT_PERP bars_1m` rows from the local DB
- added bounded repair tooling at `scripts/repair_bars_integrity_windows.py` and `scripts/repair_bars_integrity_windows.ps1` so the corrupt-minute and tail-gap windows can be re-fetched locally without a full backfill
- cleaned up dataset-integrity semantics so interval datasets now classify coverage shortfall and tail shortfall as `warning`, leaving `fail` for true internal gaps, duplicates, and corrupt rows
- updated the `/monitoring -> Quality` integrity UI to surface the new coverage/internal/tail breakdown directly in summary cards, dataset rows, and selected dataset detail
- fixed the integrity API contract so the new warning/coverage/tail fields now reach the UI correctly
- hardened BTC `open_interest` history catch-up so multi-day windows are executed as day-sized refresh calls
- added local `open_interest` debug tooling so operators can inspect raw Binance `openInterestHist` coverage by requested day window
- confirmed through a real local `debug_open_interest_history` run that Binance returns daily `open_interest` windows cleanly from `2026-03-06T00:00:00Z`, so the earlier local late-start coverage was caused by the older catch-up path
- refreshed the default bounded repair windows for `scripts/repair_bars_integrity_windows.py` and `scripts/repair_mark_index_gap.py` so they now match the currently remaining BTC perp integrity failures, including the `2026-04-05T02:30:00Z -> 2026-04-05T02:46:59Z` bars gap
- implemented `UI Slice 4C` for `/monitoring -> Quality`, adding BTC backfill status visibility plus a UI-triggered incremental backfill action backed by API endpoints and a backend service layer
- confirmed the bounded BTC perp repair work is complete enough that integrity is now warning-only for `2026-03-06 -> 2026-04-05`; no true internal gaps/corrupt rows remain in the selected window
- added the first Phase 5 sentiment-ratio research-consumption slice by surfacing perp market context into strategy evaluations through `bars_perp_context_v1`
- seeded `btc_sentiment_momentum@v1.0.0` plus `baseline_perp_sentiment_research@v1`
- added Phase 5 regression coverage proving a runner can trigger a trade from persisted Binance sentiment-ratio context
- updated `/monitoring -> Backtests` so operators can actually launch the sentiment-aware research path through a `Sentiment Perp` preset, strategy selector, threshold fields, and bundle guidance
- added a Windows-friendly `scripts/binance_btc_history_backfill.ps1` wrapper for bootstrap/resume/incremental/status operations on the BTC history backfill tool
- hardened the BTC history incremental mode against future-dated local test rows so checkpoint planning now uses bounded safe coverage instead of raw future timestamps
- upgraded the local BTC history backfill tool with an explicit `--incremental` catch-up mode that derives per-dataset checkpoints from DB coverage
- upgraded the BTC history incremental planner again so it now schedules all detected history gaps plus the live tail for available datasets, instead of only filling forward from the latest checkpoint
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
