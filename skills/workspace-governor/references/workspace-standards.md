# Workspace Standards

## Root policy

Keep the workspace root strict. It should contain only:
- core operating files such as `SOUL.md`, `USER.md`, `MEMORY.md`, `AGENTS.md`, `TOOLS.md`, `FINANCE_SOUL.MD`, `Continuity Protocol.md`, `HEARTBEAT.md`, `CLAUDE.md`, `DREAMS.md`, and `Home.md`
- canonical numbered knowledge domains
- essential system or implementation folders
- the archive domain
- clearly documented generated or staged surfaces that cannot live more naturally elsewhere

Current canonical numbered review and delivery domains:
- `01. Dashboards/`
- `02. Markets/`
- `03. Portfolio/`
- `04. Research/`
- `05. Intelligence/`
- `06. Playbooks/`
- `07. Risk/`
- `08. Audits/`
- `09. Archive/`
- `10. Deliverables/` for durable human-facing deliverable packs, PDFs, workbooks, HTML exports, and retrieval indexes; review/delivery surface only, not canon, approval, external-send, customer-output, or execution authority

Current allowed non-numbered active root folders:
- `memory/` for daily notes
- `scripts/` for repeatable tooling
- `skills/` for installed or local AgentSkills
- `tmp/` for generated machine artifacts and staged render outputs
- `data/` for approved durable append-only derived state/history datasets only; each subfolder needs a README and must not store credentials or canonical portfolio authority
- `state/` for approved durable machine state such as PM cockpit registry and finance SQL canon candidate surfaces; these remain derived/proof or gated machine-canon candidates, not portfolio/trade/approval authority unless an exact gate says otherwise
- `apps/` for local application surfaces such as `apps/pm-control-cockpit`; apps remain local/review-only unless a separate exposure gate is approved
- `training/` for internal WF75 Academy/training assets; internal only, no public/customer delivery authority
- `wiki/` for durable WF88 second-brain synthesis and retrieval pages generated from validated source packets; review-only and never canon, approval, execution, customer output, model-training, or apply authority
- `schemas/` for durable local JSON/schema contracts that are shared across scripts or training assets
- `tests/` for root-level cross-script/workspace tests when placing them under `scripts/` would obscure the contract being tested
- `migration-backups/` for reversible local backup checkpoints
- `node_modules/` as a rebuildable local QA/development dependency cache only while root `package.json` owns local training QA dependencies
- `.obsidian/`, `.openclaw/`, `.clawhub/`, `.git/` for tool or repo infrastructure
- `.claude/` as a runtime/tool-settings compatibility surface; do not move, archive, or clean it without exact runtime/config approval

`templates/` is not a permanent root entitlement. Recreate it only when active finance-first templates actually exist.

Current documented root exceptions:
- `attachments/` while `.obsidian/app.json` still points `attachmentFolderPath` there, even if the folder is currently empty
- `migration-review.md` while it still has active review or retrieval value
- `GEMINI.md` as an external-process compatibility surface parallel to `CLAUDE.md`; keep route-only and do not treat it as active Veritas doctrine
- `DREAMS.md` as an OpenClaw dream diary/reference surface. Treat it as read-only bootstrap/reference material during memory flushes and cleanup passes unless Randall explicitly scopes content edits.
- `openclaw-workspace-state.json` as a small OpenClaw bootstrap/setup state file. Treat it as runtime-owned unless OpenClaw documentation proves it can be retired.
- `package.json`, `package-lock.json`, and `requirements-dev.txt` as local development/test dependency manifests; they do not grant runtime, customer, finance, external, or execution authority.
- `.backups/` as a temporary rollback/provenance surface with `README.md`; do not move whole folder, and do not move config/runtime-sensitive subtrees without exact approval
- `backups/` as a temporary rollback/provenance surface with `README.md`; do not move whole folder, and archive only retired individual backup sets after fresh proof

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
- undocumented backup folders such as `backups/`; use `migration-backups/` for active reversible checkpoints or `09. Archive/` for retired backup sets
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

## Durable derived data handling

`data/` is allowed only for durable append-only derived state/history datasets that need to survive beyond `tmp/` but still are not canonical finance notes.

Rules:
- each subfolder needs a README with authority, producer, proof, and retention posture
- no credentials, tokens, auth material, or runtime config
- no ungated portfolio mutation, ungated deployment-state mutation, trade execution, or owner-approval inference
- SQL or JSONL hits must route back to source Markdown/JSON before judgment
- current approved subfolders: `data/state-history/`, `data/fundamentals/`

## Generated artifact handling

`tmp/` is the default home for generated outputs, staging files, normalized payloads, and rendered machine views.

Examples:
- `tmp/market-state.json`
- `tmp/portfolio-config.json`
- `tmp/dashboard-data.json`
- `tmp/veritas-command-center.html`

Rules:
- generated files do not outrank canonical notes
- `tmp/` may contain Markdown sidecars only when they are generated explanations, helper-lane scratch reports, patch previews, or short human-readable companions to machine artifacts
- final audits, durable research notes, and workflow truth must be promoted out of `tmp/` to `08. Audits/`, `04. Research/`, or `06. Playbooks/Project Continuity/` as appropriate
- when a final Markdown report is promoted, keep any machine-consumed JSON/CSV/SQLite companion in `tmp/` and update durable references to the promoted note
- keep helper scripts out of `tmp/` when they are durable tooling and belong in `scripts/`
- remove or relocate stale scratch artifacts once they stop supporting an active workflow or audit trail
- entry-band HTML reports belong under `tmp/entry-band-reports/`; do not recreate a root-level `generated documents/` exception for them

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

### `10. Deliverables/`
Durable human-facing deliverable packs, exports, and retrieval indexes.

### `memory/`
Daily notes and continuity support only.

### `scripts/`
Durable automation and helper tooling only.

### `tmp/`
Generated artifacts and staged Markdown sidecars only, not final audits, long-lived research notes, workflow truth, or durable scripts.

## Cleanup checklist

1. Root sanity
- verify every root surface is canonical active, archival, generated, durable-derived, or explicitly being cleaned up
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

6. Retrieval metadata hygiene
- new major audits, workflow continuity notes, research notes, and procedures should use the lightweight `## Retrieval Notes` standard when status, owner, next action, archive posture, or key entities matter
- metadata is an index aid only; it must not overrule the note body, canonical finance ownership, or owner approval boundaries

## Full-workspace audit add-on for data-heavy operating systems

When scripts, dashboards, or retrieval depend on folder truth, recurring audits should also:
1. verify policy text matches the live root exceptions and owned surfaces
2. run `python scripts/workspace_boundary_check.py` and `python scripts/dashboard_truth_lint.py` when available
3. inspect `scripts/`, `tmp/`, `skills/`, `08. Audits/`, and root together instead of auditing only the root listing
4. flag inconsistencies between structure docs, recent audits, and the live filesystem before recommending moves
5. prefer doc-first fixes when the live exception is real but underdocumented

## Current enforcement notes

- The finance-first numbered structure above is the canonical root review order.
- `09. Archive/` is the required sink for retired root material that still deserves preservation.
- `tmp/` is the default home for rendered dashboards and other staged machine outputs.
- A root surface without an explicit policy reason should be treated as drift until proven otherwise.
