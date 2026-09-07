# Execution Board

## Purpose and ownership boundary

This is the consolidated execution surface for the finance canon. It combines the pre-consolidation technical-entry and deployment-trigger layers into one parser-compatible note.

Owns:
- live action state and operational blocker / condition
- execution bands, stops, support/resistance, repair state, and invalidation logic
- explicit authority notes for owner approval, manual-only constraints, and no-automatic-execution limits

Does **not** own:
- durable company thesis and coverage membership; see [[04. Research/Coverage and Watchlist]]
- portfolio weights / sleeve sizing; see [[03. Portfolio/Portfolio Snapshot]] and [[07. Risk/Risk Rules]]
- automatic trading authority; this board is manual and owner-gated

## State vocabulary and rules

- **Deployable now** - gates line up on paper, price is in the approved zone, and owner/manual constraints are explicit.
- **Almost deployable** - thesis and structure are constructive, but one or more promotion, pullback, sizing, or timing conditions remain.
- **Wait / no chase** - quality may be intact, but entry is extended or timing-sensitive.
- **Watch-only** - tracked for thesis, sector, or read-through value; no execution entitlement.
- **Repair / do not touch** - prior setup failed or price is below stop / below key structure; new action requires reclaim plus fresh review.
- **Blocked** - a catalyst, earnings window, data-quality problem, or regime issue prevents normal action.

Rules:
- In-band does not equal deployable by itself.
- Owner approval does not override a broken stop, stale band, or near-term catalyst blocker.
- Reference bands refresh chart context only; they do not create trade, sizing, sleeve, approval, or execution authority.
- Watch-lane names cannot be silently promoted into execution-lane candidates.
- All execution remains manual-only unless Randall separately authorizes otherwise.

## Current execution table

