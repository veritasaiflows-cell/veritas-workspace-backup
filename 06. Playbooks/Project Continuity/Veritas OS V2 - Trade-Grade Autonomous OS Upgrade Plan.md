# Veritas OS V2 - Trade-Grade Autonomous OS Upgrade Plan

Opened: 2026-06-11
Workflow: WF87
Owner: Veritas main session
Status: Official workflow, plan approved for registration; execution authority unchanged

## V2 Plan - Part 1 Executive Summary

V2 is not a rebuild. The current spine is already close: WF84 data plane -> WF85 decision OS -> WF86 paper autotrader, guarded by WF67. The $5k autonomous-pilot approval artifact is valid, the WF67 guard is ok, and the cap bridge passed. The remaining autonomy blockers are shadow proof and reconciliation maturity: currently 3/20 decisions and 1/5 sessions. Those accrue through the 14:36 daily cron, so they are time-gated, not rebuild-gated.

V2 has three workstreams.

## Workstream 1 - Autonomy Hardening

Phase A runs for roughly two weeks in parallel with shadow accrual. The script audit identified five missing runtime components before autonomous execution is actually safe:

| Gap | Fix |
|---|---|
| Position sizing enforcement | Promote the WF78 sizing proposal layer into a fail-closed runtime check in WF86. |
| Portfolio circuit breakers | Add daily loss cap, exposure cap, and concentration halt into the WF67 guard chain. |
| Intraday monitoring | Add market-hours cron from 06:30 to 13:00 for stop breaches, fill drift, anomaly halt, and main-session wake. |
| Stop management wiring | Make WF86 sell gates consume same-session refreshed stops from the existing entry_band gate. |
| Approval/freshness TTL | Expired approvals, quotes, or bands block automatically. |

Phases:

1. Phase A: runtime hardening, validators, and fail-closed checks.
2. Phase B: assisted mode; Randall approves each paper order and the system proves clean round trips.
3. Phase C: autonomous paper buy pilot under existing caps: Tier A, $5k, max 3/day.
4. Phase D: autonomous risk-reduction sells and full loop.
5. Phase E: live trading remains explicitly out of scope and requires a separate doctrine decision after 2-3 months of measured paper track record.

V2 does not deliver live autonomy. It delivers the proof needed to decide whether a live-autonomy conversation is justified later.

## Workstream 2 - One Unified Picture

Current approval/decision state is fragmented across 8+ stores. V2 consolidates to:

- A single append-only trade-decision journal extending the WF86 shadow ledger: decision -> gates -> approval -> order -> fill -> outcome in one record.
- One readiness rollup as the single "state of the OS" packet.
- WF79 Command Center reading the readiness rollup instead of scattered state.
- Legacy overlaps, including finance-canon.sqlite vs WF84 and decision-sync-spine, folded through gated lifecycle paths.

## Workstream 3 - Script And Canon Optimization

Current script estate is large: 666 scripts, approximately 390 active spine scripts, 138 tests, and about 138 legacy/paused/one-off scripts.

V2 prepares a gated archive proposal batch of roughly 80-100 candidates, focused on completed one-offs, paused SaaS surfaces, superseded dashboards, and shims. No deletes or moves happen outside the tombstone/rollback gate.

Canon remains the owner truth layer. It is already parser-compatible and compact. V2 adds only:

- A daily canon-vs-WF84 drift validator.
- Machine-checkable refresh stamps.

## Decisions Needed

1. Approve the V2 plan shape or redline phases/order.
2. Confirm Phase C trigger: shadow threshold plus clean Phase B round trips, not calendar time. Recommended answer: yes.
3. Decide whether WF79 Command Center promotion to P0 is in scope now or after Phase C.

## Recommended Build Order

Start with the decision journal and the two risk validators. This has the highest leverage and grants zero new authority.

Initial implementation sequence:

1. Trade-decision journal contract and append-only writer.
2. Position-sizing runtime validator.
3. Portfolio circuit-breaker runtime validator.
4. Readiness rollup unification.
5. WF79 Command Center rollup consumer.
6. Intraday monitor and stop-management wiring.
7. Assisted-mode paper round-trip proof.
8. Autonomous paper buy pilot only after shadow and reconciliation thresholds are clean.

## Stop Lines

