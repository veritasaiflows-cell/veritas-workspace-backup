# Capital Deployment Readiness — Phase 1 Audit

**Project:** Capital Deployment Readiness
**Phase:** 1 — Current-stack audit
**Author:** Claude (IC)
**Date:** 2026-05-01
**Status:** Complete — awaiting operator review

---

## 1. What this document is

A systematic audit of every artifact in the deployment readiness stack against the Phase 0 contract. It identifies which artifacts are authoritative for what, where false positives and false negatives originate in the current stack, distinguishes valid trust blocks from substance blocks, and defines the minimum field set for a reliable morning deployment decision.

No canonical notes or scripts were changed. This is a read-and-analyze pass only.

---

## 2. Artifact authority audit

Each artifact audited against: what it claims to be, what it actually is, and what gaps exist.

---

### technical-refresh.json
**Claims:** Per-name price, MA posture, `in_entry_band`, `below_stop`, `earnings_blocked`  
**Status:** Fresh (2026-04-30 data, 0h old, 36h threshold). 17 tracked tickers. No self-declared warnings.  
**Is it authoritative?** For technical posture (price vs. MAs): yes. For `in_entry_band`: mechanically yes, but only as reliable as the entry bands in `portfolio-config.json`. For `earnings_blocked`: **no** — this flag is set from vault watchlist dates, not from `earnings-calendar.json`. Post-print, a stale vault date keeps the flag active.  
**Gap:** This file has no visibility into `workflow_state` or human-layer setup validation. A name can be `in_entry_band: true` and `earnings_blocked: false` and still not be deployable because its setup has not been human-validated.  
**Authority rating:** Authoritative for technical posture. NOT authoritative for deployment readiness.

---

### deployment-check.json
**Claims:** Per-name deployment states (DEPLOYABLE/ALMOST/BLOCKED/BELOW STOP/BENCH/WATCH)  
**Status:** Fresh (2026-04-30, 0h old, 24h threshold). Derives from technical-refresh + market-state.  
**Is it authoritative?** For hard states (BELOW STOP, BLOCKED by active earnings): conditionally yes. For DEPLOYABLE: **no** — it only checks price-vs-band and earnings flags; `workflow_state` is not a gate.  
**Root cause of FP-1:** This file emits `DEPLOYABLE` for GS because GS is `in_entry_band: true`, with no check against `workflow_state`.  
**Root cause of FP-2:** `earnings_blocked: true` for GOOG, MSFT, AMZN because vault watchlist dates (2026-04-29) predate their actual prints. The deployment-check script is using vault dates for the earnings block window, not the live `earnings-calendar.json` dates.  
**Authority rating:** Conditionally authoritative for hard blocks (BELOW STOP). Not authoritative for positive deployment signals. FP-1 and FP-2 both originate here.

---

### trigger-sheet.json
**Claims:** Full per-name deployment assessment combining technical state, macro fit, earnings context, and human-authored thesis/entry fields  
**Status:** Fresh (2026-05-01, 0h old, 24h threshold). Most information-rich single artifact.  
**Is it authoritative?** More so than deployment-check — it adds `workflow_state`, human `why`, `catalyst_blocker`, and note-layer entry text. But `action_state` is still derived mechanically without gating on `workflow_state`.  
**Critical gap:** `workflow_state` is present in the record but NOT used as a gate on `action_state`. GS record: `workflow_state: "WATCH"`, `action_state: "DEPLOYABLE NOW"`. These two fields directly contradict each other in the same record. The human reason text (`why`) says "not yet decision-grade," but the state label says deployable.  
**Secondary gap:** The `earnings_blocked` field flows through from deployment-check without rechecking against `earnings-calendar.json`. GOOG, MSFT, AMZN records all show `earnings_blocked: true` with `next_earnings_date` in July 2026 — a logical contradiction that no downstream artifact flags.  
**Authority rating:** Best available single artifact for morning review, but action_state cannot be trusted without reading `workflow_state` and `why` alongside it.

---