| Ticker | Lane | Action state | Close/date | Band | Stop | Technical posture | Blocker/condition | Authority note | Source/freshness |
|---|---|---|---|---|---|---|---|---|---|
| ETN | Execution | **Deployable now** | 400.60 / 2026-05-29 | 382.90-401.36 | 362.67 | above 50d and 200d, below 20d | inside band 382.90-401.36; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. owner-approved setup remains in entry band at 400.6. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| JPM | Execution | **Almost deployable / below-band trigger not live** | 299.31 / 2026-05-29 | 300.47-305.27 | 293.02 | below all MAs | below band 300.47-305.27; trigger not live until reclaim or explicit owner-approved review. workflow state is ALMOST -- constructive but not yet promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| NVDA | Execution | **Promotion review / explicit decision required** | 211.14 / 2026-05-29 | 198.47-216.66 | 187.90 | above 50d and 200d, below 20d | inside band 198.47-216.66; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band at 211.14 -- explicit owner promotion review required before deployable-now status. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| GOOG | Execution | **Promotion review / explicit decision required** | 376.43 / 2026-05-29 | 357.91-381.38 | 339.61 | above 50d and 200d, below 20d | inside band 357.91-381.38; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band at 376.43 -- explicit owner promotion review required before deployable-now status. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| MSFT | Execution | **Almost deployable / above-band no-chase** | 450.24 / 2026-05-29 | 389.64-412.56 | 378.18 | above 20d and 50d, below 200d | above band 389.64-412.56; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| AMZN | Watch | **Watch-only / review-only** | 270.64 / 2026-05-29 | 252.27-267.19 | 244.81 | above all MAs -- bullish 20>50>200 stack | above band 252.27-267.19; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| VRT | Promotion review | **Promotion review / explicit decision required** | 315.71 / 2026-05-29 | 284.18-333.07 | 261.95 | above 50d and 200d, below 20d | inside band 284.18-333.07; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band at 315.71 -- portfolio-review only; separate owner model/sleeve/deployment decision required. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| CAT | Watch | **Watch-only / review-only** | 875.87 / 2026-05-29 | 811.65-866.48 | 784.25 | above 50d and 200d, below 20d | above band 811.65-866.48; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| LLY | Watch | **Watch-only / review-only** | 1105.00 / 2026-05-29 | 907.64-969.88 | 876.52 | above all MAs -- bullish 20>50>200 stack | above band 907.64-969.88; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| GS | Execution | **Almost deployable / above-band no-chase** | 1025.56 / 2026-05-29 | 913.96-966.83 | 882.04 | above all MAs -- bullish 20>50>200 stack | above band 913.96-966.83; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| BRK.B | Execution repair | **Do not touch / below-stop** | 474.48 / 2026-05-29 | 489.78-498.19 | 483.05 | below all MAs | Below 483.05 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. workflow state is REPAIR -- wait for setup to rebuild. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| XOM | Execution repair | **Do not touch / below-stop** | 145.26 / 2026-05-29 | 150.24-158.44 | 146.14 | above 200d, below 20d and 50d | Below 146.14 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. workflow state is REPAIR -- wait for setup to rebuild. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| LMT | Execution repair | **Do not touch / below-stop** | 530.45 / 2026-05-29 | 548.51-582.27 | 531.63 | above 20d and 200d, below 50d | Below 531.63 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. close 530.45 is below stop -- do not deploy. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| RTX | Watch repair | **Watch-only / near-stop repair** | 179.66 / 2026-05-29 | 183.01-193.23 | 177.91 | above 20d and 200d, below 50d | Near-stop repair/no-chase condition: close is within 1% of the 177.91 stop; require reclaim/fresh review before any deployment review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| CVX | Watch | **Watch-only / near-stop repair** | 182.46 / 2026-05-29 | 186.91-196.41 | 182.16 | above 200d, below 20d and 50d | Near-stop repair/no-chase condition: close is within 1% of the 182.16 stop; require reclaim/fresh review before any deployment review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| PLTR | Watch/speculative | **Watch-only / review-only** | 156.54 / 2026-05-29 | 137.37-149.53 | 131.29 | above 20d and 50d, below 200d | above band 137.37-149.53; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| AMD | Watch | **Watch-only / review-only** | 516.10 / 2026-05-29 | 295.33-342.53 | 271.73 | above all MAs -- bullish 20>50>200 stack | above band 295.33-342.53; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| LNG | Watch repair | **Do not touch / below-stop** | 224.86 / 2026-05-29 | 260.82-275.56 | 253.45 | below all MAs | Below 253.45 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 224.86 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| BKNG | Watch repair | **Do not touch / repair review** | 167.43 / 2026-05-29 | 164.05-170.91 | 155.97 | above 20d, below 50d and 200d | inside band 164.05-170.91; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. Repair state remains active until explicitly lifted by fresh review. watch lane only; no execution-board entitlement. in band at 167.43 but workflow state is REPAIR -- wait for setup to rebuild. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| LIN | Portfolio review / Materials sleeve | **Promotion review / explicit decision required** | 497.69 / 2026-05-29 | 497.11-506.11 | 487.17 | above 200d, below 20d and 50d | inside band 497.11-506.11; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band at 497.69 -- portfolio-review only; separate owner model/sleeve/deployment decision required. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| ECL | Watch / sector monitor | **Do not touch / below-stop** | 256.00 / 2026-05-29 | 271.22-278.98 | 265.01 | above 20d, below 50d and 200d | Below 265.01 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 256.0 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| VMC | Watch / sector monitor | **Do not touch / below-stop** | 282.92 / 2026-05-29 | 291.87-300.98 | 284.58 | above 20d and 50d, below 200d | Below 284.58 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 282.92 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| META | Portfolio review / watch lane | **Do not touch / below-stop** | 632.51 / 2026-05-29 | 672.60-693.91 | 655.55 | above 20d and 50d, below 200d | Below 655.55 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 632.51 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| NFLX | Watch / sector monitor | **Do not touch / below-stop** | 86.02 / 2026-05-29 | 102.56-105.46 | 100.24 | below all MAs | Below 100.24 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 86.02 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| TMUS | Watch / sector monitor | **Do not touch / below-stop** | 187.53 / 2026-05-29 | 213.01-220.38 | 207.11 | below all MAs | Below 207.11 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 187.53 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| PH | Portfolio review / watch lane | **Promotion review / explicit decision required** | 844.63 / 2026-05-29 | 851.36-908.98 | 819.35 | below all MAs | below band 851.36-908.98; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| GE | Watch / sector monitor | **Watch-only / review-only** | 323.76 / 2026-05-29 | 299.03-311.84 | 288.78 | above all MAs | above band 299.03-311.84; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| CME | Portfolio review / watch lane | **Do not touch / below-stop** | 273.54 / 2026-05-29 | 287.74-298.86 | 276.68 | below all MAs | Below 276.68 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 273.54 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| WMB | Watch / sector monitor | **Watch-only / review-only** | 71.39 / 2026-05-29 | 73.25-75.50 | 70.32 | above 200d, below 20d and 50d | below band 73.25-75.50; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| XLI | ETF monitor | **Watch-only / review-only** | 173.13 / 2026-05-29 | 166.78-173.40 | 163.10 | above all MAs -- bullish 20>50>200 stack | inside band 166.78-173.40; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| XLB | ETF monitor | **Watch-only / review-only** | 51.17 / 2026-05-29 | 49.84-51.68 | 48.81 | above all MAs -- bullish 20>50>200 stack | inside band 49.84-51.68; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| XLC | ETF monitor | **Watch-only / review-only** | 115.69 / 2026-05-29 | 114.31-116.55 | 112.71 | above 50d and 200d, below 20d | inside band 114.31-116.55; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| PAVE | ETF monitor | **Watch-only / review-only** | 56.31 / 2026-05-29 | 53.94-56.28 | 52.64 | above all MAs -- bullish 20>50>200 stack | above band 53.94-56.28; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| XLF | ETF monitor | **Do not touch / below-stop** | 51.58 / 2026-05-29 | 52.26-53.07 | 51.61 | above 20d and 50d, below 200d | Below 51.61 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 51.58 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| XLE | ETF monitor | **Watch-only / review-only** | 56.32 / 2026-05-29 | 56.35-58.04 | 54.83 | above 200d, below 20d and 50d | below band 56.35-58.04; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| ITA | ETF candidate / promotion-review | **Promotion review / explicit decision required** | 235.44 / 2026-05-29 | 212.15-223.44 | 205.88 | above all MAs -- bullish 20>50>200 stack | above band 212.15-223.44; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| VAW | ETF monitor | **Watch-only / review-only** | 232.57 / 2026-05-29 | 225.44-233.70 | 220.85 | above all MAs -- bullish 20>50>200 stack | inside band 225.44-233.70; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| VXUS | ETF monitor / international diversification | **Watch-only / review-only** | 86.06 / 2026-05-29 | 80.88-83.36 | 78.15 | above all MAs -- bullish 20>50>200 stack | above band 80.88-83.36; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-29; volatile canon sync 2026-05-29 |
| KTOS | Speculative / watch lane | **Watch-only / reference band defined** | 52.09 / 2026-05-15 | 80.79-85.20 | 77.27 | below reclaim structure | Speculative defense-tech monitor; current close is below reclaim band, so this is repair/reclaim context only. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
| SLV | Speculative / macro watch | **Watch-only / reference band defined** | 69.04 / 2026-05-15 | 64.07-72.34 | 60.31 | mixed / macro-linked | Macro metals hedge monitor; band is reference context and requires macro confirmation before any action proposal. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
| TLT | Macro watch | **Watch-only / reclaim reference** | 83.66 / 2026-05-15 | 86.60-87.41 | 85.96 | below reclaim structure | Duration/macro monitor; below reclaim band, rate-regime confirmation required before any action proposal. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
| SMCI | Speculative / watch lane | **Watch-only / reference band defined** | 31.04 / 2026-05-15 | 24.92-30.93 | 22.19 | volatile / below 200-day context | Speculative AI-infrastructure monitor; high volatility and below-200-day context keep it non-deployable without fresh review. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |

## Parser-compatible technical sections

### ECL
- Reference band: **271.22 to 278.98** / reference stop **265.01** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **256.00** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **253.80 / 261.86 / 270.64**
- MA posture: **above 20d, below 50d and 200d**.
- Preferred entry band: **271.22 to 278.98** *(current artifact layer 2026-05-29)
- Explicit stop / invalidation: **265.01**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 265.01 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 256.0 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### VMC
- Reference band: **291.87 to 300.98** / reference stop **284.58** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **282.92** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **276.61 / 280.05 / 290.74**
- MA posture: **above 20d and 50d, below 200d**.
- Preferred entry band: **291.87 to 300.98** *(current artifact layer 2026-05-29)
- Explicit stop / invalidation: **284.58**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 284.58 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 282.92 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### META
- Reference band: **672.60 to 693.91** / reference stop **655.55** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **632.51** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **613.33 / 618.53 / 665.83**
- MA posture: **above 20d and 50d, below 200d**.
- Preferred entry band: **672.60 to 693.91** *(current artifact layer 2026-05-29)
- Explicit stop / invalidation: **655.55**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 655.55 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 632.51 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### NFLX
- Reference band: **102.56 to 105.46** / reference stop **100.24** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **86.02** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **88.10 / 93.04 / 101.20**
- MA posture: **below all MAs**.
- Preferred entry band: **102.56 to 105.46** *(current artifact layer 2026-05-29)
- Explicit stop / invalidation: **100.24**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 100.24 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 86.02 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### TMUS
- Reference band: **213.01 to 220.38** / reference stop **207.11** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **187.53** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **191.43 / 196.29 / 210.81**
- MA posture: **below all MAs**.
- Preferred entry band: **213.01 to 220.38** *(current artifact layer 2026-05-29)
- Explicit stop / invalidation: **207.11**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 207.11 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 187.53 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### GE
- Reference band: **299.03 to 311.84** / reference stop **288.78** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **323.76** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **298.88 / 295.35 / 300.52**
- MA posture: **above all MAs**.
- Preferred entry band: **299.03 to 311.84** *(current artifact layer 2026-05-29)
- Explicit stop / invalidation: **288.78**; below this level the setup is fail-closed pending fresh review.
- Stance: **Watch-only / review-only**. above band 299.03-311.84; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### XLF
- Reference band: **52.26 to 53.07** / reference stop **51.61** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **51.58** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **51.51 / 51.01 / 52.28**
- MA posture: **above 20d and 50d, below 200d**.
- Preferred entry band: **52.26 to 53.07** *(current artifact layer 2026-05-29)
- Explicit stop / invalidation: **51.61**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 51.61 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 51.58 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---

