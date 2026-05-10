# Workflow 38 - Sector Expansion and Promotion Review Hardening

## Objective
- Build the next bounded lane for broadening investment options without unsafe watchlist auto-promotion.
- Establish a weekly review process that explicitly answers:
  - which new sector deserves expansion now
  - which 1-2 names are the best candidates
  - why they beat adding more to the current crowded sleeve
- Keep final promotion and deployment authority in canonical owner notes.

## Current State
- closed with handoff on 2026-05-07 after the weekly-cadence / diversification-coverage closeout proof landed in `06. Playbooks/WF38 Phase 4 Weekly Cadence and Coverage Closeout - 2026-05-07.md`.
- WF37 remains paused with follow-up for repeated clean daily-summary review-only runs and delivery-posture decision; it is not closed or scheduler-promoted.
- under Randall's explicit approval, the WF38 Phase 0-5 automation foundation was implemented early as a bounded structural prep pass; the workflow is now closed without widening promotion, trade, or canonical auto-mutation authority.
- sector/regime monitoring already exists through:
  - `02. Markets/Regime Scoring Matrix.md`
  - `tmp/positioning-ranking.json`
  - `03. Portfolio/Portfolio Snapshot.md` sector-cap checks
  - `03. Portfolio/Deployment Trigger Sheet.md` five-gate owner logic
- the current system can surface candidates through an owner-safe candidate-packet intake lane, Promotion Review Queue, shadow-canon check, and read-only promotion-review checker.
- current live posture now keeps JPM as the sole canonical deployable-now name after explicit 2026-05-07 owner approval; NVDA remains timing-blocked in `PROMOTION REVIEW`, GS/GOOG/MSFT/ETN remain almost-deployable / entry-discipline cases, and LLY/CAT remain review-prep candidates rather than approved promotion candidates.
- 2026-05-07 governance / truth-control audit integration remains in force: `scripts/workspace_governance_truth_check.py` passes cleanly, the no-chat-channel Control UI posture is reflected in `TOOLS.md`, and canonical live notes plus adjacent dashboard/intelligence surfaces are resynced to the current owner truth.
- 2026-05-07 morning proof is now clean enough at the workflow layer: `python scripts/run_finance_refresh_chain.py morning` completed successfully, `scripts/test_dashboard_acceptance.py` passed 17/17, the run-summary terminal-state contradiction is fixed, and workbook export reran successfully. That narrowed WF38 away from workbook-lock recovery and into owner/posture cleanup work.
- Coverage Universe authority leaks were removed: it no longer acts as candidate-packet gate, dashboard consistency source, workbook fallback owner, or tracked-universe source of truth. Candidate packets now use `thesis_evidence_source` instead of canonical-thesis wording.
- entry-band automation now implements the audit's review-only Keltner-first / dual-MA-gated / SMA-envelope-audited proposal engine; only clear-earnings `IN_BAND` / `NEAR_BAND` execution-lane, band-defined, decision-grade workflow proposals can be apply-eligible. Earnings-imminent, timing-window, above-band-wait, below-stop/reclaim, watch-lane, underdefined, and non-execution proposals are non-applyable, and `scripts/test_entry_band_automation.py` protects the core residue fixes.

## Scope
- define the sector-expansion review layer
- define the watchlist -> candidate packet -> promotion review -> owner decision funnel
- decide the best current diversification candidates outside the crowded sleeve
- define what is automated, what remains manual, and what proof is required before any wider automation

## Out of Scope
- direct watchlist -> deployable-now automation
- automatic trigger-sheet or portfolio-note mutation
- autonomous sector rotation or capital-allocation changes
- silent promotion based on machine ranking alone

## Preflight / Entry Checklist
- [x] watchlist is already explicitly non-canonical
- [x] trigger sheet five-gate owner layer exists
- [x] sector-cap and correlated-sleeve constraints are explicit in `07. Risk/Risk Rules.md` and `03. Portfolio/Portfolio Snapshot.md`
- [x] a bounded promotion-candidate packet contract now exists
- [x] repeated weekly review proof exists
- [x] a sector-expansion recommendation surface exists
- [x] band-definition coverage is complete enough for the current review-prep expansion candidates
- [x] candidate-packet schema exists
- [x] fail-closed 5-gate validator exists
- [x] sector-cap / correlated-sleeve check exists
- [x] catalyst-window check exists
- [x] Promotion Review Queue exists
- [x] ranking shadow-canon check exists
- [x] bounded promotion-review checker exists; it can auto-approve a workspace review verdict under exact gates but still forbids trade execution and automatic canonical note mutation

