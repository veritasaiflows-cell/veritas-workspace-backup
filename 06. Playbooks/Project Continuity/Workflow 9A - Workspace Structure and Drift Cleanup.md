# Workflow 9A - Workspace Structure and Drift Cleanup

## Objective
- Reorganize the workspace and control-plane surfaces so temporary exceptions, stale artifacts, and overloaded playbook folders stop accumulating as silent drift.
- Turn audit residue into explicit cleanup decisions before more feature or workflow expansion.

## Current State
- Completed on 2026-05-02 after the approved Phase 4-7 execution pass.
- The root-level `generated documents/` exception is retired: entry-band HTML now lives under `tmp/entry-band-reports/`, live callers were rewritten, downstream artifacts were regenerated, and the old root folder was removed.
- The stale nested worktree residue under `scripts/.claude/...` is gone: the worktree was deregistered from `git worktree list`, leftover filesystem copies were removed manually after git handled the registry step, and the empty `scripts/.claude/` parent path was cleared.
- The active `06. Playbooks/` root no longer carries the three `.bak-2026-05-02-control-plane-hardening` files; they now live under `migration-backups/2026-05-02-control-plane-hardening-baks/`.
- The non-prefixed predecessor continuity notes `Research Department Operating Model.md` and `Sector Coverage Expansion Plan.md` were backed up, then moved to `09. Archive/Project Continuity/`; the numbered workflow notes remain in place.
- The technical skill boundary is now explicit enough for closure: `veritas-technical-pass` is the canonical Veritas workflow skill, while `technical-chart-pass` is documented as the generic fallback rather than a silent parallel authority.
- The daily-note duplication gap remains honestly closed only at the local-workspace layer: `scripts/daily_note_dedupe.py` stays the verified fail-safe, while the upstream session-memory hook remains unresolved runtime debt outside this workflow.

## Last Meaningful Progress
- Executed the approved Phase 4 cleanup set: removed the registered stale nested worktree under `scripts/.claude/worktrees/wonderful-matsumoto-f7ad44/`, cleared the leftover `.git/worktrees/wonderful-matsumoto-f7ad44` metadata directory after git had already deregistered the worktree, deleted the empty `scripts/.claude/` path, moved the three control-plane `.bak-*` files into `migration-backups/2026-05-02-control-plane-hardening-baks/`, backed up the two predecessor continuity notes into `migration-backups/2026-05-02-workflow-9a-phase4/Project Continuity/`, and archived those predecessor notes into `09. Archive/Project Continuity/`.
- Executed the approved `generated documents/` migration: moved the existing 19 entry-band HTML reports into `tmp/entry-band-reports/`, rewrote the four live code-path callers plus the `entry_band_fetch.py` output/help text, regenerated the HTML report set with `python scripts/entry_band_fetch.py --all-tracked --html` (`18/18` succeeded), regenerated `tmp/entry-band-status.html`, `tmp/dashboard-data.json`, `tmp/dashboard-last.json`, `tmp/veritas-command-center.html`, and `tmp/veritas-command-center.last-good.html`, then removed the empty root `generated documents/` directory.
- Closed the technical-skill ambiguity with the smallest live edit set: `skills/veritas-fundamental-pass/SKILL.md` now points Veritas technical timing work to `veritas-technical-pass`, and `skills/technical-chart-pass/SKILL.md` now states its generic-fallback boundary explicitly.
- Verified the cleaned state: `git worktree list` no longer shows the removed nested worktree, `06. Playbooks/` root now has zero `.bak-*` residue, `python scripts/daily_note_dedupe.py --all` returns `files_changed: 0` / `total_removed: 0`, `tmp/dashboard-validation.json` is `0 critical / 0 warning`, `tmp/dashboard-acceptance-report.json` shows `17/17` passing checks, and the regenerated dashboard / status surfaces now emit `entry-band-reports/...` links instead of the retired root path.

## Phase 1 Inventory Map - Initial Live Pass

