# Skills and Protocols Audit — 2026-05-04

**Scope:** All 20 active skills + Cron Job Protocol, Automation Orchestration Protocol, Major Workflow Contract Standard, Skill Quality Standard
**Auditor:** Claude (independent review layer)
**Trigger:** Pre-WF25 entry QC pass; /effort xhigh

---

## Part 1 — Skill-by-Skill Findings

### Group A: Finance Analysis Pass Skills

**`veritas-macro-pass`** — Solid. Evidence hierarchy, regime language, confidence rules, portfolio-implication requirement are all correct. No material gaps. Reads `tmp/market-state.json` and `tmp/dashboard-validation.json` correctly.

**`veritas-fundamental-pass`** — Best-structured analysis skill. The data-quality scorecard that forces confidence caps based on coverage/conflicts/freshness is the strongest feature in the finance skill set. No material gaps.

**`veritas-technical-pass`** — Strong. The four-state model (Deployable/Blocked/Repair mode/Watch-only) is explicit, each state has clear use conditions, and "Repair mode" is correctly distinguished from "Blocked." Board-sync scope clearly defined.

**`technical-chart-pass`** — Concrete vocabulary mismatch with `veritas-technical-pass`. Uses {Ready now / Close / Bench / Avoid for now} while the vault's canonical board state uses {Deployable / Blocked / Repair mode / Watch-only}. The governance index acknowledges the overlap and calls it "acceptable" — but the `technical-chart-pass` description includes "converting a thesis or watchlist into an execution-aware technical sheet," which is board-sync territory. Anyone using it for that purpose gets state labels that don't map to the Technical Entry and Invalidation Sheet vocabulary. Silent translation failure risk.

**`veritas-positioning-pass`** — Good. Three-pillar model (macro/fundamental/technical) is explicit. "Protect capital first" is correctly prioritized. **Gap:** `tmp/deployment-readiness-surface.json` is missing from the primary input list. This artifact has been written by every post-close chain run since CDR Phase 3 (2026-05-03). It directly encodes whether tracked names are near-deployment, blocked, or fail-closed. A positioning pass that doesn't read it operates without the machine-layer deployment signal.

---

### Group B: Workflow/Process Skills

**`veritas-post-earnings-sync`** — Strongest skill in the set. The closure-state model (Reported → Interpreted → Synced → Closed with follow-up) prevents fake completion. The "do not update Monday Game Plan.md" defensive null-reference guard is a good pattern. No material gaps.

**`veritas-portfolio-update`** — Strong. Synchronized update order (Technical→Execution→Portfolio→Watchlist→Orientation) is explicit and correct. "No silent sync" governance rule is the right posture. **Gap (same as positioning pass):** `tmp/deployment-readiness-surface.json` is absent from the primary input list. The skill can sync the board without seeing the machine's current deployment-readiness verdict.

**`veritas-weekly-brief`** — Good. Sunday chain inputs are well-defined. "Do not act like the weekly process starts from a blank slate" is correct. **Same gap:** `tmp/deployment-readiness-surface.json` is not in the primary input list, but it is a live Sunday chain output.

**`veritas-pdf-brief`** — Solid packaging layer. Trust and disclosure rules are concrete (written date, as-of date, trust grade, stale/manual dependencies). The "note layer wins over staged machine output" posture is correct. No material gaps.

**`veritas-investment-deck`** — The weakest finance skill. Has no `Read first` / input artifact list, no verification gate, and no trust/disclosure requirements on the deck output. The workspace evidence standard requires explicit trust grade, data as-of date, and stale/manual dependency labeling in any decision-grade output. A deck built from this skill could polish uncertainty out of the output — inconsistent with the "no fake green states" rule and with the PDF brief standard. Needs a disclosure section.

---

### Group C: Workspace Infrastructure Skills

**`workspace-governor`** — Concise and operational. The `references/workspace-standards.md` link is the right architectural choice (skill stays thin, standards live in a reference file). No gaps.

