# Execution Board display sync proposal - 2026-05-19
## Verdict
Safe for main-session bounded freshness/status sync after main verifies the patch and reruns validators. This is display/parser freshness only: no sizing, sleeve, cash, risk-rule, order, account, or owner-approval mutation.
## Material findings
- **ETN:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **MSFT:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **GOOG:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **GS:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **JPM:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **CVX:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **AMZN:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **NVDA:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **VRT:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **VXUS:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.
- **ITA:** table row is stale/mixed versus 2026-05-19 artifacts. Proposed replacement below. Risk: bounded display/freshness/status sync; review-only labels only; no sizing/sleeve/cash/risk-rule/execution mutation.

## Exact current-table row replacements

### ETN
Old:
```markdown
| ETN | Execution | **Deployable now** | 381.87 / 2026-05-18 | 364.48-407.95 | 344.71 | above 200d, below 20d and 50d | Manual-only; no chase above approved band; AI-power/correlation sizing discipline remains. | Owner-approved Tier 1 explicit add; manual-only, no automatic execution. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| ETN | Execution | **Deployable now** | 368.92 / 2026-05-19 | 360.79-404.65 | 340.85 | above 200d, below 20d and 50d | Manual-only; current close remains in gated band; do not chase above 404.65; AI-power/correlation sizing discipline remains. | Owner-approved Tier 1 explicit add; manual-only, no automatic execution. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-readiness-surface.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/trigger-sheet.json. Safe for bounded sync: True.

### MSFT
Old:
```markdown
| MSFT | Execution | **Wait / above-band / staged manual candidate** | 423.54 / 2026-05-18 | 389.64-412.56 | 378.18 | above 20d and 50d, below 200d | Owner-approved staged candidate, but current close is above the written band; wait/no chase until pullback into 389.64-412.56 or an explicit approved band review. Direct Tech is at cap, so deployment sequencing still needs explicit owner decision. | Owner-approved 2026-05-12 staged manual candidate remains recorded; live trigger is not active and there is no automatic execution or sizing authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| MSFT | Execution | **Almost deployable / above-band staged manual candidate** | 423.08 / 2026-05-19 | 389.64-412.56 | 378.18 | above 20d and 50d, below 200d | Above written band by 2.5%; wait/no chase until pullback into 389.64-412.56 or explicit approved band review; Direct Tech remains at cap and sequencing still needs explicit owner decision. | Owner-approved 2026-05-12 staged manual candidate remains recorded; live trigger is not active and there is no automatic execution or sizing authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-readiness-surface.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/trigger-sheet.json. Safe for bounded sync: True.

### GOOG
Old:
```markdown
| GOOG | Execution | **Almost deployable** | 393.11 / 2026-05-18 | 354.05-377.00 | 332.16 | above all MAs -- bullish 20>50>200 stack | Needs pullback/revalidation into written band and explicit promotion. | Promotion still required. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| GOOG | Execution | **Almost deployable / above band** | 385.60 / 2026-05-19 | 354.91-378.08 | 333.50 | above all MAs -- bullish 20>50>200 stack | Above written band by 2.0%; needs pullback/revalidation into 354.91-378.08 and explicit promotion; no chase. | Promotion still required; no automatic execution or sizing authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-readiness-surface.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/trigger-sheet.json. Safe for bounded sync: True.

### GS
Old:
```markdown
| GS | Execution | **Almost deployable** | 946.36 / 2026-05-18 | 894.64-935.77 | 866.76 | above all MAs -- bullish 20>50>200 stack | Above band; secondary to JPM until promoted/sized; WF65 industrial-FCF false-positive is fixed and V1.5 official bank-capital supplement now has manual-confirmed risk-based capital evidence (CET1 12.5% Standardized / 13.3% Advanced; Tier 1 14.1% Standardized / 15.1% Advanced). Tier 1 leverage 5.9% remains separate and **NOT risk-based**. Broader ROTCE/NIM/funding/liquidity/credit-quality review remains required before any Financials execution promotion. | Promotion and sizing review required; no automatic execution, no inferred approval, no sizing authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| GS | Execution | **Promotion review / in band** | 930.31 / 2026-05-19 | 894.64-935.77 | 866.76 | above 50d and 200d, below 20d | In written band, but explicit owner promotion/sizing review and bank-specific fundamentals review remain required before any Financials execution promotion. | Promotion and sizing review required; no automatic execution, no inferred approval, no sizing authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-readiness-surface.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/trigger-sheet.json. Safe for bounded sync: True.

