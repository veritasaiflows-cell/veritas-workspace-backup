# Alerts OS audit and monetization readiness

Owner: Main. Requested by Randall in Telegram on 2026-09-23 at 09:03 America/Phoenix: *"Complete an audit of our new finance alert system and phase 3 and phase 4 work … provide recommendations to ensure we have a robust, intelligent and very capable alert system that will allow me to monetize these alerts. Ensure thesis, bands, alerts and all the ecosystem is well structured and future work is well aligned to this goal."*

Status: **audit record, read-only.** It was written while G8 Day 5 was still in session. It touched no frozen surface, canon row, job, schedule, or config. It grants no capital, order, brokerage, account, paper, live-execution, external-delivery, customer, or publication authority. Every recommendation below is a proposal for Randall's decision, sequenced to start **after G9**. Work continues from here after G8 and G9 close.

Read with: `Alerts OS Unified Objective - 2026-09-17.md` (the outcome objective), `Phase 3 Main-Only End-to-End Acceptance - 2026-09-05.md` (G1–G9), `Phase 4 Tier Promotion and Demotion Design - 2026-09-07.md`, `Forward Scorecard Rescoring Lane - 2026-09-17.md`, `Workflow 85 - Alerts and Recommendations OS.md`, and `03. Alerts and Recommendations/`.

---

## 1. Bottom line

1. **The machinery is sound. The product is not yet sellable.** Phase 3 built a reliable, fail-closed, auditable pipeline: guarded SQL, content-addressed baselines, rollback, freshness decay, and an honest authority boundary. That is a real asset, and most retail alert services do not have it.
2. **What the pipeline emits today is a status board, not an alert service.** Every run classifies all 32 names against mechanical technical bands and sends a ticker list. It carries no thesis, no ranking, no context, and no track record. Nobody pays for that, and it currently fails our own WF85 output contract.
3. **The single most valuable missing asset is a verifiable track record, and it cannot be backfilled.** Every week without an immutable, timestamped record of the calls the system makes is a week of sellable history lost. This is the top post-G9 priority, above Phase 4.
4. **Phase 4 is correctly sequenced after the scorecard, and it should be widened.** As designed it is tier plumbing. Promotion must require outcome evidence, a live thesis, and a fresh band, or scale just multiplies an unproven signal.
5. **Monetization has preconditions outside the code**: the market-data licence, regulatory posture, and separating the personal system from the product. They are cheap to decide early and expensive to discover late. They are listed in section 7 as owner decisions, not as defects.

---

## 2. Scope and method

- **Read:** the five owner records above, the four canon files in `03. Alerts and Recommendations/`, the G9 reconciliation register, and the G8 observation declaration and its addenda.
- **Inspected live, read-only:** `state/finance/finance-canon.sqlite`, covering `reference_levels`, `universe_membership` and `finance_state_meta`. Also the current digest, controller and chain-run history (`tmp/alerts-chain-runs/`, 359 files); the digest send state; the 32-ticker band derivation matrix (`tmp/g8-yahoo32-reference-level-matrix-20260916.json`); and the earnings, macro and analyst evidence artifacts with their cron contracts. Code greps covered `run_alerts_recommendations_chain.py`, `alert_level_freshness_controller.py` and `finance_alert_os_digest.py`.
- **Not done:**
  - No full line-by-line code review of the chain.
  - No execution of any finance job.
  - No performance claim of any kind. The only outcome data in the workspace is the pre-pivot ledger, and its limits are documented in the scorecard lane.
- Measurements are as of 2026-09-23 ~16:00Z unless stated.

---

## 3. Phase 3 (G1–G9) status

