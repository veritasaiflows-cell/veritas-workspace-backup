# Retail-Grade Truth Routing System

## Status - 2026-06-18

Randall approved resuming `WF-RETAIL-ROUTING` on 2026-06-18 for internal answer-safety infrastructure.

Current posture:
- Internal retail truth routing is resumed for source-open, review-only answer-path safety.
- Customer-safe output remains blocked.
- No SQL-first promotion, SQL writes/imports, customer/external output, canon/portfolio mutation, paper/live/account action, Python fallback retirement, cron mutation, or approval inference.

## Built Surfaces

- `scripts/retail_truth_routing_contract.py`
- `scripts/retail_answer_harness.py`
- `scripts/retail_automation_control_plane.py`
- `scripts/retail_customer_output_decision_packet.py`

## Proof Artifacts

- `tmp/retail-truth-routing-contract.json`
- `tmp/retail-answer-harness.json`
- `tmp/retail-automation-control-plane.json`
- `tmp/retail-customer-output-decision-packet.json`

## Current Truth

- Route contract: 8 routes, source-open gates enforced, fallback-decay gates enforced.
- Answer harness: clean and seeded-bad cases validate; 14/14 unsafe prompts block across 11/11 explicit categories.
- Automation control plane: operator visibility, SQL support health, customer-safety gate, seeded-bad coverage, demo cards, and customer-output decision are visible in one proof packet.
- Customer-output decision packet: `internal_answer_safety_ready=true`, `customer_output_allowed=false`, `decision=customer_output_blocked`.

## Command Center Visibility - 2026-06-18

- `tmp/veritas-command-center-compact.html` now renders a first-screen Retail Truth Routing Gate.
- `tmp/veritas-command-center-compact-reader.json` now exposes `retail_truth_routing` with status, decision, blocker list, unsafe prompt coverage, unsafe category coverage, proof artifacts, and review-only authority flags.
- `apps/pm-control-cockpit/public/app.js` Retail tab now shows the customer-output decision, internal answer-safety readiness, blocked customer-output state, blocker list, and per-card unsafe category labels.
- `deliverables_publisher.py` now publishes retail proof JSONs under `10. Deliverables/Command Center/`.

Current visible retail gate:
- Retail routing: `ok`
- Output decision: `customer_output_blocked`
- Internal answer-safety: `ready`
- Customer output: `blocked`
- Unsafe prompts: `14/14` blocked
- Unsafe categories: `11/11` covered

## Customer Output Gates

Customer output remains blocked until every gate has a separate approved artifact:
- Randall exact customer-output approval
- source licensing review
- privacy/customer-data policy
- legal/compliance review
- approved disclaimer language
- personalization/suitability boundary
- external delivery/channel approval
- security/runtime exposure approval

## Validator Commands

```powershell
python scripts\retail_truth_routing_contract.py --write --validate
python scripts\retail_answer_harness.py --write --validate
python scripts\retail_customer_output_decision_packet.py --write --validate
python scripts\retail_automation_control_plane.py --write --validate
python scripts\dashboard_compact_shell.py --write --validate
python scripts\dashboard_compact_shell_acceptance.py --write --validate
python scripts\deliverables_publisher.py --write --validate
python scripts\workflow_routing_index.py --write --write-db --validate
```

## Stop Lines

- No customer/public/external output.
- No real customer data, PII, account, suitability, tax, retirement, or brokerage data.
- No SQL-first answer promotion, SQL writes/imports, or SQL source-of-truth promotion.
- No canon/portfolio mutation.
- No paper/live/account action.
- No brokerage/account action.
- No money movement.
- No Python fallback retirement.
- No cron/config/runtime/channel mutation without separate approval.
- No owner approval inference.
