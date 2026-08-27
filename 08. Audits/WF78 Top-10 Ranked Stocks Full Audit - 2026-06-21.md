# WF78 Top-10 Ranked Stocks Audit
**Date:** 2026-06-21  
**Scope:** Why the top-10 in `tmp/wf78-routing-dashboard.json` appear as non-actionable monitor-only blocked candidates.

## Conclusion
The top-10 list is not a sign of system failure. It is a consequence of **bucket ordering plus evidence-coverage gating** in the WF78 owner-decision/routing pipeline. Every rank-1…10 row is currently `needs_evidence` (blocked), with `missing_evidence_count = 10/10`, so they are review candidates only.

## Critical Findings (Severity Ordered)

### 1) High — Ranking is currently based on a blocked WF78 queue, not a tradable/action-ready ranking
The dashboard rows are sorted by transition bucket (`d_to_c`, `c_to_b`, `b_to_a`) and then position within that source order. The top-10 are all `from_tier: Tier C`, `to_tier: Tier B`, and therefore intentionally occupy the highest queue position for this run, while still blocked from action.

### 2) High — Every candidate row is blocked by missing evidence family completeness
The `tmp/wf78-routing-dashboard.json` summary and per-row fields show:
- `blocked: 100` (`needs_evidence`) in the full routing payload
- `actionable_now_count: 0`
- `evidence_present_count: 0` and `missing_evidence_count: 10` for each row shown in the top-10

This is why each is surfaced as “non-actionable,” even though they lead the queue.

### 3) Medium — Top-10 are Tier C→Tier B candidates in the “research/repair” lane
WF78 pipeline writes all candidate lanes by transition type and gate verdict. For this snapshot, all rows are in the evidence repair lane:
- `owner_action_category = needs_evidence`
- `gate_verdict = blocked_missing_evidence`
- `routing_lane = c_to_b`
- `action_lane = evidence_repair_lane`

So they are ranked as highest-priority to repair, not to execute.

### 4) Medium — Evidence completeness logic is strict and source data appears empty
`c_to_b` gating computes decision-family completeness from required families vs present evidence. In this run, present evidence arrays are empty and required families are fully missing, so each candidate is blocked.

### 5) Low — Snapshot timestamp mismatch creates interpretive drift
Evidence packet timestamps in the chain are inconsistent (`owner_decision_packet` older, dashboard built later). This is expected in staged pipelines but creates confusion if interpreted without lineage context. The top-10 statement is still true in the dashboard output, but the stale packet timestamp means freshness context must be checked before deciding actionable set size.

## Evidence and traceability

### Snapshot artifact evidence
- `tmp/wf78-routing-dashboard.json` (generated 2026-06-20T15:59:18Z)
  - `summary.by_owner_action_category.needs_evidence = 100`
  - `summary.by_gate_verdict.blocked_missing_evidence = 100`
  - `summary.by_transition_lane.research_promotion_lane = 100`
  - `routing_rows` rank-1..10 are A, ABBV, ABNB, ABT, ACGL, ACN, ADI, ADM, ADP, ADSK
  - Top-10 row fields include:
    - `from_tier: "Tier C"`
    - `to_tier: "Tier B"`
    - `missing_evidence_count: 10`
    - `evidence_present_count: 0`
    - `action: needs_evidence`
    - `status: blocked_missing_evidence`
    - `action_lane: evidence_repair_lane`
- `tmp/wf78-funnel-owner-decision-packet.json` (older generated_at: 2026-06-05T05:57:29Z) shows broad blockage:
  - `packet_count: 100`
  - `blocked_missing_evidence: 100`
  - `actionable_now_count: 0`

### Script-level evidence
- `scripts/wf78_funnel_owner_decision_packet.py`
  - maps blocked evidence verdict to needs-evidence action
  - serializes buckets in this order: `d_to_c`, then `c_to_b`, then `b_to_a`
- `scripts/wf78_tier_funnel_promotion_gate.py`
  - computes missing families and sets `blocked_missing_evidence` when evidence set incomplete
- `scripts/wf78_routing_dashboard.py`
  - `build_routing_rows` sets rank by source-order index, so ranking is queue order + transition context, not actionability score.

## Root cause summary
The top-10 are exactly the highest-priority Tier C→B repair candidates after evidence gating, not active investment/recommendation candidates. Their common blocker is total absence of required evidence families in this snapshot. The “monitor-only” interpretation is therefore operationally accurate for this state.

## Recommended remediation
- Refresh the decision family corpus used by owner decision packet and phase2/phase3 decision builders before treating ranking as deployment/decision-ready.
- Re-run owner decision/funnel pipeline end-to-end, then regenerate routing dashboard from that fresh packet.
- Validate:
  - `needs_evidence` / `blocked_missing_evidence` reduction
  - increase in `actionable_now_count`
  - per-ticker evidence family fill rates
- Only then produce an “actionable top-10” slice (`actionable_now=true`, complete families, fresh freshness) to avoid confusion.

## What to do next
If you want, switch this output to an actionable queue snapshot and I will generate a companion audit file for the resulting top-10 that includes:
- evidence family completeness by ticker
- missing-family list by candidate
- promotion readiness status (decision-grade vs monitor-only)
