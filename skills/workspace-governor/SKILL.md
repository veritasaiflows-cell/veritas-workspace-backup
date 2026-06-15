---
name: "workspace-governor"
description: "Govern workspace structure, startup surfaces, tmp/durable placement, and audit residue."
---

# Proposed Update: workspace-governor

## Summary

Broaden `workspace-governor` from startup/root hygiene into the owning structural-governance skill for audit residue that affects workspace truth, retrieval, or operator clarity.

Keep the current direct-file governance posture. Add these sections to the live skill.

## Proposed Description

`Govern workspace structure, startup surfaces, tmp/durable placement, and audit residue. Use when auditing root drift, workspace structure, startup bloat, generated-proof placement, memory hygiene, final audit placement, root exceptions, or structural findings from full workspace audits.`

## Add Section: Audit Residue Intake

After any full workspace audit, targeted finding review, cleanup pass, or ClawHub pattern intake, check whether the finding is structural or procedural residue.

Classify residue as:
- root/folder structure drift
- startup-surface bloat
- generated artifact in the wrong layer
- durable human report left only in `tmp/`
- memory hygiene issue
- undocumented root exception
- link/reference risk from rename or move
- workspace policy mismatch
- skill/procedure/validator routing candidate

If it is structural, update `workspace-governor`, `references/workspace-standards.md`, or the relevant validator path. If it is procedural agent behavior, route it to a skill or operating procedure instead.

## Add Section: Knowledge Base Hygiene Lens

When a workspace audit touches notes, memory, procedures, playbooks, or research folders, include a lightweight KB hygiene pass:
- broken local markdown links or wikilinks in changed/durable surfaces
- duplicate note titles or near-duplicate purpose files
- orphaned durable notes with no owner or next action
- stale drafts that claim current status
- repeated daily-memory headings or duplicate flush sections
- tags/frontmatter only where the local note standard expects them

Do not impose universal frontmatter or generic vault rules on canonical finance notes unless the workspace standard requires it.

## Add Section: Final Audit Placement

Final user-facing audits belong under `08. Audits/`. Machine proof, JSON, SQLite, and scratch reports may remain under `tmp/` when validators or scripts consume them.

Before closing an audit-related cleanup or governance pass:
1. Confirm the durable human-facing audit is not stranded only under `tmp/`.
2. Confirm any companion machine artifact is named in the audit or queue item.
3. Confirm no generated artifact is treated as canon, approval, portfolio truth, or execution authority.

## Add Section: External Pattern Intake Boundary

ClawHub and web audit patterns may be used as pattern libraries. Do not install or apply third-party skills directly into the live workspace without a dedicated security and governance review.

For each external pattern adopted, record:
- source skill or web source
- useful pattern
- local owner skill/procedure/validator
- boundary that prevents generic advice from overriding Veritas finance/control-plane doctrine

## Add Section: Review Proof

When a governance pass claims structure is clean, use the smallest meaningful proof:
- direct file inspection for the touched surface
- `openclaw skills check` when skills are touched
- `python scripts\boot_surface_size_guard.py --write --validate` when startup surfaces are touched
- `python scripts\workspace_boundary_check.py` and `python scripts\dashboard_truth_lint.py` when those validators exist and path/truth drift is in scope
- lane register validation when the pass wrote artifacts

If a validator does not exist, say so and recommend the exact validator gap instead of claiming automated proof.

## Acceptance Proof

After applying this proposal:
- `openclaw skills check` passes.
- A future workspace audit can route final report placement, tmp/durable proof, root exceptions, memory hygiene, and external pattern intake through this skill without needing a new ad hoc rule.
