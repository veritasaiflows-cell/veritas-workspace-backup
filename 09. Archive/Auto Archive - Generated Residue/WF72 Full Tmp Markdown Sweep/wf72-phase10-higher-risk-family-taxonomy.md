# WF72 Phase 10 - Higher-risk family taxonomy

- Generated: `2026-05-24T18:41:31Z`
- Status: `complete_review_only_taxonomy_no_activation`
- Boundary: `phase10_review_only_taxonomy_no_sql_cache_write_no_canon_or_portfolio_mutation`
- SQL/cache writes: **not allowed / not performed**
- Canon/Markdown/portfolio mutation: **not allowed / not performed**
- Dashboard behavior change: **not allowed / not performed**

## Current active SQL-canon metadata preserved
Only the existing 13 low-risk metadata keys remain active under `phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority`. They are dashboard proof metadata only, fallback-required, and carry no approval/apply/execution authority.

## Classification matrix

| Family | Classification | Can ever be SQL-canon? | Route |
|---|---|---|---|
| entry/stop metadata | `future_exact_gated_metadata_candidate` | yes_only_as_future_exact_gated_display_metadata_not_apply_or_execution_source | Keep out of active SQL-canon now; route changes to proposal/gated-apply, not cache activation. |
| sizing/sleeve/cash/weight metadata | `proposal_only_sql_staging` | no_for_active_sql_canon_under_current_authority; staging_yes_for_review_proposals | Use SQL as review/proposal staging only; keep canonical allocation truth in owner notes/config and gated apply artifacts. |
| risk-rule metadata | `proposal_only_sql_staging` | no_for_active_sql_canon_under_current_authority; staging_yes_for_review_proposals | Keep risk rules in owner guardrail surfaces; SQL may stage proposed deltas and proof links only. |
| trade/account/paper/live execution metadata | `never_sql_canon` | no | Never route execution/account/paper/live authority through SQL-canon. Keep as guarded workflow telemetry only. |
| credential/config metadata | `never_sql_canon` | no | Never place credential/config truth in SQL-canon; at most index redacted validation status. |
| portfolio source freshness from Phase 8 | `held_permanent_hold_current_contract` | yes_only_if_redesigned_as_degraded_manual_dependency_metadata_with_exact_gate; no_under_current_contract | Remain held; do not activate or write cache rows. |
| deployment_proof_status from Phase 9 | `held_permanent_hold_current_field` | no_for_current_deployment_proof_status_field; possible_only_as_new_neutral_display_metadata_after_exact_gate | Permanent hold for current field/value set; do not migrate to SQL-canon. |

## entry/stop metadata
- Classification: `future_exact_gated_metadata_candidate`
- Authority class: portfolio-context metadata; owner-gated workspace portfolio/canon maintenance when changing bands/stops; not execution authority
- Owner surface: 03. Portfolio/Execution Board.md and portfolio-config/entry-band owner surfaces
- Allowed outputs:
  - review-only display of current canonical band/stop context
  - proposal packets for band/stop changes through gated apply path
  - derived proof/no-drift comparison rows outside SQL-canon activation
  - future exact-key metadata cache only if it mirrors already-approved owner truth and cannot change dashboard action state
- Forbidden outputs:
  - owner approval inference
  - trade/account/paper/live execution entitlement
  - money movement
  - cron-direct canonical apply
  - dashboard recommendation/deployment/action-state behavior change
  - using SQL row as entry-band/stop canonical source before exact gate
  - promotion to deployable/buy/sell/wait state
  - portfolio mutation without WF64-style gated preview, approval artifact, backup/rollback, and validator proof
  - broad field-family migration containing entry, stop, band, sizing, sleeve, cash, risk, or execution terms
- Required validator/proof:
  - scripts/sql_consumer_authority_guard.py must fail closed for current forbidden entry terms unless explicitly changed by a later exact approval
  - before/after dashboard payload no-drift for recommendation/deployment/action-state/ranking/authority flags
  - artifact_index validate and dashboard acceptance tests
  - WF64/gated portfolio maintenance validator proof for any actual canonical band/stop edit
  - fallback equality against owner note/artifact and rollback/export drill before any SQL-canon candidate activation
- Rationale: Entry and stop values are action-adjacent. They may be useful dashboard context, but a SQL row must not become the trigger, approval, or canonical portfolio source.
- Future gate: Requires a separate written approval artifact naming exact keys/fields, neutral display contract, forbidden-family guard update, fallback equality, no-drift proof, rollback/export proof, and main-session authority review.

