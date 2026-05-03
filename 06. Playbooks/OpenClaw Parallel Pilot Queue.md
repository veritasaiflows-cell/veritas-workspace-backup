# OpenClaw Parallel Pilot Queue

## Purpose

Define the first concrete pilot queue for using OpenClaw parallel resources deliberately.

This queue is not a wish list.
It is the bounded next set of pilots that should prove whether parallel execution is actually reducing operator burden.

## Resource posture

### Main default
- `openai-codex/gpt-5.4`
- use for orchestration, integration, and higher-trust workspace work

### Spawned worker default
- `openai-codex/gpt-5.4`
- use for bounded implementation, patch prep, and detached worker passes by default

### Lower-complexity Codex helpers now available
- `openai-codex/gpt-5.3-codex`

Use it only for:
- bounded read-heavy inspection
- mechanical comparisons
- draft patch preparation
- cheap implementation scaffolding

Do not use it for:
- final trust adjudication
- canonical-state judgment
- ambiguous architecture decisions
- final portfolio or OS calls

`openai-codex/gpt-5.3-codex-spark` is removed from Veritas-routed workflow use. If Randall uses Spark manually, treat that output as external evidence for review rather than a pilot lane.

## Pilot success standard

The pilot queue is succeeding only if:
- completion time drops
- main-session clutter drops
- reconciliation burden stays low
- artifact ownership stays clear
- the user gets more finished passes, not more chatter

## Queue structure

Each pilot should define:
- lane owner
- model posture
- deliverable
- what not to touch
- acceptance check
- execution mode (`spawned`, `main-session exception`, or other justified posture)
- QC complete (`yes` or `no`)

## Next orchestrated workflow queue

Current chain goal:
- keep advancing the approved trust-hardening and note-sync chain in sequence until the finance note layer is truth-synced and the dashboard/workbook surfaces are linked to fresh trustworthy artifacts strongly enough to use as real operator surfaces
- do not stop after a local completion if final QC says the next approved item is already clear

### Workflow 1 - Policy target-range fail-closed hardening
Status:
- completed before the 2026-05-01 Workspace QA Audit
- missing-policy formatting crash path removed
- residual manual-policy dependency remains a separate trust debt, not an open crash path

Why now:
- manual target range is still the most important policy trust residue
- current missing-policy branch may still crash numeric formatting in `market_state_refresh.py`

Preflight reviewer:
- required for this workflow
- reviewer checks chain contract, missing-branch behavior, and whether the implementation scope is too narrow

Implementation lane:
- OpenClaw subagent
- default model: `openai-codex/gpt-5.4`

Deliverable:
- remove the missing-policy formatting crash path
- tighten missing-policy degraded branch
- define the smallest honest freshness/fail-closed rule for manual Fed target constants

Acceptance check:
- missing `policy-expectations.json` path does not crash
- output degrades honestly
- no fake numeric Fed formatting when values are absent

### Workflow 2 - Broad residual atomic-write migration
Status:
- completed on 2026-05-01 as a bounded six-file migration
- verification passed; broader residual atomic-write debt remains a later ranked backlog, not this workflow's completion blocker

Why now:
- core artifacts are safer, but direct write surfaces still exist elsewhere
- this is now a bounded integrity-hardening backlog, not a vague concern

Preflight reviewer:
- optional if scope is kept mechanical and file list is explicit

Implementation lane:
- OpenClaw subagent
- default model: `openai-codex/gpt-5.4`

Deliverable:
- migrate remaining direct `write_text` / equivalent artifact writes to shared atomic helpers in a bounded file set
- write a backlog note for residual out-of-scope callsites if needed

Acceptance check:
- touched producers still run
- no temp-file litter
- no broadened semantic changes

### Workflow 3 - External payload schema guards
Status:
- completed on 2026-05-01
- shared guards and downstream sanitizers landed and validated on live workspace data

Why now:
- source parsing is still too assumption-heavy in several places
- we need degrade-to-partial behavior, not silent shape optimism

Preflight reviewer:
- required if the patch touches multiple data-source families

Implementation lane:
- OpenClaw subagent
- default model: `openai-codex/gpt-5.4`

Deliverable:
- add lightweight dict-shape / required-key guards for external JSON payloads in the active finance stack
- degrade to partial/warning instead of silent misuse

Acceptance check:
- malformed/missing structures do not crash the active path
- trust downgrade is explicit

### Workflow 3B - Independent workspace QA audit and QA-pass skill creation
Status:
- completed on 2026-05-01
- produced `08. Audits/Workspace QA Audit - 2026-05-01.md` and `skills/workspace-qa-pass/SKILL.md`
- validated with `openclaw skills check`

