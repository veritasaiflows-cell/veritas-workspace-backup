---
name: "task-intake-contract"
description: "Translate material user tasks into mission, authority, debugging, cleanup, and proof contracts."
---

# Task Intake Contract

Use this skill when a user asks for material work that requires interpretation, multi-step execution, source selection, debugging, cleanup, finance/workflow judgment, implementation, config/runtime care, or owner-gated action handling.

Do not use this skill for tiny direct answers, simple command outputs, or obvious one-step edits unless the task touches finance, execution, credentials, config/runtime, external delivery, destructive cleanup, or another high-risk boundary.

## Purpose

Convert the user's natural-language request into an explicit operating contract before acting. The contract is the working prompt: it states what the mission is, what is out of scope, which authority boundary applies, what sources/proof matter, how debugging will run, what cleanup is included, and what will count as done.

The goal is speed with clarity, not ceremony. Keep the intake compact and scale it to risk.

## Risk Tiers

Classify the request first:

- `tiny`: one-step answer or command; no visible contract needed.
- `routine`: small edit, status, or bounded inspection; use an internal mini-contract and proceed.
- `material`: multi-step implementation, workflow, finance, cron, PM, paper-trading, broad inspection, or cleanup; provide a short visible mission statement before work.
- `high-risk`: finance execution, portfolio/canon mutation, credentials, config/runtime, external delivery, destructive/archive work, paper/live/account action, or ambiguous authority; state the contract and ask only when authority is genuinely missing.

## Contract Fields

For material or high-risk tasks, establish these fields before acting:

1. `Objective`: the concrete outcome Randall is asking for.
2. `Interpretation`: how the request is being translated into the working mission.
3. `Non-goals`: what will not be done, especially authority-sensitive actions.
4. `Authority class`: safe autonomous, review-only, owner-gated, blocked, external-sensitive, destructive-sensitive, config/runtime-sensitive, finance-sensitive, paper-only, or live-blocked.
5. `Source surfaces`: the first files, artifacts, memory, workflow capsules, or tools that should ground the work.
6. `Approach`: the shortest sound path, including whether to inspect, implement, validate, or prepare an approval artifact.
7. `Debugging loop`: reproduce, isolate, fix, add/adjust regression proof, rerun the failing gate, then close out.
8. `Cleanup scope`: adjacent cleanup included only when local, reversible, validator-proven, and within authority; otherwise route it as a follow-up or ask Randall.
9. `Stop lines`: conditions that force a block, user decision, or narrower scope.
10. `Acceptance proof`: exact tests, validators, artifacts, reconciliation, or user-visible result that prove done.
11. `Response contract`: what Randall should receive at closeout: result, proof, trust limits, and next recommendations.

## Visible Intake Pattern

For material tasks, send one short update before tool work:

```text
I'm treating this as <objective>. I'll use <source/proof surfaces>, keep <boundary> out of scope, and consider it done when <acceptance proof> is clean.
```

For high-risk tasks, include the stop line:

```text
Stop line: I will not <blocked action> unless <exact approval/proof> exists.
```

Do not expose detailed hidden reasoning. Do not turn every small task into a checklist.

## Task-Class Defaults

### Finance / Capital / Paper Trading

Default authority: review-only unless exact Randall approval and workflow-specific guard proof exist.

Required intake additions:

- source freshness and market-session state
- recommendation vs approval boundary
- review-ready vs deployable boundary
- paper/live/account/money movement boundary
- exact order/card terms when relevant
- fresh WF67/WF63 guard, kill switch, wrapper, and reconciliation requirements for paper execution

Stop if approval is inferred, quote/band proof is stale for execution, guard proof fails, live endpoint/account authority appears, or terms are incomplete.

### Code / Workflow / Validators

Default authority: safe local implementation when inside workspace and non-destructive.

Required intake additions:

- changed surfaces and owner files
- lane-register check when concurrent or write-heavy
- narrow write scope
- targeted tests first, then changed-file/router/release proof as risk demands
- adjacent cleanup rule

Debugging loop: reproduce the failing gate, inspect owner code, patch narrowly, add regression proof, rerun the original failure, then close out.

### Config / Auth / Runtime / External Delivery

Default authority: ask-first unless explicit approval exists.

Required intake additions:

- exact config/auth/runtime/external surface
- backup or rollback requirement
- no secret exposure
- no channel/network/startup/service mutation without approval

Stop before mutation when authority is ambiguous.

### Cleanup / Archive / Delete

Default authority: review-only until explicit destructive/archive approval.

Required intake additions:

- target inventory
- reference review
- backup/rollback
- dry-run proof
- exact apply approval

Stop before destructive changes.

### Research / Advice / Strategy

Default authority: answer from the best available source surface, disclose freshness and uncertainty.

Required intake additions:

- local truth surface first when workspace owns the domain
- web/source-open only when needed
- confidence and missing evidence
- recommendation vs action boundary

## Cleanup Rule

Include cleanup in the task only when it is necessary to make the original work truthful or release-clean and it stays inside the task authority. Examples:

- stale generated proof that blocks the release contract
- local metadata/proof residue with a validator-proven repair path
- test fixture drift caused by the patch
- narrow documentation/reference update required by the behavior change

Do not silently expand into portfolio/canon mutation, paper/live/account action, config/auth/runtime mutation, cron schedule mutation, external delivery, destructive/archive action, or source-content rewrites outside the approved scope.

## Debugging Rule

When the task includes a failure, bug, blocked gate, or broken workflow, use this order:

1. Reproduce or inspect the failing artifact/command.
2. Identify the smallest owner surface responsible.
3. Patch narrowly.
4. Add or update regression coverage when the failure could recur.
5. Rerun the original failing gate.
6. Run broader closeout proof only after the targeted gate passes.
7. Report whether the bug is fixed, still blocked, or warning-grade.

Do not skip from symptom to broad cleanup without isolating cause.

## Closeout Contract

A material-task closeout should include:

- bottom-line result: complete, blocked, warning-grade, or proposal-only
- what changed and why it matters
- validation/proof rollup with pass/warning/fail counts
- trust limits and authority boundaries
- top recommendations with action class: auto-safe, review-only, owner-gated, or blocked

Never imply owner approval, capital deployment, paper/live execution, portfolio/canon mutation, external delivery, destructive cleanup, or config/runtime authority from a clean contract or validator.

## Anti-Patterns

Avoid:

- treating the user's first sentence as the full execution prompt when authority and proof need interpretation
- using validators as a substitute for mission clarity
- hiding cleanup scope until the end
- asking Randall to decide things already determined by files or standing doctrine
- over-contracting tiny tasks
- turning a clean review artifact into execution authority
- using broad web/search/tool work before local owner surfaces when the workspace owns the truth

## Minimal Examples

Material implementation:

```text
I'm treating this as a narrow validator repair. I'll inspect the failing gate and owner script, patch only the validator/test surfaces, and consider it done when the original failure, targeted regression test, changed-file router, and release contract are clean.
```

Finance approval-card prep:

```text
I'm treating this as review-only approval-card preparation, not execution. I'll refresh quote/band/stop proof, prepare exact terms if still in band, and stop before paper submit unless exact approval plus fresh WF67 guard and kill switch exist.
```

Config-sensitive task:

```text
I'm treating this as config inspection only. I'll read current config and produce a proposed diff; I will not apply runtime/channel/auth changes without explicit approval.
```
