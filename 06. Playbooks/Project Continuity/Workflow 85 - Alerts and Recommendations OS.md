# Workflow 85 — Alerts and Recommendations OS

## Status

Primary P0 finance lane. It produces alerts and non-executing recommendations from WF84 evidence.

## Objective

Turn current, source-backed market evidence into concise review states and recommendations while keeping freshness, confidence, uncertainty, and invalidation visible.

This is a fidelity objective and is currently met at the pipeline level. The 2026-09-23 audit (`Alerts OS Audit and Monetization Readiness - 2026-09-23.md`) found that the delivered digest does not yet carry the thesis, base/bull/bear, or regime/catalyst fields this contract requires. It is not the program's outcome objective. The stated outcome objective — scale, entry quality, long-term return, and alignment to thesis, leadership, and environment — lives in `Alerts OS Unified Objective - 2026-09-17.md`, which also measures the current system against it and names what is missing.

## Decision States

- Recommendation review
- Band entry
- Near band
- No chase
- Invalidation alert
- Thesis change
- Catalyst alert
- Freshness decay
- Monitor only
- Suppressed

These are review states, not instructions or approvals.

## Output Contract

Every material recommendation should identify:

- ticker and timeframe;
- evidence date, source lineage, and freshness;
- confidence and uncertainty;
- thesis plus base/bull/bear context;
- material risks;
- band and invalidation context;
- the specific decision Randall may review.

The system may rank candidates and explain why attention is warranted. It does not maintain account state or create an executable instruction.

## Current Route

Morning, midday, post-close, and weekly modes use:

`python scripts\run_alerts_recommendations_chain.py <mode> --timeout-seconds 120 --write --validate`

Primary review product: `tmp/finance-alert-os-digest.json`.

Supporting proof:

- `tmp/alert-level-freshness-controller.json`;
- `tmp/alerts-recommendations-chain-morning.json`;
- `tmp/alerts-recommendations-chain-midday.json`;
- `tmp/alerts-recommendations-chain-post-close.json`;
- `tmp/alerts-recommendations-chain-weekly.json`;
- `tmp/alerts-os-pivot-validator.json`.

## Acceptance

- the direct chain validates end to end;
- the digest uses only current guarded-SQL, quote, controller, and canon inputs;
- freshness decay remains visible when data is old or incomplete;
- active workflow, cron, skill, status, memory, and retrieval routes do not reintroduce retired finance state;
- generated output grants no approval or action authority.

## Tier Entitlement And Atomic Promotion Contract - Review Only

The owner-review contract is [Tier Entitlement and Atomic Promotion Review Contract](Tier%20Entitlement%20and%20Atomic%20Promotion%20Review%20Contract.md).

Current state:

- Policy is adopted for review: tiers define research/evidence entitlements, never approval or readiness.
- Guarded SQL remains the sole tier-membership owner.
- The accepted Phase 2 plan is `tmp/tier-entitlement-v091-phase2-plan.json` (`3c0f7b5c...b597c`).
- Phase 2 is closed and Main-accepted as a bounded implementation slice; its durable closeout is `tmp/tier-entitlement-v091-phase2-closeout.json`.
- Phase 2A source retirement and guarded-SQL migration are accepted: active reactivation errors moved `13 -> 0`.
- The question router now derives the exact 32 Tier A+B names from guarded SQL and fails closed on identity or SQL errors; it adds no recurring external calls.
- Analyst consensus is quarantined to a four-field evidence-only projection. Local tier/confidence/queue truth is removed, quarantine targets moved `2 -> 0`, the weekly 18-name provider workload is unchanged, and all 32 Tier A+B cards validate read-only.
- Current inventory remains truthful at zero errors, zero quarantine targets, 42 consolidation targets, and 44 unexplained residual-sweep hits.
- Phase 3 status (aligned 2026-09-29): 3A dynamic-routing amendment and 3D observed-entitlement coverage are complete and Main-accepted. The 3F standing-policy cutover was approved by Randall 2026-09-02 (cryptographic per-run approval path dropped; daily aggregate provider-call budget with reserve/settle in force); the first bounded run covered the full 32-name guarded-SQL scope with 64/64 provider attempts and zero failures. 3G scheduler cutover remains open, requires its own separate owner decision, and the September 5 completion work remains unaccepted. Gate snapshot (2026-09-07 record): G1-G5 hold with G4 hash drift on `scripts/phase3g_dynamic_execution.py`; G6 hermetic passed with one real post-close run `completed_with_visible_debt`; G7-G9 not started. The weekly g6 renewal and the Sat 10-03 Option B renewal are the live recurring events.
- Phase 4 status (aligned 2026-09-29): the [2026-09-07 design record](Phase%204%20Tier%20Promotion%20and%20Demotion%20Design%20-%202026-09-07.md) has been built out under [Phase 4 Unified Monitoring and Scale-Out Plan - 2026-09-27](Phase%204%20Unified%20Monitoring%20and%20Scale-Out%20Plan%20-%202026-09-27.md), which is the current phase authority. The proposal-route foundation (version-lineage guard, append-only recommendation decision ledger, per-name readiness gate, in-memory tier transaction simulator) was accepted 2026-09-26 as bounded inert code. P4-3a tier transaction core passed 11 independent QA rounds (final ACCEPT) and was committed 2026-09-29 as `1646a4cd`. P4-3b onboarding writer (inverse capture, `--inverse-rollback`, pre-COMMIT inverse file, compensation-based recovery) was QA-accepted 2026-09-29 and committed locally as `fdae1df1` (not pushed; push requires Randall). Activation is blocked: production tier/canon mutation requires Randall's `state/finance/standing-approvals/phase4-tier-cutover.json` plus a bound, unconsumed, in-window owner decision — none exist. The Oct-15 scorer-readiness gate and one owner-approved pilot swap (~Nov 9 target; caps full at 15/17) still stand before any live tier change.

