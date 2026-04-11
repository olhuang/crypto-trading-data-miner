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

## 2026-04-04

### Decision
Ship reusable start/stop/operator templates with the repo-local memory workflow instead of leaving the process only as prose in the main spec.

### Reason
- a workflow that exists only as theory is easy to skip
- long-running AI-assisted work becomes more consistent when operators can reuse the same start and stop packets every session

### Impact
- `docs/agent-memory/SESSION_START_PROMPT.md` is the default session-start packet
- `docs/agent-memory/SESSION_STOP_CHECKLIST.md` is the default stop packet
- `docs/agent-memory/WORKFLOW_AUTOMATION_TEMPLATE.md` is the baseline CLI/editor launch reference

## 2026-04-04

### Decision
Ship repo-owned VS Code tasks and PowerShell helper scripts for the memory start/stop workflow instead of leaving execution entirely up to local ad hoc setup.

### Reason
- this makes the workflow immediately usable on this project
- it reduces the chance that operators skip the process because setup is inconvenient
- it preserves a simple local baseline without forcing a specific external AI CLI path

### Impact
- `.vscode/tasks.json` now exposes `Memory: Start Session` and `Memory: Stop Session`
- `scripts/start_memory_session.ps1` and `scripts/stop_memory_session.ps1` are the baseline local workflow helpers

## 2026-04-04

### Decision
Treat compare/review notes and replay investigation notes as object-level memory that complements repo-level handoff rather than replacing it.

### Reason
- repo-level handoff is too coarse once many runs, compare sets, and replay investigations exist
- object-linked notes let research conclusions stay attached to the exact object they describe

### Impact
- repo-level memory remains the session/handoff layer
- future compare/replay/workbench notes should use a shared annotation model and be linked from repo-level handoff when relevant

## 2026-04-04

### Decision
Implement compare-review notes as persisted compare-set identity plus a seeded system review draft before building replay notes or full annotation UI.

### Reason
- compare work already exists in Phase 5, so it is the lowest-risk place to introduce object-linked memory
- seeding a system-fact note first keeps machine facts separate from later human/agent conclusions
- durable compare-set identity is needed before review memory can be resumed across sessions

### Impact
- `POST /api/v1/backtests/compare-sets` now returns a durable `compare_set_id`
- compare creation now seeds a system review note in the generic annotation store
- replay investigation notes can later reuse the same object-level annotation direction instead of inventing a separate notes path

## 2026-04-04

### Decision
Implement Level 1 backtest debug traces as compact, opt-in persisted rows rather than storing full per-step state for every run by default.

### Reason
- persisted runs are already useful without full traces, so trace capture should not make every run materially heavier
- replay/investigation requirements are still evolving, so Level 1 should focus on durable compact evidence instead of prematurely designing a replay engine payload
- compact trace rows are enough to support the next UI/debug slice and future note linkage

### Impact
- persisted runs now support `persist_debug_traces` as an explicit opt-in
- `backtest.debug_traces` stores compact per-step evidence plus small JSON payloads
- the next trace slice should focus on internal UI inspection, not on widening the schema into a replay payload too early

## 2026-04-04

### Decision
Expose Level 1 debug traces in the internal Backtests UI as a compact table plus selected-trace JSON detail instead of skipping directly to charts, anchors, or replay-style timeline controls.

### Reason
- the immediate goal is to make persisted trace evidence inspectable without SQL or raw API calls
- keeping the first UI slice compact preserves the Level 1 design boundary and avoids pulling replay concerns into the current monitoring console too early
- a table/detail pattern is enough to validate the trace substrate before investing in richer drill-down UX

### Impact
- `/monitoring` Backtests run detail now surfaces persisted debug traces with minimal filters
- the next debug-trace slice should focus on richer linkage and diagnostics anchors, not on replacing the current compact UI with a heavy timeline view

## 2026-04-04

### Decision
Implement Level 2 debug-trace linkage by enriching persisted trace rows with linked simulated order/fill ids and compact state-delta fields instead of introducing a second trace table or replay-specific schema.