Why now:
- after the first trust-spine chains, we need an independent review of where the workspace still has integrity debt or orchestration drift
- repeated audit needs now justify building our own reusable QA-pass skill instead of re-prompting the same review logic each time

Lane:
- Veritas main session orchestrating bounded helper lanes as needed

Deliverable:
- run an independent workspace review and audit after Workflow 3 completes
- look for existing relevant skills on the web and extract only the useful patterns
- implement a workspace-owned skill for a high-quality QA pass
- record what still needs tightening after the first trust-spine chains

Acceptance check:
- audit identifies real residual risks and control-surface debt
- useful external skill patterns are reviewed without cargo-culting them
- a local QA-pass skill exists in the workspace with a clear trigger and bounded procedure

### Workflow 3C - Canonical-note trust gate enforcement
Status:
- completed on 2026-05-01
- bounded fail-closed writer gate implemented and validated
- next workflow is Workflow 4

Why now:
- the QA audit found canonical-note mutation can occur before trust adjudication finishes
- this is a real trust-semantic gap, not a documentation problem

Preflight reviewer:
- required for this workflow
- reviewer checks whether the safest bounded fix is earlier trust adjudication, explicit writer fail-closed gates, or a minimal hybrid

Implementation lane:
- OpenClaw subagent
- default model: `openai-codex/gpt-5.4`

Deliverable:
- prevent canonical note mutation when the trust contract does not explicitly allow it
- harden the finance refresh chain so trust gating is enforced before weekly/canonical writers run or those writers fail closed without an allow signal
- keep the scope bounded to trust-gate enforcement rather than broad architecture redesign

Acceptance check:
- warning-grade/internal-only trust posture cannot mutate canonical weekly/intelligence notes implicitly
- chain degrades honestly instead of writing first and disclaiming later
- bounded verification proves no pre-trust canonical write path remains in the touched flow

Completion evidence:
- added shared `canonical_note_mutation_gate(...)` helper in `scripts/market_data_utils.py`
- hardened `weekly_macro_snapshot.py`, `weekly_intelligence_brief.py`, `postmarket_snapshot.py`, and `daily_executive_brief.py` to write machine sidecars when validation is not explicitly clean
- updated `run_summary_refresh.py` so downstream trust output now reports the real canonical-note mutation decision and rationale
- live degraded-state rerun preserved canonical file mtimes and wrote only machine artifacts

### Workflow 4 - Sequential chain protocol
Status:
- completed on 2026-05-02 after a second clean day-job orchestrator validation pass
- protocol landed in the control-plane docs and passed bounded QA/audit review
- live validation now proved the orchestrator can keep the queue, registry, and continuity note aligned without falsely advancing the chain

Why now:
- we have enough real passes to standardize the protocol
- reviewer-before-implementation should become an explicit rule where stakes justify it

Lane:
- Veritas main session

Deliverable:
- compact protocol for sequential chains
- required reads, allowed edits, out-of-bounds, verification, reviewer trigger rules, and final QA rules

Acceptance check:
- next chain can be launched from the protocol with minimal reconstruction

Completion evidence:
- `06. Playbooks/Continuity Stewardship Protocol.md`, `06. Playbooks/Cron Job Protocol.md`, `06. Playbooks/OpenClaw Parallel Work Plan.md`, and `06. Playbooks/Automation Architecture Spec.md` now encode the sequential-chain rules, reviewer-first trigger, secure spawn defaults, and completion-confirmation logic
- first live `veritas:day-job-orchestrator` run corrected a real queue/registry/continuity drift without falsely marking Workflow 4 complete
- bounded read-only QA/audit found Workflow 4 was not closable from a single live run and required one more real validation pass
- second live day-job pass found queue, registry, and continuity already synchronized, confirmed Workflow 4 complete, and advanced the queue honestly to Workflow 4B

### Workflow 4B - Live cron shakedown + run ledger hardening
Status:
- completed on 2026-05-02 after controlled proof runs across all five live Veritas cron jobs and final QC

Owner:
- Veritas

Next pass:
- residual follow-up only: later fix the finance-window run-summary `execution.chain_status` field so successful runs do not still report `running`

Blocker:
- no closure blocker remains; residual run-summary state bug is captured as later control-surface hardening

Category:
- control plane / automation

Parallel posture:
- serial while the proof-run contract and run-ledger surface are being pinned down

Why now:
- the cron/control-plane architecture is coherent, but the live scheduler is not yet boringly trustworthy
- the next missing proof is repeated run evidence, run-history visibility, and fail-closed follow-up behavior
- this is more urgent than packaging or expansion because those assume the operating spine is already reliable

