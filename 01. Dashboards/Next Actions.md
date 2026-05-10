# Next Actions

## Role

This dashboard answers one question:
- what should Randall or Veritas do next?

Boundary:
- immediate action queue only
- route to owner notes and proof artifacts
- do not restate the full portfolio, catalyst, or workflow registry
- do not infer trade, deployment, portfolio mutation, or owner approval authority

## Current best next actions

1. **Wait for the next ordinary WF40 security cron proof**
   - Owner surface: [[06. Playbooks/OpenClaw Parallel Pilot Queue]] and [[06. Playbooks/Cron Run Ledger]].
   - Required proof: `tmp/cyber-security-daily-audit-cron-proof.json` fresh from the scheduled run with `proof_status=ok`, `audit_stop_line=false`, and empty wrapper errors.
   - Do not close WF40 from the controlled manual rerun alone.

2. **Run WF43 durable state-history proof when ready**
   - Owner surface: [[06. Playbooks/Project Continuity/Workflow 43 - State History and Review Outcome Retention]].
   - Proof path:
     - `python -m py_compile scripts\state_history_capture.py scripts\test_state_history_capture.py`
     - `python scripts\test_state_history_capture.py`
     - `python scripts\state_history_capture.py sample --window post-close`
     - `python scripts\state_history_capture.py append --window post-close`
     - `python scripts\state_history_capture.py validate`
   - Inspect the first durable row before any consumer wiring.

3. **Use owner notes before any finance action**
   - Read [[03. Portfolio/Deployment Trigger Sheet]], [[03. Portfolio/Portfolio Snapshot]], [[03. Portfolio/Technical Entry and Invalidation Sheet]], and [[07. Risk/Risk Rules]].
   - Current owner-layer posture: JPM and ETN are deployable/conditional-add names; ETN requires band discipline; NVDA is wait/no-chase; XOM remains repair/bench.
   - This is review support only, not trade execution.

4. **Keep source trust partial / review-required visible**
   - Review `tmp/dashboard-validation.json` before trusting any generated dashboard state.
   - Current key limits: FRED-backed policy/credit inputs are incomplete without runtime FRED persistence; policy still has manual dependency; source trust is not presentation-clean.

5. **Handle WF50 cleanup only with owner approval**
   - Owner surface: [[06. Playbooks/Project Continuity/Workflow 50 - Tmp Helper Archive Cleanup]].
   - Do not promote the six `tmp/*.py` helpers as standalone scripts.
   - If approved, archive them with manifest/hashes and rerun boundary/governance/truth validators.

6. **Keep WF49 credential/runtime work separate**
   - Rotate/replace the exposed FRED key outside chat before persistent runtime configuration.
   - Do not write secrets to workspace files.
   - Do not mutate config/auth/runtime surfaces without explicit approval.

7. **Use retrieval, but verify source**
   - Use `scripts\workspace_index.py --search "<query>" --limit 10` or `scripts\artifact_index.py` to locate evidence faster.
   - Open the source Markdown/JSON before judgment, queue movement, or note mutation.

## If there are only 15 minutes

Do one of these:
- check whether WF40 scheduled proof is fresh and clean
- run the WF43 durable proof sequence through validate
- inspect `tmp/dashboard-validation.json` and name the current source-trust blockers
- classify the six tmp helpers for WF50 archive approval
- read the owner portfolio notes before considering JPM/ETN/NVDA/XOM

## If there is a full focused session

Work in this order:
1. WF40 scheduled proof review / close-or-keep-open decision
2. WF43 durable append/validate proof
3. WF50 owner-approved archive cleanup, if approved
4. WF45 artifact-index freshness/provenance follow-up
5. WF44 LMT dual-layer owner-state / technical-risk rendering follow-up
6. WF49 FRED runtime persistence after key rotation/replacement

## Anti-drift rule

If the action does not improve truth, freshness, retrieval efficiency, portfolio discipline, risk awareness, or owner-gated decision clarity, it is probably not the next action.

## Last updated

- 2026-05-09 — tightened after the current session. Reframed around WF40 scheduled proof, WF43 durable state-history proof, owner-note finance action, partial source trust, WF50 tmp-helper cleanup, and WF49 credential/runtime gating.