### ETN
- Explicit stop: **362.67**
- Close: **400.60** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **401.43 / 392.78 / 362.99**
- MA posture: **above 50d and 200d, below 20d**.
- Support: **360.82** (preferred band low), then **340.89** (explicit stop)
- Resistance: **387.42 / 404.69 / 409.46** (50-day reclaim / top of preferred band / 20-day reclaim and no-chase ceiling)
- Preferred entry band: **382.90 to 401.36** *(current artifact layer 2026-05-29)
- Reference band: **382.90 to 401.36** / reference stop **362.67** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Deployable now**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **362.67**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the preferred band low and ultimately fails the explicit 341.01 stop.
- Stance: **Deployable now**. inside band 382.90-401.36; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. owner-approved setup remains in entry band at 400.6.
- Entry-distance context: **inside band 382.90-401.36** (close 400.60 vs band 382.90-401.36; technical refresh 2026-05-29).
- WF64 entry-band proposal preview: packet `post-close:ETN:capital-deployment-review:2026-05-16` is review-only; apply_allowed=false, owner_approval_granted=false, trade_or_account_action_allowed=false, and main-session final action is required.
- **POST-EARNINGS FOLLOW-UP.** The pre-print blocker has passed and owner promotion has landed. ETN is still the first capital-deployment priority in the review stack, but execution remains manual-only: no automatic execution and no chase above the written band.
- **Automated band maintenance:** 2026-05-26 eligible proposal applied: prior **356.99–400.66 / stop 337.14** → new **382.90–401.36 / stop 362.67**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### JPM
- Explicit stop: **293.02**
- Close: **299.31** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **303.27 / 302.49 / 303.56**
- MA posture: **below all MAs**.
- Support: **301.17** (near-term support / reference level), then **293.02** (current explicit stop / invalidation). Legacy/parser stop **286.81** is retained only as non-authoritative context.
- Historical trigger-review context: **306.82 to 318.12** was the 2026-05-16 owner-resolved trigger-review band, but the fresh 2026-05-22 artifact layer superseded it for current reference-band display. Do not treat either band as automatic deployable authority.
- Preferred / current reference entry band: **300.47 to 305.27** *(current artifact layer 2026-05-22)*.
- Reference stop / invalidation: **293.02** (current artifact layer 2026-05-22; volatile canon sync). **301.17** is not the formal stop.
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / below-band trigger not live**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **293.02**; below this level the setup is fail-closed pending fresh review.
- Stance: **Almost deployable / below-band trigger not live**. below band 300.47-305.27; trigger not live until reclaim or explicit owner-approved review. workflow state is ALMOST -- constructive but not yet promoted.
- Entry-distance context: **below band 300.47-305.27** (close 299.31 vs band 300.47-305.27; technical refresh 2026-05-29).
- Earnings: **July 14 (Q2 2026)**; no near-term earnings block, but the technical trigger is not live.
- **Fresh conflict resolution:** Current artifacts support **above-band wait / no-chase** against **300.47-305.27 / stop 293.02**. The old **306.82-318.12** trigger-review language is historical context only after the 2026-05-22 automated band maintenance.
- **Automated band maintenance:** 2026-05-22 eligible proposal applied: prior **306.82–318.12 / stop 301.17** → new **300.47–305.27 / stop 293.02**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### NVDA
- Explicit stop: **187.90**
- Close: **211.14** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **215.46 / 199.35 / 187.64**
- MA posture: **above 50d and 200d, below 20d**.
- Support: **209.12** (20-day / band-top area), then **192.23-185.73** (50-day / 200-day cluster)
- Resistance: **235.74** current extension zone, then any post-earnings higher-high attempt.
- Preferred entry band: **198.47 to 216.66** *(current artifact layer 2026-05-29)
- Reference band: **198.47 to 216.66** / reference stop **187.90** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **187.90**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses 190.10 and the MA cluster, then slips back under the breakout zone.
- Stance: **Promotion review / explicit decision required**. inside band 198.47-216.66; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band at 211.14 -- explicit owner promotion review required before deployable-now status.
- Entry-distance context: **inside band 198.47-216.66** (close 211.14 vs band 198.47-216.66; technical refresh 2026-05-29).
- Earnings: **Q1 FY2027 reported / interpreted.** Official SEC/NVIDIA 8-K evidence is captured in [[05. Intelligence/Earnings/NVDA Q1 FY2027 Post-Earnings Scorecard]]; the print confirmed AI infrastructure demand, but the stock remains above the written band, so stance stays **Almost deployable / above-band no-chase** pending post-print technical/positioning refresh. No deployment, sizing, owner-approval, or trade/account authority is created.
- **Automated band maintenance:** 2026-05-21 eligible proposal applied: prior **198.47–216.66 / stop 187.90** → new **198.47–216.66 / stop 187.90**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### GOOG
- Explicit stop: **339.61**
- Close: **376.43** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **387.64 / 345.05 / 299.44**
- MA posture: **above 50d and 200d, below 20d**.
- Support: **367.49-362.08** (20-day / top of the written band / first disciplined pullback zone), then **328.93** (50-day)
- Resistance: **397.17** current extension zone, then fresh post-print highs.
- Preferred entry band: **357.91 to 381.38** *(current artifact layer 2026-05-29)
- Reference band: **357.91 to 381.38** / reference stop **339.61** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **339.61**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the post-print breakout shelf and falls back under the 20-day / band support zone.
- Stance: **Promotion review / explicit decision required**. inside band 357.91-381.38; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band at 376.43 -- explicit owner promotion review required before deployable-now status.
- Entry-distance context: **inside band 357.91-381.38** (close 376.43 vs band 357.91-381.38; technical refresh 2026-05-29).
- **Automated band maintenance:** 2026-05-27 eligible proposal applied: prior **355.35–378.98 / stop 334.58** → new **357.91–381.38 / stop 339.61**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### MSFT
- Close: **450.24** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **416.97 / 402.06 / 456.42**
- MA posture: **above 20d and 50d, below 200d**.
- Support: **398.84-389.64** (50-day / lower working band), then **378.18** (explicit stop)
- Resistance: **412.56-417.45** (band ceiling / 20-day reclaim zone), then **462.35** (200-day)
- Preferred entry band: **389.64 to 412.56** *(current artifact layer 2026-05-29)
- Reference band: **389.64 to 412.56** / reference stop **378.18** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / above-band no-chase**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **378.18**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the recovery structure and fails back through the 50-day / band zone.
- Stance: **Almost deployable / above-band no-chase**. above band 389.64-412.56; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted.
- Entry-distance context: **above band 389.64-412.56** (close 450.24 vs band 389.64-412.56; technical refresh 2026-05-29).
- **Sequencing constraint:** direct Technology is already at the 25% cap in the draft model. MSFT deployment requires an explicit owner sequencing decision: reduce another Tech weight first, keep any MSFT tranche within verified headroom, or approve a written Tech-cap exception. No automatic sizing, sleeve, cash, or execution-entitlement change is authorized here.
- **Consolidation resolution:** owner-approved staged setup uses 389.64-412.56 / 378.18; below-200-day repair caveat limits sizing/tranche confidence.

---

