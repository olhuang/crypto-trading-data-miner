# Minimal Authentication Contract

## Purpose

This document defines the minimum authentication and actor-identity contract needed for the first implementation wave.

It is intentionally narrow.
It does not attempt to define a full production identity platform.

This spec exists so Phase 2 and Phase 3 API implementation can proceed without ambiguity.

It complements:
- `docs/security-and-secrets-spec.md`
- `docs/ui-api-spec.md`
- `docs/implementation-lock.md`
- `docs/peer-review-followups.md`

---

## 1. Scope

This document defines:
- local development auth bypass behavior
- default auth header convention for non-local environments
- actor identity fields required by backend actions
- minimum role shape used by route protection and action authorization

It does not yet define:
- SSO
- multi-factor auth
- refresh token lifecycle
- external identity provider integration

## 1.1 Current Implementation Status

The current repository implements this contract for the initial models API slice:
- local bypass support driven by environment settings
- bearer-header parsing for protected routes
- current-actor resolution with `user_id`, `user_name`, `role`, and `auth_mode`
- role checks for the current `/api/v1/models/*` endpoints

Current protected endpoints:
- `GET /api/v1/models/payload-types`
- `POST /api/v1/models/validate`
- `POST /api/v1/models/validate-and-store`

Current public endpoint:
- `GET /api/v1/system/health`

---

## 2. Local Development Rule

## 2.1 Local Bypass

In `APP_ENV=local`, authentication may be bypassed only when:
- `ENABLE_LOCAL_AUTH_BYPASS=true`

If bypass is enabled:
- backend should inject a placeholder actor identity
- backend should still record actor identity for auditable actions

## 2.2 Local Default Actor

Recommended default local actor:
```json
{
  "user_id": "local-dev",
  "user_name": "Local Developer",
  "role": "admin",
  "auth_mode": "local_bypass"
}
```

This actor should be visible in audit records where relevant.

---

## 3. Non-Local Authentication Rule

For `staging` and `production`:
- authentication is required
- requests should use the `Authorization` header
- bearer-token style is the default first implementation convention

Header form:
```http
Authorization: Bearer <token>
```

This locks the header convention even if the token backend evolves later.

---

## 4. Token Shape (Initial Practical Contract)

For the first implementation wave, the backend may support either:
- a signed JWT-like token, or
- an opaque bearer token resolved server-side

But the API contract exposed to clients is the same:
- client sends `Authorization: Bearer <token>`
- backend resolves current actor identity and role

This means frontend work and API tests do not need to wait for final identity backend selection.

### 4.1 Current Placeholder Bearer Parsing

For the current minimal implementation, bearer tokens may use a simple placeholder form for local/shared testing:

```http
Authorization: Bearer <role>:<user_id>[:<user_name>]
```

Examples:
- `Authorization: Bearer developer:u_123`
- `Authorization: Bearer admin:u_999:Alice`

If the token does not follow that structured form, the current implementation may still resolve a default bearer actor. This placeholder parsing rule is for initial implementation convenience and can later be replaced without changing the header convention itself.

---

## 5. Current Actor Model

The backend should resolve a current actor with at least these fields:

```json
{
  "user_id": "u_123",
  "user_name": "Alice",
  "role": "operator",
  "auth_mode": "bearer"
}
```

Minimum required fields:
- `user_id`
- `user_name`
- `role`
- `auth_mode`

Optional later fields:
- `team`
- `email`
- `scopes`
- `session_id`

---

## 6. Role Model

Use the same initial role set already established elsewhere:
- `developer`
- `researcher`
- `operator`
- `admin`

## 6.1 Minimum Authorization Guidance

### Developer
Can:
- inspect system and bootstrap pages
- use model validation and repository explorer
- inspect ingestion and logs

### Researcher
Can:
- inspect data
- run backtests
- inspect paper outputs

### Operator
Can:
- run paper sessions
- inspect and operate live runtime according to policy
- inspect reconciliation and risk events

### Admin
Can:
- access all routes/actions
- invoke emergency and deployment-level controls

---

## 7. API Behavior on Missing or Invalid Auth

If auth is required and missing:
- return `401 UNAUTHORIZED`

If auth is present but actor lacks permission:
- return `403 FORBIDDEN`

Error envelope should follow the common API error shape.

Example:
```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "FORBIDDEN",
    "message": "actor role does not allow this action",
    "details": {}
  },
  "meta": {
    "request_id": "req_001",
    "timestamp": "2026-04-02T12:00:00Z"
  }
}
```

---

## 8. Actor Identity in Audit-Relevant Actions

For user-triggered actions, backend must persist actor identity where relevant.

Examples:
- bootstrap verification
- bar backfill trigger
- backtest run create
- paper session start/stop
- live order submit/cancel
- emergency stop
- mismatch review

Minimum persisted actor fields:
- `requested_by` or equivalent user identifier
- environment
- timestamp

---

## 9. Frontend Contract Implications

Frontend should assume:
- in local dev, it may operate without login UI if local bypass is enabled
- in non-local environments, requests must include `Authorization: Bearer <token>`
- route visibility should still be role-aware once current actor is known

Frontend does not need final login UX to begin implementing protected-route patterns.

---

## 10. Testing Implications

API tests should support at least two modes:
- local bypass mode
- bearer-token-required mode

This allows Phase 2 API tests to start before a full identity platform exists.

---

## 11. Deferred Topics

These are intentionally deferred:
- refresh token behavior
- login endpoint UX
- session expiry policy details
- federated identity integration
- full production IAM design

These should not block Phase 2/3 implementation.

---

## 12. Minimum Acceptance Criteria

This auth contract is sufficiently specified when:
- local bypass behavior is deterministic
- non-local header convention is fixed
- actor identity shape is fixed
- role model is fixed
- 401 vs 403 behavior is fixed
- auditable actions persist actor identity

---

## 13. Final Summary

The minimal authentication contract is:
- local bypass allowed only in local mode with explicit flag
- non-local requests use `Authorization: Bearer <token>`
- backend resolves a current actor with `user_id`, `user_name`, `role`, and `auth_mode`
- backend enforces role checks for protected actions
- auditable actions always preserve actor identity

This is enough to begin API implementation without waiting for a full auth platform.