### JPM
Old:
```markdown
| JPM | Execution | **Do not touch / below-stop; approval recorded but trigger not live** | 300.73 / 2026-05-18 | 306.82-318.12 | 301.17 | above 50d, below 20d and 200d | Manual-only; do not touch and do not treat as deployment-eligible or active trigger-monitoring candidate until reclaim of 306.82-318.12 or a later explicit owner-approved band review; WF65 industrial-FCF false-positive is fixed and V1.5 official bank-capital supplement now has manual-confirmed risk-based capital evidence (CET1 14.1% Advanced / 14.3% Standardized; Tier 1 15.1% Advanced / 15.2% Standardized) plus official TBV/share 108.87, but broader ROTCE/NIM/deposit/funding/credit-quality review remains required if future entry is reconsidered. | Prior owner approval remains recorded, but current trigger is not live; no automatic execution, no inferred approval, no sizing authority. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| JPM | Execution | **Do not touch / below-stop; approval recorded but trigger not live** | 299.89 / 2026-05-19 | 306.82-318.12 | 301.17 | below all MAs | Below 301.17 stop and below 306.82-318.12 trigger band; do not treat as deployment-eligible until reclaim or later explicit owner-approved band review; bank-capital evidence remains separate from trigger. | Prior owner approval remains recorded, but current trigger is not live; no automatic execution, no inferred approval, no sizing authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-readiness-surface.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/trigger-sheet.json. Safe for bounded sync: True.

### CVX
Old:
```markdown
| CVX | Watch | **Watch-only / bench** | 196.12 / 2026-05-18 | 186.91-196.41 | 182.16 | above all MAs | Secondary energy read-through; not hidden XOM substitute. | Watch lane only. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| CVX | Watch | **Watch-only / in-band review candidate** | 195.19 / 2026-05-19 | 186.91-196.41 | 182.16 | above all MAs | Inside written watch band; secondary energy read-through and review-only promotion candidate; not a hidden XOM substitute and no automatic promotion. | Watch lane / review-only; no auto-promotion, sizing, sleeve, cash, paper/live order, or trade authority. | tmp/technical-refresh.json + tmp/watchlist-promotion-radar.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/watchlist-promotion-radar.json. Safe for bounded sync: True.

### AMZN
Old:
```markdown
| AMZN | Watch | **Watch-only / bench** | 264.86 / 2026-05-18 | 252.27-267.19 | 244.81 | above 50d and 200d, below 20d | Secondary large-cap platform read; above refreshed watch band; no daily execution entitlement. | Watch lane only. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| AMZN | Watch | **Watch-only / in-band review candidate** | 257.07 / 2026-05-19 | 252.27-267.19 | 244.81 | above 50d and 200d, below 20d | Inside written watch band; secondary large-cap platform read and review-only promotion candidate; no daily execution entitlement. | Watch lane / review-only; no auto-promotion, sizing, sleeve, cash, paper/live order, or trade authority. | tmp/technical-refresh.json + tmp/watchlist-promotion-radar.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/watchlist-promotion-radar.json. Safe for bounded sync: True.

### NVDA
Old:
```markdown
| NVDA | Execution | **Wait / no chase** | 222.32 / 2026-05-18 | 197.01-210.84 | 190.10 | above all MAs -- bullish 20>50>200 stack | Above written band; May 20 earnings is primary-confirmed by NVIDIA IR; event-risk freeze and crowding/timing caveats. | No deployable-now authority; bounded review kept band frozen. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| NVDA | Execution | **Almost / near-earnings caution; no chase** | 219.21 / 2026-05-19 | 197.01-210.84 | 190.10 | above all MAs -- bullish 20>50>200 stack | Above written band and May 20 earnings is 1d away; event-risk freeze/timing-sensitive no-chase state remains active. | No deployable-now authority; event-risk band freeze remains review-only/non-applyable through catalyst window. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-readiness-surface.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/trigger-sheet.json. Safe for bounded sync: True.

