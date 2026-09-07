# WF58 Paper Dashboard / Deployment Truth Gap Analysis

Generated: 2026-05-18T03:20Z (subagent analysis)
Scope: identify minimal changes needed so WF58 deployment packets and Command Center/dashboard surfaces show the new WF67 paper pilot state and later paper performance truth without implying live trade authority.

## Bottom line

WF67 paper submit/cancel guardrails are now active enough for scoped paper pilots, but WF58/dashboard surfaces are still effectively stuck at the older WF63 readiness-only worldview. The current Command Center payload says `WF63 / NOT READY FOR PAPER ORDERS` from an older dashboard generation, while live WF67 artifacts show paper-only scoped pilots submitted and accepted/unfilled.

This is a truth-surface gap, not a live-trading authority gap. The fix should add a narrow **paper simulation / pilot telemetry** block that is explicitly non-live, non-authorizing, and separate from capital-deployment recommendation authority.

## Evidence inspected

- `06. Playbooks/Active Workflows.md`
  - Current priority is WF67.
  - WF67 status: ETN passive paper order accepted/unfilled; MSFT filled-position pilot accepted/unfilled pending market-open reconciliation.
  - Stop lines still block live trading, live endpoint/credentials, money movement, account settings mutation, replace/close/liquidate paths, inferred approval, and paper execution without exact scoped owner confirmation.
- `tmp/alpaca-paper-readiness/paper-execution-guard-validation.json`
  - `status=ok`, `ready_for_paper_submit_cancel=true`.
  - `live_trading_allowed=false`, `money_movement_allowed=false`.
  - Trade request currently points to `paper-trade-request.wf67-filled-position-001.json`.
- `tmp/alpaca-paper-readiness/paper-execution-result.json`
  - MSFT paper submit result: `status=submitted`, broker redacted status `accepted`, endpoint `https://paper-api.alpaca.markets`, `live_endpoint_detected=false`, `live_submit_allowed=false`, secrets/headers/raw response bodies not persisted.
- `tmp/alpaca-paper-readiness/paper-position-reconciliation.wf67-filled-position-001.json`
  - `status=accepted_unfilled`, matching MSFT order = 1, filled qty = 0, no matching position.
  - Hold policy: if filled, leave paper position open until Randall explicitly instructs close/cancel/sell.
- `tmp/alpaca-paper-readiness/paper-submit-reconciliation.wf67-reviewed-packet-001.json`
  - ETN paper order status `accepted`, filled qty = 0.
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
  - Capital recommendations remain review-only: top-level `trade_or_account_action_allowed=false`, `trade_execution_allowed=false`, `owner_approval_granted=false`, `apply_allowed=false`.
  - ETN source freshness is stale/review-required and `capital_action_allowed=false`, even though it was used as a paper pilot source context.
- `tmp/capital-deployment-recommendation-validation.json`
  - 4 packets, 0 critical, 0 warning.
- `tmp/deployment-readiness-surface.json`
  - Shows ETN as `DEPLOYABLE NOW`; has no paper-pilot or paper-order lifecycle awareness.
  - `system.presentation_allowed=false` because dashboard validation is stale relative to current generation.
- `tmp/dashboard-data.json`
  - `workflow_focus.top_workflow.id=WF63` and status `NOT READY FOR PAPER ORDERS` from `generated_at_utc=2026-05-16T03:44:25Z`.
  - This conflicts with current WF67 artifacts and Active Workflows.
- `scripts/dashboard_payload.py`
  - `_build_workflow_focus()` is hard-coded around WF63 readiness and reads only WF63 policy/readiness artifacts.
  - Existing acceptance tests intentionally fail if paper submit is shown as allowed, which was correct pre-WF67 but now needs a more precise distinction: **scoped WF67 paper pilot active** vs **general/autonomous paper submit allowed**.
- `scripts/daily_review_objects.py`
  - Recommendation packets have no paper-simulation/performance sidecar input.
- `scripts/capital_deployment_recommendation_validator.py`
  - Correctly blocks trade/account/live authority and forbidden execution language, but has no schema for paper-simulation telemetry.

## Current gaps

1. **Dashboard top workflow is stale/wrong for current state**
   - It still says WF63 readiness-only / not ready for paper orders.
   - It does not surface WF67 as current priority, pilot status, guard validation, or accepted/unfilled orders.

