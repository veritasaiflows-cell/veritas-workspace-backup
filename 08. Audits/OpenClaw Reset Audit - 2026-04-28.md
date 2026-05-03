# OpenClaw Reset Audit - 2026-04-28

## Scope

Post-reinstall audit focused on rebuilding OpenClaw into a Windows-aligned, decision-grade investment operating system.

Primary focus for this pass:
- native OpenClaw install state
- Windows tool and skill readiness
- current config and scheduler state
- gaps between the live install and the finance-first workspace mission
- relevant OpenClaw documentation and online best-practice guidance

## Sources reviewed

### Workspace / prior internal context
- `scripts/README.md`
- `08. Audits/Workspace Audit - 2026-04-27.md`
- core finance dashboard and portfolio notes already reviewed earlier in session

### Local OpenClaw docs
- `docs/platforms/windows.md`
- `docs/tools/skills.md`
- `docs/tools/skills-config.md`
- `docs/automation/cron-jobs.md`
- `docs/gateway/configuration.md`
- `docs/start/getting-started.md`

### Online docs cross-check
- `https://docs.openclaw.ai/platforms/windows`
- `https://docs.openclaw.ai/tools/skills`
- `https://docs.openclaw.ai/tools/skills-config`
- `https://docs.openclaw.ai/automation/cron-jobs`
- `https://docs.openclaw.ai/gateway/configuration`

## Live install state

### Gateway / runtime
- Gateway is running locally on loopback `127.0.0.1:18789`.
- Service mode is installed through Windows Scheduled Task.
- A Startup-folder login-item path is also present as fallback/startup support.
- Config path is `C:\Users\Veritas2.0\.openclaw\openclaw.json`.
- Gateway probe is healthy.
- Admin-capable runtime detected.

### OpenClaw state directories present
- `agents`
- `canvas`
- `devices`
- `flows`
- `identity`
- `logs`
- `memory`
- `plugin-runtime-deps`
- `plugins`
- `tasks`
- `workspace`

### Current scheduler state
- Cron scheduler is enabled.
- Current job count: `0`.
- Result: all prior finance automation schedules were lost or never recreated after reinstall.

## Current config observations

Observed from `~/.openclaw/openclaw.json`:
- workspace is correctly pointed at `C:\Users\Veritas2.0\.openclaw\workspace`
- primary model is `openai-codex/gpt-5.4`
- tool profile is currently `coding`
- web fetch/search are enabled in config
- bundled provider plugins include OpenAI, Google, and Anthropic
- internal hooks are enabled
- no explicit `skills` block is currently defined
- no explicit skill allowlist policy is currently defined
- no explicit extra skill directories are configured
- no explicit finance-specific automation config is present

### Important concern
- Secrets are currently stored directly in config for at least some providers/tokens. This should be cleaned up during rebuild and moved to environment-backed or otherwise safer secret handling where possible.

## Skill surface and Windows dependency readiness

### Workspace custom skills survived reinstall
Present under `workspace/skills`:
- `technical-chart-pass`
- `veritas-fundamental-pass`
- `veritas-investment-deck`
- `veritas-macro-pass`
- `veritas-pdf-brief`
- `veritas-positioning-pass`
- `veritas-self-improvement`
- `veritas-technical-pass`
- `workspace-governor`

### Shared skill roots currently absent or unused
- `~/.agents/skills` does not exist
- no evidence yet of a populated `~/.openclaw/skills` managed local skill directory

### Key skill-related binaries verified working on Windows
- `openclaw`
- `node`
- `npm`
- `python`
- `git`
- `gh`
- `ffmpeg`
- `jq`
- `rg`
- `gemini`
- `claude`
- `clawhub`
- `curl.exe`

### Missing but potentially useful binaries
- `codex`
- `opencode`
- `pi`
- `pnpm`
- `uv`

### Meaning
- The current Windows machine can already support a serious OpenClaw skill stack.
- `coding-agent` is usable now through Claude Code because `claude` is installed.
- GitHub, Gemini, session-log, video-frame, weather, and ClawHub skill paths are materially available.
- Optional tooling is still missing for a more complete or more flexible setup, especially `codex`, `uv`, and possibly `pnpm`.

## Best-practice findings from docs

### Windows guidance
- OpenClaw supports both native Windows and WSL2.
- Docs still describe WSL2 as the more stable full-experience path.
- Native Windows is valid for core CLI and Gateway use, but has caveats around service install/startup behavior.
- Scheduled Tasks are preferred when available; Startup-folder fallback is the recovery path.

