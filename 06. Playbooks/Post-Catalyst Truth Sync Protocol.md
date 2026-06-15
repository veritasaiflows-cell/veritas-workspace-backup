# Post-Catalyst Truth Sync Protocol

## Purpose
Keep post-earnings, post-event, and post-regime note updates honest, bounded, and owner-surface-first.

This protocol exists so the workspace does not keep stale pre-event wording after the machine layer and owner notes already moved on.

## Trigger events
Run this protocol when any of the following happens:
- a tracked company reports earnings
- a named macro/policy event changes the active regime read
- a deployment-trigger state changes materially (`DEPLOYABLE NOW`, `ALMOST DEPLOYABLE`, `DO NOT TOUCH`, `BELOW STOP`, `WATCH / RESEARCH NEEDED`)
- a validator or audit finds a stale mirror phrase that can mislead operator decisions

## Sync window
- **Same day preferred** for owner surfaces
- **Within the next controlled pass** for mirrors and downstream orientation notes
- if the machine layer moved but canonical note mutation is intentionally deferred, the defer must be explicit and named rather than implied by silence

## Owner surfaces first
Update in this order:
1. owner/canonical decision surface
2. machine evidence artifact if it is stale or wrong
3. human-facing mirrors
4. downstream dashboards / orientation notes

Owner-first examples:
- deployment state -> `03. Portfolio/Execution Board.md`
- technical levels / invalidation -> `03. Portfolio/Execution Board.md`
- thesis / quick-reference thesis mirror -> `04. Research/Coverage and Watchlist.md`
- high-level mirror -> `04. Research/Coverage and Watchlist.md`
- orientation summary -> `01. Dashboards/Executive Brief.md`

## Required checks before closing a sync pass
- the owner surface no longer contradicts the current machine layer
- mirrors no longer preserve stale pre-event phrases that change the real decision
- downstream orientation notes do not continue to warn about already-cleared contradictions
- validator output is re-run when the changed surface is inside validator scope
- any intentionally unresolved residue is named with owner, reason, and next pass

## Allowed bounded wording changes
Safe post-catalyst sync changes include:
- rolling past event dates forward
- replacing stale "pending" / "unreviewed" language after review is complete
- replacing stale watch-only language after an owner surface has already promoted the state
- removing obsolete warnings from downstream orientation notes once the underlying contradiction is actually cleared

## Not allowed
Do not use this protocol to:
- widen scope into a broad thesis rewrite
- silently change canonical judgment because a dashboard implies it
- let downstream dashboards overrule owner notes
- mark a contradiction fixed before validator or owner-surface evidence supports it

## Acceptable close condition
A post-catalyst truth-sync pass is honestly closed when:
- owner surfaces reflect the current decision
- mirrors no longer contradict those owner surfaces on the changed point
- validator / acceptance checks are rerun when relevant
- any remaining residue is explicitly documented instead of lingering as hidden drift