2. **Capital recommendation bundle does not preserve the paper-pilot link**
   - ETN was selected from the clean recommendation bundle for a WF67 passive paper pilot, but the recommendation packet itself has no `paper_simulation` or `pilot_telemetry` block.
   - That means later performance/outcome review will have to infer links from separate WF67 artifacts rather than a first-class trace.

3. **Deployment readiness surface does not show paper pilot overlays**
   - ETN and MSFT deployment states are still portfolio/deployment states only.
   - There is no visible indication that ETN/MSFT have paper pilot orders accepted/unfilled.
   - This is good insofar as it avoids authority leakage, but bad as a dashboard truth surface once paper pilots are running.

4. **No performance truth contract yet**
   - Current reconciliation records lifecycle truth (`accepted_unfilled`, matching orders, no positions) but there is no normalized paper-performance artifact for fill status, fill price, unrealized P/L, realized P/L, slippage versus packet close/limit, or hold/cancel state.
   - Until such an artifact exists, do not claim paper performance beyond order lifecycle.

5. **Validator/test posture is pre-WF67**
   - Dashboard tests currently enforce `paper_submit_allowed=false` and reject active paper language broadly.
   - That should remain true for general/autonomous paper submit, but tests need a new safe path for `paper_simulation.status = scoped_pilot_active|accepted_unfilled|filled_monitoring` with all live/account authority false.

## Minimal recommended changes

### 1. Add a normalized WF67 paper pilot status artifact

Create a small read-only aggregator, e.g.:

- Script: `scripts/paper_pilot_status_surface.py`
- Output: `tmp/alpaca-paper-readiness/paper-pilot-status-surface.json`

Inputs should be only redacted/validator artifacts:
- `paper-execution-guard-validation.json`
- `wf63-readiness-report.json`
- `paper-execution-result.json`
- `paper-submit-reconciliation.wf67-reviewed-packet-001.json`
- `paper-position-reconciliation.wf67-filled-position-001.json`
- optionally any future `paper-position-reconciliation.*.json` / `paper-pilot-reconciliation.*.json`

Minimum output shape:

```json
{
  "schema_version": 1,
  "generated_at_utc": "...",
  "status": "ok",
  "workflow": "WF67 - Alpaca Paper Execution Guardrail",
  "authority": {
    "paper_simulation_only": true,
    "scoped_paper_submit_cancel_allowed": true,
    "general_autonomous_paper_submit_allowed": false,
    "live_trading_allowed": false,
    "live_endpoint_allowed": false,
    "money_movement_allowed": false,
    "account_settings_mutation_allowed": false,
    "owner_approval_inferred": false,
    "promotion_to_live_allowed": false
  },
  "pilots": [
    {
      "pilot_id": "wf67-reviewed-packet-001",
      "ticker": "ETN",
      "side": "buy",
      "qty": 1,
      "order_type": "limit",
      "limit_price": 364.49,
      "status": "accepted_unfilled",
      "filled_qty": 0,
      "position_observed": false,
      "source_recommendation": "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json",
      "source_proposal_id": "sunday:ETN:capital-deployment-review:2026-05-17",
      "performance_state": "not_started_unfilled",
      "paper_pnl_available": false
    }
  ],
  "stop_lines": [
    "Paper simulation only; no live trade/account/money movement authority.",
    "No owner approval inferred from recommendation packets, validation, or paper fills.",
    "No close/cancel/sell unless Randall explicitly instructs inside WF67 guardrails."
  ]
}
```

### 2. Update `dashboard_payload.py` workflow focus from WF63-only to WF67-aware

Minimal behavior:
- If WF67 guard validation exists and is `ok`, show top workflow as `WF67 - Alpaca Paper Execution Guardrail`.
- Display status as something like: `Scoped paper pilot active — paper simulation only; live trading blocked`.
- Keep `live_submit_allowed=false`, `money_movement_allowed=false`, `owner_approval_inferred=false`.
- Rename or add a field so consumers do not confuse general permission with scoped pilot state:
  - keep `paper_submit_allowed=false` for general/autonomous submit compatibility, or rename in new block as `general_autonomous_paper_submit_allowed=false`.
  - add `scoped_paper_pilot_active=true` and `scoped_paper_submit_cancel_guard_ready=true` only when WF67 validation is clean.
- Include `paper_pilot_status` summary from the new status artifact.

### 3. Add dashboard validation rules for the new safe language

