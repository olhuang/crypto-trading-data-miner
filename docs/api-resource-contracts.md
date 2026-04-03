# API Resource Contracts

## Purpose

This document defines canonical resource and response models for early API endpoints whose routes already exist but whose response resources need clearer implementation-level definitions.

This spec is focused on the first implementation wave and Phase 2/3 cleanup.

It complements:
- `docs/ui-api-spec.md`
- `docs/api-contracts.md`
- `docs/contract-naming-conventions.md`
- `docs/peer-review-followups.md`

---

## 1. General Rules

All resources in this document assume:
- snake_case fields
- UTC ISO-8601 timestamps
- standard response envelope from `docs/ui-api-spec.md`
- `status` as the normalized lifecycle/status field where relevant

---

## 2. Bootstrap Verification Result Resource

Used by:
- `GET /api/v1/bootstrap/verification-runs/{verification_run_id}`

## 2.1 Resource Shape

```json
{
  "verification_run_id": "verify_001",
  "status": "succeeded",
  "schemas_ok": true,
  "exchanges_ok": true,
  "assets_ok": true,
  "instruments_ok": true,
  "fee_schedules_ok": true,
  "duplicate_checks_ok": true,
  "started_at": "2026-04-02T12:00:00Z",
  "finished_at": "2026-04-02T12:00:03Z",
  "failures": [],
  "summary": {
    "checks_total": 6,
    "checks_passed": 6,
    "checks_failed": 0
  }
}
```

## 2.2 Failure Item Shape

```json
{
  "check_name": "assets",
  "status": "failed",
  "message": "expected asset USDC not found",
  "detail_json": {}
}
```

---

## 2. Current Implemented Resource Set

The following resources are already implemented in the current Phase 2 API slice and should be treated as canonical for the existing endpoints:
- `GET /api/v1/system/health`
- `GET /api/v1/models/payload-types`
- `POST /api/v1/models/validate`
- `POST /api/v1/models/validate-and-store`
- `POST /api/v1/ingestion/jobs/instrument-sync`
- `POST /api/v1/ingestion/jobs/bar-backfill`
- `POST /api/v1/ingestion/jobs/market-snapshot-refresh`
- `POST /api/v1/ingestion/jobs/market-snapshot-remediation`
- `GET /api/v1/ingestion/jobs`
- `GET /api/v1/ingestion/jobs/{job_id}`
- `GET /api/v1/market/*`
- `GET /api/v1/streams/*`
- `GET /api/v1/quality/*`
- `POST /api/v1/quality/run`
- `GET /api/v1/market/raw-events/{raw_event_id}`
- `GET /api/v1/market/raw-events/{raw_event_id}/normalized-links`
- `GET /api/v1/replay/readiness`

### 2.1 Meta Resource

Current success responses use:

```json
{
  "request_id": "req_001",
  "timestamp": "2026-04-02T12:00:00Z",
  "current_actor": {
    "user_id": "local-dev",
    "user_name": "Local Developer",
    "role": "admin",
    "auth_mode": "local_bypass"
  }
}
```

Rules:
- `current_actor` may be omitted or `null` for public endpoints
- protected endpoints should include `current_actor`
- `request_id` and `timestamp` should always be present

### 2.2 System Health Resource

Used by:
- `GET /api/v1/system/health`

```json
{
  "success": true,
  "data": {
    "app": {
      "status": "ok",
      "checked_at": "2026-04-02T12:00:00Z"
    }
  },
  "error": null,
  "meta": {
    "request_id": "req_001",
    "timestamp": "2026-04-02T12:00:00Z",
    "current_actor": null
  }
}
```

### 2.3 Payload Types Resource

Used by:
- `GET /api/v1/models/payload-types`

```json
{
  "success": true,
  "data": {
    "payload_types": [
      "balance_snapshot",
      "bar_event",
      "fill",
      "funding_rate",
      "instrument_metadata",
      "open_interest",
      "order_request",
      "order_state",
      "position_snapshot",
      "trade_event"
    ]
  },
  "error": null,
  "meta": {
    "request_id": "req_001",
    "timestamp": "2026-04-02T12:00:00Z",
    "current_actor": {
      "user_id": "u_123",
      "user_name": "Alice",
      "role": "developer",
      "auth_mode": "bearer"
    }
  }
}
```

### 2.4 Validation Result Resource

Used by:
- `POST /api/v1/models/validate`

