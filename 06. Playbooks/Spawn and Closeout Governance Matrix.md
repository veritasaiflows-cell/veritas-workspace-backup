# Spawn and Closeout Governance Matrix

## Purpose

Make spawn decisions, helper-lane authority, executive-summary timing, and workflow closeout rules explicit enough that major workflows do not depend on habit or guesswork.

This is the canonical spawn / closeout governing source.
Other protocol docs may keep short local summaries, but they should point here rather than compete with it.

## Core rule

Helper lanes support.
Veritas/main is the live truth surface: it interprets the workspace file layer as the durable canonical financial database, integrates evidence, judges, and closes.

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
| Model-free command | explicit deterministic command and deterministic proof both exist | exact local proof | hidden model fallback |
| Codex-native bounded | explicitly opted-in read-only work, or one exact leased implementation file | Terra low/medium bounded result | broad/multi-file implementation, Kimi/Sol override, silent eligibility expansion |
| Persistent isolated agent | bounded specialist work with fresh strict context-transport proof | Terra low/medium/high by role/scope | dispatch without valid transport proof, silent Main fallback |
| Main-session only | final judgment, shared canonical semantics, emergency truth fix, final merge / QC | direct decision, bounded edits, final synthesis | offloading final truth ownership |
| Spawn read-only | evidence gathering, audits, contradiction checks, inventory, contract challenge | findings, gap maps, review packets | queue movement, canonical note mutation, final verdict |
| Spawn distinct-output | separate artifacts can be produced without touching the same owner surface | draft docs, packet artifacts, report assets, validators, isolated code changes | competing writes on the same canonical surface |
| Blocked / operator-gated | human judgment, trust ambiguity, auth/network/destructive action, unresolved owner boundary | note updates that record the blocker | fake progress theater |

If a workflow cannot be classified cleanly, stop and default to blocked or main-session serial work until clarified.

## Single route and spawn decision tree

0. Run `python scripts\project_implementation_router.py ... --validate`; `veritas.execution_efficiency_policy.v1` is the machine owner.
1. Is there a complete deterministic command/proof contract?
   - yes -> **Model-free command**
2. Is explicit bounded Codex-native eligibility proven?
   - yes -> **Codex-native bounded**
3. Is the blocker human judgment, unresolved trust, auth/network/destructive action, or owner ambiguity?
   - yes -> **Blocked / operator-gated**
4. Is final canonical judgment, quick bounded repair, or final integration central, with an explicit Main exception?
   - yes -> **Main-session only**
5. Does a fresh strict persistent context-transport proof pass for the selected specialist?
   - yes -> **Persistent isolated agent**, read-only or distinct-output as classified
   - no -> **Blocked**; do not fall back silently to Main

## Main-session exception rule

Meaningful work may stay in the main session only when one of these is true:
- the work is quick, reversible, and bounded enough to stay under roughly five minutes
- an immediate truth fix is safer than spawning
- the work is the final merge / QC step
- spawning adds more friction than value

Substantial work expected to exceed roughly five minutes, touch multiple artifacts, require broad inspection, or need independent QA should default to a file-grounded helper lane, but not automatically to maximum thinking. Select effort by role: low for routine research/read-only audit, medium for implementation, high for hard debugging, repeated contract failures, or high-stakes trust adjudication.

If a meaningful workflow pass uses a main-session exception, record that explicitly in the continuity note or status summary.

## Post-helper continuation decision

After each helper completion, Veritas/main must choose the next state deliberately:
- **spawn next helper** when the queue has a clear bounded next action that is substantial, file-grounded, and helper-safe
- **main-session execute** when the next action is quick, reversible, and bounded
- **ask Randall** when priority, authority, scope, or human judgment is the blocker
- **close / pause** only when acceptance evidence and control-surface sync are complete or a real blocker is recorded

Ambiguity is not permission to guess the queue direction. Ask a concrete question first.

## Spawn preflight and runtime-budget rule

Before opening a spawned helper lane, the main session must make the spawn contract explicit enough that the child does not burn its runtime reconstructing context.

Minimum preflight:
1. validate the selected backend/model/thinking with `project_implementation_router.py`
2. name the objective in one sentence
3. name the exact files to read first
4. name the stop line / what not to touch
5. record expected backend/model/thinking and require actual values at closeout; mismatch blocks acceptance
6. record an explicit runtime budget in the packet, using a tool timeout only when the tool exposes one
7. require an artifact-first partial output when the work may exceed 10 minutes
8. for implementation lanes, require an early progress checkpoint within 3-5 minutes when practical
9. name the acceptance proof before launch
10. declare a workspace-relative base path and freeze no more than 6 files / 120,000 bytes / 30,000 estimated context tokens with sorted hashes and a snapshot id
11. record parent job, phase, attempt/retry identity, and the 90-second provisional incident SLA

### Narrow-packet default

After the 2026-05-29 SQL retail-grade/scaleout helper timeout cluster, the default spawn shape is a narrow packet, not a broad workstream.

