# PM WF74 Learning Runtime Blocker Audit

Generated: 2026-06-23 23:04 MST / 2026-06-24 06:04 UTC  
Scope: PM job `pm-wf74-learning-runtime-inspect-blocker` / `pm-wf74-code-mutation-repair-blocked-collection-step` and its underlying WF74 model-quality collection runner.  
Authority: review-only. No code mutation, config/runtime change, SQL write/import, canon/portfolio/sizing/cash/risk mutation, paper/live/brokerage/account action, customer data/credentials/outreach, or owner approval inference.

## Executive Summary

The PM blocker is **current, not stale**. `wf74_model_quality_collection_cron_runner.py` and `model_quality_scorecard.py` both report `status=blocked` / `validation=critical` because the `finance_response_quality_slice` step reports `source_open_blocked_count=42` and `status=blocked`.

The original blocker narrative said the issue was an outdated embedded scorecard result and that the standalone scorecard was now clean. That is no longer true on the latest run. The scorecard is correctly fail-closed: it will not pass while finance response quality is blocked, regardless of SQL-canon access being ok and regardless of `production_grade_candidate_count=0` being a valid policy state.

The deeper issue is that the PM job is **mis-routed**. It sits in `runtime_ops` with a title implying a code-mutation repair to WF74, but the actual fix belongs in the finance domain repair conveyor (`WF78/WF85 source-open repair`). The runner is doing its job by blocking; the defect is upstream in finance response quality.

## Live Proof

Commands executed:

1. `python scripts\wf74_model_quality_collection_cron_runner.py --write --write-md --validate`
2. `python scripts\model_quality_scorecard.py --write --write-md --validate`
3. `python scripts\pm_control_packet.py --write --write-db --validate`

### WF74 runner

| Field | Value |
|---|---|
| status | `blocked` |
| steps_total | 15 |
| steps_ok | 13 |
| steps_blocked | 1 |
| steps_attention | 1 |
| blocking_step | `model_quality_scorecard` |
| non_blocking_attention | `finance_response_quality_slice` |
| wf74_validation_status | `critical` |

### Model quality scorecard

| Field | Value |
|---|---|
| status | `scaffold_active` |
| validation | `critical` |
| active_tracks | implementation_quality, performance, learning_capture, decision_quality |
| critical | 1 |
| critical finding | `finance response quality slice must be ok` |

### Finance response quality slice

| Field | Value |
|---|---|
| status | `blocked` |
| average_score | 0.8229 |
| source_open_blocked_count | **42** |
| source_freshness_blocked_count | 0 |
| blocked_archetypes | 5 |
| remediation_tracks_needing_repair | 1 |
| wf72_support_only | true |
| sector_timing_warning | true |

### SQL-canon context in scorecard

| Field | Value |
|---|---|
| access_validation_status | `ok` |
| production_answer_count | 0 |
| production_grade_count | 0 |
| legacy_production_answer_count | 42 |
| legacy_42_retired_from_blocking | true |
| legacy_42_role | `historical_compatibility_only_not_readiness_or_repair_authority` |

### PM control packet

| Field | Value |
|---|---|
| status | `ok` |
| top_action | `wf74_learning_runtime-inspect_blocker` |
| top_job_id | `pm-wf74-code-mutation-repair-blocked-collection-step` |
| department | `runtime_ops` |
| readiness_score | 15 |
| blocked_lanes | 1 |
| wf74_steps_blocked | 1 |
| wf74_steps_ok | 13 |

## Findings

### F1 — The Blocker Is Current, Not Stale

**Evidence:**
- `wf74_model_quality_collection_cron_runner.py` generated at 2026-06-24 06:06 UTC reports `steps_blocked=1`.
- `model_quality_scorecard.py` generated at the same time reports `validation=critical` with one critical finding: `finance response quality slice must be ok`.
- The scorecard correctly treats `finance_response_quality_status=blocked` as a critical gate.

**Impact:** Rerunning the runner without fixing the finance response quality slice will keep producing the same blocker.  
**Severity:** P1 — operational noise but the underlying gate is healthy.

### F2 — The Finance Response Quality Slice Is Blocked by Source-Open Gaps

**Evidence:**
- `source_open_blocked_count=42`.
- `source_freshness_blocked_count=0`.
- `wf72_support_only=true`.
- `remediation_tracks_needing_repair=1`.

**Interpretation:** The 42 rows are not stale-market-data failures; they are cases where the answer requires a source-open review or lineage repair before the response quality gate can pass. This is exactly the kind of residue the WF78 repair conveyor is designed to surface.  
**Severity:** P1 — finance-domain repair debt.

### F3 — The Scorecard Correctly Distinguishes Two Different "Zero" States

