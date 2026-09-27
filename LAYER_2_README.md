# FPL Strategist — Layer 2

## Purpose

Layer 2 establishes two independent foundations:

1. **Data-driven FPL Rules Engine**
2. **Freshness Policy Engine**

### Rules architecture

The Strategist must not permanently hard-code season rules as its ultimate
source of truth.

The intended flow is:

Official FPL/Premier League source
→ rules source adapter
→ validation
→ versioned rules store
→ active rules version
→ typed Rules Engine
→ deterministic consumers.

The included 2026/27 fallback rules exist only for local development/tests.
Production strategy must require an authoritative rules snapshot.

### Rule refresh cadence

FPL rules are normally stable for a season, so the normal policy is effectively
one seasonal refresh. The architecture nevertheless supports exceptional
mid-season changes.

When a new authoritative rules payload differs from the active fingerprint:

- preserve the previous version
- close its validity period
- create a new version
- activate the new version
- retain both versions for auditability.

This means a future ordinary rule change should not require changing
`transfer_engine.py`, `chip_engine.py`, `captain_engine.py`, or the ML/xP code.

## Freshness

Freshness answers:

> Is the stored dataset fresh enough for this operation?

It does not perform API calls.

Initial policies are operational defaults and can later be changed through
configuration without changing strategy logic.

Near-deadline availability/news uses a shorter TTL than ordinary analysis.

## Important boundary

Official FPL rules and our strategy rules are different.

Official rules determine what is legal and how FPL points are scored.

Strategy rules/models determine what action the Strategist recommends.

The LLM should not invent or override official FPL rules.
