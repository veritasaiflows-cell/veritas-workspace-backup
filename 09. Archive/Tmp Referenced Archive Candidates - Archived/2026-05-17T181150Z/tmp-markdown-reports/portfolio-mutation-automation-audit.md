# Portfolio Mutation Automation Audit

Generated: 2026-05-11T04:02:55Z

## Executive conclusion

The current Veritas system is ready for **review-only portfolio-mutation proposal automation**, not mutation automation.

Conservative conclusion: keep portfolio mutation execution owner-gated. Automate typed proposal artifacts, pro-forma risk math, status-tuple checks, and exact patch previews first. A write-capable helper should exist only as a dry-run / scoped-patch surface until Randall explicitly approves one specific mutation.

The best path is **not** to reopen WF38. WF38 is closed and should remain the standing sector-expansion / promotion-review governance surface. Use WF42, WF51, WF53, WF55, the Portfolio Mutation Proposal Protocol, and the ticker ownership/checklist files as inputs. If Randall wants apply-helper bones, open a new bounded workflow: **WF56 - Portfolio Mutation Proposal Object and Gated Apply Helper**.

## Existing workflow ownership map

| Surface | Owns | Current state | Authority boundary |
|---|---|---|---|
| Portfolio Mutation Proposal Protocol | Mutation definition, proposal packet shape, proposal-first workflow | Policy exists; typed schemas/apply-helper contract missing | Veritas may draft proposals; applying needs explicit Randall approval |
| Ticker Add Canonical Ownership Checklist / Ticker Lane Templates | Canonical note ownership by fact type | Good owner map; lacks explicit status-move packet template | No deployment, approval, model weight, promotion, or trade authority |
| Promotion Review Queue | Review-only row for explicit promotion review | Exists; queue row does not grant deployment | Human review required for lane / deployable-state changes |
| Watchlist Promotion Candidate Packet Contract | Watchlist -> packet -> human review path | Good base contract; production generator deferred | `review_only`; canonical mutation false |
| WF38 | Sector expansion and promotion-review governance | Closed with handoff | Standing review surface only; no auto-promotion or canonical auto-mutation |
| WF42 | Capital deployment recommendation object | Continuity says v1 complete; registry/queue still include stale queued wording | Recommendation only; no execution, sizing, portfolio mutation, trigger mutation, or inferred approval |
| WF51 | Daily trend/fresh-intel promotion branch | Phase 2 complete; Phase 3 production candidate generation deferred | Review-only; no canonical mutation or precise probability claims |
| WF53 | Sector/correlation proof | v1 implemented and QA-accepted; current artifact `degraded` from partial trust/band debt | Concentration proof only; no promotion, sizing, or owner approval |
| WF55 | Probability readiness gate | Active | Blocks win/deploy probabilities, expected return, calibrated readiness scores, and model-ranked candidates |
| Canonical notes | Watchlist index, Coverage thesis, Technical levels, Trigger deployment state, Snapshot weights/sleeves, Risk Rules caps | Ownership map is now explicit after canonical compression | Owner-gated where posture/allocation/action meaning changes |

## Update existing workflows vs open new workflow recommendation

**Recommendation:** update existing control surfaces with clearer contracts, then open one new bounded workflow only if Randall wants apply-helper bones.

- Do **not** reopen WF38 for this. It already owns the review doctrine and is closed.
- Update protocol/template surfaces to define typed mutation proposal contracts.
- Reconcile WF42 status drift between the continuity note and registry/queue.
- Keep WF51 production candidate generation deferred until trust-context, sector/correlation, owner-conflict, and outcome-history gates are stronger.
- Use WF53 as concentration context, but not as allocation or promotion authority.
- Use WF55 to keep probability/model language blocked until retained outcomes exist.
- If implementation proceeds, create **WF56 - Portfolio Mutation Proposal Object and Gated Apply Helper** with phases: schema -> proposal generator -> dry-run scoped patch -> approval-only apply -> post-apply validation.

## Automation bones/data contracts needed for sleeve proposals

Minimum proposal artifact: `tmp/portfolio-mutation-proposals/sleeve-change-<scope>-<timestamp>.json`.

Required contract fields:
- `schema_version`, `generated_at_utc`, `proposal_id`
- `mutation_type`: `sleeve_change`, `rebalance`, or `cash_target_change`
- current and proposed portfolio model, cash target, sleeves, sector exposure, and correlated-sleeve exposure
- pro-forma Risk Rules check: 25% sector cap, 15% normal single-name ceiling, speculative sleeve cap, catalyst-window exception check
- source artifacts and source freshness
- affected files and exact patch preview
- `owner_decision_required=true`, `owner_approval_granted=false`, `apply_allowed=false` by default
- rollback/reversal note and stop lines triggered

