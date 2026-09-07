<!-- GENERATED CORE LIVE SURFACE STUB
Source proof: state/finance/execution-board-replacement.json
Archived full source: 09. Archive/Core Finance Human Surfaces/2026-05-30/03. Portfolio/Execution Board.md
Generated: 2026-05-31T06:21:28Z
Authority: canonical path preserved for parser compatibility; no owner approval, portfolio mutation, or execution.
-->

# Execution Board

## Purpose and ownership boundary

This compact surface preserves the canonical parser path for action state, entry bands, stops, blockers, and technical discipline. Full prior narrative is archived; structured replacement proof is in `state/finance/execution-board-replacement.json`.

## Current execution table

| Ticker | Lane | Action state | Close/date | Band | Stop | Technical posture | Blocker/condition | Authority note | Source/freshness |
|---|---|---|---|---|---|---|---|---|---|
| ETN | Execution | **Almost deployable / above-band no-chase** | 421.77 / 2026-06-18 | 387.67-404.02 | 367.60 | above all MAs | above band 387.67-404.02; wait/no chase unless a later approved band review changes the level. owner-approved setup, but current close is outside the live entry band -- wait for reclaim or approved band update. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| JPM | Execution | **Almost deployable / above-band no-chase** | 325.22 / 2026-06-18 | 304.96-315.95 | 296.21 | above all MAs -- bullish 20>50>200 stack | above band 304.96-315.95; wait/no chase unless a later approved band review changes the level. approval recorded, but trigger is not live -- wait for reclaim or explicit approved review. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| NVDA | Execution | **Promotion review / explicit decision required** | 210.69 / 2026-06-18 | 202.81-212.23 | 192.95 | above 50d and 200d, below 20d | inside band 202.81-212.23; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band at 210.69 -- explicit owner promotion review required before deployable-now status. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| GOOG | Execution | **Promotion review / explicit decision required** | 367.46 / 2026-06-18 | 354.25-369.69 | 341.07 | above 50d and 200d, below 20d | inside band 354.25-369.69; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band at 367.46 -- explicit owner promotion review required before deployable-now status. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| MSFT | Execution | **Near-stop repair/no-chase / trigger not live** | 379.40 / 2026-06-18 | 389.64-412.56 | 378.18 | below all MAs | Near-stop repair/no-chase condition: close is within 1% of the 378.18 stop; require reclaim/fresh review before any deployment review. workflow state is ALMOST -- constructive but not yet promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| AMZN | Watch | **Do not touch / below-stop** | 244.39 / 2026-06-18 | 252.27-267.19 | 244.81 | above 200d, below 20d and 50d | Below 244.81 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 244.39 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| VRT | Formal tactical challenger planning | **Promotion review / explicit decision required** | 333.05 / 2026-06-18 | 300.02-319.13 | 276.97 | above all MAs | near band 300.02-319.13 at 333.05; auto-applied routine technical band maintenance. Band freshness does not override workflow, sizing, catalyst, or owner-gated constraints. | Routine band maintenance only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/band-proposals.json + tmp/portfolio-config.json 2026-06-18; auto band maintenance 2026-06-18 |
| CAT | Watch | **Watch-only / review-only** | 985.82 / 2026-06-18 | 811.65-866.48 | 784.25 | above all MAs -- bullish 20>50>200 stack | above band 811.65-866.48; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| LLY | Watch | **Watch-only / review-only** | 1098.57 / 2026-06-18 | 907.64-969.88 | 876.52 | above 50d and 200d, below 20d | above band 907.64-969.88; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| GS | Execution | **Almost deployable / above-band no-chase** | 1096.56 / 2026-06-18 | 971.53-1048.14 | 928.97 | above all MAs -- bullish 20>50>200 stack | near band 971.53-1048.14 at 1096.56; auto-applied routine technical band maintenance. Band freshness does not override workflow, sizing, catalyst, or owner-gated constraints. | Routine band maintenance only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/band-proposals.json + tmp/portfolio-config.json 2026-06-18; auto band maintenance 2026-06-18 |
| BRK.B | Execution repair | **Do not touch / repair review** | 489.46 / 2026-06-18 | 489.78-498.19 | 483.05 | above 20d and 50d, below 200d | below band 489.78-498.19; trigger not live until reclaim or explicit owner-approved review. Repair state remains active until explicitly lifted by fresh review. workflow state is REPAIR -- wait for setup to rebuild. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| XOM | Execution repair | **Do not touch / below-stop** | 137.81 / 2026-06-18 | 150.24-158.44 | 146.14 | above 200d, below 20d and 50d | Below 146.14 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. workflow state is REPAIR -- wait for setup to rebuild. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| LMT | Execution repair | **Do not touch / below-stop** | 510.95 / 2026-06-18 | 548.51-582.27 | 531.63 | below all MAs | Below 531.63 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. close 510.95 is below stop -- do not deploy. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| RTX | Watch repair | **Watch-only / review-only** | 185.60 / 2026-06-18 | 183.01-193.23 | 177.91 | above all MAs | inside band 183.01-193.23; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- main-session entry-policy review required; no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| CVX | Watch | **Do not touch / below-stop** | 173.63 / 2026-06-18 | 186.91-196.41 | 182.16 | above 200d, below 20d and 50d | Below 182.16 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 173.63 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| PLTR | Watch/speculative | **Do not touch / below-stop** | 128.47 / 2026-06-18 | 137.37-149.53 | 131.29 | below all MAs | Below 131.29 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 128.47 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| AMD | Watch | **Watch-only / review-only** | 537.37 / 2026-06-18 | 295.33-342.53 | 271.73 | above all MAs -- bullish 20>50>200 stack | above band 295.33-342.53; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| LNG | Watch repair | **Do not touch / below-stop** | 227.03 / 2026-06-18 | 260.82-275.56 | 253.45 | below all MAs | Below 253.45 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 227.03 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| BKNG | Watch repair | **Do not touch / repair review** | 171.78 / 2026-06-18 | 164.05-170.91 | 155.97 | above 20d and 50d, below 200d | above band 164.05-170.91; wait/no chase unless a later approved band review changes the level. Repair state remains active until explicitly lifted by fresh review. watch lane only; no execution-board entitlement. workflow state is REPAIR -- wait for setup to rebuild. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| LIN | Portfolio review / Materials sleeve | **Promotion review / explicit decision required** | 512.15 / 2026-06-18 | 497.11-506.11 | 487.17 | above all MAs -- bullish 20>50>200 stack | above band 497.11-506.11; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| ECL | Watch / sector monitor | **Watch-only / review-only** | 269.12 / 2026-06-18 | 271.22-278.98 | 265.01 | above all MAs | below band 271.22-278.98; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| VMC | Watch / sector monitor | **Watch-only / review-only** | 302.84 / 2026-06-18 | 291.87-300.98 | 284.58 | above all MAs | above band 291.87-300.98; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| META | Portfolio review / watch lane | **Do not touch / below-stop** | 577.22 / 2026-06-18 | 672.60-693.91 | 655.55 | below all MAs | Below 655.55 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 577.22 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| NFLX | Watch / sector monitor | **Do not touch / below-stop** | 77.38 / 2026-06-18 | 102.56-105.46 | 100.24 | below all MAs | Below 100.24 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 77.38 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| TMUS | Watch / sector monitor | **Do not touch / below-stop** | 181.67 / 2026-06-18 | 213.01-220.38 | 207.11 | below all MAs | Below 207.11 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 181.67 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| PH | Portfolio review / watch lane | **Promotion review / explicit decision required** | 953.27 / 2026-06-18 | 851.36-908.98 | 819.35 | above all MAs | above band 851.36-908.98; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| GE | Watch / sector monitor | **Watch-only / review-only** | 357.64 / 2026-06-18 | 299.03-311.84 | 288.78 | above all MAs -- bullish 20>50>200 stack | above band 299.03-311.84; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| CME | Portfolio review / watch lane | **Do not touch / below-stop** | 246.38 / 2026-06-18 | 287.74-298.86 | 276.68 | below all MAs | Below 276.68 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 246.38 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| WMB | Watch / sector monitor | **Watch-only / review-only** | 73.12 / 2026-06-18 | 73.25-75.50 | 70.32 | above all MAs | below band 73.25-75.50; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| XLI | ETF monitor | **Watch-only / review-only** | 180.91 / 2026-06-18 | 166.78-173.40 | 163.10 | above all MAs -- bullish 20>50>200 stack | above band 166.78-173.40; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| XLB | Formal Materials ETF starter planning | **Promotion review / explicit decision required** | 51.81 / 2026-06-18 | 49.84-51.68 | 48.81 | above all MAs | above band 49.84-51.68; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| XLC | ETF monitor | **Do not touch / below-stop** | 109.45 / 2026-06-18 | 114.31-116.55 | 112.71 | below all MAs | Below 112.71 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 109.45 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| PAVE | ETF monitor | **Watch-only / review-only** | 58.56 / 2026-06-18 | 53.94-56.28 | 52.64 | above all MAs -- bullish 20>50>200 stack | above band 53.94-56.28; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| XLF | ETF monitor | **Watch-only / review-only** | 53.57 / 2026-06-18 | 52.26-53.07 | 51.61 | above all MAs | above band 52.26-53.07; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| XLE | ETF monitor | **Do not touch / below-stop** | 53.77 / 2026-06-18 | 56.35-58.04 | 54.83 | above 200d, below 20d and 50d | Below 54.83 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 53.77 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| ITA | ETF candidate / promotion-review | **Promotion review / explicit decision required** | 238.99 / 2026-06-18 | 212.15-223.44 | 205.88 | above all MAs -- bullish 20>50>200 stack | above band 212.15-223.44; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| VAW | ETF monitor | **Watch-only / review-only** | 234.24 / 2026-06-18 | 225.44-233.70 | 220.85 | above all MAs | above band 225.44-233.70; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| VXUS | ETF monitor / international diversification | **Watch-only / review-only** | 86.77 / 2026-06-18 | 80.88-83.36 | 78.15 | above all MAs -- bullish 20>50>200 stack | above band 80.88-83.36; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-06-18; volatile canon sync 2026-06-18 |
| KTOS | Speculative / watch lane | **Watch-only / reference band defined** | 52.09 / 2026-05-15 | 80.79-85.20 | 77.27 | below reclaim structure | Speculative defense-tech monitor; current close is below reclaim band, so this is repair/reclaim context only. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
| SLV | Speculative / macro watch | **Watch-only / reference band defined** | 69.04 / 2026-05-15 | 64.07-72.34 | 60.31 | mixed / macro-linked | Macro metals hedge monitor; band is reference context and requires macro confirmation before any action proposal. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
| TLT | Macro watch | **Watch-only / reclaim reference** | 83.66 / 2026-05-15 | 86.60-87.41 | 85.96 | below reclaim structure | Duration/macro monitor; below reclaim band, rate-regime confirmation required before any action proposal. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
| SMCI | Speculative / watch lane | **Watch-only / reference band defined** | 31.04 / 2026-05-15 | 24.92-30.93 | 22.19 | volatile / below 200-day context | Speculative AI-infrastructure monitor; high volatility and below-200-day context keep it non-deployable without fresh review. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |

