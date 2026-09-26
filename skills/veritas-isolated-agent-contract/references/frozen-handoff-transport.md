# Frozen Handoff Transport

Read when preparing bounded specialist inputs, proving receiver access, or recovering a stale scoped worktree. This branch grants no new mount, tool, configuration, or archive authority.

## Freeze and select transport

1. Record parent job, lane, phase, attempt/retry, expected backend/model/thinking, task shape, authority, exact writes, deliverable, acceptance proof, next recipient, and stop lines. Include a workspace-relative base, sorted file inventory with byte sizes and SHA-256 hashes, contract hash, frozen snapshot ID, and deterministic preflight fingerprint/status. Enforce at most 6 files, 120,000 bytes, and 30,000 estimated context tokens. Reject absolute manifest paths, any `..` component, directories, symlink/reparse escapes, case-folded duplicates, and over-budget payloads. For patches, include source-preimage hashes/sizes and declare `source_writes: false` unless live writeback is separately proven. Main checks the current lane register before dispatch. If the isolated receiver cannot read Main's register, include the exact bounded lease row and attributed validation proof; the receiver checks that supplied identity/scope rather than probing an inaccessible host path. A copied row is not fresh execution authority by itself. When the receiver lacks a directory-listing tool, stage a conventional `handoff-manifest.json` plus a small `FILE-INDEX.md` containing every exact relative path, and name both paths explicitly in the dispatch. Generate the index after staging and hash its final bytes; do not require the receiver to discover or guess packet filenames. Re-hash immediately before dispatch; finish with an immutable source set.

2. Select from the receiver's actual callable transport and configured mounts, not the session label. Main's host `tmp/` or `state/` path and an arbitrary file in the persistent agent workspace are not automatically reachable by a spawned child. An explicitly configured `/worktree` bind can reach it: inspect that exact bind and stage within its existing host source. Probe exact frozen filenames inside the container; a failed bare-directory probe does not establish that files below an allowed mount are inaccessible. For a read-only reviewer without listing, require it to open the dispatch-named manifest and file index first, then the listed paths. Failure to discover unnamed files is a transport/packaging failure, not a semantic verdict: add the exact index, reseal the packet, and use a fresh review rather than patching the candidate. Verify file readback before declaring transport available.

3. For attachments, require current staging support. Send a small raw UTF-8 manifest and one raw UTF-8 attachment per file; keep each attachment and individual line at or below 40 KB. Do not send nonempty attachments through a spawn contract that declares staging unsupported. Prove the exact decoder/reader shape before using gzip, base64, or a large one-line JSON envelope.

4. If staged and attachment transport are unavailable, use the existing inline branch: embed complete inputs between explicit begin/end markers with the same 40 KB per-file cap. Require byte-faithful extraction and independently computed SHA-256 matches before drafting. Return exact old_text/new_text spans; Main applies unique matches and verifies post-apply hashes against the child's computed hashes. An inline task or nonce alone does not prove extraction or hashing. Child `/workspace` outputs may recover under `~/.openclaw/sandboxes/workspace-<hash>/`, not the persistent workspace root; verify the actual mapping before reading outputs.

## Receiver proof

Run preflight against the actual payload in the same agent/runtime mode. Prove multiline readback at the intended size, readable manifest, source content and hashes, and paths inside the declared base. Prove required decoder/test commands only in the approved sandbox. An empty list of preapproved executables is not an observed tool denial: for an authorized harmless check, use the available first-class tool and honor its actual policy result. If no call was made, record not-run/unverified, not exec-denied. A write lane additionally needs an exact leased output, observed write/readback, and Main's independent host-side content/hash and changed-path check.

For a shell-free file-tool canary, ask for source-derived fields or exact lines, then one receipt write and readback. Label hashes copied from the manifest as declared, not independently computed. Main compares them with hashes computed from the actual frozen and source bytes. Compare the declared path/bytes/hash fields, not whole dictionaries that may legitimately include extra encoding metadata. Keep attribution explicit; receiver readback and Main hashing are different evidence.

Finish with the capability actually proven. File read/write proves neither shell/test execution nor shared access to Main. A nonce proves delivery only. Classify a preflight failure locally and repair context without crediting a successful implementation attempt or bypassing a denial.

## Recover a display-capped completed output

If the completed patch or verdict is truncated in an announcement/history preview, recover the existing output rather than restart implementation. Read the complete artifact from its proven output mapping when available. Otherwise, only within the receiver's existing permissions, explicitly lease one response artifact and ask it to save the completed result without new fixes; inspect the actual tool result. A new artifact lease does not authorize another source path or a policy workaround. Stop if that write is denied.

Main reads and hashes the complete artifact, parses the expected schema, checks exact target paths and unique patch anchors, and verifies resulting postimages before applying. Never apply a truncated prefix or claim byte identity with an unseen original. If the receiver regenerated the transport copy, state that limitation and validate the recovered content independently. Keep this recovery separate from a new implementation attempt.

## Recover an occupied scoped worktree

Use only when the existing narrow bind is present but carries an old job or lacks the assigned sources.

1. Inspect the current manifest, control record, Git inventory, exact mount source, active write lanes and owning sessions. Retain dirty and untracked files as user work. Finish with old-job identity and evidence that no active writer owns the handoff; a running idle container is not an active task.

2. Obtain exact preservation/reuse authority before moving the old handoff. Resolve both the scoped-worktree directory and sibling `.veritas-scoped-worktree.json`; inventory all files, reject link escapes, require an absent retention destination, and record rollback. Preserve the pair together, then verify every retained file and control-record hash. Do not delete old work or alter mounts to make staging succeed.

3. Stage only the new frozen inputs through `scripts/implementation_builder_worktree_manager.py prepare` with explicit job, source root/base label, `--file` paths and narrowly named `--allow-output` paths; inspect current help before constructing argv. Run its `verify` action and require matching clean baseline, manifest and source hashes. Keep the task's writable subset narrower than the manifest when the preflight only needs a receipt.

4. Use a fresh receiver session for one bounded file-tool canary against exact `/worktree/...` paths. Permit only the named receipt write; leave sources unchanged. Verify the resulting host receipt, source-derived fields, all frozen/live source hashes, and absence of unrelated changes. Preserve the old pair's hash proof separately.

5. Record a fresh agent-matched proof with observed model, manifest binding, live sandbox/tool configuration fingerprint, write/readback evidence, expiry and limitations. Run `scoped_writeback_preflight.py --agent <id> --proof <proof-path>` and require `ok`. Report restored scoped file transport, not untested command execution or implementation completion. Later work still needs its own write lease and drift check.
