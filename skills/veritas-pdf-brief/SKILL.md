---
name: "veritas-pdf-brief"
description: "Package grounded alerts, evidence, and recommendations into truthful PDFs."
---

# Veritas PDF Brief

## Purpose

Package already-grounded work into a readable fixed-layout deliverable. Notes and guarded sources own judgment; the PDF preserves lineage, dates, uncertainty, and non-executing status.

## Finance Product Types

- Weekly Alerts and Recommendations PDF
- Post-Earnings Scorecard PDF
- Equity Research / Thesis PDF
- Macro and Sector Alerts PDF

Portfolio-positioning, exposure-weight, sleeve, allocation, capital-priority, and deployment-readiness PDF products are retired.

PM/product-readiness PDFs remain separately governed by `veritas-pm-department` and are not finance authority.

## Finance Sources

Use:

- active `03. Alerts and Recommendations` canon
- guarded SQL validation
- explicit quote snapshot and validation
- alert-level freshness controller
- current daily or weekly digest
- current macro, fundamental, technical, catalyst, and earnings evidence

For weekly finance PDFs first run:

```powershell
python scripts\run_alerts_recommendations_chain.py weekly --timeout-seconds 120 --write --validate
```

If source layers conflict, resolve or disclose the conflict before rendering.

## Standard Structure

1. title, scope, timeframe, and as-of
2. executive conclusion
3. trust/freshness/confidence panel
4. ranked non-executing recommendations
5. alert-state summary
6. evidence and catalysts
7. thesis, base/bull/bear
8. risks, uncertainty, and invalidation
9. Randall's decision points
10. source/methodology appendix when needed

## Alert Vocabulary

Recommendation review, Band entry, Near band, No chase, Invalidation alert, Thesis change, Catalyst alert, Freshness decay, Monitor only, and Suppressed.

## Layout

Lead with conclusions. Prefer short sections, high contrast, and one useful visual per page. Do not use decorative charts, screenshots, tiny tables, or raw data dumps. Put trust degradation near the front.

## Boundary

No maintained holdings, positions, sleeves, allocations, weights, sizing, tranches, cash posture, rebalancing, simulated positions, order packages, account reads, or execution routes. A polished PDF does not make evidence fresh and never implies approval.
