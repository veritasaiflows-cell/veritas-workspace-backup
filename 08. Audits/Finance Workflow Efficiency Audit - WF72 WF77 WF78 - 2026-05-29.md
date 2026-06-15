# Finance Workflow Efficiency Audit - WF72, WF77, WF78 - 2026-05-29

**Auditor:** Veritas main session (Claude Opus 4.8)
**Run window:** 2026-05-29 20:58-22:15 MST
**Scope:** Efficiency and decision-value review of the three coupled finance-engine workflows — WF72 (SQL/canon efficiency), WF77 (coverage + question router / answer engine), WF78 (500-ticker scaleout). Triggered by Randall's workspace efficiency assessment and follow-on recommendation requests.
**Posture:** Review-only. No mutations performed. No portfolio, canon, trade/account, paper/live, config/auth/channel/runtime, or owner-approval state changed. Validator/index reads only.

---

## 1. Executive Summary

- **One-line finding:** All three workflows are disciplined and safe, but they share one root inefficiency — **effort is flowing to the provable/buildable surface instead of the decision-critical one.** WF72 and WF78 build infrastructure *ahead of demand*; WF77 has real demand but polishes *structure over freshness*.
- **Net new decision-grade output of WF72 + WF78 since they opened: zero.** WF72's SQL layer serves **0 effective answer rows**; WF78's answerable universe is **still 42 tickers**.
- **WF77 is the only one of the three that produces genuine decision value**, and its architecture is sound — but its single most decision-critical data family (`price_band_stop`) is **stale across nearly the entire 42-name universe**, forcing every answer to self-downgrade to "fresh quote required."
- **The safety/authority discipline across all three is correct and should be preserved.** This audit is about timing, sequencing, and where effort lands — not about loosening boundaries.
- **Recommended posture:** Freeze WF78 expansion at "mechanism proven." Demote WF72 SQL-first ambition to routing/index-only and rip out the recurring readiness-gate churn. Redirect WF77 effort from schema enrichment to a working price-refresh pipeline.

---

## 2. Workspace Efficiency Context

Evidence gathered 2026-05-29 ~21:00 MST:

| Metric | Value | Read |
|---|---|---|
| Last git commit | 2026-05-09 (20 days) | Danger — checkpoint cadence is 72h per AGENTS.md |
| Uncommitted changes | 1,665 (1,357 new, 285 modified, 23 deleted) | Danger — includes deletions of canonical files |
| Commits last 14 days | 0 | Danger |
| Distinct workflows (WF6-WF78) | 78 | Heavy framework footprint |
| Project-continuity notes | 109 | Heavy |
| Playbook .md files | 227 | Heavy |
| tmp/ files | 2,885 (118 MB) | Bloated |
| otel-collector .pb dumps in tmp | 981 | Garbage accumulation |
| Skills | 33 | OK |

This context matters because the three audited workflows are the largest active consumers of build effort, and the workspace-level signal (much motion, self-referential framework grooming, no recent checkpoint) shows up concentrated inside them.

---

## 3. WF72 - Financial OS Efficiency / SQL-canon transition

### Evidence
- SQL cache holds exactly **265 metadata rows** (13 proof/freshness/lifecycle + 252 WF72 entry/stop reference rows across 42 tickers).
- `tmp/sql-canon-retail-grade-readiness.json` = **blocked**: 265 rows mapped, **0 SQL-effective retail rows**, global SQL-read guard blocked.
- All 252 entry/stop rows are `fallback-required` (Markdown still answers). The 13 proof/freshness rows are stale or unsafe.
- Root blocker is **data provenance, not code**: reference levels lack `owner_source_path`, `source_sha256`, `source_timestamp`, and verified `price_high/low/invalidation` (blocking keys span AMD, AMZN, BKNG, BRK.B, CAT, CME, CVX, ECL, ETN, GE, GOOG, GS, …).
- 2026-05-29 alone added: pre-Phase5 hardening gate, retail validation bundle, Phases 1-4 gate, 500 design gate, flattening plan, three hardening audits. This is proof infrastructure layered on top of a layer that proves it cannot be trusted yet.

### Assessment
The "0 SQL-effective rows" state has persisted across many sessions. SQL-first canon would replace a layer (compact JSON packets + Markdown owner notes) that **already works and is already fast**, so the runtime efficiency gain is marginal. Lane A's cost (capture verifiable provenance for 42 tickers' bands/stops, then re-hash/re-validate on every band change) is a recurring maintenance tax. The consumer that would justify that cost — the retail SaaS at scale — is externally gate-blocked (privacy/source/counsel).

