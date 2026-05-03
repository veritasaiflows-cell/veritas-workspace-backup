# Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers

## Objective
- Keep canonical notes fresh without letting scheduled automation rewrite judgment-heavy content unsafely.
- Use parallel agents to find stale claims, validate evidence, draft narrow patches, and QA surface impact — never to autonomously rewrite truth-layer notes.
- Define the canonical freshness patch contract and prove it on a bounded pilot only after Workflow 16A finishes its contracts.

## Current Phase
- Queued behind Workflow 16A contract completion
- Design / trust-gate definition only

## Core rule
**Freshness patch != thesis rewrite**

A freshness patch may update:
- dates
- event status
- post-earnings state
- source references
- dashboard / weekly-brief alignment wording

A freshness patch may **not** automatically:
- upgrade
- downgrade
- promote
- bench
- change deployment posture
- rewrite thesis logic
unless that change is explicitly reviewed and approved by Veritas/main.

## Problem split
Canonical-note freshness breaks into four classes:
1. mechanical date roll / elapsed-event wording
2. stale post-catalyst or post-earnings status wording
3. contradiction against owner artifacts or machine evidence
4. real thesis / posture change

Only the first two are realistic automation candidates in the near term.
Classes 3 and 4 remain human-gated unless a future hardening pass proves otherwise.

## Phase 1 - Canonical Freshness Patch Contract
### Parallel roles
| Agent | Job |
| --- | --- |
| Freshness scanner | Find stale dates, outdated earnings references, stale ratings, stale catalysts, or old macro assumptions |
| Evidence validator | Verify new evidence and check conflicts |
| Patch drafter | Draft a narrow proposed update |
| Surface-impact auditor | Check whether dashboard, workbook, trigger sheet, weekly brief, and owner notes need alignment |
| Final QA agent | Confirm the patch is narrow, reversible, and does not change judgment without approval |

### Required patch-contract fields
Every canonical freshness patch candidate must include:
- target canonical note
- exact stale claim or stale section
- why it is stale
- new evidence
- source quality
- patch scope
- judgment impact: none / possible / material
- affected surfaces
- required downstream sync
- rollback note
- verifier signoff
- Veritas/main approval required

## Phase 2 - Owner-boundary and surface-impact rules
### Candidate owner surfaces
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/Next Actions.md`
- `05. Intelligence/Event Calendar.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- selected dated dashboard notes under `01. Dashboards/`

### Candidate caution / non-owner surfaces
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`
- `02. Markets/Macro Regime Dashboard.md`

These can receive patch proposals, but they should not be auto-mutated in v1.

### Required boundary decisions
- what can become a patch proposal only
- what can be reviewed for a later gated helper
- what must remain fully manual
- how dashboard/workbook/weekly-brief sync is checked after a patch candidate appears

## Phase 3 - Gated helper posture
### Safe automation boundary
- detect stale note windows after refresh runs
- emit exact patch/checklist proposals
- classify freshness issues by type and owner surface
- generate candidate note-target packets
- optionally apply only low-risk mechanical freshness edits after explicit approval and validation in a later pass

### Still human-gated
- thesis rewrites
- portfolio posture changes
- macro-regime wording changes beyond obvious stale phrasing
- Trigger Sheet final judgment changes
- any cross-surface truth arbitration

## Phase 4 - Bounded pilot
Do not test broadly first.
Use:
- `NVDA`
- `JPM`
- `ETN`
- `GOOG` / `MSFT` post-earnings revalidation
- Oil / Hormuz / Middle East production-risk sleeve

The pilot should prove:
- stale-claim detection is useful
- patch packets stay narrow
- source quality is explicit
- surface impact is visible
- no second truth layer is created
- no autonomous thesis rewrite sneaks through under freshness language

## Schedule recommendation
- daily freshness packet after morning refresh
- daily post-close freshness packet after post-close refresh
- Sunday weekly freshness packet after weekly rebuild
- no auto-apply behavior in v1

## Required trust gates
1. approved intake packet contract from Workflow 16A
2. freshness classifier schema
3. owner-surface map
4. exact patch proposal format
5. validator proving no blocked or contradictory state is being masked
6. rollback/checkpoint rule before any gated apply helper is allowed
7. explicit Veritas/main approval requirement for anything beyond narrow freshness hygiene

## Acceptance condition
- freshness issues are classified, not just dumped
- patch proposals are exact and reviewable
- low-risk mechanical freshness edits are clearly separated from judgmental edits
- dashboard/workbook/weekly-brief sync implications are named
- no scheduled job silently mutates portfolio or thesis truth surfaces in v1
- the bounded pilot proves value before any scale-out

## Next Action
- Wait for Workflow 16A contract completion.
- Then execute Phase 1 -> Phase 2 -> Phase 3 -> Phase 4 in order.
- Stop immediately if the pilot starts behaving like a second truth layer.
