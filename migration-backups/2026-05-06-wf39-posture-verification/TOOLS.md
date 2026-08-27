# TOOLS.md - Local Notes

Keep this file for environment facts and global tool rules only.
Procedures belong in skills.

## Local setup

- Workspace root: `C:\Users\Veritas.RQs_Business\.openclaw\workspace`
- OpenClaw config: `~/.openclaw/openclaw.json`
- Daily notes folder: `memory/`
- Long-term memory note: `MEMORY.md`
- Home note: `Home.md`
- Obsidian vault should point at the workspace root, not `.obsidian/` itself
- Obsidian CLI on this Windows host is provided by `notesmd-cli.exe` with local `obsidian-cli` / `obsidian` compatibility wrappers in `C:\Users\Veritas\AppData\Roaming\npm`; the default vault is `workspace` -> `C:\Users\Veritas\.openclaw\workspace`
- `rg` and `jq` are installed via Winget (`BurntSushi.ripgrep.MSVC`, `jqlang.jq`). Because the live OpenClaw process may not inherit Winget PATH changes until restart, local wrappers live in `C:\Users\Veritas\AppData\Roaming\npm\rg.cmd` and `jq.cmd`, matching the existing OpenClaw/npm command path.
- Active runtime posture: native Windows
- Plugin skill publication on this Windows host depends on directory symlink privilege. After an OpenClaw update or reinstall changes plugin target paths, `~/.openclaw/plugin-skills` may need fresh symlinks; if the runtime logs `EPERM` / `WinError 1314` while creating plugin-skill links, fix Windows symlink privilege first (prefer Developer Mode) instead of assuming the skill itself is missing.
- Current intentionally approved stable OpenClaw pin on this machine: `2026.5.4`. Randall accepted `2026.5.4` as the new stable runtime on 2026-05-05 after reinstall drift from the previous `2026.4.22` pin. Do not update OpenClaw again unless that stability judgment is intentionally revisited.
- `web_search` is currently unusable on this host because the SearXNG base URL is not configured. Until that is fixed, use native `openclaw skills search <term>` for ClawHub discovery and `web_fetch` for direct-page fallback instead of pretending a normal web-search pass happened.

## Model routing

- Primary posture for the main agent / new top-level sessions: live truth surface, canonical financial database interpreter, orchestration, QC, and final integration
- Primary model for spawned sub-sessions performing substantial workspace work: `openai-codex/gpt-5.5` with high-thinking posture when available
- Use OpenAI Codex OAuth-backed routing by default
- Verify live route availability before relying on `openai-codex/gpt-5.5`; if unavailable, keep the same bounded contract and record the fallback instead of silently downgrading trust
- Gemini Pro CLI (`gemini -m gemini-3.1-pro-preview`) is the preferred IC lane for implementation, script/code, and broad research passes when available
- Claude CLI is the hard-judgment lane for trust/contract adjudication and high-stakes review; increase effort (`--effort high` or above) when the task risk justifies it
- Gemini CLI in this environment does not expose a direct effort flag; scale effort via model choice, prompt depth, and bounded scope
- Veritas remains the orchestrator, auditor, and product owner/manager for queue movement and final integration
- Default workspace execution posture: use a bounded spawned `openai-codex/gpt-5.5` high-thinking subagent for work likely to exceed roughly five minutes, touch multiple artifacts, require broad inspection, or need independent QA; keep the main session for orchestration, QC, final integration, and quick bounded fixes
- Keep routed usage inside the approved `openai-codex/*` model set unless runtime policy is explicitly changed

## Skill posture

- Bundled skills must stay on an explicit allowlist
- Current bundled allowlist: `github`, `healthcheck`, `node-connect`, `skill-creator`, `taskflow`, `taskflow-inbox-triage`, `weather`
- Workspace skills are the primary custom operating layer
- Existing finance spine (OpenClaw): `veritas-fundamental-pass`, `veritas-technical-pass`, `veritas-macro-pass`, `veritas-positioning-pass`, `veritas-investment-deck`, `veritas-pdf-brief`, `veritas-self-improvement`, `workspace-governor`
- Operator skills now own repeatable OpenClaw procedures: `openclaw-operator`, `openclaw-troubleshooter`, `memory-continuity-manager`, `cron-automation-manager`, `operating-procedure-repository-manager`
- Local coding spine (2026-05-05): `disciplined-implementation` for acceptance-contract implementation passes, `code-review-auditor` for high-signal diff/contract review, and `safe-refactor-planner` for low-risk structural cleanup with parity gates
- `09. Archive/temp-skill-inspect - Archived/` holds scratch skill-inspection material; it is preserved for reference but is not an active skill root

