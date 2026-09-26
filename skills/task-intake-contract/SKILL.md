---
name: "task-intake-contract"
description: "Translate material requests into objective, authority, source, implementation, cleanup, and proof contracts."
---

# Task Intake Contract

## Purpose

Turn a material request into a compact operating contract before acting. Optimize for speed with clear scope, authority, truth sources, stop lines, and acceptance.

## Risk Tiers

- `tiny` — direct answer or one safe step.
- `routine` — bounded inspection or edit.
- `material` — multi-step implementation, finance, cron, workflow, or cleanup.
- `high-risk` — config/runtime, external action, destructive work, credentials, capital, order, account, brokerage, money movement, or execution.

Give a short visible mission statement for material work. Ask only when required authority or a consequential user choice is genuinely missing.

## Contract Fields

Establish:

1. objective
2. interpretation
3. non-goals
4. authority class
5. source surfaces
6. shortest sound approach
7. debugging loop
8. cleanup scope
9. stop lines
10. acceptance proof
11. closeout shape

## Visible Pattern

```text
I'm treating this as <objective>. I'll use <authoritative sources>, keep <boundary> out of scope, and consider it done when <acceptance proof> is clean.
```

For a high-risk boundary, state the stop line directly.

## Finance Alerts And Recommendations

The finance OS owns alerts, evidence, source lineage, freshness, thesis context, bands, invalidation thresholds, routing, and non-executing recommendations.

Default finance authority is review-only. Intake must identify:

- evidence freshness and market-session state
- recommendation versus approval
- active alert state
- thesis, risks, timeframe, and invalidation context
- guarded SQL and source lineage
- Randall's decision point

The OS does not own or maintain holdings, sleeves, positions, allocations, weights, sizing, tranches, cash posture, rebalancing, simulated positions, order packages, brokerage/account state, or execution paths.

Paper and live execution are outside the OS, not conditionally available finance routes. Stop if a request requires capital, order, account, brokerage, money movement, endpoint/credential use, or execution.

Owner-provided objectives or limits may inform a response transiently; do not write them into maintained portfolio state.

## Code And Workflow

For local implementation:

- inspect exact owner surfaces
- check concurrent write lanes
- lease narrow writes
- when changing local scripts or tests for a review-only finance workflow, declare the source-code lane `workspace-write` and preserve the produced finance output as review-only; do not combine `review_only` authority with a write-capable lane, because the contract is intentionally blocked
- reproduce the failure
- patch the smallest owner
- add regression proof
- rerun the original failure
- run proportionate broader acceptance

Preserve unrelated dirty work.

## Cron

Separate contract edits, scheduler edits, and force-run acceptance. Require exact job IDs, payloads, schedules, timeouts, output contracts, rollback, and enabled-error proof.

Build a promoted recurring payload only from the validated repair's declared entry points, not from an older broad chain manifest. If the forced canary exposes an adjacent retired dependency, remove the failed job before repairing; decide whether that step belongs to the approved scope, then recreate and retest the narrowed job. Never recreate a retired input merely to make the canary green.

During a declared frozen observation window, run the canary outside the observation hours and suppress natural payloads until the authoritative closeout state is closed or accepted. Use a read-only, fail-closed condition gate bound to the closeout artifact and include that gate in the cron contract; an open, unreadable, or unknown state must not run the payload. Do not rely on a calendar date alone when the window can restart.

