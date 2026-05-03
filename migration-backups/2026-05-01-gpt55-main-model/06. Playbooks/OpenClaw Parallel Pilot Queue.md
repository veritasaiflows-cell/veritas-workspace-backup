# OpenClaw Parallel Pilot Queue

## Purpose

Define the first concrete pilot queue for using OpenClaw parallel resources deliberately.

This queue is not a wish list.
It is the bounded next set of pilots that should prove whether parallel execution is actually reducing operator burden.

## Resource posture

### Main default
- `openai-codex/gpt-5.4`
- use for orchestration, integration, and higher-trust workspace work

### Lower-complexity Codex helpers now available
- `openai-codex/gpt-5.3-codex`
- `openai-codex/gpt-5.3-codex-spark`

Use these only for:
- bounded read-heavy inspection
- mechanical comparisons
- draft patch preparation
- cheap implementation scaffolding

Do not use them for:
- final trust adjudication
- canonical-state judgment
- ambiguous architecture decisions
- final portfolio or OS calls

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

## Pilot Queue

### Pilot 1 — Workspace inventory / drift scan
Status:
- ready now

Lane:
- OpenClaw subagent

Model posture:
- `openai-codex/gpt-5.3-codex-spark` preferred
- escalate to `gpt-5.3-codex` only if the file set is larger or the diff logic becomes messy

Deliverable:
- compact inventory of high-drift operator surfaces
- top 5 mismatch or cleanup candidates
- no edits, just evidence and suggested next actions

Good targets:
- overlapping playbooks
- stale routing notes
- duplicated operator rules
- notes that should be merged or demoted

Do not touch:
- canonical portfolio notes
- config files
- live automation jobs

Acceptance check:
- report identifies concrete cleanup candidates with file paths and reasons
- no speculative framework churn

### Pilot 2 — Subagent patch-prep lane
Status:
- ready after Pilot 1

Lane:
- OpenClaw subagent

Model posture:
- `openai-codex/gpt-5.3-codex`

Deliverable:
- exact patch proposal for one bounded multi-file cleanup chosen from Pilot 1
- patch only, not silent application unless separately approved

Do not touch:
- broad architecture
- canonical note semantics
- auth/network settings

Acceptance check:
- patch is reviewable, bounded, and reversible
- each file changed has a clear reason

### Pilot 3 — Claude review lane on subagent output
Status:
- ready after Pilot 2

Lane:
- Claude CLI

Model posture:
- Sonnet 4.6 medium by default
- high only if the patch touches trust semantics or multiple playbooks

Deliverable:
- judgment review of the proposed patch
- identify hidden drift, ownership confusion, or overreach

Do not touch:
- final application
- unrelated style churn

Acceptance check:
- review clearly says approve, narrow, or reject
- comments are about contract and operating quality, not cosmetic rewrite pressure

### Pilot 4 — Cheap contradiction check lane
Status:
- optional helper after Pilot 3

Lane:
- Gemini Flash or `gpt-5.3-codex-spark`

Deliverable:
- narrow contradiction check on one claim only
- examples: duplicated rule, conflicting ownership statement, outdated routing claim

Do not touch:
- first-pass synthesis
- final decisions

Acceptance check:
- one bounded answer, not a broad re-analysis

### Pilot 5 — Parallel work kickoff packet standardization
Status:
- ready once 2-3 pilots complete cleanly

Lane:
- Veritas main session

Deliverable:
- reusable kickoff template for OpenClaw subagent work
- reusable review packet template for Claude / cheap helper lanes

Acceptance check:
- next delegated run should need less prompt reconstruction than today

## Execution order

Run in this order:
1. Pilot 1 — drift scan
2. Pilot 2 — patch-prep lane
3. Pilot 3 — Claude review lane
4. Pilot 4 — contradiction helper only if useful
5. Pilot 5 — formalize the packet templates

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
