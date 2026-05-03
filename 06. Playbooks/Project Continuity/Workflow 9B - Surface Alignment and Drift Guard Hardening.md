# Workflow 9B - Surface Alignment and Drift Guard Hardening

## Objective
- Make dashboards, validators, note-owned mirrors, and bounded `06. Playbooks/` cleanup reflect one coherent lane / ownership contract before more scaling or automation.
- Convert repeated drift warnings into enforced rules or explicit owner-bound manual exceptions.
- Close the approved archive / routing residue without turning this workflow into a broad content rewrite or doctrine-merging exercise.

## Current State
- Workflow 9A is honestly closed and its closure baseline is committed clean before 9B (`f4b196a` for the 9A closure set, `abf05af` for the follow-up memory note).
- Workflow 9B is now **honestly closed** after Phase 3 execution, Phase 4 hardening, Phase 5 verification, and a closing QA audit.
- The highest-risk mirror contradictions were addressed: GS stale watch wording is cleared, Coverage Universe quick-reference phrasing was updated for the main post-earnings drift set, and the first safe archive pass ran with backup first.
- Phase 4 bounded hardening deliverables now exist: Post-Catalyst Truth Sync protocol, expanded note-surface validator checks, a written dry-run-first technical write-back helper spec, and a `migration-backups/` retention policy.
- Consolidation / shedding is reduced to an explicit cleanup plan and deferred execution gate rather than an unnamed residue bucket.

## Last Meaningful Progress
- Workflow 6 hardened the lane / tier framework and downstream validator behavior.
- Workflow 8 kept Command Center downstream and non-authoritative while proving a cleaner source-truth contract.
- Workflow 9A removed the root structure drift that was blocking honest surface hardening and explicitly handed the remaining contract residue here.
- The 9B helper-lane inventory confirmed GS was a carried mismatch, not an intentional hold, and identified the real high-risk drift set (`GS`, `NVDA` quick-reference tier wording, stale post-earnings phrases, archive-safety references).
- Phase 3 execution completed the GS/mirror sync and archived five safe unreferenced phase artifacts from `06. Playbooks/Project Continuity/` into `09. Archive/Project Continuity/` with backup first under `migration-backups/2026-05-03-wf9b-packet-c/`.
- Phase 4 execution landed `06. Playbooks/Post-Catalyst Truth Sync Protocol.md`, `06. Playbooks/Technical Write-Back Helper Spec.md`, retention-policy updates in `06. Playbooks/Workspace Structure Protocol.md`, and live validator expansion in `scripts/dashboard_validation.py`.
- Phase 5 verification now passes again: `validate_dashboard_state.py --write` at `0 critical / 0 warning`, `test_dashboard_acceptance.py` at `17/17`, and `daily_note_dedupe.py --all` dry run back to `0 changed` after removing fresh duplicate bullets from `memory/2026-05-02.md`.
- Phase 6 now has an explicit redundancy/control cleanup plan in `06. Playbooks/Playbooks Redundancy Cleanup Plan.md`; execution remains gated until the active workflow chain closes.

## Workflow Contract
- Keep this main-session controlled.
- Helper lanes are allowed only for planning ahead, read-only research, audits, and bounded proposal prep.
- No silent canonical rewrites.
- No broad content passes.
- No archive/move/delete work before the relevant approval packet is explicitly approved.
- `06. Playbooks/` cleanup during 9B is routing/classification work, not semantic rewriting.
- Consolidation / shedding is last or separate; do not mix doctrine dedupe into the earlier truth-contract passes.

## Phased Plan

### Phase 1 - Bounded Issue Inventory (read-only)
Produce a written findings table before any approval is requested.

#### 1A - GS state resolution input
- Read `tmp/portfolio-config.json` GS entry, `03. Portfolio/Deployment Trigger Sheet.md` GS row, and `02. Markets/Watchlist.md` GS row.
- Answer one question: is the WATCH state an intentional hold with documented reason, or a carried mismatch with no owner decision behind it?
- If intentional, document the reason in config / owner surfaces and close the validator noise.
- If stale, escalate as a deployment decision rather than letting it remain drift.

#### 1B - Note-to-machine mirror consistency
- For every tracked name in `tmp/portfolio-config.json`, compare `coverageLane` against the lane listed in `02. Markets/Watchlist.md` and the tier/lane contract listed in `04. Research/Coverage Universe.md`.
- Output a pass/fail table per ticker per surface.
- Flag every mismatch with the specific field and value discrepancy.
- This table becomes the validator-expansion target for Phase 4.

#### 1C - `06. Playbooks/` root classification using the three-tier framework
Classify all root files into:
- **Governance & Doctrine**
- **Operations & Orchestration**
- **Component Specs**
- **Archive candidates**
- **Needs review**

For each file, mark a recommended action:
- keep-as-is
- keep-rename
- move-to-subfolder
- archive
- defer

