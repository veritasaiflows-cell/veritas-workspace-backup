# Coverage Universe

## Purpose

Define which tickers may enter the research, freshness, alert, and recommendation pipeline.

## High-Attention Coverage

ETN, JPM, NVDA, GOOG, MSFT, GS, VRT, BRK.B, XOM, LMT, RTX, AMZN, CAT, LLY, CVX, PLTR, AMD, and LNG.

These names receive the direct quote/freshness pass used by the scheduled alerts-and-recommendations chain.

## Reference-Level Coverage

AMD, AMZN, BKNG, BRK.B, CAT, CME, CVX, ECL, ETN, GE, GOOG, GS, ITA, JPM, KTOS, LIN, LLY, LMT, LNG, META, MSFT, NFLX, NVDA, PAVE, PH, PLTR, RTX, SLV, SMCI, TLT, TMUS, VAW, VMC, VRT, VXUS, WMB, XLB, XLC, XLE, XLF, XLI, and XOM.

Exact static levels, substantive review dates, and ticker-level alert interpretation live in `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md`.

## Admission Contract

A new symbol needs:

- a clear research question and timeframe
- source lineage and evidence date
- thesis, principal risks, and invalidation logic
- a named freshness owner
- a defined alert or recommendation use case
- guarded SQL and register reconciliation when levels are introduced

Admission never creates action authority. Names may be suppressed when evidence, freshness, or signal quality is inadequate.

## Authority Boundary

This universe is research scope only. It does not maintain account, capital, order, execution, or simulated-account state.
