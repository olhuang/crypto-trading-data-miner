const DEFAULT_HEADERS = {};

const state = {
  selectedJobId: null,
  selectedRawEventId: null,
  selectedBacktestRunId: null,
  selectedBacktestDebugTraceId: null,
  selectedCompareSetId: null,
  selectedCompareNoteId: null,
};

const BACKTEST_LAUNCH_PRESETS = {
  baseline_perp: {
    label: "Baseline Perp",
    values: {
      unified_symbol: "BTCUSDT_PERP",
      assumption_bundle_code: "baseline_perp_research",
      assumption_bundle_version: "v1",
      risk_policy_code: "perp_medium_v1",
      short_window: "5",
      long_window: "20",
      target_qty: "0.05",
      allow_short: "false",
      persist_debug_traces: false,
      enforce_spot_cash_check: true,
      allow_reduce_only_when_blocked: true,
    },
  },
  baseline_spot: {
    label: "Baseline Spot",
    values: {
      unified_symbol: "BTCUSDT_SPOT",
      assumption_bundle_code: "baseline_spot_research",
      assumption_bundle_version: "v1",
      risk_policy_code: "spot_conservative_v1",
      short_window: "5",
      long_window: "20",
      target_qty: "0.05",
      allow_short: "false",
      persist_debug_traces: false,
      enforce_spot_cash_check: true,
      allow_reduce_only_when_blocked: true,
    },
  },
  aggressive_perp: {
    label: "Aggressive Perp",
    values: {
      unified_symbol: "BTCUSDT_PERP",
      assumption_bundle_code: "aggressive_perp_execution",
      assumption_bundle_version: "v1",
      risk_policy_code: "perp_aggressive_v1",
      short_window: "3",
      long_window: "12",
      target_qty: "0.08",
      allow_short: "true",
      persist_debug_traces: true,
      enforce_spot_cash_check: true,
      allow_reduce_only_when_blocked: true,
    },
  },
};

function statusClass(value) {
  if (!value) {
    return "";
  }
  return `status-${String(value).replaceAll(" ", "_")}`;
}

function formatValue(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

async function fetchEnvelope(path, query = {}) {
  const url = new URL(path, window.location.origin);
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, value);
    }
  }
  const response = await fetch(url, { headers: DEFAULT_HEADERS });
  const envelope = await response.json();
  if (!response.ok || envelope.success === false) {
    throw new Error(envelope?.error?.message || `Request failed for ${path}`);
  }
  return envelope.data;
}

async function sendEnvelope(path, method, payload) {
  const response = await fetch(path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...DEFAULT_HEADERS,
    },
    body: JSON.stringify(payload),
  });
  const envelope = await response.json();
  if (!response.ok || envelope.success === false) {
    throw new Error(envelope?.error?.message || `Request failed for ${path}`);
  }
  return envelope.data;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) {
    node.textContent = value;
  }
}

