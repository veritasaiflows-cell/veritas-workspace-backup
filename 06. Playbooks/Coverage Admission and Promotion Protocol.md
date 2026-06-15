# Coverage Admission and Promotion Protocol

## Purpose
Define how a ticker enters, advances within, or leaves the Veritas tracked universe without reopening Workflow 6's settled lane framework.

This protocol governs procedure, not thesis quality by vibes.

## Inherited lane framework
Use the existing machine lanes only:
- `execution`
- `watch`
- `macro`
- `speculative`

Do not relitigate lane definitions here.

## Core rule
A name may be machine-tracked before it is execution-ready, but it may not be treated as honestly covered unless the required thesis and owner-note obligations are met for its lane.

## WF78 full-funnel tier posture

WF78 uses a staged evidence funnel. Each promotion asks a different question and carries a different authority boundary:
- `Tier D -> Tier C`: is this clean enough to monitor cheaply?
- `Tier C -> Tier B`: does this deserve scarce research time?
- `Tier B -> Tier A`: does this deserve one of only 25 Tier A seats more than current alternatives?

As of Randall's 2026-06-05 12:30 MST instruction, ordinary ticker tier/routing movement is automated by Veritas when artifacts and validators support it. Owner approval is not required for non-capital Tier A/B/C routing state. Owner approval remains required for capital deployment, trade/order execution, paper/live/brokerage/account action, portfolio cash/sizing/execution mutation, and other explicitly gated actions.

The current derived routing owner is `tmp/wf78-auto-tier-routing.json`, produced by `scripts/wf78_auto_tier_router.py`. Downstream roster and dashboard consumers should prefer that artifact for non-capital routing state.

Current quick-routing implementation sequence:
1. sync downstream roster/dashboard/PM/WF77/WF68 consumers to `tmp/wf78-auto-tier-routing.json`
2. generate a daily routing delta for promotions, demotions, challenged names, stale evidence, holds, and capital-review candidates
3. add a `route TICKER` quick packet for per-name triage
4. build an `A-DEPLOY-CANDIDATE` capital-review queue that prepares approval cards without implying capital approval
5. add event-triggered rerouting for earnings, guidance, official evidence, major news, analyst resets, macro shocks, and band/stop breaches

**Machine source (Phase 1, built 2026-06-04):** this section is the prose mirror of the canonical machine-readable funnel contract `scripts/wf78_tier_funnel_contract.py` -> `tmp/wf78-tier-funnel-contract.json` (`veritas.wf78_tier_funnel_contract.v1`). The contract encodes the tiers, gate questions, per-transition required evidence, competition rules, state vocabularies, decay triggers, caps, and authority boundary as data, and the future promotion gates import its constants rather than re-deriving the rules. It is report-only and validates its caps against `wf78_tier_capacity_policy_gate.py`. If this prose and the contract ever diverge, reconcile both in the same pass.

### Tier D -> Tier C monitorability gate

Tier D is raw intake, weak evidence, unresolved identity, validation repair, duplicate review, or rejected/low-confidence residue. A Tier D name can move to Tier C only when it becomes monitorable.

Tier D reasons:
- identity unclear
- source proof weak
- sector/theme mapping incomplete
- ticker card missing
- provider/runtime gaps
- duplicate or overlap conflict
- low-confidence business model
- stale or broken evidence

Tier D states:
- `D-RAW`
- `D-IDENTITY-REPAIR`
- `D-SOURCE-REPAIR`
- `D-DUPLICATE-REVIEW`
- `D-REJECT`

Required for Tier D -> Tier C:
- clean ticker/company identity
- sector and industry classification
- basic business model description
- source-open identity proof
- provider/runtime proof
- basic liquidity sanity check
- duplicate/conflict check against current universe
- explicit reason to monitor

Tier D -> Tier C means safe enough for cheap monitoring. It does not mean research-worthy, decision-ready, investable, or eligible for production answers.

### Tier C -> Tier B research-worthiness gate

Tier C is the broad radar and cheap monitor pool. A Tier C name can move toward Tier B only when it earns scarce research attention versus other Tier C names.

