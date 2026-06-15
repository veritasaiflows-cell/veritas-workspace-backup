---
name: "workspace-qa-pass"
description: "Run high-signal QA on Veritas workspace changes, audit claims, and control-plane consistency."
---

# Proposed Update: workspace-qa-pass

## Summary

Tighten `workspace-qa-pass` so it can independently review not just implementation patches, but audit claims and control-plane consistency. Keep it bounded and evidence-first.

## Proposed Description

`Run high-signal QA on Veritas workspace changes, audit claims, and control-plane consistency. Use when checking residual integrity risk, orchestration drift, live-artifact mismatches, schema/contract propagation, skill hygiene, or whether an audit or hardening pass actually closed the intended gaps.`

## Add Section: Layered QA Stack

When reviewing a completed audit, hardening pass, workflow repair, or generated proof claim, use this layered check:

1. **Existence**: Does the claimed file/artifact/proof exist where stated?
2. **Authenticity**: Was it produced by the expected script, workflow, or owner surface?
3. **Freshness**: Is the timestamp current enough for the claim?
4. **Accuracy**: Does the artifact content match the live owner/source surface?
5. **Authority**: Does the artifact stay inside review/proof authority and avoid implying approval/execution/mutation?
6. **Closure**: Do queue, lane, memory, and audit surfaces agree on what remains open?

If any layer fails, report the weakest layer instead of claiming global failure or success.

## Add Section: Live State Versus Generated Artifact Reconciliation

When QA reviews PM, cron, runtime, routes, or dashboards, compare generated control packets against live control surfaces when available.

Examples:
- cron control packet green but scheduler `lastRunStatus` has errors
- PM packet says no blockers while lane register still has active or stale lanes
- runtime scorecard green while harness artifact is stale or warning
- route registry green while binary freshness is stale

Report conflicts explicitly with:
- generated artifact status
- live/source status
- likely owner
- next proof needed

Do not collapse conflicting statuses into a single green summary.

## Add Section: Audit Claim QA

When reviewing a workspace audit, check whether:
- every P1/P2 finding has evidence, impact, recommendation, and acceptance proof
- top findings are current, not copied from stale memory
- unresolved blockers name owner surfaces and stop lines
- recommendations route to skills, procedures, validators, or queue items when they are recurring
- finance/account/paper/live/config boundaries remain explicit
- intentionally deferred checks are named

## Add Section: External Pattern Intake QA

When a pass borrows from ClawHub or web sources:
- verify the source pattern is summarized, not blindly installed
- check for security warnings or generic instructions that conflict with Veritas doctrine
- confirm adopted behavior is routed into a Veritas-owned skill/procedure/validator
- ensure third-party examples do not introduce Bash assumptions, config mutation, credential exposure, public/customer action, or finance authority drift

## Add Section: Worker Cannot Review Itself

If the same lane implemented a substantial change and then claims closure, QA should treat that as implementation evidence, not independent proof.

For higher-risk changes, recommend one of:
- main-session independent inspection
- a bounded helper QA lane
- a deterministic validator
- a targeted acceptance command

Do not require a separate reviewer for tiny local edits when direct proof is enough.

## Acceptance Proof

After applying this proposal:
- `openclaw skills check` passes.
- A future QA pass can catch live scheduler/artifact mismatch and audit-claim overreach without inventing new criteria in chat.
