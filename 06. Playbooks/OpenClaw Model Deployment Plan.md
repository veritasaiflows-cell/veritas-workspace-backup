# OpenClaw Model Deployment Plan

## Purpose

Define how Veritas should use:
- the main OpenClaw session
- spawned OpenClaw sub-sessions
- Gemini CLI
- Claude CLI
- low-cost external research lanes

This plan exists to scale productivity without losing routing discipline, budget discipline, or trust discipline.

For concurrency structure and lane ownership, also use `06. Playbooks/OpenClaw Parallel Work Plan.md`.

## Supersession note

Updated on 2026-05-06 after Randall's WF39 posture correction.

Current posture supersedes the earlier 2026-05-01 default-worker posture. Historical daily notes and audits may still mention older routing decisions as history; this file is the live model-routing plan.

## Core routing ownership

Veritas owns:
- OpenClaw model selection when session-level control is available
- spawned OpenClaw sub-session model / thinking choice
- Gemini CLI routing
- Claude CLI routing when using the local CLI lane
- escalation decisions across all local model lanes

Randall may still use Claude or lighter external/helper models directly when desired. The operating system should treat those outputs as evidence for Veritas review, not as final queue state or canonical judgment.

## Current live OpenClaw posture

Verified / updated on 2026-05-06:
- main OpenClaw session posture: live truth surface, workspace-file truth interpreter, orchestrator, QC owner, and final integrator
- default spawned sub-session model for substantial workspace work: `openai-codex/gpt-5.5` with high-thinking posture when available
- current stable OpenClaw runtime pin remains `2026.5.4` unless Randall intentionally revisits the runtime stability decision
- lower-complexity 5.3 Codex lanes are not approved for Veritas-routed workflow use
- Randall may still use lighter external/manual outputs as evidence for review, but Veritas should not route live workflow work through removed 5.3 Codex lanes

## Codex lane policy

### Main OpenClaw session

Use the main session for:
- live truth-surface judgment
- canonical financial database interpretation
- project selection and queue movement
- handoff packet creation
- QC / audit integration
- final synthesis and closeout
- quick bounded execution expected to stay under roughly five minutes

The main session is not the durable canonical database. The workspace file layer is the durable canonical financial database; the main session interprets and reconciles it.

### Spawned OpenClaw sub-sessions

Use spawned sessions when work is substantial, detached, multi-step, multi-artifact, broad-inspection, or QA-heavy.

Recommended spawn posture:
- default model for substantial workspace work: `openai-codex/gpt-5.5`
- thinking posture: high-thinking when available
- handoff: explicit file-grounded context packet
- authority: bounded execution, inspection, draft prep, validation, or audit only
- not allowed: final queue state, final portfolio/OS judgment, canonical conflict resolution, or canonical finance-note mutation unless a later explicit workflow contract authorizes it

### Direct main-session exception

Direct execution in the main session is acceptable when:
- the work is quick, reversible, and bounded enough to stay under roughly five minutes
- an immediate truth fix is safer than spawning
- the work is final merge / QC after worker or audit evidence
- spawning would add more friction than value

If meaningful work uses this exception, record the exception in status, continuity, or closeout notes.

### Fallback rule

If `openai-codex/gpt-5.5` is unavailable:
- keep the same bounded contract
- record the fallback explicitly
- do not silently downgrade trust
- do not revive removed 5.3 Codex helper lanes as Veritas-routed workflow lanes

## Candidate models to adopt only when verified

Potential future Codex models of interest may exist, but catalog rumors and entitlement notes are not proof.

Rule:
- do not route meaningful work to a candidate model until it is actually verified as exposed and reliable in this environment
- if a smaller helper posture is needed, reduce scope or use manual external evidence review instead of routing through a removed model

## CLI lane posture

### Gemini CLI

Current posture:
- Gemini Pro is the preferred CLI implementation/research lane when available
- Gemini Flash is a bounded audit / contradiction / narrow diagnosis lane
- Veritas owns routing and integration

Use Gemini for:
- bounded contradiction checks
- file-level diagnosis
- narrow implementation prep
- broad research or implementation only when the model and contract are fit for the task

### Claude CLI

Current posture:
- Claude is the hard-judgment CLI lane when available
- use higher effort for trust/contract adjudication or high-stakes review

Use Claude for:
- judgment passes
- cross-artifact synthesis
- bounded review of machine contradictions
- selective implementation only when coherence and judgment both matter

## External low-cost lanes

Use low-cost external lanes as:
- external web research
- thesis challenge passes
- macro / policy / event-risk context
- manual helper evidence supplied by Randall

Cheap lanes gather evidence or diagnose. They do not become canonical truth by themselves.

## Limits / usage discipline

Until local CLIs expose reliable remaining-limit signals:
- use model/effort discipline as the control layer
- reserve high-cost judgment lanes for real ambiguity or high consequence
- reserve Gemini Flash / cheaper lanes for bounded tasks only
- keep OpenClaw spawned subagents as the primary workspace execution lane for substantial work

## Current deployment baseline

Available posture:
- Main OpenClaw: live truth surface / final integrator
- OpenClaw spawned sub-sessions: `openai-codex/gpt-5.5` high-thinking by default for substantial workspace work when available
- Claude CLI: judgment / contract / challenge lane
- Gemini Pro: preferred implementation / broad research CLI lane when available
- Gemini Flash: bounded audit / contradiction / diagnosis lane
- external research lanes: evidence only

## Durable rule

Scale productivity by splitting lanes deliberately:
- OpenClaw main = truth surface, orchestration, QC, final integration
- OpenClaw spawned subagents = substantial bounded workspace execution
- Claude CLI = hard-judgment review / challenge lane
- Gemini Pro = implementation or broad research lane when available
- Gemini Flash = cheap bounded audit / diagnosis lane
- external research = evidence intake only

More models do not help unless routing discipline stays stronger than model enthusiasm.

## Manual-use exception

Randall may still bring outputs from lighter manual helper models back to Veritas for QA, audits, reports, judgment, and integration.

That is explicitly different from Veritas routing those models as workflow lanes.
