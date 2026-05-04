# Spawn and Closeout Governance Matrix

## Purpose

Make spawn decisions, helper-lane authority, executive-summary timing, and workflow closeout rules explicit enough that major workflows do not depend on habit or guesswork.

This is the canonical spawn / closeout governing source.
Other protocol docs may keep short local summaries, but they should point here rather than compete with it.

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

## Single spawn decision tree

1. Is the blocker human judgment, unresolved trust, auth/network/destructive action, or owner ambiguity?
   - yes -> **Blocked / operator-gated**
2. Is final canonical judgment or shared semantic interpretation central?
   - yes -> **Main-session only**
3. Is the helper output evidence, audit, contradiction, inventory, or contract challenge only?
   - yes -> **Spawn read-only**
4. Can a helper produce a distinct artifact without touching the same owner surface as another lane?
   - yes -> **Spawn distinct-output**
5. If none of the above are clearly true:
   - stop and treat the workflow as blocked or serial until clarified

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

## Independent auditor closeout rule

For any meaningful workflow closeout, QC/QA should default to an **independent auditor** spawned in a **fresh new session**.

Meaning here:
- not the implementation lane that just did the working pass
- not a same-thread continuation pretending to be independent
- bounded to read-only audit / contradiction / gap-finding authority

The independent audit should return at minimum:
1. closure verdict (`complete`, `closed with follow-up`, or `blocked`)
2. acceptance-proof check
3. real gaps or residue
4. reopen triggers
5. one immediate next-pass recommendation
6. when useful, 1-2 bounded adjacent workflow recommendations

Default spawn posture for that audit:
- **Spawn read-only**
- fresh session
- explicit file-grounded handoff packet
- no queue movement, no canonical mutation, no final closeout authority

If a meaningful workflow closes without this independent audit, record the exception explicitly and say why that lower bar was still honest.

## Executive-summary gate

Do not issue an executive summary for a meaningful workflow until all are true:
1. acceptance evidence exists
2. expected helper lanes are complete or intentionally abandoned
3. the independent spawned audit is complete or an explicit exception is recorded
4. queue / registry / continuity note agree on the real state
5. residual debt is named honestly
6. checkpoint decision is explicit

If one of those is missing, give a status update instead of an executive summary.

## Closeout checklist

Before closing a major workflow:
1. confirm the scope actually closed
2. confirm acceptance or blocker evidence
3. complete the independent spawned audit or record the honest exception
4. integrate helper-lane outputs
5. update queue / registry / continuity note
6. name real residual risks
7. make the checkpoint decision explicit
8. name the next pass
9. name up to two adjacent candidates when useful

Use `06. Playbooks/Workflow Closeout Artifact Standard.md` as the closing artifact contract.

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

Default source for those recommendations should be the independent audit closeout pass, then main-session integration decides whether to adopt them.

Do not open them automatically unless the queue already approves the chain.

## Skills governance companion rule

Use `06. Playbooks/Skills Governance Index.md` and `06. Playbooks/Skill Quality Standard.md` as the active governance surfaces for the workspace skill layer.

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
