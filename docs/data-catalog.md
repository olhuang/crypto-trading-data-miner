# Data Catalog

## Purpose

This document defines what data the system collects, why it is collected, where it comes from, how often it updates, and which tables store it.

The goal is to make the collection scope explicit across:

- backtesting
- paper trading
- live trading
- monitoring and audit

---

## 1. Reference Data

### 1.1 Exchanges
- **Table**: `ref.exchanges`
- **Purpose**: Registry of supported trading venues
- **Source**: Internal master data
- **Update frequency**: Rare / manual
- **Primary identifiers**: `exchange_id`, `exchange_code`
- **Used by**: instruments, accounts, ingestion jobs, raw market events

### 1.2 Assets
- **Table**: `ref.assets`
- **Purpose**: Canonical asset registry such as BTC, ETH, USDT
- **Source**: Internal master data
- **Update frequency**: Rare / manual
- **Primary identifiers**: `asset_id`, `asset_code`
- **Used by**: instruments, balances, ledger, fees

### 1.3 Instruments
- **Table**: `ref.instruments`
- **Purpose**: Canonical instrument definitions across exchanges
- **Source**: Exchange exchangeInfo / instrument metadata APIs plus manual normalization
- **Update frequency**: Daily sync plus event-driven when listing or delisting changes
- **Primary identifiers**: `instrument_id`, `(exchange_id, venue_symbol)`
- **Key fields**:
  - `venue_symbol`
  - `unified_symbol`
  - `instrument_type`
  - `base_asset_id`
  - `quote_asset_id`
  - `settlement_asset_id`
  - `tick_size`
  - `lot_size`
  - `min_qty`
  - `min_notional`
  - `contract_size`
  - `status`
  - `launch_time`
  - `delist_time`
- **Used by**: all market data, signal, execution, backtest, risk tables

### 1.4 Fee Schedules
- **Table**: `ref.fee_schedules`
- **Purpose**: Maker/taker fee assumptions and historical fee model tracking
- **Source**: Exchange fee schedule pages / account tier info / manual entry
- **Update frequency**: When tiers or fee schedule change
- **Primary identifiers**: `fee_schedule_id`
- **Used by**: backtest, execution cost analysis, attribution

---

## 2. Market Data

### 2.1 OHLCV Bars
- **Table**: `md.bars_1m`
- **Purpose**: Primary V1 historical bar data for research and backtests
- **Source**: Exchange kline/candlestick APIs
- **Update frequency**: Every minute
- **Primary key**: `(instrument_id, bar_time)`
- **Key fields**:
  - `open`, `high`, `low`, `close`
  - `volume`
  - `quote_volume`
  - `trade_count`
- **Used by**: signal generation, backtests, monitoring dashboards
- **Notes**: V2 may add `bars_1s`, `bars_5m`, `bars_1h`

### 2.2 Trades
- **Table**: `md.trades`
- **Purpose**: Tick-level trade history for replay, microstructure, and higher-fidelity backtests
- **Source**: Exchange public trade websocket / REST trade history
- **Update frequency**: Real-time / batch backfill
- **Primary key**: `(instrument_id, exchange_trade_id)`
- **Key fields**:
  - `event_time`
  - `ingest_time`
  - `price`
  - `qty`
  - `aggressor_side`
- **Used by**: trade replay, slippage models, trade-flow features

### 2.3 Funding Rates
- **Table**: `md.funding_rates`
- **Purpose**: Perpetual futures funding history
- **Source**: Exchange funding history APIs
- **Update frequency**: Per funding interval, typically every 8h depending on exchange
- **Primary key**: `(instrument_id, funding_time)`
- **Key fields**:
  - `funding_rate`
  - `mark_price`
  - `index_price`
- **Used by**: perp strategy research, carry analysis, funding PnL attribution

### 2.4 Open Interest
- **Table**: `md.open_interest`
- **Purpose**: Derivatives positioning proxy
- **Source**: Exchange open interest APIs
- **Update frequency**: Exchange-dependent, commonly every few seconds to minutes
- **Primary key**: `(instrument_id, ts)`
- **Used by**: regime detection, perp signal generation, crowding analysis

