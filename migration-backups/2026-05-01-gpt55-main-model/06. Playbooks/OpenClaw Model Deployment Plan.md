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

Verified on 2026-05-01:
- current main OpenClaw model: `openai-codex/gpt-5.4`
- current session has a large context budget and fresh weekly capacity
- local generated model metadata currently only verifies `gpt-5.4` as the exposed Codex model entry in `agents/main/agent/models.json`

## Codex lane policy

### Current verified default
Use:
- `openai-codex/gpt-5.4`

Why:
- verified live in the current session
- already configured with expanded local context metadata
- stable default until a higher model is actually confirmed available in this environment

### Candidate models to adopt only when verified
Potential Codex models of interest:
- `openai-codex/gpt-5.5`
- `openai-codex/gpt-5.4-mini`
- `openai-codex/gpt-5.3-codex`
- `openai-codex/gpt-5.3-codex-spark`

Rule:
- do not route meaningful work to a candidate model until it is actually verified as exposed in this environment
- treat catalog rumors and entitlement notes as hints, not truth

Additional 2026-05-01 verification:
- `openai-codex/gpt-5.3-codex`
- `openai-codex/gpt-5.3-codex-spark`

Current posture for both:
- helper lanes only
- suitable for lower-complexity inspection, patch preparation, and cheap bounded work
- not suitable as the final lane for trust adjudication or ambiguous architecture decisions

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
- medium thinking: default for most real work
- high thinking: when the spawned task is complex and error-sensitive
- `xhigh` thinking: default when the spawned lane uses `openai-codex/gpt-5.3-codex-spark`
- low thinking: only for narrow mechanical tasks

### Future Codex adoption rule
If `openai-codex/gpt-5.5` becomes verified:
- promote it to the preferred main Codex lane
- keep `gpt-5.4` as the fallback stable lane

If `openai-codex/gpt-5.4-mini` becomes verified:
- use it for smaller coding sub-sessions and cheap bounded helper passes

If `openai-codex/gpt-5.3-codex-spark` becomes verified:
- use it as a fast iteration / cheap experimentation lane only
- when Veritas routes work to Spark, default the effort / thinking posture to `xhigh`
- do not use Spark for canonical-state judgment or high-trust final implementation without later verification by a stronger lane

If `openai-codex/gpt-5.3-codex` is verified:
- use it for bounded read-heavy inspection, modest multi-file helper work, and patch-prep lanes
- keep final integration and harder judgment in `gpt-5.4`

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

### GPT5.5 Research
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
- reserve future Spark / mini lanes for cheap iteration only after verification

## Today’s recommended deployment

### Available now
- OpenClaw main: `openai-codex/gpt-5.4`
- Claude CLI: deployable
- Gemini Flash: deployable
- GPT5.5 Research: deployable as external research lane

### Hold until tomorrow or verification
- Gemini Pro implementation lane
- unverified Codex candidate models

## Durable rule

Scale productivity by splitting lanes deliberately:
- OpenClaw/Codex = primary workspace execution and orchestration
- Claude CLI = primary judgment CLI lane
- Gemini Flash = cheap bounded audit/diagnosis lane
- Gemini Pro = primary external implementation CLI lane when available
- GPT5.5 Research = external evidence lane

More models do not help unless routing discipline stays stronger than model enthusiasm.
