const DEFAULT_HEADERS = {};

const state = {
  selectedJobId: null,
  selectedRawEventId: null,
  selectedBacktestRunId: null,
  selectedBacktestDebugTraceId: null,
  selectedTraceNoteId: null,
  selectedCompareSetId: null,
  selectedCompareNoteId: null,
  selectedComparedRunId: null,
  selectedCompareDiffKey: null,
  currentIntegrityResult: null,
  selectedIntegrityDataType: null,
  integrityRepairContext: null,
  currentBtcBackfillStatus: null,
  selectedBtcBackfillDatasetKey: null,
  btcBackfillStatusPollHandle: null,
};

const INTEGRITY_DATASET_FIELDS = [
  "bars_1m",
  "funding_rates",
  "open_interest",
  "mark_prices",
  "index_prices",
  "global_long_short_account_ratios",
  "top_trader_long_short_account_ratios",
  "top_trader_long_short_position_ratios",
  "taker_long_short_ratios",
  "trades",
  "raw_market_events",
];

const BACKTEST_LAUNCH_PRESETS = {
  baseline_perp: {
    label: "Baseline Perp",
    values: {
      strategy_code: "btc_momentum",
      strategy_version: "v1.0.0",
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
  sentiment_perp: {
    label: "Sentiment Perp",
    values: {
      strategy_code: "btc_sentiment_momentum",
      strategy_version: "v1.0.0",
      unified_symbol: "BTCUSDT_PERP",
      assumption_bundle_code: "baseline_perp_sentiment_research",
      assumption_bundle_version: "v1",
      risk_policy_code: "perp_medium_v1",
      short_window: "5",
      long_window: "20",
      target_qty: "0.05",
      allow_short: "false",
      max_global_long_short_ratio: "2.25",
      min_taker_buy_sell_ratio: "0.95",
      persist_debug_traces: true,
      enforce_spot_cash_check: true,
      allow_reduce_only_when_blocked: true,
    },
  },
  hourly_perp: {
    label: "Hourly Perp",
    values: {
      strategy_code: "btc_hourly_momentum",
      strategy_version: "v1.0.0",
      unified_symbol: "BTCUSDT_PERP",
      assumption_bundle_code: "baseline_perp_research",
      assumption_bundle_version: "v1",
      risk_policy_code: "perp_medium_v1",
      short_window: "5",
      long_window: "20",
      target_qty: "0.05",
      allow_short: "false",
      persist_debug_traces: true,
      enforce_spot_cash_check: true,
      allow_reduce_only_when_blocked: true,
    },
  },
  breakout_perp: {
    label: "4H Breakout Perp",
    values: {
      strategy_code: "btc_4h_breakout_perp",
      strategy_version: "v0.1.0",
      unified_symbol: "BTCUSDT_PERP",
      assumption_bundle_code: "breakout_perp_research",
      assumption_bundle_version: "v1",
      risk_policy_code: "perp_medium_v1",
      trend_fast_ema: "20",
      trend_slow_ema: "50",
      breakout_lookback_bars: "20",
      atr_window: "14",
      initial_stop_atr: "2",
      trailing_stop_atr: "1.5",
      exit_on_ema20_cross: "true",
      risk_per_trade_pct: "0.005",
      volatility_floor_atr_pct: "0.008",
      volatility_ceiling_atr_pct: "0.08",
      max_funding_rate_long: "0.0005",
      oi_change_pct_window: "0.05",
      min_price_change_pct_for_oi_confirmation: "0.01",
      skip_entries_within_minutes_of_funding: "30",
      max_consecutive_losses: "3",
      max_daily_r_multiple_loss: "2",
      max_position_qty: "25",
      max_order_qty: "25",
      persist_debug_traces: true,
      enforce_spot_cash_check: true,
      allow_reduce_only_when_blocked: true,
    },
  },
  baseline_spot: {
    label: "Baseline Spot",
    values: {
      strategy_code: "btc_momentum",
      strategy_version: "v1.0.0",
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
      strategy_code: "btc_momentum",
      strategy_version: "v1.0.0",
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

const BACKTEST_STRATEGY_CONFIGS = {
  btc_momentum: {
    title: "Bars-Only Momentum",
    detail: "Uses moving-average crossover on minute bars only.",
    hint: "Works naturally with `baseline_perp_research` or `baseline_spot_research`.",
    showBaseMomentumThresholds: true,
    showSentimentThresholds: false,
    showBreakoutThresholds: false,
  },
  btc_sentiment_momentum: {
    title: "Sentiment-Aware Momentum",
    detail:
      "Uses the same moving-average baseline, but only allows long entries when crowding and taker-flow context stay within configured thresholds.",
    hint:
      "Best paired with `baseline_perp_sentiment_research`, which turns on `bars_perp_context_v1` so the runner loads funding, OI, mark/index, and the Binance sentiment ratios.",
    showBaseMomentumThresholds: true,
    showSentimentThresholds: true,
    showBreakoutThresholds: false,
  },
  btc_hourly_momentum: {
    title: "Hourly Bars Momentum",
    detail: "Groups minute data into dynamic 1-hour boundaries before calculating moving averages for crosses.",
    hint: "Best paired with `baseline_perp_research`; short and long windows represent hours instead of minutes.",
    showBaseMomentumThresholds: true,
    showSentimentThresholds: false,
    showBreakoutThresholds: false,
  },
  btc_4h_breakout_perp: {
    title: "4H Breakout Perp",
    detail:
      "Aggregates 1m bars into 4H closes, then applies trend, breakout, ATR-volatility, and perp-context gates before sizing a long entry.",
    hint:
      "Best paired with `breakout_perp_research`, which turns on `bars_perp_breakout_context_v1` so funding-window and OI-vs-price context are available.",
    showBaseMomentumThresholds: false,
    showSentimentThresholds: false,
    showBreakoutThresholds: true,
  },
};

function statusClass(value) {
  if (!value) {
    return "";
  }
  return `status-${String(value).replaceAll(" ", "_")}`;
}

function normalizeDisplayValue(value) {
  if (Array.isArray(value)) {
    return value.map((entry) => normalizeDisplayValue(entry));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, entryValue]) => [key, normalizeDisplayValue(entryValue)])
    );
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (/^[+-]?0+(?:\.0+)?e[+-]?\d+$/i.test(trimmed)) {
      return "0";
    }
  }
  return value;
}

function formatValue(value) {
  value = normalizeDisplayValue(value);
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
  const text = await response.text();
  let envelope = null;
  if (text) {
    try {
      envelope = JSON.parse(text);
    } catch {
      envelope = null;
    }
  }
  if (!response.ok || envelope?.success === false) {
    throw new Error(
      envelope?.error?.message ||
        text.trim() ||
        `Request failed for ${path}`
    );
  }
  return envelope?.data;
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
  const text = await response.text();
  let envelope = null;
  if (text) {
    try {
      envelope = JSON.parse(text);
    } catch {
      envelope = null;
    }
  }
  if (!response.ok || envelope?.success === false) {
    throw new Error(
      envelope?.error?.message ||
        text.trim() ||
        `Request failed for ${path}`
    );
  }
  return envelope?.data;
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
      if (typeof column.render === "function") {
        const rendered = column.render(record, rawValue, td);
        if (rendered instanceof Node) {
          td.appendChild(rendered);
        } else {
          td.textContent = formatValue(rendered);
        }
      } else if (column.type === "status") {
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
  container.textContent = JSON.stringify(normalizeDisplayValue(payload), null, 2);
}

async function copyTextToClipboard(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.setAttribute("readonly", "");
  textArea.style.position = "absolute";
  textArea.style.left = "-9999px";
  document.body.appendChild(textArea);
  textArea.select();
  document.execCommand("copy");
  document.body.removeChild(textArea);
}

function setJsonCopyButtonState(button, copied) {
  if (!button) {
    return;
  }
  button.classList.toggle("is-copied", copied);
  button.setAttribute("aria-label", copied ? "Copied" : "Copy contents");
  button.setAttribute("title", copied ? "Copied" : "Copy contents");
}

function createJsonCopyButton() {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "json-copy-button";
  button.setAttribute("aria-label", "Copy contents");
  button.setAttribute("title", "Copy contents");
  button.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true" focusable="false">
      <path d="M9 9h9v11H9z"></path>
      <path d="M6 5h9v2H8v9H6z"></path>
    </svg>
  `;
  return button;
}

function enhanceJsonShells() {
  document.querySelectorAll(".json-shell").forEach((shell) => {
    if (shell.parentElement?.classList.contains("json-shell-frame")) {
      return;
    }

    const frame = document.createElement("div");
    frame.className = "json-shell-frame";
    shell.parentNode.insertBefore(frame, shell);
    frame.appendChild(shell);

    const button = createJsonCopyButton();
    let resetTimer = null;
    button.addEventListener("click", async () => {
      const text = shell.textContent || "";
      if (!text.trim()) {
        return;
      }
      try {
        await copyTextToClipboard(text);
        setJsonCopyButtonState(button, true);
        window.clearTimeout(resetTimer);
        resetTimer = window.setTimeout(() => {
          setJsonCopyButtonState(button, false);
        }, 1200);
      } catch (error) {
        window.alert(`Unable to copy contents: ${error.message}`);
      }
    });

    frame.appendChild(button);
  });
}

function humanizeKey(key) {
  return String(key || "")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (match) => match.toUpperCase())
    .replaceAll(" Json", " JSON")
    .replaceAll(" Pct", " Pct");
}

function isEmptyValue(value) {
  if (value === null || value === undefined || value === "") {
    return true;
  }
  if (Array.isArray(value)) {
    return value.length === 0;
  }
  if (typeof value === "object") {
    return Object.keys(value).length === 0;
  }
  return false;
}

function formatCompactValue(value) {
  value = normalizeDisplayValue(value);
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (Array.isArray(value)) {
    if (!value.length) {
      return "-";
    }
    return value.map((item) => formatCompactValue(item)).join(", ");
  }
  if (typeof value === "object") {
    const entries = Object.entries(value);
    if (!entries.length) {
      return "-";
    }
    const preview = entries
      .slice(0, 4)
      .map(([key, entryValue]) => `${humanizeKey(key)}=${formatCompactValue(entryValue)}`)
      .join(" | ");
    if (entries.length <= 4) {
      return preview;
    }
    return `${preview} | +${entries.length - 4} more`;
  }
  return String(value);
}

function renderPropertyGrid(targetId, items, emptyMessage) {
  const container = document.getElementById(targetId);
  if (!container) {
    return;
  }
  if (!items.length) {
    container.innerHTML = `<div class="summary-empty">${emptyMessage}</div>`;
    return;
  }

  const grid = document.createElement("div");
  grid.className = "property-grid";

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = "property-card";

    const label = document.createElement("p");
    label.className = "property-label";
    label.textContent = item.label;

    const value = document.createElement("p");
    value.className = "property-value";
    value.textContent = formatCompactValue(item.value);

    card.appendChild(label);
    card.appendChild(value);
    grid.appendChild(card);
  });

  container.innerHTML = "";
  container.appendChild(grid);
}

function buildPropertyItemsFromObject(source, labelMap = {}, order = [], options = {}) {
  if (!source || typeof source !== "object") {
    return [];
  }
  const excludeKeys = new Set(options.excludeKeys || []);
  const excludeEmpty = options.excludeEmpty !== false;
  const entries = Object.entries(source).filter(([key, value]) => {
    if (excludeKeys.has(key)) {
      return false;
    }
    if (excludeEmpty && isEmptyValue(value)) {
      return false;
    }
    return true;
  });

  const ranked = new Map(order.map((key, index) => [key, index]));
  entries.sort(([leftKey], [rightKey]) => {
    const leftRank = ranked.has(leftKey) ? ranked.get(leftKey) : Number.MAX_SAFE_INTEGER;
    const rightRank = ranked.has(rightKey) ? ranked.get(rightKey) : Number.MAX_SAFE_INTEGER;
    if (leftRank !== rightRank) {
      return leftRank - rightRank;
    }
    return leftKey.localeCompare(rightKey);
  });

  return entries.map(([key, value]) => ({
    label: labelMap[key] || humanizeKey(key),
    value,
  }));
}

function renderBacktestRunStructuredDetails(detail) {
  if (!detail || !detail.run_id) {
    renderPropertyGrid(
      "backtest-run-strategy-params",
      [],
      "Strategy parameters will appear here."
    );
    renderPropertyGrid(
      "backtest-run-execution-protection",
      [],
      "Execution and protection settings will appear here."
    );
    renderPropertyGrid("backtest-run-risk-snapshot", [], "Risk snapshot will appear here.");
    renderPropertyGrid(
      "backtest-run-assumption-snapshot",
      [],
      "Assumption snapshot will appear here."
    );
    renderPropertyGrid(
      "backtest-run-runtime-snapshot",
      [],
      "Runtime metadata will appear here."
    );
    return;
  }

  const strategyItems = buildPropertyItemsFromObject(
    detail.strategy_params_json || {},
    {
      short_window: "Short Window",
      long_window: "Long Window",
      target_qty: "Target Quantity",
      allow_short: "Allow Short",
      target_notional: "Target Notional",
      max_global_long_short_ratio: "Max Global Long/Short Ratio",
      min_taker_buy_sell_ratio: "Min Taker Buy/Sell Ratio",
      trend_fast_ema: "Trend Fast EMA",
      trend_slow_ema: "Trend Slow EMA",
      breakout_lookback_bars: "Breakout Lookback Bars",
      atr_window: "ATR Window",
      initial_stop_atr: "Initial Stop ATR",
      trailing_stop_atr: "Trailing Stop ATR",
      exit_on_ema20_cross: "Exit On EMA20 Cross",
      risk_per_trade_pct: "Risk Per Trade Pct",
      volatility_floor_atr_pct: "Volatility Floor ATR %",
      volatility_ceiling_atr_pct: "Volatility Ceiling ATR %",
      max_funding_rate_long: "Max Funding Rate Long",
      oi_change_pct_window: "OI Change Pct Window",
      min_price_change_pct_for_oi_confirmation: "Min Price Change Pct For OI Confirmation",
      skip_entries_within_minutes_of_funding: "Skip Entries Within Minutes Of Funding",
      max_consecutive_losses: "Max Consecutive Losses",
      max_daily_r_multiple_loss: "Max Daily R Multiple Loss",
    },
    [
      "short_window",
      "long_window",
      "target_qty",
      "target_notional",
      "allow_short",
      "max_global_long_short_ratio",
      "min_taker_buy_sell_ratio",
      "trend_fast_ema",
      "trend_slow_ema",
      "breakout_lookback_bars",
      "atr_window",
      "initial_stop_atr",
      "trailing_stop_atr",
      "exit_on_ema20_cross",
      "risk_per_trade_pct",
      "volatility_floor_atr_pct",
      "volatility_ceiling_atr_pct",
      "max_funding_rate_long",
      "oi_change_pct_window",
      "min_price_change_pct_for_oi_confirmation",
      "skip_entries_within_minutes_of_funding",
      "max_consecutive_losses",
      "max_daily_r_multiple_loss",
    ]
  );

  const executionItems = buildPropertyItemsFromObject(
    {
      execution_policy_code: detail.execution_policy?.policy_code,
      order_type_preference: detail.execution_policy?.order_type_preference,
      urgency: detail.execution_policy?.urgency,
      reduce_only_on_exit: detail.execution_policy?.reduce_only_on_exit,
      allow_position_flip: detail.execution_policy?.allow_position_flip,
      maker_bias: detail.execution_policy?.maker_bias,
      max_child_order_qty: detail.execution_policy?.max_child_order_qty,
      max_participation_rate: detail.execution_policy?.max_participation_rate,
      protection_policy_code: detail.protection_policy?.policy_code,
      protection_scope_mode: detail.protection_policy?.scope_mode,
      protection_trigger_basis: detail.protection_policy?.trigger_basis,
      stop_loss_bps: detail.protection_policy?.stop_loss_bps,
      take_profit_bps: detail.protection_policy?.take_profit_bps,
      trailing_stop_bps: detail.protection_policy?.trailing_stop_bps,
      time_exit_bars: detail.protection_policy?.time_exit_bars,
    },
    {
      execution_policy_code: "Execution Policy Code",
      order_type_preference: "Order Type Preference",
      reduce_only_on_exit: "Reduce Only On Exit",
      allow_position_flip: "Allow Position Flip",
      maker_bias: "Maker Bias",
      max_child_order_qty: "Max Child Order Qty",
      max_participation_rate: "Max Participation Rate",
      protection_policy_code: "Protection Policy Code",
      protection_scope_mode: "Protection Scope Mode",
      protection_trigger_basis: "Protection Trigger Basis",
      stop_loss_bps: "Stop Loss Bps",
      take_profit_bps: "Take Profit Bps",
      trailing_stop_bps: "Trailing Stop Bps",
      time_exit_bars: "Time Exit Bars",
    },
    [
      "execution_policy_code",
      "order_type_preference",
      "urgency",
      "reduce_only_on_exit",
      "allow_position_flip",
      "maker_bias",
      "max_child_order_qty",
      "max_participation_rate",
      "protection_policy_code",
      "protection_scope_mode",
      "protection_trigger_basis",
      "stop_loss_bps",
      "take_profit_bps",
      "trailing_stop_bps",
      "time_exit_bars",
    ]
  );

  const riskOverrideKeys = Object.keys(detail.risk_overrides_json || {});
  const riskItems = buildPropertyItemsFromObject(
    {
      session_policy_code: detail.session_risk_policy?.policy_code,
      effective_policy_code: detail.risk_policy?.policy_code,
      override_keys: riskOverrideKeys.length ? riskOverrideKeys : "None",
      max_position_qty: detail.risk_policy?.max_position_qty,
      max_order_qty: detail.risk_policy?.max_order_qty,
      max_order_notional: detail.risk_policy?.max_order_notional,
      max_gross_exposure_multiple: detail.risk_policy?.max_gross_exposure_multiple,
      max_drawdown_pct: detail.risk_policy?.max_drawdown_pct,
      max_daily_loss_pct: detail.risk_policy?.max_daily_loss_pct,
      max_leverage: detail.risk_policy?.max_leverage,
      cooldown_bars_after_stop: detail.risk_policy?.cooldown_bars_after_stop,
      enforce_spot_cash_check: detail.risk_policy?.enforce_spot_cash_check,
      allow_reduce_only_when_blocked: detail.risk_policy?.allow_reduce_only_when_blocked,
      block_new_entries_below_equity: detail.risk_policy?.block_new_entries_below_equity,
    },
    {
      session_policy_code: "Session Policy Code",
      effective_policy_code: "Effective Policy Code",
      override_keys: "Run Override Keys",
      max_position_qty: "Max Position Qty",
      max_order_qty: "Max Order Qty",
      max_order_notional: "Max Order Notional",
      max_gross_exposure_multiple: "Max Gross Exposure Multiple",
      max_drawdown_pct: "Max Drawdown Pct",
      max_daily_loss_pct: "Max Daily Loss Pct",
      max_leverage: "Max Leverage",
      cooldown_bars_after_stop: "Cooldown Bars After Stop",
      enforce_spot_cash_check: "Enforce Spot Cash Check",
      allow_reduce_only_when_blocked: "Allow Reduce Only When Blocked",
      block_new_entries_below_equity: "Block New Entries Below Equity",
    },
    [
      "session_policy_code",
      "effective_policy_code",
      "override_keys",
      "max_position_qty",
      "max_order_qty",
      "max_order_notional",
      "max_gross_exposure_multiple",
      "max_drawdown_pct",
      "max_daily_loss_pct",
      "max_leverage",
      "cooldown_bars_after_stop",
      "enforce_spot_cash_check",
      "allow_reduce_only_when_blocked",
      "block_new_entries_below_equity",
    ],
    { excludeEmpty: false }
  );

  const assumptionOverrideKeys = Object.keys(detail.assumption_overrides_json || {});
  const assumptionItems = buildPropertyItemsFromObject(
    {
      assumption_bundle: detail.assumption_bundle_code
        ? `${detail.assumption_bundle_code}@${detail.assumption_bundle_version || "latest"}`
        : null,
      market_data_version: detail.effective_assumptions_json?.market_data_version || detail.market_data_version,
      feature_input_version:
        detail.effective_assumptions_json?.feature_input_version || detail.feature_input_version,
      fee_model_version: detail.effective_assumptions_json?.fee_model_version || detail.fee_model_version,
      slippage_model_version:
        detail.effective_assumptions_json?.slippage_model_version || detail.slippage_model_version,
      fill_model_version: detail.effective_assumptions_json?.fill_model_version || detail.fill_model_version,
      latency_model_version:
        detail.effective_assumptions_json?.latency_model_version || detail.latency_model_version,
      benchmark_set_code:
        detail.effective_assumptions_json?.benchmark_set_code || detail.benchmark_set_code,
      assumption_override_keys: assumptionOverrideKeys.length ? assumptionOverrideKeys : "None",
    },
    {
      assumption_bundle: "Assumption Bundle",
      market_data_version: "Market Data Version",
      feature_input_version: "Feature Input Version",
      fee_model_version: "Fee Model Version",
      slippage_model_version: "Slippage Model Version",
      fill_model_version: "Fill Model Version",
      latency_model_version: "Latency Model Version",
      benchmark_set_code: "Benchmark Set Code",
      assumption_override_keys: "Assumption Override Keys",
    },
    [
      "assumption_bundle",
      "market_data_version",
      "feature_input_version",
      "fee_model_version",
      "slippage_model_version",
      "fill_model_version",
      "latency_model_version",
      "benchmark_set_code",
      "assumption_override_keys",
    ],
    { excludeEmpty: false }
  );

  const riskSummary = detail.runtime_metadata_json?.risk_summary || {};
  const stateSnapshot = riskSummary.state_snapshot || {};
  const debugTraceSummary = detail.runtime_metadata_json?.debug_trace_summary || {};
  const runtimeItems = buildPropertyItemsFromObject(
    {
      active_trading_day: stateSnapshot.active_trading_day,
      trading_timezone: stateSnapshot.trading_timezone || detail.trading_timezone,
      peak_equity: stateSnapshot.peak_equity,
      daily_start_equity: stateSnapshot.daily_start_equity,
      current_drawdown_pct: stateSnapshot.current_drawdown_pct,
      current_daily_loss_pct: stateSnapshot.current_daily_loss_pct,
      cooldown_bars_remaining: stateSnapshot.cooldown_bars_remaining,
      activation_counts_by_code: stateSnapshot.activation_counts_by_code,
      allowed_intent_count: riskSummary.allowed_intent_count,
      blocked_intent_count: riskSummary.blocked_intent_count,
      evaluated_intent_count: riskSummary.evaluated_intent_count,
      block_counts_by_code: riskSummary.block_counts_by_code,
      outcome_counts_by_code: riskSummary.outcome_counts_by_code,
      trace_persisted: debugTraceSummary.persisted,
      captured_trace_count: debugTraceSummary.captured_trace_count,
    },
    {
      active_trading_day: "Active Trading Day",
      trading_timezone: "Trading Timezone",
      peak_equity: "Peak Equity",
      daily_start_equity: "Daily Start Equity",
      current_drawdown_pct: "Current Drawdown Pct",
      current_daily_loss_pct: "Current Daily Loss Pct",
      cooldown_bars_remaining: "Cooldown Bars Remaining",
      activation_counts_by_code: "Activation Counts By Code",
      allowed_intent_count: "Allowed Intent Count",
      blocked_intent_count: "Blocked Intent Count",
      evaluated_intent_count: "Evaluated Intent Count",
      block_counts_by_code: "Block Counts By Code",
      outcome_counts_by_code: "Outcome Counts By Code",
      trace_persisted: "Trace Persisted",
      captured_trace_count: "Captured Trace Count",
    },
    [
      "active_trading_day",
      "trading_timezone",
      "peak_equity",
      "daily_start_equity",
      "current_drawdown_pct",
      "current_daily_loss_pct",
      "cooldown_bars_remaining",
      "activation_counts_by_code",
      "allowed_intent_count",
      "blocked_intent_count",
      "evaluated_intent_count",
      "block_counts_by_code",
      "outcome_counts_by_code",
      "trace_persisted",
      "captured_trace_count",
    ],
    { excludeEmpty: false }
  );

  renderPropertyGrid(
    "backtest-run-strategy-params",
    strategyItems,
    "No strategy parameters were saved for this run."
  );
  renderPropertyGrid(
    "backtest-run-execution-protection",
    executionItems,
    "No execution or protection settings were saved for this run."
  );
  renderPropertyGrid(
    "backtest-run-risk-snapshot",
    riskItems,
    "No risk snapshot was saved for this run."
  );
  renderPropertyGrid(
    "backtest-run-assumption-snapshot",
    assumptionItems,
    "No assumption snapshot was saved for this run."
  );
  renderPropertyGrid(
    "backtest-run-runtime-snapshot",
    runtimeItems,
    "No runtime metadata was saved for this run."
  );
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
  updateBacktestStrategyFields();

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

function updateBacktestStrategyFields() {
  const form = document.getElementById("backtest-launch-form");
  if (!form) {
    return;
  }
  const strategyCode = String(form.elements.namedItem("strategy_code")?.value || "btc_momentum").trim();
  const config = BACKTEST_STRATEGY_CONFIGS[strategyCode] || BACKTEST_STRATEGY_CONFIGS.btc_momentum;
  setText("backtest-strategy-variant-title", config.title);
  setText("backtest-strategy-variant-detail", config.detail);
  setText("backtest-strategy-variant-hint", config.hint);

  const sentimentPanel = document.getElementById("backtest-sentiment-params");
  if (sentimentPanel) {
    sentimentPanel.hidden = !config.showSentimentThresholds;
  }
  const baseMomentumPanel = document.getElementById("backtest-base-params");
  if (baseMomentumPanel) {
    baseMomentumPanel.hidden = !config.showBaseMomentumThresholds;
  }
  const breakoutPanel = document.getElementById("backtest-breakout-params");
  if (breakoutPanel) {
    breakoutPanel.hidden = !config.showBreakoutThresholds;
  }
}

function initializeBacktestLaunchControls() {
  const form = document.getElementById("backtest-launch-form");
  if (!form) {
    return;
  }
  form.elements.namedItem("strategy_code")?.addEventListener("change", () => {
    updateBacktestStrategyFields();
  });
  updateBacktestStrategyFields();
}

function formatUtcDateInput(date) {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, "0");
  const day = String(date.getUTCDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function expandUtcDateBoundary(dateValue, boundary) {
  const [year, month, day] = String(dateValue || "")
    .split("-")
    .map((part) => Number(part));
  if (!year || !month || !day) {
    return "";
  }

  const hour = boundary === "end" ? 23 : 0;
  const minute = boundary === "end" ? 59 : 0;
  const second = boundary === "end" ? 59 : 0;
  return new Date(Date.UTC(year, month - 1, day, hour, minute, second))
    .toISOString()
    .replace(/\.\d{3}Z$/, "Z");
}

function setIntegrityQuickRange(rangeKey) {
  const form = document.getElementById("integrity-validation-form");
  if (!form) {
    return;
  }
  const startControl = form.elements.namedItem("start_time");
  const endControl = form.elements.namedItem("end_time");
  const now = new Date();
  let start = new Date(now);

  if (rangeKey === "last_24h") {
    start.setUTCDate(start.getUTCDate() - 1);
  } else if (rangeKey === "last_7d") {
    start.setUTCDate(start.getUTCDate() - 7);
  } else if (rangeKey === "last_30d") {
    start.setUTCDate(start.getUTCDate() - 30);
  } else if (rangeKey === "this_month") {
    start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1, 0, 0, 0));
  } else if (rangeKey === "ytd") {
    start = new Date(Date.UTC(now.getUTCFullYear(), 0, 1, 0, 0, 0));
  } else {
    return;
  }

  setFormControlValue(startControl, formatUtcDateInput(start));
  setFormControlValue(endControl, formatUtcDateInput(now));
}

function syncIntegrityDatasetControls() {
  const form = document.getElementById("integrity-validation-form");
  if (!form) {
    return;
  }

  const useDefaults = form.elements.namedItem("use_symbol_defaults")?.checked !== false;
  INTEGRITY_DATASET_FIELDS.forEach((dataType) => {
    const control = form.elements.namedItem(`integrity_data_type_${dataType}`);
    if (!control) {
      return;
    }
    control.disabled = useDefaults;
    if (useDefaults) {
      control.checked = false;
    }
  });

  const rawEventsEnabled =
    !useDefaults && Boolean(form.elements.namedItem("integrity_data_type_raw_market_events")?.checked);
  const rawEventChannelControl = form.elements.namedItem("raw_event_channel");
  if (rawEventChannelControl) {
    rawEventChannelControl.disabled = !rawEventsEnabled;
    if (!rawEventsEnabled) {
      rawEventChannelControl.value = "";
    }
  }
}

function bindIntegrityQuickRangeButtons() {
  document.querySelectorAll("[data-integrity-range]").forEach((button) => {
    button.addEventListener("click", () => {
      setIntegrityQuickRange(button.dataset.integrityRange);
    });
  });
}

function initializeIntegrityValidationControls() {
  const form = document.getElementById("integrity-validation-form");
  if (!form) {
    return;
  }

  if (!String(form.elements.namedItem("start_time")?.value || "").trim()) {
    setIntegrityQuickRange("last_24h");
  }
  syncIntegrityDatasetControls();

  const controlsToWatch = [
    "use_symbol_defaults",
    ...INTEGRITY_DATASET_FIELDS.map((dataType) => `integrity_data_type_${dataType}`),
  ];
  controlsToWatch.forEach((fieldName) => {
    const control = form.elements.namedItem(fieldName);
    if (!control) {
      return;
    }
    control.addEventListener("change", () => {
      syncIntegrityDatasetControls();
    });
  });

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      await runIntegrityValidation(form);
    } catch (error) {
      window.alert(error.message);
    }
  });
}

function getSelectedIntegrityDataTypes(form) {
  return INTEGRITY_DATASET_FIELDS.filter((dataType) => {
    return Boolean(form.elements.namedItem(`integrity_data_type_${dataType}`)?.checked);
  });
}

function getCurrentIntegrityForm() {
  return document.getElementById("integrity-validation-form");
}

function getCurrentIntegrityUnifiedSymbol() {
  return state.currentIntegrityResult?.unified_symbol || "";
}

function unifiedSymbolToVenueSymbol(unifiedSymbol) {
  return String(unifiedSymbol || "")
    .replace(/_PERP$/u, "")
    .replace(/_SPOT$/u, "");
}

function mapIntegrityDataTypeToBackfillDataset(unifiedSymbol, dataType) {
  if (dataType === "bars_1m") {
    return String(unifiedSymbol || "").endsWith("_SPOT") ? "spot_bars_1m" : "perp_bars_1m";
  }
  const aliases = {
    funding_rates: "funding_rates",
    open_interest: "open_interest",
    mark_prices: "mark_prices",
    index_prices: "index_prices",
    global_long_short_account_ratios: "global_long_short_account_ratios",
    top_trader_long_short_account_ratios: "top_trader_long_short_account_ratios",
    top_trader_long_short_position_ratios: "top_trader_long_short_position_ratios",
    taker_long_short_ratios: "taker_long_short_ratios",
  };
  return aliases[dataType] || null;
}

function canonicalizeBackfillDatasetSelector(selector) {
  const aliases = {
    btc_spot_bars_1m: "btc_spot_bars_1m",
    spot_bars_1m: "btc_spot_bars_1m",
    btc_perp_bars_1m: "btc_perp_bars_1m",
    perp_bars_1m: "btc_perp_bars_1m",
    funding_rates: "btc_perp_funding_rates",
    btc_perp_funding_rates: "btc_perp_funding_rates",
    open_interest: "btc_perp_open_interest",
    btc_perp_open_interest: "btc_perp_open_interest",
    mark_prices: "btc_perp_mark_prices",
    btc_perp_mark_prices: "btc_perp_mark_prices",
    index_prices: "btc_perp_index_prices",
    btc_perp_index_prices: "btc_perp_index_prices",
    global_long_short_account_ratios: "btc_perp_global_long_short_account_ratios",
    btc_perp_global_long_short_account_ratios: "btc_perp_global_long_short_account_ratios",
    top_trader_long_short_account_ratios: "btc_perp_top_trader_long_short_account_ratios",
    btc_perp_top_trader_long_short_account_ratios: "btc_perp_top_trader_long_short_account_ratios",
    top_trader_long_short_position_ratios: "btc_perp_top_trader_long_short_position_ratios",
    btc_perp_top_trader_long_short_position_ratios: "btc_perp_top_trader_long_short_position_ratios",
    taker_long_short_ratios: "btc_perp_taker_long_short_ratios",
    btc_perp_taker_long_short_ratios: "btc_perp_taker_long_short_ratios",
  };
  return aliases[String(selector || "").trim()] || null;
}

function findBackfillDatasetStatus(datasets, selectors) {
  const canonicalSelectors = (Array.isArray(selectors) ? selectors : [])
    .map((selector) => canonicalizeBackfillDatasetSelector(selector))
    .filter(Boolean);
  if (!canonicalSelectors.length) {
    return null;
  }
  return datasets.find((dataset) => canonicalSelectors.includes(dataset.dataset_key)) || null;
}

function appendUtcMinuteBoundary(timestamp, boundary) {
  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return timestamp;
  }
  if (boundary === "end") {
    parsed.setUTCSeconds(59, 0);
  } else {
    parsed.setUTCSeconds(0, 0);
  }
  return parsed.toISOString().replace(/\.\d{3}Z$/u, "Z");
}

function mergeIntegrityRepairWindows(windows) {
  if (!windows.length) {
    return [];
  }

  const ordered = [...windows].sort((left, right) => {
    return new Date(left.start_time).getTime() - new Date(right.start_time).getTime();
  });
  const merged = [ordered[0]];

  ordered.slice(1).forEach((window) => {
    const current = merged[merged.length - 1];
    const currentEndMs = new Date(current.end_time).getTime();
    const nextStartMs = new Date(window.start_time).getTime();
    if (nextStartMs <= currentEndMs + 1000) {
      if (new Date(window.end_time).getTime() > currentEndMs) {
        current.end_time = window.end_time;
      }
      current.label = `${current.label}+${window.label}`;
      return;
    }
    merged.push({ ...window });
  });

  return merged;
}

function buildBarsRepairWindowsFromFinding(finding) {
  const windows = [];
  if (!finding || typeof finding !== "object") {
    return windows;
  }

  if (finding.category === "gap") {
    (finding.detail_json?.segments || []).forEach((segment, index) => {
      if (!segment.gap_start || !segment.gap_end) {
        return;
      }
      windows.push({
        label: `gap_${index + 1}`,
        start_time: appendUtcMinuteBoundary(segment.gap_start, "start"),
        end_time: appendUtcMinuteBoundary(segment.gap_end, "end"),
      });
    });
  }

  if (finding.category === "corrupt") {
    (finding.detail_json?.corrupt_examples || []).forEach((example, index) => {
      if (!example.ts) {
        return;
      }
      windows.push({
        label: `corrupt_${index + 1}`,
        start_time: appendUtcMinuteBoundary(example.ts, "start"),
        end_time: appendUtcMinuteBoundary(example.ts, "end"),
      });
    });
    (finding.detail_json?.future_examples || []).forEach((example, index) => {
      if (!example.ts) {
        return;
      }
      windows.push({
        label: `future_${index + 1}`,
        start_time: appendUtcMinuteBoundary(example.ts, "start"),
        end_time: appendUtcMinuteBoundary(example.ts, "end"),
      });
    });
  }

  return mergeIntegrityRepairWindows(windows);
}

function setIntegrityRepairBusy(isBusy) {
  document.querySelectorAll("[data-integrity-repair-action]").forEach((button) => {
    button.disabled = isBusy;
  });
}

function setIntegrityRepairContext(context) {
  state.integrityRepairContext = context || null;
}

function clearIntegrityRepairContext() {
  state.integrityRepairContext = null;
}

function setIntegrityRepairStatus({ phase, title, detail, progress, stateClass }) {
  const container = document.getElementById("integrity-repair-status");
  const titleNode = document.getElementById("integrity-repair-status-title");
  const phaseNode = document.getElementById("integrity-repair-status-phase");
  const detailNode = document.getElementById("integrity-repair-status-detail");
  const progressNode = document.getElementById("integrity-repair-progress");
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

function createIntegrityFindingActionButton(label, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "secondary-button compact-button";
  button.dataset.integrityRepairAction = "true";
  button.textContent = label;
  button.addEventListener("click", async (event) => {
    event.preventDefault();
    event.stopPropagation();
    try {
      await onClick();
    } catch (error) {
      window.alert(error.message);
    }
  });
  return button;
}

function buildDatasetScopedIncrementalFindingAction(dataset, finding, label) {
  const unifiedSymbol = getCurrentIntegrityUnifiedSymbol();
  const backfillDataset = mapIntegrityDataTypeToBackfillDataset(unifiedSymbol, dataset?.data_type);
  if (!backfillDataset || Number(finding?.related_count || 0) <= 0) {
    return null;
  }
  return {
    label,
    execute: () => triggerBtcIncrementalBackfill({ datasets: [backfillDataset], sourceDataset: dataset?.data_type }),
  };
}

function isRetentionLimitedIntegrityDataset(dataType) {
  return [
    "open_interest",
    "global_long_short_account_ratios",
    "top_trader_long_short_account_ratios",
    "top_trader_long_short_position_ratios",
    "taker_long_short_ratios",
  ].includes(dataType);
}

function buildIntegrityFindingAction(dataset, finding) {
  if (dataset?.data_type === "bars_1m" && finding?.status === "fail" && ["gap", "corrupt"].includes(finding?.category)) {
    let label = finding.category === "gap" ? "Repair Gap" : "Repair Corrupt";
    if (finding.category === "corrupt") {
      const corruptCount = Number(finding.detail_json?.corrupt_examples?.length || 0);
      const futureCount = Number(finding.detail_json?.future_examples?.length || 0);
      if (futureCount > 0 && corruptCount === 0) {
        label = "Repair Future Row";
      } else if (futureCount > 0) {
        label = "Repair Corrupt/Future";
      }
    }
    return {
      label,
      execute: () => executeBarsIntegrityRepair(dataset, finding),
    };
  }

  if (finding?.category === "tail") {
    return buildDatasetScopedIncrementalFindingAction(dataset, finding, "Run Incremental");
  }

  if (finding?.category === "gap" && dataset?.data_type !== "bars_1m") {
    return buildDatasetScopedIncrementalFindingAction(dataset, finding, "Repair via Incremental");
  }

  if (finding?.category === "corrupt" && dataset?.data_type !== "bars_1m" && !isRetentionLimitedIntegrityDataset(dataset?.data_type)) {
    return buildDatasetScopedIncrementalFindingAction(dataset, finding, "Repair Corrupt via Incremental");
  }

  if (finding?.category === "coverage" && !isRetentionLimitedIntegrityDataset(dataset?.data_type)) {
    return buildDatasetScopedIncrementalFindingAction(dataset, finding, "Backfill Coverage");
  }

  return null;
}

async function executeBarsIntegrityRepair(dataset, finding) {
  const unifiedSymbol = getCurrentIntegrityUnifiedSymbol();
  const windows = buildBarsRepairWindowsFromFinding(finding);
  if (!windows.length) {
    throw new Error("No repair windows could be derived from the selected finding.");
  }

  setIntegrityRepairContext({
    type: "bars_repair",
    dataset: dataset.data_type,
    unifiedSymbol,
    windowCount: windows.length,
  });
  setIntegrityRepairBusy(true);
  setIntegrityRepairStatus({
    phase: "preparing",
    title: "Preparing Bars Repair",
    detail: `Building ${windows.length} bounded repair window(s) for ${unifiedSymbol}.`,
    progress: 12,
    stateClass: "is-running",
  });

  try {
    const payload = {
      exchange_code: "binance",
      symbol: unifiedSymbolToVenueSymbol(unifiedSymbol),
      unified_symbol: unifiedSymbol,
      interval: "1m",
      windows,
    };
    setIntegrityRepairStatus({
      phase: "repairing",
      title: "Repairing Bars Finding",
      detail: `Applying ${windows.length} bounded repair window(s) for ${unifiedSymbol}.`,
      progress: 46,
      stateClass: "is-running",
    });
    const result = await sendEnvelope("/api/v1/quality/integrity-repairs/bars", "POST", payload);

    setIntegrityRepairStatus({
      phase: "refreshing",
      title: "Refreshing Integrity Result",
      detail: `Repair affected ${formatValue(result.total_rows_written)} row(s). Re-running integrity validation now.`,
      progress: 82,
      stateClass: "is-running",
    });

    const form = getCurrentIntegrityForm();
    if (form) {
      await runIntegrityValidation(form);
    }

    setIntegrityRepairStatus({
      phase: "complete",
      title: "Bars Repair Completed",
      detail: `${dataset.data_type} finding repaired and integrity results refreshed.`,
      progress: 100,
      stateClass: "is-complete",
    });
  } catch (error) {
    setIntegrityRepairStatus({
      phase: "error",
      title: "Bars Repair Failed",
      detail: error.message || "The selected bars integrity finding could not be repaired.",
      progress: 100,
      stateClass: "is-error",
    });
    throw error;
  } finally {
    clearIntegrityRepairContext();
    setIntegrityRepairBusy(false);
  }
}

function renderIntegritySummaryCards(result) {
  const container = document.getElementById("integrity-result-summary");
  if (!container) {
    return;
  }
  if (!result) {
    container.innerHTML = '<div class="summary-empty">No integrity validation has been run in this session.</div>';
    return;
  }

  const summaryItems = [
    {
      label: "Symbol",
      value: formatValue(result.unified_symbol),
      detail: `${formatValue(result.exchange_code)} | persisted checks ${formatValue(result.persisted_checks_written)}`,
    },
    {
      label: "Window",
      value: `${formatValue(result.start_time)} -> ${formatValue(result.end_time)}`,
      detail: `Observed ${formatValue(result.observed_at)}`,
    },
    {
      label: "Datasets",
      value: `${formatValue(result.summary?.passed_datasets)} pass / ${formatValue(result.summary?.warning_datasets)} warning / ${formatValue(result.summary?.failed_datasets)} fail`,
      detail: `Total ${formatValue(result.summary?.dataset_count)}`,
    },
    {
      label: "Coverage / Tail",
      value: `${formatValue(result.summary?.total_coverage_shortfall_count)} / ${formatValue(result.summary?.total_tail_missing_count)}`,
      detail: "Coverage shortfall / tail points",
    },
    {
      label: "Internal Gap / Missing",
      value: `${formatValue(result.summary?.total_gap_count)} / ${formatValue(result.summary?.total_internal_missing_count)}`,
      detail: "Gap segments / internal missing points",
    },
    {
      label: "Duplicate / Corrupt",
      value: `${formatValue(result.summary?.total_duplicate_count)} / ${formatValue(result.summary?.total_corrupt_count)}`,
      detail: `Future rows ${formatValue(result.summary?.total_future_row_count)}`,
    },
    {
      label: "Persisted",
      value: `Checks ${formatValue(result.persisted_checks_written)}`,
      detail: `Gaps ${formatValue(result.persisted_gaps_written)}`,
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

    const detail = document.createElement("p");
    detail.className = "summary-detail";
    detail.textContent = item.detail;

    card.appendChild(label);
    card.appendChild(value);
    card.appendChild(detail);
    container.appendChild(card);
  });
}

function renderIntegrityDatasetDetail(dataset) {
  if (!dataset) {
    renderPropertyGrid(
      "integrity-dataset-summary",
      [],
      "Select a dataset row after running integrity validation."
    );
    renderTable("integrity-findings-table", [], []);
    renderJson("integrity-dataset-raw", {
      message: "Dataset detail will appear here.",
    });
    setIntegrityRepairStatus({
      phase: "idle",
      title: "Finding Repair Idle",
      detail: "Select a failing finding to run a supported repair action.",
      progress: 0,
      stateClass: "",
    });
    return;
  }

  const summaryItems = buildPropertyItemsFromObject(
    {
      data_type: dataset.data_type,
      status: dataset.status,
      row_count: dataset.row_count,
      expected_interval_seconds: dataset.expected_interval_seconds,
      expected_points: dataset.expected_points,
      profile_window_start: dataset.profile_window_start,
      available_from: dataset.available_from,
      available_to: dataset.available_to,
      safe_available_to: dataset.safe_available_to,
      selected_window_available_from: dataset.selected_window_available_from,
      selected_window_available_to: dataset.selected_window_available_to,
      missing_count: dataset.missing_count,
      coverage_shortfall_count: dataset.coverage_shortfall_count,
      internal_missing_count: dataset.internal_missing_count,
      tail_missing_count: dataset.tail_missing_count,
      gap_count: dataset.gap_count,
      duplicate_count: dataset.duplicate_count,
      corrupt_count: dataset.corrupt_count,
      future_row_count: dataset.future_row_count,
    },
    {
      data_type: "Data Type",
      row_count: "Row Count",
      expected_interval_seconds: "Expected Interval Seconds",
      expected_points: "Expected Points",
      profile_window_start: "Integrity Profile Start",
      available_from: "First Record Used For Integrity",
      available_to: "Last Record In Selected Window",
      safe_available_to: "Last Safe Record In Selected Window",
      selected_window_available_from: "First Record In Selected Window",
      selected_window_available_to: "Last Record In Selected Window",
      missing_count: "Total Missing Count",
      coverage_shortfall_count: "Coverage Shortfall Count",
      internal_missing_count: "Internal Missing Count",
      tail_missing_count: "Tail Missing Count",
      gap_count: "Internal Gap Count",
      duplicate_count: "Duplicate Count",
      corrupt_count: "Corrupt Count",
      future_row_count: "Future Row Count",
    },
    [
      "data_type",
      "status",
      "row_count",
      "expected_interval_seconds",
      "expected_points",
      "profile_window_start",
      "available_from",
      "safe_available_to",
      "selected_window_available_from",
      "selected_window_available_to",
      "missing_count",
      "coverage_shortfall_count",
      "internal_missing_count",
      "tail_missing_count",
      "gap_count",
      "duplicate_count",
      "corrupt_count",
      "future_row_count",
    ],
    { excludeEmpty: false }
  );

  renderPropertyGrid(
    "integrity-dataset-summary",
    summaryItems,
    "Dataset-level integrity summary will appear here."
  );

  renderTable(
    "integrity-findings-table",
    [
      { key: "category", label: "Category", type: "status" },
      { key: "severity", label: "Severity", type: "status" },
      { key: "status", label: "Status", type: "status" },
      { key: "related_count", label: "Count" },
      { key: "message", label: "Message" },
      {
        key: "action",
        label: "Action",
        render: (record) => {
          const action = buildIntegrityFindingAction(dataset, record);
          if (!action) {
            return "-";
          }
          return createIntegrityFindingActionButton(action.label, action.execute);
        },
      },
    ],
    dataset.findings || []
  );
  renderJson("integrity-dataset-raw", dataset);
}

function renderIntegrityValidationResult(result) {
  state.currentIntegrityResult = result || null;
  state.selectedIntegrityDataType = result?.datasets?.[0]?.data_type || null;

  renderIntegritySummaryCards(result);
  renderJson("integrity-result-raw", result || { message: "Full integrity payload will appear here." });

  setText(
    "integrity-validation-context",
    result
      ? `symbol=${result.unified_symbol} | datasets=${result.summary?.dataset_count ?? 0} | fail=${result.summary?.failed_datasets ?? 0} | warning=${result.summary?.warning_datasets ?? 0}`
      : "Run one bounded validation window to see the latest integrity summary."
  );

  const datasets = result?.datasets || [];
  renderTable(
    "integrity-datasets-table",
    [
      { key: "data_type", label: "Dataset" },
      { key: "status", label: "Status", type: "status" },
      { key: "available_from", label: "First Record Used For Integrity" },
      { key: "safe_available_to", label: "Last Safe Record In Selected Window" },
      { key: "coverage_shortfall_count", label: "Coverage" },
      { key: "gap_count", label: "Internal Gaps" },
      { key: "tail_missing_count", label: "Tail" },
      { key: "internal_missing_count", label: "Internal Missing" },
      { key: "duplicate_count", label: "Duplicate" },
      { key: "corrupt_count", label: "Corrupt" },
      { key: "future_row_count", label: "Future" }
    ],
    datasets,
    (record) => {
      state.selectedIntegrityDataType = record.data_type;
      renderIntegrityDatasetDetail(record);
    }
  );

  const selectedDataset =
    datasets.find((record) => record.data_type === state.selectedIntegrityDataType) || datasets[0] || null;
  renderIntegrityDatasetDetail(selectedDataset);
}

function clearBtcBackfillStatusPoll() {
  if (state.btcBackfillStatusPollHandle) {
    window.clearTimeout(state.btcBackfillStatusPollHandle);
    state.btcBackfillStatusPollHandle = null;
  }
}

function scheduleBtcBackfillStatusPoll(delayMs = 5000) {
  clearBtcBackfillStatusPoll();
  state.btcBackfillStatusPollHandle = window.setTimeout(() => {
    loadBtcBackfillStatus({ silent: true }).catch((error) => {
      setBtcBackfillActionStatus({
        phase: "error",
        title: "Status Refresh Failed",
        detail: error.message || "Could not refresh BTC backfill status.",
        progress: 100,
        stateClass: "is-error",
      });
    });
  }, delayMs);
}

function setBtcBackfillActionBusy(isBusy) {
  const controls = document.querySelectorAll("[data-btc-backfill-action]");
  controls.forEach((button) => {
    button.disabled = isBusy;
  });
}

function setBtcBackfillActionStatus({ phase, title, detail, progress, stateClass }) {
  const container = document.getElementById("btc-backfill-action-status");
  const titleNode = document.getElementById("btc-backfill-action-status-title");
  const phaseNode = document.getElementById("btc-backfill-action-status-phase");
  const detailNode = document.getElementById("btc-backfill-action-status-detail");
  const progressNode = document.getElementById("btc-backfill-action-progress");
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

function renderBtcBackfillSummaryCards(status) {
  const container = document.getElementById("btc-backfill-summary");
  if (!container) {
    return;
  }
  if (!status) {
    container.innerHTML = '<div class="summary-empty">No BTC backfill status has been loaded yet.</div>';
    return;
  }

  const summaryItems = [
    {
      label: "State / Mode",
      value: `${formatValue(status.state)} / ${formatValue(status.mode)}`,
      detail: status.updated_at ? `Updated ${status.updated_at}` : "No backfill run recorded yet.",
    },
    {
      label: "Progress",
      value: `${formatValue(status.overall?.tasks_completed)} / ${formatValue(status.overall?.tasks_total)}`,
      detail: `${formatValue(status.overall?.progress_pct)}% complete`,
    },
    {
      label: "Process",
      value: status.process_id ? `PID ${status.process_id}` : "No active process",
      detail: `alive=${formatValue(status.process_alive)} | requested_by=${formatValue(status.requested_by)}`,
    },
    {
      label: "Last Result",
      value: status.last_result?.dataset_key || status.last_result?.dataset || "—",
      detail: `status=${formatValue(status.last_result?.status)} | rows=${formatValue(status.last_result?.rows_written)}`,
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

    const detail = document.createElement("p");
    detail.className = "summary-detail";
    detail.textContent = item.detail;

    card.appendChild(label);
    card.appendChild(value);
    card.appendChild(detail);
    container.appendChild(card);
  });
}

function renderBtcBackfillDatasetDetail(dataset) {
  if (!dataset) {
    renderPropertyGrid(
      "btc-backfill-dataset-summary",
      [],
      "Select a dataset row after loading BTC backfill status."
    );
    renderJson("btc-backfill-dataset-raw", {
      message: "Dataset-level backfill detail will appear here.",
    });
    return;
  }

  const items = buildPropertyItemsFromObject(
    {
      dataset_key: dataset.dataset_key,
      label: dataset.label,
      unified_symbol: dataset.unified_symbol,
      chunk_total: dataset.chunk_total,
      chunks_completed: dataset.chunks_completed,
      rows_written: dataset.rows_written,
      first_nonzero_window_start: dataset.first_nonzero_window_start,
      last_nonzero_window_end: dataset.last_nonzero_window_end,
    },
    {
      dataset_key: "Dataset Key",
      label: "Label",
      unified_symbol: "Unified Symbol",
      chunk_total: "Chunk Total",
      chunks_completed: "Chunks Completed",
      rows_written: "Rows Written",
      first_nonzero_window_start: "First Nonzero Window Start",
      last_nonzero_window_end: "Last Nonzero Window End",
    },
    [
      "dataset_key",
      "label",
      "unified_symbol",
      "chunk_total",
      "chunks_completed",
      "rows_written",
      "first_nonzero_window_start",
      "last_nonzero_window_end",
    ],
    { excludeEmpty: false }
  );
  renderPropertyGrid(
    "btc-backfill-dataset-summary",
    items,
    "Dataset-level backfill detail will appear here."
  );
  renderJson("btc-backfill-dataset-raw", dataset);
}

function renderBtcBackfillStatus(status) {
  state.currentBtcBackfillStatus = status || null;
  const datasets = Array.isArray(status?.datasets) ? status.datasets : [];
  state.selectedBtcBackfillDatasetKey =
    datasets.find((dataset) => dataset.dataset_key === state.selectedBtcBackfillDatasetKey)?.dataset_key ||
    datasets[0]?.dataset_key ||
    null;

  renderBtcBackfillSummaryCards(status);
  renderJson("btc-backfill-status-raw", status || { message: "Backfill status will appear here." });
  setText(
    "btc-backfill-context",
    status
      ? `state=${status.state} | mode=${formatValue(status.mode)} | progress=${formatValue(status.overall?.tasks_completed)}/${formatValue(status.overall?.tasks_total)} | updated=${formatValue(status.updated_at)}`
      : "Load BTC backfill status to inspect the latest incremental/bootstrap progress."
  );

  renderTable(
    "btc-backfill-datasets-table",
    [
      { key: "dataset_key", label: "Dataset" },
      { key: "label", label: "Label" },
      { key: "chunks_completed", label: "Done" },
      { key: "chunk_total", label: "Total" },
      { key: "rows_written", label: "Rows" },
      { key: "last_nonzero_window_end", label: "Last Nonzero Window End" },
    ],
    datasets,
    (record) => {
      state.selectedBtcBackfillDatasetKey = record.dataset_key;
      renderBtcBackfillDatasetDetail(record);
    }
  );

  const selectedDataset =
    datasets.find((dataset) => dataset.dataset_key === state.selectedBtcBackfillDatasetKey) ||
    datasets[0] ||
    null;
  renderBtcBackfillDatasetDetail(selectedDataset);

  if (status?.state === "running") {
    setBtcBackfillActionStatus({
      phase: "running",
      title: "Backfill Running",
      detail: "A BTC backfill process is active; the Quality workspace will keep polling for updates.",
      progress: Number(status.overall?.progress_pct || 0),
      stateClass: "is-running",
    });
  } else if (status?.state === "not_started") {
    setBtcBackfillActionStatus({
      phase: "idle",
      title: "Backfill Status Idle",
      detail: "No BTC backfill run has been triggered yet from this workspace.",
      progress: 0,
      stateClass: "",
    });
  }

  const repairContext = state.integrityRepairContext;
  if (repairContext?.type === "incremental_backfill") {
    const progress = Number(status?.overall?.progress_pct || 0);
    const currentTaskLabel = status?.current_task?.label || status?.current_task?.dataset_key || "current dataset";
    const repairedDataset = findBackfillDatasetStatus(datasets, repairContext.datasets);
    if (status?.state === "running") {
      setIntegrityRepairStatus({
        phase: "monitoring",
        title: "Repair Backfill Running",
        detail: `Incremental repair for ${repairContext.dataset} is running. ${currentTaskLabel} is in progress.`,
        progress,
        stateClass: "is-running",
      });
    } else if (status?.state === "finished") {
      const rowsWritten = Number(repairedDataset?.rows_written || 0);
      setIntegrityRepairStatus({
        phase: "complete",
        title: "Repair Backfill Completed",
        detail:
          rowsWritten > 0
            ? `Incremental repair for ${repairContext.dataset} wrote ${rowsWritten} row(s). Re-run integrity to confirm the finding is cleared.`
            : `Incremental repair for ${repairContext.dataset} completed but wrote 0 rows. The source may not have returned data for the requested gap window(s); re-run integrity to confirm whether the finding remains.`,
        progress: 100,
        stateClass: rowsWritten > 0 ? "is-complete" : "is-error",
      });
      clearIntegrityRepairContext();
    } else if (status?.state === "failed" || status?.state === "stale" || status?.state === "status_unreadable") {
      setIntegrityRepairStatus({
        phase: "error",
        title: "Repair Backfill Failed",
        detail: status?.error?.message || `Incremental repair for ${repairContext.dataset} did not complete cleanly.`,
        progress: 100,
        stateClass: "is-error",
      });
      clearIntegrityRepairContext();
    } else if (status?.state === "not_started" || status?.state === "unknown") {
      setIntegrityRepairStatus({
        phase: "queued",
        title: "Repair Backfill Queued",
        detail: `Incremental repair for ${repairContext.dataset} has been requested. Waiting for the backfill status artifact to update.`,
        progress: 32,
        stateClass: "is-running",
      });
    }
  }

  if (status?.state === "running") {
    scheduleBtcBackfillStatusPoll();
  } else {
    clearBtcBackfillStatusPoll();
  }
}

async function loadBtcBackfillStatus({ silent = false } = {}) {
  const status = await fetchEnvelope("/api/v1/quality/backfill-status/binance-btc");
  renderBtcBackfillStatus(status);

  if (!silent) {
    setBtcBackfillActionStatus({
      phase: status.state === "running" ? "running" : "idle",
      title: status.state === "running" ? "Backfill Running" : "Backfill Status Loaded",
      detail:
        status.state === "running"
          ? "A BTC backfill process is currently active; status will auto-refresh."
          : "The latest BTC backfill status has been loaded into the Quality workspace.",
      progress: status.state === "running" ? Number(status.overall?.progress_pct || 0) : 100,
      stateClass: status.state === "running" ? "is-running" : "is-complete",
    });
  }
}

async function triggerBtcIncrementalBackfill(options = {}) {
  const datasets = Array.isArray(options.datasets) ? options.datasets.filter(Boolean) : [];
  const sourceDataset = options.sourceDataset || null;
  if (sourceDataset) {
    setIntegrityRepairContext({
      type: "incremental_backfill",
      dataset: sourceDataset,
      datasets,
    });
    setIntegrityRepairBusy(true);
    setIntegrityRepairStatus({
      phase: "submitting",
      title: "Submitting Repair Backfill",
      detail: `Requesting incremental repair for ${sourceDataset}.`,
      progress: 18,
      stateClass: "is-running",
    });
  }
  setBtcBackfillActionBusy(true);
  setBtcBackfillActionStatus({
    phase: "submitting",
    title: "Submitting Incremental Backfill",
    detail: datasets.length
      ? `Requesting detached incremental catch-up for ${datasets.join(", ")}.`
      : "Requesting a detached BTC incremental catch-up run from the Quality API.",
    progress: 18,
    stateClass: "is-running",
  });

  try {
    const result = await sendEnvelope("/api/v1/quality/backfill-jobs/binance-btc/incremental", "POST", {
      datasets: datasets.length ? datasets : undefined,
    });
    renderJson("btc-backfill-trigger-result", result);

    setBtcBackfillActionStatus({
      phase: result.already_running ? "running" : "started",
      title: result.already_running ? "Backfill Already Running" : "Incremental Backfill Started",
      detail: result.already_running
        ? "Another BTC backfill process is already active; loading the current status instead of starting a duplicate run."
        : `Detached process ${formatValue(result.job_id)} started${datasets.length ? ` for ${datasets.join(", ")}` : ""}; loading the latest backfill status now.`,
      progress: result.already_running ? 55 : 42,
      stateClass: "is-running",
    });

    await loadBtcBackfillStatus({ silent: true });

    setBtcBackfillActionStatus({
      phase: "monitoring",
      title: "Monitoring Backfill Status",
      detail: "The Quality workspace will keep polling the BTC backfill status while it remains running.",
      progress: state.currentBtcBackfillStatus?.state === "running"
        ? Number(state.currentBtcBackfillStatus?.overall?.progress_pct || 0)
        : 100,
      stateClass: state.currentBtcBackfillStatus?.state === "running" ? "is-running" : "is-complete",
    });

  } catch (error) {
    setBtcBackfillActionStatus({
      phase: "error",
      title: "Backfill Trigger Failed",
      detail: error.message || "The BTC incremental backfill could not be started.",
      progress: 100,
      stateClass: "is-error",
    });
    if (sourceDataset) {
      setIntegrityRepairStatus({
        phase: "error",
        title: "Incremental Trigger Failed",
        detail: error.message || `The incremental repair action for ${sourceDataset} could not be started.`,
        progress: 100,
        stateClass: "is-error",
      });
      clearIntegrityRepairContext();
    }
    throw error;
  } finally {
    setBtcBackfillActionBusy(false);
    if (sourceDataset) {
      setIntegrityRepairBusy(false);
    }
  }
}

async function runIntegrityValidation(form) {
  const formData = new FormData(form);
  const useSymbolDefaults = form.elements.namedItem("use_symbol_defaults")?.checked !== false;
  const selectedDataTypes = getSelectedIntegrityDataTypes(form);
  const startDate = String(formData.get("start_time") || "").trim();
  const endDate = String(formData.get("end_time") || "").trim();
  const payload = {
    exchange_code: String(formData.get("exchange_code") || "").trim() || "binance",
    unified_symbol: String(formData.get("unified_symbol") || "").trim(),
    start_time: expandUtcDateBoundary(startDate, "start"),
    end_time: expandUtcDateBoundary(endDate, "end"),
    persist_findings: Boolean(form.elements.namedItem("persist_findings")?.checked),
  };

  if (!payload.unified_symbol || !payload.start_time || !payload.end_time) {
    throw new Error("exchange_code, unified_symbol, start_date, and end_date are required");
  }

  if (endDate < startDate) {
    throw new Error("end_date must be on or after start_date");
  }

  if (!useSymbolDefaults) {
    if (!selectedDataTypes.length) {
      throw new Error("Select at least one dataset override or turn symbol defaults back on.");
    }
    payload.data_types = selectedDataTypes;
  }

  const rawEventChannel = String(formData.get("raw_event_channel") || "").trim();
  if (rawEventChannel) {
    payload.raw_event_channel = rawEventChannel;
  }

  setIntegrityValidationFormBusy(true);
  setIntegrityValidationStatus({
    phase: "submitting",
    title: "Submitting Validation Request",
    detail: "Sending the bounded integrity validation request to the quality API.",
    progress: 18,
    stateClass: "is-running",
  });

  try {
    setIntegrityValidationStatus({
      phase: "validating",
      title: "Integrity Validation Running",
      detail: "Waiting for the quality validator to scan the requested datasets and time window.",
      progress: 58,
      stateClass: "is-running",
    });
    const result = await sendEnvelope("/api/v1/quality/integrity", "POST", payload);

    setIntegrityValidationStatus({
      phase: "rendering",
      title: "Rendering Validation Results",
      detail: "Applying dataset summaries and findings to the current Quality workspace.",
      progress: 86,
      stateClass: "is-running",
    });
    renderIntegrityValidationResult(result);

    setIntegrityValidationStatus({
      phase: "complete",
      title: "Integrity Validation Completed",
      detail: `${result.unified_symbol} validated across ${result.summary?.dataset_count ?? 0} dataset(s).`,
      progress: 100,
      stateClass: "is-complete",
    });
  } catch (error) {
    setIntegrityValidationStatus({
      phase: "error",
      title: "Validation Failed",
      detail: error.message || "The integrity validation request failed.",
      progress: 100,
      stateClass: "is-error",
    });
    throw error;
  } finally {
    setIntegrityValidationFormBusy(false);
  }
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

function setIntegrityValidationFormBusy(isBusy) {
  const form = document.getElementById("integrity-validation-form");
  if (!form) {
    return;
  }
  form.classList.toggle("is-busy", isBusy);
  form.querySelectorAll("input, select, textarea, button").forEach((element) => {
    element.disabled = isBusy;
  });
  document.querySelectorAll("[data-integrity-range]").forEach((button) => {
    button.disabled = isBusy;
  });
}

function setIntegrityValidationStatus({ phase, title, detail, progress, stateClass }) {
  const container = document.getElementById("integrity-validation-status");
  const titleNode = document.getElementById("integrity-validation-status-title");
  const phaseNode = document.getElementById("integrity-validation-status-phase");
  const detailNode = document.getElementById("integrity-validation-status-detail");
  const progressNode = document.getElementById("integrity-validation-progress");
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
    renderJson("backtest-expected-observed-summary", {
      message: "Run-level investigation summary will appear here.",
    });
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
    renderJson("backtest-debug-trace-market-context", {
      message: "Market context snapshot will appear here.",
    });
    renderJson("backtest-debug-trace-decision", {
      message: "Decision payload will appear here.",
    });
    renderJson("backtest-debug-trace-risk", {
      message: "Risk outcomes will appear here.",
    });
    renderJson("backtest-debug-trace-investigations", {
      message: "Investigation anchors will appear here.",
    });
    renderJson("backtest-trace-note-detail", {
      message: "Trace investigation notes will appear here.",
    });
    renderJson("backtest-trace-note-result", {
      message: "Saved trace notes will appear here.",
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
    renderJson("backtest-debug-trace-market-context", {
      message: "Market context snapshot will appear here.",
    });
    renderJson("backtest-debug-trace-decision", {
      message: "Decision payload will appear here.",
    });
    renderJson("backtest-debug-trace-risk", {
      message: "Risk outcomes will appear here.",
    });
    renderJson("backtest-debug-trace-investigations", {
      message: "Investigation anchors will appear here.",
    });
    renderJson("backtest-trace-note-detail", {
      run_id: trace.run_id || null,
      debug_trace_id: trace.debug_trace_id || null,
      notes: [],
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
  renderJson(
    "backtest-debug-trace-market-context",
    trace.market_context_json || { message: "No market context captured for this step." },
  );
  renderJson("backtest-debug-trace-decision", trace.decision_json || {});
  renderJson("backtest-debug-trace-risk", trace.risk_outcomes_json || []);
  renderJson("backtest-debug-trace-investigations", trace.investigation_anchors || []);
  renderJson("backtest-debug-trace-detail", trace);
}

function resetTraceNoteForm() {
  const form = document.getElementById("backtest-trace-note-form");
  if (!form) {
    return;
  }
  form.reset();
  form.elements.annotation_id.value = "";
  form.elements.annotation_type.value = "investigation";
  form.elements.status.value = "in_review";
  form.elements.note_source.value = "human";
  form.elements.verification_state.value = "verified";
  form.elements.title.value = "";
  form.elements.summary.value = "";
  form.elements.verified_findings.value = "";
  form.elements.open_questions.value = "";
  form.elements.next_action.value = "";
}

function populateTraceNoteForm(note) {
  const form = document.getElementById("backtest-trace-note-form");
  if (!form) {
    return;
  }
  form.elements.annotation_id.value = note.annotation_id || "";
  form.elements.annotation_type.value = note.annotation_type || "investigation";
  form.elements.status.value = note.status || "in_review";
  form.elements.note_source.value = note.note_source || "human";
  form.elements.verification_state.value = note.verification_state || "verified";
  form.elements.title.value = note.title || "";
  form.elements.summary.value = note.summary || "";
  form.elements.verified_findings.value = (note.verified_findings || []).join("\n");
  form.elements.open_questions.value = (note.open_questions || []).join("\n");
  form.elements.next_action.value = note.next_action || "";
}

async function saveTraceInvestigationAnchor(formValues) {
  if (!state.selectedBacktestRunId) {
    throw new Error("No run selected.");
  }
  if (!state.selectedBacktestDebugTraceId) {
    throw new Error("Select a debug trace to anchor the investigation to.");
  }
  const payload = {
    scenario_id: String(formValues.scenario_id || "").trim() || null,
    expected_behavior: String(formValues.expected_behavior || "").trim() || null,
    observed_behavior: String(formValues.observed_behavior || "").trim() || null,
  };
  await sendEnvelope(
    `/api/v1/backtests/runs/${state.selectedBacktestRunId}/debug-traces/${state.selectedBacktestDebugTraceId}/investigation-anchors`,
    "POST",
    payload
  );
  document.getElementById("backtest-trace-investigation-form").reset();
  await loadBacktestDebugTraces();
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

async function loadTraceNotes(runId, debugTraceId, preferredAnnotationId = null) {
  const notesEnvelope = await fetchEnvelope(
    `/api/v1/backtests/runs/${runId}/debug-traces/${debugTraceId}/notes`
  );
  const notes = notesEnvelope.notes || [];
  const preferredNote =
    notes.find((note) => note.annotation_id === preferredAnnotationId) ||
    notes.find((note) => note.annotation_id === state.selectedTraceNoteId) ||
    notes.find((note) => note.note_source !== "system") ||
    notes[0] ||
    null;

  if (preferredNote) {
    state.selectedTraceNoteId = preferredNote.annotation_id;
  } else {
    state.selectedTraceNoteId = null;
  }

  renderTable(
    "backtest-trace-notes-table",
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
      state.selectedTraceNoteId = record.annotation_id;
      renderJson("backtest-trace-note-detail", record);
      if (record.note_source === "system") {
        resetTraceNoteForm();
      } else {
        populateTraceNoteForm(record);
      }
    }
  );

  if (preferredNote) {
    renderJson("backtest-trace-note-detail", preferredNote);
    if (preferredNote.note_source === "system") {
      resetTraceNoteForm();
    } else {
      populateTraceNoteForm(preferredNote);
    }
  } else {
    renderJson("backtest-trace-note-detail", {
      run_id: notesEnvelope.run_id,
      debug_trace_id: notesEnvelope.debug_trace_id,
      step_index: notesEnvelope.step_index,
      unified_symbol: notesEnvelope.unified_symbol,
      bar_time: notesEnvelope.bar_time,
      notes: [],
    });
    resetTraceNoteForm();
  }
}

function renderExpectedObservedOverview(overview) {
  if (!overview || !overview.run_id) {
    renderJson("backtest-expected-observed-summary", {
      message: "Run-level investigation summary will appear here.",
    });
    renderTable(
      "backtest-expected-observed-table",
      [
        { key: "debug_trace_id", label: "Trace" },
        { key: "step_index", label: "Step" },
        { key: "annotation_type", label: "Type" },
        { key: "status", label: "Status", type: "status" },
        { key: "note_source", label: "Source", type: "status" },
        { key: "scenario_ids", label: "Scenarios" },
        { key: "title", label: "Title" },
      ],
      []
    );
    return;
  }

  renderJson("backtest-expected-observed-summary", {
    run_id: overview.run_id,
    run_name: overview.run_name || null,
    total_trace_count: overview.total_trace_count,
    trace_count_with_notes: overview.trace_count_with_notes,
    total_note_count: overview.total_note_count,
    expected_vs_observed_note_count: overview.expected_vs_observed_note_count,
    unresolved_note_count: overview.unresolved_note_count,
    status_counts: overview.status_counts || {},
    annotation_type_counts: overview.annotation_type_counts || {},
    note_source_counts: overview.note_source_counts || {},
    scenario_counts: overview.scenario_counts || {},
  });

  renderTable(
    "backtest-expected-observed-table",
    [
      { key: "debug_trace_id", label: "Trace" },
      { key: "step_index", label: "Step" },
      { key: "bar_time", label: "Bar Time" },
      { key: "annotation_type", label: "Type", type: "status" },
      { key: "status", label: "Status", type: "status" },
      { key: "note_source", label: "Source", type: "status" },
      {
        key: "scenario_ids",
        label: "Scenarios",
        render: (record) => (record.scenario_ids || []).join(", "),
      },
      { key: "title", label: "Title" },
    ],
    overview.items || [],
    async (record) => {
      state.selectedBacktestDebugTraceId = record.debug_trace_id;
      state.selectedTraceNoteId = record.annotation_id;
      await loadBacktestDebugTraces({
        ...getBacktestTraceFilters(),
        limit: getBacktestTraceFilters().limit,
      });
    }
  );
}

async function renderBacktestDebugTraces(runId, debugTraces, appliedFilters) {
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
    async (record) => {
      state.selectedBacktestDebugTraceId = record.debug_trace_id;
      state.selectedTraceNoteId = null;
      renderBacktestDebugTraceDetail(record);
      await loadTraceNotes(runId, record.debug_trace_id);
    }
  );

  if (preferredTrace) {
    renderBacktestDebugTraceDetail(preferredTrace);
    await loadTraceNotes(runId, preferredTrace.debug_trace_id);
  } else {
    renderBacktestDebugTraceDetail({
      run_id: runId,
      trace_count: traceCount || 0,
      message: "No persisted debug traces matched the current filter for this run.",
    });
    renderTable(
      "backtest-trace-notes-table",
      [
        { key: "annotation_id", label: "Note" },
        { key: "annotation_type", label: "Type" },
        { key: "status", label: "Status", type: "status" },
        { key: "note_source", label: "Source", type: "status" },
        { key: "verification_state", label: "Verify", type: "status" },
        { key: "title", label: "Title" },
        { key: "updated_at", label: "Updated" },
      ],
      []
    );
    renderJson("backtest-trace-note-detail", {
      run_id: runId,
      notes: [],
      message: "Select a debug trace row to inspect notes.",
    });
    renderJson("backtest-trace-note-result", {
      message: "Saved trace notes will appear here.",
    });
    resetTraceNoteForm();
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

function renderSelectedComparedRun(run) {
  if (!run || !run.run_id) {
    const emptyMessage = "Select a compared run row to inspect compare-specific detail.";
    const summary = document.getElementById("backtest-compare-run-summary");
    if (summary) {
      summary.innerHTML = `<div class="summary-empty">${emptyMessage}</div>`;
    }
    renderPropertyGrid("backtest-compare-run-identity", [], "Run identity will appear here.");
    renderPropertyGrid("backtest-compare-run-kpis", [], "KPI snapshot will appear here.");
    renderPropertyGrid("backtest-compare-run-diagnostics", [], "Diagnostics and risk evidence will appear here.");
    renderPropertyGrid("backtest-compare-run-state", [], "Guardrail state will appear here.");
    return;
  }

  const summaryItems = [
    {
      label: "Run",
      value: run.run_id,
      detail: run.run_name || "Selected compare run",
      tone: run.diagnostic_status || "ok",
    },
    {
      label: "Diagnostics",
      value: `${run.diagnostic_warning_count || 0} / ${run.diagnostic_error_count || 0}`,
      detail: "Warnings / errors for this compared run",
      tone: run.diagnostic_error_count ? "error" : run.diagnostic_warning_count ? "warning" : "ok",
    },
    {
      label: "Blocked Intents",
      value: run.blocked_intent_count || 0,
      detail: "Runtime guardrail blocks observed during the run",
      tone: Number(run.blocked_intent_count || 0) > 0 ? "warning" : "ok",
    },
  ];
  const summary = document.getElementById("backtest-compare-run-summary");
  if (summary) {
    summary.innerHTML = summaryItems
      .map(
        (item) => `
          <article class="summary-card ${statusClass(item.tone)}">
            <p class="summary-label">${item.label}</p>
            <h4>${formatValue(item.value)}</h4>
            <p class="summary-detail">${item.detail}</p>
          </article>
        `
      )
      .join("");
  }

  renderPropertyGrid(
    "backtest-compare-run-identity",
    [
      { label: "Run Name", value: run.run_name },
      { label: "Strategy Code", value: run.strategy_code },
      { label: "Strategy Version", value: run.strategy_version },
      { label: "Account Code", value: run.account_code },
      { label: "Environment", value: run.environment },
      { label: "Status", value: run.status },
      { label: "Window Start", value: run.start_time },
      { label: "Window End", value: run.end_time },
      { label: "Universe", value: run.universe },
    ],
    "Run identity will appear here."
  );
  renderPropertyGrid(
    "backtest-compare-run-kpis",
    [
      { label: "Total Return", value: run.total_return },
      { label: "Annualized Return", value: run.annualized_return },
      { label: "Max Drawdown", value: run.max_drawdown },
      { label: "Turnover", value: run.turnover },
      { label: "Win Rate", value: run.win_rate },
      { label: "Fee Cost", value: run.fee_cost },
      { label: "Slippage Cost", value: run.slippage_cost },
    ],
    "KPI snapshot will appear here."
  );
  renderPropertyGrid(
    "backtest-compare-run-diagnostics",
    [
      { label: "Diagnostic Status", value: run.diagnostic_status },
      { label: "Warning Count", value: run.diagnostic_warning_count },
      { label: "Error Count", value: run.diagnostic_error_count },
      { label: "Blocked Intents", value: run.blocked_intent_count },
      { label: "Diagnostic Flags", value: run.diagnostic_flag_codes },
      { label: "Blocked Codes", value: run.block_counts_by_code },
      { label: "Outcome Counts", value: run.outcome_counts_by_code },
    ],
    "Diagnostics and risk evidence will appear here."
  );
  renderPropertyGrid(
    "backtest-compare-run-state",
    buildPropertyItemsFromObject(
      run.state_snapshot || {},
      {
        policy_code: "Policy Code",
        trading_timezone: "Trading Timezone",
      }
    ),
    "Guardrail state will appear here."
  );
}

function renderSelectedCompareDiff(diff) {
  if (!diff || !diff.field_name) {
    const summary = document.getElementById("backtest-compare-diff-summary");
    if (summary) {
      summary.innerHTML =
        '<div class="summary-empty">Select an assumption or diagnostics diff row to inspect run-by-run detail.</div>';
    }
    renderTable("backtest-compare-diff-values-table", [], []);
    renderJson("backtest-compare-diff-detail", {
      message: "Selected diff detail will appear here.",
    });
    return;
  }

  const values = diff.raw_values_by_run || [];
  const summaryItems = [
    {
      label: "Diff Type",
      value: diff.diff_type,
      detail: diff.diff_type === "diagnostic" ? "Diagnostics / runtime risk compare evidence" : "Run configuration / assumption compare evidence",
      tone: diff.diff_type,
    },
    {
      label: "Field",
      value: diff.field_name,
      detail: "Selected compare dimension",
      tone: "info",
    },
    {
      label: "Distinct Values",
      value: diff.distinct_value_count,
      detail: `${values.length} run-specific values captured`,
      tone: diff.distinct_value_count > 1 ? "warning" : "ok",
    },
  ];

  const summary = document.getElementById("backtest-compare-diff-summary");
  if (summary) {
    summary.innerHTML = summaryItems
      .map(
        (item) => `
          <article class="summary-card ${statusClass(item.tone)}">
            <p class="summary-label">${item.label}</p>
            <h4>${formatValue(item.value)}</h4>
            <p class="summary-detail">${item.detail}</p>
          </article>
        `
      )
      .join("");
  }

  renderTable(
    "backtest-compare-diff-values-table",
    [
      { key: "run_id", label: "Run" },
      { key: "value", label: "Value" },
    ],
    values.map((entry) => ({
      run_id: entry.run_id,
      value: formatValue(entry.value),
    })),
    (record) => {
      const matchedRunId = Number(record.run_id);
      if (!Number.isInteger(matchedRunId)) {
        return;
      }
      state.selectedComparedRunId = matchedRunId;
      const currentComparePayload = window.__lastCompareSetPayload || null;
      const matchedRun = currentComparePayload?.compared_runs?.find((run) => run.run_id === matchedRunId) || null;
      renderSelectedComparedRun(matchedRun);
    }
  );
  renderJson("backtest-compare-diff-detail", diff);
}

function renderCompareSummary(compareSet, assumptionDiffs, diagnosticsDiffs, comparisonFlags) {
  const runs = compareSet.compared_runs || [];
  const warningRuns = runs.filter((run) => run.diagnostic_status === "warning").length;
  const errorRuns = runs.filter((run) => run.diagnostic_status === "error").length;
  const blockedRuns = runs.filter((run) => Number(run.blocked_intent_count || 0) > 0).length;
  const totalBlockedIntents = runs.reduce((sum, run) => sum + Number(run.blocked_intent_count || 0), 0);
  const benchmarkCount = (compareSet.benchmark_deltas || []).length;
  const summaryItems = [
    {
      label: "Compared Runs",
      value: runs.length,
      detail: compareSet.compare_name || "Selected run set",
      tone: "ok",
    },
    {
      label: "Assumption Diffs",
      value: assumptionDiffs.length,
      detail: "Metadata, bundle, execution, and strategy-parameter differences",
      tone: assumptionDiffs.length ? "assumption" : "ok",
    },
    {
      label: "Diagnostics Diffs",
      value: diagnosticsDiffs.length,
      detail: "Status, guardrail, blocked-intent, and diagnostic-flag differences",
      tone: diagnosticsDiffs.length ? "diagnostic" : "ok",
    },
    {
      label: "Runs With Blocks",
      value: blockedRuns,
      detail: `${totalBlockedIntents} blocked intents across selected runs`,
      tone: blockedRuns ? "warning" : "ok",
    },
    {
      label: "Warn / Error Runs",
      value: `${warningRuns} / ${errorRuns}`,
      detail: "Diagnostics status distribution across compared runs",
      tone: errorRuns ? "error" : warningRuns ? "warning" : "ok",
    },
    {
      label: "Compare Flags",
      value: comparisonFlags.length,
      detail: benchmarkCount
        ? `${benchmarkCount} benchmark delta rows also available`
        : "No benchmark overlay selected",
      tone: comparisonFlags.some((flag) => flag.severity === "warning")
        ? "warning"
        : comparisonFlags.length
        ? "info"
        : "ok",
    },
  ];

  const container = document.getElementById("backtest-compare-summary");
  if (!container) {
    return;
  }
  if (!summaryItems.length) {
    container.innerHTML = '<div class="summary-empty">Create a compare set to see summary evidence cards.</div>';
    return;
  }
  container.innerHTML = summaryItems
    .map(
      (item) => `
        <article class="summary-card ${statusClass(item.tone)}">
          <p class="summary-label">${item.label}</p>
          <h4>${formatValue(item.value)}</h4>
          <p class="summary-detail">${item.detail}</p>
        </article>
      `
    )
    .join("");
}

function renderCompareResult(compareSet) {
  const runs = compareSet.compared_runs || [];
  const assumptionDiffs = (compareSet.assumption_diffs || []).map((diff) => ({
    diff_key: `assumption:${diff.field_name}`,
    diff_type: "assumption",
    field_name: diff.field_name,
    distinct_value_count: diff.distinct_value_count,
    raw_values_by_run: diff.values_by_run || [],
    values_by_run: (diff.values_by_run || [])
      .map((value) => `${value.run_id}: ${formatValue(value.value)}`)
      .join(" | "),
  }));
  const diagnosticsDiffs = (compareSet.diagnostics_diffs || []).map((diff) => ({
    diff_key: `diagnostic:${diff.field_name}`,
    diff_type: "diagnostic",
    field_name: diff.field_name,
    distinct_value_count: diff.distinct_value_count,
    raw_values_by_run: diff.values_by_run || [],
    values_by_run: (diff.values_by_run || [])
      .map((value) => `${value.run_id}: ${formatValue(value.value)}`)
      .join(" | "),
  }));
  window.__lastCompareSetPayload = compareSet;
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
  renderCompareSummary(compareSet, assumptionDiffs, diagnosticsDiffs, comparisonFlags);
  renderJson("backtest-compare-result", compareSet);
  renderTable(
    "backtest-compare-runs-table",
    [
      { key: "run_id", label: "Run" },
      { key: "run_name", label: "Run Name" },
      { key: "strategy_code", label: "Strategy" },
      { key: "strategy_version", label: "Version" },
      { key: "diagnostic_status", label: "Diag", type: "status" },
      { key: "diagnostic_warning_count", label: "Warn" },
      { key: "diagnostic_error_count", label: "Err" },
      { key: "blocked_intent_count", label: "Blocked" },
      { key: "total_return", label: "Return" },
      { key: "max_drawdown", label: "Max DD" },
      { key: "turnover", label: "Turnover" },
      { key: "fee_cost", label: "Fees" },
      { key: "slippage_cost", label: "Slip" },
    ],
    runs,
    (record) => {
      state.selectedComparedRunId = record.run_id;
      renderSelectedComparedRun(record);
    }
  );
  const preferredRun =
    runs.find((run) => run.run_id === state.selectedComparedRunId) ||
    runs[0] ||
    null;
  state.selectedComparedRunId = preferredRun?.run_id || null;
  renderSelectedComparedRun(preferredRun);
  renderTable(
    "backtest-compare-assumption-diffs-table",
    [
      { key: "field_name", label: "Field" },
      { key: "distinct_value_count", label: "Distinct" },
      { key: "values_by_run", label: "Values by Run" },
    ],
    assumptionDiffs,
    (record) => {
      state.selectedCompareDiffKey = record.diff_key;
      renderSelectedCompareDiff(record);
    }
  );
  renderTable(
    "backtest-compare-diagnostics-diffs-table",
    [
      { key: "field_name", label: "Field" },
      { key: "distinct_value_count", label: "Distinct" },
      { key: "values_by_run", label: "Values by Run" },
    ],
    diagnosticsDiffs,
    (record) => {
      state.selectedCompareDiffKey = record.diff_key;
      renderSelectedCompareDiff(record);
    }
  );
  const allDiffs = [...assumptionDiffs, ...diagnosticsDiffs];
  const preferredDiff =
    allDiffs.find((diff) => diff.diff_key === state.selectedCompareDiffKey) ||
    allDiffs[0] ||
    null;
  state.selectedCompareDiffKey = preferredDiff?.diff_key || null;
  renderSelectedCompareDiff(preferredDiff);
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
  state.selectedTraceNoteId = null;
  const traceFilters = getBacktestTraceFilters();
  const [detail, diagnostics, artifacts, breakdown, signals, orders, fills, timeseries, debugTraces, expectedObserved] =
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
      fetchEnvelope(`/api/v1/backtests/runs/${runId}/expected-vs-observed`),
      ]);
  renderBacktestRunSummary(detail);
  renderBacktestRunStructuredDetails(detail);
  renderJson("backtest-run-detail", detail);
  renderBacktestDiagnostics(diagnostics);
  renderExpectedObservedOverview(expectedObserved);
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
  await renderBacktestDebugTraces(runId, debugTraces, traceFilters);
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
  const expectedObserved = await fetchEnvelope(
    `/api/v1/backtests/runs/${state.selectedBacktestRunId}/expected-vs-observed`
  );
  renderExpectedObservedOverview(expectedObserved);
  await renderBacktestDebugTraces(state.selectedBacktestRunId, debugTraces, traceFilters);
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
  const strategyCode = String(formValues.strategy_code || "").trim() || "btc_momentum";
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

  const strategyParams = {
    short_window: Number(formValues.short_window || 5),
    long_window: Number(formValues.long_window || 20),
    target_qty: formValues.target_qty || "1",
    allow_short: parseBooleanInput(formValues.allow_short),
  };
  if (strategyCode === "btc_sentiment_momentum") {
    const maxGlobalLongShortRatio = String(formValues.max_global_long_short_ratio || "").trim();
    const minTakerBuySellRatio = String(formValues.min_taker_buy_sell_ratio || "").trim();
    if (maxGlobalLongShortRatio !== "") {
      strategyParams.max_global_long_short_ratio = maxGlobalLongShortRatio;
    }
    if (minTakerBuySellRatio !== "") {
      strategyParams.min_taker_buy_sell_ratio = minTakerBuySellRatio;
    }
  }
  if (strategyCode === "btc_4h_breakout_perp") {
    strategyParams.trend_fast_ema = Number(formValues.trend_fast_ema || 20);
    strategyParams.trend_slow_ema = Number(formValues.trend_slow_ema || 50);
    strategyParams.breakout_lookback_bars = Number(formValues.breakout_lookback_bars || 20);
    strategyParams.atr_window = Number(formValues.atr_window || 14);
    strategyParams.initial_stop_atr = String(formValues.initial_stop_atr || "2").trim() || "2";
    strategyParams.trailing_stop_atr = String(formValues.trailing_stop_atr || "1.5").trim() || "1.5";
    strategyParams.exit_on_ema20_cross = parseBooleanInput(formValues.exit_on_ema20_cross);
    strategyParams.risk_per_trade_pct = String(formValues.risk_per_trade_pct || "0.005").trim() || "0.005";
    strategyParams.volatility_floor_atr_pct = String(formValues.volatility_floor_atr_pct || "0.008").trim() || "0.008";
    strategyParams.volatility_ceiling_atr_pct = String(formValues.volatility_ceiling_atr_pct || "0.08").trim() || "0.08";
    strategyParams.max_funding_rate_long = String(formValues.max_funding_rate_long || "0.0005").trim() || "0.0005";
    strategyParams.oi_change_pct_window = String(formValues.oi_change_pct_window || "0.05").trim() || "0.05";
    strategyParams.min_price_change_pct_for_oi_confirmation =
      String(formValues.min_price_change_pct_for_oi_confirmation || "0.01").trim() || "0.01";
    strategyParams.skip_entries_within_minutes_of_funding = Number(
      formValues.skip_entries_within_minutes_of_funding || 30
    );
    strategyParams.max_consecutive_losses = Number(formValues.max_consecutive_losses || 3);
    strategyParams.max_daily_r_multiple_loss =
      String(formValues.max_daily_r_multiple_loss || "2").trim() || "2";
    delete strategyParams.short_window;
    delete strategyParams.long_window;
    delete strategyParams.target_qty;
    delete strategyParams.allow_short;
  }

  const payload = {
    run_name: formValues.run_name,
    session: {
      session_code: `${strategyCode}_${Date.now()}`,
      environment: "backtest",
      account_code: formValues.account_code || "paper_main",
      strategy_code: strategyCode,
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
    strategy_params: strategyParams,
    persist_signals: false,
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

async function saveTraceInvestigationNote(formValues) {
  if (!state.selectedBacktestRunId || !state.selectedBacktestDebugTraceId) {
    throw new Error("Select a debug trace before saving investigation notes.");
  }
  const annotationId = Number(formValues.annotation_id);
  const payload = {
    annotation_type: String(formValues.annotation_type || "investigation").trim() || "investigation",
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
    `/api/v1/backtests/runs/${state.selectedBacktestRunId}/debug-traces/${state.selectedBacktestDebugTraceId}/notes`,
    "POST",
    payload
  );
  renderJson("backtest-trace-note-result", saved);
  await loadTraceNotes(state.selectedBacktestRunId, state.selectedBacktestDebugTraceId, saved.annotation_id);
}

async function loadQuality(filters = {}) {
  const [checks, gaps, backfillStatus] = await Promise.all([
    fetchEnvelope("/api/v1/quality/checks", { limit: 30, latest_only: "true", ...filters }),
    fetchEnvelope("/api/v1/quality/gaps", { limit: 30, status: "open", unified_symbol: filters.unified_symbol }),
    fetchEnvelope("/api/v1/quality/backfill-status/binance-btc"),
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

  renderBtcBackfillStatus(backfillStatus);
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
  if (viewName !== "quality") {
    clearBtcBackfillStatusPoll();
  }
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

function activateBacktestSubtab(tabName) {
  document.querySelectorAll(".workspace-tab[data-subtab]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.subtab === tabName);
  });
  document.querySelectorAll(".backtest-subtab").forEach((tab) => {
    tab.classList.toggle("is-active-tab", tab.dataset.subtabId === tabName);
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
  enhanceJsonShells();
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
  bindForm("backtest-trace-investigation-form", saveTraceInvestigationAnchor);
  bindForm("backtest-trace-note-form", saveTraceInvestigationNote);
  bindBacktestPresetButtons();
  initializeBacktestLaunchControls();
  document.querySelectorAll(".workspace-tab[data-subtab]").forEach((btn) => {
    btn.addEventListener("click", () => activateBacktestSubtab(btn.dataset.subtab));
  });
  bindIntegrityQuickRangeButtons();
  initializeIntegrityValidationControls();
  document.getElementById("backtest-compare-note-reset")?.addEventListener("click", () => {
    resetCompareNoteForm();
  });
  document.getElementById("backtest-trace-note-reset")?.addEventListener("click", () => {
    resetTraceNoteForm();
  });
  document.getElementById("btc-backfill-refresh")?.addEventListener("click", () => {
    loadBtcBackfillStatus().catch((error) => window.alert(error.message));
  });
  document.getElementById("btc-backfill-run-incremental")?.addEventListener("click", () => {
    triggerBtcIncrementalBackfill().catch((error) => window.alert(error.message));
  });
  window.addEventListener("beforeunload", () => {
    clearBtcBackfillStatusPoll();
  });

  try {
    await loadOverview();
  } catch (error) {
    window.alert(error.message);
  }
});
