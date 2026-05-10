---
name: workspace-governor
description: Audit and maintain an Obsidian-backed workspace so folders, notes, and operating files stay organized instead of drifting. Use when cleaning up the workspace, defining or enforcing root folder policy, recommending naming conventions, moving notes into better homes, spotting empty or duplicate folders, reviewing note placement, or running periodic organization audits.
---

# Workspace Governor

Treat the workspace as an operating system, not a junk drawer.

Use direct filesystem and note edits. Prefer simple structural rules that can be enforced repeatedly.
When the workspace is a data-heavy operating system, treat folder/layout drift as an execution risk, not just a cosmetic mess.

## Core standards

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

## Audit workflow

1. Inspect the whole workspace surface that affects retrieval or script-path truth:
   - root
   - numbered domains
   - `memory/`
   - `scripts/`
   - `skills/`
   - `tmp/`
   - `09. Archive/`
   - the current structure policy and the most relevant recent audits
2. Identify concrete drift:
   - empty folders
   - misplaced notes
   - vague or duplicate naming
   - accidental new top-level folders
   - special-purpose notes that should be merged, promoted, or archived
   - missing or inconsistent `## Retrieval Notes` blocks on major audits, workflows, research notes, or procedures where status/owner/next-action/archive posture affects retrieval
   - policy text that no longer matches approved runtime reality
   - generated artifacts or helper code in the wrong ownership layer
   - root exceptions that exist live but are undocumented or no longer justified
3. Cross-check live structure against governing docs and available validators before recommending moves.
4. Recommend the minimum structural changes that improve clarity and preserve review order.
5. If asked to act, make the changes directly and preserve link safety when renaming or moving notes.
6. Record durable rules in the skill or workspace operating files, not only in a one-off chat reply.

## Root policy enforcement

Use a strict test before allowing a new top-level folder:
- does it represent a durable domain
- will it hold multiple notes over time
- would using an existing folder make retrieval meaningfully worse

If the answer is no, do not create it.

When top-level folders are user-facing review domains, use zero-padded numeric prefixes to encode review order.

## Rename and move safety

Before moving or renaming notes:
- search for inbound references such as wikilinks or markdown links
- update references if the change would break navigation
- prefer stability over churn when the existing name is already adequate

## Cleanup posture

Prefer the smallest cleanup that restores clarity.
Do not reorganize for aesthetics alone.
Do not create elaborate folder trees without evidence they will be used.
Do not keep empty scaffolding around “just in case”.

For auto-archive recommendations, classify each candidate as:
- safe to report automatically
- safe to archive only after explicit approval
- blocked from archive because it is canonical, active, referenced, or authority-bearing

Never auto-archive canonical finance notes, active workflow continuity, credentials/config/runtime files, or proof artifacts still referenced by a live validator/queue.

## Weekly audit expectations

During recurring audits:
- run the cleanup checklist from `references/workspace-standards.md`
- sweep the whole workspace ownership chain, not only the root listing
- run `python scripts/workspace_boundary_check.py` and `python scripts/dashboard_truth_lint.py` when those validators exist and the audit scope touches path or truth-surface drift
- verify documented root exceptions still match live runtime needs before proposing moves or deletions
- verify the numbered root order still matches the intended review flow
- report only meaningful drift, decisions, or fixes
- keep noise low
- suggest structural changes only when repeated patterns justify them

## Automatic Governance Improvement Capture

After workspace cleanup, note-placement, root-boundary, retrieval-metadata, archive-policy, or operating-file governance work, check whether the session exposed a repeatable drift pattern.

If yes, harden one of these before closure when safe:
- `references/workspace-standards.md`
- `06. Playbooks/Operating Procedures/Retrieval Metadata and Notes Field Standard.md`
- the relevant validator such as `scripts/workspace_boundary_check.py` or `scripts/dashboard_truth_lint.py`
- the owning operating procedure or queue item
- this skill, when the governance sequence itself needs a stronger rule

If the right structural direction is ambiguous, ask Randall a concrete question before moving, renaming, archiving, or widening policy.
