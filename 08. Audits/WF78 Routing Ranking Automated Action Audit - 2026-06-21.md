# WF78 Routing Ranking Automated Action Audit - 2026-06-21

## Bottom Line

**Grade: B- operationally, A- on authority discipline.**

WF78 already has most of the machinery needed to avoid missing opportunities: tier routing, repair queues, macro overlay, source-open packets, daily movement ledger, production-grade policy gate, WF84/WF85 handoff, and market deployment visibility. The current weakness is not missing scripts; it is that the automation does not yet behave like a tight opportunity-refresh controller.

The system should be allowed to take **automated non-capital action** on:

- refreshing stale macro, fundamentals, technical, band, source, and promotion-gate artifacts
- advancing deterministic Tier C -> B and Tier B -> A routing when existing gates pass
- clearing repair blockers into review-ready packets
- surfacing clean A-READY / owner-review candidates into WF85/market visibility
- escalating only the final capital/execution decision to Randall

It must still block:

- capital deployment
- paper/live orders
- brokerage/account action
- portfolio/canon/cash/sizing mutation
- owner-lineage apply
- registry apply
- customer/public output
- inferred owner approval

## Scope Audited

Primary route:

- `python scripts\workflow_router.py WF78 --answer all`
- `06. Playbooks\Project Continuity\Workflow 78 - 500 Ticker Finance Intelligence Scaleout.md`
- `skills\veritas-wf78-tier-promotion-spine\SKILL.md`
- `scripts\wf78_intelligence_routing_v2.py`
- `scripts\wf78_daily_freshness_loop.py`
- `scripts\wf_manifest.py`
- `scripts\wf78_tier_weighted_freshness_resolver.py`
- `scripts\wf78_repair_debt_scoreboard.py`
- `scripts\artifact_intelligence_action_scorer.py`
- `scripts\finance_decision_factory.py`
- `scripts\finance_market_deployment_operating_loop.py`
- `scripts\finance_production_grade_policy_gate.py`
- `scripts\chief_intelligence_promotion_gate.py`

Fresh proof refreshed during this audit:

- `tmp\wf78-intelligence-routing-v2.json`
- `tmp\finance-market-deployment-operating-loop.json`
- `tmp\finance-market-deployment-operating-loop.md`
- `tmp\finance-production-grade-policy-gate.json`
- `tmp\artifact-intelligence-action-scorer.json`
- `tmp\finance-decision-factory.json`
- `tmp\wf78-tier-weighted-freshness-resolution.json`

Sidecar review:

- Kimi 2.7 high-effort no-write review completed and was used as advisory input only. Main session verified against local artifacts.

## Current State Snapshot

WF78 route capsule says WF78 is the non-capital repair/promotion feeder into `finance_intelligence_state -> WF84 -> WF85`. The workflow remains effectively blocked for capital-review deployment because final readiness artifacts still fail closed.

Current evidence:

| Surface | Current Read |
|---|---|
| `tmp\wf78-auto-tier-routing.json` | 200 active tickers; Tier A 24, Tier B 29, Tier C 147; A-READY 3: `GOOG`, `NVDA`, `VRT`; capital/execution approved 0. |
| `tmp\finance-production-grade-policy-gate.json` | Production-grade candidates 3: `GOOG`, `NVDA`, `VRT`; answer-consumer cutover still false. |
| `tmp\wf78-tier-weighted-freshness-resolution.json` | 195/200 resolved, 5 unresolved Tier A/B debt rows, 48 decision/promotion-ready rows, 10 owner-lineage proposal rows. |
| `tmp\wf78-repair-priority-queue.json` | 52 repair rows; top repair tickers include `BRK.B`, `ETN`, `GOOG`, `GS`, `JPM`, `NVDA`, `RTX`, `SMCI`, `VRT`, `CME`, `LMT`, `META`, `XOM`, `ECL`, `WMB`. |
| `tmp\wf78-daily-movement-ledger.json` | 6 owner-review candidates, 37 repair decisions, 15 invalidation-review candidates, 0 moved today. |
| `tmp\finance-decision-factory.json` | 3 candidates, 0 ready, 3 deferred: `NVDA`, `GOOG`, `VRT`. |
| `tmp\finance-market-deployment-operating-loop.json` | `candidate_pending_market_refresh`; next action is rerun at fresh market-hours probe before owner-review/current deployment label. |
| `tmp\artifact-intelligence-action-scorer.json` | 3 high-materiality clean actions; top action is macro inflation release window review ahead of PCE on 2026-06-25. |

