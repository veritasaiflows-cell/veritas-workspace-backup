# Composite Regime and Sector Positioning PDF Candidate

## Recommendation

Build the first candidate as a **Weekly Composite Regime and Sector Positioning PDF**.

This is better than a macro-only PDF because Randall needs the regime read translated into portfolio behavior. It should combine:
- current macro regime
- sector leadership / underexposure
- candidate promotion-review names
- proposed sector tilts or model-sector weight changes for review
- explicit owner-gated mutation boundaries

Do **not** make this an applied allocation document. It can recommend review targets and draft proposed sector weights, but applying sector weights, cash targets, sleeve changes, promotions, demotions, sizing, risk-rule changes, or execution entitlement remains explicit Randall-approval gated.

## Product role

PDF layer:
- fixed-layout presentation and archive artifact
- not the canonical truth layer
- not a blind export of machine artifacts

Truth layer:
- `05. Intelligence/Weekly Positioning Review.md`
- `02. Markets/Macro Regime Dashboard.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`
- relevant generated artifacts in `tmp/`

## Source stack

Canonical notes:
- `05. Intelligence/Weekly Intelligence Brief.md` when available
- `05. Intelligence/Weekly Positioning Review.md`
- `02. Markets/Macro Regime Dashboard.md`
- `04. Research/Coverage and Watchlist.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Execution Board.md`
- `07. Risk/Risk Rules.md`

Structured artifacts:
- `tmp/market-state.json`
- `tmp/sector-expansion-board.json`
- `tmp/sector-correlation-check.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/positioning-ranking.json`
- `tmp/dashboard-validation.json`
- `tmp/earnings-calendar.json`

Required validation before PDF packaging:
- `python scripts\run_finance_refresh_chain.py sunday` or the relevant current refresh chain
- note-layer reconciliation
- `python scripts\validate_dashboard_state.py --write`

## Candidate title

Preferred title:
- `Weekly Composite Regime and Sector Positioning - YYYY-MM-DD.pdf`

Recommended draft path:
- `06. Playbooks/Weekly Intelligence PDF/Weekly Composite Regime and Sector Positioning - YYYY-MM-DD.pdf`

## Target length

Default: 6 pages.
Hard cap: 8 pages without a specific reason.

## Page structure

### Page 1 — Executive verdict

Answer:
- What regime are we in?
- Should posture be offense, patience, or defense?
- What changed this week?
- What is the biggest trust limit?

Required blocks:
- one-sentence regime verdict
- one-sentence portfolio posture verdict
- top 3 portfolio implications
- validation / trust status

### Page 2 — Composite macro regime

Cover only the macro signals that change portfolio behavior:
- policy / rates
- curve
- credit
- breadth
- inflation / energy
- dollar
- volatility

End with a plain-English deployment implication.

### Page 3 — Sector leadership and underexposure

Required table:

| Sector | Current read | Portfolio exposure / gap | Review action |
|---|---|---|---|

Must answer:
- Where is sector leadership improving?
- Where are we underexposed?
- Which sectors deserve research or promotion-review work?

### Page 4 — Sector tilt / weight proposal layer

This page may include **review-only proposed sector tilts**.

Rules:
- label every proposed weight or tilt as `proposal_for_review`, not applied state
- include current exposure, proposed direction, rationale, and blocker
- no trade sizing or execution entitlement
- do not imply owner approval

Preferred table:

| Sector | Proposed tilt | Rationale | Owner-gated blocker |
|---|---|---|---|

### Page 5 — Names that matter

Connect sector view to actual names:
- deployable-now / owner-approved names
- almost-deployable names
- promotion-review candidates
- repair / do-not-touch names

Preferred table:

| Name | Sector / sleeve | Current state | Next review trigger |
|---|---|---|---|

### Page 6 — Risks, invalidation, and next actions

Include:
- what breaks the regime read
- what would upgrade or downgrade sector tilts
- stale/manual/fallback dependencies
- next concrete review actions

## Current candidate angle from latest artifacts

As of the latest available artifacts:
- leadership improving: Technology
- underexposed: Communication Services, Consumer Discretionary, Consumer Staples, Health Care, Materials, Real Estate, Utilities
- promotion-review candidates: CAT, ETN, GS, JPM, LLY, NVDA
- concentration warning: direct Technology at cap and AI-power correlated exposure elevated when ETN is included

Implication:
- The first PDF should not simply say “buy more Technology.”
- The useful document is a regime-aware sector positioning memo: stay selective risk-on, acknowledge Technology leadership and concentration risk, then identify underexposed sectors where promotion-review candidates or new research can improve balance without forcing bad entries.

## Trust rules

- If notes and artifacts disagree, notes win and the PDF waits.
- If validation is warning-grade, put that on Page 1.
- If proposed sector weights are included, mark them review-only and owner-gated.
- If a name is a promotion-review candidate, do not call it deployable unless deployment rules also agree.
