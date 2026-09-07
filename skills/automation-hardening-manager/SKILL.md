---
name: "automation-hardening-manager"
description: "Harden scheduled systems for truth, freshness, latency, idempotency, and fail-closed authority."
---

# Automation Hardening Manager

## Purpose

Make automation reliable without widening authority. Optimize for truthful state, fresh evidence, efficient routes, bounded latency, clean recovery, and visible failure.

## Core Review

For each automated workflow, establish:

1. real job and owner
2. authoritative inputs
3. generated outputs
4. freshness and latency budgets
5. idempotency and deduplication key
6. retry and timeout behavior
7. failure visibility and recovery
8. authority boundary
9. exact acceptance proof

If any field is ambiguous, do not promote autonomy.

## Automation Levels

- Level 0 — observe.
- Level 1 — route.
- Level 2 — refresh review-only proof.
- Level 3 — prepare a bounded helper contract.
- Level 4 — execute validated non-capital proof and refresh front doors.
- Level 5 — stop for a separately authorized owner-gated action.

Success at one level never implies the next.

## Alerts OS Finance Contract

The only active recurring finance chain is:

```text
guarded SQL
  -> explicit current quote proof
  -> alert-level freshness controller
  -> non-executing recommendation digest
```

Preferred runner:

```powershell
python scripts\run_alerts_recommendations_chain.py <morning|midday|post-close|weekly> --timeout-seconds 120 --write --validate
```

Required properties:

- static alert levels are read from active guarded canon
- current-last-completed-session handling is calendar-aware
- stale or conflicted inputs emit visible freshness decay
- digest consumes only the controller output
- runs are bounded by explicit timeouts
- outputs are deterministic enough for contract validation and deduplication
- reruns are idempotent and do not create duplicate delivery
- no stage reads retired portfolio, deployment, or simulated-state artifacts
- no stage writes finance canon or maintains account-like state

## No-False-Green Rules

A scheduler is green only when:

- every enabled job's latest run is successful
- required artifacts exist and meet age contracts
- payload matches the registered contract
- upstream warnings are surfaced rather than suppressed
- no enabled job invokes a retired route
- delivery success is not substituted for data freshness
- validator success is not substituted for recommendation correctness

Historical errors on disabled retired jobs are not active failures; keep them visibly retired.

## Reliability Hardening

Prefer:

- one owner per artifact
- minimal stage count
- exact argv, schedule, timeout, and output contracts
- atomic writes
- stable schema versions
- content or digest keys for deduplication
- bounded retries with explicit terminal failure
- source timestamps and hashes
- age gates and market-calendar awareness
- recovery commands that are safe to rerun
- force-runs only for patched non-delivery jobs during acceptance

Never force an unsafe or delivery job merely to erase red history.

## PM / Helper Delegation

Signals and telemetry may create review-only work candidates. They do not authorize implementation or action.

Every helper lane needs exact deliverables, writable surfaces, stop lines, proof commands, and Main verification. Cron must not spawn uncontrolled writers or infer approval.

## Retired Finance Routes

Do not harden, schedule, revive, or treat as dependencies:

- portfolio board/config/state maintenance
- sizing, sleeve, allocation, weight, cash, tranche, or rebalancing logic
- deployment/trade-grade/card-to-order paths
- simulated account, position, order, reconciliation, or execution systems
- operational WF56/WF58/WF63/WF64/WF67/WF86/WF87 routes

Preserve immutable audit history and deny-only safety evidence.

## Mechanism Choice

- heartbeat — lightweight vigilance
- cron — exact recurring review-only proof
- helper — bounded work with explicit contract
- manual — weak trust, high consequence, or owner decision

## Acceptance

For material hardening, prove:

- targeted tests
- contract parity with zero drift
- cron inventory with zero enabled errors
- freshness/control proofs
- forbidden-route scan over enabled payloads
- alerts-OS pivot validation
- representative non-delivery force-run success
- explicit residual warnings and rollback

## Stop Lines

This skill grants no config, auth, credential, network, channel, startup, service, plugin, runtime, external, destructive, capital, order, brokerage, account, money movement, execution, finance-canon mutation, simulated-state, or owner-approval authority. Exact user approval remains required where workspace doctrine says ask first.
