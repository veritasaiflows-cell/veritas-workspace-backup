# WF23 Phase 1 Command Center Surface Map - 2026-05-06

## Purpose
Create one bounded map of the Command Center / dashboard surfaces WF23 may tighten without turning those surfaces into a second truth layer.

## Scope basis
- `06. Playbooks/Project Continuity/Workflow 23 - Command Center Fresh Brief and Decision Surface Tightening.md`
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/This Week.md`
- `01. Dashboards/Next Actions.md`
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `02. Markets/Watchlist.md`
- `06. Playbooks/WF22 Phase 1 Pilot Stale-Claim Inventory and Owner-Surface Map - 2026-05-06.md`
- `08. Audits/Closed Workflow Retrospective Guidance - 2026-05-06.md`
- `08. Audits/Retrospective Governance Hardening Pass - 2026-05-06.md`

## Command Center owner rule
The Command Center layer is an **orientation and access layer only**.
It may:
- summarize what matters now
- expose open decisions
- point to fresh brief artifacts and canonical notes
- surface freshness degradation or unresolved truth warnings

It may not:
- become the owner of deployment state, portfolio posture, risk posture, catalyst canon, or thesis canon
- silently arbitrate contradictions between weekly, portfolio, trigger-sheet, or event-calendar owners
- upgrade machine or packet outputs into decision-grade language on its own

## Minimum mapping standard
Every mapped surface item in WF23 must declare:
- surface name
- claim type
- canonical owner
- allowed derived input
- update authority
- stop-line language rule
- conflict rule

Minimum conflict rule for all Command Center surfaces:
- canonical owner wins
- when owner state and dashboard summary diverge, the dashboard must degrade to unresolved-truth / warning / link-out language rather than silently choosing a side

## Surfaces to tighten

### 1) `01. Dashboards/Executive Brief.md`
- **Function:** top-level orientation for what matters now, current focus, current next move, and trust posture
- **Claim type:** orientation summary, freshness warning, unresolved-truth warning, report link
- **Truth owner(s):**
  - portfolio posture -> `03. Portfolio/Portfolio Snapshot.md`
  - weekly operating stance -> `05. Intelligence/Weekly Positioning Review.md`
  - risk posture -> `07. Risk/Risk Rules.md`
  - event timing -> `05. Intelligence/Event Calendar.md`
- **Allowable derived inputs from WF21/WF22:**
  - WF21 review-packet outputs may contribute a **fresh brief signal** like “new packet exists,” “scorecard completed,” or “post-earnings review still incomplete”
  - WF22 freshness outputs may contribute a **warning or cleanup signal** like “a prior future-tense dashboard claim was stale and has been reconciled”
- **Update authority:** summarize only; summarize plus link-out; summarize plus warning state. No independent state adjudication.
- **Allowable content shape:**
  - one-line freshness-aware summary of what changed materially
  - one-line reminder when a brief or scorecard now exists and should be consulted
  - one-line trust warning when primary capture, validation, or timing remains incomplete
- **Stop line / non-authority language:**
  - “This note does not decide deployment state; use the owning portfolio and weekly notes.”
  - “If packet evidence is incomplete or secondary-only, summarize the uncertainty instead of claiming resolution.”
  - “Do not use this surface to promote a name, clear a blocker, or resolve a contradiction by itself.”
- **Conflict rule:** if this note's summary and an owner surface diverge, the owner wins and `Executive Brief` must degrade to warning / unresolved wording plus owner link-out.

### 2) `01. Dashboards/This Week.md`
- **Function:** short weekly outcome and active-week orientation surface
- **Claim type:** weekly orientation summary, unresolved-truth warning, navigation pointer
- **Truth owner(s):**
  - weekly operating map -> `05. Intelligence/Weekly Positioning Review.md`
  - event timing -> `05. Intelligence/Event Calendar.md`
  - portfolio posture reference -> `03. Portfolio/Portfolio Snapshot.md`
- **Allowable derived inputs from WF21/WF22:**
  - WF21 review packets may supply “this week’s fresh review items” and “this week’s open follow-ups” as bounded orientation bullets
  - WF22 freshness outputs may supply “which high-risk stale phrases were cleaned up” or “which unresolved stale surfaces still need human attention”
- **Update authority:** summarize only; summarize plus link-out; warning visibility only. No independent weekly-state ownership.
- **Allowable content shape:**
  - this week’s intended outcomes, stated as derived from the canonical weekly positioning view
  - catalyst-window reminders only when they point back to the event-calendar or weekly owner
  - unresolved-truth reminders such as incomplete primary-source capture or follow-up still pending
- **Stop line / non-authority language:**
  - “Do not let this note carry its own catalyst canon or deployment map.”
  - “If event timing or weekly stance differs elsewhere, point to the owner rather than restating a guessed answer.”
  - “Freshness warnings stay visible here even when the final judgment belongs to another note.”
- **Conflict rule:** if weekly owner notes disagree with this summary, `This Week` must point to the owner and show unresolved status rather than act like the authoritative weekly map.

### 3) `01. Dashboards/Next Actions.md`
- **Function:** immediate action queue for Randall; a routing surface, not a decision engine
- **Claim type:** action routing, report link, unresolved-truth warning
- **Truth owner(s):**
  - weekly action posture -> `05. Intelligence/Weekly Positioning Review.md`
  - portfolio posture / constraints -> `03. Portfolio/Portfolio Snapshot.md`
  - deployment logic -> `03. Portfolio/Deployment Trigger Sheet.md`
  - fresh report / scorecard references -> `05. Intelligence/Weekly Intelligence Brief.md` and note-level scorecards
- **Allowable derived inputs from WF21/WF22:**
  - WF21 packet outputs may create bounded prompts like “read the new scorecard before touching XOM” or “decide whether ETN ambiguity is resolved after primary capture”
  - WF22 freshness outputs may create bounded cleanup actions like “inspect a still-stale dashboard sentence” or “confirm that a known stale claim no longer appears on owner surfaces”
- **Update authority:** route work; point to owners; show warning-grade constraints. No independent deployment/thesis/posture authority.
- **Allowable content shape:**
  - concrete next-step routing actions
  - explicit “read this owner first” links
  - short trust-aware action constraints when unresolved evidence blocks a clean decision
- **Stop line / non-authority language:**
  - “This note routes work; it does not authorize capital deployment or thesis changes.”
  - “Do not convert a queue item into a state change unless the owning note already supports it.”
  - “If a machine or packet signal is warning-grade, the action here should be to review, not to conclude.”
- **Conflict rule:** if a routed action implies a state change not yet supported by the owner surface, `Next Actions` must reduce to “review / confirm / read first” language only.

## Upstream derived-input classes allowed into Command Center

### WF21 inputs allowed
- existence of a fresh daily / weekly review packet
- existence of a fresh scorecard or post-earnings prep artifact
- explicit open questions already named in the packet
- evidence-quality labels such as complete / partial / primary-source-missing when already established upstream

### WF21 inputs not allowed
- auto-published thesis judgments
- auto-promoted deployment states
- inferred certainty beyond the packet’s evidence grade

### WF22 inputs allowed
- stale-claim or alignment-cleanup warnings on approved owner-facing dashboard surfaces
- explicit note that a previous future-tense or pre-event phrase was reconciled
- explicit note that a stale issue remains unresolved and still needs human cleanup

### WF22 inputs not allowed
- direct mutation authority over portfolio, trigger-sheet, technical-sheet, or macro truth surfaces through the Command Center
- contradiction arbitration where owner notes disagree materially
- conversion of partial freshness evidence into full “all clear” language

## Report-intelligence access surfaces to expose, not own
These may be linked from Command Center surfaces for retrieval convenience, but they remain report/intelligence owners or source artifacts rather than dashboard-owned content:
- `05. Intelligence/Weekly Intelligence Brief.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `03. Portfolio/Portfolio Snapshot.md`
- relevant scorecards / post-earnings notes when they exist
- `tmp/` artifacts only indirectly via human-written notes, not as direct canon

