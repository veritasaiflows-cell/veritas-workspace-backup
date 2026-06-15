# Workflow 86 - Main-Session Paper Autotrader OS

## Status

Opened 2026-06-11 after Randall approved creating a new workflow to reach bounded autonomous **paper-only** buy and sell orders. This workflow is an orchestration layer. It does not replace WF85, WF67, WF78, WF68, WF55, or canonical portfolio notes.

Current status: **open / planning / shadow-first**. No autonomous paper order authority exists yet.

2026-06-11 08:41 MST owner policy decisions:

- Shadow threshold: minimum `5` market sessions and at least `20` clean would-buy / would-sell / no-action decisions before assisted or autonomous execution escalation.
- Initial autonomous paper order cap: `$5,000` max notional per order.
- Initial autonomous buy universe: Tier A only; Tier B remains shadow-only until separately reviewed.
- Initial autonomous sell scope: risk-reduction only; no autonomous profit-taking/trimming at first.
- Initial execution window: market-hours-only; no extended-hours flags.
- Initial fixtures: VRT/NVDA/GOOG remain shadow fixtures until blockers clear. VRT may move to assisted mode only after band-review and WF67 guard proof are clean.

2026-06-11 09:50 MST implementation hardening:

- WF78 capital-review queue now prefers validated WF84 canonical band/stop fields when the WF84 default-switch gate is clean.
- Decision factory now carries `band_field_source`, `decision_factory_band_snapshot`, and `wf84_canonical_data_plane` provenance.
- Morning recommendation cards already prefer WF84 canonical bands for top-level display/classification.
- Owner-card cache and the VRT WF67 request artifact were regenerated from the corrected WF78 queue.
- Added `scripts/wf86_shadow_eligibility_validator.py`, writing `tmp/paper-autotrader/shadow-eligibility.json`.
- Current shadow proof: 3 candidates evaluated, 3 shadow-eligible, 1 `would_buy_shadow` ticker (`VRT`), 0 execution-ready.
- Execution remains blocked: WF67 guard is not clean, no fresh kill-switch/audit/reconciliation proof, and no separate scoped Randall pilot approval.

2026-06-11 10:11 MST shadow/readiness preparation:

- Added `scripts/wf86_shadow_decision_ledger.py`, writing `tmp/paper-autotrader/shadow-decisions.json`.
- Added `scripts/wf86_autotrader_readiness_packet.py`, writing:
  - `tmp/paper-autotrader/autotrader-readiness.json`
  - `tmp/paper-autotrader/guard-readiness.json`
- Current phase readiness:
  - shadow mode: ready
  - assisted paper mode: not ready
  - autonomous paper buy/sell: not ready
  - live trading: not ready / blocked
- Current shadow ledger proof:
  - decisions logged: 3
  - clean shadow decisions: 3
  - unique clean market sessions: 1 of required 5
  - required clean decisions: 3 of required 20
  - current `would_buy_shadow`: VRT
- Current hard blockers before assisted/autonomous paper execution:
  - WF67 executor/guard cap bridge required from `$500` to WF86 policy `$5,000`
  - WF67 guard remains blocked
  - shadow threshold not met
  - fresh short-lived kill switch not active
  - redacted audit schema and guard status not clean for autonomy
  - post-trade reconciliation not proven for autonomy
  - separate scoped Randall autonomous paper pilot approval still missing
- Boundary unchanged: this preparation grants no paper/live submit/cancel/sell authority.

2026-06-11 10:18 MST WF67/WF86 cap bridge:

- Added guarded WF86 full-scope cap support to WF67 request validation:
  - `scripts/alpaca_paper_trade_executor.py`
  - `scripts/alpaca_paper_execution_guard_validator.py`
  - `scripts/wf67_order_card_request_generator.py`
  - `scripts/wf67_advisor_paper_request_generator.py`
