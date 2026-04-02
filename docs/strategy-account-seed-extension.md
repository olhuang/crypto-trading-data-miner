# Strategy and Account Seed Extension

## Purpose

This document defines the minimal seed extension required before strategy-driven phases begin.

Current status:
- implemented via `db/init/006_seed_strategy_and_accounts.sql`
- currently seeds one starter strategy, one starter strategy version, one paper account, and one live-placeholder account

The current bootstrap seed covers:
- exchanges
- assets
- instruments
- fee schedules

That is sufficient for early bootstrap and public market-data work, but not sufficient once the project enters:
- Phase 5 backtesting
- Phase 6 paper trading
- Phase 7 live trading

This spec complements:
- `db/init/004_seed.sql`
- `docs/internal-id-resolution-spec.md`
- `docs/peer-review-followups.md`
- `docs/implementation-plan.md`

---

## 1. Goal

Before strategy-driven implementation begins, the database should contain a minimal but coherent set of rows for:
- strategy registry
- strategy versions
- paper account(s)
- optional live-placeholder account(s)

This allows service-layer identifier resolution and first end-to-end flows to work without hand-inserting setup data each time.

---

## 2. Scope

## 2.1 In Scope
- minimal `strategy.strategies` seed rows
- minimal `strategy.strategy_versions` seed rows
- minimal `execution.accounts` seed rows
- naming and idempotency rules for these seeds

## 2.2 Out of Scope
- multiple production strategies
- real live exchange credentials
- treasury setup
- full deployment records
- portfolio allocation history

---

## 3. Seed Philosophy

These seeds are **bootstrap convenience defaults**, not a substitute for later runtime-managed metadata.

They should:
- make local development and early testing easier
- be idempotent
- use natural-key resolution where practical
- avoid hardcoding fragile FK assumptions

They should not:
- contain secrets
- pretend to be production account configuration
- become the long-term mutable source for live operational data

---

## 4. Minimum Strategy Seed

## 4.1 Strategies

At least one starter strategy row should exist.

Recommended example:
- `strategy_code = btc_momentum`
- `strategy_name = BTC Momentum`
- `description = minimal seed strategy for early backtest/paper flows`

Optional second example later:
- `strategy_code = basis_carry`

## 4.2 Strategy Versions

At least one version row should exist for the starter strategy.

Recommended example:
- `strategy_code = btc_momentum`
- `strategy_version = v1.0.0`
- `is_active = true`
- `params_json = {}`
- `feature_version = seed-v1`
- `execution_version = seed-v1`
- `risk_version = seed-v1`

### Uniqueness Rule

The seed and service logic should treat:
- `strategy_code` as unique at strategy level
- `strategy_code + strategy_version` as the natural unique version key

This matches `docs/internal-id-resolution-spec.md`.

---

## 5. Minimum Account Seed

## 5.1 Paper Account

At least one paper account row should exist before Phase 6.

Recommended example:
- `account_code = paper_main`
- `account_type = paper`
- `exchange_code = binance`
- `base_currency = USDT`
- `is_active = true`

## 5.2 Live Placeholder Account

Optional for early development, but useful before Phase 7:
- `account_code = binance_live_placeholder`
- `account_type = live`
- `exchange_code = binance`
- `base_currency = USDT`
- `is_active = false`

This account must not contain secrets.
It exists only to stabilize code paths and identifier resolution.

---

## 6. Seed Timing Recommendation

## 6.1 Not Required for Earliest Slice

These rows are **not required** for:
- Phase 1 bootstrap validation
- Phase 2 model/repository scaffolding
- the earliest Phase 3 public Binance ingestion work

## 6.2 Required Before Later Phases

These rows should exist before:
- Phase 5 backtest run creation that references strategy/version records
- Phase 6 paper session startup
- Phase 7 live-trading account-scoped actions

---

## 7. Recommended Storage Path

Recommended approach:
- keep current `db/init/004_seed.sql` focused on reference/bootstrap data
- add a later seed extension file or migration-backed seed script for strategy/account starter rows

Good options:
- `db/init/005_seed_strategy_and_accounts.sql`
- or `db/migrations/005_seed_strategy_and_accounts.sql`

The exact file path may follow the migration strategy locked in `docs/implementation-lock.md`.

Current implemented path:
- `db/init/006_seed_strategy_and_accounts.sql`

---

## 8. Idempotency Rules

## 8.1 Strategy Seed

Insert or upsert by:
- `strategy_code`

## 8.2 Strategy Version Seed

Insert or upsert by:
- `strategy_code + strategy_version`

## 8.3 Account Seed

Insert or upsert by:
- `account_code`

## 8.4 Drift Rule

Seed extension should avoid becoming a silent mutable operational update mechanism.

Recommended first-wave rule:
- safe repeated insert/upsert for clearly bootstrap-style fields
- any meaningful operational config drift should be managed through explicit migrations or admin workflows later, not hidden seed reruns

---

## 9. Service-Layer Dependency Impact

Adding these rows enables:
- deterministic `strategy_code -> strategy_id` resolution
- deterministic `strategy_code + strategy_version -> strategy_version_id` resolution
- deterministic `account_code -> account_id` resolution

This supports:
- backtest run create APIs
- paper session create APIs
- later live session/account flows

---

## 10. Example Seed Targets

Recommended minimal starter set:

### Strategies
- `btc_momentum`

### Strategy Versions
- `btc_momentum / v1.0.0`

### Accounts
- `paper_main`
- optionally `binance_live_placeholder`

This is enough to prevent strategy/account identifier resolution from blocking Phase 5+ work.

---

## 11. Acceptance Criteria

This seed extension plan is sufficiently specified when:
- strategy seed natural keys are explicit
- strategy-version seed natural keys are explicit
- account seed natural keys are explicit
- project knows these rows are not required for the earliest public-ingestion slice
- project also knows they must exist before strategy-driven phases begin

---

## 12. Final Summary

The practical rule is:
- keep Phase 1 bootstrap seed focused on reference data
- add a small seed extension for strategies, strategy versions, and accounts before Phase 5/6/7
- use `strategy_code`, `strategy_code + strategy_version`, and `account_code` as natural seed keys
- never place secrets in these seed defaults

This gives later phases stable startup metadata without polluting the core reference bootstrap.
