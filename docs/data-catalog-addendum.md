# Data Catalog Addendum

## Purpose

This document extends `docs/data-catalog.md` with additional data domains identified during a second review of the collection plan.

These additions focus on the most commonly missed data needed for:
- production trading auditability
- treasury and account reconciliation
- margin and financing cost attribution
- execution latency analysis
- strategy deployment traceability

---

## 1. Strategy Deployment and Change Audit

### 1.1 Strategy Deployments
- **Table**: `strategy.deployments`
- **Purpose**: Track when a strategy version is rolled out, stopped, or changed in each environment
- **Source**: Internal deployment workflow / orchestration layer
- **Update frequency**: On each deployment or stop event
- **Primary identifier**: `deployment_id`
- **Key fields**:
  - `strategy_version_id`
  - `environment`
  - `deployment_status`
  - `deployed_by`
  - `rollout_time`
  - `stop_time`
  - `git_commit_sha`
  - `image_tag`
  - `config_snapshot_json`
  - `reason_code`
- **Used by**: production audit, incident review, strategy lifecycle history

### 1.2 Strategy Config Change Audit
- **Table**: `strategy.config_change_audit`
- **Purpose**: Record strategy parameter and configuration changes over time
- **Source**: Internal strategy admin / deployment workflow
- **Update frequency**: On each config or parameter change
- **Primary identifier**: `config_change_id`
- **Key fields**:
  - `strategy_version_id`
  - `deployment_id`
  - `changed_by`
  - `change_time`
  - `change_type`
  - `old_config_json`
  - `new_config_json`
  - `reason_code`
- **Used by**: reproducibility, performance regression analysis, governance

---

## 2. Treasury and Transfer Data

### 2.1 Deposits and Withdrawals
- **Table**: `execution.deposits_withdrawals`
- **Purpose**: Track treasury movement events with chain and transaction context
- **Source**: Exchange wallet history APIs / treasury operations
- **Update frequency**: Event-driven and reconciliation batch
- **Primary identifier**: `treasury_event_id`
- **Key fields**:
  - `event_type`
  - `network`
  - `tx_hash`
  - `wallet_address`
  - `address_tag`
  - `amount`
  - `fee_amount`
  - `fee_asset_id`
  - `requested_at`
  - `completed_at`
  - `status`
  - `external_reference_id`
- **Used by**: treasury operations, wallet reconciliation, transfer cost accounting

---

## 3. Borrowing, Lending, and Financing Data

### 3.1 Borrow and Lend Rates
- **Table**: `execution.borrow_lend_rates`
- **Purpose**: Store financing rate time series for margin and lending products
- **Source**: Exchange margin APIs / financing endpoints
- **Update frequency**: Periodic polling
- **Primary identifier**: `rate_id`
- **Key fields**:
  - `exchange_id`
  - `asset_id`
  - `margin_mode`
  - `ts`
  - `borrow_rate`
  - `lend_rate`
- **Used by**: margin strategy costs, financing attribution, what-if backtesting

### 3.2 Borrow and Lend Events
- **Table**: `execution.borrow_lend_events`
- **Purpose**: Track borrow, repay, and accrued interest events
- **Source**: Exchange account financing history APIs / internal reconciliation
- **Update frequency**: Event-driven / reconciliation batch
- **Primary identifier**: `borrow_event_id`
- **Key fields**:
  - `event_time`
  - `event_type`
  - `principal_amount`
  - `interest_amount`
  - `outstanding_amount`
  - `external_reference_id`
- **Used by**: financing accounting, margin cost analysis, debt monitoring

---

## 4. Execution Timing and Latency Data

### 4.1 Execution Latency Metrics
- **Table**: `execution.execution_latency_metrics`
- **Purpose**: Measure timing across signal generation, submission, exchange acknowledgment, and fills
- **Source**: Strategy engine, execution engine, exchange callbacks, websocket timestamps
- **Update frequency**: Per order lifecycle
- **Primary identifier**: `latency_metric_id`
- **Key fields**:
  - `signal_time`
  - `order_submit_time`
  - `exchange_ack_time`
  - `first_fill_time`
  - `final_fill_time`
  - `ws_receive_time`
  - `local_process_time_ms`
  - `signal_to_submit_ms`
  - `submit_to_ack_ms`
  - `ack_to_first_fill_ms`
  - `submit_to_final_fill_ms`
