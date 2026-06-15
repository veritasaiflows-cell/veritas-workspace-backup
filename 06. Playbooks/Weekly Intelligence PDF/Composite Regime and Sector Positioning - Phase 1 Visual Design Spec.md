# Composite Regime and Sector Positioning - Weekly Visual PDF Standard

## Product intent

Create the standard weekly visual PDF shell that turns macro regime, sector leadership, underexposure, and name-level deployment state into a decision document. The PDF is a presentation layer only: it must never imply applied portfolio weights, sector allocation changes, promotions, sizing, cash deployment, or execution authority.

Promoted by Randall on 2026-05-11 after review of `Weekly Composite Regime and Sector Positioning - 2026-05-11 Visual Review Candidate.pdf`.

## Visual style

- **Format:** six-page Letter PDF rendered from static HTML/CSS through the local headless browser.
- **Tone:** committee-grade operating memo, not dashboard dump.
- **Density:** compact cards and tables; no early page break or large unused first-page whitespace.
- **Typography:** high-contrast navy headings, small but legible body/table text, short bullets.
- **Color semantics:**
  - Green: constructive / clean / deployable-now state.
  - Amber: manual dependency / review required / almost deployable / caution.
  - Red: stop line / do-not-touch / false approval / no authority.
  - Blue/neutral: informational review context.

## Required trust placement

Trust disclosure belongs on Page 1, above the fold:
- trust level and freshness classification,
- presentation / capital-action authority,
- manual dependencies and mixed-source-date warnings,
- explicit review-only authority boundary.

Every proposed sector tilt must carry `proposal_for_review` or equivalent review-only labeling.

## Six-page wireframe

1. **Executive verdict**
   - Title strip, date, generated timestamp.
   - Authority boundary card.
   - One-line regime / posture verdict.
   - Four-card trust panel.
   - Leadership, underexposure, pending promotion review, approved/promoted split.

2. **Composite macro regime**
   - Six macro metric cards: Fed, 10Y, VIX, HY OAS, breadth, energy/DXY.
   - Signal table: policy/rates, credit, breadth, inflation/energy.
   - Deployment implication.

3. **Sector leadership and underexposure**
   - Status question and concentration warning.
   - Full sector comparison table: sector, current read, exposure/gap, review action.

4. **Review-only sector tilt layer**
   - Red authority stop panel.
   - Sector tilt table generated from current leadership/exposure semantics.
   - Every row labeled `proposal_for_review`.

5. **Names that matter**
   - Strict deployment-surface summary cards.
   - Pending promotion-review candidates separated from approved/promoted names.
   - Name table: ticker, state, band posture, next review trigger.

6. **Risks, invalidation, next actions**
   - Downgrade paths and upgrade conditions.
   - Action table: promotion-review packets, approved/promoted separation, underexposed-sector research, renderer productization.
   - Source lineage and no-mutation footer.

## Reuse route

This is now the standard weekly visual shell for Composite Regime and Sector Positioning PDFs.

Default command:

```powershell
python scripts\render_composite_regime_sector_pdf.py --report-date YYYY-MM-DD --variant "Visual Review Candidate"
```

Default output path:
- `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - YYYY-MM-DD Visual Review Candidate.pdf`

Keep this as a script-generated HTML/PDF shell. HTML/CSS gives tighter visual control than Markdown export, avoids new dependencies, and can fail closed by surfacing missing/stale artifact state in visible panels.

Default visual route:
- inline SVG charts inside the HTML renderer
- pandas may shape table/chart data when available
- do not install matplotlib, plotly, seaborn, or other chart libraries unless a future visual requirement justifies explicit approval
