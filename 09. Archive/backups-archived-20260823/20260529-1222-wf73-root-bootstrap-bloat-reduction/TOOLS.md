# TOOLS.md - Local Environment and Runtime Notes

Keep this file for environment facts and global tool rules only. Procedures belong in skills; history belongs in `memory/`.

## Local setup

- Workspace root: `C:\Users\Veritas\.openclaw\workspace`
- OpenClaw config: `~/.openclaw/openclaw.json`
- Daily notes: `memory/`
- Durable memory: `MEMORY.md`
- Home note: `Home.md`
- Active runtime posture: native Windows / PowerShell
- Obsidian vault should point at the workspace root, not `.obsidian/`.
- Obsidian CLI is `notesmd-cli.exe` v0.3.6 with local `obsidian-cli` / `obsidian` wrappers in `C:\Users\Veritas\AppData\Roaming\npm`; default vault `workspace` -> workspace root.
- SQLite CLI is installed via Winget with `sqlite3.cmd` wrapper in `C:\Users\Veritas\AppData\Roaming\npm`.
- Veritas SQL cockpit: `scripts/artifact_index.py` maintains `tmp/veritas-artifact-index.sqlite` as the primary fast generated-artifact/proof/provenance/staging lookup surface. Preferred commands: `cockpit`, `ticker-cockpit`, `trust-cockpit`, `proof-field`, `stoplines`, `validate`, `rebuild`, and `incremental`. It is derived proof/index/staging only, not canon, approval, apply authority, or trade/account/paper authority. Separate from that, `tmp/veritas-canon-cache.sqlite` has bounded SQL proof/cache authority for exactly 265 approved metadata rows: 13 low-risk proof/freshness/lifecycle keys plus 252 WF72 entry/stop reference metadata rows. For questions about SQL truth/canon authority, check Active Workflows, the SQLite skill, and/or the live canon-cache DB before answering.
- Question/coverage routing posture: new sessions should answer recurring inventory/review questions by routing through registries and indexes first, then opening exact sources. For finance, the target surfaces are `tmp/finance-data-coverage-current.json`, enriched ticker intelligence cards under `tmp/ticker-intelligence-cards/`, `scripts/finance_intelligence_state.py` read-only packets (`ticker`, `preopen`, `stale-tickers`, `pending-approvals`, `validator-status`, `source-proof`, `entry-stop-refs`, `action-queue`, `phase3-qc`, `paper-positions`), and `artifact_index.py` read-only commands `data-coverage`, `missing-data`, `ticker-card`, `answer-contract`, and `validate-answer-contract`. Coverage currently targets the 42-ticker registry; ticker cards and SQL packets are review/routing dossiers only and include source-open/authority boundaries. Paper-position visibility routes through `tmp/wf67-paper-position-state.sqlite` via `finance_intelligence_state.py paper-positions`; `tmp/alpaca-paper-readiness/current-paper-holdings-readonly.json/.md` are compatibility exports only. Use `answer-contract` or the finance-intelligence-state packet answer contract for material finance/readiness/recommendation/authority answers, then inspect the listed exact source artifacts/canonical notes before making claims. Do not substitute broad workspace search for a missing coverage/card/contract/query surface without marking that as a system gap.
- Retail Investor Finance Intelligence SaaS routing: for product/SaaS/workflow-pivot questions, start with Active Workflows P0, `06. Playbooks/Workflow Alias Index.md`, `tmp/handoff-current.json`, WF75 continuity, and the retail SaaS proof packets before broad search; customer/public use remains blocked until privacy/source/counsel/export-validator gates are resolved.
- `rg.cmd` and `jq.cmd` wrappers live in `C:\Users\Veritas\AppData\Roaming\npm` because live OpenClaw PATH may lag until restart.
- ClawHub CLI shims live in `C:\Users\Veritas\.openclaw\tools\node\npm`; this folder was added to the user PATH on 2026-05-17. Existing OpenClaw processes may need restart/new sessions to inherit it.
- Git for Windows: `C:\Users\Veritas\AppData\Local\Programs\Git\cmd\git.exe`; use full path if plain `git` is unavailable.
- Plugin skill publication depends on Windows symlink privilege. If logs show `EPERM` / `WinError 1314` for `~/.openclaw/plugin-skills`, fix symlink privilege first, preferably Windows Developer Mode.
- Current intentionally approved OpenClaw runtime after Randall's 2026-05-29 update: `2026.5.27`. Revalidate runtime health after any further update before relying on finance/cron answers.
- Historical compatibility note: external `@openclaw/codex` plugin was uninstalled on 2026-05-25 because installed plugin `2026.5.20` was version-skewed against then-pinned OpenClaw core `2026.5.4` and broke `openclaw security audit --deep --json`; keep using `openai-codex/*` PI/OAuth routing unless native Codex is deliberately re-approved with a compatible pinned plugin/core plan.
- `web_search` is available through the configured Ollama-backed route as of 2026-05-10; verify finance claims with primary sources via `web_fetch`, SEC, company IR, or the inspected local `sec` skill when official EDGAR evidence is needed.
- ClawHub `sec` skill is installed at `skills/sec` as of 2026-05-17 with an isolated `.venv`; SEC User-Agent is `Veritas OpenClaw Research veritasaiflows@gmail.com`; bounded smoke test passed. Treat it as official-source evidence tooling only, subordinate to WF65/WF66 validators and never as portfolio/canon/trading authority.