Lane:
- Veritas main session plus bounded helper lanes as needed

Deliverable:
- exercise each live Veritas cron window in proof mode
- create one compact workspace-native run ledger / operator surface
- define blocked/error follow-up behavior and rerun rules per job
- decide explicitly whether internal-only / no-delivery posture is acceptable per job or needs tightening

Acceptance check:
- each live Veritas cron job is run at least once in a controlled proof path
- result is visible in both cron run history and workspace artifacts/notes
- blocked/error runs leave a visible next-step record instead of silent drift
- trust-boundary fields like `canonical_note_mutation_allowed` and `presentation_allowed` remain enforced
- rerun and overlap rules are explicit

### Workflow 4C - Finance chain truth-sync hardening
Status:
- completed on 2026-05-02 after the XOM post-earnings sync, owner-note alignment, and closure QA

Owner:
- Veritas

Next pass:
- none inside Workflow 4C; promote directly to **Reassess trust grade**

Blocker:
- no closure blocker remains; residual caveats are explicit and passed forward to trust-grade reassessment

Category:
- note-sync / reconciliation

Parallel posture:
- serial for canonical-note writers; bounded read-only reviewer support is allowed, but not parallel canonical writers

Why now:
- the visible finance note layer is currently split-brain relative to the live machine artifact layer
- several top human-facing notes are stale enough to mislead after the late-April / early-May catalyst cluster
- this should be fixed with a narrow evidence-first truth-sync, not a broad note cleanup spree

Lane:
- Veritas main session with optional bounded reviewer support if needed

Deliverable:
- run a bounded post-cluster truth-sync for the six highest-risk finance notes
- quarantine stale duplicate week blocks and unfinished staging content from weekly canonical notes
- refresh only the sections that currently lie or mislead
- keep scope out of broad scorecard, research-note, or risk-doctrine churn

Acceptance check:
- the six highest-risk finance notes no longer speak as if Apr 29 is still ahead
- weekly/canonical notes do not mix stale duplicate week blocks with unfinished staging content
- priority-name statuses match current trigger data and macro timing matches current market-state data
- the visible finance note layer becomes trustworthy enough to use as an operator surface again without pretending full autonomy is ready
- the XOM post-earnings interpretation gap is closed and the owner notes agree on the resulting posture

Completion evidence:
- `05. Intelligence/Earnings/XOM Q1 2026 Post-Earnings Scorecard.md` now exists with closure state `Closed with follow-up`
- XOM owner-note sync landed across trigger, technical, portfolio, calendar, weekly, dashboard, and watchlist surfaces
- `tmp/dashboard-acceptance-report.json` returned `16 passed / 0 failed`
- `tmp/dashboard-validation.json` returned `0 critical / 11 warning`
- closure QA recorded in `08. Audits/Workflow 4C Finance Chain Truth Sync Closure QA Audit - 2026-05-02.md`

### Trust-grade reassessment / warning-residue gate
Status:
- closed on 2026-05-02 with follow-up after the latest E17 blocker-clearing and band-sync passes
- verdict: trust still remains warning-grade / `usable_with_caution`, not clean
- Workflow 5 is now allowed to open **only** as a staging-only packaging/workflow-fit pass because the remaining residue no longer blocks that narrower question, even though it still blocks any claim of clean scheduling or presentation-grade trust

Owner:
- Veritas

Next pass:
- carry the warning stack forward into Workflow 5 as explicit no-go conditions for scheduled packaging, presentation promotion, or fake-clean trust claims
- use the approved bounded band-sync automation path as part of the first Workflow 5 pass to define workbook / technical-note parity expectations for the remaining missing-section names (`CVX`, `PLTR`, `AMD`, `LNG`)

Blocker:
- no blocker remains for opening Workflow 5 under a degraded contract, but the following residue stays active and must remain visible:
  - 11 entry bands still need review after the approved May 1 band pass (`GOOG`, `LMT`, `AMZN`, `VRT`, `RTX`, `CAT`, `AMD`, `KTOS`, `SLV`, `TLT`, `SMCI`); existing note sections are now synced, and the remaining missing-section flags (`CVX`, `PLTR`, `AMD`, `LNG`) are scope/lane questions rather than missed level updates
  - timing-sensitive earnings-date confirmation remains unresolved, now led mainly by `NVDA`
  - in-band / WATCH residue remains live for `GS`, `CVX`, and `PLTR`
  - non-daily deployment-flow warnings remain live for `AMD`, `CVX`, `LNG`, and `PLTR`
  - macro/policy artifacts still depend on manual caution flags

Category:
- trust gate / reconciliation

Parallel posture:
- serial until the degraded Workflow 5 packaging contract is written clearly enough that no one can confuse staging analysis with safe scheduled output