## Parser-compatible technical sections

### AMD
- Close: **537.37** *(technical refresh; 2026-06-18 close; current artifact layer)******************************************************************************************
- Support: **311.80** (top of preferred band / first disciplined pullback zone), then **284.89** (20-day)
- Preferred entry band: **295.33 to 342.53** *(current artifact layer 2026-06-18)
- Reference band: **295.33 to 342.53** / reference stop **271.73** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **271.73**
- Invalidation logic: loses the pullback zone and breaks back through 271.73 after the earnings window.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### AMZN
- Close: **244.39** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **252.27 to 267.19** *(current artifact layer 2026-06-18)
- Reference band: **252.27 to 267.19** / reference stop **244.81** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **244.81**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### BKNG
- Close: **171.78** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- MA posture: **above 20d and 50d, below 200d**. This is repair mode, not an entry setup.
- Support: **164.05–170.91** (watch/rebuild zone only), then **161–164** (manual support area from BKNG review)
- Resistance: **174–177** (repair/reclaim zone), then **198.30** (200-day / machine reclaim reference)
- Preferred entry band: **164.05 to 170.91** *(current artifact layer 2026-06-18)
- Reference band: **164.05 to 170.91** / reference stop **155.97** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / repair review**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **155.97**
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### BRK.B
- Close: **489.46** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Stop-breached / invalidation: close **474.48** is below explicit stop **483.05** and below band low **489.78**; do not deploy, promote, size, or execute until fresh reclaim review clears the repair state.
- MA posture: **above 20d and 50d, below 200d**. Ballast profile intact, but chart remains in repair until the 200-day is reclaimed and held.
- Support: **483.05** (reclaim-band stop), then **479.58** (50-day), then prior repair stop zone near **465.81**
- Resistance: **489.78** (200-day / reclaim trigger), then **498.19** (top of reclaim band)
- Preferred entry band: **489.78 to 498.19** *(current artifact layer 2026-06-18)
- Reference band: **489.78 to 498.19** / reference stop **483.05** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Do not touch / repair review**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### CAT
- Close: **985.82** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **811.65 to 866.48** *(current artifact layer 2026-06-18)
- Reference band: **811.65 to 866.48** / reference stop **784.25** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **784.25**
- Invalidation logic: loses the 50-day and breaks the uptrend.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### CME
- Close: **246.38** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Stop-breached / invalidation: close **273.54** is below explicit stop **276.68** and below band low **287.74**; watch-lane monitor only, with no deployment, promotion, sizing, or execution authority.
- Support: **296.93** (50-day / near-term support), then **287.74** (20-day / lower band reference), then **276.68** (200-day)
- Resistance: **298.86-300** (current close / round-number test), then **305** *(extension reference; confirm on next chart refresh)*
- Preferred entry band: **287.74 to 298.86** *(current artifact layer 2026-06-18)
- Reference band: **287.74 to 298.86** / reference stop **276.68** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### CVX
- Close: **173.63** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Support: **189** (20-day), then **186.91** (bottom of preferred band)
- Resistance: **193** (50-day), then **196.41** (top of preferred band)
- Preferred entry band: **186.91 to 196.41** *(current artifact layer 2026-06-18)
- Reference band: **186.91 to 196.41** / reference stop **182.16** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **182.16**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### ECL
- Reference band: **271.22 to 278.98** / reference stop **265.01** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **269.12** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **271.22 to 278.98** *(current artifact layer 2026-06-18)
- Explicit stop / invalidation: **265.01**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### ETN
- Explicit stop: **367.60**
- Close: **421.77** *(technical refresh; 2026-06-18 close; current artifact layer)*************************
- 20 / 50 / 200-day: **402.49 / 404.63 / 367.01**
- MA posture: **above all MAs**.
- Support: **367.00** (preferred band low), then **348.82** (explicit stop)
- Resistance: **406.99** live written band high; do not chase above the live written band without a later approved band review.
- Preferred entry band: **387.67 to 404.02** *(current artifact layer 2026-06-18)
- Reference band: **387.67 to 404.02** / reference stop **367.60** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / above-band no-chase**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **367.60**; below this level the setup is fail-closed pending fresh review.
- Stance: **Almost deployable / above-band no-chase**. above band 387.67-404.02; wait/no chase unless a later approved band review changes the level. owner-approved setup, but current close is outside the live entry band -- wait for reclaim or approved band update.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.
- **Automated band maintenance:** 2026-06-15 eligible proposal applied: prior **361.19–402.25 / stop 342.53** → new **387.67–404.02 / stop 367.60**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

