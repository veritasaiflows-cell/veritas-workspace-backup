# WF74-WF88 Bootstrap OTEL Enforcement Implementation Contract - 2026-07-03

Status: implemented / release proof clean / review-only enforcement
Owner workflow: WF74-WF88
Accountable integrator: Veritas main session
Authority: local proof and implementation planning only

## Objective

Make the WF74/WF88 self-improvement system fully enforce:

1. Wiki/bootstrap proof before material WF74/WF88/OTEL work.
2. Durable closure or reclassification of the one overdue improvement-ledger row.
3. OTEL runtime metadata emission proof so the learning loop can consume richer metadata-safe runtime evidence.

## Implementation Closeout - 2026-07-03/04

Implemented in lane `WF74-WF88::bootstrap-otel-enforcement-20260703`.

Current proof:

- `tmp/wiki-bootstrap-proof.json`: `bootstrap_warning_no_apply_authority`; required files `3/3`, missing markers `0`, leak guard `True`, auto-apply `0`, no-orphan `ok`. Warning is classified WF88 wiki synthesis posture, not bootstrap failure.
- `tmp/improvement-ledger-current.json`: `ok`; `followup_required_open_count=0`, `high_priority_overdue_open_count=0`.
- `tmp/otel-runtime-metadata-probe.json`: `ok`; runtime metadata observed, forbidden marker counts `0`, emission repair packet `not_required`, learning-ready `True`.
- `tmp/wf88-wiki-synthesis-packet.json`: warning/no-apply posture; page count `9`, leak guard `True`, open unrouted recommendations `0`, auto-apply `0`, follow-up-required open improvements `0`.
- `tmp/startup-brief-packet.json` and `tmp/veritas-status-card.json`: bootstrap proof surfaced; status is `stale_input_warning` from existing PM/autonomy freshness residue, validation `ok`.
- `tmp/implementation-release-contract.json`: `ok`, `ready_to_close=True`.

Actual lane write scope excluded `memory/2026-07-03.md` because the active WF75 lane held the daily-memory surface. The durable closeout proof is carried by this contract, the lane register, and generated proof packets.

## Current Baseline

Current refreshed proof shows the system is mostly healthy but not fully enforced:

- WF88 OS2: `control_packet_ready_no_apply_authority`, stale input count `0`.
- WF88 wiki synthesis: `wiki_synthesis_warning_no_apply_authority`, leak guard pass, open unrouted recommendations `0`, auto-apply `0`.
- WF74 queue: `2` open opportunities, top row `Keep WF87 runtime blockers visible as maturity blockers`.
- WF74 auto-patch proposer: `2` plans, `1` patch plan, `0` Skill Workshop requests, `2` owner-gated plans, auto-apply `0`.
- WF74 decision docket: `12` rows, `fix_now=0`, `hard_stop=0`, `market_session_accrual=5`, `monitor_only=7`.
- Improvement ledger: `6` open rows, `1` follow-up-required row, `1` high-priority overdue row.
- WF74 self-audit: P1 `fix_now` is `route-overdue-improvement-followup`.
- OTEL ops: collector/control healthy.
- OTEL runtime metadata probe: approved/enabled metadata depth is not observed in current collector stream.
- Token attribution: implementation token events `2`, implementation gaps `364`.
- Retrieval quality: `needs_repair`, average score `0.65`.

## Non-Goals

This contract does not authorize:

- Cron schedule/state mutation.
- OTEL collector/runtime/config mutation.
- Skill Workshop apply/reject/quarantine.
- Destructive cleanup, archive, move, or delete.
- Finance canon/portfolio/cash/sizing/risk mutation.
- Paper/live/account/brokerage action.
- External delivery or telemetry export.
- Raw prompt/response/tool-payload capture.
- Model training, base-model self-modification, or owner-approval inference.

## Required Implementation Lanes

### Lane 1 - Bootstrap Proof Gate

Goal: prove a new/material session opened the required wiki/bootstrap route before acting.

Owner surfaces:

