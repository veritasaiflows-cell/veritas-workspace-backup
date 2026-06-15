# Workspace Structure Audit - 2026-05-01

## Scope

Bounded full-workspace audit focused on:
- root structure and folder policy fit
- active vs stray surfaces
- generated/staged artifact placement
- naming consistency
- current runtime / config / skills health signals
- major open workflow and trust risks already visible in the workspace

## Executive read

The workspace is usable and substantially more organized than a junk-drawer state, but it still has real structural drift.

The biggest current problems are not cosmetic:
1. trust hardening is still incomplete (`Workflow 3C` paused)
2. root-level surface discipline has drifted
3. scratch/generated material is leaking outside the clean policy boundaries
4. runtime/control-surface trust still needs skepticism even though config/skills validate

## What is in good order

- Canonical numbered domains are present and intact:
  - `01. Dashboards/`
  - `02. Markets/`
  - `03. Portfolio/`
  - `04. Research/`
  - `05. Intelligence/`
  - `06. Playbooks/`
  - `07. Risk/`
  - `08. Audits/`
  - `09. Archive/`
- Core doctrine files are present and coherent.
- `openclaw config validate` passed.
- `openclaw skills check` passed with all intended workspace/operator skills ready.
- Active model-routing docs were moved back to `gpt-5.4` for the main lane.
- `09. Archive/` exists and is being used rather than leaving old branches loose at root.

## Out-of-order / drift surfaces

### 1. Root contains policy-drift surfaces

Current root extras beyond the strict workspace standard:
- `.claude/`
- `06. Playbooks.lnk`
- `attachments/`
- `GEMINI.md`
- `generated documents/`
- `migration-backups/`
- `query`
- `state/`
- `temp-skill-inspect/`
- `templates/`

Judgment:
- some are defensible as tool compatibility or active staging
- several are still drift until explicitly governed

Highest-confidence drift:
- `query` (contains `WinDefend`) -> stray root artifact
- `06. Playbooks.lnk` -> redundant shortcut inside the workspace itself
- `attachments/` -> empty root folder
- `state/` -> empty root folder
- `generated documents/` -> generated/staged output should usually live under `tmp/`
- `temp-skill-inspect/` -> scratch inspection material still living as an active root surface

### 2. Generated/scratch material is not fully contained

Examples:
- `tmp/external-research/2026-05-01 XOM Post-Earnings Risk Pass - GPT5.md.md` -> duplicate extension / naming drift
- `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-03-tmp-cleanup/rtx_doc_builder.py`
- `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-03-tmp-cleanup/rtx_doc_builder_v2.py`
- `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-03-tmp-cleanup/rtx_fetch_ir_links.py`
- `09. Archive/Scripts and Tmp Cleanup - Archived/2026-05-03-tmp-cleanup/schedule_openclaw_audits.py`

Judgment:
- `tmp/` is being used correctly for many artifacts
- but it is also holding durable-looking helper scripts, which weakens the rule that durable tooling belongs in `scripts/`

### 3. Root policy and actual practice are slightly misaligned

Examples:
- `templates/` exists even though the standard says it is not a permanent entitlement unless actively justified
- `migration-backups/` is large and useful, but not yet clearly governed as either active infrastructure or archive-domain material
- `.claude/` exists as infrastructure but is not called out in the root standard allowlist

This is a governance mismatch more than an emergency.

### 4. Naming consistency is imperfect

Examples:
- `memory/2026-04-12 - Content Pivot.md` breaks the dominant daily-note naming convention
- `08. Audits/Workspace Audit — 2026-04-27.md` uses an em dash while most audit files use ` - `
- `08. Audits/Ticket Mismatch in scripts, dashboard and notes.txt` is useful but sits in the audit folder with weaker naming and a `.txt` extension instead of standard note naming

## Runtime / operating challenges

### 1. Trust hardening is still the main real challenge

Per `08. Audits/Workspace QA Audit - 2026-05-01.md` and `Workflow 3C` continuity:
- canonical-note mutation can still occur before trust adjudication fully closes
- `Workflow 3C — Canonical-note trust gate enforcement` is the real next hardening task

This is the highest-value unresolved issue.

### 2. Control-surface trust is still imperfect

Live status shows:
- config valid
- skills ready
- gateway reachable
- but task/issues counts are still non-zero
- session inventory remains high (`23` retained sessions)

This is consistent with the earlier conclusion: the runtime is usable, but not yet “trust blindly” clean.

### 3. Memory/index signal looks suspicious

`openclaw status` reported:
- `Memory 0 files · 0 chunks · dirty`

That does not match the visible workspace reality (`memory/` exists and contains many notes).

That may be a plugin/indexing/reporting issue rather than data loss, but it is a real audit flag.

## Opportunities

### 1. Fast cleanup wins

Low-risk cleanup candidates:
- remove `query`
- remove empty `attachments/`
- remove empty `state/`
- remove `06. Playbooks.lnk`
- fix the `.md.md` filename in `tmp/external-research/`

These are small, clear, and would improve workspace discipline immediately.

### 2. Reclassify ambiguous root surfaces

Decide and document one of these paths:
- move `generated documents/` under `tmp/` or archive it
- archive or delete `temp-skill-inspect/` if it is no longer active
- explicitly govern `migration-backups/` as retained operator infrastructure or move older snapshots under `09. Archive/`
- either justify `templates/` as active finance templates or retire it again

### 3. Tighten naming discipline

Bounded follow-up pass could normalize:
- audit filenames
- odd memory filename outliers
- nonstandard scratch artifact names

### 4. Audit/runtime follow-through

High-value next operational sequence:
1. finish `Workflow 3C`
2. then run a root-cleanup / classification pass
3. then investigate the memory-index inconsistency from `openclaw status`
4. then tackle Workflow 10 runtime/session lifecycle reliability

## Bottom line

The workspace is not broken, but it is not fully tight either.

Current truth:
- structure is mostly sound
- policy enforcement at root is drifting
- generated/scratch clutter is starting to leak across boundaries
- the biggest real risk is still trust/runtime integrity, not folder cosmetics

If you want the highest-value next move, do **Workflow 3C first**, then a **small root cleanup/classification pass**, not a giant reorganization.