- Cron never executes paper/live orders.
- No inferred approval.
- No paper-to-live promotion.
- No live endpoint, live credentials, live order, account action, or money movement.
- No portfolio/canon/cash/risk-rule mutation outside existing exact gates.
- No autonomous paper submit/cancel/sell until the separate scoped pilot gate clears.
- Generated cards, readiness rows, dashboards, SQL rows, or Telegram alerts never become owner approval.

## Current Proof Inputs

- WF84 data plane: ready support layer.
- WF85 decision OS: primary trade-grade review layer.
- WF86 paper autotrader: shadow-first, no autonomous execution authority.
- WF67 paper guard: ok in current guard proof, still requires fresh execution-time proof for any paper order.
- Cap bridge: passed for the existing $5k autonomous-pilot policy artifact.
- Shadow proof: incomplete, currently 3/20 decisions and 1/5 sessions.
- Reconciliation maturity: incomplete, accrues through daily WF86 shadow/reconciliation cron.

## Implementation Checkpoint - 2026-06-11 21:36 MST

Phase A hardening pass is implemented as proof-producing runtime gates, not execution authority.

Parallel-lane outputs:

- WF87 append-only trade-decision journal: `scripts/wf87_trade_decision_journal.py`, writing `tmp/paper-autotrader/trade-decision-journal.jsonl`.
- WF87 position sizing runtime check: `scripts/wf87_position_sizing_runtime_check.py`, writing `tmp/wf87-position-sizing-runtime-check.json`.
- WF87 portfolio circuit breakers: `scripts/wf87_portfolio_circuit_breakers.py`, writing `tmp/wf87-portfolio-circuit-breakers.json`.
- WF87 approval/freshness TTL: `scripts/wf87_approval_freshness_ttl.py`, writing `tmp/wf87-approval-freshness-ttl.json`.
- WF87 intraday monitor: `scripts/wf87_intraday_monitor.py`, writing `tmp/wf87-intraday-monitor.json`.
- WF87 unified readiness rollup: `scripts/wf87_v2_readiness_rollup.py`, writing `tmp/wf87-v2-readiness-rollup.json`.

Integration:

- `scripts/wf86_daily_shadow_reconciliation_cron_runner.py` now refreshes all WF87 Phase A proof artifacts after WF86 readiness and the trade-grade OS rollup.
- WF86 and WF87 routes in `scripts/workflow_routing_index.py` now point to the Phase A artifacts and validators.
- `06. Playbooks/Active Workflows.md` now records WF87 as Phase A implemented but runtime blocked/fail-closed.
- Fable challenger review was used as a read-only hardening pass; its concerns are reflected in the V2 rollup checks: fail-closed rollup behavior, journal idempotency/authority drift, approval provenance, per-cycle kill-switch/TTL checks, and breach-simulation validator coverage.

Current live status:

- `tmp/wf87-v2-readiness-rollup.json`: `phase_a_hardening_implemented_runtime_blocked`, validation `ok`.
- Phase A components installed: true.
- Phase A runtime gates clean: false.
- Shadow threshold: still incomplete.
- Reconciliation maturity: still not autonomous-ready because historical order classification is clean, but current paper-position reconciliation freshness is blocked.
- Current runtime blockers are expected fail-closed signals: expired approval/quote/band/stop/guard/kill-switch proof, missing anomaly/halt proof, same-session stop absence, current paper reconciliation blocked, and current circuit-breaker inputs not clean.

Boundary:

- This checkpoint does not authorize paper/live execution.
- Cron may refresh proof and wake/report only.
- No capital deployment approval, owner approval inference, live endpoint, account action, money movement, portfolio/canon mutation, or paper-to-live promotion is granted.

## Continuation Notes

## Implementation Checkpoint - 2026-06-11 23:00 MST

Added the WF87 autonomy command center as the owner-facing V2 state packet:

- `scripts/wf87_autonomy_command_center.py`
- `scripts/test_wf87_autonomy_command_center.py`
- `tmp/wf87-autonomy-command-center.json`
- `tmp/wf87-autonomy-command-center.md`

Purpose:

- One compact readiness surface across WF87 rollup, WF86 daily runner, assisted cadence, shadow outcome scoring, market-hours gate probe, and cron health.
- Quiet expected data-collection state as `NO_REPLY` when only maturity blockers and at-rest fail-closed states are present.
- Escalate only for validation errors, authority drift, daylight runtime blocks, runtime blockers, or stale pending outcome follow-up.

Current live command-center proof:

- Status: `maturity_blocked_collecting_data`
- Validation: `ok`
- Operator action: `NO_REPLY`
- Shadow proof: `6/20` decisions and `2/5` sessions
- Assisted cadence: `1` current-week attempt, `1` terminal attempt, `0` maturity reps, `0` filled round trips
- Daylight probe: outside-market-hours sample only tonight

Integration:

- WF86 daily shadow/reconciliation runner now refreshes the command center after the V2 rollup and market-hours probe snapshot.
- Cron freshness spine and workflow routing index now treat the command center as a first-class WF87 proof surface.
- Active Workflows now points WF87 owner-facing state to `tmp/wf87-autonomy-command-center.json`, with `tmp/wf87-v2-readiness-rollup.json` retained as the machine readiness packet.

Boundary:

- Command center is review-only.
- It does not approve capital, create/cancel/sell orders, create/clear kill switches, mutate accounts, move money, infer owner approval, or promote paper to live.

## Implementation Checkpoint - 2026-06-11 23:08 MST

Added shadow outcome non-score cause classification:

- `scripts/wf87_shadow_outcome_scorecard.py` now labels each non-scored row with `non_score_cause`, `non_score_cause_detail`, and `score_blockers`.
- Summary now includes `non_score_cause_counts`.
- `scripts/wf87_autonomy_command_center.py` surfaces those cause counts as `shadow_outcome_non_score_cause_counts`.

Current live cause counts:

- `awaiting_regular_session_followup`: `2`
- `duplicate_or_unaccepted_followup_context`: `2`
- `non_scoreable_shadow_decision`: `2`

Interpretation:

- Current would-buy rows are not scored because they still need later regular-session follow-up.
- After-hours/same-context duplicate rows are explicitly treated as unaccepted follow-up, not quality proof.
- Repair-only shadow rows are informational and not model-quality evidence.

Boundary:

- Cause classification is calibration only.
- No decision-quality claim, model-performance claim, capital approval, order authority, account action, money movement, owner approval inference, or paper-to-live promotion.

## Implementation Checkpoint - 2026-06-11 22:45 MST

Fable recommendation implementation pass completed without using a new challenger lane. The earlier cadence interpretation was tightened:

- Expired/unfilled assisted paper attempts are telemetry and cadence evidence only; they no longer count as Phase B maturity reps.
- Current VRT WF86-assisted paper attempt remains classified `expired`; current-week assisted attempts `1`, terminal attempts `1`, filled orders `0`, maturity reps `0`, filled round trips `0`.
- Assisted cadence proof now reports `attempted_cadence_satisfied_maturity_blocked`, validation `ok`.
- WF87 rollup still reports `phase_a_hardening_implemented_runtime_blocked`, validation `ok`; binding blockers are still `shadow_threshold_not_met` and `reconciliation_maturity_not_met`.
- Shadow outcome scorecard now has a 2-market-day pending-aging threshold; current state is `pending_regular_session_followup`, validation `ok`, pending `4`, stale pending `0`.
- Added `scripts/wf87_market_hours_gate_probe.py` and `scripts/test_wf87_market_hours_gate_probe.py`.
- Added scheduled review-only cron `Finance - WF87 Market-Hours Fresh Gate Probe` at `06:45`, `08:45`, and `11:45` America/Phoenix, Monday-Friday.
- The probe refreshes WF87 runtime proof during regular market hours so fail-closed-at-rest blockers can be proven clean or blocked in daylight rather than inferred from nighttime state.
- The WF86 daily shadow/reconciliation runner now snapshots the market-hours probe and reports assisted attempts separately from maturity reps.
- WF86/WF87 workflow routing and cron freshness contracts now include the market-hours probe artifact and validator.

Boundary:

- No order resubmission automation.
- No phase promotion automation.
- No kill-switch creation or clearing automation.
- No at-rest-to-clean reclassification without daylight proof.
- No cadence-triggered orders.
- No paper/live execution, no submit/cancel/sell/replace, no live endpoint, no account action, no money movement, no owner approval inference, no portfolio/canon/cash/risk-rule mutation, and no paper-to-live promotion.

## Implementation Checkpoint - 2026-06-11 22:20 MST

Randall approved the assisted-paper cadence as policy: 1-2 small assisted paper maturity reps per week during fresh-gate windows, with each exact order still requiring fresh WF67 proof and exact owner approval.