#### 1D - `06. Playbooks/Project Continuity/` reference check
- For the closed notes still sitting in the active folder, grep the queue, registry, and active continuity notes for each filename.
- Classify each as `safe to archive` or `must defer - still referenced`.
- Output the findings as a table and use that as the approval input for the archive pass.

### Phase 2 - Operator Decision Packet
Present three approval packets, each independent.

#### Packet A - GS state decision
- One decision only: promote GS from WATCH to DEPLOYABLE, widen the band so in-band detection stops firing, or document a deliberate hold reason so the mismatch is explicitly owned rather than noise.
- Present the current GS data, written state, and the recommended resolution.

#### Packet B - `06. Playbooks/` reorganization scope
- Present the 1C classification table.
- Ask explicitly:
  - which archive candidates to move to `09. Archive/`
  - whether Component Specs should stay flat or move under a bounded specs subfolder
  - whether the prompt/model-ops files stay in operations or get their own bounded subfolder
  - whether `technical-chart-pass` should be structurally deprecated / archived in favor of `veritas-technical-pass`
- Treat the three-tier framework as a classification tool, not an automatic restructure trigger.

#### Packet C - `06. Playbooks/Project Continuity/` archive pass
- Present the 1D safe-to-archive list and must-defer list.
- Get approval on the safe list before moving anything.
- Do not touch notes still referenced by active files.

### Phase 3 - Execute Approved Decisions
Execute only what Packet A/B/C explicitly approves. Back up before destructive work.

- Apply the approved GS fix to the machine / owner surfaces and re-run validator checks.
- Move approved `06. Playbooks/` archive candidates, create approved bounded subfolders, and perform approved routing-only renames.
- Structurally deprecate `technical-chart-pass` only if approved; keep `veritas-technical-pass` as the canonical replacement.
- Move the approved safe-to-archive continuity notes to `09. Archive/Project Continuity/` and verify active-file references remain clean.

### Phase 4 - Contract Hardening
Land four bounded deliverables.

#### 4A - Post-Catalyst Truth Sync protocol
- Write `06. Playbooks/Post-Catalyst Truth Sync Protocol.md`.
- Define trigger events, sync window, owner surfaces, verification steps, and acceptable close condition.

#### 4B - Expanded consistency validator
- Expand `scripts/validate_dashboard_state.py` so it checks Watchlist and Coverage Universe lane alignment against `tmp/portfolio-config.json`.
- Surface mismatches as warnings, not pseudo-decisions.
- Use the Phase 1B mismatch table as the target set.

#### 4C - Write-back utility design decision
- Do not assume build-now.
- Either write the one-page near-term spec for a dry-run-first gated write-back helper, or explicitly defer it to a named future workflow with owner and rationale.

#### 4D - `migration-backups/` retention policy
- Add a retention policy section to `06. Playbooks/Workspace Structure Protocol.md`.
- Define what triggers a new backup, baseline retention windows, and who approves pruning.

### Phase 5 - Verification and Closure
Run the bounded closure checks:
- `python scripts/validate_dashboard_state.py --write` -> target `0 critical / 0 warning / 0 info`
- `python scripts/test_dashboard_acceptance.py` -> target `17/17` or higher if new tests are added
- `python scripts/daily_note_dedupe.py --all` dry run -> target `0 changed`
- confirm `GS` no longer emits state-vs-band drift noise
- confirm `06. Playbooks/Project Continuity/` now holds only active or intentionally-held notes
- confirm `06. Playbooks/` root no longer holds approved archive candidates
- confirm the technical-skill deprecation decision is structurally visible if approved
- commit the workspace before closing summary

Closure criteria:
- GS has an explicit documented decision, not carried mismatch
- Post-Catalyst Truth Sync protocol exists as a named governance doc
- at least one expanded consistency check is live in the validator
- the approved continuity-note archive pass is complete
- the technical-skill conflict is structurally resolved if approved for 9B scope
- write-back utility has a written design decision or explicit named defer
- `migration-backups/` retention policy is written

### Phase 6 - Consolidation and Shedding (deferred last or separate)
Do not mix this into the earlier truth-contract passes.

Target it only after Phase 5 closes cleanly or spin it into a separate bounded workflow if the scope grows.

Initial same-function clusters already identified:
- **Parallel / IC orchestration cluster**: `OpenClaw Parallel Work Plan.md`, `OpenClaw Parallel Pilot Queue.md`, `Automation Orchestration Protocol.md`, `Independent Contractor Workflow.md`, `Parallel IC Project Workflow.md`, `IC Project Registry.md`, plus adjacent routing docs like `IC Model Routing Policy.md` and `OpenClaw Model Deployment Plan.md`
- **Workbook / packaging cluster**: `Excel Operating Workbook Structure.md`, `Minimum-Viable Workbook Schema.md`, `Workbook Export Contracts.md`, plus the adjacent continuity artifacts around Workflow 5 / workbook packaging
- **Legacy predecessor / duplicate continuity cluster**: `Coverage Tier Framework.md` vs `Workflow 6 - Coverage Tier Framework.md`, `Command Center Chain Readiness Review.md`, `Excel Operating Workbook.md`, and similar historical/adjacent continuity notes
- **Prompt / model-ops cluster**: `Active Model Prompt Queue.md`, `Model Prompt Operations.md`, `OpenClaw Model Deployment Plan.md`, `IC Model Routing Policy.md`, and the prompt-pack / guardrail group