| Gate | Status | Evidence |
|---|---|---|
| G1–G4 | PASS | G9 register `gate_state` |
| G5 | PASS_WITH_WARNINGS | Opus 5 actual-diff QA, accepted 2026-09-06 |
| G6 | CLOSED (owner-approved close with documented limit) | `tmp/g6-closure-proof-20260911.json` |
| G7 | CLOSED (Path A: four jobs cut over; the analyst job is unchanged by design) | `tmp/phase3-main-only-20260905/g7-live-closeout-20260914.json` |
| G8 | Days 1–3 banked creditable (09-17, 09-18, 09-21). **Day 4 (09-22) is not yet adjudicated.** Day 5 (09-23) is in session. | declaration addenda, last updated 2026-09-22T03:48Z |
| G9 | Blocked on G8 | register `open_in_progress` |

**Findings:**

- **G3-1. Day 4 needs explicit adjudication before G9.** On 09-22 the pivot-validator seed `tmp/alerts-os-pivot-validator.json` errored with "morning chain proof is not coherent and green" (see `memory/2026-09-22.md`). The fix was deferred as a G8-frozen surface. Whether that affects the "morning refresh on time / zero fail-open" voiding conditions has to be decided on evidence. It must not be assumed.
- **G3-2. The G9 register is stale.** Its `gate_state.G8` still reads `NOT_STARTED` and its last update is 2026-09-17. G9 is meant to be "a review rather than a reconstruction", so it should be brought current with Days 1–5 before the review.
- **G3-3. Baseline expiry is the next hard date.** The active pin (`067398e2…`, generated 2026-09-17T01:22Z, 14-day limit) expires around **2026-10-01T01:22Z, which is 09-30 18:22 Phoenix**, with the warning from about 09-26. Every evaluated ticker flips to `freshness_decay` at once on expiry. Renewal needs one owner approval of recomputed Yahoo values; it is not blocked on any provider question.
- **G3-4. Post-G8 items are ready and should be applied in order.** The session-boundary false-decay controller fix has a prepared package: `tmp/preopen-post-g8-package-20260922/package.md`. The pivot-validator seed repair is deferred to post-G8. The analyst-consensus extension from 18 to 32 is defined in `post-g9-analyst-consensus-extension-lane-definition-20260912.json`.
- **G3-5. Naming collision.** WF85 uses "Phase 3" for the *tier-entitlement external cutover* (18→32 external workloads). The acceptance program uses "Phase 3" for G1–G9. They are different programs. Rename one, for example "Entitlement Phase 3" versus "Acceptance Phase 3", before post-G9 planning, or decisions will be attributed to the wrong program.

**Assessment:** Phase 3 delivered what it set out to deliver, which is **reliability and auditability**. That is necessary for a monetizable product but not enough. No G-gate measures whether the alerts are any good, and none was meant to.

---

## 4. Phase 4 status

Design record only, correctly deferred until after G9. Its five named gaps are all still live:

1. `sql_tier_state` is a hard-coded literal.
2. Code still names the retired WF78 router as the tier authority.
3. `production_scope_member` is 0 for all 300 rows.
4. `promotion_required_before_action` is 1 even for Tier A.
5. Promotion does not require a fresh reference level.

Randall's 2026-09-17 decision to run the forward-scorecard lane **ahead of** Phase 4 is correct and reaffirmed here.

**Recommendation P4-1: widen Phase 4 from "tier plumbing" to "evidence-gated promotion".** A promotion decision card should not render unless the candidate carries all of the following:

- (a) a current structured thesis (section 5.1);
- (b) a fresh reference band inside its age limit, which resolves gap 5;
- (c) earnings-date and regime context;
- (d) once the scorecard exists, an outcome-evidence summary for the setup type.

Demotion should add **sustained outcome underperformance** as a reason alongside evidence impairment.

**Recommendation P4-2: settle the open design choice before any build.** The choice is a whole-canon rebuild versus the per-ticker transactional writer. For a product with a published universe, prefer the per-ticker writer. Subscribers will see names added and removed, and each change needs its own timestamped, reversible record.

---

## 5. Ecosystem audit: thesis, bands, alerts, context, outcomes

### 5.1 Thesis — **weakest layer**

