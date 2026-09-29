# Phase 4 Unified Monitoring and Scale-Out Plan - 2026-09-27

Status: **planned; nothing executed. No canon, tier, schedule, config, or authority change.** Owner direction: Randall, WebChat 2026-09-27 ~12:01, "review attach and plan a fix to ensure we integrate this into phase 4. This has to be fully functional alert system that is unified and is able to monitor up to thousands of names." Parent record: `Phase 4 Tier Promotion and Demotion Design - 2026-09-07.md`.

## Conclusion

"Bands on promotion" is confirmed as the rule for **decision-grade** bands. That alone cannot satisfy the thousands-name monitoring goal: promotion-only leaves 268 of 300 names (and any future expansion) with no monitoring surface at all. The unified system therefore needs **three monitoring grades**, one method, clearly labelled, with only the top grade feeding alerts. The 168 carried-over Tier C rows prove what happens to bands nobody renews: they go stale and mislabel. Screening bands fix that by being recomputed weekly and never persisted stale. The build integrates into the existing Phase 4 spine (per-name writer P4-2, D3 onboarding, readiness gate, scope-change stop rule) rather than adding a parallel system.

## Verified current state (first-hand, 2026-09-27 ~12:05-12:15 Phoenix)

- Tiers: 15 A / 17 B / 268 C = 300 names (`universe_membership`, live canon). Matches the reviewed Q&A exactly.
- Band rows: 200 total. All 32 A+B have rows; 168 of 268 Tier C have carried-over rows from the 08-30 migration (59 still carry status labels: 21 IN_BAND, 19 NEAR_BAND, 14 BELOW_STOP, 4 ABOVE_BAND_WAIT, 1 RECLAIM_ONLY; 141 NULL); 100 Tier C have no row. Nothing renews the 168; the alert chain does not read them.
- Static-32 removal: accepted and committed (`31154c3b`). Both HIGH QA findings fixed first-hand: a non-regular prior applied-audit record now stops the renewal (`weekly_band_renewal.py`), and every apply now requires a scoped, fingerprint-matched, live-verified matrix (`g6_yahoo32_sql_apply.py`). Tests rerun 12:0x: g6 125/125, renewal suite, matrix suite all pass.
- Scope-change stop rule (D2): in and enforced. First renewal after any promotion/demotion stops for owner review.
- Aggregator fixes committed (`3d7721c5`): quarter-lag fallback (ETN/GS cause found; confirmation pending next Windows-host refresh) and BRK.B P/B 0.0 rejection.
- Caps in force: Tier A 15 / Tier B 17 proof-period caps (both full); evaluated-scope policy cap 128 (`max_scope_count`); 200-row canon guard (`finance_sql_canon_access.py`, inventory S7) blocks D3 inserts today.
- Option B standing approval covers renewal **for the evaluated scope only**. Auto-apply conditions unchanged; the label-clearing amendment (08:17) is recorded.
- No promotion path exists today: the tier writer was retired (`ca1a7381`), `resolve_production_scope` has no current feed, and the promotion rule is undefined until the forward scorecard exists (10-15 readiness gate).

## Target architecture: three monitoring grades

| Grade | Who | What they get | Feeds alerts? | Authority |
|---|---|---|---|---|
| **Decision-grade** | Evaluated scope (A+B, cap 128 policy / 15+17 proof-period) | Weekly renewed reference bands under Option B, full alert canon, theses, readiness gate | **Yes — the only alert source** | Option B + existing gates |
| **Screening** | All 300 universe names (A+B+C) | Weekly recomputed **bench bands**, review-only, never persisted stale; weekly digest of names near/through bands and promotion-candidate flags | No — review-only digest | One new standing approval |
| **Universe watch** | Future expansion toward thousands | Cheaper snapshot screening (batched quotes vs rolling windows), no per-name evidence model | No | Owner decision per expansion step |

One method, three grades, honest labels. "Monitor thousands" means the screening/watch layers produce review-only flags; decision-grade alerts stay capped to the evaluated scope until capacity is proven and you raise the cap deliberately.

## Reconciliation with the bands-on-promotion review (2026-09-27 12:09; adopted)

The second-opinion review (GPT-6 Astra session, same records checked) is adopted with five amendments that refine this plan. Verified first-hand: the host deployment IS the repaired committed code (`3d7721c5`, clean scripts tree, both HIGH-finding fixes in the live files) — the review's open deployment concern is closed. Tier B thesis coverage is 0 of 17 (AMD, AMZN, BKNG, CAT, CVX, ECL, GE, KTOS, LLY, LNG, NFLX, PLTR, RTX, SMCI, TMUS, VMC, WMB).

