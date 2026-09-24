# Alerts OS unified objective

Owner: Main. Stated by Randall in Telegram on 2026-09-17 at 17:21 America/Phoenix, captured on request at 17:34.

Status: **objective record.** This is the first written statement of what the alerts OS is ultimately for. It grants no authority: no capital, order, brokerage, account, paper, or live execution; no canon mutation; no guarded-SQL write; no cron install; no provider expansion; no external delivery. It changes nothing inside the G8 observation window. Its purpose is to give Phase 4 and everything after it a target to be measured against, instead of being judged only against the gates that happen to be open.

**Follow-up (2026-09-23):** `Alerts OS Audit and Monetization Readiness - 2026-09-23.md` audits the whole ecosystem against this objective and a monetization goal. It covers thesis, bands, alerts, context, outcomes and pivot residue. It proposes success measures (open item 3) and a post-G9 roadmap. It is proposal-only.

## The objective, as stated

> This alert system must have a unified goal to ensure it monitors tickers at scale, provides best recommendations for entries and it aims at making money long term. It must align with thesis, market leadership and environment.

Recorded verbatim. Everything below is Main's decomposition of it and an honest measurement of the current system against it. Where a term is undefined, this record says so rather than guessing a definition.

## Why this record exists

Before 2026-09-17 there was no unified goal statement anywhere in the workspace. What existed was:

- **WF85's objective**, the only objective statement in the alerts lane: *"Turn current, source-backed market evidence into concise review states and recommendations while keeping freshness, confidence, uncertainty, and invalidation visible."*
- **A gate ladder** (G1–G9) measuring whether the machinery runs correctly and unattended.
- **A Phase 4 design record** covering tier promotion and demotion plumbing.

WF85's objective is a **fidelity** goal: be honest about what you know. It is a good goal and the system currently meets it. It is not an **outcome** goal. It says nothing about entry quality, return over time, scale beyond the currently evaluated names, or alignment to leadership and environment. The gates measure reliability, not usefulness. Neither answers "is this system worth running."

## Decomposition into five claims

| # | Claim in the objective | What it would require | Status today |
|---|---|---|---|
| 1 | Monitors tickers **at scale** | Evaluated scope grows beyond the current 32 without manual per-name work | **Not met.** 32 evaluated of 300 in the universe. No working promotion path. |
| 2 | Provides **best recommendations for entries** | A defined notion of entry quality, and a way to rank candidates by it | **Not met.** No entry-quality definition exists. Ranking is not by expected outcome. |
| 3 | **Aims at making money long term** | A stated measure of success and a record of whether past calls worked | **Not met.** No target, horizon, or benchmark is defined anywhere. |
| 4 | Aligns with **thesis** | Thesis carried as live evidence, refreshed, and checked at alert time | **Partial.** Thesis informs the band at baseline build; it is not a live field. |
| 5 | Aligns with **market leadership and environment** | Regime, sector, and relative-strength context inside the decision path | **Not met.** No such input exists in the alerts path. |

## Evidence behind each status

**1. Scale.** `universe-v1.json` holds 300 entries; `reference_levels` holds 200 rows, of which 32 are the evaluated scope and 168 are tier-C bench rows. Tier movement is unbuilt: `sql_tier_state` is a hardcoded literal naming a router retired 2026-08-29, `production_scope_member` is 0 for all 300 rows, and `promotion_required_before_action` is 1 even for Tier A. Phase 4 owns exactly this gap.

**2. Entry quality.** The system emits review states — band entry, near band, no chase, invalidation alert, and the rest. These describe *where price sits relative to a frozen band*. "Best" implies an ordering across candidates by expected quality of outcome. No such ordering exists, and no definition of what makes one entry better than another has been written down.

**3. Long-term money.** Nothing in the workspace states a return target, a holding horizon, a benchmark, or an acceptable drawdown. Without one, "making money long term" is unfalsifiable — the system cannot pass or fail it. Note the standing boundary: Veritas does not own positions, sizing, or account state, so any success measure here must be a measure of **recommendation quality**, not portfolio performance.

**4. Thesis.** `reference_levels` carries `reference_price_low`, `reference_price_high`, `reference_invalidation_level`, `reference_confidence`, `reference_band_status`, and source lineage. There is no thesis field. Thesis enters only upstream, when a human-gated baseline apply sets the band. All 1000 lineage cells currently share one `source_generated_at_utc` of 2026-09-10T23:34:45Z. So thesis alignment is real but **frozen and coarse**: the band encodes a thesis held at build time, and drift between that thesis and current reality is invisible until someone rebuilds the baseline.

