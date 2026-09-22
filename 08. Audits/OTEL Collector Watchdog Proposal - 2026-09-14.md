# OTEL Collector Watchdog Proposal - 2026-09-14

**Status: APPROVED AND APPLIED (A + C + B) - 2026-09-14 18:37 MST (2026-09-15T01:37Z).**
Prepared 2026-09-14 18:22 MST. Approved by Randall 18:25 MST. Main-owned, evidence-first.

### Applied state

| Item | What | Evidence |
| --- | --- |
| A | `Ops - OTEL Collector Watchdog`, cron `*/10 * * * *` @ America/Phoenix, isolated, `--restart --write --validate --starvation-hours 2`, timeout 180s | job `8fa73747-e22d-4751-b574-6846fe90e514`, enabled, forced test run `status=ok completionStatus=succeeded` exit 0 |
| A | failureAlert after 1 -> telegram `8650152206` (matches existing retention job route) | `{"after":1,"channel":"telegram","to":"telegram:8650152206","mode":"announce","accountId":"default"}` |
| C | Zero-event starvation detection (alert-only, never restarts a live collector) | stale-fixture proof: `starving=True`, exit 1, `action=none`, live pid untouched |
| B | `OpenClaw OTEL Collector Watchdog` Scheduled Task, at logon, interactive/Limited as Veritas (mirrors the Gateway task pattern) | registered `State=Ready`, on-demand run `LastTaskResult=0` |
| - | wrapper `scripts\otel_collector_watchdog_run.cmd` | smoke test exit 0 |

Post-apply verification: collector listening on 127.0.0.1:4318 (pid 9948, detached, parent gone);
config sha256 still `c9b51de50b52cc6e01d1c5ef9e3985e7cd7de8a3809e057a9d95d17aa23823e6`;
`otel_ops_control.py --write --write-db --multi-window --validate` = `status=ok` exit 0;
file exporters actively growing. Remove B with:
`Unregister-ScheduledTask -TaskName 'OpenClaw OTEL Collector Watchdog' -Confirm:$false`.

## 1. Problem (confirmed)

The local collector (`tools\otelcol\otelcol.exe`) had no supervision or auto-restart.

Verified failure window: last telemetry **2026-09-13T10:18:57 local (-0700)** = `17:18:57Z`;
the log shows a clean `Received signal from OS {signal: terminated}` -> `Shutdown complete.`
The audit's "last event 2026-09-13T17:10:28Z" is the last **parsed event** in
`tmp/otel-ops-events.jsonl`; both are consistent (last metrics batch 10:10:28 local / 17:10:28Z).
Telemetry was dark ~31.6h until the manual restart at 2026-09-14 17:57 MST.

Root cause of the *silence* (not the death): the collector step inside WF74
(`otel_ops_control`) is a member of `NON_BLOCKING_STEP_NAMES` in
`scripts\wf74_model_quality_collection_cron_runner.py:97`. A down collector makes that
step return non-zero, which is classified `attention`, not `blocked`; the scheduler exit
decision then returns code 0. So collector death produced **no WF74 alert and no job failure** -
it only degraded evidence quality. That is the exact silent-failure gap to close.

## 2. Corrections to the original framing (evidence)

**(a) The collector outage did NOT block WF74.** `otel_ops_control` is non-blocking by name
(code-verified). The one blocked step in the 2026-09-14 18:03 MST run was
`wf74_autonomy_work_router` (rc 2), and its cause is
`required_source_status_not_ok:pm_control_packet:blocked` - a PM-side source, not the collector.
`tmp/pm-control-packet.json` now reads `status=ok` (written 18:20 MST, after that run), and its
`component_validation` contains no OTEL component. The earlier memory note claiming
"OTEL Local Digest blocked by it" is not supported by the artifacts.

**(b) The collector was not crashing.** Every recorded stop across 09-07..09-13 is an external
`signal: terminated`, and every restart was manual (multi-hour to multi-day gaps). The pattern is
process-teardown, consistent with the collector being a child of a shell/session tree - which is
why a plain background start does not survive a gateway restart.

**(c) Consequence for evidence:** the audit's claim limit is correct and still applies to the
pre-restart window - those usage/efficiency figures are displayed-record estimates, not
collector-backed proof. Post-restart telemetry is flowing again.

## 3. What is already implemented and proven (no gated mutation)

`scripts\otel_collector_watchdog.py` (new, local-only, **non-mutating unless `--restart` is passed**).