### VRT
Old:
```markdown
| VRT | Watch/research | **Watch / research needed** | 339.73 / 2026-05-18 | 306.85-338.33 | 291.11 | above all MAs -- bullish 20>50>200 stack | Above written band / no chase; ETN remains primary AI-power execution name and VRT needs research/promotion before any actionability. | No quiet promotion. | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| VRT | Watch/research | **Watch / research needed; in band** | 315.52 / 2026-05-19 | 306.85-338.33 | 291.11 | above 50d and 200d, below 20d | Inside written band, but ETN remains primary AI-power execution name and VRT still requires research/promotion before any deployment, sizing, sleeve, cash, or trade authority. | No quiet promotion; watch/research lane only; no deployment or trade authority. | tmp/technical-refresh.json + tmp/trigger-sheet.json + tmp/deployment-readiness-surface.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/trigger-sheet.json. Safe for bounded sync: True.

### VXUS
Old:
```markdown
| VXUS | ETF monitor / international diversification | **Review-only / ETF watch target** | 83.53 / 2026-05-18 | 80.88-83.36 | 78.15 | above all MAs -- bullish 20>50>200 stack | Core ex-U.S. diversification candidate; review-only and no deployment, sizing, sleeve, cash, approval, paper/live order, brokerage, account, or trade authority. | tmp/portfolio-config.json + VXUS official proof 2026-05-18 | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| VXUS | ETF monitor / international diversification | **Review-only / ETF watch target in band** | 82.46 / 2026-05-19 | 80.88-83.36 | 78.15 | above 50d and 200d, below 20d | Inside reference band; core ex-U.S. diversification candidate remains review-only with no deployment/sizing/sleeve/cash/order authority. | Review-only ETF diversification target; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/watchlist-promotion-radar.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/watchlist-promotion-radar.json. Safe for bounded sync: True.

### ITA
Old:
```markdown
| ITA | ETF candidate / promotion-review | **Portfolio-review only / ETF candidate in band** | 220.23 / 2026-05-18 | 212.15-223.44 | 205.88 | above 20d and 200d, below 50d | Aerospace/defense gap candidate while LMT/RTX/GE single-name paths remain repair/watch; GE/RTX/BA concentration and LMT/KTOS look-through must be accepted before any paper order. | tmp/portfolio-config.json + ITA closeout proof 2026-05-18 | tmp/technical-refresh.json + tmp/portfolio-config.json 2026-05-18; canon freshness sync 2026-05-18 |
```
New:
```markdown
| ITA | ETF candidate / promotion-review | **Portfolio-review only / ETF candidate in band** | 216.84 / 2026-05-19 | 212.15-223.44 | 205.88 | below all MAs | Inside reference band, but now below all MAs; aerospace/defense gap candidate remains promotion-review only and needs look-through acceptance/gates before any paper order. | Portfolio-review only; no sizing, sleeve, cash, deployment, paper/live order, brokerage, account, or trade authority. | tmp/technical-refresh.json + tmp/watchlist-promotion-radar.json 2026-05-19; proposed canon freshness sync 2026-05-19 |
```
Source: tmp/technical-refresh.json, tmp/watchlist-promotion-radar.json. Safe for bounded sync: True.

## Parser-compatible line replacements

### ETN - parser.close
Old:
```markdown
- Close: **369.33** *(technical refresh; 2026-05-19 close; current artifact layer)*
```
New:
```markdown
- Close: **368.92** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### ETN - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **409.46 / 387.42 / 361.76**
```
New:
```markdown
- 20 / 50 / 200-day: **409.44 / 387.42 / 361.76**
```

### ETN - parser.ma_posture
Old:
```markdown
- MA posture: **above the 200-day, but below the 20-day and 50-day**. The owner-approved setup remains inside the approved band, but the short-term trend is not a clean above-all-MAs chase setup.
```
New:
```markdown
- MA posture: **above 200d, below 20d and 50d**.
```

### ETN - parser.preferred_entry_band
Old:
```markdown
- Preferred entry band: **360.79 to 404.65** (auto-applied band maintenance 2026-05-19; KELTNER_PRIMARY / IN_BAND)
```
New:
```markdown
- Preferred entry band: **360.79 to 404.65** (current artifact layer 2026-05-19)
```

### ETN - parser.stop
Old:
```markdown
- Explicit stop: **340.85**
```
New:
```markdown
- Explicit stop / invalidation: **340.85**
```

### ETN - parser.entry_distance_context
Old:
```markdown
- Entry-distance context: **inside the preferred band; below the 50-day and 20-day reclaim levels**.
```
New:
```markdown
- Entry-distance context: **inside the current written band** (close 368.92 vs band 360.79-404.65; technical refresh 2026-05-19).
```

### MSFT - parser.close
Old:
```markdown
- Close: **409.43** *(technical refresh; 2026-05-14 close; current artifact layer)*
```
New:
```markdown
- Close: **423.08** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### MSFT - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **417.45 / 398.84 / 462.35**
```
New:
```markdown
- 20 / 50 / 200-day: **417.62 / 399.63 / 460.89**
```