- Added `scripts/test_wf67_wf86_cap_bridge.py`.
- The WF67 default pilot cap remains `$500`; requests above `$500` validate only when they carry `risk_check.full_scope_artifact = tmp/paper-autotrader/policy.json`.
- The full-scope artifact must be the approved WF86 policy, paper-only, owner-approved, no live/account/money movement authority, and cap no higher than `$5,000`.
- Cap bridge proof passed:
  - over-$500 request without full-scope artifact blocks
  - `$1,000` WF86-scoped paper request validates without execution authority
  - pending approval still blocks execute-path approval checks
  - order-card generator carries `pilot_notional_cap_usd = 5000.0` and `full_scope_artifact`
- Current readiness packet no longer lists the cap bridge as a blocker; remaining blockers are WF67 guard, shadow threshold, kill switch, audit/reconciliation, and separate scoped autonomous pilot approval.
- Boundary unchanged: cap bridge enables validation/preparation only; it does not create autonomous paper execution authority.

2026-06-11 10:32 MST assisted VRT start preparation:

- Randall approved continuing the next WF86 sequence and phases to get ready to start WF86.
- Refreshed the WF84/WF85/WF86 proof chain:
  - `canonical_finance_data_plane.py --write --write-db --validate`
  - `trade_grade_decision_cards.py --write --validate`
  - `trade_grade_full_answer_assembler.py --all-wf84 --write --validate`
  - `wf78_capital_review_queue.py --write --write-db --validate`
  - `finance_decision_factory.py --ledger-only --write --validate`
  - `morning_paper_deployment_recommendation_builder.py --ledger-only --write --write-md --validate`
  - `wf86_shadow_eligibility_validator.py --write --validate`
- Added assisted-mode draft builder:
  - `scripts/wf86_assisted_order_card_builder.py`
  - `scripts/test_wf86_assisted_order_card_builder.py`
- Generated non-executing VRT assisted draft artifacts:
  - `tmp/paper-autotrader/assisted-order-cards.json`
  - `tmp/alpaca-paper-readiness/main-session-cards/VRT.wf86-assisted-card.json`
  - `tmp/alpaca-paper-readiness/paper-trade-request.wf86-assisted-vrt.json`
- Draft details:
  - ticker: VRT
  - side: buy
  - order type / TIF: limit / day
  - notional: `$5,000`
  - limit price: `$288.03`
  - WF84 canonical band: `265.90-318.35`
  - stop: `242.07`
  - cap bridge: `risk_check.full_scope_artifact = tmp/paper-autotrader/policy.json`
  - owner approval: `pending_exact_randall_approval`
  - execution allowed: false
- Current VRT assisted blockers:
  - `band_review_required`
  - `post_apply_band_review_still_open`
- Current WF86/WF67 execution blockers:
  - WF67 guard still blocked
  - shadow threshold not met
  - fresh short-lived kill switch not active
  - audit/reconciliation proof not clean for autonomy
  - separate scoped Randall autonomous paper pilot approval missing
- Boundary unchanged: draft/request artifacts are preparation only; no paper/live submit/cancel/sell authority.

2026-06-11 10:46 MST VRT band review closure for assisted prep:

- Randall approved closing the VRT band review for WF86 assisted preparation by voice note.
- Added durable closure artifact: `tmp/paper-autotrader/band-review-closures.json`.
- Updated `scripts/wf86_shadow_eligibility_validator.py` so approved WF86 band-review closures remove only the assisted-prep blockers:
  - `band_review_required`
  - `post_apply_band_review_still_open`
- Regenerated:
  - `tmp/paper-autotrader/shadow-eligibility.json`
  - `tmp/paper-autotrader/shadow-decisions.json`
  - `tmp/paper-autotrader/assisted-order-cards.json`
  - `tmp/alpaca-paper-readiness/main-session-cards/VRT.wf86-assisted-card.json`
  - `tmp/alpaca-paper-readiness/paper-trade-request.wf86-assisted-vrt.json`
  - `tmp/paper-autotrader/autotrader-readiness.json`
  - `tmp/paper-autotrader/guard-readiness.json`
- Result: VRT assisted draft is now `draft_ready_for_exact_owner_review` with no assisted-review blockers.
- Current VRT draft remains non-executing:
  - owner approval status: `pending_exact_randall_approval`
  - execution ready: false
  - paper/live execution allowed: false
