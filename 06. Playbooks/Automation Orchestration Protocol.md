# Automation Orchestration Protocol

## Purpose
Keep the project queue moving, fresh, and honestly categorized while using parallel lanes only where ownership boundaries are clear.

This protocol promotes the live operating posture into a first-class control document.

For major workflow structure, pair this document with `06. Playbooks/Major Workflow Contract Standard.md`.
For long or multi-surface implementation, pair this document with `skills/disciplined-implementation/SKILL.md`.
For spawn / closeout governance, pair it with `06. Playbooks/Spawn and Closeout Governance Matrix.md`.
For closeout artifacts, pair it with `06. Playbooks/Workflow Closeout Artifact Standard.md`.

## Core role posture
Veritas main session is Randall's live financial truth surface: it reads the workspace file layer as the durable canonical financial database, reconciles owner notes, artifacts, market evidence, and queue state, and makes final judgment traceable.

Veritas remains the:
- orchestrator
- auditor / QA owner
- product owner / manager (PoM)
- final integrator

Claude CLI, Gemini Flash, OpenClaw subagents, and other helper lanes are support lanes.
They do not own final queue state, final judgment, or canonical conflict resolution. `scripts/project_implementation_router.py` and `veritas.execution_efficiency_policy.v1` own implementation route selection. Use model-free proof first; explicit bounded Codex-native Terra only when eligible; Main/Terra is the default integrator route; Main/Sol is permitted only as an explicit escalation, challenger, or QA exception; otherwise persistent Terra requires fresh strict transport proof. Missing transport does not authorize silent Main fallback.

## Main-lane reserve rule
When an approved workflow is being advanced, route before spawning. Use deterministic/model-free execution where possible. Use one file-grounded helper when a distinct bounded deliverable justifies the overhead; use multiple helpers only for genuinely independent outputs. Main may own quick bounded fixes, final integration, and authority-sensitive judgment, but is not the implicit implementation fallback.

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
- the work is quick, reversible, and bounded enough to stay under roughly five minutes
- an emergency truth fix is needed immediately
- the work is the final merge / QC step
- the work is a coordinating validator or spawn-contract repair where helper context overhead is the bottleneck
- spawning would add more friction than value

If the main session takes one of those exceptions on a meaningful workflow pass, say so explicitly in the continuity note or status summary.

## Helper-completion continuation rule

When a helper lane finishes, Veritas/main must not treat the event as an endpoint by default.

Required sequence:
1. integrate the helper output and verify it against live files, artifacts, or control surfaces
2. check the live queue / registry / continuity note for the next approved action
3. decide whether another role-appropriate helper lane can safely move the queue, whether the main session should execute the next quick bounded task, or whether the chain is blocked on human judgment
4. continue until the active workflow is complete, blocked, or ambiguous enough to require Randall's direction
5. if priority, authority, or next action is ambiguous, ask the smallest concrete question before moving the queue

Do not spawn continuation work just to look busy. The next lane must have a clear owner, deliverable, stop line, and acceptance check.

## Reuse-before-new-script gate

Before creating a new script, helper lane, validator, dashboard surface, or workflow artifact family, the lane must explicitly check whether an existing command, helper module, validator, chain step, skill, or owner surface can be extended safely.

Default order:
1. reuse an existing CLI/script as-is when it already covers the need
2. extend an existing helper/module when behavior is compatible and validators can prove no drift
3. add a thin wrapper around an existing stable command when the user-facing contract must stay stable
4. create a new script only when reuse would create unsafe coupling, two-writer risk, authority ambiguity, or excessive regression risk

When a new script is justified, the lane must state:
- what existing scripts/helpers were checked
- why extension was rejected or deferred
- whether the new script is intended as prototype, wrapper, validator, production entrypoint, or temporary proof
- which owner department owns it
- how it will be consolidated, migrated, or archived after proof

For proof-first work, isolated scripts are allowed to reduce blast radius. But proof scripts must not become permanent by default. Once the proof is green, the next workflow step should consider migration into a shared module, stable CLI wrapper, declarative registry, or archive-candidate review.

This rule is especially strict for finance automation, canon/portfolio maintenance, WF67 paper execution, WF68 alerting, WF70 official-source capture, and dashboard/Today-card surfaces. Never flatten by merging high-authority guardrails into generic helpers unless validators prove authority boundaries remain intact.

## Queue freshness rule
The active project queue must stay fresh enough that the next move is visible without reconstructing chat history.

For generated artifact/proof awareness, use the SQL cockpit as the first routing layer before broad `tmp/` scans: `scripts/artifact_index.py cockpit`, `ticker-cockpit`, `trust-cockpit`, `proof-field`, `stoplines`, and `validate`. SQL cockpit output may route work, expose provenance, and flag authority boundaries, but it remains derived proof/index/staging only. Inspect the target artifact or canonical owner note before making content claims, queue moves, finance judgments, or any gated apply decision.

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

## Execution route and lane roles

`scripts/project_implementation_router.py` is the single route-policy owner. Run it before material implementation and consume the selected backend/model/thinking contract; provider labels elsewhere are descriptive only.

Route order:
1. explicit deterministic command plus proof -> `model_free_command`
2. explicitly eligible bounded read-only or one-file leased task -> Codex-native Terra low/medium, only when the spawn capability proof exposes exact model, thinking, backend, and `fork_turns=none`
3. explicit quick fix, final integration, or authority-sensitive judgment -> Main/Terra; use Main/Sol only when the route carries an explicit `escalation`, `challenger`, or `qa` use case and reason
4. other bounded helper work -> persistent Terra only with fresh strict context-transport proof

