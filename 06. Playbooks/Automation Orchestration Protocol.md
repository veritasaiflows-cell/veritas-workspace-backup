# Automation Orchestration Protocol

## Purpose
Keep the project queue moving, fresh, and honestly categorized while using parallel lanes only where ownership boundaries are clear.

This protocol promotes the live operating posture into a first-class control document.

For major workflow structure, pair this document with `06. Playbooks/Major Workflow Contract Standard.md`.
For spawn / closeout governance, pair it with `06. Playbooks/Spawn and Closeout Governance Matrix.md`.
For closeout artifacts, pair it with `06. Playbooks/Workflow Closeout Artifact Standard.md`.

## Core role posture
Veritas remains the:
- orchestrator
- auditor / QA owner
- product owner / manager (PoM)
- final integrator

Claude CLI, Gemini Flash, OpenClaw subagents, and other helper lanes are support lanes.
They do not own final queue state, final judgment, or canonical conflict resolution. Prioritize OpenClaw subagents. 

## Main-lane reserve rule
When an approved workflow is being advanced, default to a spawned sub-session for the working pass.

The main session should remain available as the:
- PM / orchestrator
- QA/QC owner
- executive manager
- final integrator

Child lanes should do the bounded implementation, inspection, or draft-prep work.
The main lane should do the handoff packet, scope control, live control-plane updates, QC judgment, and queue movement.

For early automation lanes, default helper scope is contract-building, audit / QA, contradiction review, or distinct-output prep unless a workflow contract explicitly widens authority.

The canonical spawn decision source is `06. Playbooks/Spawn and Closeout Governance Matrix.md`.
This document keeps the orchestration posture, not a competing spawn standard.

Main-session exceptions are allowed only when one of these is true:
- the edit is trivial and bounded
- an emergency truth fix is needed immediately
- the work is the final merge / QC step
- spawning would add more friction than value

If the main session takes one of those exceptions on a meaningful workflow pass, say so explicitly in the continuity note or status summary.

## Queue freshness rule
The active project queue must stay fresh enough that the next move is visible without reconstructing chat history.

At minimum, each active or near-term queued item should make clear:
- current status
- current owner
- next pass
- blocker if any
- category
- parallel posture
- execution mode
- QC complete

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

### Gemini Pro (preferred IC lane)
Primary contractor lane for implementation-heavy and broad research passes.
Best for:
- script/code passes
- bounded implementation drafts
- broad research sweeps with explicit output contracts
- first-pass verification when judgment stakes are moderate

### Claude CLI (hard-judgment lane)
Use for harder judgment-heavy work and high-stakes challenge passes.
Best for:
- trust/contract adjudication
- synthesis stress-testing
- second-opinion pushback on major decisions
- high-risk reasoning where false-green risk is high

Effort posture:
- hard judgment/trust work: run Claude with higher effort (`--effort high` or above)
- routine bounded checks: keep effort lower and prompts tighter
- Gemini CLI has no direct effort flag in this environment; adjust effort by task scope, model choice, and prompt depth

## IC runtime fallback rule
When a preferred contractor lane is unavailable, fail over fast instead of stalling the chain.

Fallback order:
1. preferred ACP harness lane (Claude/Gemini)
2. local CLI lane (`claude -p ...` / `gemini -p ...`)
3. OpenClaw spawned subagent with the same bounded decision contract

Rules:
- retry ACP once or twice only, then downgrade
- keep the same scope/contract across fallback lanes
- record the fallback decision and reason in continuity
- treat provider-capacity errors (429/resource exhausted) as lane-availability failures, not as final decision evidence

## IC completion handshake rule
For any multi-lane decision pass, track expected completions explicitly and close only after all expected lanes are done or intentionally abandoned.

Minimum handshake:
- define expected lanes up front (for example: spawned pass + shell CLI)
- if one lane finishes first, hold final synthesis until the other lane completes or is formally timed out/canceled
- once all expected lanes are resolved, publish one combined decision summary immediately

Do not leave completed lane output waiting unintegrated.

## Runtime proof rule
Runtime/session state is advisory until it earns boring consistency.

## Machine-readable automation trust-block pilot
Workflow 29 Phase 4 adds one bounded producer/consumer path for cron-facing automation trust.

