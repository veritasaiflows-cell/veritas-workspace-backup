---
name: "veritas-response-contract"
description: "Add thin 5/20DMA and signal warnings to capital recommendations."
---

# Veritas Response Contract Update: Thin Timing And Signal Warnings

Add this rule under `## Finance / portfolio response boundaries` after the existing source-freshness and confidence bullet:

- When giving capital-influencing recommendations, include a thin timing/signal caution when available: ticker or sector 5DMA/20DMA posture, price-vs-5DMA, price-vs-20DMA, and current macro/market signal warnings. Keep it compact. Treat 5DMA/20DMA as timing and confirmation context only; they do not override written entry bands, stop/invalidation levels, thesis quality, source freshness, concentration limits, or owner approval gates.

Add this rule under `### Market-state intelligence hardening` after the portfolio implication bullet:

- If `tmp/sector-expansion-board.json` includes `short_term_moving_averages`, use the sector ETF `signal` and `warning` fields as thin sector timing context in capital posture answers. Example interpretations: `short_term_confirmed` supports normal review, `constructive_pullback` supports wait-for-reclaim or staged entries, `momentum_cooling` argues for smaller/staged deployment, and `short_term_repair_needed` argues for patience. These are review-only warnings, not forecast, win-rate, approval, or execution signals.

Add this stop-line sentence to the same section:

- Do not make 5DMA/20DMA or macro-signal-spine warnings sound like model training, predictive probability, or automatic capital authority. They are context carried into recommendations, not a trading system.