```json
{
  "success": true,
  "data": {
    "valid": true,
    "model_name": "TradeEvent",
    "normalized_payload": {
      "exchange_code": "binance",
      "unified_symbol": "BTCUSDT_PERP",
      "exchange_trade_id": "123",
      "event_time": "2026-04-02T12:34:56Z",
      "ingest_time": "2026-04-02T12:34:57Z",
      "price": "84250.12",
      "qty": "0.01",
      "payload_json": {}
    },
    "validation_errors": []
  },
  "error": null,
  "meta": {
    "request_id": "req_001",
    "timestamp": "2026-04-02T12:00:00Z",
    "current_actor": {
      "user_id": "local-dev",
      "user_name": "Local Developer",
      "role": "admin",
      "auth_mode": "local_bypass"
    }
  }
}
```

### 2.5 Validate-And-Store Result Resource

Used by:
- `POST /api/v1/models/validate-and-store`

```json
{
  "success": true,
  "data": {
    "valid": true,
    "stored": true,
    "entity_type": "trade_event",
    "model_name": "TradeEvent",
    "record_locator": "binance:BTCUSDT_PERP:123",
    "normalized_payload": {
      "exchange_code": "binance",
      "unified_symbol": "BTCUSDT_PERP",
      "exchange_trade_id": "123",
      "event_time": "2026-04-02T12:34:56Z",
      "ingest_time": "2026-04-02T12:34:57Z",
      "price": "84250.12",
      "qty": "0.01",
      "payload_json": {}
    },
    "duplicate_handled": true
  },
  "error": null,
  "meta": {
    "request_id": "req_001",
    "timestamp": "2026-04-02T12:00:00Z",
    "current_actor": {
      "user_id": "u_123",
      "user_name": "Alice",
      "role": "developer",
      "auth_mode": "bearer"
    }
  }
}
```

---

## 3. Strategy Version Resource

Used by:
- `GET /api/v1/strategy-versions`
- `GET /api/v1/strategy-versions/{strategy_version_id}`

## 3.1 Resource Shape

```json
{
  "strategy_version_id": 101,
  "strategy_id": 10,
  "strategy_family": "momentum",
  "strategy_code": "btc_momentum",
  "strategy_name": "BTC Momentum",
  "strategy_version": "v1.0.0",
  "is_active": true,
  "created_at": "2026-04-02T12:00:00Z",
  "config_snapshot_json": {},
  "description": "first production candidate"
}
```

## 3.2 List Response Expectation

List endpoints should return an array of strategy version resources plus pagination metadata where applicable.

---

## 4. Backtest Run Timeseries Resource

Used by:
- `GET /api/v1/backtests/runs/{run_id}/timeseries`

## 4.1 Response Shape

```json
{
  "run_id": 5001,
  "series": [
    {
      "ts": "2026-01-01T00:00:00Z",
      "equity": "100000.00",
      "cash": "100000.00",
      "gross_exposure": "0.00",
      "net_exposure": "0.00",
      "drawdown": "0.00"
    }
  ]
}
```

## 4.2 Notes

- `series` is ordered by ascending timestamp
- numeric values may be returned as strings for exact decimal handling
- this resource is time-series output, not a raw DB table dump

---

## 4.3 Backtest Diagnostics Summary Resource

Used by:
- `GET /api/v1/backtests/runs/{run_id}/diagnostics`

### Response Shape

```json
{
  "run_id": 5001,
  "diagnostic_status": "warning",
  "has_errors": false,
  "has_warnings": true,
  "error_count": 0,
  "warning_count": 1,
  "run_integrity": {
    "run_status": "finished",
    "start_time": "2026-01-01T00:00:00Z",
    "end_time": "2026-02-01T00:00:00Z",
    "timepoints_observed": 43200,
    "expected_timepoints": 44640,
    "missing_timepoints": 1440
  },
  "strategy_activity": {
    "signal_count": 38,
    "entry_signals": 10,
    "exit_signals": 10,
    "reduce_signals": 6,
    "reverse_signals": 2,
    "rebalance_signals": 10
  },
  "execution_summary": {
    "simulated_order_count": 38,
    "simulated_fill_count": 36,
    "expired_order_count": 2,
    "unlinked_order_count": 0,
    "fill_rate_pct": "0.9474"
  },
  "pnl_summary": {
    "total_return": "0.0842",
    "max_drawdown": "0.0310",
    "turnover": "1.8420",
    "fee_cost": "124.55",
    "slippage_cost": "54.20"
  },
  "diagnostic_flags": [
    {
      "code": "expired_orders_present",
      "severity": "warning",
      "message": "one or more simulated orders expired without filling",
      "related_count": 2
    }
  ]
}
```

### Notes

