# Playbooks Redundancy Cleanup Plan

## Purpose
Remove avoidable redundancy from `06. Playbooks/` without breaking active links, queue state, or owner boundaries.

This is a **cleanup plan**, not permission for silent merging.

## Operating rule
When two notes overlap, prefer:
1. one live owner note
2. one supporting reference note if needed
3. explicit archive of retired predecessors

Do not merge doctrine just to reduce file count.

## Cluster map

### 1. Parallel / IC orchestration cluster
Files:
- `Automation Orchestration Protocol.md`
- `OpenClaw Parallel Pilot Queue.md`
- `IC Project Registry.md`
- `Independent Contractor Workflow.md`
- `Parallel IC Project Workflow.md`
- `OpenClaw Parallel Work Plan.md`
- `IC Model Routing Policy.md`
- `OpenClaw Model Deployment Plan.md`

Decision map:
- **Keep live owners:**
  - `Automation Orchestration Protocol.md`
  - `OpenClaw Parallel Pilot Queue.md`
  - `IC Project Registry.md`
- **Keep as supporting operator docs:**
  - `Independent Contractor Workflow.md`
  - `IC Model Routing Policy.md`
- **Needs review / likely archive-or-merge later:**
  - `Parallel IC Project Workflow.md`
  - `OpenClaw Parallel Work Plan.md`
  - `OpenClaw Model Deployment Plan.md`

Stop line:
- do not merge or archive this cluster until Workflow 10 is closed and the runtime/control-surface trust layer is boring enough to support route changes

### 2. Workbook / packaging cluster
Files:
- `Excel Operating Workbook Structure.md`
- `Minimum-Viable Workbook Schema.md`
- `Workbook Export Contracts.md`
- `Weekly Intelligence PDF Product Spec.md`
- `PDF Brief Standards.md`
- `External Model Report Template.md`

Decision map:
- **Keep live owner docs:**
  - `Workbook Export Contracts.md`
  - `PDF Brief Standards.md`
- **Move together when routing is intentionally revisited:**
  - workbook and packaging specs into one bounded specs/workbooks home
- **Do not semantically merge yet:**
  - leave structure/schema/spec distinctions visible until workbook workflow debt is actually reopened

Stop line:
- no broad workbook-doc merge inside Workflow 9B

### 3. Legacy predecessor / duplicate continuity cluster
Files:
- `Coverage Tier Framework.md`
- `Command Center Chain Readiness Review.md`
- `Excel Operating Workbook.md`
- numbered workflow successors already in `06. Playbooks/Project Continuity/`

Decision map:
- **Archive when unreferenced:** predecessor notes only
- **Keep while referenced:** any note still named by queue, registry, or active workflow
- **Do not archive active numbered workflow notes just because a later workflow exists**

Stop line:
- no move if active references remain

### 4. Prompt / model-ops cluster
Files:
- `Active Model Prompt Queue.md`
- `Model Prompt Operations.md`
- `GPT5 Research Prompt Pack.md`
- `Gemini Flash Prompt Pack.md`
- `Claude CLI Guardrails.md`
- `Gemini CLI Guardrails.md`
- `OpenClaw Model Deployment Plan.md`

Decision map:
- **Keep live owners:**
  - `Model Prompt Operations.md`
  - guardrail docs
- **Candidate bounded route later:**
  - prompt packs and prompt queue into a dedicated prompt-ops home if link churn is worth it
- **Do not move now:**
  - any file with active high-reference use across queue/continuity docs

Stop line:
- route only after the active workflow chain is closed or after references are rewritten in one bounded pass

## Safe immediate cleanup already completed
- archived safe unreferenced phase artifacts from `Project Continuity/` with backup first
- deferred high-reference routing moves to avoid fake cleanliness and link breakage

## Deferred execution gate
Reopen this plan for execution only when:
- Workflow 9B through Workflow 12 are closed
- queue/registry references are stable
- the move list is explicit
- validation and link checks are part of the same pass
- the work is being executed inside `06. Playbooks/Project Continuity/Workflow 19 - Playbooks Retrieval and Governance Cleanup.md` or another explicitly approved successor lane

## Acceptance for a future execution pass
- every moved file has a before/after map
- every archived file is unreferenced or intentionally re-linked
- queue/registry/active continuity notes remain accurate
- no semantic owner boundary gets blurred just to reduce note count
