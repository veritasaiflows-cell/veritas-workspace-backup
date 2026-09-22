# Forward scorecard rescoring lane

Owner: Main. Requested by Randall in Telegram on 2026-09-17 at 18:37 America/Phoenix: *"proceed with recommendations, and wire it ahead of phase 4."*

Status: **design record with measured feasibility.** It grants no implementation, schedule, canon, capital, order, brokerage, account, paper, or live-execution authority. Nothing in this lane may start before G9 closes. It records a sequencing decision Randall made, the verified root cause, and a measured coverage result, so the work can be scoped on evidence rather than on my earlier and partly incorrect description of it.

## Sequencing decision

**This lane runs ahead of Phase 4.** Randall decided this on 2026-09-17 after reviewing the objective record. Rationale: Phase 4 builds the mechanism to move tickers between tiers, but `Alerts OS Unified Objective - 2026-09-17.md` finds no definition of what makes a name worth promoting in outcome terms. Promotion logic built before an outcome measure exists has nothing to optimise against. This lane produces the outcome measure. Phase 4 consumes it.

## Correction to the prior assessment

On 2026-09-17 I told Randall two things about this that were wrong. Both are corrected here.

**Wrong claim 1: "the harness works and is merely unwired."** It does not work. The scoring path has a structural defect that guarantees a permanently empty result, described below. Connecting inputs to it would not have produced a single score.

**Wrong claim 2: "49 daily snapshots, roughly 3.5 months of daily history, enough to populate every window it defines."** The file count is right; the characterisation is not. There are 47 dated files, but they contain only **31 distinct market data dates**, and they carry a **six-week hole from 2026-06-24 to 2026-08-04**. Most tickers' series terminate at **2026-08-28**, the pivot date. It is not daily history and it does not cover every window.

## Verified root cause

Two independent defects in `scripts/wf55_outcome_ledger_v2.py`. Both verified by reading the source on 2026-09-17.

**Defect 1 — the scorecard is computed once, at append time, when no window has elapsed.**

`forward_scorecard_for_row` (line 259) sets each checkpoint's status by comparing `now` against `due_at = observed_at + horizon_days` (lines 270-281). At append time `now` is approximately `observed_at`, so every horizon is still in the future and every checkpoint is written as `pending_window`.

`append_durable_rows` (line 1206) opens the ledger in `"a"` mode and skips any `ledger_event_id` already present. A row is therefore written exactly once and never revisited. The CLI offers `preview`, `validate`, and `record` (line 1301) — there is no rescore command.

The consequence is not a bug that sometimes fires. **Every row is `pending_window` by construction and can never become anything else.** That is exactly what the ledger shows: 1,660 checkpoints, all pending, `legacy_forward_scorecard_graded_rows: 0`.

**Defect 2 — one price is reused for all four horizons.**

`observed_price` is resolved once per row, outside the horizon loop (line 267), from a single current quote. If the status check ever passed, the 1-day, 5-day, 21-day and 63-day checkpoints would all receive the identical price and the identical `absolute_return_pct`. The structure describes forward windows; the computation does not implement them.

Its quote source, `tmp/post-close-final-quote-ledger.json` (line 25), exists but was last written **2026-08-29 14:43** — the pivot date. `price_quote_map` returns `{}` silently when the file is absent (lines 204-205), so a missing source degrades to no scores with no error.

## Measured feasibility

Probe: `tmp/forward_scorecard_feasibility_probe.py`, read-only, output `tmp/forward-scorecard-feasibility-20260917.json`. It reconstructs per-ticker price series from the retained dated snapshots and asks, for each checkpoint already past due, whether a close exists at or after the due date.

| Checkpoint outcome | Count |
|---|---|
| Scoreable from retained snapshots | **880** |
| No price at or after due date | 458 |
| Not yet due | 318 |
| Missing anchor price | 4 |
| **Total** | **1,660** |

All 27 ledger tickers are present in the snapshot data; none is missing outright. The 458 failures are a **time** problem, not a coverage problem: due dates that land in the 2026-06-24 to 2026-08-04 hole, or after a ticker's series ends at 2026-08-28.

By horizon, scoreable counts are 397 (1D), 329 (5D), 130 (21D), and **24 (63D)**. The long horizon is effectively unmeasurable from retained data, which matters because "long term" is the part of the stated objective this lane exists to serve.

**Conclusion: roughly two thirds of due checkpoints can be scored today, and the 63-day horizon cannot.** That is enough to build and validate the rescorer against real data. It is not enough to characterise long-term outcome quality, and this lane must not be described as delivering that.

### On the returns the probe produced

The probe emitted a return distribution because producing numbers is the proof that the pipeline works. **It is not a performance result and must not be read as one.** The sample is selection-biased — only rows whose windows happened to land on retained dates are included — there is no benchmark, the 63-day cell has 24 observations, and the market environment across the window is uncharacterised. The artifact carries these limits inline. No strategy, model-quality, or predictive-performance claim may be drawn from it.

## What the lane must build

1. **A rescore path.** A command that re-evaluates existing durable rows against current evidence and records results without violating append-only semantics — most likely by appending scored events to the grade-history file rather than mutating ledger rows. The append-only guarantee is load-bearing and must not be relaxed to make rescoring convenient.
2. **Per-horizon price resolution.** Each checkpoint resolves its own observation at its own due date from dated snapshots. Defect 2 is fixed here.
3. **Explicit unscoreable states.** A checkpoint that falls in the data hole must record *why* it cannot be scored. Silent nulls are what let this sit unnoticed since June.
4. **A loud empty result.** `price_quote_map` returning `{}` must not degrade quietly. A scoring run that scores nothing reports a non-green status.

Items 3 and 4 are the general lesson from the sweep, applied to the specific place that needed it.

## Preconditions

- **G9 must close first.** This lane touches no frozen surface, but the standing rule is that no new workstream starts inside the observation window.
- **The pivot validator must be cleared before any component is revived.** `wf55_outcome_ledger_v2.py` builds rows from `build_capital_recommendation_rows`, `build_paper_card_rows`, `build_wf67_paper_manager_rows`, and `build_wf67_paper_position_rows`. These carry capital, deployment, and paper-position semantics that the 2026-08-29 pivot deliberately removed, and `wf67-paper-trading-operator` is a deny-only tombstone. Rescoring must not reanimate those builders as a side effect.
- **The alerts-OS write side stays out of scope.** Wiring the alerts OS to emit new ledger rows would touch `run_alerts_recommendations_chain.py`, which is frozen for G8. This lane scores the 415 rows that already exist. Emitting new ones is a separate, later decision.

## Stop lines

No capital, order, brokerage, account, paper, or live execution authority arises from this document. No sleeve, holding, position, allocation, weight, sizing, tranche, cash, or rebalancing state is created or implied. No canon write, no guarded-SQL write, no schedule change, no cron install, no provider-policy change, no external delivery. Outcome scores produced by this lane are review-only evidence and confer no predictive-performance or model-ranking claim.

## Open items for Randall

1. Whether the 63-day horizon is retained as an aspiration with honest `unscoreable` states, or dropped until price retention improves.
2. Whether price-snapshot retention should be widened going forward so the hole does not recur. This is a retention-policy decision, and under the settled Yahoo-only source decision it is about what is kept, not about buying a new provider.
3. Whether scored outcomes eventually feed Phase 4 promotion criteria, which is the reason this lane was sequenced first.