1. **Tier semantics adopted:** Tier A = "deserves intensive research", not "most likely to rise". A Tier A name can stay no-chase or monitor-only. Tier and attractiveness remain separate.
2. **Promotion policy defined now, calibrated later:** two tests — (a) can we cover it reliably (identity, liquidity, current official evidence, capacity, onboarding proofs); (b) is additional attention justified (thesis strength, developments, catalysts, distinct value vs existing coverage). C→B needs a credible source-backed monitoring case; B→A needs a clear reason intensive coverage adds value. Caps stay. Challenger admission and incumbent demotion justify independently; our own missing evidence is repair debt, not a demotion reason.
3. **Band-before-promotion flow replaces promote-then-wait:** candidate → evidence and thesis review → proposed fresh band → owner approval → guarded onboarding/tier change → readiness verification → recommendation eligibility; bandless interim state is explicitly monitor-only. The D2 scope-change stop stays as backstop. No grandfathering: stale existing bands are revalidated through the same path. Guard contract becomes validated membership/completeness/lineage/pin-consistency, not a looser row count.
4. **Scorecard tests the process, not newcomers:** requiring prior recommendation success to become covered is circular — uncovered names cannot earn the history. Forward outcomes evaluate ranking/band methodology and benchmark-relative results; newcomers qualify through evidence-based review. Oct 15 remains scorer-first for activating *automated* tier movement only.
5. **Coverage before expansion:** Tier B theses (0/17) are the critical path and proceed first. These two threads don't compete for the same resource: thesis drafting is Main-plus-owner work; the writer lane is delegated builder/QA work. Stage 2 screening remains "not decision-grade bands": review-only bench screening for all 300, never persisted to `reference_levels` — composition, not conflict, with bands-on-promotion.