- Thesis lives only in Markdown, in the `Primary Tracked Names` table of `Alert Bands and Invalidation Register.md`, as a one-line "thesis context" per name. There is **no thesis field in SQL**; `reference_levels` has none.
- **14 of the 32 evaluated names have no thesis entry at all:** BKNG, CME, ECL, GE, ITA, KTOS, LIN, META, NFLX, PH, SMCI, TMUS, VMC, WMB. Five of them are **Tier A** (CME, ITA, LIN, META, PH). Another 7 are listed only by name as "secondary monitor names", so only **11 of 32** have any thesis sentence.
- There is no base/bull/bear case, no invalidation *rationale*, no thesis date or freshness, no catalyst list, and no thesis owner-acceptance record. Yet the WF85 output contract and the Alert Trigger Policy both **require** thesis, base/bull/bear, risks and invalidation logic for every material recommendation. **The delivered digest meets none of that contract.**

**Recommendation T-1: a structured thesis record per evaluated ticker.**
- **Location:** a guarded SQL `thesis` table, or content-addressed JSON pinned like the band baseline.
- **Fields:** thesis statement; thesis type (quality compounder, cyclical, AI infrastructure, defensive, and so on); base/bull/bear with drivers; key risks; invalidation *reasons*, both price and fundamental; catalysts; timeframe; conviction; `thesis_as_of`; `thesis_review_due`; `owner_accepted_at`.
- **Governance:** the same gate as bands. Veritas drafts from evidence; Randall accepts. Thesis is Randall's call under USER.md.
- **Freshness:** thesis age gets a policy and decays exactly like quotes do.

**T-2:** fill the 14 missing theses first, the Tier A five first of all. Evaluating a name with no written thesis is incompatible with our own trigger policy.

### 5.2 Bands — **mechanical, uniform, low-confidence**

- Every band comes from one formula (`tmp/g8-yahoo32-reference-level-matrix-20260916.json`):
  - low = 20-day support
  - high = 50-day SMA
  - invalidation = low − 1.5 × ATR20
  - classification = `trend_qualified`
- Source confidence is `low_single_source_yahoo_personal_use`.
- **`reference_confidence` is NULL for all 32 rows in SQL**, even though the matrix carries a confidence label.
- The band is **not thesis-aware**. A compounder and a cyclical get the same geometry, and valuation plays no part.
- At baseline build, 5 of 32 names were already `BELOW_STOP` and 16 were `IN_BAND`.

**Recommendations:**
- **B-1:** populate `reference_confidence` and make the digest print it.
- **B-2:** publish a written band methodology, version it, and stamp the version on every band row. A sellable product has to be able to say how a band was made.
- **B-3:** band methodology v2, per thesis type. For example, compounders anchor on longer-term trend and valuation; cyclicals on regime-aware levels. Validate v2 against the scorecard before adoption, not after.
- **B-4:** keep renewal owner-gated and batch-wise, as now. That discipline is a selling point.

### 5.3 Alerts — **level-triggered status board, 4 of 10 states unimplemented**

- **Selectivity.** Today's digest (2026-09-23T13:50Z) flagged 13 names as `band_entry`, 12 as `no_chase`, 2 as `invalidation_alert`, 4 as `near_band` and 1 as `monitor_only`. That is 31 of 32 names in an actionable-sounding state at once. States are level-based (where price sits right now), not edge-based (what just changed), so the same names repeat every run.
- **No ranking and no conviction.** Nothing orders the 13 band entries. The Unified Objective's claim 2 ("best recommendations for entries") is unmet, exactly as recorded on 09-17.
- **Unimplemented policy states.** `thesis_change`, `catalyst_alert`, `recommendation_review` and `suppressed` are defined in the Alert Trigger Policy and WF85, but have **zero references** in the chain, controller or digest code. Only price-versus-band states can ever fire.
- **Two truth defects in the delivered message** (`scripts/finance_alert_os_digest.py`):
  - **A-D1.** The line *"Fresh intraday alert firing is suppressed; last-completed-session evidence is review-only."* is inserted whenever **any** ticker is `monitor_only`. Today it printed alongside 13 fresh band-entry signals whose controller rows say `alert_fire_eligible: true`. The message contradicts itself.
  - **A-D2.** The dedup `digest_key` hashes a message that contains the quote and controller timestamps, so it can never match and duplicate suppression cannot work. Sends are currently about 2 a day, so the harm is small. The dedup is illusory all the same.