Before crediting a frozen observation session or reporting the gate ready to close, compare every declared frozen source surface with its window-start baseline using its recorded hash or a scoped source diff/history. Treat a verified post-window change according to the declared restart rule. A green current run or fresh receipt proves only the current build; it cannot certify earlier sessions. If the restart rule distinguishes trading sessions from a closed-market observation, verify separately that the observation ran on the post-change build rather than assuming it carries forward or must repeat. On a hash mismatch, stop before crediting the session or declaring a restart: date the change from file mtimes, characterize what changed by reading the changed region, and search for a written owner approval record; with none found, ask the owner rather than assuming either outcome. Record a verbal owner adjudication in the declaration's session addendum together with the re-pinned observed-build hashes — that addendum then serves as the approval record — and let the owner's explicit restart-or-continue decision govern, which supersedes the default restart rule only because it is recorded. Read current window state and banked-session evidence from the canonical live declaration file, not from suffixed point-in-time copies beside it, which lack later addenda. Before crediting, also check for unapplied staged patch drafts targeting a frozen surface (for example `patched_*.py` under `tmp/`): flag any found as an open provenance item, and never apply one mid-window, because applying it is itself a restart-class change. Resolve the provenance before reporting it as unknown: read the artifact's own docstring and any sibling generator (proposal and validator files in this workspace self-identify their purpose by design), date the artifact cluster by mtime, and match the writing session from the session list rather than treating the file as an outside actor. When comparing a staged copy against the live file with `git diff --no-index staged live`, the first path owns the `-` lines — state which side carries the change before claiming anything about the live build.

Do not force delivery or retired unsafe jobs merely to clear historical state.

## Config / Runtime / External

Inspect and propose by default. Apply only with explicit approval. Never expose secrets.

## Cleanup / Archive

Require exact target inventory, reference review, hashes, rollback, validation, and explicit destructive/archive authority. Keep the operation bounded to resolved workspace paths.

## Research And Advice

Use local owner truth first. Use narrow external evidence only when needed. State confidence, freshness, missing evidence, and what would change the judgment.

Re-measure any quantitative fact before it anchors a scope claim or recommendation — file sizes, config keys and their defaults, source-list membership, test coverage, gating semantics. A number recalled from a prior note, memory, or earlier analysis is a hypothesis; the live surface is the evidence. Quote the measured value and where it was measured in the contract, and prefer withdrawing an earlier claim over defending it from a note.

When the live surface is a growing or append-only artifact (session log, event ledger, receipt stream), a count is valid only as of its cutoff: record that cutoff with the value and never restate it as a period or day total, because the same file later yields a larger count. Bound a claim by its scope as well as its cutoff: "no mutation in this lane" is a different claim from "no mutation today", and the narrower statement must not be restated as the broader one. Verify a claimed artifact by resolving and enumerating its named path rather than searching for the claimed number, since a literal-value search both misses reformatted matches and returns coincidental ones. A flag or evidence field inside a derived artifact (opportunity queue, decision docket, scorecard) is likewise a hypothesis when a durable row-level store exists behind it: before acting on the signal — drafting a proposal a gate conditions on a repeated pattern, opening a repair, ranking work — count the matching rows in the primary store and check the aggregator's own build status, because an aggregator running in a warning or error state can emit a signal with nothing behind it, and a pattern whose repeats exist only in retired lanes fails the gate's own repetition test. Build the search itself with literal or regex patterns (`Select-String -Pattern`, escaped metacharacters, or `-SimpleMatch`): wildcard `-like`/`-Filter` patterns treat `[` `]` `*` and `?` as metacharacters and throw or silently mismatch, and this host's PowerShell rejects the `??` operator at parse time, so use an explicit `if`/`else` test.

## Debugging Loop

1. reproduce or inspect
2. isolate the owner
3. patch narrowly
4. add regression coverage
5. rerun the failing gate
6. run broader proof
7. report fixed, warning-grade, or blocked

For blocked artifact consumers, cross-chain discrepancies or generated-mirror parity failures, use [fail-closed chain debugging](references/chain-debugging.md) before patching. It distinguishes stale inputs, fresh validation failures, healthy terminal statuses and context drift without widening the lease.

For historical lane-register errors or missing terminal proof, use the audit owner's [historical lane validation](../veritas-workspace-audit-orchestrator/references/historical-lane-validation.md) instead of regenerating evidence or changing lane state.

## Closeout

Report:

- bottom-line outcome
- material changes
- pass/warning/fail proof
- freshness and trust limits
- authority boundaries
- one to three ranked next actions

Never let a validator, packet, clean cron run, generated card, or recommendation imply authority beyond the contract.
