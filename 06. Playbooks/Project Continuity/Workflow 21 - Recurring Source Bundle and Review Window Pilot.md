# Workflow 21 - Recurring Source Bundle and Review Window Pilot

## Objective
- Turn the approved research-automation source-bundle contract into a real low-noise operating lane.
- Define what evidence enters the system, when it is collected, and how it feeds review packets into the daily and weekly chain without creating a second truth layer.
- Keep all output fail-closed: review packets only, no autonomous canonical mutation, no autonomous thesis/posture change.

## Current State
- The canonical source-bundle contract already exists: `06. Playbooks/Research Automation Source Bundle Contract.md`.
- The exact v1 pre-packet input shape now exists: `06. Playbooks/Research Automation Raw Event Input Contract.md`.
- The intake-packet contract and routing / promotion contract already exist and are approved downstream consumers.
- `scripts/research_intake_packet.py` now exists as a review-only prototype and has been run successfully on sample input.
- No recurring research-source cron is live yet.
- Existing finance refresh jobs remain the only recurring finance writers.
- As of 2026-05-05, the finance writer lane now has an explicit late-earnings cadence: the morning chain refreshes `earnings-calendar.json` before `post_earnings_prep.py`, carries `post-earnings-note-targets.json` into the pre-market surface, and a weekday 15:30 America/Phoenix isolated cron now runs the `post-earnings` window as a catch-up for reporters that miss the first 13:20 post-close pass.
- That means Workflow 21 should not invent a duplicate pre-market or post-close earnings writer; any later research-source packet lane must consume these artifacts or sit strictly downstream of them.
- Workflow 25 is now the immediate upstream consumer this lane must serve, so the pilot coverage set and packet outputs should be shaped around real research-department intake and admission needs rather than generic automation widening.
- Workflow 29 is now closed with follow-up, so this lane becomes the active downstream consumer that should start using the newly landed proof surfaces rather than leaving them theoretical.
- On 2026-05-05, Phase 1 moved into live artifacts: `06. Playbooks/Research Automation Source Map - WF21 Pilot v1.md` now pins the pilot source tiers and scope, `tmp/research-automation/raw-events-wf21-phase1-2026-05-05.json` now exists as the first real starter input, and a bounded manual packet run against that file produced 4 review-only packets with 1 stop-line, 1 canonical-freshness patch candidate, 1 thesis-review route, and 1 dashboard-watch-item route while keeping `canonical_mutation_allowed: false`.
- On 2026-05-06, operator review of `tmp/research-automation/intake-packets-20260506-021940.json` confirmed that output is honest enough to count as the first real Phase 2 post-close dry run: it shows routed items, an unresolved stop-line object, and review-only posture without autonomous canon mutation.
- On 2026-05-06, `tmp/research-automation/raw-events-wf21-sunday-phase2-2026-05-06.json` was staged as the missing Sunday-oriented input and `python scripts\research_intake_packet.py --input tmp\research-automation\raw-events-wf21-sunday-phase2-2026-05-06.json` produced `tmp/research-automation/intake-packets-20260506-152048.json`. That output is honest enough to count as the missing Sunday Phase 2 proof: it shows 1 archive/digest route, 1 thesis-review route, 2 stop-lines, and an explicitly unpromoted geopolitical verification object while keeping `canonical_mutation_allowed: false`.
- On 2026-05-06, the smallest useful Phase 3 design artifact landed as `06. Playbooks/Research Automation Review Window Cron Design - WF21 Phase 3.md`. It names one post-close and one Sunday review window, keeps both downstream of the finance writers, and explicitly consumes the 15:30 post-earnings catch-up instead of duplicating it. No cron job was created in this pass.
- On 2026-05-06, Phase 4 closed with a **HOLD** verdict after audit-backed packet comparison. The lane proved useful as a manual review-packet surface, but it is not wide enough for live cron activation yet: the post-close packet run produced 4 packets with 1 canonical-freshness candidate, 1 thesis-review item, 1 stop-line, and 1 dashboard-watch item; the Sunday packet run produced 4 packets with 1 archive/digest item, 1 thesis-review item, and 2 stop-lines. The repeated NVDA timing stop-line and Oil/Hormuz verification object prove fail-closed behavior, but also argue against widening now. Closeout audit: `08. Audits/WF21 Schema Island and Closeout Audit - 2026-05-06.md`.
- On 2026-05-05/06, a local coding skill spine was added to support the next implementation passes without importing generic outside doctrine. Current routing uses `skills/disciplined-implementation/SKILL.md` for implementation/refactor work and `skills/workspace-qa-pass/SKILL.md` for code/diff QA; `skills/code-review-auditor/SKILL.md` and `skills/safe-refactor-planner/SKILL.md` are now deprecated compatibility routers only. Use that spine when WF21 moves from packet review into bounded implementation or cron-design work.

