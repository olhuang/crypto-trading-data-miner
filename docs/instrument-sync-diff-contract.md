# Instrument Sync Diff Contract

## Purpose

This document defines how instrument metadata differences should be represented after an instrument sync job.

It exists because the UI expects metadata-difference visibility, but the immediate sync trigger response only returns a job identifier and status.

This spec complements:
- `docs/ui-api-spec.md`
- `docs/api-resource-contracts.md`
- `docs/job-orchestration-spec.md`
- `docs/peer-review-followups.md`

---

## 1. Design Principle

The immediate response to `POST /api/v1/ingestion/jobs/instrument-sync` should remain lightweight.
It should not attempt to include the full metadata diff payload inline.

The canonical pattern is:
1. trigger sync job
2. return `job_id` and `status`
3. fetch job detail resource
4. inspect summary and diffs from job detail

---

## 2. Trigger Response Rule

The trigger endpoint:
- `POST /api/v1/ingestion/jobs/instrument-sync`

should return only a lightweight acknowledgment such as:

```json
{
  "success": true,
  "data": {
    "job_id": "job_123",
    "status": "queued"
  },
  "error": null,
  "meta": {
    "request_id": "req_001",
    "timestamp": "2026-04-02T12:00:00Z"
  }
}
```

This keeps the trigger contract simple and async-friendly.

---

## 3. Job Detail Endpoint Requirement

A job-detail endpoint or equivalent domain-specific detail endpoint must expose:
- job summary
- inserted count
- updated count
- unchanged count
- failed count if applicable
- diffs for changed instruments

Recommended endpoint shape:
- `GET /api/v1/ingestion/jobs/{job_id}`

If the project later prefers a more specific endpoint, that is acceptable as long as the diff resource model remains consistent.

---

## 4. Diff Resource Shape

## 4.1 Job-Level Resource

```json
{
  "job_id": "job_123",
  "job_type": "instrument_sync",
  "status": "succeeded",
  "exchange_code": "binance",
  "started_at": "2026-04-02T12:00:00Z",
  "finished_at": "2026-04-02T12:00:03Z",
  "summary": {
    "instruments_seen": 450,
    "instruments_inserted": 2,
    "instruments_updated": 4,
    "instruments_unchanged": 444,
    "instruments_failed": 0
  },
  "diffs": []
}
```

## 4.2 Instrument Diff Item

```json
{
  "unified_symbol": "BTCUSDT_PERP",
  "venue_symbol": "BTCUSDT",
  "change_type": "updated",
  "field_diffs": [
    {
      "field_name": "tick_size",
      "old_value": "0.10",
      "new_value": "0.01"
    }
  ]
}
```

## 4.3 Allowed `change_type` Values

Recommended values:
- `inserted`
- `updated`
- `unchanged`
- `failed`

UI may choose to display only `inserted` and `updated` rows in the diff section.

---

## 5. Field Diff Rules

Each field diff item should include:
- `field_name`
- `old_value`
- `new_value`

Optional later additions:
- `diff_category`
- `source_time`
- `normalization_note`

Values may be strings when preserving exact decimal-like formatting is useful.

---

## 6. UI Expectations

The UI should:
- trigger instrument sync
- receive `job_id`
- poll or fetch job detail
- display summary counts immediately once available
- display diffs for inserted/updated instruments

The UI should **not** assume diffs are present synchronously in the trigger response.

---

## 7. Storage / Observability Expectations

The backend may persist diff details in:
- job metadata
- a dedicated sync result record
- structured ops log / result blob

This spec does not force a specific persistence table, only the contract shape exposed to API/UI.

---

## 8. Error Behavior

If the job fails before diff generation:
- `status` should indicate failure
- `summary` should still include counts if available
- `diffs` may be empty
- failure details should be available in error metadata/logs/job detail

---

## 9. Minimum Acceptance Criteria

This contract is sufficiently specified when:
- instrument sync trigger returns a lightweight async acknowledgment
- a follow-up detail resource exposes diffs and summary counts
- UI can display metadata differences without guessing payload shape

---

## 10. Final Summary

The locked behavior is:
- trigger endpoint returns only job acknowledgment
- diff data is exposed through job detail
- diff payload uses instrument-level `change_type` and `field_diffs`

This keeps instrument sync fully compatible with the repository's async job pattern while still satisfying UI validation needs.