## Model routing

- Main/default posture: live truth surface, workspace-file interpreter, portfolio-change proposal engine, orchestrator, QC owner, and final integrator.
- Default top-level model policy: `openai-codex/gpt-5.5` primary, with allowed set constrained to `openai-codex/gpt-5.5`, `openai-codex/gpt-5.4`, and `openai-codex/gpt-5.3-codex` unless Randall changes policy.
- Use OpenAI Codex OAuth-backed routing by default; verify route availability before relying on a new model.
- Spawned subagents should stay inside allowed `openai-codex/*` and select thinking by role: low for routine audit/research, medium for implementation, high for hard debugging or high-stakes trust adjudication.
- Claude and Gemini are manual IC/challenger surfaces only when Randall chooses them; do not treat their CLIs as automatic default routing paths.

## Skills and operating layer

- Bundled skill allowlist: `github`, `healthcheck`, `node-connect`, `skill-creator`, `taskflow`, `taskflow-inbox-triage`, `weather`.
- Workspace skills are the primary custom operating layer.
- Finance spine: `veritas-fundamental-pass`, `veritas-technical-pass`, `veritas-macro-pass`, `veritas-positioning-pass`, `veritas-financial-planning-pass`, `veritas-investment-deck`, `veritas-pdf-brief`, `veritas-portfolio-update`, `veritas-post-earnings-sync`, `veritas-weekly-brief`.
- Official-source tooling: `sec` supports EDGAR/company-facts/filing retrieval for evidence capture only; use through its local `.venv` and preserve provenance in review packets.
- Response/continuity/operator spine: `veritas-response-contract`, `veritas-self-improvement`, `memory-continuity-manager`, `project-continuity-manager`, `openclaw-operator`, `openclaw-troubleshooter`, `cron-automation-manager`, `operating-procedure-repository-manager`, `workspace-governor`, `workspace-qa-pass`, `wf67-paper-trading-operator`.
- Coding spine: `disciplined-implementation`, `code-review-auditor`, `safe-refactor-planner`, `SQLite`, `windows-powershell-workspace`, `bash-compatibility`.
- Retrieval restored as of 2026-05-09: `obsidian` and `SQLite`. For generated finance/OS artifacts, use the Veritas SQL cockpit before broad file scans when it can answer the routing/provenance question.
- Fast-answer discipline: classify the user's question first (`coverage`, `missing evidence`, `freshness`, `proof`, `ticker intelligence`, `recommendation support`, `authority/guardrail`, `workflow status`). Use the owner registry/index for that class before reading large files or running broad search. Source-open rule still applies before final finance, readiness, recommendation, or action claims.
- Validate skill state with `openclaw skills check` after skill changes.

## Manual IC / Cowork packages

External/manual packages are not OpenClaw-managed helper lanes. Use only when Randall chooses them.

| Skill | Trigger | Owns |
|---|---|---|
| `veritas-weekly-brief` | weekly brief / weekly sweep / market sweep | End-to-end Weekly Intelligence Brief |
| `veritas-portfolio-update` | portfolio sweep / update entry bands | Portfolio Snapshot, Execution Board, Watchlist sync |
| `veritas-deep-dive` | deep dive / research ticker / build thesis | Thesis template, coverage universe, evidence standard |

Document packages: `docx`, `pdf`, `xlsx`, `pptx`, `schedule`, `skill-creator`.

## Config posture