Acceptance gate: do not execute Phase 3 until the Phase 2 external cutover is measured and explicitly approved, the hash-bound approval packet still matches its sources, and the existing freshness/pivot baseline blockers are either cleared or formally accepted as external residue.

Next action: none from the former 18-to-32 cutover packet — `tmp/tier-entitlement-v091-phase3-external-cutover-approval-packet.json` is superseded (2026-09-02) by the dynamic contract and has no approval or execution effect. Current owner-review items live in the Phase 4 close-out plan windows: Sat 10-03 Option B renewal check and first scheduled screening run; Oct 5-9 screening calibration (47 review candidates is too loose), duplicate census, D-C cleanup proposal, and the Oct-15 trigger route fix (automation `3df080bc` DataCloneError); Oct 12-14 S4/S5 enrollment and evidence-input proofs; Oct-15 scorer readiness; ~Nov 9 cutover approval and one pilot swap. 3G scheduler cutover remains a separate open owner decision.

Primary proof:

- `tmp/tier-entitlement-v091-phase2b-question-router-cutover-proof.json`
- `tmp/analyst-consensus-current.json`
- `tmp/tier-entitlement-surface-inventory.json`
- `tmp/tier-entitlement-v091-phase2c-analyst-quarantine-route.json`
- `tmp/tier-entitlement-v091-phase2-closeout.json`
- `tmp/tier-entitlement-v091-phase3-external-cutover-approval-packet.json`

## Phase 3 And Phase 4 Alignment To This Workflow - 2026-09-29

Aligned at Randall's direction (2026-09-29 Telegram: "align all work done in phase 3 and phase 4 to wf85 and wf84"):

- **Phase 3 feeds this workflow's scope.** The dynamic entitlement policy resolves the exact 32 Tier A+B names from guarded SQL and governs external evidence workloads under a daily call budget with fail-closed overflow. 3D observed-entitlement coverage makes quote/session, reference-level, lineage, freshness, analyst, card, and queue evidence visible per name. 3G scheduler cutover is the only open Phase 3 front and needs Randall's separate decision.
- **Phase 4 is the tier-maintenance machinery underneath this workflow.** P4-3a (tier promotion/demotion transactions) and P4-3b (reference-level onboarding with row-level inverse and compensation) are accepted and committed but inert behind the cutover gate. When activated, scorecard-first promotion moves names between research grades, and WF85 alert/recommendation coverage follows the guarded-SQL tier state automatically.
- **Stage 2 weekly screening** (`weekly_screening_refresh.py`, cron `e6532249`) surfaces promotion review candidates into the tier pipeline; calibration is an Oct 5-9 close-out item.
- **The alert-ledger outcome scorer** (ledger started 2026-09-24; Oct-15 readiness gate) is the bridge from review states to measured outcomes in `Alerts OS Unified Objective - 2026-09-17.md`.
- **No authority change.** Nothing in Phase 3 or Phase 4 alters this workflow's authority: review-only alerts and non-executing recommendations; no portfolio state, capital, orders, accounts, money movement, or paper/live execution; no writer output or generated digest becomes owner approval.

## Stop Lines

- No holdings, account, order, cash, or execution-state maintenance.
- No capital deployment or money movement.
- No brokerage endpoint or credential use.
- No generated recommendation becomes owner approval.

Last updated: 2026-09-29 Phoenix / 2026-09-30 UTC.