| Surface | Live evidence | Initial classification | Owner / next check | Approval |
|---|---|---|---|---|
| `06. Playbooks/` root | `37` root files, `2` active subfolders, and `3` root-level `.bak-2026-05-02-control-plane-hardening` copies | `keep` domain, `reorganize` root | Workflow 9A Phase 2-3 should define the closure end-state as three root tiers: governance/doctrine, operations/orchestration, and component specs | Root structure changes yes; naming/routing doctrine updates no |
| `06. Playbooks/Project Continuity/` | `27` files mixing active workflows, closed workflows, chain logs, and phase packets; initial spot-check already shows some closed notes are still referenced by active files (`Workflow 4` in `Workflow 10`, `Workflow 4C` in `Research Automation`, `Workflow 6` in `Workflow 11` / `Workflow 7`) | `keep` active staging folder, `defer` per-file archive calls until references are checked | Workflow 9A Phase 2 reference check against queue, registry, and active notes | Archive / move decisions yes |
| `06. Playbooks/*.bak-2026-05-02-control-plane-hardening` | `3` backup copies in the active root (`Automation Orchestration Protocol`, `IC Project Registry`, `OpenClaw Parallel Pilot Queue`) | `move` candidate out of active root | Workflow 9A Phase 3 should choose `migration-backups/` or `09. Archive/` as the explicit sink | Yes |
| `generated documents/entry-bands/` | `19` HTML outputs present; live callers found in `scripts/dashboard_payload.py`, `scripts/entry_band_fetch.py`, `scripts/generate_entry_band_status.py`, and `scripts/dashboard-js/14-entry-bands.js` | `keep` temporary exception for now | Workflow 9A Phase 2-3 must commit to one outcome: bounded migration item with target/owner/timeline, or permanent documented exception with maintenance rules | Path move yes |
| `scripts/.claude/worktrees/wonderful-matsumoto-f7ad44/` | `1` nested worktree mirror with copied doctrine, memory, and tool metadata; no live caller references found outside audits / 9A notes | `delete` candidate after dependency check | Workflow 9A Phase 2 should verify no live Claude/runtime dependency before surfacing it as a fast-track stale-artifact deletion | Yes |
| `.claude/worktrees/` | `7` root worktrees plus `.claude/settings.local.json`; referenced in `06. Playbooks/Claude CLI Guardrails.md` as a permission/trust surface | `defer` as adjacent tool-infra residue, not a blind-cleanup target | Separate Claude/runtime check before any deletion or relocation claim | Yes |
| `scripts/__pycache__/` | directory exists locally; `git status --short -- scripts\\__pycache__` returns `?? scripts/__pycache__/`; `.gitignore` now includes `__pycache__/`, so remaining residue is local generated bytecode only | `safe mechanical hygiene` candidate, not a tracked-index cleanup | Phase 2 resolved the rule gap; Phase 3-4 only need the local cache cleanup decision | No separate per-item approval if Phase 2 confirms generated/untracked only |
| `skills/technical-chart-pass/` vs `skills/veritas-technical-pass/` | both skills are live; `technical-chart-pass` is generic and still referenced by `skills/veritas-fundamental-pass/SKILL.md`; `veritas-technical-pass` is referenced by multiple active Veritas skills; `technical-chart-pass/references/` is empty | `keep` both for now, `defer` merge/deprecate decision | Workflow 9A Phase 2 must trace all live callers before any precedence, merge, or archive action | Skill deprecation / archive yes |