Tier C jobs:
- monitor macro/theme relevance
- track sector exposure candidates
- surface valuation resets
- surface earnings/revision inflections
- detect technical improvement
- detect source/evidence repair needs
- nominate a small number into Tier B candidate work

Tier C states:
- `C-MONITOR`
- `C-REPAIR`
- `C-THEME-WATCH`
- `C-CANDIDATE`
- `C-DECAY`

Required for Tier C -> Tier B candidate status:
- macro/theme fit
- business quality reason
- initial fundamentals snapshot available
- valuation context available
- analyst/revision layer available or explicitly not applicable
- initial technical/price-band context
- risk reason understood
- portfolio role identified
- source-open proof usable
- evidence repair burden acceptable

Tier C -> Tier B is competitive within the monitor pool and may be automated by the router:
- each 100-name batch may nominate no more than 15 Tier B candidates
- only top-ranked Tier C names enter the Tier B research queue
- if Tier B is full at 50, a new candidate must beat the weakest Tier B candidate or remain Tier C
- a score can nominate research work; the validated auto-router decides whether to route to Tier B, hold as `C-CANDIDATE-HOLD`, or leave in monitor/repair

Tier B states:
- `B-CANDIDATE`
- `B-VALIDATED`
- `B-STALE`
- `B-CHALLENGED`
- `B-REJECT-TO-C`

Tier B also decays. Stale research, failed thesis, unresolved evidence gaps, broken valuation relevance, or a stronger candidate can move a name to `B-STALE`, `B-CHALLENGED`, `B-REJECT-TO-C`, Tier C repair/monitor, or Tier D repair.

Phase 1 (machine funnel contract) is built: `scripts/wf78_tier_funnel_contract.py`. Phase 2 (the report-only `tier_funnel_promotion_gate`) is built as `scripts/wf78_tier_funnel_promotion_gate.py` -> `tmp/wf78-tier-funnel-promotion-gate.json`: it imports the contract and deterministically evaluates Tier D -> C monitorability and Tier C -> B research-worthiness, enforcing required-evidence completeness, decay/reject states, the 15-per-batch nomination limit, and live Tier B cap pressure (from the capacity gate). The first evidence-depth layer is built as `scripts/wf78_tier_b_research_packet.py` -> `tmp/wf78-tier-b-research-packets.json/.sqlite` plus `tmp/wf78-tier-b-research-packet-requests.json`. Phase 3 (the report-only `tier_a_competitive_promotion_gate`, Tier B -> A) is built as `scripts/wf78_tier_a_competitive_promotion_gate.py` -> `tmp/wf78-tier-a-competitive-promotion-gate.json` over the same contract. The auto-routing layer is built as `scripts/wf78_auto_tier_router.py` -> `tmp/wf78-auto-tier-routing.json`: it consumes the gate/packet/label-sync proof stack and emits derived non-capital `auto_tier` / `auto_state` for all active names. Its output may automate tier/routing state, but it keeps capital deployment and trade/execution approval false.

## WF78 competitive Tier B -> Tier A doctrine

Tier A is a scarce roster, not a broad "good ticker" label. A Tier B name does not enter Tier A because it is good; it enters Tier A only because it is complete, current, portfolio-useful, and better than the current alternative for one of the limited Tier A seats.

This doctrine is enforced by the Phase 3 gate `scripts/wf78_tier_a_competitive_promotion_gate.py` and by the derived auto-routing artifact `tmp/wf78-auto-tier-routing.json`. The gate evaluates the evidence ladder; the auto-router decides non-capital routing state. Neither grants capital deployment, trade/order execution, brokerage/account action, or money movement.

Use the WF78 stage ladder:
- `Tier B Candidate`: research-candidate status from Tier C/D monitoring or macro overlay. It has a reason to investigate, but no promotion or portfolio action.
- `Tier B Validated`: full research packet exists, including fundamentals, valuation, analyst/revision layer, technicals, thesis, counter-thesis, risk register, source-open proof, and portfolio role. It is serious-monitor quality, not deployment quality.
- `Tier A Nominee`: a validated Tier B name has a live reason to compete for a scarce Tier A seat, such as entry band improvement, thesis/revision improvement, sector/macro regime improvement, portfolio need, incumbent weakness, or materially better risk/reward.
- `Tier A Approved`: legacy wording for roster admission; current posture is automated non-capital Tier A routing when evidence supports it. Owner approval is reserved for capital deployment and execution.