### AMZN
- Close: **270.64** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **268.74 / 246.67 / 231.52**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Support: **247** (20-day), then **227** (200-day)
- Resistance: prior highs (confirm via chart)
- Preferred entry band: **252.27 to 267.19** *(current artifact layer 2026-05-29)
- Reference band: **252.27 to 267.19** / reference stop **244.81** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **244.81**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the 200-day and fails to recover.
- Stance: **Watch-only / review-only**. above band 252.27-267.19; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **above band 252.27-267.19** (close 270.64 vs band 252.27-267.19; technical refresh 2026-05-29).
- **Lane note:** keep AMZN technically visible for post-earnings follow-through, but it no longer owns weekday deployment-board cost while GOOG and MSFT already cover the large-cap quality sleeve.
- Earnings: **July 30 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### VRT
- Explicit stop: **261.95**
- Close: **315.71** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **339.69 / 307.36 / 211.23**
- MA posture: **above 50d and 200d, below 20d**.
- Support: **315** (20-day), then **282** (50-day)
- Resistance: confirm via chart
- Preferred entry band: **284.18 to 333.07** *(current artifact layer 2026-05-29)
- Reference band: **284.18 to 333.07** / reference stop **261.95** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **261.95**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the 20-day and breaks the uptrend structure.
- Stance: **Promotion review / explicit decision required**. inside band 284.18-333.07; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band at 315.71 -- portfolio-review only; separate owner model/sleeve/deployment decision required.
- Entry-distance context: **inside band 284.18-333.07** (close 315.71 vs band 284.18-333.07; technical refresh 2026-05-29).
- Earnings: **July 29 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**
- **Automated band maintenance:** 2026-05-29 eligible proposal applied: prior **284.18–333.07 / stop 261.95** → new **284.18–333.07 / stop 261.95**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### CAT
- Close: **875.87** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **893.17 / 814.04 / 633.64**
- MA posture: **above 50d and 200d, below 20d**.
- Support: **831** (20-day), then **760** (50-day)
- Resistance: prior high
- Preferred entry band: **811.65 to 866.48** *(current artifact layer 2026-05-29)
- Reference band: **811.65 to 866.48** / reference stop **784.25** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **784.25**
- Invalidation logic: loses the 50-day and breaks the uptrend.
- Stance: **Watch-only / review-only**. above band 811.65-866.48; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **above band 811.65-866.48** (close 875.87 vs band 811.65-866.48; technical refresh 2026-05-29).
- **Lane note:** CAT keeps technical visibility for post-print follow-through and sector read-through, but it no longer earns weekday execution-board ownership.
- Earnings: **August 4 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### LLY
- Close: **1105.00** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **1015.62 / 953.19 / 934.56**
- MA posture: **above all three MAs**, but the **20-day still sits below the 50-day**, so this is not a clean 20 > 50 > 200 trend-stack breakout.
- Support: **970** (top of the written band), then **943** (50-day)
- Resistance: prior high / confirm via chart
- Preferred entry band: **907.64 to 969.88** *(current artifact layer 2026-05-29)
- Reference band: **907.64 to 969.88** / reference stop **876.52** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **876.52**
- Invalidation logic: loses the written stop and fails the current healthcare watch-lane base.
- Stance: **Watch-only / review-only**. above band 907.64-969.88; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **above band 907.64-969.88** (close 1105.00 vs band 907.64-969.88; technical refresh 2026-05-29).
- **Lane note:** LLY now has explicit owner-layer technical levels for review-only competition against other diversification candidates, not deployable authority.
- Earnings: **August 5 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### GS
- Explicit stop: **882.04**
- Close: **1025.56** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **958.81 / 912.78 / 849.41**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Support: **924** (20-day / refreshed band top zone), then **873** (50-day)
- Resistance: current extension zone above the refreshed band top at **923.51**
- Preferred entry band: **913.96 to 966.83** *(current artifact layer 2026-05-29)
- Reference band: **913.96 to 966.83** / reference stop **882.04** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / above-band no-chase**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **882.04**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the 50-day and breaks the uptrend; do not chase while price remains above the refreshed band.
- Stance: **Almost deployable / above-band no-chase**. above band 913.96-966.83; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted.
- Entry-distance context: **above band 913.96-966.83** (close 1025.56 vs band 913.96-966.83; technical refresh 2026-05-29).
- Earnings: **July 14 (Q2 2026 provider-estimate calendar date)** — no near-term earnings risk, but cross-check company IR before treating as primary-confirmed.
- **Automated band maintenance:** 2026-05-28 eligible proposal applied: prior **913.96–966.83 / stop 882.04** → new **913.96–966.83 / stop 882.04**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### BRK.B
- Close: **474.48** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **478.81 / 477.08 / 490.52**
- MA posture: **below all MAs**. Ballast profile intact, but chart remains in repair until the 200-day is reclaimed and held.
- Support: **483.05** (reclaim-band stop), then **479.58** (50-day), then prior repair stop zone near **465.81**
- Resistance: **489.78** (200-day / reclaim trigger), then **498.19** (top of reclaim band)
- Preferred entry band: **489.78 to 498.19** *(current artifact layer 2026-05-29)
- Reference band: **489.78 to 498.19** / reference stop **483.05** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **483.05** for the reclaim setup; prior **465.81** remains the deeper repair failure reference.
- Invalidation logic: fails to reclaim/hold the 200-day or loses **483.05** after reclaim attempt; deeper weakness below **465.81** confirms continued repair.
- Stance: **Do not touch / below-stop**. Below 483.05 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. workflow state is REPAIR -- wait for setup to rebuild.
- Entry-distance context: **below band 489.78-498.19** (close 474.48 vs band 489.78-498.19; technical refresh 2026-05-29).

---

### XOM
- Close: **145.26** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **151.65 / 154.02 / 130.27**
- MA posture: **above 200d, below 20d and 50d**. The chart failed the refreshed band and remains below the short/intermediate trend stack.
- Support: **146.14** (explicit stop / urgent review line), then **141.97–143.92** (recent low zone / monthly artifact low)
- Resistance: **150.24** (bottom of refreshed band), then **154.84–158.44** (50-day / top of refreshed band)
- Preferred entry band: **150.24 to 158.44** *(current artifact layer 2026-05-29)
- Reference band: **150.24 to 158.44** / reference stop **146.14** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **146.14**
- Invalidation logic: loses the refreshed band and fails back below 146.14, or fails another 50-day reclaim with oil context rolling over. **May 11 produced an intraday stop breach and close-back-above-stop, so this must be treated as a formal repair review item before any oil-supported thesis refresh.**
- Stance: **Do not touch / below-stop**. Below 146.14 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. workflow state is REPAIR -- wait for setup to rebuild.
- Entry-distance context: **below band 150.24-158.44** (close 145.26 vs band 150.24-158.44; technical refresh 2026-05-29).

