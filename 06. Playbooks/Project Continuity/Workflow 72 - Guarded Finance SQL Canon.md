# Workflow 72 — Guarded Finance SQL Canon

## Status

Active support lane for the alerts-and-recommendations OS. The SQL store is an internal, guarded evidence surface; it is not an action, account, approval, or execution system.

## Objective

Keep `state/finance/finance-canon.sqlite` truthful, provenance-backed, fast, and safe for bounded alert and recommendation reads.

## Canonical Scope

WF72 may represent:

- security identity and coverage metadata;
- alert bands and invalidation thresholds;
- thesis/evidence freshness and source lineage;
- recommendation-review scope and uncertainty;
- consumer lifecycle and migration proof.

The database must not maintain holdings, capital structure for Randall, order state, simulated account state, or execution readiness.

## Current Route

1. `python scripts\finance_sql_canon_access.py --write --validate`
2. `python scripts\alerts_os_pivot_validator.py --write --validate`
3. `python scripts\workflow_router.py WF72 --answer all --write-capsules --validate`

Primary proof: `tmp/finance-sql-canon-access-validation.json`.

## Migration Contract

- Preserve every existing numeric alert level and confidence value exactly.
- Require an immutable, content-addressed baseline for active reference lineage.
- Require exact file existence and SHA-256 matches for active provenance.
- Retire legacy consumers through an explicit content-addressed manifest.
- Preserve audit history and negative authority flags.
- Fail closed and restore the verified pre-migration backup if post-commit validation fails.
- An isolated smoke test must receive explicit database, root, output, baseline, manifest, and backup paths; no function may retain the live database through a bound default.

## Resume State

Cutover completed under Randall's 2026-08-29 alerts-OS gate after the isolation regression and two independent reviews passed on pinned source hashes. The migration preserved all 200 numeric alert rows with projection SHA-256 `4b30ac2db897512d661767b5ea55842c7c41916ac48375b7244a76b3ab750996`, retired 300 tier-routing rows and 1,200 tier-lineage rows, retired the remaining 153 legacy consumers, and pinned active reference lineage to the immutable baseline at `state/finance/baselines/alert-reference-levels-v1-bb11218340670d8b6a59cc9bcf334ec932c0dda99b84ae3fafb4ae7ca103e007.json`. The consumer retirement manifest is `state/finance/retirement-manifests/alerts-os-consumer-retirement-v1-666e68f4fed77e5242e56bc7e12b97963aa80b9178657d33ff7e4f3d4d524d84.json`.

The earlier smoke-test isolation defect remains part of the audit record: it was caught, writes were frozen, the logical pre-migration state was restored through SQLite backup semantics, and exact before/after backups were verified. Current integrity is `ok`, foreign-key issues are zero, guarded SQL validation is green, the alerts-OS pivot validator is green with zero warnings, and all four direct chain windows pass.

## Acceptance

- SQLite integrity is `ok`; foreign-key issues are zero.
- The numeric projection hash is unchanged from the verified pre-migration snapshot.
- Active reference and evidence lineage resolves to existing exact-hash artifacts.
- Legacy routing/state rows are retired according to the frozen manifest.
- Every answer scope is recommendation review only; all action-authority flags are false.
- The guarded access validator and alerts-OS pivot validator both pass.

## Stop Lines

- No unreviewed schema or canon write.
- No fabricated provenance or changed alert value to make validation pass.
- No capital, account, order, money-movement, or execution authority.
- No archive/delete or fallback retirement without its exact lifecycle gate.

Last updated: 2026-08-29 22:02 Phoenix / 2026-08-30 05:02 UTC.
