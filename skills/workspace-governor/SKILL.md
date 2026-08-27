---
name: "workspace-governor"
description: "Govern workspace structure, note/procedure placement, tmp-vs-durable routing, root policy, agent paths, and cleanup stop lines."
---

# Workspace Governor

Use this skill when cleaning up the workspace, defining or enforcing root folder policy, reviewing note or procedure placement, spotting empty or duplicate folders, auditing startup/root drift, deciding `tmp` versus durable placement, routing structural findings from workspace audits, classifying operating procedures versus playbooks versus skills, preventing procedure sprawl, or clarifying governance authority.

## Purpose

Treat the workspace as an operating system, not a junk drawer. Folder/layout drift is an execution risk when the workspace is a data-heavy operating system.

## Core Standards

Read `references\workspace-standards.md` when current policy, naming conventions, folder-fit rules, or cleanup checklist details matter.

Default standards:

- keep the root limited to core files, system folders, and durable top-level domains
- preserve numbered top-level review order
- file work into existing folders before creating new top-level categories
- use descriptive Title Case note names for human-facing notes
- use lowercase for system or implementation folders like `memory`, `templates`, and `skills`
- keep approved root exceptions documented in policy text
- use validator proof when recurring audits claim structure is coherent
- remove empty folders and diagnostic clutter only when safe, scoped, and approved where required

## `tmp/` Versus Durable Note Rule

`tmp/` is generated/staged-only, not a durable human truth layer.

Use `tmp/` for:

- generated JSON/CSV/HTML/SQLite artifacts
- script-created Markdown sidecars explaining generated artifacts
- helper-lane scratch reports before main-session acceptance
- patch previews, dry-run outputs, and review packet drafts

Promote out of `tmp/` when Markdown becomes durable human-facing truth:

- final audits -> `08. Audits\`
- durable research -> `04. Research\`
- weekly/event intelligence -> `05. Intelligence\`
- workflow pickup state -> `06. Playbooks\Project Continuity\`
- daily continuity -> `memory\YYYY-MM-DD.md`

When promoting a generated report, keep machine companion artifacts in `tmp\` if scripts or validators consume them, and update references to point at the durable Markdown home.

## Agent Workspace Path Guidance

OpenClaw does **not** use a fixed `~/.openclaw/workspaces/` root. Multi-agent isolation is configured via `agents.list[].workspace` and `agents.list[].agentDir`, with each workspace explicitly named.

If a proposal creates `~/.openclaw/workspaces/` or treats it as an auto-discovery directory, flag it as a configuration error. The standard pattern is:

- main: `~/.openclaw/workspace` or `~/.openclaw/workspace-main`
- additional isolated agents: `~/.openclaw/workspace-<agentId>` (or any explicit approved path)

Do not let a generic `workspaces/` folder become a parallel root. Treat it like any other non-standard path: report it, require explicit documentation, and do not assume discovery behavior.

## Audit Residue Intake

After any full workspace audit, targeted finding review, cleanup pass, or external pattern intake, classify whether the finding is structural or procedural residue.

Structural residue includes:

- root/folder structure drift
- startup-surface bloat
- generated artifact in the wrong layer
- durable human report left only in `tmp\`
- memory hygiene issue
- undocumented root exception
- link/reference risk from rename or move
- workspace policy mismatch
- skill/procedure/validator routing candidate
- non-standard OpenClaw path layout such as `~/.openclaw/workspaces/`

If structural, update `workspace-governor`, workspace standards, or the relevant validator path. If procedural agent behavior, route it to a skill or operating procedure.

## Knowledge Base Hygiene Lens

When a workspace audit touches notes, memory, procedures, playbooks, or research folders, include a lightweight hygiene pass:

- broken local markdown links or wikilinks in changed/durable surfaces
- duplicate note titles or near-duplicate purpose files
- orphaned durable notes with no owner or next action
- stale drafts that claim current status
- repeated daily-memory headings or duplicate flush sections
- tags/frontmatter only where the local note standard expects them

Do not impose generic vault rules on canonical finance notes unless the workspace standard requires it.

## Procedure Repository Governance

Use this skill as the canonical owner for operating-procedure repository placement and SOP-sprawl control. The old `operating-procedure-repository-manager` skill is retained only as a compatibility router while references are drained.

A durable operating procedure belongs under `06. Playbooks\Operating Procedures\` only when it describes a real repeated operator task, has an identifiable owner surface, names trigger/read-first/steps/proof/stop lines/next action, and reduces operator ambiguity.

Route content this way:

- operator-facing repeated steps -> `06. Playbooks\Operating Procedures\`
- workflow-specific sequencing/history -> workflow continuity notes
- durable governance rules -> playbooks or core doctrine
- automation/runtime behavior -> skill or script docs
- one-off lessons -> daily memory or audit notes

Before creating or updating a procedure, name:

1. The repeated operator task that is real now.
2. The proof that makes it a procedure instead of an aspiration.
3. The truth owner for the underlying work.
4. The repository location.
5. What should stay outside the procedure.

Repository rules:

- procedures must stay operator-facing
- procedures must link back to the owning workflow, playbook, skill, or script when authority lives elsewhere
- procedures must not silently outrank canonical owner notes, governance docs, skills, validators, or owner artifacts
- prefer one clean procedure note per recurring task instead of overlapping variants
- tighten the index, classification rubric, or ownership map before creating a broad new governance surface
- do not write procedures for hypothetical, unstable, or one-off work without likely recurrence

A procedure is ready only if it describes a real repeated task, has an owner surface, names explicit stop lines, points to proof or validation, and reduces operator ambiguity instead of adding another layer to inspect.

## Final Audit Placement

Final user-facing audits belong under `08. Audits\`. Machine proof, JSON, SQLite, and scratch reports may remain under `tmp\` when validators or scripts consume them.

Before closing audit cleanup or governance work:

1. Confirm the durable human-facing audit is not stranded only under `tmp\`.
2. Confirm companion machine artifacts are named in the audit or queue item.
3. Confirm no generated artifact is treated as canon, approval, portfolio truth, or execution authority.

## Root Policy Enforcement

Allow a new top-level folder only when it represents a durable domain, will hold multiple notes over time, and existing folders would make retrieval meaningfully worse. Otherwise, do not create it.

Do not create a `workspaces/` root folder at `~/.openclaw/` unless it is explicitly documented as a local convention and paired with a discovery mechanism. OpenClaw's standard discovery path is `agents.list[]`, not folder scanning.

## Rename And Move Safety

Before moving or renaming notes:

- search for inbound references such as wikilinks or markdown links
- update references if the change would break navigation
- prefer stability over churn when the existing name is adequate

## Cleanup Posture

Prefer the smallest cleanup that restores clarity. Do not reorganize for aesthetics alone. Do not create elaborate folder trees without evidence they will be used.

For archive recommendations, classify each candidate as:

- safe to report automatically
- safe to archive only after explicit approval
- blocked because it is canonical, active, referenced, or authority-bearing

Never auto-archive canonical finance notes, active workflow continuity, credentials/config/runtime files, or proof artifacts still referenced by a live validator or queue.

## External Pattern Intake Boundary

External skills and web patterns may be used as pattern libraries. Do not install or apply third-party skills directly into the live workspace without dedicated security and governance review.

For each external pattern adopted, record source, useful pattern, local owner skill/procedure/validator, and boundary that prevents generic advice from overriding Veritas doctrine.

## Allowed Governance Work

Allowed:

- inspect workspace doctrine, governance surfaces, audit residue, and final placement paths
- recommend safe routing, archive/reference-review paths, and bounded cleanup proposals
- classify route proof versus canon/authority distinction
- update governance surfaces through exact scoped edits when authorized

## Blocked Governance Work

Blocked without exact approved gate:

- destructive cleanup, moves, deletes, archive action, or broad cleanup
- external install or third-party skill adoption
- config/auth/network/runtime/startup/service mutation
- capital deployment, paper/live/account action, brokerage action, or money movement
- portfolio/canon/cash/sizing/risk mutation
- generated artifacts outranking canon or owner notes

## Stop Lines

Stop for doctrine conflict, unclear authority owner, external pattern intake without security review, destructive/archive/delete path, credential/config/runtime implication, finance authority ambiguity, portfolio/canon implication, paper/live/account implication, non-standard OpenClaw path layout presented as standard, unstable procedure candidate, procedure duplication of workflow history or canonical truth, procedure repository sprawl, or missing backup/rollback proof for authority-bearing cleanup.

## Review Proof

Use the smallest meaningful proof:

- direct file inspection for touched surfaces
- exact source artifacts when governance/canon authority matters
- `openclaw skills check` when skills are touched
- `python scripts\boot_surface_size_guard.py --write --validate` when startup surfaces are touched
- workspace/path/truth validators when those are in scope and exist
- lane register validation when the pass wrote artifacts
- backup/rollback proof when moves/archive/cleanup are approved

If a validator does not exist, say so and recommend the exact validator gap instead of claiming automated proof.

## Closeout

State governance decision, allowed path, blocked path, proof, changed placement if any, route-proof-versus-canon distinction, and next owner decision if needed.