### GE
- Reference band: **299.03 to 311.84** / reference stop **288.78** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **357.64** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **299.03 to 311.84** *(current artifact layer 2026-06-18)
- Explicit stop / invalidation: **288.78**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### GOOG
- Explicit stop: **341.07**
- Close: **367.46** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Support: **367.49-362.08** (20-day / top of the written band / first disciplined pullback zone), then **328.93** (50-day)
- Resistance: **397.17** current extension zone, then fresh post-print highs.
- Preferred entry band: **354.25 to 369.69** *(current artifact layer 2026-06-18)
- Reference band: **354.25 to 369.69** / reference stop **341.07** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **341.07**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.
- **Automated band maintenance:** 2026-06-18 eligible proposal applied: prior **346.66–369.83 / stop 333.78** → new **354.25–369.69 / stop 341.07**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

### GS
- Explicit stop: **928.97**
- Close: **1096.56** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Support: **924** (20-day / refreshed band top zone), then **873** (50-day)
- Resistance: current extension zone above the refreshed band top at **923.51**
- Preferred entry band: **971.53 to 1048.14** (auto-applied band maintenance 2026-06-18; KELTNER_MA_CONSTRAINED / NEAR_BAND)
- Reference band: **971.53 to 1048.14** / reference stop **928.97** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / above-band no-chase**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **928.97**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.
- **Automated band maintenance:** 2026-06-18 eligible proposal applied: prior **971.53–1048.14 / stop 928.97** → new **971.53–1048.14 / stop 928.97**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