- **Surface disagreement to verify.** The chain-run receipts in `tmp/alerts-chain-runs/` record `alert_state_counts` of `monitor_only: 32` on every run since 09-17. The digest reports the signal mix above. One is probably a pre-fire counter, but a product cannot have two counters that disagree without a documented reason.

**Recommendations:**
- **A-1: edge-triggered alert events.** Emit an alert when a name *changes* state, for example into a band, below invalidation, or on a thesis change. Carry the full contract: why now, thesis, band, invalidation, confidence, context, and horizon. Keep the full state table as a daily or weekly board, not as the alert.
- **A-2: a conviction score and ranking.** The score should be computed from band position, thesis conviction, regime fit, relative strength, catalyst proximity and data confidence. Its weights must be calibrated against the scorecard, not asserted.
- **A-3:** implement the four missing states, starting with `catalyst_alert` and `thesis_change`, whose inputs already exist (5.4).
- **A-4:** fix A-D1 and A-D2 after G9. Both are in a frozen file.
- **A-5:** reconcile or document the receipt-versus-digest counter mismatch.

### 5.4 Context — **evidence is produced daily and consumed by nothing**

The Alert Trigger Policy's required conditions include **regime** and **catalyst**. The inputs exist and refresh daily, but the alert path never reads them:

| Input | Artifact | Freshness | Wired into alerts? |
|---|---|---|---|
| Macro/regime | `tmp/macro-signal-spine.json`, `macro-judgment-draft.json` | 2026-09-23 12:35Z; today's posture `defensive_review_bias` | **No.** The same day's digest sent 13 band entries with no regime qualifier. |
| Earnings dates | `tmp/earnings-calendar.json` | 2026-09-23 04:27Z; 31 of 32 covered (ITA is an ETF) | **No.** The chain, controller and digest contain zero references to earnings or catalysts. |
| Analyst consensus | `tmp/analyst-consensus-current.json` | 2026-09-21; **18 of 32** covered | No (evidence-only by design); 14 names missing |
| Sector leadership / relative strength | WF53/WF57/WF61 exist | n/a | **No** |

**Recommendations:**
- **C-1: the cheapest high-value work in this audit.** Wire regime and earnings proximity into the alert contract as labels and gates:
  - regime changes the evidence burden and the ranking;
  - earnings inside N days produces a `catalyst_alert` and a "binary event" warning.
  - Neither may silently suppress an invalidation alert.
- **C-2:** add relative strength against the sector ETF and against SPY as a ranking input. This covers the Unified Objective's claim 5.
- **C-3:** extend analyst consensus from 18 to 32 through the lane already defined.

### 5.5 Outcomes — **no track record exists for the alerts OS**

- The alerts OS **never writes an outcome or ledger row**. `outcome-ledger-v2.jsonl` (415 rows) froze at the 2026-08-28 pivot, and every one of its 1,660 forward checkpoints is `pending` because of the append-time scoring defect documented in the scorecard lane.
- `recommendation-outcome-grades.jsonl` is still being appended (last write 2026-09-18). Its sources include retired pivot-era capital-deployment paths such as `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`. That is pivot residue writing into the outcome surface.

**Recommendations:**
- **O-1: start the track record now (first post-G9 build).** Every emitted alert event (A-1) is recorded in an append-only, **hash-chained**, timestamped alert ledger. Each record carries: ticker, state, price, band, invalidation, thesis version, band-methodology version, context labels, horizon, and the exact message sent. Nothing may be edited after the fact. This is what makes a future performance claim *verifiable*, and it is the asset that takes months to build.
- **O-2:** build the forward rescorer as specified in the scorecard lane, pointed at the new alert ledger as well as the 415 legacy rows.
  - Score against a **benchmark** (SPY and the sector ETF) at 5, 21 and 63 trading days.
  - Also record **maximum adverse excursion before invalidation**.
  - The four fixes the lane already specifies still apply: append-only rescoring, per-horizon prices, explicit unscoreable states, and a loud empty result.
