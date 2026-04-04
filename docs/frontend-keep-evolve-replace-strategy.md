# Frontend Keep / Evolve / Replace Strategy

## Purpose

This document defines the repository's three-part frontend strategy:

- `keep`
- `evolve`
- `replace`

The goal is to avoid forcing the current internal `/monitoring` console to become the final product frontend while also avoiding a premature rewrite that would slow down the current Phase 5 research workflow.

This strategy should be read together with:
- `docs/frontend-architecture-spec.md`
- `docs/frontend-foundation-spec.md`
- `docs/frontend-ui-usability-improvement-plan.md`
- `docs/ui-information-architecture.md`

---

## 1. Current Frontend State

The repository currently has:

- a lightweight internal monitoring/research console under `frontend/monitoring/`
- a single-page, static-file implementation centered around `frontend/monitoring/app.js`
- direct API fetches and a simple local state model
- useful Phase 3-5 operational and research functionality already exposed through `/monitoring`

This is a good short-term internal console.
It is **not** the intended long-term frontend foundation for the future strategy workbench, replay investigation workspace, or paper/live trading consoles.

---

## 2. Strategy Summary

The frontend should be managed in three lanes:

### Keep
Preserve and keep using the current `/monitoring` console as the repository's internal operational and research console.

### Evolve
Improve the current `/monitoring` console so it becomes clearer, safer, and easier to use for current internal workflows.

### Replace
Build the future primary product frontend on the planned route-based foundation instead of stretching the current static monitoring console into roles it was not designed to support.

---

## 3. Keep

## 3.1 What To Keep

Keep the following in place:

- `frontend/monitoring/` as the internal operator and engineering console
- direct access to current monitoring, diagnostics, traceability, backtest, compare, and debug workflows
- lightweight deployment through the existing FastAPI-mounted static surface
- the current role of `/monitoring` as a fast internal tool that tracks backend capability as it lands

## 3.2 Why Keep It

Keep this surface because it already provides real value:

- it makes early Phase 3-5 backend slices operable
- it gives internal users a practical way to run and inspect research flows now
- it lets the repo continue to validate APIs and workflows without waiting for the long-term app shell

## 3.3 Keep Boundaries

Keeping `/monitoring` does **not** mean:

- treating `frontend/monitoring/app.js` as the final architecture
- forcing every future UI requirement into one growing static page
- delaying usability improvements because a future rewrite might happen later

---

## 4. Evolve

## 4.1 What Evolve Means

Evolve means improving the current `/monitoring` console for short- and medium-term internal use without pretending it is already the long-term product frontend.

The current evolution track is defined in:
- `docs/frontend-ui-usability-improvement-plan.md`

## 4.2 What Should Evolve

The current `/monitoring` console should continue to evolve in these directions:

- clearer information hierarchy
- smaller, better-labeled forms
- summary-first run detail views
- cleaner separation between launch, compare, inspect, and investigate tasks
- better trace/debug investigation workflow
- better compare/review note surfaces

## 4.3 What Should Not Evolve Here

Do **not** turn `/monitoring` into a pseudo-final app by layering in ad hoc replacements for:

- route-based app navigation
- a reusable feature-module system
- a proper query/cache layer
- broad product-grade state management
- the future main app shell

If a new requirement strongly depends on those capabilities, it belongs in the `replace` path instead.

## 4.4 Evolve Success Criteria

The evolve path is successful if:

- current internal users can run Phase 5 research flows with less confusion
- the Backtests experience becomes easier to operate without a full rewrite
- `/monitoring` remains useful as an internal console even after a future main frontend exists

---

## 5. Replace

## 5.1 What Replace Means

Replace means introducing the intended long-term frontend foundation described in:

- `docs/frontend-architecture-spec.md`
- `docs/frontend-foundation-spec.md`

This future frontend should be:

- route-based
- componentized
- domain-oriented
- backed by a typed API client and shared query patterns
- suitable for longer-lived product-grade workspaces

## 5.2 What Belongs In The Replace Path

The replace path should own the future product-grade UI such as:

- strategy workbench
- replay investigation workspace
- compare/analyze workspace
- paper trading console
- live trading console
- richer account, positions, risk, and reporting pages

## 5.3 Replace Trigger Conditions

Move work into the replace path when one or more of the following become true:

- the UI needs stable multi-route navigation and bookmarkable pages
- multiple complex workspaces need shared reusable components
- data-fetching/query caching becomes a first-class requirement
- user roles, route guards, or stronger page composition become necessary
- the repository needs a true product-facing frontend instead of an internal console

## 5.4 Replace Strategy

The replacement strategy should be additive first:

1. build the new app foundation alongside the current `/monitoring` console
2. place new product-grade surfaces in the new frontend
3. keep `/monitoring` as the internal ops/research console
4. migrate only the workflows that clearly outgrow the old surface

The goal is not to delete `/monitoring`.
The goal is to stop using it as the forced home for every future UI requirement.

---

## 6. Recommended Sequencing

The recommended sequencing is:

### Short Term
- keep `/monitoring`
- evolve the Backtests and investigation UX
- avoid premature rewrite pressure

### Medium Term
- continue current `/monitoring` usability cleanup
- start the real frontend foundation once the first product-grade workspace is ready

### Long Term
- use the new frontend for strategy workbench, replay investigation, and trading consoles
- keep `/monitoring` as an internal operator/debug console

---

## 7. Practical Rule Of Thumb

Use this rule:

- if the work improves today's internal console, it belongs to `evolve`
- if the work requires a true long-term app shell, it belongs to `replace`
- if the work keeps existing internal workflows operational, it belongs to `keep`

In other words:

- **keep the console**
- **evolve the current internal UX**
- **replace the architecture for the future product frontend**

---

## 8. Current Recommended Next Step

The current recommended next step remains:

- start `UI Phase A: Launch Form Cleanup` from `docs/frontend-ui-usability-improvement-plan.md`

This is the highest-value near-term evolve slice and does not conflict with the future replace path.
