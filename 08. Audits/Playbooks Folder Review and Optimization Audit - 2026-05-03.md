# Playbooks Folder Review and Optimization Audit - 2026-05-03

## Resolution status after hardening pass
- P1 stale WF16A / WF16B blocker wording -> fixed on 2026-05-03
- P2 stale Workflow 10-open cron wording -> fixed on 2026-05-03
- P2 split continuity archive destination guidance -> fixed on 2026-05-03
- P3 retrieval / density recommendations -> intentionally deferred; not a pre-WF16 blocker

## Scope audited
- `06. Playbooks/` root
- `06. Playbooks/Project Continuity/`
- `06. Playbooks/Workbooks/`
- `Home.md` playbook navigation references
- workspace skill validation state

## Snapshot
- Root playbook files: 48
- Project continuity files: 30
- Workbook files: 1
- Total files under `06. Playbooks/`: 79
- Largest active operator surface: `06. Playbooks/OpenClaw Parallel Pilot Queue.md` at 643 lines
- Validation run: `openclaw skills check` returned 72 total skills, 27 eligible, 3 disabled, 42 allowlist-blocked, 0 missing requirements
- Git state at audit time: dirty worktree already contained modified and untracked Workflow 17 / Workflow 18 governance files; this audit did not alter those files

## Findings

### P1 - Workflow 16A / 16B still carry stale Workflow 17 / Workflow 18 blockers
Evidence:
- `06. Playbooks/Project Continuity/Workflow 16A - Research Intake Desk and Parallel Review Packets.md:9` still says the workflow is held behind Workflow 17 / Workflow 18 protocol hardening.
- `06. Playbooks/Project Continuity/Workflow 16A - Research Intake Desk and Parallel Review Packets.md:136` still says to wait for Workflow 17 / Workflow 18 closure.
- `06. Playbooks/Project Continuity/Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers.md:9` still says the workflow is held behind Workflow 17 / Workflow 18 protocol hardening.
- `06. Playbooks/Project Continuity/Workflow 16B - Canonical Freshness Sync and Gated Note Update Helpers.md:145` still says to wait for Workflow 17 / Workflow 18 closure and Workflow 16A completion.
- In contrast, `06. Playbooks/Project Continuity/Workflow 16 - Research Automation and Canonical Freshness Hardening.md:11` says Workflow 17 and Workflow 18 are closed.
- `06. Playbooks/IC Project Registry.md:34` also says Workflow 16 is active and ready for the readiness-gate pass.
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md:794-796` lists Workflow 16 active, 16A queued under 16, and 16B queued behind 16A.

Risk:
- The next operator pass can be misrouted into waiting on already-closed prerequisites.
- This is a live sequencing contradiction, not cosmetic wording.

Recommendation:
- Update 16A to say it is queued behind Workflow 16 readiness gate, not blocked by Workflow 17 / 18.
- Update 16B to say it is queued behind 16A contract completion, not blocked by Workflow 17 / 18.

### P2 - `Cron Job Protocol.md` still says Workflow 10 is open
Evidence:
- `06. Playbooks/Cron Job Protocol.md:103` says Workflow 10 is still open.
- `06. Playbooks/Project Continuity/Workflow 10 - Subagent Session Lifecycle Reliability Review.md:8` says Workflow 10 is honestly closed.
- `06. Playbooks/Automation Orchestration Protocol.md:200-212` now carries the correct durable rule: runtime/session state remains advisory beneath artifact-level proof.

Risk:
- Cron and stewardship guidance may overstate a completed workflow as an active blocker.
- The correct residual risk is runtime/session advisory posture and memory-index/credential residue, not "Workflow 10 is open."

Recommendation:
- Replace the stale Workflow 10-open wording with a current residual-risk statement.

### P2 - Archive destination policy is split between old and current archive paths
Evidence:
- `06. Playbooks/Continuity Stewardship Protocol.md:217` prefers `09. Archive\06. Project Continuity - Archived\`.
- `06. Playbooks/Automation Architecture Spec.md:197` also points to `09. Archive/06. Project Continuity - Archived/`.
- Recent actual workflow cleanup used `09. Archive/Project Continuity/`, including `Workflow 9A` lines 12 and 17 and `Workflow 9B` line 20.
- Both archive directories currently exist under `09. Archive/`.

Risk:
- Future archive passes can split continuity history across two active sinks.
- Operators must remember unstated path history instead of following one canonical rule.

Recommendation:
- Choose `09. Archive/Project Continuity/` as the current canonical sink for new continuity archive moves.
- Treat `09. Archive/06. Project Continuity - Archived/` as legacy historical archive unless explicitly migrated later.
- Update the two stale protocol references before the next archive pass.

### P3 - `06. Playbooks/` is still too dense for fast operator retrieval
Evidence:
- `06. Playbooks/` root has 48 files.
- `06. Playbooks/Project Continuity/` has 30 files.
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` is 643 lines and begins detailed completed-workflow history at line 61 while active execution order appears much later at line 767.
- `06. Playbooks/Workspace Structure Protocol.md:47-65` says the playbook root should hold durable control documents with obvious note types.
- `06. Playbooks/Workspace Structure Protocol.md:67-72` allows subfolders only when ownership is clear.

Risk:
- The right documents exist, but retrieval cost is rising.
- The queue doubles as active queue, historical ledger, and workflow encyclopedia.