### Initial `06. Playbooks/` Root Tier Proposal
- **Governance & doctrine**: `Automation Orchestration Protocol.md`, `Continuity Stewardship Protocol.md`, `Cron Job Protocol.md`, `IC Model Routing Policy.md`, `Notes Layer Governance Protocol.md`, `Operating Model.md`, `Workspace Structure Protocol.md`, plus guardrail notes such as `Claude CLI Guardrails.md` and `Gemini CLI Guardrails.md`.
- **Operations & orchestration**: `Active Model Prompt Queue.md`, `Cron Run Ledger.md`, `IC Project Registry.md`, `OpenClaw Parallel Pilot Queue.md`, `OpenClaw Parallel Work Plan.md`, `Model Prompt Operations.md`, and the active workflow/process surfaces that coordinate real execution.
- **Component specs / contracts**: `Automation Architecture Spec.md`, `Automation Run Summary Contract.md`, `Excel Operating Workbook Structure.md`, `Market Data Coverage Matrix.md`, `Market Data Script Specifications.md`, `Minimum-Viable Workbook Schema.md`, `PDF Brief Standards.md`, `Weekly Intelligence PDF Product Spec.md`, `Workbook Export Contracts.md`, and similar file-format / system-contract notes.
- **Still needs Phase 2 reference check before any move/archive call**: planning or prompt-pack surfaces such as `Market Data Upgrade Plan.md`, `OpenClaw Model Deployment Plan.md`, `Research Unit Concept.md`, `Gemini Flash Prompt Pack.md`, and `GPT5 Research Prompt Pack.md`.

## Phase 2 Findings - Dependency and Caller-Risk Analysis

| Surface | Phase 2 finding | Label | Phase 3 treatment |
|---|---|---|---|
| `generated documents/entry-bands/` | Live path is still hard-coded in `scripts/dashboard_payload.py`, `scripts/entry_band_fetch.py`, `scripts/generate_entry_band_status.py`, and `scripts/dashboard-js/14-entry-bands.js`; downstream generated artifacts in `tmp/dashboard-data.json`, `tmp/dashboard-last.json`, `tmp/entry-band-status.html`, and the Command Center HTML also embed the current relative path | `safe after rewrite` | operator must choose migration plan or permanent exception; recommended migration target is `tmp/entry-band-reports/`, with directory-object rewrites to `WORKSPACE / "tmp" / "entry-band-reports"`, emitted-link replacement `../generated documents/entry-bands/` -> `entry-band-reports/`, target-directory creation before first run, and regeneration of the selected downstream `tmp/` artifacts |
| `scripts/.claude/worktrees/wonderful-matsumoto-f7ad44/` | No live script, config, or automation caller was found outside audits/governance notes; `git status` shows it as untracked local residue; live `git worktree list` also shows it as a prunable registered worktree, and its `.git` file points at `.git/worktrees/wonderful-matsumoto-f7ad44` rather than acting like a normal standalone folder | `safe now` | delete candidate after written operator approval, but only through git-worktree-aware removal (`git worktree list` -> `git worktree remove --force ...` if still registered -> `git worktree prune` -> manual leftover deletion only if residue remains); do not use `git rm` or blind file deletion |
| root `.claude/worktrees/` | Separate tool-infrastructure surface documented by `06. Playbooks/Claude CLI Guardrails.md`; not the same issue as `scripts/.claude/...` | `out of scope` for 9A cleanup execution | leave in place; only revisit under Claude/runtime posture review |
| `scripts/__pycache__/` | `git ls-files` shows no tracked `__pycache__` entries; problem was missing ignore coverage plus untracked generated bytecode; ignore rule is now landed in `.gitignore` | `safe now` | local cache directory is a low-risk cleanup item once delete approval is explicitly granted or bundled as generated-noise cleanup |
| `skills/technical-chart-pass/` vs `skills/veritas-technical-pass/` | No live script/config/automation caller found; live dependency is skill-layer only: `technical-chart-pass` is still referenced by `veritas-fundamental-pass`, while `veritas-technical-pass` is referenced by `veritas-macro-pass`, `veritas-positioning-pass`, `veritas-post-earnings-sync`, `veritas-pdf-brief`, and `veritas-weekly-brief` | `defer` / decision-heavy | treat as boundary-precedence decision, not emergency chain repair |
| `06. Playbooks/*.bak-2026-05-02-control-plane-hardening` | No active non-backup references were found | `safe now` | move candidate; recommended sink = `migration-backups/` rather than active playbook root |
| Closed workflow notes with live refs (`Workflow 4`, `Workflow 4B`, `Workflow 4C`, `Workflow 5`, `Workflow 6`, `Excel Operating Workbook`) | Still referenced by active continuity or governance notes; archive now would create churn or broken context; the full closure archive scope is therefore still triage-driven across the wider `Project Continuity/` set rather than limited to a small example tree | `defer` | keep in `Project Continuity/` until references are intentionally rewritten |
| Legacy predecessor notes (`Research Department Operating Model.md`, `Sector Coverage Expansion Plan.md`) | Unreferenced in active surfaces and superseded by the numbered workflow notes (`Workflow 9 - ...`, `Workflow 7 - ...`); these are the non-prefixed predecessor notes, not the numbered workflow continuity notes themselves | `safe now` | archive candidate after written operator approval; do not conflate them with `Workflow 9 - Research Department Operating Model.md` or `Workflow 7 - Sector Coverage Expansion Plan.md` |
| `Workflow 7 - Sector Coverage Expansion Plan.md` and `Workflow 9 - Research Department Operating Model.md` | Both read as closed with follow-up; current file-path reference count is zero, but each still represents a historical closure artifact tied to numbered workflows | `defer` | operator should decide whether closed numbered workflow notes stay in active continuity for historical readability or move to archive later |