## Execution Posture
- main session owns workflow contract, weekly review judgment, and final integration
- bounded helper lanes are appropriate for candidate-packet prep, sector-map research, and QA challenge
- any machine-generated ranking remains subordinate to canonical owner notes

## Acceptance Gates
- one bounded Phase 1 artifact defines the weekly sector-expansion review contract and review questions
- one bounded Phase 2 artifact identifies the current best diversification sectors and 1-2 best candidates with evidence-backed rationale
- entry-band automation posture is stated honestly: proposal generation vs canonical application
- a repeatable weekly review cadence exists without implying autonomous promotion authority
- queue / registry / daily memory reflect that WF38 is active and non-authorizing

## Sequential phase approach

### Phase 1 - Weekly review contract and owner map
- define the exact weekly review questions
- define inputs, owners, stop lines, and output shape

### Phase 2 - Current diversification recommendation
- decide which sector deserves expansion now
- name the best 1-2 candidates
- explain why they beat adding to the crowded sleeve

### Phase 3 - Candidate-packet and band-coverage hardening
- generate promotion-candidate packets for selected names
- identify which expansion candidates still lack entry band / invalidation / sizing definition
- keep all output review-only

### Phase 4 - Weekly operating cadence and automation posture
- define what the weekly review can auto-generate
- keep promotion review and owner-note mutation manual unless future proof justifies widening

## Current best starting judgment
- most justified next sector-expansion focus: **Healthcare** and **Industrials**
- strongest current diversification candidates: **LLY** and **CAT**
- secondary follow-on candidate: **AMZN** as a quality expansion name, but it is still too adjacent to the already crowded large-cap growth / Tech-AI complex to be the first diversification answer
- explicit non-starter for now: adding more AI sleeve risk just because ETN / NVDA / MSFT / GOOG / VRT score well

## Checkpoint Decision
- closed with handoff. Coverage Universe de-authoring, bounded promotion-review auto-approval, stricter band apply-eligibility automation, JPM owner-note sync, owner posture sync, repeated weekly-review proof, and LLY/CAT review-prep owner-layer coverage are all implemented with targeted proof. Broader automation authority remains unchanged.

## Next Action
- keep using the weekly sector-expansion procedure as a standing review surface, not as an active workflow excuse.
- keep NVDA in promotion review but blocked from clean approval while the timing window still makes the verdict unsafe.
- keep LLY and CAT watch-only / review-prep until future promotion and sizing judgment is explicitly approved in the owner layer.
- hand the active control plane to `06. Playbooks/Project Continuity/Workflow 40 - Cyber-Security Hardening and Bounded Daily Audit.md`.

## Next Pass
- none inside WF38 unless the weekly sector-expansion process materially fails, the diversification-candidate coverage drifts stale again, or a new promotion-authority widening request intentionally reopens the lane.
- continue WF37 Phase 6 repeated clean-run proof separately when summary-brief scheduling becomes the priority again.

## Key Files
- `06. Playbooks/Project Continuity/Workflow 38 - Sector Expansion and Promotion Review Hardening.md`
- `06. Playbooks/Watchlist Promotion Candidate Packet Contract.md`
- `06. Playbooks/WF38 Phase 0-5 Promotion Automation Foundation Proof - 2026-05-06.md`
- `06. Playbooks/Promotion Review Queue.md`
- `scripts/schemas/candidate_packet_schema.json`
- `scripts/candidate_packet_validator.py`
- `scripts/portfolio_integrity_check.py`
- `scripts/catalyst_window_check.py`
- `scripts/ranking_shadow_canon_check.py`
- `scripts/promotion_review_check.py`
- `02. Markets/Regime Scoring Matrix.md`
- `03. Portfolio/Deployment Trigger Sheet.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`
- `tmp/positioning-ranking.json`
- `tmp/band-proposals.json`
- `scripts/band_refresh.py`
- `scripts/entry_band_fetch.py`
- `scripts/generate_entry_band_status.py`
- `scripts/operators/apply_band_update.py`
- `scripts/test_entry_band_automation.py`
- `scripts/test_wf38_authority.py`
