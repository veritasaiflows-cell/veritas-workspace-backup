# Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge

## Status

Opened 2026-05-17 / current WF70/WF66 official evidence spine is validator-backed and consumed review-only across all **31 tracked operating-company equities**. Live normalized coverage flows through `tmp/wf70-wf66-official-evidence-spine.json/.md`, `tmp/fundamental-ir-reconciliation-packets.json`, and `tmp/official-earnings-bridge.json` with clean validators.

WF66 is no longer an early limited prototype lane. It consumes the full validated WF70 official evidence set while preserving manual review, unreconciled bridge posture, and hard-false authority flags.

Current normalized source-state truth:
- 31 operating-company equity records are covered.
- Official company release or official SEC filing is captured for 31/31.
- SEC exhibit evidence is captured for 30/31; BRK.B is covered by official SEC 10-Q and keeps SEC-exhibit source state explicit/manual-required.
- Investor presentation and transcript states are explicitly represented and currently manual-required unless separately captured later.
- Priority fields are represented for every ticker: adjusted EPS, guidance, revenue/growth bridge, segment margins, orders/backlog/book-to-bill, management explanation, acquisition/debt notes, and source freshness.
- Field statuses remain non-fabricated: `official_captured`, `partial`, `not_disclosed_in_release`, `not_applicable`, `manual_required`, or `missing` under validator control.
- Bank/native operating fields remain review-only/manual-gated unless specifically captured with source URL, source section, period, and capture date.

## Purpose

Make capital recommendation packets explain the why behind a ranked candidate without pretending unresolved official evidence is complete. WF66 owns review-only evidence bridges for adjusted EPS, guidance, growth bridge, segment margins, orders/backlog, management explanation, acquisition/debt notes, and bank-specific ROTCE/NIM/funding/liquidity/credit-quality fields.

## Authority boundary

WF66 is evidence and packet-context only. It may generate structured rationale fields, official-source bridge placeholders, SEC/EDGAR evidence packets, validators, and reports. A WF66 packet alone may not infer owner approval, mutate canonical portfolio notes, change deployment state, change sizing/sleeves/cash/risk rules, place paper/live orders, touch brokerage/accounts, move money, handle credentials, or authorize external financial action. Main-session Veritas may later consume validated WF66 evidence inside the separate WF64/WF56 gated apply path for standing-approved workspace portfolio/canon maintenance.

## Current implementation

- `scripts/wf70_wf66_official_evidence_spine.py` normalizes WF70 capture artifacts into a WF66-consumable review-only evidence spine. It writes `tmp/wf70-wf66-official-evidence-spine.json/.md` and validation at `tmp/wf70-wf66-official-evidence-spine-validation.json/.md`.
- `scripts/official_ir_capture_validator.py --all` validates all non-validation capture artifacts under `tmp/official-ir-captures/`; current live count is 31 captures with clean validation.
- `scripts/fundamental_ir_reconciliation_packets.py` and `scripts/official_earnings_bridge.py` consume registry-selected validated official captures via `scripts/official_capture_period_registry.py`, not hard-coded Q1 paths. They keep bridge-present distinct from bridge-reconciled, preserve `manual_review_required=true`, `resolved_for_apply=false`, `reconciled=false`, and hard-false authority flags.
- `scripts/validate_fundamental_ir_reconciliation.py` and `scripts/validate_official_earnings_bridge.py` now require a clean WF70/WF66 evidence spine before passing, and check ticker coverage, source-state presence for release/SEC exhibit/presentation/transcript, priority field presence/status, and authority boundaries.
- `scripts/daily_review_objects.py` attaches `why_stack` / `decision_rationale` to capital recommendations with setup, entry, fundamental, official-earnings, sector/macro, risk/blocker, missing-evidence, and authority-boundary rationale.
- `scripts/portfolio_mutation_proposal_generator.py` carries the why stack into proposal packets while keeping packet apply/approval/external-action flags false.
- SEC/EDGAR sidecar tooling remains available through `scripts/sec_evidence_packet.py`, `scripts/sec_evidence_packet_validator.py`, `scripts/sec_capital_recommendation_bridge.py`, and `scripts/sec_capital_freshness_review.py`; it is fallback/review evidence, not portfolio/canon/trade authority.
- MSFT stop-label semantics remain guarded: raw `BELOW_STOP` from band proposals becomes `BELOW_RECLAIM_STOP` when authoritative deployment `below_stop=false`, and validators block literal `BELOW_STOP` unless `below_stop=true`.