**`workspace-qa-pass`** — Strong QA framework. Five QA lenses are concrete. "Do not act like the implementation lane defending its own patch" is the defining feature. **Gap:** When used to audit *skills specifically*, the instruction to "read one or two strong local skills to match workspace style" is circular — if skills are the audit target, you're anchoring the standard to the thing being audited. Needs a specific override for skills-focused QA passes: read `Skill Quality Standard.md` and `Skills Governance Index.md` instead.

**`memory-continuity-manager`** — Solid. Routing rules are clear, daily-note discipline is correct. **Minor gap:** Routing rules say durable user preferences belong in `USER.md or MEMORY.md`, but `USER.md` does not appear in the "Files This Skill May Edit" list. The skill correctly routes a lesson to `USER.md` but the edit manifest excludes it — inconsistency.

**`project-continuity-manager`** — Appropriately thin. Anti-patterns section is the right framing. No gaps.

**`veritas-self-improvement`** — Excellent framework. Routing matrix, promotion rules, and audit-to-contract rule are all strong. **Gap:** When the skill decides to create or update a skill (via the "Skill creation trigger" section), it doesn't reference `Skill Quality Standard.md` or `Skills Governance Index.md`. The governance check ensuring a new skill meets the minimum quality bar and doesn't push count over 20 is missing from the trigger logic.

---

### Group D: Automation/Infrastructure Skills

**`automation-hardening-manager`** — Good architecture guidance. Safe-automation preference order (stable script output → stable artifacts → review surfaces → gated helpers → selective autonomous maintenance) is the right progression. **Gap:** The "Mechanism Choice" section lists `TaskFlow` as an option. TaskFlow does not appear in the Automation Orchestration Protocol, is not documented in any workflow note, and shows no evidence of being a live mechanism in this workspace. An operator following this skill could attempt to route work to a mechanism that doesn't exist.

**`cron-automation-manager`** — Good. Correctly defers to `Cron Job Protocol.md` rather than duplicating it. The research/freshness automation gate ("do not schedule until source bundle, owner layer, review window, stop lines, canonical mutation posture are explicit") is correct. **Gap:** WF24's primary output was `Cron Job Retrofit Checklist.md` — the tool for auditing existing jobs against the run-packet contract. This skill is the natural home for cron-job audit work but doesn't reference the checklist.

**`openclaw-operator`** — Clean and precise. Classification rule table is exactly right. "Validate after edits instead of assuming success" is enforced at every step. No material gaps.

**`openclaw-troubleshooter`** — Good diagnostic protocol. The "take the safe non-destructive forward fix before ending at diagnosis" rule from 2026-05-04 is correctly embedded. Config-inspection sequence is explicit and correct. No material gaps.

**`ic-swarm-orchestrator`** — Most fragile skill. Three concrete issues:

1. **Duplicate model routing that will drift.** The fallback order names `gemini -m gemini-3.1-pro-preview -p ...` and `claude -p ...` as specific CLI invocations. The Automation Orchestration Protocol already contains the canonical IC routing logic and fallback order. The skill maintains a parallel copy that will diverge. It should defer to `Automation Orchestration Protocol.md` for lane routing.

2. **`ACP harness lane` is undefined.** The fallback order says "ACP harness lane (if available)" but `ACP` is not defined in any workspace file — not in protocol docs, not in AGENTS.md, not in TOOLS.md.

3. **Effort posture is too vague.** "Hard judgment/trust decisions: Claude `--effort high` (or higher when needed)" doesn't name which effort levels are available. Specific effort-level references should be grounded in the live environment or deferred to the orchestration protocol.

---

## Part 2 — Cross-Skill Coherence Findings

**Finding 1 (Critical): State vocabulary mismatch — `technical-chart-pass` vs `veritas-technical-pass`**

`veritas-technical-pass`: Deployable / Blocked / Repair mode / Watch-only
`technical-chart-pass`: Ready now / Close / Bench / Avoid for now