- `wiki/README.md`
- `wiki/index.md`
- `wiki/source-map/WF88 Wiki Source Map.md`
- `tmp/wf88-wiki-synthesis-packet.json`
- `tmp/wf88-os2-control-packet.json`
- `tmp/actionable-improvement-queue.json`
- `tmp/no-orphan-validator.json`
- `scripts/startup_brief_packet.py`
- `scripts/status_card_packet.py`
- `scripts/future_session_enhancement_packet.py`

Implementation shape:

1. Add `scripts/wiki_bootstrap_validator.py`.
2. Validator checks required wiki files exist and contain required markers:
   - `Status: synthesis only`
   - `Owner workflow: WF88`
   - `Authority boundary`
   - `Promotion path`
   - source artifact section.
3. Validator checks packet truth:
   - `auto_apply_count == 0`
   - recommendation leak guard pass is true
   - no-orphan validation is not blocked
   - wiki page count is expected
   - source freshness is inside threshold or warning is explicitly classified.
4. Validator writes `tmp/wiki-bootstrap-proof.json`.
5. Startup/future/status packets consume the proof and surface:
   - bootstrap proof present
   - required wiki files opened/validated
   - proof age
   - blocking reason when missing.
6. Material WF74/WF88 startup treats missing proof, leak-guard failure, blocked wiki validation, or nonzero auto-apply as a hard stop.

Acceptance proof:

```powershell
python scripts\wiki_bootstrap_validator.py --write --validate
python scripts\test_wiki_bootstrap_validator.py
python scripts\future_session_enhancement_packet.py --write --write-md --validate
python scripts\startup_brief_packet.py --write --validate
python scripts\status_card_packet.py --write --validate
python scripts\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate
```

Success state:

- `tmp/wiki-bootstrap-proof.json` status is not blocked; warning is allowed only when warnings are classified no-apply/review-only posture.
- Startup/status/future packets show bootstrap proof current.
- Material WF74/WF88 route can prove wiki bootstrap before work.

Stop lines:

- Do not block shallow `Status?` from rendering cached status.
- Do not require broad packet regeneration for shallow status.
- Do not mutate cron schedule to enforce this in Lane 1.

### Lane 2 - Overdue Improvement Ledger Closure/Reclassification

Goal: close the current high-priority overdue row or reclassify it into a durable standing monitor/accrual state with proof.

Target row:

- `Keep WF87 runtime blockers visible as maturity blockers`

Current issue:

- The item is routed into WF74 decision docket and actionable queue, but `improvement_ledger.py` still reports `followup_required_open_count=1` and `high_priority_overdue_open_count=1`.
- This creates false urgency even though the correct route is market-session accrual / maturity visibility, not immediate implementation.

Owner surfaces:

- `scripts/improvement_ledger.py`
- `scripts/actionable_improvement_queue.py`
- `scripts/no_orphan_validator.py`
- `scripts/wf74_decision_docket.py`
- `scripts/wf74_self_audit_cadence_packet.py`
- `tmp/improvement-ledger-current.json`
- `tmp/wf74-decision-docket.json`
- `tmp/actionable-improvement-queue.json`

Implementation shape:

1. Inspect how `improvement_ledger.py` classifies durable WF87 maturity visibility rows.
2. Add a closure/reclassification path for rows that are:
   - already routed to WF74 decision docket,
   - explicitly market-session accrual or monitor-only,
   - backed by current WF87 runtime/readiness proof,
   - not an immediate code/config/cron/runtime fix.
3. Preserve high-priority escalation when the row lacks a durable destination or proof command.
4. Ensure `wf74_self_audit_cadence_packet.py` no longer marks `route-overdue-improvement-followup` as `fix_now` once the ledger row is classified correctly.
5. Add/update regression tests.

Acceptance proof:

```powershell
python scripts\test_improvement_ledger.py
python scripts\improvement_ledger.py --write --write-md --validate
python scripts\actionable_improvement_queue.py --write --write-md --validate
python scripts\no_orphan_validator.py --write --validate
python scripts\wf74_decision_docket.py --write --write-md --validate
python scripts\wf74_self_audit_cadence_packet.py --write --write-md --validate
```

Success state:

- `followup_required_open_count=0` unless a real unclassified follow-up exists.
- `high_priority_overdue_open_count=0` for the WF87 maturity visibility row.
- WF74 decision docket still surfaces the row as market-session accrual or monitor-only.
- No-orphan validation remains `ok`.