Added Phase B readiness support surfaces:

- `scripts/wf87_assisted_paper_cadence.py`, writing `tmp/wf87-assisted-paper-cadence.json`.
- `scripts/wf87_shadow_outcome_scorecard.py`, writing `tmp/wf87-shadow-outcome-scorecard.json`.
- Tests:
  - `scripts/test_wf87_assisted_paper_cadence.py`
  - `scripts/test_wf87_shadow_outcome_scorecard.py`

Integration:

- `scripts/wf87_v2_readiness_rollup.py` now consumes the cadence proof and outcome scorecard.
- The rollup now separates blockers into:
  - `maturity_blockers`
  - `fail_closed_at_rest`
  - `runtime_blockers`
  - `binding_blockers`
- `scripts/wf86_daily_shadow_reconciliation_cron_runner.py` now refreshes cadence and outcome proof before the V2 rollup.
- `scripts/cron_freshness_spine.py` now expects the WF87 proof surfaces for the WF86 daily job and treats review-only blocked-at-rest WF87 roles as main-review semantics rather than false urgent automation breakage.
- WF86/WF87 workflow routing now lists the cadence/outcome artifacts and validators.

Current live proof:

- WF87 V2 rollup: `phase_a_hardening_implemented_runtime_blocked`, validation `ok`.
- Shadow proof: `6/20` clean decisions and `2/5` clean market sessions.
- Assisted cadence: `cadence_satisfied_for_week`, validation `ok`.
- Current-week WF86-assisted maturity reps: `1`.
- All-time assisted filled round trips: `0`.
- Shadow outcome scorecard: `pending_regular_session_followup`, validation `ok`.
- Shadow outcomes scored: `0`; pending regular-session follow-up: `4`.
- Rollup blocker taxonomy: `2` maturity blockers, `4` fail-closed-at-rest blockers, `0` unexplained runtime blockers, `2` binding blockers.
- WF86 daily runner: `ok`, validation `warning`, operator action `MAIN_HANDOFF_REQUIRED` because current GET-only paper reconciliation is blocked at night.

Important interpretation:

- The current VRT WF86-assisted rep is a terminal reconciled paper attempt, classified `expired`; it is not a filled round trip.
- Outcome scoring does not score after-hours duplicate shadow rows as quality proof.
- Phase B/C remain blocked until clean assisted-mode reps and shadow/reconciliation maturity prove out.

Residual unrelated safety signal:

- Global cron control still reports one escalation from `Finance - WF63/WF67 Paper Position Read-Only Refresh`.
- The source is `tmp/finance-intelligence-state-paper-positions.json`, status `blocked`, validation `ok`, with `kill_switch_invalid:not_expired`.
- This was not quieted because it is a paper-trading safety signal, not a WF87 implementation failure.

Boundary:

- Cadence approval is not order approval.
- No paper/live execution, no submit/cancel/sell/replace, no live endpoint, no account action, no money movement, no owner approval inference, no portfolio/canon/cash/risk-rule mutation, and no paper-to-live promotion.

## Implementation Checkpoint - 2026-06-11 22:14 MST

Added two review-only V2 tracking surfaces so WF87 can measure implementation quality and finance-decision follow-through without pretending those measurements are mature skill proof.

Added:

- `scripts/coding_outcome_ledger.py`, writing:
  - `data/state-history/coding-outcome-ledger.jsonl`
  - `tmp/coding-outcome-ledger-current.json`
- `scripts/finance_decision_performance_digest.py`, writing:
  - `tmp/finance-decision-performance-digest.json`
  - `tmp/finance-decision-performance-digest.md`
- Tests:
  - `scripts/test_coding_outcome_ledger.py`
  - `scripts/test_finance_decision_performance_digest.py`

Purpose:

- Coding outcome ledger: append-only tracking of completed implementation lanes, proof artifacts, acceptance commands, and later-review placeholders for rework/regression.
- Finance decision performance digest: one review-only slice over WF55 recommendation outcomes, WF87 trade-decision journal rows, WF87 shadow outcome scoring, and WF87 readiness.

Current live proof:

- Coding outcome ledger rows: `54`.
- Finance digest:
  - WF55 recommendation-tracking rows: `15`
  - tracked tickers: `9`
  - WF87 journal rows: `6`
  - terminal tracked paper-order outcomes: `2`
  - WF87 shadow scoreable decisions: `0`
  - status: `pending_mature_observations`

