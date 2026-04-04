# Project State

## Current Repo Maturity
- Phase 1-4 core scope is implemented and validated.
- Phase 5 has a working bars-based backtest foundation.
- The repo already supports strategy session config, named risk policies, named assumption bundles, diagnostics summary, period breakdown, persisted compare sets, and compare-review note API baseline.
- `/monitoring` now includes a minimal internal Backtests research slice.

## Current Strong Areas
- design/spec coverage
- phased implementation planning
- Binance market-data ingestion baseline
- market-data quality and replay-readiness baseline
- bars-based backtest, diagnostics, compare foundation, and first object-level compare-review memory

## Current Gaps
- no replay engine yet
- no step-level debug trace foundation yet
- compare-review notes now have a minimal internal UI surface, but replay/debug-trace-linked investigation workflow is still future work
- cooldown semantics are still tied to a losing-close proxy instead of explicit protection events
- a dedicated `docs/debug-trace-rollout-plan.md` now exists to track where debug-trace work should resume

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