- **O-3: price retention.** Keep a daily close for every evaluated name going forward so the 2026-06-24 → 2026-08-04 hole cannot recur. This is a retention decision, not a provider decision.
- **O-4:** quarantine the pivot-era feeders of `recommendation-outcome-grades.jsonl` before the rescorer reads it.

### 5.6 Pivot residue (structural hygiene)

- The earnings calendar's watchlist source is `tmp/portfolio-config.json:earnings_date_watchlist`. That file **no longer exists**, so `watchlist_tickers` is empty. The records are still fetched, but the watchlist alerts path is dead.
- The outcome-grade feeder points at retired capital-deployment artifacts (5.5).
- `finance_sql_canon.py` still names `tmp/wf78-auto-tier-routing.json` as tier authority (Phase 4 gap 2).
- **R-1:** a single post-G9 residue sweep, run through the pivot validator, with one owner decision per retirement. Nothing is deleted without approval.

---

## 6. What "very capable" should mean: proposed success measures

The Unified Objective left the success measure undefined; open item 3 there is Randall's decision. The proposal below is aligned to monetization. All of it measures **recommendation quality**, never portfolio performance, and none of it implies Veritas owns positions.

| Measure | Definition | Why a buyer cares |
|---|---|---|
| Excess return after entry alert | Forward return at 5 / 21 / 63 trading days minus the sector ETF and SPY | The headline number every alert service is judged on |
| Hit rate | Share of entry alerts with positive excess return at 21 and 63 days | Simple, checkable |
| Invalidation discipline | Share of invalidation alerts after which price fell further, versus recovered | Proves the "risk" half of the product |
| Max adverse excursion | Worst drawdown from alert price before invalidation or horizon | Honest risk disclosure |
| Selectivity | Entry alerts per week across the universe | Too many alerts is noise; too few is no product |
| Timeliness and reliability | On-time delivery rate, fail-open events (already measured by G8) | Service quality |

Minimum evidence before any external performance claim: an immutable ledger (O-1) with enough resolved 63-day observations to be meaningful. **Recommendation:** at least 6 months of live, unedited history, with methodology and ledger hashes published alongside any figures. Until then, marketing may describe the *process*, not the *results*.

---

## 7. Monetization preconditions (owner decisions, not code)

These sit outside the pipeline, but each one can block revenue on its own. They are listed so they get decided early.

1. **Market-data licence.** The settled source contract is `single_source_yahoo_personal_use`. That decision is **not** reopened here: it stands for the personal system, and the audit does not treat single-sourcing as a quality defect. Selling alerts is a different use than the one approved. Before any paid distribution, confirm what the chosen data source's terms allow for commercial redistribution of derived signals. That may mean a licensed feed *for the product only*. This is a scoping question for Randall and possibly counsel, not a recommendation to change the personal system's provider.
2. **Regulatory posture.** Selling investment alerts or recommendations can fall under investment-adviser regulation. In the US, general, impersonal publications may qualify for the publisher's exclusion; personalised advice generally does not. The current system is explicitly **personalised** (`Investor Profile.md`: Randall's horizon, drawdown tolerance and preferences). **Recommendation:** get a securities-counsel opinion before launch, and design the product as impersonal and general, with standard disclaimers. This is not legal advice.
3. **Separate the personal system from the product.** Keep Randall's `Investor Profile` driving his private digest. The product needs its own impersonal output contract, its own universe definition and its own delivery channel. That also keeps any subscriber surface out of the private workspace.
4. **Authority boundary.** SOUL.md keeps customer and public delivery outside automation authority. Every external step is owner-gated: publishing, subscriber lists, payment, and any new channel. The build can prepare approval-ready artifacts but may not launch anything.
5. **Product form to decide.** For example: a daily or weekly impersonal alert newsletter; a Telegram or Discord channel; or an API/data product. Each has different licensing, regulatory and delivery implications. Decide after the track record exists; design the output contract now so the ledger captures what the product will need.

