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
- Phase 3 status (corrected 2026-09-30 from the gate register; the 09-29 alignment repeated a stale 09-07 snapshot): **Phase 3 is COMPLETE.** 3A dynamic-routing amendment and 3D observed-entitlement coverage are Main-accepted. 3F standing provider policy has been in force since Randall's 2026-09-02 approval (daily aggregate call budget, reserve/settle; first bounded run 64/64 attempts, zero failures). 3G, the recurring scheduler cutover, was executed as acceptance gate G7 of the [Phase 3 Main-Only End-to-End Acceptance](Phase%203%20Main-Only%20End-to-End%20Acceptance%20-%202026-09-05.md) program on 2026-09-14 under owner Path A: the four alert-chain jobs were cut over, and the weekly analyst-consensus job was left unchanged by design. G8 observed five sessions (09-17 to 09-23) plus the 09-20 closed-market run. G9 closed 2026-09-23 when Randall accepted the 09-21 repin as the final pin. Record: `g9_close_20260923` in `tmp/phase3-main-only-20260905/g9-reconciliation-register-20260916.json`. Naming note: "Phase 3A-3G" are tier-entitlement sub-phases, and "G1-G9" are the acceptance gates that closed them; 3G maps to G7. Carried post-Phase-3 owner items:
  - D2 gateway reboot survival;
  - D5 renewal-gate wording;
  - D9 invalidation-ordering bundle;
  - D4 analyst-consensus lane (extend the dynamic path to the weekly analyst job);
  - pre_open repair Option A/B;
  - the disclosed 09-20 manual-trigger issuer gap.

  The reference-level pin was renewed 2026-09-26 and expires 2026-10-10 (guard ok, 9.7 days remaining at 2026-09-30). The weekly Sat 09:00 Option B renewal keeps it current.
- Phase 4 status (aligned 2026-09-29): the [2026-09-07 design record](Phase%204%20Tier%20Promotion%20and%20Demotion%20Design%20-%202026-09-07.md) has been built out under [Phase 4 Unified Monitoring and Scale-Out Plan - 2026-09-27](Phase%204%20Unified%20Monitoring%20and%20Scale-Out%20Plan%20-%202026-09-27.md), which is the current phase authority. The proposal-route foundation (version-lineage guard, append-only recommendation decision ledger, per-name readiness gate, in-memory tier transaction simulator) was accepted 2026-09-26 as bounded inert code. P4-3a tier transaction core passed 11 independent QA rounds (final ACCEPT) and was committed 2026-09-29 as `1646a4cd`. P4-3b onboarding writer (inverse capture, `--inverse-rollback`, pre-COMMIT inverse file, compensation-based recovery) was QA-accepted 2026-09-29 as `fdae1df1` and pushed 2026-09-30 with checkpoint `00683f74` (Randall approved). The Oct-15 scorer-readiness reminder (`3df080bc`) was moved 2026-09-30 to a main-session systemEvent so the 2026.9.6 DataCloneError cannot kill it. Activation is blocked: production tier/canon mutation requires Randall's `state/finance/standing-approvals/phase4-tier-cutover.json` plus a bound, unconsumed, in-window owner decision — none exist. The Oct-15 scorer-readiness gate and one owner-approved pilot swap (~Nov 9 target; caps full at 15/17) still stand before any live tier change.

Historical acceptance gate (satisfied; Phase 3 closed 2026-09-23): do not execute Phase 3 until the Phase 2 external cutover is measured and explicitly approved, the hash-bound approval packet still matches its sources, and the existing freshness/pivot baseline blockers are either cleared or formally accepted as external residue.

Next action: none from the former 18-to-32 cutover packet — `tmp/tier-entitlement-v091-phase3-external-cutover-approval-packet.json` is superseded (2026-09-02) by the dynamic contract and has no approval or execution effect. Current owner-review items live in the Phase 4 close-out plan windows: Sat 10-03 Option B renewal check and first scheduled screening run; Oct 5-9 screening calibration (47 review candidates is too loose), duplicate census, D-C cleanup proposal (the Oct-15 trigger route fix for automation `3df080bc` was done early, 2026-09-30); Oct 12-14 S4/S5 enrollment and evidence-input proofs; Oct-15 scorer readiness; ~Nov 9 cutover approval and one pilot swap. Output-contract gap (09-23 audit): new-entry thesis blocks for the digest were approved 2026-09-30 and are being built under contract `tmp/impl-digest-thesis-20260930/contract.md`.

Primary proof:

- `tmp/tier-entitlement-v091-phase2b-question-router-cutover-proof.json`
- `tmp/analyst-consensus-current.json`
- `tmp/tier-entitlement-surface-inventory.json`
- `tmp/tier-entitlement-v091-phase2c-analyst-quarantine-route.json`
- `tmp/tier-entitlement-v091-phase2-closeout.json`
- `tmp/tier-entitlement-v091-phase3-external-cutover-approval-packet.json`

## Phase 3 And Phase 4 Alignment To This Workflow - 2026-09-29

Aligned at Randall's direction (2026-09-29 Telegram: "align all work done in phase 3 and phase 4 to wf85 and wf84"):

- **Phase 3 feeds this workflow's scope.** The dynamic entitlement policy resolves the exact 32 Tier A+B names from guarded SQL and governs external evidence workloads under a daily call budget with fail-closed overflow. 3D observed-entitlement coverage makes quote/session, reference-level, lineage, freshness, analyst, card, and queue evidence visible per name. The 3G recurring cutover (gate G7) put the morning, intraday, post-close and weekly alert chains on the dynamic path; G8/G9 closed Phase 3 on 2026-09-23. The open Phase 3 follow-ons are owner items, not gates. The one that touches this workflow's evidence is D4: weekly analyst consensus still runs its pre-Phase-3 path.
- **Phase 4 is the tier-maintenance machinery underneath this workflow.** P4-3a (tier promotion/demotion transactions) and P4-3b (reference-level onboarding with row-level inverse and compensation) are accepted and committed but inert behind the cutover gate. When activated, scorecard-first promotion moves names between research grades, and WF85 alert/recommendation coverage follows the guarded-SQL tier state automatically.
- **Stage 2 weekly screening** (`weekly_screening_refresh.py`, cron `e6532249`) surfaces promotion review candidates into the tier pipeline; calibration is an Oct 5-9 close-out item.
- **The alert-ledger outcome scorer** (ledger started 2026-09-24; Oct-15 readiness gate) is the bridge from review states to measured outcomes in `Alerts OS Unified Objective - 2026-09-17.md`.
- **No authority change.** Nothing in Phase 3 or Phase 4 alters this workflow's authority: review-only alerts and non-executing recommendations; no portfolio state, capital, orders, accounts, money movement, or paper/live execution; no writer output or generated digest becomes owner approval.

## Stop Lines

- No holdings, account, order, cash, or execution-state maintenance.
- No capital deployment or money movement.
- No brokerage endpoint or credential use.
- No generated recommendation becomes owner approval.

Last updated: 2026-09-30 Phoenix (Phase 3 completion correction, P4 push, Oct-15 reminder route, digest thesis blocks).
