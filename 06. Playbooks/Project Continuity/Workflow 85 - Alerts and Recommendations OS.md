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
- Phase 3 is not ready. The live alert chain and weekly analyst contract still own 18-name external workloads.
- Phase 4 (guarded-SQL tier transactions) has a Main-owned design record at [Phase 4 Tier Promotion and Demotion Design - 2026-09-07](Phase%204%20Tier%20Promotion%20and%20Demotion%20Design%20-%202026-09-07.md). It is a design record only: no tier write, canon mutation, schedule change, or activation authority. It recommends deferring implementation until after Phase 3 G9, because a tier change alters the entitlement scope that G8's five-session observation exists to measure.

Acceptance gate: do not execute Phase 3 until the Phase 2 external cutover is measured and explicitly approved, the hash-bound approval packet still matches its sources, and the existing freshness/pivot baseline blockers are either cleared or formally accepted as external residue.

Next action: review `tmp/tier-entitlement-v091-phase3-external-cutover-approval-packet.json`. It defines the exact 18-to-32 recurring external cutover: the alert chain would add 14 symbols per run and 2,394 symbol-snapshot units per week; the weekly analyst job would add 14 ticker constructions and 28 yfinance method invocations per run, while underlying provider HTTP calls/bytes remain unmeasured. This packet is review-only and requires your explicit approval before any Phase 3 execution.

Primary proof:

- `tmp/tier-entitlement-v091-phase2b-question-router-cutover-proof.json`
- `tmp/analyst-consensus-current.json`
- `tmp/tier-entitlement-surface-inventory.json`
- `tmp/tier-entitlement-v091-phase2c-analyst-quarantine-route.json`
- `tmp/tier-entitlement-v091-phase2-closeout.json`
- `tmp/tier-entitlement-v091-phase3-external-cutover-approval-packet.json`

## Stop Lines

- No holdings, account, order, cash, or execution-state maintenance.
- No capital deployment or money movement.
- No brokerage endpoint or credential use.
- No generated recommendation becomes owner approval.

Last updated: 2026-09-01 Phoenix / 2026-09-01 UTC.
