# Recommendation Readiness Before Ledger - 2026-09-23

Owner: Main. Randall, Telegram 2026-09-23 16:58 MST: narrow recommendations on thesis, macro, bands and other data **before** the alert-event ledger starts, so the ledger does not open on legacy behaviour. Approved 17:05 MST ("Proceed with recommendations"), including: minimum band width = one ATR20 (widen, record, keep the name); Tier A five theses drafted first.

Status: in progress. Grants no canon, capital, order, account, execution, delivery, or schedule authority. Ledger wiring stays off until the gate below is met. Ledger design: `Alert Event Ledger Design - 2026-09-23.md`.

## Recommendation funnel

1. **Eligible**: accepted thesis (`state/finance/thesis/<T>.json`, status accepted, within `review_due`) + fresh band + non-null `reference_confidence`. Otherwise monitor-only (invalidation and data-quality alerts still fire).
2. **Band quality**: band width ≥ 1×ATR20 (floor-widened if needed, flagged) and invalidation strictly below band low (D9-A/C).
3. **Context**: macro posture raises the evidence bar (defensive ⇒ high conviction only); earnings within 10 days ⇒ binary-event flag and `catalyst_alert`; relative strength vs SPY and sector ETF feeds rank. Context never suppresses an invalidation alert.
4. **Rank**: transparent score (band position, conviction, regime fit, relative strength, catalyst proximity, data confidence), labelled uncalibrated until the ledger scorer exists. Top 3–5 become recommendation-review candidates; the rest stay on the board.

## Checklist and state

| # | Item | State (2026-09-23 evening) |
|---|---|---|
| 1 | Baseline renewal on D9-A formula + ATR20 width floor (`mech-v3-floor-atr20`) | Generator done (floor, flag, confidence, version stamp; 19 tests pass). Recompute blocked by Yahoo null closes on 20/32 names; retry after next close. Owner approves numbers. Due before ~2026-09-30 18:22 PHX. |
| 2 | `reference_confidence` populated and printed | Generator emits `data_confidence_v1` (0.5 single-source cap, −0.15 floor-widened, −0.10 not trend-qualified; provisional). **Open:** `g6_yahoo32_sql_apply.py` preserves the existing SQL confidence (NULL) and does not write proposed confidence; needs a tested change to the gated apply (SET list, pin projection, rollback) before renewal. Digest print pending. |
| 3 | Structured thesis records | Schema + rules in `state/finance/thesis/`. Tier A drafts (CME, ITA, LIN, META, PH) next, for owner acceptance. |
| 4 | Macro + earnings gates | Not started. |
| 5 | Relative strength vs SPY/sector | Not started. |
| 6 | Ranking + top-N | Not started; weights need owner approval. |
| 7 | Digest truth fixes A-D1, A-D2 | **Done.** Suppressed line only when nothing is fire-eligible; dedup key hashes content, not timestamps. 31 tests pass; production untouched. |
| 8 | Pivot-era outcome feeder quarantine (O-4) | Recommendation outcome grader retired 2026-09-25 (see update below); other pivot-era feeders still per-item owner approval. |

## Ledger start gate

Items 1, 2, 4, 6, 7 done and the Tier A five theses accepted. The genesis record stamps `band_methodology_version`, the thesis-record schema, and the funnel version.

## Update 2026-09-23 ~18:30 MST

- Item 1: nightly Yahoo gap repair live (cron 202a5801, 19:30 PHX weekdays). Renewal matrix on the 09-22 close computes 32/32 (`tmp/renewal-matrix-20260922close-v3.json`); dry run against live canon: 32 triples, drift 0, no mutation, pin preview `alert-reference-levels-v1-28bf68b2...`. Review table `tmp/renewal-review-table-20260923.md`. **Awaiting Randall's numeric approval.**
- Item 2: `g6_yahoo32_sql_apply.py` now writes proposed `reference_confidence` to SQL and the successor pin (range-checked 0-1), verified post-apply; rollback byte-exact. 110/110 checks. Digest print still pending.
- Item 3: Tier A drafts CME, ITA, LIN, META, PH in `state/finance/thesis/` (status draft); `scripts/thesis_record_validator.py` + 5 tests; all valid, none eligible. **Awaiting Randall's acceptance.**

## Update 2026-09-23 ~19:00 MST

- Item 1 **done**: renewal applied 18:13 MST (pin `e4fc0165...`, expiry ~2026-10-06 18:13 PHX). Weekly renewal under the Option B standing gate: cron `aa6b52ee` (Sat 09:00 PHX) + Main review wake `1d762d96` (Sat 09:30).
- Item 2 **done** except the digest print of confidence.
- Item 3 **done** for Tier A: CME, ITA (v2), LIN, META, PH (v2) accepted 18:17 MST.
- Remaining before the ledger starts: items 4 (macro/earnings gates), 6 (ranking, weights need approval), confidence in the digest.

## Update 2026-09-23 ~21:05 MST

- Item 4 **done**: macro posture and earnings gates in `scripts/recommendation_funnel.py`.
- Item 5 **done**: relative strength vs SPY and sector ETF (63 sessions) in the funnel.
- Item 6 **done**: ranking `funnel-v1`, weights owner-approved (uncalibrated); defensive rule admits medium conviction when the thesis favors the posture. Refreshed weekly (Sat 08:00) and surfaced by the Sat 09:30 Main review.
- Remaining before ledger genesis: confidence line in the digest, and one live funnel run on the renewed controller (first 06:05 run on 2026-09-24). Then wire the ledger (owner go-ahead on the wiring diff).

## Update 2026-09-23 ~22:00 MST

- Item 2 **done**: digest prints a data-confidence line (median, lowest four, missing). Known display gap: the controller's `confidence_label()` still assumes a 1-5 scale, so every row labels "low" on 0-1 values (owner decision).
- Live funnel run on the renewed controller: scheduled check 2026-09-24 07:00 PHX (automation `d6a06375`).
- Ledger wiring diff ready for owner review: `tmp/ledger-wiring-20260923/ledger-wiring.diff`. Checkpoint commit `2e083ea9`.

## Update 2026-09-25 ~17:45 MST

- Item 8, first feeder: **recommendation outcome grading retired** (Randall 17:36 MST: "Yes, proceed with recommendations"). Its inputs stopped with the pivot (WF55 recommendation rows and `tmp/post-close-final-quote-ledger.json` end 2026-08-29), so it graded 0 of 415 rows while reporting ok. It was removed from the WF88 runner (45 -> 44 steps). `wf88_wiki_refresh_cron_gate.py` now checks the frozen `data/state-history/recommendation-outcome-grades.jsonl` directly (2,967 rows). The WF88 contract no longer expects the grading receipts, and the script carries a RETIRED header. Tests: runner and gate 59 pass. Checks: validator 57/0 drift, spine 0 blocked, control escalation 0.
- **Successor: alert-ledger outcome scorer**, which calibrates the `funnel-v1` weights, tests the ATR20 band floor, and rates alert types. It uses nightly Yahoo price snapshots for later closes, so no new quote job is needed. It is scheduled for scoping once events mature: a one-shot reminder on 2026-10-15 09:00 PHX (automation `3df080bc`, contract `state/cron-contracts/finance-alert-ledger-scorer-readiness-check.json`). Building it needs Randall's approval of the design.