### 2.5 Order Book Snapshots
- **Table**: `md.orderbook_snapshots`
- **Purpose**: Point-in-time depth book states
- **Source**: Exchange order book snapshot endpoints or internally reconstructed books
- **Update frequency**: Scheduled snapshots, e.g. every few seconds or minutes
- **Primary key**: `(instrument_id, snapshot_time)`
- **Key fields**:
  - `depth_levels`
  - `bids_json`
  - `asks_json`
  - `checksum`
  - `source`
- **Used by**: execution modeling, liquidity estimation, order book replay

### 2.6 Order Book Deltas
- **Table**: `md.orderbook_deltas`
- **Purpose**: Incremental order book updates for real-time state reconstruction
- **Source**: Exchange websocket depth streams
- **Update frequency**: Real-time
- **Primary identifier**: `delta_id`
- **Key fields**:
  - `event_time`
  - `ingest_time`
  - `first_update_id`
  - `final_update_id`
  - `bids_json`
  - `asks_json`
  - `checksum`
- **Used by**: live book building, queue position estimates, advanced slippage simulation

### 2.7 Mark Prices
- **Table**: `md.mark_prices`
- **Purpose**: Canonical mark price time series for perp PnL and liquidation math
- **Source**: Exchange premium/index/mark price feeds
- **Update frequency**: Real-time or frequent polling
- **Primary key**: `(instrument_id, ts)`
- **Used by**: unrealized PnL, liquidation price monitoring, funding logic

### 2.8 Index Prices
- **Table**: `md.index_prices`
- **Purpose**: Underlying index reference series for derivatives
- **Source**: Exchange index price feeds
- **Update frequency**: Real-time or frequent polling
- **Primary key**: `(instrument_id, ts)`
- **Used by**: basis analysis, mark/index divergence monitoring

### 2.9 Liquidations
- **Table**: `md.liquidations`
- **Purpose**: Public liquidation events useful for regime detection and stress signals
- **Source**: Exchange liquidation feeds where available
- **Update frequency**: Event-driven
- **Primary identifier**: `liquidation_id`
- **Key fields**:
  - `event_time`
  - `side`
  - `price`
  - `qty`
  - `notional`
- **Used by**: liquidation spike detection, volatility stress models

### 2.10 Raw Market Events
- **Table**: `md.raw_market_events`
- **Purpose**: Store unnormalized source payloads for replay and debugging
- **Source**: All supported exchange REST/websocket data collectors
- **Update frequency**: Real-time / batch backfill
- **Primary identifier**: `raw_event_id`
- **Key fields**:
  - `exchange_id`
  - `instrument_id`
  - `channel`
  - `event_type`
  - `event_time`
  - `ingest_time`
  - `source_message_id`
  - `payload_json`
- **Used by**: parser debugging, reprocessing, schema evolution, audit

---

## 3. Strategy Data

### 3.1 Strategies
- **Table**: `strategy.strategies`
- **Purpose**: Top-level strategy registry
- **Source**: Internal application configuration
- **Update frequency**: On strategy creation / update
- **Primary identifier**: `strategy_id`

### 3.2 Strategy Versions
- **Table**: `strategy.strategy_versions`
- **Purpose**: Versioned strategy definitions and parameter sets
- **Source**: Internal application configuration / deployment workflow
- **Update frequency**: On each strategy version release
- **Primary identifier**: `strategy_version_id`
- **Key fields**:
  - `version_code`
  - `params_json`
  - `feature_version`
  - `execution_version`
  - `risk_version`
  - `is_active`
- **Used by**: signals, orders, backtest runs, reproducibility

### 3.3 Signals
- **Table**: `strategy.signals`
- **Purpose**: Persist strategy decisions before execution
- **Source**: Strategy engine
- **Update frequency**: Per strategy evaluation cycle
- **Primary identifier**: `signal_id`
- **Key fields**:
  - `signal_time`
  - `signal_type`
  - `direction`
  - `score`
  - `target_qty`
  - `target_notional`
  - `reason_code`
  - `metadata_json`
