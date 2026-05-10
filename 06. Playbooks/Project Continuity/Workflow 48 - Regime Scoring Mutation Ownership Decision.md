# Workflow 48 - Regime Scoring Mutation Ownership Decision

## Objective
- Decide and encode whether `scripts/regime_scoring_refresh.py` is allowed to directly mutate `02. Markets/Regime Scoring Matrix.md`, or whether that output should become generated/review-only.

## Current State
- Closed 2026-05-09 after Randall approved the ownership decision and proof passed.
- `02. Markets/Regime Scoring Matrix.md` is a **controlled machine-companion ranking note**, not final canonical deployment truth.
- `regime_scoring_refresh.py` may keep writing both `tmp/regime-scores.json` and bounded scoring/ranking/freshness blocks in `02. Markets/Regime Scoring Matrix.md`.
- Final action authority remains with the Deployment Trigger Sheet, Portfolio Snapshot, Risk Rules, and explicit owner approval.

## Last Meaningful Progress
- Ownership decision landed and was encoded in the note, script docstring/constants, script README, JSON authority object, and targeted authority test.
- Proof passed: `python -m py_compile scripts\regime_scoring_refresh.py scripts\test_regime_scoring_authority.py`; `python scripts\regime_scoring_refresh.py`; `python scripts\test_regime_scoring_authority.py`; `python scripts\positioning_ranking_refresh.py`; `python scripts\run_finance_refresh_chain.py post-close`.

## Outstanding
- Keep any future decision-grade scoring upgrade separate from this ownership cleanup; do not use this approval to add execution, portfolio mutation, or owner-approval inference.

## Blockers / Trust Gaps
- Do not widen bounded machine-companion note mutation into general canonical note mutation.
- Do not let regime scores become a second portfolio/deployment truth source.
- Do not treat high numeric score as deployable-now authority.

## Next Action
- No WF48 action pending. Continue with WF49 only if Randall is ready to handle credential/runtime work, or return to WF40 scheduled-repeat proof monitoring.

## Key Files
- `scripts/regime_scoring_refresh.py`
- `02. Markets/Regime Scoring Matrix.md`
- `tmp/regime-scores.json`
- `scripts/run_finance_refresh_chain.py`
- `scripts/chain_manifest.py`

## Acceptance Gate
- Ownership decision is recorded in the workflow note and relevant script/playbook comments.
- Script behavior matches the decision.
- `tmp/regime-scores.json` includes explicit authority fields denying deployment truth, portfolio/deployment mutation, trade execution, and owner approval inference.
- `02. Markets/Regime Scoring Matrix.md` removes the old canonical-ranking claim and names the final authority surfaces.
- Targeted authority test and finance-chain-adjacent proof pass.
- The exception is explicit and bounded.

## Automation / Refresh Path
- Approved and proven as bounded machine-companion note mutation only.
