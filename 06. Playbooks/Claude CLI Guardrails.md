# Claude CLI Guardrails

## Purpose

Define the safe operating posture for Claude CLI inside the Veritas OS.

This playbook mirrors the Gemini guardrail approach, but matches the current verified reality on this machine.

## Current verified posture

Observed on 2026-05-01:
- `claude --help` works
- `claude --version` works
- verified version: `2.1.126`
- headless invocation works via:
  - `claude -p "..."`
- live model menu includes:
  - `Sonnet 4.6`
  - `Sonnet 4.6 (1M context)`
  - `Opus 4.7`
  - `Opus 4.7 (1M context)`
  - `Haiku 4.5`
- live effort control includes:
  - `low`
  - `medium`
  - `high`
- Claude executables now exist under:
  - `%APPDATA%\\npm\\claude`
  - `%APPDATA%\\npm\\claude.cmd`
  - `%APPDATA%\\npm\\claude.ps1`
- local Claude state exists under:
  - `~/.claude/`
  - `~/.claude.json`

## Operational conclusion

Claude is now a verified local CLI lane.

However, its safe default role inside Veritas OS remains:
- higher-judgment collaborator
- bounded implementation only when intentionally chosen
- not a free-roaming automation surface

## Current trust-surface findings

### Sensitive local state
Treat these as sensitive:
- `~/.claude.json`
- `~/.claude/`
- session logs
- project logs
- shell snapshots
- backup config files

### Current permission surface
Observed workspace-related entries exist in `~/.claude.json` for:
- the active OpenClaw workspace (two path variants)
- several Claude worktree paths under `.claude/worktrees/...`

Important:
- duplicate workspace path variants increase ambiguity
- old worktree trust entries may remain after worktrees are no longer relevant

### Current tool posture
Observed in project entries:
- `allowedTools: []`

That is good. Nothing suggests a broad pre-allowlist is currently in place.

## Approval and permission guardrails

Default safe posture:
- use headless or interactive runs without bypassing permissions
- prefer bounded prompts and explicit model selection
- keep Claude in normal permission mode unless there is a clear reason otherwise

High-risk flags that should not be default:
- `--dangerously-skip-permissions`
- `--allow-dangerously-skip-permissions`
- permissive `--permission-mode` choices such as `bypassPermissions`

Reason:
- Claude now has real local CLI access to a trusted workspace
- bypass-permission posture removes too much friction for stateful finance OS work

## Current routing split

- Veritas now owns Claude CLI routing inside the workspace
- Randall may still prompt Claude directly when desired
- Gemini remains the primary local implementation / bounded audit lane unless Claude is intentionally chosen
- Claude remains the stronger default judgment and synthesis lane

## Safe-use rules

### Good Claude CLI uses
- bounded judgment passes
- post-earnings interpretation
- cross-artifact synthesis
- bounded review of specific notes, artifacts, or reports
- selective implementation where judgment and coherence matter together

### Effort guidance
- `medium` = default savings mode for real judgment work that is not yet a final high-consequence call
- `high` = use when near a real operator decision, canonical-state change, or difficult reconciliation
- 1M context variants = use only when context volume is the actual bottleneck, not just because they exist
- `Haiku 4.5` = quick helper only, not a serious deployment-readiness or thesis-adjudication lane

### Use caution with
- broad autonomous edits across many files
- shell automation with dangerous permission bypass
- unattended scheduled Claude CLI runs

## Current recommended hardening direction

### Read-only conclusions
Recommended next cleanup targets:
1. normalize duplicate active-workspace entries in `~/.claude.json`
2. review whether older Claude worktree trust entries are still intentionally needed
3. keep dangerous permission bypass modes disabled as the default posture

### Requires explicit approval before changing
- editing `~/.claude.json`
- pruning Claude worktree trust entries
- changing Claude default permission behavior
- scheduling Claude CLI tasks or persistent automation

## Durable rule

Claude CLI is approved as a local CLI lane in the Veritas OS.
Its default posture should remain permission-respecting, bounded, and judgment-first.
Veritas owns local Claude CLI routing even when Randall continues to use direct Claude prompting separately.
