# Workflow 13 Script and Tmp Hygiene Hardening QA Audit - 2026-05-03

## Verdict
- Workflow 13 is honestly complete.
- The pass stayed bounded: it improved script hygiene and tmp governance without pretending to solve the separate structural cleanup work queued under Workflow 14.

## What landed
- `equity_visual_report.py`, `equity_pdf_report.py`, and `equity_ppt_report.py` now derive the live workspace root instead of using the stale `Veritas2.0` hardcoded path.
- `scripts/validate_portfolio_config.py` now writes fail-soft machine validation to `tmp/portfolio-config-validation.json`.
- `scripts/tmp_cleanup.py` now provides a report-first archive utility, with explicit apply mode and Sunday `--cleanup` hook.
- `scripts/run_finance_refresh_chain.py` now wires the portfolio-config validator early and the tmp cleanup tail only when explicitly requested.
- `scripts/run_summary_refresh.py` now handles the narrow post-summary tail edge case more honestly instead of leaving successful runs stranded as misleading `running` state.
- `06. Playbooks/Workspace Structure Protocol.md` now includes an explicit `tmp/` retention policy.

## Verification evidence
- `python scripts/equity_visual_report.py --help`
- `python scripts/equity_pdf_report.py --help`
- `python scripts/equity_ppt_report.py --help`
- `python scripts/validate_portfolio_config.py` -> `status: ok`, `warning: 0`, `checked_tickers: 22`
- `python scripts/tmp_cleanup.py --dry-run` -> `eligible_count: 0`, `moved_count: 0`
- `python scripts/run_finance_refresh_chain.py post-close` -> completed successfully
- `python scripts/run_finance_refresh_chain.py sunday --cleanup` -> completed successfully
- `tmp/run-summary-post-close.json` -> `execution.chain_status: ok`
- `tmp/run-summary-sunday.json` -> `execution.chain_status: ok`
- `tmp/dashboard-validation.json` -> `0 critical / 0 warning`
- `tmp/dashboard-acceptance-report.json` -> `17 / 17`

## Residual truth
- `tmp_cleanup.py` has not yet had to archive real stale one-off tmp artifacts; the contract is landed, but the live run was a zero-candidate proof, not a stress test.
- `validate_portfolio_config.py` is intentionally warning-only. That is correct for Workflow 13, but it is not the same thing as strict config enforcement.
- Workflow 14 still owns operator-boundary cleanup, caller tracing, wrapper usage audit, and any evidence-based archive decision for PDF/PPT report wrappers.

## QA conclusion
- Close Workflow 13.
- Do not pretend Workflow 14 residue was solved here.
