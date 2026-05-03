# Spawn and Closeout Governance Matrix

## Purpose

Make spawn decisions, helper-lane authority, executive-summary timing, and workflow closeout rules explicit enough that major workflows do not depend on habit or guesswork.

## Core rule

Helper lanes support.
Veritas/main integrates, judges, and closes.

Parallel agents in the current automation posture are for:
- contract-building
- audit / QA
- contradiction review
- bounded packet prep
- distinct-output implementation when the contract is already clear

They are **not** a freeform research swarm and do not own final truth.

## Execution-mode matrix

| Mode | Use when | Allowed outputs | Not allowed |
|---|---|---|---|
| Main-session only | final judgment, shared canonical semantics, emergency truth fix, final merge / QC | direct decision, bounded edits, final synthesis | offloading final truth ownership |
| Spawn read-only | evidence gathering, audits, contradiction checks, inventory, contract challenge | findings, gap maps, review packets | queue movement, canonical note mutation, final verdict |
| Spawn distinct-output | separate artifacts can be produced without touching the same owner surface | draft docs, packet artifacts, report assets, validators, isolated code changes | competing writes on the same canonical surface |
| Blocked / operator-gated | human judgment, trust ambiguity, auth/network/destructive action, unresolved owner boundary | note updates that record the blocker | fake progress theater |

If a workflow cannot be classified cleanly, stop and default to blocked or main-session serial work until clarified.

## Main-session exception rule

Meaningful work may stay in the main session only when one of these is true:
- the edit is trivial and bounded
- an immediate truth fix is safer than spawning
- the work is the final merge / QC step
- spawning adds more friction than value

If a meaningful workflow pass uses a main-session exception, record that explicitly in the continuity note or status summary.

## Helper-lane authority rule

Helper lanes may:
- inspect
- compare
- challenge
- draft
- validate
- prepare distinct outputs

Helper lanes may not:
- publish final queue state
- resolve canonical conflicts alone
- close a workflow alone
- issue executive summaries alone
- mutate canonical finance notes unless an explicit later workflow contract permits it

## Contract-building and QA rule for automation lanes

Until an automation workflow explicitly widens scope, spawned helper lanes in that lane are limited to:
- source-bundle design challenge
- intake-packet schema challenge
- routing / promotion QA
- freshness-patch QA
- contradiction audits
- bounded draft prep

If helper output starts behaving like a second truth layer, stop the workflow immediately.

## Executive-summary gate

Do not issue an executive summary for a meaningful workflow until all are true:
1. acceptance evidence exists
2. expected helper lanes are complete or intentionally abandoned
3. queue / registry / continuity note agree on the real state
4. residual debt is named honestly
5. checkpoint decision is explicit

If one of those is missing, give a status update instead of an executive summary.

## Closeout checklist

Before closing a major workflow:
1. confirm the scope actually closed
2. confirm acceptance or blocker evidence
3. integrate helper-lane outputs
4. update queue / registry / continuity note
5. name real residual risks
6. make the checkpoint decision explicit
7. name the next pass
8. name up to two adjacent candidates when useful

## Checkpoint rule

Meaningful workflow closeout should not leave checkpoint posture implicit.
Use one of:
- checkpoint taken
- checkpoint deferred
- checkpoint not needed

Default to a checkpoint when the workflow changed:
- protocol
- skills
- automation governance
- control-plane architecture
- a large multi-file execution contract

## Next-work recommendation rule

At closeout, always name:
- one immediate next pass
- and, when useful, 1-2 bounded adjacent workflow candidates

Do not open them automatically unless the queue already approves the chain.

## Default posture for current research automation lane

For Workflow 16 / 16A / 16B:
- contract-building and QA -> spawn-safe read-only or distinct-output
- canonical judgment -> main-session only
- canonical patch proposals -> helper lanes may draft, main session approves
- canonical note mutation -> blocked / operator-gated in v1

## Anti-patterns

Do not allow:
- two writers on one canonical note
- helper lanes racing ahead of an unresolved owner boundary
- executive summary before helper integration
- queue advancement based on runtime vibes instead of evidence
- “freshness” language to hide real thesis or posture mutation
