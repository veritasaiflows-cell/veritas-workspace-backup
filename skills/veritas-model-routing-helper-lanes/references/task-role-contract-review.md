# Task-Role Contract Review

## Owner-Directed Same-Session Roles

When Randall explicitly directs Main-only work with named reviewer/QA models and no subagents, run each named role as its own sequential inference in the same Main session. Pin the session model to the named role's model, then verify the actual live model for that inference before doing the role's work; if the current inference is not the named model, reissue the caller-owned wake instead of claiming the role ran. Lease each role's writes as a bounded distinct-output lane, record the runtime backend distinction (for example `claude-cli/claude-opus-5` versus a requested provider path), and disclose that same-session roles are not clean-context independent review. Restore the primary Main model when the role's work ends and queue continuation through a caller-owned wake. The exception is task-scoped: it never becomes a persistent specialist, routing, or config change.

## Frozen Task-Role Contracts

When asked whether a frozen, hash-bound task-scoped role contract (for example `scripts/task_scoped_model_role_contract.py`) can represent a new owner request:

1. Read the frozen constants first — expiry window, root/task/slice ids, approval path and hash. An expired or identity-locked contract answers the headline question "no" before any consumer file is opened; do not spend turns reading router/linter/harness first.
2. Never propose editing a frozen contract module in place: any byte change breaks the approval-hash binding and write scope. The only defensible fix is a new contract instance from a fresh owner approval snapshot (new ids, new expiry, new hash).
3. Classify each blocker as intended bounded limitation versus actual defect. Exact-match role maps, a hardcoded single child backend, one frozen approval path, and Main-acceptance-role exclusion are intended fail-closed limits. Stale hardcoded values that a live resolver should own (for example the effective Main model), and missing cross-surface gates (a default route backend contradicting a task-child backend), are defects.
4. Verify "absent flag preserves default behavior" from the parser default and the default-path test, not from prose claims.
5. Deliver the smallest defensible fix proposal plus regression cases (default-unchanged, expiry boundary, masquerade/tamper set) without implementing; report the actual runtime model and no invented usage.
