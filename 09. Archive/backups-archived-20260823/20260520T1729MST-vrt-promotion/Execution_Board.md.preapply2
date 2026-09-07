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
| ETN | Execution | **Deployable now** | 379.69 / 2026-05-20 | 358.82-402.93 | 338.77 | above 200d, below 20d and 50d | inside band 358.82-402.93; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. owner-approved setup remains in entry band at 379.69. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| JPM | Execution | **Near-stop repair/no-chase / trigger not live** | 301.98 / 2026-05-20 | 306.82-318.12 | 301.17 | above 50d, below 20d and 200d | Near-stop repair/no-chase condition: close is within 1% of the 301.17 stop; require reclaim/fresh review before any deployment review. workflow state is ALMOST -- constructive but not yet promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| NVDA | Execution | **Almost deployable / above-band no-chase** | 223.47 / 2026-05-20 | 197.01-210.84 | 190.10 | above all MAs -- bullish 20>50>200 stack | above band 197.01-210.84; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| GOOG | Execution | **Almost deployable / above-band no-chase** | 384.90 / 2026-05-20 | 355.35-378.98 | 334.58 | above all MAs -- bullish 20>50>200 stack | above band 355.35-378.98; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| MSFT | Execution | **Almost deployable / above-band no-chase** | 421.06 / 2026-05-20 | 389.64-412.56 | 378.18 | above 20d and 50d, below 200d | above band 389.64-412.56; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| AMZN | Watch | **Watch-only / review-only** | 265.01 / 2026-05-20 | 252.27-267.19 | 244.81 | above 50d and 200d, below 20d | inside band 252.27-267.19; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| VRT | Watch/research | **Watch / Research Needed** | 315.67 / 2026-05-20 | 306.85-338.33 | 291.11 | above 50d and 200d, below 20d | inside band 306.85-338.33; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band, but this execution setup remains watch-only until it is intentionally promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| CAT | Watch | **Watch-only / review-only** | 872.56 / 2026-05-20 | 811.65-866.48 | 784.25 | above 50d and 200d, below 20d | above band 811.65-866.48; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| LLY | Watch | **Watch-only / review-only** | 1018.87 / 2026-05-20 | 907.64-969.88 | 876.52 | above all MAs -- bullish 20>50>200 stack | above band 907.64-969.88; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| GS | Execution | **Almost deployable / above-band no-chase** | 982.12 / 2026-05-20 | 894.64-935.77 | 866.76 | above all MAs -- bullish 20>50>200 stack | above band 894.64-935.77; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| BRK.B | Execution repair | **Do not touch / below-stop** | 480.90 / 2026-05-20 | 489.78-498.19 | 483.05 | above 20d and 50d, below 200d | Below 483.05 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. workflow state is REPAIR -- wait for setup to rebuild. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| XOM | Execution repair | **Do not touch / repair review** | 156.28 / 2026-05-20 | 150.24-158.44 | 146.14 | above all MAs | inside band 150.24-158.44; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. Repair state remains active until explicitly lifted by fresh review. in band at 156.28 but workflow state is REPAIR -- wait for setup to rebuild. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| LMT | Execution repair | **Do not touch / below-stop** | 522.59 / 2026-05-20 | 548.51-582.27 | 531.63 | above 20d, below 50d and 200d | Below 531.63 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. close 522.59 is below stop -- do not deploy. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| RTX | Watch repair | **Do not touch / below-stop** | 174.85 / 2026-05-20 | 183.01-193.23 | 177.91 | below all MAs | Below 177.91 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 174.85 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| CVX | Watch | **Watch-only / review-only** | 191.33 / 2026-05-20 | 186.91-196.41 | 182.16 | above 20d and 200d, below 50d | inside band 186.91-196.41; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| PLTR | Watch/speculative | **Watch-only / review-only** | 137.15 / 2026-05-20 | 137.37-149.53 | 131.29 | below all MAs | below band 137.37-149.53; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| AMD | Watch | **Watch-only / review-only** | 447.58 / 2026-05-20 | 295.33-342.53 | 271.73 | above all MAs -- bullish 20>50>200 stack | above band 295.33-342.53; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| LNG | Watch repair | **Do not touch / below-stop** | 243.66 / 2026-05-20 | 260.82-275.56 | 253.45 | above 200d, below 20d and 50d | Below 253.45 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 243.66 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| BKNG | Watch repair | **Watch-only / near-stop repair** | 156.95 / 2026-05-20 | 164.05-170.91 | 155.97 | below all MAs | Near-stop repair/no-chase condition: close is within 1% of the 155.97 stop; require reclaim/fresh review before any deployment review. Repair state remains active until explicitly lifted by fresh review. watch lane only; no execution-board entitlement. workflow state is REPAIR -- wait for setup to rebuild. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| LIN | Portfolio review / Materials sleeve | **Promotion review / explicit decision required** | 506.63 / 2026-05-20 | 497.11-506.11 | 487.17 | above all MAs -- bullish 20>50>200 stack | above band 497.11-506.11; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. portfolio-review only -- wait for band reclaim or explicit owner model/sleeve/deployment decision. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| ECL | Watch / sector monitor | **Do not touch / below-stop** | 248.64 / 2026-05-20 | 271.22-278.98 | 265.01 | below all MAs | Below 265.01 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 248.64 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| VMC | Watch / sector monitor | **Do not touch / below-stop** | 263.26 / 2026-05-20 | 291.87-300.98 | 284.58 | below all MAs | Below 284.58 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 263.26 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| META | Portfolio review / watch lane | **Do not touch / below-stop** | 605.06 / 2026-05-20 | 672.60-693.91 | 655.55 | below all MAs | Below 655.55 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 605.06 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| NFLX | Watch / sector monitor | **Do not touch / below-stop** | 88.09 / 2026-05-20 | 102.56-105.46 | 100.24 | below all MAs | Below 100.24 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 88.09 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| TMUS | Watch / sector monitor | **Do not touch / below-stop** | 190.16 / 2026-05-20 | 213.01-220.38 | 207.11 | below all MAs | Below 207.11 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 190.16 is below stop -- watch-lane monitor only, not execution-board entitled. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| PH | Portfolio review / watch lane | **Promotion review / explicit decision required** | 859.44 / 2026-05-20 | 851.36-908.98 | 819.35 | above 200d, below 20d and 50d | inside band 851.36-908.98; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band at 859.44 -- portfolio-review only; separate owner model/sleeve/deployment decision required. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| GE | Watch / sector monitor | **Watch-only / review-only** | 300.17 / 2026-05-20 | 299.03-311.84 | 288.78 | above all MAs | inside band 299.03-311.84; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| CME | Portfolio review / watch lane | **Promotion review / explicit decision required** | 290.12 / 2026-05-20 | 287.74-298.86 | 276.68 | above 20d and 200d, below 50d | inside band 287.74-298.86; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band at 290.12 -- portfolio-review only; separate owner model/sleeve/deployment decision required. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| WMB | Watch / sector monitor | **Watch-only / review-only** | 77.88 / 2026-05-20 | 73.25-75.50 | 70.32 | above all MAs -- bullish 20>50>200 stack | above band 73.25-75.50; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| XLI | ETF monitor | **Watch-only / review-only** | 170.73 / 2026-05-20 | 166.78-173.40 | 163.10 | above 50d and 200d, below 20d | inside band 166.78-173.40; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| XLB | ETF monitor | **Watch-only / review-only** | 49.72 / 2026-05-20 | 49.84-51.68 | 48.81 | above 200d, below 20d and 50d | below band 49.84-51.68; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| XLC | ETF monitor | **Watch-only / review-only** | 116.10 / 2026-05-20 | 114.31-116.55 | 112.71 | above 50d and 200d, below 20d | inside band 114.31-116.55; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| PAVE | ETF monitor | **Watch-only / review-only** | 54.49 / 2026-05-20 | 53.94-56.28 | 52.64 | above 50d and 200d, below 20d | inside band 53.94-56.28; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| XLF | ETF monitor | **Watch-only / near-stop repair** | 51.66 / 2026-05-20 | 52.26-53.07 | 51.61 | above 20d and 50d, below 200d | Near-stop repair/no-chase condition: close is within 1% of the 51.61 stop; require reclaim/fresh review before any deployment review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| XLE | ETF monitor | **Watch-only / review-only** | 59.80 / 2026-05-20 | 56.35-58.04 | 54.83 | above all MAs | above band 56.35-58.04; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| ITA | ETF candidate / promotion-review | **Promotion review / explicit decision required** | 223.28 / 2026-05-20 | 212.15-223.44 | 205.88 | above 20d and 200d, below 50d | inside band 212.15-223.44; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band at 223.28 -- portfolio-review only; separate owner model/sleeve/deployment decision required. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| VAW | ETF monitor | **Watch-only / review-only** | 225.01 / 2026-05-20 | 225.44-233.70 | 220.85 | above 200d, below 20d and 50d | below band 225.44-233.70; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| VXUS | ETF monitor / international diversification | **Watch-only / review-only** | 84.17 / 2026-05-20 | 80.88-83.36 | 78.15 | above all MAs -- bullish 20>50>200 stack | above band 80.88-83.36; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet. | Volatile canon freshness sync only; no automatic execution, no inferred owner approval, no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-check.json 2026-05-20; volatile canon sync 2026-05-20 |
| KTOS | Speculative / watch lane | **Watch-only / reference band defined** | 52.09 / 2026-05-15 | 80.79-85.20 | 77.27 | below reclaim structure | Speculative defense-tech monitor; current close is below reclaim band, so this is repair/reclaim context only. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
| SLV | Speculative / macro watch | **Watch-only / reference band defined** | 69.04 / 2026-05-15 | 64.07-72.34 | 60.31 | mixed / macro-linked | Macro metals hedge monitor; band is reference context and requires macro confirmation before any action proposal. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
| TLT | Macro watch | **Watch-only / reclaim reference** | 83.66 / 2026-05-15 | 86.60-87.41 | 85.96 | below reclaim structure | Duration/macro monitor; below reclaim band, rate-regime confirmation required before any action proposal. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
| SMCI | Speculative / watch lane | **Watch-only / reference band defined** | 31.04 / 2026-05-15 | 24.92-30.93 | 22.19 | volatile / below 200-day context | Speculative AI-infrastructure monitor; high volatility and below-200-day context keep it non-deployable without fresh review. | Reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |

## Parser-compatible technical sections

### ECL
- Reference band: **271.22 to 278.98** / reference stop **265.01** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **248.64** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **256.62 / 263.76 / 271.03**
- MA posture: **below all MAs**.
- Preferred entry band: **271.22 to 278.98** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **265.01**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 265.01 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 248.64 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### VMC
- Reference band: **291.87 to 300.98** / reference stop **284.58** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **263.26** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **283.94 / 279.71 / 291.68**
- MA posture: **below all MAs**.
- Preferred entry band: **291.87 to 300.98** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **284.58**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 284.58 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 263.26 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### META
- Reference band: **672.60 to 693.91** / reference stop **655.55** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **605.06** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **624.93 / 619.29 / 670.22**
- MA posture: **below all MAs**.
- Preferred entry band: **672.60 to 693.91** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **655.55**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 655.55 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 605.06 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### NFLX
- Reference band: **102.56 to 105.46** / reference stop **100.24** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **88.09** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **89.57 / 93.91 / 102.16**
- MA posture: **below all MAs**.
- Preferred entry band: **102.56 to 105.46** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **100.24**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 100.24 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 88.09 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### TMUS
- Reference band: **213.01 to 220.38** / reference stop **207.11** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **190.16** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **191.74 / 199.07 / 212.35**
- MA posture: **below all MAs**.
- Preferred entry band: **213.01 to 220.38** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **207.11**; below this level the setup is fail-closed pending fresh review.
- Stance: **Do not touch / below-stop**. Below 207.11 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 190.16 is below stop -- watch-lane monitor only, not execution-board entitled.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### GE
- Reference band: **299.03 to 311.84** / reference stop **288.78** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **300.17** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **290.55 / 294.50 / 299.32**
- MA posture: **above all MAs**.
- Preferred entry band: **299.03 to 311.84** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **288.78**; below this level the setup is fail-closed pending fresh review.
- Stance: **Watch-only / review-only**. inside band 299.03-311.84; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---
### XLF
- Reference band: **52.26 to 53.07** / reference stop **51.61** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / near-stop repair**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Close: **51.66** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **51.56 / 50.69 / 52.27**
- MA posture: **above 20d and 50d, below 200d**.
- Preferred entry band: **52.26 to 53.07** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **51.61**; below this level the setup is fail-closed pending fresh review.
- Stance: **Watch-only / near-stop repair**. Near-stop repair/no-chase condition: close is within 1% of the 51.61 stop; require reclaim/fresh review before any deployment review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Authority: reference-only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority.

