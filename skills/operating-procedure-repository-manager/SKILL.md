---
name: "operating-procedure-repository-manager"
description: "Deprecated compatibility router to workspace-governor for procedure placement and SOP-sprawl control."
---

# Operating Procedure Repository Manager

Deprecated compatibility router.

Use `workspace-governor` for operating-procedure repository placement, repeated-operator-task classification, SOP-sprawl control, procedure-vs-playbook-vs-skill routing, and final placement hygiene.

This skill exists only to catch older references while they are drained. When invoked, immediately route to `workspace-governor` and preserve these expectations:

- procedure candidates must describe real repeated operator work, not one-off or hypothetical work
- procedures belong under `06. Playbooks\Operating Procedures\` only when trigger, read-first list, steps, proof, stop lines, owner surface, and next action are clear
- workflow-specific sequencing/history stays in workflow continuity notes
- durable governance rules stay in playbooks or core doctrine
- automation/runtime behavior stays in skills or script docs
- one-off lessons stay in daily memory or audit notes
- procedure repository growth must reduce ambiguity and must not become a second control plane

Do not use this skill as a separate procedure-governance authority. Do not create a second repository standard here. Do not delete or archive this skill until a reference/residue scan shows no active owner surfaces require direct `operating-procedure-repository-manager` routing and Randall separately approves removal.

## Authority Boundary

This router does not authorize destructive cleanup, archive/delete, moves/renames, config/auth/runtime mutation, cron schedule mutation, finance canon or portfolio mutation, paper/live/brokerage/account action, capital deployment, external delivery, or owner-approval inference.
