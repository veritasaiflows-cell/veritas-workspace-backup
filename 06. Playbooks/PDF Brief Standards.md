# PDF Brief Standards

## Purpose

PDF is the fixed-layout presentation layer for the alerts-and-recommendations OS. It packages validated judgment for private review; it is never canon, approval, or execution authority.

The active source of truth remains the alert canon, guarded SQL, current evidence, and validated chain artifacts. When a PDF conflicts with an owner surface, regenerate the PDF.

## Approved products

- Weekly alerts and recommendations brief
- Single-name thesis and recommendation brief
- Catalyst or post-earnings change brief
- Macro, sector, or thematic intelligence brief

Every product is non-executing. A recommendation communicates judgment and Randall's decision point; it does not authorize an account or transaction action.

## Required structure

1. **Conclusion** — the decision-relevant finding and what changed.
2. **Scope** — ticker or theme, timeframe, and evidence cutoff.
3. **Trust panel** — as-of time, source freshness, confidence, and validation state.
4. **Alert state** — one controlled state from the active alert vocabulary.
5. **Thesis and scenarios** — base, bull, and bear cases with material assumptions.
6. **Band and invalidation context** — canonical levels, distance or relationship to them, and what would break the thesis.
7. **Risks and uncertainty** — known gaps, conflicting evidence, and unresolved questions.
8. **Evidence lineage** — concise source list with dates and owner paths.
9. **Recommendation** — non-executing judgment, review horizon, and Randall's decision point.

## Controlled alert states

- Recommendation review
- Band entry
- Near band
- No chase
- Invalidation alert
- Thesis change
- Catalyst alert
- Freshness decay
- Monitor only
- Suppressed

Do not invent synonyms that obscure routing or trust state.

## Source contract

Preferred inputs are:

- `03. Alerts and Recommendations/Alert Trigger Policy.md`
- `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md`
- `03. Alerts and Recommendations/Alert Operations Board.md`
- `03. Alerts and Recommendations/Investor Profile.md`
- `tmp/alerts-recommendations-chain-<window>.json`
- `tmp/alert-level-freshness-controller.json`
- `tmp/finance-alert-os-digest.json`
- `tmp/finance-sql-canon-access-validation.json`
- current, cited company, market, macro, and catalyst evidence

Static bands and invalidation levels must be read from guarded canon. A PDF generator may not derive, rewrite, or auto-apply them.

## Truth and freshness rules

- Put the evidence cutoff and freshness state on page one.
- Label stale, fallback, partial, or conflicting evidence where it affects a conclusion.
- Suppress a recommendation when required evidence is missing or outside its freshness threshold.
- Preserve uncertainty; visual polish may not imply stronger proof than the sources support.
- Separate company quality from timing quality and evidence from judgment.

## Layout rules

- Lead with the conclusion and trust panel.
- Give each page one dominant message.
- Prefer short tables and annotated charts over raw data dumps.
- Use consistent visual semantics for constructive, caution, invalidated, and stale states.
- Keep weekly and thematic briefs to 4–8 pages and single-name or catalyst briefs to 3–8 pages unless evidence requires more.

## Prohibited content

PDFs must not contain or maintain system-owned sleeves, holdings or positions, allocation or weight state, sizing or tranche plans, cash state, order packages, transaction instructions, or paper/live execution routes. Owner-provided objectives or limits may be cited only as transient recommendation context and never become maintained state.

## Generation and acceptance

1. Run the relevant alerts-and-recommendations chain window.
2. Verify guarded-SQL, freshness-controller, and source-lineage proofs.
3. Build the document from current owner and proof artifacts.
4. Validate required sections, dates, states, and citations.
5. Keep the output private unless a separate delivery gate is explicitly approved.

A PDF passes only when its conclusion is traceable, its freshness is visible, its recommendation is clearly non-executing, and no prohibited state is present.
