# WF72 FTS + field-family plan QA

- Generated: `2026-05-24T07:57:00Z`
- Verdict: **PASS** (`pass_with_closeout_follow_up`)
- Boundary: read-only QA except this `tmp/` artifact. No canon/portfolio/trade/account/paper/config/runtime/destructive changes.

## 1. PASS/BLOCKED verdict

**PASS.** The FTS hardening is valid and scoped, and the field-family migration prework is safe as a plan-only artifact.

No blocking fixes are required before accepting the FTS behavior or the plan artifact. One closeout follow-up remains: update WF72 continuity/queue text after main-session acceptance because the durable WF72 note still describes hyphenated `note-drift` as residue from before this hardening.

## 2. FTS query behavior result

| Query | Result | Evidence |
|---|---:|---|
| `note-drift` | PASS | Returned 5 hits; no `sqlite3.OperationalError`. Top hit: `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md`. |
| `note drift` | PASS | Returned 5 hits via normal search. Top hit: archived rebalancing note, with SQLite procedure second. |
| `Phase 4A SQL canon` | PASS | Returned 5 relevant hits including memory, SQLite skill, Active Workflows, WF72 continuity, and SQLite procedure. |
| `WF72` | PASS | Exact alias hit returned first for the WF72 continuity note; 4 total hits. |

Implementation check: `scripts/workspace_index.py` tries exact aliases first, preserves raw FTS5 query behavior, catches `sqlite3.OperationalError`, then falls back to quoted phrase / token-AND variants from extracted word tokens passed as SQLite parameters.

## 3. Documentation adequacy

Adequate with one closeout follow-up.

- `tmp/wf72-fts-query-hardening.json/.md` records before/after, smoke queries, validation, and retrieval-only authority boundary.
- `scripts/README.md` documents `workspace_index.py`, `note-drift`, `Phase 4A SQL canon`, exact alias behavior, hyphen fallback, WAL sidecars, and the source-open-before-judgment rule.
- `06. Playbooks/Operating Procedures/SQLite Retrieval Index Procedure.md` documents SQL retrieval proof, stop lines, and that SQL rows are locator/provenance hints only.
- Follow-up: WF72 continuity still has pre-hardening wording saying hyphenated `note-drift` residue should be handled. Update after main-session acceptance.

## 4. Field-family plan quality / risk assessment

**Quality: good.** The plan is appropriately plan-only/read-only and does not expand SQL canon by itself.

Strengths:
- Starts with the already approved exact Phase 4A keys only.
- Keeps early consumer changes in proof/trust metadata.
- Requires fallback, rollback export hashes, exact allowlists, cache validation, and no-drift compares.
- Correctly ranks risk: freshness/status first; entry-band/technical second; sector/sleeve/sizing later.
- Explicitly blocks changed recommendation, deployment/action state, owner-action text, ranking, authority flags, entry-band state, or fallback failures.

Residual risk:
- Deployment/status wording can be misread as approval if later wired into behavior instead of proof metadata.
- Entry bands, stops, sizing, sleeve, and sector fields sit near portfolio construction authority and must stay shadow/no-drift until exact keys and gates exist.

## 5. Authority-boundary concerns

No blocking authority-boundary concern found.

Confirmed boundaries remain false/no-authority for:
- Markdown/canonical note mutation
- portfolio mutation
- owner approval inference
- paper/live trade or account action
- money movement
- cron/config/auth/runtime/channel mutation
- dashboard recommendation/deployment/action-state behavior changes from this plan

## 6. Required fixes before acceptance

None.

Required before WF72 workflow closeout:
1. Update the WF72 continuity/queue truth to reflect that hyphenated FTS search has been hardened and the field-family migration prework is complete.

## Validation run

Passed:

```powershell
python -m py_compile scripts\workspace_index.py
python scripts\workspace_index.py --search note-drift --limit 5
python scripts\workspace_index.py --search "note drift" --limit 5
python scripts\workspace_index.py --search "Phase 4A SQL canon" --limit 5
python scripts\workspace_index.py --search WF72 --limit 5
python -m json.tool tmp\wf72-field-family-migration-prework.json
python -m json.tool tmp\wf72-fts-query-hardening.json
```

## Recommended next pass

If the migration proceeds, use only the recommended first slice: Today-card proof metadata for the two existing Phase 4A NVDA keys, with normalized no-drift compare, cache-missing fallback test, Today validator, artifact-index validation, and unchanged authority banner.
