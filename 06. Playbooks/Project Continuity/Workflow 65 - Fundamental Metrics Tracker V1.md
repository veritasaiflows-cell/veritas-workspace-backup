# Workflow 65 - Fundamental Metrics Tracker V1

## Status

Implemented / review-only V1.6 official earnings-bridge propagation active as of 2026-05-16; bank/Financials FCF guard active, official JPM/GS CET1 and Tier 1 risk-based ratios are manual-confirmed, Tier 1 leverage remains separate from risk-based capital metrics, and capital recommendation packets now carry official earnings-bridge context.

## Purpose

Create a durable covered-universe full-picture fundamental metrics dataset so revenue, EPS, net income, margin, cash-flow, balance-sheet, SEC reconciliation, official-IR adjusted/guidance review gates, and per-share shareholder-value drivers can be tracked point-in-time instead of pulled ad hoc in chat.

## Authority boundary

Review-only evidence layer. This workflow may generate metrics, summaries, validation artifacts, history rows, official-IR source metadata, adjusted-EPS/guidance reconciliation packets, and capital-allocation/per-share quality evidence. It may not infer owner approval, mutate canonical notes, change portfolio weights, alter sleeves/cash/risk rules, grant deployment entitlement, place paper/live orders, touch brokerage/accounts, or authorize trades.

## Implemented artifacts

- `scripts/fundamental_metrics_refresh.py`
- `scripts/validate_fundamental_metrics.py`
- `scripts/fundamental_ir_reconciliation_packets.py`
- `scripts/validate_fundamental_ir_reconciliation.py`
- `data/fundamentals/company-ir-metadata.json`
- `tmp/fundamental-metrics-current.json`
- `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (fundamental-metrics-current.md)`
- `tmp/fundamental-metrics-validation.json`
- `tmp/fundamental-ir-reconciliation-packets.json`
- `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (fundamental-ir-reconciliation-packets.md)`
- `tmp/fundamental-ir-reconciliation-validation.json`
- `data/fundamentals/fundamentals-quarterly-v1.jsonl`
- `scripts/bank_native_sec_concept_probe.py`
- `tmp/bank-native-sec-concept-probe.json`
- Dashboard data/view integration: `fundamental_trends` payload, Fundamentals tab, review-only acceptance case, per-share/capital-allocation fields, WF65 V1.5 partial bank-native status fields, and V1.6 official earnings-bridge status fields.

## Full-picture stack now tracked

V1.4 completes the shareholder-value lens Randall requested:

- diluted average shares and YoY share-count change
- free cash flow and FCF/share YoY change
- gross and net share repurchase dollars where available
- buyback yield when market-cap data is available
- stock-based compensation and SBC/revenue or SBC/FCF burden
- dividends paid and dividend yield when market-cap data is available
- capital returns as a percent of FCF
- debt issued, debt repaid, net debt issued, total debt, cash, net debt, and debt/annualized-EBITDA proxy where available
- valuation context: market cap, enterprise value, trailing/forward P/E, price/sales, price/book, FCF yield, earnings yield, EV/EBITDA proxy, EV/FCF proxy, shareholder yield
- ROIC proxy using latest-quarter operating income annualized and tax-adjusted at 21% over invested-capital proxy
- structured capital-allocation anomaly gates for dilution, buyback/SBC offset, negative or strained FCF coverage, debt-funded-return risk, EPS/FCF-per-share divergence, leverage, low ROIC proxy, and net issuance
- capital-allocation quality classification: `tracked`, `caution`, `manual_review_required`, `bank_manual_review`, or `not_applicable`
- bank/Financials guardrail: JPM/GS-style bank rows suppress industrial FCF/debt-funded-return anomaly gates, carry `bank_fcf_not_applicable` info notes, label FCF as `bank_structural`, label net debt as `bank_balance_sheet_structure`, and route to bank-native manual review instead of industrial `caution`
- V1.5 official bank-capital supplement: SEC companyfacts remains partial/manual-required for CET1 and Tier 1 risk-based concepts, but `data/fundamentals/company-ir-metadata.json` now supplies official manual-confirmed JPM/GS risk-based capital ratios from SEC/IR filings. JPM carries CET1 14.1% Advanced / 14.3% Standardized, Tier 1 15.1% Advanced / 15.2% Standardized, and official TBV/share 108.87. GS carries CET1 12.5% Standardized / 13.3% Advanced and Tier 1 14.1% Standardized / 15.1% Advanced. GS Tier 1 leverage 5.9% remains a distinct NOT-risk-based field.

