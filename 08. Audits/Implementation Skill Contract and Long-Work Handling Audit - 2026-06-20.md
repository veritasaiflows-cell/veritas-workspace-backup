# Implementation Skill / Contract and Long-Work Handling Audit — 2026-06-20

**Auditor:** Veritas main session  
**Date generated (UTC):** 2026-06-21T05:03:00Z  
**Scope:** Review the workspace's implementation/long-work skill layer, how a "complete a project / implement something" request is routed, and how large/multi-surface implementation work is planned, executed, validated, and closed.  
**Authority boundary:** Review-only. No skill, playbook, config, cron, canon/portfolio, or execution mutations in this audit.

---

## Executive Judgment

The workspace has a **mature, well-layered implementation contract**. It is genuinely good: there is a single canonical long-work skill (`disciplined-implementation`), a separate model-routing skill (`veritas-model-routing-helper-lanes`), a separate spawn-packet template (`Subagent Spawn Handoff Template`), and an explicit governance matrix (`Spawn and Closeout Governance Matrix`). The boundaries are clean and recently consolidated (2026-06-21).

However, **operational friction persists** in three areas:

1. **Skill count has grown to 41 active + 1 deprecated**, exceeding the 20-skill governance trigger. The recent consolidation of long-work/model-routing/spawn mechanics helped, but further expansion should require explicit justification.
2. **The `disciplined-implementation` skill is structurally sound (Tier 1) but lacks Tier 2/Tier 3 live-workflow proof** tied to the actual steps a user would take when saying "implement this." There is no automated linter that checks whether a given main-session response actually followed the long-work contract.
3. **The "ask → plan → complete" path is implicit, not instrumented.** A user request like "implement X" is routed through the skill, but there is no single artifact or script that captures the planned-vs-executed steps, lane lease, helper packet, and closeout proof in one place. The evidence exists in scattered `tmp/` files, lane register rows, and PM packets, but integration depends on main-session discipline.

**Grade: B+** — strong design, clean separation of concerns, good stop lines, but needs better live enforcement, lower skill count pressure, and a single instrumented "project implementation" artifact.

---

## 1. Implementation Skill Inventory

### 1.1 Primary long-work skill

| Skill | Role | Status | Validation tier | Last tested |
|---|---|---|---|---|
| `disciplined-implementation` | Primary long-work implementation contract | Active | Tier 1 structural | 2026-06-21 |
| `veritas-model-routing-helper-lanes` | Model/thinking selection for helpers/cron | Active | Tier 1 structural | 2026-06-20 |
| `workspace-qa-pass` | Independent QA after implementation | Active | Tier 2 functional local proof | 2026-06-21 |
| `code-review-auditor` | Deprecated compatibility router; code/patch review moved to `workspace-qa-pass` | Deprecated | Tier 1 structural | 2026-07-03 |
| `safe-refactor-planner` | Deprecated compatibility router; refactor planning moved to `disciplined-implementation` | Deprecated | Tier 1 structural | 2026-07-03 |
| `main-session-handoff-finisher` | Deprecated compatibility router; handoff pickup moved to `project-continuity-manager`, cron blockers to `cron-automation-manager`, and closeout wording to `veritas-response-contract` | Deprecated | Tier 1 structural | 2026-07-03 |
| `automation-hardening-manager` | Automation trust gates | Active | Tier 2 functional local proof | 2026-06-04 |

### 1.2 Supporting playbooks

| Playbook | Role |
|---|---|
| `06. Playbooks/Subagent Spawn Handoff Template.md` | Copyable helper-lane packet mechanics |
| `06. Playbooks/Spawn and Closeout Governance Matrix.md` | Spawn/closeout decision authority |
| `06. Playbooks/Major Workflow Contract Standard.md` | Required sections for major workflows |
| `06. Playbooks/Workflow Closeout Artifact Standard.md` | Closeout artifact structure |
| `06. Playbooks/Automation Orchestration Protocol.md` | Orchestration posture, parallel work, QA |
| `06. Playbooks/Operating Model.md` | Finance OS control-plane boundaries |
| `06. Playbooks/Skills Governance Index.md` | Active skill catalog and deprecation triggers |

