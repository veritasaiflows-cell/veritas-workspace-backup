# Capital Deployment Readiness

## Objective
- Increase confidence and discipline around actual capital deployment decisions by making the morning deployability picture cleaner, more trust-aware, and less vulnerable to stale or contaminated signals.
- Turn the current research/trigger/risk stack into a more decision-grade deployment-readiness layer without crossing the line into trade execution.

## Current State
- The workspace has a growing machine pipeline for technicals, trigger sheets, deployment checks, regime scores, positioning ranks, dashboard validation, and run-summary trust.
- Phase 3 is now implemented in the machine layer: the stack carries the Phase 2 review fields, emits a dedicated deployment-readiness surface, and applies bounded trust downgrades instead of letting raw ranking or in-band status speak last.
- The current system can now distinguish raw machine posture from reviewed surface posture more honestly: ETN is explicitly near-earnings caution, NVDA is capped at ALMOST while timing confirmation remains unresolved inside the active catalyst window, and recent reviewed post-print names no longer fall back into stale limbo.
- **Automation phase (post-closeout reality):** this lane is now a **bounded, usable deployment-readiness operating layer**. Scheduled evidence, validator output, trigger artifacts, contradiction routing, and explicit morning review cadence are defined and usable, but canonical readiness judgment remains note-owned and human-gated.

## Why this project exists
- Randall wants to start deploying capital while markets are moving.
- Discipline comes first.
- That means the OS must distinguish clearly between:
  - ready now
  - near-ready with confirm conditions
  - blocked for valid reasons
  - blocked because the system still has trust/freshness flaws

## Last Meaningful Progress
- The machine layer already had the bounded deployment-readiness surface from Phase 3.
- Phase 4 through Phase 7 finished the operating contract around that surface:
  - `06. Playbooks/Deployment Readiness Morning Operating Cadence.md`
  - `06. Playbooks/Deployment Readiness Helper Packet Contract.md`
  - `06. Playbooks/Deployment Readiness Surface Integration Contract.md`
- The project is now closed honestly as usable, review-gated infrastructure instead of an unfinished optional idea.

## Outstanding
- Narrow timing/date trust residue remains open:
  - NVDA timing confirmation inside the active catalyst window
  - BRK.B next-quarter timing cleanup / confirmation
- Macro/policy trust remains caution-bearing even with clean validator state.
- Canonical readiness judgment remains human-owned in `03. Portfolio/Deployment Trigger Sheet.md`.

## Blockers / Trust Gaps
- Macro/policy trust remains degraded and can undermine confidence even when individual names look technically attractive.
- The highest-value earnings-date trust noise is now narrow: NVDA still shows May 20 in machine outputs versus an older May 27 vault date, and BRK.B next-quarter timing still needs IR-grade confirmation before anyone should lean on the provider date.
- No autonomous Trigger Sheet apply path is approved in v1.
- Any future attempt to surface the JSON artifact as a decision-grade dashboard or workbook board would risk creating a second truth layer unless the owner boundary is intentionally reopened and revalidated.

## Automation readiness assessment — 2026-05-03

**Workflow under review:** Capital Deployment Readiness

**Current phase:** bounded, usable deployment-readiness operating layer with read-only helper contracts and no approved autonomous apply path

**Recommended next phase:** closed with follow-up triggers only; widen autonomy only if the named reopen conditions are met

**Safe automation boundary now:**
- scheduled evidence collection and staging artifacts for macro, technical, earnings, trigger, and dashboard layers
- validator runs, acceptance checks, contradiction scans, and mirror-parity warnings
- read-only prep packets for admission review, thesis drift, and deployment-risk review
- distinct-output helper lanes that do not compete for the same canonical note surface

**Still human-gated:**
- queue movement, workflow advancement, and final QC closeout
- admission / promotion / demotion into tracked universe or execution lane
- canonical thesis rewrites, trigger-sheet final judgment, and portfolio conclusion changes
- final macro regime judgment, policy-caveat wording, and any cross-surface truth arbitration
- any packaging/publishing step that could be mistaken for presentation-grade truth while upstream residue remains active

