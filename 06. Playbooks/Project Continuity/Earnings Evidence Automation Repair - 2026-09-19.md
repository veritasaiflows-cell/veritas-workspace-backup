# Earnings Evidence Automation Repair — 2026-09-19

## Objective
Restore a bounded, review-only earnings evidence and post-report reconciliation path without reviving the retired `tmp/portfolio-config.json` surface or changing any schedule, delivery, finance canon, portfolio state, capital, account, or execution state.

## Current State
- **Code repair complete; live evidence remains stale until a separately authorized refresh.**
- The former zero-ticker false green condition now falls back to the 31-ticker official-capture registry.
- The active alert controller is included as review context for post-earnings alert reconciliation.

## Changed
- `scripts/earnings_rollforward_guard.py`: uses the bounded official-capture scope when legacy portfolio config is absent and records the scope source.
- `scripts/earnings_date_source_confidence.py`: preserves the 31-ticker review scope, uses maintained company IR URLs for primary-source probes, and never upgrades a provider estimate without matching primary evidence.
- `scripts/fundamental_ir_reconciliation_packets.py`: rebuilds review packets over the official-capture scope rather than producing an empty success.
- `scripts/earnings_calendar_enrichment.py`: watchlist/config closeouts now require `--apply-watchlist-closeouts`; normal collection is non-mutating.
- `scripts/post_earnings_prep.py` and `scripts/post_earnings_note_targets.py`: tolerate the retired deployment-check input, emit near-earnings and post-print review queues, attach current alert-controller context, and exclude `03. Portfolio/` targets.

## Proof
- `python -m pytest scripts\test_earnings_calendar_enrichment_shard.py -q` → 4 passed.
- `python -B scripts\test_earnings_date_source_confidence.py --write-md` → passed.
- `python -B scripts\test_earnings_rollforward_guard.py` → passed.
- `python -B scripts\test_post_earnings_prep.py` → passed.
- Scope checks confirm 31 official-capture tickers for roll-forward and reconciliation fallback paths.

## Outstanding / Next Action
1. **Do not add a schedule without Randall’s approval.** Recommendation: a single weekday review-only earnings run after the existing morning alert refresh, with no delivery and a fail-closed validation gate.
2. After a market-data/source refresh window is authorized, run the bounded official IR/SEC capture and reconciliation sequence, inspect the resulting review queue, and keep any canon or alert change owner-gated.

## Rollback
Use `git restore --` only on the changed earnings scripts, tests, and this note. No configuration, scheduler, finance-canon, portfolio, or external artifacts were changed by this repair.

## Stop Line
This repair creates evidence and review queues only. It does not authorize or perform portfolio/canon mutation, alert-canon changes, schedule changes, capital deployment, orders, accounts, or external delivery.
