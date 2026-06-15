# OpenClaw Parallel Work Plan

## Purpose

Turn the newly available local resources into controlled parallel execution instead of ad hoc model enthusiasm.

This plan is for using:
- the main OpenClaw session
- spawned OpenClaw subagents
- Claude CLI
- Gemini Flash
- external research lanes

without creating ownership drift, fake green states, or reconciliation debt.

## Current verified resource posture

### Keep stable
- OpenClaw main session posture: live truth surface, workspace-file truth interpreter, orchestrator, QC owner, and final integrator
- OpenClaw spawned subagent default for substantial workspace work: use the approved `openai/*` Codex-runtime model set with role-based thinking rather than blanket high effort
- OpenClaw app/runtime pinned at `2026.5.4` because Randall accepted `2026.5.4` as the current stable runtime on this machine

### Lower-complexity helper posture
- Lower-complexity helper work should usually use tighter scope and lower thinking, not a lower-trust model.
- Keep Veritas-routed helper work inside the approved `openai/*` Codex-runtime model set unless Randall intentionally changes runtime policy.

`openai-codex/gpt-5.3-codex` and `openai-codex/gpt-5.3-codex-spark` are removed from Veritas-routed workflow use. Randall may still use lighter external tools manually and report findings back as evidence for review.

### Available local lanes
- **Main OpenClaw session** -> orchestration, handoff packets, QC, final judgment, verified quick fixes, final integration
- **Spawned OpenClaw subagents** -> bounded detached workspace tasks with explicit contracts
- **Claude CLI** -> judgment-heavy review, contract definition, cross-artifact synthesis, high-coherence cleanup
- **Gemini Flash** -> cheap bounded audit, contradiction checks, narrow mechanical diagnosis
- **External research lane** -> low-cost web research intake when the work is evidence gathering rather than canonical judgment

## Core rule

Parallelism should be organized by **lane ownership**, not by "how many models can run at once."

One lane owns one bounded workstream at a time.
Veritas remains the only integrator across lanes.

Queue governance is part of orchestration, not admin overhead.
The workflow queue must be kept in sync with real findings, real blockers, and real prerequisites as chains advance.
Use `06. Playbooks/Automation Orchestration Protocol.md` as the control note for queue freshness, category labels, and parallel-posture decisions.
Use `06. Playbooks/Spawn and Closeout Governance Matrix.md` when deciding whether helper lanes are read-only, distinct-output, or blocked.
Use `06. Playbooks/Skills Governance Index.md` to keep the skill layer auditable instead of letting lane guidance drift inside skills alone.

## Queue freshness and category model

Every active or near-term queued item should stay fresh enough to delegate without reconstructing chat context.

Minimum fields to keep clear:
- status
- owner
- next pass
- blocker if any
- category
- parallel posture

Default category set:
- control plane / automation
- research
- audit / QA
- workbook / packaging
- note-sync / reconciliation
- runtime / infrastructure

Default parallel posture labels:
- serial
- parallel-safe (read-only)
- parallel-safe (distinct outputs)
- blocked / operator-gated

If category or posture is unclear, default back to serial until the contract is clean.

## Default operating mode

As of the 2026-06-12 WF73 shadow-pilot stress pass, default implementation posture is **parallel-by-default when lane contracts are clean**:
- Veritas acts as product owner/manager (PoM), orchestrator, auditor/QA owner, and executive integrator.
- Main session handles blocker classification, lane leasing, shared-surface edits, skill governance, and final synthesis.
- Helper lanes run in parallel only when outputs are disjoint, `allowed_writes` are exact, and the lane register validates cleanly.
- Each helper produces a proof artifact or blocks cleanly; helpers do not mutate shared continuity, startup files, skills, finance canon, portfolio, config/runtime, or execution surfaces unless separately leased.
- Veritas integrates helper outputs before any shared-surface update, owner-facing claim, or next queue promotion.
- Fall back to serial when write surfaces overlap, authority boundaries are ambiguous, or the next action needs owner judgment.

As of the 2026-06-13 autonomous-paper posture pass, new parallel lanes should default to **implementation slices**, not QA/audit-only lanes. Use QA, audit, challenger, or contradiction lanes after a slice lands, after trust is disputed, or when Randall explicitly asks. Do not re-lease completed helper candidates from stale recommender output; refresh the PM packet and recommender after material state changes, then select a PM/WF next-action slice with exact write ownership.