- this is the Stage A diagnostics surface from `docs/backtest-and-replay-diagnostics-spec.md`
- the response is a summary/projection, not a full step trace
- later debug-trace endpoints should drill down from the flags and aggregates returned here

---

## 4.4 Backtest Period Breakdown Resource

Used by:
- `GET /api/v1/backtests/runs/{run_id}/period-breakdown`

### Response Shape

```json
{
  "run_id": 5001,
  "period_type": "month",
  "entries": [
    {
      "period_type": "month",
      "period_start": "2026-01-01T00:00:00Z",
      "period_end": "2026-01-31T23:59:00Z",
      "start_equity": "100000.00",
      "end_equity": "101250.00",
      "total_return": "0.0125",
      "max_drawdown": "0.0210",
      "turnover": "184200.00",
      "fee_cost": "124.55",
      "slippage_cost": "54.20",
      "signal_count": 38,
      "fill_count": 36
    }
  ]
}
```

### Notes

- `period_type` currently supports `year`, `quarter`, and `month`
- this resource is a derived projection, not a separate persisted raw fact table
- it should remain compatible with future compare/analyze and promotion-review workflows

---

## 4.5 Backtest Artifact Bundle Resource

Used by:
- `GET /api/v1/backtests/runs/{run_id}/artifacts`

### Response Shape

```json
{
  "run_id": 5001,
  "artifacts": [
    {
      "artifact_type": "run_metadata",
      "status": "available",
      "record_count": 1,
      "description": "canonical persisted run metadata and lineage baseline"
    },
    {
      "artifact_type": "period_breakdown",
      "status": "available",
      "record_count": 3,
      "description": "derived year/quarter/month performance breakdown projections"
    }
  ]
}
```

### Notes

- this is the first artifact-bundle baseline, not the final exported artifact system
- the artifact list is intended to give UI/research workflows a stable inventory of what a run already exposes

---

## 5. Mismatch Review Result Resource

Used by:
- `POST /api/v1/reconciliation/mismatches/{mismatch_id}/review`

## 5.1 Response Shape

```json
{
  "mismatch_id": 9001,
  "status": "reviewed",
  "reviewed_by": "u_123",
  "reviewed_at": "2026-04-02T12:00:00Z",
  "review_note": "confirmed exchange-side lag",
  "resolution_status": "unresolved"
}
```

## 5.2 Semantic Rule

For early implementation:
- `reviewed` does not automatically mean repaired or resolved
- review and resolution are distinct concepts unless a later spec merges them explicitly

---

## 6. Instrument Sync Job Detail Resource

Used by:
- implemented `GET /api/v1/ingestion/jobs/{job_id}`

## 6.1 Resource Shape

```json
{
  "job_id": 123,
  "service_name": "instrument_sync",
  "data_type": "instrument_metadata",
  "status": "succeeded",
  "exchange_code": "binance",
  "unified_symbol": null,
  "started_at": "2026-04-02T12:00:00Z",
  "finished_at": "2026-04-02T12:00:03Z",
  "records_expected": null,
  "records_written": 6,
  "error_message": null,
  "metadata_json": {
    "job_type": "instrument_sync",
    "requested_by": "u_123"
  },
  "summary": {
    "instruments_seen": 450,
    "instruments_inserted": 2,
    "instruments_updated": 4,
    "instruments_unchanged": 444
  },
  "diffs": [
    {
      "unified_symbol": "BTCUSDT_PERP",
      "change_type": "updated",
      "field_diffs": [
        {
          "field_name": "tick_size",
          "old_value": "0.10",
          "new_value": "0.01"
        }
      ]
    }
  ]
}
```

Notes:
- `strategy_code` is the stable variant identity
- `strategy_version` is the immutable release identity within that variant
- `strategy_family` is optional metadata for future grouping and comparison

## 6.2 Generic Job Action Resource

Used by:
- implemented `POST /api/v1/ingestion/jobs/instrument-sync`
- implemented `POST /api/v1/ingestion/jobs/bar-backfill`
- implemented `POST /api/v1/ingestion/jobs/market-snapshot-refresh`
- implemented `POST /api/v1/ingestion/jobs/market-snapshot-remediation`

```json
{
  "job_id": 123,
  "status": "succeeded"
}
```

Current implementation note:
- `POST /api/v1/ingestion/jobs/market-snapshot-refresh` now supports bounded history windows for funding, open interest, mark prices, and index prices via the existing job path
- `POST /api/v1/ingestion/jobs/market-snapshot-remediation` is the scheduler-ready parent job shape for manual/API-triggered funding/OI/mark/index catch-up planning