- Remaining execution blockers are WF67/phase gates, not VRT band review:
  - WF67 guard not clean
  - shadow threshold not met
  - fresh short-lived kill switch not active
  - audit/reconciliation proof not autonomy-clean
  - separate scoped autonomous paper pilot approval missing
- Boundary unchanged: band-review closure does not approve the order and does not grant paper/live submit/cancel/sell authority.

## Purpose

Build a main-session-owned paper autotrader that can eventually place bounded paper buy and sell orders from:

- written entry bands, stop/invalidation levels, and no-chase rules
- WF85 trade-grade decision state
- WF84/WF78/WF77 evidence, routing, and freshness surfaces
- market-session quotes and regime/sector conditions
- existing paper positions and risk caps
- WF67 paper-only guard validation, kill switch, wrapper execution, audit, and reconciliation

WF86 is paper simulation only. Live trading, live endpoints, live credentials, account mutation, money movement, and paper-to-live promotion remain blocked.

## Workflow Ownership

- WF85 owns decision/research quality.
- WF67 owns paper-only execution guardrails and wrapper execution.
- WF78/WF77 own routing, capital-review candidates, and evidence repair.
- WF68/WF85 notifications may wake or inform the main session.
- WF55 owns outcome-retention/probability-readiness support.
- **WF86 owns the autonomous paper orchestration policy, shadow decisions, execution-candidate gating, and main-session execution loop.**

Main session must remain the final runtime owner for autonomous paper execution. Cron may prepare artifacts or wake main, but cron must not independently submit, cancel, or sell orders.

## Authority Boundary

Allowed after implementation and validation only:

- create paper autotrader policy artifacts
- classify buy/sell/no-action paper decisions in shadow mode
- generate exact WF67 request artifacts
- run paper-only guard and kill-switch checks
- execute scoped paper buy/sell/cancel through the WF67 wrapper only after the configured autonomy phase allows it
- reconcile paper orders/positions and log outcomes
- notify Randall/main session with proof

Blocked:

- live endpoint, live credentials, live order, live brokerage/account action
- money movement or account settings mutation
- close-position, liquidation, replacement, PATCH, PUT, transfer, or unwrapped brokerage paths
- short sales, margin, leverage, options, crypto, bracket/OCO/OTO orders unless separately scoped and validated
- canonical portfolio/cash/sleeve/risk-rule mutation from a paper packet
- owner approval inferred from score, card, SQL row, alert, notification, or fill
- cron-direct paper execution
- Telegram `APPROVE` execution path
- promotion of paper results to live execution

## Phase Plan

### Phase 0 - Workflow Open and Authority Contract

Deliverables:

- this continuity note
- `state/workflows/WF86.json`
- Active Workflows row
- initial policy artifact at `tmp/paper-autotrader/policy.json`

Acceptance:

- WF86 routes through `workflow_router.py WF86 --answer all`
- Active Workflows records paper-only, main-session-owned, shadow-first posture
- no authority flag implies paper/live execution is currently allowed

Status: opened 2026-06-11.

### Phase 1 - Policy Schema and Decision Contract

Deliverables:

- paper autotrader policy schema
- buy/sell/no-action decision schema
- authority scanner for every WF86 artifact
- validator that fails closed if live/account/canon/execution authority widens
- shadow eligibility validator: `scripts/wf86_shadow_eligibility_validator.py`
- shadow eligibility artifact: `tmp/paper-autotrader/shadow-eligibility.json`

Buy gates:

- ticker is in allowed paper universe or explicitly owner-scoped
- source/freshness state is clean enough for paper review
- same-session quote is fresh
- price is in written band or approved reclaim zone
- no chase above configured band percentile
- stop/invalidation exists and is fresh
- risk from entry to stop fits order and daily loss caps
- no active promotion veto, band review blocker, stale source blocker, or catalyst blackout unless policy explicitly allows it
- market/sector condition filter is not hostile for that sleeve

