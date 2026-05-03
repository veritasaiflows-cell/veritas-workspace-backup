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
- Active runtime posture: native Windows
- Keep the current OpenClaw version. Do not update to `2026.4.26` during this migration.

## Model routing

- Primary model for new sessions: `openai-codex/gpt-5.4`
- Primary model for spawned sub-sessions: `openai-codex/gpt-5.4`
- Use OpenAI Codex OAuth-backed routing by default
- Do not assume direct `openai/gpt-5.4` works unless `OPENAI_API_KEY` was intentionally configured

## Skill posture

- Bundled skills must stay on an explicit allowlist
- Current bundled allowlist: `github`, `healthcheck`, `node-connect`, `skill-creator`, `taskflow`, `taskflow-inbox-triage`, `weather`
- Workspace skills are the primary custom operating layer
- Existing finance spine (OpenClaw): `veritas-fundamental-pass`, `veritas-technical-pass`, `veritas-macro-pass`, `veritas-positioning-pass`, `veritas-investment-deck`, `veritas-pdf-brief`, `veritas-self-improvement`, `workspace-governor`
- Operator skills now own repeatable OpenClaw procedures: `openclaw-operator`, `openclaw-troubleshooter`, `memory-continuity-manager`, `cron-automation-manager`
- `temp-skill-inspect/` is scratch inspection material, not an active skill root

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
- Validate config after edits with `openclaw config validate`
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
- Scripts and long runbooks belong in `scripts/README.md` or skills, not here
- `CLAUDE.md` is retained for external-process compatibility only; it is not part of the active OpenClaw constitutional hierarchy
- If browser availability matters, verify live browser state instead of assuming it from prior notes
