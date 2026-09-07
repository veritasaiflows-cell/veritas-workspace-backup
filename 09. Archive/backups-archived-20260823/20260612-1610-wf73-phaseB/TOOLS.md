# TOOLS.md - Local Runtime And Route Map

First-hop map only. Procedures live in skills/playbooks; command detail: `scripts/README.md`; history: `memory/`.

## Local Setup

- Root: `C:\Users\Veritas\.openclaw\workspace`
- Config: `~/.openclaw/openclaw.json`; daily notes: `memory/`; durable memory: `MEMORY.md`.
- Runtime: native Windows / PowerShell. Do not assume Bash/WSL semantics.
- OpenClaw runtime: `2026.6.1`; known doctor/security warnings are documented in `migration-review.md`.
- Tool shims: SQLite/rg/jq in `C:\Users\Veritas\AppData\Roaming\npm`; Git fallback in `C:\Users\Veritas\AppData\Local\Programs\Git\cmd\git.exe`; ClawHub shims in `C:\Users\Veritas\.openclaw\tools\node\npm`.
- Go validator freshness: `python scripts\go_binary_freshness_guard.py --write --validate`; rebuild `scripts\go` validators when source is newer than `bin\*.exe`.
- Model posture: main/new sessions use `openai/gpt-5.5`; bounded helpers use `openai/gpt-5.4`; Spark is bounded canary/proof only. WF84/WF85 promotion gates should use verified `claude-cli/claude-opus-4-8` challenger proof when warranted.

## Fast Routing

Use route/index/capsule surfaces first, then exact owner artifacts. Generated SQL/JSON/capsules are proof and routing only; they are not canon, approval, portfolio, trade, account, paper, or live authority.

- Workflow lookup: `python scripts\workflow_router.py WF## --answer summary|next|blockers|helper|all`; refresh capsules with `python scripts\workflow_router.py --all --write-capsules --validate`.
- Fast greeting/status brief: `python scripts\startup_brief_packet.py --write --validate`; use for simple direct-session hello/status when existing packets are fresh, then refresh heavier PM/cron/future-session packets only when stale or material work requires live proof.
- Future-session packet: `python scripts\future_session_enhancement_packet.py --write --write-md --validate`; open first after compaction/new-session handoff for PM, cron, WF74, workflow, memory, and stop-line routing.
- Concurrent helper/implementation work: `python scripts\concurrent_lane_manager.py --status --write --validate` first; before concurrent Telegram/WebChat/session implementation writes, lease exact writable surfaces with `--lease`, tag running lanes with `--set-status ... --status-value running --session-key ... --session-id ...`, and close with `--complete ... --proof ...`.
- Pause/resume: `python scripts\workflow_control_override.py hold <workflow_key> --reason "..." --validate`; `resume <workflow_key> --validate`.
- PM control: `python scripts\pm_control_packet.py --write --write-db --validate`; use `summary.stale_lane_digest` for PM-yellow drilldown. Legacy sidecars require `--write-compat`.
- Cron control: `python scripts\cron_control_packet.py --write --validate`; drill into cron freshness/scorecard only when attention, stale, or blocker signals appear.
- WF73 full audit: `python scripts\wf73_control_plane_audit.py --write --validate`; ordered producer-before-consumer route for workflow index, lane register, truth inventory, cron/PM, boot/hygiene, fast QA, closeout, artifact index, and memory-index health.
- Fast QA/timing: `python scripts\truth_surface_inventory.py --write --validate`; `python scripts\fast_path_qa.py --write --validate`; `python scripts\changed_file_validator_router.py --write --validate`; `python scripts\validator_timing_ledger.py --profile normal --write --validate`.
- Closeout: `python scripts\control_closeout_bundle.py --validation-budget shared --write --validate`; use `major` only for broad control-plane closeout.
- Artifact lookup: `python scripts\artifact_index.py ...`; proof mirror is `tmp\veritas-artifact-index.sqlite`.
- OTEL ops: `python scripts\otel_ops_control.py --write --write-db --multi-window --validate`; local operational digest and multi-window summary only.
- Local voice notes: `python scripts\local_audio_transcriber.py --write --pretty --validate`; defaults to newest `~\.openclaw\media\inbound` audio and local cache under `tmp\audio-tools`.
- Skill checkpoint: `python scripts\skill_git_checkpoint.py --write --validate`; commit/tag only on explicit request. Stages only `skills/`, Skills Governance Index, and today's memory file.
- PM execution dry-run: `python scripts\pm_execution_loop.py --write --validate`; `--execute` only runs guarded review-only proof commands from PM jobs.
- DB lifecycle route: `python scripts\db_lifecycle_manifest.py --write --validate`; review `tmp\db-lifecycle-manifest.json` (`tmp/db-lifecycle-manifest.json`); archive/delete only via `python scripts\db_lifecycle_archive_apply.py ...` after explicit owner approval, reference review, proof, and backup/rollback.
- Workspace search/index: `python scripts\workspace_index.py`; proof/search support only.

## Finance Front Doors

