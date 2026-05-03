# Capital Deployment Readiness

## Objective
- Increase confidence and discipline around actual capital deployment decisions by making the morning deployability picture cleaner, more trust-aware, and less vulnerable to stale or contaminated signals.
- Turn the current research/trigger/risk stack into a more decision-grade deployment-readiness layer without crossing the line into trade execution.

## Current State
- The workspace has a growing machine pipeline for technicals, trigger sheets, deployment checks, regime scores, positioning ranks, dashboard validation, and run-summary trust.
- The OS is getting stronger, and the worst workflow/action leakage has been repaired, but deployment certainty is still limited by stale note ownership, post-earnings note/date reconciliation, degraded macro/policy trust, and imperfect morning operator clarity.
- The current system can produce rankings and statuses, but it still needs a clearer contract for what "deployable now" actually means under live trust conditions.

## Why this project exists
- Randall wants to start deploying capital while markets are moving.
- Discipline comes first.
- That means the OS must distinguish clearly between:
  - ready now
  - near-ready with confirm conditions
  - blocked for valid reasons
  - blocked because the system still has trust/freshness flaws

## Last Meaningful Progress
- The parallel-IC operating layer was formalized with:
  - `06. Playbooks/Independent Contractor Workflow.md`
  - `06. Playbooks/Parallel IC Project Workflow.md`
- `E17 Universe Synchronization` progressed through Phase 3 Sub-Pass 3, including the workflow/action integrity repair that removed the GS false-positive leakage path.
- The remaining gap is no longer the worst machine-state leakage; it is note/date reconciliation plus post-earnings judgment on the most consequential names.

## Outstanding
- Define the deployment-readiness contract.
- Clarify which existing artifacts are authoritative for:
  - readiness
  - blocked state
  - near-ready state
  - trust override / do-not-deploy state
- Identify where current rankings or trigger outputs can produce false positives.
- Define the minimum morning operator surface needed for disciplined capital deployment.
- Decide what belongs in machine artifacts versus canonical notes versus morning brief output.
- Determine what must be repaired in the OS before broader capital deployment should scale.

## Blockers / Trust Gaps
- Note-layer reconciliation is now narrowly centered on post-earnings judgment quality rather than obvious state mismatch; MSFT and GOOG remain intentionally conservative until explicit review is complete.
- Macro/policy trust remains degraded and can undermine confidence even when individual names look technically attractive.
- Trigger-sheet canonical note ownership is improving, but post-earnings adjudication still needs explicit human review before any upgrade.
- The highest-value earnings-date trust noise is now narrow: NVDA still shows May 20 in machine outputs versus an older May 27 vault date, BRK.B shows May 2 versus an older May 4 vault date, and CAT is no longer primarily a date problem — it is a post-earnings rewrite problem.
- The current stack still needs a clean rule for when degraded trust should override otherwise-constructive deployability.

## Phase History

### Phase 0 — Completed 2026-05-01
- Contract definition pass complete.
- Deliverable: `06. Playbooks/Project Continuity/Capital Deployment Readiness - Phase 0 Contract.md`
- Defines: deployment-readiness contract, six-state readiness vocabulary, source-owner-reader-cadence table, seven false-positive pathways, trust-override rules, current morning trust state.
- Key finding: GS is the most dangerous active false positive — machine ranks it DEPLOYABLE NOW #1; contract analysis shows it is TRUST BLOCKED (workflow_state=WATCH, no decision-grade note, fallback_state active). JPM is the only name that survives trust-override review in a constructive state.
- Operator decisions required before Phase 1: see Section 7 of Phase 0 Contract (seven open items).

### Phase 1 — Completed 2026-05-01
- Artifact authority audit and per-name state audit complete.
- Deliverable: `06. Playbooks/Project Continuity/Capital Deployment Readiness - Phase 1 Audit.md`
- **Key findings:**
  - 4 false positives: GS (DEPLOYABLE NOW → TRUST BLOCKED), VRT (ALMOST → TRUST BLOCKED), CAT (ALMOST → WATCH/REVIEW), ETN (ALMOST → ALMOST + NEAR-EARNINGS CAUTION missing)
  - 3 false negatives: AMZN, GOOG, MSFT all held in stale pre-print earnings blocks; root cause is vault watchlist dates (still showing Apr 29) not updated post-print — scripts use vault dates, not earnings-calendar.json. MSFT is most consequential (currently in entry band, incorrectly blocked).
  - No names are blocked solely by system trust degradation. All blocks are substantive. The fallback_state/macro-manual degradation adds a confirmation requirement layer but is NOT causing any valid candidate to disappear.
  - 10 gaps documented (G-1 through G-10). Critical: G-1 (workflow_state not gated), G-2 (stale earnings blocks), G-3 (run-summary trust gates not propagated), G-7 (run-summary timestamp predates artifact refresh).
  - Authoritative sources for morning decision mapped: trigger-sheet.json is the primary per-name source; run-summary and dashboard-validation are the trust pre-filters; positioning-ranking priority_rank should NOT be used as a decision signal (WATCH-state names can outrank ALMOST-state names).
  - JPM is the only name that survives full contract review in a constructive state. GS at #1 in machine ranking is a confirmed false positive.

