# WF72 SQL Adoption Phase 5B Dashboard Trust Proof

- Status: ok
- Generated: 2026-05-23T00:55:40Z
- Scope: propagate derived SQL artifact-index health from run-summary into dashboard trust state.
- Authority: SQL remains derived proof/index/staging only; no canon/apply/portfolio/trade/account/paper/approval authority.

## What changed

- `dashboard_run_summary_consumer.py` now writes `trust.artifact_index` from the run-summary artifact-index health block.
- Workflow-window dashboard alerts warn when SQL cockpit health is degraded.
- `test_run_summary_tail_order.py` covers the dashboard propagation and degraded SQL warning path.
- Startup/procedure/README/run-summary contract wording now consistently routes generated-artifact lookup through SQL first, with `tmp/current-window-artifacts.*` as compatibility/fallback.

## Proof

- Run-summary/dashboard propagation: dashboard SQL status `ok`, boundary `derived_review_only_index_not_canon_not_apply`.
- Artifact-index validation: `ok`, checks `{'checks': 15, 'failed': 0}`, safety counts `{'canon_stage_apply_allowed': 0, 'forbidden_true_authority_flags': 0, 'official_ir_fields_without_lineage': 0}`.
- Targeted tests: py_compile passed; `python scripts\test_run_summary_tail_order.py` passed; real `run_summary_refresh.py --window post-close` + `dashboard_run_summary_consumer.py --window post-close` passed.

## Known blocker outside this change

- `python scripts\test_dashboard_acceptance.py` remains failed: {'passed': 25, 'failed': 1, 'total': 26, 'all_passed': False}. Failed check is `workflow8_command_center_alignment` with ETN/JPM/LMT WF8 alignment drift. This is not caused by SQL trust propagation and was not repaired in this pass because it touches finance/dashboard semantics.
