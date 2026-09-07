# WF70 Run Summary Registry Migration Proof

- **Status:** ok
- **Workflow:** WF70 - Official Company Source Capture and Reconciliation
- **Script:** `scripts/run_summary_refresh.py`
- **Generated:** 2026-05-22T23:37:47Z

## Change

`run_summary_refresh.py` now derives official IR capture required-output aliases from `scripts/official_capture_period_registry.py` / the latest-selector instead of carrying duplicated static Q1 path mappings.

Scope stayed intentionally narrow: the historical 20 run-summary official IR aliases are preserved. Long-tail captures remain tracked through chain-manifest expected outputs and validators rather than widening run-summary required outputs.

## No-drift proof

- Compare artifact: `tmp/wf70-proof/run-summary-registry-migration-normalized-compare.json`
- All windows matched: `True`
- Registry paths match legacy static paths: `True`
- Source still has `q1-2026` literal: `False`
- Excluded fields: `generated_at_utc, run_id`

Window compare:

| Window | Matched | Current status | Legacy status |
|---|---:|---|---|
| morning | True | blocked | blocked |
| post-close | True | blocked | blocked |
| post-earnings | True | blocked | blocked |
| sunday | True | blocked | blocked |

## Validation

- `python -m py_compile scripts\run_summary_refresh.py scripts\official_capture_period_registry.py` ? passed
- `python scripts\test_official_capture_period_registry.py` ? passed
- `python scripts\official_ir_capture_validator.py --all --write --output tmp\official-ir-captures\all-validation.json` ? ok, 31 captures / 0 findings
- `python scripts\validate_fundamental_ir_reconciliation.py --strict` ? ok, 31 packets / 0 findings
- `python scripts\validate_official_earnings_bridge.py --strict` ? ok, 31 bridges / 0 findings
- `python scripts\capital_deployment_recommendation_validator.py` ? ok, 7 packets / 0 critical / 0 warning

## Authority

Review-only. No canon/portfolio/deployment/trade/account/paper order/sizing/sleeve/cash/risk-rule mutation occurred, and no owner approval was inferred.

## Residue

- Current run-summary status remains `blocked` because existing chain artifacts are stale/failed; that is unchanged and unrelated to the registry alias migration.
- Keep `chain_manifest.py`, `fundamental_ir_reconciliation_packets.py`, and `official_earnings_bridge.py` unchanged until this second low-risk consumer proof is accepted.
