# WF72 Gates 13-16 Phase Approach

Status: **review-only planning; no implementation; no activation**  
Generated: 2026-05-24 12:34 MST

This is a planning artifact for optional WF72 work **after Gate 12**. It does not approve or perform SQL/cache activation, canon/Markdown/portfolio mutation, dashboard action-state changes, cron-direct apply, trade/account/paper/live/money actions, config/auth/channel/service mutation, deletes, moves, or owner-approval inference.

## Current boundary from Gate 11

- Active SQL proof-metadata/cache set remains exactly **13 keys** under the Phase 7 boundary.
- `portfolio:source_freshness_classification` remains held because the current state is `manual_dependency` / `review_required`, not fresh/current.
- Current `deployment_proof_status` field and values remain permanent hold/no SQL-canon migration.
- Higher-risk families remain future exact-gate, proposal-only staging, or never-SQL-canon.
- `canon_proposal_staging` residue remains display/index/proof context only until separately hardened.

## Gate 13 - Portfolio source freshness redesign

**Objective:** design a separate degraded/manual-dependency freshness contract for `portfolio:source_freshness_classification` without reusing the current fresh/current activator assumption.

**Allowed outputs**
- Review-only redesign contract for portfolio manual-dependency metadata.
- Shadow-only proof comparing proposed display value to portfolio-config/manual-review owner source.
- Negative tests proving `manual_dependency` cannot be normalized to fresh/current.
- Future exact-approval packet template.

**Forbidden outputs**
- Activating the field under the current low-risk/fresh-current contract.
- SQL/cache writes or SQL-canon expansion.
- Treating source freshness as owner truth, approval, or portfolio mutation permission.
- Canon/portfolio edits, cron-direct apply, dashboard action-state changes, or trade/account/paper/live/money/config/auth/channel/service mutation.

**Implementation phases**
1. Contract design: define neutral degraded values and owner fallback source.
2. Shadow extractor plan: read-only/preflight mode in existing preflight/guard surfaces.
3. Consumer no-drift plan: display as trust metadata only.
4. Future gate packet: exact key/vocabulary, fallback equality, rollback/export, guard/test update, main-session authority review.

**Acceptance gates / proof**
- Phase 8 blockers are resolved by design, not ignored.
- No fresh/current hard-code is reused.
- Fallback equality to owner source is proven in shadow.
- Dashboard/Today/run-summary no-drift protects action/recommendation/deployment fields.
- Guard fails closed unless exact future key/vocabulary gate exists.

**Likely owners:** `scripts/sql_canon_field_family_preflight.py`, `scripts/sql_consumer_authority_guard.py`, `scripts/dashboard_payload.py`, Phase 8 closeout artifacts, portfolio-config/manual-review owner surfaces.

## Gate 14 - Neutral deployment display field redesign

**Objective:** replace the current action-worded `deployment_proof_status` concept with a neutral display-only evidence/completeness field that cannot drive dashboard buckets, recommendations, approval, or execution semantics.

**Allowed outputs**
- Neutral proof/display vocabulary proposal.
- Mapping showing current values are not migrated as SQL-canon values.
- Shadow inventory and no-drift proof plan.
- Negative tests blocking action words.

**Forbidden outputs**
- SQL-canon rows for `deployment_proof_status` or current values.
- Renaming current action statuses without changing semantics.
- Dashboard recommendation/deployment/action-state behavior changes.
- Any implication of deploy/buy/sell/hold/approval/paper/live/account authority.

**Implementation phases**
1. Semantic red-team of field names and values.
2. New display-only field contract.
3. Additive shadow payload plan.
4. Negative and no-drift tests.

**Acceptance gates / proof**
- `deployment_proof_status` remains excluded and active rows remain 0.
- Proposed vocabulary passes neutral-display review.
- Dashboard action buckets/cards/ranking/recommendation state unchanged.
- Guards block current action values and action words.
- Exact future approval before activation is considered.

**Likely owners:** `scripts/deployment_readiness_surface.py` as a current action-state producer to avoid, `scripts/dashboard_payload.py`, `scripts/sql_consumer_authority_guard.py`, `scripts/test_dashboard_acceptance.py`, Phase 9 closeout artifacts, `03. Portfolio/Execution Board.md` as read-only context.

## Gate 15 - Higher-risk family exact-gate work

**Objective:** convert Phase 10 taxonomy into exact gate / proposal-only / never-SQL-canon procedures for higher-risk families.