function renderTable(targetId, columns, records, onRowClick) {
  const container = document.getElementById(targetId);
  if (!container) {
    return;
  }
  if (!records.length) {
    container.innerHTML = '<div class="json-shell">No records found</div>';
    return;
  }
  const table = document.createElement("table");
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  columns.forEach((column) => {
    const th = document.createElement("th");
    th.textContent = column.label;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  records.forEach((record) => {
    const tr = document.createElement("tr");
    columns.forEach((column) => {
      const td = document.createElement("td");
      const rawValue = record[column.key];
      if (column.type === "status") {
        const badge = document.createElement("span");
        badge.className = `status-pill ${statusClass(rawValue)}`;
        badge.textContent = formatValue(rawValue);
        td.appendChild(badge);
      } else {
        td.textContent = formatValue(rawValue);
      }
      tr.appendChild(td);
    });
    if (onRowClick) {
      tr.addEventListener("click", () => onRowClick(record));
    }
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.innerHTML = "";
  container.appendChild(table);
}

function renderJson(targetId, payload) {
  const container = document.getElementById(targetId);
  if (!container) {
    return;
  }
  container.textContent = JSON.stringify(payload, null, 2);
}

function renderBacktestRunSummary(detail) {
  const container = document.getElementById("backtest-run-summary");
  if (!container) {
    return;
  }
  if (!detail || !detail.run_id) {
    container.innerHTML = '<div class="summary-empty">Select a backtest run row to inspect a summary.</div>';
    return;
  }

  const universe = Array.isArray(detail.universe) ? detail.universe.join(", ") : "";
  const summaryItems = [
    {
      label: "Run",
      value: `#${formatValue(detail.run_id)}`,
      detail: `${formatValue(detail.run_name)} | ${formatValue(detail.status)}`,
    },
    {
      label: "Strategy",
      value: `${formatValue(detail.strategy_code)} @ ${formatValue(detail.strategy_version)}`,
      detail: universe || formatValue(detail.account_code),
    },
    {
      label: "Window",
      value: `${formatValue(detail.start_time)} -> ${formatValue(detail.end_time)}`,
      detail: `TZ ${formatValue(detail.trading_timezone)}`,
    },
    {
      label: "Return",
      value: formatValue(detail.total_return),
      detail: `Annualized ${formatValue(detail.annualized_return)}`,
    },
    {
      label: "Max Drawdown",
      value: formatValue(detail.max_drawdown),
      detail: `Turnover ${formatValue(detail.turnover)}`,
    },
    {
      label: "Costs",
      value: `Fee ${formatValue(detail.fee_cost)}`,
      detail: `Slip ${formatValue(detail.slippage_cost)}`,
    },
  ];

  container.innerHTML = "";
  summaryItems.forEach((item) => {
    const card = document.createElement("article");
    card.className = "summary-card";

    const label = document.createElement("p");
    label.className = "summary-label";
    label.textContent = item.label;

    const value = document.createElement("h4");
    value.textContent = item.value;

    const detailText = document.createElement("p");
    detailText.className = "summary-detail";
    detailText.textContent = item.detail;

    card.appendChild(label);
    card.appendChild(value);
    card.appendChild(detailText);
    container.appendChild(card);
  });
}

function setFormControlValue(control, value) {
  if (!control) {
    return;
  }
  if (control.type === "checkbox") {
    control.checked = Boolean(value);
    return;
  }
  control.value = value === null || value === undefined ? "" : String(value);
}

function applyBacktestPreset(presetKey) {
  const preset = BACKTEST_LAUNCH_PRESETS[presetKey];
  const form = document.getElementById("backtest-launch-form");
  if (!preset || !form) {
    return;
  }

  Object.entries(preset.values).forEach(([fieldName, value]) => {
    const control = form.elements.namedItem(fieldName);
    setFormControlValue(control, value);
  });

  renderJson("backtest-launch-result", {
    preset_applied: preset.label,
    note: "Preset values are loaded into the form and remain editable before launch.",
  });
}

function bindBacktestPresetButtons() {
  document.querySelectorAll("[data-backtest-preset]").forEach((button) => {
    button.addEventListener("click", () => {
      applyBacktestPreset(button.dataset.backtestPreset);
    });
  });
}

function setBacktestLaunchFormBusy(isBusy) {
  const form = document.getElementById("backtest-launch-form");
  if (!form) {
    return;
  }
  form.classList.toggle("is-busy", isBusy);
  form.querySelectorAll("input, select, textarea, button").forEach((element) => {
    element.disabled = isBusy;
  });
  document.querySelectorAll("[data-backtest-preset]").forEach((button) => {
    button.disabled = isBusy;
  });
}

function setBacktestLaunchStatus({ phase, title, detail, progress, stateClass }) {
  const container = document.getElementById("backtest-launch-status");
  const titleNode = document.getElementById("backtest-launch-status-title");
  const phaseNode = document.getElementById("backtest-launch-status-phase");
  const detailNode = document.getElementById("backtest-launch-status-detail");
  const progressNode = document.getElementById("backtest-launch-progress");
  if (!container || !titleNode || !phaseNode || !detailNode || !progressNode) {
    return;
  }

  container.classList.remove("is-running", "is-complete", "is-error");
  if (stateClass) {
    container.classList.add(stateClass);
  }
  titleNode.textContent = title;
  phaseNode.textContent = phase;
  detailNode.textContent = detail;
  progressNode.style.width = `${Math.max(0, Math.min(100, progress || 0))}%`;
}

function renderBacktestDiagnostics(diagnostics) {
  renderJson("backtest-run-diagnostics", diagnostics);

  const anchors = diagnostics.trace_anchors || [];
  const contextParts = [`anchors=${anchors.length}`];
  if (diagnostics.diagnostic_status) {
    contextParts.push(`status=${diagnostics.diagnostic_status}`);
  }
  setText(
    "backtest-diagnostic-anchor-context",
    anchors.length
      ? `${contextParts.join(" | ")} | click an anchor to focus the trace viewer`
      : `${contextParts.join(" | ")} | no trace anchors projected for this run`
  );

  renderTable(
    "backtest-diagnostic-anchors-table",
    [
      { key: "source_kind", label: "Source Kind" },
      { key: "source_code", label: "Source Code" },
      { key: "matched_block_code", label: "Block Code" },
      { key: "step_index", label: "Step" },
      { key: "bar_time", label: "Bar Time" },
      { key: "unified_symbol", label: "Symbol" },
      { key: "related_count", label: "Count" },
    ],
    anchors,
    (anchor) => {
      void focusBacktestTraceAnchor(anchor);
    }
  );
}

async function focusBacktestTraceAnchor(anchor) {
  if (!anchor || !anchor.debug_trace_id) {
    return;
  }
  state.selectedBacktestDebugTraceId = anchor.debug_trace_id;
  const currentFilters = getBacktestTraceFilters();
  const anchorRiskCode =
    anchor.matched_block_code ||
    (anchor.source_kind === "block_summary" ? anchor.source_code : undefined);
  const blockedOnly =
    Boolean(anchorRiskCode) || anchor.source_code === "risk_blocks_present";
  await loadBacktestDebugTraces({
    limit: currentFilters.limit,
    unified_symbol: anchor.unified_symbol || currentFilters.unified_symbol,
    bar_time_from: anchor.bar_time_from,
    bar_time_to: anchor.bar_time_to,
    blocked_only: blockedOnly,
    risk_code: anchorRiskCode,
    signals_only: false,
    fills_only: false,
    orders_only: false,
  });
}

function renderBacktestDebugTraceDetail(trace) {
  if (!trace) {
    renderJson("backtest-debug-trace-summary", {
      message: "Select a debug trace row to inspect detail.",
    });
    renderJson("backtest-debug-trace-linkage", {
      blocked_codes: [],
      sim_order_ids: [],
      sim_fill_ids: [],
    });
    renderJson("backtest-debug-trace-state", {
      current_position_qty: null,
      position_qty_delta: null,
      cash: null,
      cash_delta: null,
      equity: null,
      equity_delta: null,
      gross_exposure: null,
      net_exposure: null,
      drawdown: null,
    });
    renderJson("backtest-debug-trace-decision", {
      message: "Decision payload will appear here.",
    });
    renderJson("backtest-debug-trace-risk", {
      message: "Risk outcomes will appear here.",
    });
    renderJson("backtest-debug-trace-detail", {
      message: "Full raw trace will appear here.",
    });
    return;
  }

  if (!trace.debug_trace_id && trace.message) {
    renderJson("backtest-debug-trace-summary", {
      run_id: trace.run_id || null,
      trace_count: trace.trace_count || 0,
      message: trace.message,
    });
    renderJson("backtest-debug-trace-linkage", {
      blocked_codes: [],
      sim_order_ids: [],
      sim_fill_ids: [],
    });
    renderJson("backtest-debug-trace-state", {
      current_position_qty: null,
      position_qty_delta: null,
      cash: null,
      cash_delta: null,
      equity: null,
      equity_delta: null,
      gross_exposure: null,
      net_exposure: null,
      drawdown: null,
    });
    renderJson("backtest-debug-trace-decision", {
      message: "Decision payload will appear here.",
    });
    renderJson("backtest-debug-trace-risk", {
      message: "Risk outcomes will appear here.",
    });
    renderJson("backtest-debug-trace-detail", trace);
    return;
  }

  renderJson("backtest-debug-trace-summary", {
    debug_trace_id: trace.debug_trace_id,
    step_index: trace.step_index,
    bar_time: trace.bar_time,
    unified_symbol: trace.unified_symbol,
    close_price: trace.close_price,
    signal_count: trace.signal_count,
    intent_count: trace.intent_count,
    blocked_intent_count: trace.blocked_intent_count,
    created_order_count: trace.created_order_count,
    fill_count: trace.fill_count,
  });
  renderJson("backtest-debug-trace-linkage", {
    blocked_codes: trace.blocked_codes || [],
    sim_order_ids: trace.sim_order_ids || [],
    sim_fill_ids: trace.sim_fill_ids || [],
  });
  renderJson("backtest-debug-trace-state", {
    current_position_qty: trace.current_position_qty,
    position_qty_delta: trace.position_qty_delta,
    cash: trace.cash,
    cash_delta: trace.cash_delta,
    equity: trace.equity,
    equity_delta: trace.equity_delta,
    gross_exposure: trace.gross_exposure,
    net_exposure: trace.net_exposure,
    drawdown: trace.drawdown,
  });
  renderJson("backtest-debug-trace-decision", trace.decision_json || {});
  renderJson("backtest-debug-trace-risk", trace.risk_outcomes_json || []);
  renderJson("backtest-debug-trace-detail", trace);
}

function normalizeLineList(value) {
  return String(value || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseBooleanish(value) {
  if (typeof value === "boolean") {
    return value;
  }
  const normalized = String(value || "").trim().toLowerCase();
  return ["1", "true", "yes", "on"].includes(normalized);
}

function getBacktestTraceFilters(formValues = null) {
  const form = document.getElementById("backtest-trace-filter-form");
  const values =
    formValues || (form ? Object.fromEntries(new FormData(form).entries()) : {});
  const parsedLimit = Number(String(values.limit || "").trim() || "100");
  const filters = {
    limit: Number.isInteger(parsedLimit) && parsedLimit > 0 ? parsedLimit : 100,
    unified_symbol: String(values.unified_symbol || "").trim() || undefined,
    risk_code: String(values.risk_code || "").trim() || undefined,
    bar_time_from: String(values.bar_time_from || "").trim() || undefined,
    bar_time_to: String(values.bar_time_to || "").trim() || undefined,
    blocked_only: parseBooleanish(values.blocked_only),
    signals_only: parseBooleanish(values.signals_only),
    fills_only: parseBooleanish(values.fills_only),
    orders_only: parseBooleanish(values.orders_only),
  };
  if (form) {
    form.elements.limit.value = String(filters.limit);
    form.elements.unified_symbol.value = filters.unified_symbol || "";
    form.elements.risk_code.value = filters.risk_code || "";
    form.elements.blocked_only.checked = Boolean(filters.blocked_only);
    form.elements.signals_only.checked = Boolean(filters.signals_only);
    form.elements.fills_only.checked = Boolean(filters.fills_only);
    form.elements.orders_only.checked = Boolean(filters.orders_only);
  }
  return filters;
}

function renderBacktestDebugTraces(runId, debugTraces, appliedFilters) {
  const records = debugTraces.traces || debugTraces.records || [];
  const contextParts = [`run_id=${runId}`];
  const traceCount =
    debugTraces.trace_count !== undefined && debugTraces.trace_count !== null
      ? debugTraces.trace_count
      : records.length;
  if (traceCount !== undefined && traceCount !== null) {
    contextParts.push(`trace_count=${traceCount}`);
  }
  if (appliedFilters?.limit) {
    contextParts.push(`limit=${appliedFilters.limit}`);
  }
  if (appliedFilters?.unified_symbol) {
    contextParts.push(`symbol=${appliedFilters.unified_symbol}`);
  }
  if (appliedFilters?.risk_code) {
    contextParts.push(`risk_code=${appliedFilters.risk_code}`);
  }
  if (appliedFilters?.blocked_only) {
    contextParts.push("blocked_only=true");
  }
  if (appliedFilters?.signals_only) {
    contextParts.push("signals_only=true");
  }
  if (appliedFilters?.orders_only) {
    contextParts.push("orders_only=true");
  }
  if (appliedFilters?.fills_only) {
    contextParts.push("fills_only=true");
  }
  if (appliedFilters?.bar_time_from || appliedFilters?.bar_time_to) {
    contextParts.push(
      `window=${appliedFilters.bar_time_from || "..." } -> ${appliedFilters.bar_time_to || "..."}`
    );
  }
  setText("backtest-debug-trace-context", contextParts.join(" | "));

  const preferredTrace =
    records.find((record) => record.debug_trace_id === state.selectedBacktestDebugTraceId) ||
    records[0] ||
    null;
  state.selectedBacktestDebugTraceId = preferredTrace?.debug_trace_id || null;

  renderTable(
    "backtest-debug-traces-table",
    [
      { key: "step_index", label: "Step" },
      { key: "bar_time", label: "Bar Time" },
      { key: "unified_symbol", label: "Symbol" },
      { key: "signal_count", label: "Signals" },
      { key: "intent_count", label: "Intents" },
      { key: "blocked_intent_count", label: "Blocked" },
      { key: "created_order_count", label: "Orders" },
      { key: "fill_count", label: "Fills" },
      { key: "current_position_qty", label: "Position Qty" },
      { key: "position_qty_delta", label: "Position Delta" },
      { key: "equity_delta", label: "Equity Delta" },
      { key: "gross_exposure", label: "Gross" },
      { key: "drawdown", label: "Drawdown" },
    ],
    records,
    (record) => {
      state.selectedBacktestDebugTraceId = record.debug_trace_id;
      renderBacktestDebugTraceDetail(record);
    }
  );

  if (preferredTrace) {
    renderBacktestDebugTraceDetail(preferredTrace);
  } else {
    renderBacktestDebugTraceDetail({
      run_id: runId,
      trace_count: traceCount || 0,
      message: "No persisted debug traces matched the current filter for this run.",
    });
  }
}

function resetCompareNoteForm() {
  const form = document.getElementById("backtest-compare-note-form");
  if (!form) {
    return;
  }
  form.reset();
  form.elements.annotation_id.value = "";
  form.elements.annotation_type.value = "review";
  form.elements.status.value = "in_review";
  form.elements.note_source.value = "human";
  form.elements.verification_state.value = "verified";
  form.elements.title.value = "";
  form.elements.summary.value = "";
  form.elements.verified_findings.value = "";
  form.elements.open_questions.value = "";
  form.elements.next_action.value = "";
}

function populateCompareNoteForm(note) {
  const form = document.getElementById("backtest-compare-note-form");
  if (!form || !note) {
    return;
  }
  form.elements.annotation_id.value = note.annotation_id || "";
  form.elements.annotation_type.value = note.annotation_type || "review";
  form.elements.status.value = note.status || "in_review";
  form.elements.note_source.value = note.note_source || "human";
  form.elements.verification_state.value = note.verification_state || "verified";
  form.elements.title.value = note.title || "";
  form.elements.summary.value = note.summary || "";
  form.elements.verified_findings.value = (note.verified_findings || []).join("\n");
  form.elements.open_questions.value = (note.open_questions || []).join("\n");
  form.elements.next_action.value = note.next_action || "";
}

function renderCompareResult(compareSet) {
  const runs = compareSet.compared_runs || [];
  const assumptionDiffs = (compareSet.assumption_diffs || []).map((diff) => ({
    field_name: diff.field_name,
    distinct_value_count: diff.distinct_value_count,
    values_by_run: (diff.values_by_run || [])
      .map((value) => `${value.run_id}: ${formatValue(value.value)}`)
      .join(" | "),
  }));
  const benchmarkDeltas = compareSet.benchmark_deltas || [];
  const comparisonFlags = compareSet.comparison_flags || [];
  const contextParts = [];
  if (compareSet.compare_set_id) {
    contextParts.push(`compare_set_id=${compareSet.compare_set_id}`);
  }
  if (compareSet.compare_name) {
    contextParts.push(`name=${compareSet.compare_name}`);
  }
  if (Array.isArray(compareSet.available_period_types) && compareSet.available_period_types.length) {
    contextParts.push(`periods=${compareSet.available_period_types.join(", ")}`);
  }
  setText(
    "backtest-compare-context",
    contextParts.length ? contextParts.join(" | ") : "Create a compare set to inspect review notes."
  );
  renderJson("backtest-compare-result", compareSet);
  renderTable(
    "backtest-compare-runs-table",
    [
      { key: "run_id", label: "Run" },
      { key: "run_name", label: "Run Name" },
      { key: "strategy_code", label: "Strategy" },
      { key: "strategy_version", label: "Version" },
      { key: "diagnostic_status", label: "Diag", type: "status" },
      { key: "total_return", label: "Return" },
      { key: "max_drawdown", label: "Max DD" },
      { key: "turnover", label: "Turnover" },
      { key: "fee_cost", label: "Fees" },
      { key: "slippage_cost", label: "Slip" },
    ],
    runs
  );
  renderTable(
    "backtest-compare-diffs-table",
    [
      { key: "field_name", label: "Field" },
      { key: "distinct_value_count", label: "Distinct" },
      { key: "values_by_run", label: "Values by Run" },
    ],
    assumptionDiffs
  );
  renderTable(
    "backtest-compare-benchmark-table",
    [
      { key: "run_id", label: "Run" },
      { key: "benchmark_run_id", label: "Benchmark" },
      { key: "total_return_delta", label: "Return Delta" },
      { key: "annualized_return_delta", label: "Annualized Delta" },
      { key: "max_drawdown_delta", label: "Max DD Delta" },
      { key: "turnover_delta", label: "Turnover Delta" },
      { key: "win_rate_delta", label: "Win Rate Delta" },
    ],
    benchmarkDeltas
  );
  renderTable(
    "backtest-compare-flags-table",
    [
      { key: "code", label: "Code" },
      { key: "severity", label: "Severity", type: "status" },
      { key: "message", label: "Message" },
    ],
    comparisonFlags
  );
}

async function loadCompareNotes(compareSetId, preferredAnnotationId = null) {
  const notesEnvelope = await fetchEnvelope(`/api/v1/backtests/compare-sets/${compareSetId}/notes`);
  const notes = notesEnvelope.notes || [];
  const preferredNote =
    notes.find((note) => note.annotation_id === preferredAnnotationId) ||
    notes.find((note) => note.annotation_id === state.selectedCompareNoteId) ||
    notes.find((note) => note.note_source !== "system") ||
    notes[0] ||
    null;
  if (preferredNote) {
    state.selectedCompareNoteId = preferredNote.annotation_id;
  }
  renderTable(
    "backtest-compare-notes-table",
    [
      { key: "annotation_id", label: "Note" },
      { key: "annotation_type", label: "Type" },
      { key: "status", label: "Status", type: "status" },
      { key: "note_source", label: "Source", type: "status" },
      { key: "verification_state", label: "Verify", type: "status" },
      { key: "title", label: "Title" },
      { key: "updated_at", label: "Updated" },
    ],
    notes,
    (record) => {
      state.selectedCompareNoteId = record.annotation_id;
      renderJson("backtest-compare-note-detail", record);
      if (record.note_source === "system") {
        resetCompareNoteForm();
      } else {
        populateCompareNoteForm(record);
      }
    }
  );
  if (preferredNote) {
    renderJson("backtest-compare-note-detail", preferredNote);
    if (preferredNote.note_source === "system") {
      resetCompareNoteForm();
    } else {
      populateCompareNoteForm(preferredNote);
    }
  } else {
    state.selectedCompareNoteId = null;
    renderJson("backtest-compare-note-detail", {
      compare_set_id: notesEnvelope.compare_set_id,
      compare_name: notesEnvelope.compare_name,
      notes: [],
    });
    resetCompareNoteForm();
  }
}

async function loadOverview() {
  const [health, qualitySummary, gaps, jobs, streams, replay] = await Promise.all([
    fetchEnvelope("/api/v1/system/health"),
    fetchEnvelope("/api/v1/quality/summary", { latest_only: "true" }),
    fetchEnvelope("/api/v1/quality/gaps", { status: "open", limit: 5 }),
    fetchEnvelope("/api/v1/ingestion/jobs", { limit: 8 }),
    fetchEnvelope("/api/v1/streams/ws-status"),
    fetchEnvelope("/api/v1/replay/readiness"),
  ]);

  setText("health-status", health.app.status);
  setText("health-checked-at", `Checked at ${health.app.checked_at}`);
  setText("quality-total", String(qualitySummary.total_checks));
  setText(
    "quality-breakdown",
    `Passed ${qualitySummary.passed_checks} / Failed ${qualitySummary.failed_checks} / Severe ${qualitySummary.severe_checks}`
  );
  setText("gaps-count", String(gaps.records.length));
  setText(
    "gaps-detail",
    gaps.records[0] ? `${gaps.records[0].data_type} ${gaps.records[0].unified_symbol || ""}` : "No open gaps"
  );
  setText("replay-status", `${replay.raw_coverage_status} / ${replay.normalized_coverage_status}`);
  setText("replay-detail", `Known gaps ${replay.known_gaps}; streams ${replay.retained_streams.length}`);

  renderTable(
    "overview-jobs",
    [
      { key: "service_name", label: "Service" },
      { key: "status", label: "Status", type: "status" },
      { key: "unified_symbol", label: "Symbol" },
      { key: "records_written", label: "Rows" },
    ],
    jobs.records
  );

  renderTable(
    "overview-streams",
    [
      { key: "service_name", label: "Service" },
      { key: "exchange_code", label: "Exchange" },
      { key: "channel", label: "Channel" },
      { key: "connection_status", label: "Status", type: "status" },
      { key: "last_message_time", label: "Last Message" },
    ],
    streams.streams
  );
}

async function loadJobs(filters = {}) {
  const jobs = await fetchEnvelope("/api/v1/ingestion/jobs", { limit: 30, ...filters });
  renderTable(
    "jobs-table",
    [
      { key: "job_id", label: "Job" },
      { key: "service_name", label: "Service" },
      { key: "data_type", label: "Data Type" },
      { key: "status", label: "Status", type: "status" },
      { key: "exchange_code", label: "Exchange" },
      { key: "unified_symbol", label: "Symbol" },
      { key: "records_written", label: "Rows" },
      { key: "started_at", label: "Started" },
    ],
    jobs.records,
    async (record) => {
      state.selectedJobId = record.job_id;
      const detail = await fetchEnvelope(`/api/v1/ingestion/jobs/${record.job_id}`);
      renderJson("job-detail", detail);
    }
  );
}

function parseBooleanInput(value) {
  return ["1", "true", "yes", "on"].includes(String(value || "").trim().toLowerCase());
}

async function loadBacktests(filters = {}) {
  await loadBacktestAssumptionBundles();
  await loadBacktestRiskPolicies();
  const runs = await fetchEnvelope("/api/v1/backtests/runs", { limit: 30, ...filters });
  renderTable(
    "backtest-runs-table",
    [
      { key: "run_id", label: "Run" },
      { key: "run_name", label: "Run Name" },
      { key: "strategy_code", label: "Strategy" },
      { key: "strategy_version", label: "Version" },
      { key: "status", label: "Status", type: "status" },
      { key: "account_code", label: "Account" },
      { key: "total_return", label: "Return" },
      { key: "created_at", label: "Created" },
    ],
    runs.runs,
    (record) => loadSelectedBacktestRun(record.run_id)
  );
}

async function loadSelectedBacktestRun(runId) {
  state.selectedBacktestRunId = runId;
  state.selectedBacktestDebugTraceId = null;
  const traceFilters = getBacktestTraceFilters();
  const [detail, diagnostics, artifacts, breakdown, signals, orders, fills, timeseries, debugTraces] =
    await Promise.all([
      fetchEnvelope(`/api/v1/backtests/runs/${runId}`),
      fetchEnvelope(`/api/v1/backtests/runs/${runId}/diagnostics`),
      fetchEnvelope(`/api/v1/backtests/runs/${runId}/artifacts`),
      fetchEnvelope(`/api/v1/backtests/runs/${runId}/period-breakdown`, { period_type: "month" }),
      fetchEnvelope(`/api/v1/backtests/runs/${runId}/signals`, { limit: 50 }),
      fetchEnvelope(`/api/v1/backtests/runs/${runId}/orders`, { limit: 50 }),
      fetchEnvelope(`/api/v1/backtests/runs/${runId}/fills`, { limit: 50 }),
        fetchEnvelope(`/api/v1/backtests/runs/${runId}/timeseries`, { limit: 120 }),
        fetchEnvelope(`/api/v1/backtests/runs/${runId}/debug-traces`, traceFilters),
      ]);
  renderBacktestRunSummary(detail);
  renderJson("backtest-run-detail", detail);
  renderBacktestDiagnostics(diagnostics);
  renderJson("backtest-run-artifacts", artifacts);
  renderTable(
    "backtest-period-breakdown",
    [
      { key: "period_start", label: "Period Start" },
      { key: "period_end", label: "Period End" },
      { key: "total_return", label: "Return" },
      { key: "max_drawdown", label: "Max DD" },
      { key: "turnover", label: "Turnover" },
      { key: "signal_count", label: "Signals" },
      { key: "fill_count", label: "Fills" },
    ],
    breakdown.entries || []
  );
  renderTable(
    "backtest-signals-table",
    [
      { key: "signal_time", label: "Signal Time" },
      { key: "unified_symbol", label: "Symbol" },
      { key: "signal_type", label: "Type", type: "status" },
      { key: "direction", label: "Direction" },
      { key: "target_qty", label: "Target Qty" },
      { key: "reason_code", label: "Reason" },
    ],
    signals.signals || []
  );
  renderTable(
    "backtest-orders-table",
    [
      { key: "order_time", label: "Order Time" },
      { key: "unified_symbol", label: "Symbol" },
      { key: "side", label: "Side", type: "status" },
      { key: "order_type", label: "Type" },
      { key: "price", label: "Price" },
      { key: "qty", label: "Qty" },
      { key: "status", label: "Status", type: "status" },
    ],
    orders.orders || []
  );
  renderTable(
    "backtest-fills-table",
    [
      { key: "fill_time", label: "Fill Time" },
      { key: "unified_symbol", label: "Symbol" },
      { key: "price", label: "Price" },
      { key: "qty", label: "Qty" },
      { key: "fee", label: "Fee" },
      { key: "slippage_cost", label: "Slippage" },
    ],
    fills.fills || []
  );
  renderTable(
    "backtest-timeseries-table",
    [
      { key: "ts", label: "Time" },
      { key: "equity", label: "Equity" },
      { key: "cash", label: "Cash" },
      { key: "gross_exposure", label: "Gross" },
      { key: "net_exposure", label: "Net" },
      { key: "drawdown", label: "Drawdown" },
    ],
    timeseries.points || []
  );
  renderBacktestDebugTraces(runId, debugTraces, traceFilters);
}

async function loadBacktestDebugTraces(formValues = null) {
  if (!state.selectedBacktestRunId) {
    throw new Error("Select a backtest run before loading debug traces.");
  }
  const traceFilters = getBacktestTraceFilters(formValues);
  const debugTraces = await fetchEnvelope(
    `/api/v1/backtests/runs/${state.selectedBacktestRunId}/debug-traces`,
    traceFilters
  );
  renderBacktestDebugTraces(state.selectedBacktestRunId, debugTraces, traceFilters);
}

async function loadBacktestAssumptionBundles() {
  const bundles = await fetchEnvelope("/api/v1/backtests/assumption-bundles");
  const records = (bundles.assumption_bundles || []).map((entry) => ({
    assumption_bundle_code: entry.assumption_bundle_code,
    assumption_bundle_version: entry.assumption_bundle_version,
    market_scope: entry.market_scope,
    fee_model_version: entry.assumptions.fee_model_version,
    slippage_model_version: entry.assumptions.slippage_model_version,
    feature_input_version: entry.assumptions.feature_input_version,
    benchmark_set_code: entry.assumptions.benchmark_set_code,
    risk_policy_code: entry.assumptions.risk_policy?.policy_code,
    description: entry.description,
  }));

  renderTable(
    "backtest-assumption-bundles-table",
    [
      { key: "assumption_bundle_code", label: "Bundle" },
      { key: "assumption_bundle_version", label: "Version" },
      { key: "market_scope", label: "Scope" },
      { key: "fee_model_version", label: "Fee" },
      { key: "slippage_model_version", label: "Slippage" },
      { key: "feature_input_version", label: "Input" },
      { key: "risk_policy_code", label: "Risk Policy" },
      { key: "description", label: "Description" },
    ],
    records
  );

  const codeList = document.getElementById("backtest-assumption-bundle-options");
  if (codeList) {
    codeList.innerHTML = "";
    (bundles.assumption_bundles || []).forEach((entry) => {
      const option = document.createElement("option");
      option.value = entry.assumption_bundle_code;
      option.label = `${entry.display_name} (${entry.assumption_bundle_version})`;
      codeList.appendChild(option);
    });
  }
}

async function loadBacktestRiskPolicies() {
  const policies = await fetchEnvelope("/api/v1/backtests/risk-policies");
  const records = (policies.risk_policies || []).map((entry) => ({
    policy_code: entry.policy_code,
    display_name: entry.display_name,
    market_scope: entry.market_scope,
    max_position_qty: entry.risk_policy.max_position_qty,
    max_order_notional: entry.risk_policy.max_order_notional,
    max_gross_exposure_multiple: entry.risk_policy.max_gross_exposure_multiple,
    max_drawdown_pct: entry.risk_policy.max_drawdown_pct,
    max_daily_loss_pct: entry.risk_policy.max_daily_loss_pct,
    max_leverage: entry.risk_policy.max_leverage,
    cooldown_bars_after_stop: entry.risk_policy.cooldown_bars_after_stop,
    description: entry.description,
  }));

  renderTable(
    "backtest-risk-policies-table",
    [
      { key: "policy_code", label: "Policy" },
      { key: "market_scope", label: "Scope" },
      { key: "max_position_qty", label: "Max Pos Qty" },
      { key: "max_order_notional", label: "Max Order Notional" },
      { key: "max_gross_exposure_multiple", label: "Max Gross x" },
      { key: "max_drawdown_pct", label: "Max DD %" },
      { key: "max_daily_loss_pct", label: "Max Daily Loss %" },
      { key: "max_leverage", label: "Max Lev" },
      { key: "cooldown_bars_after_stop", label: "Cooldown Bars" },
      { key: "description", label: "Description" },
    ],
    records
  );

  const datalist = document.getElementById("backtest-risk-policy-options");
  if (datalist) {
    datalist.innerHTML = "";
    (policies.risk_policies || []).forEach((entry) => {
      const option = document.createElement("option");
      option.value = entry.policy_code;
      option.label = `${entry.display_name} (${entry.market_scope})`;
      datalist.appendChild(option);
    });
  }
}

async function launchBacktest(formValues) {
  const riskPolicy = {};
  const riskOverrides = {};
  const riskPolicyCode = String(formValues.risk_policy_code || "").trim();
  if (riskPolicyCode) {
    riskPolicy.policy_code = riskPolicyCode;
  }
  [
    "block_new_entries_below_equity",
    "max_position_qty",
    "max_order_qty",
    "max_order_notional",
    "max_gross_exposure_multiple",
    "max_drawdown_pct",
    "max_daily_loss_pct",
    "max_leverage",
    "cooldown_bars_after_stop",
  ].forEach((fieldName) => {
    const value = String(formValues[fieldName] || "").trim();
    if (value !== "") {
      riskOverrides[fieldName] = value;
    }
  });
  ["enforce_spot_cash_check", "allow_reduce_only_when_blocked"].forEach((fieldName) => {
    const rawValue = String(formValues[fieldName] || "").trim();
    if (rawValue !== "") {
      riskOverrides[fieldName] = parseBooleanInput(rawValue);
    }
  });

  const payload = {
    run_name: formValues.run_name,
    session: {
      session_code: `${formValues.strategy_code}_${Date.now()}`,
      environment: "backtest",
      account_code: formValues.account_code || "paper_main",
      strategy_code: formValues.strategy_code,
      strategy_version: formValues.strategy_version,
      exchange_code: formValues.exchange_code || "binance",
      trading_timezone: formValues.trading_timezone || "UTC",
      universe: [formValues.unified_symbol],
    },
    start_time: formValues.start_time,
    end_time: formValues.end_time,
    initial_cash: formValues.initial_cash || "100000",
    assumption_bundle_code: formValues.assumption_bundle_code || null,
    assumption_bundle_version: formValues.assumption_bundle_version || null,
    strategy_params: {
      short_window: Number(formValues.short_window || 5),
      long_window: Number(formValues.long_window || 20),
      target_qty: formValues.target_qty || "1",
      allow_short: parseBooleanInput(formValues.allow_short),
    },
    persist_signals: true,
    persist_debug_traces: parseBooleanInput(formValues.persist_debug_traces),
  };
  if (Object.keys(riskPolicy).length > 0) {
    payload.session.risk_policy = riskPolicy;
  }
  if (Object.keys(riskOverrides).length > 0) {
    payload.risk_overrides = riskOverrides;
  }

  setBacktestLaunchFormBusy(true);
  setBacktestLaunchStatus({
    phase: "submitting",
    title: "Submitting Run Configuration",
    detail: "Sending the current launch form to the backtest API.",
    progress: 14,
    stateClass: "is-running",
  });

  try {
    setBacktestLaunchStatus({
      phase: "running",
      title: "Backtest Running",
      detail: "Waiting for the current synchronous backtest request to complete.",
      progress: 55,
      stateClass: "is-running",
    });
    const created = await sendEnvelope("/api/v1/backtests/runs", "POST", payload);
    renderJson("backtest-launch-result", created);

    setBacktestLaunchStatus({
      phase: "refreshing",
      title: "Refreshing Run List",
      detail: "Updating the current Backtests workspace with the newly created run.",
      progress: 80,
      stateClass: "is-running",
    });
    await loadBacktests();

    if (created.run_id) {
      setBacktestLaunchStatus({
        phase: "loading",
        title: "Loading Selected Run",
        detail: `Fetching details for run ${created.run_id}.`,
        progress: 92,
        stateClass: "is-running",
      });
      await loadSelectedBacktestRun(created.run_id);
    }

    setBacktestLaunchStatus({
      phase: "complete",
      title: "Backtest Completed",
      detail: created.run_id
        ? `Run ${created.run_id} finished and is now selected below.`
        : "The backtest request completed successfully.",
      progress: 100,
      stateClass: "is-complete",
    });
  } catch (error) {
    setBacktestLaunchStatus({
      phase: "error",
      title: "Launch Failed",
      detail: error.message || "The run could not be created.",
      progress: 100,
      stateClass: "is-error",
    });
    throw error;
  } finally {
    setBacktestLaunchFormBusy(false);
  }
}

async function compareBacktestRuns(formValues) {
  const runIds = String(formValues.run_ids || "")
    .split(",")
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isInteger(value) && value > 0);
  const benchmarkRunId = formValues.benchmark_run_id ? Number(formValues.benchmark_run_id) : null;
  const payload = {
    run_ids: runIds,
    benchmark_run_id: Number.isInteger(benchmarkRunId) ? benchmarkRunId : null,
    compare_name: formValues.compare_name || null,
  };
  const result = await sendEnvelope("/api/v1/backtests/compare-sets", "POST", payload);
  state.selectedCompareSetId = result.compare_set_id || null;
  state.selectedCompareNoteId = null;
  renderCompareResult(result);
  renderJson("backtest-compare-note-result", result);
  resetCompareNoteForm();
  if (state.selectedCompareSetId) {
    await loadCompareNotes(state.selectedCompareSetId);
  }
}

async function saveCompareReviewNote(formValues) {
  if (!state.selectedCompareSetId) {
    throw new Error("Create or select a compare set before saving review notes.");
  }
  const annotationId = Number(formValues.annotation_id);
  const payload = {
    annotation_type: String(formValues.annotation_type || "review").trim() || "review",
    status: String(formValues.status || "in_review").trim() || "in_review",
    title: String(formValues.title || "").trim(),
    summary: String(formValues.summary || "").trim() || null,
    note_source: String(formValues.note_source || "human").trim() || "human",
    verification_state: String(formValues.verification_state || "verified").trim() || "verified",
    verified_findings: normalizeLineList(formValues.verified_findings),
    open_questions: normalizeLineList(formValues.open_questions),
    next_action: String(formValues.next_action || "").trim() || null,
  };
  if (!payload.title) {
    throw new Error("title is required");
  }
  if (Number.isInteger(annotationId) && annotationId > 0) {
    payload.annotation_id = annotationId;
  }
  const saved = await sendEnvelope(
    `/api/v1/backtests/compare-sets/${state.selectedCompareSetId}/notes`,
    "POST",
    payload
  );
  renderJson("backtest-compare-note-result", saved);
  await loadCompareNotes(state.selectedCompareSetId, saved.annotation_id);
}

async function loadQuality(filters = {}) {
  const [checks, gaps] = await Promise.all([
    fetchEnvelope("/api/v1/quality/checks", { limit: 30, latest_only: "true", ...filters }),
    fetchEnvelope("/api/v1/quality/gaps", { limit: 30, status: "open", unified_symbol: filters.unified_symbol }),
  ]);

  renderTable(
    "quality-checks",
    [
      { key: "data_type", label: "Data Type" },
      { key: "check_name", label: "Check" },
      { key: "severity", label: "Severity", type: "status" },
      { key: "status", label: "Status", type: "status" },
      { key: "observed_value", label: "Observed" },
      { key: "check_time", label: "Time" },
    ],
    checks.records,
    (record) => renderJson("job-detail", record)
  );

  renderTable(
    "quality-gaps",
    [
      { key: "data_type", label: "Data Type" },
      { key: "unified_symbol", label: "Symbol" },
      { key: "gap_start", label: "Gap Start" },
      { key: "gap_end", label: "Gap End" },
      { key: "status", label: "Status", type: "status" },
    ],
    gaps.records
  );
}

async function loadTraceability(filters = {}) {
  const rawEvents = await fetchEnvelope("/api/v1/market/raw-events", { limit: 20, ...filters });
  renderTable(
    "raw-events",
    [
      { key: "raw_event_id", label: "Raw Event" },
      { key: "exchange_code", label: "Exchange" },
      { key: "unified_symbol", label: "Symbol" },
      { key: "channel", label: "Channel" },
      { key: "event_type", label: "Type" },
      { key: "event_time", label: "Event Time" },
    ],
    rawEvents.records,
    async (record) => {
      state.selectedRawEventId = record.raw_event_id;
      const [detail, links] = await Promise.all([
        fetchEnvelope(`/api/v1/market/raw-events/${record.raw_event_id}`),
        fetchEnvelope(`/api/v1/market/raw-events/${record.raw_event_id}/normalized-links`),
      ]);
      renderJson("raw-event-detail", detail);
      renderJson("raw-event-links", links);
    }
  );
}

async function refreshCurrentView() {
  const active = document.querySelector(".nav-link.is-active")?.dataset.view || "overview";
  if (active === "overview") {
    await loadOverview();
  }
  if (active === "backtests") {
    await loadBacktests(Object.fromEntries(new FormData(document.getElementById("backtest-filter-form")).entries()));
  }
  if (active === "jobs") {
    await loadJobs(Object.fromEntries(new FormData(document.getElementById("jobs-filter-form")).entries()));
  }
  if (active === "quality") {
    await loadQuality(Object.fromEntries(new FormData(document.getElementById("quality-filter-form")).entries()));
  }
  if (active === "traceability") {
    await loadTraceability(Object.fromEntries(new FormData(document.getElementById("raw-filter-form")).entries()));
  }
}

function activateView(viewName) {
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.view === viewName);
  });
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("is-visible", view.id === `view-${viewName}`);
  });
  setText("view-title", viewName.charAt(0).toUpperCase() + viewName.slice(1));
  refreshCurrentView().catch((error) => {
    window.alert(error.message);
  });
}

function bindForm(id, loader) {
  const form = document.getElementById(id);
  if (!form) {
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await loader(Object.fromEntries(new FormData(form).entries()));
    } catch (error) {
      window.alert(error.message);
    }
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.addEventListener("click", () => activateView(button.dataset.view));
  });
  document.getElementById("refresh-all")?.addEventListener("click", () => {
    refreshCurrentView().catch((error) => window.alert(error.message));
  });
  bindForm("jobs-filter-form", loadJobs);
  bindForm("backtest-filter-form", loadBacktests);
  bindForm("quality-filter-form", loadQuality);
  bindForm("raw-filter-form", loadTraceability);
  bindForm("backtest-launch-form", launchBacktest);
  bindForm("backtest-compare-form", compareBacktestRuns);
  bindForm("backtest-compare-note-form", saveCompareReviewNote);
  bindForm("backtest-trace-filter-form", loadBacktestDebugTraces);
  bindBacktestPresetButtons();
  document.getElementById("backtest-compare-note-reset")?.addEventListener("click", () => {
    resetCompareNoteForm();
  });

  try {
    await loadOverview();
  } catch (error) {
    window.alert(error.message);
  }
});