### MSFT - parser.ma_posture
Old:
```markdown
- MA posture: **above the 50-day, but below the 20-day and 200-day**. Recovery is intact enough for the staged setup, but long-term repair is still incomplete.
```
New:
```markdown
- MA posture: **above 20d and 50d, below 200d**.
```

### MSFT - parser.preferred_entry_band
Old:
```markdown
- Preferred entry band: **389.64 to 412.56** (working post-print owner-approved band)
```
New:
```markdown
- Preferred entry band: **389.64 to 412.56** (current artifact layer 2026-05-19)
```

### MSFT - parser.stop
Old:
```markdown
- Explicit stop: **378.18**
```
New:
```markdown
- Explicit stop / invalidation: **378.18**
```

### MSFT - parser.entry_distance_context
Old:
```markdown
- Entry-distance context: **above the preferred band**; latest artifact close **423.54** sits **10.98 / 2.7% above** the **412.56** band ceiling. Prefer no new starter tranche while above band and below the 200-day unless Randall explicitly approves a fresh band/sequence decision.
```
New:
```markdown
- Entry-distance context: **outside the current written band; keep no-chase / review-only state active** (close 423.08 vs band 389.64-412.56; technical refresh 2026-05-19).
```

### GOOG - parser.close
Old:
```markdown
- Close: **397.17** *(technical refresh; 2026-05-14 close; current artifact layer)*
```
New:
```markdown
- Close: **385.60** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### GOOG - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **367.49 / 328.93 / 290.03**
```
New:
```markdown
- 20 / 50 / 200-day: **375.83 / 334.27 / 292.99**
```

### GOOG - parser.ma_posture
Old:
```markdown
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Trend remains strong after the print.
```
New:
```markdown
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
```

### GOOG - parser.preferred_entry_band
Old:
```markdown
- Preferred entry band: **354.91 to 378.08** (auto-applied band maintenance 2026-05-19; KELTNER_MA_CONSTRAINED / NEAR_BAND)
```
New:
```markdown
- Preferred entry band: **354.91 to 378.08** (current artifact layer 2026-05-19)
```

### GOOG - parser.stop
Old:
```markdown
- Explicit stop: **333.50**
```
New:
```markdown
- Explicit stop / invalidation: **333.50**
```

### GOOG - parser.entry_distance_context
Old:
```markdown
- Entry-distance context: **+.09 / +9.7% above the top of the preferred band** — materially extended, no chase.
```
New:
```markdown
- Entry-distance context: **outside the current written band; keep no-chase / review-only state active** (close 385.60 vs band 354.91-378.08; technical refresh 2026-05-19).
```

### GS - parser.close
Old:
```markdown
- Close: **944.86** *(band-sync refresh; 2026-05-11 close from `tmp/band-proposals.json`)*
```
New:
```markdown
- Close: **930.31** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### GS - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **924.03 / 873.36 / 832.38**
```
New:
```markdown
- 20 / 50 / 200-day: **933.63 / 885.66 / 839.45**
```

### GS - parser.ma_posture
Old:
```markdown
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**.
```
New:
```markdown
- MA posture: **above 50d and 200d, below 20d**.
```

### GS - parser.preferred_entry_band
Old:
```markdown
- Preferred entry band: **894.64 to 935.77** (auto-applied band maintenance 2026-05-15; KELTNER_MA_CONSTRAINED / NEAR_BAND)
```
New:
```markdown
- Preferred entry band: **894.64 to 935.77** (current artifact layer 2026-05-19)
```

### GS - parser.stop
Old:
```markdown
- Explicit stop: **866.76**
```
New:
```markdown
- Explicit stop / invalidation: **866.76**
```

### GS - parser.entry_distance_context
Old:
```markdown
- Entry-distance context: **+$21.35 / +2.3% above the top of the refreshed preferred band**.
```
New:
```markdown
- Entry-distance context: **inside the current written band** (close 930.31 vs band 894.64-935.77; technical refresh 2026-05-19).
```

### JPM - parser.close
Old:
```markdown
- Close: **297.81** *(research freshness handoff; 2026-05-15 close)*
```
New:
```markdown
- Close: **299.89** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### JPM - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **308.21 / 299.68 / 302.93** *(technical-refresh context from 2026-05-15)*
```
New:
```markdown
- 20 / 50 / 200-day: **306.74 / 300.17 / 303.04**
```

