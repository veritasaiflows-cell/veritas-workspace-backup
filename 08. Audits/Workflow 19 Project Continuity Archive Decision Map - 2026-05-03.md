# Workflow 19 Project Continuity Archive Decision Map - 2026-05-03

## Purpose

Reference-check the `06. Playbooks/Project Continuity/` folder and make explicit keep / archive decisions without fake-cleanliness claims.

## Result

Archive-now candidates were limited to the low-signal predecessor notes that no longer needed to live in the active continuity folder:
- moved to `09. Archive/Project Continuity/Command Center Chain Readiness Review.md`
- moved to `09. Archive/Project Continuity/Coverage Tier Framework.md`

The active continuity folder now contains:
- active workflow notes
- deferred/queued workflow notes
- intentionally held closed workflow notes
- intentionally held adjacent workstream notes or chain logs that still serve active references

## Classification rules used

- **keep active** -> current active workflow or still-open/deferred backlog note
- **keep intentionally held** -> honestly closed but still part of the live control-plane memory, still referenced by queue/registry/workflow notes, or still useful as an adjacent workstream note
- **archive now** -> predecessor note with low live retrieval value and no unresolved active-path dependency
- **rewrite refs then archive** -> archive-worthy, but moving it now would leave live references misleading

## Archive-now actions executed

| Note | Action | Reference-check result |
|---|---|---|
| `Command Center Chain Readiness Review.md` | archived to `09. Archive/Project Continuity/` | only one live-path reference needed rewriting inside Workflow 9; updated |
| `Coverage Tier Framework.md` | archived to `09. Archive/Project Continuity/` | no unresolved active-path references remained |

## Keep active

| Note | Why |
|---|---|
| `Workflow 19 - Playbooks Retrieval and Governance Cleanup.md` | current active workflow |
| `Workflow 15 - Script Performance and Payload Modularity Backlog.md` | real deferred backlog note, not closed history |

## Keep intentionally held - adjacent workstream / chain-log truth

| Note | Why |
|---|---|
| `Capital Deployment Readiness.md` | closed-with-follow-up lane still named in registry and reopen logic |
| `Capital Deployment Readiness - Chain Log.md` | active closeout ledger linked from registry |
| `E17 Universe Synchronization.md` | closed-with-follow-up lane still named in registry |
| `E17 Universe Synchronization - Chain Log.md` | active ledger linked from registry |
| `Excel Operating Workbook.md` | still a real adjacent workbook workstream note referenced by Workflow 5 |
| `Research Automation - News, Geopolitics, and Thesis Drift Monitoring.md` | still the named continuity home for future research-automation widening |
| `Workflow 16 - Research Automation and Canonical Freshness Hardening - Chain Log.md` | active closeout ledger |
| `Workflow 16A - Research Intake Desk and Parallel Review Packets - Chain Log.md` | active closeout ledger |
| `Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers - Chain Log.md` | active closeout ledger |
| `Workflow 17 - Sequential Workflow Contract and Skills Hardening - Chain Log.md` | active closeout ledger |
| `Workflow 18 - Spawn, Closeout, and Skills Governance Hardening - Chain Log.md` | active closeout ledger |

## Keep intentionally held - closed workflow notes still carrying live control-plane value

| Note | Why |
|---|---|
| `Workflow 4 - Sequential Chain Protocol.md` | canonical continuity record for a major control-plane workflow |
| `Workflow 4B - Live Cron Shakedown + Run Ledger Hardening.md` | still informs live cron proof posture |
| `Workflow 4C - Finance Chain Truth Sync Hardening.md` | still part of trust-hardening chain history |
| `Workflow 5 - PDF Excel Workflow Fit Pass.md` | closed-with-follow-up and still owns workbook packaging residue |
| `Workflow 6 - Coverage Tier Framework.md` | canonical successor to the archived predecessor note |
| `Workflow 7 - Sector Coverage Expansion Plan.md` | still names the bounded Healthcare pilot and later Utilities follow-on |
| `Workflow 9 - Research Department Operating Model.md` | still holds normalized desk and ownership doctrine |
| `Workflow 9A - Workspace Structure and Drift Cleanup.md` | still part of active workspace-governance history |
| `Workflow 9B - Surface Alignment and Drift Guard Hardening.md` | still owns the redundancy-cluster framing inherited by Workflow 19 |
| `Workflow 10 - Subagent Session Lifecycle Reliability Review.md` | closed history still referenced by audits and governance |
| `Workflow 11 - Coverage Admission Model.md` | still governs tracked-name add/remove semantics |
| `Workflow 12 - Macro Policy Trust Repair.md` | still the latest trust-repair control note for that lane |
| `Workflow 13 - Script and Tmp Hygiene Hardening.md` | closed recent hygiene pass still part of the control-plane history |
| `Workflow 14 - Operator Script Boundary and Lifecycle Cleanup.md` | closed recent structural pass still part of the control-plane history |
| `Workflow 16 - Research Automation and Canonical Freshness Hardening.md` | closed umbrella lane with named reopen triggers |
| `Workflow 16A - Research Intake Desk and Parallel Review Packets.md` | closed contract lane with reusable packet standard |
| `Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers.md` | closed contract lane with reusable patch standard |
| `Workflow 17 - Sequential Workflow Contract and Skills Hardening.md` | closed but now part of the live governance baseline |
| `Workflow 18 - Spawn, Closeout, and Skills Governance Hardening.md` | closed but now part of the live governance baseline |

## Rewrite refs then archive

None were left in this category after the bounded WF19 pass.
If a future continuity note becomes archive-worthy but still has live-path references, rewrite those references in the same pass or keep the note intentionally held.

## Acceptance verdict

- the low-signal predecessor notes were archived
- no unresolved active-path dependency remains from those moves
- the active continuity folder is now limited to active, deferred, queued, or intentionally held notes
- broader archive reduction beyond this point would become file-count theater unless more references or ownership value actually disappear
