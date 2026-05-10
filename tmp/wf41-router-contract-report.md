# WF41 Router Contract Report

## Verdict
closeout-vs-more-implementation: **bounded implementation closeout for the current artifact-derived v1 router; broader WF41 source-tier expansion still requires a separate policy/design pass.**

The existing router was already review-only and consumed approved workspace artifacts only. The smallest real contract gap was that routed events did not carry explicit per-event source trust/freshness metadata, and the packet did not explicitly surface unresolved source-truth / no-route behavior. I patched only that contract surface.

## Files changed
- `scripts/market_intelligence_event_router.py`
  - Added normalized per-event `source_trust` and `source_freshness` fields.
  - Added source-context enrichment from the packet's required/optional source artifact records.
  - Added `unresolved_truth` event generation when source freshness/trust is not clean.
  - Added explicit `no_route` event helper for empty material-event windows.
  - Preserved review-only authority flags: `canonical_mutation_allowed=false`, `deployment_state_mutation_allowed=false`, `trade_execution_allowed=false`.
- `scripts/test_market_intelligence_event_router.py`
  - Added assertions for per-event source trust/freshness fields.
  - Added assertion that partial/stale live source truth emits an `unresolved_truth` event.
  - Added direct no-route event contract coverage.
- Refreshed artifacts through required proof runs:
  - `tmp/market-intelligence-events-post-close.json`
  - `tmp/daily-review-objects-post-close.json`

## Tests / proof run
- `python -m py_compile scripts\market_intelligence_event_router.py scripts\test_market_intelligence_event_router.py` — passed
- `python scripts\market_intelligence_event_router.py --window post-close` — passed; emitted 23 events / 5 escalations
- `python scripts\test_market_intelligence_event_router.py` — passed
- `python scripts\daily_review_objects.py --window post-close` — passed; consumed refreshed router packet; emitted 16 review objects / 3 escalations / 1 capital recommendation
- `python scripts\test_daily_review_objects.py` — passed

Additional spot check: refreshed router artifact contains an `unresolved_truth` event ranked 8 with `materiality_score=4`, `recommended_route=risk_review`, `urgency=today`, `source_trust=review_required`, and `source_freshness.classification=partial`.

## Remaining gaps
- The router remains an artifact-derived v1 sidecar; it does not crawl broad web/news sources, ingest social streams, or perform external source automation.
- WF26-style approved source-tier policy is still represented by existing artifact/provider labels, not a broad new external source-tier map.
- Broader source-tier expansion, external intake, unresolved-truth schema standardization across non-workspace sources, or scheduled widening should be handled as a separate owner-gated WF41 implementation/design pass.

## Authority statement
This router is **review-only**. It may generate event/materiality packets, unresolved-truth packets, and no-route decisions under `tmp/`, but it may not mutate canonical finance notes, thesis state, deployment state, portfolio/risk rules, config/auth/channel/network state, or execute/recommend trades as approved actions. `owner_review_required` remains true and all canonical/deployment/trade mutation flags remain false.