- Ticker Q&A route: `python scripts\finance_intelligence_state.py ticker <TICKER> --pretty` -> WF84 data plane -> WF85 full answer/card when guard-clean; source-open fallback when stale.
- Ticker cards/full answers: `python scripts\artifact_index.py ticker-card|answer-packet <TICKER>`; `answer-packet` is compatibility lookup backed by WF85 assembler output.
- Paper position visibility only: `python scripts\alpaca_paper_position_sql_refresh.py refresh --create-kill-switch --expires-minutes 90`, then `python scripts\finance_intelligence_state.py paper-positions`.
- Retail truth routing: `retail_truth_routing_contract.py`, `retail_answer_harness.py`, `retail_automation_control_plane.py`.
- WF78: non-capital repair/promotion feeder for WF84/WF85; route through `workflow_router.py WF78 --answer all`, then use freshness/decision-factory/phase artifacts as drill-ins.
- WF84: `python scripts\canonical_finance_data_plane.py --write --write-db --validate`, then phase 6-10. Internal/personal derived data plane only; no customer/account/canon/portfolio/execution authority.
- WF85: contract, cards, then `python scripts\trade_grade_full_answer_assembler.py --all-wf84 --write --validate`. Review-only decision/full-answer/approval-draft layer; no generated card/score/draft is approval.
- Macro: `macro_metrics_ingest.py`, `macro_signal_spine.py`, `macro_energy_supply_ingest.py`, `macro_geopolitical_sweep.py`, `macro_judgment_draft.py`; evidence only, no forecast/capital/execution authority.
- Entry-band maintenance: `band_refresh.py` proposes; `auto_apply_entry_band_maintenance.py --dry-run|--apply` may apply only eligible posture-preserving `entry_band` rows through the bounded gate.

Finance detail lives in `scripts/README.md`, workflow capsules, WF77/WF78 continuity, and exact owner artifacts. Source-open exact artifacts before material recommendation/action claims.

## Current Workflow Routes

- P0 Retail/WF75: `workflow_router.py WF75 --answer all`; customer/public/account/advice blocked.
- SMB Workflow Clarity: owner-paused; verify with `workflow_router.py WF79-SMB --answer all`; do not advance unless Randall resumes it.
- WF78 scaleout/promotion: feeder/repair route for WF84/WF85; derived non-capital routing only.
- WF84/WF85: current primary finance routing surface and Personal Trade-Grade Decision OS; review-only, source feeders and WF72 support cache retained until separate lifecycle gates clear.
- WF80-WF83 product scaleout: hold/resume-later; public/customer launch, spend, outreach, legal/compliance/security claims, and finance execution remain gated.
- PM cockpit: `apps\pm-control-cockpit`, `state\pm-cockpit-source-registry.json`, local `http://127.0.0.1:8765`; read-only.

## Model / Skill Layer

- Main posture: live truth surface, orchestrator, QC owner, final integrator.
- Serious-work challenger: use verified `claude-cli/claude-opus-4-8` for WF84/WF85-class gates when warranted; if actual model differs, classify as standard challenger evidence.
- Workspace skills are primary: `veritas-*`, SMB, WF67, cron, SQLite, Windows, implementation/review/refactor/governor/QA.
- Use `cron-automation-manager` for scheduled workflow design; `disciplined-implementation` for scripts, validators, manifests, workflow code, and boot/control surfaces.
- After material skill changes, update `06. Playbooks\Skills Governance Index.md`, then run `openclaw skills check`.

## Windows / PowerShell

- Do not use Bash-style `&&` or `||`; use `; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE };`.
- Do not wrap commands in `cmd /c`, nested `powershell -Command`, `&`, or WSL unless explicitly asked.
- Use backslashes and quote paths with spaces.
- For multiline Python, prefer a single-quoted here-string piped to Python.
- Avoid PowerShell redirection for JSON/UTF-8 artifacts; use Python writers.
- If a binary appears missing, check known wrappers/full paths before concluding it is unavailable.

## Config, Security, And Finance Boundary

- Prefer first-class Gateway/config tools; inspect active config/schema/value before editing.
- Ask before changing auth, credentials, network exposure, permissions, channels, startup, service, plugin, or runtime files outside the workspace.
- Local Control UI remains the trusted operating surface and stays local-only unless trusted exposure is explicitly approved.
- Telegram is enabled for Randall with narrow owner allowlisting and mention-gating; Discord/other chat remains disabled unless separately approved.
- Never expose tokens, OAuth credentials, API keys, or gateway secrets.
- Generated packets never imply approval, allocation, execution entitlement, trade/account authority, or external approval.
- Automated non-capital research/routing/tier state is allowed through validated derived artifacts.
- Portfolio/canon maintenance needs exact gate, proposal, preview/diff, validator proof, backup/rollback, and audit trail.
- Live trading, live credentials/endpoints, brokerage/account changes, money movement, and inferred approval remain blocked.
- Paper submit/cancel/sell requires WF63/WF67 paper-only guardrails, fresh kill switch, exact scoped artifact, notification, and Randall exact approval.

## Operating Notes

- Use `memory/` for chronological logs; do not create a parallel daily-memory system.
- `CLAUDE.md` is retained for external-process compatibility only and is not active doctrine.
- Root `tools/` is a local tool-runtime exception for workspace helpers such as `tools\otelcol`; not canon, approval, portfolio, account, or execution.
- Root `skills-backup/` is a non-runtime backup/provenance exception; active skills remain under `skills/`, and cleanup/archive still requires the gated reference-review path.
- Helper lanes need context, deliverable, proof, stop lines, and boundaries.
- Do not remove the OpenClaw Startup-folder launcher unless persistence is re-verified live.
