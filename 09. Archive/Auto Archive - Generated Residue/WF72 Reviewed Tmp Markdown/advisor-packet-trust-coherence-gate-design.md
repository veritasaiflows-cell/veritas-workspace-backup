# Advisor Packet Trust-Coherence Gate Design

- Generated UTC: `2026-05-24T23:28:41Z`
- Status: **design_ready_review_only**
- Phase: **Phase 3 / next-level workspace intelligence**
- Boundary: **review-only design; no canon/portfolio mutation, no apply/trade/account authority, no owner-approval inference**

## Bottom line

Build a fail-closed bundle validator before treating capital/advisor packets as decision-grade display objects. The current live fixture should **not** be clean advisor-ready: deployment presentation is disallowed, macro gate is degraded, timestamp lineage has an 18.36h run-summary/trigger gap, all 7 recommendation packets are partial/action-blocked, and official-source reconciliation remains manual-required.

## Current observed state

| Surface | Observed state |
|---|---|
| Deployment readiness | generated `2026-05-24T21:22:07.471081+00:00`; `presentation_allowed=False`; `macro_gate=DEGRADED` |
| Timestamp lineage | run summary `2026-05-23T20:43:02Z` vs trigger `2026-05-24T15:04:26.662166+00:00`; gap `18.36`h |
| Dashboard validation | `warning`; warnings `1`; codes `portfolio_suspended_weight_gap` |
| Capital recommendations | `7` proposals; `7` partial source-freshness packets; `7` capital-action-blocked packets |
| Capital validator | status `ok`; summary `{"critical": 0, "packets_checked": 7, "warning": 0}` |
| Official reconciliation | `ok`; packets `31`; manual-required `31`; SEC counts `{"matched": 27, "no_period_match": 4}` |
| Current-window index | status `ok`; missing roles `[]` |

## Validator contract

The validator should bundle-check:

1. **Timestamp lineage** - all required artifacts need parseable `generated_at_utc`; critical roles must be same-window and validation must not predate the packet it validates. Warn above a 2h gap; block clean display above a 6h gap or on cross-window critical roles.
2. **Macro/deployment presentation state** - `presentation_allowed=false` blocks clean display. `macro_gate=DEGRADED` requires a red/amber trust banner and cannot be hidden by clean packet validation.
3. **Source freshness** - partial/stale/manual-required freshness keeps packets review-required and `capital_action_allowed=false`.
4. **Official-source reconciliation** - official captures are evidence, not reconciled readiness. `manual_required`, unreconciled claims, or SEC `no_period_match` must propagate to packet blockers.
5. **Current-window index** - resolve paths through `tmp/current-window-artifacts.json`; missing/cross-window/unreadable critical roles fail closed.
6. **Authority flags** - any true execution/apply/approval-inference flag is critical. Workspace maintenance authority may be recognized only as bounded main-session scope; gate output grants no self-apply, trade, paper, account, cash, or owner-approval authority.

## Output severity and display

| Severity | Meaning | Dashboard behavior |
|---|---|---|
| `critical` | Trust or authority contract is broken/missing. | Red banner; artifact-only; not advisor-ready. |
| `warning` | Useful review object but degraded freshness/reconciliation/presentation. | Red/amber banner; no clean display; blockers visible. |
| `info` | Provenance/context only. | May display as detail; never relaxes blockers. |
| `ok` | All trust gates clean. | Normal review display, while execution/apply flags remain false. |

**Current recommended display:** blocked/artifact-only or degraded-with-red-banner, pending Randall's display preference.

## Blocker taxonomy

- `missing_required_artifact` - critical
- `unparseable_or_missing_generated_at` - critical
- `timestamp_lineage_gap` - warning/critical by threshold
- `presentation_disallowed` - critical
- `macro_gate_degraded` - warning
- `dashboard_warning_propagated` - warning
- `source_freshness_partial` - warning
- `official_reconciliation_manual_required` - warning
- `official_sec_no_period_match` - warning
- `authority_conflict` - critical
- `validator_stale_or_missing` - critical
- `sql_index_invalid` - critical

## Minimal implementation plan

1. Add `scripts/advisor_packet_trust_coherence_gate.py` as a thin bundle validator that reuses existing validator outputs rather than duplicating packet schema validation.
2. Resolve inputs through `tmp/current-window-artifacts.json` role aliases first; record fallback lineage when needed.
3. Implement timestamp parser and lineage graph; warn >2h, block clean display >6h for critical-role gaps.
4. Aggregate deployment presentation, dashboard warnings, source freshness, official reconciliation, current-window completeness, and authority flags.
5. Emit `tmp/advisor-packet-trust-coherence-gate.json` and `.md` with fail-closed booleans plus dashboard banner text.
6. Only then wire dashboard display to consume this gate output.

## Test plan

- Current live fixture should fail closed/degraded with red banner.
- Missing required artifact => critical.
- Capital validation older than recommendation bundle => critical.
- Any trade/apply/owner-approval-inference flag true => critical.
- SEC `no_period_match` > 0 => warning propagated.
- Synthetic clean fixture => `ok`/clean review display, while all execution/apply flags remain false.

## Future acceptance proof

```text
python -m py_compile scripts\advisor_packet_trust_coherence_gate.py
python scripts\advisor_packet_trust_coherence_gate.py --input tmp\portfolio-mutation-proposals\current-capital-deployment-recommendations.json --out tmp\advisor-packet-trust-coherence-gate.json --md tmp\advisor-packet-trust-coherence-gate.md
python scripts\capital_deployment_recommendation_validator.py
python scripts\artifact_index.py validate
dashboard_truth_lint if dashboard consumer is touched
```

## Open owner decision

Decide whether dashboards should show degraded-but-useful packets with a red trust banner or keep them artifact-only until all trust-coherence gates are clean.
