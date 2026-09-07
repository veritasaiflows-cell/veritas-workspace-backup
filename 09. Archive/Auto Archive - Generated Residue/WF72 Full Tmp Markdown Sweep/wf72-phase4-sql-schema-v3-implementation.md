# WF72 Phase 4 SQL schema-v3 implementation

Status: **ok**  
Generated: 2026-05-22T07:46:43Z

## What changed
- Extended existing `scripts/artifact_index.py` and existing `tmp/veritas-artifact-index.sqlite`; no new database family was created.
- Bumped artifact index schema to v3.
- Indexed `tmp/official-ir-captures/*.json` into official-source proof tables.
- Added explicit source-field lineage rows using official excerpt/source metadata.
- Added exact canon proposal staging/evidence-link tables for review-only proposal lookup.
- Added read-only CLI queries: `official-ir`, `lineage`, and `canon-stage`.

## Authority boundary
SQL remains derived proof/index/staging only. It is **not** canon truth, not a canon apply engine, not portfolio mutation authority, not paper/live execution authority, and not owner approval.

## Counts after rebuild
| Row type | Count |
|---|---:|
| source files | 35 |
| artifact runs | 35 |
| market events | 187 |
| daily review objects | 74 |
| capital recommendations | 19 |
| source artifacts | 111 |
| validator runs | 7 |
| authority flags | 339 |
| canon proposals | 18 |
| Today decision items | 7 |
| official IR capture runs | 20 |
| official IR capture fields | 140 |
| source field lineage rows | 140 |
| canon proposal staging rows | 18 |
| canon proposal evidence links | 28 |

## Proof
- `python -m py_compile scripts\artifact_index.py scripts\test_artifact_index.py` — ok
- `python scripts\artifact_index.py rebuild` — ok
- `python scripts\artifact_index.py official-ir --limit 3` — ok
- `python scripts\artifact_index.py canon-stage --limit 3` — ok
- `python scripts\test_artifact_index.py` — `artifact_index_tests_passed`

## Residue
- Official IR coverage count remains 20; long-tail captures are still pending after more helper consolidation.
- Canon staging is intentionally review/index support only; `proposal_apply_allowed` stays false.
