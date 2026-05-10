# Daily Review Objects Contract

## Purpose

Define the bounded daily review-object layer that turns the existing finance refresh stack into ranked decision-prep packets without widening authority.

This layer exists to help Veritas act like a daily market-intelligence chief of staff:
- rank what matters
- escalate only the highest-signal items
- prepare owner-gated capital-deployment recommendations
- stop before canonical mutation, state changes, or execution

## Workflow under review

- workflow: daily decision-grade review objects / capital-deployment recommendation prep
- producers:
  - `python scripts/market_intelligence_event_router.py --window <window>`
  - `python scripts/daily_review_objects.py --window <window>`
- current phase: scheduled review-surface generation
- recommended next phase: keep this layer review-only until sector/correlation artifacts and state-history retention are wired

## Safe automation boundary

Allowed:
- read current machine artifacts
- rank names and system-level trust issues
- emit review objects
- emit escalation subsets
- emit owner-gated capital-deployment recommendation packets

Not allowed:
- canonical note mutation
- deployment-state mutation
- queue mutation
- trade execution
- silent portfolio or config changes

## Owner layer

Canonical owner judgment remains in:
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `07. Risk/Risk Rules.md`

This packet is a review surface only.

## Review windows

Supported windows:
- `morning`
- `post-close`
- `post-earnings`
- `sunday`

Outputs:
- `tmp/market-intelligence-events-morning.json`
- `tmp/market-intelligence-events-post-close.json`
- `tmp/market-intelligence-events-post-earnings.json`
- `tmp/market-intelligence-events-sunday.json`
- `tmp/daily-review-objects-morning.json`
- `tmp/daily-review-objects-post-close.json`
- `tmp/daily-review-objects-post-earnings.json`
- `tmp/daily-review-objects-sunday.json`

## Inputs

Core inputs:
- `tmp/deployment-readiness-surface.json`
- `tmp/deployment-check.json`
- `tmp/dashboard-validation.json`
- `tmp/run-summary-<window>.json`
- `tmp/band-proposals.json`
- `tmp/market-intelligence-events-<window>.json`

Window-specific summary inputs:
- morning: `tmp/premarket-snapshot.json`
- post-close / sunday: `tmp/daily-executive-brief.json`, `tmp/postmarket-snapshot.json`
- post-earnings: `tmp/post-earnings-prep.json` plus any available summary surfaces

## Ranking logic

The market-intelligence router is an artifact-derived v1 event/materiality layer. It may route dashboard trust issues, macro warnings, promotion-review names, near-deployment names, band-review debt, provider-calendar catalyst windows, and post-earnings prep packets into read-only event packets. It does **not** crawl broad web/news sources, ingest social rumor streams, or override the existing WF26 source-tier contract.

Priority order:
1. trust ceilings and contradictions that make the rest less trustworthy
2. promotion-review names already close enough to deserve owner attention
3. near-deployable names that are close to the band but still need discipline
4. timing-caution and post-earnings review names
5. risk-hold / review-debt names only when they materially contaminate trust

Ranking signals may use:
- surface state
- in-band / near-band status
- native `canonical_apply_eligible` flag from band proposals
- active catalyst timing
- trust-grade downgrades
- stale or blocking band-review debt

## Escalation rule

Escalate only a small subset:
- blocked / stop-line days: 2 items max
- warning-grade days: 3 items max
- clean days: 4 items max

System trust objects should be allowed into the escalation set before lower-priority ticker objects when trust is degraded.

When reporting escalations to Randall, do not stop at listing routed events. Each escalation should include a concrete recommended next action, not just a route label. The action should name the useful next tool, script, note, or review surface when one exists, for example: run and review `python scripts/entry_band_fetch.py <TICKER> --html --quiet` for entry-band questions; open the generated entry-band HTML; compare against the Technical Entry Sheet / Deployment Trigger Sheet; check earnings/catalyst timing; or route to owner promotion review. `Wait`, `review only`, or `owner approval required` is acceptable only when paired with the specific review/check that should happen next. Recommended actions must preserve the authority boundary: no trade execution, no automatic portfolio mutation, no inferred owner approval, and no canonical note mutation unless separately approved.

## Capital-deployment recommendation posture

Recommendation classes may include:
- `deploy_candidate`
- `wait_for_band`
- `wait_for_catalyst_clearance`
- `hold_promotion_review`
- `no_new_approval`

Rules:
- every recommendation must keep `owner_approval_required=true`
- no recommendation may imply autonomous execution
- no recommendation may imply canonical authority by itself
- trust-ceiling warnings must remain visible in the packet

## Stop lines

Fail closed or stay review-only if:
- workflow stop line is active
- dashboard validation is critical
- canonical mutation is not explicitly allowed
- key upstream artifacts are missing or stale enough to contaminate the packet

Even on clean days, this layer remains review-only in v1.

## Known trust gates still missing

Not wired yet:
- stable machine-readable sector/correlation check artifact
- append-only state-history / owner-outcome retention (`WF43` style history lane)

Because those are missing, this layer is recommendation-prep, not final portfolio judgment. Fresh-intelligence routing exists only as a read-only workspace-artifact router; broader external-source automation still requires a separate approved WF41-style widening pass.

## Validation / evidence

Proof checks:
- `python -m py_compile scripts\market_intelligence_event_router.py scripts\daily_review_objects.py`
- `python scripts\market_intelligence_event_router.py --window post-close`
- `python scripts\daily_review_objects.py --window post-close`
- `python scripts\test_market_intelligence_event_router.py`
- `python scripts\test_daily_review_objects.py`

This layer should stay downstream of the existing finance refresh owners, not become a parallel truth engine.