### regime-scores.json
**Claims:** Per-name scores across regime_fit, technical_posture, catalyst_risk, fundamental_conviction  
**Status:** Fresh (2026-04-30, 0h old, 36h threshold).  
**Is it authoritative?** For scoring: yes within the model's parameters. For the regime classification itself: mostly yes — two of three pillars (credit, breadth) are auto-sourced and clean. The policy pillar is manual (CME 404 fallback), but the resulting hold-dominant assessment at 96% is robust and consistent with observable market data.  
**Important finding:** The macro trust degradation from the policy pillar is a **method quality issue, not a directional accuracy issue**. The regime classification `restrictive_pause_benign_broad` is almost certainly correct even under manual sourcing. This distinction matters: the trust-override rules appropriately require a DEGRADED qualifier on macro-gated results, but operators should understand the actual risk is low — the regime is not likely wrong.  
**Gap:** No per-name flag indicating which names are affected by macro trust degradation.  
**Authority rating:** Authoritative for regime classification direction. Method quality is degraded on the policy pillar only.

---

### positioning-ranking.json
**Claims:** Priority-ranked list for morning deployment review  
**Status:** Fresh (2026-05-01, 0h old, 24h threshold).  
**Is it authoritative?** **No** — this is the most misleading artifact in the stack for an operator reading it cold. The priority rank is constructed from regime scores plus bonuses (+3 for in-band DEPLOYABLE, +2 for near-band ALMOST), but without a workflow_state gate. This produces the GS-ranked-above-JPM inversion.  
**Gap 1 (FP-7):** Score bonuses can move a WATCH-state name into the highest priority bucket. GS: score 20, priority rank #1, but workflow_state=WATCH and thesis not decision-grade. JPM: score 20, priority rank #2, workflow_state=ALMOST, thesis intact. The operator sees GS ranked above JPM.  
**Gap 2:** Several names (TLT, KTOS, SLV, SMCI) have `action_state: ""` and `deployment_priority: ""` — blank fields. These are in the Secondary bucket but lack explicit priority numbers. Minor gap — these are not near-term candidates.  
**Authority rating:** Useful for initial sort. Ranking should NOT be used as a decision signal without reading workflow_state and why fields per name. The absolute rank numbers are unreliable for WATCH-state names.

---

### dashboard-validation.json
**Claims:** System-level trust state via warning codes  
**Status:** Fresh (2026-05-01, 0h old, 24h threshold). 8 warnings, 0 critical.  
**Is it authoritative?** Yes — this is the single most authoritative trust-signal artifact in the stack. Warning codes map directly to specific trust failures with affected tickers named.  
**Gap:** Dashboard-validation is a prerequisite input that should gate the morning deployment review, but no downstream artifact checks it. If an operator skips directly to trigger-sheet.json or positioning-ranking.json, they miss the trust qualification entirely.  
**Authority rating:** Authoritative for system trust state. Must be read before trigger-sheet or positioning-ranking.

---