**5. Leadership and environment.** Verified by search: `run_alerts_recommendations_chain.py` and `alert_level_freshness_controller.py` contain zero references to regime, leadership, sector, or relative strength. Regime and sector work exists elsewhere in the workspace (WF53, WF57, WF61), but none of it is wired into the alert decision path. An alert today fires on price versus a frozen band regardless of whether the name is leading or lagging its sector, and regardless of the macro environment.

## Where Phase 4 lands against this

Phase 4 (`Phase 4 Tier Promotion and Demotion Design - 2026-09-07.md`) addresses **claim 1 only, and only the mechanism half of it.** It builds propose → decision card → owner approval → gated rebuild so that a ticker can lawfully move between tiers. That is genuinely necessary: without it, scale is impossible. It is nowhere near sufficient.

Specifically, Phase 4 as designed does not:

- define what makes a name worth promoting in outcome terms (it inherits a dormant predicate built for a retired router);
- define entry quality or ranking;
- define any success measure;
- carry thesis as a live, refreshable field;
- introduce leadership, regime, or environment anywhere.

Phase 4's own fifth gap (addendum 2026-09-16) is worth reading as a symptom: a promoted name arrives carrying a bench-age baseline and may be stale on arrival. That is what happens when scale is built as plumbing without an evidence model behind it.

**Conclusion: Phase 4 is a prerequisite, not the plan.** Meeting the stated objective needs at least four more named workstreams that do not currently exist.

## What is missing and needs naming

These are gaps, not proposals. Each would need its own design record and its own owner decision.

1. **A success measure.** What "making money long term" means in recommendation terms — horizon, benchmark, and how a call is scored after the fact. **Assessed 2026-09-17 — see "The scoring harness already exists" below. Do not design new scoring before reading it.**
2. **An entry-quality definition.** What separates a good entry from a merely valid one, expressed so it can be computed and ranked, not just asserted.
3. **Thesis as live evidence.** A thesis field with its own freshness policy and its own decay behaviour, so thesis drift becomes visible the way quote staleness already is. Today the band is the only carrier of thesis and it is frozen at a single stamp.
4. **Leadership and environment inputs.** A defined path by which regime, sector leadership, and relative strength enter the alert decision — including what the system should do when a technically valid band entry sits in a losing group.

## The scoring harness already exists and is unwired

Assessed 2026-09-17 in response to open item 4. This materially changes what gap 1 costs.

**`tmp/recommendation-outcome-ledger-current.json` (WF55) is live.** It regenerated 2026-09-17T05:12:06Z, status `ok`. It carries an `outcome_grading_taxonomy` whose stated purpose is *"Grade recommendations/decisions once outcomes resolve, as semantic decision/outcome grades while blocking predictive-performance and model-ranking claims."* Its assignment status is `enabled_for_deterministic_review_only_evidence` and `requires_separate_gate_before_assignment: false`. Durable append is **already approved by Randall, 2026-06-19**, scoped to append-only review-only outcome rows, with capital, paper/live execution, brokerage, canon mutation, model-ranking, and owner-approval inference all explicitly blocked.

**It is grading nothing.** `tracking_row_count: 0`, `tracked_tickers: []`, `applied_to_rows: 0`, `last_append_report: null`, `consumer_posture: review_only_outcome_tracking_not_model_ready`. It reads `tmp/wf55-outcome-ledger-v2-migration-preview.json` and the pivot-era capital-deployment packets. Verified by search: `run_alerts_recommendations_chain.py` and `alert_level_freshness_controller.py` contain **zero** references to it. The alerts OS emits review states and never writes a tracked row.

So the measurement harness was built, approved, and left running against a source that the 2026-08-29 pivot removed. It has produced an empty ledger every day since.

**The two scripts named in the earlier draft of this record, assessed:**

- `finance_recommendation_correctness_ledger.py` (331 lines, last ran 2026-08-29 22:14 — the pivot date). Despite the name it does **not** grade outcomes. Its docstring: *"ex-ante rule/authority correctness surface... checks whether current recommendation packets carried the required finance discipline and boundary language. It does not assign later outcome grades."* It is a compliance checker, not a scorer. Its input `tmp/capital-deployment-recommendation-validation.json` no longer exists.
- `finance_recommendation_lookback_engine.py` (717 lines, last ran 2026-06-12). This one *is* outcome-adjacent: it computes observable 1D / 5D / 20–21D / 60–63D forward windows from retained dated price snapshots. Its recommendation input `tmp/wf78-deployment-readiness-human-review.json` is gone with WF78. **Its price data is partly alive.** `data/market/price-snapshots/` holds 47 dated files plus current/supplemental, spanning 2026-05-29 to 2026-09-16. **Corrected 2026-09-17:** an earlier draft of this record called that "roughly 3.5 months of daily history — enough to populate every window it defines." That was wrong. The 47 files contain only **31 distinct market data dates**, with a **six-week hole from 2026-06-24 to 2026-08-04**, and most tickers' series terminate at **2026-08-28**, the pivot date. See `Forward Scorecard Rescoring Lane - 2026-09-17.md` for the measured consequence.

