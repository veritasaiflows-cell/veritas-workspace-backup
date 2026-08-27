# OTEL Command Map

Use these commands only as needed for the user request.

## Status And Recommendations

```powershell
python scripts\otel_ops_control.py --write --write-db --multi-window --validate
```

Primary outputs:

- `tmp\otel-ops-control.json`
- `tmp\otel-ops-window-summary.json`
- `tmp\otel-tool-workflow-metadata.json`
- `tmp\otel\control-loop.json`

## Cron / PM / WF74 Follow-Through

```powershell
python scripts\otel_recommendation_closeout.py --write --write-md --validate
python scripts\wf74_autonomy_work_router.py --write --validate
python scripts\pm_implementation_job_queue.py --write --write-db --validate
python scripts\pm_control_packet.py --write --write-db --validate
python scripts\cron_control_packet.py --write --validate
```

## Validation After Code Changes

```powershell
python scripts\test_otel_ops_control.py
python scripts\changed_file_validator_router.py --write --validate
python scripts\validator_bundle_router.py --write --validate
python scripts\implementation_release_contract.py --phase blocking --write --validate
python scripts\control_closeout_bundle.py --validation-budget shared --write --validate
```

## Do Not Use For Status-Only Answers

Do not run broad release/validator bundles for ordinary OTEL status unless code changed, trust regressed, or the user asked for closeout proof.