### Reason
- the existing Level 1 trace table is already the durable substrate for run-level evidence
- linked order/fill ids and small deltas provide immediate diagnostic value without widening the model into a replay engine payload
- keeping Level 2 in the same table preserves compatibility with the current API and internal trace viewer while future diagnostics anchors are still pending

### Impact
- `/api/v1/backtests/runs/{run_id}/debug-traces` now carries linkage/delta evidence that can be reused by later diagnostics anchors and replay-note flows
- the next trace slice should focus on richer UI drill-down and diagnostics anchors rather than another backend-schema redesign

## 2026-04-04

### Decision
Implement the next trace UI slice as a structured drill-down with summary, linkage, state-delta, decision, risk, and raw-trace sections instead of leaving the viewer as a single raw JSON blob.

### Reason
- the Level 2 backend already exposes richer linkage/delta fields, but they are hard to scan when buried in a single payload dump
- a structured detail layout gives immediate diagnostic value without prematurely turning the monitoring console into a replay timeline
- the same sections can become the future landing point for diagnostics anchors and replay-linked evidence

### Impact
- `/monitoring` now exposes Level 2 trace evidence in a more readable per-step drill-down
- the next trace slice should connect diagnostics outputs to these structured sections rather than redesigning the viewer again

## 2026-04-04

### Decision
Implement diagnostics-to-trace anchors as typed diagnostics-summary output plus an anchor-driven trace focus flow in the internal UI, rather than inventing a separate diagnostics timeline surface first.

### Reason
- the repository already has a compact trace viewer, so the fastest useful bridge is to let diagnostics point into that viewer
- blocked-intent and guard-trigger evidence is already persisted in debug traces, so anchors can reuse existing evidence without a new trace schema
- this keeps Level 2 additive and avoids dragging replay-specific UI concepts into the current monitoring console too early

### Impact
- `GET /api/v1/backtests/runs/{run_id}/diagnostics` now carries typed `trace_anchors`
- the internal Backtests view can jump from diagnostics anchors into matching trace windows and selected trace rows
- the next trace slice should focus on targeted filters or replay linkage rather than another diagnostics viewer redesign

## 2026-04-04

### Decision
Implement Level 2 targeted trace filters directly on the existing debug-trace API and internal viewer, and make diagnostics-anchor navigation reset conflicting signal/order/fill toggles when focusing blocked-evidence anchors.

### Reason
- the current trace viewer already works as the investigation surface, so the fastest useful improvement is to let users narrow the same endpoint by blocked status, risk code, signal presence, order presence, and fill presence
- blocked/guard-related diagnostics anchors need deterministic navigation, so preserving unrelated `fills_only` or `orders_only` toggles would often hide the very anchor row the user clicked
- this keeps the Level 2 viewer queryable without widening it into a replay-specific UI too early

### Impact
- `GET /api/v1/backtests/runs/{run_id}/debug-traces` now supports targeted filters for blocked traces, specific risk codes, signals, orders, and fills
- the internal Backtests trace viewer now exposes the same filter set and shows the active filters in context
- diagnostics-anchor clicks now align the filter state with blocked-evidence investigation instead of inheriting potentially conflicting trace toggles

## 2026-04-04

### Decision
Plan the next front-end work as a phased usability cleanup of the current `/monitoring` Backtests surface, starting with launch-form cleanup before attempting larger workspace restructuring.

### Reason
- the current Backtests page is functionally rich but mixes launch, compare, run inspection, and trace investigation into one flat scroll
- the most immediate user-facing confusion comes from placeholder-only form fields and unlabeled boolean/debug inputs such as `persist_debug_traces`
- starting with the launch form gives the highest usability gain with the lowest layout risk

### Impact
- `docs/frontend-ui-usability-improvement-plan.md` now tracks the front-end cleanup path
- the next recommended UI slice is `UI Phase A: Launch Form Cleanup`
- broader workspace restructuring should wait until that smaller slice has landed cleanly

## 2026-04-04

### Decision
Adopt a three-part frontend strategy: keep the current `/monitoring` console as the internal ops/research surface, evolve its near-term usability, and replace the long-term product frontend through the planned route-based foundation instead of stretching the static console into that role.

