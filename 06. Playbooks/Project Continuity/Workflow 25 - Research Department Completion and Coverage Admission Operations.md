# Workflow 25 - Research Department Completion and Coverage Admission Operations

## Objective
- Turn the already-defined research department, coverage-tier framework, and coverage-admission procedure into a real operating lane instead of leaving them as closed doctrine only.
- Make new-ticker intake, lane assignment, thesis obligations, and promotion/demotion decisions repeatable enough that future research automation widens into a real desk process rather than ad hoc chat judgment.
- Finish the missing operational layer before broader source-bundle widening, geopolitical intake expansion, or predictive-model work claims to serve a mature research department.

## Why this lane exists
- Workflow 6 defined the lane framework.
- Workflow 9 defined the research department operating model.
- Workflow 11 defined the admission and promotion procedure.
- Those pieces are real, but the next proof layer is still missing: a live operating queue, intake discipline, and repeatable use on fresh names and promotion/demotion cases.
- Randall explicitly wants the research department, ticker-entry decision process, and coverage-admission model tackled first.

## Current State
- active downstream workflow after Workflow 24 closed with follow-up on 2026-05-04
- depends on WF24 only for cron/handoff discipline, not for finance-judgment widening
- inherits the settled lane framework from WF6 and must not relitigate it
- inherits the desk ownership model from WF9 and must operationalize it
- inherits the admission/promotion procedure from WF11 and must prove it on real cases

## Scope
- define the live research-department operating queue for new names, promotions, demotions, and removals
- define the intake packet for a new ticker admission review
- define what evidence, thesis fields, and decision fields are required before a name enters the tracked universe or advances lanes
- define how active desks consume research outputs and hand off to portfolio/deployment surfaces
- run bounded live proof cases for at least one new-name intake and one promotion/demotion review
- define what research outputs later source-bundle and geopolitical workflows must feed

## Out of Scope
- autonomous tracked-universe mutation
- autonomous execution-lane promotion
- autonomous thesis rewrite
- predictive-model deployment into live portfolio decisions
- broad universe sprawl without a named admission reason

## Sequential phase approach

### Phase 1 - Operating queue and decision contract
Purpose:
- create the real operator-facing research queue and the exact decision object for admission/promotion reviews

Required outputs:
- research-department intake queue shape
- admission review object / checklist
- promotion / demotion review object / checklist
- explicit desk handoff map to coverage, portfolio, and publishing surfaces

Execution approach:
- start with the smallest usable queue that can hold four states only: new-name intake, promotion review, demotion review, and removal / bench review
- turn WF11 into concrete operator review objects rather than prose-only doctrine
- force each decision object to name owner, evidence status, blockers, required notes, and downstream handoff surface before any name is considered actionable

### Phase 2 - Pilot case set
Purpose:
- choose bounded live cases instead of leaving the process hypothetical

Required outputs:
- 1 new-name admission candidate
- 1 existing-name promotion/demotion candidate
- evidence requirements and owner files for each case
- explicit no-go conditions

Execution approach:
- choose one candidate that is genuinely unresolved rather than a fake-easy layup
- choose one existing tracked name whose lane status actually needs confirmation, not a ceremonial review
- reject any pilot that would require hidden thesis rewrite or broad universe sprawl just to make the workflow look busy

### Phase 3 - Real operating proof
Purpose:
- run the procedure on the bounded case set and force honest outcomes

Required outputs:
- one completed admission review
- one completed promotion/demotion review
- visible use of the settled WF11 protocol
- validator / surface reruns after each approved mutation

Execution approach:
- run each case to a real decision: admit, defer, hold, demote, or remove
- if a case is not ready, treat that as a valid outcome instead of padding the record
- after any approved mutation, rerun only the validator and owner surfaces that actually need to move

### Phase 4 - Downstream handoff contract
Purpose:
- define what later workflows must feed this desk

Required outputs:
- required inputs from WF21 research packets
- required inputs from later geopolitical verification lanes
- required operator-action output for portfolio and command-center surfaces
- widen / hold decision for follow-on research automation

Execution approach:
- define the minimum acceptable packet from WF21 before allowing recurring source widening
- define which geopolitical / fresh-intelligence facts are mandatory for admission versus merely helpful context
- end with an explicit widen / hold recommendation for WF21, WF26, and later decision-surface work instead of vague “ready for next steps” language

## Acceptance Gates
Workflow 25 should not close unless all are true:
1. the research-department operating queue is explicit
2. the admission and promotion review objects are explicit
3. at least one live new-name review and one live promotion/demotion review were run honestly
4. the workflow proves use of WF6/WF9/WF11 instead of bypassing them
5. downstream dependencies for source-bundle / geopolitical / decision-surface work are explicit

## Next Action
- Phase 1 now opens: define the research-department intake queue plus the exact admission / promotion decision objects, then choose the first bounded live case set.

## Key Files
- `06. Playbooks/Project Continuity/Workflow 6 - Coverage Tier Framework.md`
- `06. Playbooks/Project Continuity/Workflow 9 - Research Department Operating Model.md`
- `06. Playbooks/Project Continuity/Workflow 11 - Coverage Admission Model.md`
- `06. Playbooks/Coverage Admission and Promotion Protocol.md`
- `04. Research/Coverage Universe.md`
- `02. Markets/Watchlist.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Technical Entry and Invalidation Sheet.md`

## Automation / Refresh Path
- main-session owned first
- helper lanes allowed only for bounded evidence assembly, comparison, or audit
- no recurring cron owner in v1; this workflow defines what later recurring research lanes are allowed to feed