- **Used by**: execution, attribution, decision audit

### 3.4 Target Positions
- **Table**: `strategy.target_positions`
- **Purpose**: Store desired target exposure produced by the strategy layer
- **Source**: Portfolio construction / strategy engine
- **Update frequency**: Per rebalance / signal cycle
- **Primary identifier**: `target_position_id`
- **Used by**: execution engine, portfolio audit, rebalance analysis

---

## 4. Execution Data

### 4.1 Accounts
- **Table**: `execution.accounts`
- **Purpose**: Store trading accounts across backtest, paper, and live environments
- **Source**: Internal account registry
- **Update frequency**: Rare / administrative
- **Primary identifier**: `account_id`
- **Key fields**:
  - `account_code`
  - `exchange_id`
  - `account_type`
  - `base_currency_id`

### 4.2 Orders
- **Table**: `execution.orders`
- **Purpose**: Canonical order records shared across backtest, paper, and live trading
- **Source**: Execution engine / exchange adapter
- **Update frequency**: Event-driven
- **Primary identifier**: `order_id`
- **Key fields**:
  - `environment`
  - `client_order_id`
  - `exchange_order_id`
  - `side`
  - `order_type`
  - `time_in_force`
  - `price`
  - `qty`
  - `status`
  - `submit_time`
  - `ack_time`
  - `cancel_time`
- **Used by**: fills, positions, order events, execution analytics

### 4.3 Order Events
- **Table**: `execution.order_events`
- **Purpose**: Detailed lifecycle and status transition log for each order
- **Source**: Execution engine / exchange callbacks / polling reconciler
- **Update frequency**: Event-driven
- **Primary identifier**: `order_event_id`
- **Key fields**:
  - `event_type`
  - `event_time`
  - `status_before`
  - `status_after`
  - `reason_code`
  - `detail_json`
- **Used by**: audit, debugging, live reconciliation

### 4.4 Fills
- **Table**: `execution.fills`
- **Purpose**: Executed trade fills associated with orders
- **Source**: Exchange execution reports / simulator
- **Update frequency**: Event-driven
- **Primary identifier**: `fill_id`
- **Key fields**:
  - `exchange_trade_id`
  - `fill_time`
  - `price`
  - `qty`
  - `notional`
  - `fee`
  - `fee_asset_id`
  - `liquidity_flag`
- **Used by**: PnL, position updates, transaction cost analysis

### 4.5 Positions
- **Table**: `execution.positions`
- **Purpose**: Current position snapshot by account and instrument
- **Source**: Execution state engine / reconciliation jobs
- **Update frequency**: On fills and mark updates
- **Primary key**: `(account_id, instrument_id)`
- **Used by**: risk, live state, position dashboards

### 4.6 Position Snapshots
- **Table**: `execution.position_snapshots`
- **Purpose**: Historical position state series for analytics and audit
- **Source**: Snapshot jobs / mark-to-market pipeline
- **Update frequency**: Configurable, e.g. every minute
- **Primary key**: `(account_id, instrument_id, snapshot_time)`
- **Used by**: exposure history, attribution, historical state reconstruction

### 4.7 Balances
- **Table**: `execution.balances`
- **Purpose**: Historical balance snapshots by account and asset
- **Source**: Exchange account balance APIs / simulator
- **Update frequency**: Snapshot interval or account event-driven
- **Primary key**: `(account_id, asset_id, snapshot_time)`
- **Used by**: equity curve, collateral monitoring, treasury reporting

### 4.8 Account Ledger
- **Table**: `execution.account_ledger`
- **Purpose**: Normalized cashflow ledger for deposits, withdrawals, fees, transfers, realized PnL, funding, rebates
- **Source**: Exchange account history APIs / internal accounting events
- **Update frequency**: Event-driven / reconciliation batches
- **Primary identifier**: `ledger_id`
- **Key fields**:
  - `ledger_type`
  - `amount`
  - `balance_after`
  - `reference_type`
  - `reference_id`
  - `external_reference_id`
