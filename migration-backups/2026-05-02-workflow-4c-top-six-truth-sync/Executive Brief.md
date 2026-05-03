# Executive Brief

## Role

This is the high-level derived operating view for Randall and Veritas.

It should answer, fast:
- what matters now
- what the current operating focus is
- what the next important move is
- whether trust or freshness is degraded

Boundary:
- this is an orientation surface, not a canonical source of truth
- do not restate full deployment logic, portfolio tables, or weekly catalyst detail
- if a script-backed input is partial, stale, missing, manual, or unconfirmed, summarize that degradation instead of implying clean confidence

Canonical owners:
- portfolio posture: [[03. Portfolio/Portfolio Snapshot]]
- risk posture: [[07. Risk/Risk Rules]]
- weekly operating stance: [[05. Intelligence/Weekly Positioning Review]]
- event timing: [[05. Intelligence/Event Calendar]]

## Current focus

- operate the finance-first system as a live research and portfolio-review stack, not as a build project
- keep the note layer aligned with the script-backed evidence layer through the FOMC + earnings cluster (April 29 – May 5)
- preserve capital by favoring disciplined conditional adds over forcing entries into extended or blocked names

## What matters now

1. **FOMC April 29 + megacap earnings April 29 (after close)** — GOOG, MSFT, AMZN report into the Fed decision day. This is the densest single-day catalyst window of the cycle.
2. **JPM is still the cleanest active conditional add** — closest to band (+1.8% extended), no near-term earnings risk. **GS is the second-closest** (+1.2% extended) but newly added — verify thesis depth before treating as core.
3. **ETN is the highest-quality chart** but earnings May 5 caps any pre-print sizing. Pullback into 386–410 is the only entry.
4. **NVDA, AMZN, VRT, CAT, MSFT, GOOG remain pullback-only or earnings-blocked**. None are deployable at current prices.
5. **Repair / do-not-touch list grew this week:** RTX entered below-stop (joining LMT). BRK.B exited its prior band. XOM still awaits May 1 earnings as the requalification gate.
6. **Bands refreshed 2026-04-28** for ETN, GOOG, MSFT, NVDA, AMZN, VRT, RTX, CAT. AMZN, VRT, CAT bands formally defined for the first time.

## Current next move

- Stand down into the April 29 catalyst day — do not force entries into the megacap earnings cluster
- Watch JPM and GS for any pullback into their respective bands (300–306 for JPM, 879–927 for GS)
- Run `post_earnings_prep.py` after each earnings print and re-evaluate band/state from data
- Keep RTX and LMT explicitly in repair mode — neither is a fresh opportunity

## Trust and operating rule

- capital preservation comes first
- thesis first, evidence second
- dashboards summarize, canonical notes decide
- good businesses do not override bad timing
- avoid hype, drift, and fake certainty

## Active dashboard warnings (4)

- **band_drift:** 11 names extended >5% above the latest MA-anchored band midpoint — operationally correct (real signal, not staleness)
- **timing_sensitive_earnings_dates:** date changes in NVDA (May 27 → May 20), BRK.B (May 4 → May 2), LMT (April 23 → July 21) need direct IR confirmation
- **earnings_date_in_past:** VRT April 22 elapsed; calendar needs roll-forward
- **macro_manual_dependency:** Fed target hardcoded (3.5–3.75%), FedWatch unwired

## Navigation

Read in this order:
1. [[01. Dashboards/Executive Brief]]
2. [[01. Dashboards/Pre-Market Snapshot]] (auto-generated each morning)
3. [[01. Dashboards/Daily Executive Summary]] (auto-generated each post-close)
4. [[01. Dashboards/This Week]]
5. [[01. Dashboards/Next Actions]]
6. [[05. Intelligence/Weekly Intelligence Brief]]
7. [[02. Markets/Macro Regime Dashboard]]
8. [[03. Portfolio/Technical Entry and Invalidation Sheet]]
9. [[03. Portfolio/Portfolio Snapshot]]

## References

- [[02. Markets/Macro Regime Dashboard]]
- [[02. Markets/Watchlist]]
- [[02. Markets/Weekly Macro Snapshot]] (auto-generated each Sunday)
- [[03. Portfolio/Portfolio Snapshot]]
- [[05. Intelligence/Weekly Positioning Review]]
- [[05. Intelligence/Weekly Intelligence Brief]]
- [[07. Risk/Risk Rules]]
- `scripts/README.md`

## Last updated

- 2026-04-28 — refreshed against 2026-04-27 close. Updated to reflect: CAT/GS/VRT now ALMOST DEPLOYABLE (no longer benched); RTX below-stop (joined LMT in repair); BRK.B exited band; bands refreshed for 8 names; new auto-generated dashboard surfaces wired in.
