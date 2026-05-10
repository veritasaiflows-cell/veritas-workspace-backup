# WF23 Phase 3 Live Surface QA - 2026-05-06

## Purpose
Challenge the current live dashboard layer before any WF23 live-edit pass so the highest-risk overlap claims are explicit, remediation is bounded, and owner-note authority is preserved.

## Files reviewed
- `06. Playbooks/Project Continuity/Workflow 23 - Command Center Fresh Brief and Decision Surface Tightening.md`
- `06. Playbooks/WF23 Phase 1 Command Center Surface Map - 2026-05-06.md`
- `06. Playbooks/WF23 Phase 2 Fresh Brief and Decision-Point Contract - 2026-05-06.md`
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/This Week.md`
- `01. Dashboards/Next Actions.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `05. Intelligence/Event Calendar.md`

## QA verdict
The live dashboard layer still carries several high-risk overlap claims that overstate authority, compress owner-note nuance, or preserve stale week framing. The most serious issue is not a factual typo; it is that the dashboards sometimes sound like they own deployment and catalyst judgment even when the canonical owner notes say those states remain conditional, almost deployable, or follow-up-bound.

A safe live-edit pass should therefore reduce authority, remove stale weekly framing, and convert owner-sensitive claims into read-owner-first / unresolved-truth language.

## Highest-risk overlapping claims

### 1) Dashboards say JPM / NVDA / GS are effectively live while owners still say zero deployable-now names
**Where it appears**
- `01. Dashboards/Executive Brief.md`: "The live action list is narrow... JPM, NVDA, and GS are the names currently in band. GS is now a confirmed tactical secondary..."
- `01. Dashboards/Executive Brief.md`: "treat JPM, NVDA, and GS as the live in-band candidates"
- `01. Dashboards/This Week.md`: "JPM and NVDA recognized as the primary live in-band names, with GS now explicit as a deployable-now tactical secondary"
- `01. Dashboards/Next Actions.md`: "Treat JPM and NVDA as the only live in-band candidates"

**Why this is high risk**
- `03. Portfolio/Portfolio Snapshot.md` says the latest surface shows **zero deployable-now names** and keeps JPM / NVDA / GS as **almost deployable**.
- `03. Portfolio/Deployment Trigger Sheet.md` is the deployment owner and also says **Deployable now: None**.
- The dashboards collapse the difference between "in band" and "deployable now," which is exactly the owner-boundary drift WF23 is supposed to prevent.

**Sufficient remediation**
- Keep the orientation value, but rewrite these claims into explicit subordinate language such as: in band / almost deployable / explicit promotion still required / use Trigger Sheet and Portfolio Snapshot before treating as a real add.
- Remove any phrase that implies GS is already a confirmed deployable state unless that exact state exists in the owner notes.

**Must not change in the live pass**
- Do not change actual deployment states in `Portfolio Snapshot` or `Deployment Trigger Sheet`.
- Do not silently promote any name just to make dashboards consistent.

### 2) `This Week` still owns a stale week and stale catalyst posture
**Where it appears**
- `01. Dashboards/This Week.md` is still titled and framed as **Week of April 27 – May 3**.
- It says ETN is "kept conditional into earnings" and references "the next catalyst week" even though `Event Calendar` now shows ETN reported/interpreted on May 5.

**Why this is high risk**
- This creates live overlap with `05. Intelligence/Event Calendar.md` and `05. Intelligence/Weekly Positioning Review.md` by carrying its own outdated catalyst-state summary.
- The problem is structural: an orientation note is speaking from an expired week and preserving pre-report framing after the event has already closed with follow-up.

**Sufficient remediation**
- Remove or rewrite week-specific bullets that still speak from Apr 27–May 3 as if current.
- Convert ETN wording from pre-/into-earnings framing to post-earnings follow-up / evidence-quality / owner-note-first wording.
- Keep `This Week` as a short current-week orientation pointer, not a lagging catalyst archive.

**Must not change in the live pass**
- Do not rewrite the canonical event history in `Event Calendar`.
- Do not invent a fresh weekly operating stance beyond what `Weekly Positioning Review` already supports.

### 3) Dashboard wording compresses ETN post-earnings nuance into a decision surface
**Where it appears**
- `Executive Brief`: "ETN is no longer a pre-print decision; it has already reported and remains a post-earnings review item with incomplete primary-source capture."
- `Next Actions`: "Keep ETN in post-print review mode... Default posture should stay review-only until primary-source capture and next-session confirmation remove the remaining ambiguity."
- `This Week`: still mixes ETN with pre-earnings / next-week language.