### 1.3 Skill health check

Most recent `openclaw skills check` (run during this audit):

- Total skills: 99
- Eligible: 57
- Visible to model: 57
- Available as command: 56
- Missing requirements: 0

Workspace canonical active skills: 41 + 1 deprecated fallback (`technical-chart-pass`).

The skill count exceeds the 20-skill governance trigger defined in `Skills Governance Index.md`.

---

## 2. Long-Work Contract Review

### 2.1 Contract steps (from `disciplined-implementation`)

The skill requires ten gates before/during long work:

1. Classify the task (shape, authority class, write scope, helper fit, validation budget).
2. Check cached truth surfaces before broad scans.
3. Check authority and approval boundaries.
4. Lease exact write surfaces or declare read-only/distinct-output mode.
5. Route helpers through the model-routing skill and spawn template.
6. Execute the full approved plan, not just the first step.
7. Validate with the smallest complete validator set.
8. Integrate helper output in main; helper output is untrusted until verified.
9. Update continuity only when the lane owns that surface or the result is durable.
10. Close lanes with proof artifacts, validation commands, and remaining blockers.

These gates are comprehensive and correctly sequenced.

### 2.2 Classification dimensions

The skill classifies tasks by:

- **Task shape:** implementation, audit, PM, cron, runtime-ops, finance-support, QA, continuity, routing, or mixed.
- **Authority class:** review-only, owner-gated, runtime-sensitive, finance-sensitive, external-sensitive, destructive-sensitive.
- **Write scope:** no-write, single-surface, distinct-output, shared-contract, broad multi-surface.
- **Helper fit:** main-only, one bounded helper, multiple distinct-output helpers.
- **Validation budget:** micro, narrow, shared, major.

This taxonomy is good. It prevents one-size-fits-all helper packets.

### 2.3 Stop lines

The skill correctly stops for:

- destructive cleanup
- external/public action
- auth/credential/network/startup/service mutation
- live or paper execution
- capital deployment approval
- cron schedule mutation
- portfolio/canon mutation outside approved gates

This is the right posture.

### 2.4 Cached front doors

The skill lists specific fast-route commands before broad scans:

- status card
- future-session packet
- workflow router
- PM/cron control packets
- lane register
- validator routers
- memory search

This is correct and reduces main-session drift.

---

## 3. Spawn / Closeout Contract Review

### 3.1 Execution-mode matrix

`Spawn and Closeout Governance Matrix` defines four modes:

| Mode | Use when | Allowed | Not allowed |
|---|---|---|---|
| Main-session only | final judgment, shared semantics, emergency fix, final merge/QC | direct decision, bounded edits, final synthesis | offloading final truth ownership |
| Spawn read-only | evidence gathering, audits, contradiction checks | findings, gap maps, review packets | queue movement, canonical mutation, final verdict |
| Spawn distinct-output | separate artifacts without same-owner collision | drafts, packets, validators, isolated code changes | competing canonical writes |
| Blocked / operator-gated | human judgment, trust ambiguity, destructive action | note updates that record the blocker | fake progress theater |

The matrix is clean and unambiguous.

### 3.2 Spawn handoff template

The template requires:

- Mode (read-only / distinct-output / blocked / main-only)
- Why spawn
- Long-work route / department owner
- Lane proof or read-only posture
- Stop line
- Artifact-first requirement
- Runtime budget
- Model / thinking
- Acceptance proof
- Validator budget
- Early progress checkpoint
- Context/tool budget
- Windows-safe shell reminder

This is a strong packet. Recent lessons (2026-05-29) about broad packets and missing Windows reminders are captured.

### 3.3 Independent auditor rule

The matrix and closeout standard both require an **independent spawned-session audit** for meaningful workflow closeouts. The auditor must return:

1. closure verdict
2. acceptance-proof check
3. real gaps/residue
4. stale inherited blockers to mark superseded
5. reopen triggers
6. next-pass recommendation
7. 1-2 bounded adjacent workflow recommendations when useful