**Evidence:**
- `production_grade_count=0` is treated as a valid wait state (new policy is fail-closed).
- `legacy_production_answer_count=42` is treated as compatibility-only and retired from blocking.
- `finance_response_quality_status=blocked` is treated as a real critical gate.

**Impact:** The original blocker description conflated the production-grade zero policy with the finance-response-quality blocked state. The scorecard now separates them correctly. The remaining blocker is the 42 source-open rows, not the empty production-grade set.  
**Severity:** P2 — clarity issue in the PM job text.

### F4 — The PM Job Is Mis-Routed

**Evidence:**
- Job title: `Repair blocked WF74 collection step`.
- Department: `runtime_ops`.
- Owner workflow: `Runtime Ops/WF74`.
- Actual blocker: `finance_response_quality_slice` with 42 source-open rows.
- Finance repair conveyor already has 200 rows and 94 classified as `wf78_source_open_or_owner_lineage_repair`.

**Impact:** A runtime_ops code-mutation lane cannot fix a finance response quality source-open problem. The job will keep cycling until the finance-domain repair is done or the gate policy is changed.  
**Severity:** P1 — queue routing error.

### F5 — The WF74 Runner Is Behaving Correctly

**Evidence:**
- The runner blocks on a downstream critical scorecard result.
- It does not self-authorize, rank models, capture raw content, mutate config, or infer owner approval.
- All authority flags and forbidden actions from the job description are preserved.

**Impact:** No WF74 code fix is needed. The runner should stay fail-closed.  
**Severity:** P2 — confirms the runner is the symptom, not the disease.

## Recommendations

### R1 — Re-Route the PM Job to Finance Domain Repair (P1)

Change the job identity and proof path:

- **Department:** move from `runtime_ops` to `finance_wf78_wf84_wf85`.
- **Title:** change from `Repair blocked WF74 collection step` to `Clear finance response quality source-open blockers so WF74 scorecard can pass`.
- **Proof command:** keep `python scripts\wf74_model_quality_collection_cron_runner.py --write --write-md --validate` as the acceptance check, but add the upstream repair commands as the work surface:
  - `python scripts\wf78_source_open_repair_executor.py --tier all --write --validate`
  - `python scripts\wf78_source_open_work_packet.py --write --validate`
  - `python scripts\finance_response_quality_slice.py --write --validate` (or equivalent)

### R2 — Update PM Job Text to Match the Actual Blocker (P1)

Current job text:
> Run wf74_model_quality_collection_cron_runner.py with harness, then refresh pm_control_packet.py so PM sees the latest coding/runtime KPIs.

Proposed update:
> WF74 runner is blocked because the finance response quality slice has 42 source-open blocked rows. Clear those source-open/lineage repair items, then rerun the WF74 collection runner and refresh PM.

### R3 — Keep the Scorecard Fail-Closed on Finance Response Quality (P2)

Do **not** downgrade `finance_response_quality_status=blocked` to a warning inside `model_quality_scorecard.py`. The current behavior is correct. If PM wants the runner to pass while finance response quality is still blocked, that should be an explicit policy decision, not a silent relaxation.

### R4 — Add a Diagnostic Step to the Runner That Names the Upstream Source (P3)

The runner's output currently says `blocking_step: model_quality_scorecard`. It would be more useful if the runner also emitted:

```json
{
  "blocker_chain": [
    "wf74_model_quality_collection_cron_runner",
    "model_quality_scorecard",
    "finance_response_quality_slice",
    "source_open_blocked_count=42"
  ],
  "recommended_department": "finance_wf78_wf84_wf85"
}
```

This would make future PM routing less error-prone.

## Acceptance Criteria for Closing This PM Blocker

The job should be considered handled when:

- [ ] The PM job is reclassified under `finance_wf78_wf84_wf85` (or at least tagged with finance-domain dependency).
- [ ] `finance_response_quality_slice` reports `status=ok` or the 42 `source_open_blocked_count` rows are explicitly triaged/accepted.
- [ ] `wf74_model_quality_collection_cron_runner.py` completes with `steps_blocked=0` and `wf74_validation_status=ok`.
- [ ] `pm_control_packet.py` refreshes and shows the lane no longer blocked.
- [ ] No model-ranking, raw-content-capture, config/runtime mutation, SQL write/import, canon/portfolio/sizing/cash/risk mutation, paper/live/brokerage/account action, customer data/credentials/outreach, or owner approval inference occurs.

## Bottom Line

This is a **finance-domain repair blocker wearing a runtime_ops costume**. The WF74 collection runner and model-quality scorecard are correctly fail-closed. Fix the 42 source-open finance response quality rows through the WF78/WF85 source-open repair path; do not patch WF74 to ignore them. Then refresh PM and the lane will clear.
