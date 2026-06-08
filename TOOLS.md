# TOOLS.md - Local Runtime And Route Map

Keep only environment facts, global tool rules, and first-hop routes here. Procedures live in skills/playbooks; detailed command catalogs live in `scripts/README.md`; history lives in `memory/`.

## Local Setup

- Root: `C:\Users\Veritas\.openclaw\workspace`
- Config: `~/.openclaw/openclaw.json`; daily notes: `memory/`; durable memory: `MEMORY.md`.
- Runtime: native Windows / PowerShell; do not assume Bash/WSL semantics.
- OpenClaw runtime: `2026.6.1`; post-update validation passed on 2026-06-05 with known doctor/security warnings in `migration-review.md`.
- SQLite/rg/jq wrappers: `C:\Users\Veritas\AppData\Roaming\npm`; Git fallback: `C:\Users\Veritas\AppData\Local\Programs\Git\cmd\git.exe`.
- Go validator freshness: `python scripts\go_binary_freshness_guard.py --write --validate`; rebuild all Go validators from `scripts\go` when source is newer than `bin\*.exe`.
- ClawHub CLI shims: `C:\Users\Veritas\.openclaw\tools\node\npm`.
- Codex route: main/new sessions default to `openai/gpt-5.5`; bounded helper lanes use `openai/gpt-5.4` (`gpt54`) unless the task justifies otherwise. Spark (`codex/gpt-5.3-codex-spark`) is for bounded canary/proof/QA/pre-work with `xhigh` thinking until repeated proof says otherwise.

## Fast Routing

Use route/index/capsule surfaces first, then exact owner artifacts. Generated SQL/JSON/capsules are proof/routing surfaces only; they are not canon, approval, portfolio, trade, account, paper, or live authority.

- Workflow lookup: `python scripts\workflow_router.py WF## --answer summary|next|blockers|helper|all`.
- Future-session startup packet: `python scripts\future_session_enhancement_packet.py --write --write-md --validate`; open this first after compaction/new-session handoff to route PM, cron, WF74, workflow, memory, and stop-line state without broad scans.
- Workflow capsules: `python scripts\workflow_router.py --all --write-capsules --validate` writes `state\workflows\*.json`.
- Pause/resume: `python scripts\workflow_control_override.py hold <workflow_key> --reason "..." --validate`; `resume <workflow_key> --validate`.
- PM control: `python scripts\pm_control_packet.py --write --write-db --validate`; legacy sidecars require explicit `--write-compat`.
- PM sidecar guard: `python scripts\pm_sidecar_retirement_guard.py --write --validate`.
- Cron control: `python scripts\cron_control_packet.py --write --validate`; drill into components only when this packet reports attention/stale/noisy signals.
- OTEL ops: `python scripts\otel_ops_control.py --write --write-db --validate`; local operational digest only.
- WF74 model-quality collection: `python scripts\wf74_model_quality_collection_cron_runner.py --write --write-md --validate --include-harness`; scheduled by `Ops - OTEL Local Digest` at 07:40, 15:40, and 21:40 America/Phoenix. Review-only evidence; no model ranking, WF55 outcome grading, portfolio/canon mutation, or execution authority.
- WF74 cron duplication audit: `python scripts\wf74_cron_duplication_audit.py --write --validate`; confirms WF74 component ledgers are not scheduled outside the single owner job.
- Training/eval candidate review: `python scripts\training_dataset_candidate_builder.py --write --write-md --validate`; local metadata-only candidate index for future eval/fine-tune review. No raw prompt/chat export, no upload, no training call, no model-weight mutation.
- Skill local git checkpoint: `python scripts\skill_git_checkpoint.py --write --validate`; use `--commit --message "..." --tag-name ...` only for explicit local skill-layer checkpoints. Stages only `skills/`, Skills Governance Index, and today's memory file; no external push.
- Validation routing/timing: `python scripts\changed_file_validator_router.py --write --validate`; `python scripts\validator_timing_ledger.py --profile normal --write --validate`.
- Artifact lookup: `python scripts\artifact_index.py ...`; SQL proof mirror is `tmp\veritas-artifact-index.sqlite`.
- Fast QA: `python scripts\truth_surface_inventory.py --write --validate`; `python scripts\fast_path_qa.py --write --validate`.
- Integration closeout: `python scripts\control_closeout_bundle.py --validation-budget shared --write --validate`; use `major` only for broad control-plane closeout.
- PM execution dry-run: `python scripts\pm_execution_loop.py --write --validate`; `--execute` only runs guarded review-only proof commands from PM jobs.
- DB lifecycle: `python scripts\db_lifecycle_manifest.py --write --validate`; archive/delete only through explicit owner-approved lifecycle apply paths.
- Workspace search/index: `python scripts\workspace_index.py`; proof/search support only.

