# Weekly Alerts and Recommendations PDF Product Spec

## Purpose

Define a portable weekly intelligence memo for Randall. The PDF packages current alerts, evidence, freshness, thesis changes, risks, and ranked non-executing recommendations. It is a presentation artifact, not canon or approval.

## Trigger

Generate only after this command passes:

`python scripts/run_alerts_recommendations_chain.py weekly --timeout-seconds 120 --write --validate`

Do not generate from stale, incomplete, or internally inconsistent inputs.

## Source Stack

- `03. Alerts and Recommendations/Investor Profile.md`
- `03. Alerts and Recommendations/Alert Trigger Policy.md`
- `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md`
- `03. Alerts and Recommendations/Alert Operations Board.md`
- guarded SQL proof
- current explicit quote snapshot
- current alert freshness-controller proof
- current weekly alert digest
- current macro and company evidence, with warnings preserved

## Required Sections

1. Executive conclusion and freshness status
2. Market and macro context
3. Material alerts and thesis changes
4. Ranked recommendation reviews
5. No-chase and invalidation alerts
6. Catalyst calendar
7. Risks, uncertainty, and evidence gaps
8. Randall's decision points

Every material ticker entry must include timeframe, evidence date, freshness, confidence, thesis, base/bull/bear view, risks, alert-band and invalidation context, and uncertainty.

## Output

Store finished deliverables under `10. Deliverables/` with an unambiguous week-ending date. Store machine proof in `tmp/`.

## Boundary

The PDF does not maintain account, capital, order, execution, or simulated-account state. It cannot grant approval or override an alert-canon owner. If the PDF conflicts with current validated canon or proof, the PDF is stale and must be regenerated.
