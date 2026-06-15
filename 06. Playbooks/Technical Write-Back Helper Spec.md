# Technical Write-Back Helper Spec

## Decision
Do **not** allow direct autonomous canonical-note mutation yet.
Build only a **dry-run-first gated helper** that prepares exact write-back suggestions and requires explicit operator approval before any canonical note edit.

## Why
Current trust state supports:
- machine proposal generation
- exact diff preparation
- post-apply validation

Current trust state does **not** support:
- unattended note mutation across technical/deployment/thesis owner surfaces
- silent scope widening from band updates into broader narrative rewrites

## Near-term scope
The helper may:
1. read machine config and approved proposal artifacts
2. generate exact proposed note lines or patches
3. emit a human-readable change summary
4. stop for approval
5. run post-apply validation after the approved edit is made

The helper may **not**:
- publish canonical note edits without explicit approval
- infer thesis wording beyond the approved technical/deployment field change
- overwrite narrative context outside the exact bounded field set

## Approved first use cases
### 1. Entry-band write-back prep
Inputs:
- `tmp/portfolio-config.json`
- `tmp/band-proposals.json`
- `03. Portfolio/Execution Board.md`

Current supporting tools:
- `scripts/apply_band_update.py` -> updates config only, dry-run/interactively gated
- `scripts/band_note_sync.py` -> emits exact sync report only, no note edits

### 2. Deployment-state mirror prep
Inputs:
- `tmp/trigger-sheet.json`
- owner deployment note
- mirror note targets like `04. Research/Coverage and Watchlist.md`

Output should stay proposal-only unless explicitly approved in the active workflow.

## Required guardrails
- dry run is the default
- exact file targets must be declared up front
- patch scope must be field-bounded, not section-wide unless explicitly approved
- create a backup or rely on current git safety checkpoint before destructive apply
- re-run validator / acceptance checks immediately after apply
- if validation worsens, stop and surface the regression instead of auto-retrying

## Required outputs
Every run must produce:
- target files
- exact proposed changes
- reason for each change
- apply mode used (`dry-run` or `approved-apply`)
- post-apply validation result if apply occurred

## Promotion gate
Only consider a true apply-capable helper after:
- repeated clean dry-run use
- stable owner-boundary rules
- no recent mirror/validator contradictions in the same surface family
- explicit workflow-level approval

## Current posture
For Workflow 9B this remains a **written spec, not an implementation mandate**.
Any future build should be queued deliberately rather than smuggled into a cleanup pass.