Stop lines:

- Do not delete ledger history.
- Do not hide real unresolved improvement debt.
- Do not close rows by source absence alone.
- Do not convert WF87 runtime blockers into execution readiness.

### Lane 3 - OTEL Runtime Metadata Emission Proof

Goal: make approved metadata-safe runtime fields observable in local OTEL, or prove precisely why the approved field path is not emitting.

Current issue:

- OTEL collector/control is healthy.
- `otel_runtime_metadata_probe.py` reports:
  - `metadata_depth_approved_enabled=true`
  - `runtime_metadata_observed=false`
  - `allowed_field_count=0`
  - `enabled_vs_observed_reconciliation=approved_enabled_not_observed`
  - `emission_path_diagnosis=collector_debug_log_current_allowed_fields_absent`

Owner surfaces:

- `scripts/otel_runtime_metadata_probe.py`
- `scripts/otel_ops_control.py`
- `scripts/otel_tool_workflow_metadata.py`
- `scripts/otel_learning_loop.py`
- `tmp/otel-runtime-metadata-probe.json`
- `tmp/otel-ops-control.json`
- `tmp/otel-tool-workflow-metadata.json`
- `tools/otelcol/openclaw-local-otel-runtime-metadata.yaml`

Implementation shape:

1. Audit the approved metadata owner packet and current collector stream.
2. Identify the producer expected to emit allowed runtime fields.
3. Add an emission-path diagnostic packet, not a config mutation:
   - producer present/missing
   - allowed field names expected
   - collector file/source inspected
   - recent runtime event available
   - observed allowed fields
   - forbidden raw-content/secret marker counts.
4. If missing because no local runtime event occurred, create a safe local test event path that emits only approved metadata fields.
5. If missing because producer does not stamp fields, stage a separate owner-gated runtime/config repair plan.
6. Wire observed metadata into WF74/WF88 learning only after privacy scan and regression proof pass.

Acceptance proof:

```powershell
python scripts\test_otel_runtime_metadata_probe.py
python scripts\otel_runtime_metadata_probe.py --write --write-md --validate
python scripts\otel_ops_control.py --write --write-db --multi-window --validate
python scripts\otel_tool_workflow_metadata.py --write --validate
python scripts\otel_learning_loop.py --write --validate
python scripts\wf74_improvement_opportunity_queue.py --write --write-md --validate
python scripts\wf74_self_audit_cadence_packet.py --write --write-md --validate
```

Success state:

- Either `runtime_metadata_observed=true` with allowed fields present and forbidden marker counts `0`, or a precise owner-gated repair packet exists.
- OTEL remains local-only and metadata-only.
- WF74 learning loop can consume richer runtime metadata without raw prompt/response/tool capture.

Stop lines:

- Do not mutate collector config in this lane without explicit approval.
- Do not expand capture depth beyond approved metadata fields.
- Do not capture raw prompt, response, tool payload, headers, secrets, account data, or customer data.
- Do not send telemetry externally.

### Lane 4 - Wiki Page Freshness Parity

Goal: prevent durable wiki pages from drifting behind `tmp/wf88-wiki-synthesis-packet.json`.

Owner surfaces:

- `scripts/wf88_wiki_synthesis_packet.py`
- `scripts/wf88_daily_actionability_refresh.py`
- `wiki/`
- `tmp/wf88-wiki-synthesis-packet.json`

Implementation shape:

1. Add/update parity checks in `test_wf88_wiki_synthesis_packet.py`.
2. Ensure `wf88_daily_actionability_refresh.py` calls the wiki synthesis with `--write-wiki`.
3. Add summary hash or generated-at parity fields if needed.
4. Startup/status packets should report stale wiki page parity separately from packet warning/no-apply posture.

Acceptance proof:

```powershell
python scripts\test_wf88_wiki_synthesis_packet.py
python scripts\test_wf88_daily_actionability_refresh.py
python scripts\wf88_daily_actionability_refresh.py --dry-run --validate
python scripts\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate
```

Success state:

- Wiki pages match current packet summary fields after refresh.
- Warning/no-apply posture is not confused with stale-page drift.

### Lane 5 - Closeout And Release Proof

Goal: prove the enforcement path is safe, current, and not authority-expanding.

Required producer order:

```powershell
python scripts\wiki_bootstrap_validator.py --write --validate
python scripts\improvement_ledger.py --write --write-md --validate
python scripts\actionable_improvement_queue.py --write --write-md --validate
python scripts\no_orphan_validator.py --write --validate
python scripts\otel_runtime_metadata_probe.py --write --write-md --validate
python scripts\otel_ops_control.py --write --write-db --multi-window --validate
python scripts\otel_learning_loop.py --write --validate
python scripts\wf74_improvement_opportunity_queue.py --write --write-md --validate
python scripts\wf74_autonomy_work_router.py --write --validate
python scripts\wf74_auto_patch_proposer.py --write --write-md --validate
python scripts\wf74_decision_docket.py --write --write-md --validate
python scripts\wf74_learning_loop_eval_harness.py --write --validate
python scripts\wf74_self_audit_cadence_packet.py --write --write-md --validate
python scripts\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate
python scripts\wf88_os2_control_packet.py --write --write-md --validate
python scripts\future_session_enhancement_packet.py --write --write-md --validate
python scripts\startup_brief_packet.py --write --validate
python scripts\status_card_packet.py --write --validate
```

Release proof:

```powershell
python scripts\changed_file_validator_router.py --write --validate
python scripts\validator_bundle_router.py --write --validate
python scripts\implementation_release_contract.py --phase blocking --write --validate
python scripts\control_closeout_bundle.py --validation-budget shared --write --validate
python scripts\implementation_release_contract.py --phase blocking --write --validate
```

Success state:

- Bootstrap proof current.
- Improvement ledger has no false overdue row for routed WF87 maturity blocker.
- OTEL metadata emission either observed safely or owner-gated with exact repair plan.
- Wiki packet/page parity current.
- WF74/WF88 still report `auto_apply_count=0`.
- No new owner-gated action is applied.

## Suggested Work Order

1. Implement Lane 1 first because it prevents future session drift.
2. Implement Lane 2 second because it clears the active false-urgency cleanup debt.
3. Implement Lane 3 third because it improves learning-loop signal quality.
4. Implement Lane 4 after Lane 1/3 so the wiki mirrors the new proof accurately.
5. Run Lane 5 closeout after all touched producers regenerate downstream packets.

## Lane Register Contract For Implementation

Before implementation starts:

```powershell
python scripts\concurrent_lane_manager.py --status --write --validate
```

Use a distinct lane name such as:

`WF74-WF88::BOOTSTRAP-OTEL-ENFORCEMENT-20260703`

Allowed writes should be exact and phase-scoped. Suggested first lane writes:

- `scripts/wiki_bootstrap_validator.py`
- `scripts/test_wiki_bootstrap_validator.py`
- `scripts/startup_brief_packet.py`
- `scripts/status_card_packet.py`
- `scripts/future_session_enhancement_packet.py`
- `06. Playbooks/Startup Truth Index.md`
- `memory/2026-07-03.md` only if no active lane owns daily memory.

The implemented lane was explicitly broadened to include improvement-ledger closure/reclassification and OTEL probe/front-door wiring after a collision-free lease was obtained. Daily memory remained excluded because WF75 owned that write surface.

## Final Acceptance Contract

The project is fully functional only when all of this is true:

- New/material WF74/WF88 sessions have machine-readable wiki bootstrap proof.
- Startup/status/future-session surfaces expose bootstrap proof status.
- WF88 wiki leak guard passes, no-orphan validation passes, and auto-apply remains zero.
- Current overdue improvement-ledger row is closed or reclassified without hiding real debt.
- OTEL runtime metadata fields are observed safely or a precise owner-gated producer repair packet exists.
- WF74 self-audit no longer has unresolved P1 `fix_now` for overdue follow-up routing.
- Daily actionability refresh and wiki refresh gate pass.
- Release contract is clean or any remaining warning is explicitly classified as no-apply/owner-gated posture rather than a hidden defect.
