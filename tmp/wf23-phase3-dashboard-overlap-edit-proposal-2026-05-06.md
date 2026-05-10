# WF23 Phase 3 Dashboard Overlap Edit Proposal - 2026-05-06

## Purpose
Provide one bounded exact-edit proposal for the three approved dashboard notes so they stop acting like a second live-state truth layer and align with the WF23 owner-first contract.

This artifact does **not** edit live notes.
It proposes the smallest safe wording changes only.

## Inputs reviewed
- `06. Playbooks/Project Continuity/Workflow 23 - Command Center Fresh Brief and Decision Surface Tightening.md`
- `06. Playbooks/WF23 Phase 1 Command Center Surface Map - 2026-05-06.md`
- `06. Playbooks/WF23 Phase 2 Fresh Brief and Decision-Point Contract - 2026-05-06.md`
- `08. Audits/WF23 Phase 1 Surface Boundary QA - 2026-05-06.md`
- `08. Audits/WF23 Phase 2 Contract QA - 2026-05-06.md`
- `01. Dashboards/Executive Brief.md`
- `01. Dashboards/This Week.md`
- `01. Dashboards/Next Actions.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `05. Intelligence/Event Calendar.md`

## Working diagnosis
The highest-risk overlap is concentrated in three dashboard sections:
- `Executive Brief` uses declarative live-state wording in `What matters now` and `Current next move`
- `This Week` duplicates weekly deployment judgments in `Primary outcome`, `This week's priorities`, and `Success condition`
- `Next Actions` mixes safe routing with state-authority language in `Current best next actions`

The owner notes currently say:
- `Portfolio Snapshot`: **zero deployable-now names**; JPM, NVDA, GS, MSFT, ETN, GOOG are almost deployable only
- `Deployment Trigger Sheet`: same owner-state posture, with explicit ALMOST / DO NOT TOUCH / WATCH distinctions
- `Weekly Positioning Review`: canonical weekly map, but itself still contains some stronger state language than the dashboards should mirror
- `Event Calendar`: ETN is already reported/interpreted; NVDA timing remains unconfirmed; BRK.B and XOM are post-event follow-up cases

So the smallest safe fix is **not** broad rewriting.
It is to degrade the dashboard wording where it currently publishes state, and convert it to:
- owner-first orientation
- review/routing verbs
- explicit unresolved-truth language where needed

## Exact-edit proposals

### 1) `01. Dashboards/Executive Brief.md`

#### Target section
`## What matters now`

#### Replace block
**Old:**
```md
1. **The live action list is narrow.** **JPM**, **NVDA**, and **GS** are the names currently in band. GS is now a confirmed tactical secondary to JPM at Tier 2 sizing. **ETN** is no longer a pre-print decision; it has already reported and remains a post-earnings review item with incomplete primary-source capture.
2. **GOOG and MSFT are no longer unresolved post-earnings cases.** The scorecards are now written, but both names still stay off the live board because GOOG is extended above band and MSFT still needs cleaner repair below the 200-day.
3. **XOM reported on May 1 and the scorecard is done, but the name is still benched.** Oil is strong, but follow-through still is not clean enough to put energy back on the active board.
4. **BRK.B reported May 2 and the ETN / AMD / SMCI cluster lands this week.** That is the next real catalyst window.
5. **Trust is improved, not perfect.** The dashboard layer is fresh through the 2026-05-01 close and validation is clean again, but execution freshness still stays usable-with-caution because the policy model is simplified and true pre-market tape remains limited.
```

**New:**
```md
1. **The live setup list remains narrow, but owner notes still govern actual state.** Use [[03. Portfolio/Portfolio Snapshot]] and [[03. Portfolio/Deployment Trigger Sheet]] for the canonical deployment view; the current owner layer still keeps **JPM**, **NVDA**, **GS**, **MSFT**, **ETN**, and **GOOG** in almost-deployable / review-first territory rather than deployable-now status.
2. **Fresh post-earnings interpretation now exists for GOOG, MSFT, XOM, and ETN.** Use the owner notes and scorecards before changing posture; fresh review artifacts improve visibility, not automatic deployability.
3. **Some event paths are closed, but unresolved truth still matters.** **ETN** remains a post-earnings follow-up case with incomplete primary-source capture, and **NVDA** timing still carries a narrow confirmation gap in the owner layer.
4. **The catalyst window has shifted from pre-event planning to post-event reconciliation.** Use [[05. Intelligence/Event Calendar]] and [[05. Intelligence/Weekly Positioning Review]] for the current event and weekly operating map.
5. **Trust is improved, not perfect.** Validation is clean again, but execution freshness still stays usable-with-caution because the policy model is simplified and true pre-market tape remains limited.
```

#### Why this is the smallest safe change
- preserves the section structure and five-bullet shape
- removes dashboard-published claims like “currently in band” and “confirmed tactical secondary” from the top orientation layer
- keeps useful freshness visibility, but reframes it as owner-subordinate
- explicitly surfaces unresolved truth instead of smoothing it over

---

#### Target section
`## Current next move`