## 6.3 Ingestion Job List Resource

Used by:
- implemented `GET /api/v1/ingestion/jobs`

```json
{
  "records": [
    {
      "job_id": 123,
      "service_name": "market_snapshot_refresh",
      "data_type": "funding_rates",
      "status": "succeeded",
      "exchange_code": "binance",
      "unified_symbol": "BTCUSDT_PERP",
      "started_at": "2026-04-03T12:00:00Z",
      "finished_at": "2026-04-03T12:00:04Z",
      "records_expected": null,
      "records_written": 24,
      "error_message": null,
      "metadata_json": {
        "requested_by": "local-dev"
      }
    }
  ]
}
```

Current implementation note:
- this list endpoint is intended for recent operational inspection and Monitoring Console usage
- current filtering supports `status`, `service_name`, `data_type`, `exchange_code`, `unified_symbol`, and `limit`

---

## 7. Phase 4 Quality Summary Resource

Used by:
- implemented `GET /api/v1/quality/summary`

```json
{
  "total_checks": 12,
  "passed_checks": 8,
  "failed_checks": 4,
  "severe_checks": 2,
  "latest_only": true
}
```

Current implementation note:
- `GET /api/v1/quality/summary` accepts `latest_only=true`
- `GET /api/v1/quality/checks` also accepts `latest_only=true`
- when enabled, the API returns only the latest check per `(symbol, data_type, check_name)` so monitoring views can focus on current state instead of full historical logs

## 7.1 Raw Event Detail Resource

Used by:
- implemented `GET /api/v1/market/raw-events/{raw_event_id}`

```json
{
  "raw_event_id": 501,
  "exchange_code": "binance",
  "unified_symbol": "BTCUSDT_PERP",
  "channel": "btcusdt@trade",
  "event_type": "trade",
  "event_time": "2026-04-02T12:34:56Z",
  "ingest_time": "2026-04-02T12:34:56.100Z",
  "source_message_id": "123456789",
  "payload_json": {}
}
```

## 7.2 Normalized Links Resource

Used by:
- implemented `GET /api/v1/market/raw-events/{raw_event_id}/normalized-links`

```json
{
  "raw_event_id": 501,
  "links": [
    {
      "resource_type": "trade",
      "record_locator": "trade_id:7001",
      "match_strategy": "exchange_trade_id"
    }
  ]
}
```

## 7.3 Replay Readiness Resource

Used by:
- implemented `GET /api/v1/replay/readiness`

```json
{
  "raw_coverage_status": "ready",
  "normalized_coverage_status": "ready",
  "retained_streams": [
    "btcusdt@forceOrder",
    "btcusdt@markPrice",
    "btcusdt@trade"
  ],
  "known_gaps": 0,
  "retention_policy": {
    "raw_market_events": "retain recent hot data in PostgreSQL, archive colder partitions later",
    "orderbook_deltas": "retain only as long as replay and modeling needs justify",
    "orderbook_snapshots": "retain managed recent coverage in PostgreSQL and archive older snapshots later"
  },
  "replay_ready_datasets": {
    "trade_stream": true,
    "mark_price_stream": true,
    "liquidation_stream": true
  }
}
```

---

## 8. Paper Risk Limits Resource (Optional Early Addition)

If Phase 6 UI exposes configured risk limits explicitly, use:

```json
{
  "account_code": "paper_main",
  "environment": "local",
  "limits": [
    {
      "instrument_type": "perp",
      "max_position_qty": "1.0",
      "max_notional_usd": "10000",
      "max_leverage": "3"
    }
  ]
}
```

This resource is optional for Phase 2/3 but should be canonical once introduced.

---

## 9. Signal Resource Clarification

For:
- `GET /api/v1/backtests/runs/{run_id}/signals`

Rule:
- signal resources may be returned even if signals are not yet permanently stored as first-class DB entities in all environments
- this endpoint may be served from persisted records or deterministic run outputs depending on phase implementation

This endpoint is valid as an API contract even if storage strategy evolves.

---

## 10. Minimum Acceptance Criteria

This resource-contract set is sufficiently useful when:
- early implemented endpoints have concrete response shapes
- frontend does not need to invent ad hoc resource models
- backend services can map domain outputs into stable response objects

---

## 11. Final Summary

This document provides the missing concrete resource shapes for the earliest route-level API gaps, especially:
- bootstrap verification result
- strategy version
- backtest timeseries
- mismatch review result
- instrument sync job detail

This should reduce backend/frontend drift before implementation begins.
