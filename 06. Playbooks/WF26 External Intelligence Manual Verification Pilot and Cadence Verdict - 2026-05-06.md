# WF26 External Intelligence Manual Verification Pilot and Cadence Verdict - 2026-05-06

## Purpose

Capture the bounded manual-proof pass for Workflow 26 after the Phase 1 source / sleeve map was tightened and de-duplicated.

This note covers:
- Phase 2 manual verification-object proof
- Phase 3 smallest useful recurring-review design
- Phase 4 usefulness verdict

## Evidence used

Primary pilot artifacts:
- `tmp/research-automation/raw-events-wf21-sunday-phase2-2026-05-06.json`
- `tmp/research-automation/intake-packets-20260506-152048.json`
- `06. Playbooks/Fresh External Intelligence Source and Sleeve Map - WF26 Phase 1.md`
- `06. Playbooks/Research Department Downstream Handoff Contract.md`
- `06. Playbooks/Research Automation Raw Event Input Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Research Automation Routing and Promotion Contract.md`

Owner / consumer surfaces checked:
- `02. Markets/Macro Regime Dashboard.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `02. Markets/Watchlist.md`

## Phase 2 - Manual verification-object pilot

### Pilot cases used

1. **Rates / credit / policy backdrop remains stable**
- source quality: Tier 1 primary + Tier 2 corroboration
- outcome: `archive_weekly_digest`
- why it matters: proves the lane can reject fake urgency even when the backdrop is real

2. **AMD Q1 AI infrastructure read-through**
- source quality: Tier 1 primary (AMD IR) + Tier 2 reviewed summary
- outcome: `thesis_review_queue`
- why it matters: proves attributable external-intelligence can feed the research lane without promoting pilot names automatically

3. **NVDA timing confirmation remains unresolved**
- source quality: Tier 2 trusted signal plus incomplete primary-capture path
- outcome: unresolved review object carried forward intentionally
- why it matters: proves the lane can keep a timing-sensitive company item open honestly instead of overstating certainty

4. **Oil / Hormuz verification object remains open**
- source quality: rumor / blocked-source only
- outcome: `stop_line_no_promotion`
- why it matters: proves fast-moving geopolitical / energy chatter stays verification-only when attributable evidence is missing

### What Phase 2 proved
- at least one unresolved event stayed open honestly (**NVDA timing**, **Oil / Hormuz**)
- at least one high-confidence attributable development fed a real review surface without silent canon drift (**AMD read-through**)
- low-materiality but real macro context stayed digest-only instead of becoming fake action (**rates / credit / policy**)
- contradiction / uncertainty handling stayed explicit instead of being rounded away

### Operator notes on noise and miss risk
- The bounded sleeve map materially reduced noise versus open-ended fresh-news scanning.
- The biggest miss risk is not lack of input volume; it is false promotion from incomplete attribution chains.
- The Oil / Hormuz object is the right model: high potential materiality does not justify promotion when the source chain is weak.
- The NVDA timing object is also the right model: trusted secondary timing can justify watchfulness without justifying canonical certainty.

## Phase 3 - Smallest useful recurring-review design

### Recommended cadence
- **No standalone WF26 cron in v1.**
- Reuse the existing review windows already proved or designed elsewhere:
  - **post-close review window** for company / sector read-throughs
  - **Sunday review window** for macro, geopolitical, and unresolved carry-forward objects
  - **event-driven manual only** for fast-moving geopolitical or supply-shock cases

### Interaction with WF21
- WF21 remains the packet-window spine.
- WF26 supplies the source / sleeve and verification rules for what may enter those windows.
- WF26 does not create a parallel writer lane or separate recurring source-bundle engine.

### Downgrade / stop-line rules
- rumor-tier or unattributed geopolitical / energy items remain verification-only
- timing-critical company items without clean primary capture remain unresolved even if trusted secondary timing exists
- duplicate or circular corroboration never counts as multiple confirmations
- packet outputs may recommend desk review, but they may not mutate Trigger Sheet, Portfolio Snapshot, Macro Regime Dashboard, or Weekly Positioning Review directly

### Proof surfaces
- raw-event input file
- intake packet file
- explicit route / no-route / stop-line outcomes
- downstream review-surface naming
- operator note when an unresolved object is intentionally carried forward

## Phase 4 - Usefulness verdict

### Verdict
- **Close WF26 with follow-up.**
- The lane is useful enough to keep as a bounded review-first operating layer.
- It is **not** strong enough to justify a standalone recurring cron or autonomous widening.

### Why this closes honestly
- source classes are explicit
- unresolved-truth handling is explicit
- fast-moving geopolitical and timing-sensitive cases stayed honest under pressure
- downstream research / macro / portfolio consumers are now explicit and ownership-safe
- the lane stayed low-noise because it used bounded sleeves and approved-source rules instead of freeform monitoring

### Residue kept visible
- no standalone WF26 recurring cron
- no autonomous geopolitical or fresh-news lane
- future packet use should stay downstream of WF21 windows unless a separate widening workflow is approved

### Next trust gap
- use Workflow 22 only for mechanical freshness candidates that emerge from this bounded intake path; do not let freshness patching become a disguised thesis-rewrite lane