### ITA
- Close: **238.99** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **212.15 to 223.44** *(current artifact layer 2026-06-18)
- Reference band: **212.15 to 223.44** / reference stop **205.88** (current artifact layer 2026-06-18; volatile canon sync)
- Explicit stop / invalidation: **205.88**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### JPM
- Preferred entry band: **304.96 to 315.95** *(current artifact layer 2026-06-18)
- Reference band: **304.96 to 315.95** / reference stop **296.21** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / above-band no-chase**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **296.21**
- Close: **325.22** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Support: **301.17** (near-term support / reference level), then **293.02** (current explicit stop / invalidation). Legacy/parser stop **286.81** is retained only as non-authoritative context.
- Historical trigger-review context: **306.82 to 318.12** was the 2026-05-16 owner-resolved trigger-review band, but the fresh 2026-05-22 artifact layer superseded it for current reference-band display. Do not treat either band as automatic deployable authority.
- Preferred / current reference entry band: **300.47 to 305.27** *(current artifact layer 2026-05-22)*.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.
- **Automated band maintenance:** 2026-06-18 eligible proposal applied: prior **301.50–307.78 / stop 293.93** → new **304.96–315.95 / stop 296.21**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

### LIN
- Close: **512.15** *(technical refresh; 2026-06-18 close; current artifact layer)**************************
- MA posture: **above all MAs -- bullish 20>50>200 stack**. Structure is constructive, but price is at the top edge of the written band.
- Support: **504.34-497.11** (20-day / lower written band pullback cluster), then **487.17** (explicit stop / invalidation), then **461.95** (200-day deeper trend support)
- Resistance: **506.11** (written band ceiling / no-chase line), then **515** extension reference requiring fresh review.
- Preferred entry band: **497.11 to 506.11** *(current artifact layer 2026-06-18)
- Reference band: **497.11 to 506.11** / reference stop **487.17** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### LLY
- Close: **1098.57** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Support: **970** (top of the written band), then **943** (50-day)
- Preferred entry band: **907.64 to 969.88** *(current artifact layer 2026-06-18)
- Reference band: **907.64 to 969.88** / reference stop **876.52** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **876.52**
- Invalidation logic: loses the written stop and fails the current healthcare watch-lane base.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### LMT
- Close: **510.95** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Stop-breached / invalidation: close **530.45** is below explicit stop **531.63** and below band low **548.51**; do not deploy, promote, size, or execute until fresh reclaim review clears the repair state.
- MA posture: **below all MAs**. The chart is broken — price is below every major MA and below the explicit stop.
- Support: confirm fresh support only after a new base forms.
- Resistance: **524.03-527.21** (200-day / 20-day reclaim zone), then **548.51** (bottom of written band) and **588.84** (50-day)
- Preferred entry band: **548.51 to 582.27** *(current artifact layer 2026-06-18)
- Reference band: **548.51 to 582.27** / reference stop **531.63** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### LNG
- Close: **227.03** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Stop-breached / invalidation: close **224.86** is below explicit stop **253.45** and below band low **260.82**; watch-lane monitor only, with no deployment, promotion, sizing, or execution authority.
- Support: no live support from the old band; next repair reference is the **229.19** 200-day after the stop breach.
- Resistance: **253.45** (lost stop / first repair line), then **260.82** (bottom of the old preferred band), then **275.56** (top of the old band)
- Preferred entry band: **260.82 to 275.56** *(current artifact layer 2026-06-18)
- Reference band: **260.82 to 275.56** / reference stop **253.45** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### META
- Reference band: **672.60 to 693.91** / reference stop **655.55** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **577.22** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **672.60 to 693.91** *(current artifact layer 2026-06-18)
- Explicit stop / invalidation: **655.55**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### MSFT
- Close: **379.40** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Support: **398.84-389.64** (50-day / lower working band), then **378.18** (explicit stop)
- Resistance: **412.56-417.45** (band ceiling / 20-day reclaim zone), then **462.35** (200-day)
- Preferred entry band: **389.64 to 412.56** *(current artifact layer 2026-06-18)
- Reference band: **389.64 to 412.56** / reference stop **378.18** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Near-stop repair/no-chase / trigger not live**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **378.18**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### NFLX
- Reference band: **102.56 to 105.46** / reference stop **100.24** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **77.38** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **102.56 to 105.46** *(current artifact layer 2026-06-18)
- Explicit stop / invalidation: **100.24**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### NVDA
- Explicit stop: **192.95**
- Close: **210.69** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Support: **209.12** (20-day / band-top area), then **192.23-185.73** (50-day / 200-day cluster)
- Resistance: **235.74** current extension zone, then any post-earnings higher-high attempt.
- Preferred entry band: **202.81 to 212.23** *(current artifact layer 2026-06-18)
- Reference band: **202.81 to 212.23** / reference stop **192.95** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **192.95**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.
- **Automated band maintenance:** 2026-06-18 eligible proposal applied: prior **190.65–212.18 / stop 180.86** → new **202.81–212.23 / stop 192.95**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

