# Watchlist Promotion Candidate Packet Contract

## Purpose
Define the first bounded intake layer between the non-canonical watchlist and any future promotion decision.

This contract exists to expand option coverage without granting automatic deployment authority.

## Owner boundary
- `04. Research/Coverage and Watchlist.md` = consolidated tracking universe and thesis surface
- this packet = review-only candidate prep artifact
- `03. Portfolio/Execution Board.md` = canonical promotion / deployment-decision and technical-state owner
- `03. Portfolio/Portfolio Snapshot.md` = canonical portfolio posture / sizing owner

## Workflow boundary
Safe path:
1. watchlist / machine-tracked universe
2. promotion candidate packet
3. human promotion review
4. canonical owner decision

Unsafe path:
- coverage/watchlist -> automatic deployable-now promotion

## Packet posture
- consumer posture: `review_only`
- canonical mutation allowed: `false`
- deployment authority: `false`
- watchlist entitlement: `false`

## Required fields
- `schema_version`
- `generated_at_utc`
- `ticker`
- `proposed_lane`
- `source_surface`
- `thesis_evidence_source`
- `canonical_trigger_source`
- `canonical_portfolio_source`
- `thesis_exists`
- `levels_exist`
- `timing_posture` (`clean`, `blocked`, `stale`, or `unknown`)
- `portfolio_competition_assessed`
- `sector_cap_checked`
- `correlated_sleeve_checked`
- `regime_score_total`
- `regime_score_rank`
- `current_watch_state`
- `current_trigger_state`
- `entry_band_defined`
- `invalidation_defined`
- `numeric_entry_band_low`
- `numeric_entry_band_high`
- `numeric_stop`
- `band_propagation_validated`
- `sizing_tier_defined`
- `catalyst_window_status` (`clear`, `warning`, `blocked`, or `unknown`)
- `sector`
- `correlated_sleeve`
- `sector_cap_check`
- `five_gate_status`
- `missing_gates`
- `promotion_blockers`
- `promotion_candidate`
- `promotion_review_required`
- `owner_conflict_check`
- `sector_correlation_artifact`
- `current_canonical_status_tuple`
- `proposed_canonical_status_tuple`
- `canonical_status_move_required`
- `notes`

## Minimum gate logic
A candidate packet may mark `promotion_candidate: true` only if:
- thesis source is present
- trigger source is present
- regime score exists
- entry band is defined
- invalidation is defined
- numeric low/high/stop are present in the machine config or exact patch preview
- downstream propagation has been validated or explicitly marked pending/blocking
- sizing tier is defined
- catalyst window is not blocked
- sector-cap check is not breached

Even then:
- `promotion_review_required` must stay `true`
- no canonical note may be updated automatically

If a packet proposes `DEPLOYABLE`, `DEPLOYABLE NOW`, execution-lane entitlement, or any status tuple change with capital-action meaning, it must link a portfolio-mutation proposal artifact and remain `apply_allowed=false` until Randall approves the exact move.

## Five-gate mapping
Map packet evidence into the Execution Board gates:
1. thesis gate
2. macro and regime gate
3. technical gate
4. catalyst gate
5. risk and sizing gate

If any gate is `missing`, `warning`, or `failed`, the packet must fail closed.

## Stop lines
Stop and deny promotion if:
- coverage/watchlist is the only source
- entry band or stop is missing
- entry band or stop exists only as prose, placeholder, sentinel label, or dashboard-only text
- deployment/dashboard consumers would render `WATCH_DEFINED_INITIAL`, `WATCH_PULLBACK_INITIAL`, `TBD`, blank stop, or a false-green deployable state for the promoted ticker
- sector cap would be breached
- correlated sleeve stacking would worsen a known concentration issue
- catalyst timing is unresolved or inside a blocked window
- owner notes conflict materially
- the packet implies deployable-now status without explicit owner review

## Output classes
- `not_eligible`
- `needs_research`
- `candidate_review_ready`
- `blocked`

## Current intended use
Near-term use is manual / review-first:
- generate packet under `tmp/`
- review candidate against Execution Board and Risk Rules
- decide whether the name deserves explicit promotion review
- if a ticker is promoted to portfolio-review, run the promotion band-propagation closure gate before calling the promotion done: `validate_portfolio_config.py --strict`, `deployment_check.py`, `generate_dashboard.py`, and `validate_dashboard_state.py --write`

## Current non-goals
- no autonomous promotion
- no watchlist-based queue movement
- no automatic sizing changes
- no silent sector expansion