### Recommendation — demote, do not keep grooming
1. **Stop adding gates/validators/audit packets.** The proof scaffolding is over-built relative to what it protects.
2. **Declare SQL routing/index/cache-only.** Stop the "trending toward canon" framing; keep Markdown + JSON packets as the answer path.
3. **Rip out the recurring readiness-gate churn** from the finance chains — the per-chain "is SQL retail-grade yet?" check returns "blocked / 0 effective rows" every time. That third step is where the actual efficiency lands; without it, "demote" is cosmetic.
4. **Keep SQL as routing/index/FTS** — that genuinely earns its keep (what exists, what's stale, where proof lives).

**Why B (demote) over A (make SQL real):** B is more efficient on *effort and attention*, neutral on *answer speed*. A is the right *eventual* move, but only once retail SaaS unblocks and pulls for SQL-grade access. Doing A now is premature optimization — provenance captured now goes stale before the consumer exists, and the consumer will likely reshape the data requirements. B is reversible: reopen A with real requirements in hand when SaaS unblocks.

---

## 4. WF77 - Finance Intelligence Coverage and Question Router

### Evidence
- 42/42 enriched ticker cards (schema v2, ~30 fields, 24 data families). QA grew V1 -> V1.4a in ~2 days: 33 -> 37 -> 43 -> 62 -> 180 -> 306 -> 390 checks.
- Coverage registry `tmp/finance-data-coverage-current.json` generated `2026-05-28T12:58:48Z` (~33h stale at audit time).
- **`price_band_stop` is stale across nearly all 42 tickers** (stale_by_family list: AMD, AMZN, BKNG, BRK.B, CAT, CME, CVX, ECL, ETN, GE, GOOG, GS, ITA, JPM, KTOS, LIN, LLY, LMT, LNG, META, MSFT, NFLX, NVDA, PAVE, PH, PLTR, RTX, SLV, SMCI, TLT, TMUS, …).
- Every card carries `fresh_quote_required: True` and `staleness_note: "Reference price/band from prepared packet; refresh before final use."`
- 20 of 24 data families have gaps somewhere. `competitive_moat` is permanently `not_yet_structured_source_open_required` (structural placeholder, never populated).
- Analyst layer is yfinance-derived (unofficial), 31/42 sourced, with an 18-name Tier A/B manual-review queue.

### Assessment
WF77 is the real decision-value engine and its architecture is correct (question class -> coverage registry -> ticker card -> answer contract -> source-open). But the card schema kept growing while the 3-4 fields that actually drive a decision — current price vs written band vs stop — are stale universe-wide. A 30-field card whose price is 33h old and flagged "refresh before use" is not more useful than a 5-field card with a fresh price.

**Efficiency killer:** a router that always returns "fresh quote required, refresh before use" does not save time — the user still fetches the quote manually. The speed win is only realized if freshness is wired in.

### Recommendation — fix freshness, freeze schema
1. **Fix the freshness pipeline, not the schema.** Wire a reliable price refresh into the card build so `latest_known_price` and band-position are genuinely current, not "reference from prepared packet." This is the whole game.
2. **Freeze the card schema.** 24 families / 390 QA checks is past the point of returns. Add a field only if it is both populatable with real data AND decision-relevant.
3. **Kill or fill placeholder fields.** `competitive_moat` should be populated from real research or dropped — an always-empty "source-open required" field dilutes every card.
4. **Make the analyst layer honest.** Either commit to the weekly manual review for the 18 Tier A/B names that matter, or relabel the field "unofficial context only" and stop implying coverage.

### What is genuinely good (keep)
- The decision-support architecture is correct and worth investment.
- Authority discipline is clean (review-only, no approval inference).
- Resolver hardening (PLTR null-price catch) shows the QA earns its keep.
- 42/42 structured coverage is a real asset — the frame is right, the fill is stale.

---

## 5. WF78 - 500-ticker scaleout

### Evidence
- 25-name pilot imported into **isolated** SQL tables; production answer path **unchanged at 42**.
- `tmp/wf78-100-ticker-candidate-scope-packet.json` is clean: 58 new candidates, **all Tier C, all `decision_grade_eligible: false`**, no import performed.
- Extensive gate stack: pilot contract gate, provider/runtime probe (11/11 and 25/25 fixtures ok), live-pilot import gate, 500-ticker design gate, Phases 1-4 gate — all validate.

### Assessment
The packet is not wrong; the *demand* is absent. A 100-ticker approval would add 58 non-decision-grade monitor rows plus provider load and **zero answer-quality gain**, on top of a 42-name SQL substrate that is still 0-effective (WF72). With $10k planning capital and a 42-name decision universe, 500 tickers solves a problem that does not yet exist.

WF78 cannot responsibly scale ticker *count* while WF72's SQL layer serves 0 trusted rows for the *existing* 42. Running both in parallel is why they spin. **WF78 is downstream of WF72.**

### Recommendation — freeze at "mechanism proven"
1. **Do not approve the 100-ticker import.** Demand is absent.
2. **Declare WF78 deliverable complete at the proven-mechanism stage** — tier-aware schema + isolated pilot import + provider/runtime proof all exist and validate. That is a real, reusable asset. Lock it.
3. **Resume expansion only on a concrete trigger** — retail SaaS goes live, or a specific new name is genuinely wanted.

---

## 6. Connecting Insight and Sequencing

- **Root inefficiency shared by all three:** effort flows to the provable/buildable surface, not the decision-critical one.
- **Sequencing:** Fix or freeze WF72 first (it is the substrate). WF78 is downstream of WF72 and should freeze. WF77 deserves continued *investment*, but redirected to freshness.
- **Highest-leverage single move:** a working daily/intraday price-refresh path for WF77. That one fix converts dozens of "fresh quote required" downgrades into completed answers — the actual efficiency payoff across the whole finance engine.

---

## 7. Decision Asks for Randall

1. **WF72:** Approve demote-to-index (lane B), including removing the recurring readiness-gate churn from finance chains? (Recommended.) Or pursue lane A (remediate-the-42 provenance)?
2. **WF78:** Approve freeze at proven-mechanism and reject the 100-ticker import for now? (Recommended.)
3. **WF77:** Approve redirecting effort to the price-refresh pipeline and freezing the card schema? (Recommended.) Next concrete step would be tracing where `latest_known_price` resolves from and why it is stale.
4. **Workspace hygiene (out of audit scope but urgent):** Commit the 20-day, 1,665-change backlog so the deletions/renames are recoverable.

---

## 8. Boundaries Preserved

- No portfolio, canon, sizing, cash, or risk-rule mutation.
- No trade/account/brokerage/money-movement action.
- No paper/live execution.
- No config/auth/channel/service/runtime change.
- No owner-approval inference.
- No SQL writes or SQL-canon expansion.
- This audit is a review/proof artifact only; it is not canon, approval, apply authority, or execution authority.
