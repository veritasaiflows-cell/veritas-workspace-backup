# Procedure Classification Rubric

## Purpose
Decide what kind of operating document a new item should become.

## Use this rule first
If a note does not clearly reduce operator ambiguity, do not promote it into the procedure repository yet.

## Document classes

### Procedure
Use when the operator needs a repeatable step path.
A procedure should answer:
- what triggers it
- what to read first
- what to run
- what proof counts
- what stop lines apply
- what to do next

### Protocol / governance standard
Use when the note defines system-wide rules, boundaries, or authority posture.
Examples:
- orchestration rules
- cron design rules
- workflow closeout rules

### Contract / spec
Use when the note defines an input/output shape, allowed claims, trust fields, or a machine/human boundary.
Examples:
- packet contracts
- summary contracts
- routing contracts

### Workflow continuity note
Use when the note tracks one numbered workflow through phases, residue, and next pass.
Do not convert workflow history into a procedure unless the operating pattern clearly repeats.

### Audit
Use when the note evaluates whether a system, workflow, or artifact met its contract.
Audits prove or challenge reality; they do not become procedures by themselves.

### Skill
Use when the repeated work should guide the assistant directly during future execution.
Create or expand a skill only when:
- the task repeats enough to justify dedicated instructions
- a procedure note alone is not enough
- the scope can stay narrow and stable

## Routing shortcuts
- repeated operator steps -> procedure
- global operating rule -> protocol / governance standard
- schema or claim boundary -> contract / spec
- one workflow's progress -> continuity note
- validation verdict -> audit
- repeated assistant execution pattern -> skill

## Stop lines
Do not create a new procedure if:
- the note is mostly workflow history
- the task is still unstable or hypothetical
- the procedure would duplicate an existing protocol, skill, or workflow note
- the note would become a second control plane