## Cowork skills (Claude layer)

Installed via Cowork. These are separate from OpenClaw skills and run in Claude sessions, not OpenClaw agents.

| Skill | Trigger | Owns |
|---|---|---|
| `veritas-weekly-brief` | "run the weekly brief", "weekly sweep", "market sweep" | End-to-end WIB: scripts → research → write → log |
| `veritas-portfolio-update` | "update the portfolio", "portfolio sweep", "update entry bands" | Portfolio Snapshot, Trigger Sheet, Watchlist sync |
| `veritas-deep-dive` | "deep dive on [ticker]", "research [name]", "build a thesis" | Investment Thesis Template, Coverage Universe, evidence standard |

Skill packages (`.skill` files) are in `scripts/skills/`. Install via Cowork skill manager.

Document-layer skills also installed: `docx`, `pdf`, `xlsx`, `pptx`, `schedule`, `skill-creator`.

## Config posture

- Remove stale or ineffective `gateway.nodes.denyCommands` entries rather than trusting them
- Keep the Control UI local-only unless trusted proxy configuration is intentionally added
- For OpenClaw config changes, inspect the active config file, schema, and current value before editing; do not guess config paths or assume similar names mean the same thing
- Prefer `openclaw config set <path> "<value>"` over manual JSON edits when the CLI path supports it
- Validate config after edits with `openclaw config validate`
- Restart the gateway after important runtime-sensitive config changes, then verify with `openclaw config get <path>` plus `openclaw status`
- If runtime behavior does not match a default setting, inspect override surfaces with `openclaw config get agents.list --json`
- Never expose tokens, OAuth credentials, API keys, or gateway secrets in logs or chat
- Treat gateway-token rotation as a multi-file cleanup problem, not just a single-config edit: check `openclaw.json`, `.bak`, `.last-good`, migration backups, and session transcript artifacts for stale copies after any rotation.
- Exec approvals are a two-layer surface here: `tools.exec` policy in config plus host-local durable approvals in `~/.openclaw/exec-approvals.json`. On this Windows host, interpreter-launched scheduled chains like `python scripts\\run_finance_refresh_chain.py <window>` should use narrow exact-command durable approvals rather than broad interpreter safe-bins or guessed path allowlists.
- Ask before changing auth, network exposure, permissions, or destructive settings
- Validate skill state after skill changes with `openclaw skills check`

## Tool safety rules

- Inspect before editing
- Back up core files and config before modifying them
- Prefer reversible changes and explicit validation
- Do not claim a binary, plugin, or service is ready until it works live
- Do not install unaudited third-party finance skills without Randall's approval
- When skills or tool posture change, update `TOOLS.md` in the same workstream

## Operating notes

- Use `memory/` for chronological logs; do not create a parallel daily-memory system unless Randall explicitly changes the convention
- On this host's PowerShell, do not chain commands with `&&` or `||`; use `; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }` when a later step must stop on failure
- Scripts and long runbooks belong in `scripts/README.md` or skills, not here
- `CLAUDE.md` is retained for external-process compatibility only; it is not part of the active OpenClaw constitutional hierarchy
- If browser availability matters, verify live browser state instead of assuming it from prior notes
- In local webchat / Control UI work, prefer session-bound cron jobs for follow-up work over chat-channel fallback assumptions; delivery previews can look fail-closed even when the bound session target is the real route.
- Current channel hardening posture (2026-05-05): Discord and Telegram are intentionally locked to **DM-only** with explicit `allowFrom` owner IDs and `groupPolicy: "disabled"`; Telegram `groups` is intentionally `{}`. Before any future guild/group/channel expansion, reverse this deliberately from `openclaw.json` rather than assuming defaults: restore the intended `groupPolicy`, add explicit guild/group allowlists, set mention behavior intentionally, and re-audit `commands.ownerAllowFrom` so owner authority does not widen accidentally.
- Keep queue movement category-driven and trust-gated: classify major work by category and parallel posture before opening helper lanes, rather than treating every open item as parallel by default.
- In this local webchat / Control UI posture, do not assume thread-bound persistent subagent sessions are available. If `mode="session"` / `thread=true` subagent spawning is unavailable, use a continuity note plus a resume keyword that launches a fresh bounded subagent run against the file-based project context instead of pretending a live resumable worker exists.
- When spawning subagents in this environment, pass file-grounded context explicitly; do not rely on memory search or hidden session continuity to reconstruct critical project state.
- Do not remove the OpenClaw Startup-folder launcher unless persistence is re-verified live; status can imply Scheduled Task coverage while the Startup item still matters operationally.