Why now:
- green acceptance alone does not mean clean operator trust
- the live dashboard still reads `usable_with_caution` and validation still reads `warning`
- Workflow 5 is a packaging/workflow-fit pass, not a deployment-decision pass, so it can proceed if the residue is carried forward honestly instead of hidden

Lane:
- Veritas main session with bounded reviewer support if needed

Deliverable:
- honest trust-grade verdict against the live dashboard, trigger, and note layer
- explicit decision on whether Workflow 5 can open

Acceptance check:
- close this gate only if Workflow 5 opens without implying clean trust, safe scheduling, or presentation-grade packaging

### Workflow 5 - PDF/Excel workflow-fit pass
Status:
- completed on 2026-05-02 under a degraded / `usable_with_caution` contract
- pass 1 kickoff, pass 2 workbook freshness/checksum hardening, execution/QC control-surface hardening, pass 3 workbook coverage-gap review, pass 4 manual missing-section cleanup, and the final trust/promotion decision are now QC-closed
- the workbook contract is now explicit as `21` tracked / `17` technical-entitled / `13` execution-board, and note/workbook parity is closed across the 17 technical-entitled names
- approved posture now: default scheduled chains stop at `workbook_export.py`, while an explicit operator-invoked `run_finance_refresh_chain.py <window> --build-workbook` tail is allowed when staging parity matters
- scheduled workbook packaging, scheduled PDF packaging, and presentation-grade promotion remain blocked while the warning residue stays active

Category:
- workbook / packaging

Parallel posture:
- bounded helper lanes were acceptable for the packaging-fit pass, but the result does not justify autonomous scheduled packaging yet

Why now:
- the trust spine is still warning-grade, but the remaining residue belonged in the packaging contract rather than as a hard blocker to defining that contract
- the workbook freshness/parity gap and the approved bounded band-sync helper made this workflow concrete enough to close with an explicit no-go promotion decision instead of vague caution language

Lane:
- Veritas main session plus bounded helper lanes as needed during the pass

Execution mode:
- main-session closure / QC after bounded spawned passes

QC complete:
- yes - Workflow 5 closed by an explicit no-go promotion decision rather than a fake-clean upgrade

Deliverable:
- define where PDF and Excel belong in the automation workflow
- decide what stays staging-only, what can be scheduled, and what remains operator-gated
- decide whether workbook generation becomes a chain-tail step and how the approved bounded band-sync helper fits the workbook / technical-note parity contract

Acceptance check:
- packaging role is clear, explicitly degraded where needed, and does not pretend trust we have not earned
- any future scheduled packaging path remains fail-closed behind the unresolved warning stack until a later trust pass clears it

Completion evidence:
- `scripts/run_finance_refresh_chain.py` still requires explicit `--build-workbook` opt-in before `workbook_template.py` runs
- `tmp/workbook-export-manifest.json` is fresh and checksum-clean, but still carries warning-grade residue from the upstream stack
- `tmp/workbook-build-validation.json` still reports `overall_status = warning`, and `tmp/dashboard-validation.json` still reports `11` warnings
- `tmp/band-note-sync.json` now returns `0` missing sections and `0` needs-sync, so note/workbook parity is closed without widening canonical-note automation

### Workflow 6 - Coverage tier framework
Status:
- completed on 2026-05-02 with follow-up after final QC
- first bounded framework draft now lives in `06. Playbooks/Project Continuity/Workflow 6 - Coverage Tier Framework.md`
- pass 2 normalization is complete: `AMD`, `LNG`, `TLT`, and `SMCI` carry explicit machine semantics in `tmp/portfolio-config.json`, and the `CVX` watchlist mirror gap is closed
- pass 3 validator/contract hardening is complete: false non-daily deployment-flow leakage is cleared, watch-lane `CVX` / `PLTR` no longer raise false in-band/WATCH conflicts, and macro/speculative names no longer count as live band-review debt
- pass 4 daily-entitlement judgment right-sized the execution board to **10** names
- pass 5 closure QC confirmed the remaining warning stack is the expected residue, not an open framework blocker: `band_staleness`, `state_vs_entry_band_conflict`, `timing_sensitive_earnings_dates`, `macro_manual_dependency`, `policy_expectations_manual_dependency`
- small safe timing fix landed: `scripts/earnings_calendar_enrichment.py` now carries the confirmed `BRK.B` May 2 date, but the timing warning remains because the remaining `DATE CHANGED` alerts still need manual confirmation or a policy-level handling decision

Category:
- research

Parallel posture:
- serial for framework design; later parallel-safe (read-only) for supporting scans once the framework is fixed