For the current WF85/WF86/WF87 work, "autonomous trading" means scoped autonomous **paper** readiness only. Phase A hardening is already built; the critical path is clean shadow-decision/session accrual, GET-only reconciliation maturity, daylight/stale-gate clearance, fresh WF67 guard/kill-switch proof, and Randall exact approval. Parallel work should make that bottleneck visible and feed it higher-quality decisions, not pretend code can skip the empirical maturity gates.

WF73 shadow-pilot telemetry is the operating speedometer: if lane-register shadow refresh stays comfortably under a few hundred milliseconds and validation is clean, parallel implementation may continue. If overhead or collision warnings rise, reduce active lanes before adding infrastructure.

Default worker posture:
- Veritas main session = live truth surface, workspace-file truth interpreter, orchestration, QC, and final integration
- spawned OpenClaw helper = file-grounded bounded lane with thinking selected by role: low for routine research/read-only audit, medium for implementation, high for hard debugging or high-stakes trust adjudication
- Claude = standby escalation or second-opinion judgment lane, not default labor
- Gemini Flash / cheaper lanes = standby bounded audit or contradiction helpers only

## Lane model

### Lane 0 — Veritas main session
Owner:
- Veritas

Owns:
- project selection
- task decomposition
- continuity updates
- approvals
- cross-lane reconciliation
- verified quick fixes after worker/auditor evidence
- final integration and next-step decisions

Never delegate away:
- trust adjudication
- canonical conflict resolution
- final portfolio or OS judgment
- final closeout decision

### Lane 1 — OpenClaw subagent implementation lane
Best use:
- bounded workspace-local implementation
- file inspection across many artifacts
- reversible refactors
- validator or script scaffolding
- mechanical cleanup once the contract is fixed

Guardrails:
- one bounded deliverable per spawn
- no silent canonical note rewrites
- prefer read/inspect first, patch second
- use when the main session should stay clean
- default thinking medium for implementation; escalate to high only for hard debugging, repeated failures, or ambiguous shared-contract drift

### Lane 2 — Claude judgment lane
Best use:
- contract-definition passes
- difficult review/audit passes
- coherence-heavy HTML / presentation cleanup
- deployment-readiness reasoning
- hard cross-artifact synthesis

Guardrails:
- use for judgment, not busywork
- escalate to Opus only when the incremental quality really matters
- require a continuity note or explicit context packet for non-trivial passes

### Lane 3 — Gemini Flash cheap audit lane
Best use:
- narrow contradiction checks
- file-level diagnosis
- bounded audit or cleanup suggestions
- cheap second-pass verification on already-defined contracts

Guardrails:
- do not use as the first-pass strategic synthesizer
- do not let Flash define architecture
- use only when the contract and current state are pinned down

### Lane 4 — External evidence lane
Best use:
- web research
- competitor scans
- event / policy / thesis challenge intake

Guardrails:
- evidence only, not canonical truth
- save outputs in a reviewable format
- Veritas must review before promotion

## Concurrency cap

### Now
Run at most:
- **1 main Veritas lane**
- **2 meaningful parallel execution lanes**
- **0-1 manual helper inputs reported back by Randall**

Practical cap right now:
- Main OpenClaw
- plus one serious implementation lane
- plus one serious judgment lane
- plus optional manual helper findings supplied back by Randall

That is enough to gain leverage without blowing up synthesis cost.

### Later
Only expand beyond this when:
- the IC registry is staying current
- continuity notes stay short and clean
- handoffs are getting shorter, not longer
- lanes stop stepping on the same artifact family

## Ownership rules

### Safe parallel splits
Good split examples:
- subagent -> validator implementation
- Claude -> review the validator contract
- Gemini Flash -> bounded contradiction audit on artifacts produced by that validator

Also good:
- subagent -> workspace inventory / comparison pass
- Claude -> deployment-readiness reasoning pass on separate notes/artifacts

### Unsafe splits
Do not run in parallel:
- two writers on the same canonical note
- one lane redefining semantics while another updates dependent surfaces
- multiple lanes silently interpreting the same trust state differently
- cheap lanes making final calls on ambiguous or stale state

## Default work allocation by task shape