This is the right QA posture. The audit we wrote earlier today (`Cron PM Canon Drift WF74 Audit`) follows this pattern.

---

## 4. How "Implement Something" Is Currently Handled

### 4.1 The implicit path today

When a user says "complete a project / implement something," the current path is:

1. Main session loads `disciplined-implementation` and `veritas-model-routing-helper-lanes`.
2. Main session checks cached truth surfaces (status card, workflow router, PM/cron packets, lane register).
3. Main session classifies the task (shape, authority, write scope, helper fit, validation budget).
4. If the task is large/multi-surface, main session leases a lane and spawns a helper using the handoff template.
5. Helper executes the bounded pass and writes proof artifacts.
6. Main session verifies artifacts, runs validators, integrates output, updates continuity if durable, closes the lane.
7. If the workflow is major, an independent auditor is spawned in a fresh session.

### 4.2 What works well

- **Clean skill separation:** long-work, model-routing, and spawn mechanics are not duplicated.
- **Explicit authority gates:** the skill stops at the right boundaries.
- **Lane leasing:** `concurrent_lane_manager.py` is used to prevent write collisions.
- **Artifact-first discipline:** helpers are told to write partial output before long runs.
- **Independent audit expectation:** meaningful closeouts require a fresh-session audit.

### 4.3 What is weak

- **No single instrumented "project" artifact.** The plan exists in chat turns and scattered `tmp/` files. There is no `tmp/project-<id>.json` that records objective → plan → lane → helper packet → executed steps → validation results → closeout proof.
- **No automated contract compliance check.** There is no script that inspects a main-session turn and reports whether the long-work contract was followed (lane leased? write scope declared? acceptance proof named? independent audit required?).
- **Skill count pressure.** 41 active skills is high. The recent consolidation helped, but further expansion should require explicit governance justification.
- **Tier 2/Tier 3 proof is thin for `disciplined-implementation`.** The skill is structurally validated, but there is no live test that runs a synthetic long-work request through the contract and checks the output.
- **Closeout artifact placement is inconsistent.** Some closeouts produce `08. Audits/Workflow Executive Summaries/...`; others produce only `tmp/` files and daily-memory entries. The standard exists, but enforcement is manual.

---

## 5. Live Evidence From Today

### 5.1 Helper lane used

- **Lane ID:** `PM::STALE-PROOF-REFRESH-2026-06-20`
- **Owner:** main session
- **Write scope:** `tmp/*` and `state/pm-cockpit-source-registry.json`
- **Status:** completed
- **Proof artifacts:** 8 files (WF78/retail/WF67 refreshes)
- **Merge required by main:** true

This followed the contract: lane leased, write scope declared, helper executed, proof produced, main verified, lane closed.

### 5.2 Independent audit produced

- `08. Audits/Cron PM Canon Drift WF74 Audit - 2026-06-20.md`
- Followed the audit/closeout standard: findings, risks, recommendations, next actions, authority boundary.

### 5.3 Control surfaces refreshed

- `tmp/pm-control-packet.json` — PM state
- `tmp/cron-control-packet.json` — cron state
- `tmp/main-session-escalation-consumer.json` — escalation state
- `tmp/control-closeout-bundle.json` — closeout validation

These are the expected proof artifacts from a disciplined pass.

### 5.4 Model-routing consolidation

Recent 2026-06-21 Skill Workshop update `disciplined-implementation-20260621-af34f457a8` formalized the split:

- Long-work contract → `disciplined-implementation`
- Model choice → `veritas-model-routing-helper-lanes`
- Spawn packet mechanics → `Subagent Spawn Handoff Template`
- Cron long-work posture → `cron-automation-manager`
- QA/closeout → `workspace-qa-pass`

This removed duplication across skills.

---

## 6. Risks