---

### ETN
- Explicit stop: **338.77**
- Close: **379.69** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **407.94 / 387.87 / 361.77**
- MA posture: **above 200d, below 20d and 50d**.
- Support: **360.82** (preferred band low), then **340.89** (explicit stop)
- Resistance: **387.42 / 404.69 / 409.46** (50-day reclaim / top of preferred band / 20-day reclaim and no-chase ceiling)
- Preferred entry band: **358.82 to 402.93** *(current artifact layer 2026-05-20)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, paper/live order, or execution authority.
- Explicit stop / invalidation: **338.77**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the preferred band low and ultimately fails the explicit 341.01 stop.
- Stance: **Deployable now**. inside band 358.82-402.93; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. owner-approved setup remains in entry band at 379.69.
- Entry-distance context: **inside band 358.82-402.93** (close 379.69 vs band 358.82-402.93; technical refresh 2026-05-20).
- WF64 entry-band proposal preview: packet `post-close:ETN:capital-deployment-review:2026-05-16` is review-only; apply_allowed=false, owner_approval_granted=false, trade_or_account_action_allowed=false, and main-session final action is required.
- **POST-EARNINGS FOLLOW-UP.** The pre-print blocker has passed and owner promotion has landed. ETN is still the first capital-deployment priority in the review stack, but execution remains manual-only: no automatic execution and no chase above the written band.
- **Automated band maintenance:** 2026-05-20 eligible proposal applied: prior **358.82–402.93 / stop 338.77** → new **358.82–402.93 / stop 338.77**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### JPM
- Close: **301.98** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **305.98 / 300.38 / 303.08**
- MA posture: **above 50d, below 20d and 200d**.
- Support: **301.17** (near-term invalidation/reference stop), then **286.81** (legacy/parser explicit stop retained only as non-authoritative context)
- Resistance / trigger zone: **306.82 to 318.12** is the owner-resolved authoritative JPM trigger-review band. Older parser band **294.57 to 308.54** is legacy/non-authoritative and must not be treated as deployable-now by itself.
- Preferred entry band: **306.82 to 318.12** *(current artifact layer 2026-05-20)
- Reference band: **306.82 to 318.12** / reference stop **301.17** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Near-stop repair/no-chase / trigger not live**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **301.17**; below this level the setup is fail-closed pending fresh review.
- Stance: **Near-stop repair/no-chase / trigger not live**. Near-stop repair/no-chase condition: close is within 1% of the 301.17 stop; require reclaim/fresh review before any deployment review. workflow state is ALMOST -- constructive but not yet promoted.
- Entry-distance context: **below band 306.82-318.12** (close 301.98 vs band 306.82-318.12; technical refresh 2026-05-20).
- Earnings: **July 14 (Q2 2026)**; no near-term earnings block, but the technical trigger is not live.
- **Consolidation resolution:** Randall resolved on 2026-05-16 that **306.82-318.12** is authoritative for JPM right now, with **301.17** as near-term invalidation/reference stop. Dashboard/deployment surfaces must not render JPM deployable from the lower parser band.

---

