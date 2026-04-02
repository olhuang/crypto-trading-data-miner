# Observability Spec

## Purpose

This document defines the observability model for the trading platform.

It covers:
- logs
- metrics
- traces
- correlation identifiers
- dashboards
- alerts
- ownership and operational visibility

This spec complements:
- `docs/backend-system-design.md`
- `docs/job-orchestration-spec.md`
- `docs/ui-api-spec.md`

---

## 1. Goals

The observability system must allow operators and developers to answer:
1. is the system healthy right now?
2. what failed?
3. where did it fail?
4. what data or order flow was affected?
5. how long did it take?
6. what should be done next?

---

## 2. Three Pillars

## 2.1 Logs
Use logs for:
- event detail
- exception context
- audit trail for control actions
- debugging exchange/API interactions

## 2.2 Metrics
Use metrics for:
- health trends
- latency tracking
- throughput monitoring
- error rates
- alert thresholds

## 2.3 Traces
Use traces or equivalent correlation propagation for:
- request path timing
- job execution timing
- multi-step flow reconstruction
- API to worker to DB to exchange flow correlation

---

## 3. Correlation Identifiers

Every important flow should carry identifiers that allow cross-system inspection.

Recommended IDs:
- `request_id`
- `job_id`
- `session_id`
- `run_id`
- `order_id`
- `signal_id`
- `exchange_order_id`
- `trace_id` if tracing is introduced

## 3.1 Propagation Rule

If a flow starts in the UI/API and continues asynchronously, the originating identifier should be carried forward where possible.

Examples:
- UI action -> API `request_id` -> job enqueue -> `job_id` -> worker logs
- strategy signal -> order -> fill -> latency metrics -> order detail view

---

## 4. Logging Specification

## 4.1 Logging Principles

Logs should be:
- structured
- machine-parseable
- context-rich
- free of unnecessary secrets or sensitive payload leakage

## 4.2 Required Log Fields

Recommended structured fields:
- timestamp
- level
- service_name
- environment
- module
- event_name
- message
- request_id
- job_id
- session_id
- account_code where relevant
- exchange_code where relevant
- unified_symbol where relevant
- error_code if applicable
- metadata_json

## 4.3 Log Severity Guidance

- `DEBUG`: local development diagnostics only
- `INFO`: normal state changes and workflow milestones
- `WARNING`: degraded but recoverable conditions
- `ERROR`: failed operations requiring attention or retries
- `CRITICAL`: live safety or major integrity incidents

## 4.4 Audit-Relevant Log Events

At minimum, log these explicitly:
- bootstrap verification triggered
- ingestion job started/completed/failed
- backtest run created/completed/failed
- paper session started/stopped/paused/resumed
- live session started/stopped
- emergency stop invoked
- live order submitted/canceled/rejected
- reconciliation mismatch detected
- config or deployment change applied

---

## 5. Metrics Specification

## 5.1 Metric Categories

### System Health
- app health
- DB connectivity/latency
- Redis connectivity/latency
- worker availability

### Ingestion
- jobs started/succeeded/failed
- rows written by data type
- websocket disconnect count
- freshness lag
- gap counts

### Backtest
- run count
- run duration
- failed run count

### Paper and Live Execution
- signal-to-submit latency
- submit-to-ack latency
- ack-to-fill latency
- order rejection count
- fill count
- live session runtime status

### Reconciliation / Operations
- open mismatch count
- mismatch age
- treasury sync failures
- alert count by severity

## 5.2 Metric Naming Guidance

Use domain-oriented metric names, for example:
- `system.health.check.latency_ms`
- `ingestion.jobs.started_total`
- `ingestion.jobs.failed_total`
- `market.ws.disconnect_total`
- `quality.gaps.open_total`
- `execution.orders.rejected_total`
- `execution.latency.submit_to_ack_ms`
- `reconciliation.mismatches.open_total`

---

## 6. Trace / Flow Reconstruction Specification

## 6.1 Tracing Scope

At minimum, flows should be reconstructable through correlated logs and IDs even if full distributed tracing is not yet deployed.

Full tracing should later support:
- API request -> domain service -> DB -> job enqueue
- worker job -> external API -> DB writes
- live runtime -> exchange adapter -> order event -> fill update

## 6.2 High-Value Traceable Flows

- bootstrap verification flow
- bar backfill flow
- instrument sync flow
- backtest run flow
- paper order lifecycle flow
- live order lifecycle flow
- reconciliation mismatch detection flow

---

## 7. Dashboard Requirements

## 7.1 Minimum Dashboards

### System Dashboard
Should show:
- app/DB/Redis health
- worker health
- recent critical errors

### Ingestion Dashboard
Should show:
- recent jobs
- success/failure rates
- latest trade/bar/funding freshness
- websocket connection state

### Execution Dashboard
Should show:
- active paper/live sessions
- recent orders/fills
- rejection counts
- latency summaries

### Reconciliation Dashboard
Should show:
- open mismatches
- mismatch categories
- oldest unresolved mismatch age

### Reliability Dashboard
Should show:
- ingestion failures
- stale data alerts
- reconnect counts
- alert totals by severity

---

## 8. Alerting Specification

## 8.1 Alert Categories

### Critical Alerts
Examples:
- live order submission failure bursts
- emergency stop invoked
- exchange connectivity loss affecting live runtime
- reconciliation mismatch indicating state divergence in live account

### Warning Alerts
Examples:
- stale bars
- stale trade ingestion
- repeated websocket reconnects
- scheduled reconciliation failure
- repeated quality check failures

### Info Alerts
Examples:
- backfill completed
- reconciliation job completed with minor issues

## 8.2 Alert Payload Requirements

Alert payloads should include:
- alert id
- severity
- category
- title
- description
- affected scope
- first seen / last seen
- recommended action if known
- correlation ids where relevant

---

## 9. Mapping to Existing Tables

Current DB structures already support parts of observability:
- `ops.system_logs`
- `ops.ingestion_jobs`
- `ops.data_quality_checks`
- `ops.data_gaps`
- `ops.ws_connection_events`
- `execution.execution_latency_metrics`

These tables should be treated as part of the operational observability surface, not as the only observability mechanism.

---

## 10. Ownership Model

Recommended ownership model:
- each backend domain owns its logs/metrics emission correctness
- platform/ops owns observability conventions and dashboards
- alert routing and triage ownership must be explicit by alert category

Examples:
- ingestion team/domain owns ingestion freshness metrics
- execution domain owns order latency and rejection metrics
- reconciliation domain owns mismatch metrics

---

## 11. Security Rules for Observability

- never log raw secrets
- avoid dumping private exchange credentials or sensitive auth payloads
- redact account-sensitive data when necessary in shared environments
- raw payload inspection must follow role-based access where it includes sensitive account details

---

## 12. SLO / SLA Guidance

Initial practical SLO guidance may include:
- ingestion freshness for active market data feeds
- reconciliation completion lag for live accounts
- live order lifecycle visibility lag
- system health endpoint availability

Exact numeric targets may be introduced after baseline runtime measurements are available.

---

## 13. Minimum Acceptance Criteria

Observability is sufficiently specified when:
- logs, metrics, and trace/correlation strategy are defined
- required log fields are explicit
- dashboard categories are explicit
- alert categories and payload requirements are explicit
- critical runtime flows are traceable by identifiers

---

## 14. Final Summary

The observability strategy should provide:
- structured logs for detail and audit
- metrics for health and trends
- traceable identifiers for flow reconstruction
- dashboards for ingestion, execution, reconciliation, and reliability
- alerts with severity and action context

This is required for safe operation well before full live-trading scale.