# WF78 Decision-Family Completeness Blocked Audit and Remediation Plan

**Owner:** Veritas main session  
**Generated (UTC):** 2026-06-21T00:00:00Z (local workspace evidence snapshot)  
**Scope:** Unblock WF78/decision-family completeness blockers (`blocked_missing_freshness`, stale evidence, owner-card gate dependencies) and stabilize the related cron refresh posture.

**Authority boundary:** Review-only and non-capital. No cron schedule mutation in this artifact. No canon/portfolio mutation, live trading, account action, or deployment approval inference.

## Executive summary

WF78 decision-families are not fundamentally broken; they are blocked by two independent factors:

1. **Cron execution reliability gap** — `Finance - WF78 Daily Freshness and Promotion Proof` is in error (consecutive errors > 0), while adjacent WF78 jobs are running.
2. **Blocker composition is evidence-heavy** — even when the runner executes, there are persistent freshness and evidence classes (`stale_source_open`, `blocked_structural`, missing/degraded source-open and band context, technical/freshness debt) that require explicit repair waves before decision-grade unblocking.

Net effect: cron is helping, but it is not enough by itself. Decision-fidelity remains constrained by open proof/research queues.

## 1) Audit findings with evidence

### 1.1 Cron/control posture snapshot

- From `tmp/cron-list-live.json`:
  - `Finance - WF78 Daily Freshness and Promotion Proof` (schedule `8 6 * * 1-5`) status = `error`, `consecutive_errors` = 2.
  - `Finance - WF78 Open-Ready Owner Review Proof` (`20 6 * * 1-5`) status = `ok`.
  - `Finance - WF87 Market-Hours Fresh Gate Probe` (`45 6,8,11 * * 1-5`) status = `ok`.
  - `Finance - WF87 Autonomy Command Center Refresh` (`50 6,8,11 * * 1-5`) status = `ok`.
- `tmp/wf78-daily-freshness-cron-launcher.json` and `tmp/wf78-daily-freshness-cron-runner.json` confirm the WF78 daily runner remains review-only and non-authority-expanding; runner status remains `ok` and escalation signals are currently zero.

### 1.2 Decision-family blocker composition

From `tmp/wf78-daily-freshness-loop.json`:
- `trade_grade_decision_cards.decision_state_counts`
  - `below_stop_or_invalidation`: 88
  - `blocked_missing_freshness`: 7
  - `monitor_only`: 89
  - `evidence_repair`: 2
  - `no_chase`: 14
- `trade_grade_repair_conveyor` shows finance-domain repair rows are complete and no implementation blocker, but control-plane still needs active repair processing:
  - `finance_domain_blocker_count`: 200
  - `finance_or_owner_gate_repair_item_count`: 200
  - `primary_state_blocker_repair`: 24
  - `wf78_source_open_or_owner_lineage_repair`: 11
  - `freshness_repair_after_band_review`: 10
- Freshness ledger in same summary:
  - `stale_refreshable`: 171
  - `stale_source_open`: 10
  - `fresh`: 10
  - `blocked_structural`: 9
- Top stale families repeatedly include: `stale:catalyst_earnings_state`, `stale:deployment_readiness`, `stale:price_band_stop`, `stale:technical_posture`, `stale:recommendation_support` (count 158 each in current top list).

### 1.3 Repair surface currently queued

From `tmp/wf78-repair-priority-queue.json`:
- `repair_count`: 52
  - `general_evidence_repair`: 11
  - `technical_or_band_gap`: 31
  - `source_open_gap`: 7
  - `analyst_revision_gap`: 3
- Tier split: A=13, B=24, C=15.

From `tmp/wf78-source-open-work-packets.json` and `tmp/wf78-source-open-repair-execution.json`:
- Source-open execution mode = `needs_deployment_readiness_surface` for 28 rows.
- Equal split by tiers: 14 Tier A and 14 Tier B.
- Priority top groups include `ITA, LIN, PAVE, PH, RTX, SMCI, VAW, VMC, VXUS, XLF, XLI, BKNG, CME, META...` etc.

