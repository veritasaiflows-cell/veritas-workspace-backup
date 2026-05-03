---
name: workspace-governor
description: Audit and maintain an Obsidian-backed workspace so folders, notes, and operating files stay organized instead of drifting. Use when cleaning up the workspace, defining or enforcing root folder policy, recommending naming conventions, moving notes into better homes, spotting empty or duplicate folders, reviewing note placement, or running periodic organization audits.
---

# Workspace Governor

Treat the workspace as an operating system, not a junk drawer.

Use direct filesystem and note edits. Prefer simple structural rules that can be enforced repeatedly.

## Core standards

Read `references/workspace-standards.md` when you need the current policy, naming conventions, folder-fit rules, or cleanup checklist.

Default standards:
- keep the root limited to core files, system folders, and a small set of durable top-level domains
- preserve the numbered top-level review order when organizing root folders
- prefer filing work into existing folders over creating new top-level categories
- use descriptive Title Case note names for human-facing notes
- use lowercase for system or implementation folders like `memory`, `templates`, and `skills`
- remove empty folders and stray diagnostic clutter

## Audit workflow

1. Inspect the root and major folders.
2. Identify concrete drift:
   - empty folders
   - misplaced notes
   - vague or duplicate naming
   - accidental new top-level folders
   - special-purpose notes that should be merged, promoted, or archived
3. Recommend the minimum structural changes that improve clarity and preserve review order.
4. If asked to act, make the changes directly and preserve link safety when renaming or moving notes.
5. Record durable rules in the skill or workspace operating files, not only in a one-off chat reply.

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

## Weekly audit expectations

During recurring audits:
- run the cleanup checklist from `references/workspace-standards.md`
- verify the numbered root order still matches the intended review flow
- report only meaningful drift, decisions, or fixes
- keep noise low
- suggest structural changes only when repeated patterns justify them