- Prefer first-class Gateway/config tools when available; otherwise inspect active config, schema/docs, and current value before editing.
- Ask before changing auth, credentials, network exposure, permissions, channels, startup, service, plugin, or runtime files outside the workspace.
- Keep Control UI local-only unless trusted proxy configuration is deliberately added.
- Current channel posture: local Control UI is trusted; all chat channels are intentionally disabled. Validator-friendly expected posture: `channels {}`, `telegram.enabled=false`, `discord.enabled=false`, and no external `ownerAllowFrom` authority beyond local Control UI. Telegram was removed/disabled and Discord remains disabled. Future channel expansion must explicitly restore intended channel, policies, allowlists, mention behavior, and owner allowlists.
- Never expose tokens, OAuth credentials, API keys, or gateway secrets in logs or chat.
- Treat gateway-token rotation as multi-file cleanup: check config, backups, `.last-good`, migration backups, and transcript artifacts.
- Exec approvals are two-layer: OpenClaw tool policy plus host-local durable approvals in `~/.openclaw/exec-approvals.json`. Scheduled finance chains should use narrow exact-command durable approvals.

## Windows / PowerShell rules

- Do not use Bash-style `&&` or `||` in PowerShell. Use `; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE };` for dependent commands.
- Do not wrap commands in `cmd /c`, `powershell -Command`, `&`, or WSL unless explicitly asked.
- Use backslashes in shell commands and quote paths with spaces.
- For multiline Python, prefer a single-quoted here-string piped to Python.
- Avoid PowerShell redirection for JSON/UTF-8 artifacts; use Python or existing writers.
- If a binary appears missing, check known wrappers/full paths before concluding it is unavailable.

## Tool safety rules

- Inspect before editing.
- Back up core files/config/control surfaces before modifying them.
- Prefer reversible changes and explicit validation.
- Use tools proactively and efficiently: batch independent reads/searches, prefer first-class tools over shell workarounds, spawn bounded subagents for long proof-heavy work, and avoid asking Randall for manual lookup when workspace artifacts or tools can answer safely.
- Do not claim a binary, plugin, route, scheduled chain, or service is ready until live behavior is verified.
- Do not install unaudited third-party finance skills without Randall's approval.
- Use `cron` for reminders/delayed follow-ups; do not emulate timers with sleep/poll loops.
- Long work should use spawned subagents or background processes with proof, not vague promises.

## Finance automation posture

Canonical finance authority lives in `SOUL.md`/`USER.md`; this file keeps only runtime-routing facts.

- Cron may generate review-only packets/proposals; it must not apply canonical portfolio/intelligence edits or portfolio mutations.
- Veritas main session may apply bounded workspace finance/canon maintenance only through the standing-approved gated path: exact scope/artifact, approval source, validator proof, backup/rollback, post-apply validation, and audit trail.
- Generated packets never imply owner approval, allocation, execution entitlement, trade/account authority, or external approval.
- Live trading, live credentials/endpoints, brokerage/account changes, money movement, and inferred approval remain blocked.
- Paper trading is paper-only through WF63/WF67: paper endpoint, paper credentials, kill switch, redacted audit log, guard validation, explicit scoped request/pilot/advisor package, and main-session notification. Execution still requires Randall's exact approval for the order.
- Direct main-session WF67 request path: `scripts/wf67_order_card_request_generator.py`; advisor packet path: `scripts/wf67_advisor_paper_request_generator.py`. Read-only paper account/position freshness path: `scripts/alpaca_paper_position_sql_refresh.py refresh --create-kill-switch --expires-minutes 90`, then `scripts/finance_intelligence_state.py paper-positions`; this grants no submit/cancel/sell/live/account authority.

## Operating notes

- Use `memory/` for chronological logs; do not create a parallel daily-memory system.
- Scripts and long runbooks belong in `scripts/README.md` or skills, not here.
- `CLAUDE.md` is retained for external-process compatibility only and is not active doctrine.
- If browser availability matters, verify live browser state.
- In Control UI/webchat, prefer session-bound cron jobs for follow-up over disabled chat-channel delivery assumptions.
- Do not assume persistent thread-bound subagent sessions exist; use file-grounded continuity and fresh bounded subagents when needed.
- When spawning subagents, pass file-grounded context explicitly; do not rely on hidden session continuity.
- Spawned helper lanes should use explicit file-grounded handoff packets, role-based thinking, explicit timeout budgets, artifact-first partial output for long work, and named acceptance proof.
- Do not launch broad helper lanes without stop lines, files-to-read-first, ownership boundaries, and merge expectations.
- Do not remove the OpenClaw Startup-folder launcher unless persistence is re-verified live.