### JPM - parser.ma_posture
Old:
```markdown
- MA posture: **below all key moving averages**. Current chart posture supports fail-closed treatment; the prior green machine read must not override the owner-resolved trigger band.
```
New:
```markdown
- MA posture: **below all MAs**.
```

### JPM - parser.preferred_entry_band
Old:
```markdown
- Preferred entry band: **not live** until JPM reclaims **306.82 to 318.12** or a later explicit owner-approved band review replaces it.
```
New:
```markdown
- Preferred entry band: **306.82 to 318.12** (current artifact layer 2026-05-19)
```

### JPM - parser.entry_distance_context
Old:
```markdown
- Entry-distance context: **below authoritative trigger band / near invalidation**.
```
New:
```markdown
- Entry-distance context: **outside the current written band; keep no-chase / review-only state active** (close 299.89 vs band 306.82-318.12; technical refresh 2026-05-19).
```

### CVX - parser.close
Old:
```markdown
- Close: **190.63** *(manual watch-lane parity pass; 2026-05-01 close)*
```
New:
```markdown
- Close: **195.19** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### CVX - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **189.29 / 192.94 / 164.49**
```
New:
```markdown
- 20 / 50 / 200-day: **188.42 / 193.28 / 166.90**
```

### CVX - parser.ma_posture
Old:
```markdown
- MA posture: **above the 20-day and 200-day, still below the 50-day**. Better than a broken chart, not a clean trend reclaim.
```
New:
```markdown
- MA posture: **above all MAs**.
```

### CVX - parser.preferred_entry_band
Old:
```markdown
- Preferred entry band: **186.91 to 196.41** (band updated 2026-05-01)
```
New:
```markdown
- Preferred entry band: **186.91 to 196.41** (current artifact layer 2026-05-19)
```

### CVX - parser.stop
Old:
```markdown
- Explicit stop: **182.16**
```
New:
```markdown
- Explicit stop / invalidation: **182.16**
```

### CVX - parser.entry_distance_context
Old:
```markdown
- Entry-distance context: **inside the preferred band**.
```
New:
```markdown
- Entry-distance context: **inside the current written/reference band** (close 195.19 vs band 186.91-196.41; technical refresh 2026-05-19).
```

### AMZN - parser.close
Old:
```markdown
- Close: **268.26** *(band-sync refresh; 2026-05-01 close)*
```
New:
```markdown
- Close: **257.07** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### AMZN - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **247.37 / 224.80 / 227.38**
```
New:
```markdown
- 20 / 50 / 200-day: **265.71 / 238.61 / 229.78**
```

### AMZN - parser.ma_posture
Old:
```markdown
- MA posture: **above all three MAs**. Trend is constructive.
```
New:
```markdown
- MA posture: **above 50d and 200d, below 20d**.
```

### AMZN - parser.preferred_entry_band
Old:
```markdown
- Preferred entry band: **252.27 to 267.19** (bounded note sync 2026-05-13; current fresh band from `tmp/band-proposals.json`)
```
New:
```markdown
- Preferred entry band: **252.27 to 267.19** (current artifact layer 2026-05-19)
```

### AMZN - parser.stop
Old:
```markdown
- Explicit stop: **244.81**
```
New:
```markdown
- Explicit stop / invalidation: **244.81**
```

### AMZN - parser.entry_distance_context
Old:
```markdown
- Entry-distance context: **+$2.94 / +1.1% above the top of the refreshed preferred band**.
```
New:
```markdown
- Entry-distance context: **inside the current written/reference band** (close 257.07 vs band 252.27-267.19; technical refresh 2026-05-19).
```

### NVDA - parser.close
Old:
```markdown
- Close: **235.74** *(technical refresh; 2026-05-14 close; current artifact layer)*
```
New:
```markdown
- Close: **219.21** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### NVDA - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **209.12 / 192.23 / 185.73**
```
New:
```markdown
- 20 / 50 / 200-day: **212.28 / 194.69 / 186.41**
```

### NVDA - parser.ma_posture
Old:
```markdown
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. AI leadership intact, but crowding and event risk still matter.
```
New:
```markdown
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
```

### NVDA - parser.preferred_entry_band
Old:
```markdown
- Preferred entry band: **197.01 to 210.84** (band updated 2026-05-06; bounded review 2026-05-13 kept band frozen)
```
New:
```markdown
- Preferred entry band: **197.01 to 210.84** (current artifact layer 2026-05-19)
```

### NVDA - parser.stop
Old:
```markdown
- Explicit stop: **190.10**
```
New:
```markdown
- Explicit stop / invalidation: **190.10**
```

