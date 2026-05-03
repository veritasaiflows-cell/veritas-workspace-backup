# scripts/operators

Operator-only or maintenance-oriented script implementations live here when they are not part of the default finance refresh chain.

Compatibility rule:
- user-facing CLI entrypoints remain available at `scripts/<name>.py`
- the root files are thin wrappers so existing docs, habits, and prompts do not break
- if a script becomes chain-active later, do not move it casually; prove the caller map first

Current operator-boundary implementations:
- `apply_band_update.py`
- `band_note_sync.py`
- `daily_note_dedupe.py`
- `post_earnings_scorecard.py`
- `test_universe.py`

Intentionally left in `scripts/` root:
- `call_log_sync.py` because the Sunday chain calls it directly
- `workbook_template.py` because `run_finance_refresh_chain.py --build-workbook` can call it as a manual chain tail
- the equity report scripts because they remain active documented operator entrypoints, not dead wrappers