These fields are evidence only. A positive buyback yield, lower share count, FCF/share growth, high ROIC proxy, or cheap-looking valuation does not grant deployment, approval, sizing, sleeve, cash, account, or trade authority.

## Chain integration

`scripts/chain_manifest.py` includes, after `validate_portfolio_config.py` in morning, post-close, post-earnings, and Sunday windows:

1. `bank_native_sec_concept_probe.py --write`
2. `fundamental_metrics_refresh.py`
3. `validate_fundamental_metrics.py --write`
4. `fundamental_ir_reconciliation_packets.py --write`
5. `validate_fundamental_ir_reconciliation.py --write`

`current_window_artifact_index.py` indexes the bank-native SEC probe, current metrics, metrics summary, metrics validation, durable history, IR metadata, IR reconciliation packets, and IR validation. The fundamental validator now fails critical when SEC-resolved bank rows are missing probe/payload timestamps or when the bank-native probe is more than 15 minutes older than the fundamentals payload; a probe timestamp newer than the payload remains a rerun warning.

## Current proof

Final WF65 closeout proof as of 2026-05-16:

- `python -m py_compile scripts\bank_native_sec_concept_probe.py scripts\fundamental_metrics_refresh.py scripts\validate_fundamental_metrics.py scripts\dashboard_payload.py scripts\test_dashboard_acceptance.py scripts\chain_manifest.py scripts\current_window_artifact_index.py scripts\fundamental_ir_reconciliation_packets.py scripts\validate_fundamental_ir_reconciliation.py` passed.
- `python scripts\bank_native_sec_concept_probe.py --tickers JPM GS --write --verbose` wrote `tmp/bank-native-sec-concept-probe.json`: JPM 8 auto-resolved / 2 manual-required / 0 critical / 1 warning; GS 9 auto-resolved / 2 manual-required / 0 critical / 0 warning. SEC companyfacts still treats CET1 and Tier 1 risk-based concepts as structural manual-required fields, which is why official manual metadata is the supplement path.
- `python scripts\fundamental_metrics_refresh.py` refreshed 41 covered tickers and wrote current JSON/MD/history artifacts. JPM now carries `bank_native_sec_status=partial`, CET1 14.1, Tier 1 15.1, both `manual_confirmed`, plus official TBV/share 108.87; GS carries `bank_native_sec_status=partial`, CET1 12.5 and Tier 1 14.1, both `manual_confirmed`, plus Tier 1 leverage 5.9 with mandatory NOT-risk-based disclosure.
- `python scripts\validate_fundamental_metrics.py --write` returned 0 critical / 0 warning after BRK.B and XOM revenue conflicts were resolved by replacing conflicting yfinance revenue with SEC companyfacts period-matched `Revenues` for both current and prior periods. The prior JPM TBV intangibles warning cleared because JPM now uses official TBV/share. Targeted in-memory mutations confirmed `bank_native_probe_stale` becomes critical for JPM/GS when the probe is more than 15 minutes older than the fundamentals payload and official-capital period mismatches critical-fail against `period_end`.
- `python scripts\fundamental_ir_reconciliation_packets.py --write` generated 31 equity adjusted-EPS/guidance reconciliation packets; `python scripts\validate_fundamental_ir_reconciliation.py --write` returned `status=ok`, 0 critical / 0 warning.
- `python scripts\generate_dashboard.py` + `python scripts\validate_dashboard_state.py --write` returned dashboard validation 0 critical / 1 expected NVDA event-risk band warning; Fundamental metrics and IR packets are fresh.
- `python scripts\test_dashboard_acceptance.py` passed 26/26, including official bank-capital display, `bankNativeSecStatus=partial`, JPM official TBV/share, bank FCF denominator suppression, and Tier 1 leverage NOT-risk-based separation.
- `python scripts\current_window_artifact_index.py --window post-close --write` returned `status=ok`, 38/38 existing artifacts, now including `tmp/bank-native-sec-concept-probe.json`.

Authority unchanged: this is review-only evidence. Official capital-ratio capture, cleaner TBV/share, dashboard propagation, and stale-probe guardrails do not grant owner approval, portfolio mutation, deployment entitlement, sizing/sleeve/cash/risk-rule authority, brokerage/account authority, paper/live order authority, or trade authority.

### Claude final hardening closure