### Reason
- the current console already delivers real internal value and should not be discarded prematurely
- the current static implementation is still too lightweight to serve as the final strategy workbench, replay investigation workspace, and trading console architecture
- separating keep, evolve, and replace reduces the risk of both premature rewrite churn and accidental long-term architectural drift

### Impact
- `docs/frontend-keep-evolve-replace-strategy.md` is now the source of truth for the frontend transition path
- `/monitoring` usability work should continue through the evolve path, starting with `UI Phase A: Launch Form Cleanup`
- future product-grade frontend work should land on the planned route-based foundation instead of accumulating inside `frontend/monitoring/app.js`

## 2026-04-04

### Decision
Handle the requested Binance BTC long-history pull through a repo-local backfill script with a rolling JSON status file, instead of trying to execute the operation inside the current harness.

### Reason
- outbound Binance access is blocked in the current execution harness, so the historical pull cannot complete here
- the repository already has working spot/perp backfill jobs, so packaging them into a local runnable script is safer than inventing a second ingestion path
- the operator also needs visible progress during a long pull, which is better served by a durable status file than by terminal scrollback alone

### Impact
- `scripts/binance_btc_history_backfill.py` is now the canonical local bootstrap entrypoint for `BTCUSDT_SPOT` and `BTCUSDT_PERP`
- `tmp/binance_btc_history_backfill_status.json` is the durable progress artifact while the script is running

## 2026-04-05

### Decision
Treat Binance `openInterestHist` as a separately available dataset inside the BTC history backfill tool, and make the script resumable from its status file.

### Reason
- the first live local run failed because `openInterestHist` rejects early historical `startTime` values with HTTP 400
- funding, mark-price, and index-price history remain useful even when open-interest history is unavailable for older windows
- a long chunked backfill needs resume support so an operator does not have to restart from the beginning after a single endpoint-specific failure

### Impact
- the script now fetches funding, open interest, and mark/index history as separate subcomponents for each monthly futures window
- early windows before the current open-interest availability floor are skipped instead of failing the entire task
- reruns can continue with `--resume-from-status`

## 2026-04-05

### Decision
Add an explicit incremental catch-up mode to the BTC history backfill tool, and treat it as the normal future-monthly update path while keeping `--resume-from-status` as a fallback for interrupted bootstrap runs.

### Reason
- task-count resume is good for recovering a failed long bootstrap, but it is not the right source of truth for future monthly catch-up
- the database already contains durable per-dataset coverage, so incremental fetches should derive their start point from stored data rather than from an old status-file task count
- spot bars, perp bars, funding, open interest, mark prices, and index prices can all move at different cadences and should not share one synthetic resume cursor

### Impact
- `--incremental` now derives a separate start checkpoint for each dataset from DB coverage
- future monthly catch-up runs can use `--incremental` instead of relying on an old bootstrap status file
- `--resume-from-status` remains useful for continuing the current interrupted bootstrap

## 2026-04-05

### Decision
Protect incremental Binance catch-up from future-dated local test contamination by deriving checkpoints from a safe upper-bounded coverage window instead of the raw maximum timestamp.

### Reason
- the local database currently contains a few future-dated BTC test fixtures from quality/remediation tests
- raw `max(timestamp)` values therefore point to `2030/2031`, which would incorrectly suppress real 2026 catch-up tasks
- the backfill tool needs to remain useful even before those future test rows are cleaned out of the local database

### Impact
- coverage summaries now expose both raw `available_to` and bounded `safe_available_to`
- incremental catch-up now uses `safe_available_to` as the checkpoint source
- future-row anomalies are now visible instead of silently poisoning incremental planning

## 2026-04-05

### Decision
Provide a dedicated cleanup utility for future-dated local Binance market-data contamination and use it to remove the current BTC fixture leakage from the local DB.

### Reason
- a few future-dated BTC rows from local test fixtures had already landed in the database and were polluting raw `available_to`
- keeping a reusable cleanup path is safer than relying on ad hoc SQL every time this happens again
- after cleanup, raw coverage should once again match the real stored horizon so operators do not have to mentally translate around anomaly rows

