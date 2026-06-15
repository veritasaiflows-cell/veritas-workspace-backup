---
name: "veritas-wf78-tier-promotion-spine"
description: "Automated WF78 non-capital tier routing workflow."
---

# Veritas WF78 Tier Promotion Spine

Use this skill when Randall asks to continue WF78 ticker scaleout, Tier A/B routing, Tier B bench expansion, evidence repair, auto-tier routing, approved label registers, label-sync previews, or repeatable non-capital ticker routing automation.

## Purpose

Produce evidence-backed automated Tier A/B/C routing state while preserving the only hard owner approvals that remain: capital deployment, trade/order execution, account action, and other explicitly gated portfolio/cash/sizing mutations.

## Current Authority Posture

Randall changed the WF78 routing posture on 2026-06-05 12:30 MST: Veritas should automate ticker movement/routing between non-capital tiers; Randall approval is required for execution of trades and approval for capital deployment.

Treat this as standing WF78 routing authority unless a later owner instruction narrows it. Core surfaces (`SOUL.md`, `AGENTS.md`, `USER.md`, Startup Truth Index, Coverage Admission and Promotion Protocol, TOOLS, Active Workflows) have been hardened to match this posture.

## Hard Boundary

Always preserve these boundaries:

- Automated tier/routing state is allowed.
- A clean validator result is not trade approval.
- Tier A membership is not capital deployment approval.
- Tier B means research bench only, not deployable.
- Quote-backed Tier B evidence repair is research context only. It does not create written entry bands, stops, invalidation levels, deployment readiness, or action authority.
- Tier A means decision-grade roster; use separate deployment states such as A-DEPLOY, A-WATCH, A-READY, A-CHALLENGED, or A-DEMOTE when available.
- `A-READY` means evidence/routing ready, not an order approval.
- No capital deployment, paper/live execution, brokerage/account action, money movement, portfolio cash/sizing/sleeve execution, customer/public output, SQL-first/canon authority, or owner approval inference without an exact separate gated approval.

## Default Read Path

Before making claims, inspect the current proof surfaces:

1. `tmp/wf78-auto-tier-routing.json`
2. `tmp/wf78-production-tier-adjudication.json`
3. `tmp/wf78-tier-a-final-promotion-packet.json`
4. `tmp/wf78-tier-b-final-promotion-packet.json`
5. `tmp/wf78-tier-b-final-promotion-packet.next-batch.json`
6. `tmp/wf78-tier-b-final-promotion-packet.next-batch-2.json`
7. `tmp/wf78-tier-b-final-promotion-packet.next-batch-3.json`
8. `tmp/wf78-tier-b-evidence-repair.json`
9. `tmp/wf78-tier-label-decision-register.json`
10. `tmp/wf78-tier-label-sync-preview.json`
11. `tmp/wf78-tier-b-research-packets.json`
12. `tmp/wf78-tier-funnel-promotion-gate.json`
13. `06. Playbooks/Active Workflows.md`
14. `TOOLS.md` WF78 section

## Repeatable Auto-Routing Pass

Run the all-safe chain first:

```powershell
python scripts\wf78_phase_runner.py --phase all-safe --write --validate
```

For the current routed state alone:

```powershell
python scripts\wf78_auto_tier_router.py --write --validate
```

The auto-router writes `tmp/wf78-auto-tier-routing.json` and should classify every active WF78 ticker into `auto_tier` and `auto_state` while keeping these counts at zero:

- `capital_deployment_approved_count`
- `trade_or_execution_approved_count`

## Auto-Routing Rules

Use the router output as the live non-capital routing truth.

- Tier A packet-eligible names can route automatically into Tier A states.
- Names in-band with clean Tier A packet evidence can route to `A-READY`.
- Legacy Tier A names with repair/adjudication concerns can route to `A-CHALLENGED` instead of being treated as current deploy candidates.
- Approved or previewed Tier B research-bench labels can route automatically into Tier B.
- Production-bench Tier B names with stronger evidence can route to `B-VALIDATED`.
- New research-bench names can route to `B-CANDIDATE`.
- Phase 2-eligible but lower-quality, over-cautioned, or lower-priority names should route to `C-CANDIDATE-HOLD` rather than consuming Tier B capacity.
- Broad active coverage remains `C-MONITOR` or `C-REPAIR` unless evidence earns a higher state.

## Tier B Evidence Repair

Use this when Tier B research packets are blocked only by initial technical/price-band context and evidence repair burden.

