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

## Core routing ownership

Veritas owns:
- OpenClaw model selection when session-level control is available
- spawned OpenClaw sub-session model / thinking choice
- Gemini CLI routing
- Claude CLI routing when using the local CLI lane
- escalation decisions across all local model lanes

Randall may still use Claude directly when desired, but the operating system should treat Veritas as the primary routing layer for local execution capacity.

## Current live OpenClaw posture

Verified / updated on 2026-05-01:
- target main OpenClaw model: `openai-codex/gpt-5.4`
- default spawned sub-session model: `openai-codex/gpt-5.4`
- current session has a large context budget and fresh weekly capacity
- `openai-codex/gpt-5.3-codex` remains an allowed bounded helper lane
- `openai-codex/gpt-5.3-codex-spark` is removed from Veritas-routed workflow use after repeated contract/control-surface failures; Randall may still use it manually and report findings back into the workspace

## Codex lane policy

### Current verified default
Use:
- `openai-codex/gpt-5.4` for the main agent / top-level OpenClaw session
- `openai-codex/gpt-5.4` for spawned sub-sessions by default

Why:
- Randall explicitly promoted `gpt-5.4` to the main-agent default once it became available
- `gpt-5.4` remains the stable high-trust subagent lane
- this keeps the strongest default reasoning in the orchestration seat while preserving a known-good worker baseline

### Candidate models to adopt only when verified
Potential Codex models of interest:
- `openai-codex/gpt-5.4`
- `openai-codex/gpt-5.4-mini`
- `openai-codex/gpt-5.3-codex`

Rule:
- do not route meaningful work to a candidate model until it is actually verified as exposed in this environment
- treat catalog rumors and entitlement notes as hints, not truth

Additional 2026-05-01 verification:
- `openai-codex/gpt-5.3-codex`
- `openai-codex/gpt-5.3-codex-spark` (verified available, but removed from Veritas-routed workflow use)

Current posture:
- `openai-codex/gpt-5.3-codex` may be used for bounded read-heavy inspection, patch preparation, and cheap helper work
- `openai-codex/gpt-5.3-codex-spark` is no longer used by Veritas as a workflow lane because it failed repeated structured-audit / session-control expectations
- neither is suitable for final trust adjudication or ambiguous architecture decisions

## Recommended Codex usage by lane

### Main OpenClaw session
Default:
- `openai-codex/gpt-5.4`
- use for orchestration, synthesis, file-grounded work, and higher-trust execution in the workspace

### Spawned sub-sessions
Use spawned sessions when:
- work is multi-step and detached
- the main thread should stay clean
- a bounded pass can run in isolation

Recommended spawn posture by task type:
- default model: `openai-codex/gpt-5.4`
- medium thinking: default for most real work
- high thinking: when the spawned task is complex and error-sensitive
- low thinking: only for narrow mechanical tasks

### Future Codex adoption rule
`openai-codex/gpt-5.4` is now the preferred main Codex lane.
- keep `gpt-5.4` as the default stable subagent lane
- if `gpt-5.4` proves unstable in live use, fall back to `gpt-5.4` for the main lane deliberately rather than implicitly

If `openai-codex/gpt-5.4-mini` becomes verified:
- use it for smaller coding sub-sessions and cheap bounded helper passes

If `openai-codex/gpt-5.3-codex` is verified:
- use it for bounded read-heavy inspection, modest multi-file helper work, and patch-prep lanes
- keep final integration and harder judgment in `gpt-5.4` or the default `gpt-5.4` subagent lane depending on who owns the pass

## CLI lane posture

### Gemini CLI
Current live posture:
- Gemini Pro unavailable until tomorrow by operator report
- Gemini Flash is available now
- Veritas owns routing

Use now for:
- bounded contradiction checks
- file-level diagnosis
- narrow implementation prep

### Claude CLI
Current live posture:
- all current Claude models are available for deployment
- Veritas now owns Claude CLI routing too

Use now for:
- judgment passes
- cross-artifact synthesis
- bounded review of machine contradictions
- selective implementation only when coherence and judgment both matter

## External low-cost lanes

### GPT5.4 Research
Use as:
- external web research
- thesis challenge pass
- macro / policy / event-risk context

### Cheap-lane rule
Cheap lanes gather evidence or diagnose.
They do not become canonical truth by themselves.

## Limits / usage discipline

### What is actually visible now
Claude CLI:
- authenticated
- subscription type visible: `pro`
- no clean remaining session/weekly quota number exposed yet through the checked commands

Gemini CLI:
- sessions/history visible
- no clean quota/remaining-limit number exposed yet through the checked commands

OpenClaw main session:
- session_status exposes current usage and weekly remaining for the OpenClaw session itself

### Operational rule
Until local CLIs expose real remaining-limit signals reliably:
- use model/effort discipline as the control layer
- assume Claude Sonnet medium is the default savings mode
- reserve Opus for genuine escalation
- reserve Gemini Flash for bounded tasks only
- reserve future Gemini Pro for real implementation passes
- reserve mini/helper lanes only when they prove workflow reliability under Veritas control

## Today’s recommended deployment

### Available now
- OpenClaw main: `openai-codex/gpt-5.4`
- OpenClaw spawned sub-sessions: `openai-codex/gpt-5.4` by default
- Claude CLI: deployable
- Gemini Flash: deployable
- GPT5.4 Research: deployable as external research lane

### Hold until tomorrow or verification
- Gemini Pro implementation lane
- unverified Codex candidate models

## Durable rule

Scale productivity by splitting lanes deliberately:
- OpenClaw/Codex = primary workspace execution and orchestration
- Claude CLI = primary judgment CLI lane
- Gemini Flash = cheap bounded audit/diagnosis lane
- Gemini Pro = primary external implementation CLI lane when available
- GPT5.4 Research = external evidence lane

More models do not help unless routing discipline stays stronger than model enthusiasm.

## Manual-use exception

Randall may still use `openai-codex/gpt-5.3-codex-spark` manually for manual QA, audits, or reports and then bring the output back to Veritas for judgment and integration.
That is explicitly different from Veritas routing Spark as a workflow lane.