## Current limitations

- WF66 is now source-state-complete for 31 tracked operating-company equities, but not every source type is fully captured. Investor presentations and transcripts remain explicit manual-required states until a separate reliable capture/extraction pass is implemented.
- SEC exhibit/official release evidence remains the primary source. Transcript text may add context later but must not override official releases, SEC exhibits, or official SEC filings.
- Some fields are intentionally `partial`, `not_disclosed_in_release`, or `not_applicable` where the official source does not disclose a full numeric value. Those states are valid evidence states, not defects.
- BRK.B is covered by an official SEC 10-Q rather than a separate SEC Exhibit 99.1-style earnings release; the evidence spine represents that distinction explicitly.
- Official evidence consumption improves recommendation quality but remains review-only and unreconciled for apply authority. It must not be described as owner-approved, execution-ready, portfolio/canon mutation-ready, or decision-complete without a separate WF64/WF56 gate.

## Next pass

1. Steady-state use: keep WF70/WF66 validators clean before capital recommendation packets, dashboard/advisor summaries, or promotion/deployment reviews rely on official evidence.
2. Q2 2026 rollforward: when Q2 releases are filed, follow `tmp/wf70-phase7-q2-rollforward-readiness.json/.md`; update per-ticker source URLs and period slug in capture entrypoints, then run captures, validation, registry refresh, reconciliation, bridge, and evidence-spine validation.
3. Optional source-type expansion: add investor-presentation and transcript capture only as a separate review-only pass with source provenance, parser reliability checks, and validator coverage; do not mark them captured until actually captured.
4. Bank/native enrichment: extend ROTCE/ROE, NIM, deposits/funding/liquidity, provisions/charge-offs/reserves, and efficiency ratio capture before Financials promotion reviews.
5. SEC fallback / primary-source routing: use SEC evidence sidecar when provider data is stale, missing, or contradictory, while preserving source hierarchy and confidence downgrades.

## Latest proof

- 2026-05-23/24 integrated WF70/WF66 closeout proof passed after adding the normalized evidence spine and making WF66 bridge validators depend on it. Proof commands included: `python -m py_compile scripts\wf70_wf66_official_evidence_spine.py scripts\validate_fundamental_ir_reconciliation.py scripts\validate_official_earnings_bridge.py scripts\official_ir_capture_validator.py scripts\fundamental_ir_reconciliation_packets.py scripts\official_earnings_bridge.py scripts\wf70_parallel_capture_runbook.py scripts\wf70_q2_rollforward_readiness.py`; `python scripts\official_ir_capture_validator.py --all --write`; `python scripts\fundamental_ir_reconciliation_packets.py`; `python scripts\official_earnings_bridge.py`; `python scripts\wf70_wf66_official_evidence_spine.py`; `python scripts\wf70_wf66_official_evidence_spine.py --validate-only`; `python scripts\validate_fundamental_ir_reconciliation.py --write --strict`; `python scripts\validate_official_earnings_bridge.py --write --strict`; `python scripts\wf70_parallel_capture_runbook.py`; `python scripts\wf70_q2_rollforward_readiness.py`; `python scripts\artifact_index.py incremental`; `python scripts\artifact_index.py validate`; `openclaw skills check`.
- Current evidence-spine validation: `tmp/wf70-wf66-official-evidence-spine-validation.json` status `ok`, records=31, checks=165, critical=0, warning=0, official release/SEC filing coverage=31/31, SEC exhibit coverage=30/31, presentations captured=0, transcripts captured=0.
- Current reconciliation validation: `tmp/fundamental-ir-reconciliation-validation.json` status `ok`, expected_equity_tickers=31, packets=31, critical=0, warning=0, findings=0.
- Current official earnings bridge validation: `tmp/official-earnings-bridge-validation.json` status `ok`, bridges=31, critical=0, warning=0, findings=0.
- WF70 Phase 6 runbook: `tmp/wf70-phase6-parallel-capture-runbook.json` status `ok`, total_tickers=31, workers=7, post_merge_steps=4.
- WF70 Phase 7 Q2 rollforward readiness: `tmp/wf70-phase7-q2-rollforward-readiness.json` status `ok`, registry coexistence proven, consumer scripts registry-routed, Q2 releases not yet available.
- SQL cockpit validation after indexing: `python scripts\artifact_index.py validate` passed 27/0. `openclaw skills check` passed.
- Independent read-only QA initially blocked closeout only because WF66/WF70 continuity text was stale; this note now matches live artifacts.
