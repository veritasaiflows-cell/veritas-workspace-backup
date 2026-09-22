# Workspace Structure Protocol

## Purpose

Keep ownership, retrieval, generated proof, and retired history unambiguous.

## Root domains

- `01. Dashboards/` — fast orientation
- `02. Markets/` — macro regime and market structure
- `03. Alerts and Recommendations/` — active finance alert and recommendation canon
- `03. Portfolio/` — retired tombstone only; never an active owner
- `04. Research/` — company, thesis, and source evidence
- `05. Intelligence/` — weekly and event synthesis
- `06. Playbooks/` — durable procedures, contracts, and workflow control
- `07. Risk/` — recommendation risk and escalation doctrine
- `08. Audits/` — durable audits and QA
- `09. Archive/` — retired history and rollback evidence
- `10. Deliverables/` — human-facing read-only exports

Implementation and state roots are `scripts/`, `skills/`, `tmp/`, `state/`, `data/`, `memory/`, `wiki/`, `schemas/`, `tests/`, `apps/`, and documented runtime folders. A root `00/` layer is disallowed; do not reintroduce it.

## Current documented root exceptions

- `migration-backups/` — retained migration rollback evidence
- `attachments/` — inbound attachment staging
- `migration-review.md` — migration/security review note

## Placement rules

- Durable human truth belongs in its numbered owner domain.
- Generated or staged JSON, SQLite, rendered views, and sidecars normally belong in `tmp/`.
- Durable machine state belongs in `state/` only under an explicit owner contract.
- Append-only derived data belongs in `data/` only with a producer, README, proof, and retention policy.
- Daily continuity belongs in `memory/`; project resume detail belongs in the project continuity owner.
- Generated artifacts never become canon or approval.

## Active finance placement

Active finance canon is limited to alert/recommendation preferences, triggers, guarded levels and invalidation, thesis and routing state, evidence, freshness, and non-executing recommendations.

Do not create current-state holdings, positions, sleeves, allocations, weights, sizing, tranches, cash posture, rebalancing, simulated positions, order packages, brokerage/account state, or execution routes. Company capital-allocation quality and commercial order backlog remain legitimate fundamental evidence.

## Archive and retirement

Before moving or archiving a surface:

1. resolve exact paths and active owner
2. search scheduler, workflow, skill, PM, vector, checkpoint, and lifecycle references
3. separate immutable history from current state
4. capture hashes and rollback
5. apply only the authorized set
6. validate destination hashes, source absence, and active-reference cleanup

Retired compatibility files must say so at the top and must not retain executable current-state routes.

## Playbooks

Keep durable protocols, policies, workflows, contracts, specs, checklists, registries, and active queues in `06. Playbooks/`. Workflow history belongs in `06. Playbooks/Project Continuity/`; repeated operator procedures belong in `06. Playbooks/Operating Procedures/` only when they have a real owner, trigger, proof, and stop lines.

## Validation

After material structure changes, run the smallest relevant owner validator, active-reference scan, archive/hash verification when applicable, lane validation, and `openclaw skills check` after skill changes.
