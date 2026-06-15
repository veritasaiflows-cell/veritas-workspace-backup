# Workspace Folder Automation and Truth Architecture Audit - 2026-05-05

## Purpose
- Deep review of whether the finance, continuity, implementation, and generated-artifact folders support automation and truth.
- Convert the findings into bounded follow-up workflows instead of broad cosmetic reorganization.

## Executive Verdict
- The workspace does **not** need a major top-level reorg.
- The numbered finance/domain spine is sound.
- The main weakness is boundary and truth-surface discipline:
  - generated/machine surfaces must remain subordinate to canonical notes
  - scripts and executable helpers must not live in `tmp/`
  - dashboard/read surfaces must link to owner truth, not become parallel truth
  - workflow names/aliases must be resolved through live paths before status claims

## Current Strengths
- Root numbered domains match the finance-first review order.
- `03. Portfolio/` has strong ownership separation: snapshot, deployment trigger, technical entry/invalidation, model portfolio, rebalance log.
- `05. Intelligence/Earnings/` is a coherent home for post-earnings scorecards.
- `scripts/README.md` already states the correct `scripts/` vs `tmp/` boundary.
- `Workspace Structure Protocol`, `Notes Layer Governance Protocol`, and `workspace-governor` provide enough policy backbone for enforcement.

## Risks Found

### Finance-note truth risks
- Dashboard, market, portfolio, and intelligence notes can describe the same names with subtly different language.
- `*-machine.md` companions are useful but must never outrank human-approved canonical notes.
- Dated dashboard streams mix human and machine variants; that is acceptable only if naming and ownership stay strict.
- `04. Research/` is still flat. That is okay now, but it may need company/sector substructure later if coverage expands.

### Automation / implementation risks
- Executable helpers exist in `tmp/`:
  - `09. Archive/tmp-helper-scripts - Archived/2026-05-05-wf34/fetch_news.py`
  - `09. Archive/tmp-helper-scripts - Archived/2026-05-05-wf34/scrape_ir_links.py`
- Trust vocabulary is not fully normalized: some downstream surfaces use `clean` while contracts use `ok | warning | blocked | error`.
- Stale generated artifacts can coexist with green/clean output language.
- `tmp/` is carrying retention debt from old sidecars and fallback artifacts.
- `scripts/` contains some active-surface debris, including a dated `.bak` file.

### Root / folder policy risks
- Empty root folders found:
  - `attachments/`
  - `state/`
- `migration-review.md` sits at root without a current obvious active-root entitlement.
- These are not catastrophic, but they weaken the strict root policy if left unexplained.

### Continuity risk already surfaced
- Workflow-name drift caused a false read that Workflow 21 did not exist.
- The durable lesson is now recorded: resolve workflow references through exact live filenames/paths before making status claims.

## Target State
- Keep the existing top-level folder model.
- Strengthen the owner map and generated-vs-canonical boundaries.
- Keep machine artifacts in `tmp/` unless intentionally review-facing and clearly marked as machine-generated note companions.
- Keep durable tooling in `scripts/`, not `tmp/`.
- Keep dashboards as summaries and routers, not canonical truth.
- Keep workflow continuity in `06. Playbooks/Project Continuity/` plus daily memory only.
- Add bounded workflows instead of broad manual cleanup.

## Workflow Integration Decisions

### Existing owners
- Workflow 30 owns queue/index/carryover truth reconciliation.
- Workflow 31 owns runtime continuity, memory indexing, and scheduled-proof hardening.
- Workflow 32 owns finance JSON surface contract normalization.
- Workflow 33 owns declarative finance chain/dependency map hardening.

### Newly opened follow-up workflows
- Workflow 34 - Workspace Folder Governance and Root Drift Integration
  - owns root drift, `tmp`/`scripts` boundary enforcement, retention policy application, and stale-green folder-surface risks.
- Workflow 35 - Dashboard and Document Truth-Surface Integration
  - owns dashboard/document owner-map integration, machine companion note policy, and read-stack truth routing.

## What Not To Change
- Do not create new top-level finance folders.
- Do not move canonical current-state notes out of their numbered domains.
- Do not merge `Watchlist`, `Portfolio Snapshot`, and `Deployment Trigger Sheet`.
- Do not move all machine-facing review notes to `tmp/` blindly; some are intentionally human-review companions.
- Do not prune backups or generated artifacts without verifying active references.

## Recommended Sequence
1. Finish WF21 to an honest handoff point.
2. Run WF30 to fix queue/index truth.
3. Run WF31 if runtime/proof residue still blocks trust.
4. Run WF32 to normalize JSON/trust vocabulary.
5. Run WF33 to make the finance chain manifest inspectable.
6. Run WF34 to clean folder boundaries and root drift.
7. Run WF35 to integrate the cleaned truth model into dashboards and documents.
8. Let WF23 consume the improved owner map for Command Center/dashboard tightening later.

## Acceptance Standard For The Whole Folder Upgrade
- Folder structure supports automation without hiding uncertainty.
- Canonical notes, generated artifacts, dashboards, and workflow continuity each have one clear owner role.
- Machine outputs cannot imply green trust while required inputs are stale or degraded.
- Dashboard/document surfaces point to truth owners instead of duplicating truth.
- Workflow lookup uses exact live paths or a normalized index, not remembered titles.