### PAVE
- Close: **58.56** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **53.94 to 56.28** *(current artifact layer 2026-06-18)
- Reference band: **53.94 to 56.28** / reference stop **52.64** (current artifact layer 2026-06-18; volatile canon sync)
- Explicit stop / invalidation: **52.64**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### PH
- Close: **953.27** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **851.36 to 908.98** *(current artifact layer 2026-06-18)
- Reference band: **851.36 to 908.98** / reference stop **819.35** (current artifact layer 2026-06-18; volatile canon sync)
- Explicit stop / invalidation: **819.35**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### PLTR
- Close: **128.47** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- MA posture: **below all MAs**. Short-term bounce, longer-term repair is still incomplete.
- Support: **141.56** (20-day), then **138.60** (bottom of preferred band)
- Resistance: **145.18** (50-day), then **150.44** (top of preferred band)
- Preferred entry band: **137.37 to 149.53** *(current artifact layer 2026-06-18)
- Reference band: **137.37 to 149.53** / reference stop **131.29** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **131.29**
- Invalidation logic: loses 131.29 and fails the current rebound attempt.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### RTX
- Close: **185.60** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **183.01 to 193.23** *(current artifact layer 2026-06-18)
- Reference band: **183.01 to 193.23** / reference stop **177.91** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **177.91**
- Invalidation logic: name is below band and only marginally above the refreshed stop; prior setup remains in repair.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### TMUS
- Reference band: **213.01 to 220.38** / reference stop **207.11** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **181.67** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **213.01 to 220.38** *(current artifact layer 2026-06-18)
- Explicit stop / invalidation: **207.11**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### VAW
- Close: **234.24** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **225.44 to 233.70** *(current artifact layer 2026-06-18)
- Reference band: **225.44 to 233.70** / reference stop **220.85** (current artifact layer 2026-06-18; volatile canon sync)
- Explicit stop / invalidation: **220.85**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### VMC
- Reference band: **291.87 to 300.98** / reference stop **284.58** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **302.84** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **291.87 to 300.98** *(current artifact layer 2026-06-18)
- Explicit stop / invalidation: **284.58**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### VRT
- Explicit stop: **276.97**
- Close: **333.05** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **300.02 to 319.13** (auto-applied band maintenance 2026-06-18; KELTNER_MA_CONSTRAINED / NEAR_BAND)
- Reference band: **300.02 to 319.13** / reference stop **276.97** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **276.97**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.
- **Automated band maintenance:** 2026-06-18 eligible proposal applied: prior **300.02–319.13 / stop 276.97** → new **300.02–319.13 / stop 276.97**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