### NVDA
- Close: **223.47** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **213.40 / 195.49 / 186.63**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Support: **209.12** (20-day / band-top area), then **192.23-185.73** (50-day / 200-day cluster)
- Resistance: **235.74** current extension zone, then any post-earnings higher-high attempt.
- Preferred entry band: **197.01 to 210.84** *(current artifact layer 2026-05-20)
- Reference band: **197.01 to 210.84** / reference stop **190.10** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / above-band no-chase**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **190.10**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses 190.10 and the MA cluster, then slips back under the breakout zone.
- Stance: **Almost deployable / above-band no-chase**. above band 197.01-210.84; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted.
- Entry-distance context: **above band 197.01-210.84** (close 223.47 vs band 197.01-210.84; technical refresh 2026-05-20).
- Earnings: **Q1 FY2027 reported / interpreted.** Official SEC/NVIDIA 8-K evidence is captured in [[05. Intelligence/Earnings/NVDA Q1 FY2027 Post-Earnings Scorecard]]; the print confirmed AI infrastructure demand, but the stock remains above the written band, so stance stays **Almost deployable / above-band no-chase** pending post-print technical/positioning refresh. No deployment, sizing, owner-approval, or trade/account authority is created.

---

### GOOG
- Explicit stop: **334.58**
- Close: **384.90** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **378.15 / 335.82 / 293.94**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Support: **367.49-362.08** (20-day / top of the written band / first disciplined pullback zone), then **328.93** (50-day)
- Resistance: **397.17** current extension zone, then fresh post-print highs.
- Preferred entry band: **355.35 to 378.98** *(current artifact layer 2026-05-20)
- Reference band: **355.35 to 378.98** / reference stop **334.58** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / above-band no-chase**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **334.58**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the post-print breakout shelf and falls back under the 20-day / band support zone.
- Stance: **Almost deployable / above-band no-chase**. above band 355.35-378.98; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted.
- Entry-distance context: **above band 355.35-378.98** (close 384.90 vs band 355.35-378.98; technical refresh 2026-05-20).
- **Automated band maintenance:** 2026-05-20 eligible proposal applied: prior **354.75–378.04 / stop 333.40** → new **355.35–378.98 / stop 334.58**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### MSFT
- Close: **421.06** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **416.75 / 399.82 / 460.30**
- MA posture: **above 20d and 50d, below 200d**.
- Support: **398.84-389.64** (50-day / lower working band), then **378.18** (explicit stop)
- Resistance: **412.56-417.45** (band ceiling / 20-day reclaim zone), then **462.35** (200-day)
- Preferred entry band: **389.64 to 412.56** *(current artifact layer 2026-05-20)
- Reference band: **389.64 to 412.56** / reference stop **378.18** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / above-band no-chase**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **378.18**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the recovery structure and fails back through the 50-day / band zone.
- Stance: **Almost deployable / above-band no-chase**. above band 389.64-412.56; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted.
- Entry-distance context: **above band 389.64-412.56** (close 421.06 vs band 389.64-412.56; technical refresh 2026-05-20).
- **Sequencing constraint:** direct Technology is already at the 25% cap in the draft model. MSFT deployment requires an explicit owner sequencing decision: reduce another Tech weight first, keep any MSFT tranche within verified headroom, or approve a written Tech-cap exception. No automatic sizing, sleeve, cash, or execution-entitlement change is authorized here.
- **Consolidation resolution:** owner-approved staged setup uses 389.64-412.56 / 378.18; below-200-day repair caveat limits sizing/tranche confidence.

---

### AMZN
- Close: **265.01** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **266.31 / 239.67 / 230.06**
- MA posture: **above 50d and 200d, below 20d**.
- Support: **247** (20-day), then **227** (200-day)
- Resistance: prior highs (confirm via chart)
- Preferred entry band: **252.27 to 267.19** *(current artifact layer 2026-05-20)
- Reference band: **252.27 to 267.19** / reference stop **244.81** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **244.81**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the 200-day and fails to recover.
- Stance: **Watch-only / review-only**. inside band 252.27-267.19; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Entry-distance context: **inside band 252.27-267.19** (close 265.01 vs band 252.27-267.19; technical refresh 2026-05-20).
- **Lane note:** keep AMZN technically visible for post-earnings follow-through, but it no longer owns weekday deployment-board cost while GOOG and MSFT already cover the large-cap quality sleeve.
- Earnings: **July 30 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### VRT
- Close: **315.67** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **338.84 / 300.68 / 205.81**
- MA posture: **above 50d and 200d, below 20d**.
- Support: **315** (20-day), then **282** (50-day)
- Resistance: confirm via chart
- Preferred entry band: **306.85 to 338.33** *(current artifact layer 2026-05-20)
- Reference band: **306.85 to 338.33** / reference stop **291.11** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Watch / Research Needed**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **291.11**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the 20-day and breaks the uptrend structure.
- Stance: **Watch / Research Needed**. inside band 306.85-338.33; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. in band, but this execution setup remains watch-only until it is intentionally promoted.
- Entry-distance context: **inside band 306.85-338.33** (close 315.67 vs band 306.85-338.33; technical refresh 2026-05-20).
- Earnings: **July 29 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### CAT
- Close: **872.56** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **877.42 / 791.28 / 619.49**
- MA posture: **above 50d and 200d, below 20d**.
- Support: **831** (20-day), then **760** (50-day)
- Resistance: prior high
- Preferred entry band: **811.65 to 866.48** *(current artifact layer 2026-05-20)
- Reference band: **811.65 to 866.48** / reference stop **784.25** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **784.25**
- Invalidation logic: loses the 50-day and breaks the uptrend.
- Stance: **Watch-only / review-only**. above band 811.65-866.48; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **above band 811.65-866.48** (close 872.56 vs band 811.65-866.48; technical refresh 2026-05-20).
- **Lane note:** CAT keeps technical visibility for post-print follow-through and sector read-through, but it no longer earns weekday execution-board ownership.
- Earnings: **August 4 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### LLY
- Close: **1018.87** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **957.34 / 939.26 / 922.25**
- MA posture: **above all three MAs**, but the **20-day still sits below the 50-day**, so this is not a clean 20 > 50 > 200 trend-stack breakout.
- Support: **970** (top of the written band), then **943** (50-day)
- Resistance: prior high / confirm via chart
- Preferred entry band: **907.64 to 969.88** *(current artifact layer 2026-05-20)
- Reference band: **907.64 to 969.88** / reference stop **876.52** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **876.52**
- Invalidation logic: loses the written stop and fails the current healthcare watch-lane base.
- Stance: **Watch-only / review-only**. above band 907.64-969.88; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **above band 907.64-969.88** (close 1018.87 vs band 907.64-969.88; technical refresh 2026-05-20).
- **Lane note:** LLY now has explicit owner-layer technical levels for review-only competition against other diversification candidates, not deployable authority.
- Earnings: **August 5 (Q2 2026 per yfinance; treat as provisional until company IR confirms).**

