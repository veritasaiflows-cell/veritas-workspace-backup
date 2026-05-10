# WF23 Phase 1 Surface Boundary QA - 2026-05-06

## Purpose
Challenge WF23 Phase 1 surface-mapping before any dashboard edits.
This QA pass is read-only and focuses on second-truth-layer risk, owner-boundary ambiguity, and the minimum acceptable mapping standard.

## Files reviewed
- `06. Playbooks/Project Continuity/Workflow 23 - Command Center Fresh Brief and Decision Surface Tightening.md`
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/This Week.md`
- `01. Dashboards/Next Actions.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `02. Markets/Watchlist.md`
- `08. Audits/Retrospective Governance Hardening Pass - 2026-05-06.md`

## QA verdict
Phase 1 is safe to proceed only if the surface map stays strict about dashboards being derived orientation surfaces.
The current stack already shows real owner intent, but it also shows multiple places where dashboard language can drift into hidden publish authority if Phase 1 maps "what to show" without also mapping "who owns the claim" and "what kind of claim is allowed here."

## Highest-risk second-truth-layer failure modes

### 1) Dashboard surfaces restate live state too specifically
`Executive Brief`, `This Week`, and `Next Actions` already contain specific claims about:
- which names are in band
- which names are live candidates
- which warnings are active
- which catalysts matter next

Those are useful orientation summaries, but they become a shadow truth layer if Phase 1 allows dashboard surfaces to carry exact state claims without an attached owner reference and derivation rule.

Risk example:
- `Executive Brief` says JPM / NVDA / GS are the live in-band list
- `Next Actions` says JPM / NVDA are the only live in-band candidates
- `Portfolio Snapshot` says zero deployable-now names and several almost-deployable names

These can all be reconciled with nuance, but they are close enough to sound canonical if the Phase 1 map does not force explicit owner/claim typing.

### 2) Weekly notes and dashboards are already partially overlapping in function
`Weekly Positioning Review` is the canonical weekly operating map.
`Weekly Intelligence Brief` is the recurring synthesis brief.
`This Week` is supposed to be short outcome guidance.
`Executive Brief` is supposed to be high-level orientation.
`Next Actions` is supposed to be the immediate action queue.

In practice, all four currently speak about posture, live names, trust state, and catalyst sequencing.
Without a strict surface map, WF23 could make this overlap easier to navigate but also easier to misuse.

### 3) Watchlist still mirrors deployment-state summaries
`Watchlist` says it is navigation-only, but it still mirrors current deployment state and live action orientation.
That is acceptable only as a thin mirror.
If Phase 1 routes more dashboard freshness or decision signals into this layer without a strict mirror-only rule, it will become another soft truth surface.

### 4) Freshness and unresolved-truth warnings could mutate into implied approval
WF23 explicitly wants fresh brief outputs, unresolved truths, and freshness visibility on Command Center surfaces.
That is good.
But if those appear as plain English summary statements instead of labeled warning/status objects tied to owners, the dashboard layer will quietly start adjudicating truth instead of exposing truth condition.

Example failure:
- "ETN remains almost deployable" is a decision-state summary
- if the true owner is Trigger Sheet / Positioning Review / post-earnings scorecard evidence, the dashboard must present that as derived status with source and caveat, not as independent judgment

## Owner-boundary ambiguities that must be resolved in Phase 1

### A) Portfolio posture vs execution posture
`Portfolio Snapshot` owns portfolio posture and model allocation.
But dashboard notes also summarize live candidates, almost-deployable names, and capital caution.
Phase 1 must separate:
- portfolio-level posture and allocation ownership
- execution-readiness / deployment-state ownership
- dashboard-facing orientation summary

Minimum requirement: the map must name the exact canonical owner for each of these claim types instead of calling them all "portfolio state."

### B) Weekly posture vs immediate action queue
`Weekly Positioning Review` owns the weekly operating map.
`Next Actions` owns what to do next.
The boundary gets blurry when `Next Actions` starts repeating weekly thesis, catalyst interpretation, or trust regime language.

