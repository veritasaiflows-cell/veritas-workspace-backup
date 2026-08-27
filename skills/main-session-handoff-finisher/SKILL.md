---
name: "main-session-handoff-finisher"
description: "Deprecated router for handoff pickup."
---

# Main Session Handoff Finisher

Deprecated compatibility router. Do not expand this skill.

The durable handoff-pickup doctrine belongs to stronger owners:

- `project-continuity-manager` owns resumable project, lane, and handoff pickup state.
- `cron-automation-manager` owns cron design, schedule boundaries, blocked cron signal repair routing, and cron proof gates.
- `veritas-response-contract` owns Randall-facing closeouts, proof summaries, recommendation labels, and plain-English blocker wording.
- `disciplined-implementation` owns code, script, validator, release-contract, and refactor implementation work.
- `workspace-qa-pass` owns post-change QA, claim-vs-proof checks, and authority-boundary review.

## Current Posture

Use this skill only when an older reference explicitly points here. Immediately route to the canonical owner above and preserve the boundary that this router does not authorize action by itself.

Do not use this skill as the primary route for new work. Do not add new doctrine here unless the update is a narrow compatibility or deprecation repair.

## Compatibility Routing

When an old handoff references this skill:

1. Use `project-continuity-manager` for pickup notes, incomplete lane state, continuity homes, next action, and owner-gated stop lines.
2. Use `cron-automation-manager` for cron-specific blockers, freshness chains, schedule-diff gates, and cron-control proof.
3. Use `veritas-response-contract` for the final user-facing summary, proof rollup, recommendation labels, and blocker wording.
4. Use `disciplined-implementation` for any code/script/validator/control-surface implementation.
5. Use `workspace-qa-pass` before claiming a meaningful change is correct or safe.

## Preserved Stop Lines

This compatibility router does not authorize:

- inferred Randall approval
- finance canon, portfolio, cash, sizing, risk-rule, or capital mutation
- paper/live/brokerage/account action, order submit/cancel/replace, money movement, or execution approval
- external/public/customer delivery or messaging
- config, auth, credentials, network exposure, startup, service, plugin, runtime, or schedule mutation
- archive/delete/destructive cleanup
- helper spawning, write leasing, or apply actions outside the active lane contract

Stop and escalate only for external action, authority-gated action, destructive/config/auth/network/startup/service change, capital/execution approval, unclear owner intent, repeated timeout, broad unresolved diff, or material finance judgment without fresh proof.

## Compatibility Completion Contract

If this skill appears in an old checklist, complete the handoff through `project-continuity-manager` using these fields:

- owner workflow or lane
- current status
- exact next action
- proof artifact or validation command
- blocker in plain English if not complete
- whether main session can resolve it automatically
- whether Randall approval is actually required
- continuity home where the next session should resume
- stop line that must not be crossed without approval

Do not ask Randall for blockers that main session can resolve through route refresh, source-open fallback, bounded repair, QA rerun, or continuity update. Ask only for external action, authority-gated action, destructive/config/auth/network/startup/service change, capital/execution approval, or unclear owner intent.

## Removal Rule

Keep this deprecated router in place until active references are clean and Randall separately approves delete, archive, or removal. Reference cleanup alone is not removal approval.