Recommendation:
- Do not broad-reorganize immediately.
- First create or update one playbook index / map that groups root documents by role.
- Then compact the queue so the active operator section is top-heavy and historical detail moves to a linked history/retired-detail surface.

### P3 - Home navigation does not surface the new canonical workflow standards
Evidence:
- `Home.md:88-94` lists the playbook navigation set but does not include:
  - `Major Workflow Contract Standard.md`
  - `Spawn and Closeout Governance Matrix.md`
  - `Workflow Closeout Artifact Standard.md`
  - `Skill Quality Standard.md`
  - `Skills Governance Index.md`
- `06. Playbooks/IC Project Registry.md:32` says those new standards are now live baseline outputs from Workflow 17 / 18.

Risk:
- The standards are cross-linked inside playbook files, but they are not visible from the main navigation path.
- This makes future startup/review behavior depend on already knowing the new standard names.

Recommendation:
- Add a compact "Workflow / Governance Standards" group under the Home playbook navigation or create a single `Playbooks Index.md` linked from Home.

### P3 - Redundancy cleanup plan is now eligible for a bounded execution pass, but should not interrupt Workflow 16 readiness
Evidence:
- `06. Playbooks/Playbooks Redundancy Cleanup Plan.md:37-40` already names the parallel/IC orchestration files that need review or archive/merge consideration.
- `06. Playbooks/Playbooks Redundancy Cleanup Plan.md:107-112` says execution can reopen when Workflow 9B through Workflow 12 are closed, references are stable, the move list is explicit, and validation/link checks are part of the pass.
- Workflow 9B through Workflow 12 are closed in the live queue and registry.

Risk:
- The cleanup plan is no longer blocked by the original 9B-12 gate, but executing it during Workflow 16 readiness could distract from the active automation sequence.

Recommendation:
- Run only a non-destructive classification pass now if needed.
- Defer actual merge/archive/move execution until after Workflow 16 readiness gate or after an explicit operator decision.

## Optimization plan

### Phase 1 - Truth-fix pass
Goal:
- remove live contradictions before the next Workflow 16 handoff.

Actions:
- Patch 16A current phase and next action to reference Workflow 16 readiness gate instead of Workflow 17 / 18 closure.
- Patch 16B current phase and next action to reference 16A contract completion only.
- Patch `Cron Job Protocol.md` current-risk wording for Workflow 10 closure reality.
- Patch archive destination references in `Continuity Stewardship Protocol.md` and `Automation Architecture Spec.md`.

Acceptance:
- `rg` no longer finds stale "wait for Workflow 17 / Workflow 18 closure" language in 16A/16B.
- `rg` no longer finds "Workflow 10 is still open" in live cron protocol.
- new archive guidance points to one current path.

### Phase 2 - Playbook retrieval map
Goal:
- improve operator retrieval without moving files.

Actions:
- Create or update a single `06. Playbooks/Playbooks Index.md`.
- Group files into:
  - current control surfaces
  - workflow standards
  - automation / cron contracts
  - research / freshness contracts
  - workbook / packaging specs
  - model / IC operations
  - historical or review-needed specs
  - project continuity notes
- Link this index from `Home.md`.

Acceptance:
- Randall can find the correct playbook surface without scanning 48 root files.
- No file moves are required in this phase.

### Phase 3 - Queue compaction
Goal:
- make `OpenClaw Parallel Pilot Queue.md` an active operator surface again instead of a long history document.

Actions:
- Keep current resource posture, active workflow queue, execution order, capacity rules, and current next actions in the main queue.
- Move detailed completed Workflow 1-14 histories into a linked history surface or archive note after reference check.
- Keep one compact completion line per completed workflow in the active queue.

Acceptance:
- active queue opens directly to current state.
- detailed history remains preserved but no longer dominates the operator surface.

### Phase 4 - Project continuity archive decision pass
Goal:
- reduce `Project Continuity/` density without breaking live references.

Actions:
- Reference-check each closed workflow note against Home, queue, registry, active continuity notes, protocols, and skills.
- Classify each file as keep active, keep intentionally-held, archive, or rewrite references then archive.
- Use `09. Archive/Project Continuity/` for new archive moves.

Acceptance:
- no moved file has an active unresolved reference unless the reference is intentionally updated in the same pass.
- `Project Continuity/` contains active, queued, or intentionally-held workflow notes only.

### Phase 5 - Redundancy cluster cleanup
Goal:
- execute the existing redundancy cleanup plan only after the active queue can tolerate it.

Actions:
- Review the parallel / IC orchestration cluster first:
  - `Parallel IC Project Workflow.md`
  - `OpenClaw Parallel Work Plan.md`
  - `OpenClaw Model Deployment Plan.md`
- Decide keep / merge / archive with before-after map.
- Repeat later for workbook / packaging and prompt / model-ops clusters.

Acceptance:
- no semantic owner boundary is merged away.
- active standards remain discoverable.
- link checks pass after any move.

## Deferred
- No destructive archive/move/delete action in this audit pass.
- No deprecation of `technical-chart-pass`; the Skills Governance Index has the correct current posture: generic fallback versus `veritas-technical-pass` as canonical Veritas technical skill.
- No workbook or packaging spec merge yet.
- No new research automation cron or note-helper execution before Workflow 16 readiness gate and 16A / 16B contracts.