---

## 8. Recommended roadmap

The sequence respects the standing rule: nothing new starts inside the G8 window, and no frozen surface changes before G9.

**Stage 0: close Phase 3 (now → about 09-26).**
1. Adjudicate G8 Day 4 on evidence (G3-1) and bank Day 5 after post-close.
2. Bring the G9 register current (G3-2), then run the G9 review.
3. Apply the prepared post-G8 controller fix and the pivot-validator seed repair (G3-4).
4. Schedule the baseline renewal owner decision **well before 09-30 18:22 Phoenix** (G3-3).
5. Resolve the "Phase 3" naming collision (G3-5).

**Stage 1: truth and track record (post-G9, about 3 weeks).** This is the top priority.
1. O-1: hash-chained alert ledger wired into the chain.
2. A-1: edge-triggered alert events.
3. A-4 and A-5: digest truth fixes and the counter reconciliation.
4. O-2: forward rescorer with benchmark, including the legacy 415 rows.
5. O-3: price retention. O-4 and R-1: residue quarantine.
6. B-1: populate the confidence field.

**Stage 2: intelligence (about weeks 3–8).**
1. T-1 and T-2: structured thesis for all 32, starting with the Tier A five.
2. C-1: regime and earnings gates, plus the `catalyst_alert` and `thesis_change` states (A-3).
3. C-2: relative strength and sector leadership.
4. A-2: conviction ranking, calibrated on the scorecard.
5. B-2 and B-3: band methodology document, then v2, validated on the scorecard.
6. C-3: analyst consensus 18 → 32.

**Stage 3: scale through Phase 4 (after Stage 2 produces evidence).** Evidence-gated promotion (P4-1) and the per-ticker writer (P4-2). A promotion requires a thesis, a fresh band, context, and scorecard evidence.

**Stage 4: monetization readiness (gated; runs in parallel as decisions only until the track record matures).**
1. Resolve the section 7 items.
2. Draft the impersonal product output contract.
3. Build an internal "subscriber preview" digest from the ledger.
4. Review the track record at 6 months against section 6.
5. Any launch is a separate owner decision.

**Recommended new gate ladder for Stage 1–2 (outcome gates, not reliability gates):**
- O1: ledger is live and hash-chain verified.
- O2: the rescorer scores the legacy rows loudly (non-green on empty).
- O3: the first 30 days of live alert events are recorded with full contract fields.
- O4: 100% of evaluated names carry an accepted, in-date thesis.
- O5: context gates are live, with a replay test showing invalidation alerts are never suppressed.

---

## 9. Open decisions for Randall

1. Accept, amend or reject the success measures in section 6 (this closes Unified Objective open item 3).
2. Approve Stage 1 as the first post-G9 workstream, with the alert ledger (O-1) ahead of Phase 4.
3. Approve the widened Phase 4 scope (P4-1) and choose between whole-canon rebuild and the per-ticker writer (P4-2).
4. Thesis ownership model: Veritas drafts and Randall accepts per name (T-1). Confirm, and set the thesis review cadence.
5. Section 7: decide when to seek the data-licence and securities-counsel answers. Early is cheaper.
6. Baseline renewal timing before 2026-09-30 18:22 Phoenix.

## 10. Stop lines

This audit creates no capital, order, brokerage, account, paper or live-execution authority. It creates no sleeve, holding, position, allocation, weight, sizing, tranche, cash or rebalancing state. It performs no canon, guarded-SQL, thesis, band or tier write, no schedule, cron or config change, no provider-policy change, and no external, customer or public delivery. Recommendations are proposals; none is approved by being written here. Performance figures from any existing artifact are not results and must not be quoted as such.
