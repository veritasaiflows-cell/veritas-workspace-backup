# Workflow 57 - Composite Regime and Sector Positioning PDF Visual Enhancement

## Objective

Turn the first Weekly Composite Regime and Sector Positioning draft into a visually appealing, reusable PDF product without weakening trust boundaries or turning review-only proposals into applied portfolio state.

Primary draft input:
- `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - 2026-05-10 Draft.md`

Product spec inputs:
- `06. Playbooks/Composite Regime and Sector Positioning PDF Candidate.md`
- `06. Playbooks/PDF Brief Standards.md`
- `skills/veritas-pdf-brief/SKILL.md`

## User request trigger

Opened 2026-05-10 after Randall approved building the first draft and requested a new workflow to enhance it and make it visually appealing.

## Current phase

Status: **Phase 1-4 complete / closed as internal polished PDF product**.

The first draft and first-format visual artifacts remain intact for traceability:
- `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - 2026-05-10 First Format.html`
- `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - 2026-05-10 First Format.pdf`

WF57 now also has a compact design spec and a reusable script-generated HTML/CSS report shell:
- design spec: `06. Playbooks/Weekly Intelligence PDF/Composite Regime and Sector Positioning - Phase 1 Visual Design Spec.md`
- renderer: `scripts/render_composite_regime_sector_pdf.py`
- polished HTML: `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - 2026-05-11 Polished.html`
- polished PDF: `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - 2026-05-11 Polished.pdf`
- review-candidate HTML: `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - 2026-05-11 Review Candidate.html`
- review-candidate PDF: `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - 2026-05-11 Review Candidate.pdf`
- visual-review HTML: `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - 2026-05-11 Visual Review Candidate.html`
- visual-review PDF: `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - 2026-05-11 Visual Review Candidate.pdf`

Live proof on 2026-05-11:
- `python -m py_compile scripts\render_composite_regime_sector_pdf.py` completed cleanly.
- `python scripts\render_composite_regime_sector_pdf.py --report-date 2026-05-11 --variant Polished` completed with status `ok` using Microsoft Edge headless PDF print.
- Polished output sizes: HTML 25,185 bytes; PDF 241,909 bytes; design spec 3,003 bytes.
- Direct output inspection confirmed pending promotion-review names are `CAT`, `GS`, `LLY`, `NVDA`, while approved/promoted names are separately shown as `ETN`, `JPM`.
- Direct output inspection confirmed `proposal_for_review` labels are present and stale ETN conflict wording is absent.
- `python scripts\render_composite_regime_sector_pdf.py --report-date 2026-05-11 --variant "Review Candidate"` completed with status `ok`; review-candidate PDF size is 241,915 bytes.
- Review-candidate trust panel shows `manual_dependency` / `review_required`, `presentation_allowed=False`, and `capital_action_allowed=False`.
- `python scripts\render_composite_regime_sector_pdf.py --report-date 2026-05-11 --variant "Visual Review Candidate"` completed with status `ok`; visual-review PDF size is 268,656 bytes.
- Visual-review candidate adds inline SVG charts without new package installs: leadership/underexposure heatmap, strict deployment-surface distribution, and sector exposure-vs-cap chart.

The document remains an internal polished candidate, not an external/client-final PDF. It is suitable for review and reuse as the current Composite Regime and Sector Positioning PDF product, not portfolio mutation.

Phase 4 productization decision:
- promoted by Randall on 2026-05-11: the Visual Review Candidate renderer is now the standard weekly visual PDF shell for Composite Regime and Sector Positioning
- keep this as the script-generated HTML/CSS PDF route for weekly reuse
- use Microsoft Edge headless print as the verified export path on this Windows workspace
- treat `scripts/render_composite_regime_sector_pdf.py` as the reusable shell and `06. Playbooks/Weekly Intelligence PDF/Composite Regime and Sector Positioning - Phase 1 Visual Design Spec.md` as the product standard
- default command: `python scripts\render_composite_regime_sector_pdf.py --report-date YYYY-MM-DD --variant "Visual Review Candidate"`
- keep inline SVG + pandas shaping as the default visual route before adding charting dependencies; install matplotlib/plotly only if a future visual need justifies explicit approval

## Product boundary

This workflow owns:
- visual hierarchy
- reusable page layout
- PDF/export mechanics
- table/chart/panel design
- trust/status disclosure placement
- source-lineage disclosure

