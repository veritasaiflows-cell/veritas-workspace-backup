# Workflow 10 - Subagent Session Lifecycle Reliability Review

## Objective
- Document and harden around the real gap between reported session/subagent state and verified artifact-level completion.
- Prevent orchestration policy from assuming runtime truth that the control surface has not yet earned.

## Current State
- Workflow 10 is now **honestly closed** after protocol hardening, run-summary execution-state repair, stale root worktree metadata cleanup, and a closing QA audit.
- Scope stayed intentionally bounded: this was not a broad runtime redesign. It was the trust-hardening pass for when session/runtime signals disagree with artifact-level completion or cleanup reality.
- Real failures and ambiguities were captured explicitly across subagent/session behavior, async exec events, worktree cleanup, run summaries, and memory/runtime reporting.
- The remaining runtime residue is named rather than hidden: memory embedding credentials/index health remain broken, and runtime/session state still does not outrank artifact-level proof.

## Last Meaningful Progress
- The queue explicitly added Workflow 10 after real control-surface reliability concerns were observed.
- The day-job orchestrator protocol now treats runtime/session state as advisory when artifact-level proof is stronger.
- `openclaw status` and `openclaw memory status --deep --json` were rechecked live on 2026-05-03: gateway/session runtime is up, but memory embeddings still fail credential probe and the memory index remains non-boring (`0 files / 0 chunks`, dirty, no usable credential-backed probe success).
- `scripts/run_summary_refresh.py` now normalizes the finalizer self-observation race instead of leaving consumer-facing `execution.chain_status="running"` after otherwise successful runs, while preserving the raw runtime field for audit.
- The helper audit then caught a second real Workflow 10 gap: scheduled-window run summaries were still flipping `presentation_allowed` and `canonical_note_mutation_allowed` true on clean runs even though the written v1 contract stayed fail-closed. That mismatch is now fixed in the script layer and regenerated summaries again show both fields as `false`.
- `git worktree prune --dry-run -v` surfaced four stale root metadata directories (`goofy-burnell-4fe3eb`, `happy-tu-045966`, `modest-bell-f26bd5`, `silly-roentgen-69acb1`) that were not active worktrees but failed deletion because the directories were read-only; those stale directories were then cleared and prune no longer reports them.

## Named incidents already on record

### Incident 1 - 2026-05-02 multi-lane completion race
- Context: an IC comparison pass expected more than one lane outcome, but one lane finished asynchronously after another lane had already returned.
- What happened: lane completion timing and session/runtime visibility were not reliable enough to treat the first visible completion as the whole job being done.
- Observable consequence: without an explicit handshake, the main session could have published synthesis early or left late-arriving lane output unintegrated.
- Resulting hardening already landed: `06. Playbooks/Automation Orchestration Protocol.md` now has an explicit **IC completion handshake rule** requiring expected-lane tracking and combined closeout only after all expected lanes resolve or are intentionally abandoned.

### Incident 2 - 2026-05-01 memory-index/runtime failure
- Context: continuity recall looked degraded enough that it could be mistaken for memory loss.
- What happened: `openclaw memory status --deep --json` resolved to a Bedrock embedding path without valid credentials, and `openclaw memory index --force` failed on Windows with `EBUSY` against orphaned `main.sqlite.tmp-*` files.
- Observable consequence: indexed recall could not be treated as trustworthy runtime support, so file-grounded continuity had to remain the operating truth.
- Resulting hardening already landed: the workspace now treats memory search as helpful when healthy, but not as a substitute for continuity files or artifact verification.

### Incident 3 - 2026-05-02 async exec SIGKILL termination
- Context: previously launched helper commands later reported completion through `exec-event` rather than an interactive session checkpoint.
- What happened: two earlier async commands (`clear-sa` and `swift-cr`) were reported as failed with `signal SIGKILL`; one surfaced a truncated stderr path into `flows\registry.sqlite` / sequential-chain text instead of a clean bounded result.
- Observable consequence: command labels can appear to finish only after the fact and can terminate without a trustworthy success/failure artifact, which reinforces that runtime completion events alone are not enough evidence for closeout.
- Resulting hardening implication: Workflow 10 should explicitly cover async exec-event failure handling and the need to reconcile labeled helper commands against artifact-level proof before treating a background pass as resolved.

