# WF72 entry/stop SQL activation pilot - main integration

- Generated: 2026-05-24T21:00:15Z
- Status: `blocked_shadow_preflight_only`
- Verdict: **not activation-ready**
- Boundary: `entry_stop_reference_metadata_pilot_only_not_broad_sql_finance_canon_not_portfolio_or_trade_authority`

## Main finding

The worker completed after compaction and the artifacts are usable, but this remains a shadow/preflight pilot. QA was right to block activation: the original stale artifact-index blocker existed, and the 252-key candidate set is too broad for a first write activation. Main session refreshed the owning deployment-readiness surface and re-indexed, so the stale-index blocker is cleared, but activation remains blocked by scope and missing exact activation gates.

## Validation after main repair

- `deployment_readiness_surface.py --window post-close` wrote `tmp/deployment-readiness-surface.json` with review/trust warnings.
- `artifact_index.py incremental` indexed 1 changed/new file.
- `artifact_index.py validate` passed `28/0`, `stale=0`.
- `sql_canon_field_family_preflight.py --write` passed; active cache remains 13 keys; entry/stop candidate keys = 252; activation=false.
- `test_artifact_index.py` passed.
- `test_dashboard_acceptance.py` passed `29/29`.

## Candidate set

- Candidate rows: 42
- Candidate fields: `reference_price_low`, `reference_price_high`, `reference_invalidation_level`, `reference_level_source_timestamp`, `reference_level_source_sha256`, `reference_level_owner_source_path`
- Exact candidate key count: 252

## Recommended first slice before any activation

Use one ticker only: `NVDA` / 6 keys.

- `NVDA:reference_price_low`
- `NVDA:reference_price_high`
- `NVDA:reference_invalidation_level`
- `NVDA:reference_level_source_timestamp`
- `NVDA:reference_level_source_sha256`
- `NVDA:reference_level_owner_source_path`

This artifact does **not** approve activation. It only defines a safer first-slice candidate for owner approval and follow-on rollback/export/no-drift proof.

## Required before any write activation

- Exact owner approval naming the first-slice keys and consumer family.
- Preactivation export of cache rows and rollback SQL for the exact key slice.
- Fallback equality/no-drift proof against 03. Portfolio/Execution Board.md and generated proof artifacts.
- Source timestamp/hash/owner-source lineage proof for every activated key.
- Consumer authority guard fail-closed proof for the exact first slice.
- Protected dashboard/Today/run-summary no-drift fingerprints.
- Post-activation validation and rollback drill on a temp copy before/after real write.

## Authority boundary

No broad SQL finance-canon authority, no Markdown/canon/portfolio mutation, no owner approval inference, no proposal apply authority, no dashboard action-state behavior change, no trade/account/paper/live action, no money movement, and no credential/config/channel/service mutation.