Why now:
- scale should come from better coverage rules, not a random ticker pile
- the tracked universe needs explicit ownership and refresh rules before widening
- Workflow 5 made the live lane split explicit (`21` tracked / `17` technical-entitled / `13` execution-board), and Workflow 6 pass 4 has now right-sized that execution board to **10** while preserving the same **17** technical-entitled names

Lane:
- Veritas main session as orchestrator / QC owner with bounded spawned working passes by default

Execution mode:
- main-session QC after spawned draft/normalization/entitlement passes; passes 1 through 4 are now closed as spawned-pass results

QC complete:
- yes — Workflow 6 is now closed with follow-up; flip back to `no` only if a new follow-up reopens the lane contract

Deliverable:
- define coverage tiers such as daily, event-driven, watchlist-only, and bench/archive
- define admission, promotion, demotion, and freshness rules
- right-size the execution lane only where daily upkeep still changes real capital decisions

Acceptance check:
- every tracked name can be assigned a clean tier with an explicit operating expectation
- downstream validators/contracts respect those explicit tiers without treating watch/macro/speculative names as implicit daily-execution names
- the weaker execution-lane review closes with an honest keep/demote call instead of leaving legacy daily coverage on autopilot

### Workflow 7 - Sector coverage expansion plan
Status:
- pass 1 framework draft completed on 2026-05-02
- pass 2 recommendation design completed on 2026-05-02
- pass 3 decision/implementation completed on 2026-05-02: `LLY` was chosen over `JNJ` and added as the single Healthcare **watch-lane** pilot under Option C
- continuity note now includes the preferred sleeve pair (**Healthcare + Utilities / regulated power**), ranked proxy shortlist (`LLY` / `JNJ`, `SO` / `NEE`), and the bounded implementation result
- current result remains intentionally narrow: **no immediate +2 expansion**, no execution-lane promotion, and Utilities stays queued behind a post-add review cycle

Why now:
- sectors should expand by sleeve logic, not by ad hoc ticker enthusiasm
- this is the correct bridge between a stable core universe and broader coverage

Lane:
- Veritas main session

Deliverable:
- define which sectors deserve active coverage
- define leader/proxy names and target coverage tier by sector
- define the next controlled wave of names if the system can support them

Acceptance check:
- sector expansion is tied to workflow capacity and real portfolio relevance
- any first-wave adds remain explicitly human-approved and default to watch-lane until a later promotion decision
- warning-grade posture is allowed to stop at a recommendation of **+1 or 0**, rather than forcing a cosmetic two-name wave

### Workflow 8 - Command Center chain readiness review
Status:
- completed on 2026-05-02 across two truthful phases: the original pass 1-3 no-go remains preserved for the pre-remediation state, and the later bounded reopen is now QC-closed
- blocker-first remediation cleared the original four-warning gate, and the bounded reopen then aligned Command Center state/reason/lane behavior with live source truth
- `tmp/dashboard-validation.json` is `clean` (`0 critical / 0 warning / 0 info`), `tmp/workbook-build-validation.json` is `overall_status = ok`, and the acceptance suite now passes `17/17`
- execution/QC visibility: main-session bounded implementation / full-chain QC; yes

Why now:
- the Command Center should expand only after the trust spine and coverage model are strong enough to support it

Lane:
- Veritas main session with bounded reviewer support if needed

Execution mode:
- main-session bounded implementation / full-chain QC

QC complete:
- yes for blocker-first remediation and the clean full-chain rerun

Deliverable:
- keep Command Center aligned with live source truth without promoting it into a second truth owner
- land only the minimal code/config/note sync required for honest state display

Acceptance check:
- `GOOG` / `MSFT` show `ALMOST` across the live deployment/technical surfaces
- benched names do not show false LIVE trigger badges
- watch/execution lane posture is visible and truthful
- command-center expansion remains sequenced behind truth, not ahead of it

Current findings:
- the original pass 1-3 no-go remains the correct historical record for the pre-remediation state
- the blocker-first pass materially changed the gate: the former blocker stack (`band_staleness`, `timing_sensitive_earnings_dates`, `macro_manual_dependency`, `policy_expectations_manual_dependency`) is gone from live dashboard validation
- stale `workflow_state` machine drift in `tmp/portfolio-config.json` had been forcing false `BLOCKED` state for `GOOG` / `MSFT` through `scripts/trigger_sheet_refresh.py`; that drift is now corrected
- `triggerToday` gating no longer treats `BENCH` as live-ready, and watch/execution lane reasons now distinguish lane scope from truly underdefined setups
- Technical Analysis now exposes lane badges while Command Center remains downstream and non-authoritative
- the minimum upstream contract is re-proved: dashboard, workbook, and note-owned surfaces are consuming one coherent same-window truth contract while remaining fail-closed

