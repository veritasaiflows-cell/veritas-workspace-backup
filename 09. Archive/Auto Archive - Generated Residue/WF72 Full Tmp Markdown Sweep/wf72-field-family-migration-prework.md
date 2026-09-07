# WF72 SQL-canon consumer / field-family migration prework

Status: plan-only, read-only. This does **not** expand SQL canon, mutate Markdown/canonical notes, mutate portfolio surfaces, infer owner approval, or authorize paper/live trades, account actions, or money movement.

## Current Phase 4A boundary

- SQL-canon cache: `tmp/veritas-canon-cache.sqlite`.
- Exact approved keys only:
  - `NVDA:earnings_lifecycle_status`
  - `NVDA:post_earnings_review_confirmed`
- Current consumer: `scripts/dashboard_payload.py` proof metadata only (`sqlCanonProofMetadata` / `sql_canon`).
- Fallback remains required. Dashboard recommendation, deployment, and action-state behavior must not change.

SQL canon/cache authority is limited to approved exact keys. Markdown/canonical note mutation is a separate authority path. Execution approval is separate again and is not granted by SQL rows, validators, dashboard labels, or deployable wording.

## Ranked migration batches

1. **Freshness/status first**
   - Existing Phase 4A keys: `NVDA:earnings_lifecycle_status`, `NVDA:post_earnings_review_confirmed`.
   - Candidate freshness keys with current clean matches: `deployment:source_freshness_classification`, `earnings:source_freshness_classification`.
   - Candidate deployment proof-status keys with current clean matches: `ETN`, `GOOG`, `GS`, `JPM`, `MSFT`, `NVDA`, `VRT`, `XOM` as `*:deployment_proof_status`.
   - Exclude for now: `BRK.B:deployment_proof_status`, `LMT:deployment_proof_status` (`sql_newer` / review needed), and other freshness keys that require Markdown/manual review.
   - Risk: deployable/status words can imply action. Keep owner approval and trade execution flags false.

2. **Entry-band / technical support second**
   - Candidate keys: `requires_registry_expansion`.
   - Known consumer terms: `entry_band_status`, `band_status`, `in_entry_band`, `below_stop`, band low/high/close labels, stop labels.
   - Must be shadow/no-drift first because these fields affect timing and no-chase decisions.

3. **Sector / sleeve / sizing draft later**
   - Candidate keys: `requires_registry_expansion`.
   - Known consumer terms: `sectors_relative`, `sector_weights`, `sector_map`, sleeve/candidate-sleeve labels, `sizing_rules`, weights, max-sector thresholds.
   - Highest authority risk: can look like portfolio construction or capital deployment approval.

## Consumer migration map

- `scripts/dashboard_payload.py`
  - Generalize Phase 4A cache reader into family/key allowlist.
  - Keep new fields in proof/trust metadata first.
  - Do not change `decision_queue`, deployment readiness, recommendation state, or action-state routing without no-drift proof.

- `scripts/dashboard_run_summary_consumer.py`
  - Add SQL-canon cache health only after a validator exists.
  - Degrade/warn on cache problems; never upgrade authority or alert severity from SQL canon alone.

- `scripts/today_card_generator.py`
  - Best first slice: consume the existing two Phase 4A NVDA keys as Today-card proof metadata only.
  - Preserve generated-artifact/Markdown fallback and the review-only/no-execution banner.

- `scripts/run_summary_refresh.py`
  - Later: include SQL-canon cache status, family count, exact key count, failed checks, and fallback requirement.
  - Do not replace artifact-index or source-freshness validation.

- `scripts/deployment_readiness_surface.py`
  - Do **not** migrate early as an authority consumer.
  - Keep deployment proof status shadow-only until no-drift proves state/bucket/recommendation/action fields do not change.

## Validator / no-drift matrix

- Preflight: JSON parses; candidate keys are exact; no `requires_registry_expansion` key is written to cache; authority boundary and forbidden flags match.
- Cache: exact approved key set only; source artifact hash, note excerpt hash, validator status, reconciliation status, freshness status, and rollback hash present; consumers open cache read-only.
- Consumer compare: run before/after with identical inputs; normalize timestamps/run IDs and expected additive SQL metadata only.
- Blockers: changed recommendation, deployment/action state, owner-action text, ranking, authority flags, entry-band status, or fallback failure.
- Existing gates: `py_compile`, `test_artifact_index.py`, `artifact_index.py incremental/validate`, `test_dashboard_acceptance.py`, `today_card_validator.py` when Today changes, and deployment/capital validators if deployment readiness changes.

## Rollback / fallback requirements

- Export rollback rows before each activation and record `rollback_export_sha256`.
- Keep generated-artifact/Markdown fallback loaders in the same slice.
- Missing/stale/mismatched cache must degrade to fallback, not crash or widen authority.
- Family/key allowlist must disable a slice without file deletion.
- Rollback proof must show key counts before/after and no-drift after fallback/rollback.

## Recommended first implementation slice

Implement **consumer-only Today-card proof metadata** for the two already approved Phase 4A keys:

- `NVDA:earnings_lifecycle_status`
- `NVDA:post_earnings_review_confirmed`

No new cache keys, no registry expansion, no Markdown/canon/portfolio mutation, no deployment/action-state behavior change, no cron/config/runtime change, and no trade/account/paper/live authority. Acceptance: Today validator clean, normalized Today-card compare shows no decision/action/authority drift except additive SQL proof metadata, cache-missing fallback test passes, and SQL/artifact validators remain clean.