The Technical Entry and Invalidation Sheet uses the `veritas-technical-pass` vocabulary. The governance index says this is "acceptable because the generic-fallback vs canonical-Veritas distinction is already documented" — but the `technical-chart-pass` description says it's good for "converting a thesis or watchlist into an execution-aware technical sheet," which directly overlaps board-sync use cases. Anyone who uses the wrong skill for a board-sync pass produces state labels that the downstream portfolio infrastructure can't interpret consistently.

**Finding 2 (High): `tmp/deployment-readiness-surface.json` missing from three skills**

`veritas-portfolio-update`, `veritas-weekly-brief`, and `veritas-positioning-pass` all list primary input artifacts but don't include `tmp/deployment-readiness-surface.json`. This artifact is written by every post-close chain run since CDR Phase 3 (2026-05-03). It directly encodes whether tracked names are near-deployment, blocked, or fail-closed. Not reading it means these skills operate without a live machine-layer deployment signal.

**Finding 3 (High): `veritas-investment-deck` has no trust disclosure requirement**

Every other output-facing skill requires disclosure of trust grade, as-of date, stale/manual dependencies, and validation warnings. `veritas-investment-deck` has none. A deck produced by this skill could polish uncertainty out of the output — explicitly prohibited by the "no fake green states" rule in CLAUDE.md and inconsistent with the PDF brief standard.

**Finding 4 (Medium): Skill count is exactly at the governance trigger threshold**

The no-skill-sprawl rule fires when count exceeds 20. The current count is exactly 20. The next skill creation decision must go through the governance matrix. Before adding one, the `technical-chart-pass` deprecation decision should be made to create headroom.

---

## Part 3 — Protocol Layer Assessment

**`Cron Job Protocol.md`** — Excellent. WF24 hardening is thorough. Run-packet contract, symmetry standard, response-contract rule, spawn recommendation rule, validation sequence, proof-run contract, failure/skipped-run rule — all explicit. "A job is not real because it was created. It is real after proof" is the right posture.

**`Automation Orchestration Protocol.md`** — Comprehensive and canonical. Main-lane reserve rule, IC routing, IC completion handshake, runtime proof rule, and executive-summary gate are all strong. Correctly labels Claude/Gemini lane postures as "operator-maintained" rather than permanent truth.

**`Major Workflow Contract Standard.md`** — Well-structured. Required sections, acceptance gates, independent-audit expectation, and commit checkpoint obligation are explicit. The commit checkpoint obligation ("the workflow should not open the next major lane on an unstable uncommitted baseline") is directly relevant to the WF24 main-file-is-untracked finding.

**`Skill Quality Standard.md`** — The tiered validation model (structural check → functional proof → live workflow proof) is the right approach. One gap: the standard calls for a validation tier assignment per skill, but the governance index only records a date and method. All 20 skills show the same "2026-05-03 | openclaw skills check" entry, which means the index can't distinguish Tier 1 structural checks from Tier 2+ validated skills. No skill in the active set has a recorded Tier 3 (live workflow proof) validation, including the core workflow skills that drive real board state.

---

## Part 4 — Ranked Recommendations

### Critical — Fix before next major workflow execution

**1. Add `tmp/deployment-readiness-surface.json` to `veritas-portfolio-update`, `veritas-weekly-brief`, and `veritas-positioning-pass`**

Highest-priority correction. Add to the `Primary inputs` / `Before starting` lists of all three skills. CDR Phase 3 landed this artifact 2026-05-03.

**2. Add trust disclosure requirements to `veritas-investment-deck`**

Add a minimum `Disclosure` or `Trust panel` slide requirement: written date, data as-of date, trust/validation grade, stale/manual dependency labeling. Brings the skill into alignment with the rest of the output layer.

**3. Add `USER.md` to `memory-continuity-manager`'s "Files This Skill May Edit" list**

Single-line fix. The routing rules already name it; the edit manifest missed it.

---

### High — Address in a bounded skills governance pass

**4. Formally resolve `technical-chart-pass` vs `veritas-technical-pass`**