- **Used by**: latency monitoring, slippage diagnosis, paper/live comparison

---

## 5. Exchange Status and Forced Reduction Data

### 5.1 Exchange Status Events
- **Table**: `risk.exchange_status_events`
- **Purpose**: Track exchange or instrument trading status changes such as maintenance, pause, resume, or delisting
- **Source**: Exchange system status APIs / announcements / internal sync jobs
- **Update frequency**: Event-driven / periodic sync
- **Primary identifier**: `exchange_status_event_id`
- **Key fields**:
  - `exchange_id`
  - `instrument_id`
  - `event_time`
  - `event_type`
  - `status`
  - `detail_json`
- **Used by**: trading guards, outage windows, post-mortems, backtest exclusions

### 5.2 Forced Reduction Events
- **Table**: `risk.forced_reduction_events`
- **Purpose**: Capture ADL, forced deleveraging, forced reduction, and related exchange-imposed position changes
- **Source**: Exchange account events / reconciliation workflow
- **Update frequency**: Event-driven
- **Primary identifier**: `forced_reduction_event_id`
- **Key fields**:
  - `account_id`
  - `instrument_id`
  - `event_time`
  - `event_type`
  - `qty`
  - `price`
  - `amount`
  - `external_reference_id`
- **Used by**: exception accounting, risk review, unexplained PnL reconciliation

---

## 6. Universe and Allocation History

### 6.1 Universe Snapshots
- **Table**: `backtest.universe_snapshots`
- **Purpose**: Persist the symbol universe considered by a strategy or run at a point in time
- **Source**: Backtest engine / portfolio construction layer
- **Update frequency**: Per rebalance or universe refresh
- **Primary key**: `(run_id, snapshot_time)`
- **Key fields**:
  - `universe_json`
- **Used by**: reproducibility, universe drift review, ranking/debug workflows

### 6.2 Portfolio Allocation History
- **Table**: `backtest.portfolio_allocation_history`
- **Purpose**: Track target versus realized allocation by symbol over time
- **Source**: Portfolio construction layer / backtest analytics / live snapshots
- **Update frequency**: Per rebalance or snapshot interval
- **Primary identifier**: `allocation_id`
- **Key fields**:
  - `snapshot_time`
  - `account_id`
  - `instrument_id`
  - `target_weight`
  - `actual_weight`
  - `target_notional`
  - `actual_notional`
  - `cash_weight`
  - `hedge_weight`
  - `reason_code`
- **Used by**: portfolio attribution, rebalance analysis, target-vs-actual diagnostics

---

## 7. Priority Assessment

### Add Now
1. `strategy.deployments`
2. `strategy.config_change_audit`
3. `execution.deposits_withdrawals`
4. `execution.execution_latency_metrics`

### Add Before Margin / Financing Strategies
1. `execution.borrow_lend_rates`
2. `execution.borrow_lend_events`

### Add Before Broader Multi-Asset or Production Rollout
1. `risk.exchange_status_events`
2. `risk.forced_reduction_events`
3. `backtest.universe_snapshots`
4. `backtest.portfolio_allocation_history`

---

## 8. Recommended Source Mapping

### Internal Services
- deployment workflow -> `strategy.deployments`, `strategy.config_change_audit`
- portfolio constructor -> `backtest.universe_snapshots`, `backtest.portfolio_allocation_history`
- execution service -> `execution.execution_latency_metrics`

### Exchange Private APIs
- wallet history -> `execution.deposits_withdrawals`
- margin/loan history -> `execution.borrow_lend_events`
- borrow rate endpoints -> `execution.borrow_lend_rates`
- liquidation / ADL / position adjustment events -> `risk.forced_reduction_events`
- exchange status endpoints or announcements -> `risk.exchange_status_events`
