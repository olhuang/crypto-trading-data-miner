# Database Bootstrap Guide

## Purpose

This document explains how to initialize the local database for this project and verify that Phase 1 has been completed successfully.

---

## 1. What Bootstrap Includes

When PostgreSQL initializes from an empty state, it should apply the SQL files in `db/init/` in filename order.

Current bootstrap sequence:

1. `001_schema.sql`
2. `002_extend_market_and_audit.sql`
3. `003_extend_audit_treasury_latency.sql`
4. `004_seed.sql`

This should result in:
- all project schemas created
- all core tables created
- exchanges seeded
- assets seeded
- starter instruments seeded
- starter fee schedules seeded

---

## 2. Local Bootstrap Flow

### Step 1: Start local services
Use Docker Compose to start PostgreSQL and Redis.

Example:
```bash
cp .env.example .env
docker compose up -d
```

### Step 2: Let PostgreSQL initialize
Because `docker-compose.yml` mounts `./db/init` into `/docker-entrypoint-initdb.d`, PostgreSQL should automatically execute all SQL files in that folder on first initialization.

### Step 3: Verify bootstrap
Connect to PostgreSQL and run the verification queries in this document or in `docs/phase-1-checklist.md`.

---

## 3. Important Notes

### Initialization timing
The SQL files in `/docker-entrypoint-initdb.d` are only executed when PostgreSQL initializes a fresh data directory.

If the container already has existing database files, changing SQL in `db/init/` will not automatically re-run those files.

### Rebuilding from empty state
To test bootstrap from scratch, remove the existing PostgreSQL volume and start again.

Example:
```bash
docker compose down -v
docker compose up -d
```

This will:
- remove the old PostgreSQL data directory
- trigger fresh initialization
- re-run all files in `db/init/`

---

## 4. Phase 1 Verification Queries

### 4.1 Verify schemas
```sql
select schema_name
from information_schema.schemata
where schema_name in ('ref', 'md', 'strategy', 'execution', 'backtest', 'risk', 'ops')
order by schema_name;
```

Expected result:
- `backtest`
- `execution`
- `md`
- `ops`
- `ref`
- `risk`
- `strategy`

### 4.2 Verify exchanges
```sql
select exchange_code, exchange_name, timezone
from ref.exchanges
order by exchange_code;
```

Expected result includes:
- `binance`
- `bybit`

### 4.3 Verify assets
```sql
select asset_code, asset_name, asset_type
from ref.assets
order by asset_code;
```

Expected result includes:
- `BTC`
- `ETH`
- `USDT`
- `USDC`

### 4.4 Verify instruments
```sql
select e.exchange_code, i.venue_symbol, i.unified_symbol, i.instrument_type, i.status
from ref.instruments i
join ref.exchanges e on e.exchange_id = i.exchange_id
order by e.exchange_code, i.instrument_type, i.venue_symbol;
```

Expected result includes for each exchange:
- `BTCUSDT_SPOT`
- `ETHUSDT_SPOT`
- `BTCUSDT_PERP`
- `ETHUSDT_PERP`

### 4.5 Verify instrument counts by exchange and type
```sql
select e.exchange_code, i.instrument_type, count(*) as instrument_count
from ref.instruments i
join ref.exchanges e on e.exchange_id = i.exchange_id
group by e.exchange_code, i.instrument_type
order by e.exchange_code, i.instrument_type;
```

Expected result:
- each exchange has at least one `spot`
- each exchange has at least one `perp`

### 4.6 Verify fee schedules
```sql
select e.exchange_code, f.instrument_type, f.vip_tier, f.maker_fee_bps, f.taker_fee_bps, f.effective_from
from ref.fee_schedules f
join ref.exchanges e on e.exchange_id = f.exchange_id
order by e.exchange_code, f.instrument_type, f.effective_from;
```

Expected result:
- each exchange has a starter `spot` fee row
- each exchange has a starter `perp` fee row

### 4.7 Verify no duplicate exchanges
```sql
select exchange_code, count(*)
from ref.exchanges
group by exchange_code
having count(*) > 1;
```

Expected result:
- no rows

### 4.8 Verify no duplicate assets
```sql
select asset_code, count(*)
from ref.assets
group by asset_code
having count(*) > 1;
```

Expected result:
- no rows

### 4.9 Verify no duplicate instruments
```sql
select exchange_id, venue_symbol, count(*)
       , instrument_type
from ref.instruments
group by exchange_id, venue_symbol, instrument_type
having count(*) > 1;
```

Expected result:
- no rows

---

## 5. Phase 1 Exit Criteria

Phase 1 is considered complete when:
- the DB can be initialized from an empty state
- all SQL files apply successfully
- reference data exists immediately after bootstrap
- the seeded instruments are queryable without manual inserts
- repeated seed execution does not create duplicate exchange, asset, or instrument rows

---

## 6. Next Step After Bootstrap

Once the queries above pass, the project can move to Phase 2:
- domain models
- storage layer
- validated DB persistence for canonical payloads
