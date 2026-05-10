# WF23 Phase 2 Contract QA - 2026-05-06

## Purpose
Challenge the Phase 2 fresh-brief / decision-point contract before any live dashboard edits.
This QA pass is read-only and tests whether the proposed contract is strict enough to prevent wording-shape drift, hidden publish authority, and owner-bypass linking.

## Files reviewed
- `06. Playbooks/Project Continuity/Workflow 23 - Command Center Fresh Brief and Decision Surface Tightening.md`
- `06. Playbooks/WF23 Phase 1 Command Center Surface Map - 2026-05-06.md`
- `08. Audits/WF23 Phase 1 Surface Boundary QA - 2026-05-06.md`
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/This Week.md`
- `01. Dashboards/Next Actions.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`

## QA verdict
Phase 2 should proceed only if the contract gets tighter than “show fresh things on the dashboards.”
The current surfaces already carry enough live-state language that any loose Phase 2 wording will quietly turn orientation summaries into publish authority. The minimum safe contract is: claim-shape limited, owner-first, unresolved-truth explicit, and link behavior biased toward canonical notes rather than dashboard-native synthesis.

## Highest-risk Phase 2 failure modes

### 1) Fresh brief visibility mutates into dashboard publication
The dashboard layer already speaks in sentence form about live names, catalyst state, and post-earnings interpretation. If Phase 2 says a fresh packet or scorecard should become “visible” without constraining the sentence shape, the dashboard will effectively publish judgments such as:
- a name is live
- a blocker is cleared
- a scorecard resolved the question
- a catalyst changed posture

That is hidden authority unless the dashboard sentence is explicitly degraded to a freshness / review / unresolved-truth object with a named owner.

### 2) Unresolved truths get rewritten into cleaner prose
The source stack contains real uncertainty:
- ETN primary-source capture is incomplete
- NVDA timing still has narrow residue
- weekly and dashboard language do not fully agree on deployable-now vs almost-deployable shapes
- some notes still preserve older week-specific wording

If Phase 2 allows dashboards to rewrite these into “improved confidence” or “review completed” summaries, the surface will erase the exact thing the user needs to see: what remains unproven, who must resolve it, and what note currently owns the answer.

### 3) Decision-point routing becomes soft decision-making
`Next Actions` is especially exposed here. A Phase 2 contract that allows “decision points” without a strict routing shape will drift into action-authority language like:
- trim the list to these names
- treat this as the live setup
- use this result as the canonical read

Those are not harmless reminders; they are publish actions unless the owner already says the same thing. Phase 2 must require review-first wording whenever owner confirmation is incomplete.

### 4) Report links bypass owners and reward the fastest summary
If dashboards link directly to the latest packet-like artifact or summarize from `Weekly Intelligence Brief` while skipping `Weekly Positioning Review`, `Portfolio Snapshot`, or the trigger surfaces, the dashboard becomes the easiest place to read truth. Even with honest caveats, operator behavior will follow convenience.

Phase 2 therefore needs an owner-first linking rule, not just a “helpful links” rule.

## Wording-shape drift already visible in the current stack

### Executive Brief
Current language includes exact live-state statements such as:
- “JPM, NVDA, and GS are the names currently in band”
- “GS is now a confirmed tactical secondary”
- “ETN is no longer a pre-print decision”

Those may be directionally useful, but as sentence shapes they already read like published state rather than derived orientation. If Phase 2 inherits this shape, fresh-brief visibility will become dashboard adjudication.

### This Week
This note mixes outcomes, state summaries, and cleanup goals. Phrases like:
- “JPM and NVDA recognized as the primary live in-band names”
- “ETN moved out of pre-print status”
- “GOOG and MSFT kept almost deployable only”

are not neutral routing objects; they are compact state judgments. Phase 2 must decide whether this surface is allowed to hold that sentence shape at all. My view: only if every such line is explicitly owner-derived and degradable to unresolved wording when owners diverge.

### Next Actions
This note is closest to hidden publish authority. It already says things like:
- “Treat JPM and NVDA as the only live in-band candidates”
- “Keep ETN in post-print review mode”
- “Use the XOM scorecard before changing any energy posture”

The third is safe routing. The first two are stateful directives. Phase 2 must force `Next Actions` toward verbs like read, confirm, review, reconcile, and only allow act/keep/treat language when the owning surface already makes the same judgment cleanly.

## Minimum acceptable Phase 2 contract
A Phase 2 artifact is not acceptable unless it enforces all of the following.

### 1) Allowed claim shapes are explicit per surface
Every dashboard sentence or bullet introduced by Phase 2 must be typed as one of:
- freshness signal
- unresolved-truth warning
- action-routing item
- owner-first navigation pointer
- bounded orientation summary

Anything that looks like deployment adjudication, catalyst canon, blocker clearance, or thesis resolution is disallowed unless the contract also names the owner note and the exact downgrade behavior on conflict.

### 2) Unresolved-truth language has a mandatory degraded form
When evidence is partial, stale, secondary-only, or owner-conflicted, the dashboard must use unresolved-truth wording such as:
- primary-source capture incomplete; review owner note
- timing path not fully confirmed; owner judgment still governs
- scorecard exists, but deployment state remains owner-held
- dashboard wording reconciled, but final state still unresolved in owner notes

Not acceptable:
- resolved enough
- effectively cleared
- fresh now
- no longer a concern
- use as canon

### 3) Owner-first linking is mandatory
If a dashboard item references a fresh brief, scorecard, or packet-derived object, the link order must prefer:
1. the canonical owner note that currently holds the decision-grade state
2. the supporting brief / scorecard / intelligence artifact
3. only then any broader navigation surface

The dashboard must not train the operator to skip the owner note just because the brief is fresher or more concise.

### 4) Update authority must be sentence-level, not note-level
It is not enough to say a dashboard “summarizes only.”
Phase 2 must say what sentence forms are allowed to summarize and what forms are forbidden.
Minimum rule:
- dashboards may summarize status-of-review, status-of-freshness, and next-reading order
- dashboards may not summarize final state when owner evidence is incomplete or conflicting

### 5) Conflict behavior must preserve the conflict, not smooth it over
If `Executive Brief`, `This Week`, `Next Actions`, and the owner surfaces disagree, the dashboard should not choose the cleaner story.
Minimum acceptable behavior:
- show unresolved status
- identify the owner that governs
- route the user to reconcile there

### 6) Named tickers need claim-type limits
Phase 2 should answer which surfaces may mention tickers and for what purpose.
Minimum safe rule:
- `Executive Brief`: tickers allowed only inside bounded orientation summaries or warning-grade “review this owner” framing
- `This Week`: tickers allowed only inside weekly outcome framing tied to owner notes
- `Next Actions`: tickers allowed only inside action-routing verbs, not standalone posture judgments

## Recommended wording constraints by surface

### Executive Brief
Allowed:
- “New ETN post-earnings review exists; owner judgment remains in Weekly Positioning Review / trigger surfaces.”
- “Fresh scorecards now exist for GOOG and MSFT; entry-state still belongs to owner notes.”

Not acceptable:
- “ETN remains almost deployable.”
- “GOOG and MSFT are now resolved post-earnings names.”

### This Week
Allowed:
- “This week’s outcome is to reconcile post-earnings owner notes and keep unresolved cases explicit.”
- “Use weekly owner notes for live deployment posture; this note only tracks the week’s review priorities.”

Not acceptable:
- “This week’s live board is X, Y, Z.”
- “This week ETN moved into post-earnings review only” unless the owner note is explicitly cited and no owner conflict exists.

### Next Actions
Allowed:
- “Read ETN post-earnings owner notes before changing posture.”
- “Confirm NVDA timing residue in the owner surface before acting.”
- “Reconcile GS deployment wording across owner notes before treating dashboard language as current.”

Not acceptable:
- “Treat X as live.”
- “Keep Y conditional.”
- “Use Z as the canonical read” unless the owner surface explicitly already made that designation.

## Specific contract questions Phase 2 must answer before dashboard edits
1. What exact sentence shapes are allowed for fresh-brief visibility on each of the three dashboard surfaces?
2. What exact degraded wording appears when packet evidence is secondary-only or owner-conflicted?
3. If a scorecard is newer than the weekly owner note, does the dashboard link to the scorecard first or the owner first?
4. Which dashboard surfaces may name tickers in declarative sentences, and under what claim types?
5. What wording is required when a dashboard note is fresher than the canonical owner but not authorized to publish the state change?

## Recommendation
Proceed with Phase 2 only if the contract is written as a sentence-shape and authority contract, not as a content-refresh plan.
The real danger is subtle: the more useful the dashboards become, the easier it is for them to become the de facto source of truth. The safe path is owner-first linking, explicit degraded language, and a bias toward review/routing verbs over state/judgment verbs.

## Verification
- Read-only review completed across the requested workflow, Phase 1 map, Phase 1 QA artifact, dashboard notes, and weekly intelligence / positioning notes
- Wrote exactly one new artifact: `08. Audits/WF23 Phase 2 Contract QA - 2026-05-06.md`
- No dashboard surfaces, queue state, or workflow continuity notes were edited