## Phase 3 Decision Packet - Draft

### Already landed without approval gate
- Added `__pycache__/` to `.gitignore` because it is non-destructive repo-hygiene hardening, not a delete/move/archive action.

### Fast-track low-risk items once operator confirms the delete/move bucket
- Remove the stale nested worktree under `scripts/.claude/worktrees/wonderful-matsumoto-f7ad44/` with git-worktree-safe mechanics: check `git worktree list`, use `git worktree remove --force scripts/.claude/worktrees/wonderful-matsumoto-f7ad44` if it is still registered, run `git worktree prune`, and only then manually delete the directory if residue remains.
- Delete local generated bytecode under `scripts/__pycache__/` now that ignore coverage exists.
- Move the three root-level `.bak-2026-05-02-control-plane-hardening` files out of active `06. Playbooks/`; recommended sink is `migration-backups/` because these are reversible local backups, not active doctrine.
- Archive superseded predecessor notes `Research Department Operating Model.md` and `Sector Coverage Expansion Plan.md` under `09. Archive/Project Continuity/` or a similarly explicit archive sink; these are illustrative immediate archive candidates, not the full future closure archive list.

### Decision-heavy structural items that should not be auto-cleaned
- `generated documents/` must end this workflow in one of two states only:
  - **recommended:** bounded migration to a `tmp/`-owned target such as `tmp/entry-band-reports/`, with explicit rewrites to the four live source callers, target-directory creation before first output, and regeneration of the downstream dashboard artifacts; or
  - explicit permanent root exception with owned maintenance rules if Randall decides the churn is not worth it now.
- `technical-chart-pass` versus `veritas-technical-pass` should be resolved as a boundary decision, not a bulk skill rewrite. Current recommendation remains: keep `veritas-technical-pass` as canonical Veritas workflow skill; either narrow `technical-chart-pass` into an explicit generic fallback or archive it if no separate non-Veritas use remains.
- `06. Playbooks/Project Continuity/` still needs a human decision on how aggressively to archive closed numbered workflow notes once reference rewrites are intentional rather than opportunistic.