Sell gates:

- paper position exists and sell quantity cannot exceed held quantity
- stop/invalidation breach
- thesis/catalyst state degradation
- failed reclaim after below-band or below-stop review
- overextension/upper-band trim rule, once approved
- exposure cap or daily risk cap breach
- stale thesis/time-stop rule, once approved

### Phase 2 - Shadow Mode

Run would-buy / would-sell / no-action decisions without submitting orders.

Required outputs:

- `tmp/paper-autotrader/shadow-decisions.json`
- decision reasons, blocked reasons, and source artifacts
- outcome-tracking IDs
- WF55-compatible outcome rows or proposal artifacts

Acceptance:

- several market sessions of clean shadow decisions
- no execution artifacts emitted
- no authority drift
- no stale quote/band/source false-greens

Status: started 2026-06-11. Initial ledger is clean but threshold is not met.

### Phase 2A - Daily Shadow / Reconciliation Cron Runner

Added 2026-06-11 after Randall approved continuing the automatic fill path.

Deliverables:

- `scripts/wf86_daily_shadow_reconciliation_cron_runner.py`
- `scripts/test_wf86_daily_shadow_reconciliation_cron_runner.py`
- `scripts/test_wf86_shadow_decision_ledger.py`
- `tmp/paper-autotrader/wf86-daily-shadow-reconciliation-cron-runner.json`
- `tmp/paper-autotrader/wf86-daily-shadow-reconciliation-cron-runner.md`

Scheduled job:

- Name: `Finance - WF86 Daily Shadow and Paper Reconciliation`
- Job ID: `b9b1b275-b259-4885-a947-e43e5eb0138e`
- Schedule: weekdays at `14:36` America/Phoenix
- Session target: isolated
- Delivery: none
- Model: `openai/gpt-5.4`

Run order:

1. Refresh WF84/WF85 trade-grade OS proof with `trade_grade_os_freshness_cron_runner.py --component daily_core`.
2. Refresh WF86 shadow eligibility.
3. Append/merge WF86 shadow decisions.
4. Run GET-only Alpaca paper-position/order reconciliation to the VRT reconciliation artifact.
5. Refresh WF86 autotrader readiness and guard-readiness packets.
6. Refresh the compact trade-grade OS readiness rollup.

Acceptance:

- runner exits validation `ok`
- ledger counts one decision per ticker per market session
- GET-only reconciliation status is `ok`
- autonomous paper buy remains false until threshold/reconciliation gates clear
- all authority flags remain false for paper submit/cancel/sell/replace, live endpoint, account action, money movement, portfolio/canon mutation, and owner approval inference

Current proof after manual run:

- runner status `ok`
- clean shadow decisions `3/20`
- clean market sessions `1/5`
- paper reconciliation status `ok`
- autonomous paper buy ready `false`
- remaining autonomous blockers: `shadow_threshold_not_met`, `post_trade_reconciliation_not_proven_for_autonomy`
- forced scheduler run status `ok`
- cron control recognizes the job as `fresh` / `NO_REPLY`

Ledger hardening:

- `scripts/wf86_shadow_decision_ledger.py` now merges by `session_key:ticker`, not by action-specific decision ID. This prevents same-session ticker state changes from inflating the 20-decision threshold.

Reconciliation bridge hardening:

- `scripts/trade_grade_os_readiness_rollup.py` no longer treats a `submitted` execution-result artifact as proof the order remains open.
- If GET-only reconciliation shows no matching position and `open_orders_count=0`, the rollup emits `unresolved_after_reconciliation` and requires GET-only order-history drilldown before classifying the paper order as filled, expired, canceled, or rejected.

2026-06-11 14:50 MST all-submitted-order history classifier:

- Added `scripts/alpaca_paper_order_history_classifier.py` and `scripts/test_alpaca_paper_order_history_classifier.py`.
- Scope is all WF67 paper execution-result artifacts with `action=submit` and `status=submitted`; it is not limited to VRT.
- Broker access is GET-only against Alpaca paper `/v2/orders` and `/v2/positions`; no submit/cancel/replace/sell/close-position/live/account action is available in this classifier.
- Output artifact: `tmp/alpaca-paper-readiness/paper-order-history-classifier.json`.
- Classifier buckets submitted paper orders into `open_or_pending`, `filled`, `partially_filled`, `expired`, `canceled`, `rejected`, `replaced`, terminal-other, or unresolved.
- Current live proof classifies `10` submitted paper orders: `9` filled and `1` expired; VRT is classified `expired`, not open and not filled.
- Wired the classifier into `scripts/wf86_daily_shadow_reconciliation_cron_runner.py`, `scripts/trade_grade_os_readiness_rollup.py`, the WF86 route, and the cron freshness spine.
- WF86 remains blocked from autonomous execution: shadow proof is still `3/20` decisions and `1/5` sessions, and reconciliation maturity still needs more accumulated proof.

2026-06-11 21:36 MST WF87 Phase A hardening integration:

- Added WF87 Phase A hardening outputs to the WF86 daily shadow/reconciliation runner:
  - `scripts/wf87_trade_decision_journal.py`
  - `scripts/wf87_position_sizing_runtime_check.py`
  - `scripts/wf87_portfolio_circuit_breakers.py`
  - `scripts/wf87_approval_freshness_ttl.py`
  - `scripts/wf87_intraday_monitor.py`
  - `scripts/wf87_v2_readiness_rollup.py`
- The runner now refreshes these proof artifacts after WF86 readiness and the trade-grade OS rollup:
  - `tmp/paper-autotrader/trade-decision-journal.jsonl`
  - `tmp/wf87-position-sizing-runtime-check.json`
  - `tmp/wf87-portfolio-circuit-breakers.json`
  - `tmp/wf87-approval-freshness-ttl.json`
  - `tmp/wf87-intraday-monitor.json`
  - `tmp/wf87-v2-readiness-rollup.json`
- Current V2 rollup posture is `phase_a_hardening_implemented_runtime_blocked` with validation `ok`.
- This is the intended fail-closed state: Phase A components exist and validate, but runtime gates remain blocked until fresh approval/quote/band/stop/guard/kill-switch/anomaly proof, current paper reconciliation freshness, shadow threshold, and reconciliation maturity are clean.
- The daily runner now continues through WF87 when GET-only paper reconciliation returns a nonzero fail-closed status, but only if the exported artifact remains paper/GET-only with no submit/cancel/live/account/money/approval authority. The runner surfaces that as `MAIN_HANDOFF_REQUIRED`, not execution readiness.
- Boundary unchanged: WF86/WF87 cron proof never submits, cancels, sells, replaces, uses live endpoints, mutates accounts, moves money, infers approval, or promotes paper to live.

2026-06-11 22:20 MST assisted cadence and outcome scoring integration:

- Randall approved the assisted-paper cadence as policy: 1-2 small assisted paper maturity reps per week during fresh-gate windows.
- This is cadence approval only; every exact paper order still requires fresh WF67 guard proof, kill switch, exact card/request, and Randall exact approval.
- Added cadence proof: `scripts/wf87_assisted_paper_cadence.py` -> `tmp/wf87-assisted-paper-cadence.json`.
- Added shadow outcome scorecard: `scripts/wf87_shadow_outcome_scorecard.py` -> `tmp/wf87-shadow-outcome-scorecard.json`.
- Wired both into `scripts/wf86_daily_shadow_reconciliation_cron_runner.py` before `scripts/wf87_v2_readiness_rollup.py`.
- Current cadence proof is `cadence_satisfied_for_week`, validation `ok`; it counts `1` current-week WF86-assisted maturity rep from the VRT terminal paper attempt.
- VRT is classified `expired`; all-time assisted filled round trips remain `0`.
- Current outcome scorecard is `pending_regular_session_followup`, validation `ok`; after-hours duplicate shadow rows are not scored as quality proof.
- Current WF87 rollup taxonomy: `2` maturity blockers, `4` fail-closed-at-rest blockers, `0` unexplained runtime blockers, and `2` binding blockers.
- Daily runner proof remains `ok` with validation `warning` / `MAIN_HANDOFF_REQUIRED` because current GET-only paper reconciliation is blocked at night.
- Boundary unchanged: no cron-direct paper execution, no paper submit/cancel/sell, no live endpoint/account/money movement, no owner approval inference, and no paper-to-live promotion.

