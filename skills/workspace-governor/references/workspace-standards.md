# Workspace Standards

## Root Policy

The root contains core doctrine, numbered knowledge domains, essential implementation folders, archive/deliverable domains, and documented compatibility exceptions.

Active numbered domains:

- `01. Dashboards`
- `02. Markets`
- `03. Alerts and Recommendations`
- `04. Research`
- `05. Intelligence`
- `06. Playbooks`
- `07. Risk`
- `08. Audits`
- `09. Archive`
- `10. Deliverables`

`03. Portfolio` is a retired tombstone only. It must not regain active canon or generated-state ownership.

Allowed implementation/state roots include `memory`, `scripts`, `skills`, `tmp`, `data`, `state`, `apps`, `training`, `wiki`, `schemas`, `tests`, and documented tool/runtime folders. Do not create a new top-level folder without a durable domain, multiple likely artifacts, and a clear owner.

## Classification

- Canonical active: current owner notes and essential operating surfaces.
- Archival: retired but useful history under `09. Archive`.
- Generated/staged: rebuildable proof or views, normally under `tmp`.
- Durable derived: explicitly owned state/history under `data` or `state`.
- Stray: unowned, obsolete, empty, or misplaced.

## Finance Placement

Active finance canon is limited to alert/recommendation preferences, triggers, guarded levels/invalidation, thesis/routing state, evidence, freshness, and non-executing recommendations.

Generated examples:

- `tmp\alert-level-freshness-controller.json`
- `tmp\alerts-recommendations-chain-midday.json`
- `tmp\finance-alert-os-digest.json`
- `tmp\finance-sql-canon-validation.json`

Do not create current-state holdings, positions, sleeves, allocations, weights, sizing, tranches, cash posture, rebalancing, simulated positions, order packages, brokerage/account state, or execution routes. Company capital-allocation quality and order backlog remain legitimate fundamental evidence.

## Generated Artifacts

Generated outputs never outrank owner notes. Human-facing durable conclusions must move to their owner domain; machine companions may remain in `tmp` when an active validator consumes them. Do not leave a final audit only in `tmp`.

## Archive Policy

Archive retired material that remains useful for history or rollback. Preserve original names when practical. Before moving, prove:

- exact identity and current owner
- no active scheduler, workflow, skill, PM, vector, checkpoint, or lifecycle dependency
- hash and rollback
- immutable history separated from current state
- post-move reference and validator results

## Naming

Use zero-padded numbered Title Case for human domains, descriptive Title Case for notes, lowercase for implementation folders, and ISO dates for daily notes. Avoid vague names, near-duplicate domains, and fake-final suffixes.

## Folder Fit

- Dashboards: orientation
- Markets: macro and market structure
- Alerts and Recommendations: active finance alert canon and operations
- Research: company/thesis evidence
- Intelligence: weekly/event synthesis
- Playbooks: workflows and procedures
- Risk: risk doctrine and escalation
- Audits: durable audits/readiness
- Archive: retired history
- Deliverables: human-facing exports
- memory: continuity
- scripts/skills: implementation
- tmp: generated/staged proof

## Cleanup Checklist

1. classify every touched surface
2. preserve current owners and history
3. update inbound references
4. keep generated material out of canon
5. keep retired material out of active routing
6. validate structure, hashes, skills, lanes, and downstream consumers
7. report remaining uncertainty honestly