## Explicit non-scope mirror surface
`02. Markets/Watchlist.md` is intentionally **not** part of WF23 Phase 1 tightening.
It already acts as a thin mirror/navigation surface and should not become a richer sink for freshness patches, decision-state nuance, or dashboard-side adjudication through this workflow.

## Unresolved-truth / freshness warning contract
When WF23 later tightens live dashboard wording, unresolved truth should appear in explicit degraded-language form such as:
- primary-source capture incomplete
- timing path not fully confirmed
- scorecard exists but deployment status still belongs to the trigger / portfolio layer
- stale dashboard wording was cleaned up, but final owner judgment remains elsewhere

Avoid:
- “resolved” when the source note still says conditional, almost deployable, or review-only
- “fresh” as shorthand for “decision-grade”
- any summary that hides owner-surface disagreement

## Surface-by-surface authority summary
| Surface | Role | Claim type | Canonical owner(s) it may summarize | Allowed WF21/WF22 derived use | Update authority | Conflict rule | Must not do |
|---|---|---|---|---|---|---|---|
| `01. Dashboards/Executive Brief.md` | top-level orientation | orientation summary / freshness warning / unresolved-truth warning / report link | Portfolio Snapshot, Weekly Positioning Review, Risk Rules, Event Calendar | fresh-brief signal, scorecard-exists signal, freshness/trust warning | summarize/link/warn only | owner wins; degrade to warning/link-out on conflict | own deployment state, clear blockers, resolve contradictions |
| `01. Dashboards/This Week.md` | weekly outcome / orientation | weekly orientation summary / unresolved-truth warning / navigation pointer | Weekly Positioning Review, Event Calendar, Portfolio Snapshot | weekly packet follow-up signal, stale-surface warning, outcome reminder | summarize/link/warn only | owner wins; unresolved status on conflict | own catalyst canon, carry an independent deployment map |
| `01. Dashboards/Next Actions.md` | immediate action routing | action routing / report link / unresolved-truth warning | Weekly Positioning Review, Portfolio Snapshot, Trigger Sheet, Weekly Intelligence Brief | review-this-next routing, inspect-this-warning routing, read-the-owner-first routing | route/link/warn only | reduce to review-first language on conflict | authorize trades, rewrite thesis, infer state changes |

## Phase 1 verdict
WF23 Phase 1 should stay bounded to these three dashboard surfaces.
The real tightening opportunity is not adding more content; it is clarifying:
- which owner each surface summarizes
- which WF21/WF22 signals are safe to expose as derived orientation only
- which stop-line phrases must remain visible whenever truth is incomplete

## Verification
- readback completed on the named dashboard, intelligence, portfolio, watchlist, WF22, and retrospective audit files
- mapped each dashboard surface against its explicit role text and canonical-owner language already present in the notes
- confirmed this artifact does not mutate any dashboard surface or queue/control-plane state