Minimum requirement: `Next Actions` may point to decisions and pending confirmations, but should not become a second weekly positioning note.

### C) Event / catalyst timing ownership
Dashboard notes currently mention dates and catalyst windows.
WF23 should not assume dashboards own timing truth.
If a surface shows next catalysts, the map must specify whether the truth owner is Event Calendar, Weekly Positioning Review, or another canonical schedule note.

### D) Trust / warning ownership
`Executive Brief` contains active dashboard warnings.
That is useful, but Phase 1 must distinguish between:
- validator-owned machine health / freshness evidence
- canonical note-level unresolved truth
- dashboard-level summary of those warnings

If not separated, the dashboard becomes the place where warning severity is effectively decided.

## Minimum acceptable Phase 1 mapping standard
A Phase 1 artifact is not acceptable unless every proposed surface entry includes all of the following fields or their equivalent:

1. **Surface name**
   - exact note / section that will display the item

2. **Claim type**
   - one of: orientation summary, action routing, freshness warning, unresolved-truth warning, report link, or navigation pointer

3. **Canonical owner**
   - the note or artifact that owns the underlying truth

4. **Allowed derived input**
   - the upstream artifact(s) allowed to feed this surface
   - WF21/WF22 outputs must be explicitly marked derived-only

5. **Update authority**
   - whether the surface may summarize only, summarize plus link, or summarize plus show warning state
   - dashboards must not adjudicate deployable status, thesis quality, or blocker clearance independently

6. **Stop-line language rule**
   - what the surface must say when the input is stale, partial, unresolved, warning-grade, or source-conflicted

7. **Conflict rule**
   - what happens when the surface and owner disagree
   - minimum acceptable rule: canonical owner wins, dashboard degrades to warning / link-out / unresolved status

## Minimum acceptable surface behavior by dashboard class

### Executive Brief
Allowed:
- concise orientation
- current focus
- top-level trust/freshness condition
- links to canonical decision surfaces

Not acceptable:
- exact deployment-state adjudication without owner callout
- detailed catalyst sequencing that duplicates weekly owners
- silent synthesis of conflicting canonical states into a cleaner story

### This Week
Allowed:
- intended outcomes
- bounded weekly priorities
- success condition framing

Not acceptable:
- becoming a second Weekly Positioning Review
- carrying name-by-name state logic beyond short orientation framing

### Next Actions
Allowed:
- immediate action routing
- explicit pending decisions
- "read this before acting" sequencing

Not acceptable:
- owning the decision itself
- repeating long-form thesis, posture, or catalyst analysis
- inventing blocker severity

### Watchlist mirror usage
Allowed:
- thin index / mirror / navigation role

Not acceptable:
- becoming a dashboard sink for freshness patches or decision-state nuance
- holding richer deployment commentary than the true owner surfaces

## QA challenge questions Phase 1 must answer explicitly
1. For each proposed dashboard sentence, what exact owner note would overrule it?
2. If WF21 packet output and a canonical note diverge, what does the dashboard show before human reconciliation?
3. If WF22 freshness output detects stale wording but no canonical note has been updated yet, does the dashboard warn or rewrite?
4. Which surfaces may show unresolved truth, and in what wording form?
5. Which surfaces are allowed to mention named tickers at all, and for what claim types?

## Recommendation
Proceed with Phase 1 only if the artifact is built as a boundary map, not a content wish list.
The main risk is not obvious duplication; it is soft authority drift where dashboards become the fastest and therefore de facto trusted place to read live state.
Phase 1 should optimize for honest routing, not for richer summary density.

## Verification
- Read-only review completed across the requested workflow, dashboard, intelligence, portfolio, market, and audit notes
- Wrote exactly one new artifact: `08. Audits/WF23 Phase 1 Surface Boundary QA - 2026-05-06.md`
- No dashboard surfaces, queue state, or workflow continuity notes were edited