## sizing/sleeve/cash/weight metadata
- Classification: `proposal_only_sql_staging`
- Authority class: portfolio allocation and capital-control metadata; proposal/review only unless a separate bounded workspace maintenance gate applies exact edits
- Owner surface: portfolio model / allocation / cash reserve owner notes and portfolio-config surfaces
- Allowed outputs:
  - SQL-indexed proposal staging with proposal_apply_allowed=false unless separately gated
  - review-only concentration/cash/sleeve diagnostics
  - draft proposed sizing/weight/sleeve changes for owner/main-session review
- Forbidden outputs:
  - owner approval inference
  - trade/account/paper/live execution entitlement
  - money movement
  - cron-direct canonical apply
  - dashboard recommendation/deployment/action-state behavior change
  - active SQL-canon rows for current portfolio weights/cash/sizing/sleeve truth
  - model/cash/risk entitlement changes from SQL cache
  - sizing an order or paper/live execution package from staged SQL alone
- Required validator/proof:
  - artifact_index authority guard: canon_proposal_staging proposal_apply_allowed must remain 0 outside exact gate
  - portfolio/risk concentration validators and source-lineage/evidence-status checks
  - explicit proposal preview/diff hash, backup/rollback, post-apply validation for any approved workspace maintenance edit
  - dashboard no-drift proof if display consumers read staged diagnostics
- Rationale: Sizing, sleeve, cash, and weights are allocation authority. Treating SQL as canon would create a second portfolio truth source and could imply capital deployment authority.

