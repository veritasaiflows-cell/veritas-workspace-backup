# WF72 Phase 9 deployment/status QA challenge

Generated: 2026-05-24T18:33:00Z  
Status: review-only; no SQL/cache/canon/portfolio/dashboard behavior mutation.

## Verdict

**Block all current `*:deployment_proof_status` rows from SQL-canon proof metadata.**

No current row can safely migrate. The field name and values are action-semantic (`DEPLOYABLE NOW`, `ALMOST DEPLOYABLE`, `PROMOTION REVIEW`, `DO NOT TOUCH`), and the inspected producers/consumers use the same vocabulary for deployment-readiness/action-card behavior. Treat this family as **permanent hold for the current field/value contract** unless a future packet replaces it with neutral display-only metadata and proves full no-drift.

## Rows challenged

Source proof: `tmp/wf72-phase6-held-field-adjudication.json` + `tmp/deployment-readiness-surface.json`.

- `BRK.B:deployment_proof_status` = `DO NOT TOUCH` — repair/prework blocker
- `ETN:deployment_proof_status` = `DEPLOYABLE NOW`
- `GOOG:deployment_proof_status` = `ALMOST DEPLOYABLE`
- `GS:deployment_proof_status` = `ALMOST DEPLOYABLE`
- `JPM:deployment_proof_status` = `ALMOST DEPLOYABLE`
- `LMT:deployment_proof_status` = `DO NOT TOUCH` — repair/prework blocker
- `MSFT:deployment_proof_status` = `ALMOST DEPLOYABLE`
- `NVDA:deployment_proof_status` = `PROMOTION REVIEW`
- `VRT:deployment_proof_status` = `PROMOTION REVIEW`
- `XOM:deployment_proof_status` = `DO NOT TOUCH`

## Blocking findings

1. **Phase 6 already rejects this as low-risk metadata.**  
   `tmp/wf72-phase6-held-field-adjudication.json` classifies all 10 rows as `status_action_wording_candidate`, with `low_risk_metadata_candidate=false` and `decision=remain_held_separate_gate_shadow_only_no_activation`.

2. **The field/value contract is action language, not passive proof metadata.**  
   `deployment_proof_status` plus `DEPLOYABLE NOW` / `PROMOTION REVIEW` / `DO NOT TOUCH` can be read as deployment authority, recommendation posture, or owner-facing instruction.

3. **Producer is a deployment-readiness surface, not a neutral metadata source.**  
   `scripts/deployment_readiness_surface.py` derives `surface_state` from below-stop, repair, earnings, fallback, stale-band, and machine-state rules; it also sets `review_only_no_apply_artifact` for deployable-like states.

4. **Dashboard consumer uses the same vocabulary behaviorally.**  
   `scripts/dashboard_payload.py` maps these values into deployment summaries, dashboard states, action cards, trigger labels, and `reviewOnlyNoApplyArtifact`. That makes SQL-canon activation high-risk for dashboard/action-state drift.

5. **Preflight and guard do not authorize the family.**  
   `scripts/sql_canon_field_family_preflight.py` keeps `deployment_status_metadata` as `shadow_only_hold_for_separate_gate`; `scripts/sql_consumer_authority_guard.py` exact-approved keys include only the 13 earnings/source-freshness keys and no `*:deployment_proof_status` keys.

## Authority leakage risks

- `DEPLOYABLE NOW` / `PROMOTION REVIEW` can imply owner approval or deployability.
- `DO NOT TOUCH` is an imperative action label, not provenance metadata.
- Deployment readiness is adjacent to entry band, stop, trigger, repair, and action-card surfaces.
- SQL cache reads could be mistaken for canonical portfolio truth or recommendation authority.
- Equality/no-drift alone is insufficient while the vocabulary itself carries action meaning.

## Read-only proof performed

- Ran `python scripts\sql_canon_field_family_preflight.py` without `--write`: `status=ok`, `outputs=[]`, `hold_separate_gate_shadow_only=11`, `shadow_eligible_keys=[]`.
- Opened `tmp/veritas-canon-cache.sqlite` read-only: integrity `ok`; 13 active cache rows; no `deployment_proof_status` rows.
- Imported `build_phase4a_sql_consumer_authority_guard` read-only: approved key count 13; no deployment-status approved keys. It blocked with an empty fallback map, as expected, because fallback values were intentionally omitted.

## Required tests before any future redesign

A future redesign would need all of this before even considering activation:

- New neutral field name/vocabulary; do **not** reuse `deployment_proof_status` or action words.
- Exact-key activation packet with source artifact, owner surface, fallback path, validator, rollback/export proof, and authority boundary.
- SQL-disabled vs SQL-enabled no-drift comparison for dashboard payload, Today/action cards, deployment summary, trigger labels, ranking/order, `triggerToday`, `reviewOnlyNoApplyArtifact`, authority flags, and run summaries.
- Guard proof for exact approved keys only, fallback equality, source-hash match, `validator_status=ok`, `reconciliation_status=match`, freshness/currentness, and no forbidden authority flags.
- Negative tests for stale cache, mismatched fallback, missing source, extra unapproved rows, and action-word values.

## Recommendation

For Phase 11 readiness, mark current `deployment_proof_status` as **permanent SQL-canon hold**. If the workspace still wants status display metadata later, create a separate neutral display-status proposal and prove full dashboard no-drift before any exact-key approval.
