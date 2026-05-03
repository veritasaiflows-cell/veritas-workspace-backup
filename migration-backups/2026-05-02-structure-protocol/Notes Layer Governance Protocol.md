# Notes Layer Governance Protocol

## Purpose
Keep the notes layer legible, durable, and easy to review without turning the vault root into a junk drawer.

## Core decision
Do **not** create a root `00/` folder.

Why:
- the workspace already has a numbered review order starting at `01. Dashboards/`
- `Home.md` already serves as the root command center
- a new `00/` folder would create a second navigation layer and likely become a catch-all bucket
- the real problem is governance and filing discipline, not missing top-level scaffolding

## Root model
The workspace root should contain only:
- core operating files (`SOUL.md`, `AGENTS.md`, `TOOLS.md`, `USER.md`, `MEMORY.md`, `Home.md`, `HEARTBEAT.md`, `Continuity Protocol.md`, etc.)
- the numbered active domains `01` through `09`
- essential implementation folders (`memory/`, `scripts/`, `skills/`, `tmp/`)
- clearly justified system or backup surfaces

If a note or artifact does not clearly belong at root, it should be filed elsewhere.

## Read-layer model
Use **notes**, not folders, for reading order.

### Entry point
- `Home.md` is the primary vault entry point

### Fast operator read stack
Default human-facing read order:
1. `01. Dashboards/Executive Brief.md`
2. `01. Dashboards/This Week.md`
3. `01. Dashboards/Next Actions.md`
4. `05. Intelligence/Weekly Positioning Review.md`
5. `02. Markets/Macro Regime Dashboard.md`
6. `02. Markets/Watchlist.md`
7. `03. Portfolio/Portfolio Snapshot.md`
8. `07. Risk/Risk Rules.md`
9. `05. Intelligence/Weekly Intelligence Brief.md`

### Read packets
If a workflow needs a special read packet:
- create a note, not a folder
- place it in the domain that owns the work
- use names like:
  - `<Topic> Read Packet.md`
  - `<Workflow> Review Packet.md`
  - `<Project> Operator Packet.md`

Examples:
- workflow/control-plane read packets -> `06. Playbooks/`
- thesis or company read packets -> `04. Research/`
- weekly operator packets -> `05. Intelligence/`

## Continuity model
Use only two continuity lanes:

### Daily continuity
- `memory/YYYY-MM-DD.md`
- raw facts, pass completion, blockers, and short state changes

### Project continuity
- `06. Playbooks/Project Continuity/*.md`
- active workflow/project objective, current state, last progress, blocker, next action

Do not create a third continuity system.
Do not create root-level session scratch notes for continuity.

## Generated vs canonical rule
- human judgment notes stay in the numbered domains
- generated machine artifacts go in `tmp/`
- audits go in `08. Audits/`
- retired material goes in `09. Archive/`

If something is machine-generated but useful for review, it still does **not** outrank the canonical note layer.

## Filing rules
When creating or moving a note, ask:
1. Is it a dashboard, market view, portfolio view, research note, intelligence note, playbook, risk rule, audit, or archive?
2. Is it active, generated, or retired?
3. Does an existing folder already fit it?

If yes, file it there.
If no, stop before creating a new top-level category.

## Anti-drift rules
Do not:
- create new root folders for temporary clarity
- use root as a staging area for read packets
- leave durable notes in `tmp/`
- leave generated artifacts in numbered human-note domains unless the workflow explicitly requires it
- keep duplicate operator surfaces alive when one canonical surface should own the job

## Current structural recommendation
The next structural gain should be:
- enforce this protocol
- keep `Home.md` as the root navigator
- continue filing continuity into `memory/` and `06. Playbooks/Project Continuity/`
- tighten existing stray root surfaces before inventing a new `00/` layer

## When to promote this into a skill
Promote this protocol into a dedicated skill only if note-layer maintenance becomes a repeated multi-step workflow with stable rules beyond what `workspace-governor` already owns.

Right now, a protocol is enough.