Acceptance for this layer:
- explicit keep / merge / archive / move map by cluster
- no silent doctrine merging
- no control-surface breakage in queue / registry / active governance docs

## Phase 1 Findings - Completed (2026-05-03)

### 1A - GS state resolution input (verdict)
- Verdict: **carried mismatch**, not an intentional hold.
- Evidence: Trigger Sheet + Technical Entry both already show GS as deployable-now tactical secondary; Watchlist and Coverage Universe quick-reference wording had stale watch-only language.
- Phase 3 action (executed): promote stale mirror wording to match owner surfaces.

### 1B - Note-to-machine mirror consistency (high-risk set)
- Highest-risk contradiction was GS (resolved in Phase 3 mirror sync).
- Remaining high-signal contradictions to carry into the validator-expansion target set:
  - NVDA tier wording conflict (config tactical vs stale core phrasing in thesis quick-reference table; resolved in Phase 3 mirror sync)
  - stale post-earnings phrasing for GOOG/MSFT/XOM/VRT (resolved in Phase 3 mirror sync)
  - known thesis-parity residue for CAT/CVX/SMCI/LLY (intentionally routed to Workflow 11 intake/procedure scope, not broad 9B rewrite)

### 1C - `06. Playbooks/` root classification (35-file inventory)
- Governance/Doctrine: 10
- Operations/Orchestration: 9
- Component Specs: 10
- Needs review/defer: 6
- Direction: route-only normalization is approved for bounded execution; broad semantic rewrites remain out of scope.

### 1D - `06. Playbooks/Project Continuity/` archive safety (reference-checked)
- Safe-to-archive now: 11 notes (no active references in queue/registry/active 9B/10/11/12 continuity chain)
- Must-defer: 11 notes (still referenced by active control surfaces or active workflows)
- Rule enforced: no archive move for anything still referenced.

## Phase 2 Packet Posture (operator-directed)
- Operator directive is explicit: complete WF9B and continue sequentially through WF10-12 with hardening passes.
- Packet handling in this pass:
  - **Packet A (GS decision): approved and executed** as mirror alignment to deployable-now tactical-secondary wording.
  - **Packet B (`06. Playbooks/` routing): approved as a bounded route map + cleanup plan in 9B; high-reference path moves defer to the final consolidation/shedding layer to avoid link breakage.**
  - **Packet C (continuity archive): approved for safe-list-only moves with backups first; must-defer list remains in place.**

## Outstanding
- Commit the 9B change set after the control surfaces and audit note are included.
- Keep consolidation/shedding execution deferred; only the cleanup plan belongs in 9B.
- Carry routed residue forward without reopening 9B:
  - Workflow 10 -> runtime/session/completion-state trust debt
  - Workflow 11 -> intake procedure plus thesis-parity residue for watch-lane names
  - Workflow 12 -> macro/policy manual-dependency and timing-trust residue

## Blockers / Trust Gaps
- This workflow must not become a backdoor for silent canonical rewrites.
- UI / presentation changes must remain downstream and non-authoritative.
- Several closed continuity notes still have live references, so archive safety must be proven rather than assumed.
- Structural deprecation of `technical-chart-pass` needs explicit approval before any archive move.

## Next Action
- Workflow 10 is the active next pass.

## Key Files
- `08. Audits/Workspace Optimization and Scale Readiness Audit - 2026-05-02.md` - primary queue trigger.
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` - active queue contract.
- `06. Playbooks/IC Project Registry.md` - live operator board.
- `06. Playbooks/Automation Orchestration Protocol.md` - ownership and sequencing rules.
- `06. Playbooks/Notes Layer Governance Protocol.md` - note-layer mutation boundary.
- `06. Playbooks/Notes Layer Audit Checklist.md` - downstream note-surface audit checklist.
- `06. Playbooks/Workspace Structure Protocol.md` - structural routing / retention target.
- `02. Markets/Watchlist.md` - human-facing mirror to validate.
- `04. Research/Coverage Universe.md` - thesis / lane mirror to validate.
- `03. Portfolio/Deployment Trigger Sheet.md` - owner deployment surface for GS.
- `03. Portfolio/Portfolio Snapshot.md` - current owner note with known state-surface residue.
- `tmp/portfolio-config.json` - machine lane assignment source.
- `tmp/dashboard-validation.json` - current validator artifact.

## Automation / Refresh Path
- Keep this main-session controlled.
- Read-only helper lanes are fine for planning, audit, validator-expansion proposals, and consolidation research.
- Do not let helper lanes publish final queue state, archive decisions, or canonical-surface truth calls.
- Any write-back utility must default to dry run and require post-apply validation before it is ever treated as usable.