## Top Findings

### P1 - A-READY Candidates Are Hidden Behind a Stale Promotion Gate

Evidence:

- `finance_production_grade_policy_gate.py` identifies `GOOG`, `NVDA`, and `VRT` as the only production-grade candidates.
- `finance_decision_factory.py` defers all three because `tmp\chief-intelligence-promotion-gate.json` was generated at `2026-06-18T05:39:44Z` while newer inputs exist:
  - `tmp\research-freshness-opportunity-review.json`
  - `tmp\band-proposals.json`
  - `tmp\band-hygiene-freshness-controller.json`
  - `tmp\technical-refresh.json`
  - `tmp\deployment-readiness-surface.json`

Impact:

- The system correctly refuses to call the candidates deployable, but it also risks hiding timely opportunity because the stale gate is not automatically refreshed at the moment it blocks top A-READY names.

Recommendation:

- Add a WF78 opportunity-refresh controller rule:
  - If production-grade candidates exist and decision factory returns `gate_deferred` due to `promotion_gate_stale_relative_to_inputs`, automatically run:

```powershell
python scripts\chief_intelligence_promotion_gate.py --write --validate
python scripts\finance_decision_factory.py --ledger-only --write --validate
python scripts\finance_market_deployment_operating_loop.py --refresh-readiness --write --write-md --validate
```

Acceptance proof:

- `finance_decision_factory` no longer carries stale-promotion-gate blockers.
- Any still-deferred ticker has a current substantive blocker, not stale-gate residue.
- Capital/execution flags remain false.

### P1 - Daily-Core V2 Can Block on a Timing Budget False Positive

Evidence:

- `wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate` returned blocked.
- Root cause in current proof: `preflight` elapsed `30.151s` against a `30s` budget.
- The preflight layer also had `cron_freshness_spine` fail, while the downstream WF78 tier routing, freshness, ledger publish, and postflight layers were OK.

Impact:

- A near-threshold preflight timing issue can mark the promoted daily-core route blocked even when the WF78-specific routing/freshness chain completed successfully.
- This creates noisy blocker state and can delay promotion visibility.

Recommendation:

- Split daily-core validation into:
  - **hard blockers:** authority drift, missing artifacts, failed WF78 routing/freshness/ledger layers
  - **soft ops blockers:** global cron freshness/preflight timing noise
- Increase preflight time budget from 30s to 45s or classify `cron_freshness_spine` budget misses as `ops_attention` unless authority drift or missing expected artifacts is present.

Acceptance proof:

```powershell
python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate
```

Expected result:

- Blocks only on real WF78 or authority failure.
- Emits warning for global cron/preflight timing noise.

### P1 - Market-Hour Freshness Is Correctly Required But Not Yet Tied to Candidate Escalation

Evidence:

- `finance_market_deployment_operating_loop.py --refresh-readiness --write --write-md --validate` returned `status=ok`.
- Current market state: `candidate_pending_market_refresh`.
- Next safe action: rerun at fresh market-hours probe before any owner-review/current deployment label.

Impact:

- The system does not falsely mark candidates deployable during weekend/off-hours, which is good.
- But it should automatically rerun the market-hour probe when the market opens and A-READY candidates exist, so Randall sees candidates promptly.

Recommendation:

- Controller rule:
  - If `production_grade_candidate_count > 0` and market window is open/settled, run:

```powershell
python scripts\finance_market_deployment_operating_loop.py --refresh-readiness --refresh-intraday --write --write-md --validate
```

- If it produces clean owner-review candidates, notify/display them as **review-ready, not approved**.

Acceptance proof:

- `final_market_deployment_state` becomes current-market-window specific.
- `operator_action` is not `MARKET_REFRESH_PENDING`.
- No approval/execution flags become true.

### P2 - Repair Queue Is Strong, But It Needs an Automatic "Smallest Safe Next Action" Selector

Evidence:

- `tmp\wf78-repair-priority-queue.json`: 52 repair rows.
- `tmp\wf78-repair-debt-scoreboard.json`: next wave includes ready-for-review and lineage/proposal rows.
- `tmp\wf78-tier-weighted-freshness-resolution.json`: 5 unresolved Tier A/B debt rows; 48 decision/promotion-ready rows.

Impact:

- The system knows what is stale or blocked, but the next action is spread across many scripts.
- Main/cron can burn time picking from a long menu instead of executing the best bounded repair.

Recommendation:

- Add `scripts\wf78_opportunity_refresh_controller.py` as a review-only controller that reads:
  - `artifact-intelligence-action-scorer`
  - `wf78-repair-priority-queue`
  - `wf78-tier-weighted-freshness-resolution`
  - `finance-production-grade-policy-gate`
  - `finance-decision-factory`
  - `finance-market-deployment-operating-loop`
- It should emit:
  - top safe automated command
  - reason
  - expected output
  - stop lines
  - whether owner action is required after refresh

Allowed automatic command families:

```powershell
python scripts\macro_metrics_ingest.py --write --validate
python scripts\macro_signal_spine.py --write --validate
python scripts\macro_judgment_draft.py --write --validate
python scripts\wf78_macro_thesis_overlay_gate.py --write --write-db --validate
python scripts\wf78_intelligence_routing_v2.py --layer tier_routing --write --validate
python scripts\wf78_intelligence_routing_v2.py --layer freshness --write --validate
python scripts\wf78_evidence_repair_batch_runner.py --tier A --cursor <cursor> --limit 10 --write --validate
python scripts\wf78_tier_weighted_freshness_resolver.py --write --validate
python scripts\finance_decision_factory.py --ledger-only --write --validate
```

Blocked automatic command families:

- any `--apply` registry/lineage/canon path
- portfolio/canon mutation
- cron schedule mutation
- paper/live/order/account action
- owner approval inference

Acceptance proof:

- New controller writes `tmp\wf78-opportunity-refresh-controller.json`.
- Validation proves all recommended commands are allowlisted review-only commands.
- No forbidden authority flags are true.

### P2 - Macro Action Scoring Should Feed WF78 Candidate Visibility

Evidence:

- `artifact_intelligence_action_scorer.py` top action is a macro inflation release window review ahead of PCE on `2026-06-25`.
- Recommended commands include macro metrics, macro signal spine, macro judgment draft, and WF78 macro thesis overlay.
- `tmp\wf78-macro-thesis-overlay-gate.json` currently shows 100 candidates, 15 Tier B research shortlist, 0 Tier A/B promotions, and 0 capital-deployment-ready rows.

Impact:

- Macro is correctly integrated as a higher evidence burden, but it is not yet directly tied to candidate promotion visibility.

Recommendation:

- Controller rule:
  - If a high-materiality macro action affects WF78, run macro refresh before promotion gate/factory.
  - Recompute WF78 macro overlay before candidate escalation.
  - Do not promote a macro-sensitive ticker to review-ready unless macro overlay is fresh and clean enough for the claim.

Acceptance proof:

```powershell
python scripts\artifact_intelligence_action_scorer.py --write --validate
python scripts\macro_metrics_ingest.py --write --validate
python scripts\macro_signal_spine.py --write --validate
python scripts\macro_judgment_draft.py --write --validate
python scripts\wf78_macro_thesis_overlay_gate.py --write --write-db --validate
```

### P2 - WF84/WF85 Handoff Is Clean But Not Yet Producing Approval Drafts

Evidence:

- `tmp\canonical-finance-data-plane.json` status OK.
- `tmp\trade-grade-decision-cards.json` status OK, card count 200.
- `approval_card_draft_count=0`.
- Decision states include `below_stop_or_invalidation=88`, `monitor_only=89`, `no_chase=14`, `blocked_missing_freshness=7`, `evidence_repair=2`.

Impact:

- WF84/WF85 are not broken, but they remain visibility surfaces rather than deployment surfaces.
- That is correct, but top candidates need explicit escalation when they are clean, not buried in 200-card state.

Recommendation:

- When controller sees:
  - A-READY candidate
  - current promotion gate
  - market-hour freshness clean
  - WF85 card not `blocked_missing_freshness`
  - no owner-lineage/canon mutation required
