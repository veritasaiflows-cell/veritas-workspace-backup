# Workflow 59 - Continuity and Compaction Hardening

## Purpose

Reduce compaction pain and file sprawl by making workspace continuity thinner, more explicit, and less dependent on raw chat history.

## Status

- **Opened:** 2026-05-12
- **Owner:** Veritas main session
- **Mode:** orchestration mode with bounded helper lanes
- **Current phase:** Phase I - config inspection, startup truth index, and archive-candidate staging
- **Authority:** workspace-note and proposal generation only

## Problem

Long sessions are compacting frequently and recovery currently depends on reading too many large startup/control files. The workspace also has many historical workflow and phase notes, which increases retrieval noise and encourages file sprawl.

## Operating thesis

The fix is not just a bigger context budget. The stronger model is:

1. keep the live workflow truth in one compact surface (`06. Playbooks/Active Workflows.md`)
2. keep one durable pickup note per active workflow
3. keep daily memory as material deltas only
4. keep generated proof/navigation in `tmp/`
5. stage archive candidates without moving or deleting anything until owner-approved
6. tune compaction to preserve more recent context and avoid over-aggressive compression

## Phase plan

### Phase I - Inspection and control-surface foundation

Deliverables:
- inspect active compaction config and schema
- stage a safe config patch proposal without applying it
- create `06. Playbooks/Startup Truth Index.md`
- update `Active Workflows.md` so WF59 is visible as the continuity/compaction hardening lane
- stage archive-candidate notes only; no moves/deletes

Acceptance:
- config proposal validates in dry-run or is explicitly marked blocked
- startup truth index exists and routes to canonical sources instead of duplicating them
- Active Workflows identifies this lane and stop lines
- archive candidates remain review-only

### Phase II - Startup-load reduction

Deliverables:
- review startup read burden and identify which surfaces can be summarized by the Startup Truth Index
- propose targeted updates to startup procedure without weakening safety or finance truth
- identify oversized files that should be split, summarized, or demoted to archive/reference

Acceptance:
- startup path is shorter while preserving SOUL/USER/TOOLS/MEMORY/finance truth boundaries
- no core file becomes a procedure dump

### Phase III - Continuity/sprawl cleanup package

Deliverables:
- merge helper audit findings
- produce reference-checked archive candidate set
- update archive queue in `Active Workflows.md` or a dedicated review artifact
- optionally create a reusable validator/report for continuity-sprawl checks

Acceptance:
- no destructive action without approval
- active owner surfaces are protected
- duplicate/phase residue has clear keeper/archive rationale

### Phase IV - Closeout and proof

Deliverables:
- validate config/current docs
- log the outcome in daily memory
- update relevant operating file or skill only if a durable rule changed
- hand off any config apply step as explicit owner/runtime approval if still pending

Acceptance:
- no untracked workflow drift
- no config mutation claimed unless actually applied and validated
- next pickup point is visible from Startup Truth Index + Active Workflows

## Stop lines

- Do not edit `~/.openclaw/openclaw.json` directly in this workflow without explicit config-apply approval.
- Do not mutate auth, credentials, channels, network exposure, plugin/runtime startup, or service state.
- Do not delete, move, or archive files; stage candidates only.
- Do not weaken finance boundaries: no trade/account action, no owner-approval inference, no ungated portfolio mutation, and no cash/risk-rule/execution-entitlement changes; sizing/sleeve/sector-posture/ticker-state/entry-band changes require exact validator-backed approved gates.
- Do not create a second memory system.

## Phase I evidence

- Active compaction config path currently has no explicit `agents.defaults.compaction` object; defaults are in effect unless overridden elsewhere.
- Live session status during opening: OpenClaw 2026.5.7, model `openai-codex/gpt-5.5`, context approximately 94k/272k, compactions 2.
- Existing `legacy tmp artifact tombstoned in `state/tmp-lifecycle-deletion-tombstone.json` (`archive-suggestions.md`)` is review-only and already lists 65 suggestions with 54 inbound references; owner approval remains required before moves/deletes.

