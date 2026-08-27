# TOOLS.md - Local Runtime And Route Map

Details: skills, playbooks, scripts README, memory.

## Local Setup

- Root: `C:\Users\Veritas\.openclaw\workspace`
- Config: `~/.openclaw/openclaw.json`; continuity: `memory/` and `MEMORY.md`.
- Runtime: native Windows/PowerShell; do not assume Bash/WSL.
- OpenClaw `2026.7.1-2`; doctor/security warnings: `migration-review.md`.
- Shims: SQLite/rg/jq in `AppData\Roaming\npm`; Git in `AppData\Local\Programs\Git\cmd\git.exe`.
- Go freshness: `python scripts\go_binary_freshness_guard.py --write --validate`; rebuild when source is newer than `bin\*.exe`.
- Implementation route owner: `python scripts\project_implementation_router.py ... --validate` (`veritas.execution_efficiency_policy.v1`). Order: `model_free_command` first; explicit bounded `codex_native_subagent` on `openai/gpt-5.6-terra`; explicit Main/Sol only for quick fix, final integration, or authority-sensitive judgment; otherwise `persistent_isolated_agent` on Terra only with fresh strict context-transport proof. No silent Main/Sol fallback. Proven deterministic cron/status/proof may use low-reasoning `openai/gpt-5.6-luna`; fallback `openai/gpt-5.5`; rollback/control `openai/gpt-5.4`; Spark is canary/proof only.

## Fast Routing

Use route/index/capsules first, then exact owner artifacts. Generated SQL/JSON/capsules route proof only; they are not canon, approval, portfolio, trade, account, paper, or live authority.