### Phase 2 — Completed 2026-05-01
- Morning decision surface design complete.
- Deliverable: `06. Playbooks/Project Continuity/Capital Deployment Readiness - Phase 2 Surface Design.md`
- **Key deliverables:**
  - 7 surface states defined (DEPLOYABLE NOW / ALMOST / ALMOST+NEAR-EARNINGS CAUTION / POST-EARNINGS REVIEW / BLOCKED / DO NOT TOUCH / WATCH)
  - 9-rule adjudication decision tree that converts raw machine fields into surface states — first match wins
  - 3 override types defined (A: semantic downgrade, B: post-earnings downgrade, C: trust ceiling)
  - Required fields per name on the morning surface: 11 fields in explicit order
  - Name grouping by surface state, not by machine priority rank (directly fixes FP-7)
  - Current morning surface rendered in full against 2026-05-01 data
  - `post_earnings_review_confirmed` field defined and scoped for Phase 3 implementation
  - 4 new fields defined for portfolio-config.json (post_earnings_review_date, last_earnings_date, earnings_date_ir_confirmed, earnings_date_ir_confirmed_date)
  - Phase 3 implementation sequence specified with G-2 first (stale blocks), G-1 second (workflow_state gate), G-7 third (run-summary ordering)
- **State as of 2026-05-01 morning under the Phase 2 surface:**
  - 0 DEPLOYABLE NOW (suspended)
  - 2 ALMOST DEPLOYABLE: JPM, NVDA
  - 1 ALMOST + NEAR-EARNINGS CAUTION: ETN
  - 5 POST-EARNINGS REVIEW: MSFT (priority, in band), AMZN, GOOG, CAT (post-Apr-30 setup obsolete until rewritten), XOM
  - 0 BLOCKED (no valid active pre-print blocks — AMZN/GOOG/MSFT reclassified)
  - 4 DO NOT TOUCH: LMT, RTX, BRK.B, and GS cross-reference
  - 3 WATCH: GS (machine said DEPLOYABLE NOW), VRT, AMD

## Current Hold State — as of 2026-05-01

**Claude status:** Held but re-engageable. Phases 0–2 complete and still valid as the contract layer.

**Phase 3 owner:** Gemini / Veritas machine-side work already moved the stack materially forward. The current bottleneck is no longer a pure implementation lane.

**Claude standing instructions (held):**
- Remain owner of the deployment-readiness contract (Phase 0) and morning-surface logic (Phase 2)
- Stand by for cross-project review after note-layer reconciliation and the next judgment-sensitive state pass
- MSFT remains top post-earnings review priority — in band post-Apr-29 print, stale block, needs human read on earnings before any re-classification
- GS remains overridden to WATCH — machine false positive (DEPLOYABLE NOW) is not cleared until: (1) thesis review completed, (2) human-validated entry and stop written into Deployment Trigger Sheet, (3) workflow_state changed from WATCH to ALMOST by operator
- Do not begin Phase 3 implementation

**What Claude will do when re-engaged:**
- Review the post-Phase-3 stack against the Phase 2 surface design contract
- Verify that workflow_state gating and stale-block cleanup are behaving honestly enough in the note layer
- Run the adjudication rules against the post-Phase-3 machine output to confirm the surface now produces correct states
- Write the post-Phase-3 review note

## Next Action
- **Immediate next action:** re-run the deployment-readiness interpretation pass against the cleaned note layer, with MSFT and GOOG still held conservatively until explicit post-earnings review is complete
- **Then:** decide whether a second-opinion review is still useful on MSFT/GOOG adjudication or whether the conservative hold is sufficient for now
- **Claude re-engagement trigger:** after the note-layer reconciliation lands, if a second-opinion review is still useful on MSFT/GOOG adjudication or morning-surface trust

## Key Files
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`
- `01. Dashboards/Executive Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `tmp/trigger-sheet.json`
- `tmp/deployment-check.json`
- `tmp/regime-scores.json`
- `tmp/positioning-ranking.json`
- `tmp/dashboard-validation.json`
- `tmp/run-summary-post-close.json`
- `tmp/workbook-control-panel.csv`
- `06. Playbooks/Project Continuity/E17 Universe Synchronization.md`

## Automation / Refresh Path
- This should become a daily-use project, but not by skipping trust gates.
- Start with contract definition and false-positive mapping.
- Then identify the minimum set of morning surfaces or artifacts that should drive deployment readiness.
- Only after the contract is clear should any dedicated deployment-readiness surface or export be built.

## Phase Approach

### Phase 0 — Deployment-readiness contract
Goal:
- define what "deployable now" means in this OS

Deliverables:
- readiness-state vocabulary
- source-owner-reader-cadence table
- false-positive map
- trust-override rules

### Phase 1 — Current-stack audit
Goal:
- identify where present artifacts already support readiness and where they mislead

Deliverables:
- artifact audit
- gap list
- recommended authoritative sources for the morning decision stack

### Phase 2 — Morning decision surface design
Goal:
- define the minimum effective morning deployability view

Deliverables:
- view/spec for ready / near-ready / blocked / trust-blocked
- explicit required fields
- downgrade behavior when trust is degraded

### Phase 3 — Implementation / integration
Goal:
- build the first trustworthy deployment-readiness layer

Deliverables:
- machine artifact or surface changes
- validation rules
- integration with existing ranking/trust stack

### Phase 4 — Operating cadence
Goal:
- fit the new readiness layer into daily workflow cleanly

Deliverables:
- morning use pattern
- refresh cadence
- escalation/override rules
- contractor and operator handoff path