Neither script is referenced by any cron job.

### The durable ledger is not empty — the forward scorecard is

Found 2026-09-17 while auditing the empty `tracking_row_count`. The daily artifact's own `durable_v2_ledger` block points at two append-only files that already hold real history:

| File | Rows | Content |
|---|---|---|
| `data/state-history/outcome-ledger-v2.jsonl` | 415 | 415 recommendation tracking rows across 27 tickers |
| `data/state-history/recommendation-outcome-grades.jsonl` | 2943 | 2943 assigned grade events, 316 of them attached to ledger rows |

Grade distribution: `no_chase_correct` 1359, `band_reclaim_held` 1095, `entry_poor_even_if_thesis_right` 260, `stop_or_invalidation_hit` 229.

But: `forward_scorecard_status_counts: {"pending": 415}` and `legacy_forward_scorecard_graded_rows: 0`. **Every row is pending. Not one has ever been forward-scored.**

The two files have diverged. `outcome-ledger-v2.jsonl` was last written 2026-08-28 22:12 — it froze at the pivot. `recommendation-outcome-grades.jsonl` was last written 2026-09-16 22:12 and is still being appended. The last ledger row is XOM observed 2026-08-28T13:24:42Z; the last grade event is a `no_chase_correct` with `event_subtype: owner_decision_pending` and an evidence window that came due 2026-09-16T13:25:26Z at a 21-day horizon.

So the system has graded **decision discipline** — did the call follow the rules, did it chase, did it respect invalidation — 2,943 times. It has never measured **what price actually did afterward** on any of the 415 rows. Those are different questions and only the second one speaks to claim 3.

**What this means for gap 1. Revised 2026-09-17 after reading the source.** An earlier draft framed this as "the harness works and is merely unwired." That was wrong and is corrected here. The scoring path in `scripts/wf55_outcome_ledger_v2.py` carries a structural defect: the forward scorecard is computed once at append time, when no window has yet elapsed, and the ledger is append-only with no rescore command — so every checkpoint is `pending_window` by construction and can never become anything else. A second defect reuses one current price across all four horizons. Connecting inputs to this would have produced nothing.

The accurate framing: *an owner-approved review-only grading surface exists, 415 rows with anchor prices and due dates are already durably recorded, and the scoring step that would resolve them was never capable of running.* A read-only probe on 2026-09-17 measured that **880 of 1,660 checkpoints are scoreable from retained snapshots**, 458 fall in the price-history hole, and the 63-day horizon has only 24 observations. That is enough to build and validate a rescorer, and not enough to characterise long-term outcome quality.

`Forward Scorecard Rescoring Lane - 2026-09-17.md` owns this work. Randall sequenced it **ahead of Phase 4** on 2026-09-17, because promotion logic built before an outcome measure exists has nothing to optimise against.

**Caution before anyone acts on this.** These are pivot-era components. Reviving them without clearing the pivot validator would risk importing capital/deployment/position semantics that the 2026-08-29 pivot deliberately removed — the same failure mode Phase 4 documents for the retired WF78 router. Any wiring work must pass that check first, and none of it may start before G9.

## Relationship to the gates

None of this is G8 work. G8 is observing one frozen build for five sessions and this record touches no code, no job payload, no canon, and no policy. Nothing here may be started before G9 closes unless Randall explicitly says otherwise.

The right sequence is: close G8, close G9, then decide Phase 4 scope **against this objective** rather than against the tier-plumbing design alone.

## Open items for Randall

1. Accept, amend, or replace the objective as stated above. Everything downstream is measured against it, so it is worth getting the wording right.
2. Decide whether Phase 4 keeps its current narrow tier-plumbing scope, or is widened to carry an evidence model that makes promotion meaningful.
3. Decide the success measure (gap 1). This is the one that unblocks the others — entry quality and leadership weighting cannot be evaluated without a definition of what a good outcome looks like.
4. Confirm whether the existing recommendation-ledger scripts are live, retired, or pivot-era residue, before any new scoring work is designed.

## Stop lines

No capital, order, brokerage, account, paper, or live execution authority arises from this document. No sleeve, holding, position, allocation, weight, sizing, tranche, cash, or rebalancing state is created or implied. No canon write, no guarded-SQL tier write, no schedule change, no cron install, no provider-policy change, and no external delivery. This record does not authorise starting any of the four missing workstreams; it names them so they can be decided.