From `tmp/wf78-missing-band-context-repair.json`:
- `active_missing_band_repair_context_count`: 15 (Tier B).
- `repair_status = ready_for_decision_grade_band_context` for those 15 rows.
- `repair_applied`: false (pending proof-to-use conversion not yet promoted).

From `tmp/wf78-event-triggered-rerouting.json`:
- `repair_evidence`: 190
- `reroute_review`: 21
- `owner_action_required`: 3
- `owner_action_required_count`: 3 with next-safe-action explicitly set to repair evidence and reroute labels only.

### 1.4 Routing/movement context

From `tmp/wf78-routing-dashboard.json` summary (`routing_delta` section):
- Active tickers: 200
- Stale count: 190
- Auto tier counts: A=24, B=29, C=147
- Auto state includes `A-CHALLENGED` (17), `A-WATCH` (4), `A-READY` (3), holds/repair/stale states present.
- `capital_deployment_approved_count`: 0, `trade_or_execution_approved_count`: 0 (as expected by boundary).

## 2) Root-cause diagnosis

### Root-cause A — Cron refresh is unstable, not complete

One core WF78 proof job is failing and has repeated failures despite active schedule. That limits confidence in fresh recovery and can delay repair consumption, especially if upstream artifacts are stale.

### Root-cause B — Decision blocking is mostly repair debt, not gating logic

Even when WF78 loop runs cleanly, evidence freshness and source lineage are still stale at scale (high `stale_*`, source-open gaps, missing/partial band context). These are semantic blockers that must clear through repair jobs.

### Root-cause C — Missing/undriven execution on repair queue

`repair_count=52`, with many rows across families, indicates broad queued work but no broad automatic clearance for all classes in-place. `repair_conveyor_ready_for_repair_execution` is true but queue progression is still manual/packetized.

### Root-cause D — Cadence exists but not fully coupled to failure recovery

Cadence has pre-open/intraday/probes in place, but failure recovery for WF78 daily proof is not currently acting as a hard dependency with explicit run-fail re-execution guardrails visible on this ticket path.

## 3) Remediation plan (execution-safe, review-only)

### Phase 0 — Guardrail freeze and measurement (Immediate, 0.5 day)

Goal: remove ambiguity and stop blind reruns.

1. Confirm WF78 cron launcher/runner pair has not drifted from current commands:
   - `tmp/wf78-daily-freshness-cron-launcher.json`
   - `tmp/wf78-daily-freshness-cron-runner.json`
2. Capture the exact failing payload/message for daily WF78 job from cron ledger.
3. Document failure trend: consecutive_errors, last run timestamps, prior successful run hash.

Acceptance:
- Exact failing root command/path known.
- No schedule mutation performed; no authority expansion.

### Phase 1 — Fix WF78 daily runner stability (Immediate, 1 day)

Goal: get daily freshness chain back to reliable green status.

Actions:
1. Re-run the daily WF78 proof job directly in a controlled session and capture diagnostics:
   - `python scripts/wf78_daily_freshness_cron_runner.py --write --validate`
2. If failing persists, isolate failing sub-step by running candidate commands from loop payload one-by-one and record first failing step.
3. Remove only transient blockers (path, command typo, stale artifact contract mismatch).

Acceptance:
- Cron state changes from `error` to stable `ok` with `consecutive_errors = 0` in `cron-list-live.json` for the WF78 daily job.

### Phase 2 — Prioritize repair classes (1 day)

Goal: convert decision-family debt into near-term reductions.

1. Execute source-open repair packet(s):
   - `tmp/wf78-source-open-work-packets.json`
   - `tmp/wf78-source-open-repair-execution.json`
2. Process three packets in this order:
   - `deployment_readiness_surface-01`
   - `deployment_readiness_surface-02`
   - `deployment_readiness_surface-03`