**Still unresolved / intentionally not widened:**
- continued fail-closed handling for timing-sensitive date noise, led by NVDA when decision-critical
- BRK.B next-quarter machine-date cleanup / confirmation
- macro/policy caution remains a real confidence ceiling even when the mechanical checks are clean
- no autonomous apply helper is approved for the Trigger Sheet in v1

**Final rollout posture after this edit:**
1. use `tmp/deployment-readiness-surface.json` only as the bounded operator review artifact beneath the Trigger Sheet owner surface
2. keep helper lanes read-only: admission prep, thesis-drift intake, and contradiction QA
3. stop every helper lane at packet/review output; do not let them mutate canonical readiness notes or portfolio posture
4. keep any wider visibility or helper-gating request behind an explicit reopen decision instead of letting it creep in informally

## Phase 3 — Completed 2026-05-03
- Implemented the bounded machine-side review surface without crossing into autonomous readiness judgment.
- **Code / artifact deliverables:**
  - `scripts/trigger_sheet_refresh.py` now emits the Phase 2 review fields:
    - `post_earnings_review_confirmed`
    - `post_earnings_review_date`
    - `last_earnings_date`
    - `earnings_date_ir_confirmed`
    - `earnings_date_ir_confirmed_date`
  - `scripts/deployment_readiness_surface.py` now builds `tmp/deployment-readiness-surface.json`
  - `scripts/run_finance_refresh_chain.py` now runs the new surface generator in all scheduled windows after run-summary consumption
  - `tmp/portfolio-config.json` now carries the bounded post-earnings/date-confirmation fields needed for reviewed names
- **Behavioral outcomes:**
  - ETN now renders as `ALMOST / NEAR-EARNINGS CAUTION` instead of blending into generic almost-ready output
  - NVDA is now fail-closed to `ALMOST DEPLOYABLE` under Rule 6B while its active-window earnings timing remains unconfirmed
  - BRK.B, XOM, GOOG, MSFT, LMT, and other reviewed names now carry explicit post-earnings/date fields instead of relying on silent inference
  - canonical note mutation remains fail-closed from scheduled windows; this surface is review support, not autonomous note control
- **Live verification:**
  - `python scripts/run_finance_refresh_chain.py post-close` completed successfully on 2026-05-03
  - `tmp/deployment-readiness-surface.json` now shows:
    - `DEPLOYABLE NOW`: `GS`, `JPM`
    - `ALMOST DEPLOYABLE`: `GOOG`, `MSFT`, `NVDA`
    - `ALMOST / NEAR-EARNINGS CAUTION`: `ETN`
    - `DO NOT TOUCH`: `BRK.B`, `LMT`, `XOM`
    - `WATCH / RESEARCH NEEDED`: `VRT`
  - `tmp/dashboard-validation.json` stayed `0 critical / 0 warning`
  - `tmp/dashboard-acceptance-report.json` stayed passing via the post-close chain

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

## Current Posture — closed 2026-05-03

**Phase status:** Phase 4 through Phase 7 are now complete. The project is closed as a bounded, review-gated operating layer rather than an open-ended automation experiment.

**Current owner posture:** Veritas owns the machine-side implementation and QA state here. Canonical readiness judgment still belongs to the Trigger Sheet / note layer, not the helper surface.

**What is now true:**
- GS is no longer the old false positive from Phase 0/1; the current note-layer and machine-layer posture both treat it as a tactical but secondary deployable setup.
- MSFT and GOOG are no longer blocked by stale post-print logic; they remain ALMOST because price posture is still extended versus band, not because the stack lost the plot.
- NVDA is the main active fail-closed timing case: technically in band, but not allowed to present as full deployable-now truth in the review surface until timing confirmation is cleaned up.

**What a second-opinion lane would review now if needed:**
- whether Rule 6B is the right fail-closed ceiling for active-window timing uncertainty
- whether a later human-facing panel should expose the same surface directly or keep it as JSON/operator-only infrastructure
- whether a future proposal-only freshness helper is justified without weakening the owner boundary

## Next Action
- **Current state:** closed with follow-up triggers.
- **Immediate next action outside this workflow:** continue using the Trigger Sheet as canonical, use the operating cadence when deployment review matters, and reopen only if the named triggers fire.

## Sequential finish plan — proposed 2026-05-03

