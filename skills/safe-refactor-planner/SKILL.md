---
name: "safe-refactor-planner"
description: "Convert safe-refactor-planner to deprecated router."
---

# Safe Refactor Planner

Deprecated compatibility router.

Use `disciplined-implementation` for low-risk refactors, helper extraction, duplication reduction, manifest migration, script reorganization, and technical-debt cleanup. The refactor-specific doctrine now lives there so implementation planning, write leasing, parity proof, release closeout, and authority boundaries stay under one owner.

This skill exists only to catch older references while they are drained. When invoked, immediately route to `disciplined-implementation` and preserve these expectations:

- name the seam, unchanged behavior, proof gate, rollback point, and deferred debt before moving code
- freeze live behavior with the smallest meaningful proof
- extract one seam at a time
- keep compatibility wrappers for live CLI, workflow, cron, or documented entrypoints
- rerun proof after each material seam
- close only after parity proof, entrypoint proof, named residue, and continuity updates are complete

Do not use this skill as a separate planning authority. Do not create a second refactor standard here. Do not delete or archive this skill until a reference/residue scan shows no active owner surfaces require direct `safe-refactor-planner` routing and Randall separately approves the removal.

## Authority Boundary

This router does not authorize destructive cleanup, archive/delete, config/auth/runtime mutation, cron schedule mutation, finance canon or portfolio mutation, paper/live/brokerage/account action, capital deployment, external delivery, or owner-approval inference.