3. Preserve non-blocking monitor state for structural hold cases.

Acceptance:
- Source-open repair row count reduces materially from 28.
- More rows move from `stale_source_open`/`blocked_structural` to supported states.

### Phase 3 — Band-context backlog closeout (same day)

Goal: remove missing/blocked band context that blocks decision-grade completeness.

1. Execute:
   - `python scripts/wf78_missing_band_context_repair.py --write --validate`
2. Re-verify `tmp/wf78-missing-band-context-repair.json`:
   - `ready_for_decision_grade_band_context_count` should convert from 15 to 0 only via evidence/decision pipeline.
3. Re-run WF78 daily loop and confirm top stale families decrement.

Acceptance:
- Band-context repair rows move out of queued state into contextual decision-grade readiness.

### Phase 4 — Controlled reroute/evidence cleanup (1 day)

Goal: reduce `repair_conveyor` finance-domain blockers and avoid route churn.

1. Re-run source-status and reroute proof:
   - `tmp/wf78-event-triggered-rerouting.json`
   - `tmp/wf78-routing-dashboard.json`
2. Triage `repair_evidence` actions first, then `reroute_review`.
3. Keep `owner_action_required` queue untouched unless explicitly requested by owner (this run remains review-only).

Acceptance:
- `wf78-repair-priority-queue.json` repair_count materially down.
- `owner_action_required` unchanged unless queue semantics require escalation.

### Phase 5 — Post-work validation loop

Goal: verify blocker classes are reduced and not shifted.

Run/verify evidence in sequence:
1. `tmp/wf78-daily-freshness-loop.json`
2. `tmp/wf78-repair-priority-queue.json`
3. `tmp/wf78-source-open-repair-execution.json`
4. `tmp/wf78-routing-dashboard.json`

Pass criteria:
- `trade_grade_decision_cards.blocked_missing_freshness` decreases from 7.
- `stale_source_open` decreases from 10.
- `wf78-repair-priority-queue.summary.repair_count` decreases from 52.
- WF78 daily cron job transitions from `error` to `ok` with no immediate re-fault.
- No authority breaches and no non-owner-capital actions triggered.

## 4) Recommended cadence for this recovery

Keep the existing market-aware rhythm, with a temporary escalation overlay for the failing WF78 daily proof:

1. **Pre-open**: `06:08` daily WF78 proof, `06:15` layered advancement, `06:20` open-ready owner-review.
2. **Morning lane**: `06:42` Tier A intraday opportunity probe.
3. **Market-hour checks**: `08:50`, `11:50` WF87 probes.
4. **Post-close**: existing post-close jobs (currently in place around `13:55`, `15:00+`).

Overlay (recovery logic): if `consecutive_errors >= 2` on WF78 daily proof, trigger one immediate rerun cycle and pause any cadence expansion until one successful clear run is observed.

## 5) Risks and limits

- **Residual evidence risk:** Freshness families may continue due to external market events and external-source latency.
- **Control-plane risk:** Not all classes are implementation blockers; over-aggressive mutation could misroute repair efforts.
- **Boundary risk:** Owner actions and deployment approvals must remain off by default.

## 6) Concrete outcomes expected (2–3 run cycles)

- Cron reliability: WF78 daily job back to stable green.
- Decision-family blockers: `blocked_missing_freshness` trend downward and reduced stale-source-open debt.
- Repair queues: shrinking from 52 toward a single-digit maintenance level.
- Routing posture: less stale and more consistent decision-grade read states in `trade_grade_decision_cards` and `routing_delta`.

---

## 7) Owner-ready next actions

1. Execute Phase 0–1 first (cron stability + error capture).
2. Execute Phase 2 and Phase 3 in parallel via separate workers where safe.
3. Run Phase 5 validation after each packet batch.
4. Do not widen cadence before proving two consecutive successful WF78 daily proof runs.
