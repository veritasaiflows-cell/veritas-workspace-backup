<!-- GENERATED REVIEW-ONLY SURFACE
Source JSON: tmp/today-card.json
Source Markdown: tmp/today-card.md
Published by Veritas main session: 2026-05-22T07:04:02Z
Authority: not canon; not owner approval; no portfolio/canon mutation; no paper/live order; no trade/account/money movement.
-->

# Today

- Generated: `2026-05-22T06:41:43Z`
- Window: `morning`
- Status: **review_only_warning**
- Surface: `01. Dashboards/Today.md` generated review-only daily action surface; source prototype remains `tmp/today-card.md`.

## Trust banner
- Label: **USABLE_WITH_CAUTION**
- Presentation allowed: `True`
- Capital action allowed: `False`
- Owner review required: `True`
  - current-window index status=ok missing_required_roles=[]
  - run summary status=warning acceptance_passed=True exec_freshness=usable_with_caution
  - dashboard validation overall=warning critical=0 warning=1 source_trust=review_required
  - capital validation status=ok critical=0 warning=0
  - board guardrail status=warning below_stop=['BRK.B', 'ECL', 'LMT', 'LNG', 'META', 'NFLX', 'RTX', 'TMUS', 'VMC'] near_stop=['JPM', 'XLF']

## Authority boundary

This card is review-only. It is not canonical, does not infer owner approval, and cannot authorize canon/portfolio mutation, paper or live orders, account actions, money movement, sizing, sleeves, cash, or risk-rule changes.
- `posture`: `review_only_today_card`
- `generated_report_is_canonical`: `False`
- `artifact_mutation_allowed_by_today_card`: `False`
- `today_md_write_allowed_by_this_run`: `False`
- `canonical_note_mutation_allowed_by_today_card`: `False`
- `portfolio_mutation_allowed_by_today_card`: `False`
- `proposal_apply_allowed_by_today_card`: `False`
- `trade_execution_allowed`: `False`
- `live_trade_or_account_action_allowed`: `False`
- `paper_trade_submit_cancel_allowed_by_today_card`: `False`
- `money_movement_allowed`: `False`
- `owner_approval_inferred`: `False`

## Decision items

| Rank | Ticker | State | Posture | Owner action? | Close | Band | Band status | Boundary |
|---:|---|---|---|---:|---:|---|---|---|
| 1 | VRT | review_only | deploy_candidate | False | 323.4 | 286.97-339.27 | IN_BAND | review only; no approval, apply, order, account, sizing, sleeve, cash, or risk-rule authority |
| 2 | ETN | deployable | owner_decision_required | True | 381.51 | 358.11-401.18 | IN_BAND | owner decision required; not approval |
| 3 | GOOG | wait | wait_for_band | False | 383.47 | 355.35-378.98 | ABOVE_BAND_WAIT | review only; no approval, apply, order, account, sizing, sleeve, cash, or risk-rule authority |
| 4 | GS | wait | wait_for_band | False | 988.17 | 894.64-935.77 | ABOVE_BAND_WAIT | review only; no approval, apply, order, account, sizing, sleeve, cash, or risk-rule authority |
| 5 | JPM | wait | wait_for_band | False | 303.0 | 306.82-318.12 | BELOW_BAND | review only; no approval, apply, order, account, sizing, sleeve, cash, or risk-rule authority |
| 6 | MSFT | wait | wait_for_band | False | 419.09 | 389.64-412.56 | ABOVE_BAND_WAIT | review only; no approval, apply, order, account, sizing, sleeve, cash, or risk-rule authority |
| 7 | NVDA | wait | wait_for_band | False | 219.51 | 198.47-216.66 | ABOVE_BAND_WAIT | review only; no approval, apply, order, account, sizing, sleeve, cash, or risk-rule authority |

## Owner decisions needed
- **ETN**: Review evidence packet and decide whether to authorize any next portfolio step outside this card. Boundary: owner decision required; not approval

## Blocked and repair items
- **BRK.B**: below_stop / REPAIR / BENCH (close 479.98, stop 483.05).
- **ECL**: below_stop / WATCH / BELOW STOP (close 250.18, stop 265.01).
- **JPM**: near_stop / ALMOST / ALMOST DEPLOYABLE (close 303.0, stop 301.17).
- **LMT**: below_stop / REPAIR / BELOW STOP (close 522.79, stop 531.63).
- **LNG**: below_stop / WATCH / BELOW STOP (close 240.45, stop 253.45).
- **META**: below_stop / PROMOTION REVIEW / BELOW STOP (close 607.38, stop 655.55).
- **NFLX**: below_stop / WATCH / BELOW STOP (close 89.3, stop 100.24).
- **RTX**: below_stop / WATCH / BELOW STOP (close 175.98, stop 177.91).
- **TMUS**: below_stop / WATCH / BELOW STOP (close 190.9, stop 207.11).
- **VMC**: below_stop / WATCH / BELOW STOP (close 262.08, stop 284.58).
- **XLF**: near_stop / WATCH / WATCH / RESEARCH NEEDED (close 51.73, stop 51.61).

## Proof freshness and source map
- Overall classification: `manual_dependency`
- Trust level: `review_required`
- Presentation allowed: `True`
- Capital action allowed: `False`

| Role | Path | Status | Generated | Required |
|---|---|---|---|---:|
| current_window_artifact_index | `tmp/current-window-artifacts.json` | ok / ok | 2026-05-22T05:13:12Z | True |
| run_summary | `tmp/run-summary-morning.json` | warning / ok | 2026-05-22T05:08:48Z | True |
| capital_deployment_recommendations | `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json` | ok / ok | 2026-05-22T04:56:17Z | True |
| capital_deployment_recommendation_validation | `tmp/capital-deployment-recommendation-validation.json` | ok / ok | 2026-05-22T05:48:05Z | True |
| dashboard_validation | `tmp/dashboard-validation.json` | warning / ok | 2026-05-22T04:17:38.766711+00:00 | True |
| board_canon_guardrail | `tmp/board-canon-guardrail.json` | warning / ok | 2026-05-22T04:17:43Z | True |
| intraday_delivery_router_status | `tmp/intraday-alerts/delivery-router-status.json` | GROUPED_DIGEST_READY / ok | 2026-05-22T04:56:18Z | False |

## Must not do
- Do not treat this Today card as canonical truth or an owner approval artifact.
- Do not mutate Execution Board, Portfolio Snapshot, Coverage/Watchlist, portfolio model, sizing, sleeves, cash, risk rules, or owner notes from this card.
- Do not place, submit, cancel, replace, or prepare automatic live or paper orders from this card.
- Do not infer approval from in-band price, clean validation, rank, recommendation posture, or packet quality.
- Do not hide stale/manual-dependency/source-warning state behind green action language.

## Next generator action
Refresh with `python scripts\today_card_generator.py`, validate with `python scripts\today_card_validator.py`, then publish only after main-session review. This file remains a generated review-only routing surface, not canon.
