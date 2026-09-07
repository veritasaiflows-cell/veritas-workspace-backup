# WF72 Gate 12 Proposal Staging QA

Generated UTC: 2026-05-24T19:38:26Z

## Verdict

`canon_proposal_staging` is **not clean/apply-ready**. Current staging has 18 rows: 0 with `proposal_apply_allowed != 0`, but 8 historical applied rows have `evidence_status=unstaged` and `source_lineage_status=unverified`, and 10 pending review-only rows have unverified lineage. This is acceptable only as review-only/index/proof context.

The active SQL proof cache is not affected: it remains exactly 13 approved metadata keys, `deployment_proof_status` has 0 active rows, and this QA authorizes no SQL/cache activation or canon/apply mutation.

## Current row counts

| Count slice | Rows |
|---|---:|
| total staging rows | 18 |
| applied=1, proposal_apply_allowed=0 | 8 |
| applied=0, proposal_apply_allowed=0 | 10 |
| proposal_apply_allowed != 0 | 0 |
| evidence_status=linked | 10 |
| evidence_status=unstaged | 8 |
| source_lineage_status=unverified | 18 |
| validator_status=review_only_proposals_pending_main_session_review | 10 |
| validator_status=ok | 8 |
| status=review_only_proposals_pending_main_session_review | 10 |
| status=ok | 8 |
| requires_owner_approval=0 | 8 |
| requires_owner_approval=1 | 10 |
| forbidden true authority flags | 0 |

## Blocking findings

1. **Clean/apply-ready claim is blocked.** `proposal_apply_allowed=0` is only a stop line. It does not prove staging completeness, owner approval, canonical apply readiness, or SQL-canon activation.
2. **Owner-approval inference risk remains.** Eight pending proposal rows have `requires_owner_approval=0` while still review-only, unverified, and not apply-allowed.
3. **Validator gap remains.** `artifact_index validate` gates `proposal_apply_allowed=0`, but does not fail on mixed historical-applied rows or incomplete pending rows.

## SQL proof cache / activation impact

- Artifact DB integrity: `ok`.
- Canon cache integrity: `ok`.
- Active SQL proof metadata keys: 13.
- Boundary: `phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority`.
- Consumer scope: `dashboard_proof_metadata_only`.
- Fallback required: `true`.
- `deployment_proof_status` active rows: 0.
- Staging residue does **not** activate SQL canon and does **not** change dashboard behavior or apply authority.

## Required validator/reporting changes

- Report counts for total staging rows, applied rows, pending rows, `proposal_apply_allowed`, `requires_owner_approval`, evidence, lineage, validator, and status.
- Before any activation/apply readiness claim, fail a gate when pending rows have unverified lineage, unstaged evidence, or `requires_owner_approval != 1`.
- Segregate historical applied records from active proposal-only staging, or add an explicit record class/history flag.
- Keep wording explicit: staging is not owner approval, cron-direct apply permission, canonical mutation authority, or execution authority.

## Recommended Gate 12 closeout conditions

Gate 12 may close only as independent QA/challenge if the main closeout preserves these stop lines: review-only; no SQL/cache activation; no canon/Markdown/portfolio mutation; no owner approval inference; no cron direct apply; no dashboard action-state behavior change; no trade/account/paper/live/money/config/auth/channel/service mutation.

## Proof paths

- `tmp/veritas-artifact-index.sqlite` read-only queries: `canon_proposal_staging`, `authority_flags`.
- `tmp/veritas-canon-cache.sqlite` read-only queries: `canon_cache_meta`, `canon_cache_fields`.
- `scripts/artifact_index.py:395-416`, `scripts/artifact_index.py:1017-1063`, `scripts/artifact_index.py:1434-1560`.
- `scripts/sql_consumer_authority_guard.py:187-205`, `scripts/sql_consumer_authority_guard.py:302-305`.