#### Replace block
**Old:**
```md
- treat **JPM**, **NVDA**, and **GS** as the live in-band candidates — GS at Tier 2 sizing, subordinate to JPM
- treat **ETN** as an event-risk decision: stand aside into the May 5 print or define a post-print entry-on-weakness plan explicitly
- use the **XOM** scorecard as the canonical read, but keep energy benched until follow-through improves
- use the new **GOOG** and **MSFT** scorecards as canon, but keep both names out of the live deployment list until entry quality improves
```

**New:**
```md
- use [[03. Portfolio/Deployment Trigger Sheet]] and [[03. Portfolio/Portfolio Snapshot]] before treating any name as a real add; the owner layer still holds deployable-state authority
- review the current **ETN** post-earnings owner notes before changing industrials posture; unresolved primary-source follow-up still matters
- use the **XOM** scorecard and owner notes before changing any energy posture
- use the **GOOG** and **MSFT** scorecards for post-earnings context, but keep entry judgment in the weekly / trigger owners until setup quality improves
```

#### Why this is the smallest safe change
- keeps the short action-oriented section intact
- converts state/judgment verbs (“treat as live”) into routing verbs (“use”, “review”)
- removes stale pre-print wording for ETN

---

### 2) `01. Dashboards/This Week.md`

#### Target section
`## Primary outcome`

#### Replace block
**Old:**
```md
Finish the week with a truthful visible board:
- **JPM** and **NVDA** recognized as the primary live in-band names, with **GS** now explicit as a deployable-now tactical secondary
- **ETN** moved out of pre-print status and into post-earnings review only
- **GOOG** and **MSFT** kept almost deployable only — post-earnings revalidation is explicit, but entry discipline still matters
- **XOM** kept benched even after the May 1 report is interpreted
- the highest-risk stale notes no longer speaking in late-April future tense
```

**New:**
```md
Finish the week with a truthful visible board:
- the dashboard layer reflects the owner notes honestly instead of publishing its own live-state shorthand
- post-earnings names such as **ETN**, **GOOG**, **MSFT**, and **XOM** are routed through current owner notes and scorecards rather than summarized as self-standing state changes
- unresolved items stay explicit, especially where primary-source capture or timing confirmation is still incomplete
- the highest-risk stale notes no longer speak in late-April future tense
```

#### Why this is the smallest safe change
- preserves the “truthful visible board” intent
- removes a second weekly deployment map from the dashboard layer
- aligns success to honesty and routing, not dashboard adjudication

---

#### Target section
`## This week's priorities`

#### Replace subsection
**Old subsection 1:**
```md
1. **Keep the active setup list narrow**
   - **JPM** and **NVDA** are the primary live in-band names.
   - **GS** is now a deployable-now tactical secondary at Tier 2 sizing, still subordinate to JPM.
   - **ETN** is no longer a pre-print item; it has already reported and remains under post-earnings review pending primary-source follow-up.
   - No chase above bands.
```

**New subsection 1:**
```md
1. **Keep the active setup list narrow without turning this note into the live board**
   - Use [[05. Intelligence/Weekly Positioning Review]], [[03. Portfolio/Portfolio Snapshot]], and [[03. Portfolio/Deployment Trigger Sheet]] for actual state.
   - Keep dashboard wording in review-first terms when names are still almost deployable, post-earnings, or timing-sensitive.
   - **ETN** is now a post-earnings follow-up case, and unresolved primary-source capture should stay explicit.
   - No chase above bands.
```

#### Replace subsection
**Old subsection 4:**
```md
4. **Process the immediate next catalysts without widening scope**
   - **BRK.B** already reported on May 2; post-print bench state is explicit, but the scorecard / next-date cleanup still needs completion.
   - **ETN / AMD / SMCI** and the rest of the May 4–8 cluster next week.
```

**New subsection 4:**
```md
4. **Process the current catalyst follow-up without widening scope**
   - **BRK.B** already reported on May 2; keep the post-print cleanup and owner-note sync explicit.
   - **ETN / AMD / SMCI** have already reported; use the current scorecards and owner notes for follow-up rather than leaving them framed as upcoming.
```

#### Replace block
**Old `## Success condition`:**
```md
By the end of this week, we should have:
- the highest-risk visible notes speaking from current evidence, not from Apr 29 future tense
- **JPM / NVDA / GS / ETN** clearly framed as the real live action list, with GS kept subordinate to JPM and ETN kept conditional into earnings
- **GOOG / MSFT** clearly framed as almost deployable post-earnings names, while **XOM** stays honestly benched
- the next catalyst week reduced to a manageable short list instead of another stale-note pileup
```

**New:**
```md
By the end of this week, we should have:
- the highest-risk visible notes speaking from current evidence, not from Apr 29 future tense
- dashboard surfaces routing live questions back to canonical owners instead of publishing a second action list
- post-earnings and timing-sensitive names framed honestly as review-first, owner-bound, or unresolved where that is still true
- the next catalyst follow-up reduced to a manageable short list instead of another stale-note pileup
```

