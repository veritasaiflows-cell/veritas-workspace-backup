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
- `migration-backups/`
  - justified reversible-backup surface
- `data/`
  - justified durable derived-data surface for approved append-only state/history datasets such as `data/state-history/`; each subfolder needs its own README and authority boundary
- `attachments/`
  - justified while `.obsidian/app.json` still points `attachmentFolderPath` there
- `migration-review.md`
  - justified while it still holds active review or retrieval value

`backups/` is not a documented active root entitlement. Treat it as an archive/migration-backup classification decision, not as an approved permanent root folder.

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
- `10. Deliverables/` -> human-facing PDFs, Excel workbooks, HTML views, and CSV exports copied from machine/staging surfaces for retrieval
- `memory/` -> dated daily continuity only
- `scripts/` -> durable implementation and tooling
- `skills/` -> reusable AgentSkills only
- `tmp/` -> machine-generated or staged outputs
- `state/deliverables/` -> machine-readable manifest and SQLite index for `10. Deliverables/`; not canon, approval, or proof replacement
- `data/` -> approved durable append-only derived state/history datasets only; not credentials, runtime config, or canonical portfolio truth
- entry-band HTML reports now live under `tmp/entry-band-reports/`, not in a root-level generated-documents exception

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
- human-facing project deliverables -> `10. Deliverables/` through a manifest-backed publisher, while source proof remains in `tmp/`

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
4. Does it need a `## Retrieval Notes` block because status, owner, next action, archive posture, or key entities will matter later?

If yes, file it there.
If no, stop before inventing a new category.

For audits, workflow continuity notes, major research notes, and reusable procedures, follow `06. Playbooks/Operating Procedures/Retrieval Metadata and Notes Field Standard.md`. The block is an index aid only; it must not override the body of the note, canonical finance ownership, or owner approval boundaries.

## Anti-drift rules
Do not:
- create parallel navigation systems
- keep read packets as root folders
- store durable procedures in random notes when they belong in skills or governed playbooks
- keep generated artifacts in numbered human-note domains unless the workflow explicitly requires it
- leave scratch inspection material at root once its purpose has ended
- create retrieval metadata that says a note is clean, canonical, or approved when the body says otherwise
- auto-archive a note only from metadata; verify references and ownership first
- let documented policy drift behind approved runtime exceptions; update the policy text before pretending the structure is fully governed

## Structure change threshold
Before making a folder-level reorganization, require at least one of:
- repeated retrieval friction
- repeated note-placement mistakes
- more than a few files of the same durable type piling up
- proven merge value that exceeds link-churn cost

## `migration-backups/` retention policy

Purpose:
- preserve reversible safety checkpoints for meaningful structural, config, workflow, and note-layer changes
- avoid treating `migration-backups/` as a permanent junk drawer

Create a new backup set when:
- a workflow will move, archive, or delete files
- a config or control-plane change could widen blast radius
- a broad note-sync or path migration is about to run
- a rollback point would materially reduce risk

Baseline retention windows:
- high-risk structural / workflow backups: keep at least **30 days**
- normal bounded migration backups: keep at least **14 days**
- superseded scratch backups with no unique recovery value: eligible for review after **7 days**

Pruning rule:
- do not prune during the same workflow that created the backup unless the backup was obviously mistaken or duplicated
- prune only after verifying the newer canonical state is stable and no active workflow still references the backup set
- document meaningful prune decisions in the active continuity note or daily note if the cleanup materially changes rollback posture

Approval boundary:
- Veritas may create backups without asking
- meaningful pruning of backup sets should remain operator-approved or workflow-approved
- never present pruning as completion proof for a hardening pass

## `tmp/` retention policy

Purpose:
- keep `tmp/` as the governed machine-output surface, not a silent graveyard for old one-off analysis artifacts
- protect active finance artifacts, run summaries, validation outputs, workbook exports, and entry-band surfaces from cleanup theater

Keep by default:
- active machine outputs that feed dashboards, deployment surfaces, workbooks, weekly briefs, or validation
- run-chain and run-summary artifacts for the supported windows
- governed subdirectories such as `tmp/entry-band-data/` and `tmp/entry-band-reports/`
- validator outputs such as `tmp/portfolio-config-validation.json` and `tmp/tmp-cleanup-report.json`

Archive-eligible by policy:
- non-governed one-off tmp artifacts that are no longer part of the active machine-output contract
- only after they are older than **7 days** and not protected by the current keep list

Execution rule:
- use `scripts/tmp_cleanup.py` as the cleanup surface
- default posture is report-only / dry-run
- apply mode is explicit and currently intended only as an operator-gated Sunday tail via `python scripts/run_finance_refresh_chain.py sunday --cleanup`
- cleanup should archive, not silently delete

Guardrail:
- if a tmp artifact is still referenced by an active script, validator, dashboard, workbook, or continuity contract, it is not cleanup fodder
- if cleanup scope is ambiguous, defer to Workflow 14 or a fresh decision packet instead of guessing

## Current enforcement direction
- keep root strict
- keep `Home.md` as the navigator
- keep active continuity in `memory/` and `06. Playbooks/Project Continuity/`
- keep protocols and control documents clearly named in `06. Playbooks/`
- keep human deliverables in `10. Deliverables/` and their machine manifest in `state/deliverables/`
- use audits and QA notes to catch drift early

## `10. Deliverables/` policy

Purpose:
- give Randall a stable place to find PDFs, Excel workbooks, HTML views, and CSV exports without searching `tmp/`
- preserve the separation between human presentation files and machine proof files

Allowed content:
- final or current review-ready PDFs
- Excel workbooks and CSV exports meant for human review
- HTML dashboard or briefing exports meant to be opened directly
- a generated `INDEX.md` built from `state/deliverables/current-manifest.json`

Not allowed:
- JSON proof packets
- validator outputs
- source histories
- runtime config
- canonical portfolio truth
- approval records

Execution rule:
- use `python scripts\deliverables_publisher.py --write --validate`
- publisher copies files; it does not move, delete, archive, or replace `tmp/` proof
- archive writes, restores, and deletes remain separately gated
