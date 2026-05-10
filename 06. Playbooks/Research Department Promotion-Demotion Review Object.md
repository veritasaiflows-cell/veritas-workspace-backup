# Research Department Promotion-Demotion Review Object

## Purpose
Operator review object for promoting, holding, demoting, or removing an already tracked name under Workflow 25.

Promotion review ownership now routes through `06. Playbooks/Promotion Review Queue.md`. A lane change or deployable-state promotion requires an explicit queue row before owner-note mutation.

## Required fields
- **candidate**
- **review date**
- **review owner**
- **current tier / lane / deployment posture**
- **proposed change**
- **reason the review is being opened now**
- **thesis quality check**
- **levels / timing posture check**
- **portfolio-role competition check**
- **what stronger or weaker peers change the decision**
- **no-go condition**
- **decision** (`promote`, `hold`, `demote`, `remove`)
- **decision reason**
- **downstream mutations required**

## Minimum evidence check
Before changing a tracked name's standing, confirm:
1. the current role is explicit, not inferred
2. the proposed change affects actual capital competition or research priority
3. a stronger peer comparison exists if the case depends on relative ranking
4. timing blockers and level quality are treated honestly
5. every owner surface that would need mutation is named up front

## Default decision options
- **Promote** - stronger research or capital-competition standing is now deserved
- **Hold** - current posture remains correct
- **Demote** - weaker or less actionable than its current standing implies
- **Remove** - monitoring cost now exceeds decision value

## First live pilot
- Candidate: **GS**
- Default burden of proof: show whether GS has earned anything beyond tactical-secondary status behind JPM, rather than promoting it just because it is presently deployable-now on the board