### Phase 3 - Assisted Paper Mode

Main session generates exact WF67 request artifacts, but Randall still approves every exact order.

Acceptance:

- request artifacts pass WF67 guard
- kill-switch workflow proves fresh and short-lived
- redacted audit and reconciliation path pass
- buy, sell, and cancel dry-runs are proven

### Phase 4 - Bounded Autonomous Paper Buy Pilot

Only after Randall approves the scoped pilot and Phase 1-3 proof is clean.

Initial constraints:

- paper only
- main session executes; cron does not
- limit/day orders only
- long-only buys
- max notional per order: `$5,000`
- max paper orders per day: `3`
- max same-ticker order count per day: `1`
- no averaging down unless separately approved
- no market orders in autonomous mode
- halt on any guard warning, reconciliation mismatch, stale quote, stale band, authority violation, or unexpected fill behavior

### Phase 5 - Bounded Autonomous Paper Sell/Cancel Pilot

Only existing paper positions may be sold. No close-position or liquidation endpoints.

Initial autonomous sell classes:

- stop/invalidation breach
- severe thesis/catalyst degradation
- failed setup after reclaim/band failure
- exposure cap breach

Profit-taking and discretionary trims require a later policy approval.

### Phase 6 - Full Paper Autotrader Loop

Buy, sell, cancel, reconcile, notify, and outcome-log inside paper-only caps.

Still blocked:

- live trading
- uncapped order size
- cron-direct execution
- Telegram approve-to-execute
- paper-to-live promotion

## Current Owner Decisions

- Shadow mode threshold: `5` market sessions minimum and `20` clean decisions minimum.
- Initial max notional per paper order: `$5,000`.
- Initial autonomous buy universe: Tier A only.
- Initial Tier B posture: shadow-only until explicit review.
- Initial autonomous sell scope: risk-reduction only.
- Initial autonomous profit-taking/trimming: disabled.
- Initial execution window: market hours only.
- Initial fixtures: VRT/NVDA/GOOG shadow-only until blockers clear; assisted VRT only after band-review and WF67 guard proof are clean.

## Stop Lines

Stop immediately if:

- any artifact implies live trading, account action, money movement, or live endpoint access
- any artifact treats owner approval as inferred
- any cron path can submit/cancel/sell without main-session execution ownership
- any Telegram path can approve execution
- any request lacks fresh quote, band, stop, risk, guard, kill-switch, audit, or reconciliation proof
- any generated card/score/SQL row is treated as execution authority

2026-06-11 22:45 MST Fable recommendation implementation pass:

- Tightened `scripts/wf87_assisted_paper_cadence.py` after Fable review: expired/unfilled assisted paper attempts are no longer counted as Phase B maturity reps.
- Current live interpretation changed from "cadence satisfied as maturity" to stricter proof:
  - current-week WF86-assisted attempts: `1`
  - current-week terminal attempts: `1`
  - current-week filled orders: `0`
  - current-week assisted maturity reps: `0`
  - all-time filled round trips: `0`
- Current cadence status is `attempted_cadence_satisfied_maturity_blocked`, validation `ok`.
- Added shadow outcome pending-aging: pending regular-session follow-up becomes stale after 2 market days.
- Added `scripts/wf87_market_hours_gate_probe.py` and test coverage so WF87 can prove fail-closed gates during market hours instead of inferring daytime readiness from after-hours blocked state.
- Added OpenClaw cron `Finance - WF87 Market-Hours Fresh Gate Probe`, Monday-Friday at `06:45`, `08:45`, and `11:45` America/Phoenix. It is review-only daylight proof and cannot create/clear kill switches or submit/cancel/sell.
- Updated the WF86 daily shadow/reconciliation runner to snapshot the market-hours probe and report assisted attempts separately from maturity reps.