## Phase I progress - 2026-05-12

Completed:
- created `06. Playbooks/Startup Truth Index.md` as the thin post-compaction pickup map
- staged `tmp/wf59-compaction-config-proposal.json5` as proposal-only runtime config patch
- dry-run attempted with `openclaw config patch --file tmp\wf59-compaction-config-proposal.json5 --dry-run`
- dry-run did not validate because the active config has an unrelated Telegram schema blocker: `channels.telegram.dmPolicy` and `channels.telegram.groupPolicy` are required
- updated `06. Playbooks/Active Workflows.md` to expose WF59 as an active priority sidecar
- integrated bounded helper audit output into `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf59-continuity-sprawl-audit.md)`
- staged `Veritas OS Automation Spine.md` as high-confidence duplicate/archive candidate, with reference check and owner approval still required

Config implication:
- The compaction patch itself is schema-shaped, but active config validation is currently blocked by the existing Telegram channel object. Do not apply compaction settings until the Telegram schema issue is inspected and explicitly approved for correction.

## Phase II progress - 2026-05-12

Completed:
- updated `AGENTS.md` startup guidance to use `06. Playbooks/Startup Truth Index.md` and `06. Playbooks/Active Workflows.md` before broad finance/governance rereads
- separated normal direct-session startup from post-compaction recovery startup
- preserved drill-down to finance owner notes when finance judgment, portfolio status, or canonical note sync is required
- preserved the rule that larger governance surfaces are read when the current task requires them, not by habit every time

## Phase III progress - 2026-05-12

Completed:
- created `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf59-continuity-sprawl-audit.md)`
- kept `Active Workflows.md` as the live authoritative surface
- staged archive candidates only; no move/delete/archive action was taken
- documented `workflow 24 ...` filename casing drift as normalization-only, not archive/delete
- documented old chain logs as later-batch candidates only after inbound reference checks

## Runtime/config blocker

Created `legacy tmp artifact tombstoned in state/tmp-lifecycle-deletion-tombstone.json (wf59-runtime-config-blocker.md)` with the safe finding and proposed narrow Telegram schema cleanup. This is approval-gated because it touches external channel/runtime config.

## Phase IV closeout - 2026-05-12

Randall explicitly approved removing/disabling Telegram and continuing compaction/continuity hardening.

Completed:
- backed up the active config to `tmp/wf59-backups/openclaw.before-disable-telegram-and-compaction.json`
- applied `tmp/wf59-disable-telegram-and-compaction.patch.json5`
- removed `channels.telegram`
- set `plugins.entries.telegram.enabled=false`
- applied compaction tuning under `agents.defaults.compaction`
- restarted the gateway so runtime picked up the config
- validated config after restart
- updated `TOOLS.md` channel posture to state Telegram is disabled/removed for now
- updated `Active Workflows.md` to mark WF59 implemented/monitoring

Applied compaction posture:
- `mode=safeguard`
- `reserveTokens=24000`
- `reserveTokensFloor=20000`
- `keepRecentTokens=60000`
- `maxHistoryShare=0.8`
- `recentTurnsPreserve=6`
- `memoryFlush.enabled=true`
- `memoryFlush.softThresholdTokens=45000`
- `memoryFlush.forceFlushTranscriptBytes=12mb`
- `truncateAfterCompaction=true`
- `maxActiveTranscriptBytes=20mb`
- `notifyUser=false`

Validation:
- `openclaw config validate` passed
- `session_status` after restart showed gateway uptime reset and live runtime available
- sanitized config inspection confirmed `channels_keys=[]`, `telegram_present=False`, `plugins_telegram_enabled=False`, `compaction_mode=safeguard`, `reserveTokensFloor=20000`, `keepRecentTokens=60000`

## Current pickup point

WF59 is implemented and should remain on monitoring watch through normal use. Continue using `Startup Truth Index.md` plus `Active Workflows.md` after compaction. Do not re-enable Telegram or any external channel without explicit owner approval. Archive candidates remain review-only; no files were moved or deleted.