- Loopback-only bind preserved; config hash unchanged
  (`c9b51de50b52cc6e01d1c5ef9e3985e7cd7de8a3809e057a9d95d17aa23823e6`).
- No config/service/scheduled-task/network/secret mutation; explicit authority boundary block.
- Detection: port probe on 127.0.0.1:4318 + `otelcol.exe` PID probe (PID-identity aware).
- Single-flight lock prevents double-start on overlapping runs.
- Recovery: starts the collector **detached** (`DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP |
  CREATE_NO_WINDOW`) so it survives parent/gateway exit.
- Receipt: `tmp/otel-collector-watchdog.json`; pid file `tmp/otel-collector/collector.pid`.
- Modes: `--print-plan` (no-op), `--dry-run`, `--restart`, `--validate`.

Proof executed this session:
- `--print-plan` -> exit 0, plan only.
- healthy path -> `status=ok action=none healthy=True listening=True pids=[34732]`, exit 0.
- **death + recovery**: killed pid 34732 (simulated outage) -> port down confirmed ->
  `--restart --write --validate` -> `status=ok action=restarted healthy=True listening=True pids=[9948]`,
  exit 0. New collector's parent PID was already gone => truly detached.
- Post-restart telemetry confirmed flowing; `python scripts\otel_ops_control.py --write --write-db
  --multi-window --validate` -> `status=ok`, exit 0, 42 events.

**Disclosure:** proving recovery required one live stop/start of the collector. Service was restored
within the same command; the collector is now detached (strictly better than the prior state).
The identical stop/start is already routine in the 03:30 retention cron.

## 4. Proposal - requires Randall's approval

### A. Recommended (no OS mutation) - watchdog automation
Create one OpenClaw automation (schedule mutation -> approval required):

- Name: `Ops - OTEL Collector Watchdog`
- Schedule: cron `*/10 * * * *` @ `America/Phoenix`
- Target: `isolated`; payload command:
  `"<python313>" scripts\otel_collector_watchdog.py --restart --write --validate`
- `timeoutSeconds`: 180; `delivery.mode: "none"` (silent while healthy)
- `failureAlert`: `after: 1`, mode `announce` -> **channel to be confirmed by Randall**
  (the existing retention job uses `telegram` / `telegram:8650152206`).

Effect: recovers death within <=10 min, including after a gateway restart or reboot once the
gateway is back. Exit stays 0 on successful recovery; exit 1 (-> alert) only when recovery fails.

### B. Optional hardening - reboot gap
A Windows Scheduled Task at logon/startup to start the collector directly would cut the
post-reboot dark window from "<=10 min after gateway up" to seconds. This is OS scheduled-task
mutation -> **separate explicit approval**. Not required for the core fix.

### C. WF74 alert surfacing (recommended, evidence-darkness rule)
Keep `otel_ops_control` non-blocking so job exit stays stable, but close the silence with an
independent rule that is not downgraded:
1. Watchdog alert on `restart_failed` (covered by A).
2. Add a starvation detector: collector listening **but zero events** for > N hours
   (proposed N=2) -> alert. This distinguishes "process down" from "up but not receiving",
   and is the case that actually invalidates evidence. Implementation would be a small bounded
   addition to the watchdog plus a receipt field; still local-only.

## 5. Residual risk / limits

- OpenClaw cron runs inside the gateway: it cannot fire while the gateway is down. Detachment (done)
  covers gateway restarts; B is needed to fully cover reboots.
- `otel_log_retention.py --restart` also stops/starts the collector but has no lock; a simultaneous
  fire could race with the watchdog. It currently no-ops (log 3.67 MB vs 256 MB threshold). Proposed
  mitigation if desired: give it the same single-flight lock.
- Watchdog proves liveness and recovery only; it is not proof of end-to-end telemetry correctness.

## 6. Outcome

A, B and C were all approved and applied on 2026-09-14 18:37 MST. See the Applied state table at the
top of this document for exact IDs, commands and proof.

Remaining open item (not part of the approved scope): `otel_log_retention.py --restart` (03:30 cron)
also stops/starts the collector and has no single-flight lock, so it could in principle race the
watchdog. It currently no-ops (log 3.67 MB vs 256 MB threshold). Adding the same lock is available on request.

Verification after wiring (as required): `python scripts\otel_ops_control.py --write --write-db
--multi-window --validate` -> `status=ok` with collector listening and events flowing in the 1h window,
plus one forced watchdog run proving recovery.
