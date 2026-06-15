# Portfolio Mutation Proposal Protocol

Purpose: let Veritas prepare and, when a scoped workflow is explicitly approved, apply guarded portfolio note/model changes without silently crossing into trade/account action or inferred owner approval.

## Definition

A **portfolio mutation** is any change that alters the actual intended portfolio posture, allocation, execution authority, or owner-approved decision state.

Portfolio mutation includes:

- Changing draft model weights, cash target, sleeve weights, or sector allocation.
- Adding, removing, promoting, or demoting a ticker in the portfolio model.
- Moving a name into or out of deployable-now / almost-deployable / blocked / do-not-touch state when that changes capital-action meaning.
- Recording, removing, or changing owner approval status.
- Changing sizing tiers, risk caps, stop/invalidation policy, or risk-rule thresholds.
- Treating a watch/research name as an execution-board candidate.
- Changing `tmp/portfolio-config.json` in ways that alter tracked universe lane, workflow state, weight, entry-band authority, or execution entitlement.

Portfolio mutation does **not** include:

- Refreshing source confidence, catalyst status, or earnings-date caveats.
- Updating technical-state wording after artifact confirmation.
- Keeping watch/repair/deployment labels synchronized when no owner-judgment promotion/demotion occurs.
- Generating review packets, rankings, or candidate recommendations.
- Updating generated `tmp/` artifacts.
- Fixing note ownership, stale wording, or duplicate canon when it does not change the portfolio decision.

## Current authority posture

Randall approved the guarded WF58/WF56 portfolio note/model mutation workflow on 2026-05-14.

That approval means Veritas may now acknowledge workflow-level authority to generate, validate, monitor, prepare, and apply exact validator-backed portfolio note/model mutation artifacts inside this protocol.

Approved gated apply scope: entry bands, ticker state, sleeves, sizing, and sector posture. Anything outside that scope requires a separate explicit gate.

It does **not** mean generated packets apply themselves, individual recommendations are owner-approved, or trades/accounts may be touched.

Allowed without extra approval:

1. Detect a possible mutation candidate.
2. Build a review packet.
3. State the recommended change, rationale, risks, and owner decision needed.
4. Draft exact proposed note/config edits in a review-only artifact.
5. Validate that the proposed change does not conflict with existing risk rules or authority boundaries.
6. Monitor scheduled proof surfaces for authority drift.

Requires an exact scoped apply artifact plus validator proof before applying:

- Any entry-band change that is not already eligible under the automatic entry-band maintenance allowlist.
- Any ticker-state change that affects portfolio posture, queue status, or execution meaning.
- Any model-weight or cash-target change.
- Any ticker promotion/demotion that affects portfolio posture or execution entitlement.
- Any owner-approval record change.
- Any sizing tier, sleeve, sector-posture, risk cap, or allocation framework change.
- Any generated recommendation packet moving from review to note/model write.

Still requires separate explicit Randall approval outside this protocol:

- Any real account, brokerage, order, fund movement, or trade execution action.

## Proposal packet shape

Every portfolio-mutation proposal should include:

- `ticker_or_scope`
- `current_state`
- `proposed_state`
- `mutation_type`
- `why_now`
- `evidence`
- `source_freshness`
- `base_case`
- `bear_case`
- `risk_rule_check`
- `concentration_check`
- `technical_gate`
- `catalyst_gate`
- `owner_decision_required`
- `apply_allowed`: always `false` until an exact scoped apply artifact is approved and validated
- `proposed_files_to_edit`
- `rollback_or_reversal_note`

## Typed proposal subtypes

Use typed proposal artifacts for all recommendation and apply-preview work. Store them under `tmp/portfolio-mutation-proposals/`.

### Sleeve / rebalance / cash-target proposal

Artifact pattern: `tmp/portfolio-mutation-proposals/sleeve-change-<scope>-<timestamp>.json`

Required additions:
- `mutation_type`: `sleeve_change`, `rebalance`, or `cash_target_change`
- current and proposed portfolio model, cash target, sleeves, sector exposure, and correlated-sleeve exposure
- pro-forma checks against Risk Rules, including sector cap, single-name ceiling, speculative sleeve cap, catalyst-window exceptions, and correlated Tech / AI-power exposure
- exact patch preview for `Portfolio Snapshot.md`, `Risk Rules.md`, or `tmp/portfolio-config.json` if those would change

### Ticker promotion / demotion / lane-change proposal

Artifact pattern: `tmp/portfolio-mutation-proposals/ticker-lane-change-<ticker>-<timestamp>.json`

Required additions:
- current and proposed lane/status tuple
- thesis, macro/regime, technical, catalyst, risk/sizing, and sector/correlation gates
- owner-conflict check across Coverage and Watchlist, Execution Board, Portfolio Snapshot, Risk Rules, and `tmp/portfolio-config.json`
- Promotion Review Queue status and whether a queue row is required/present

### Canonical status move proposal

Artifact pattern: `tmp/portfolio-mutation-proposals/canonical-status-move-<ticker>-<timestamp>.json`

Required additions:
- current and proposed status tuple across Coverage and Watchlist, Execution Board, Portfolio Snapshot, Risk Rules, and `tmp/portfolio-config.json`
- affected owner surfaces and exact field-level deltas
- invariant checks proving one owner per fact remains intact
- rollback / reversal note

## Default authority flags

Every typed proposal must start with:

```json
{
  "owner_decision_required": true,
  "owner_approval_granted": false,
  "apply_allowed": false,
  "canonical_mutation_allowed": false,
  "portfolio_mutation_allowed": false,
  "trade_or_account_action_allowed": false
}
```

An apply helper may only switch from dry-run to write mode after Randall explicitly approves the exact scoped mutation or the mutation is inside a previously approved gated apply lane with matching validator proof.

The WF58 capital-deployment bundle may carry top-level `gated_portfolio_note_model_mutation_allowed=true` to reflect the 2026-05-14 workflow approval. That does not override the per-packet flags above. Per-packet `owner_approval_granted`, `apply_allowed`, `canonical_mutation_allowed`, `portfolio_mutation_allowed`, and `trade_or_account_action_allowed` stay false until a separate exact apply artifact exists and passes validators.

## Safe workflow

1. Generate or inspect fresh artifacts.
2. Identify mutation candidates.
3. Create a proposal under `tmp/portfolio-mutation-proposals/`.
4. Run relevant validators:
   - `python scripts\validate_dashboard_state.py --write`
   - `python scripts\validate_canonical_ownership.py`
   - any workflow-specific validator.
5. Present the proposal / exact apply artifact to Randall or the approved main-session workflow gate.
6. Apply only the approved change, exactly scoped, and only after validator proof.
7. Re-run validators after apply.
8. Log the decision.

## Stop lines

Stop and ask Randall before applying if:

- the proposed change is outside the approved gated scope of entry bands, ticker state, sleeves, sizing, and sector posture;
- the proposed change affects weight, cash, risk limits, owner-approval records, or execution entitlement without a separate explicit gate;
- the proposed change promotes or demotes a ticker without exact approval for that state transition;
- source freshness is stale, partial, contradictory, or provider-estimated for a decision-critical catalyst;
- technical and fundamental evidence disagree materially;
- the proposal would make generated artifacts conflict with canonical notes;
- the request could be interpreted as trade execution or account action.

## Operating rule

Portfolio mutation support is allowed, and WF58/WF56 portfolio note/model mutation is approved under this guarded workflow.

Generated packets are still proposals, not applied changes.

Trade/account execution remains separately blocked.

The default output is a proposal/report/validator surface, not an applied change.
