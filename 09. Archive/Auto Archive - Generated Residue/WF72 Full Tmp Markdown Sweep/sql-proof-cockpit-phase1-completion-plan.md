# SQL proof cockpit Phase 1 closeout

Generated: 2026-05-23 13:44 MST

## Decision: current-window index vs SQL handoff

Responsibility split is now explicit:

- `scripts/current_window_artifact_index.py` owns the concise current-window manifest: what this run/window emitted, whether expected artifacts exist, and run-bundle completeness.
- `scripts/artifact_index.py` / SQL cockpit owns cross-window proof retrieval: ticker timelines, validator/trust state, source freshness, deployment readiness, earnings lifecycle, official-source fields, canon staging, and helper handoff lookup.

Do not expand current-window index into a broad retrieval cockpit. Keep it window-scoped and review-only. SQL is the broad proof cockpit, also review-only.

## Phase 1 definition

Phase 1 is complete when SQL can reliably answer:

1. Which generated artifact owns the proof?
2. Which ticker/workflow/source does it affect?
3. What validator/trust/authority boundary applies?
4. What canonical note or generated artifact must be opened before making a claim?
5. Are any review-only rows accidentally implying apply/trade/account/owner approval authority?

SQL Phase 1 remains derived proof/index/staging only. It is not canonical owner truth, not approval, not a mutation engine, and not trade/account/paper/live execution authority.

## Completed Phase 1 coverage

`artifact_index.py` schema v6 now indexes and validates these proof families:

- Artifact/file state: `artifact_runs`, `artifact_file_state`
- Market/router proof: `market_events`, `daily_review_objects`, `capital_recommendations`
- Current-window manifest rows: `source_artifacts` from `current-window-artifacts.json`
- Validator proof: `validator_runs`, `dashboard_findings`
- Source freshness: `source_freshness_rows`
- Deployment dashboard routing: `deployment_readiness_rows`
- Earnings lifecycle proof: `earnings_lifecycle_events`
- Official-source proof: `official_ir_capture_runs`, `official_ir_capture_fields`, `source_field_lineage`
- Canon/proposal staging stop lines: `canon_proposals`, `canon_proposal_staging`, `canon_proposal_evidence_links`
- Authority boundary checks: `authority_flags`, forbidden-true authority checks, stopline checks

## New / confirmed SQL cockpit commands

- `python scripts\artifact_index.py cockpit --limit 20`
- `python scripts\artifact_index.py ticker-cockpit <TICKER> --limit 30`
- `python scripts\artifact_index.py trust-cockpit --limit 50`
- `python scripts\artifact_index.py proof-field <TICKER> <field_name>`
- `python scripts\artifact_index.py earnings-lifecycle <TICKER>`
- `python scripts\artifact_index.py deployment-readiness <TICKER>`
- `python scripts\artifact_index.py dashboard-findings --limit 30`
- `python scripts\artifact_index.py source-freshness --limit 30`
- `python scripts\artifact_index.py stoplines --limit 50`
- `python scripts\artifact_index.py handoff --workflow <TOKEN> --limit 20`
- `python scripts\artifact_index.py validate`

## Phase 1 closeout proof

- `python -m py_compile scripts\artifact_index.py scripts\test_artifact_index.py` passed.
- `python scripts\artifact_index.py rebuild` passed.
- `python scripts\artifact_index.py validate` passed: schema v6, 27 checks / 0 failed.
- `python scripts\test_artifact_index.py` passed.
- `python scripts\artifact_index.py deployment-readiness ETN --limit 5` surfaced ETN `DEPLOYABLE NOW` / review-only dashboard-surface row.
- `python scripts\artifact_index.py earnings-lifecycle NVDA` surfaced NVDA active hold / already-closed earnings lifecycle row.
- `python scripts\artifact_index.py dashboard-findings --limit 5` surfaced the remaining suspended-weight warning as review-only.
- `python scripts\artifact_index.py source-freshness --limit 5` surfaced source freshness rows with `usable_for_canonical_mutation=0`.

## Boundary

SQL can now be the first-stop proof cockpit for generated-artifact lookup. It still must not be treated as canon, approval, apply authority, portfolio mutation authority, or execution authority. Required claim rule remains: SQL finds proof; Veritas must inspect the source artifact or canonical owner note before making content, finance, readiness, or action claims.
