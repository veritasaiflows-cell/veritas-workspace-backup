# Partial-Apply Recovery

Read when an authorized archive/cleanup apply is interrupted, crashes, or finishes with a report older than the run, or when a post-apply check finds sources gone without a matching manifest. The files are already moved; this is a recovery procedure, not a re-run. Re-running the cleanup first can move more and deepen the gap. Keep every step read-only until the moved set is inventoried.

1. **Confirm the run moved something and that no manifest documents it.** Compare the apply report's mtime against the run time: a report older than the run means the process died before writing its record. Inspect the archive run directory for a dated folder and measure it. Finish with moved file count and bytes, plus an explicit statement of whether a manifest exists.
   Verified 2026-09-22: `tmp_cleanup.py --apply` crashed in `manifest_record()` (`FileNotFoundError` on a transient `*.tmp` written by a live producer) after moving 7,543 files / 750.3 MB, because the move loop runs before the report write; the on-disk report was still the previous dry-run.

2. **Reconstruct the rollback inventory before changing anything.** Walk the archive run directory and record source-relative path, size and mtime for every moved file; write it to a durable artifact under `tmp/`. This is name/size/mtime evidence, not hash-verified proof — say so, and hash the archive copies directly when a hash-grade claim is needed. Finish when the inventory file exists and its count matches the measured tree.

3. **Reconcile the moved volume against the dry-run before calling it a defect.** A dry-run listing candidates as entries (files plus directories) sums bytes over file records only, because directory records carry a null size. Compare entry counts, not the byte total: 2,262 candidate entries (2,151 files plus 111 directories holding 7,543 files) is consistent with 750.3 MB moved, so the byte total alone (291.1 MB) is not a contradiction. Finish with a stated reconciliation, or the gap named unexplained.

4. **Restore git-tracked sources first.** List deletions (`git status --porcelain`, `D` entries), restore each path, then confirm the missing-tracked count is zero. Restore only paths the apply moved; leave unrelated dirty work untouched. Finish with missing-tracked at zero and the deletion entries gone.

5. **Restore live-referenced sources the tool's protection lists did not cover.** A static protected-name list is not a live reference check. For each directory or file a live route reads, verify it is present and that the consumer's expected path resolves, and move it back from the archive when it is not; a tool's `PROTECTED_DIRS`/`PROTECTED_FILES` set may omit a live-read path entirely. Finish with each restored path present and its consumer's expected path resolving.

6. **Establish whether an "absent" file was ever a candidate before calling it damage.** Check the file against the candidate list and against any prior retirement archive. A file absent from the working tree may have been retired earlier by design, and misreporting a pre-existing absence as apply damage sends the owner after the wrong problem. Finish when each reported absence is either confirmed as moved by this run or explained by an earlier retirement.
   Verified 2026-09-22: three files reported as missing were never in the candidate list and had been retired weeks earlier — the alarm came from a faulty existence check, not from the apply.

7. **Deduplicate archive copies of anything restored.** Delete an archive copy only when its size matches the restored file. Finish with copies of restored paths removed and the archive tree still holding all unrestored content.

8. **Verify the protected set and downstream consumers, then report.** Re-check every live/keep directory and file, confirm the live producer is still running, and re-run the affected validators. Report the moved volume, the reconstructed inventory location, what was restored, and the unverified remainder (hashes not taken). Finish with the keep set intact and the recovery's evidence limits stated, never a clean bill of health.

Recovery does not fix the tool. Route the ordering defect (moves before the manifest write) and any unhandled transient-input crash to their owner as a separate bounded repair, and do not re-run the apply until that ordering is fixed.
