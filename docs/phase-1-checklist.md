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
- [x] define `exchange_code` naming format
- [x] define `asset_code` naming format
- [x] define `unified_symbol` naming rules
- [x] define how spot instruments use `settlement_asset_id`
- [x] define how perp instruments use `settlement_asset_id`
- [x] define minimum required trading-rule fields for seeded instruments

### Output
- documented naming assumptions inside `004_seed.sql` comments or a companion note

### Acceptance Checks
- [x] all seeded instruments follow one unified naming convention
- [x] spot and perp instruments are distinguishable by `instrument_type`
- [x] no seeded instrument has ambiguous base/quote/settlement mapping

---

## Task 2: Seed Exchanges

### Objective
Insert the first supported exchanges into `ref.exchanges`.

### Tasks
- [x] add Binance seed row
- [x] add Bybit seed row
- [x] include exchange name
- [x] include timezone if used
- [x] make inserts safe for repeated execution

### Output
- exchange seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [x] `ref.exchanges` contains `binance`
- [x] `ref.exchanges` contains `bybit`
- [x] repeated seed runs do not create duplicate exchange rows

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
- [x] add BTC
- [x] add ETH
- [x] add USDT
- [x] add USDC
- [x] set appropriate `asset_type` values
- [x] make inserts safe for repeated execution

### Output
- asset seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [x] `ref.assets` contains BTC, ETH, USDT, USDC
- [x] all seeded assets have a valid `asset_type`
- [x] repeated seed runs do not create duplicate asset rows

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
- [x] add Binance BTCUSDT spot
- [x] add Binance ETHUSDT spot
- [x] add Bybit BTCUSDT spot
- [x] add Bybit ETHUSDT spot
- [x] populate base asset mapping
- [x] populate quote asset mapping
- [x] set `instrument_type = 'spot'`
- [x] set trading status
- [x] set tick size, lot size, min qty, min notional
- [x] make inserts safe for repeated execution

### Output
- spot instrument seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [x] each exchange has at least one BTCUSDT spot instrument
- [x] each exchange has at least one ETHUSDT spot instrument
- [x] all seeded spot instruments reference valid base and quote assets
- [x] no duplicate `(exchange_id, venue_symbol, instrument_type)` rows are created

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
- [x] add Binance BTCUSDT perp
- [x] add Binance ETHUSDT perp
- [x] add Bybit BTCUSDT perp
- [x] add Bybit ETHUSDT perp
- [x] populate base asset mapping
- [x] populate quote asset mapping
- [x] populate settlement asset mapping
- [x] set `instrument_type = 'perp'`
- [x] set trading status
- [x] set tick size, lot size, min qty, min notional, contract size
- [x] make inserts safe for repeated execution

### Output
- perp instrument seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [x] each exchange has at least one BTCUSDT perp instrument
- [x] each exchange has at least one ETHUSDT perp instrument
- [x] all seeded perp instruments have settlement asset populated where applicable
- [x] no duplicate `(exchange_id, venue_symbol, instrument_type)` rows are created

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
- [x] decide whether starter fee schedules are included in Phase 1
- [x] if included, add starter maker/taker fee rows for spot
- [x] if included, add starter maker/taker fee rows for perp
- [x] include `effective_from`
- [x] make inserts safe for repeated execution

### Output
- optional fee schedule seed statements in `db/init/004_seed.sql`

### Acceptance Checks
- [x] if fee schedules are seeded, there is at least one fee row per instrument type per exchange
- [x] seeded fee rows have non-null maker and taker fee values
- [x] repeated seed runs do not create unintended duplicates
- [x] current starter defaults are documented and verifiable:
  - `spot`: maker/taker `7.5 bps`
  - `perp`: maker `1.8 bps`, taker `4.5 bps`

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
- [x] use `on conflict do nothing` or equivalent strategy where appropriate
- [x] avoid hardcoded FK ids that break across environments
- [x] derive foreign keys from natural keys where possible
- [x] verify running the seed twice does not corrupt data

### Output
- rerunnable `db/init/004_seed.sql`

### Acceptance Checks
- [x] running the seed a second time does not fail unexpectedly
- [x] row counts remain stable after repeated execution
- [x] no duplicate exchanges, assets, or instruments are introduced

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
       , instrument_type
from ref.instruments
group by exchange_id, venue_symbol, instrument_type
having count(*) > 1;
```

---

## Task 8: Verify Schema Bootstrap From Empty Database

### Objective
Prove that an empty database can be initialized successfully using the current SQL files.

### Tasks
- [x] reset local database to empty state
- [x] re-run database bootstrap process
- [x] confirm the clean bootstrap sequence applies successfully through the current `db/init/*.sql` set
- [x] confirm seeded rows exist immediately after init

### Output
- repeatable bootstrap process validated locally

### Acceptance Checks
- [x] empty database initializes without manual SQL intervention
- [x] all expected schemas exist
- [x] all expected base reference data exists after bootstrap
- [x] bootstrap flow works on a clean environment, not only an already-initialized DB

### Suggested Verification Query
```sql
select schema_name
from information_schema.schemata
where schema_name in ('ref', 'md', 'strategy', 'execution', 'backtest', 'risk', 'ops', 'research')
order by schema_name;
```

---

## Task 9: Document the Bootstrap Flow

### Objective
Make the setup process easy for future developers to follow.

### Tasks
- [x] document how the database is initialized
- [x] document where migrations live
- [x] document where seed data lives
- [x] document how to reset and rebuild the DB
- [x] document expected seed contents

### Output
- README update or dedicated setup section

### Acceptance Checks
- [x] a new developer can follow the documented steps without guessing
- [x] the documentation clearly distinguishes schema files from seed files
- [x] the documentation states what should exist after bootstrap

---

## Task 10: Run Final Verification Checklist

### Objective
Confirm Phase 1 is complete and safe to hand off to Phase 2.

### Tasks
- [x] confirm exchanges exist
- [x] confirm assets exist
- [x] confirm spot instruments exist
- [x] confirm perp instruments exist
- [x] confirm optional fee schedules are present if included
- [x] confirm rerun safety
- [x] confirm documentation is updated

### Output
- completed Phase 1 verification

### Acceptance Checks
- [x] at least two exchanges exist
- [x] at least four assets exist
- [x] at least one spot and one perp instrument exist per exchange
- [x] all base/quote/settlement references resolve correctly
- [x] Phase 2 can begin without manual DB edits

---

## 5. Final Phase 1 Acceptance Summary

Phase 1 is complete when all of the following are true:

- [x] `db/init/004_seed.sql` exists
- [x] database can be initialized from empty state
- [x] all current schema files apply successfully
- [x] exchanges are seeded
- [x] assets are seeded
- [x] spot instruments are seeded
- [x] perp instruments are seeded
- [x] seed is idempotent
- [x] bootstrap steps are documented
- [x] verification queries pass

---

## 6. Handoff Criteria to Phase 2

Phase 2 may begin only after the following are confirmed:

- [x] `ref.exchanges` is usable as a stable exchange registry
- [x] `ref.assets` is usable as a stable asset registry
- [x] `ref.instruments` contains the first production-like symbols
- [x] future code can resolve instruments without manual DB inserts
- [x] the team agrees on the seeded naming conventions

---

## 7. Recommended Immediate Next Action

Implement the following in order:

1. treat Phase 1 as complete
2. continue Phase 2 model and storage expansion
3. keep verification queries updated when schema/seed assumptions change
