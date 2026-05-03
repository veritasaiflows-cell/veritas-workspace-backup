# Workflow Closeout Artifact Standard

## Purpose

Define the minimum closing artifact structure every major workflow should produce so closure does not depend on discipline alone.

## Required closeout artifacts

Every major workflow closeout should update or produce these, unless one is explicitly not applicable:

1. **Continuity note update**
   - closure state or closed-with-follow-up state
   - acceptance evidence
   - checkpoint decision
   - named residue
   - next pass or reopen trigger
2. **Chain-log entry**
   - dated pass entry
   - what was delivered
   - validation evidence
   - checkpoint posture
   - residue / reopen triggers
3. **Registry update**
   - current phase or closed state
   - QC complete status
   - next pass
4. **Queue update**
   - closed item state
   - next active or next queued item
5. **Named residue**
   - real remaining debt, not hidden caveats
6. **Named reopen triggers**
   - what future condition would justify reopening the workflow

## Minimum chain-log entry template

```md
## YYYY-MM-DD - <Pass name>
- Outcome:
- Delivered:
- Validation:
- Checkpoint posture:
- Residue:
- Reopen triggers:
- Next pass:
```

## Closure labels

Use one of:
- **Complete** -> acceptance evidence exists and no active follow-up remains inside the workflow scope
- **Closed with follow-up** -> workflow scope is done, but named residue or later reopen triggers remain outside the closed scope
- **Blocked** -> scope not complete; the blocker is explicit

Do not use soft language that hides which of those is true.

## Commit checkpoint obligation

If the workflow changed:
- protocol
- skills
- automation governance
- control-plane architecture
- or a meaningful multi-file execution contract

then one of these must be explicit before the next major workflow opens:
- checkpoint taken
- checkpoint deferred with reason
- checkpoint not needed with reason

For high-trust workflow chains, the default expectation is **checkpoint taken**.

## Cross-surface honesty rule

A workflow is not honestly closed if:
- the continuity note says complete but the queue still lists active work
- the registry still shows an unresolved current phase
- the chain log has no validation evidence
- the next workflow opens on an uncommitted unstable baseline despite a required checkpoint

## Where this standard is used

Use together with:
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
