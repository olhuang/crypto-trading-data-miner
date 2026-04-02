# Risk Limit Fallback Policy

## Purpose

This document defines how the system should behave when risk-limit fields are missing, null, incomplete, or otherwise not usable.

It exists to prevent ambiguous pre-trade risk behavior during implementation.

This spec complements:
- `docs/execution-and-risk-engine-spec.md`
- `docs/security-and-secrets-spec.md`
- `docs/implementation-lock.md`
- `docs/peer-review-followups.md`

---

## 1. Problem Statement

Risk tables may contain nullable fields such as:
- `max_position_qty`
- `max_notional_usd`
- `max_leverage`
- `max_daily_loss`

Without a fallback policy, implementation may diverge on whether a null value means:
- no configured limit
- unlimited
- invalid configuration
- block all trading until configured

This document locks the default behavior.

---

## 2. Core Policy

## 2.1 Default Interpretation

For the first implementation wave:

**NULL means “no explicit configured limit for that specific field.”**

It does **not** automatically mean:
- block all trading
- configuration error
- implicit zero

## 2.2 Risk Engine Default Action

The pre-trade risk engine still defaults to **block** when a concrete rule is violated.
But a missing optional limit value by itself does not count as a rule violation unless strict mode is explicitly enabled.

This keeps the behavior aligned with:
- `implementation-lock.md` default of `block` for actual risk-check failures
- practical early implementation where not every account/instrument has every limit populated on day one

---

## 3. Modes

## 3.1 Normal Mode (Default First-Wave Behavior)

In normal mode:
- if a limit field is NULL, that specific check is treated as not configured
- the system may still allow trading if all other applicable checks pass
- the system should emit a warning or audit note when a missing limit matters operationally

## 3.2 Strict Mode (Future / Production-Hardened Option)

In strict mode:
- selected missing critical limits may be treated as configuration errors
- trading may be blocked until required limits are configured

Strict mode is not the default first-wave behavior unless explicitly enabled by a later implementation/config flag.

---

## 4. Rule by Limit Type

## 4.1 `max_position_qty`

If NULL:
- treat as not configured
- do not block solely because this field is NULL

If configured:
- block when proposed resulting position exceeds the configured value

## 4.2 `max_notional_usd`

If NULL:
- treat as not configured

If configured:
- block when resulting notional exceeds configured limit

## 4.3 `max_leverage`

If NULL:
- treat as not configured

If configured:
- block when resulting leverage would exceed configured limit

## 4.4 `max_daily_loss`

If NULL:
- treat as not configured

If configured:
- block or escalate according to policy once daily loss exceeds configured threshold

---

## 5. Missing Row vs Missing Field

## 5.1 Missing Field in Existing Limit Record

If a limit row exists but one field is NULL:
- interpret only that field as unconfigured
- continue evaluating other populated fields normally

## 5.2 Missing Limit Row for Scope

If no limit row exists for the relevant account/scope:
- in the first implementation wave, treat the scope as having no configured limits unless a stricter environment policy is introduced
- record a warning if the scope is expected to be governed by limits

This avoids accidental hard blocking of all early paper/backtest execution.

---

## 6. Environment Guidance

## 6.1 Backtest

Backtest may proceed with missing limits unless the run explicitly enables risk enforcement that requires configured limits.

## 6.2 Paper

Paper may proceed with missing limits in the first implementation wave, but warnings should be visible.

## 6.3 Live

Live is more sensitive.
Recommended first-wave guidance:
- allow the same fallback logic in implementation
- but strongly prefer configured limits before enabling meaningful live operation
- treat missing live limits as operational warnings at minimum

A later strict production mode may upgrade these to blocking behavior.

---

## 7. Warning / Audit Behavior

When a limit is missing and a corresponding check is skipped, the system should be able to emit one of:
- structured warning log
- risk note/event marked as non-blocking
- configuration warning surfaced in UI or ops views

This is especially useful for:
- paper sessions
- live session startup validation
- account onboarding checks

---

## 8. API / UI Implications

If UI exposes configured limits, it should be able to distinguish:
- configured numeric value
- not configured / null

Do not silently render NULL as zero.

Suggested display semantics:
- `Not configured`
- `—`

rather than misleading numeric placeholders.

---

## 9. Example Evaluation Outcomes

### Example A
- `max_position_qty = NULL`
- `max_notional_usd = 10000`
- proposed order keeps notional below 10000

Outcome:
- allow
- record that position-qty check was skipped as unconfigured

### Example B
- `max_position_qty = 1.0`
- resulting position would be 1.2

Outcome:
- block
- emit risk event

### Example C
- no risk-limit row exists for a paper account in early development

Outcome:
- allow in default first-wave behavior
- warning recommended

---

## 10. Deferred Future Refinements

These may be added later:
- environment-specific strict mode flags
- mandatory live limit configuration policy
- required-minimum limit sets per account type
- startup health checks that fail when live accounts lack configured limits

---

## 11. Minimum Acceptance Criteria

This policy is sufficiently specified when:
- NULL field behavior is deterministic
- missing row behavior is deterministic
- backtest/paper/live default handling is documented
- UI and backend do not misinterpret missing limits as zero

---

## 12. Final Summary

The locked first-wave fallback policy is:
- NULL risk-limit fields mean “not configured”
- missing limit rows also default to “not configured” in the first implementation wave
- actual configured limit violations still block by default
- missing limits should generate warnings where operationally relevant
- strict blocking for missing limits is deferred to a later hardened mode

This prevents inconsistent early implementation while still preserving a safety-oriented path for later production tightening.