Core competitive rule:
- If Tier A has fewer than 25 admitted names, a nominee may enter only after full Tier A requirements pass.
- If Tier A has 25 admitted names, the nominee must defeat the weakest relevant Tier A incumbent by at least 5 points.
- Relevant incumbents include the weakest Tier A name, most similar Tier A name, same-sector name, same-factor name, and same-portfolio-role name.
- A score creates eligibility for competition. It never auto-promotes a ticker.

Hard gates for automated Tier A routing:
- source-open proof
- complete current ticker card
- current price, entry band, and stop/invalidation
- thesis and counter-thesis
- risk register and invalidation event
- current fundamentals/earnings context
- valuation context
- analyst/revision layer
- portfolio-fit and concentration check
- deployment/readiness state
- Tier A capacity check
- owner approval only for capital deployment or execution, not ordinary Tier A routing

Tier A states:
- `A-NOMINEE`: passed internal nomination logic, pending auto-router or deeper evidence confirmation.
- `A-WATCH`: approved-quality name, not in the preferred buy zone.
- `A-READY`: in or near preferred band, but no order is approved.
- `A-DEPLOY`: approval-ready deployment packet exists; execution still requires separate exact order approval.
- `A-HOLD`: existing position with active thesis.
- `A-CHALLENGED`: stale, crowded, weakened, or facing a stronger challenger.
- `A-DEMOTE`: failed refresh, thesis drift, stop/invalidation break, or lost the challenger test.

Tier A promotion is reversible. Stale ticker cards, stale source proof, earnings/thesis drift, broken price structure, excessive concentration, weakening analyst/revision trend, or a superior Tier B challenger must move the name to `A-CHALLENGED` or `A-DEMOTE`.

Owner boundary:
- Tier A/B/C routing does not require owner approval when produced by validated automation.
- Tier A membership does not authorize paper execution, live execution, account action, portfolio mutation, capital deployment, or money movement.
- `A-DEPLOY` means an approval-ready packet can be presented; it does not mean trade approval.
- Capital deployment and trade/order execution still require Randall's exact approval.

## Minimum admission gates

### A. Machine-tracked universe admission
Required before adding a name to `tmp/portfolio-config.json` / tracked-universe surfaces:
- ticker, sector, lane, and portfolio-role choice are explicit
- reason for inclusion is explicit in one sentence
- thesis status is not blank
- macro fit is not blank
- trigger condition is not blank
- owner note destination is named up front
- next review condition is explicit (earnings, valuation reset, technical base, macro catalyst, etc.)

### B. Honest written-coverage admission
Required before a name is treated as thesis-covered in `04. Research/Coverage and Watchlist.md`:
- full thesis block exists
- key risk is explicit
- act-when condition is explicit
- status language does not overstate deployment readiness

### C. Execution-lane promotion
Required before promotion into the execution lane:
- thesis block exists in `04. Research/Coverage and Watchlist.md`
- live deployment state is defined in `03. Portfolio/Execution Board.md`
- explicit numeric entry band and stop exist in `03. Portfolio/Execution Board.md` and `tmp/portfolio-config.json -> entry_bands`
- dashboard/deployment consumers render numeric band/stop values, not sentinel labels such as `WATCH_DEFINED_INITIAL`, `WATCH_PULLBACK_INITIAL`, or `TBD`
- earnings/timing blocker posture is explicit
- portfolio competition is real (the name is being compared against other capital uses, not just admired)