### Recommended implementation checklist if the `generated documents/` migration is approved
- Create `tmp/entry-band-reports/` before the first migrated output lands, or ensure the emitting scripts create it with an equivalent `mkdir(parents=True, exist_ok=True)` step.
- Update directory-object constants to `WORKSPACE / "tmp" / "entry-band-reports"` in `scripts/dashboard_payload.py`, `scripts/entry_band_fetch.py`, and `scripts/generate_entry_band_status.py`.
- Replace the emitted relative string `../generated documents/entry-bands/` with `entry-band-reports/` in `scripts/dashboard_payload.py`, `scripts/generate_entry_band_status.py`, and `scripts/dashboard-js/14-entry-bands.js`.
- Update the human-facing example path in `scripts/entry_band_fetch.py` so the help text no longer points at the retired root exception.
- Regenerate the selected migration-relevant downstream artifacts: `tmp/dashboard-data.json`, `tmp/dashboard-last.json`, `tmp/entry-band-status.html`, `tmp/veritas-command-center.html`, `tmp/veritas-command-center.last-good.html`, plus the HTML report set under `tmp/entry-band-reports/`.
- Leave historical references in `08. Audits/`, `memory/`, and `migration-backups/` unchanged; they are intentional records of the old state, not rewrite targets.
- Treat any abbreviated tree shown in planning notes as illustrative only: the real `tmp/` tree is much larger, and the migration checklist covers only the selected files that matter to this path move.

### Archive-scope clarification for Phase 3
- The small archive example is not the full `09. Archive/Project Continuity/` target set.
- Full archive scope still depends on the wider `06. Playbooks/Project Continuity/` triage across the current 27-file set.
- Immediate safe-now archive candidates are the non-prefixed predecessor notes only; the numbered workflow continuity notes stay governed by the later reference-rewrite and closure decisions.

## Phase 4-6 Execution Results
- `scripts/.claude/worktrees/wonderful-matsumoto-f7ad44/` is fully removed from the workspace. `git worktree remove --force` cleared the registration from `git worktree list`, but Windows permissions blocked git from deleting the internal metadata directory cleanly, so the leftover `.git/worktrees/wonderful-matsumoto-f7ad44` folder and the local filesystem copy were removed manually afterward. That finished the approved nested stale-worktree cleanup without touching the separate root `.claude/` runtime surface.
- `scripts/__pycache__/` was deleted as approved generated noise. Python recreated it during the regeneration pass, which confirmed the earlier diagnosis: the durable fix was the `.gitignore` hardening, not a fake claim that bytecode folders would stay gone forever. The directory was removed again after verification so the visible workspace ended clean.
- The `generated documents/` exception is closed. The live code path now targets `tmp/entry-band-reports/`, and the regenerated dashboard/status artifacts prove the relative-link rewrite landed.
- `06. Playbooks/` closure end-state is now explicit enough for this workflow: active root keeps governance/doctrine, operations/orchestration, and component specs/contracts; active live project notes stay in `06. Playbooks/Project Continuity/`; predecessor continuity notes that are truly superseded move to `09. Archive/Project Continuity/`; reversible local safety copies live in `migration-backups/`.
- Historical references in `08. Audits/`, `memory/`, and `migration-backups/` were intentionally left untouched so the old path survives only as historical evidence, not as a live dependency.

## Explicit Out-of-Scope Residue Owners
- `execution.chain_status = "running"` after clean finance-window completion is not a structure problem; it is explicitly owned by `Workflow 10 - Subagent Session Lifecycle Reliability Review.md`.
- `GS` in-band / `WATCH` state mismatch is not a structure problem; it is explicitly owned by `Workflow 9B - Surface Alignment and Drift Guard Hardening.md`.
- Root `.claude/` worktree and git-metadata residue outside `scripts/.claude/...` remains a runtime/tooling concern, not a workspace-structure target here. The `git worktree prune` permission-denied cleanup on alternate-user root worktree metadata is handed to `Workflow 10 - Subagent Session Lifecycle Reliability Review.md` rather than being silently absorbed back into 9A.

## Outstanding
- None inside Workflow 9A.
- Remaining residue is intentionally handed off rather than kept vague:
  - surface-contract / validator drift such as `GS` state mismatch -> `Workflow 9B - Surface Alignment and Drift Guard Hardening.md`
  - runtime/session-lifecycle and worktree-metadata residue such as stale `execution.chain_status` and root `.claude/` worktree prune failures -> `Workflow 10 - Subagent Session Lifecycle Reliability Review.md`
  - any future duplicate daily-note recurrence from the upstream session-memory hook -> runtime debt, not a reopened claim that the local workspace fix failed