**Adopted order:** finish Tier B coverage (batches of ~5, official Q2 evidence, same pattern as Tier A this morning) → promotion policy decision cards (now defined, per #2) → Oct 15 scorer readiness assessment → per-name writer + onboarding lane (D-D) → pilot exactly one owner-approved swap. No tier, band, schedule, or approval change made by adopting this reconciliation.

## Stage 1 - Decision-grade completeness (P4-2 lane, already owner-directed)

Bundle, built once in the same lane:

1. **Per-name tier writer (proposal-only):** weekly read-only proposal job lists promotion/demotion candidates with reasons; one decision card per name carrying the Tier Entitlement contract's 10 required proofs; you accept/reject/defer; a gated write applies only what you approved. Proposed cadence: weekly, Sunday, after the alerts/recommendations refresh (closes the open cadence question).
2. **D3 onboarding INSERT path:** for a promoted name with no `reference_levels` row, an owner-gated insert writes the band row, evidence row, and lineage rows. Until then such names stay monitor-only.
3. **200-row guard contract change:** the S7 guard moves from "exactly 200 rows" to a scope-derived contract (guards what the dynamic scope says should exist).
4. **Promotion rule:** forward scorecard first (your 09-17 direction), then scored quality + readiness gate becomes the rule. Interim manual rule only if you choose speed over measured quality.

Flow after Stage 1 follows the newer adopted reconciliation above: candidate → evidence and accepted thesis review → fresh promotion-band packet → owner-approved onboarding insert/refresh → separately owner-approved tier transaction → readiness verification. The first weekly renewal after the scope change still **stops for your review** under D2. A bandless name remains monitor-only and cannot enter the evaluated scope; no code/test/generated packet grants apply or activation authority.

## Stage 2 - Weekly screening refresh (new; needs one standing approval)

- **What:** recompute bench bands for all 300 names weekly with the same band method; write a review-only packet (JSON + digest MD) to a **separate review-only surface**, never to `reference_levels`. Recomputed weekly, never carried stale — that is the fix for the 168-row problem class.
- **Digest:** names near/through bench bands, data completeness, and promotion-candidate flags feeding the Stage 1 proposal job.
- **Cost:** ~268 extra Yahoo pulls/week beyond the evaluated scope (batched, off-peak, rate-limited).
- **Authority:** Option B is untouched; this is a new standing permission for a weekly non-capital research job. The 168 carried-over rows stay inert; once screening is live, propose an owner-gated cleanup (archive or relabel) so Tier C band context comes from the fresh surface.

## Stage 3 - Thousands-name scale (design now, build after 1-2 prove out)

- **Data supply is the real constraint, not code.** Per-name daily-bar pulls do not scale to thousands. The watch grade needs batched quote snapshots against rolling windows. Heavy automated Yahoo pulling at thousands-scale may exceed fair use; a licensed/screener feed is the durable answer and is a purchase decision, not a build task.
- **Cadence tiers:** evaluated scope keeps daily bars + weekly renewal; screening weekly; universe watch weekly snapshot only.
- **Caps:** the 128 evaluated-scope policy cap and 15/17 proof-period caps stay until four consecutive weeks of 100% Tier A coverage and your explicit raise.
- **Universe expansion:** `universe-v1.json` is owner-written at pivots; each expansion step is your decision, informed by screening evidence from Stage 2.
- **History:** WF78 was the 500-ticker scaleout attempt; its auto-router was deliberately retired at the 08-29 pivot. Reusable patterns exist (tier routing, freshness ledgers), but promotion stays owner-decided. The retired `tmp/wf78-*` files remain a separate cleanup decision.

## Build order

1. Stage 1 lane (P4-2: writer + D3 + guard change) — prerequisites partially met; promotion rule lands with the scorecard.
2. Stage 2 screening job — can build in parallel once you approve the standing permission.
3. 168-row cleanup decision — after Stage 2 is live.
4. Stage 3 — design artifact first; build gated on data-supply decision.

## Owner decisions needed

- **D-A:** Approve Stage 2 as a new standing permission (weekly screening refresh, review-only, ~268 extra pulls/week).
- **D-B:** Confirm scorecard-first for the promotion rule (default per your 09-17 direction) vs an interim manual rule.
- **D-C:** 168 carried-over rows: leave inert (default) or owner-gated cleanup after Stage 2.
- **D-D:** Implementation route for Stage 1 lane: same proposal route (builder drafts, Main applies, independent QA) — implementer per your 08:40 instruction.

## Not granted by this plan

Tier changes, promotion/demotion, canon writes, the screening job itself, schedule/config/runtime changes, evaluated-scope cap raises, capital, orders, accounts, execution, external delivery, or any alert-canon mutation. Alerts remain decision-grade only.

## P4-2 source closeout - 2026-09-27 17:xx Phoenix

**Outcome: source landing accepted; production activation and Phase 4 cutover remain blocked.** Main recovered both Muse Spark sandboxes, verified their declared hashes, applied the bounded source/tests, and narrowed unsafe draft claims after independent GPT-6 Sol review. No live canon, tier, band, baseline, schedule, config, runtime, delivery, capital, account, order, or execution mutation occurred.

Landed inert surfaces:

- `weekly_tier_proposal_job.py`: guarded-SQL, read-only proposal packet and owner digest; no apply mode; canonical physical `<root>/tmp` output containment. It emits all 10 proof slots but keeps identity, prior-version, official-source/macro thesis proof, non-quote recency, duplicate census, enrollment, queue, rollback and capacity gaps visibly `missing`/`blocked` instead of manufacturing readiness.
- `promotion_candidate_band.py`: review-only, no-repair candidate packet using the existing band method and guarded symbol; output refusal happens before any network call.
- `finance_sql_canon_access.py`: S7 moved from fixed 200 rows to pin-count/projection consistency, equal reference/evidence sets, full A/B coverage, and reference/evidence universe containment. The live 200-row canon remains validation-clean.
- `reference_level_onboarding_writer.py` and `tier_membership_writer.py`: production apply/rollback are explicitly blocked because no exact apply-authorization/cutover contract exists. Mutation internals are reachable only for an exact OS-temp hermetic fixture DB with a marker, no `.git`, and test activation; they are test foundations, not live writers.

Main proof: 125 focused checks pass (proposal 22, tier writer 21, guard scope 14, candidate band 23, onboarding 45), Python compile passes, final shared validator bundle executed 9/9 with 0 failures, the live proposal smoke is 15 A / 17 B / 268 C with 0 demotions and 0 swap pairs, and live production mutation probes refuse with the canon logical hash unchanged (`595232b0...c302`). Independent GPT-6 Sol final QA passed each narrowed actual-applied-diff packet with no remaining Critical/High finding. QA packet hashes and Main acceptance live under `tmp/p4-2-writer-lane-20260927/`.

Still required before cutover: a separate exact apply authorization; per-ticker lease; pending state, timeout and restart recovery; producer/consumer and queue enrollment proof; authenticated owner decision binding; live-safe atomic restore semantics; dedicated recency/corporate-action/macro/analyst/census inputs; Oct-15 scorer-readiness decision; and one separately owner-approved pilot swap. Stage 2 standing permission remains ungranted.
## 2026-09-28 decisions and build (Randall, Telegram msg 11233, 10:02 MST)

Grant text: "Proceed with the build. D-A approved. Proceed as recommended with D-b."

- **D-A approved.** Stage 2 weekly screening is a standing permission: `state/finance/standing-approvals/weekly-screening-refresh.json` (max 320 names, one attempt per name, 0.5 s pacing, 1,200 s cap, stop above 25% provider failures after 40 calls; review_by 2026-12-28).
- **D-B decided: scorecard-first.** The promotion rule stays unset until the forward scorecard exists. The Oct-15 scorer-readiness gate decides whether automated tier movement can start. Until then every promotion is a manual owner decision under the adopted two-test policy. No interim manual rule.
- **D-C unchanged (default):** the 168 carried-over Tier C band rows stay inert until Stage 2 has run for a while; cleanup is a later owner decision.
- **D-D in effect:** implementation stays in the proposal route. Today Main (Claude, GitHub session) implemented and one fresh independent agent reviewed. Reason: the Muse Spark dispatch path, a one-shot isolated agentTurn, is down under the 2026.9.6 DataCloneError bug (#157067).

### Stage 2 live

- `scripts/weekly_screening_refresh.py` (+ 30 tests): the matrix band method, unchanged and with no repair list, runs across all active universe names. Position is judged against the bench band as it stood 5 sessions earlier, because a same-day band cannot be broken by the bar it was computed from. Flags (`screen-flags-v1-provisional`, uncalibrated):
  - `review_candidate` (Tier C only): uptrend, in or near the band low, 20-day average dollar volume >= $20M.
  - `bench_breakdown`: any tier, close below the prior-week bench invalidation.
- Writes only `tmp/weekly-screening-refresh.json/.md` and `tmp/weekly-screening/<session>.json`.
- Cron `e6532249` "Finance - Weekly Screening Refresh (Stage 2)" runs Saturday 10:00 Phoenix (after the 09:00 renewal). Contract `state/cron-contracts/finance-weekly-screening-refresh.json`; validator drift 0 across 60 contracts.
- First live run, session 2026-09-25: 300/300 screened, 297 computed, 300 calls.
  - 47 review candidates. That is loose; calibrate before relying on it.
  - 27 bench breakdowns, all Tier C, 12 of them utilities (a sector move) plus TLT.
  - 3 names with no bars (EA, AVB, EQR): Yahoo quote but no daily bars since ~July. EA's $209.70 sits on its $210 take-private price. Routed as `no_bars_identity_review`; the corporate-action/identity input is still missing.

### P4-3a tier transaction core (source landed; activation still blocked)

- `scripts/tier_transaction_journal.py`: separate `state/finance/tier-transactions.sqlite`.
  - Per-ticker lease; `pending_coverage -> effective | blocked | expired`, `effective -> rolled_back`.
  - Timeout = end of the next NYSE session (2026/2027 holidays; an unknown year means an earlier timeout).
  - One-shot decision consumption; restart recovery from canon commit evidence.
- `scripts/tier_owner_decision.py`:
  - Cutover gate `state/finance/standing-approvals/phase4-tier-cutover.json`. It does not exist, so production stays blocked.
  - Per-change owner-decision records under `state/finance/tier-decisions/`, bound to ticker, tiers, card and packet sha, valid 14 days at most, never overwritten.
- `scripts/tier_membership_writer.py` changes:
  - Needs a bound owner decision per entry, in every mode including dry run.
  - Journal lease plus a re-check under `BEGIN IMMEDIATE`.
  - Journal settled on every failure branch: blocked when canon is provably unchanged, pending (recovery decides) when unknown.
  - New `--recover [--after-crash]`.
  - New `--rollback-txn`: a live-safe compare-and-swap inverse that preserves later unrelated writes and requires paired swaps to be rolled back together.
- Proof: 213 passed / 2 skipped (pre-existing) across the Phase 4 suites; g6 138/138. Live canon logical sha unchanged (`595232b0...c302`); guard ok; scope 15/17. No live journal, cutover or decision file exists.

### Still required before any live tier change

1. P4-3b: the onboarding writer on the same cutover gate, owner-decision binding and inverse (delete-inserted-rows) rollback.
2. Dedicated inputs for recency, identity/corporate actions (today's EA/AVB/EQR case), macro, analyst, and the duplicate-surface census, so the proposal job's `missing` proof slots can turn `satisfied`.
3. Producer/consumer and queue enrollment proof.
4. Oct-15 scorer-readiness decision (D-B).
5. Randall's explicit cutover approval (creates the gate file).
6. One separately approved pilot swap.

## Owner decisions recorded - 2026-09-28 10:02 Phoenix

Randall, Telegram: "Proceed with the build. D-A approved. Proceed as recommended with D-b."

- **D-A APPROVED:** Stage 2 weekly screening refresh is a standing permission. Review-only bench bands for all 300 universe names, recomputed weekly to a separate review-only surface, never persisted to reference_levels; ~268 extra Yahoo pulls/week, batched, off-peak, rate-limited.
- **D-B CONFIRMED:** scorecard-first promotion rule stands. No automated tier movement before the Oct-15 scorer-readiness assessment passes.
- **Cutover-safety build directed:** per-ticker lease, pending/timeout/restart recovery, exact owner-approval binding, live-safe atomic rollback, producer-consumer and queue enrollment proof, and dedicated recency/identity/corporate-action/census inputs. Code-only on hermetic copies; production apply stays refused.
- **D-C unchanged:** the 168 carried-over Tier C band rows stay inert until screening is live, then a separate cleanup decision.

These decisions grant no tier change, band write to reference_levels, canon mutation, cap raise, capital, order, account, or execution authority.

## 2026-09-28 late: lane repair and P4-3a QA restart

- **Parallel-session drift corrected.** A 12:10 session did not see P4-3a. It planned `scripts/p4_cutover_safety.py`, now **superseded; do not build it**. It also built a duplicate Stage 2 screener, `scripts/screening_bench_bands.py`, that no cron uses; the canonical screener is `weekly_screening_refresh.py` via cron `e6532249`. Archiving the duplicate awaits owner OK.
- **Lanes:**
  - S2 screening lane cancelled as superseded.
  - Cutover-safety lane re-leased to 2026-10-01T05:26Z, scoped to the P4-3a files.
  - Checkpoint `resume-0015` supersedes the stale ARENA `resume-0013`.
- **P4-3a is not yet QA-accepted.** The first independent review left no verdict. A fresh read-only review writes to `tmp/p4-3-tier-txn-core-20260928/qa-verdict.json`. P4-3a is commit-ready only after its findings are closed.

## 2026-09-29: P4-3a accepted and committed

Randall, Telegram msg 11314 (16:56 MST): "Proceed with short confirmation and commit."

- **Independent QA closed.** GPT-6 Sol reviewed P4-3a in 11 read-only rounds (qa-redteam agent, WF89 dispatch records). Rounds 1-10 returned REJECT with progressively narrower findings; Main confirmed each finding in code and fixed it with a regression test. Round 11 returned **ACCEPT** with no new findings: R8-1 (the whole decision record is now attested by a digest in canon's apply event) and R10-1 (canon attests the backup hash, and restore hashes the actual backup file content, lines 408-409) are both fixed; R6-1 and R7-1 stay fixed; the only exit-4 paths after a commit are the two intentional compensations.
- **Proof:** the 4 P4-3a suites pass 155/155, the wider 7 suites 267/267, and the live canon logical sha is unchanged (`595232b0f823`). `tier-transactions.sqlite`, `tier-decisions/` and `phase4-tier-cutover.json` are all absent. Evidence (gitignored): `tmp/p4-3-tier-txn-core-20260928/qa-verdict-round4..11.json` and `main-acceptance-p43a.json`.
- **Committed:** P4-3a (writer, journal, owner-decision and their tests) together with the Stage 2 screening job, its standing approval and its cron contract.
- **Activation stays blocked.** Production apply and rollback refuse until Randall grants a separate `phase4-tier-cutover` approval. The Oct-15 scorer gate and one owner-approved pilot swap also still stand.
- **Next:** P4-3b, the onboarding writer (same gate, owner-decision binding, and an inverse rollback that deletes the inserted rows). The duplicate screener `screening_bench_bands.py` stays uncommitted and still awaits the owner's OK to archive.
