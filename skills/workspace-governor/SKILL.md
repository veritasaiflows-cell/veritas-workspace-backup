---
name: "workspace-governor"
description: "Add startup-surface compression rules."
---

# Workspace Governor

Treat the workspace as an operating system, not a junk drawer.

Use direct filesystem and note edits for workspace notes and policy files. Prefer simple structural rules that can be enforced repeatedly. When the workspace is a data-heavy operating system, treat folder/layout drift and boot-surface bloat as execution risks, not cosmetic mess.

## Core Standards

Read `references/workspace-standards.md` when you need the current policy, naming conventions, folder-fit rules, or cleanup checklist.

Default standards:
- keep the root limited to core files, system folders, and a small set of durable top-level domains
- preserve the numbered top-level review order when organizing root folders
- prefer filing work into existing folders over creating new top-level categories
- use descriptive Title Case note names for human-facing notes
- use lowercase for system or implementation folders like `memory`, `templates`, and `skills`
- keep approved root exceptions documented in policy text, not only tolerated in practice
- use validator proof when a recurring audit claims the workspace is still coherent
- remove empty folders and stray diagnostic clutter

## Startup Surface Compression

Startup files are first-hop route maps, not procedure repositories.

Audit these files together when boot size, startup drift, or operating-file bloat is in scope:
- `SOUL.md`
- `AGENTS.md`
- `IDENTITY.md`
- `USER.md`
- `TOOLS.md`
- `MEMORY.md`
- `HEARTBEAT.md`
- `06. Playbooks/Startup Truth Index.md`

Use this migration rule:
- identity, mission, and hard safety doctrine stays in `SOUL.md`
- startup/orchestration/action rules stay in `AGENTS.md`
- runtime facts, global tool constraints, and first-hop commands stay in `TOOLS.md`
- Randall preferences stay in `USER.md`
- curated durable decisions stay in `MEMORY.md`
- heartbeat-only behavior stays in `HEARTBEAT.md`
- detailed procedures move to skills or operating procedures
- workflow-specific state/history moves to workflow continuity notes or route capsules
- script catalogs move to `scripts/README.md`
- chronological detail moves to `memory/YYYY-MM-DD.md`
- generated proof stays in JSON/SQLite under `tmp/` unless it is a final durable human audit

Before closing a startup compression pass:
1. Run `python scripts\boot_surface_size_guard.py --write --validate`.
2. Keep every boot/control file under the warning threshold when practical.
3. If a file remains near threshold, name the owner surface that should absorb future detail.
4. Verify the trim did not weaken finance, config/runtime, paper/live/account, customer/public, archive/delete, or owner-approval boundaries.
5. Update WF73 or the relevant continuity note with the compression lesson.

Do not compress by deleting active authority, stop lines, or current routes. Compress by moving detail to the correct owner.

## `tmp/` Versus Durable Note Rule

`tmp/` is not JSON-only, but it is generated/staged-only.

Use `tmp/` for:
- generated JSON/CSV/HTML/SQLite artifacts
- script-created Markdown sidecars that explain a generated artifact
- helper-lane scratch reports before main-session acceptance
- patch previews, dry-run outputs, and review packet drafts
- throwaway/prototype proof scripts that prove a concept before promotion

Promote out of `tmp/` when Markdown becomes durable human-facing truth:
- final audits -> `08. Audits/`
- durable research -> `04. Research/`
- weekly/event intelligence -> `05. Intelligence/`
- workflow pickup state -> `06. Playbooks/Project Continuity/`
- daily continuity -> `memory/YYYY-MM-DD.md`

When promoting a `tmp/*.md` report, keep the machine companion artifact in `tmp/` if scripts or validators consume it, and update queue/registry/workflow references to point at the durable Markdown home.

## Audit Workflow

1. Inspect the workspace surface that affects retrieval or script-path truth:
   - root
   - numbered domains
   - `memory/`
   - `scripts/`
   - `skills/`
   - `tmp/`
   - `09. Archive/`
   - current structure policy and relevant recent audits
2. Identify concrete drift:
   - empty folders
   - misplaced notes
   - vague or duplicate naming
   - accidental new top-level folders
   - special-purpose notes that should be merged, promoted, or archived
   - missing or inconsistent retrieval metadata where status/owner/next-action/archive posture affects retrieval
   - policy text that no longer matches approved runtime reality
   - generated artifacts or helper code in the wrong ownership layer
   - final audits or durable research still sitting only in `tmp/`
   - startup files carrying procedural detail that belongs in skills, workflow notes, or script docs
   - root exceptions that exist live but are undocumented or no longer justified
3. Cross-check live structure against governing docs and available validators before recommending moves.
4. Recommend the minimum structural changes that improve clarity and preserve review order.
5. If asked to act, make safe changes directly and preserve link safety when renaming or moving notes.
6. Record durable rules in the skill or workspace operating files, not only in chat.

## Root Policy Enforcement

Use a strict test before allowing a new top-level folder:
- does it represent a durable domain
- will it hold multiple notes over time
- would using an existing folder make retrieval meaningfully worse

If the answer is no, do not create it.

When top-level folders are user-facing review domains, use zero-padded numeric prefixes to encode review order.

## Rename And Move Safety

Before moving or renaming notes:
- search for inbound references such as wikilinks or markdown links
- update references if the change would break navigation
- prefer stability over churn when the existing name is already adequate

## Cleanup Posture

Prefer the smallest cleanup that restores clarity.
Do not reorganize for aesthetics alone.
Do not create elaborate folder trees without evidence they will be used.
Do not keep empty scaffolding around just in case.

For auto-archive recommendations, classify each candidate as:
- safe to report automatically
- safe to archive only after explicit approval
- blocked from archive because it is canonical, active, referenced, or authority-bearing

Never auto-archive canonical finance notes, active workflow continuity, credentials/config/runtime files, or proof artifacts still referenced by a live validator/queue.

## Weekly Audit Expectations

During recurring audits:
- run the cleanup checklist from `references/workspace-standards.md`
- sweep the whole workspace ownership chain, not only the root listing
- run `python scripts\workspace_boundary_check.py` and `python scripts\dashboard_truth_lint.py` when those validators exist and the audit scope touches path or truth-surface drift
- verify documented root exceptions still match live runtime needs before proposing moves or deletions
- verify the numbered root order still matches the intended review flow
- report only meaningful drift, decisions, or fixes
- keep noise low
- suggest structural changes only when repeated patterns justify them

## Automatic Governance Improvement Capture

After workspace cleanup, note-placement, root-boundary, retrieval-metadata, archive-policy, startup-surface compression, or operating-file governance work, check whether the session exposed a repeatable drift pattern.

If yes, harden one of these before closure when safe:
- `references/workspace-standards.md`
- `06. Playbooks/Operating Procedures/Retrieval Metadata and Notes Field Standard.md`
- the relevant validator such as `scripts/workspace_boundary_check.py`, `scripts/dashboard_truth_lint.py`, or `scripts/boot_surface_size_guard.py`
- the owning operating procedure or queue item
- this skill, when the governance sequence itself needs a stronger rule

If the right structural direction is ambiguous, ask Randall a concrete question before moving, renaming, archiving, or widening policy.