Reopen status:
- the bounded Workflow 8 reopen was explicitly reprioritized, completed, and QC-closed on 2026-05-02
- any future Workflow 8 follow-up should stay limited and preserve the downstream-only ownership rule
- the sequential queue now continues to Workflow 9A

### Workflow 9 - Research department operating model
Status:
- completed with follow-up in the main session after normalization. The five-desk model is now accepted as a functional operating model for the live workspace; Risk Rules ownership/cadence/freshness is closed with explicit operator sign-off on the three doctrine additions; and Command Center ownership remains downstream/non-authoritative.

Why now:
- a department model only made sense once trust, coverage tiers, and command-center ownership were clearer

Lane:
- Veritas main session

Execution mode:
- main-session opening draft -> Risk Rules review -> normalization / closeout

QC complete:
- yes - the Risk Rules additions are now operator-approved, the ownership/cadence model is normalized to the real live workflow, and no further Workflow 9 structural pass is required now

Next pass:
- none inside Workflow 9; the queue is now explicitly re-prioritized to Workflow 9A and Workflow 9B before the older Workflow 10-12 backlog

Most recent completed sub-pass:
- Workflow 9 normalization / closeout executed 2026-05-02 after operator sign-off on Risk Rules additions
- result: desks are explicitly functional roles with accountable ownership, cadence language now matches real finance windows, and publishing/output language now reflects the current manual/staging workbook contract instead of idealized automation

Follow-up kept outside Workflow 9:
- `NVDA` recheck obligation remains due on or before the first post-close chain on **2026-05-13**
- `BRK.B` and `CAT` remain correctly under manual post-earnings hold until real Q2 confirmation exists
- `LLY` remains the first bounded live admission-model pilot before formal Workflow 11 drafting
- the older Workflow 10 runtime-review backlog now sits behind Workflow 9A and Workflow 9B unless a fresh session-lifecycle failure overtakes them

Deliverable:
- define functional desks, owned outputs, owned inputs, and refresh cadence
- avoid fake org-chart theater

Acceptance check:
- the model improves throughput and clarity without inventing bureaucracy

### Workflow 9A - Workspace structure and drift cleanup
Status:
- newly inserted on 2026-05-02 as the immediate next priority before the earlier Workflow 10-12 backlog
- opened from the paired workspace-optimization / scale-readiness audits after repeated findings showed the OS is stronger operationally than it is organizationally
- root cause for the daily-note duplication gap is now confirmed: the session-memory append path writes without an existence check, and stale helper/worktree doctrine still reinforces append-only behavior
- bounded local fix landed: `scripts/daily_note_dedupe.py` cleaned the known duplicate daily notes and protocol surfaces now require running the dedupe guard when automated daily-note writes touch `memory/YYYY-MM-DD.md`
- Phase 2 caller-risk analysis is now complete: `generated documents/` is confirmed as live code-path debt rather than a cosmetic folder issue, `scripts/.claude/...` appears to be untracked stale residue with no live callers, the technical-pass overlap is confirmed as a skill-boundary problem rather than an automation-chain dependency, and the real `__pycache__` gap was missing ignore coverage plus local cache noise rather than tracked index residue; `.gitignore` now includes `__pycache__/`.
- Current gate: Workflow 9A is now in the Phase 3 operator-decision state. The implementation contract is clear enough to present, but Phase 4 cleanup cannot start until Randall explicitly decides the fast-track delete/move bucket and the `generated documents/` / technical-skill end-state.

Why now:
- Randall explicitly reprioritized restructuring and organization ahead of further expansion work
- `06. Playbooks/` is overloaded, stale workspace artifacts still exist, and temporary root/path exceptions now need real exit plans before they become permanent architecture

Lane:
- Veritas main session with bounded read-only helper support if needed; destructive cleanup remains operator-approved

Deliverable:
- triage `06. Playbooks/` into active governance, active project continuity, and archive candidates
- define the migration target and caller inventory for `generated documents/` before any path move is attempted
- inventory and surface explicit decisions for stale artifacts and repo noise (`scripts/.claude/...`, local `scripts/__pycache__/`, overlapping / legacy skill surfaces) instead of leaving them as audit footnotes
- keep the daily-note bloat incident honest as upstream/runtime debt plus local workspace hardening: maintain the dedupe guard, monitor recurrence, and surface any still-needed runtime fix without broad memory-system redesign
- tighten workspace-structure rules so root exceptions, archived continuity notes, and temporary control-plane surfaces have explicit homes