Claude final hardening returned **PASS WITH GAPS** with no critical blockers and no authority widening. Veritas closed both warning-grade gaps after the pass:

- G1 stale bank-native note: `apply_official_bank_capital()` now overwrites the conservative SEC-probe note when official manual-confirmed capital ratios are applied, so JPM/GS rows no longer say CET1/Tier 1 still require confirmation after carrying `manual_confirmed` ratios.
- G2 official-capital period freshness: `validate_fundamental_metrics.py` now critical-fails populated bank risk-based capital rows when `risk_based_capital_period`, `cet1_ratio_period`, or `tier1_ratio_period` does not match `period_end`. A targeted in-memory mismatch test produced six critical `bank_official_capital_period_mismatch` findings across JPM/GS.

Post-closure proof remains review-only. After the BRK.B/XOM SEC-revenue override pass, fundamental validator is 0 critical / 0 warning; IR validation is 0 critical / 0 warning across 31 packets; dashboard acceptance is 26/26; dashboard validation is 0 critical / 1 expected NVDA event-risk warning; current-window artifact index is ok 38/38.

### BRK.B / XOM SEC conflict closure

The remaining BRK.B and XOM WF65 validator warnings were real SEC-vs-yfinance revenue definition conflicts, not validation noise. `fundamental_metrics_refresh.py` now resolves material revenue conflicts by using SEC companyfacts period-matched `Revenues` for both current and prior periods, stores the original yfinance revenue fields for audit (`revenue_aggregator_original`, `revenue_prior_aggregator_original`), recomputes revenue YoY and revenue-dependent percentages, and annotates the row with `revenue_source=sec_companyfacts_period_match_override`. Latest proof: `validate_fundamental_metrics.py --write` is 0 critical / 0 warning; BRK.B and XOM SEC reconciliation status is `matched`; dashboard and artifact proof remain green except the expected NVDA event-risk dashboard warning.

### V1.7 official earnings bridge artifact

A distinct review-only official earnings bridge artifact now exists on top of the embedded IR-packet bridge. `scripts/official_earnings_bridge.py` reads `tmp/fundamental-ir-reconciliation-packets.json` and writes `tmp/official-earnings-bridge.json` / `.md` with 31 manual-required bridges. `scripts/validate_official_earnings_bridge.py` validates review-only/manual-required posture, HTTPS official source URLs, typed bridge sub-blocks, no invented/fetched official values, and false authority guards. Chain manifest now runs the bridge producer and validator after IR packet validation in morning, post-close, post-earnings, and Sunday windows; current-window artifact index now includes the bridge JSON, MD, and validation artifacts. Latest proof: official bridge validation `status=ok`, 31 bridges, 0 critical / 0 warning; current-window artifact index 41/41.

### V1.6 official earnings bridge / WF66 capital-packet propagation

Randall requested decision-grade packet context after the ETN review showed that metric snapshots explain the "what" but not enough of the "why." V1.6 adds a review-only `official_earnings_bridge` object to every IR reconciliation packet and propagates compact bridge context into daily review objects, capital recommendation JSON, capital recommendation Markdown, dashboard fundamental rows, and validation/acceptance contracts. The bridge carries official IR source URLs, growth bridge placeholders, adjusted EPS bridge placeholders, segment-margin placeholders, orders/backlog placeholders, guidance placeholders, management explanation placeholders, and acquisition/debt notes placeholders. All fields remain `manual_required` / `review_only` / `reconciled=false` until explicit official-source capture exists.

Changed surfaces:
- `data/fundamentals/company-ir-metadata.json` now carries `official_earnings_bridge_default` with false authority guards.
- `scripts/fundamental_ir_reconciliation_packets.py` injects ticker-level `official_earnings_bridge` into all 31 equity IR packets.
- `scripts/validate_fundamental_ir_reconciliation.py` validates bridge object shape, HTTPS official URLs, manual-required/unreconciled posture, typed sub-blocks, and authority guards.
- `scripts/daily_review_objects.py` carries bridge context into capital recommendations and marks unresolved official earnings context as manual review evidence.
- `scripts/portfolio_mutation_proposal_generator.py` emits `official_earnings_bridge` and `official_earnings_gate` in the 4 capital recommendation packets and adds `tmp/fundamental-ir-reconciliation-packets.json` to source artifacts.
- `scripts/capital_deployment_recommendation_report.py` renders bridge status, SEC reconciliation, adjusted EPS bridge, guidance bridge, and manual-review flag.
- `scripts/capital_deployment_recommendation_validator.py` validates the capital-packet bridge remains non-authorizing.
- `scripts/dashboard_payload.py`, `scripts/dashboard-js/07a-fundamentals.js`, and `scripts/test_dashboard_acceptance.py` expose and lock the dashboard bridge fields as review-only.

