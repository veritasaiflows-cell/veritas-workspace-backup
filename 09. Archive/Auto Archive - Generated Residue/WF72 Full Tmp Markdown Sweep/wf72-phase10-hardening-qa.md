# WF72 Phase 10 hardening / QA

- Generated: `2026-05-24T18:47:00Z`
- Verdict: **blocked before Phase 11 full-activation readiness**
- Boundary: review-only; no SQL/cache writes, no Markdown/canon/portfolio mutation, no dashboard behavior change, no cron-direct apply, no owner approval inference, no trade/account/paper/live/money/config/auth/channel/service mutation.

## Practical verdict

Do **not** proceed to Phase 11 until the high-risk family taxonomy is explicit and validator-backed. The current live SQL-canon cache remains bounded to the 13 approved proof-metadata keys, and read-only checks found zero forbidden authority flags and zero `proposal_apply_allowed` staging rows. The blocker is not current cache leakage; it is that the Phase 10 taxonomy/readiness layer is still too broad and internally inconsistent for a "full activation" packet.

## Read-only proof

| Check | Result |
|---|---:|
| Active canon cache rows | 13 |
| Forbidden authority flags in artifact index | 0 |
| `canon_proposal_staging.proposal_apply_allowed != 0` | 0 |
| Staged proposal rows | 18 |
| Preflight active rows | 13 |
| Preflight held rows | 11 |
| Preflight eligible shadow rows | 0 |

Active cache keys are exactly the Phase 7 set: NVDA earnings lifecycle metadata plus non-portfolio source freshness metadata for breadth, credit, deployment, earnings, fundamental_ir, fundamentals, market, policy, and technical.

Held rows are `portfolio:source_freshness_classification` plus 10 `deployment_proof_status` rows.

## Blocking findings

### P10-BLOCK-001 — Missing enforceable high-risk taxonomy

Phase 10 asks for a higher-risk family taxonomy, but the current protocol only classifies three families: earnings lifecycle metadata, source freshness metadata, and deployment status metadata.

Missing as enforceable per-family rows: entry/stop, sizing/sleeve/cash/weight, sector posture, risk-rule, trade/account/paper/live execution, credential/config, and owner-approval-state classes.

Proof:
- `tmp/wf72-phases-8-11-full-activation-readiness-plan.json`
- `tmp/sql-canon-field-family-migration-protocol.json`
- `tmp/sql-canon-field-registry.json`

Smallest repair: create a Phase 10 taxonomy matrix with `authority_class`, canonical owner, allowed output type, never-SQL/proposal-only/future-candidate route, exact validator, stop lines, and downstream consumer prohibition for every high-risk family.

### P10-BLOCK-002 — Deployment status protocol conflicts with Phase 9 closeout

`deployment_proof_status` still appears as an allowed field in the migration protocol, but Phase 9 closed the current field/value set as **permanent hold / do not migrate to SQL-canon**.

Proof:
- `tmp/sql-canon-field-family-migration-protocol.json`
- `tmp/wf72-phase9-closeout.json`
- `tmp/sql-canon-low-risk-field-family-preflight.json`

Smallest repair: mark current `deployment_proof_status` as rejected/permanent-hold. Any future reconsideration should require a renamed neutral display-only field with non-action vocabulary and new no-drift approval.

### P10-BLOCK-003 — Forbidden-family classifier is incomplete

Exact-key allowlists protect the current cache, but the family-term classifiers are not complete enough for Phase 10/11 expansion review. Guard/preflight term lists miss terms such as stop, sector, config, owner approval/approval, and some execution/entitlement aliases.

Proof:
- `scripts/sql_consumer_authority_guard.py`
- `scripts/sql_canon_field_family_preflight.py`
- `tmp/wf72-phases-8-11-full-activation-readiness-plan.json`

Smallest repair: replace ad hoc term screens with a taxonomy-driven denylist/classifier that fails closed unless a field has an explicit route.

### P10-BLOCK-004 — Proposal-only staging quality is not yet a readiness gate

Read-only SQL showed 18 staged proposal rows. Apply is safely blocked (`proposal_apply_allowed=0`), but staging quality is mixed:

- 10 rows: `validator_status=review_only_proposals_pending_main_session_review`, `source_lineage_status=unverified`
- 8 rows: `validator_status=ok`, `evidence_status=unstaged`, `source_lineage_status=unverified`

`artifact_index validate` proves apply is zero, but it does not prove staged proposal rows are complete enough for activation/apply readiness claims.

Proof:
- `scripts/artifact_index.py`
- `tmp/veritas-artifact-index.sqlite` read-only query

Smallest repair: Phase 11 must gate proposal-only staging separately: `proposal_apply_allowed=0`, `applied=0`, `requires_owner_approval=1`, evidence/lineage/validator state explicitly interpreted, and incomplete rows cannot support activation/apply claims.

## Should-fix-now findings

### P10-SHOULD-001 — Dashboard wording leakage: `sqlIsCanon=true`

`dashboard_payload.py` sets `sqlIsCanon=true` after the guard passes. Nearby flags correctly say metadata-only and no mutation/action authority, but the field name can still be read as "SQL row is canonical truth."

Proof:
- `scripts/dashboard_payload.py` around `_load_phase4a_sql_canon_metadata`
- `scripts/dashboard_payload.py` `_sql_canon_proof_for_ticker`

Repair: rename/supplement with `sqlReadAllowed` or `proofMetadataAuthority`, and keep canonical-note/portfolio truth semantics explicitly false.

### P10-SHOULD-002 — Registry not reconciled to Phase 9

The field registry still includes `deployment_proof_status` as a review-surface field without reflecting the newer permanent-hold decision.

Proof:
- `tmp/sql-canon-field-registry.json`
- `tmp/wf72-phase9-closeout.json`

Repair: update registry status for current `deployment_proof_status` to rejected/permanent-hold, with future reconsideration requiring neutral replacement vocabulary.

## Recommended class boundaries

Never SQL-canon:
- owner approval / entitlement
- trade/account/paper/live execution and order state
- credential/config/auth/channel/service metadata
- cash movement or account authority
- risk-rule execution/enforcement permission fields
- current `deployment_proof_status` action-state wording/value set

Proposal-only or exact gated workspace-maintenance apply:
- entry bands, stops, target prices
- sizing, sleeve, weights, sector posture
- canonical portfolio note maintenance categories

Future exact-key candidates only:
- non-portfolio source freshness metadata
- earnings lifecycle proof metadata with fallback equality/source hash/no-drift proof
- renamed neutral display-only status metadata after action vocabulary is removed

## Phase 11 blocker list

- Need explicit Phase 10 taxonomy matrix.
- Need protocol/registry alignment with Phase 8 and Phase 9 closeouts.
- Need expanded fail-closed family classifier driven by taxonomy.
- Need proposal-only staging quality gates.
- Need dashboard wording cleanup for `sqlIsCanon`.
- Phase 11 language must say active cache is exact 13 keys only; no unbounded migration, no cron-direct apply, no portfolio/canon mutation, and no execution authority.
