# Collector Recovery

Read only when manual collector recovery has been explicitly approved or when assessing whether an earlier restart proves durable supervision. Status-only inspection must not start, restart, or alter any service, automation, or Scheduled Task.

1. Restart through the existing launcher, never a hand-rolled `otelcol.exe` call or another config path. Launch it so it outlives the exec session; foreground exec dies with its session:

   ```powershell
   .\scripts\start_local_otel_collector.cmd
   ```

2. Keep `tools\otelcol\openclaw-local-otel-runtime-metadata.yaml` on loopback `127.0.0.1:4318`, with no external export. Verify in order: `otelcol` process present and 4318 reachable; `python scripts\otel_ops_control.py --write --write-db --multi-window --validate` returns `status=ok` with all five windows ok; then rerun the blocked consumer. For WF74 collection, `python scripts\wf74_model_quality_collection_cron_runner.py --write --write-md --validate` must return `steps_blocked: 0` and `otel_window_summary_status: ok`. Claim only the checks that pass.

3. A detached restart proves restored-now, not durable supervision. An owner-approved watchdog automation and at-logon Scheduled Task were verified historically; check their *current* enabled state, last natural runs, and fresh `tmp\otel-collector-watchdog.json` receipt before claiming scheduled or reboot recovery. The watchdog restarts an unreachable endpoint but only alerts on a listening, starving collector; a healthy-listener starvation alert is not an automatic restart. A healthy receipt alone proves neither trigger remains enabled nor that recovery after a reboot has occurred. If either trigger is missing or unverified, report that limit rather than the obsolete "no scheduled task" claim. Manually starting, restarting, or changing supervision still requires matching approval.