### Skills guidance
- Skill precedence is:
  1. `workspace/skills`
  2. `workspace/.agents/skills`
  3. `~/.agents/skills`
  4. `~/.openclaw/skills`
  5. bundled skills
  6. extra dirs from config
- Skill visibility and skill location are separate controls.
- A clean rebuild should explicitly decide which skills are visible by default and which remain merely installed.

### Config guidance
- Config is strict-schema validated.
- Better rebuild path is config-driven, not ad hoc drift.
- Control UI plus schema-aware config editing should be preferred over blind manual rewrites.

### Cron guidance
- Cron is gateway-native and persists independently of the model.
- Cron definitions survive restart when properly recreated.
- This is the correct layer for recurring finance refresh chains, reminders, and daily/weekly automation.

## Gaps versus mission

### Critical gaps
1. **No cron jobs exist**
   - This is the biggest operational regression.
   - Finance refresh chains, morning/post-close jobs, and weekly intelligence automation are not active.

2. **Tool profile is coding-oriented, not finance-operations-oriented**
   - Current profile may be overly narrow for a decision-grade research OS.
   - In this session, browser-style tooling is not exposed, which weakens chart-heavy and live web inspection workflows.

3. **No explicit skills config policy**
   - Current setup relies on defaults instead of a deliberate skill operating model.
   - That is workable, but not yet hardened.

4. **Secrets hygiene needs cleanup**
   - Reinstall is the right moment to remove plaintext secrets from config where possible.

5. **Finance automation state is disconnected from OpenClaw config/runtime**
   - The workspace scripts survived.
   - The orchestration layer did not.
   - That means the operating system is partially preserved, but not actually live.

### Medium-priority gaps
6. **No shared personal-skill layer exists yet**
   - Useful if we want reusable cross-workspace operator skills later.

7. **Optional Windows developer tooling is incomplete**
   - `uv` would improve Python environment and script reproducibility.
   - `codex` would broaden coding-agent options.
   - `pnpm` may be useful if package workflows expand.

8. **Config churn evidence exists**
   - Multiple config backups and last-good snapshots suggest repeated edits/recovery.
   - That is not a problem by itself, but it supports building a cleaner explicit baseline now.

## Recommendation

Use a **native-Windows-first rebuild** now, not an immediate WSL migration.

Reason:
- the current gateway is healthy on native Windows
- required core skill/tool binaries mostly work already
- the workspace is already anchored to Windows paths and local tooling
- the fastest path back to a decision-grade finance OS is to harden this native setup first

Keep **WSL2 as a phase-2 optional architecture upgrade**, not the first move.

## Proposed rebuild phases

### Phase 1 - Baseline hardening
- snapshot current config and runtime state
- clean up secret handling
- document exact required providers, models, and auth paths
- verify gateway service mode and remove ambiguity about Scheduled Task vs Startup fallback behavior

### Phase 2 - Windows skills and toolchain rebuild
- validate all skills actually needed for this mission
- install/verify optional missing binaries (`codex`, `uv`, maybe `pnpm`)
- define explicit skill policy: bundled, workspace, shared personal, and allowlists
- decide whether to create `~/.agents/skills` or keep everything mission-specific inside workspace

### Phase 3 - Mission config rebuild
- tune tool exposure away from a pure coding posture if needed
- define finance-appropriate default agent settings
- configure any required provider auth cleanly
- add any missing local skill config entries

### Phase 4 - Automation rebuild
- recreate cron jobs for:
  - morning finance refresh chain
  - post-close refresh chain
  - weekly intelligence / positioning cadence
  - selective maintenance reminders
- validate persistence and run history

### Phase 5 - Decision-grade validation
- prove end-to-end operation by running:
  - refresh chain
  - dashboard generation
  - validation harnesses
  - one daily/weekly output path
- verify that outputs land in the right workspace artifacts without stale contradictions

## Immediate next actions

1. Audit and harden `openclaw.json` into an explicit Windows + finance baseline.
2. Rebuild the skills policy and verify every required dependency for the actual mission stack.
3. Recreate cron automation for the finance operating cadence.
4. Run an end-to-end validation of the saved research OS.

## Bottom line

The reinstall did **not** destroy the workspace brain.
It **did** destroy enough runtime/config/orchestration state that the system is no longer decision-grade yet.

The good news: the core recovery path is clear, the Windows host is already mostly capable, and the missing pieces are mostly configuration, automation, and hardening rather than deep rebuild-from-scratch engineering.