---
name: "cron-automation-manager"
description: "Govern cron contracts, freshness, delivery, failure routing, and truthful fleet acceptance."
---

# Cron Automation Manager

## Production routing

- Keep deterministic command jobs model-free.
- Use openai/gpt-5.6-luna at low reasoning only for proven compact agentTurn status, proof, digest, or quiet-output jobs.
- Use openai/gpt-5.6-terra at medium reasoning for bounded synthesis or judgment.
- Reserve openai/gpt-5.6-sol for Main's high-stakes integration.
- Use openai/gpt-5.5 as primary fallback and openai/gpt-5.4 as rollback/control.
- Treat fallback as a change in evidence source, never authority.
- Require scheduler canary, prompt-contract, output validation, and clean authority boundaries before promotion.

Model routing does not authorize creating, deleting, editing, enabling, disabling, rescheduling, or force-running jobs. Every material scheduler/payload change requires its exact gate, rollback, and post-change proof.

## Proof spine

Use:

- python scripts\cron_operator_ledger.py --write --write-md --validate
- python scripts\cron_contract_validator.py --require-contracts --fail-on-drift --write --validate
- python scripts\cron_freshness_spine.py --write --validate
- python scripts\cron_control_packet.py --write --validate

A packet generated successfully does not prove fleet health. Acceptance requires actual scheduler state, zero contract drift and prompt-integrity errors, required artifacts present and fresh, zero blocked/stale/scheduler exceptions, and no false-green transitive route.

Preserve delivery mode, session target, payload, timeout, schedule, authority boundary, and rollback in an approved patch.

Classify failures:

- Technical: scheduler, command, timeout, delivery, path, schema, prompt, or validator defect. Route to bounded repair.
- Domain: evidence freshness, market window, owner decision, or source limitation. Keep the truthful warning and route to its owner.

Quiet output is allowed only when the contract permits it and required proof passes.

## Spark canary

Spark is experimental, never the production default. Use codex/gpt-5.3-codex-spark only at xhigh for bounded script-owned canaries or QA/pre-work lanes with exact paths and Main verification.

Eligible:

- isolated jobs where deterministic scripts do the work;
- exact-command proof refresh;
- known JSON inspection;
- compact status or permitted NO_REPLY;
- no delivery, scheduler/config/auth/runtime mutation, canon mutation, external action, or owner-approval inference.

Do not use Spark for primary implementation, PM dispatcher judgment, finance synthesis, high-stakes authority interpretation, or any finance-state construction, simulated-account, request/order, brokerage/account, capital, or execution task. Those finance-state and action routes are outside the alerts-and-recommendations OS, not a Main-only fallback.

Canary steps:

1. Select one or two low-risk jobs with clean baselines.
2. Preserve schedule, target, delivery, timeout, and stop lines.
3. Record baseline model, xhigh posture, and duration.
4. Let natural runs occur; do not force market or delivery jobs for convenience.
5. Validate monitor, freshness, contract, and run history.
6. Roll back on missed warning, false silence, path hallucination, tool-loop failure, or authority drift.
7. Expand only after clean natural proof and explicit approval.

## Long work

Use checkpointed long-work status when a command can exceed normal foreground limits, including vector indexing, broad alert/recommendation proof validation, OTEL summaries, scorecards, and PM proof bundles.

Pattern:

1. Contract review/proof scope.
2. Run bounded slices.
3. Write tmp/long-work-job-status-packet.json after meaningful changes.
4. Keep exact resume commands.
5. Route resumable/warning/stale/blocked state to the active owner.
6. Never mutate schedules from a status packet.

Interpret complete+ok as usable proof; complete+warning as warning-bounded; resumable as resumable rather than failed; running as monitor/no duplicate writer; blocked as repair/decision; stale as refresh-before-claim.

## Alerts-and-recommendations finance boundary

Enabled finance jobs may use guarded SQL, explicit active-symbol quote proof, alert freshness and suppression, non-executing digests, macro/analyst evidence, SQL coverage, and the pivot validator.

No enabled job or transitive consumer may recreate retired finance-state, simulated-account, sizing, deployment, approval-card, request/order, brokerage/account, or execution artifacts. Closed-market or last-completed-session quotes are monitor-only and cannot fire fresh intraday alerts.

Do not force delivery or retired jobs to erase historical scheduler status.

## Prompt-contract lint

Cron may refresh prompt-book lint and eval-gap proof only after a separate schedule/change gate. Require objective, sources, allowed/forbidden tools, output schema, proof, stop lines, eval state, and authority boundary.

## Boundary

These rules authorize bounded model selection, status refresh, validation, and review routing only. They do not authorize scheduler expansion/mutation, external delivery, config/auth/runtime/channel/service changes, telemetry expansion, finance-state or canon mutation, capital/account/brokerage/order/execution action, destructive/archive/apply action, or owner approval inference.