---

### GS
- Close: **982.12** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **935.92 / 888.60 / 840.78**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Support: **924** (20-day / refreshed band top zone), then **873** (50-day)
- Resistance: current extension zone above the refreshed band top at **923.51**
- Preferred entry band: **894.64 to 935.77** *(current artifact layer 2026-05-20)
- Reference band: **894.64 to 935.77** / reference stop **866.76** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Almost deployable / above-band no-chase**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **866.76**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses the 50-day and breaks the uptrend; do not chase while price remains above the refreshed band.
- Stance: **Almost deployable / above-band no-chase**. above band 894.64-935.77; wait/no chase unless a later approved band review changes the level. workflow state is ALMOST -- constructive but not yet promoted.
- Entry-distance context: **above band 894.64-935.77** (close 982.12 vs band 894.64-935.77; technical refresh 2026-05-20).
- Earnings: **July 14 (Q2 2026 provider-estimate calendar date)** — no near-term earnings risk, but cross-check company IR before treating as primary-confirmed.
- **Automated band maintenance:** 2026-05-15 eligible proposal applied: prior **886.29–923.51 / stop 858.76** → new **894.64–935.77 / stop 866.76**. This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority.

---

### BRK.B
- Close: **480.90** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **476.71 / 478.34 / 490.08**
- MA posture: **above 20d and 50d, below 200d**. Ballast profile intact, but chart remains in repair until the 200-day is reclaimed and held.
- Support: **483.05** (reclaim-band stop), then **479.58** (50-day), then prior repair stop zone near **465.81**
- Resistance: **489.78** (200-day / reclaim trigger), then **498.19** (top of reclaim band)
- Preferred entry band: **489.78 to 498.19** *(current artifact layer 2026-05-20)
- Reference band: **489.78 to 498.19** / reference stop **483.05** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **483.05** for the reclaim setup; prior **465.81** remains the deeper repair failure reference.
- Invalidation logic: fails to reclaim/hold the 200-day or loses **483.05** after reclaim attempt; deeper weakness below **465.81** confirms continued repair.
- Stance: **Do not touch / below-stop**. Below 483.05 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. workflow state is REPAIR -- wait for setup to rebuild.
- Entry-distance context: **below band 489.78-498.19** (close 480.90 vs band 489.78-498.19; technical refresh 2026-05-20).

---

### XOM
- Close: **156.28** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **151.70 / 154.59 / 128.86**
- MA posture: **above all MAs**. The chart failed the refreshed band and remains below the short/intermediate trend stack.
- Support: **146.14** (explicit stop / urgent review line), then **141.97–143.92** (recent low zone / monthly artifact low)
- Resistance: **150.24** (bottom of refreshed band), then **154.84–158.44** (50-day / top of refreshed band)
- Preferred entry band: **150.24 to 158.44** *(current artifact layer 2026-05-20)
- Reference band: **150.24 to 158.44** / reference stop **146.14** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Do not touch / repair review**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **146.14**
- Invalidation logic: loses the refreshed band and fails back below 146.14, or fails another 50-day reclaim with oil context rolling over. **May 11 produced an intraday stop breach and close-back-above-stop, so this must be treated as a formal repair review item before any oil-supported thesis refresh.**
- Stance: **Do not touch / repair review**. inside band 150.24-158.44; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. Repair state remains active until explicitly lifted by fresh review. in band at 156.28 but workflow state is REPAIR -- wait for setup to rebuild.
- Entry-distance context: **inside band 150.24-158.44** (close 156.28 vs band 150.24-158.44; technical refresh 2026-05-20).

---

### LMT
- Close: **522.59** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **516.84 / 577.87 / 526.25**
- MA posture: **above 20d, below 50d and 200d**. The chart is broken — price is below every major MA and below the explicit stop.
- Support: confirm fresh support only after a new base forms.
- Resistance: **524.03-527.21** (200-day / 20-day reclaim zone), then **548.51** (bottom of written band) and **588.84** (50-day)
- Preferred entry band: **548.51 to 582.27** *(current artifact layer 2026-05-20)
- Reference band: **548.51 to 582.27** / reference stop **531.63** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **execution-band eligible only within owner-approved manual discipline ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **531.63**
- Invalidation logic: prior setup already failed; no new long thesis trigger until price rebuilds support and reclaims key MAs.
- Stance: **Do not touch / below-stop**. Below 531.63 stop; do not deploy until reclaim and fresh review. Repair state remains active until explicitly lifted by fresh review. close 522.59 is below stop -- do not deploy.
- Entry-distance context: **below band 548.51-582.27** (close 522.59 vs band 548.51-582.27; technical refresh 2026-05-20).
- **Defense-sector gap:** LMT's 10% draft weight is suspended while in repair. Owner decision required: reduce it to a holding placeholder and earmark the remainder for a future defense candidate, or formally accept KTOS-only 2% Defense exposure until LMT heals.
- **Consolidation resolution:** below-stop repair/do-not-touch state controls until stop reclaim and fresh base/review.

