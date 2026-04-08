# Project State

## Current Repo Maturity
- Phase 1-4 core scope is implemented and validated.
- Phase 4 now also includes typed dataset-integrity validation for `gap / duplicate / missing / corrupt` checks across the main Binance BTC dataset surfaces, with API and local CLI/PowerShell entrypoints.
- Phase 5 has a working bars-based backtest foundation.
- The repo already supports strategy session config, named risk policies, named assumption bundles, diagnostics summary, period breakdown, persisted compare sets, and compare-review note API baseline.
- `/monitoring` now includes a minimal internal Backtests research slice with compare-review notes, Level 1 debug-trace inspection, Level 2 linkage-aware trace payloads, structured trace drill-down, diagnostics-to-trace anchor navigation, targeted trace filters, and replay-investigation anchor inspection.
- a dedicated front-end usability plan now exists for cleaning up the current `/monitoring` Backtests experience before larger workbench expansion

## Current Strong Areas
- design/spec coverage
- phased implementation planning
- Binance market-data ingestion baseline
- market-data quality, dataset-integrity validation, and replay-readiness baseline
- bars-based backtest, diagnostics, compare foundation, first object-level compare-review memory, replay-investigation anchor substrate, and Level 1/Level 2 trace-backed run inspection
- optimized inner-loop mechanics for the backtest engine allowing fast multi-coin simulation by bypassing redundant state/time evaluations

## Current Gaps
- no replay engine yet
- replay-investigation anchors now exist on persisted debug traces, but replay runs, replay notes, and broader expected-vs-observed evidence workflow are still future work
- compare-review notes now have a minimal internal UI surface, but fuller replay/debug-trace-linked investigation workflow is still future work
- cooldown semantics are still tied to a losing-close proxy instead of explicit protection events
- a dedicated `docs/debug-trace-rollout-plan.md` now exists to track where debug-trace work should resume, and the next debug-trace slice is replay-note/evidence expansion on top of the landed anchor substrate rather than more Level 2 filter work
- dataset-integrity validation now exists in API/CLI/PowerShell form and is surfaced inside `/monitoring`, but the Quality workspace still has follow-up polish/restructure work

## Most Important Source-of-Truth Docs
- `README.md`
- `docs/spec-index.md`
- `docs/implementation-plan.md`
- `docs/phases-2-to-9-checklists.md`
- `docs/strategy-workbench-spec.md`
- `docs/strategy-risk-assumption-management-spec.md`
- `docs/backtest-and-replay-diagnostics-spec.md`
- `docs/repo-self-review-tracker.md`

## Current Working Style
- prefer small, phase-aligned slices
- keep spec / plan / checklist aligned with implementation
- persist important findings into repo-visible docs instead of relying on chat memory

## Current Review Tracker
- active repo-wide findings are tracked in `docs/repo-self-review-tracker.md`

## Notes
- this file should only be updated when repo-wide state changes materially