### run-summary-post-close.json
**Claims:** Top-level workflow trust gate with stop_line, fallback_state, and downstream permission flags  
**Status:** Generated at 03:58 UTC 2026-05-01. Key downstream artifacts were regenerated at 06:47 UTC. **Timestamp mismatch.**  
**Is it authoritative?** For the flags it declares: yes — `fallback_state.used = true`, `canonical_note_mutation_allowed = false`, `presentation_allowed = false` are valid and still applicable. But the timestamp predates the 06:47 artifact run by ~2:49 hours. An operator could reasonably ask: does the run-summary cover the latest artifacts?  
**Critical gap 1:** The downstream permission flags (`canonical_note_mutation_allowed = false`, `presentation_allowed = false`) are **not propagated** into any downstream artifact. They exist only in the run-summary header. If an operator reads trigger-sheet.json or positioning-ranking.json without first reading the run-summary, these gates are invisible.  
**Critical gap 2:** The run-summary is generated as part of the post-close chain. But if artifacts are refreshed later (e.g., at 06:47), a new run-summary is NOT generated. The 06:47 artifacts are more current than the 03:58 run-summary, and there is no run-summary for the 06:47 state. The trust gates from 03:58 are still valid (fallback conditions haven't cleared), but this creates an implicit assumption the operator must know.  
**Authority rating:** Authoritative for trust gates, but only if read first. The timestamp gap is a real operational risk.

---

### earnings-calendar.json
**Claims:** Current next earnings dates from yfinance for all tracked tickers  
**Status:** Generated 2026-05-01 06:34, as_of 2026-04-30, stale threshold 7 days.  
**Is it authoritative?** For yfinance-sourced dates: yes. For vault-confirmed dates: no — it explicitly flags 14 discrepancies between yfinance and vault watchlist.  
**Root cause diagnosis:** This is where FP-2 is grounded. The watchlist_alerts section shows that MSFT (vault: Apr 29, yfinance: Jul 29), GOOG (vault: Apr 29, yfinance: Jul 23), and AMZN (vault: Apr 29, yfinance: Jul 30) all have stale vault dates. The scripts that set `earnings_blocked` in `technical-refresh.json` are using vault watchlist dates — not this calendar. Therefore, the April 29 vault date is still activating the earnings block for these three names, even though the print has passed.  
**Critical finding:** This calendar has the correct dates. The deployment chain is not reading them correctly. The fix is in the pipeline, not in the calendar.  
**Authority rating:** Authoritative for current yfinance dates. The watchlist alerts are the most actionable short-term signal in this file.

---

### policy-expectations.json
**Claims:** Fed target range and cut/hold/hike probability distribution  
**Status:** Manual (CME 404 fallback). Target range hardcoded from 2026-04-29 FOMC.  
**Is it authoritative?** Directionally: likely yes (hold at 96% is well-supported by market data). For exact probabilities: no — the single-step ZQ futures approximation is not a full FedWatch meeting tree.  
**Important distinction:** This is a method degradation, not a likely directional error. The probability that the next meeting outcome has materially changed since 2026-04-29 is low given stable macro data. The risk is failure to detect a rapid policy shift, not a current incorrect reading.  
**Authority rating:** Directionally authoritative. Precision degraded. Treat as usable with caution for regime classification; treat as unreliable for precise probability estimates.

---

### macro-regime.json
**Claims:** Regime key and sector fit scores for use by regime_scoring_refresh.py  
**Status:** Fresh (2026-05-01, no warnings).  
**Is it authoritative?** Yes — it accurately reflects the three-pillar composite. Credit (HY 2.82%, IG 0.81%, tightening 20d) and breadth (10/11 sectors above 50DMA) are clean. Policy is manual but directionally robust.  
**The regime classification `restrictive_pause_benign_broad` with selective risk-on bias is well-supported.** The macro gate in the deployment decision, while nominally degraded, is not likely producing incorrect sector-fit scores. The degradation here is process quality, not analytical quality.  
**Authority rating:** Authoritative for regime classification. Policy pillar method is degraded but conclusion is robust.

---

### portfolio-config.json
**Claims:** Machine-readable portfolio spine — tracked universe, entry bands, workflow states, sizing  
**Status:** Stale threshold 168h. Last updated by "Veritas - architecture tightening pass."  
**Is it authoritative?** This is the canonical machine config source. Entry bands in portfolio-config.json are what drive `in_entry_band` throughout the chain. Workflow states here drive `workflow_state` in trigger-sheet.  
**Critical finding:** GS has an entry band (878.71-926.76) in portfolio-config.json, and this band is within-tolerance per band-proposals. Close 923.77 is genuinely within this band. But this band was not human-validated for a deployment decision — it exists in the machine config without a corresponding human review in the trigger sheet. The presence of a band in portfolio-config does not mean a human deployment gate has been passed.  
**Authority rating:** Authoritative for machine configuration. NOT authoritative for deployment readiness — it does not encode human validation status.

---

### band-proposals.json
**Claims:** Proposed updated entry bands from apply_band_update.py  
**Status:** Fresh (2026-05-01, 14 names need review, 7 within tolerance).  
**Within tolerance (bands valid):** JPM, MSFT, LMT, BRK.B, XOM, NVDA, GS  
**Needs review (bands stale):** ETN, GOOG, AMZN, VRT, RTX, CAT, CVX, PLTR, KTOS, SLV, AMD, LNG, TLT, SMCI  
**Authority rating:** The band-proposal workflow is correctly gated — proposals must be reviewed via apply_band_update.py. The gap is that band staleness does not currently downgrade downstream `in_entry_band` signals for affected names. A stale-band name can still show `in_entry_band: true` based on the old band, even if the proposal would move the band materially.

---

### dashboard-acceptance-report.json
**Claims:** 9/9 acceptance tests passed  
**Critical misread risk:** "all_passed: true" does not mean the system is clean or deployment-ready. The acceptance tests verify that the validator is functioning and surfacing degradation correctly — not that the data is healthy. One test has `exec_freshness: "stale"` and still passes. Another has `validation: { critical: 1, warning: 12 }` and passes.  
**Authority rating:** Authoritative for validator function health. NOT authoritative for data quality or deployment readiness. The pass result is routinely misread.

---

## 3. Per-name state audit against Phase 0 contract

### Summary table

| Name | Machine state | Contract state | Type | Root cause |
|---|---|---|---|---|
| **GS** | DEPLOYABLE NOW (#1) | TRUST BLOCKED | **False positive** | FP-1: workflow_state=WATCH not gated in action_state |
| **JPM** | ALMOST DEPLOYABLE | ALMOST DEPLOYABLE ✓ | Correct | — |
| **NVDA** | ALMOST DEPLOYABLE | ALMOST DEPLOYABLE (unconfirmed earnings date) | Correct with qualifier | Earnings date unconfirmed (May 20 vs. May 27 in vault) |
| **VRT** | ALMOST DEPLOYABLE | TRUST BLOCKED | **False positive** | FP-1: workflow_state=WATCH; no human-validated entry |
| **CAT** | ALMOST DEPLOYABLE | WATCH / REVIEW NEEDED | **False positive** | FP-3: T+1 post-earnings, no review note |
| **ETN** | ALMOST DEPLOYABLE | ALMOST DEPLOYABLE + NEAR-EARNINGS CAUTION | Correct but missing qualifier | FP-5: 4 days to earnings, caution label absent |
| **AMZN** | BLOCKED | POST-EARNINGS REVIEW NEEDED | **False negative** | FP-2: stale earnings block (vault date: Apr 29) |
| **GOOG** | BLOCKED | POST-EARNINGS REVIEW NEEDED | **False negative** | FP-2: stale earnings block (vault date: Apr 29) |
| **MSFT** | BLOCKED | POST-EARNINGS REVIEW NEEDED (in band) | **False negative (most consequential)** | FP-2: in entry band but blocked by stale date |
| **LMT** | DO NOT TOUCH | DO NOT TOUCH ✓ | Correct | below_stop; repair mode |
| **RTX** | DO NOT TOUCH | DO NOT TOUCH ✓ | Correct | below_stop; below all MAs |
| **BRK.B** | DO NOT TOUCH | DO NOT TOUCH + NEAR-EARNINGS CAUTION ✓ | Correct with qualifier | Earnings tomorrow; unconfirmed date |
| **XOM** | WATCH | WATCH ✓ | Correct | Post-earnings requalification today |

---

### Name-by-name detail

**GS — False positive (substance block)**  
Machine ranks #1 DEPLOYABLE NOW. Phase 0 contract: TRUST BLOCKED.  
Evidence from trigger-sheet.json record: `workflow_state: "WATCH"`, `why: "not yet decision-grade because explicit entry and stop are still missing"`, `action_state: "DEPLOYABLE NOW"`. These fields contradict each other in the same record — the note layer says not decision-grade, the state label says deployable.  
The band (878.71–926.76) is within tolerance and GS close (923.77) genuinely falls inside it. The technical trigger is real. But no human deployment gate review has been completed for GS. The band in portfolio-config exists without a corresponding human validation in the trigger-sheet note.  
**Blocking reason:** Substance block, not trust degradation. Even with clean system trust, GS would remain WATCH. The machine's failure to gate action_state on workflow_state is the root cause.

---

**JPM — Correctly stated**  
ALMOST DEPLOYABLE confirmed. Thesis intact, workflow_state=ALMOST, no near-earnings risk (74 days), band within tolerance (300–306), close 313.23 (2.4% above band top). Most defensible active candidate.  
Under Phase 0 trust-override rules: system-level fallback_state.used=true requires operator confirmation before any action, but no name-specific block. JPM is the only name that survives full trust-filter review in a constructive state this morning.

---

**NVDA — Correctly stated with unresolved qualifier**  
ALMOST DEPLOYABLE confirmed. Close 199.57 is 0.15% above the band top (band 188.03–199.28) — effectively at the band edge. Earnings May 20 (19 days) — outside the 7-day near-earnings caution window. Catalyst risk score: 4/5 (acceptable).  
Qualifier: The earnings date has been changed in the yfinance feed (vault: May 27 → yfinance: May 20). Under trust-override rules, NVDA cannot be promoted past ALMOST until the May 20 date is confirmed from IR. This does not change NVDA's current ALMOST status, but it would block promotion to DEPLOYABLE NOW if it enters the band.

---

**VRT — False positive (substance block)**  
Machine: ALMOST DEPLOYABLE (#4). Contract: TRUST BLOCKED.  
`workflow_state: "WATCH"`. `why: "not yet decision-grade because explicit entry and stop are still missing"`. The band in portfolio-config was machine-generated (292.22–323.07); close 328.49 is 1.68% above the band top — not even in band. VRT would be ALMOST DEPLOYABLE at best even after workflow_state is resolved. Currently: substance block.

---

**CAT — False positive (post-earnings substance block)**  
Machine: ALMOST DEPLOYABLE. Contract: WATCH / REVIEW NEEDED.  
`days_to_earnings: -1` — CAT reported 2026-04-30. `workflow_state: "WATCH"`. No post-earnings review note exists. Close 890.11 is 7.2% above band top (779.15–830.59 — this band is also stale per band-proposals). CAT is doubly capped: FP-1 (WATCH state) and FP-3 (post-earnings, no review). Even after both are resolved, it would need to pull back significantly to be in band.

---

**ETN — Correctly ALMOST but missing near-earnings qualifier**  
Machine: ALMOST DEPLOYABLE. Contract: ALMOST DEPLOYABLE with NEAR-EARNINGS CAUTION.  
`workflow_state: "ALMOST"` (correctly set — human has validated this setup). Earnings May 5 (4 days) — within the 7-day caution window. Band is stale (ETN in band_staleness warning list; proposal pending in band-proposals.json). The NEAR-EARNINGS CAUTION qualifier is absent from the action_state label. Sizing should be capped at half-tier if any deployment is contemplated — and the stale band makes the current price vs. band comparison unreliable for confirming a trigger.  
**Key technical note:** The stale band has ETN (close 433.01) at 3.0% above the band top (395.59–420.31). The band-proposal appears to be drifting toward a higher level given the extended price. An updated band might actually make ETN further from entry, not closer. Do not treat the current band reading as confirmed.

---

**AMZN, GOOG, MSFT — False negatives (stale earnings block)**  
All three: Machine BLOCKED. Contract: POST-EARNINGS REVIEW NEEDED.  
Root cause is the same for all three. The vault watchlist dates (2026-04-29) were the pre-print dates. Those prints happened on April 29. The earnings-calendar.json now shows updated yfinance dates (AMZN: Jul 30, GOOG: Jul 23, MSFT: Jul 29). But the scripts that set `earnings_blocked` in technical-refresh.json and deployment-check.json are reading vault watchlist dates, not earnings-calendar.json dates. The vault dates haven't been updated post-print.  
This means all three are being held in an active pre-print block that has already passed.

**MSFT is the most consequential false negative:**  
- Close 407.78 falls inside the entry band (389.64–412.56) — `in_entry_band: true`  
- MA posture: above 20d (403.52) and 50d (395.79), below 200d (467.08)  
- Below 200d is a legitimate concern for the technical gate — it's not a clean bullish stack  
- Post-earnings setup review is needed before any ALMOST classification  
- But the current BLOCKED state is based on a stale pre-print block, not on a valid current assessment of the setup  

**GOOG:** Close 381.94 is 10.8% above band top (344.66). Even after earnings block clears, GOOG would be ALMOST DEPLOYABLE at best, not DEPLOYABLE NOW. The false negative matters less for GOOG because the technical state is extended.  

**AMZN:** Close 265.06 is 3.9% above band top (255.09). After block clearance and post-earnings review, AMZN could be in or near ALMOST territory. Medium-priority false negative.

---

**LMT, RTX — Correctly stated**  
Both below stop. DO NOT TOUCH confirmed. No false positive risk.  
Note: LMT earnings date mismatch (vault: Apr 23, yfinance: Jul 21) — the Apr 23 date was the actual print. yfinance now shows the next scheduled earnings. The vault date is stale but the overall DO NOT TOUCH conclusion is independent of this — it's driven by below_stop.

---

**BRK.B — Correctly stated with active near-earnings caution**  
DO NOT TOUCH confirmed. Below all MAs (close 473.60 vs. 20d 475.20 — just below 20d, well below 50d and 200d). Earnings in 1 day (May 2, yfinance — vault had May 4). NEAR-EARNINGS CAUTION applies. Date should be IR-confirmed before any other consideration. Under-stop: no (close 473.60 vs. stop 459.50), but structure is weak.

---

**XOM — Correctly stated**  
WATCH / RESEARCH NEEDED confirmed. Earnings today (days_to_earnings: 0). No entry band defined (in_entry_band: null). This is the requalification gate per the trigger sheet. Post-earnings review required. XOM is correctly handled — the machine and note layer are aligned.

---

## 4. Valid trust blocks vs. appropriate substance blocks

This is the key operator question: which names are blocked by degraded system trust vs. which are blocked by substantive deployment reasons that would exist under clean trust?

### Blocked by system trust degradation only (would be deployable under clean trust)
**None.** No name is currently being prevented from a justified deployment signal solely by system trust degradation.

The fallback_state.used=true and macro_manual_dependency conditions impose a confirmation requirement (operator must explicitly pass over warnings before acting), but they are not causing any valid deployment signal to disappear.

### Blocked by substance (correct regardless of trust state)
All current blocks are substantive:

| Name | Block type | Would block under clean trust? |
|---|---|---|
| GS | No human-validated setup (workflow_state=WATCH) | Yes — substance block |
| VRT | No human-validated setup (workflow_state=WATCH) | Yes — substance block |
| CAT | Post-earnings, no review (T+1) | Yes — substance block |
| LMT | Below stop | Yes — hard block |
| RTX | Below stop | Yes — hard block |
| BRK.B | Weak structure + imminent earnings | Yes — substance block |

### False negatives from stale vault data (inappropriately blocked, unrelated to trust degradation)
The AMZN/GOOG/MSFT stale earnings blocks are **not caused by trust degradation**. They are caused by the vault watchlist dates not being updated after the April 29 prints. The system trust issues (fallback_state, macro manual) are independent of this error. Clearing the fallback_state would NOT fix the stale blocks. The fix requires updating the vault watchlist dates.

**Bottom line on trust override rules:** The Phase 0 trust-override rules are appropriate. They add a confirmation layer but are not producing any incorrect blocks on valid candidates. The most important current errors (stale AMZN/GOOG/MSFT blocks, GS false positive) are data and semantic errors that exist independent of the trust degradation pathway.

---

## 5. Minimum field set for a trustworthy morning deployment decision

### Required artifacts (in read order)

1. **run-summary-post-close.json** — read first, always
   - `stop_line` (binary halt)
   - `fallback_state.used` (DEPLOYABLE NOW ceiling)
   - `downstream.canonical_note_mutation_allowed`
   - `downstream.presentation_allowed`

2. **dashboard-validation.json** — read second
   - `overall` (warning/ok/critical)
   - `warnings[].code` — specific warning type
   - `warnings[].message` — affected tickers per warning type

3. **trigger-sheet.json** — read third, per-name, filtered through steps 1–2
   - Required fields per name:
     - `workflow_state` — semantic gate; filter first
     - `action_state` — only meaningful after reading workflow_state
     - `in_entry_band` — technical trigger; only meaningful if workflow_state ≠ WATCH
     - `below_stop` — hard block flag; always read
     - `earnings_blocked` — read with awareness of FP-2 (stale if vault date predates print)
     - `days_to_earnings` — near-earnings caution check (≤7 days = caution qualifier)
     - `why` — human interpretation; read alongside action_state
     - `catalyst_blocker` — specific catalyst context; read for any near-action name
     - `thesis_status` — substance gate for ALMOST → action

4. **Deployment Trigger Sheet.md** — canonical human layer; final interpretation

### Fields to read with explicit skepticism

| Field | Where | Why skeptical |
|---|---|---|
| `action_state` | trigger-sheet.json | Must read workflow_state alongside; cannot be read cold |
| `priority_rank` | positioning-ranking.json | Misleading for WATCH-state names; FP-7 |
| `earnings_blocked` | technical-refresh, deployment-check | May be stale if vault watchlist date predates print |
| All passed / exec_freshness | dashboard-acceptance-report.json | "All passed" verifies validator function, not data quality |

### Fields that are not required for morning decision (add noise, not signal)

- `positioning-ranking.json` priority scores (redundant and misleading; trigger-sheet workflow_state + action_state tells more)
- Workbook CSV exports (all derived from JSON; operator should read JSON sources)
- `regime_scores.json` directly (regime is adequately summarized in trigger-sheet macro_fit; full scores only needed for secondary review)

---

## 6. Gap list for Phase 2/3

These are the specific gaps that need to be closed to make the morning stack reliable. Listed by severity.

### Critical gaps (actively producing false signals today)

**G-1: workflow_state not gated in action_state (FP-1)**  
Location: deployment-check.py and/or trigger-sheet generation  
Effect: GS shows DEPLOYABLE NOW, VRT shows ALMOST DEPLOYABLE  
Fix type: Add `workflow_state ≠ WATCH` as a required condition before emitting DEPLOYABLE or ALMOST states  

**G-2: Stale earnings block from vault watchlist dates (FP-2)**  
Location: technical-refresh.py earnings_blocked calculation  
Effect: AMZN, GOOG, MSFT show as pre-print BLOCKED when prints already happened; MSFT is most consequential (in band)  
Fix type: Reconcile earnings_blocked against earnings-calendar.json dates, not vault watchlist dates. When calendar shows next_earnings_date > 14 days AND earnings_block_window_unexpected warning fires, clear the block and set a POST-EARNINGS REVIEW flag instead  

**G-3: run-summary trust gates not propagated downstream**  
Location: run-summary-post-close.json  
Effect: `canonical_note_mutation_allowed = false` and `presentation_allowed = false` are invisible in all downstream artifacts  
Fix type: Add a trust_state header block to trigger-sheet.json and positioning-ranking.json that mirrors the run-summary's downstream permission flags  

### High gaps (producing misleading signals or missing qualifiers)

**G-4: Post-earnings state transition not in state machine (FP-3)**  
Location: trigger-sheet generation  
Effect: CAT shows ALMOST DEPLOYABLE on T+1 with no review note  
Fix type: Any name with `days_to_earnings ≤ 0` and no confirmed post-earnings review should be forced to WATCH/REVIEW, not pass to ALMOST based on pre-print posture  

**G-5: NEAR-EARNINGS CAUTION not in action_state label (FP-5)**  
Location: trigger-sheet generation  
Effect: ETN shows ALMOST DEPLOYABLE with no visible caution label; 4 days to earnings  
Fix type: Append NEAR-EARNINGS CAUTION qualifier to action_state string when `days_to_earnings ≤ 7` AND catalyst_risk_score ≤ 3  

**G-6: Score bonuses can move WATCH-state names to highest priority bucket (FP-7)**  
Location: positioning-ranking.py  
Effect: GS ranked #1 above JPM #2  
Fix type: Priority bucket cap — workflow_state=WATCH or thesis_status="under active review" caps name at Secondary bucket regardless of score  

**G-7: run-summary timestamp predates latest artifact refresh**  
Location: run-finance-refresh-chain.py execution order  
Effect: The 06:47 UTC artifact refresh has no corresponding run-summary; trust gates from 03:58 run-summary are applied to 06:47 artifacts without being regenerated  
Fix type: run-summary should be the last artifact generated in any chain run, not the first  

### Medium gaps (degraded method quality but likely not causing incorrect conclusions today)

**G-8: Macro trust qualifier not per-name in trigger-sheet**  
Location: trigger-sheet.json records  
Effect: No visible indicator per name that the macro gate was evaluated under degraded policy data  
Fix type: Add `macro_gate_trust: "degraded" | "clean"` field per trigger-sheet record when macro_manual_dependency warning is active  

**G-9: Band staleness not visible as a per-name flag in downstream artifacts**  
Location: trigger-sheet.json, deployment-check.json  
Effect: In_entry_band result is computed against potentially stale bands; no warning per name  
Fix type: Add `band_stale: true/false` per record based on whether the name appears in dashboard-validation band_staleness scope  

**G-10: Acceptance report "all_passed" is consistently misreadable**  
Location: dashboard-acceptance-report.json  
Effect: Operator reads "all passed" as "system is healthy" when it means "validator is functioning"  
Fix type: Rename field to `validator_functioning: true` and add `data_quality_grade` separate from pass/fail  

---

## 7. Recommended authoritative sources for morning deployment decision stack

Based on the audit, the authoritative sources and their specific roles:

| Decision needed | Authoritative source | Why |
|---|---|---|
| Is the system in stop-line? | run-summary-post-close.json → stop_line | Only place this is declared |
| Can DEPLOYABLE NOW be acted on? | run-summary → fallback_state.used | Only place downstream permissions are declared |
| What trust warnings are active? | dashboard-validation.json → warnings[].code | Most complete enumeration of active trust issues |
| What is each name's semantic readiness? | trigger-sheet.json → workflow_state + action_state + why | Only artifact combining machine state with human semantics |
| What is the priority order? | trigger-sheet.json filtered by workflow_state, NOT positioning-ranking.json priority_rank | Positioning-ranking rank is unreliable for WATCH-state names |
| What are the catalyst timing risks? | trigger-sheet.json → days_to_earnings + catalyst_blocker + earnings_blocked (verified against earnings-calendar.json) | Trigger-sheet has human context; calendar has verified dates |
| What is the macro regime? | macro-regime.json → regime.key + pillars[credit/breadth status] | Policy pillar is degraded; credit and breadth are clean |
| What is the canonical deployment decision? | Deployment Trigger Sheet.md | Human canonical layer; machine outputs inform it |
| What is the portfolio posture constraint? | Portfolio Snapshot.md → sector allocation flags | Only place where concentration caps are enforced |

### Sources that are NOT authoritative for morning deployment decisions

| Source | Why not authoritative |
|---|---|
| positioning-ranking.json priority rank | WATCH-state names can rank above ALMOST-state names (FP-7) |
| deployment-check.json action states | Does not gate on workflow_state (FP-1); uses vault dates for earnings_blocked (FP-2) |
| dashboard-acceptance-report.json | Verifies validator function, not data quality |
| workbook CSV exports | Derived from JSON; adds no new information; not suitable for decision-grade use |

---

## 8. Phase 2 recommendation

Phase 2 (Morning decision surface design) should specify exactly what fields appear on the morning deployment view, in what order, for each name — and how each of the ten gaps above is handled at the surface level.

The minimum effective morning surface needs:

1. System trust header (from run-summary + dashboard-validation) — shown before any name
2. Per-name: workflow_state → action_state (gated on workflow_state) → in_entry_band → below_stop → days_to_earnings → near-earnings flag → macro_gate_trust → band_stale → earnings_date_verified
3. A state transition note for names where the audit found stale conditions (AMZN/GOOG/MSFT: POST-EARNINGS REVIEW; CAT: POST-EARNINGS REVIEW; GS: NEEDS THESIS REVIEW)
4. Explicit "no action" summary when fallback_state.used=true

The gaps that need script-level changes (G-1 through G-7) should be scoped in Phase 3. Phase 2 should design the target surface shape independent of implementation complexity, so Phase 3 has a clear target.

---

*Phase 1 complete.*  
*All findings are read-only. No files changed except this audit document.*  
*Proceed to Phase 2 upon operator confirmation.*