## Finance Front Doors

- Ticker Q&A: `python scripts\finance_intelligence_state.py ticker <TICKER> --pretty`.
- Ticker cards/answer packets: `python scripts\artifact_index.py ticker-card|answer-packet <TICKER>`.
- Paper position visibility only: `python scripts\alpaca_paper_position_sql_refresh.py refresh --create-kill-switch --expires-minutes 90`, then `python scripts\finance_intelligence_state.py paper-positions`.
- Retail truth routing: `retail_truth_routing_contract.py`, `retail_answer_harness.py`, `retail_automation_control_plane.py`.
- WF78 front door: `workflow_router.py WF78 --answer all`, then WF78 phase/freshness/decision-factory artifacts as needed.
- Macro inputs: `macro_metrics_ingest.py`, `macro_energy_supply_ingest.py`, `macro_geopolitical_sweep.py`, then `macro_judgment_draft.py`; review-only evidence, no forecast/capital/execution authority.
- Entry-band maintenance: `band_refresh.py` proposes; `auto_apply_entry_band_maintenance.py --dry-run|--apply` may apply only approved posture-preserving `entry_band` rows marked eligible by the gate.

Finance detail lives in `scripts/README.md`, workflow capsules, WF77/WF78 continuity, and exact owner artifacts. Source-open exact artifacts before material recommendation/action claims.

## Current Workflow Routes

- P0 Retail/WF75: `workflow_router.py WF75 --answer all`; customer/public/account/advice remains blocked.
- SMB Workflow Clarity: owner-paused; verify with `workflow_router.py WF79-SMB --answer all`; do not advance unless Randall explicitly resumes it.
- WF78 scaleout/promotion: route through WF78 front doors, not ad hoc component scripts.
- Product scaleout WF80-WF83: hold/resume-later; customer/public launch, spend, outreach, legal/compliance/security claims, and finance execution authority remain gated.
- PM cockpit: `apps\pm-control-cockpit`, `state\pm-cockpit-source-registry.json`, local `http://127.0.0.1:8765`; read-only.
- Cron awareness: read `tmp\cron-control-packet.json` first, then cron freshness/scorecard/escalation only when needed.

## Model / Skill Layer

- Main posture: live truth surface, orchestrator, QC owner, final integrator.
- Workspace skills are primary: `veritas-*`, SMB, WF67, cron, SQLite, Windows, implementation/review/refactor/governor/QA.
- Use `cron-automation-manager` when designing/rebuilding scheduled workflows.
- Use `disciplined-implementation` when changing scripts, validators, manifests, workflow code, or boot/control surfaces.
- After adding/removing/materially changing skills, update `06. Playbooks\Skills Governance Index.md`, then run `openclaw skills check`.

## Windows / PowerShell

- Do not use Bash-style `&&` or `||`; use `; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE };`.
- Do not wrap commands in `cmd /c`, nested `powershell -Command`, `&`, or WSL unless explicitly asked.
- Use backslashes and quote paths with spaces.
- For multiline Python, prefer a single-quoted here-string piped to Python.
- Avoid PowerShell redirection for JSON/UTF-8 artifacts; use Python or existing writers.
- If a binary appears missing, check known wrappers/full paths before concluding it is unavailable.

## Config And Security

- Prefer first-class Gateway/config tools; inspect active config/schema/value before editing.
- Ask before changing auth, credentials, network exposure, permissions, channels, startup, service, plugin, or runtime files outside the workspace.
- Control UI local-only unless trusted proxy is deliberately approved.
- Telegram is enabled for Randall with narrow owner allowlisting and mention-gating; Discord/other chat remains disabled unless separately approved.
- Never expose tokens, OAuth credentials, API keys, or gateway secrets in logs or chat.

## Finance Boundary

- Generated packets never imply owner approval, allocation, execution entitlement, trade/account authority, or external approval.
- Automated non-capital research/routing/tier state is allowed through validated derived artifacts.
- Portfolio/canon maintenance needs the exact approved gate, proposal, preview/diff, validator proof, backup/rollback, and audit trail.
- Live trading, live credentials/endpoints, brokerage/account changes, money movement, and inferred approval remain blocked.
- Paper submit/cancel/sell requires WF63/WF67 paper-only guardrails, fresh kill switch, exact scoped artifact, notification, and Randall exact approval.

## Operating Notes

- Use `memory/` for chronological logs; do not create a parallel daily-memory system.
- `CLAUDE.md` is retained for external-process compatibility only and is not active doctrine.
- Helper lanes need context, deliverable, proof, stop lines, and boundaries.
- Do not remove the OpenClaw Startup-folder launcher unless persistence is re-verified live.