- **Used by**: accounting, reconciliation, treasury tracking, post-trade analytics

### 4.9 Funding PnL
- **Table**: `execution.funding_pnl`
- **Purpose**: Store realized funding payments/receipts on perp positions
- **Source**: Exchange funding history + internal reconciliation
- **Update frequency**: Each funding event
- **Primary identifier**: `funding_pnl_id`
- **Used by**: strategy attribution, perp cost analysis, ledger validation

---

## 5. Backtest Data

### 5.1 Backtest Runs
- **Table**: `backtest.runs`
- **Purpose**: Metadata registry for each backtest execution
- **Source**: Backtest engine
- **Update frequency**: Per backtest run
- **Primary identifier**: `run_id`
- **Key fields**:
  - `strategy_version_id`
  - `universe_json`
  - `start_time`
  - `end_time`
  - `market_data_version`
  - `fee_model_version`
  - `slippage_model_version`
  - `latency_model_version`
  - `params_json`
- **Used by**: reproducibility, performance reporting

### 5.2 Simulated Orders
- **Table**: `backtest.simulated_orders`
- **Purpose**: Backtest order generation records
- **Source**: Backtest execution logic
- **Update frequency**: Per simulated order
- **Primary identifier**: `sim_order_id`

### 5.3 Simulated Fills
- **Table**: `backtest.simulated_fills`
- **Purpose**: Backtest fill records with fees and slippage
- **Source**: Backtest execution model
- **Update frequency**: Per simulated fill
- **Primary identifier**: `sim_fill_id`

### 5.4 Performance Summary
- **Table**: `backtest.performance_summary`
- **Purpose**: Aggregate KPIs for a run
- **Source**: Backtest analytics pipeline
- **Update frequency**: Once per completed run
- **Primary key**: `run_id`
- **Typical metrics**:
  - `total_return`
  - `annualized_return`
  - `sharpe`
  - `sortino`
  - `max_drawdown`
  - `turnover`
  - `win_rate`
  - `avg_holding_seconds`
  - `fee_cost`
  - `slippage_cost`

### 5.5 Performance Timeseries
- **Table**: `backtest.performance_timeseries`
- **Purpose**: Equity curve and exposure history for each run
- **Source**: Backtest analytics pipeline
- **Update frequency**: Per bar / evaluation interval
- **Primary key**: `(run_id, ts)`

---

## 6. Risk Data

### 6.1 Risk Limits
- **Table**: `risk.risk_limits`
- **Purpose**: Configured per-account or per-instrument risk controls
- **Source**: Internal risk configuration
- **Update frequency**: On risk policy change
- **Primary identifier**: `risk_limit_id`
- **Key fields**:
  - `max_position_qty`
  - `max_notional`
  - `max_leverage`
  - `max_daily_loss`
  - `is_active`

### 6.2 Risk Events
- **Table**: `risk.risk_events`
- **Purpose**: Logged risk breaches and control events
- **Source**: Risk engine
- **Update frequency**: Event-driven
- **Primary identifier**: `risk_event_id`
- **Used by**: monitoring, post-mortem, audit

### 6.3 Margin Tiers
- **Table**: `risk.margin_tiers`
- **Purpose**: Instrument-specific leverage and margin step functions
- **Source**: Exchange derivatives metadata APIs / manual sync
- **Update frequency**: When exchange changes tier rules
- **Primary identifier**: `margin_tier_id`
- **Used by**: liquidation estimates, leverage validation, pre-trade risk

---

## 7. Operations and Data Quality

### 7.1 System Logs
- **Table**: `ops.system_logs`
- **Purpose**: Generic application logs with structured context
- **Source**: All internal services
- **Update frequency**: Event-driven
- **Primary identifier**: `log_id`
- **Used by**: debugging, incident response, service monitoring

### 7.2 Ingestion Jobs
- **Table**: `ops.ingestion_jobs`
- **Purpose**: Track ingestion tasks, window coverage, status, and row counts
- **Source**: Collector scheduler / batch jobs / backfill workers
- **Update frequency**: Per job run
- **Primary identifier**: `ingestion_job_id`
- **Used by**: observability, retry workflows, SLA tracking

