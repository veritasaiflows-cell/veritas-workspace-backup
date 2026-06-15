# SQLite Retrieval Index Procedure

## Purpose
Use the local SQLite retrieval indexes to find workspace evidence faster without letting SQL become a second source of truth.

## Trigger
Run this procedure when Randall asks for faster retrieval, SQL-backed lookup, artifact/event discovery, workflow lookup, or a finance-artifact question where scanning the whole workspace would be slower than using the derived indexes.

## Read first
- `06. Playbooks/Project Continuity/Workflow 36 - Workspace Retrieval Index and SQLite Knowledge Layer.md`
- `scripts/README.md` sections for `workspace_index.py` and `artifact_index.py`
- the source Markdown note or JSON artifact returned by any SQL hit before making a judgment

## Indexes
| Index | Script | DB/cache | Use |
|---|---|---|---|
| Workspace retrieval index | `scripts/workspace_index.py` | `tmp/workspace-index.sqlite` | Markdown/workflow lookup, owner maps, aliases, artifact inventory, freshness hints |
| Finance artifact-output index / SQL cockpit | `scripts/artifact_index.py` | `tmp/veritas-artifact-index.sqlite` | Primary generated-artifact/proof/provenance/staging lookup; cockpit queue, ticker timelines, helper handoff locator packets, official-source field proof, trust/authority boundaries, canon-staging stop lines, SQL-routed note drift candidates, validation, and incremental rebuilds |

## Operator steps
1. Rebuild or incrementally refresh the relevant index if freshness matters.
2. Run the narrowest query that answers the retrieval question.
3. Open the returned source file(s) or JSON artifact(s).
4. If the source file conflicts with the SQL row, trust the source file and rebuild the index if needed.
5. Use the SQL result as a locator/provenance hint only; do not mutate queue, portfolio, dashboard, or canonical notes from SQL alone.
6. If a query pattern becomes repeatedly useful, update `scripts/README.md` or this procedure instead of scattering examples through workflow notes.

## Common commands
```powershell
python scripts\workspace_index.py
python scripts\workspace_index.py --search "Workflow 36" --limit 10
python scripts\workspace_index.py --search "note-drift" --limit 10
python scripts\workspace_index.py --search "Phase 4A SQL canon" --limit 10
python scripts\artifact_index.py rebuild
python scripts\artifact_index.py incremental
python scripts\artifact_index.py validate
python scripts\artifact_index.py cockpit --limit 20
python scripts\artifact_index.py ticker-cockpit ETN --limit 30
python scripts\artifact_index.py trust-cockpit --limit 50
python scripts\artifact_index.py proof-field AMD adjusted_eps
python scripts\artifact_index.py stoplines --limit 50
python scripts\artifact_index.py handoff --workflow WF72 --limit 20
python scripts\artifact_index.py note-drift --limit 100 --output tmp\wf72-sql-to-note-drift-report.json --md-output tmp\wf72-sql-to-note-drift-report.md
python scripts\artifact_index.py fingerprints --json
```

## Proof
- Rebuild or incremental command exits successfully.
- Query returns source paths / artifact references.
- Workspace-index FTS queries preserve raw FTS behavior first, then fall back to safe quoted phrase / token-AND forms for human punctuation such as `note-drift`; exact aliases such as `WF72` may return alias hits first.
- The source file or artifact was opened before judgment or mutation.
- `handoff --workflow <WFxx>` is used as a helper locator packet only; canonical workflow next action still comes from `06. Playbooks/Active Workflows.md`.
- `note-drift` outputs candidate drift/review rows only; it does not apply canonical notes and requires source-artifact plus Markdown-note inspection before any sync proposal.
- `validate` returns ok before using SQL as the primary generated-artifact route for a material claim.
- Any stale/conflicting result is recorded as index freshness residue, not treated as canonical truth.

## Stop lines
- Do not index credentials, runtime secrets, `.git`, `.obsidian`, `.openclaw`, migration backups, or broad `tmp/` content outside the explicitly intended generated DB/report/artifact-output scope.
- Do not treat SQL rows as portfolio truth, queue authority, deployment authorization, or closeout proof.
- Do not widen chain integration beyond derived index refresh/health visibility without a bounded proposal, no-drift proof, and authority review.
- Do not create another retrieval index if `workspace_index.py` or `artifact_index.py` can be extended safely under Workflow 36.

## Next action after use
- For one-off lookup: answer from opened source files and mention SQL only as retrieval support when useful.
- For repeated lookup: add a documented query recipe.
- For automation integration: reopen Workflow 36 only as a bounded follow-up slice with QA/closeout and no canon-shadowing.