The sleeve proposal generator may compute and rank alternatives. It must not change `Portfolio Snapshot.md`, `Risk Rules.md`, or `tmp/portfolio-config.json` without explicit approval.

## Automation bones/data contracts needed for ticker promotion/demotion proposals

Minimum proposal artifact: `tmp/portfolio-mutation-proposals/ticker-lane-change-<ticker>-<timestamp>.json`.

Required contract fields:
- ticker, current lane/status tuple, proposed lane/status tuple
- thesis, macro/regime, technical, catalyst, and risk/sizing gates
- owner-conflict check against Watchlist, Deployment Trigger Sheet, Technical Sheet, Portfolio Snapshot, Coverage Universe, and portfolio-config
- sector/correlation artifact reference from WF53
- Promotion Review Queue status and whether a queue row is required/present
- source freshness and missing evidence
- exact proposed patch preview
- `owner_decision_required=true`, `owner_approval_granted=false`, `apply_allowed=false`

Existing `candidate_packet_validator.py` is a good base. It already checks required candidate fields, forbidden authority vocabulary, trust-context degradation, portfolio-config alignment, deployment-check alignment, earnings presence, gate shape, sector-cap status, and queue-row requirements for deployable proposals. It still needs production-generator wiring, computed owner-conflict checks, and sector/correlation proof as hard inputs before candidate generation widens.

## Automation bones/data contracts needed for canonical-status move proposals

Minimum proposal artifact: `tmp/portfolio-mutation-proposals/canonical-status-move-<ticker>-<timestamp>.json`.

Define a status tuple before and after:
- Watchlist state label only
- Deployment Trigger Sheet action state and authority note
- Technical Sheet stance / technical shorthand
- Portfolio Snapshot status, sleeve role, and draft weight if applicable
- Coverage Universe thesis/status caveat
- `tmp/portfolio-config.json`: `coverage_lane`, `workflow_state`, `portfolio_role`, `daily_technical_priority`, `entry_policy`, and `sizing_tier`

The proposal must name affected owner surfaces, prove one-owner-per-fact alignment, and include an exact patch preview. A status tuple move is a portfolio mutation when it changes capital-action meaning, execution entitlement, owner approval state, weight/sleeve role, or deployment readiness.

## Phased automation roadmap: artifact generation -> review packet -> gated apply helper -> post-approval apply -> scheduled maintenance

1. **Artifact generation** ? safe now. Generate review-only proposal artifacts, pro-forma risk math, status-tuple checks, and exact patch previews under `tmp/`.
2. **Review packet** ? safe now if authority flags stay false. Present why-now, evidence, source freshness, risk, stop lines, proposed files, and owner decision required.
3. **Gated apply helper** ? not ready. Build only after proposal schema, patch-scope validator, canonical invariant validator, and authority vocabulary checks exist. Before approval it must dry-run only.
4. **Post-approval apply** ? allowed only after explicit scoped Randall approval. Apply exactly the approved diff, then rerun validators and log the decision/outcome.
5. **Scheduled maintenance** ? artifact generation only. Cron may refresh candidates/stale warnings/review packets, never apply mutations or infer approval.

## Stop lines and owner-gated fields

Stop lines:
- Any proposed edit changes weight, cash, sleeve, sizing, sector cap, correlated-sleeve limit, or risk-rule threshold.
- Any proposed edit promotes/demotes a ticker, changes execution-lane entitlement, or changes canonical deployment/action state.
- Owner notes conflict with generated artifacts, especially Portfolio Snapshot vs Deployment Trigger Sheet vs portfolio-config.
- Source freshness is partial, stale, contradictory, manual-dependent, or provider-estimated for a decision-critical field.
- Technical evidence, thesis evidence, catalyst state, or risk/concentration checks materially disagree.
- A clean validator, ranking, score, probability, or generated packet could be read as approval or execution authority.
- The proposal affects real brokerage/account activity or could be interpreted as trade execution.

Owner-gated fields:
- model weights and draft weights
- cash target
- sleeve roles, sleeve weights, sleeve structure, sector allocation, and correlated-sleeve interpretation
- ticker promotion, demotion, addition to execution lane, or removal from execution lane
- canonical deployment/action state: deployable now, almost deployable, blocked, do-not-touch, watch-only, repair, or similar capital-action meaning
- owner approval state and any approval record
- sizing tier, risk cap, risk-rule threshold, stop/invalidation policy, or exception handling
- execution entitlement, trade readiness, buy/sell/add/trim language, account action, or real trade/fund movement
- tmp/portfolio-config.json fields that alter tracked universe lane, workflow state, weight, entry-band authority, or execution entitlement

