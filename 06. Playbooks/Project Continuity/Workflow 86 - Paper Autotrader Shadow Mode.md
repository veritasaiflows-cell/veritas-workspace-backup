# Workflow 86 - Paper Autotrader Shadow Mode

## 2026-06-18 Plain-English Blocker Root-Cause Pass

Randall asked why NVDA was `repair_only_shadow` instead of `would_buy_shadow` and correctly identified that the prior explanation repeated surface labels without exposing the real cause.

What changed:

- `scripts/chief_intelligence_promotion_gate.py` now emits `veto_details`, `root_cause_blockers`, and `plain_english_blockers` for vetoed candidates.
- `scripts/finance_decision_factory.py` now passes those fields through, adds fallback plain-English text for non-promote verdicts such as `watch_for_reclaim_or_pullback`, and emits `promotion_gate_input_freshness` so stale gate/input mismatches are visible.
- `scripts/wf86_shadow_eligibility_validator.py` now carries root-cause and plain-English blocker fields into shadow eligibility decisions.
- `scripts/wf86_shadow_decision_ledger.py` now preserves root-cause and plain-English blocker fields when future shadow decisions are written.
- Added `scripts/test_finance_decision_factory.py`; updated focused tests for the promotion gate, WF86 shadow eligibility, and shadow decision ledger.

Current NVDA interpretation after the pass:

- NVDA was in band.
- It could not be promoted because opportunity-review debt remains: band calibration review, AI/Technology crowding/concentration, and starter-sizing review.
- The 20D/50D reclaim issue is a secondary timing/momentum caution, not the main veto.
- Fresh execution-grade quote remains a separate assisted-paper blocker.
- No paper/live execution or owner approval is inferred.

Current live artifact proof:

- `tmp/chief-intelligence-promotion-gate.json`: `status=ok`, `candidate_count=48`, `promote_for_owner_review=[]`.
- `tmp/finance-decision-factory.json`: `status=ok`, `candidates=3`, `ready=0`, `deferred=3`.
- `tmp/paper-autotrader/shadow-eligibility.json`: `status=ok`, `candidate_count=3`, `shadow_eligible_count=3`, `would_buy_shadow_tickers=["GOOG"]`, `execution_ready_count=0`.
- Persisted `tmp/paper-autotrader/shadow-decisions.json` was intentionally not rewritten to avoid adding a new non-market shadow session; persisted count remains `decision_count=24`, `clean_shadow_decision_count=9`.

Validation run:

- `python scripts\test_chief_intelligence_promotion_gate.py`
- `python scripts\test_finance_decision_factory.py`
- `python scripts\test_wf86_shadow_eligibility_validator.py`
- `python scripts\test_wf86_shadow_decision_ledger.py`
- `python -m py_compile scripts\chief_intelligence_promotion_gate.py scripts\finance_decision_factory.py scripts\wf86_shadow_eligibility_validator.py scripts\wf86_shadow_decision_ledger.py`
- `python scripts\wf86_shadow_decision_ledger.py --validate` without `--write`
- `python scripts\wf86_autotrader_readiness_packet.py --validate` without `--write`

Skill proposals created, pending review:

- `veritas-response-contract-20260618-1875da5f36`
- `cron-automation-manager-20260618-27ead27958`

Stop line:

- This pass improves explanation quality and blocker routing only.
- It does not authorize capital deployment, paper/live orders, paper submit/cancel/sell, brokerage/account action, money movement, portfolio/canon/cash/sizing/risk mutation, or owner approval inference.
