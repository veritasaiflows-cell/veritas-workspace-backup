# Workspace Standards

## Root policy

Keep the workspace root strict. It should contain only:
- core operating files such as `SOUL.md`, `USER.md`, `MEMORY.md`, `AGENTS.md`, `TOOLS.md`, `IDENTITY.md`, `FINANCE_SOUL.MD`, `Continuity Protocol.md`, `HEARTBEAT.md`, `CLAUDE.md`, and `Home.md`
- canonical numbered knowledge domains
- essential system or implementation folders
- the archive domain
- clearly documented generated or staged surfaces that cannot live more naturally elsewhere

Current canonical numbered review domains:
- `01. Dashboards/`
- `02. Markets/`
- `03. Portfolio/`
- `04. Research/`
- `05. Intelligence/`
- `06. Playbooks/`
- `07. Risk/`
- `08. Audits/`
- `09. Archive/`

Current allowed non-numbered active root folders:
- `memory/` for daily notes
- `scripts/` for repeatable tooling
- `skills/` for installed or local AgentSkills
- `tmp/` for generated machine artifacts and staged render outputs
- `migration-backups/` for reversible local backup checkpoints
- `.obsidian/`, `.openclaw/`, `.clawhub/`, `.git/` for tool or repo infrastructure

`templates/` is not a permanent root entitlement. Recreate it only when active finance-first templates actually exist.

Do not create a new top-level folder unless all of the following are true:
- it represents a durable domain rather than a one-off task
- using an existing folder would make retrieval materially worse
- it will hold multiple notes or artifacts over time
- its status as active, archival, or generated is obvious

Avoid in root:
- stray review folders outside the numbered sequence
- empty scaffolding
- one-off diagnostics
- generated outputs placed in root when `tmp/` or a governed domain is a better fit
- duplicate domains with slightly different names

## Root classification model

Classify every top-level surface as one of these:

### Canonical active
Live operating files, approved numbered domains, and essential system or implementation folders.

### Archival
Retired branches, old templates, historical review logs, and preserved reference material that should not dilute the active review path. Archival material belongs under `09. Archive/`.

### Generated or staged
Machine outputs, rendered views, caches, and transient artifacts that are useful but not canonical. These should usually live in `tmp/` unless a documented exception is stronger.

### Stray
Anything unclassified, empty, obsolete, or sitting at root without a durable policy reason. Stray surfaces should be moved, archived, documented, or removed.

## Archive policy

Use `09. Archive/` for retired but worth-keeping material.

Archive when content is:
- from a prior operating branch
- still potentially useful for reference, but no longer active
- historically meaningful, but not part of the current review order

Archive naming guidance:
- prefer `Topic - Archived/` for folders
- preserve original filenames unless a rename materially improves clarity
- keep archive organization simple, not elaborate

Examples now considered archival rather than active root surfaces:
- prior consulting-era domain folders already preserved in `09. Archive/`
- old review folders like `Evening Review - Archived/`
- retired template sets like `Templates - Archived/`

## Generated artifact handling

`tmp/` is the default home for generated outputs, staging files, normalized payloads, and rendered machine views.

Examples:
- `tmp/market-state.json`
- `tmp/portfolio-config.json`
- `tmp/dashboard-data.json`
- `tmp/veritas-command-center.html`

Rules:
- generated files do not outrank canonical notes
- keep helper scripts out of `tmp/` when they are durable tooling and belong in `scripts/`
- remove or relocate stale scratch artifacts once they stop supporting an active workflow or audit trail
- `generated documents/entry-bands/` is a documented temporary exception while live entry-band scripts still read or write that path; do not widen the exception, and migrate it into `tmp/` only as an intentional code-path change

## Naming conventions

### Folders

Use zero-padded numeric prefixes plus Title Case with spaces for user-facing top-level knowledge folders.

Examples:
- `01. Dashboards`
- `05. Intelligence`
- `09. Archive`

Use lowercase for system or implementation folders.

Examples:
- `memory`
- `scripts`
- `skills`
- `tmp`

Do not create near-duplicates such as:
- `Research`
- `research-notes`
- `Intelligence Notes`

### Notes

Use descriptive Title Case filenames.

Good patterns:
- `<Topic>.md`
- `<Topic> - <Subtype>.md`
- `<YYYY-MM-DD>.md` for daily notes
- `<YYYY-MM-DD> <Context>.md` only when the dated artifact is intentionally separate

Avoid:
- vague names like `Notes.md`, `Ideas.md`, `Misc.md`
- fake-final suffixes like `final-final`
- inconsistent separators across similar note sets

## Folder-fit guidance

### `01. Dashboards/`
Fast orientation surfaces and short execution-facing summaries.

### `02. Markets/`
Macro regime, watchlists, sector context, and market structure.

### `03. Portfolio/`
Portfolio posture, sizing logic, deployment triggers, and rebalance records.

### `04. Research/`
Company coverage, thesis notes, and research scaffolding.

### `05. Intelligence/`
Weekly briefs, event tracking, and standing operating intelligence.

### `06. Playbooks/`
Operating methods, workflows, and process rules.

### `07. Risk/`
Risk doctrine, constraints, escalation, and read-only boundaries.

### `08. Audits/`
Audits, readiness checks, cleanup notes, and hardening history.

### `09. Archive/`
Retired branches, old templates, and preserved historical material.

### `memory/`
Daily notes and continuity support only.

### `scripts/`
Durable automation and helper tooling only.

### `tmp/`
Generated artifacts only, not long-lived notes or durable scripts.

## Cleanup checklist

1. Root sanity
- verify every root surface is canonical active, archival, generated, or explicitly being cleaned up
- remove empty dead weight
- block accidental new top-level folders

2. Review-order discipline
- keep the numbered root order intact
- move stray active content into the correct numbered domain
- move retired root content into `09. Archive/`

3. Generated-artifact discipline
- keep staged render outputs and machine payloads in `tmp/`
- move durable scripts out of `tmp/`
- remove root-level generated clutter unless policy explicitly requires otherwise

4. Naming drift
- fix vague names
- fix duplicate concepts with different labels
- preserve stable names when churn adds no value

5. Memory and continuity hygiene
- keep daily logs in `memory/YYYY-MM-DD.md`
- promote durable truths into `MEMORY.md` or operating files
- do not let raw logs become substitute doctrine

## Current enforcement notes

- The finance-first numbered structure above is the canonical root review order.
- `09. Archive/` is the required sink for retired root material that still deserves preservation.
- `tmp/` is the default home for rendered dashboards and other staged machine outputs.
- A root surface without an explicit policy reason should be treated as drift until proven otherwise.