### Impact
- `scripts/cleanup_future_dated_binance_market_data.py` is now the reusable cleanup entrypoint
- the known future-dated Binance BTC rows in `md.bars_1m`, `md.funding_rates`, `md.open_interest`, and `md.mark_prices` have been removed from the local DB

## 2026-04-05

### Decision
Implement dataset-integrity validation as a typed, dataset-aware Phase 4 workflow with API plus local CLI/PowerShell entrypoints, instead of treating integrity checks as ad hoc SQL-only operator work.

### Reason
- operators need a repeatable way to validate `gap / duplicate / missing / corrupt` conditions after backfills and catch-up runs
- interval datasets and event-like datasets need different integrity heuristics, so one generic row-count check would not be reliable enough
- keeping the workflow typed and persisted allows Phase 4 quality artifacts to stay aligned with the rest of the repo's API-first tooling

### Impact
- `POST /api/v1/quality/integrity` now exposes typed integrity validation results
- `scripts/validate_dataset_integrity.py` and `scripts/validate_dataset_integrity.ps1` are the local operator entrypoints
- interval gaps can now persist into `ops.data_gaps`, while duplicate/corrupt/missing integrity findings persist into `ops.data_quality_checks`

## 2026-04-07

### Decision
Optimize the risk engine's per-bar equity calculation by introducing a lightweight incremental `calculate_equity` helper that bypasses full `PortfolioState.mark_to_market` when there are no new execution intents.

### Reason
- The backtest profile revealed `mark_to_market` was scanning all portfolio symbols for every simulated bar, consuming exactly 50% of inner-loop structural overhead simply to check if the session's active equity breached limits.
- Since 99.9% of bars generate zero trading intents, this full instantiation pathway was entirely redundant.

### Impact
- Halved `mark_to_market` global execution frequencies.
- Scales inner loop throughput considerably when a backtest involves a sizable universe of multi-coin pairs over multi-year simulation bounds.

## 2026-04-07

### Decision
Replace heavy `.astimezone()` timezone conversions in the local per-bar loop with predictive float timestamp boundary tracking.

### Reason
- Backtest profiling identified `astimezone` and standard python internal datecasting as an outsized performance hog within `_refresh_session_state`.
- Since timezone bounds operate exactly like fixed UTC cutoffs over rolling 24-hr horizons, checking a single `ts >= target` timestamp float drops the cost to negligible levels.

### Impact
- Obliterated 300,000+ redundant native datetime conversions per 100k bars.
- Cut internal session state processing cycles by over 50%.

## 2026-04-08

### Decision
Treat replay trace-anchor writes as strict nested run resources, and require every anchor write to contain at least one meaningful investigation field.

### Reason
- the anchor write route is nested under `/api/v1/backtests/runs/{run_id}/debug-traces/{debug_trace_id}`, so allowing a `debug_trace_id` from another run would create inconsistent evidence linkage
- empty anchor rows create durable objects with no replay-investigation value and make later annotation cleanup harder

### Impact
- `POST /api/v1/backtests/runs/{run_id}/debug-traces/{debug_trace_id}/investigation-anchors` now returns `404` when the trace does not belong to the addressed run
- anchor writes are now rejected unless at least one of `scenario_id`, `expected_behavior`, or `observed_behavior` is present

## 2026-04-08

### Decision
Implement the first replay investigation-note slice as `debug_trace`-scoped object annotations backed by `research.annotations`, with object-specific convenience endpoints under the existing backtest debug-trace routes.

### Reason
- replay runs and replay timelines do not exist yet, but persisted debug traces and trace anchors already provide a durable evidence substrate
- the repository already has a working generic annotation store plus compare-review note pattern, so reusing that path is lower-risk than introducing a second note store
- this lets expected-vs-observed investigation memory land now without forcing a premature replay-run schema

### Impact
- `GET/POST /api/v1/backtests/runs/{run_id}/debug-traces/{debug_trace_id}/notes` is now the baseline investigation-note surface
- system-seeded trace investigation drafts now preserve step facts, risk evidence, market context, and existing anchors before human/agent conclusions are added
- future replay-run and replay-scenario notes should reuse the same annotation store and extend this evidence-linking pattern rather than replacing it