| Risk | Severity | Likelihood | Impact |
|---|---|---|---|
| Skill count (41 active) creates overlap/confusion | Medium | High | Harder to pick the right skill; Mini/cron may misfire. |
| No automated long-work contract compliance check | Medium | Medium | Main session may skip gates under pressure; drift accumulates silently. |
| No single project artifact for "implement X" requests | Medium | High | Hard to resume, audit, or prove a project was handled correctly. |
| Tier 2/Tier 3 proof for `disciplined-implementation` is thin | Low | Medium | The skill is trusted on structure, not live workflow proof. |
| Independent audit expectation is strong but manually enforced | Medium | Medium | Workflows may close without audit if main session is pressed. |
| Closeout artifact placement inconsistent | Low | Medium | Some closeouts are durable (`08. Audits/`), others are `tmp/` only. |

---

## 7. Recommendations

### 7.1 Priority 1 — Create a project implementation router script

Create `scripts/project_implementation_router.py` (or similar) that:

- Accepts a project title/description.
- Records the classification from `disciplined-implementation`.
- Captures the planned steps, lane lease, helper packet, validation budget, and acceptance proof.
- Writes `tmp/projects/<slug>-<timestamp>.json` as the single source of truth for the implementation.
- Updates the project continuity note and PM queue.
- Is read-only/proposal-only by default; does not spawn helpers or mutate state.

This would instrument the "implement something" path without removing main-session judgment.

### 7.2 Priority 2 — Add a long-work contract linter

Create a lightweight validator that inspects a completed main-session pass and reports:

- Was a lane leased if write scope was broad?
- Was a helper packet produced for substantial work?
- Was the model route recorded?
- Was acceptance proof named?
- Was an independent audit required for major workflows?
- Were stop lines respected?

Run it as part of `control_closeout_bundle.py` or `workspace-qa-pass`.

### 7.3 Priority 3 — Promote `disciplined-implementation` to Tier 2/Tier 3 proof

- Add a synthetic test case that exercises the skill's contract: a mock "implement a small validator" request.
- Verify the output includes lane lease, write scope, validation command, and closeout proof.
- Record the test in `tests/` or as a `test_disciplined_implementation_contract.py` fixture.

### 7.4 Priority 4 — Skill governance review

- Review the 41 active skills for overlap.
- Merge or deprecate candidates:
  - `code-review-auditor` could be absorbed into `workspace-qa-pass` if its scope remains narrow.
  - `safe-refactor-planner` could be folded into `disciplined-implementation` if it is only used for refactor planning.
  - `main-session-handoff-finisher` has been evaluated and deprecated as compatibility; use `project-continuity-manager` for pickup state, `cron-automation-manager` for cron-specific blockers, and `veritas-response-contract` for closeout/blocker wording.
- Update `Skills Governance Index.md` with the outcome.

### 7.5 Priority 5 — Standardize closeout artifact placement

- For major workflows, require the closeout artifact to land in `08. Audits/Workflow Executive Summaries/<Workflow N - Title>/` per `Workflow Closeout Artifact Standard.md`.
- Add a check in `control_closeout_bundle.py` or a dedicated validator.

---

## 8. Next Actions

| # | Action | Owner | Blocker |
|---|---|---|---|
| 1 | Decide whether to build `scripts/project_implementation_router.py` | Randall | None |
| 2 | If approved, design the JSON schema and PM queue integration in a narrow helper lane | Veritas main / helper | #1 |
| 3 | Add long-work contract compliance check to QA/closeout bundle | Veritas main | Design choice |
| 4 | Promote `disciplined-implementation` to Tier 2 with a synthetic contract test | Veritas main / helper | Time |
| 5 | Review 41 active skills for overlap and propose merge/deprecate candidates | Veritas main | Time |
| 6 | Standardize major-workflow closeout artifact placement | Veritas main | #1 if router owns placement |

---

## 9. Authority and Audit Trail

- No skill, playbook, config, cron, canon/portfolio, or execution mutations were performed during this audit.
- All commands were read-only or produced `tmp/*` proof artifacts.
- The only file written outside `tmp/` is this audit document under `08. Audits/`.
- `openclaw skills check` was run; it reported 99 total skills, 57 eligible/visible, 56 available as command, 0 missing requirements.

---

*End of audit.*
