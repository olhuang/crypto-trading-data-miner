const DEFAULT_HEADERS = {};

const state = {
  selectedJobId: null,
  selectedRawEventId: null,
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
  bindForm("quality-filter-form", loadQuality);
  bindForm("raw-filter-form", loadTraceability);

  try {
    await loadOverview();
  } catch (error) {
    window.alert(error.message);
  }
});