## 2026-04-08

### Decision
Implement the first expected-vs-observed overview as a run-level aggregation over existing `debug_trace` investigation notes, rather than as a replay-run-specific model.

### Reason
- the repository now has trace-scoped investigation notes, but users still need a quick way to see repeated patterns and unresolved deviations across one run without opening each trace individually
- replay runs and replay timelines are still future work, so a run-level aggregate over existing trace evidence is the lowest-risk way to surface expected-vs-observed review state now
- this preserves continuity with the existing note store and keeps the next replay-timeline slice additive instead of forcing another schema fork

### Impact
- `GET /api/v1/backtests/runs/{run_id}/expected-vs-observed` is now the baseline aggregate view for investigation-note status, type, source, and scenario summaries
- the internal Investigate workspace can now navigate from a run-level note table back into the underlying trace-linked note evidence
- future replay timeline work should enrich this overview with tighter grouping and range/timeline linkage rather than replacing it

## 2026-04-11

### Decision
Extend compare/analyze by projecting diagnostics and runtime-risk diffs directly from the existing run diagnostics projector and persisting those facts inside compare-set snapshots, instead of introducing a separate compare-only diagnostics schema.

### Reason
- the repo already has a typed diagnostics projector with stable risk-summary and flag semantics
- compare needed richer runtime evidence quickly, but adding another schema would duplicate facts and widen maintenance cost
- reusing the diagnostics projector keeps compare, review-note seed facts, and future workbench surfaces aligned to one evidence source

### Impact
- compare sets now expose diagnostics/risk diff fields such as blocked-intent counts, block/outcome counts, guardrail state snapshots, and diagnostic-flag differences
- persisted compare snapshots and seeded compare-review notes now carry those diagnostics/runtime-risk facts for later review flow
- future compare/replay/workbench work should extend this shared diagnostics evidence path rather than fork a parallel compare-specific diagnostics model

## 2026-04-11

### Decision
Scope the first BTC 4H breakout strategy line as a `long-only`, `BTCUSDT_PERP`, 4H-close decision model that uses the existing next-step bars-based market-fill convention, while keeping ATR stop sizing and repeated-loss stop-trading rules strategy-local in `v0.1`.

### Reason
- this matches the current Phase 5 backtest engine honestly without pretending intrabar breakout-entry fidelity
- the current shared guardrail layer is suited for session/account envelope controls, not yet for strategy-specific `R` math or ATR-derived trade management
- a narrower first slice makes the planned ablation matrix interpretable before adding short-side, dated futures, or fuller protection-lifecycle complexity

### Impact
- the new 4H breakout design spec now treats trend/breakout/volatility/perp-context filters and ATR-derived sizing/exits as the first strategy-owned implementation path
- shared risk remains responsible for the existing session envelope controls such as drawdown, leverage, and daily-loss guardrails
- future extensions for short-side support, intrabar breakout simulation, or protection-engine migration should build on this `v0.1` baseline rather than replace it implicitly

## 2026-04-11

### Decision
Keep the BTC 4H breakout strategy's ATR-based sizing strategy-local, but make the first launchable `/monitoring` preset include explicit `max_position_qty` and `max_order_qty` run overrides so the default research path is not silently blocked by the shared `perp_medium_v1` quantity envelope.

### Reason
- the current `perp_medium_v1` shared guardrail defaults are intentionally conservative and are still the right baseline for generic research runs
- the new breakout strategy sizes from `risk_per_trade_pct` and ATR stop distance, which can legitimately propose position sizes above the generic default quantity caps even in honest backtests
- changing the shared policy would broaden risk semantics for unrelated strategies, while a preset-level override keeps the breakout path usable without hiding the underlying guardrail interaction

### Impact
- the `4H Breakout Perp` preset in `/monitoring` now sets `max_position_qty` and `max_order_qty` explicitly
- persisted breakout launch coverage now verifies the strategy can complete an end-to-end run when those overrides are supplied
- future work can revisit whether breakout-specific sizing should migrate into a named shared risk policy, but the current `v0.1` path remains strategy-local plus run override