---

### LMT
- Close: **530.45** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **521.40 / 564.18 / 529.55**
- MA posture: **above 20d and 200d, below 50d**. The chart is broken — price is below every major MA and below the explicit stop.
- Support: confirm fresh support only after a new base forms.
- Resistance: **524.03-527.21** (200-day / 20-day reclaim zone), then **548.51** (bottom of written band) and **588.84** (50-day)
- Preferred entry band: **548.51 to 582.27** *(current artifact layer 2026-05-29)
- Reference band: **548.51 to 582.27** / reference stop **531.63** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **531.63**
- Invalidation logic: prior setup already failed; no new long thesis trigger until price rebuilds support and reclaims key MAs.
- Stance: **Do not touch / below-stop**. Below 531.63 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. close 530.45 is below stop -- do not deploy.
- Entry-distance context: **below band 548.51-582.27** (close 530.45 vs band 548.51-582.27; technical refresh 2026-05-29).
- **Defense-sector gap:** LMT's 10% draft weight is suspended while in repair. Owner decision required: reduce it to a holding placeholder and earmark the remainder for a future defense candidate, or formally accept KTOS-only 2% Defense exposure until LMT heals.
- **Consolidation resolution:** below-stop repair/do-not-touch state controls until stop reclaim and fresh base/review.

---

### RTX
- Close: **179.66** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **175.67 / 184.81 / 179.40**
- MA posture: **above 20d and 200d, below 50d**. Below the 200-day — structural weakness.
- Support: weak; needs to reclaim 185 area first
- Resistance: **178** (200-day), then **189–196** (20/50 cluster)
- Preferred entry band: **183.01 to 193.23** *(current artifact layer 2026-05-29)
- Reference band: **183.01 to 193.23** / reference stop **177.91** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / near-stop repair**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **177.91**
- Invalidation logic: name is below band and only marginally above the refreshed stop; prior setup remains in repair.
- Stance: **Watch-only / near-stop repair**. Near-stop repair/no-chase condition: close is within 1% of the 177.91 stop; require reclaim/fresh review before any deployment review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **below band 183.01-193.23** (close 179.66 vs band 183.01-193.23; technical refresh 2026-05-29).
- **Lane note:** RTX stays tracked for defense-sector read-through and possible later repair, but not for default weekday deployment upkeep.

---

### CVX
- Close: **182.46** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **186.93 / 190.68 / 166.79**
- MA posture: **above 200d, below 20d and 50d**.
- Support: **189** (20-day), then **186.91** (bottom of preferred band)
- Resistance: **193** (50-day), then **196.41** (top of preferred band)
- Preferred entry band: **186.91 to 196.41** *(current artifact layer 2026-05-29)
- Reference band: **186.91 to 196.41** / reference stop **182.16** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / near-stop repair**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **182.16**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses 182.16 and breaks back below the band / 20-day support cluster.
- Stance: **Watch-only / near-stop repair**. Near-stop repair/no-chase condition: close is within 1% of the 182.16 stop; require reclaim/fresh review before any deployment review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **below band 186.91-196.41** (close 182.46 vs band 186.91-196.41; technical refresh 2026-05-29).
- **Lane note:** use CVX for oil-major read-through versus XOM, not as a hidden second-energy promotion while XOM is still benched.
- Earnings: **July 31** *(next provider date after the May 1 print; treat as provisional until company IR confirms).*

---

### PLTR
- Close: **156.54** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **137.81 / 141.79 / 161.78**
- MA posture: **above 20d and 50d, below 200d**. Short-term bounce, longer-term repair is still incomplete.
- Support: **141.56** (20-day), then **138.60** (bottom of preferred band)
- Resistance: **145.18** (50-day), then **150.44** (top of preferred band)
- Preferred entry band: **137.37 to 149.53** *(current artifact layer 2026-05-29)
- Reference band: **137.37 to 149.53** / reference stop **131.29** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **131.29**
- Invalidation logic: loses 131.29 and fails the current rebound attempt.
- Stance: **Watch-only / review-only**. above band 137.37-149.53; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **above band 137.37-149.53** (close 156.54 vs band 137.37-149.53; technical refresh 2026-05-29).
- **Lane note:** do not treat in-band status as deployment permission. This is a watch-lane name and post-May 4 earnings monitor.
- **Post-earnings status:** reported May 4; use it as read-through evidence only unless a later owner review promotes the setup.

---

### AMD
- Close: **516.10** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **440.11 / 328.15 / 237.58**
- MA posture: **above all MAs -- bullish 20>50>200 stack**. Strong structure, but far above the written zone.
- Support: **311.80** (top of preferred band / first disciplined pullback zone), then **284.89** (20-day)
- Resistance: **current extension zone / recent highs** *(exact upside shelf is not pinned from this artifact layer)*
- Preferred entry band: **295.33 to 342.53** *(current artifact layer 2026-05-29)
- Reference band: **295.33 to 342.53** / reference stop **271.73** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **271.73**
- Invalidation logic: loses the pullback zone and breaks back through 271.73 after the earnings window.
- Stance: **Watch-only / review-only**. above band 295.33-342.53; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **above band 295.33-342.53** (close 516.10 vs band 295.33-342.53; technical refresh 2026-05-29).
- **Lane note:** treat this as a post-earnings tactical monitor that informs the AI sleeve, not as a quiet execution-board promotion.
- **Post-earnings status:** reported May 5; use the scorecard / read-through layer for interpretation and do not promote from watch-lane without owner review.

---