- It should generate a **review-ready visibility queue**, not an approval.

Proposed output:

- `tmp\wf78-opportunity-visibility-queue.json`
- fields:
  - ticker
  - tier/state
  - current blocker status
  - last refreshed evidence surfaces
  - review-ready reason
  - owner action required
  - capital/execution approved false

## Proposed Automated Control Loop

### Name

`WF78 Opportunity Refresh Controller`

### Purpose

Automatically choose and run the smallest safe refresh/repair step needed to keep top-ranked promotion candidates visible for owner review.

### Inputs

- `tmp\artifact-intelligence-action-scorer.json`
- `tmp\wf78-auto-tier-routing.json`
- `tmp\finance-production-grade-policy-gate.json`
- `tmp\wf78-tier-weighted-freshness-resolution.json`
- `tmp\wf78-repair-priority-queue.json`
- `tmp\wf78-daily-movement-ledger.json`
- `tmp\finance-decision-factory.json`
- `tmp\finance-market-deployment-operating-loop.json`
- `tmp\trade-grade-decision-cards.json`

### Decision Ladder

1. **Authority preflight**
   - fail closed on any capital/execution/account/canon/portfolio authority drift

2. **Macro first**
   - if high-materiality macro action affects WF78, refresh macro inputs and WF78 macro overlay

3. **Tier/routing freshness**
   - refresh tier routing and freshness layers if stale, blocked, or no recent ledger publish

4. **Production-grade candidate check**
   - if A-READY candidates exist, ensure promotion gate and decision factory are current

5. **Repair blocker selector**
   - if candidates blocked by evidence debt, run the next cursor/batch only
   - if blocked by owner/source lineage, emit owner-review packet but do not apply
   - if blocked by registry preview, emit gated apply preview only

6. **Market visibility**
   - if market open/settled, refresh market deployment operating loop with intraday proof
   - if market closed/weekend, mark `market_refresh_pending`

7. **Visibility queue**
   - write review-ready queue for clean candidates
   - never mark as capital-approved

### Proposed Cron Cadence

Use existing cron jobs first. Do not add new schedules until the controller script exists and has several clean manual runs.

Recommended eventual cadence:

| Time AZ | Controller Mode | Purpose |
|---|---|---|
| 05:45 | macro-priority | Macro inputs before candidate ranking. |
| 06:08 | daily-core | Tier routing, freshness, repair queue, ledgers. |
| 06:25 | candidate-unblock | Promotion gate + decision factory refresh when A-READY exists. |
| 06:42 | market-open visibility | Fresh intraday proof after open settles. |
| 07:14 | confirmation | Confirm candidates still clean. |
| 12:07 | late-session | Final opportunity/risk check. |
| 13:20 | post-close | Reconcile, log, and prepare next-day queue. |

## Implementation Plan

### Phase 1 - Tighten Existing Runner Behavior

1. Adjust `wf78_intelligence_routing_v2.py` preflight handling:
   - raise preflight budget to 45s, or
   - classify global cron freshness preflight failures separately from WF78 layer failures.
2. Add explicit summary fields:
   - `wf78_core_layers_ok`
   - `ops_preflight_warning_count`
   - `authority_drift_count`
   - `candidate_visibility_blocked_by`

Proof:

```powershell
python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate
```

### Phase 2 - Add Opportunity Refresh Controller

Create:

- `scripts\wf78_opportunity_refresh_controller.py`
- `scripts\test_wf78_opportunity_refresh_controller.py`

Controller should default to dry decision mode and require `--execute-safe` to run allowlisted review-only commands.

Modes:

- `--mode audit`
- `--mode macro-priority`
- `--mode daily-core`
- `--mode candidate-unblock`
- `--mode market-visibility`
- `--mode post-close`
- `--execute-safe`
- `--write`
- `--validate`

Proof:

```powershell
python scripts\wf78_opportunity_refresh_controller.py --mode audit --write --validate
python scripts\wf78_opportunity_refresh_controller.py --mode candidate-unblock --execute-safe --write --validate
python scripts\test_wf78_opportunity_refresh_controller.py
```

### Phase 3 - Add Visibility Queue

Create:

- `tmp\wf78-opportunity-visibility-queue.json`

It should surface:

- A-READY candidates
- owner-review candidates
- blocked-but-high-priority repairs
- market-refresh-pending candidates
- exact blocker reason
- next safe command
- owner action required flag

Never include:

- capital approved true
- trade approved true
- execution allowed true
- order instructions as executable authorization

### Phase 4 - Wire Into Existing Schedules

Only after Phase 1-3 pass manually:

- update cron contract/proposal, not live schedule directly
- prefer existing WF78 Daily Freshness and Tier A probe jobs
- add controller as a wrapper only if it reduces blocked residue and false positives

Proof:

```powershell
python scripts\cron_contract_validator.py --write --validate
python scripts\cron_control_packet.py --write --validate
```

### Phase 5 - Dashboard / Status Surfacing

Feed the visibility queue into:

- status card
- PM control packet
- finance market deployment operating loop
- WF78 routing dashboard

The UI label should be:

> Review-ready opportunity visibility, not capital approval.

## Safe Automated Actions Matrix

| Action | Safe To Automate? | Notes |
|---|---:|---|
| Refresh macro metrics/signal/judgment | Yes | Review-only evidence. |
| Refresh WF78 macro overlay | Yes | No promotion without evidence gates. |
| Refresh tier routing / Tier C attention / C->B pipeline | Yes | Non-capital derived routing only. |
| Refresh Tier B/A competitive gates | Yes | Routing gate only; no owner approval. |
| Refresh tier-weighted freshness | Yes | Classification/proof only. |
| Run evidence repair batch cursor | Yes | Bounded proof refresh; no apply. |
| Build source-open work packets | Yes | Work queue only. |
| Build owner-lineage proposals | Yes | Proposal only; apply blocked. |
| Apply owner-lineage proposal | No | Requires owner/source decision. |
| Build registry apply preview | Yes | Preview only. |
| Apply registry changes | No | Requires exact gated owner approval. |
| Refresh chief-intelligence promotion gate | Yes | Review-only gate; critical for stale blocker cleanup. |
| Build decision factory ledger | Yes | Review-only candidate ledger. |
| Build owner cards / WF67 request artifacts | Conditionally | Artifact prep only; no execution. |
| Submit paper/live order | No | Requires exact Randall approval and WF67 guard. |
| Mutate portfolio/canon/cash/sizing | No | Separate gate only. |

## Recommended Next Action

Implement Phase 1 and Phase 2:

1. Fix or reclassify the WF78 V2 preflight timing false positive.
2. Add the review-only `wf78_opportunity_refresh_controller.py`.
3. Have it run only allowlisted proof-refresh commands.
4. Have it write `tmp\wf78-opportunity-refresh-controller.json` and `tmp\wf78-opportunity-visibility-queue.json`.
5. Only after repeated clean manual proof, propose cron wiring.

## Stop Lines

- No capital deployment.
- No paper/live order submission, replacement, cancellation, or liquidation.
- No brokerage/account action.
- No money movement.
- No portfolio/canon/cash/sizing/risk-rule mutation.
- No owner-lineage apply without owner/source decision.
- No official registry apply without exact approval.
- No cron schedule mutation from this audit.
- No customer/public output.
- No generated artifact implies owner approval.

## Validation Commands Used

```powershell
python scripts\workflow_router.py WF78 --answer all
python scripts\wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate
python scripts\finance_market_deployment_operating_loop.py --refresh-readiness --write --write-md --validate
python scripts\finance_production_grade_policy_gate.py --write --validate
python scripts\artifact_intelligence_action_scorer.py --write --validate
python scripts\finance_decision_factory.py --ledger-only --write --validate
python scripts\wf78_tier_weighted_freshness_resolver.py --write --validate
```

## Intentionally Deferred Checks

- No live cron schedule changes were made.
- No chief-intelligence promotion gate refresh was run because this audit did not lease `tmp\chief-intelligence-promotion-gate.json`; it is recommended as Phase 2 controller behavior.
- No registry apply, owner-lineage apply, canon/portfolio mutation, or paper/live execution path was tested or exercised.
- No web research was needed for this local WF78 routing audit; current state came from workspace owner artifacts and generated proof.
