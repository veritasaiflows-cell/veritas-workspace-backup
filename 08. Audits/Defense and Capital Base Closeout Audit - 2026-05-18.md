# Defense + Capital-Base Closeout Audit — 2026-05-18

## 1. Verdict: closed with follow-up

The Defense sleeve + capital-base sizing integration is coherent enough to treat the requested model-accounting closeout as boundary-safe, with minor follow-up residue.

The core integration is aligned across the proposal packet, integration summary, Portfolio Snapshot, portfolio config, pro-forma risk validation, canon drift gate, and current-window artifact index:

- LMT is no longer counted as active Defense exposure: `0% active / prior 10% suspended`.
- KTOS remains a 2% active speculative placeholder only, not a core Defense substitute.
- RTX remains 0% active / watch-only, with no replacement role.
- ITA remains 0% active review-only, with a conditional future 5% planning cap only after look-through acceptance and gates.
- Defense active exposure is 2%; pro-forma with future ITA would be 7%, both below the 25% sector cap.
- The capital-base overlay preserves the 10% cash target, treats sizing as planning-only, and defaults to fractional-share / two-tranche implementation planning.

## 2. Acceptance proof checked

Files inspected, bounded to the requested list:

- `09. Archive/Broad Workspace Archive - Owner Approved/2026-05-24-wf72-phase3-owner-review-historical-md/defense-sleeve-resolution-proposal-2026-05-18.md`
- `09. Archive/Broad Workspace Archive - Owner Approved/2026-05-24-wf72-phase3-owner-review-historical-md/capital-base-sizing-proposal-2026-05-18.md`
- `06. Playbooks/Project Continuity/Workflow 64 - Defense and Capital Base Integration Summary - 2026-05-18.md`
- `tmp/defense-capital-base-integration-proposal-2026-05-18.json`
- `03. Portfolio/Portfolio Snapshot.md`
- `tmp/portfolio-config.json`
- `tmp/portfolio-pro-forma-risk-validation.json`
- `tmp/canon-drift-freshness-gate.json`
- `tmp/current-window-artifacts.json`

Acceptance evidence observed:

- `tmp/portfolio-pro-forma-risk-validation.json`: status `ok`, `critical: 0`, `warning: 0`, and authority explicitly says `portfolio_mutation_allowed: false`, `trade_or_account_action_allowed: false`.
- `tmp/canon-drift-freshness-gate.json`: status `ok`, findings `0`, verdict `Canon drift/freshness gate clean.`
- `tmp/current-window-artifacts.json`: status `ok`, no missing required roles, no critical/unreadable roles; current-window index explicitly does not grant trade execution or paper submit/cancel authority.
- `tmp/defense-capital-base-integration-proposal-2026-05-18.json`: risk checks preserve cash at 10%, set `portfolio_mutation_allowed: false`, `trade_or_account_action_allowed: false`, `live_trading_allowed: false`, and `paper_trade_submit_cancel_allowed: false`.
- `03. Portfolio/Portfolio Snapshot.md`: the live Snapshot reflects the intended accounting in the LMT, KTOS, ITA, Defense sector, risk flags, freshness policy, and capital-base sizing overlay lines.
- `tmp/portfolio-config.json`: machine-readable config reflects LMT `weight: 0`, `suspended_legacy_weight: 10`, KTOS `weight: 2`, ITA `active_model_weight: 0`, `conditional_future_planning_cap_pct: 5`, and a planning-only capital-base sizing overlay.

## 3. Gaps/residue, if any

Minor follow-up residue only; no closeout blocker found.

1. `tmp/portfolio-config.json` has a stale-looking top-level `generated_at_utc` of `2026-05-16T06:45:54Z` while also containing May 18 Defense/capital-base sync content in `last_updated_by` and model-accounting fields. The canon drift gate is clean, so this is metadata hygiene rather than evidence of failed integration.
2. RTX wording is not perfectly normalized across surfaces. The Snapshot and integration proposal describe RTX as `0% watch/repair`; config has `active_model_weight: 0` and no replacement role, but still lists `portfolio_role: tactical`, `sizing_tier: Tier 2`, `workflow_state: WATCH`, and `repair_mode: false`. This does not widen authority because the trigger condition remains underdefined and no active model weight is present, but a future cleanup should make the RTX config vocabulary match the Snapshot/proposal more tightly.
3. `tmp/current-window-artifacts.json` shows unrelated warning-status artifacts (`board_canon_guardrail`, `finance_discrepancy_resolver`, `run_summary`). The requested closeout evidence does not show critical/unreadable roles, and the integration summary already expects warning-only risk alerts when they reflect true below-stop states.

## 4. Authority boundary check

Boundary is safe.

No inspected file grants live trade, paper order, account action, brokerage action, money movement, cash-target change, or risk-rule expansion authority for this integration.

Specific boundary evidence:

- Defense proposal: review-only, no canonical apply, no trade/account/cash movement, no queue-state changes.
- Capital-base proposal: review-only, no canonical mutation, no order staging, no paper/live trading authority.
- Integration summary: bounded workspace portfolio/canon maintenance only; no live trade, paper order, account action, brokerage action, money movement, cash-target change, risk-rule change, or execution entitlement.
- Integration JSON: `proposed_cash_target_pct` remains 10 and all trading/account/paper/live flags are false.
- Portfolio Snapshot: states draft/model weights are not live allocations and do not grant trade authority; Defense gap accounting grants no paper/live order, brokerage/account action, money movement, cash change, or execution authority.
- Current-window artifact index: main-session canon/portfolio mutation authority is present for maintenance surfaces, but trade execution and paper submit/cancel remain false.

Stop-line result: no trade/account/cash/risk-rule authority widening was found.

## 5. Immediate next recommendation

Treat the integration as closed with follow-up. The next bounded maintenance pass should normalize RTX config vocabulary and refresh the top-level `generated_at_utc` / provenance metadata in `tmp/portfolio-config.json` during the next validator-backed config sync. Do not move queue state from this audit and do not treat this audit as final closeout authority.
