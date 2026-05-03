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
- OpenClaw main session on `openai-codex/gpt-5.5`
- OpenClaw spawned subagent default on `openai-codex/gpt-5.4`
- OpenClaw app/runtime pinned at `2026.4.22` for now because Randall judges it more stable on this machine

### Lower-complexity Codex helpers now available
- `openai-codex/gpt-5.3-codex`
- `openai-codex/gpt-5.3-codex-spark`

Use these as helper lanes for bounded implementation or inspection work, not as the final lane for trust-heavy judgment.

### Available local lanes
- **Main OpenClaw session** -> orchestration, integration, final judgment, file-grounded execution
- **Spawned OpenClaw subagents** -> bounded detached workspace tasks with explicit contracts
- **Claude CLI** -> judgment-heavy review, contract definition, cross-artifact synthesis, high-coherence cleanup
- **Gemini Flash** -> cheap bounded audit, contradiction checks, narrow mechanical diagnosis
- **External research lane** -> low-cost web research intake when the work is evidence gathering rather than canonical judgment

## Core rule

Parallelism should be organized by **lane ownership**, not by "how many models can run at once."

One lane owns one bounded workstream at a time.
Veritas remains the only integrator across lanes.

## Default operating mode

Default to **sequential orchestration**:
- Veritas acts as product manager, orchestrator, QA, and executive integrator
- spawned lanes do bounded execution against an explicit contract
- Veritas reviews the result before opening the next lane
- only open a second active lane when it clearly beats the merge cost

Default worker posture:
- `openai-codex/gpt-5.5` = main-session orchestration and highest-trust integrator lane
- `openai-codex/gpt-5.4` = first-choice high-trust spawned worker lane
- Claude = escalation or second-opinion judgment lane, not default labor
- Gemini Flash / cheaper lanes = bounded audit or contradiction helpers only

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
- final integration and next-step decisions

Never delegate away:
- trust adjudication
- canonical conflict resolution
- final portfolio or OS judgment

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
- **1 cheap helper/audit lane**

Practical cap right now:
- Main OpenClaw
- plus one serious implementation lane
- plus one serious judgment lane
- plus optional cheap audit helper

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

## Current recommended rollout

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

## What should not happen yet

Do not yet:
- run four serious lanes on one fragile workstream
- let cheap models own architecture
- open many active registry projects just because capacity exists
- formalize a research unit before OS integrity and deployment-readiness lanes are cleaner

## Next concrete moves

1. keep the main session as orchestrator and final integrator
2. start using spawned OpenClaw subagents for bounded workspace work immediately
3. reserve Claude for contract/judgment-heavy reviews
4. use Gemini Flash only as a cheap bounded audit helper
5. keep active serious parallel load capped at two substantive lanes plus one helper lane
6. if a split pattern repeats cleanly, promote it into a skill or playbook update

## Success test

This plan is working if:
- throughput rises
- the user sees more finished passes, not more partial chatter
- trust state stays clearer, not blurrier
- continuity notes get thinner, not fatter
- Veritas spends more time integrating and less time reconstructing what each lane did
