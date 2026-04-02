# Internal ID Resolution Spec

## Purpose

This document defines how human-readable API identifiers are resolved into internal database IDs.

It exists to remove ambiguity between:
- API-facing code/value identifiers
- internal bigint primary keys in PostgreSQL

This spec is especially important for:
- strategy resolution
- strategy version resolution
- account resolution
- exchange/instrument resolution

It complements:
- `docs/api-contracts.md`
- `docs/ui-api-spec.md`
- `docs/implementation-lock.md`
- `docs/peer-review-followups.md`

---

## 1. Core Principle

External and UI-facing requests should prefer stable human-readable identifiers where useful.
Internal storage and joins may still use bigint primary keys.

The service layer is responsible for resolving external-facing identifiers into internal IDs.

This resolution must be deterministic and documented.

---

## 2. Identifier Classes

## 2.1 Human-Readable Identifiers

Examples:
- `strategy_code`
- `strategy_version`
- `account_code`
- `exchange_code`
- `unified_symbol`

## 2.2 Internal Identifiers

Examples:
- `strategy_id`
- `strategy_version_id`
- `account_id`
- `exchange_id`
- `instrument_id`

---

## 3. Resolution Rule by Domain

## 3.1 Exchange

Resolve by:
- `exchange_code` -> `exchange_id`

Rule:
- `exchange_code` must be unique
- failure to resolve is a request/service error

## 3.2 Instrument

Resolve by one of:
- direct `instrument_id`, or
- `exchange_code + unified_symbol`, or
- `exchange_code + venue_symbol` when explicitly allowed by the API contract

Default preference:
- prefer `unified_symbol` in user-facing API contracts

## 3.3 Strategy

Resolve by:
- `strategy_code` -> `strategy_id`

Rule:
- `strategy_code` must be unique

## 3.4 Strategy Version

Resolve by:
- `strategy_code + strategy_version` -> `strategy_version_id`

Rule:
- `strategy_version` alone is not globally unique unless explicitly enforced later
- service code must not assume `strategy_version = 'v1.0.0'` is unique without `strategy_code`

## 3.5 Account

Resolve by:
- `account_code` -> `account_id`

Rule:
- `account_code` must be unique within its intended environment scope
- if environment-specific scoping is needed later, service logic must include environment in lookup rules explicitly

---

## 4. API Design Guidance

## 4.1 Preferred Request Fields

User-facing/API requests should prefer:
- `exchange_code`
- `unified_symbol`
- `strategy_code`
- `strategy_version`
- `account_code`

Do not require callers to know bigint IDs unless the endpoint is explicitly an internal detail endpoint.

## 4.2 Service Responsibility

The API layer should pass validated human-readable identifiers into the service layer.
The service layer resolves them into internal IDs before repository writes or relational queries.

---

## 5. Failure Behavior

If resolution fails:
- return `NOT_FOUND` when the requested identifier does not exist
- return `CONFLICT` or equivalent internal error only when uniqueness assumptions are violated unexpectedly

Example resolution failure cases:
- strategy code not found
- account code not found
- strategy version not found for given strategy code
- unified symbol not found for given exchange scope

---

## 6. Repository Boundary Rule

Repositories should prefer working with internal IDs once resolution has occurred.

That means:
- services resolve codes to IDs
- repositories persist/query with internal IDs and natural keys as appropriate

This keeps repository behavior simpler and avoids duplicated lookup logic.

---

## 7. Example Resolution Flow

## 7.1 Backtest Create Request

Input:
```json
{
  "strategy_code": "btc_momentum",
  "strategy_version": "v1.0.0",
  "exchange_code": "binance",
  "universe": ["BTCUSDT_PERP"]
}
```

Resolution steps:
1. resolve `strategy_code` -> `strategy_id`
2. resolve `strategy_code + strategy_version` -> `strategy_version_id`
3. resolve `exchange_code` -> `exchange_id`
4. resolve each `unified_symbol` -> `instrument_id`
5. persist run and related records using internal IDs

## 7.2 Paper Session Start

Input:
```json
{
  "account_code": "paper_main",
  "strategy_code": "btc_momentum",
  "strategy_version": "v1.0.0",
  "exchange_code": "binance",
  "universe": ["BTCUSDT_PERP"]
}
```

Resolution steps:
1. resolve `account_code` -> `account_id`
2. resolve strategy and version as above
3. resolve exchange/instrument scope
4. create session with internal IDs and preserve codes for audit readability where useful

---

## 8. Seed Data Implications

To support this contract, seed data or initial setup must eventually ensure that:
- at least one `strategy_code` exists before strategy-driven phases
- at least one `strategy_version` exists before backtest/paper/live phases
- at least one `account_code` exists before paper/live phases

This does not block the earliest public-ingestion-only slice, but it must be in place before later phases.

---

## 9. Minimum Acceptance Criteria

This resolution convention is sufficiently specified when:
- service code knows exactly how to resolve string identifiers
- `strategy_version` uniqueness assumptions are explicit
- repositories do not need to guess mapping rules
- API callers do not need to know bigint IDs for normal workflows

---

## 10. Final Summary

The key locked rules are:
- `exchange_code` resolves `exchange_id`
- `strategy_code` resolves `strategy_id`
- `strategy_code + strategy_version` resolves `strategy_version_id`
- `account_code` resolves `account_id`
- `exchange_code + unified_symbol` resolves `instrument_id`

This should be treated as the default service-layer resolution contract for early implementation.