Update acceptance/validator tests so they still reject:
- `paper trading active` if unqualified.
- `paper orders enabled` as general authority.
- any live submit/money movement/account mutation language.
- any claim that paper results imply live approval.

Allow only bounded phrases such as:
- `scoped paper pilot active`
- `paper simulation only`
- `accepted/unfilled`
- `WF67 guardrails clean`

Required assertions:
- If `scoped_paper_pilot_active=true`, then all of these must be false:
  - `live_submit_allowed`
  - `live_trading_allowed`
  - `money_movement_allowed`
  - `account_settings_mutation_allowed`
  - `owner_approval_inferred`
  - `promotion_to_live_allowed`
- If any paper pilot has `filled_qty > 0`, dashboard must show `paper position monitoring only`, not deploy/live/approved.

### 4. Add a paper-simulation sidecar to capital recommendation packets, not authority fields

Do **not** change `trade_or_account_action_allowed`, `trade_execution_allowed`, `owner_approval_granted`, `apply_allowed`, or `portfolio_mutation_allowed`.

Instead add optional read-only sidecar fields in generated proposal packets when a pilot link exists:

```json
"paper_simulation": {
  "status": "accepted_unfilled",
  "workflow": "WF67",
  "pilot_id": "wf67-reviewed-packet-001",
  "source_artifacts": ["tmp/alpaca-paper-readiness/paper-pilot-status-surface.json"],
  "paper_only": true,
  "live_authority_allowed": false,
  "owner_approval_inferred": false,
  "performance_state": "not_started_unfilled",
  "paper_pnl_available": false,
  "note": "Paper simulation telemetry only; does not alter recommendation authority or live deployment state."
}
```

Validator change: allow this block only if it preserves all false authority flags and does not contain forbidden live/execution/approval language. It should warn/critical if paper telemetry claims live authority or owner approval.

### 5. Keep deployment readiness states pure; add paper overlay only

Do not convert ETN/MSFT deployment states because of paper order lifecycle.

Add a non-authorizing overlay per ticker:

```json
"paper_simulation_overlay": {
  "has_active_pilot": true,
  "pilot_status": "accepted_unfilled",
  "paper_position_observed": false,
  "paper_performance_available": false,
  "authority_boundary": "Paper pilot lifecycle only; does not change deployment state or live authority."
}
```

This prevents paper fills from making a ticker look more deployable or approved.

## Recommended validation gates

After implementing the minimal changes, run:

1. `python -m py_compile scripts\paper_pilot_status_surface.py scripts\dashboard_payload.py scripts\deployment_readiness_surface.py scripts\daily_review_objects.py scripts\capital_deployment_recommendation_validator.py scripts\test_dashboard_acceptance.py`
2. `python scripts\paper_pilot_status_surface.py --write`
3. `python scripts\alpaca_paper_execution_guard_validator.py --write --trade-request tmp\alpaca-paper-readiness\paper-trade-request.wf67-filled-position-001.json`
4. `python scripts\deployment_readiness_surface.py --window post-close`
5. `python scripts\daily_review_objects.py --window sunday`
6. `python scripts\portfolio_mutation_proposal_generator.py --window sunday` (or current chain equivalent)
7. `python scripts\capital_deployment_recommendation_validator.py tmp\portfolio-mutation-proposals\current-capital-deployment-recommendations.json`
8. `python scripts\generate_dashboard.py`
9. `python scripts\validate_dashboard_state.py --write`
10. `python scripts\test_dashboard_acceptance.py`

Acceptance proof should show:
- Dashboard top workflow no longer says stale WF63 `NOT READY FOR PAPER ORDERS` when WF67 pilots are active.
- WF67 pilot lifecycle appears as paper simulation only.
- ETN/MSFT paper status is visible without changing deployment state or recommendation authority.
- All live/account/money-movement/approval-inference flags remain false.
- Capital recommendation validator remains 0 critical / 0 warning.

## Stop lines

- Do not add live endpoint, live credentials, live order, account settings, money movement, replace/close/liquidate, or promotion-to-live behavior.
- Do not let a clean recommendation packet, dashboard state, validator pass, or paper fill imply owner approval.
- Do not mutate canonical portfolio notes from this dashboard/paper telemetry pass.
- Do not report paper P/L until a read-only paper performance artifact exists and validates against redacted paper account/position data.
