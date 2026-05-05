# Research Department Admission Review Object

## Purpose
Operator review object for a new-name admission decision under Workflow 25.

## Required fields
- **candidate**
- **review date**
- **review owner**
- **proposed lane** (`watch`, `execution`, `macro`, `speculative`)
- **portfolio role**
- **one-sentence reason for inclusion**
- **thesis status**
- **macro fit**
- **trigger condition**
- **next review condition**
- **owner note destinations**
- **required evidence still missing**
- **no-go condition**
- **decision** (`admit`, `defer`, `reject`)
- **decision reason**
- **downstream mutations required**

## Minimum evidence check
Before admitting a name, confirm:
1. the name solves a real portfolio or monitoring need
2. it has a clearer role than existing names in the same sleeve
3. thesis is specific enough to survive first contact with the note layer
4. trigger condition is explicit enough to avoid permanent vague watch-listing
5. the owner-file mutation list is known before the decision is called complete

## Default decision options
- **Admit to watch** - thesis-covered, tracked, not falsely deployable
- **Admit to speculative** - only if asymmetric upside and sizing discipline are explicit
- **Defer** - interesting, but not enough edge or role clarity yet
- **Reject** - no durable reason to spend maintenance budget on it

## First live pilot
- Candidate: **EOG**
- Default burden of proof: show why EOG deserves a tracked role versus existing energy names (`XOM`, `CVX`, `LNG`) rather than assuming more energy names automatically improve the desk