Boundary unchanged:

- Cadence approval is not order approval.
- No order resubmission automation, phase promotion automation, kill-switch lifecycle automation, cadence-triggered order, paper/live execution, submit/cancel/sell/replace, live endpoint, account action, money movement, owner approval inference, portfolio/canon/cash/risk-rule mutation, cron-direct execution, or paper-to-live promotion.

2026-06-11 23:00 MST WF87 command center integration:

- Added `scripts/wf87_autonomy_command_center.py`, writing `tmp/wf87-autonomy-command-center.json` and optional Markdown.
- Added `scripts/test_wf87_autonomy_command_center.py`.
- WF86 daily shadow/reconciliation runner now refreshes the command center after WF87 rollup and market-hours probe snapshot.
- Current command-center proof: `maturity_blocked_collecting_data`, validation `ok`, operator action `NO_REPLY`.
- The command center intentionally quiets expected collection state: shadow proof `6/20`, sessions `2/5`, cadence attempt `1`, terminal attempt `1`, maturity reps `0`, filled round trips `0`.
- It will escalate only for validation errors, authority drift, daylight runtime blocks, runtime blockers, or stale pending shadow-outcome follow-up.

Boundary unchanged:

- The command center is a state packet, not approval or execution authority.
- No paper/live order action, kill-switch lifecycle automation, account action, money movement, owner approval inference, cron-direct execution, or paper-to-live promotion.

2026-06-11 23:18 MST WF86 assisted-card hardening:

- Verified and completed the `technical-reclaim-classifier-hardening` lane.
- `scripts/wf86_shadow_eligibility_validator.py` now distinguishes clean add versus tactical dip/reclaim setups, carries reclaim triggers, and emits recommended shadow notional throttles.
- Current shadow eligibility proof is `ok`: 3 candidates, 3 shadow-eligible, 2 would-buy shadows (`VRT`, `GOOG`), execution-ready count 0.
- VRT currently classifies as `TACTICAL_DIP_RECLAIM`, so the assisted draft is throttled to `$1,500` (30% of the `$5,000` policy cap).
- `scripts/wf86_assisted_order_card_builder.py` now strips stale or mismatched exact owner-approval artifacts fail-closed. The prior exact VRT approval at `$288.03` cannot carry forward to the refreshed `$297.88` card.
- Current VRT assisted card: `draft_blocked_before_approval`, limit `$297.88`, notional `$1,500`, blockers `fresh_execution_quote_needed`, `stale_or_mismatched_owner_approval:approval_order_mismatch:limit_price`, and `tactical_dip_reclaim_requires_fresh_exact_owner_review`.
- Added/validated focused tests:
  - `scripts/test_wf86_assisted_order_card_builder.py`
  - `scripts/test_wf86_shadow_eligibility_validator.py`

Boundary unchanged:

- Assisted cards are request drafts only.
- No paper submit/cancel/sell, no live endpoint/account/money movement, no inferred approval, no cron-direct execution, and no paper-to-live promotion.

2026-06-11 23:22 MST WF86 daily runner assisted-card integration:

- The daily WF86 shadow/reconciliation runner now refreshes `scripts\wf86_assisted_order_card_builder.py --write --validate` immediately after shadow eligibility.
- `tmp/paper-autotrader/assisted-order-cards.json` is now part of the WF86/WF87 routing and cron freshness proof set.
- Full runner proof after integration: `status=ok`, `validation=ok`, `operator_action=NO_REPLY`, paper reconciliation `ok`/fresh, shadow proof `6/20`, sessions `2/5`, autonomous ready `false`.
- WF87 command center now surfaces the current assisted-card queue:
  - VRT status `draft_blocked_before_approval`
  - notional `$1,500`
  - limit `$297.88`
  - approval `pending_exact_randall_approval`
  - execution-ready `false`

Boundary unchanged:

- Assisted-card queue visibility is not order approval and does not enable paper submit/cancel/sell.