## 2026-04-11

### Decision
Treat year-plus backtest performance first as a streaming/sorting problem in the shared Phase 5 engine: load bars as per-symbol ordered iterators, merge them in time order, and let the runner consume that already-sorted stream directly instead of forcing a full in-memory `list + sort` pass before execution.

### Reason
- one-year-plus `1m` backtests produce hundreds of thousands of bars per symbol, so an extra full materialization plus global sort adds avoidable memory pressure and startup latency before any strategy logic runs
- this cost is shared by every strategy, not just one specific implementation
- the existing repository path already queries each symbol in time order, so merging those ordered streams preserves correctness while removing duplicated sorting work

### Impact
- `BacktestBarLoader` now has an iterator path for merged ordered bars
- `BacktestRunnerSkeleton.load_and_run()` now consumes the already-sorted iterator directly
- the next performance pass should focus on per-strategy recomputation hotspots and optional persistence-volume reductions rather than revisiting global bar ordering first

## 2026-04-11

### Decision
For high-timeframe strategies built on `1m` input bars, prefer incremental in-strategy bucket maintenance over rebuilding aggregated higher-timeframe history from `recent_bars` on every minute evaluation.

### Reason
- once the shared loader/runner path is streaming, the next year-plus performance hotspot shifts to strategy-local recomputation
- the current 4H breakout strategy was rebuilding the same 4H aggregation repeatedly even though only one minute of new information arrives each step
- incremental bucket maintenance preserves the existing Phase 5 engine contract while cutting repeated work in the hottest strategy path now under development

### Impact
- `btc_4h_breakout_perp` now maintains incremental 4H buckets and tracks the last evaluated closed bucket to avoid duplicate work and duplicate decisions
- future high-timeframe strategies should follow the same incremental pattern or extract a shared helper instead of re-aggregating from full minute history every step
- the next performance pass can focus on persistence/write volume and broader reusable high-timeframe helpers

## 2026-04-11

### Decision
For persisted backtests, create the `backtest.runs` row in `running` state first, stream `performance_timeseries` to storage in chunks during execution, and finalize the run's status/runtime metadata only after the loop completes.

### Reason
- year-plus minute-bar runs can produce very large `performance_points` sequences, and holding the whole list until the end adds avoidable memory pressure on the hottest persisted path
- performance summary metrics only need the latest point plus running max drawdown, so full in-memory retention is unnecessary for persisted runs
- this keeps the existing API/result contract intact for interactive `load_and_run()` usage while making the persisted path more production-like

### Impact
- `load_run_and_persist()` now inserts a pending run, streams timeseries chunks through the repository during execution, and finalizes the run row afterward
- persisted run regressions now verify `running -> finished` lifecycle behavior and chunked timeseries writes
- the next performance pass should focus on remaining persisted write volume such as orders, fills, and optional debug traces rather than on performance-timeseries memory retention

## 2026-04-11

### Decision
For persisted backtests, stream simulated orders, fills, and debug traces during the run whenever possible, and only keep those artifact lists in memory for non-persisted or explicitly inspection-oriented paths.

### Reason
- after streaming `performance_timeseries`, the next large retained objects in trace-heavy year-plus runs were simulated orders, fills, and debug traces
- simulated orders can be inserted on creation and later status-updated on fill/expiry, while fills and debug traces can be persisted as soon as their backing persisted order/fill ids are known
- this preserves the current Phase 5 API behavior while shrinking peak memory for the persisted research path that matters most for long-window execution

### Impact
- `load_run_and_persist()` now writes orders at creation time, updates order status as fills/expiry happen, writes fills as they occur, and writes debug traces step-by-step when trace persistence is enabled
- persisted-run regressions now expect streamed artifact behavior and no longer require the loop result to retain those full artifact lists
- the next optimization pass should focus on reducing total write volume, optional trace sampling/compaction, or batchier insert/update paths rather than on end-of-run artifact retention

## 2026-04-11

### Decision
When persisted backtests already stream artifacts during execution, reduce SQL round-trips in the repository layer by batching debug-trace inserts and order-status updates instead of writing each row individually.