## Scope
- define the v1 approved source bundle by category and trust tier
- define the narrow pilot coverage map
- define the raw-event intake object that the packet script will consume
- define the daily and weekly review windows that may run packet assembly
- define downgrade and stop-line behavior when evidence quality is weak
- define how unresolved truths and fast-moving geopolitical events stay visible as verification objects instead of being forced into false certainty
- prove one low-noise packet lane before widening source coverage

## Out of Scope
- freeform web trawling
- broad research-universe expansion
- autonomous routing into canonical notes
- autonomous thesis, posture, deployment-state, or queue mutation
- per-ticker cron sprawl

## Sequential phase approach

2026-05-05 operator review:
- Keep WF21 active, but do **not** widen it into a broad news/search automation lane yet.
- The existing morning, post-close, and 15:30 post-earnings finance chains already own earnings-date prep and post-earnings target staging; WF21 must stay downstream as a review-packet lane.
- Clean closure requires proof from one real manual packet and one designed cron-backed cadence, not just more contract text.

### Phase 1 - Source map and coverage set
Purpose:
- convert the source-bundle contract into a concrete v1 source map with explicit coverage ownership

Required outputs:
- approved source categories by tier
- blocked / low-confidence categories
- pilot coverage set for 3-5 names plus 1 macro/geopolitical sleeve
- raw-event intake file contract

Status:
- completed

Close criteria:
- pilot names are explicitly limited to the current near-deployable / read-through set: **JPM, NVDA, ETN, MSFT, GOOG** plus one macro/geopolitical sleeve
- approved source tiers and blocked source classes are written in the raw-event file or an adjacent source-map note
- the first raw-event input file exists under `tmp/research-automation/` and uses the approved input contract exactly

### Phase 2 - Manual review-window dry run
Purpose:
- prove the input shape, packet quality, and routing honesty before cron owns a schedule

Required outputs:
- one manual post-close packet run
- one manual Sunday packet run
- reviewed packet examples with stop-line and no-route behavior visible
- at least one unresolved-truth / geopolitical verification example that remains explicitly open instead of being over-promoted
- operator notes on noise, misses, and source gaps

Status:
- completed

Close criteria:
- one real post-close packet has been run from the Phase 1 input file
- packet output shows at least one routed item and at least one held / no-route / unresolved-truth item
- operator review confirms the packet is useful without creating a second truth layer

### Phase 3 - Cron-backed packet assembly design
Purpose:
- add the smallest useful recurring review cadence after the manual dry run is credible

Required outputs:
- one post-close review packet window
- one Sunday weekly packet window
- dependency chain, downgrade rules, and overlap-owner map
- explicit validation-proof plan naming the future cron history and workspace artifacts

Status:
- completed

Close criteria:
- cron design names schedule, dependency order, stop lines, expected artifacts, response contract, and no-writer-overlap rule
- design keeps canonical note mutation manual-only
- design says how the 15:30 post-earnings catch-up is consumed without duplicating it

### Phase 4 - Pilot proof and widen / hold decision
Purpose:
- decide whether the source bundle is useful enough to keep or widen

