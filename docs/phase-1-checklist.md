# Phase 1 Checklist

## Purpose

This document expands **Phase 1: Database Bootstrap and Seed Data** into a concrete implementation checklist with acceptance checks.

It is intended to be used as the execution guide before Phase 2 begins.

---

## 1. Phase 1 Goal

Phase 1 makes the database layer truly usable.

At the end of this phase:
- the database can be initialized from an empty state
- all current schema files apply successfully
- base reference data exists
- core instruments are queryable immediately
- later phases can rely on the seeded master data

---

## 2. Scope of Phase 1

This phase covers:
- database bootstrap flow
- schema initialization verification
- initial reference data seed
- initial instrument seed
- optional starter fee schedule seed
- bootstrap documentation

This phase does **not** cover:
- ingestion logic
- Python domain models
- storage repositories
- backtest logic
- paper trading
- live trading

---

## 3. Phase 1 Deliverables

### Required Deliverables
- `db/init/004_seed.sql`
- documented database bootstrap flow
- seeded exchanges, assets, and instruments

### Optional Deliverables
- `Makefile`
- `scripts/reset_db.sh`
- `scripts/verify_seed.sql`

---

## 4. Task Checklist

## Task 1: Confirm Seed Data Standards

### Objective
Define the naming and data conventions used by the seed file.

### Tasks
- [ ] define `exchange_code` naming format
- [ ] define `asset_code` naming format
- [ ] define `unified_symbol` naming rules
- [ ] define how spot instruments use `settlement_asset_id`
- [ ] define how perp instruments use `settlement_asset_id`
- [ ] define minimum required trading-rule fields for seeded instruments

### Output
- documented naming assumptions inside `004_seed.sql` comments or a companion note

### Acceptance Checks
- [ ] all seeded instruments follow one unified naming convention
- [ ] spot and perp instruments are distinguishable by `instrument_type`
- [ ] no seeded instrument has ambiguous base/quote/settlement mapping

---

## Task 2: Seed Exchanges

### Objective
Insert the first supported exchanges into `ref.exchanges`.

### Tasks
- [ ] add Binance seed row
- [ ] add Bybit seed row
- [ ] include exchange name
- [ ] include timezone if used
- [ ] make inserts safe for repeated execution

### Output
- exchange seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [ ] `ref.exchanges` contains `binance`
- [ ] `ref.exchanges` contains `bybit`
- [ ] repeated seed runs do not create duplicate exchange rows

### Suggested Verification Query
```sql
select exchange_code, exchange_name, timezone
from ref.exchanges
order by exchange_code;
```

---

## Task 3: Seed Assets

### Objective
Insert the first canonical assets into `ref.assets`.

### Tasks
- [ ] add BTC
- [ ] add ETH
- [ ] add USDT
- [ ] add USDC
- [ ] set appropriate `asset_type` values
- [ ] make inserts safe for repeated execution

### Output
- asset seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [ ] `ref.assets` contains BTC, ETH, USDT, USDC
- [ ] all seeded assets have a valid `asset_type`
- [ ] repeated seed runs do not create duplicate asset rows

### Suggested Verification Query
```sql
select asset_code, asset_name, asset_type
from ref.assets
order by asset_code;
```

---

## Task 4: Seed Spot Instruments

### Objective
Insert the first spot instruments for each supported exchange.

### Tasks
- [ ] add Binance BTCUSDT spot
- [ ] add Binance ETHUSDT spot
- [ ] add Bybit BTCUSDT spot
- [ ] add Bybit ETHUSDT spot
- [ ] populate base asset mapping
- [ ] populate quote asset mapping
- [ ] set `instrument_type = 'spot'`
- [ ] set trading status
- [ ] set tick size, lot size, min qty, min notional
- [ ] make inserts safe for repeated execution

### Output
- spot instrument seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [ ] each exchange has at least one BTCUSDT spot instrument
- [ ] each exchange has at least one ETHUSDT spot instrument
- [ ] all seeded spot instruments reference valid base and quote assets
- [ ] no duplicate `(exchange_id, venue_symbol)` rows are created

### Suggested Verification Query
```sql
select e.exchange_code, i.venue_symbol, i.unified_symbol, i.instrument_type, i.status
from ref.instruments i
join ref.exchanges e on e.exchange_id = i.exchange_id
where i.instrument_type = 'spot'
order by e.exchange_code, i.venue_symbol;
```

---

## Task 5: Seed Perpetual Instruments

### Objective
Insert the first perp instruments for each supported exchange.

### Tasks
- [ ] add Binance BTCUSDT perp
- [ ] add Binance ETHUSDT perp
- [ ] add Bybit BTCUSDT perp
- [ ] add Bybit ETHUSDT perp
- [ ] populate base asset mapping
- [ ] populate quote asset mapping
- [ ] populate settlement asset mapping
- [ ] set `instrument_type = 'perp'`
- [ ] set trading status
- [ ] set tick size, lot size, min qty, min notional, contract size
- [ ] make inserts safe for repeated execution

### Output
- perp instrument seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [ ] each exchange has at least one BTCUSDT perp instrument
- [ ] each exchange has at least one ETHUSDT perp instrument
- [ ] all seeded perp instruments have settlement asset populated where applicable
- [ ] no duplicate `(exchange_id, venue_symbol)` rows are created

