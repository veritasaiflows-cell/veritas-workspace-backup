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
- Workflow 25 is now the immediate upstream consumer this lane must serve, so the pilot coverage set and packet outputs should be shaped around real research-department intake and admission needs rather than generic automation widening.
- Workflow 29 is now closed with follow-up, so this lane becomes the active downstream consumer that should start using the newly landed proof surfaces rather than leaving them theoretical.

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

### Phase 1 - Source map and coverage set
Purpose:
- convert the source-bundle contract into a concrete v1 source map with explicit coverage ownership

Required outputs:
- approved source categories by tier
- blocked / low-confidence categories
- pilot coverage set for 3-5 names plus 1 macro/geopolitical sleeve
- raw-event intake file contract

Status:
- active

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
- queued

### Phase 3 - Cron-backed packet assembly design
Purpose:
- add the smallest useful recurring review cadence after the manual dry run is credible

Required outputs:
- one post-close review packet window
- one Sunday weekly packet window
- dependency chain, downgrade rules, and overlap-owner map
- validation proof in cron history plus workspace artifacts

Status:
- queued

### Phase 4 - Pilot proof and widen / hold decision
Purpose:
- decide whether the source bundle is useful enough to keep or widen

Required outputs:
- pilot usefulness verdict
- noise / miss analysis
- widen / hold / stop decision
- next approved expansion path or explicit no-go

Status:
- queued

## Daily / Weekly chain insertion
- **Post-close chain**: finance refresh remains the writer; this workflow may add one downstream review-packet assembly step after the refresh window completes.
- **Sunday chain**: weekly refresh remains the writer; this workflow may add one downstream weekly-digest packet assembly step after Sunday refresh artifacts exist.
- **Event-driven path**: stays manual in v1, especially for unresolved truths and fast-moving geopolitical verification.
- **Pre-market**: no recurring research-source sweep in v1 unless Phase 3 proves a real need.

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
- Start Phase 1: build the v1 source map for the active pilot names and first macro/geopolitical sleeve, then start the first real manual raw-event file in the exact shape required by `06. Playbooks/Research Automation Raw Event Input Contract.md`.

## Key Files
- `06. Playbooks/Research Automation Source Bundle Contract.md`
- `06. Playbooks/Research Automation Raw Event Input Contract.md`
- `06. Playbooks/Research Automation Intake Packet Contract.md`
- `06. Playbooks/Research Automation Routing and Promotion Contract.md`
- `06. Playbooks/Cron Job Protocol.md`
- `scripts/research_intake_packet.py`
- `tmp/research-automation/`
