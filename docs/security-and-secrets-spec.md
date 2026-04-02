# Security and Secrets Spec

## Purpose

This document defines the baseline security model for the trading platform.

It focuses on:
- secrets handling
- exchange credential management
- authentication and authorization
- auditability for sensitive actions
- environment isolation
- secure operational defaults

This spec complements:
- `docs/backend-system-design.md`
- `docs/ui-api-spec.md`
- `docs/observability-spec.md`

---

## 1. Security Goals

The security model must protect:
1. exchange API credentials
2. live trading controls
3. account and treasury data
4. deployment/config change integrity
5. audit history of sensitive actions

The system should aim for:
- least privilege
- explicit authorization for high-risk actions
- secure-by-default local and shared environments
- auditable control paths for live trading

---

## 2. Security Scope

This document covers:
- backend service credentials
- exchange API secrets
- internal UI/API auth model
- role-based authorization
- live-action safety controls

It does not attempt to be a full enterprise infosec program.

---

## 3. Environment Security Model

## 3.1 Environment Separation

Minimum environments:
- local development
- staging/shared dev
- production/live

Rules:
- credentials must never be reused across these environments unnecessarily
- live trading keys must not be used in local dev
- production config must be isolated from development runtime defaults

## 3.2 Local Development Rules

Local development may use:
- `.env` files
- local-only developer credentials
- auth bypass only in explicitly marked development mode

Local development must not:
- commit secrets to the repository
- hardcode API keys in source files
- use production exchange keys

---

## 4. Secrets Handling

## 4.1 Secret Types

Examples:
- exchange API key
- exchange API secret
- session/token signing secret
- DB password
- Redis password if enabled later
- webhook/alerting secrets

## 4.2 Secret Storage Rules

Recommended progression:
- local dev: environment variables via local `.env`
- shared env and production: dedicated secret manager or secure deployment secret injection

Rules:
- secrets must not be stored in the repo
- secrets must not be stored in plaintext config docs except placeholders/examples
- secrets must not be echoed to logs

## 4.3 Secret Access Boundaries

Only the processes that require a secret should receive it.

Examples:
- public market collector should not receive live private trading credentials
- UI frontend should never receive raw exchange API secrets
- API server should not expose secrets in any debug endpoint

---

## 5. Exchange Credential Model

## 5.1 Credential Scope

Exchange credentials should be scoped by:
- exchange
- account
- environment
- permission level

## 5.2 Permission Separation

Where exchange capabilities allow, separate credentials by use case:
- read-only account sync
- trading-enabled account access
- treasury-enabled access if needed

## 5.3 Account Mapping

Each credential set should map to a known internal account record.
Credential ownership must be auditable.

## 5.4 Rotation Expectations

Credential design should support rotation without code changes.
Documented rotation process should exist before broad live use.

---

## 6. Authentication Model for Internal APIs

## 6.1 Minimum Modes

### Local Development
- optional auth bypass explicitly gated by environment

### Shared/Production Environments
- authenticated access required
- session or token-based authentication required

## 6.2 Authentication Rules

- all non-public internal UI APIs should require auth outside local dev bypass mode
- the system must know the acting user identity for sensitive actions
- background jobs triggered by users should persist actor identity where relevant

---

## 7. Authorization / RBAC Model

## 7.1 Recommended Roles

- `developer`
- `researcher`
- `operator`
- `admin`

## 7.2 Role Guidance

### Developer
Can:
- inspect system state
- run bootstrap verification
- inspect model validation and ingestion

Should not by default:
- place live orders in shared/prod environments

### Researcher
Can:
- inspect data
- run backtests
- inspect paper sessions

Should not by default:
- control live trading
- manage deployments/config for production

### Operator
Can:
- operate paper/live runtimes
- inspect reconciliation and risk state
- invoke live-safe operational controls according to policy

### Admin
Can:
- manage all routes and controls
- manage deployments/config changes
- invoke highest-risk actions such as emergency stop and account-level controls

## 7.3 Action-Level Controls

High-risk actions must be role-gated.
Examples:
- start/stop live strategy
- submit/cancel live order
- emergency stop
- mark reconciliation mismatches reviewed if policy requires elevated access
- deployment/config changes

---

## 8. High-Risk Action Safety Rules

## 8.1 Mandatory Audit

The following actions must be auditable with actor identity:
- live strategy enable/disable
- manual live order submit/cancel
- emergency stop
- deployment/config changes
- treasury-sensitive actions if later added

## 8.2 Confirmation Controls

UI and backend must both enforce extra care for high-risk actions.
Recommended controls:
- confirmation modal in UI
- explicit server-side authorization check
- reason field where applicable

## 8.3 Emergency Stop Rules

Emergency stop should be:
- highly restricted
- auditable
- clearly scoped (account, strategy, environment, or global)
- designed so intent is not ambiguous

---

## 9. Logging and Redaction Rules

## 9.1 Never Log
- exchange API secret
- session signing secret
- raw auth headers
- full private credential payloads

## 9.2 Redact or Mask Where Needed
- API keys (partial masking)
- wallet addresses where policy requires
- internal tokens

## 9.3 Safe Diagnostic Logging

It is acceptable to log:
- account code
- exchange code
- request id
- job id
- action result
- masked credential reference identifiers

---

## 10. Secure Defaults for Live Trading

Before enabling live trading broadly, require:
- explicit environment flag for live mode
- explicit account mapping
- role-checked control actions
- auditable order/cancel path
- emergency stop path
- production-safe secret injection

Live mode should never be enabled accidentally by default local settings.

---

## 11. Deployment and Config Integrity

Strategy deployment and config changes must be protected by:
- authenticated actor identity
- authorization check
- persisted audit record
- version/config snapshot capture

This aligns with existing deployment/config audit schema.

---

## 12. Data Exposure and Access Rules

## 12.1 UI Exposure Rules

The UI should expose:
- operational states
- balances/positions as allowed by role
- logs and raw payloads only according to role/sensitivity

The UI should not expose:
- raw secrets
- privileged internal config unrelated to the user's role

## 12.2 API Exposure Rules

Internal APIs should return only the fields needed for the UI use case.
Sensitive fields should be omitted or masked by default.

---

## 13. Operational Security Practices

Minimum practices:
- rotate credentials when personnel or environment risk changes
- remove unused credentials promptly
- isolate production credentials from development environments
- review audit logs for live-control actions
- avoid broad multi-purpose keys when narrower scopes are possible

---

## 14. Minimum Acceptance Criteria

The security and secrets model is sufficiently specified when:
- secret handling rules are explicit
- exchange credential boundaries are explicit
- auth modes are defined
- RBAC roles and high-risk action policies are defined
- audit requirements for sensitive actions are explicit
- log redaction rules are explicit

---

## 15. Final Summary

The security baseline for this platform is:
- no secrets in repo or logs
- environment-separated credentials
- authenticated internal APIs outside local bypass mode
- role-based controls for sensitive actions
- auditable live-trading and deployment controls
- secure-by-default live-mode behavior

This is the minimum acceptable foundation before meaningful live-trading usage.