Acceptance check:
- the workspace has a clear reorganization contract, explicit cleanup decisions, and a bounded follow-up map instead of scattered audit residue
- the daily-note duplication problem has a verified local guard, cleaned current notes, and an explicitly recorded residual upstream risk instead of hand-waving
- nothing destructive is done silently; any delete/move/index-cleanup step that needs approval is surfaced explicitly first

### Workflow 9B - Surface alignment and drift-guard hardening
Status:
- newly inserted directly after Workflow 9A as the second organization-first pass before the older Workflow 10-12 backlog
- opened from the combined scale-readiness and architecture audits to force dashboards, validators, and note-owned mirrors onto one coherent lane / ownership contract

Why now:
- the backend lane model and note-sync hardening moved faster than the human-facing surfaces and validator contracts
- further scaling will compound note rot and contractor collisions unless truth-sync rules, owner boundaries, and surface contracts are explicit first

Lane:
- Veritas main session with bounded implementation or review support as needed

Deliverable:
- expand consistency checks to cross-verify `Watchlist.md`, `Coverage Universe.md`, and other human-facing mirrors against the machine config
- define a mandatory post-catalyst **Truth Sync** protocol and explicit artifact-owner / IC boundary rules before more automation or external lanes are added
- close the known surface-drift items (`GS` state mismatch, non-execution lane presentation gaps) and continue replacing ambiguous entitlement booleans with explicit enums where residue remains
- define the dry-run-first gated write-back path for syncing technical levels / entry bands from machine truth into note-owned surfaces without enabling silent canonical rewrites

Acceptance check:
- validators, dashboards, and note mirrors speak one coherent contract
- owner/write boundaries are explicit before additional scaling or delegation
- any write-back helper remains fail-closed, dry-run-first, and audit-friendly

### Workflow 10 - Subagent/session lifecycle reliability review
Status:
- queued behind Workflow 9A and Workflow 9B as the next runtime / control-surface hardening pass
- scope now explicitly includes stale completion-state signals such as `execution.chain_status = "running"` after success and other state-independent run-ledger gaps

Why now:
- workflow control cannot be trusted fully while subagent run state, session activity, and run-summary completion fields can disagree
- the new audits confirm this is now a scale-readiness issue, not just a one-off annoyance

Lane:
- Veritas main session

Deliverable:
- document the observed subagent/session lifecycle inconsistency
- harden stale completion-state signals and state-independent run-ledger expectations so finished work does not keep presenting as live
- define operator workarounds and no-go assumptions for orchestration until the behavior is trusted
- decide whether a dedicated bug/hardening note should remain active in the queue

Acceptance check:
- orchestration protocol and run-summary/control surfaces reflect real completion state and real control-surface limits instead of idealized assumptions

### Workflow 11 - Coverage admission model
Status:
- queued behind Workflow 10 as the first post-runtime intake / governance build; this operationalizes ticker intake and execution-lane promotion without reopening Workflow 6's settled tier framework
- formal procedure drafting should stay behind one real bounded intake case: complete the missing `LLY` thesis block first, then formalize the Workflow 11 procedure

Why now:
- Workflow 6 settled the lane/tier framework, but not the full per-ticker intake checklist, canonical note obligations, or operator promotion procedure
- repeated new-ticker questions (`LLY` now; later Healthcare / Utilities / other adds) need a clean operator process instead of ad hoc chat decisions

Lane:
- Veritas main session

Deliverable:
- use `LLY` as the first real bounded intake case so the procedure is tested before it is declared finished
- define the exact minimum thesis / data / date requirements before a name can enter the tracked universe or Execution lane
- define the per-ticker intake checklist for adding or promoting a name into the tracked universe
- define required canonical note updates and explicit owner boundaries for admission, promotion, demotion, and removal
- define the operator promotion / demotion workflow without relitigating Workflow 6's already-set lane/tier contract

Acceptance check:
- new ticker intake and execution-lane promotion decisions can run from an explicit procedure without reopening Workflow 6 coverage-tier decisions or creating ownership ambiguity

### Workflow 12 - Macro / Policy trust repair
Status:
- queued behind Workflow 11 as explicit carried-forward residue from Workflows 1 through 9 plus the new scale-readiness audits rather than a vague later candidate

Why now:
- macro/policy manual-dependency residue and timing-sensitive earnings-date friction both keep reappearing in trust surfaces and should be resolved or intentionally bounded under a dedicated pass

Lane:
- Veritas main session

Deliverable:
- define which macro/policy caveats and timing-sensitive date dependencies are intentionally manual versus still repairable
- automate or explicitly bound repairable policy / expectations inputs where the trust gain is real
- design the targeted earnings-date verification / auto-resolution path for names like `NVDA` so recurring validation friction does not linger as background noise
- prevent old macro/policy / timing caveats from drifting forward as background residue without an owner

