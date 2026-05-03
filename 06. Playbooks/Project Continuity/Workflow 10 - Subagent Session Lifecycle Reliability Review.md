# Workflow 10 - Subagent Session Lifecycle Reliability Review

## Objective
- Document and harden around the real gap between reported session/subagent state and verified artifact-level completion.
- Prevent orchestration policy from assuming runtime truth that the control surface has not yet earned.

## Current State
- Not started as an implementation workflow.
- This now sits behind Workflow 9A and Workflow 9B in the reprioritized queue.
- Scope is widened slightly: this is no longer just about session-state disagreement, but also about stale completion-state signals and state-independent run-ledger trust.
- Real failures and ambiguities have already been observed in subagent/session behavior and memory/runtime reporting.

## Last Meaningful Progress
- The queue explicitly added Workflow 10 after real control-surface reliability concerns were observed.
- The day-job orchestrator protocol now treats runtime/session state as advisory when artifact-level proof is stronger.
- Memory-index/runtime issues remain open and reinforce the need for this review.

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

## Outstanding
- Expand the named incidents into a fuller pattern inventory instead of leaving them as one-off anecdotes.
- Include stale completion-state problems like `execution.chain_status = "running"` after successful finance-window runs in that pattern inventory.
- Define safe operator workarounds and no-go assumptions.
- Decide whether a dedicated bug/hardening note or external issue should remain active.
- Define what orchestration can trust versus what must be verified through files or outputs.

## Blockers / Trust Gaps
- Runtime/session state is still not fully boring or proven.
- Run-summary and run-ledger completion signals are not fully boring or proven either.
- Memory indexing remains broken, which weakens auxiliary continuity surfaces.
- Higher-priority organization / drift-hardening items now remain ahead of this standing review in the ordered queue unless a fresh runtime failure overtakes them.

## Next Action
- Revisit this workflow when the queue reaches it naturally after Workflows 9A and 9B, or sooner if a fresh runtime/session failure proves it must be pulled forward.

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