### Incident 4 - 2026-05-02 async interactive auth prompt leakage
- Context: previously launched helper commands later completed through `exec-event` with terminal-control output instead of a normal artifact or clean log summary.
- What happened: async command `mellow-c` exited `0` but surfaced a GitHub device-auth prompt transcript fragment (`Authenticate Git...`, one-time code prompt, `Press Enter to open...`) in the delayed completion event. A later async command `glow-she` then failed with `SIGKILL` while still emitting the same GitHub auth prompt / terminal-control sequence.
- Observable consequence: async commands can report either nominal success or hard failure while still actually being stuck at an unresolved interactive auth boundary, and the delayed events can leak terminal UI fragments that are not valid completion proof.
- Resulting hardening implication: treat async interactive-auth completions as unresolved until the underlying task is reconciled explicitly; do not count either exit code or delayed failure alone as proof when the payload shows a pending external login step.

### Incident 5 - 2026-05-02 worktree-prune permission residue after approved cleanup
- Context: Workflow 9A removed the stale nested worktree `scripts/.claude/worktrees/wonderful-matsumoto-f7ad44/` with the correct git-worktree-first mechanics.
- What happened: `git worktree remove --force` deregistered the nested stale worktree successfully, but Windows permission issues prevented git from fully deleting the corresponding `.git/worktrees/wonderful-matsumoto-f7ad44` metadata directory. A later `git worktree prune` also still reported permission-denied deletes on other root worktree metadata paths outside the approved 9A cleanup scope.
- Observable consequence: git/runtime cleanup can report a structurally successful removal while still leaving behind undeleted metadata that an organization workflow should not guess at or silently erase when the residue sits in root runtime/tooling surfaces.
- Resulting hardening implication: Workflow 10 should define what counts as a trustworthy worktree/session cleanup signal, how to separate safe local residue from active runtime state, and when manual filesystem cleanup is acceptable versus when the runtime/control surface needs a deeper fix.

### Incident 6 - 2026-05-03 stale root worktree metadata was removable only after manual attribute clearing
- Context: Workflow 10 rechecked root `.git/worktrees/` cleanup live with `git worktree prune --dry-run -v`.
- What happened: git identified four stale metadata directories whose `gitdir` targets no longer existed, but the actual prune operation still failed because the stale directories were read-only on disk. After confirming the names were not in `git worktree list`, those four stale directories were cleared manually and prune stopped flagging them.
- Observable consequence: successful cleanup sometimes depends on a two-step proof standard: verify the worktree is no longer active in git, then clear the filesystem residue explicitly if the runtime tool cannot remove it.
- Resulting hardening implication: a prune failure is not automatically a live-worktree risk, but it also is not safe to ignore. Workflow 10 should codify the verify-then-clear rule instead of leaving it as operator folklore.

## Outstanding
- Commit the Workflow 10 change set after queue/registry/continuity sync is included.
- Decide later whether the memory indexing / embedding-credential problem deserves its own follow-on runtime workflow.

## Blockers / Trust Gaps
- Runtime/session state is still not fully boring or proven.
- Memory indexing remains broken, which weakens auxiliary continuity surfaces.
- Async interactive-auth boundaries and delayed exec-event completions still require explicit reconciliation rather than trust by exit code alone.
- Root worktree residue is cleaner than before, but Windows/runtime cleanup trust still depends on verifying what is active versus what is merely leftover metadata.

## Next Action
- Workflow 11 is the active next pass.

## Key Files
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/Cron Run Ledger.md`
- `06. Playbooks/Project Continuity/Workflow 4 - Sequential Chain Protocol.md`
- `06. Playbooks/Continuity Stewardship Protocol.md`
- `memory/2026-05-01.md`
- `memory/2026-05-02.md`

## Automation / Refresh Path
- Do not let orchestration rely on session-state claims alone until this review closes the trust gap.
- Prefer artifact-level verification and bounded worker posture in the meantime.