## risk-rule metadata
- Classification: `proposal_only_sql_staging`
- Authority class: risk/control policy metadata; review/proposal only, not SQL-canon authority
- Owner surface: 07. Risk/* guardrails, portfolio risk-rule notes/config, and workflow-specific guardrail files
- Allowed outputs:
  - review-only risk-rule findings and stop-line evidence
  - proposal packets for rule updates requiring owner/main-session gate
  - SQL indexing of validator findings/provenance with authority boundary preserved
- Forbidden outputs:
  - owner approval inference
  - trade/account/paper/live execution entitlement
  - money movement
  - cron-direct canonical apply
  - dashboard recommendation/deployment/action-state behavior change
  - changing risk thresholds, stop discipline, cash reserve minimums, or execution entitlements from SQL rows
  - using SQL staging as risk-rule canon
  - weakening stop lines or paper/live isolation guardrails
- Required validator/proof:
  - artifact_index validate: forbidden authority flags false and canon proposal apply not allowed
  - domain risk validators for the affected rule set
  - exact approval artifact plus rollback/post-apply proof for any rule mutation
  - independent authority review when rule wording could affect execution or account permissions
- Rationale: Risk rules are control authority. SQL-canon migration would risk policy drift and could silently widen permission boundaries.

## trade/account/paper/live execution metadata
- Classification: `never_sql_canon`
- Authority class: execution/account authority surface; may be monitored as review-only telemetry, never promoted to SQL-canon authority
- Owner surface: WF63/WF67 paper-trading guardrails and explicit scoped paper artifacts; live account authority remains owner-only/external
- Allowed outputs:
  - review-only telemetry/status display with explicit no-live/no-money/no-account-mutation wording
  - guard validation evidence that paper/live isolation and kill switches are intact
  - manual/main-session notification artifacts for scoped paper pilots only
- Forbidden outputs:
  - owner approval inference
  - trade/account/paper/live execution entitlement
  - money movement
  - cron-direct canonical apply
  - dashboard recommendation/deployment/action-state behavior change
  - SQL-canon activation of order state, endpoint state, account state, broker permissions, or execution eligibility
  - paper/live submit/cancel/close-position/liquidation authority from dashboard/SQL/cache rows
  - promotion of paper results to live deployment or portfolio mutation authority
  - credential, endpoint, or account mutation
- Required validator/proof:
  - WF63/WF67 paper/live isolation validators and kill-switch/audit-log checks
  - dashboard payload forbidden-phrase/authority-field validation
  - artifact_index authority guard for forbidden true flags
  - manual scoped paper instruction or advisor-capital-package artifact when paper actions are separately allowed
- Rationale: Execution/account state is external-action authority. SQL-canon would be unsafe because it could be mistaken for permission to act.

## credential/config metadata
- Classification: `never_sql_canon`
- Authority class: security/runtime configuration authority; never finance SQL-canon
- Owner surface: OpenClaw config/auth surfaces and local credential stores outside finance canon; no secrets in workspace notes/artifacts
- Allowed outputs:
  - redacted existence/readiness status when required by an approved workflow
  - validation that no credentials/secrets are exposed and endpoints are isolated
  - manual approval packet for config/auth/channel/service changes
- Forbidden outputs:
  - owner approval inference
  - trade/account/paper/live execution entitlement
  - money movement
  - cron-direct canonical apply
  - dashboard recommendation/deployment/action-state behavior change
  - secret/token/key/credential values in SQL, Markdown, dashboard, logs, or chat
  - config/auth/channel/service mutation from SQL rows or cron
  - endpoint or permission changes without explicit owner approval and secure procedure
- Required validator/proof:
  - secret redaction/no-credential-leak checks
  - OpenClaw config/auth approval procedure and runtime validation when a change is explicitly authorized
  - paper/live endpoint isolation validators where applicable
  - artifact_index forbidden authority flags remain false
- Rationale: Credential/config data is security authority, not financial canon metadata. SQL-canon would increase exposure and mutation risk.

## portfolio source freshness from Phase 8
- Classification: `held_permanent_hold_current_contract`
- Authority class: manual-dependency trust metadata; held because current activator assumes fresh/current and would mislabel portfolio owner-truth dependency
- Owner surface: portfolio-config/manual-review spine and owner portfolio notes
- Allowed outputs:
  - shadow/review-only display of manual_dependency/review_required state
  - future degraded-manual-dependency metadata proposal with explicit fallback and no-drift proof
  - source trust warning/degrade output that cannot imply canonical mutation authority
- Forbidden outputs:
  - owner approval inference
  - trade/account/paper/live execution entitlement
  - money movement
  - cron-direct canonical apply
  - dashboard recommendation/deployment/action-state behavior change
  - activating portfolio:source_freshness_classification under the current fresh/current contract
  - treating manual_dependency as fresh/current
  - using source freshness as owner truth, approval, or portfolio mutation permission
- Required validator/proof:
  - separate degraded portfolio manual-dependency metadata contract
  - exact approval artifact naming portfolio:source_freshness_classification or replacement key
  - fallback equality against portfolio-config/manual-review owner source
  - dashboard/Today/run-summary no-drift proof and negative fail-closed tests
  - rollback/export drill and authority guard update
- Rationale: Phase 8 closeout found manual_dependency, review_required, usable_for_presentation=false, usable_for_canonical_mutation=false, and no no-drift proof for the portfolio exception.
- Future gate: Future reconsideration must not reuse the current activator's fresh/current assumption.

## deployment_proof_status from Phase 9
- Classification: `held_permanent_hold_current_field`
- Authority class: action/deployment semantic display field; current field/value set permanently held from SQL-canon
- Owner surface: deployment_readiness_surface.py/dashboard action-state producer and 03. Portfolio/Execution Board.md review surface
- Allowed outputs:
  - continue generated-artifact/dashboard display under existing review-only boundaries
  - future neutral replacement vocabulary proposal only after authority review
  - shadow inventory for QA/adjudication, not active cache/canon rows
- Forbidden outputs:
  - owner approval inference
  - trade/account/paper/live execution entitlement
  - money movement
  - cron-direct canonical apply
  - dashboard recommendation/deployment/action-state behavior change
  - SQL-canon rows for DEPLOYABLE NOW / ALMOST DEPLOYABLE / DO NOT TOUCH / PROMOTION REVIEW values
  - dashboard action bucket/card behavior changes from SQL
  - treating deployment wording as buy/sell/deploy/hold approval
- Required validator/proof:
  - full dashboard/Today/run-summary no-drift proof for any neutral replacement field
  - negative fail-closed tests blocking action words
  - manual authority review and exact approval artifact
  - sql_consumer_authority_guard allowlist remains excluding deployment_proof_status unless a new neutral field is approved
- Rationale: Phase 9 closeout found field name and values are action/deployment semantic and feed dashboard action-state behavior. Current guard excludes this family.

## Global stop lines
- This artifact does not activate or write SQL/cache rows.
- SQL rows cannot be approval, apply, execution, account, credential, cash, sizing, risk-rule, or portfolio truth authority.
- Generated artifacts/dashboards remain proof or review surfaces unless a separate gated apply path says otherwise.
- Cron may not directly apply canonical/portfolio edits from this taxonomy.
- Any future SQL-canon expansion requires exact keys/fields, written approval artifact, fallback equality, no-drift proof, rollback/export drill, authority guard update, and main-session review.

## Recommendation
Preserve the 13 active low-risk metadata keys only. Keep Phase 8 portfolio freshness held, Phase 9 deployment_proof_status permanently held for the current field, route allocation/risk families to proposal-only staging, and never route execution/account/credential/config authority through SQL-canon.