The count is at exactly 20, making this the logical merge/deprecation candidate.
- **Option A (recommended):** Keep `technical-chart-pass` as a true generic fallback but add a state-translation table mapping its labels to the canonical four-state vocabulary, and remove board-sync language from its description.
- **Option B:** Deprecate `technical-chart-pass` entirely and absorb its trigger language into `veritas-technical-pass` with a "generic mode" note.

Either way, the governance index "known follow-up" item must close with a decision, not remain perpetually open-ended.

**5. Remove or caveat the `TaskFlow` reference in `automation-hardening-manager`**

Replace the `TaskFlow` line with: "TaskFlow — not currently live in this environment; verify before use or default to spawned subagent." Prevents a dead routing reference from misleading future automation design.

**6. Refactor `ic-swarm-orchestrator` to defer to the Automation Orchestration Protocol**

The skill should not maintain its own copy of lane routing, fallback order, and effort posture. Replace the duplicated routing content with a reference to `06. Playbooks/Automation Orchestration Protocol.md`. Retain the skill's unique content (completion handshake rules, quality gates, anti-patterns, output template). Define what `ACP` means or remove the reference.

**7. Add `Cron Job Retrofit Checklist.md` to `cron-automation-manager`'s read-first list**

Single addition to `Inputs to Check First`. WF24 created this checklist precisely for use when auditing existing jobs against the run-packet contract.

**8. Add skills-specific QA override to `workspace-qa-pass`**

Add a branch instruction: "If the QA pass targets skills specifically, read `06. Playbooks/Skill Quality Standard.md` and `06. Playbooks/Skills Governance Index.md` as the style anchor instead of a sample skill file."

**9. Add governance-gate to `veritas-self-improvement`'s skill-creation trigger**

In the "Skill creation trigger" section, add: "Before creating or updating a skill, check `Skills Governance Index.md` current count (governance review triggers at 20+) and verify the skill meets the minimum quality bar in `Skill Quality Standard.md`."

---

### Forward-looking — Before WF25+ research-department work begins

**10. Add a coverage-admission gate reference to `veritas-fundamental-pass`**

When a name evaluation concludes with `candidate for deeper research` or `watchlist only`, the skill should point to the research-department intake queue and `Coverage Admission and Promotion Protocol.md`. This closes the gap between analysis output and WF25 admission decision flow.

**11. Add validation tier labels to `Skills Governance Index.md`**

The `Last tested` column only shows date and method but not which validation tier was applied. Add a `Validation tier` column. For all 20 current skills the honest answer is Tier 1 (structural). Flag the core workflow skills (`veritas-post-earnings-sync`, `veritas-portfolio-update`, `veritas-weekly-brief`) for Tier 3 validation as the next meaningful hardening target.

**12. Add web-search outage posture to research-dependent skills**

`veritas-fundamental-pass` and `veritas-macro-pass` both depend on external research access. `web_search` is currently unusable on this host (SearXNG base URL not configured, confirmed 2026-05-04). Neither skill defines a degraded-search fallback posture. Add a brief fallback rule to each: local docs + direct fetch only, explicit confidence downgrade to Medium ceiling, note the search outage in the output header.

---

## Summary Scoreboard

| Category | Count | Status |
|---|---|---|
| Critical fixes (pre-execution) | 3 | Required before next board-sync or weekly brief |
| High fixes (governance pass) | 6 | Address in next bounded skills governance pass |
| Forward-looking (WF25+ prep) | 3 | Sequence into WF25 or adjacent lane |
| Protocol layer | 4 docs audited | All solid; one Skill Quality Standard tier-labeling gap |
| Skill count | 20 / 20 | At governance trigger threshold |
| Tier 3 validation | 0 of 20 | Core workflow skills overdue |

The finance analysis skills (macro, fundamental, technical, positioning) are the strongest area. The output-layer skills (deck, PDF) and automation-infrastructure skills (ic-swarm, automation-hardening) carry the most residual debt. The protocol layer is solid. The Cron Job Protocol post-WF24 hardening is the best single-document in the system.