| Task shape | Best first lane | Second lane | Notes |
|---|---|---|---|
| multi-file workspace implementation | OpenClaw subagent | Claude review | keep contract fixed first |
| judgment-heavy audit | Claude | Gemini Flash for bounded follow-up | Flash only after the frame is clear |
| workspace inventory / drift scan | OpenClaw subagent | Main Veritas | cheap and clean detached work |
| contradiction or freshness check | Gemini Flash | Main Veritas | narrow only |
| external research intake | external lane | Main Veritas | never self-promoting |
| canonical-state reconciliation | Main Veritas | Claude review | keep ownership tight |

## Parallel project packaging rule

Any non-trivial parallel project should have:
- one continuity note
- one chain log if multi-pass
- one named owner
- one current phase
- one next pass
- one registry row when active long enough to matter

If the project is too small to justify that structure, it is probably small enough for Veritas to do directly or for one short subagent run.

## Required handoff packet for spawned lanes

Before any non-trivial spawned lane begins, pass a compact file-grounded packet.

Pre-spawn / pre-parallel route:
1. Check the lane register with `python scripts\concurrent_lane_manager.py --status --write --validate`.
2. Refresh PM operator visibility with `python scripts\parallel_operator_visibility.py --write --validate`.
3. Launch helpers only after active lanes, write leases, and PM blocker/readiness signals are clear.

Canonical rule source:
- `06. Playbooks/Spawn and Closeout Governance Matrix.md` owns spawn classification, runtime-budget, artifact-first, early-checkpoint, and closeout authority rules.
- `06. Playbooks/Subagent Spawn Handoff Template.md` owns the copyable packet structure.

This work plan should not duplicate the full checklist; use it only to remind the operator that spawned lanes must start from files, not hidden chat reconstruction.

Do not assume the child can reconstruct critical state from memory recall or vague chat history.
If the project already has a continuity note, use it as the anchor.

Do not launch broad inventory/audit work under the implicit default timeout. Either split the task or set a deliberate runtime budget before spawning.

## Resume-keyword fallback for continuity lanes

In local webchat / Control UI work, do not assume a thread-bound persistent subagent session is available.
When persistent session binding is unavailable:
- keep the continuity note current
- assign a stable resume keyword or label
- treat the keyword as a launcher for a fresh bounded run against the continuity note and control files
- do not pretend a live resumable worker still exists when it does not

## Swarm rule

Three-agent swarms are allowed only when all are true:
- the work is read-heavy, audit-heavy, or review-heavy
- one main-session integrator owns synthesis
- each child has a distinct role
- no child is mutating the same artifact family as another
- the value of parallel evidence is higher than the merge cost

If those conditions are not true, stay with one serious worker plus one reviewer/helper at most.

For the current research automation lane, parallel help should default to contract-building, contradiction review, and QA rather than freeform research synthesis.

## Current recommended rollout

### Implementation slices first
Use parallelism for bounded implementation slices, not broad swarms or stale QA re-runs.

Current priority pattern:
1. Finish any active leased lane and integrate proof before opening overlapping work.
2. Refresh `pm_control_packet.py --write --write-db --validate`, `concurrent_lane_manager.py --status --write --validate`, and `parallel_operator_visibility.py --write --validate`.
3. Pick 3-4 disjoint implementation slices from PM/WF next actions only when write leases are exact.
4. Prefer slices that advance the unified paper-autonomy OS: WF85 decision freshness, WF78 feeder handoff, WF79 command visibility, WF86/WF87 maturity/command rollups, WF76 cron selectivity, WF71 helper templates, or WF69 probability-language blockers.
5. Use QA/audit lanes only after those slices land or when trust state is uncertain.

For the autonomous-paper OS, the practical rollout is wide-to-narrow:
- Phase 0/1: parallel implementation slices that feed or expose the shadow/reconciliation loop.
- Phase 2: merge WF86/WF87 hardening validation around real shadow data.
- Phase 3: single main-session readiness synthesis and owner gate. Green readiness is not execution approval.

## Historical rollout baseline

The section below is retained as history for the original delegation pilot. Use the current implementation-slices-first rollout above for active WF/P1/WF85-WF87 work.

### Phase 1 — prove clean delegation
Use parallelism for bounded helper work, not broad swarms.

