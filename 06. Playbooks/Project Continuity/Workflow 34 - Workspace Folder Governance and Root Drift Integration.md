# Workflow 34 - Workspace Folder Governance and Root Drift Integration

## Objective
- Bring the workspace folder architecture into the intended automation/truth posture without cosmetic churn.
- Resolve root, `tmp/`, `scripts/`, attachment, and generated-artifact boundary drift so automation can trust where files live and what they mean.

## Current State
- **Closed with follow-up on 2026-05-05.**
- The 2026-05-05 folder architecture research found that the top-level numbered domain model is fundamentally sound.
- The boundary drift was corrected or documented:
  - executable one-off helpers were archived out of `tmp/`
  - script backup debris was moved out of active `scripts/`
  - empty root `state/` was removed
  - `attachments/` was retained because Obsidian config points attachments there
  - `migration-review.md` was retained as a documented root exception for uncertain migration/review material
  - stale `BRK-B` entry-band duplicate was archived after current consumers were found pointing to `BRK.B`

## Last Meaningful Progress
- Finance-folder and automation-folder audit lanes completed read-only reviews on 2026-05-05.
- Added and ran `scripts/workspace_boundary_check.py`; latest `tmp/workspace-boundary-check.json` returns `status: ok` with only informational retained-cache/fallback findings.
- Completion audit: `08. Audits/WF34 Folder Boundary Audit and Completion - 2026-05-05.md`.

## Scope
- classify and resolve root drift
- move or archive executable helpers currently living in `tmp/`
- tighten `scripts/` / `tmp/` boundary discipline
- review generated-artifact retention and stale-green risks
- update workspace/documentation standards where the live policy has changed
- preserve current finance-chain behavior while cleanup happens

## Out of Scope
- changing portfolio or market judgment logic
- broad finance JSON contract normalization owned by Workflow 32
- declarative chain manifest work owned by Workflow 33
- queue/index truth reconciliation owned by Workflow 30
- destructive pruning without an explicit backup/approval posture

## Preflight / Entry Checklist
- [ ] confirm current active workflow order before opening work
- [ ] run `git status --short` and identify files changed by active finance work
- [ ] inspect `tmp/fetch_news.py` and `tmp/scrape_ir_links.py` before moving or archiving
- [ ] verify whether `attachments/` or `state/` are runtime-required before removing or documenting them
- [ ] inspect references to `migration-review.md` before moving it

## Execution Posture
- `serial main-session`

## Owner Layer
- root folder policy -> `06. Playbooks/Workspace Structure Protocol.md` and `workspace-governor`
- durable scripts -> `scripts/`
- generated artifacts -> `tmp/`
- reversible backups -> `migration-backups/`
- audit evidence -> `08. Audits/`

## Review Window
- manual-only structural cleanup window
- do not run as scheduled automation

## Stop Lines
- a proposed cleanup touches active generated artifacts without a reference check
- a file move would break documented CLI/script usage without compatibility handling
- a root folder may be runtime-owned and that ownership is not verified
- cleanup starts deleting instead of moving/archiving without explicit approval

## Surface / Handoff Posture
- dashboard: may surface as a workspace-health / trust-risk note only, not as finance truth
- documents: update protocols/checklists and any operator read surfaces that describe folder policy
- generated artifacts: remain subordinate to canonical notes

## Canonical Mutation Posture
- canonical finance-note mutation disallowed
- workspace policy docs may be updated after direct inspection
- file moves require reference checks and reversible backup posture

## Phased Completion Approach

### Phase 1 - Root and boundary inventory
- inventory root surfaces, empty folders, backup/scratch debris, executable files in `tmp/`, and stale generated artifacts
- classify each item as keep / document / move / archive / remove-later

### Phase 2 - Safe boundary corrections
- relocate or archive `tmp` executable helpers if they matter
- move root `migration-review.md` to the correct audit/archive home if references allow
- resolve or document `attachments/` and `state/`
- clean or quarantine obvious active-surface debris only after verification

### Phase 3 - Retention and stale-green guardrails
- update standards so stale dependencies cannot present as `clean`/green without warnings
- identify which generated outputs are latest-only versus retained audit trail
- hand schema/trust-vocabulary changes to Workflow 32/33 if they exceed folder governance

### Phase 4 - Validation and closeout
- run a root sanity check
- run targeted reference checks for moved files
- update `Home.md` / dashboard-facing control surfaces only if they currently misstate folder policy
- record residual risk and next owner

## Acceptance Gates
- no durable executable helper remains in `tmp/` without an explicit documented exception
- root surfaces are either canonical active, infrastructure, documented exception, archival, or removed
- stale generated artifacts cannot silently support green/clean operator claims without a named warning or downstream owner
- workspace standards and dashboard/document references match the live folder posture
- direct inspection evidence exists for the final root and `tmp` / `scripts` boundary state

## Exit / Closeout Checklist
- [ ] root classification completed
- [ ] `tmp` executable-helper decision completed
- [ ] stale-green risk either fixed or handed to Workflow 32/33 with explicit owner
- [ ] docs/control surfaces updated if needed
- [ ] independent QA/audit pass completed or explicitly deferred with reason
- [ ] checkpoint decision recorded

## Checkpoint Decision
- checkpoint recommended with the WF34-WF36 hardening batch after final queue/registry verification

## Next Pass
- Closed with follow-up. Next owner is WF35/WF36 for truth-owner and SQL/index integration; WF32/WF33 own deeper JSON/chain semantics.

## Next 1-2 Adjacent Candidate Workflows
- Workflow 35 - Dashboard and Document Truth-Surface Integration
- Workflow 30 - Workflow Queue Truth and Carryover Governance Reconciliation, if index/root governance is still confusing workflow lookup

## Key Files
- `06. Playbooks/Workspace Structure Protocol.md`
- `06. Playbooks/Notes Layer Governance Protocol.md`
- `06. Playbooks/Notes Layer Audit Checklist.md`
- `skills/workspace-governor/references/workspace-standards.md`
- `scripts/README.md`
- `tmp/fetch_news.py`
- `tmp/scrape_ir_links.py`
- `migration-review.md`
- `Home.md`
- `01. Dashboards/Executive Brief.md`
