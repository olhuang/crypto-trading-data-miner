# Crypto Trading Data Miner

A starter repository for a crypto quantitative trading platform covering:

- market data collection
- PostgreSQL schema design
- backtest / paper trading / live trading workflow
- strategy, execution, and risk data models

## Planned structure

- `db/` database schema and migrations
- `src/` application source code
- `docs/` architecture and design notes
- `docker-compose.yml` local services

## Scope of the first scaffold

This initial scaffold is designed to support:

1. market reference data
2. market data ingestion
3. strategy signals
4. order / fill / position storage
5. backtest run tracking
6. system operations logging

## Next steps

- finalize PostgreSQL schema
- add ingestion jobs
- add backtest runner skeleton
- add paper/live execution adapters