Producer:
- `scripts/automation_trust_block.py`
- source posture still comes from `automation-hardening-manager` judgment
- output becomes the normalized machine-readable artifact at `tmp/automation-trust-block.json`

Consumer:
- `scripts/cron_trust_block_consumer.py`
- read rule is intentionally narrow: fail closed unless the trust block is explicitly `status=ok`, workflow-matched when required, and limited to `read_only`

Scope boundary:
- this pilot is only for machine-readable approval of already-bounded read-only automation posture
- it does not grant canonical note mutation, destructive apply rights, or general scheduler autonomy
- missing trust block, invalid shape, non-ok status, or non-read-only posture must all stop the automation path instead of letting cron infer safety

Do not treat any of these alone as completion proof:
- a child/session looking finished in the control surface
- an async exec event with only exit code or terminal fragments
- a run summary whose raw chain state is still mid-finalizer
- a helper command that crossed an interactive auth boundary without explicit reconciliation

Completion proof should prefer:
1. required artifact existence
2. explicit owner-surface state
3. normalized run-summary state when the normalization rule is documented
4. runtime/session state as supporting evidence only

## Queue movement rule
Keep momentum without theater.

On each real control-plane pass:
1. confirm the active item is still the real active item
2. confirm the next pass is still the real next pass
3. refresh category or parallel posture if reality changed
4. close completed items honestly
5. do not open more lanes unless the merge value is real

## Status reply contract
When Randall asks for status, reply from the live control surfaces, not vague memory.

At minimum, include:
- current active project or workflow
- current phase or status
- next item on the approved queue
- next concrete action
- blocker or trust limit, if one exists

If a meaningful state change happened recently, include it briefly.
Do not answer status requests with a generic progress vibe.

## Sequential auto-start rule
When a queued project chain has already been approved, do not stop at local closure theater.

After final QC says the current project is honestly complete:
1. mark the completed item closed in the queue, registry, and continuity note
2. promote the next approved item immediately
3. record the first concrete next action for that next item
4. continue the chain unless a real blocker, human gate, or higher-priority trust issue interrupts it

If the chain has an explicit higher-level goal, keep advancing until that goal or a real stop line is reached.

Current live example:
- the trust-hardening / note-sync chain should keep moving after each final QC pass until the finance notes are truth-synced and the dashboard/workbook surfaces are linked to trustworthy fresh artifacts strongly enough to use as real operator surfaces

## Spawn-first workflow advancement rule
For approved sequential workflow chains:
1. main session confirms the active item and next bounded pass
2. main session prepares the handoff packet
3. spawned sub-session performs the working pass
4. main session audits/QCs the result
5. queue/registry surfaces record the current `execution mode` and `QC complete` state
6. only then may the queue advance or the next spawned pass open

If that execution/QC chain is not visible on the live control surfaces, treat the workflow as not yet advanced.

This keeps the main lane free for QA/QC and prevents it from getting trapped as the implementation lane by default.

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

Default expectation for meaningful workflow orchestration work:
- QC/QA and closeout audit should be performed by an **independent auditor** spawned in a **fresh new session**
- the audit lane should be read-only and file-grounded
- the audit should return: closure verdict, acceptance-proof check, gaps/residue, reopen triggers, and next-work recommendations

Do not let the implementation lane grade its own closeout unless an explicit exception is recorded.

## Executive-summary gate
For any meaningful workflow, do not issue an executive summary until all are true:
- acceptance evidence exists
- expected helper lanes are integrated or explicitly abandoned
- the independent spawned audit is integrated or an explicit exception is recorded
- queue / registry / continuity note agree on state
- checkpoint decision is explicit
- real residual debt is named

If one of those is missing, give status instead of closure theater.

## Current operating decision
- Veritas remains the orchestrator, auditor, and PoM.
- Claude CLI and Gemini Flash are on standby for parallel work, not primary ownership.
- Queue movement should stay category-driven and trust-gated.
- Research, audit, and workbook lanes are the first parallel categories to use when the contract is clean.
- Status replies must name the current project and the next queued item explicitly.
- Final QC should trigger immediate promotion of the next approved project instead of leaving the chain idle.