Important interpretation:

- The finance digest is a truth surface for collection and follow-through, not a predictive-quality score.
- Current WF55 forward windows are still pending and current WF87 shadow outcomes do not yet have mature regular-session follow-up observations.
- The coding ledger currently reports `warning`, not because this slice widened authority, but because the shared lane register still contains a pre-existing forbidden-write validation error on `C:/Users/Veritas/.openclaw/openclaw.json` from `RUNTIME::anthropic-fable5-openclaw-route`.

Boundary:

- No predictive skill claim, no win-rate/expected-return claim, no approval, no execution, no account action, no money movement, no canon/portfolio mutation, and no owner approval inference.

Say "Part 2" for unified-picture/state detail.
Say "Part 3" for script/workflow consolidation detail.

## Implementation Checkpoint - 2026-06-11 23:18 MST

Completed the next implementation slice after WF87 command-center and shadow-outcome work:

- WF86 assisted order prep now includes technical reclaim classification and notional throttling.
- VRT currently routes as `TACTICAL_DIP_RECLAIM`, so the assisted draft is `$1,500`, not the full `$5,000` policy cap.
- Stale exact owner approval is now stripped fail-closed when terms no longer match fresh card inputs. The old VRT approval at `$288.03` no longer applies to the refreshed `$297.88` draft.
- Current VRT assisted-card proof is `draft_blocked_before_approval` with blockers:
  - `fresh_execution_quote_needed`
  - `stale_or_mismatched_owner_approval:approval_order_mismatch:limit_price`
  - `tactical_dip_reclaim_requires_fresh_exact_owner_review`
- WF67 paper-position visibility was refreshed through the GET-only chain. Current packet is `ok`, fresh, 7 paper positions, 0 open orders, paper endpoint only.
- Cron freshness now has `blocked_count=0`, `urgent_attention_count=0`, `implementation_attention_count=0`; cron control packet is `ok`, escalation `0`.
- Lane register active count is `0`; the remaining lane validation error is historical bookkeeping from `RUNTIME::anthropic-fable5-openclaw-route` declaring `.openclaw/openclaw.json` in allowed writes.

Validation:

- `python scripts\test_wf86_assisted_order_card_builder.py`
- `python scripts\test_wf86_shadow_eligibility_validator.py`
- `python scripts\wf86_shadow_eligibility_validator.py --write --validate`
- `python scripts\wf86_assisted_order_card_builder.py --write --validate`
- `python scripts\test_wf67_paper_position_readiness_classifier.py`
- `python scripts\wf67_paper_position_refresh_cron_check.py --write --validate`
- `python scripts\wf67_paper_position_refresh_cron_runner.py --write --validate`
- `python scripts\cron_freshness_spine.py --write --validate`
- `python scripts\cron_control_packet.py --write --validate`
- `python scripts\changed_file_validator_router.py --write --validate`

Boundary unchanged: V2 remains proof/assisted-prep only until maturity gates clear. No paper/live execution, no submit/cancel/sell/replace, no live endpoint, no account action, no money movement, no inferred approval, no portfolio/canon/cash/risk-rule mutation, no cron-direct execution, and no paper-to-live promotion.

## Implementation Checkpoint - 2026-06-11 23:22 MST

Closed the loop between WF86 assisted-card preparation and the WF87 command-center single picture:

- Added `tmp/paper-autotrader/assisted-order-cards.json` as an optional command-center source.
- The WF87 command center now reports current assisted-card status, ticker, notional, limit, owner-approval status, review blockers, execution blockers, and execution-ready false.
- The WF86 daily runner now refreshes the assisted-card queue before shadow ledger / WF87 rollup / command-center generation.
- Cron freshness and workflow routing now list the assisted-card queue as a nonblocking proof artifact.
- Current proof:
  - WF86 daily runner: `ok`, validation `ok`, operator action `NO_REPLY`
  - WF87 command center: `maturity_blocked_collecting_data`, validation `ok`, operator action `NO_REPLY`
  - VRT assisted draft: `draft_blocked_before_approval`, `$1,500` notional, `$297.88` limit, `pending_exact_randall_approval`, execution-ready `false`
  - cron control: `ok`, escalation `0`

Boundary unchanged: command-center visibility does not create approval, paper execution, live execution, account action, money movement, kill-switch lifecycle authority, owner approval inference, or paper-to-live promotion.