### VXUS
- Close: **86.77** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **80.88 to 83.36** *(current artifact layer 2026-06-18)
- Reference band: **80.88 to 83.36** / reference stop **78.15** (current artifact layer 2026-06-18; volatile canon sync)
- Explicit stop / invalidation: **78.15**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### WMB
- Close: **73.12** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Resistance: **77.72** (current extension zone), then **80** *(round-number extension reference; confirm on next chart refresh)*
- Preferred entry band: **73.25 to 75.50** *(current artifact layer 2026-06-18)
- Reference band: **73.25 to 75.50** / reference stop **70.32** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **70.32**
- Invalidation logic: loses the 20/50-day support cluster and fails below 70.32; deeper failure toward the 200-day would reset the setup to repair/watch-only.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### XLB
- Close: **51.81** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **49.84 to 51.68** *(current artifact layer 2026-06-18)
- Reference band: **49.84 to 51.68** / reference stop **48.81** (current artifact layer 2026-06-18; volatile canon sync)
- Explicit stop / invalidation: **48.81**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### XLC
- Close: **109.45** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **114.31 to 116.55** *(current artifact layer 2026-06-18)
- Reference band: **114.31 to 116.55** / reference stop **112.71** (current artifact layer 2026-06-18; volatile canon sync)
- Explicit stop / invalidation: **112.71**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### XLE
- Close: **53.77** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **56.35 to 58.04** *(current artifact layer 2026-06-18)
- Reference band: **56.35 to 58.04** / reference stop **54.83** (current artifact layer 2026-06-18; volatile canon sync)
- Explicit stop / invalidation: **54.83**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### XLF
- Reference band: **52.26 to 53.07** / reference stop **51.61** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **53.57** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **52.26 to 53.07** *(current artifact layer 2026-06-18)
- Explicit stop / invalidation: **51.61**; below this level the setup is fail-closed pending fresh review.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### XLI
- Close: **180.91** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Preferred entry band: **166.78 to 173.40** *(current artifact layer 2026-06-18)
- Reference band: **166.78 to 173.40** / reference stop **163.10** (current artifact layer 2026-06-18; volatile canon sync)
- Explicit stop / invalidation: **163.10**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.

### XOM
- Close: **137.81** *(technical refresh; 2026-06-18 close; current artifact layer)*********************************************************
- Stop-breached / invalidation: close **145.26** is below explicit stop **146.14** and below band low **150.24**; do not deploy, promote, size, or execute until fresh reclaim review clears the repair state.
- MA posture: **above 200d, below 20d and 50d**. The chart failed the refreshed band and remains below the short/intermediate trend stack.
- Support: **146.14** (explicit stop / urgent review line), then **141.97–143.92** (recent low zone / monthly artifact low)
- Resistance: **150.24** (bottom of refreshed band), then **154.84–158.44** (50-day / top of refreshed band)
- Preferred entry band: **150.24 to 158.44** *(current artifact layer 2026-06-18)
- Reference band: **150.24 to 158.44** / reference stop **146.14** (current artifact layer 2026-06-18; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Full historical/source-open text is archived; use the replacement proof before relying on stale narrative.
