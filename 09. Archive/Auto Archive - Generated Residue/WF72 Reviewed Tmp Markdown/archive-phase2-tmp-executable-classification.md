# WF72 Phase 2 Tmp Executable Helper Classification

Status: **classification only / no moves / no deletes**  
Scope: `tmp/implement_cron_broadening.py`, `tmp/sql-canon-cache-rollback-phase3c.py`, `tmp/wf72_make_phases_8_11_plan.py`

## Verdict

| Helper | Recommendation | Why |
|---|---|---|
| `tmp/implement_cron_broadening.py` | **Archive after explicit owner approval** | One-off implementation helper. Durable results now live in `scripts/chain_manifest.py`, `scripts/cron_authority_matrix_validator.py`, `tmp/cron-automation-authority-contract.*`, WF76 continuity, and Active Workflows. Helper references are historical/proof or archive-suggestion only. |
| `tmp/sql-canon-cache-rollback-phase3c.py` | **Retain now; promote later only via exact implementation pass** | Live/proof-critical rollback helper referenced by `scripts/artifact_index.py`, `scripts/test_artifact_index.py`, SQL rollback/export artifacts, and Phase 3F/4 proof. Not archive-ready. |
| `tmp/wf72_make_phases_8_11_plan.py` | **Archive after explicit owner approval** | One-off plan generator. The generated `tmp/wf72-phases-8-11-full-activation-readiness-plan.json/.md` remains referenced by later WF72 QA/proof, but the generator itself is only historical/proof residue. |

## Reference posture

- Reference scan used fixed-string `rg` across helper names and key output names.
- `implement_cron_broadening.py`: no live dependency on the helper basename found outside suggestions/prework/history. Preserve its outputs; archive only the helper.
- `sql-canon-cache-rollback-phase3c.py`: live dependency exists in `scripts/artifact_index.py` and `scripts/test_artifact_index.py`; many SQL rollback/export artifacts preserve it as rollback path/provenance. **Do not archive in Phase 2.**
- `wf72_make_phases_8_11_plan.py`: no live script/validator dependency on the helper basename found; generated plan artifacts remain live proof and must stay put.

## Proposed destinations if approved

- `tmp/implement_cron_broadening.py` -> `09. Archive/tmp-python-helpers - Archived/2026-05-24-wf72-phase2-owner-approved/implement_cron_broadening.py`
- `tmp/wf72_make_phases_8_11_plan.py` -> `09. Archive/tmp-python-helpers - Archived/2026-05-24-wf72-phase2-owner-approved/wf72_make_phases_8_11_plan.py`
- `tmp/sql-canon-cache-rollback-phase3c.py` -> **no archive destination; retain.** Future promotion candidate: `scripts/sql_canon_cache_rollback_phase3c.py`, but only with compatibility/reference updates and rollback proof.

## Required gates before any archive apply

1. Re-run fixed-string reference scan immediately before apply.
2. Manifest source/destination SHA-256, size, mtime, and `delete_count=0`.
3. Move only explicitly approved archive-ready helpers.
4. Verify source absent, destination present, hash unchanged.
5. Run:
   - `python scripts/artifact_index.py validate`
   - `python scripts/dashboard_truth_lint.py`
   - `python scripts/workspace_boundary_check.py`
6. Rollback route: move archived helper back to original `tmp/` path and verify original SHA-256.

## Validation performed

- JSON parse passed: `python -m json.tool tmp\archive-phase2-tmp-executable-classification.json`
- Candidate syntax passed: `python -m py_compile tmp\implement_cron_broadening.py tmp\sql-canon-cache-rollback-phase3c.py tmp\wf72_make_phases_8_11_plan.py`
- Validation sidecar: `tmp/archive-phase2-tmp-executable-classification.validation.tmp`

## Stop lines

- No deletes.
- Do not move `tmp/sql-canon-cache-rollback-phase3c.py` in Phase 2.
- Do not move generated proof/current artifacts such as `tmp/cron-automation-authority-contract.*` or `tmp/wf72-phases-8-11-full-activation-readiness-plan.*`.
- Do not rewrite SQL rollback/export proof just to clean references.
- Do not mutate config/auth/channel/service/runtime/credentials, finance canon, current-window proof, scripts, or skills in this classification lane.
