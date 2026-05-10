# WF34 Folder Boundary Audit and Completion - 2026-05-05

## Plain-English verdict
WF34 is complete enough to close as a workspace-boundary hardening pass. The top-level folder model was already sound; the real problem was smaller but important: executable helpers and backup debris were living in places that made automation trust harder.

## What was wrong
- `tmp/` contained executable helper scripts. That blurred generated artifact storage with durable tooling.
- `scripts/` contained timestamped backup files that looked like active implementation surfaces.
- `state/` had reappeared as an empty root folder with no current entitlement.
- `attachments/` looked suspicious at first, but it is intentionally referenced by Obsidian config and should stay.
- `migration-review.md` remains a root-level review surface because current operator/memory skills still reference it for uncertain migration material.
- `tmp/entry-band-reports/` had duplicate `BRK.B` / `BRK-B` report naming. Current consumers reference `BRK.B`, so the stale `BRK-B` copy was archived.

## Actions completed
- Archived one-off helper scripts out of active `tmp/`:
  - `tmp/fetch_news.py` -> `09. Archive/tmp-helper-scripts - Archived/2026-05-05-wf34/fetch_news.py`
  - `tmp/scrape_ir_links.py` -> `09. Archive/tmp-helper-scripts - Archived/2026-05-05-wf34/scrape_ir_links.py`
  - `tmp/wf36_audit_probe.py` -> `09. Archive/tmp-helper-scripts - Archived/2026-05-05-wf34/wf36_audit_probe.py`
- Moved script backup debris out of active `scripts/`:
  - `scripts/premarket_snapshot.py.bak-20260505-084507` -> `migration-backups/2026-05-05-wf34-script-backups/`
  - `scripts/run_finance_refresh_chain.py.bak-20260505-084507` -> `migration-backups/2026-05-05-wf34-script-backups/`
- Removed empty root `state/` after reference review showed no active runtime entitlement.
- Retained `attachments/` because `.obsidian/app.json` points attachments there.
- Retained `migration-review.md` as a documented root exception for uncertain migration/review material.
- Archived stale `tmp/entry-band-reports/BRK-B_entry_band.html`; current generated/dashboard consumers point to `BRK.B_entry_band.html`.
- Added `scripts/workspace_boundary_check.py` as a read-only validator.
- Wrote latest validator output to `tmp/workspace-boundary-check.json`.

## Current validation
`python scripts/workspace_boundary_check.py` now returns `status: ok`.

Remaining informational findings are expected:
- Python `__pycache__/` folders are runtime cache debris, not governance surfaces.
- `tmp/workspace-index.sqlite` is a generated SQLite retrieval cache and is ignored/non-canonical.
- `tmp/veritas-command-center.last-good.html` is retained because the finance chain uses it as last-known-good dashboard fallback.

## Stop lines preserved
- No canonical finance notes were mutated.
- No dashboard truth was changed from this workflow.
- No active generated artifact was deleted blindly.
- Moves were archival/reversible except empty `state/`, which had no active runtime entitlement and has repeatedly been treated as root drift.

## Acceptance checklist
- [x] Root classification completed.
- [x] `tmp` executable-helper decision completed.
- [x] `attachments/` runtime ownership identified and retained.
- [x] `state/` removed after no active entitlement was found.
- [x] Script backup debris moved out of active `scripts/`.
- [x] Stale generated duplicate naming handled for `BRK-B` vs `BRK.B`.
- [x] Boundary validator created and run.
- [x] Residual risks are informational, not blocking.

## Completion status
**Closed with follow-up.**

Follow-up belongs to WF32/WF33/WF36, not WF34:
- WF32 owns deeper JSON contract/status vocabulary.
- WF33 owns chain manifest/dependency hardening.
- WF36 owns SQL-backed artifact manifest and freshness semantics.