## Phased Completion Plan

### Phase 1 - Inventory and classification map
- Inventory `06. Playbooks/` by role: active governance, active control surface, active project continuity, historical planning, and likely archive candidates.
- Inventory stale artifact and repo-noise surfaces: `scripts/.claude/...`, `scripts/__pycache__/`, and any other scratch/worktree residue found during the pass.
- Inventory root/path exceptions, especially `generated documents/`, and identify whether each item is still a real operating dependency or just tolerated drift.
- Inventory overlapping skill-boundary candidates, especially `technical-chart-pass` versus `veritas-technical-pass`.
- Inventory adjacent root tool-infra residue discovered during the pass, especially whether `.claude/` is an active documented surface or extra drift that needs a separate runtime review.
- Classify each item as `keep`, `move`, `archive`, `delete`, or `defer`, with owner, risk, and approval requirement captured explicitly.

### Phase 2 - Dependency and caller-risk analysis
- Trace live script, doc, dashboard, and note references to `generated documents/` and separate real callers from stale references.
- Verify whether any live workflow reads from `scripts/.claude/...` or whether it is purely stale worktree residue, and confirm whether the path is still present in git worktree metadata before any deletion plan is proposed.
- Confirm the exact scope of `scripts/__pycache__/` cleanup, including whether the real fix is ignore-rule hardening, local cache deletion, or both.
- Identify every live caller of `technical-chart-pass` and `veritas-technical-pass` across skills, scripts, queue/continuity docs, and any automation definitions before deciding merge, deprecation, or explicit precedence.
- Verify that any archive candidate in `06. Playbooks/Project Continuity/` is truly closed and no longer referenced by the queue, registry, or an active chain.
- Split candidates into `fast-track mechanical` and `decision-heavy structural` buckets so the same approval overhead is not applied to obviously generated residue and live path architecture.
- Label each change candidate `safe now`, `safe after rewrite`, `defer`, or `out of scope`.

### Phase 3 - Operator decision packet
- Group approval-sensitive actions into `delete`, `archive`, `move`, and `keep as temporary exception` buckets.
- For each item, record why it exists, the risk of leaving it alone, the risk of changing it, reversibility, and the recommended action.
- Turn ambiguous items into an explicit defer or follow-up instead of forcing closure.
- Make the approval gate explicit: Phase 4 stays blocked by default for every delete, archive, and move action until Randall confirms each irreversible item in writing.
- Commit a hard outcome for `generated documents/`: either a bounded migration item with target / owner / queue home, or a permanent documented exception with maintenance rules.
- Define the `06. Playbooks/` closure end-state before Phase 4 begins: what remains in root, what remains in `Project Continuity/`, and what moves to `09. Archive/` or `migration-backups/`.
- Present the smallest clean approval packet needed to execute the structural cleanup honestly.

### Phase 4 - Execute approved cleanup
- Back up targeted human-authored files before any approved move or archive action.
- Execute approved archive moves for continuity/control-plane notes.
- Execute approved stale-artifact deletions and the proven-mechanical repo-noise cleanup for `scripts/__pycache__/`.
- If `scripts/.claude/worktrees/wonderful-matsumoto-f7ad44/` is approved for removal, use git worktree mechanics first: check `git worktree list`, remove it with `git worktree remove --force ...` if still registered, run `git worktree prune`, and manually delete leftover files only if residue remains afterward.
- Keep `generated documents/` in place unless Phase 3 explicitly chose migration and the caller rewrite path is approved and proven safe.
- If the migration to `tmp/entry-band-reports/` is approved, create the target directory first or prove the scripts now create it, update the three workspace-path constants plus the three emitted-link strings, regenerate the selected downstream `tmp/` artifacts, and only then retire the old directory after verification.
- If the technical-skill overlap is approved for action here, keep the fix narrow and boundary-focused rather than redesigning the whole skill layer.
- Do not treat any delete, archive, or move action as implicitly approved just because the decision packet exists.

