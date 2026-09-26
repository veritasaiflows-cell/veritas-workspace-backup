# Collector Artifact Retention

Read when an owner has approved bringing a local collector output file under retention, or when changing an existing retention route's threshold, window or budget. This branch records how an approved change is made; it is not permission to make one, and it does not authorize collector-config, exporter, capture-depth or schedule changes.

1. **Confirm the specific file has no route before adding one.** Check the retention owner's defaults and its contract argv, not the contract name: the local log-retention route defaults to `collector.err.log` and `collector.out.log`, so a sibling output in the same directory can be uncovered while the directory looks managed. Finish with the route's actual file list.

2. **Size the policy against a measured growth rate.** Derive it from the file's own timestamps, never from size divided by age, as [Performance And Disk Mass Review](../../veritas-workspace-audit-orchestrator/references/performance-and-disk-mass-review.md) prescribes in its closing retention rule - then choose cadence, threshold and budget against that rate. A cadence longer than threshold/rate cannot hold the stated target size. Finish with the rate, the cadence and the resulting peak live size.

3. **Rotation must stop the writer.** The collector holds its output file open, so truncating in place leaves the writer positioned past EOF. Stop the owning process, move the file, then restart the same config through the collector's owner-gated recovery step - never a hand-rolled executable call or a different config path - and confirm the process is present and its endpoint reachable before claiming restoration.

4. **Rotate by move, then compress, then prune; delete nothing early.** Move the live file to a dated archive, take the source hash before removing the original, and compress only after the copy has landed. Measure the compression ratio rather than assuming one, because the total-size budget is denominated in compressed bytes; a real archive measured 13.19x.

5. **Key archive age from the rotation stamp in the filename when archives are compressed.** Gzip is not seekable, so finding the newest record by tail-reading an archive means decompressing every archive. Enforce the total-size budget after compression so it measures real on-disk bytes, and let the age window be the upper bound while the budget catches a rate spike.

6. **Trigger on size, not age, when the live file holds only days of data.** An age rule cannot bound a file that is rewritten faster than its own window.

7. **Register the route as a drift-checked contract, then prove it.** Two mechanics cost extra round trips when missed: the automations tool refuses command payloads so job creation goes through the CLI, and under PowerShell 5.1 a bare JSON `--command-argv` string is mangled by native-command quoting - pass it backslash-escaped inside single quotes. After creating the job, set its failure alert (the alert flags live on edit, not on add) and re-run the contract validator until drift is zero on both the description and the alert fields. Then force one run, read the run history for its exit status, confirm the named artifact, and confirm the collector is healthy and writing again after the restart.

**Claim limit:** a route that ran once under a forced trigger is not proof it will run on schedule; report scheduler execution, run history and local success separately, and never present a task-time measurement as a standing value.
