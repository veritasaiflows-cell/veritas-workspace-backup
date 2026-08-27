# Workflow 56 - Portfolio Mutation Proposal Object and Gated Apply Helper

## Objective

Build the automation bones for portfolio-change proposals without granting portfolio-change authority.

This workflow prepares typed review-only proposal objects for:
- sleeve additions, sleeve rebalancing, cash-target changes, and sleeve-structure changes
- ticker promotion / demotion / lane changes with evidence
- canonical status moves across Watchlist, Trigger Sheet, Technical Sheet, Portfolio Snapshot, Coverage Universe, and `tmp/portfolio-config.json`

## User request trigger

Opened 2026-05-10 after Randall asked Veritas to audit the workflows and prepare a phased path toward automating sleeve and ticker-status updates while keeping actual mutations owner-gated.

Audit inputs:
- `tmp/portfolio-mutation-automation-audit.md`
- `tmp/portfolio-mutation-automation-audit.json`

## Current phase

Status: **queued / bounded design and schema workflow**.

Current safe automation level:
1. review-only artifact generation
2. review packet generation
3. exact patch preview generation

Not yet safe:
- write-capable apply helper
- scheduled apply
- autonomous promotion/demotion
- inferred owner approval

## Owner layer

| Output / fact | Owner layer |
|---|---|
| Proposal artifact | `tmp/portfolio-mutation-proposals/` |
| Watchlist membership / tracking label | `02. Markets/Watchlist.md` |
| Thesis and evidence caveats | `04. Research/Coverage Universe.md` |
| Technical levels and invalidation | `03. Portfolio/Technical Entry and Invalidation Sheet.md` |
| Deployment / action state | `03. Portfolio/Deployment Trigger Sheet.md` |
| Sleeve, draft weight, portfolio role | `03. Portfolio/Portfolio Snapshot.md` |
| Risk caps / sizing rules | `07. Risk/Risk Rules.md` |
| Machine spine fields | `tmp/portfolio-config.json` |

## Safe automation boundary

Allowed before explicit Randall approval:
- detect possible sleeve, rebalance, promotion/demotion, or canonical-status candidates
- generate typed JSON / Markdown proposal packets
- compute pro-forma concentration, sleeve, and sector-risk checks
- run owner-conflict and status-tuple checks
- draft exact patch previews under `tmp/`
- route the proposal to review surfaces

Blocked before explicit Randall approval:
- applying weights, cash target, sleeve structure, ticker promotion/demotion, owner approval, sizing, risk-rule, execution-entitlement, or canonical status changes
- changing real accounts or placing trades
- letting cron apply a proposal
- treating clean validation as approval

## Phased automation roadmap

### Phase 1 - Typed proposal schema and validators

Deliverables:
- schema for `sleeve_change`, `rebalance`, `cash_target_change`, `ticker_lane_change`, and `canonical_status_move`
- validator that requires `owner_decision_required=true`, `owner_approval_granted=false`, and `apply_allowed=false` by default
- authority vocabulary checks blocking approval/execution language

Acceptance:
- proposal schema validator exists and fails closed on missing authority fields
- proposal artifacts can be generated without touching canonical notes

### Phase 2 - Review-only proposal generator

Deliverables:
- generator that consumes current notes/artifacts and writes proposals under `tmp/portfolio-mutation-proposals/`
- pro-forma risk and concentration block
- source freshness and missing-evidence block
- owner-conflict block across the canonical note layer

Acceptance:
- sleeve and ticker proposal examples validate cleanly as review-only
- no generated output grants deployment, sizing, approval, execution, or account authority

### Phase 3 - Dry-run scoped patch helper

Deliverables:
- dry-run helper that reads one validated proposal and emits an exact patch preview
- patch-scope validator proving only approved files/fields would be touched

Acceptance:
- helper refuses writes unless explicit approved mode is present
- pre-approval mode can only produce a diff / patch artifact

### Phase 4 - Post-approval apply helper

Deliverables:
- apply mode that requires explicit scoped Randall approval for one proposal id
- applies exactly the approved diff only
- runs post-apply validation chain

Acceptance:
- `validate_canonical_ownership.py` passes
- `validate_dashboard_state.py --write` passes
- proposal-specific validator passes
- decision/outcome is logged

### Phase 5 - Scheduled maintenance

Allowed:
- scheduled proposal refresh, stale-warning refresh, candidate review-packet generation

Blocked:
- scheduled mutation apply
- scheduled owner-approval changes
- scheduled trade/account action

## Required validators before any apply helper

- `portfolio_mutation_proposal_schema_validator`
- `portfolio_pro_forma_risk_validator`
- `canonical_status_invariant_validator`
- `proposal_patch_scope_validator`
- `authority_vocabulary_consistency_check`
- post-apply validation chain:
  - `python scripts\validate_canonical_ownership.py`
  - `python scripts\validate_dashboard_state.py --write`
  - proposal-specific tests and direct artifact inspection

## Stop lines

Stop and ask Randall before applying if:
- a proposal changes weights, cash target, sleeves, sizing, sector caps, correlated-sleeve limits, or risk-rule thresholds
- a proposal promotes/demotes a ticker, changes execution entitlement, or changes canonical deployment/action state
- owner notes conflict with generated artifacts
- source freshness is stale, partial, contradictory, manual-dependent, or provider-estimated for a decision-critical field
- technical, thesis, catalyst, or risk evidence materially disagree
- a clean validator, ranking, score, or generated packet could be read as approval
- the request touches brokerage/account activity or trade execution

## Dependencies

Inputs / guardrails:
- Portfolio Mutation Proposal Protocol
- Ticker Add Canonical Ownership Checklist
- Ticker Lane Templates
- Watchlist Promotion Candidate Packet Contract
- Promotion Review Queue
- WF42 recommendation-object output
- WF51 promotion branch diagnostics
- WF53 sector/correlation proof
- WF55 probability-readiness language gate

Do not reopen WF38 unless the standing sector-expansion process itself drifts or Randall intentionally reopens that lane.

## Next action

Build Phase 1 only: typed schemas and validators for review-only proposal packets. Do not build a write-capable apply helper until Phase 1 and Phase 2 pass and Randall approves the scoped helper design.