### NVDA - parser.entry_distance_context
Old:
```markdown
- Entry-distance context: **+.90 / +11.8% above the top of the preferred band**; 	mp/band-proposals.json also flags close materially above midpoint, EARNINGS_IMMINENT, and non-applyable status.
```
New:
```markdown
- Entry-distance context: **outside the current written band; keep no-chase / review-only state active** (close 219.21 vs band 197.01-210.84; technical refresh 2026-05-19).
```

### VRT - parser.close
Old:
```markdown
- Close: **358.92** *(WF38 canonical-note sync; 2026-05-06 close)*
```
New:
```markdown
- Close: **315.52** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### VRT - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **314.72 / 281.57 / 195.15**
```
New:
```markdown
- 20 / 50 / 200-day: **337.96 / 299.62 / 204.89**
```

### VRT - parser.ma_posture
Old:
```markdown
- MA posture: **above all three MAs with a bullish 20 > 50 > 200 stack**. Clean leadership structure.
```
New:
```markdown
- MA posture: **above 50d and 200d, below 20d**.
```

### VRT - parser.preferred_entry_band
Old:
```markdown
- Preferred entry band: **306.85 to 338.33**
```
New:
```markdown
- Preferred entry band: **306.85 to 338.33** (current artifact layer 2026-05-19)
```

### VRT - parser.stop
Old:
```markdown
- Explicit stop: **291.11**
```
New:
```markdown
- Explicit stop / invalidation: **291.11**
```

### VRT - parser.entry_distance_context
Old:
```markdown
- Entry-distance context: **+$20.59 / +6.1% above the top of the preferred band**.
```
New:
```markdown
- Entry-distance context: **inside the current written band** (close 315.52 vs band 306.85-338.33; technical refresh 2026-05-19).
```

### VXUS - parser.close
Old:
```markdown
- Close: **83.53** *(technical refresh; 2026-05-18 close)*
```
New:
```markdown
- Close: **82.46** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### VXUS - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **83.37 / 80.55 / 76.02**
```
New:
```markdown
- 20 / 50 / 200-day: **83.40 / 80.62 / 76.10**
```

### VXUS - parser.ma_posture
Old:
```markdown
- MA posture: **above all MAs -- bullish 20>50>200 stack**.
```
New:
```markdown
- MA posture: **above 50d and 200d, below 20d**.
```

### VXUS - parser.reference_entry_band
Old:
```markdown
- Reference entry band: **80.88 to 83.36** *(portfolio-config reference band; latest canon freshness sync 2026-05-18)*
```
New:
```markdown
- Reference entry band: **80.88 to 83.36** *(portfolio-config/reference band; current technical refresh 2026-05-19)*
```

### VXUS - parser.stop
Old:
```markdown
- Explicit stop / invalidation: **78.15**
```
New:
```markdown
- Explicit stop / invalidation: **78.15**
```

### ITA - parser.close
Old:
```markdown
- Close: **220.23** *(technical refresh; 2026-05-18 close)*
```
New:
```markdown
- Close: **216.84** *(technical refresh; 2026-05-19 close; current artifact layer)*
```

### ITA - parser.ma_values
Old:
```markdown
- 20 / 50 / 200-day: **219.78 / 224.86 / 216.84**
```
New:
```markdown
- 20 / 50 / 200-day: **219.46 / 224.36 / 216.95**
```

### ITA - parser.ma_posture
Old:
```markdown
- MA posture: **above 20d and 200d, below 50d**.
```
New:
```markdown
- MA posture: **below all MAs**.
```

### ITA - parser.reference_entry_band
Old:
```markdown
- Reference entry band: **212.15 to 223.44** *(portfolio-config reference band; latest canon freshness sync 2026-05-18)*
```
New:
```markdown
- Reference entry band: **212.15 to 223.44** *(portfolio-config/reference band; current technical refresh 2026-05-19)*
```

### ITA - parser.stop
Old:
```markdown
- Explicit stop / invalidation: **205.88**
```
New:
```markdown
- Explicit stop / invalidation: **205.88**
```

## Guardrail notes
- `tmp/stale-intelligence-guardrail.json`: ok, no findings.
- `tmp/board-canon-guardrail.json`: warning, no critical; risk alerts do not block display sync, but require preserving below-stop/near-stop language.
- `tmp/canon-drift-freshness-gate.json`: ok, but timestamp predates morning artifacts; use morning artifacts as the freshness authority for this proposal.
