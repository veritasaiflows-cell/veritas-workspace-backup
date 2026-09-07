# Continuity Protocol

## Purpose

Preserve enough verified context to resume work without turning memory into a second source of truth. This file is the thin routing contract; detailed procedure lives in `memory-continuity-manager` and `project-continuity-manager`.

## Canonical Layers

- `memory/YYYY-MM-DD.md`: chronological outcomes and compact pickup pointers
- `MEMORY.md`: curated durable decisions, preferences, and lessons
- workflow state/capsules and exact owner notes: current operational truth
- `06. Playbooks/Project Continuity/` or an existing owner note: resumable project state that needs a dedicated checkpoint
- generated packets/indexes: routing and proof only, never authority or canon

Use one home per fact. Link to proof instead of copying full logs, packets, research, or canonical state into memory.

## Startup And Recall

Use the Startup Truth Index and current resume/active-lane pointers before broad scans. Then take only the relevant low-cost route:

- Prior decision, continuity, person, date, or todo: `memory_search`, then bounded `memory_get`; verify current claims against live owners.
- Code, workflow, skill, or document relationship: check Graphify health, then use the smallest relationship lookup; verify edges against current source/owners.
- Current operational, finance, approval, or execution truth: open the exact owner artifact or validator directly.
- Specialized or deferred tool: read its owner `SKILL.md` and exact linked reference before use; `TOOLS.md` plus `openclaw-operator`'s route map own workspace command routing.

Memory, graphs, packets, and indexes route evidence only. If memory retrieval is partial/unavailable, or a graph is stale/missing/noisy, disclose the degradation and use dated memory, workflow capsules, `rg`, and exact owners instead. Never make graph loading mandatory startup work or invent an unreferenced tool capability/flag.

## Resume Contract

A resume checkpoint identifies the exact owner, state, next action, hashes/lease when applicable, proof, and stop line. Stop on ambiguous multiple pickups, stale or missing lease/identity, hash drift, expired checkpoint, or consumed/invalid receipt. A resume pointer routes work; it never restores authority or proves execution.

## Writing Rules

- Append to the canonical daily file; do not create timestamped daily variants.
- Promote only durable lessons to `MEMORY.md`.
- Keep project checkpoints compact: current state, changed state, blocker, next action, proof, and owner gate.
- Do not use memory to authorize capital, execution, accounts, finance/canon mutation, cron changes, runtime/config changes, external action, or destructive cleanup.
- After meaningful work, update only the smallest correct continuity owner.

## Hygiene

Avoid duplicate H1s, repeated topic sections, stale status claims, parallel pickup notes, and embedded raw command/tool logs. Memory routes to current proof; it does not outrank it.
