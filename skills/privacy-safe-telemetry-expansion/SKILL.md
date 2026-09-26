---
name: "privacy-safe-telemetry-expansion"
description: "Scope owner-gated metadata-only OTEL field-depth expansion."
---

# Privacy-Safe Telemetry Expansion

Use this skill only when Randall asks to scope, review, or prepare deeper telemetry metadata collection beyond the current local OTEL control packets.

This skill is owner-gated. It may prepare a proposal, diff packet, privacy review, validation plan, and rollback plan. It must not apply runtime, collector, exporter, sampling, flush-interval, capture-depth, or external-export changes without explicit approval.

## Allowed Expansion Targets

Allowed only after explicit approval and redaction proof:

- model name and provider
- token counts
- estimated cost
- latency and duration buckets
- status and error category
- workflow, lane, session, and tool metadata IDs
- validation result counts
- redaction/privacy scan proof

## Forbidden Capture

Never capture or recommend capture of:

- raw prompts, responses, hidden reasoning, system prompts, or conversation content
- raw tool payloads, request/response bodies, screenshots, file contents, or logs containing content
- secrets, headers, credentials, tokens, cookies, auth material, account identifiers
- brokerage/account data or execution instructions
- customer/private/suitability/tax/retirement data
- anything exported externally without a separate security review and explicit approval

## Scoping Procedure

1. Establish current state through [OTEL Operations Analyst's first route](../otel-operations-analyst/SKILL.md#first-route), then check its [telemetry ownership split](../otel-operations-analyst/SKILL.md#telemetry-ownership-split). Existing dispatch/Gateway usage or outcome records may already answer the question; deeper collector capture must not duplicate or invent job-level attribution. Record the current state and the actual evidence gap before proposing new capture.

2. Identify the exact decision that deeper metadata would support:

- model-routing economics
- tool latency triage
- recurring failure taxonomy
- cost/noise baseline
- PM/WF74 routing quality

3. Write a narrow proposal with:

- fields to collect
- fields explicitly forbidden
- source/runtime surface touched
- storage path and retention plan
- redaction and privacy scan
- rollback plan
- validation commands
- owner approval required before apply

4. Route the proposal through Skill Workshop or an owner-gated implementation packet. Keep it pending unless Randall explicitly approves apply.

## Validation Plan

A privacy-safe telemetry-depth proposal should include the smallest honest subset:

```powershell
python scripts\otel_ops_control.py --write --write-db --multi-window --validate
python scripts\wf74_learning_loop_eval_harness.py --write --validate
python scripts\changed_file_validator_router.py --write --validate
python scripts\implementation_release_contract.py --phase blocking --write --validate
python scripts\control_closeout_bundle.py --validation-budget shared --write --validate
```

If runtime/collector config changes are approved and applied, closeout must include a fresh `intraday_1h` OTEL window check and rollback proof.

## Stop Lines

Stop and ask when the proposal would touch runtime config, collector config, exporters, external delivery, auth/credentials, network exposure, startup/service behavior, destructive cleanup, finance canon/portfolio/cash/sizing/risk/account state, paper/live execution, brokerage/account state, customer/public data, or owner approval inference.

A clean telemetry-expansion proposal means the scope is reviewable. It does not authorize implementation until Randall approves the exact change.