### LNG
- Close: **224.86** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **245.17 / 261.12 / 229.14**
- MA posture: **below all MAs**. The May 1 constructive setup is no longer intact.
- Support: no live support from the old band; next repair reference is the **229.19** 200-day after the stop breach.
- Resistance: **253.45** (lost stop / first repair line), then **260.82** (bottom of the old preferred band), then **275.56** (top of the old band)
- Preferred entry band: **260.82 to 275.56** *(current artifact layer 2026-05-29)
- Reference band: **260.82 to 275.56** / reference stop **253.45** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **253.45**
- Invalidation logic: the 2026-05-11 close below 253.45 invalidates the prior watch-lane setup. Any future setup requires a stop reclaim and fresh band review, not automatic reuse of the old band.
- Stance: **Do not touch / below-stop**. Below 253.45 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 224.86 is below stop -- watch-lane monitor only, not execution-board entitled.
- Entry-distance context: **below band 260.82-275.56** (close 224.86 vs band 260.82-275.56; technical refresh 2026-05-29).
- **Lane note:** useful for LNG-complex read-through and sector timing, but keep it separate from the XOM decision lane and do not promote from this state without explicit owner review.
- Earnings: provider-estimated next print **2026-08-06** in current artifacts; not primary-confirmed.
- **Consolidation resolution:** below-stop repair/do-not-touch state controls until stop reclaim and fresh base/review.

---

### BKNG
- Close: **167.43** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **162.33 / 170.43 / 194.15**
- MA posture: **above 20d, below 50d and 200d**. This is repair mode, not an entry setup.
- Support: **164.05–170.91** (watch/rebuild zone only), then **161–164** (manual support area from BKNG review)
- Resistance: **174–177** (repair/reclaim zone), then **198.30** (200-day / machine reclaim reference)
- Preferred entry band: **164.05 to 170.91** *(current artifact layer 2026-05-29)
- Reference band: **164.05 to 170.91** / reference stop **155.97** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / repair review**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **155.97**
- Invalidation logic: fails the 155.97 explicit stop or loses the 161–164 support area without reclaiming 174–177.
- Stance: **Do not touch / repair review**. inside band 164.05-170.91; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. Repair state remains active until explicitly lifted by fresh review. watch lane only; no execution-board entitlement. in band at 167.43 but workflow state is REPAIR -- wait for setup to rebuild.
- Entry-distance context: **inside band 164.05-170.91** (close 167.43 vs band 164.05-170.91; technical refresh 2026-05-29).
- **Catalyst state:** earnings state is now **CLEAR** in `tmp/band-proposals.json` (`days_to_earnings=80`) from a **2026-07-29 provider estimate** in `tmp/earnings-calendar.json`; this is not primary-confirmed.
- **Lane note:** BKNG is an accepted repair-mode blocker / manual wait-state. Do not apply the machine-suggested reclaim band as a live execution band and do not promote without explicit owner review.

### LIN
- Close: **506.07** *(technical refresh; 2026-05-19 close; current artifact layer)*
- 20 / 50 / 200-day: **504.34 / 498.14 / 461.95**
- MA posture: **above all MAs -- bullish 20 > 50 > 200 stack**. Structure is constructive, but price is at the top edge of the written band.
- Support: **504.34-497.11** (20-day / lower written band pullback cluster), then **487.17** (explicit stop / invalidation), then **461.95** (200-day deeper trend support)
- Resistance: **506.11** (written band ceiling / no-chase line), then **515** extension reference requiring fresh review.
- Preferred entry band: **497.11 to 506.11** (formal Materials sleeve planning band; not execution authority)
- Reference band: **493.46 to 508.86** / reference stop **481.03** (weekly reference refresh 2026-05-22; KELTNER_MA_CONSTRAINED / NEAR_BAND; data as of 2026-05-22)
- Reference-band authority: **reference only / no execution entitlement — watch/reference lane**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **487.17**
- Invalidation logic: loses the 50-day / lower-band support zone and fails below 487.17; deeper failure toward the 200-day resets the setup to repair/watch-only.
- Stance: **Promotion review / formal Materials starter-sizing plan; top-of-band no-chase**. Randall approved promotion into a formal Materials sleeve / starter-sizing lane on 2026-05-19 after the LIN owner-review packet. This creates workspace model/sleeve planning context only, not deployment or order authority.
- Starter-sizing context: **0% active / 3% conditional planning weight / $200-$350 starter zone** under the $10k capital framework. This is not deployed capital and does not authorize any cash movement or order.
- Entry-distance context: **inside the preferred band but effectively at the upper edge**; do not chase above 506.11 without fresh band review.
- Promotion review: **Promoted for formal Materials sleeve/starter-sizing planning**. Fundamental quality and official Q1 evidence are sufficient for planning; premium valuation and deteriorating Materials sector leadership require discipline before any action packet.
- Authority: workspace sleeve/sizing planning only; no deployment, cash movement, paper/live order, brokerage/account action, external execution entitlement, or owner-approval inference.

---

### CME
- Close: **273.54** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **288.79 / 292.95 / 277.37**
- MA posture: **below all MAs**. Constructive, though not a clean 20 > 50 > 200 stack because the 20-day sits below the 50-day.
- Support: **296.93** (50-day / near-term support), then **287.74** (20-day / lower band reference), then **276.68** (200-day)
- Resistance: **298.86-300** (current close / round-number test), then **305** *(extension reference; confirm on next chart refresh)*
- Preferred entry band: **287.74 to 298.86** *(current artifact layer 2026-05-29)
- Reference band: **287.74 to 298.86** / reference stop **276.68** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **276.68**
- Invalidation logic: loses the 20-day/50-day cluster and fails the 200-day at 276.68.
- Stance: **Do not touch / below-stop**. Below 276.68 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 273.54 is below stop -- watch-lane monitor only, not execution-board entitled.
- Entry-distance context: **below band 287.74-298.86** (close 273.54 vs band 287.74-298.86; technical refresh 2026-05-29).
- Promotion review: **Technically eligible for deeper review, not promoted**. Treat as a financial-infrastructure diversifier candidate, not a hidden third Financials allocation.
- Authority: levels are for review only; no deployment, sizing, sleeve, cash, execution-entitlement, account, or trade authority.