---

### RTX
- Close: **174.85** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **175.43 / 188.74 / 179.40**
- MA posture: **below all MAs**. Below the 200-day — structural weakness.
- Support: weak; needs to reclaim 185 area first
- Resistance: **178** (200-day), then **189–196** (20/50 cluster)
- Preferred entry band: **183.01 to 193.23** *(current artifact layer 2026-05-20)
- Reference band: **183.01 to 193.23** / reference stop **177.91** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **177.91**
- Invalidation logic: name is below band and only marginally above the refreshed stop; prior setup remains in repair.
- Stance: **Do not touch / below-stop**. Below 177.91 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 174.85 is below stop -- watch-lane monitor only, not execution-board entitled.
- Entry-distance context: **below band 183.01-193.23** (close 174.85 vs band 183.01-193.23; technical refresh 2026-05-20).
- **Lane note:** RTX stays tracked for defense-sector read-through and possible later repair, but not for default weekday deployment upkeep.

---

### CVX
- Close: **191.33** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **187.24 / 191.74 / 165.64**
- MA posture: **above 20d and 200d, below 50d**.
- Support: **189** (20-day), then **186.91** (bottom of preferred band)
- Resistance: **193** (50-day), then **196.41** (top of preferred band)
- Preferred entry band: **186.91 to 196.41** *(current artifact layer 2026-05-20)
- Reference band: **186.91 to 196.41** / reference stop **182.16** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop / invalidation: **182.16**; below this level the setup is fail-closed pending fresh review.
- Invalidation logic: loses 182.16 and breaks back below the band / 20-day support cluster.
- Stance: **Watch-only / review-only**. inside band 186.91-196.41; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Entry-distance context: **inside band 186.91-196.41** (close 191.33 vs band 186.91-196.41; technical refresh 2026-05-20).
- **Lane note:** use CVX for oil-major read-through versus XOM, not as a hidden second-energy promotion while XOM is still benched.
- Earnings: **July 31** *(next provider date after the May 1 print; treat as provisional until company IR confirms).*

---

### PLTR
- Close: **137.15** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **137.94 / 143.26 / 163.03**
- MA posture: **below all MAs**. Short-term bounce, longer-term repair is still incomplete.
- Support: **141.56** (20-day), then **138.60** (bottom of preferred band)
- Resistance: **145.18** (50-day), then **150.44** (top of preferred band)
- Preferred entry band: **137.37 to 149.53** *(current artifact layer 2026-05-20)
- Reference band: **137.37 to 149.53** / reference stop **131.29** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **131.29**
- Invalidation logic: loses 131.29 and fails the current rebound attempt.
- Stance: **Watch-only / review-only**. below band 137.37-149.53; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **below band 137.37-149.53** (close 137.15 vs band 137.37-149.53; technical refresh 2026-05-20).
- **Lane note:** do not treat in-band status as deployment permission. This is a watch-lane name and post-May 4 earnings monitor.
- **Post-earnings status:** reported May 4; use it as read-through evidence only unless a later owner review promotes the setup.

---

### AMD
- Close: **447.58** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **392.70 / 292.90 / 227.98**
- MA posture: **above all MAs -- bullish 20>50>200 stack**. Strong structure, but far above the written zone.
- Support: **311.80** (top of preferred band / first disciplined pullback zone), then **284.89** (20-day)
- Resistance: **current extension zone / recent highs** *(exact upside shelf is not pinned from this artifact layer)*
- Preferred entry band: **295.33 to 342.53** *(current artifact layer 2026-05-20)
- Reference band: **295.33 to 342.53** / reference stop **271.73** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **271.73**
- Invalidation logic: loses the pullback zone and breaks back through 271.73 after the earnings window.
- Stance: **Watch-only / review-only**. above band 295.33-342.53; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **above band 295.33-342.53** (close 447.58 vs band 295.33-342.53; technical refresh 2026-05-20).
- **Lane note:** treat this as a post-earnings tactical monitor that informs the AI sleeve, not as a quiet execution-board promotion.
- **Post-earnings status:** reported May 5; use the scorecard / read-through layer for interpretation and do not promote from watch-lane without owner review.

---

