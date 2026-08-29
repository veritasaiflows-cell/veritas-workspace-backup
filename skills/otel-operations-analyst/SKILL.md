---
name: "otel-operations-analyst"
description: "Interpret local OTEL operations and route privacy-safe telemetry evidence."
---

# OTEL Operations Analyst

Use this skill when Randall asks about OpenClaw OTEL status, data-point collection, telemetry quality, collector health, OTEL-driven recommendations, cron/PM/WF74 telemetry follow-through, or privacy-safe telemetry expansion.

This skill is review-only. It interprets local telemetry/control artifacts; it does not authorize runtime mutation, collector config changes, external telemetry export, raw content capture, cron schedule edits, finance/account action, or owner approval inference.

## First Route

Use the existing OTEL control surface before broad file search:

```powershell
python scripts\otel_ops_control.py --write --write-db --multi-window --validate
```

Then read the needed packet fields from:

- `tmp\otel-ops-control.json`
- `tmp\otel-ops-window-summary.json`
- `tmp\otel-tool-workflow-metadata.json` when tool/workflow failure attribution matters
- `tmp\otel\control-loop.json` for compatibility/control-loop status

Use cron or PM packets only when the user asks for scheduled follow-through, PM impact, or escalation routing:

```powershell
python scripts\cron_control_packet.py --write --validate
python scripts\pm_control_packet.py --write --write-db --validate
python scripts\wf74_autonomy_work_router.py --write --validate
```

## Window Selection

Choose the smallest honest window:

- `1h`: after an implementation, collector restart, incident, or suspected break.
- `6h`: same-session operations review.
- `24h`: default cron/PM/control answer and daily health.
- `7d`: recurring friction, warning/error trend, drift trend, and repeated blocker analysis.
- `30d`: capacity/noise baseline only.

Do not use longer windows to hide a current failure. Do not use short windows as proof of long-run stability.

## Interpretation Rules

Report collector/runtime health from the packet, not assumption:

- collector listening state and endpoint
- collector config presence and loopback binding
- warning/error counts
- metric batch count, trace batch count, data points, spans
- drift status and daily-vs-weekly event-rate ratio
- SQLite integrity when present
- privacy scan status for tool/workflow metadata

Treat OTEL as operational evidence only. OTEL volume or span count is not proof of model quality, coding quality, finance correctness, trade readiness, deployment readiness, customer readiness, or approval authority.

## Telemetry Ownership Split

- OTEL owns local collector health, event volume and drift, and privacy-safe metadata about tool/workflow failures.
- Job-level model, token, cache, and API-equivalent cost attribution belongs to the protected dispatch/Gateway usage path: `isolated_agent_usage_metadata.py`, `implementation_token_attribution_bridge.py`, and `token_usage_ledger.py`.
- Outcome quality and acceptance history belong to their outcome ledgers. `efficiency_cohort_ledger.py` is descriptive/report-only and never changes route order or promotion.
- OTEL may link to authoritative usage or outcome records by a verified privacy-safe identity, but it must not invent job-level allocation, treat estimates as billing, or award route/efficiency credit from collector events alone.
- Efficiency review is on demand from available trustworthy evidence; no fixed cohort minimum or automatic route promotion is authorized.

Classify findings:

- `healthy`: collector OK, validation OK, zero warnings/errors, drift inside packet threshold.
- `monitor`: stale or thin signal that does not block producer chains.
- `repair`: collector not listening, packet validation fails, SQLite integrity fails, warning/error count is nonzero, drift is outside threshold, or privacy scan is not OK.
- `owner-gated`: any action requiring runtime/config/collector/channel/external-delivery/destructive/archive/capture-depth mutation.

## Privacy Boundary

Allowed metadata for interpretation:

- counts, rates, timestamps, statuses, validation results
- tool names and high-level workflow/lane/session IDs
- failure categories such as blocked/status_review/error/warning
- duration/latency/token/cost metadata only after an approved metadata-depth path and redaction proof

Never recommend or enable capture of:

- raw prompts, responses, chain-of-thought, tool payloads, request/response bodies
- secrets, headers, credentials, tokens, cookies, account identifiers
- customer/private data, brokerage/account data, portfolio execution authority
- raw file contents beyond approved local proof metadata
- external telemetry export without explicit approval and a separate security review

If the user asks for deeper telemetry, scope a proposal first. Do not mutate collector/runtime config from this skill.

## Recommendation Format

Use this response shape:

1. Bottom line: healthy, monitor, repair, or owner-gated.
2. Current facts: key packet numbers and freshness.
3. What it means: distinguish collection health from usefulness.
4. Recommendations: ordered P0/P1/P2 actions.
5. Skill/workflow follow-through: whether to create/update skills or route PM/WF74 work.
6. Boundary: state what was not authorized or changed.
7. Proof: commands or packets checked.

Keep conclusions blunt. If data is stale or thin, say so.

## Escalation And Stop Lines

Stop and ask before:

- starting/restarting the collector or changing collector/runtime config
- changing OTEL flush interval, sampling, exporter, verbosity, or capture depth
- enabling external export or channel delivery
- deleting, archiving, moving, or cleaning collector/log artifacts
- editing cron schedules or delivery modes
- capturing token/cost/latency metadata through a new runtime path
- changing finance canon/portfolio/cash/sizing/risk/account/paper/live state

If collector health is down, say the local collector appears down and identify the exact next gated command/proof path, but do not start runtime services without approval.

## Routing Recommendations Into Work

When OTEL identifies recurring friction, route it into durable work instead of leaving it only in chat:

```powershell
python scripts\otel_recommendation_closeout.py --write --write-md --validate
python scripts\wf74_autonomy_work_router.py --write --validate
python scripts\pm_implementation_job_queue.py --write --write-db --validate
python scripts\pm_control_packet.py --write --write-db --validate
```

Use Skill Workshop for durable skill changes. Do not edit live skills directly unless the user explicitly approves applying a proposal.

## Patch Validation

For OTEL script or control-surface code changes, use the smallest honest subset:

```powershell
python scripts\test_otel_ops_control.py
python scripts\otel_ops_control.py --write --write-db --multi-window --validate
python scripts\changed_file_validator_router.py --write --validate
python scripts\validator_bundle_router.py --write --validate
python scripts\implementation_release_contract.py --phase blocking --write --validate
python scripts\control_closeout_bundle.py --validation-budget shared --write --validate
```

For status-only answers, do not over-run broad validators.

## Default Recommendations

When OTEL is healthy but tool/workflow metadata shows recurring failed/blocked/status-review rows, recommend summarization and routing improvements before increasing collection volume.

Preferred next improvements:

- metadata-only failure taxonomy packet by tool/workflow/failure category
- WF74/PM routing for recurring friction and overdue recommendations
- cron reply policy: NO_REPLY when OTEL is OK/info-only; escalate only for collector down, warning/error count > 0, drift outside threshold, stale packet, privacy scan failure, or owner-gated config decision
- owner-gated token/cost/latency metadata-depth proposal only when economics or model-routing decisions require it

Do not recommend collector config changes when the packet says drift is OK and warnings/errors are zero.
