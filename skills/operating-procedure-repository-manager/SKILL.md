---
name: operating-procedure-repository-manager
description: Build and maintain the operator-facing procedure repository for the Veritas OS. Use when promoting repeated operator work into a stable procedure, deciding whether content belongs in procedures vs playbooks vs skills, tightening operator runbooks, or preventing SOP sprawl from becoming a second control plane.
---

# Operating Procedure Repository Manager

## Purpose

Keep the operator-facing procedure repository classified, indexed, and bounded without letting it turn into shelfware, workflow history, or a duplicate governance stack.

## When to Use

Use this skill when:
- repeated operator work should become a stable procedure
- the repository needs clearer classification or indexing
- a workflow closes and leaves behind a reusable operating pattern
- it is unclear whether something belongs in a procedure, a playbook, a workflow note, or a skill
- the operating-procedure repository needs an audit or overlap/gap pass

## Read First

Read only what the pass needs, but default to:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- `06. Playbooks/Operating Model.md`
- `06. Playbooks/Operating Procedures/README.md`
- the candidate procedure note or owning workflow/skill/playbook
- any audit or continuity note that proves the procedure is real

## Contract

Before editing, make these explicit:
1. what repeated operator task is real now
2. what proof makes it a procedure instead of an aspiration
3. who owns the underlying truth surface
4. where the procedure should live
5. what should stay out of the procedure

Do not write procedures for work that is still hypothetical, unstable, or only happened once without a likely repeat.

## Routing Rules

- operator-facing repeated steps -> `06. Playbooks/Operating Procedures/`
- workflow-specific sequencing/history -> workflow continuity notes
- durable governance rules -> playbooks / core doctrine
- automation/runtime behavior -> skill or script docs
- one-off lessons -> daily memory or audit notes

## Repository Rules

- procedures must stay operator-facing
- procedures must name trigger, read-first list, steps, proof, stop lines, and next action
- procedures must link back to the owning workflow / playbook / skill when authority lives elsewhere
- procedures must not silently outrank canonical owner notes or governance docs
- prefer one clean procedure note per recurring task rather than many overlapping variants
- default to tightening the index, classification rubric, or ownership map before creating a broad new governance skill

## Procedure Quality Bar

A procedure is ready only if it:
- describes a real repeated task
- has an identifiable owner surface
- has explicit stop lines
- points to proof or validation
- reduces operator ambiguity instead of adding another layer to inspect

## Stop Lines

Stop and reassess when:
- the procedure duplicates a workflow history note
- the procedure tries to own truth that belongs to canonical notes or governance docs
- the task is still too unstable to standardize
- the repository starts expanding faster than the real operating need
- a new skill seems easier than fixing classification, retrieval, or indexing drift

## Output Format

Return in this order:
- procedure goal
- repository location
- files created or updated
- proof the procedure is real
- what stayed outside the repository
- next procedure candidate