#### Why these are the smallest safe changes
- keeps most of the note intact
- only downgrades the subsections currently publishing weekly state
- fixes the already-stale “next week” / upcoming-cluster phrasing

---

### 3) `01. Dashboards/Next Actions.md`

#### Target section
`## Current best next actions (as of 2026-05-03)`

#### Replace items 1, 2, 4, and 5
**Old item 1:**
```md
1. **Treat JPM and NVDA as the only live in-band candidates — but not as auto-buys**
   - **JPM** closed at 312.47 inside the refreshed 306.82–318.12 band.
   - **NVDA** closed at 198.45 inside the 188.03–199.28 band.
   - Size discipline still matters because the dashboard layer is warning-grade and NVDA crowding risk is still real.
   - Use [[03. Portfolio/Deployment Trigger Sheet]] and [[03. Portfolio/Technical Entry and Invalidation Sheet]] before treating either as a real add.
```

**New item 1:**
```md
1. **Use the owner layer before treating JPM or NVDA as real adds**
   - Read [[03. Portfolio/Deployment Trigger Sheet]] and [[03. Portfolio/Portfolio Snapshot]] first; both still keep deployable-now authority and currently hold live candidates in almost-deployable territory.
   - Size discipline still matters because the dashboard layer is warning-grade and NVDA crowding risk is still real.
   - Use [[03. Portfolio/Technical Entry and Invalidation Sheet]] before acting on price-location alone.
```

**Old item 2:**
```md
2. **Keep ETN in post-print review mode**
   - **ETN** is no longer a pre-print decision. The live issue is post-earnings interpretation quality because direct primary capture did not land cleanly.
   - Default posture should stay review-only until primary-source capture and next-session confirmation remove the remaining ambiguity.
   - No chase above written bands.
```

**New item 2:**
```md
2. **Review ETN through the post-earnings owner path before changing posture**
   - **ETN** is now a post-earnings follow-up case, and direct primary capture still did not land cleanly.
   - Keep this review-only until owner notes absorb primary-source follow-up and next-session confirmation removes the remaining ambiguity.
   - No chase above written bands.
```

**Old item 4:**
```md
4. **Use the GOOG and MSFT scorecards, but keep both names off the live board for now**
   - The post-earnings note / trigger / interpretation gap is now closed.
   - **GOOG** still needs a pullback into the written band.
   - **MSFT** still needs either a cleaner pullback or better 200-day repair.
```

**New item 4:**
```md
4. **Use the GOOG and MSFT scorecards for context, but leave state judgment with the owner notes**
   - The post-earnings interpretation gap is closed, but fresh scorecards do not by themselves create deployable-now status.
   - **GOOG** still needs a pullback into the written band.
   - **MSFT** still needs either a cleaner pullback or better 200-day repair.
```

**Old item 5:**
```md
5. **Process the next catalyst cluster without widening scope**
   - **BRK.B** reported May 2; post-print posture confirmed benched — scorecard still pending.
   - **ETN, AMD, SMCI, EOG, LDOS, ET, MPLX, WMB, PLTR, KTOS, LNG** hit next week.
   - Keep the update path evidence-first and selective.
```

**New item 5:**
```md
5. **Process the current catalyst follow-up without widening scope**
   - **BRK.B** reported May 2; keep post-print cleanup explicit until the scorecard path is complete.
   - **ETN, AMD, and SMCI** have already reported; use their current scorecards and owner notes for follow-up. Keep the rest of the May window anchored to [[05. Intelligence/Event Calendar]].
   - Keep the update path evidence-first and selective.
```

#### Why this is the smallest safe change
- preserves the actionable queue format
- keeps the safe routing items already present
- removes “treat / keep” language that reads like dashboard state authority
- corrects already-outdated catalyst timing wording

## Edits intentionally not proposed
- no change to role/boundary headers; they are already aligned with the owner-first contract
- no change to `Executive Brief` trust-warning section; it already behaves like warning-grade orientation
- no change to `Next Actions` “If there are only 15 minutes” and “If there is a full focused session”; those are routing-oriented already
- no attempt to clean overlapping state language inside the owner notes themselves; that is outside this bounded pass

## Verification performed
- compared the three dashboard notes against the Phase 1 map and Phase 2 contract
- checked the proposed wording against canonical owner posture in:
  - `03. Portfolio/Portfolio Snapshot.md`
  - `03. Portfolio/Deployment Trigger Sheet.md`
  - `05. Intelligence/Weekly Positioning Review.md`
  - `05. Intelligence/Event Calendar.md`
- confirmed the proposal only targets dashboard sections currently publishing second-truth overlap
- confirmed no live dashboard files were edited

## Proposed implementation order
1. `Executive Brief` exact replacements
2. `This Week` exact replacements
3. `Next Actions` exact replacements
4. readback check that no dashboard sentence still claims deployable/live state without owner framing

## Verdict
A very small wording pass should be enough.
The main fixes are:
- replace dashboard state publication with owner-first routing
- keep freshness visible without equating freshness to decision quality
- make unresolved truth explicit where ETN and NVDA still have real residue
- remove stale upcoming-catalyst phrasing now that ETN / AMD / SMCI already reported