Default limits:
- one child lane owns one artifact, one validator, or one read-only finding set
- first-pass read list should usually be three to six files
- implementation lanes should write or update one primary output before documentation or continuity edits
- main session should handle broad owner-note reading, final integration, and queue/continuity sync
- use `lightContext: true` and isolated context unless the current transcript is strictly required

Split instead of spawning when the proposed lane includes more than one of these in the same packet:
- broad workflow review
- script implementation
- README/documentation update
- continuity/memory update
- archive or path migration planning
- final QA/closeout synthesis

If a child times out after reading but before output, treat the next attempt as a contract shrink: fewer files, one output, earlier checkpoint, or main-session execution if the validator is coordinating shared truth.

Role-effort matrix:

| Role / task shape | Default thinking | Escalate when |
|---|---|---|
| Routine research, inventory, read-only audit, alignment check | low | evidence conflicts, high financial/trust stakes, or broad ambiguous ownership |
| Implementation, validator/script edits, workflow artifact production | medium | repeated test failures, shared-contract drift, or unclear downstream consumers |
| Hard debugging, runtime failures, auth/config diagnosis, false-green/false-red residue, trust adjudication | high | already high; narrow scope before increasing runtime |

Use `scripts/project_implementation_router.py` as route authority and `skills/veritas-model-routing-helper-lanes/SKILL.md` as the human procedure. Model-free remains model-free; bounded native and persistent helpers use Terra; Main/Terra is the default integrator; Sol is Main-only and requires an explicit escalation, challenger, or QA use case plus reason. `openai/gpt-5.6-luna` remains restricted to proven deterministic scheduled proof/status work, `openai/gpt-5.5` is fallback, and `openai/gpt-5.4` is rollback/control.

Use `06. Playbooks/Subagent Spawn Handoff Template.md` for the copyable packet.

Default runtime-budget guidance:
- quick read-only check: 900-1200 seconds
- bounded multi-file audit: 2400-3600 seconds
- broad inventory / architecture audit: 5400-7200 seconds, or split into smaller phases
- implementation pass: 3600-7200 seconds with exact validation gates

For cron `agentTurn` jobs, also set `timeoutSeconds`. For `sessions_spawn`, use a narrow contract, artifact-first checkpoints, and `sessions_yield` rather than polling.

If the task needs more than that, the contract is probably too broad. Split it before spawning.

Root-cause lesson from the 2026-05-09 finance-OS audit timeout: a broad audit with no explicit runtime budget and no artifact-first checkpoint can time out after doing useful inspection but before delivering a usable packet. Treat that as a contract failure, not a worker-quality verdict.

Runtime lesson from the 2026-05-09 SQLite artifact-index implementation spawn: a helper can have valid write/exec access and still fail with `subagent run lost active execution context` before writing the intended files. Treat that as runtime/session reliability residue. Preserve any partial inspection output, verify access separately if needed, then continue in main or relaunch a narrower lane with an early progress checkpoint.

Runtime lesson from the 2026-05-29 SQL scaleout orchestration pass: helper lanes with large inherited prompt/cache, broad file lists, and multiple deliverables can time out before producing a usable artifact even when the underlying task is bounded. Treat that as a spawn-contract failure. The corrective action is a narrow packet with light context, one target file/artifact, and a 3-5 minute checkpoint, or main-session execution for the coordinating validator.

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
- claim final closeout authority or a final canonical verdict
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

For shared/major validation, privacy/security/authority/finance semantics, or repeated failure, QC/QA requires one **independent auditor** spawned in a **fresh new session** after deterministic preflight. Micro and narrow work may close with deterministic/focused proof plus Main verification.

Meaning here:
- not the implementation lane that just did the working pass
- not a same-thread continuation pretending to be independent
- bounded to read-only audit / contradiction / gap-finding authority

The independent audit should return at minimum:
1. audit closure verdict (`complete`, `closed with follow-up`, or `blocked`) without final closeout authority
2. acceptance-proof check
3. real gaps or residue
4. stale inherited blockers or diagnoses that should now be marked superseded when live evidence overturned them
5. reopen triggers
6. one immediate next-pass recommendation
7. when useful, 1-2 bounded adjacent workflow recommendations

Detail standard:
- bounded does not mean under-explained
- each material gap should include evidence/source file, why it matters, severity, owner or affected surface, recommended fix, and acceptance proof
- each closure claim should name the exact proof that makes it safe to treat as closed
- if the audit is intentionally only a smoke check, label it as a smoke check and do not let it satisfy major closeout QA by itself

Default spawn posture for that audit:
- **Spawn read-only**
- fresh session
- explicit file-grounded handoff packet
- no queue movement, no canonical mutation, no final closeout authority

After one repair and one fresh QA rerun, another rejection returns to Main for scope/root-cause reclassification. Do not keep replaying the same frozen context through additional agents.

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
5. update the closeout sync bundle: queue top summary, recent-closures summary when present, registry row, continuity note, audit artifact, and daily memory entry
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
