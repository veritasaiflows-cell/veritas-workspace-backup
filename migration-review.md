# Migration Review - 2026-04-29 0016 MST

## Execution status

### Completed in this pass
- created timestamped backups in `migration-backups/2026-04-29-0016/`
- added four operator skills:
  - `skills/openclaw-operator/`
  - `skills/openclaw-troubleshooter/`
  - `skills/memory-continuity-manager/`
  - `skills/cron-automation-manager/`
- condensed these core files:
  - `SOUL.md`
  - `IDENTITY.md`
  - `MEMORY.md`
  - `USER.md`
  - `TOOLS.md`
  - `AGENTS.md`
  - `Continuity Protocol.md`
  - `HEARTBEAT.md`

## Architecture now in force

### Core constitution files
- `SOUL.md`
- `IDENTITY.md`
- `MEMORY.md`
- `USER.md`
- `TOOLS.md`
- `AGENTS.md`
- `Continuity Protocol.md`
- `HEARTBEAT.md`

### Operator skills
- `skills/openclaw-operator/`
- `skills/openclaw-troubleshooter/`
- `skills/memory-continuity-manager/`
- `skills/cron-automation-manager/`

### Existing finance skills preserved as the finance spine
- `veritas-fundamental-pass`
- `veritas-technical-pass`
- `veritas-macro-pass`
- `veritas-positioning-pass`
- `veritas-investment-deck`
- `veritas-pdf-brief`
- `veritas-self-improvement`
- `workspace-governor`

## Deliberate non-actions

- kept `memory/` as the chronological daily-history layer; did not create a parallel `daily-memory/` tree
- did not delete `BOOTSTRAP.md` in the same pass; it remains a cleanup candidate
- did not delete or operationalize `CLAUDE.md`; it remains outside the active OpenClaw core constitution
- did not create generic duplicate finance skills that overlap with the existing Veritas finance stack
- kept the current OpenClaw version; no update to `2026.4.26`

## Review items still open

1. `BOOTSTRAP.md`
   - recommended next move: archive or remove after one final explicit cleanup decision
2. `CLAUDE.md`
   - recommended next move: archive or clearly label as non-core reference material
3. `06. Playbooks/Operating Model.md`
   - likely next move: trim or align to the new skills so it does not re-accumulate procedural sprawl
4. `scripts/README.md`
   - likely next move: keep as tooling reference, but split any overly long runbooks into skill references if it keeps growing

## Validation results

- core files are materially shorter:
  - `SOUL.md` 88 lines
  - `IDENTITY.md` 9 lines
  - `MEMORY.md` 44 lines
  - `USER.md` 11 lines
  - `TOOLS.md` 40 lines
  - `AGENTS.md` 75 lines
  - `Continuity Protocol.md` 67 lines
  - `HEARTBEAT.md` 18 lines
- `openclaw config validate` passed
- `openclaw skills check` passed with 20 eligible skills
- the four new operator skills loaded successfully
- bundled-skill allowlist posture remains intact
- no critical identity, mission, or safety rule was intentionally removed

## OpenClaw Update Prep - 2026-06-05 09:40 MST

Randall is about to update OpenClaw from `OpenClaw 2026.5.27 (27ae826)` on stable/pnpm. Pre-update posture:

- `openclaw status`: gateway local/reachable at `http://127.0.0.1:18789/`; gateway scheduled task installed/running; Tailscale exposure off; Telegram enabled/configured; 39 active sessions; 25 enabled cron jobs per current workspace proof.
- `openclaw config validate`: passed for `~\.openclaw\openclaw.json`.
- `openclaw skills check`: passed with 92 total, 50 eligible/visible, 49 command-available, 0 missing requirements, 0 blocked by allowlist.
- `openclaw security audit`: 0 critical, 3 warnings, 1 info. Warnings: loopback gateway has no trusted proxies configured; personal-assistant/multi-user heuristic due Telegram group allowlist and broad tools; unpinned npm plugin install records for `codex` and `diagnostics-otel`.
- `openclaw doctor`: no hard stop, but warnings exist: expired Anthropic and Gemini CLI auth, 1 explicit Anthropic session override, 57 orphan transcripts, 27 legacy `openai-codex/*` session route pins, 1 cron job with explicit model override, plaintext gateway/Telegram secret-bearing config fields, bootstrap files near size limits, memory search provider set to OpenAI without API key.
- `openclaw approvals get --json`: approvals file exists at `~\.openclaw\exec-approvals.json`; effective `tools.exec` policy is full security with ask off; hash `eb327f41aa8d5f56a94fd94b5ec022a1c08331aefa6c530c78ba78cb2d68b32a`.

Known-good workspace proof immediately before update:

- Retail/source-trust blockers closed: `automation_stack_hardening_pass.py --write --validate`, `retail_truth_routing_contract.py --write --validate`, `retail_answer_harness.py --write --validate`, `retail_automation_control_plane.py --write --validate`, `wf78_phase_runner.py --phase all-safe --write --validate`, and `veritas_harness_scorecard.py --write --validate` all validated ok.
- PM state was green; PM queue ok; no customer/external output, SQL-first promotion, Python fallback retirement, canon/portfolio mutation, paper/live/brokerage/account action, or owner approval inference.

Post-update recovery checklist:

1. Run `openclaw --version`, `openclaw status`, `openclaw doctor`, `openclaw config validate`, and `openclaw skills check`.
2. Confirm `~\.openclaw\openclaw.json`, `~\.openclaw\exec-approvals.json`, workspace `skills\`, plugin skill links, gateway scheduled task, and startup persistence survived.
3. If `openclaw skills check` reports plugin-skill symlink errors (`EPERM` / `WinError 1314`), treat it as Windows symlink privilege/Developer Mode, not as lost skill doctrine.
4. Re-run workspace proof before trusting finance/cron/retail output: `python scripts\cron_freshness_spine.py --write --validate`; `python scripts\retail_truth_routing_contract.py --write --validate`; `python scripts\retail_answer_harness.py --write --validate`; `python scripts\retail_automation_control_plane.py --write --validate`; `python scripts\wf78_phase_runner.py --phase all-safe --write --validate`; `python scripts\veritas_harness_scorecard.py --write --validate`; `python scripts\pm_program_state.py --write --write-db --validate`; `python scripts\pm_implementation_job_queue.py --write --write-db --validate`.
5. Do not run `openclaw doctor --fix`, archive orphan transcripts, rewrite legacy session pins, alter secrets, or change cron/channel/config/service state unless Randall approves the exact mutation after the update.

## OpenClaw Post-Update Validation - 2026-06-05 09:45 MST

Randall completed the update. New runtime baseline is `OpenClaw 2026.6.1 (2e08f0f)`.

Runtime and config proof:

- `openclaw --version`: `OpenClaw 2026.6.1 (2e08f0f)`.
- `openclaw status --deep`: gateway local/reachable at `http://127.0.0.1:18789/`; update up to date; gateway service scheduled task installed/running; Telegram OK; Tailscale off; 39 active sessions; memory enabled; 0 active/queued/running tasks; security audit still 0 critical / 3 warnings / 1 info.
- `openclaw config validate`: passed.
- `openclaw skills check`: passed with 92 total, 50 eligible/visible, 49 command-available, 0 missing requirements, 0 allowlist blocks.
- `openclaw doctor`: warnings only. Known warnings after update: legacy plugin install index conflict for `codex` and `diagnostics-otel`; Telegram group allowlist empty for group messages; expired Anthropic auth and soon-expiring Gemini auth; 1 explicit Anthropic session override; 57 orphan transcripts; 1 cron job with explicit model override; plaintext secret-bearing config fields; plugin install index legacy state. No `doctor --fix` action was run.
- `openclaw security audit`: 0 critical, 3 warnings, 1 info. Warnings remain trusted proxy config absent on loopback gateway, personal-assistant/multi-user heuristic, and unpinned npm plugin install records for `codex` and `diagnostics-otel`.

Workspace proof after update:

- `cron_freshness_spine.py --write --validate`: validation `ok`; spine status `warning` because 2 enabled jobs require attention; 25 enabled, 16 disabled, 23 fresh, 0 stale, 0 blocked, 0 unregistered.
- `retail_truth_routing_contract.py --write --validate`: `ok`, 8 routes, A2 live complete.
- `retail_answer_harness.py --write --validate`: `ok`, 40 checks, 9 seeded-bad cases blocked as expected.
- `retail_automation_control_plane.py --write --validate`: `ok`, review-only; 8 routes; customer-safe retail output remains blocked; SQL support mode only.
- `wf78_phase_runner.py --phase all-safe --write --validate`: `ok`, 13 steps, 0 failures.
- `veritas_harness_scorecard.py --write --validate`: `ok`, 71/71 pass, 0 warnings.
- `automation_stack_hardening_pass.py --write --validate`: `ok`, 132 checks, 0 critical, 0 warnings.
- `pm_program_state.py --write --write-db --validate`: `ok`; readiness green, average 81.2, 13 lanes, 0 blocked/gated/stale, 4 needing validation.
- `pm_implementation_job_queue.py --write --write-db --validate`: `ok`; 14 jobs, 10 ready, 0 blocked; expected warnings for collision group and owner-decision jobs.

Post-update boundaries:

- Runtime is usable, but warnings remain review items rather than silent fixes.
- No config/auth/channel/service/plugin/session cleanup mutation was performed.
- No customer/external output, SQL-first promotion, Python fallback retirement, canon/portfolio mutation, paper/live/brokerage/account action, or owner approval inference was performed.