### Phase 4 — Operating cadence contract
Goal:
- define the exact daily morning operator pattern around `tmp/deployment-readiness-surface.json`, `tmp/trigger-sheet.json`, `tmp/run-summary-morning.json`, and the canonical Trigger Sheet.

Deliverables:
- explicit morning checklist
- escalation/override rules
- exact human decision points
- proof rule for when the machine surface may be consulted versus ignored

Acceptance:
- one unambiguous morning cadence
- owner boundary preserved: JSON supports, Trigger Sheet decides
- no implicit canonical mutation path

### Phase 5 — Read-only helper lanes and packet layer
Goal:
- add the first recurring read-only helper packets that make the morning desk more useful without crossing into canonical ownership.

Deliverables:
- admission prep packet contract
- thesis-drift / news-monitoring intake packet contract
- adversarial contradiction / QA packet contract
- clear stop-line rules for helper output quality

Acceptance:
- helper lanes stop at packet output
- no queue movement, no note mutation, no portfolio conclusion changes
- at least one bounded packet format per helper class is specified

### Phase 6 — Surface integration and low-risk gating
Goal:
- decide how the deployment-readiness artifact should surface operationally and whether any low-risk gated helper is justified.

Deliverables:
- decision on JSON-only vs additional dashboard/workbook visibility
- explicit low-risk gating rules for mechanical freshness or parity helpers, if any
- validation rule proving the surfaced view cannot outrank the owner notes

Acceptance:
- no second conflicting truth layer created
- surfaced deployment state remains visibly derived and bounded
- any helper remains gated and reviewable

### Phase 7 — Closeout and automation posture lock
Goal:
- close the project honestly with the final automation posture, unresolved residue list, and reopen triggers named.

Deliverables:
- closeout note update
- chain-log closure entry
- registry state update
- named reopen triggers for:
  - NVDA timing trust
  - BRK.B next-quarter timing confirmation
  - any future request for higher-autonomy readiness maintenance

Acceptance:
- project can sit closed without hidden ambiguity
- the allowed automation boundary is explicit and durable
- future expansion path is named but not pretended into existence

## Phase execution rule
- Run Phases 4 -> 5 -> 6 -> 7 in order.
- Do not skip from Phase 3 directly to autonomous note-control ideas.
- Keep helper lanes read-only until Phase 6 proves a bounded gated-helper use case.
- Keep canonical readiness judgment in `03. Portfolio/Deployment Trigger Sheet.md` through the full sequence.

## Phase 4 — Completed 2026-05-03
- Landed `06. Playbooks/Deployment Readiness Morning Operating Cadence.md`.
- Defined the exact morning review order, trust preflight, freshness preflight, Trigger Sheet cross-check rule, and escalation behavior.
- Explicitly encoded that the machine surface may support review only and must be ignored when trust/freshness degrades materially.

## Phase 5 — Completed 2026-05-03
- Landed `06. Playbooks/Deployment Readiness Helper Packet Contract.md`.
- Defined the minimum read-only helper packet set:
  - admission prep
  - thesis-drift / news-monitoring intake
  - contradiction / QA
- Kept all helper outputs packet-only with no canonical note mutation, no queue movement, and no portfolio conclusion authority.

## Phase 6 — Completed 2026-05-03
- Landed `06. Playbooks/Deployment Readiness Surface Integration Contract.md`.
- Chose the safer v1 decision: keep the deployment-readiness surface as JSON/operator infrastructure rather than promoting it into a new dashboard/workbook truth surface.
- Explicitly declined any autonomous apply helper for the Trigger Sheet in this phase.

## Phase 7 — Completed 2026-05-03
- Closed the project as a bounded, usable operating layer with explicit automation limits.
- Locked the owner-of-truth statement: `03. Portfolio/Deployment Trigger Sheet.md` decides; helper artifacts support.
- Wrote the closeout QA artifact: `08. Audits/Capital Deployment Readiness Closeout QA Audit - 2026-05-03.md`.
- Named the reopen triggers:
  - NVDA timing confirmation remains unresolved inside the active catalyst window
  - BRK.B next-quarter timing cleanup / confirmation remains unresolved
  - any explicit request to widen visibility or autonomy beyond read-only helper packets

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
- `tmp/deployment-readiness-surface.json`
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
