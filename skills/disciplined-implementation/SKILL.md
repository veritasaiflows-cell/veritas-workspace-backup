---
name: disciplined-implementation
description: Disciplined implementation for OpenClaw workspace code and automation. Use when adding or changing scripts, validators, manifests, chain steps, tests, or workflow code that needs acceptance contracts, smallest-diff edits, adjacent-consumer scans, proof before closure, and continuity or control-surface updates.
---

# Disciplined Implementation

Build the smallest real fix that closes the actual contract gap.

## Read First

Read only what the pass needs, but default to:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- the owning workflow or continuity note
- the changed file
- the nearest upstream producer and nearest downstream consumer when shared vocab, JSON shape, freshness metadata, or manifests are involved
- the smallest useful validator or acceptance harness

## Contract

Before editing, make these explicit:
1. the real defect or requested behavior
2. what file owns the change
3. what must not change
4. what proof will count
5. what adjacent consumer can silently drift

If any of those are unclear, inspect before patching. Do not guess.

## Implementation Procedure

1. Reconstruct the live contract from code and owning workflow notes.
2. Prefer the smallest meaningful diff.
3. Patch the owner first, then scan adjacent consumers, validators, ranking maps, fallback paths, and summaries.
4. If a shared state label, manifest field, or trust/freshness field changes, update at least one adjacent acceptance path in the same pass.
5. Add or tighten proof only where it materially reduces fake-green risk.
6. Re-run the smallest honest verification set before claiming closure.
7. Update continuity or control surfaces only after proof is real.

## Default Proof Ladder

Use the smallest set that proves the claim:
- direct inspection for simple text/routing fixes
- `python -m py_compile ...` for Python syntax safety
- targeted script run for producer behavior
- adjacent consumer or validator run for contract propagation
- acceptance harness or chain run for workflow-level closure

Do not stop at compile-only when runtime proof is practical.

## Stop Lines

Stop and reassess when:
- the patch widens scope beyond the stated contract
- the fix depends on stale artifacts you did not refresh
- a shared contract changed but no downstream proof exists
- the runner says success but the output artifact still contradicts the claim

## Control-Surface Rule

If the work closes or materially changes a workflow state:
- update the owning continuity note
- update the queue or registry only after proof
- keep wording honest about residue and next pass

## Automatic Improvement Capture

After any coding, script, validator, manifest, or workflow-code pass, check whether the session exposed a reusable failure pattern or proof gap.

If yes, harden one of these before closure when safe:
- the nearest acceptance harness or validator
- this skill's procedure
- the owning script contract / README
- the live queue item with owner, next pass, and acceptance criteria

If the next step is ambiguous, ask a concrete question instead of guessing the coding direction.

## Output Format

Return in this order:
- implementation goal
- files changed
- proof run
- remaining residue
- next workflow action