### LNG
- Close: **243.66** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **254.24 / 263.55 / 229.08**
- MA posture: **above 200d, below 20d and 50d**. The May 1 constructive setup is no longer intact.
- Support: no live support from the old band; next repair reference is the **229.19** 200-day after the stop breach.
- Resistance: **253.45** (lost stop / first repair line), then **260.82** (bottom of the old preferred band), then **275.56** (top of the old band)
- Preferred entry band: **260.82 to 275.56** *(current artifact layer 2026-05-20)
- Reference band: **260.82 to 275.56** / reference stop **253.45** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Do not touch / below-stop**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **253.45**
- Invalidation logic: the 2026-05-11 close below 253.45 invalidates the prior watch-lane setup. Any future setup requires a stop reclaim and fresh band review, not automatic reuse of the old band.
- Stance: **Do not touch / below-stop**. Below 253.45 stop; do not deploy until reclaim and fresh review. watch lane only; no execution-board entitlement. close 243.66 is below stop -- watch-lane monitor only, not execution-board entitled.
- Entry-distance context: **below band 260.82-275.56** (close 243.66 vs band 260.82-275.56; technical refresh 2026-05-20).
- **Lane note:** useful for LNG-complex read-through and sector timing, but keep it separate from the XOM decision lane and do not promote from this state without explicit owner review.
- Earnings: provider-estimated next print **2026-08-06** in current artifacts; not primary-confirmed.
- **Consolidation resolution:** below-stop repair/do-not-touch state controls until stop reclaim and fresh base/review.

---

### BKNG
- Close: **156.95** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **165.36 / 171.35 / 195.69**
- MA posture: **below all MAs**. This is repair mode, not an entry setup.
- Support: **164.05–170.91** (watch/rebuild zone only), then **161–164** (manual support area from BKNG review)
- Resistance: **174–177** (repair/reclaim zone), then **198.30** (200-day / machine reclaim reference)
- Preferred entry band: **164.05 to 170.91** *(current artifact layer 2026-05-20)
- Reference band: **164.05 to 170.91** / reference stop **155.97** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / near-stop repair**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **155.97**
- Invalidation logic: fails the 155.97 explicit stop or loses the 161–164 support area without reclaiming 174–177.
- Stance: **Watch-only / near-stop repair**. Near-stop repair/no-chase condition: close is within 1% of the 155.97 stop; require reclaim/fresh review before any deployment review. Repair state remains active until explicitly lifted by fresh review. watch lane only; no execution-board entitlement. workflow state is REPAIR -- wait for setup to rebuild.
- Entry-distance context: **below band 164.05-170.91** (close 156.95 vs band 164.05-170.91; technical refresh 2026-05-20).
- **Catalyst state:** earnings state is now **CLEAR** in `tmp/band-proposals.json` (`days_to_earnings=80`) from a **2026-07-29 provider estimate** in `tmp/earnings-calendar.json`; this is not primary-confirmed.
- **Lane note:** BKNG is an accepted repair-mode blocker / manual wait-state. Do not apply the machine-suggested reclaim band as a live execution band and do not promote without explicit owner review.

### LIN
- Close: **506.07** *(technical refresh; 2026-05-19 close; current artifact layer)*
- 20 / 50 / 200-day: **504.34 / 498.14 / 461.95**
- MA posture: **above all MAs -- bullish 20 > 50 > 200 stack**. Structure is constructive, but price is at the top edge of the written band.
- Support: **504.34-497.11** (20-day / lower written band pullback cluster), then **487.17** (explicit stop / invalidation), then **461.95** (200-day deeper trend support)
- Resistance: **506.11** (written band ceiling / no-chase line), then **515** extension reference requiring fresh review.
- Preferred entry band: **497.11 to 506.11** (formal Materials sleeve planning band; not execution authority)
- Reference band: **490.63 to 505.45** / reference stop **478.25** (weekly reference refresh 2026-05-15; KELTNER_MA_CONSTRAINED / NEAR_BAND; data as of 2026-05-15)
- Reference-band authority: **formal planning only / no execution entitlement**. Reference levels refresh chart context only; they do not create trade, cash, brokerage/account, paper/live order, or execution authority.
- Explicit stop: **487.17**
- Invalidation logic: loses the 50-day / lower-band support zone and fails below 487.17; deeper failure toward the 200-day resets the setup to repair/watch-only.
- Stance: **Promotion review / formal Materials starter-sizing plan; top-of-band no-chase**. Randall approved promotion into a formal Materials sleeve / starter-sizing lane on 2026-05-19 after the LIN owner-review packet. This creates workspace model/sleeve planning context only, not deployment or order authority.
- Starter-sizing context: **0% active / 3% conditional planning weight / $200-$350 starter zone** under the $10k capital framework. This is not deployed capital and does not authorize any cash movement or order.
- Entry-distance context: **inside the preferred band but effectively at the upper edge**; do not chase above 506.11 without fresh band review.
- Promotion review: **Promoted for formal Materials sleeve/starter-sizing planning**. Fundamental quality and official Q1 evidence are sufficient for planning; premium valuation and deteriorating Materials sector leadership require discipline before any action packet.
- Authority: workspace sleeve/sizing planning only; no deployment, cash movement, paper/live order, brokerage/account action, external execution entitlement, or owner-approval inference.

---

### CME
- Close: **290.12** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **289.74 / 296.33 / 277.08**
- MA posture: **above 20d and 200d, below 50d**. Constructive, though not a clean 20 > 50 > 200 stack because the 20-day sits below the 50-day.
- Support: **296.93** (50-day / near-term support), then **287.74** (20-day / lower band reference), then **276.68** (200-day)
- Resistance: **298.86-300** (current close / round-number test), then **305** *(extension reference; confirm on next chart refresh)*
- Preferred entry band: **287.74 to 298.86** *(current artifact layer 2026-05-20)
- Reference band: **287.74 to 298.86** / reference stop **276.68** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Promotion review / explicit decision required**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **276.68**
- Invalidation logic: loses the 20-day/50-day cluster and fails the 200-day at 276.68.
- Stance: **Promotion review / explicit decision required**. inside band 287.74-298.86; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band at 290.12 -- portfolio-review only; separate owner model/sleeve/deployment decision required.
- Entry-distance context: **inside band 287.74-298.86** (close 290.12 vs band 287.74-298.86; technical refresh 2026-05-20).
- Promotion review: **Technically eligible for deeper review, not promoted**. Treat as a financial-infrastructure diversifier candidate, not a hidden third Financials allocation.
- Authority: levels are for review only; no deployment, sizing, sleeve, cash, execution-entitlement, account, or trade authority.

