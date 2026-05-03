# Workspace Structure Protocol

## Purpose
Define where projects, playbooks, protocols, audits, generated artifacts, and supporting files belong so the workspace stays legible instead of turning into overlapping note piles.

## Core rule
Structure should follow ownership and retrieval value, not aesthetics.

Do not create new folders just to feel organized.
Create structure only when it improves repeated use.

## Root structure
The root should contain only:
- core operating files
- numbered active domains
- essential implementation folders
- archive surfaces
- documented exceptions that still have a real operational reason

### Current documented root exceptions
- `generated documents/`
  - temporary generated-surface exception because live scripts still read/write `generated documents/entry-bands/`
- `migration-backups/`
  - justified reversible-backup surface

Do **not** create a root `00/` layer.
Use `Home.md` as the top-level navigator.

## Domain ownership
- `01. Dashboards/` -> fast orientation and execution-facing summaries
- `02. Markets/` -> macro regime, watchlists, market structure
- `03. Portfolio/` -> portfolio posture, triggers, sizing, deployment state
- `04. Research/` -> company research, thesis notes, coverage work
- `05. Intelligence/` -> weekly briefs, event intelligence, monitoring surfaces
- `06. Playbooks/` -> operating methods, protocols, workflow rules, project control notes
- `07. Risk/` -> risk doctrine and constraints
- `08. Audits/` -> dated audits, QA notes, hardening reports
- `09. Archive/` -> retired but worth-keeping material
- `memory/` -> dated daily continuity only
- `scripts/` -> durable implementation and tooling
- `skills/` -> reusable AgentSkills only
- `tmp/` -> machine-generated or staged outputs

## Playbooks structure
`06. Playbooks/` is for operating doctrine and control surfaces.
It should not become a generic scratch folder.

### Keep in `06. Playbooks/` root
Use the root of `06. Playbooks/` for durable control documents such as:
- protocols
- policies
- operating models
- workflow definitions
- contracts
- checklists
- registries and active queues

Naming should make the note type obvious:
- `* Protocol.md`
- `* Policy.md`
- `* Workflow.md`
- `* Contract.md`
- `* Spec.md`
- `* Checklist.md`
- `* Registry.md`
- `* Plan.md`

### Use subfolders only when they have clear ownership
Current justified subfolders:
- `06. Playbooks/Project Continuity/` -> active project/workflow continuity notes and chain logs
- `06. Playbooks/Workbooks/` -> workbook assets and workbook-adjacent files

Do not create extra playbook subfolders unless:
- multiple durable files of the same type are accumulating
- retrieval is materially worse without the folder
- the folder will stay active over time

## Project structure
A real active project should have:
- one continuity note
- one owner
- one current phase
- one next pass
- one registry row if it remains active long enough to matter
- one chain log only if the work is genuinely multi-pass

### Project note home
- active project continuity -> `06. Playbooks/Project Continuity/`
- project audit outputs -> `08. Audits/`
- project-generated machine artifacts -> `tmp/`

## Protocol vs playbook vs audit vs script
Use this routing rule:

### Protocol
A rule set that governs behavior across many runs.
Example: `Cron Job Protocol.md`

### Playbook / workflow note
A repeatable operating method or sequence.
Example: `Independent Contractor Workflow.md`

### Project continuity note
A live pickup point for one active workstream.
Example: `Workflow 4B - Live Cron Shakedown + Run Ledger Hardening.md`

### Audit
A dated review, QA pass, or findings report.
Example: `08. Audits/<Topic> - YYYY-MM-DD.md`

### Script
Executable implementation.
Lives in `scripts/`, not in playbooks.

## File placement rules
When creating a new file, ask:
1. Is this canonical human judgment, control doctrine, generated output, or implementation?
2. Is it active or retired?
3. Does an existing governed location already fit it?

If yes, file it there.
If no, stop before inventing a new category.

## Anti-drift rules
Do not:
- create parallel navigation systems
- keep read packets as root folders
- store durable procedures in random notes when they belong in skills or governed playbooks
- keep generated artifacts in numbered human-note domains unless the workflow explicitly requires it
- leave scratch inspection material at root once its purpose has ended

## Structure change threshold
Before making a folder-level reorganization, require at least one of:
- repeated retrieval friction
- repeated note-placement mistakes
- more than a few files of the same durable type piling up
- proven merge value that exceeds link-churn cost

## Current enforcement direction
- keep root strict
- keep `Home.md` as the navigator
- keep active continuity in `memory/` and `06. Playbooks/Project Continuity/`
- keep protocols and control documents clearly named in `06. Playbooks/`
- use audits and QA notes to catch drift early
