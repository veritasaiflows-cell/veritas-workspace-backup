# WF72 Phases 8-11 Full Activation Readiness Plan

- Status: `ready_for_bounded_phase_8_start`
- Current active SQL-canon keys: `13`
- Boundary: `phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority`

## Phases

### Phase 8 - Portfolio source-freshness separate-gate adjudication

Goal: Decide whether portfolio:source_freshness_classification can migrate as non-authoritative proof metadata or must remain permanently held.

**Acceptance**
- activation packet names exact key
- manual-dependency/owner-truth wording cannot imply approval or canonical portfolio mutation
- guard blocks on missing/mismatched fallback
- artifact-index validate and dashboard acceptance pass

**Stop lines**
- portfolio mutation implication
- owner approval inference
- manual dependency being treated as canonical truth
- dashboard action/recommendation behavior drift

### Phase 9 - Deployment/status wording redesign or permanent hold

Goal: Normalize deployment_proof_status into non-authoritative display metadata or keep it outside SQL-canon.

**Acceptance**
- either reject/permanent hold with proof, or exact normalized non-action metadata contract exists
- no DEPLOYABLE/DO NOT TOUCH/PROMOTION REVIEW wording can be read as instruction or owner approval
- no dashboard action-state behavior drift

**Stop lines**
- any wording implying buy/sell/deploy/do-not-touch authority
- portfolio/cash/sizing/risk-rule linkage
- trade/account/paper/live implication

### Phase 10 - Higher-risk family separation and activation taxonomy

Goal: Classify remaining families into never-SQL-canon, proposal-only SQL staging, or future exact-gated metadata candidates.

**Acceptance**
- taxonomy artifact has per-family authority class, owner, validator, and route
- no execution/account/config/credential family enters SQL-canon authority
- portfolio mutation families remain gated apply/proposal only

**Stop lines**
- SQL row as approval/apply source
- credential/config exposure
- execution entitlement

### Phase 11 - Full activation readiness packet

Goal: Assemble final readiness proof for all approved/held/rejected SQL-canon families without silently widening authority.

**Acceptance**
- all active keys have fallback map and value-equality guard
- all held/rejected keys named with reasons
- all validators pass
- rollback drill uses temp copy
- no authority flags widened
- next phase requires exact approval if any new family moves

**Stop lines**
- unbounded full migration claim
- cron-direct canon/apply
- Markdown/canon/portfolio mutation without gated apply
- trade/account/paper/live authority

## Recommended next action

Start Phase 8 with a bounded adjudication/proof lane for portfolio:source_freshness_classification only; do not touch deployment/status or higher-risk families in the same write pass.