```powershell
python scripts\wf78_tier_b_evidence_repair.py --quote TICKER=PRICE --quote-source "<source>" --quote-time-utc "<timestamp>" --write --write-db --validate
python scripts\wf78_tier_b_research_packet.py --write --write-db --validate
python scripts\wf78_tier_funnel_promotion_gate.py --requests tmp\wf78-tier-b-research-packet-requests.json --write --validate
```

When quote repair is needed in the same runner pass, include repeated quote flags:

```powershell
python scripts\wf78_phase_runner.py --phase all-safe --write --validate --tier-b-repair-quote TICKER=PRICE --tier-b-repair-quote-source "<source>" --tier-b-repair-quote-time-utc "<timestamp>" --tier-b-next-batch-offset <offset>
```

## Tier B Packet Batching

Build repeatable five-name packets from the Phase 2 eligible queue when diagnostics or audit detail is needed:

```powershell
python scripts\wf78_tier_b_final_promotion_packet.py --source phase2_eligible --offset 0 --out tmp\wf78-tier-b-final-promotion-packet.next-batch.json --write --validate
python scripts\wf78_tier_b_final_promotion_packet.py --source phase2_eligible --offset 5 --out tmp\wf78-tier-b-final-promotion-packet.next-batch-2.json --write --validate
python scripts\wf78_tier_b_final_promotion_packet.py --source phase2_eligible --offset 10 --out tmp\wf78-tier-b-final-promotion-packet.next-batch-3.json --write --validate
```

These are auto-routing input packets now. Do not ask Randall for manual label-only approval for ordinary tier routing. Use the auto-router to decide route state. Ask Randall only when the next action would approve capital deployment, execute a trade/order, touch account/brokerage, mutate portfolio cash/sizing/sleeve execution, or cross another explicit gated boundary.

## Label Register And Sync Preview

The historical label register and sync preview remain useful audit surfaces, but they are no longer the main operating route for every tier movement.

```powershell
python scripts\wf78_tier_label_sync_preview.py --write --validate
```

Use them when:

- auditing prior owner label decisions
- comparing legacy universe tier metadata to current routed state
- preparing a future apply path for a formal roster consumer

A future label-sync apply requires a separate exact approval, backup/rollback, diff, validator proof, and post-apply validation if it mutates durable universe/canon/portfolio surfaces.

## Evidence Repair Priority

For C-to-B scaleout queues, repair these first:

- initial technical/price-band context
- evidence repair burden acceptable
- source-open proof and freshness where stale
- written band/stop/invalidation only when evaluating deployability, not ordinary Tier B research-bench routing
- deployment/sizing context only when evaluating Tier A/deployability

## Current 2026-06-05 Routing Baseline

Latest validated `tmp/wf78-auto-tier-routing.json`:

- 200 active tickers classified.
- 16 auto Tier A.
- 27 auto Tier B.
- 157 Tier C.
- `GOOG`, `NVDA`, and `VRT` route to `A-READY`.
- `ALB`, `ALLE`, `AMCR`, `AME`, and `AOS` route to `C-CANDIDATE-HOLD`.
- 0 capital deployments approved.
- 0 trade/execution approvals.

## Tier A Policy

Tier A should not mean only current buys. Tier A should mean the best decision-grade roster. Use a deployment substate to avoid confusion:

- `A-DEPLOY`: current in-band, source-open, stop/band valid, sizing/staggering ready, approval-card eligible; still requires exact trade/capital approval before execution.
- `A-WATCH`: high-quality Tier A roster name, but no-chase, waiting for entry, catalyst, or repair.
- `A-READY`: evidence clean and routing-ready, not necessarily approved for trade.
- `A-CHALLENGED`: stale, crowded, weakened, or facing a stronger challenger.
- `A-DEMOTE`: failed refresh, thesis drift, stop/invalidation break, or lost challenger test.

A paper/live order still requires a separate exact order approval even if a ticker is Tier A or A-DEPLOY.

## Tier B Policy

Tier B is the research bench. Route to Tier B only when the name deserves scarce research time and has enough evidence to support active monitoring/research. Tier B does not mean deployable and should not trigger order generation by itself.

## Downstream Consumer Rule

The next workflow target is to make downstream roster/dashboard consumers read `tmp/wf78-auto-tier-routing.json` as the default non-capital routing truth. Do not keep building manual approval prompts for ordinary Tier A/B label movement.

## Closeout

After meaningful WF78 routing work:

- update `06. Playbooks/Active Workflows.md`
- append `memory/YYYY-MM-DD.md`
- update `TOOLS.md` only if routes or global tool posture changed
- update `scripts/README.md` when a script route is added or materially changed
- revise the pending Skill Workshop proposal when the reusable procedure changes
- run the smallest relevant validators
- state clearly what was automated, what was routed, what was not mutated, and whether any capital/execution decision remains