Latest V1.6 proof:
- `python -m py_compile` passed across changed producer, validator, packet, report, dashboard, and acceptance scripts.
- `python scripts\fundamental_ir_reconciliation_packets.py --write` + `python scripts\validate_fundamental_ir_reconciliation.py --write`: `status=ok`, 31 packets, 0 critical / 0 warning.
- `python scripts\daily_review_objects.py --window post-close`, `python scripts\portfolio_mutation_proposal_generator.py --window post-close --write`, `python scripts\capital_deployment_recommendation_report.py --write`, and `python scripts\capital_deployment_recommendation_validator.py --write`: 4 packets (ETN, GOOG, GS, MSFT), validator `ok`, 0 critical / 0 warning.
- `python scripts\generate_dashboard.py`, `python scripts\validate_dashboard_state.py --write`, `python scripts\test_dashboard_acceptance.py`, and `python scripts\current_window_artifact_index.py --window post-close --write`: dashboard validation 0 critical / 1 expected NVDA warning, dashboard acceptance 26/26, artifact index 38/38.
- QC lanes passed: IR bridge QC PASS, capital packet QC PASS, dashboard QC PASS.

Cron/manifest update: V1.7 adds a distinct `official_earnings_bridge.py` artifact/validator while preserving the embedded V1.6 packet context. The bridge artifact is still review-only and manual-required; it is an indexed review surface, not a second source of portfolio truth or an apply path.

## Current limitations

- V1.5 still uses yfinance as the primary aggregator source and SEC companyfacts as a reconciliation gate where period-matched facts exist; material revenue conflicts now use SEC period-matched `Revenues` overrides when current/prior facts are available. Official JPM/GS capital metadata supplements the bank-specific fields but does not replace full source-of-record research.
- SEC companyfacts does not reliably expose CET1 or Tier 1 risk-based ratios for large U.S. banks; these stay manual-source fields and may be populated only from official filings/supplements with source URL, period, section/table, trust, and no-derived-ratio guard.
- Tier 1 leverage / SLR remain leverage metrics, not risk-based ratios. They must stay visually and structurally separate from CET1 and Tier 1 risk-based capital.
- Adjusted EPS, guidance, growth bridge, segment margins, orders/backlog, management commentary, and acquisition/debt notes remain manual-required review fields inside official earnings bridge packets; no blind scraping, overwrite, or authority inference occurs.
- Buyback, SBC, dividend, and market-cap-derived yield fields are aggregator-dependent; missing values remain null rather than fabricated.
- Some tickers have partial EPS coverage from pulled income-statement rows: CAT, CVX, SMCI, ECL.
- ETF and macro proxies are intentionally `not_applicable` for issuer operating-company metrics.
- Bank/Financials industrial-FCF false positives are suppressed/relabelled for JPM/GS-style rows: FCF/share, capital-return/FCF, debt-funded-return risk, EPS-vs-FCF/share divergence, leverage-elevated, and negative-bank-FCF SBC/FCF ratios are not treated as industrial capital-allocation defects.
- JPM/GS still require broader bank-native ROTCE/ROE, NIM, funding/liquidity, charge-offs, reserves, efficiency ratio, and rate-regime/NIM commentary review before the bank-specific capital/credit question is considered fully answered for execution use.
- Shareholder-yield and dividend/buyback-yield fields carry `shareholder_yield_period=latest_period_market_cap_proxy`; they remain latest-period/market-cap proxies, not owner approval or annualized return claims.

## Next pass

1. Add reliable official-source capture/extraction only when it can preserve manual-required/no-fabrication rules for adjusted EPS, guidance, growth bridge, segment margins, orders/backlog, management explanation, acquisition/debt notes, ROTCE/NIM/funding/liquidity/credit-quality fields.
2. Consider GS official TBV/share capture if GS becomes a serious Financials promotion candidate; current GS TBV/share remains SEC-probe/market-cap proxy, not official manual-confirmed TBV.
3. Consider a canonical research-note sync only after SEC/IR reconciliation, sector-specific metric handling, and capital-allocation evidence are stable and reviewed.