### Phase 5 - Structure normalization and rule tightening
- Update `06. Playbooks/Workspace Structure Protocol.md` and only the smallest set of other governing files needed to reflect the cleaned state.
- Tighten `06. Playbooks/` routing rules so the closure end-state is explicit: root = governance/doctrine + operations/orchestration + component specs, `Project Continuity/` = active workstream staging, archive sinks = `09. Archive/` or `migration-backups/` only where justified.
- Resolve or explicitly document the technical skill boundary so the overlap does not remain as silent ambiguity.
- Keep the daily-note dedupe guard visible as a local hygiene rule, not a fake claim that the upstream session-memory hook is repaired.

### Phase 6 - Verification pass
- Re-scan `06. Playbooks/` and confirm the active-versus-archive split is coherent after cleanup.
- Re-scan for stale worktree residue and repo noise to confirm approved cleanup actually landed.
- Re-run `python scripts/daily_note_dedupe.py --all` in dry-run mode to confirm duplicate daily-note residue is still zero.
- Check queue / registry / Workflow 9A note alignment and confirm no active file still points to moved or archived paths incorrectly.
- Record what was fixed, what remains open intentionally, and what was deferred to later workflows.

### Phase 7 - Closure and handoff
- Update the Workflow 9A continuity note, queue, and registry with the real completed actions and the remaining owned residue.
- Write only a thin daily-note delta if a material control-plane state change occurred.
- Hand off surface-contract and validator residue to the already-open Workflow 9B, and runtime/session-lifecycle residue to Workflow 10, without letting 9A absorb them.
- Name the specific out-of-scope handoffs in the closure note at minimum: `GS` state drift -> Workflow 9B, `execution.chain_status` stale-completion signal -> Workflow 10.
- Close 9A only when the reorganization contract is explicit, approved cleanup has been handled honestly, the `generated documents/` outcome is no longer vague, and remaining drift has a named owner or next workflow.

## Blockers / Trust Gaps
- The hidden OpenClaw session-memory hook is not patched from inside this workspace, so the current fix is a local fail-safe and cleanup guard, not a claim that the upstream writer is repaired.
- Root `.claude/` runtime worktree metadata is still not boring, but that sits outside this workflow's approved structural scope and is now explicitly handed to Workflow 10.

## Next Action
- Workflow 9A is complete. Promote `Workflow 9B - Surface Alignment and Drift Guard Hardening` as the active next queue item, with `Workflow 10` retaining the runtime/session-lifecycle handoff items named above.

## Key Files
- `08. Audits/Workspace Optimization and Scale Readiness Audit - 2026-05-02.md` - primary audit evidence.
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` - queue owner for the reprioritized sequence.
- `06. Playbooks/IC Project Registry.md` - live control surface that must reflect the new order.
- `06. Playbooks/Workspace Structure Protocol.md` - governing structure policy.
- `Continuity Protocol.md` - newly tightened daily-note contract.
- `skills/memory-continuity-manager/SKILL.md` - continuity routing / dedupe discipline.
- `scripts/daily_note_dedupe.py` - bounded local exact-duplicate cleanup guard for canonical daily notes.
- `tmp/daily-note-dedupe.json` - proof/report output from the 9A daily-note cleanup pass.
- `06. Playbooks/Project Continuity/` - continuity cluster under review.
- `scripts/.claude/` - stale worktree artifact called out in audit.
- `.gitignore` - repo hygiene boundary for cache files.

## Automation / Refresh Path
- Keep this in the main session first.
- Use read-only helper lanes only for inventories or comparison passes.
- Daily-note enforcement is now in bounded-local-fix status: use `scripts/daily_note_dedupe.py` as the fail-safe and avoid broad memory-system redesign unless recurrence proves the local guard inadequate.
- Treat deletes and moves as operator-confirmed actions unless they are already clearly approved and reversible; keep repo-noise hygiene separate from bigger structural actions.
