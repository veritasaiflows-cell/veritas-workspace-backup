---
name: "workspace-governor"
description: "Govern workspace structure, active ownership, archive boundaries, and cleanup proof."
---

# Workspace Governor

## Purpose

Keep the workspace coherent, minimal, and retrievable. Use for root policy, folder placement, active-versus-retired ownership, generated-artifact placement, safe moves, and cleanup proof.

Read `references\workspace-standards.md` when folder policy or cleanup details matter.

## Core Boot Owners

- SOUL owns identity, mission, and hard boundaries.
- AGENTS owns startup, orchestration, action boundaries, and continuity triggers.
- USER owns stable Randall preferences and authority boundaries.
- TOOLS owns environment and runtime-route facts.
- Skills and playbooks own procedures.
- MEMORY and daily memory own continuity, not operating authority.

Keep core files thin. Preserve constitutional rules in core and implementation steps in owner skills.

## Placement

- durable human truth belongs in the numbered owner domain
- generated/staged JSON, SQLite, rendered views, and sidecars belong in `tmp`
- final audits belong in `08. Audits`
- retired but valuable material belongs in `09. Archive`
- durable machine state belongs in `state` only under an explicit owner contract
- append-only derived datasets belong in `data` only with a README, producer, proof, and retention policy

Generated artifacts never outrank canon or owner approval.

## Active Finance Domain

`03. Alerts and Recommendations` owns active alert profile, trigger policy, guarded bands/invalidation, and operations routes. `03. Portfolio` is a retired tombstone only. Do not recreate active portfolio, paper, deployment, sizing, order, or account-state files in either active notes or generated current-state families.

## Moves And Archive

Before a rename, move, or archive:

1. resolve exact paths
2. search inbound references
3. verify current owner and scheduler/skill consumers
4. distinguish immutable history from active state
5. capture hashes and rollback
6. apply only the authorized set
7. validate destination hashes, source absence, and active-reference cleanup

Never reorganize for aesthetics. Preserve stable names when they are adequate.

## Procedure Governance

Put repeated operator steps under `06. Playbooks\Operating Procedures` only when the task is real, repeated, owner-backed, proof-backed, and has stop lines. Workflow history belongs in continuity notes; runtime behavior belongs in skills/scripts; one-off lessons belong in memory or audits.

## Stop Lines

Stop for unclear ownership, doctrine conflict, destructive scope without authorization, active references, missing rollback, config/auth/network/service implications, credentials, external delivery, customer data, accounts, money, capital, or execution.

## Proof

Use direct inspection plus the smallest relevant validator. Run `openclaw skills check` after skill changes, boot-surface guard after core changes, lane validation after material writes, and archive/hash verification after moves.

## Closeout

State the governance decision, changed placement, active owner, preserved history, proof, rollback, unresolved blocker, and next safe action.

## Manifest-Bound Archive Microbatches

For a generated-residue archive microbatch, freeze each proposed row with its source path, SHA-256, exact byte count, destination, original restore target, reference result, and retention status. Make the mover verify the declared hash and byte count during preflight and again immediately before the filesystem move; reject an existing destination rather than renaming or overwriting it. Record matching manifest, source, and destination hashes after each move. Before any retention packet is accepted, complete one byte-identical drill from archive to its original restore target and back to the identical archive path. Classify the packet as retention-ready—not delete-ready—until per-file origin/replacement proof, an applicable integrity rule, a retention rule, a frozen deletion manifest, and a separate exact deletion approval exist.
