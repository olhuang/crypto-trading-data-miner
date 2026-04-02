# Architecture Overview

## Goal

Build a crypto trading data and execution platform that can share a consistent data model across:

- backtesting
- paper trading
- live trading

## Core layers

### 1. Reference data
- exchanges
- assets
- instruments
- fee schedules

### 2. Market data
- OHLCV bars
- trades
- funding rates
- open interest

### 3. Strategy
- strategies
- strategy versions
- signals
- target positions

### 4. Execution
- accounts
- orders
- fills
- positions
- balances

### 5. Backtest
- runs
- simulated orders
- simulated fills
- performance summary
- performance timeseries

### 6. Risk and ops
- risk limits
- risk events
- system logs

## Design principles

1. Keep raw market data and normalized data separate in later versions.
2. Use both event time and ingest time for market data.
3. Use the same execution model for backtest, paper, and live.
4. Version strategy logic, feature logic, fee models, and slippage assumptions.
5. Separate transactional data from high-volume market data if scale grows.

## Suggested future stack

- PostgreSQL: metadata, orders, fills, positions, analytics summary
- ClickHouse or object storage: high-volume trades and order book data
- Redis: real-time cache and latest state
