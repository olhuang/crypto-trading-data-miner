# Contract Naming Conventions

## Purpose

This document freezes the naming conventions used across:
- database-facing contracts
- backend API resources
- internal canonical payloads
- frontend/backend JSON responses

It exists to remove avoidable naming drift before Phase 2 and Phase 3 implementation begins.

This spec complements:
- `docs/api-contracts.md`
- `docs/ui-api-spec.md`
- `docs/peer-review-followups.md`
- `docs/implementation-lock.md`

---

## 1. Core Rule

Use one naming convention per layer:

### JSON / API / internal payloads
- use **snake_case**
- use explicit suffixes only when they add real meaning

### SQL schema
- continue existing **snake_case** naming
- preserve current schema naming where already established in `db/init/*.sql`

There should not be avoidable semantic renaming between API contracts and DB contracts unless the field meanings actually differ.

---

## 2. JSON Field Suffix Rules

## 2.1 `*_json`

Use `*_json` only when the field stores or returns an arbitrary JSON object/blob and the suffix is helpful to distinguish it from a scalar field.

Examples:
- `detail_json`
- `config_snapshot_json`
- `payload_json`
- `metadata_json`

## 2.2 `detail` vs `detail_json`

Rule:
- if the field is arbitrary structured object data, use `detail_json`
- do not use plain `detail` for JSON blob fields in canonical contracts

## 2.3 `payload` vs `payload_json`

Rule:
- if the field carries a raw or semi-raw JSON payload blob, use `payload_json`
- do not use `raw_payload` in new canonical contracts when the schema convention is `payload_json`

---

## 3. Raw Event Naming Rules

For raw event records, use:
- `payload_json`
- `event_type`
- `event_time`
- `ingest_time`
- `channel`

Do not create parallel field names such as:
- `raw_payload`
- `message_payload`
- `raw_detail`

unless they represent a genuinely different concept.

---

## 4. ID Naming Rules

Use these rules consistently:
- primary resource id: `<resource>_id`
- foreign keys: `<related_resource>_id`
- external exchange-native identifiers: `external_reference_id`, `exchange_order_id`, `exchange_trade_id`
- client-generated outbound identifier: `client_order_id`

Examples:
- `instrument_id`
- `account_id`
- `strategy_version_id`
- `exchange_order_id`

---

## 5. Time Naming Rules

Use these field names consistently:
- `created_at`
- `updated_at`
- `event_time`
- `ingest_time`
- `started_at`
- `finished_at`
- `requested_at`
- `completed_at`

Do not mix semantically similar alternatives unless there is a clear distinction.

Examples to avoid without reason:
- `ts`
- `time`
- `timestamp`
- `received_at`
- `processed_at`

for user-facing or canonical API contracts.

---

## 6. Status Naming Rules

Use normalized status field names:
- `status` for general entity state
- `connection_status` for stream/runtime connection state
- `deployment_status` for deployment-specific state

Avoid multiplying equivalent fields such as:
- `state`
- `job_state`
- `workflow_status`

unless they represent different domains and are clearly justified.

---

## 7. Numeric / Price / Quantity Naming Rules

Use:
- `price`
- `qty`
- `amount`
- `notional`
- `fee_amount`
- `maker_fee_bps`
- `taker_fee_bps`

Use `qty` for instrument quantity and `amount` for broader monetary or event amount semantics.

---

## 8. Nullable / Optional Naming Guidance

Do not use naming alone to imply optionality.
Optionality must be specified by contract rules, not by weak naming patterns like:
- `maybe_*`
- `optional_*`
- `nullable_*`

---

## 9. Canonical Naming Decisions Locked Now

The following are explicitly locked:
- `payload_json` is canonical for raw JSON payload blobs
- `detail_json` is canonical for structured detail blobs
- `config_snapshot_json` remains canonical
- `old_config_json` / `new_config_json` remain canonical

These replace ambiguous alternatives in future contract writing.

---

## 10. Required Follow-Up Impact

After adopting this naming spec:
- future API resource definitions should use these names
- Phase 2 internal models should prefer these names
- repository mapping code should avoid unnecessary translation aliases
- existing docs with conflicting names should be normalized over time

---

## 11. Minimum Acceptance Criteria

This spec is considered applied when:
- new Phase 2/3 models use these naming conventions
- new API resource docs avoid `raw_payload` / `detail` ambiguity
- future contract additions choose `*_json` consistently for JSON blobs

---

## 12. Final Summary

The main practical naming decisions are:
- use snake_case everywhere
- use `payload_json` for raw JSON payload blobs
- use `detail_json` for structured detail blobs
- use explicit `<resource>_id` names for identifiers
- use canonical time/status names consistently

This should eliminate the most immediate naming drift before implementation starts.