Acceptance check:
- remaining macro/policy and timing manual dependencies are intentional, current, and explicitly owned rather than inherited residue

## Queue hardening rule

This queue is part of the orchestration protocol, not a scratchpad.

Hardening rules:
- lock the execution order unless a higher-priority trust blocker overtakes it
- when a real failure, blocker, or newly proven prerequisite appears, update this queue before opening the next major workflow
- prefer inserting new work as an explicit numbered workflow instead of burying it in chat context
- if a workflow finishes with material residue, capture that residue as a later queue item or a continuity note before moving on
- do not widen scope mid-chain without first updating the queue entry and phase contract
- do not treat a workflow as advanced until its current `execution mode` and `QC complete` state are visible here and on the registry

Adjustment rule:
- make adjustments as we move through the chains, but only from evidence
- changes should come from verified results, reviewer findings, or real operator constraints
- do not reorder the queue just because a later item sounds exciting

## Reviewer rule for chains

Use a preflight reviewer before spawning the implementation lane when:
- the phase touches trust semantics
- the phase changes chain behavior or automation policy
- the phase affects multiple files with possible hidden consequences
- the cost of a wrong patch is higher than the delay of one review pass

Skip the reviewer when:
- the phase is mechanical and bounded
- file scope is explicit
- validation is straightforward
- the implementation risk is genuinely low

Default recommendation:
- reviewer first for trust/chain/policy work
- no reviewer required for narrow mechanical integrity passes

## Execution order

Run in this order:
1. Workflow 1 - policy target-range fail-closed hardening [completed]
2. Workflow 2 - residual atomic-write migration [completed]
3. Workflow 3 - external payload schema guards [completed]
4. Workflow 3B - independent workspace QA audit and QA-pass skill creation [completed]
5. Workflow 3C - canonical-note trust gate enforcement [completed]
6. Workflow 4 - sequential chain protocol [completed]
7. Workflow 4B - live cron shakedown + run ledger hardening [completed]
8. Workflow 4C - finance chain truth-sync hardening [completed]
9. Trust-grade reassessment / warning-residue gate [completed - closed with follow-up; Workflow 5 opened under degraded contract]
10. Workflow 5 - PDF/Excel workflow-fit pass [completed - closed with follow-up; manual packaging remains required]
11. Workflow 6 - coverage tier framework [completed - closed with follow-up; remaining 5-code warning stack accepted as separate residue]
12. Workflow 7 - sector coverage expansion plan [completed - closed with follow-up; single-name Healthcare watch-lane pilot (`LLY`) added under Option C, Utilities queued for post-add review cycle]
13. Workflow 8 - command center chain readiness review [completed - historical pass-3 no-go preserved; bounded reopen QC-closed; downstream-only ownership rule preserved]
14. Workflow 9 - research department operating model [completed - closed with follow-up; functional desk model normalized, Risk Rules doctrine additions operator-approved, and Command Center kept downstream/non-authoritative]
15. Workflow 9A - workspace structure and drift cleanup [new top priority; reorganize playbooks/root exceptions/cleanup decisions before more expansion work]
16. Workflow 9B - surface alignment and drift-guard hardening [new second priority; lock truth-sync/validator/owner contracts before scaling further]
17. Workflow 10 - subagent/session lifecycle reliability review [runtime/control-surface pass; includes stale completion-state and run-ledger hardening]
18. Workflow 11 - coverage admission model [do not relitigate Workflow 6; operationalize per-ticker intake / promotion procedure and execution-lane admission gates instead]
19. Workflow 12 - macro / policy trust repair [close or explicitly own the remaining macro/policy and timing-trust manual-dependency debt]

Entry-log rule:
- keep new workflow entries in this exact order unless a higher-priority trust blocker overtakes them
- if the order changes, update this queue first so downstream continuity notes do not drift

## Capacity rule for this queue

At one time:
- 1 active OpenClaw subagent implementation lane
- 1 active Claude review lane
- 0 or 1 cheap helper lane

Do not open multiple OpenClaw subagent cleanup lanes at once until this queue proves clean.

## Candidate first real tasks

Best first pilot candidates:
1. operator playbook dedupe / drift scan
2. routing-note consistency scan across model playbooks
3. continuity/control-surface cleanup recommendation pass
4. post-rotation token-cleanup checklist packaging

## Promotion rule

If the same parallel pattern works cleanly at least a few times, then:
- promote it into a tighter playbook update
- and only then decide whether it deserves a dedicated orchestration skill

Do not create the skill first and hope the workflow appears later.
