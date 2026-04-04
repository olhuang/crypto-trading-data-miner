const DEFAULT_HEADERS = {};

const state = {
  selectedJobId: null,
  selectedRawEventId: null,
  selectedBacktestRunId: null,
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
  return String(value || "").trim().toLowerCase() === "true";
}

async function loadBacktests(filters = {}) {
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
    async (record) => {
      state.selectedBacktestRunId = record.run_id;
      const [detail, diagnostics, artifacts, breakdown, signals, orders, fills, timeseries] = await Promise.all([
        fetchEnvelope(`/api/v1/backtests/runs/${record.run_id}`),
        fetchEnvelope(`/api/v1/backtests/runs/${record.run_id}/diagnostics`),
        fetchEnvelope(`/api/v1/backtests/runs/${record.run_id}/artifacts`),
        fetchEnvelope(`/api/v1/backtests/runs/${record.run_id}/period-breakdown`, { period_type: "month" }),
        fetchEnvelope(`/api/v1/backtests/runs/${record.run_id}/signals`, { limit: 50 }),
        fetchEnvelope(`/api/v1/backtests/runs/${record.run_id}/orders`, { limit: 50 }),
        fetchEnvelope(`/api/v1/backtests/runs/${record.run_id}/fills`, { limit: 50 }),
        fetchEnvelope(`/api/v1/backtests/runs/${record.run_id}/timeseries`, { limit: 120 }),
      ]);
      renderJson("backtest-run-detail", detail);
      renderJson("backtest-run-diagnostics", diagnostics);
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
    }
  );
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
  };
  if (Object.keys(riskPolicy).length > 0) {
    payload.session.risk_policy = riskPolicy;
  }
  if (Object.keys(riskOverrides).length > 0) {
    payload.risk_overrides = riskOverrides;
  }
  const created = await sendEnvelope("/api/v1/backtests/runs", "POST", payload);
  renderJson("backtest-launch-result", created);
  await loadBacktests();
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
  renderJson("backtest-compare-result", result);
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

  try {
    await loadOverview();
  } catch (error) {
    window.alert(error.message);
  }
});
