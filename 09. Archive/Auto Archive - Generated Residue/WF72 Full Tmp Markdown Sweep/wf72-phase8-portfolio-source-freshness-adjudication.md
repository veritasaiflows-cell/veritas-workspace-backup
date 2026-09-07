# WF72 Phase 8 - Portfolio source freshness adjudication

- Status: `held_not_safe_currently`
- Candidate: `portfolio:source_freshness_classification`
- Recommendation: Do not activate now. Keep held behind separate gate because the live value is manual_dependency/review_required, presentation is false, and the source is the portfolio config spine with owner-truth/manual-review semantics.

## Decision

Keep held. Current live/fallback value is `manual_dependency`, with `trust_level=review_required`, `usable_for_presentation=false`, and `usable_for_canonical_mutation=false`. That is useful warning metadata, but not safe to promote into SQL-canon metadata without a separate neutral contract because the underlying source is the portfolio config spine and manual review policy.

## Live source / fallback path

- SQL cockpit row: source_file=`tmp/dashboard-data.json`, path=`tmp/portfolio-config.json`, classification=`manual_dependency`, trust=`review_required`, presentation=`0`, canonical_mutation=`0`
- SQL cockpit row: source_file=`tmp/dashboard-validation.json`, path=`tmp/portfolio-config.json`, classification=`manual_dependency`, trust=`review_required`, presentation=`0`, canonical_mutation=`0`

- Current fallback path: `tmp/dashboard-data.json -> trust.source_freshness.sources[source_key=portfolio].classification`
- Underlying source path: `tmp/portfolio-config.json`
- Fallback value: `manual_dependency`

## If later deemed safe, exact code/test changes

- `scripts/sql_canon_field_family_preflight.py`: Replace the unconditional portfolio_source_freshness_requires_separate_owner_canon_gate blocker with an exact Phase-8-approved portfolio metadata gate; keep activation_allowed_by_preflight false unless fallback value, source hashes, manual-dependency wording, and authority flags match the new contract.
- `scripts/sql_canon_low_risk_phase3_activate.py`: Do not edit Phase 7 constants in place. Add a new Phase 8 activation path/boundary with approved key set including portfolio:source_freshness_classification only if explicitly approved; require preactivation export/rollback and source_path hash capture.
- `scripts/sql_consumer_authority_guard.py`: Add a separate Phase 8 approved-key tuple/boundary or parameterized extension; require fallback value equality for portfolio, forbid use when usable_for_presentation is false unless the approved contract explicitly allows manual_dependency display metadata, and preserve fail-closed behavior.
- `scripts/dashboard_payload.py`: Add portfolio:source_freshness_classification to fallback_values_by_key and approved metadata only as proof metadata; no changes to decision_queue, action_state, deployment, portfolio, sizing, sleeve, cash, or recommendation behavior.
- `scripts/test_artifact_index.py`: Add Phase 8 tests proving exact key set, no extra portfolio/field-family rows, fallback-missing fail-closed behavior, fallback mismatch blocks SQL read, forbidden authority flags stay false, and dashboard acceptance/no-drift remains unchanged.

## Stop lines

- Do not activate while value remains manual_dependency/review_required without an explicit Phase 8 neutral metadata contract.
- Do not treat manual dependency as owner approval, portfolio truth, canonical mutation authority, or dashboard action-state input.
- Do not widen dashboard recommendations/deployment/action behavior.
- Do not write SQL cache rows or modify Markdown/canon/portfolio state from this review artifact.

## Validation / proof

- Read-only query of v_cockpit_source_freshness found two portfolio rows (dashboard-data and dashboard-validation), both manual_dependency/review_required, usable_for_presentation=0, usable_for_canonical_mutation=0.
- Read-only query of tmp/veritas-canon-cache.sqlite found zero rows for portfolio:source_freshness_classification.
- Existing preflight candidate remains hold_separate_gate_shadow_only with blockers portfolio_source_freshness_requires_separate_owner_canon_gate and not_fresh_or_current.
- python scripts\artifact_index.py validate -> status=ok checks=27 failed=0.

No SQL activation/write, Markdown/canon/portfolio mutation, owner-approval inference, cron-direct apply, dashboard action/recommendation/deployment behavior change, trade/account/paper/live action, money movement, or config/auth/channel/service mutation was performed.