This workflow does **not** own:
- portfolio mutation
- sector-weight application
- owner approval
- deployment-state changes
- trade/account actions
- hidden changes to canonical notes

## Safe automation boundary

Allowed:
- create visual mockups, HTML, Markdown, DOCX, PPTX, or PDF drafts
- create reusable templates or renderer scripts inside the workspace
- generate review-only charts from already-refreshed artifacts
- label sector tilts as `proposal_for_review`
- create source-lineage and trust-status panels
- use generated assets under `tmp/` while promoting durable outputs to the correct notes/report folders

Blocked without explicit Randall approval:
- applying proposed sector weights or sleeve changes
- promoting/demoting tickers
- changing cash targets, sizing, risk-rule thresholds, or execution entitlement
- mutating Portfolio Snapshot, Deployment Trigger Sheet, Watchlist, Technical Sheet, Coverage Universe, or `tmp/portfolio-config.json` based on the PDF alone
- presenting review-only proposals as owner-approved allocation decisions

## Target deliverables

### Phase 1 - Visual design spec

Deliverables:
- one-page visual style plan for the Composite Regime and Sector Positioning product
- page-by-page layout wireframe for the six-page structure
- color semantics for constructive / caution / blocked / neutral states
- required trust/disclosure panel placement

Acceptance:
- design preserves the current draft's trust caveats
- proposal-for-review labels are visually prominent
- no page implies applied allocation authority

### Phase 2 - Reusable report shell

Deliverables:
- reusable renderer or template for this PDF product type
- data ingestion map from source artifacts to report panels
- generated HTML/Markdown/PDF preview if dependencies support it

Acceptance:
- source files are named explicitly
- missing or stale source fields fail closed into visible warnings
- no raw JSON dump is used as a final visual page

### Phase 3 - First polished PDF candidate

Deliverables:
- polished candidate under `06. Playbooks/Weekly Intelligence PDF/` or an approved report-output path
- source lineage section
- visible data-as-of and validation/trust panel
- reusable assets or renderer notes documented

Acceptance:
- PDF reads as a decision document, not a dashboard screenshot dump
- tables are legible
- trust limits are near the front
- all sector tilts/weights are labeled review-only / `proposal_for_review`
- final response includes proof and remaining limits

### Phase 4 - Productization / reuse decision

Deliverables:
- recommendation on whether to keep this as manual Markdown-to-PDF, template-driven HTML/PDF, or script-generated report
- backlog items for optional charts and library dependencies

Acceptance:
- no dependency is treated as available until verified live
- any new script has a small validation/proof gate
- durable procedure updates go to the relevant playbook or skill, not chat only

## Data freshness gate

Before producing a final polished PDF candidate, verify or rerun as needed:
- `python scripts\run_finance_refresh_chain.py sunday`
- `python scripts\validate_dashboard_state.py --write`

If validation remains `manual_dependency` / `review_required`, the PDF can still exist as an internal review artifact, but the front-page trust panel must say so.

## Known starting caveats

From the first draft package:
- dashboard integrity is clean, but source freshness is `manual_dependency` / `review_required`
- strict validator says presentation is not allowed
- canonical mutation and capital action are not allowed
- true pre-market tape is unavailable from current yfinance responses
- market-state source dates are mixed
- weekly-intelligence artifact conflicts with the stricter deployment surface on ETN deployability; the stricter surface should govern polished wording unless reconciled

## Stop lines

Stop and ask Randall before:
- treating the PDF as a final external/client-ready document
- changing any canonical portfolio/deployment/risk note
- adding applied sector weights, target allocations, or execution recommendations
- installing new packages or changing runtime/config outside the workspace
- publishing, emailing, or sending the PDF outside the current local workspace/session

## Next action

WF57 is complete for the requested internal polished PDF product. The next workflow is WF56 Phase 2 review-only portfolio mutation proposal generation.

Optional later WF57 backlog:
1. add a small validator that asserts pending promotion-review candidates exclude already approved/promoted names before render,
2. add chart panels only if they improve decision value and the dependency is verified live,
3. create a scheduled/report-refresh wrapper only after the source freshness and trust gates remain stable.

Current route decision: keep **script-generated HTML/CSS PDF** because it runs live on this Windows workspace with Microsoft Edge headless print, avoids new dependencies, provides better visual control than raw Markdown, and keeps the PDF presentation layer separate from canonical portfolio truth.