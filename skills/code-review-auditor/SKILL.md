---
name: "code-review-auditor"
description: "Review OpenClaw diffs for correctness, scope drift, contracts, and proof quality."
---

# Proposed Update: code-review-auditor

## Summary

Keep `code-review-auditor` as a review-only skill, but add stronger targeted-review checks for scope drift, adjacent contract completeness, stale docs, and proof honesty.

## Proposed Description

`Review OpenClaw diffs for correctness, scope drift, contracts, and proof quality. Use when reviewing scripts, validators, manifests, workflow patches, generated-artifact writers, shared JSON/schema/vocab changes, or audit-driven targeted repairs before closure.`

## Add Review Lens: Scope Drift

Before judging correctness, compare the diff against the stated task.

Flag:
- unrelated rewrites
- hidden behavior changes outside the requested lane
- new writes to authority-bearing surfaces
- config/auth/runtime/channel changes not explicitly requested
- finance/account/paper/live/canon/portfolio mutations outside gates
- cleanup or archive behavior mixed into review/validation work

Classify scope drift as blocking when it changes authority, data ownership, runtime exposure, or external behavior.

## Add Review Lens: Adjacent Contract Completeness

When a patch changes shared values, JSON shape, routes, status labels, schema fields, or manifest semantics, inspect beyond the diff:
- producers
- consumers
- validators
- presentation/reporting adapters
- compatibility sidecars
- fallback paths
- docs or route indexes that describe the contract

Look for enum/value additions that were handled in one map but not another.

## Add Review Lens: Documentation And Audit Staleness

If the patch changes behavior that users or future agents rely on, check whether the nearest docs, skill, route capsule, README, audit note, or continuity note still tells the truth.

Report stale docs as material only when they can misroute future work or cause false-green closeout. Do not require documentation churn for small private implementation details.

## Add Review Lens: Claims Versus Proof

For every success claim, ask:
- what command or artifact proves it?
- is it fresh enough?
- did it exercise the runtime path or only compile/import?
- did it inspect a source surface, or only a generated mirror?
- did it validate fail-closed behavior or just the happy path?

Flag compile-only proof when runtime artifact proof is available and material.

## Add Review Lens: Risk And Tradeoff Framing

For architecture/design-gate reviews, include:
- decision being reviewed
- alternatives considered or implicitly ruled out
- reversibility
- failure mode
- blast radius
- probability/impact
- smallest acceptance proof

Do not ask for a full architecture redesign unless the inspected change has a concrete design risk.

## Procedure Addition: Two-Pass Review For Shared Contracts

For shared-contract changes:
1. First pass: inspect correctness and scope drift in changed files.
2. Second pass: search adjacent repository surfaces for old vocabulary, stale assumptions, missing validators, and presentation drift.

Prefer `rg` for the second pass.

## Acceptance Proof

After applying this proposal:
- `openclaw skills check` passes.
- A future targeted review can catch scope drift, stale adjacent consumers, and insufficient proof without widening into implementation by default.