### 7.3 Data Quality Checks
- **Table**: `ops.data_quality_checks`
- **Purpose**: Structured outcomes of quality checks such as gap checks, null checks, freshness checks, duplicate checks
- **Source**: Data quality validation jobs
- **Update frequency**: Scheduled or event-triggered
- **Primary identifier**: `check_id`
- **Used by**: alerts, quality dashboard, remediation pipeline

### 7.4 Data Gaps
- **Table**: `ops.data_gaps`
- **Purpose**: Record missing windows or incomplete expected records in market or execution datasets
- **Source**: Gap detection jobs
- **Update frequency**: Scheduled or event-triggered
- **Primary identifier**: `gap_id`
- **Used by**: backfill queueing, quality reporting

### 7.5 Websocket Connection Events
- **Table**: `ops.ws_connection_events`
- **Purpose**: Connection lifecycle logs for websocket collectors and exchange streams
- **Source**: Real-time collectors / exchange adapters
- **Update frequency**: Event-driven
- **Primary identifier**: `ws_event_id`
- **Used by**: diagnosing disconnects, message loss investigations, latency incidents

---

## 8. Collection Priority

### 8.1 Must Have for V1
1. `ref.exchanges`
2. `ref.assets`
3. `ref.instruments`
4. `ref.fee_schedules`
5. `md.bars_1m`
6. `md.trades`
7. `md.funding_rates`
8. `md.open_interest`
9. `strategy.strategies`
10. `strategy.strategy_versions`
11. `strategy.signals`
12. `execution.accounts`
13. `execution.orders`
14. `execution.fills`
15. `execution.positions`
16. `execution.balances`
17. `backtest.runs`
18. `backtest.simulated_orders`
19. `backtest.simulated_fills`
20. `backtest.performance_summary`
21. `backtest.performance_timeseries`
22. `risk.risk_limits`
23. `risk.risk_events`
24. `ops.system_logs`

### 8.2 Strongly Recommended for Perp / Live Trading
1. `md.mark_prices`
2. `md.index_prices`
3. `md.orderbook_snapshots`
4. `md.orderbook_deltas`
5. `md.raw_market_events`
6. `execution.order_events`
7. `execution.account_ledger`
8. `execution.funding_pnl`
9. `risk.margin_tiers`
10. `ops.ingestion_jobs`
11. `ops.data_quality_checks`
12. `ops.data_gaps`
13. `ops.ws_connection_events`

### 8.3 Nice to Have Later
1. Additional bar granularities such as 1s and 5s
2. Feature store tables
3. Venue latency tables
4. Portfolio allocation history
5. Borrow rates and lending rates
6. Transfer and treasury routing history by wallet/network

---

## 9. Recommended Source Mapping for First Exchange Adapter

### Public Endpoints
- instrument metadata -> `ref.instruments`
- klines/candles -> `md.bars_1m`
- public trades -> `md.trades`
- funding history -> `md.funding_rates`
- open interest -> `md.open_interest`
- order book snapshot -> `md.orderbook_snapshots`
- depth stream -> `md.orderbook_deltas`
- mark price stream -> `md.mark_prices`
- index price stream -> `md.index_prices`
- liquidation stream -> `md.liquidations`
- raw websocket frames -> `md.raw_market_events`

### Private Endpoints
- account balances -> `execution.balances`
- open positions -> `execution.positions`
- order placement / order query -> `execution.orders`
- execution reports -> `execution.fills`, `execution.order_events`
- account funding history -> `execution.funding_pnl`, `execution.account_ledger`
- account transfer history -> `execution.account_ledger`

---

## 10. Open Gaps Still Not Yet Modeled

These are not blockers for current V1, but may be needed soon depending on strategy type:

1. Feature store tables for derived indicators and factors
2. Borrow rate / lending rate tables for margin trading
3. Network-level deposit / withdrawal metadata for treasury ops
4. Strategy deployment history and config change audit
5. Separate raw tables for each market stream if scale grows beyond generic JSON storage