### Reason
- after moving artifact persistence into the run loop, round-trip count became the next clear bottleneck for trace-heavy long-window runs
- debug traces are the highest-volume persisted artifact in investigation-heavy runs, and order-status updates can also accumulate unnecessarily as one-row updates
- batching at the repository layer improves throughput without changing the current Phase 5 API contract or the trace investigation model

### Impact
- `BacktestRunRepository.insert_debug_traces()` now inserts traces in batches while still returning trace ids for investigation flows
- `BacktestRunRepository.update_order_statuses()` now updates statuses in batched SQL instead of row-by-row
- the next optimization pass should focus on optional trace sampling/compaction or broader batch coverage rather than on raw repository round-trip count for these two paths

## 2026-04-11

### Decision
Make the first long-window debug-trace compaction policy "keep all activity, sample quiet background by stride" via `debug_trace_activity_only` plus `debug_trace_stride`, instead of a pure every-Nth-step sampler.

### Reason
- investigation value comes mostly from steps with signals, orders, fills, or blocked intents, so dropping those would make compact mode much less trustworthy
- pure stride-only sampling would reduce volume more aggressively, but it risks deleting exactly the sparse decision points operators care about in long-window runs
- this policy gives a conservative first compaction mode that is easy to explain in the UI and cheap to validate against existing trace workflows

### Impact
- backtest runs can now persist all activity-bearing traces while sampling quiet background bars more sparsely
- persisted run metadata now records the chosen trace sampling options and the resulting captured trace count
- future compaction work should extend this baseline with richer policies or levels rather than replacing the "keep activity first" rule silently

## 2026-04-11

### Decision
Expose debug-trace compaction to operators as named levels (`full`, `compact`, `sparse`) layered on top of the lower-level stride/activity controls, instead of requiring every user to set sampling knobs manually.

### Reason
- long-window performance work is only useful if the resulting controls are easy to choose during real launches
- most users think in terms of "full vs lighter tracing" rather than in terms of stride integers, so preset levels reduce launch friction and make intent clearer in persisted metadata
- keeping the low-level controls underneath preserves flexibility for experiments without making the common path verbose

### Impact
- backtest launch requests can now choose a trace density level directly, with defaults applied automatically to stride/activity behavior
- persisted run metadata and runtime debug-trace summaries now surface both the selected level and the effective sampling behavior
- future compaction work should add new named levels or richer policies in this layer rather than forcing users back to raw low-level tuning for common cases

## 2026-04-11

### Decision
In the `/monitoring` launch UI, selecting a debug-trace level should immediately sync the visible stride/activity fields, and only later direct edits to those fields should count as manual overrides.

### Reason
- backend-only defaults were correct but confusing because the visible form state could disagree with the actual effective run configuration
- operators need the launch form to show which values are currently presets versus overrides, especially when long-window trace volume is part of the tuning workflow
- keeping the sync logic in the UI improves trust without changing the persisted backtest contract

### Impact
- choosing `full`, `compact`, or `sparse` in the launch form now updates the visible stride/activity settings immediately
- built-in presets no longer silently combine a trace level with an unrelated hard-coded stride value by default
- future UI work should preserve this "preset first, explicit override second" behavior for trace controls rather than reintroducing hidden precedence rules

## 2026-04-11

### Decision
In the `/monitoring` launch flow, enabling `Persist Debug Traces` should also enable signal persistence automatically so persisted orders, fills, traces, and diagnostics retain one coherent signal-linkage chain.

### Reason
- debug traces without persisted signals create misleading diagnostics such as `no_signals_generated` and `signal_link_gap` even when the strategy did trade
- investigation and compare workflows are much more useful when traces, orders, and persisted signals all point to the same originating evidence
- this is the more intuitive operator behavior: asking for richer traceability should not silently drop the signal layer that traceability depends on

### Impact
- `/monitoring` backtest launches with `Persist Debug Traces` now send `persist_signals=true`
- diagnostics for trace-enabled runs should no longer show false-positive signal-linkage warnings caused only by the launch payload shape
- future UI work can still expose `persist_signals` explicitly if needed, but the trace-enabled default should remain linked rather than split
