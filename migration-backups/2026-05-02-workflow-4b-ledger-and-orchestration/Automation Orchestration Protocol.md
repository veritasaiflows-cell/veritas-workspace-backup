# Automation Orchestration Protocol

## Purpose
Keep the project queue moving, fresh, and honestly categorized while using parallel lanes only where ownership boundaries are clear.

This protocol promotes the live operating posture into a first-class control document.

## Core role posture
Veritas remains the:
- orchestrator
- auditor / QA owner
- product owner / manager (PoM)
- final integrator

Claude CLI, Gemini Flash, OpenClaw subagents, and other helper lanes are support lanes.
They do not own final queue state, final judgment, or canonical conflict resolution.

## Queue freshness rule
The active project queue must stay fresh enough that the next move is visible without reconstructing chat history.

At minimum, each active or near-term queued item should make clear:
- current status
- current owner
- next pass
- blocker if any
- category
- parallel posture

If one of those becomes stale enough to misroute work, refresh it before spawning more labor.

## Category model
Use a small stable category set.

### 1. Control plane / automation
Examples:
- orchestration
- cron hardening
- trust-gate work
- queue / registry / continuity control

### 2. Research
Examples:
- thesis work
- company deep dives
- macro regime research
- sector coverage expansion

### 3. Audit / QA
Examples:
- workspace audits
- independent verification passes
- contradiction checks
- readiness reviews

### 4. Workbook / packaging
Examples:
- workbook structure
- PDF/report packaging
- presentation surfaces
- export contracts

### 5. Note-sync / reconciliation
Examples:
- canonical note truth-sync
- stale dashboard cleanup
- project note reconciliation

### 6. Runtime / infrastructure
Examples:
- OpenClaw runtime diagnosis
- skill-layer hardening
- startup posture audits
- config-path troubleshooting

Do not create category sprawl unless repeated work proves the need.

## Parallel posture labels
Every meaningful queued item should be treated as one of these:

### Serial
Must stay in the main line.
Use when:
- final judgment is central
- the artifact family is shared
- the contract is still ambiguous

### Parallel-safe (read-only)
Safe for helper lanes when the output is evidence, audit findings, or review.
Good examples:
- research scans
- contradiction checks
- bounded audits

### Parallel-safe (distinct outputs)
Safe when child lanes produce separate artifacts that do not compete for the same canonical surface.
Good examples:
- workbook packaging prep
- isolated report assets
- read-heavy comparison passes

### Blocked / operator-gated
Do not spawn labor yet.
Use when:
- human judgment is the blocker
- trust gates are unresolved
- auth/network/destructive actions would be needed

If posture is unclear, default to **Serial**.

## Parallel lane posture
### Veritas main lane
Owns:
- project selection
- queue movement
- categorization
- delegation decisions
- QA judgment
- synthesis and final decision

### OpenClaw subagents
Best for:
- bounded implementation
- file-grounded inspection
- mechanical prep
- isolated workspace execution

### Claude CLI
Standby judgment lane.
Best for:
- hard review
- synthesis
- contract definition
- second-opinion reasoning

### Gemini Flash
Standby audit lane.
Best for:
- cheap bounded verification
- contradiction checks
- narrow read-heavy audits after the contract is pinned down

## Queue movement rule
Keep momentum without theater.

On each real control-plane pass:
1. confirm the active item is still the real active item
2. confirm the next pass is still the real next pass
3. refresh category or parallel posture if reality changed
4. close completed items honestly
5. do not open more lanes unless the merge value is real

## Parallelization rule
Parallel work is justified only when all are true:
- the category is parallel-suitable
- the output ownership is distinct
- the handoff packet is explicit
- the merge cost is lower than the expected speed gain
- Veritas can still audit and integrate the result cleanly

Good candidates for parallel help:
- research
- audits / QA
- workbook / packaging prep
- bounded runtime diagnosis

Bad candidates for parallel help:
- two writers on the same canonical note
- unresolved trust adjudication
- ambiguous note-sync semantics
- queue movement based on vague context

## Startup posture rule
When automation or parallel-work governance is active, startup review should include:
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `06. Playbooks/OpenClaw Parallel Work Plan.md`

## QA rule
After a meaningful automation-protocol or queue-governance change:
- run a bounded QA or audit pass
- do not claim the new posture is ready merely because the wording sounds good
- verify the startup/governing files still point at the real posture

## Current operating decision
- Veritas remains the orchestrator, auditor, and PoM.
- Claude CLI and Gemini Flash are on standby for parallel work, not primary ownership.
- Queue movement should stay category-driven and trust-gated.
- Research, audit, and workbook lanes are the first parallel categories to use when the contract is clean.