### Suggested Verification Query
```sql
select e.exchange_code, i.venue_symbol, i.unified_symbol, i.instrument_type, i.status
from ref.instruments i
join ref.exchanges e on e.exchange_id = i.exchange_id
where i.instrument_type = 'perp'
order by e.exchange_code, i.venue_symbol;
```

---

## Task 6: Optionally Seed Starter Fee Schedules

### Objective
Provide a starter fee model so backtest and execution code can use realistic defaults.

### Tasks
- [ ] decide whether starter fee schedules are included in Phase 1
- [ ] if included, add starter maker/taker fee rows for spot
- [ ] if included, add starter maker/taker fee rows for perp
- [ ] include `effective_from`
- [ ] make inserts safe for repeated execution

### Output
- optional fee schedule seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [ ] if fee schedules are seeded, there is at least one fee row per instrument type per exchange
- [ ] seeded fee rows have non-null maker and taker fee values
- [ ] repeated seed runs do not create unintended duplicates

### Suggested Verification Query
```sql
select e.exchange_code, f.instrument_type, f.vip_tier, f.maker_fee_bps, f.taker_fee_bps, f.effective_from
from ref.fee_schedules f
join ref.exchanges e on e.exchange_id = f.exchange_id
order by e.exchange_code, f.instrument_type, f.effective_from;
```

---

## Task 7: Make Seed File Idempotent

### Objective
Ensure the seed file can be rerun safely during development.

### Tasks
- [ ] use `on conflict do nothing` or equivalent strategy where appropriate
- [ ] avoid hardcoded FK ids that break across environments
- [ ] derive foreign keys from natural keys where possible
- [ ] verify running the seed twice does not corrupt data

### Output
- rerunnable `db/init/004_seed.sql`

### Acceptance Checks
- [ ] running the seed a second time does not fail unexpectedly
- [ ] row counts remain stable after repeated execution
- [ ] no duplicate exchanges, assets, or instruments are introduced

### Suggested Verification Queries
```sql
select exchange_code, count(*)
from ref.exchanges
group by exchange_code
having count(*) > 1;
```

```sql
select asset_code, count(*)
from ref.assets
group by asset_code
having count(*) > 1;
```

```sql
select exchange_id, venue_symbol, count(*)
from ref.instruments
group by exchange_id, venue_symbol
having count(*) > 1;
```

---

## Task 8: Verify Schema Bootstrap From Empty Database

### Objective
Prove that an empty database can be initialized successfully using the current SQL files.

### Tasks
- [ ] reset local database to empty state
- [ ] re-run database bootstrap process
- [ ] confirm `001`, `002`, `003`, and `004` all apply successfully
- [ ] confirm seeded rows exist immediately after init

### Output
- repeatable bootstrap process validated locally

### Acceptance Checks
- [ ] empty database initializes without manual SQL intervention
- [ ] all expected schemas exist
- [ ] all expected base reference data exists after bootstrap
- [ ] bootstrap flow works on a clean environment, not only an already-initialized DB

### Suggested Verification Query
```sql
select schema_name
from information_schema.schemata
where schema_name in ('ref', 'md', 'strategy', 'execution', 'backtest', 'risk', 'ops')
order by schema_name;
```

---

## Task 9: Document the Bootstrap Flow

### Objective
Make the setup process easy for future developers to follow.

### Tasks
- [ ] document how the database is initialized
- [ ] document where migrations live
- [ ] document where seed data lives
- [ ] document how to reset and rebuild the DB
- [ ] document expected seed contents

### Output
- README update or dedicated setup section

### Acceptance Checks
- [ ] a new developer can follow the documented steps without guessing
- [ ] the documentation clearly distinguishes schema files from seed files
- [ ] the documentation states what should exist after bootstrap

---

## Task 10: Run Final Verification Checklist

### Objective
Confirm Phase 1 is complete and safe to hand off to Phase 2.

### Tasks
- [ ] confirm exchanges exist
- [ ] confirm assets exist
- [ ] confirm spot instruments exist
- [ ] confirm perp instruments exist
- [ ] confirm optional fee schedules are present if included
- [ ] confirm rerun safety
- [ ] confirm documentation is updated

### Output
- completed Phase 1 verification

### Acceptance Checks
- [ ] at least two exchanges exist
- [ ] at least four assets exist
- [ ] at least one spot and one perp instrument exist per exchange
- [ ] all base/quote/settlement references resolve correctly
- [ ] Phase 2 can begin without manual DB edits

---

## 5. Final Phase 1 Acceptance Summary

Phase 1 is complete when all of the following are true:

- [ ] `db/init/004_seed.sql` exists
- [ ] database can be initialized from empty state
- [ ] all current schema files apply successfully
- [ ] exchanges are seeded
- [ ] assets are seeded
- [ ] spot instruments are seeded
- [ ] perp instruments are seeded
- [ ] seed is idempotent
- [ ] bootstrap steps are documented
- [ ] verification queries pass

---

## 6. Handoff Criteria to Phase 2

Phase 2 may begin only after the following are confirmed:

- [ ] `ref.exchanges` is usable as a stable exchange registry
- [ ] `ref.assets` is usable as a stable asset registry
- [ ] `ref.instruments` contains the first production-like symbols
- [ ] future code can resolve instruments without manual DB inserts
- [ ] the team agrees on the seeded naming conventions

---

## 7. Recommended Immediate Next Action

Implement the following in order:

1. define naming assumptions
2. create `db/init/004_seed.sql`
3. verify bootstrap from empty DB
4. document bootstrap flow
5. run final verification checklist