### D. Promotion-review admission
Required before a name may be called `PROMOTION REVIEW` / portfolio-review candidate:
- `tmp/portfolio-config.json -> tracked_universe[TICKER].workflow_state` is set deliberately
- `tmp/portfolio-config.json -> entry_bands[TICKER]` has numeric `low`, `high`, and `stop`
- display labels are numeric or the dashboard derives numeric labels from the numeric fields
- `python scripts\validate_portfolio_config.py --strict` passes
- `python scripts\deployment_check.py` keeps the name in `PROMOTION REVIEW`, not `DEPLOYABLE NOW`, unless a separate owner-approved deployment/model gate exists
- `python scripts\generate_dashboard.py` and `python scripts\validate_dashboard_state.py --write` pass without rendering sentinel labels or false-green deployable states

Promotion is incomplete if bands exist only as prose, labels, placeholders, or watch-lane sentinel names. Numeric propagation across config, deployment check, and dashboard is part of the promotion itself, not a later cleanup item.

## Owner-boundary map
- `tmp/portfolio-config.json` -> machine-tracked universe, lane, workflow state
- `04. Research/Coverage and Watchlist.md` -> high-level mirror of the machine-tracked universe
- `04. Research/Coverage and Watchlist.md` -> thesis coverage and promotion logic
- `03. Portfolio/Execution Board.md` -> deployment entitlement and action state
- `03. Portfolio/Execution Board.md` -> entry bands, stops, and invalidation logic
- `03. Portfolio/Portfolio Snapshot.md` -> actual position/posture once capital is competing or allocated

Do not let a mirror note invent a greener state than the owner note.

## Admission checklist
1. Decide lane (`execution`, `watch`, `macro`, `speculative`)
2. Record machine fields in `tmp/portfolio-config.json`
3. Update `04. Research/Coverage and Watchlist.md` if the name is in the tracked universe
4. Add or update the thesis block in `04. Research/Coverage and Watchlist.md`
5. If execution-lane eligible, update `03. Portfolio/Execution Board.md` in the same pass
6. If capital competition changes, update Portfolio Snapshot
7. For any promotion/review upgrade, run the band propagation closure gate:
   - `python scripts\validate_portfolio_config.py --strict`
   - `python scripts\deployment_check.py`
   - `python scripts\generate_dashboard.py`
   - `python scripts\validate_dashboard_state.py --write`
8. Confirm no promoted/review ticker renders as `DEPLOYABLE NOW` unless owner deployment/model authority is explicitly present
9. Re-run any additional affected downstream checks

## Promotion / demotion rules

### Promote to execution
Only when:
- thesis exists
- levels exist
- timing blockers are honest
- the name deserves real capital competition now

### Demote from execution to watch
When any of these become true:
- levels are missing or stale
- repair mode begins
- earnings/timing block turns the setup non-actionable
- a stronger name displaces it and the weaker one becomes secondary research only

### Remove from tracked universe
When any of these become true:
- no durable reason remains to monitor it
- note maintenance cost exceeds expected decision value
- the thesis no longer fits the portfolio framework
- a cleaner sector proxy fully replaces it

Removal requires updating both machine and note mirrors in the same pass.

## LLY pilot result
`LLY` is the first bounded live intake pilot under Workflow 11.

Pilot outcome:
- remain in the `watch` lane
- keep `portfolio_role=watch_only`
- thesis block now exists in `04. Research/Coverage and Watchlist.md`
- no execution-lane promotion because valuation/setup and explicit levels are still undefined

This is the model for future watch-lane admissions:
- thesis-covered
- machine-tracked
- not falsely deployable

## No-go assumptions
- do not add a tracked name just because it is interesting
- do not promote to execution without levels and timing posture
- do not mark a ticker promotion complete while dashboard/deployment consumers still show sentinel band labels or false-green deployable states
- do not let `Coverage and Watchlist.md` or quick-reference wording imply a greener state than `03. Portfolio/Execution Board.md`
- do not leave machine-tracked names without thesis coverage indefinitely

## Workflow 11 closure standard
Workflow 11 is honestly closed when:
- the procedure is explicit
- the live pilot (`LLY`) is complete
- existing thesis-coverage residue names are resolved or intentionally removed
- owner-boundary mutations are clear enough that the next ticker can be admitted without reconstructing chat history