## Validators/tests required before any apply helper

- **portfolio_mutation_proposal_schema_validator** ? Validate typed proposal packets for sleeve_change, ticker_lane_change, and canonical_status_move. Must check: authority flags false before approval, owner_decision_required true, apply_allowed false unless approved mode is explicitly passed, required fields by mutation type.
- **portfolio_pro_forma_risk_validator** ? Compute pre/post weights, cash, sector exposure, correlated sleeve exposure, single-name max, speculative sleeve, and catalyst-window exceptions. Must check: Risk Rules 25% sector cap, 15% normal single-name ceiling, Tech + AI-power sleeve warning, cash target, speculative sleeve cap.
- **canonical_status_invariant_validator** ? Validate Watchlist / Trigger Sheet / Technical Sheet / Snapshot / Coverage / portfolio-config status tuple alignment. Must check: one owner per fact, no Watchlist technical/weight detail, Trigger owns action state, Snapshot owns weight/sleeve, Technical shorthand subordinate to Trigger.
- **proposal_patch_scope_validator** ? Confirm a proposed apply patch touches only the files and fields listed in the approved proposal. Must check: no unlisted files, no config/auth/runtime files, no trade/account language, no field outside proposal scope.
- **authority_vocabulary_consistency_check** ? Block generated text from implying buy/sell/add/trim/execute/deployable-now/approval/probability authority where not approved. Must check: candidate_packet_validator forbidden vocabulary, WF47 shared authority vocabulary when implemented, all proposal artifacts and review notes.
- **post_apply_validation_chain** ? After explicit approved apply, re-run note ownership and dashboard/state validators before closeout. Must check: validate_canonical_ownership.py, validate_dashboard_state.py --write, daily review / dashboard regeneration if relevant, decision/outcome log append.

Before any post-approval apply, the minimum validation chain should include:
- proposal schema validator
- pro-forma risk / concentration validator
- canonical status invariant validator
- patch-scope validator
- authority vocabulary consistency check
- `python scripts\validate_canonical_ownership.py`
- `python scripts\validate_dashboard_state.py --write`
- proposal-specific tests and direct artifact inspection

## Exact suggested workflow/control-surface updates for main session to apply after audit

- `06. Playbooks/Portfolio Mutation Proposal Protocol.md` ? Add explicit subtypes: sleeve_change, ticker_lane_change, canonical_status_move; require proposal artifacts under tmp/portfolio-mutation-proposals/ with owner_decision_required=true, owner_approval_granted=false, apply_allowed=false by default.
- `06. Playbooks/Ticker Add Canonical Ownership Checklist.md` ? Add a Canonical Status Move section that defines the status tuple across Watchlist, Trigger Sheet, Technical Sheet, Portfolio Snapshot, Coverage Universe, and tmp/portfolio-config.json.
- `06. Playbooks/Ticker Lane Templates.md` ? Add a review-only status-move proposal template and sleeve/rebalance proposal template; keep exact patches in tmp artifacts, not in canonical notes before approval.
- `06. Playbooks/Watchlist Promotion Candidate Packet Contract.md` ? Add fields for owner_conflict_check, sector_correlation_artifact, current_canonical_status_tuple, proposed_canonical_status_tuple, and canonical_status_move_required.
- `06. Playbooks/Promotion Review Queue.md` ? Add guidance that DEPLOYABLE / DEPLOYABLE NOW / execution-lane proposals need a linked proposal artifact path before any apply, while ALMOST remains visible but not automatically queued unless escalation is requested.
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` ? Do not reopen WF38. Add a queued bounded workflow, suggested title ?WF56 - Portfolio Mutation Proposal Object and Gated Apply Helper?, after WF55/WF51 trust-context work and WF47 authority vocabulary unless Randall explicitly prioritizes it sooner.
- `06. Playbooks/IC Project Registry.md` ? Reconcile WF42 status wording: the WF42 continuity note says v1 completed on 2026-05-09, while the registry still says queued behind WF41. Choose one live truth and update the registry/queue accordingly.
- `scripts/` ? Before any apply helper, add tests/validators for proposal schema, pro-forma risk, canonical status invariants, patch-scope limits, and authority vocabulary. Do not wire scheduled apply behavior.