- Workflow lookup: `python scripts\workflow_router.py WF## --answer summary|next|blockers|helper|all`; refresh with `python scripts\workflow_router.py --all --write-capsules --validate`.
- Wiki retrieval: query `memory_search` with `corpus=wiki` for cold-session procedures and source maps; validate with `python scripts\wiki_bootstrap_validator.py --write --validate`. The canonical pages live under `wiki\`; the plugin-native retrieval mirror lives under `state\wiki-retrieval\`. Wiki results route to owners and never replace current JSON, canon, approval, or execution proof.
- Fast greeting/status: read `tmp\veritas-status-card-frontdoor.json` or run `python scripts\status_card_packet.py --read-only --frontdoor --render --validate`; use its hashed drilldown only for material/critical detail. Fall back to `startup_brief_packet.py --write --validate` only when the compact card is missing or critical.
- Future/compaction pickup: `python scripts\future_session_enhancement_packet.py --write --write-md --validate`.
- WF74 pickup: use startup/status/future summaries; for material pickup run `main_session_greenkeeper_controller.py --refresh-frontdoors --execute-safe --write --validate --append-ledger`, then inspect `tmp\workflow-blocker-followups.json`. No cron schedule/state mutation.
- Concurrent work: `python scripts\concurrent_lane_manager.py --status --write --validate`; lease exact writes with `--lease`, always declare `--phase` for model-driven work, tag running with `--set-status`, and close with `--complete ... --proof ...` plus exposed session/usage metadata or a truthful unavailable classification.
- Efficient implementation: router first; freeze at most 6 files / 120,000 bytes / 30,000 context tokens with `helper_lane_manifest.py`; revalidate with `swarm_completion_handshake.py`. Record actual route, attempt/retry, and 90-second incident SLA. QA is risk-budgeted, not automatic.
- Pause/resume: `python scripts\workflow_control_override.py hold <workflow_key> --reason "..." --validate`; `resume <workflow_key> --validate`.
- PM control: `python scripts\pm_control_packet.py --write --write-db --validate`; use `summary.stale_lane_digest` for PM-yellow drilldown. Legacy sidecars require `--write-compat`.
- Cron control: `python scripts\cron_control_packet.py --write --validate`; drill into freshness/scorecard only on attention, stale, or blocker signals.
- Cron patch/drift: `python scripts\cron_patch_manager.py ... --write --validate`; `python scripts\cron_contract_validator.py --write --validate`.
- Audit/QA: `wf73_control_plane_audit.py --write --validate`; `changed_file_validator_router.py --write --validate`; `validator_bundle_router.py --write --validate`; timing via `validator_timing_ledger.py --profile normal --write --validate`.
- OS preflights: `python scripts\artifact_staleness_explainer.py --write --validate`; `python scripts\lane_collision_preflight.py --write-path <path> --write --validate`; `python scripts\worktree_checkpoint_planner.py --write --validate`.
- Closeout: `python scripts\control_closeout_bundle.py --validation-budget shared --write --validate`; use `major` only for broad closeout.
- Release cleanup: run `implementation_release_contract.py --phase blocking --write --validate`; deterministic local metadata/proof residue gets a named adjacent lane, its failing gate, Go implementation profile, and closeout—never silent feature-scope expansion.
- Artifact lookup: `python scripts\artifact_index.py ...`; proof mirror is `tmp\veritas-artifact-index.sqlite`.
- OTEL ops: `python scripts\otel_ops_control.py --write --write-db --multi-window --validate`; local operational digest and multi-window summary only.
- Long jobs: `long_work_job_status_packet.py --write --write-md --validate`; use bounded `vector_memory_ollama_job_runner.py start|resume|status|validate ...`. Resume grants no extra authority.
- PM execution dry-run: `python scripts\pm_execution_loop.py --write --validate`; `--execute` only runs guarded review-only proof commands from PM jobs.
- DB lifecycle route: `db_lifecycle_manifest.py --write --validate` writes `tmp/db-lifecycle-manifest.json`; archive/delete uses `db_lifecycle_archive_apply.py` only after explicit owner approval, reference proof, and rollback. Workspace index is search support only.

## Finance Front Doors

- SQL/JSON guard: `finance_sql_canon_access.py --write --validate`. SQL owns approved structured current state, never approval/capital/execution/customer/portfolio-note authority. Lineage repair stays metadata-only with rollback proof.
- Ticker Q&A: SQL guard -> `finance_intelligence_state.py ticker <TICKER> --pretty` -> WF84 -> WF85. Prefer guarded SQL/JSON internally; retain source-open and Python/JSON fallback for stale, blocked, material, parity, or rollback cases. Check `trade_grade_os_freshness_cron_runner.py` before calling data ready; data readiness is not review, approval, or execution readiness.
- Markdown thinning: `md_finance_structured_drift_lint.py --write --validate`; Markdown keeps policy/decisions/reasoning, structured ticker fields stay in SQL/JSON proof.
- Ticker cards/full answers: `python scripts\artifact_index.py ticker-card|answer-packet <TICKER>`; `answer-packet` is a WF85-backed compatibility lookup.
- Paper position visibility: `alpaca_paper_position_sql_refresh.py refresh --create-kill-switch --expires-minutes 90`, then `finance_intelligence_state.py paper-positions`; visibility is not execution.
- Retail truth routing: `retail_truth_routing_contract.py`, `retail_answer_harness.py`, `retail_automation_control_plane.py`.
- WF78: router then `wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate`; non-capital feeder only. WF84 uses `canonical_finance_data_plane.py`; WF85 uses contract/cards then `trade_grade_full_answer_assembler.py`. Generated output is never approval.
- Macro: `macro_metrics_ingest.py`, `macro_signal_spine.py`, `macro_energy_supply_ingest.py`, `macro_geopolitical_sweep.py`, `macro_judgment_draft.py`; evidence only.
- Entry-band maintenance: `band_refresh.py` proposes; `auto_apply_entry_band_maintenance.py --dry-run|--apply` may apply only eligible posture-preserving `entry_band` rows through the bounded gate.

Finance detail: `scripts/README.md`, capsules, WF77/WF78 continuity, exact owners. Source-open before material recommendation/action claims.

## Current Workflow Routes

- WF75 and WF79-SMB remain paused unless Randall resumes them. WF78 feeds non-capital repair into review-only WF84/WF85. WF80-WF83 remain hold/resume-later with public/customer/spend/execution gated. PM cockpit is local/read-only.

## Model / Skill Layer

- Main posture: live truth surface, orchestrator, QC owner, final integrator.
- Serious-work challenger: use verified `claude-cli/claude-opus-4-8` for WF84/WF85-class gates when warranted; if actual model differs, classify as standard challenger evidence.
- Workspace skills are primary (`veritas-*`, SMB, WF67, cron, SQLite, Windows, implementation/review/refactor/governor/QA). Use `cron-automation-manager` for schedules and `disciplined-implementation` for scripts, validators, manifests, workflows, and boot/control surfaces.
- After material skill changes, update `06. Playbooks\Skills Governance Index.md`, then run `openclaw skills check`.

## Windows / PowerShell

- Native PowerShell only: no Bash `&&`/`||`, `cmd /c`, nested PowerShell, WSL, or unnecessary `&`. Use backslashes/quoted paths, here-strings for multiline Python, and Python writers for JSON/UTF-8. Check known full paths before declaring a binary missing.

## Config, Security, And Finance Boundary

- Use first-class config tools and inspect active schema. Ask first before any auth, credential, exposure, channel, config, startup, service, plugin, or runtime change, because those reach outside the workspace. The local Control UI remains the trusted operating surface. Telegram is the one approved Telegram exception: it is enabled but narrowly scoped by owner allowlisting to Randall's owner ID with group mention-gating, so no unapproved chat expansion is implied. Discord and any other chat channel remain disabled. Never expose secrets. Generated packets grant no approval/execution authority. Portfolio/canon writes need exact gate, diff, proof, rollback, and audit. Live trading/account/money action stays blocked; paper action requires WF63/WF67, fresh kill switch, exact artifact, notification, and Randall's exact approval.

## Operating Notes

- Use `memory/` for chronological logs; do not create a parallel daily-memory system.
- `CLAUDE.md` is retained for external-process compatibility only and is not active doctrine.
- Root `tools/` is helper runtime only; `skills-backup/` is provenance only; active skills stay in `skills/`. Cleanup/archive remains gated.
- Keep the Startup launcher unless persistence is re-verified live.
