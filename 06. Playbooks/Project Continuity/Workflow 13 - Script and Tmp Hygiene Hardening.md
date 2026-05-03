# Workflow 13 - Script and Tmp Hygiene Hardening

## Objective
- Land the low-risk script and tmp hardening work that fixes known silent breakage, removes misleading diagnostics, and adds bounded lifecycle guards without restructuring the proven finance chain.

## Current State
- Workflow 13 is complete.
- The targeted hygiene set landed without widening into structural cleanup theater:
  - the three off-chain equity-report scripts now resolve the live workspace root from `Path(__file__).resolve().parents[1]`
  - `run_summary_refresh.py` now handles the narrow post-summary tail normalization case more honestly
  - `validate_portfolio_config.py` writes fail-soft machine warnings to `tmp/portfolio-config-validation.json`
  - `tmp_cleanup.py` now provides an explicit, gated Sunday cleanup tail with report output, not a silent sweep

## Last Meaningful Progress
- Workflow 13 was completed on 2026-05-03 with live proof:
  - `equity_visual_report.py --help`, `equity_pdf_report.py --help`, and `equity_ppt_report.py --help` all ran clean after the path fix
  - `python scripts/validate_portfolio_config.py` returned `status: ok`, `warning: 0`, `checked_tickers: 22`
  - `python scripts/tmp_cleanup.py --dry-run` and the Sunday `--cleanup` tail both completed cleanly with `eligible_count: 0`
  - `python scripts/run_finance_refresh_chain.py post-close` and `python scripts/run_finance_refresh_chain.py sunday --cleanup` both completed successfully
  - `tmp/run-summary-post-close.json` and `tmp/run-summary-sunday.json` now show terminal `execution.chain_status = "ok"`
  - `tmp/dashboard-validation.json` stayed `0 critical / 0 warning` and `tmp/dashboard-acceptance-report.json` stayed `17/17`

## Outstanding
- Workflow 13 residue is now small and explicit:
  - `tmp_cleanup.py` currently found zero archive-eligible items, so the live archive path exists as a contract but has not yet been meaningfully exercised on non-governed stale tmp artifacts
  - Workflow 14 still owns operator-boundary cleanup, wrapper usage audit, and any evidence-based archive decision for the PDF/PPT report wrappers

## Blockers / Trust Gaps
- `tmp_cleanup.py` must remain gated and reviewable; this is not permission for broad autonomous tmp pruning.
- `validate_portfolio_config.py` remains warning-only by design; strict enforcement would need a later contract decision.
- The normalization hardening is intentionally narrow; if a different run-summary residue appears later, open it as fresh evidence instead of stretching this fix beyond its proof set.

## Next Action
- Deliver the executive summary, then decide whether to open Workflow 14 or leave the Scripts + Tmp Optimization stream paused after the bounded Workflow 13 close.

## Key Files
- `scripts/run_summary_refresh.py` - misleading terminal-state normalization residue lives here.
- `scripts/run_finance_refresh_chain.py` - optional Sunday cleanup / validator hooks would land here.
- `tmp/portfolio-config.json` - heavily consumed machine config that lacks a validator.
- `06. Playbooks/Workspace Structure Protocol.md` - tmp retention policy home.

## Automation / Refresh Path
- Keep this workflow mechanical and bounded.
- Do not restructure the working chain order.
- Validation should prefer reruns of the affected windows plus direct script invocation for the off-chain report tools.

## Closure State
- Status: honestly complete
- QC: passed
- Follow-on owner: Workflow 14 for structural/operator-boundary residue; no hidden residue is being carried inside Workflow 13
