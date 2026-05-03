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

## Next orchestrated workflow queue

### Workflow 1 — Policy target-range fail-closed hardening
Status:
- ready now

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

### Workflow 2 — Broad residual atomic-write migration
Status:
- queued after Workflow 1

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

### Workflow 3 — External payload schema guards
Status:
- queued after Workflow 2

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

### Workflow 3B — Independent workspace QA audit and QA-pass skill creation
Status:
- queued immediately after Workflow 3 by user approval

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

### Workflow 3C — Canonical-note trust gate enforcement
Status:
- approved by user and opened on 2026-05-01
- queue updated, file inspection completed, preflight reviewer spawned
- currently paused pending session restart because the reviewer completion was not confirmed before handoff

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

### Workflow 4 — Sequential chain protocol
Status:
- queued after Workflow 3C

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

### Workflow 5 — PDF/Excel workflow-fit pass
Status:
- queued after trust-spine reassessment

Why now:
- only worth doing once the trust spine is less fragile
- otherwise packaging work outruns truth quality

Lane:
- Veritas main session plus bounded helper lanes if needed

Deliverable:
- define where PDF and Excel belong in the automation workflow
- decide what stays staging-only, what can be scheduled, and what remains operator-gated

Acceptance check:
- packaging role is clear and does not pretend trust we have not earned

### Workflow 6 — Coverage tier framework
Status:
- queued after PDF/Excel workflow-fit pass

Why now:
- scale should come from better coverage rules, not a random ticker pile
- the tracked universe needs explicit ownership and refresh rules before widening

Lane:
- Veritas main session

Deliverable:
- define coverage tiers such as daily, event-driven, watchlist-only, and bench/archive
- define admission, promotion, demotion, and freshness rules

Acceptance check:
- every tracked name can be assigned a clean tier with an explicit operating expectation

### Workflow 7 — Sector coverage expansion plan
Status:
- queued after coverage tier framework

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

### Workflow 8 — Command Center chain readiness review
Status:
- queued after sector coverage expansion plan

Why now:
- the Command Center should expand only after the trust spine and coverage model are strong enough to support it

Lane:
- Veritas main session with bounded reviewer support if needed

Deliverable:
- determine whether the Command Center should gain a dedicated chain phase
- define prerequisites, required inputs, and no-go conditions

Acceptance check:
- command-center expansion is sequenced behind truth, not ahead of it

### Workflow 9 — Research department operating model
Status:
- queued after command center chain readiness review

Why now:
- a department model only makes sense once trust, coverage tiers, and command-center ownership are clearer

Lane:
- Veritas main session

Deliverable:
- define functional desks, owned outputs, owned inputs, and refresh cadence
- avoid fake org-chart theater

Acceptance check:
- the model improves throughput and clarity without inventing bureaucracy

### Workflow 10 — Subagent/session lifecycle reliability review
Status:
- queued as a standing control-surface hardening item

Why now:
- workflow control cannot be trusted fully while subagent run state and session activity can disagree
- this came from a real failure, not a hypothetical concern

Lane:
- Veritas main session

Deliverable:
- document the observed subagent/session lifecycle inconsistency
- define operator workarounds and no-go assumptions for orchestration until the behavior is trusted
- decide whether a dedicated bug/hardening note should remain active in the queue

Acceptance check:
- orchestration protocol reflects the real control-surface limits instead of idealized assumptions

## Queue hardening rule

This queue is part of the orchestration protocol, not a scratchpad.

Hardening rules:
- lock the execution order unless a higher-priority trust blocker overtakes it
- when a real failure, blocker, or newly proven prerequisite appears, update this queue before opening the next major workflow
- prefer inserting new work as an explicit numbered workflow instead of burying it in chat context
- if a workflow finishes with material residue, capture that residue as a later queue item or a continuity note before moving on
- do not widen scope mid-chain without first updating the queue entry and phase contract

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
1. Workflow 1 — policy target-range fail-closed hardening
2. Workflow 2 — residual atomic-write migration
3. Workflow 3 — external payload schema guards
4. Workflow 3B — independent workspace QA audit and QA-pass skill creation
5. Workflow 3C — canonical-note trust gate enforcement
6. Workflow 4 — sequential chain protocol
7. Reassess trust grade
8. Workflow 5 — PDF/Excel workflow-fit pass
9. Workflow 6 — coverage tier framework
10. Workflow 7 — sector coverage expansion plan
11. Workflow 8 — command center chain readiness review
12. Workflow 9 — research department operating model
13. Workflow 10 — subagent/session lifecycle reliability review

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
