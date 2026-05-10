---
name: safe-refactor-planner
description: Plan and execute low-risk refactors in the OpenClaw workspace without behavior drift. Use when extracting helpers, reducing duplication, moving hard-coded chains into manifests, reorganizing script structure, or paying down technical debt while preserving outputs, proof gates, and rollback posture.
---

# Safe Refactor Planner

Refactor only when the seam is real and the proof can keep up.

## Read First

Read only what the refactor touches, but default to:
- the current owner file
- the workflow note that justifies the refactor
- the acceptance harness or validator
- one downstream consumer
- `TOOLS.md` when path, packaging, or runtime posture matters

## Plan First

Before moving code, name:
1. the seam
2. the behavior that must stay unchanged
3. the proof gate
4. the rollback point
5. the intentionally deferred debt

If you cannot name the seam cleanly, do not refactor yet.

## Preferred Refactor Pattern

1. freeze the live behavior with the smallest meaningful proof
2. extract one seam at a time
3. keep compatibility wrappers when the CLI or workflow entrypoint is live
4. move configuration or manifests out of hard-coded logic only when parity can be shown
5. rerun proof after each material seam, not only at the end

## Good Refactor Targets

- duplicated state-normalization helpers
- hard-coded chain definitions that belong in manifest data
- repeated freshness checks
- brittle summary-shape adapters
- path or owner logic repeated across scripts

## Bad Refactor Targets

- broad renames without proof
- cleanup passes that mix behavior changes with structure changes
- moving ownership across files without updating continuity and validators
- abstracting code just to look cleaner

## Closeout Rule

A refactor is not closed until:
- parity proof exists
- the entrypoint still works
- residue is named
- continuity notes reflect the new owner surface

## Output Format

Return in this order:
- refactor goal
- seam plan
- proof gate
- changes made
- parity result
- deferred debt