**Why this is high risk**
- Some ETN wording is directionally honest, but it is spread across all three dashboards with different levels of specificity, increasing the chance that the dashboards become the de facto owner of the ETN follow-up state.
- `Deployment Trigger Sheet` already carries the canonical ETN judgment: constructive evidence, primary-source follow-up still required, almost deployable, no promotion yet.

**Sufficient remediation**
- Reduce dashboards to one consistent shape: ETN post-earnings interpretation exists; final state remains owner-bound; read the Trigger Sheet / scorecard before changing posture.
- Eliminate any leftover pre-print or conditional-into-earnings framing.

**Must not change in the live pass**
- Do not upgrade ETN to deployable-now.
- Do not erase the primary-source limitation or next-session confirmation requirement.

### 4) XOM / GOOG / MSFT summaries risk duplicating owner judgment rather than routing to it
**Where it appears**
- `Executive Brief` and `Next Actions` summarize XOM, GOOG, and MSFT state in relatively decision-heavy prose.
- Examples: "XOM... scorecard is done, but the name is still benched" and "use the new GOOG and MSFT scorecards as canon, but keep both names out of the live deployment list until entry quality improves."

**Why this is high risk**
- These are mostly aligned with owner notes, but the dashboards are doing too much of the interpretive work themselves.
- This is lower risk than the JPM/NVDA/GS conflict, but still an overlap hazard because repeated detailed judgment across multiple dashboards creates shadow canon.

**Sufficient remediation**
- Shorten these to fresh-brief / report-link / owner-bound language.
- Prefer "scorecard exists; owner notes still keep the name benched / off-board" over multi-clause interpretive restatements.

**Must not change in the live pass**
- Do not alter XOM, GOOG, or MSFT canonical state in owner notes.
- Do not remove valid caution just to make dashboards cleaner.

### 5) `Next Actions` contains owner-sensitive details that belong in canonical decision notes
**Where it appears**
- Exact prices, bands, cap language, and deployment-sensitive status appear inline in `01. Dashboards/Next Actions.md`.
- It also carries a portfolio-governance item: "Force an explicit decision on Capital Deployment Readiness..."

**Why this is high risk**
- `Next Actions` is supposed to route work, not restate trigger logic or carry side-governance decisions as if they are part of the immediate market action board.
- The more exact gate data it repeats, the more drift risk it creates versus `Deployment Trigger Sheet` and `Portfolio Snapshot`.

**Sufficient remediation**
- Keep `Next Actions` action-shaped: read owner note first, confirm unresolved issue, process follow-up cluster, respect cap before adding.
- Remove or trim exact band/price restatement unless it is strictly necessary for immediate routing and clearly owner-subordinate.
- Consider whether the capital-deployment-readiness governance item belongs on this live dashboard at all.

**Must not change in the live pass**
- Do not delete real risk constraints such as the tech/AI cap warning.
- Do not convert routing language into new portfolio judgments.

## What counts as sufficient remediation overall
A Phase 3 live edit is sufficient only if it does all of the following:
1. makes `Deployment Trigger Sheet`, `Portfolio Snapshot`, `Weekly Positioning Review`, and `Event Calendar` visibly authoritative whenever state matters
2. removes stale Apr 27–May 3 / pre-earnings framing from live dashboard surfaces
3. replaces deployment-sounding dashboard claims with in-band / almost deployable / review-first / owner-note-first wording where applicable
4. preserves unresolved-truth language for ETN, NVDA timing, and any other still-limited evidence path
5. improves retrieval and orientation without adding any new state that exists only on dashboards

## What must not be changed in the live edit pass
- Do not edit queue state, workflow registry state, or memory.
- Do not change canonical owner judgments in `Weekly Positioning Review`, `Portfolio Snapshot`, `Deployment Trigger Sheet`, or `Event Calendar` just to harmonize wording.
- Do not promote any ticker to deployable-now from dashboard surfaces.
- Do not remove real caution language around ETN primary-source follow-up, NVDA timing confirmation, concentration limits, or XOM follow-through.
- Do not turn dashboards into a compressed second copy of the deployment board or catalyst canon.

## Recommended edit posture
- Fix the authority drift first: JPM / NVDA / GS wording.
- Fix stale temporal framing second: `This Week` current-week / post-event posture.
- Then trim detailed interpretive duplication on ETN, XOM, GOOG, and MSFT into shorter owner-routed language.

## Verification
- Read all requested workflow, dashboard, intelligence, portfolio, trigger, and event files.
- Produced exactly one new read-only artifact: `08. Audits/WF23 Phase 3 Live Surface QA - 2026-05-06.md`.
- Did not edit any dashboard file or queue/control-surface state.
