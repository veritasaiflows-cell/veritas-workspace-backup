---
name: "cron-automation-manager"
description: "Govern cron contracts, freshness, delivery, failure routing, and truthful fleet acceptance."
---

# Cron Automation Manager

## Production routing

- Keep deterministic command jobs model-free.
- Use ollama-cloud/glm-5.3:cloud at low reasoning only for proven compact agentTurn status, proof, digest, or quiet-output jobs.
- Use ollama-cloud/glm-5.3:cloud at medium reasoning for bounded synthesis or judgment.
- Reserve xai/grok-4.6 for Main-session high-stakes integration. Do not pin OpenAI/GPT models on cron jobs.
- Cron fallbacks inherit Main's ordered chain: GLM 5.3, Ollama Cloud Kimi K3, zAI GLM 5.3, then Opus 5. Coding work stays off cron and uses Spark 1.3 in a leased builder lane.
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

## Main-session and proof-inspection jobs

Keep main-session jobs as `systemEvent` or `script`. Do not convert them to `agentTurn`. Do not set `--timeout-seconds` on `systemEvent`.

When a weekly proof inspector needs a hard timeout, use an isolated command job: pinned CPython path, explicit timeout, review-only packet, no delivery. Do not invent a main `script` payload when the fleet has none. Keep any Main wake packet-driven and short; do not use a long Main model turn as the inspector.

## Spark canary

Spark is not the production cron default. Use meta/muse-spark-1.3-contributor only in leased coding lanes with exact paths and Main verification, not as a cron primary.

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
3. Record baseline model, posture, and duration.
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

## Model-attribution audit

When a cron/session view labels a scheduled run with a model, inspect the live job definition before attributing model use. Classify `payload.kind=command` jobs as deterministic execution; a model label may instead belong to a conditional downstream Main wake. Trace the prefilter/dispatcher launch path and its explicit model pin or inherited agent default. Report command execution, conditional model invocation, trigger condition, and unresolved handoff separately. Do not change scheduler, model, or wake policy during the audit without the required approval gate.