**Allowed outputs**
- Exact gate templates for entry/stop display metadata candidates only.
- Proposal-only staging hardening plan for sizing/sleeve/cash/weight and risk-rule packets.
- Never-SQL-canon guard requirements for trade/account/paper/live execution and credential/config families.
- Validator/audit requirements keeping `proposal_apply_allowed=0` outside exact approved gates.

**Forbidden outputs**
- Broad SQL-canon migration for entry, stop, sizing, sleeve, cash, weight, risk rules, execution/account/paper/live, credentials, or config.
- SQL as portfolio truth, approval, apply authority, order sizing, risk entitlement, execution permission, or credential source.
- Cron-direct apply or paper/live submit/cancel/sell authority.
- Canonical portfolio/model mutation from this gate.

**Implementation phases**
1. Family contract matrix: future exact-gated metadata, proposal-only staging, or never SQL-canon.
2. Entry/stop exact-gate design as display metadata only.
3. Proposal-staging hardening for mixed historical/pending residue.
4. Never-SQL-canon guards for execution/account/credential surfaces.

**Acceptance gates / proof**
- Every higher-risk family has exactly one route.
- Proposal staging cannot produce apply permission outside a separate gate.
- Entry/stop candidates require owner-truth fallback equality and no action-state drift.
- Sizing/sleeve/cash/weight/risk-rule stay proposal-only unless a separate bounded workspace maintenance gate exists.
- Execution/account/paper/live and credential/config are permanently blocked from SQL-canon authority.

**Likely owners:** Phase 10 taxonomy, `scripts/artifact_index.py`, `scripts/sql_consumer_authority_guard.py`, dashboard display guards, `03. Portfolio/Execution Board.md`, portfolio-config, `07. Risk/*`, WF63/WF67 guardrails.

## Gate 16 - Full OS revamp closeout / hardening pass

**Objective:** close WF72 as an OS efficiency revamp by consolidating continuity, Active Workflows routing, validators, proof lookup, boot/load overhead, and final authority boundaries without adding another control plane.

**Allowed outputs**
- Closeout packet with completed gates, held gates, accepted residue, and owner routes.
- Review-only patch proposals for continuity/procedure wording if needed after proof.
- Validator coverage map and proof lookup map centered on SQL cockpit as derived proof/index/staging only.
- Boot/load overhead assessment and consolidation recommendations.

**Forbidden outputs**
- Unapproved Markdown/canon/portfolio mutations.
- Archive/move/delete actions without reference checks and owner approval.
- Config/auth/channel/service mutation.
- Cron-direct apply or scheduled canonical mutation.
- Claims that SQL/proof artifacts are portfolio truth, approval, apply authority, or execution authority.

**Implementation phases**
1. Closeout inventory using SQL cockpit for lookup, then direct artifact inspection for claims.
2. Validator map: artifact-index validation, SQL guard, dashboard acceptance, Today validator, drift/freshness/risk validators.
3. Boot/load compression: route to owner surfaces rather than copying history.
4. Final boundary wording proposal.
5. Independent closeout QA.

**Acceptance gates / proof**
- One concise WF72 closeout source exists and Active Workflows points to the right status/owner.
- Startup/boot files route to owner surfaces/proof indexes without long duplicated history.
- Validators prove forbidden authority flags false, proposal apply allowed false outside exact gates, and dashboard action-state unchanged.
- Held/future gates have owner, stop lines, and next action.
- Archive/move/delete/config/channel/service items remain owner-approved-only.

**Likely owners:** WF72 continuity, Active Workflows, Startup Truth Index, SQLite Retrieval Index Procedure, `scripts/README.md`, `skills/sqlite/SKILL.md`, `scripts/artifact_index.py`, Phase 11 and Gates 13-16 artifacts.

## Recommended sequence

1. Gate 13 first: one known held key and concrete manual-dependency contract gap.
2. Gate 14 second: deployment wording is semantically hazardous and must stay conservative.
3. Gate 15 third: harden higher-risk family routing before any portfolio-context experiments.
4. Gate 16 last: close only after optional gates are closed, held, or explicitly deferred.

## Main recommendation

Do **not** implement Gates 13-16 until Gate 12 is closed and Randall/main-session explicitly scopes the next gate. If continuing, Gate 13 is the safest optional next planning-to-proof lane; Gate 14 and Gate 15 need stricter authority review because their vocabulary can imply action, allocation, risk, or execution authority.