---

### WMB
- Close: **71.39** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **75.60 / 73.77 / 65.02**
- MA posture: **above 200d, below 20d and 50d**. Trend is strong, but price is already extended above the preferred pullback zone.
- Support: **73.82-73.25** (20/50-day pullback cluster), then **64.18** (200-day / deep trend support)
- Resistance: **77.72** (current extension zone), then **80** *(round-number extension reference; confirm on next chart refresh)*
- Preferred entry band: **73.25 to 75.50** *(current artifact layer 2026-05-29)
- Reference band: **73.25 to 75.50** / reference stop **70.32** (current artifact layer 2026-05-29; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **70.32**
- Invalidation logic: loses the 20/50-day support cluster and fails below 70.32; deeper failure toward the 200-day would reset the setup to repair/watch-only.
- Stance: **Watch-only / review-only**. below band 73.25-75.50; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **below band 73.25-75.50** (close 71.39 vs band 73.25-75.50; technical refresh 2026-05-29).
- Promotion review: **Constructive but not promoted**. Energy infrastructure could diversify XOM spot-beta exposure, but rate sensitivity, project/regulatory risk, income-sleeve fit, and owner promotion are required first.
- Authority: levels are for review only; no deployment, sizing, sleeve, cash, execution-entitlement, account, or trade authority.

---

## Freshness and migration note

- Created: **2026-05-13** as Phase 1 consolidation.
- Source notes copied unchanged to `09. Archive/Finance Canon/2026-05-13 pre-consolidation/` before consolidation.
- Old Technical Entry / Deployment Trigger / Watchlist / Coverage Universe notes are now redirect stubs after WF62 consumer migration.
- Live script ownership now expects `03. Portfolio/Execution Board.md` for execution/action/technical state and `04. Research/Coverage and Watchlist.md` for universe/thesis/watchlist state.
- Bounded band/status sync applied **2026-05-13** for AMZN, RTX, PLTR, AMD, BKNG and bounded NVDA review; this did not grant trade, sizing, sleeve, cash, risk-rule, execution-entitlement, or owner-approval authority.

---

### PH
- Close: **844.63** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **869.33 / 911.06 / 862.97**
- MA posture: **below all MAs**.
- Preferred entry band: **851.36 to 908.98** *(current artifact layer 2026-05-29)
- Reference band: **851.36 to 908.98** / reference stop **819.35** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **819.35**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Stance: **Promotion review / explicit decision required**. below band 851.36-908.98; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### ITA
- Close: **235.44** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **223.78 / 223.74 / 218.09**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Preferred entry band: **212.15 to 223.44** *(current artifact layer 2026-05-29)
- Reference band: **212.15 to 223.44** / reference stop **205.88** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **205.88**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Stance: **Promotion review / explicit decision required**. above band 212.15-223.44; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### VXUS
- Close: **86.06** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **84.52 / 81.66 / 76.69**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Preferred entry band: **80.88 to 83.36** *(current artifact layer 2026-05-29)
- Reference band: **80.88 to 83.36** / reference stop **78.15** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **78.15**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Stance: **Watch-only / review-only**. above band 80.88-83.36; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### PAVE
- Close: **56.31** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **56.14 / 54.37 / 50.34**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Preferred entry band: **53.94 to 56.28** *(current artifact layer 2026-05-29)
- Reference band: **53.94 to 56.28** / reference stop **52.64** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **52.64**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Stance: **Watch-only / review-only**. above band 53.94-56.28; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### VAW
- Close: **232.57** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **230.98 / 229.72 / 215.83**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Preferred entry band: **225.44 to 233.70** *(current artifact layer 2026-05-29)
- Reference band: **225.44 to 233.70** / reference stop **220.85** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **220.85**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Stance: **Watch-only / review-only**. inside band 225.44-233.70; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### XLB
- Close: **51.17** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **51.07 / 50.78 / 47.38**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Preferred entry band: **49.84 to 51.68** *(current artifact layer 2026-05-29)
- Reference band: **49.84 to 51.68** / reference stop **48.81** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **48.81**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Stance: **Watch-only / review-only**. inside band 49.84-51.68; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### XLC
- Close: **115.69** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **116.31 / 114.92 / 114.87**
- MA posture: **above 50d and 200d, below 20d**.
- Preferred entry band: **114.31 to 116.55** *(current artifact layer 2026-05-29)
- Reference band: **114.31 to 116.55** / reference stop **112.71** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **112.71**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Stance: **Watch-only / review-only**. inside band 114.31-116.55; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### XLE
- Close: **56.32** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **58.23 / 58.32 / 49.52**
- MA posture: **above 200d, below 20d and 50d**.
- Preferred entry band: **56.35 to 58.04** *(current artifact layer 2026-05-29)
- Reference band: **56.35 to 58.04** / reference stop **54.83** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **54.83**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Stance: **Watch-only / review-only**. below band 56.35-58.04; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### XLI
- Close: **173.13** *(technical refresh; 2026-05-29 close; current artifact layer)******************************
- 20 / 50 / 200-day: **172.87 / 169.93 / 160.80**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Preferred entry band: **166.78 to 173.40** *(current artifact layer 2026-05-29)
- Reference band: **166.78 to 173.40** / reference stop **163.10** (current artifact layer 2026-05-29; volatile canon sync)
- Explicit stop / invalidation: **163.10**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Stance: **Watch-only / review-only**. inside band 166.78-173.40; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