Targets:
1. use spawned OpenClaw subagents for workspace-local inspection and mechanical prep
2. keep Claude as the judgment escalation lane
3. use Gemini Flash only for cheap bounded verification
4. keep Veritas main as sole integrator

Success condition:
- shorter completion time without more reconciliation debt

### Phase 2 — standardize recurring split patterns
Once Phase 1 feels clean, standardize a few recurring pairings:
- **Subagent + Claude** for implementation plus judgment review
- **Subagent + Gemini Flash** for implementation plus cheap bounded audit
- **Claude + Gemini Flash** for judgment plus cheap contradiction check

Success condition:
- reusable kickoff packets and fewer hand-built prompts

### Phase 3 — promote stable patterns into operating files or skills
Only after repeated success:
- add or refine skills
- formalize a project intake checklist
- possibly expand the IC project registry posture

Success condition:
- repeatable gains, not just one good day

## Near-term pilot plan

### Pilot A — OpenClaw local parallel execution
Goal:
- prove that spawned OpenClaw subagents can take real bounded work cleanly

Test tasks:
- inventory or compare artifact sets
- draft validator candidates
- perform multi-file read-only audits
- prepare exact patch candidates without applying them

### Pilot B — two-lane judgment + implementation split
Goal:
- let one lane build while another reviews

Pattern:
- subagent performs bounded implementation or inspection
- Claude performs contract or risk review on a separate artifact packet
- Veritas integrates

### Pilot C — cheap verification lane
Goal:
- use Gemini Flash only where it saves time without taking on judgment risk

Pattern:
- Flash checks a narrow contradiction, missing-file, or consistency question after the main contract is already fixed

Do not use Codex Spark as a Veritas-routed workflow lane here. If Randall wants Spark input, treat it as manual evidence intake rather than an orchestrated lane.

## What should not happen yet

Do not yet:
- run four serious lanes on one fragile workstream
- let cheap models own architecture
- open many active registry projects just because capacity exists
- formalize a research unit before OS integrity and deployment-readiness lanes are cleaner

## Queue governance protocol

When advancing a chain:
1. update the queue first if a new blocker, prerequisite, or hardening item is proven
2. lock workflow order unless a higher-priority trust issue overtakes it
3. add real residue as an explicit later workflow or continuity note instead of leaving it in chat history
4. do not widen implementation scope mid-chain without updating the queue entry and contract
5. treat queue maintenance as part of the orchestration protocol, not optional cleanup
6. once a workflow is approved and active, continue sequentially until that workflow is complete unless a real blocker, user reprioritization, or higher-priority trust/safety issue interrupts it

This keeps the queue stable enough to trust while still allowing evidence-driven adjustments.

## Secure spawn rule for the day-job lane

For the daily queue/orchestration control plane:
- low-effort control-plane fixes stay in the main session
- medium-effort detached work should use an approved live default model with a tighter scope rather than a removed cheap helper model
- substantial or high-effort detached work uses `openai/gpt-5.5` through the Codex runtime with high-thinking posture after preflight review clears the contract
- default detached posture is one worker at a time, bounded task, no silent canonical finance note mutation, and no auth/config/network escalation without approval
- if the blocker is judgment rather than labor, stop and record the blocker instead of spawning theater

## Next concrete moves

1. keep the main session as live truth surface, orchestrator, QC owner, and final integrator
2. use spawned `openai/gpt-5.5` Codex-runtime high-thinking subagents for substantial bounded workspace work when available
3. reserve Claude for contract/judgment-heavy reviews
4. use Gemini Flash only as a cheap bounded audit helper
5. keep active serious parallel load capped at two substantive lanes plus one helper lane
6. follow the live active queue in `06. Playbooks/OpenClaw Parallel Pilot Queue.md`; current post-WF39 baseline is WF38 active/resumed, WF37 paused follow-up, then SOP / automation optimization backlog only when approved
7. use the orchestration control-plane cron only for queue/registry/continuity stewardship, preflight QA, next-step adjudication, and hardening insertion when the queue item is not truthfully automation-ready — not for silent canonical finance note rewrites
8. if a split pattern repeats cleanly, promote it into a skill or playbook update

## Success test

This plan is working if:
- throughput rises
- the user sees more finished passes, not more partial chatter
- trust state stays clearer, not blurrier
- continuity notes get thinner, not fatter
- Veritas spends more time integrating and less time reconstructing what each lane did
