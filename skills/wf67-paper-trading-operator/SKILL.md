---
name: "wf67-paper-trading-operator"
description: "Deny-only historical safety tombstone; blocks former simulated execution and account routes."
---

# Deny-Only Historical Safety

The operational simulation lane was retired on 2026-08-29.

Allowed behavior is limited to explaining these fail-closed controls:

- keep live and simulated endpoints isolated and unreachable;
- redact credentials and secrets;
- reject stale or ambiguous artifacts;
- preserve immutable historical audit evidence;
- report that no action is authorized.

Do not access endpoints or credentials. Do not read or reconcile accounts, positions, or orders. Do not create request cards, order terms, kill switches, packages, notifications, submit/cancel/sell paths, or simulated state. Do not route through WF86 or WF87.

All current finance work terminates at alerts and non-executing recommendations. Restoring any operational path requires a new explicit architecture decision from Randall.