---

### WMB
- Close: **77.88** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **74.94 / 73.56 / 64.47**
- MA posture: **above all MAs -- bullish 20>50>200 stack**. Trend is strong, but price is already extended above the preferred pullback zone.
- Support: **73.82-73.25** (20/50-day pullback cluster), then **64.18** (200-day / deep trend support)
- Resistance: **77.72** (current extension zone), then **80** *(round-number extension reference; confirm on next chart refresh)*
- Preferred entry band: **73.25 to 75.50** *(current artifact layer 2026-05-20)
- Reference band: **73.25 to 75.50** / reference stop **70.32** (current artifact layer 2026-05-20; volatile canon sync)
- Reference-band authority: **reference only / no execution entitlement ? Watch-only / review-only**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, or execution authority.
- Explicit stop: **70.32**
- Invalidation logic: loses the 20/50-day support cluster and fails below 70.32; deeper failure toward the 200-day would reset the setup to repair/watch-only.
- Stance: **Watch-only / review-only**. above band 73.25-75.50; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Entry-distance context: **above band 73.25-75.50** (close 77.88 vs band 73.25-75.50; technical refresh 2026-05-20).
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
- Close: **859.44** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **898.08 / 916.39 / 858.75**
- MA posture: **above 200d, below 20d and 50d**.
- Preferred entry band: **851.36 to 908.98** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **819.35**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement — IN_BAND / review reference**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **Promotion review / explicit decision required**. inside band 851.36-908.98; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band at 859.44 -- portfolio-review only; separate owner model/sleeve/deployment decision required.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### ITA
- Close: **223.28** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **219.75 / 224.07 / 217.09**
- MA posture: **above 20d and 200d, below 50d**.
- Preferred entry band: **212.15 to 223.44** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **205.88**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement — IN_BAND / review reference**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **Promotion review / explicit decision required**. inside band 212.15-223.44; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band at 223.28 -- portfolio-review only; separate owner model/sleeve/deployment decision required.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### VXUS
- Close: **84.17** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **83.50 / 80.73 / 76.18**
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
- Preferred entry band: **80.88 to 83.36** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **78.15**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement — OUT_OF_BAND / watch reference**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **Watch-only / review-only**. above band 80.88-83.36; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### PAVE
- Close: **54.49** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **56.19 / 53.75 / 50.02**
- MA posture: **above 50d and 200d, below 20d**.
- Preferred entry band: **53.94 to 56.28** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **52.64**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement — IN_BAND / review reference**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **Watch-only / review-only**. inside band 53.94-56.28; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### VAW
- Close: **225.01** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **231.76 / 228.77 / 214.80**
- MA posture: **above 200d, below 20d and 50d**.
- Preferred entry band: **225.44 to 233.70** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **220.85**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement — IN_BAND / review reference**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **Watch-only / review-only**. below band 225.44-233.70; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### XLB
- Close: **49.72** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **51.28 / 50.58 / 47.16**
- MA posture: **above 200d, below 20d and 50d**.
- Preferred entry band: **49.84 to 51.68** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **48.81**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement — IN_BAND / review reference**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **Watch-only / review-only**. below band 49.84-51.68; trigger not live until reclaim or explicit owner-approved review. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### XLC
- Close: **116.10** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **116.34 / 114.78 / 114.60**
- MA posture: **above 50d and 200d, below 20d**.
- Preferred entry band: **114.31 to 116.55** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **112.71**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement — OUT_OF_BAND / watch reference**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **Watch-only / review-only**. inside band 114.31-116.55; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### XLE
- Close: **59.80** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **58.24 / 58.28 / 49.03**
- MA posture: **above all MAs**.
- Preferred entry band: **56.35 to 58.04** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **54.83**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement — OUT_OF_BAND / watch reference**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **Watch-only / review-only**. above band 56.35-58.04; wait/no chase unless a later approved band review changes the level. watch lane only; no execution-board entitlement. watch-lane only -- not in execution-board scope yet.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
---

### XLI
- Close: **170.73** *(technical refresh; 2026-05-20 close; current artifact layer)****
- 20 / 50 / 200-day: **172.70 / 169.06 / 160.09**
- MA posture: **above 50d and 200d, below 20d**.
- Preferred entry band: **166.78 to 173.40** *(current artifact layer 2026-05-20)
- Explicit stop / invalidation: **163.10**; below this level the setup is fail-closed pending fresh review.
- Reference-band authority: **reference only / no execution entitlement — IN_BAND / review reference**. Reference levels refresh chart context only; they do not create trade, sizing, sleeve, owner-approval, cash, paper/live order, brokerage, account, or execution authority.
- Stance: **Watch-only / review-only**. inside band 166.78-173.40; in-band does not override workflow, sizing, catalyst, or owner-gated constraints. watch lane only; no execution-board entitlement. in band, but watch-lane only -- no execution-board entitlement.
- Source/freshness: `tmp/technical-refresh.json` + `tmp/portfolio-config.json` as of **2026-05-18**; parser-compatible section added by canon freshness sync 2026-05-18.