Missing capability/transport proof blocks dispatch. Never convert it into a silent Main/Terra or Main/Sol fallback. Sol is a named escalation/challenger/QA path, not a default or helper fallback. Manual Claude/Gemini/challenger work is evidence-only and requires Randall's choice; it never rewrites the selected default route.

Main owns selection, queue movement, QC, acceptance, integration, and final judgment. Helpers own only leased bounded deliverables. Actual backend/model/thinking and authoritative usage or a controlled unavailable reason must be recorded at closeout; mismatch blocks acceptance.

Effort follows scope: low for bounded read-only checks, medium for narrow implementation, high only for broad ambiguity or material trust/security/finance adjudication. Compare like-for-like Main-accepted cohorts; require at least 10 comparable jobs before reviewing a default change; automatic ranking/promotion remains disabled.

Resource rules: bounded handoff, `fork_turns=none`, fork-baseline-aware usage, per-lane token/replay/tool/time ceilings, and early incident stop. One repair plus one fresh QA rerun is the normal loop; another rejection returns to Main for scope reduction.

## IC completion handshake rule
For any multi-lane decision pass, track expected completions explicitly and close only after all expected lanes are done or intentionally abandoned.

Minimum handshake:
- define expected lanes up front (for example: spawned pass + shell CLI)
- define required completion artifacts up front for each lane (`tmp/...worker.json/.md`, QA artifact, validator output, or an explicit `PARTIAL_BLOCKED` artifact)
- treat subagent announcement text as notification only; do not accept summary-only completion as proof
- if a lane compacts/resumes, require it to continue from durable artifacts and not announce `complete` unless the required artifacts exist and parse
- if one lane finishes first, hold final synthesis until the other lane completes or is formally timed out/canceled
- if QA finishes before the worker artifact exists, classify QA as baseline-only and require post-worker main verification or a targeted follow-up QA before final closeout
- once all expected lanes are resolved and artifact requirements are met, publish one combined decision summary immediately

Do not leave completed lane output waiting unintegrated. Do not label a compacted/resumed or artifact-missing worker as failed by assumption; classify it as `partial_unverified` until live artifacts/history prove success, partial completion, or failure.

## Runtime proof rule
Runtime/session state is advisory until it earns boring consistency.

## Shared-contract drift rule
When a workflow changes a shared state vocabulary, JSON contract, manifest shape, or trust/freshness field:
- inspect adjacent consumers, validators, ranking maps, fallback paths, and presentation adapters before calling the change closed
- regenerate or freshen the relevant proof artifacts before accepting QA conclusions
- treat stale fixtures and stale generated artifacts as a real false-red / false-green risk
- if SQL/index consumers depend on the changed contract, update their consumer notes or follow-up queue entry before widening use

Do not treat the first patched producer as sufficient proof that the contract change is actually integrated.

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

Spawn launch requirement:
- follow `06. Playbooks/Spawn and Closeout Governance Matrix.md` as the canonical spawn/closeout authority
- use `06. Playbooks/Subagent Spawn Handoff Template.md` for the copyable handoff packet
- do not duplicate spawn-budget rules here; if timeout, artifact-first, early-checkpoint, or closeout rules change, update the matrix/template first

Failure classification rule:
- **contract failure**: scope too broad, missing stop line, missing files-to-read-first, no partial artifact, or no timeout budget
- **runtime/tool failure**: provider/network/tool abort, approval blockage, missing binary, or process failure
- **worker-execution failure**: child ignored a clear bounded contract

Do not respond to a spawn timeout by simply relaunching the same broad prompt. Inspect the child history, classify the failure, and narrow or budget the next spawn.

## Workflow completion hardening rule
Validation follows the declared budget:
1. micro: deterministic proof plus Main verification
2. narrow: focused tests plus Main verification
3. shared/major, privacy/security/authority/finance semantics, or repeated failure: deterministic preflight, then one fresh independent auditor
4. one repair plus one fresh QA rerun is the normal loop; another rejection returns to Main for scope/root-cause reclassification rather than spawning another replay-heavy chain

The closeout chain must match the route and validation budget. Do not add worker and QA lanes merely to satisfy ceremony.

Main-session quick-fix boundary:
- allowed: tiny follow-up repairs, truth fixes, and final merge/QC edits
- not allowed: quietly absorbing the whole implementation pass back into the main lane without an explicit exception

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
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `06. Playbooks/Subagent Spawn Handoff Template.md`
- `tmp/veritas-status-card-frontdoor.json`; open the full status/future packet only through its hashed drilldown when material work requires it
- `tmp/wiki-bootstrap-proof.json`

`06. Playbooks/OpenClaw Parallel Work Plan.md` is historical planning evidence only and must not be loaded as current startup doctrine.

## QA rule
After a meaningful automation-protocol or queue-governance change:
- run a bounded QA or audit pass
- do not claim the new posture is ready merely because the wording sounds good
- verify the startup/governing files still point at the real posture

Default expectation for shared/major or risk-triggered workflow orchestration work:
- QC/QA and closeout audit should be performed by one **independent auditor** in a **fresh new session** after deterministic preflight
- the audit lane should be read-only, file-grounded, hash-frozen, and limited to the declared file/context budget
- the audit should return: closure verdict, acceptance-proof check, gaps/residue, reopen triggers, and next-work recommendations

Micro and narrow work may close with deterministic/focused proof plus Main verification when the declared budget and risk triggers support that lower-cost route.

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
- Queue movement stays route-selected, category-driven, trust-gated, and instrumented for actual usage/outcomes.
- Deterministic work is first; bounded Terra lanes are next; Main/Terra integrates by default; Main/Sol is an explicit escalation/challenger/QA exception, never a fallback.
- Status replies must name the current project and the next queued item explicitly.
- Final QC should trigger immediate promotion of the next approved project instead of leaving the chain idle.