Required outputs:
- pilot usefulness verdict
- noise / miss analysis
- widen / hold / stop decision
- next approved expansion path or explicit no-go

Status:
- completed

Close criteria:
- pilot verdict is one of: widen, hold, or stop
- noise / miss analysis is documented from actual packet outputs
- if widened, the next coverage expansion is named and still narrow

## Recommended clean-close sequence

1. **Finish Phase 1 only.** Write the v1 source map and first real raw-event input for JPM / NVDA / ETN / MSFT / GOOG plus one macro/geopolitical sleeve.
2. **Run one manual post-close packet.** Use `scripts/research_intake_packet.py`; do not schedule anything yet.
3. **Review packet quality.** Confirm route discipline, unresolved-truth handling, and no autonomous note mutation.
4. **Draft cron-backed design only after manual proof.** One post-close window and one Sunday window are enough for v1.
5. **Close with a widen / hold / stop verdict.** If evidence is noisy or low-value, hold rather than widen.

## Daily / Weekly chain insertion
- **Post-close chain**: finance refresh remains the writer; this workflow may add one downstream review-packet assembly step after the refresh window completes.
- **Late post-close catch-up**: finance refresh now also owns a 15:30 post-earnings catch-up window for tracked reporters that land after the first post-close run; this workflow must stay downstream of that owner surface too.
- **Sunday chain**: weekly refresh remains the writer; this workflow may add one downstream weekly-digest packet assembly step after Sunday refresh artifacts exist.
- **Event-driven path**: stays manual in v1, especially for unresolved truths and fast-moving geopolitical verification.
- **Pre-market**: no recurring research-source sweep in v1 unless Phase 3 proves a real need; the existing morning finance chain now already carries overnight earnings review state into the pre-market snapshot.

## Operating chain
1. collect approved-source events only
2. write them into `Research Automation Raw Event Input Contract.md` shape
3. run `python scripts\research_intake_packet.py --input <file>`
4. inspect packet routes, stop lines, and open questions
5. push only allowed review outputs forward:
   - archive / weekly digest
   - dashboard / weekly intelligence review item
   - thesis-review queue candidate
   - canonical freshness patch candidate
6. hand only high-confidence narrow freshness candidates to WF22

## Immediate-use posture
Use it now as a manual operator lane:
1. collect a narrow raw-event input set for pilot names / macro sleeve
2. run `python scripts\research_intake_packet.py --input <file>`
3. inspect packet routes and stop lines
4. for unresolved truths or geopolitical events, allow the packet to stay open as a verification object rather than forcing a premature route
5. promote only into review surfaces allowed by the routing contract
6. leave canonical notes manual-only

## Acceptance Gates
Workflow 21 should not close unless all are true:
1. approved source categories and blocked categories are explicit
2. the pilot coverage map is explicit and still narrow
3. one manual post-close run and one manual Sunday run are proved
4. one cron-backed post-close and one cron-backed Sunday design exist without writer overlap
5. stop-line and downgrade behavior are visible in packet outputs
6. the lane stays review-only and does not blur ownership

## Next Action
- None inside WF21. The workflow is closed with a **HOLD** verdict: keep the manual review-packet lane available, keep the Phase 3 cron design as a future design artifact, and do not create live recurring WF21 cron jobs until a later workflow proves stronger repeated value.
- Handoff the active queue to `Workflow 31 - Runtime Continuity, Memory Indexing, and Scheduled-Proof Hardening`.
- If research automation is intentionally reopened later, start from the closeout audit and the Phase 3 design artifact; do not infer authorization to widen source coverage or canonical mutation from this closure.

## Key Files
- `06. Playbooks/Research Automation Source Bundle Contract.md`
- `06. Playbooks/Research Automation Raw Event Input Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Research Automation Routing and Promotion Contract.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Research Automation Source Map - WF21 Pilot v1.md`
- `scripts/research_intake_packet.py`
- `tmp/research-automation/`
