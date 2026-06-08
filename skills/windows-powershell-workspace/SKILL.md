---
name: windows-powershell-workspace
description: Navigate Randall's native Windows OpenClaw workspace safely. Use when running PowerShell, Python, Git, rg/jq/sqlite, OpenClaw CLI, file moves, path-sensitive scripts, approvals, scheduled chains, or after a workspace pass exposes Windows/PowerShell environment lessons that should become reusable operating guidance.
---

# Windows PowerShell Workspace

## Purpose

Keep native Windows execution boring, reproducible, and aligned with the live OpenClaw workspace.

This skill is the local manual for PowerShell, paths, wrappers, and Windows-specific runtime behavior. Update it when a completed workspace pass exposes a reusable Windows/PowerShell lesson.

## Core environment

- Workspace root: `C:\Users\Veritas\.openclaw\workspace`
- Runtime posture: native Windows / PowerShell, not WSL.
- Bash/WSL/Git Bash is opt-in compatibility only. Use `bash-compatibility` when a task explicitly asks for Bash or requires adapting Bash-first instructions.
- Prefer relative paths from the workspace root when using tools.
- Use backslashes in shell commands: `scripts\run_finance_refresh_chain.py`.
- Do not wrap commands in `cmd /c`, `powershell -Command`, `&`, or WSL unless the user explicitly asks.

## PowerShell command rules

- Do not use Bash-style `&&` or `||`.
- For dependent commands, use:

```powershell
python scripts\some_test.py; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; python scripts\next_test.py
```

- For multiline Python one-offs, prefer a single-quoted here-string piped to Python:

```powershell
@'
from pathlib import Path
print(Path.cwd())
'@ | python -
```

- Avoid fragile redirection for JSON samples when encoding matters. Prefer Python `Path.write_text(..., encoding="utf-8")` or existing atomic-write helpers.
- PowerShell `>` may write UTF-16 depending on host/version; do not assume redirected files are UTF-8.
- Quote paths with spaces, especially numbered vault folders like `06. Playbooks\...`.

## Local wrappers and PATH drift

The live OpenClaw process may not inherit recent PATH changes until restart. Known wrappers / full paths:

- `rg.cmd`, `jq.cmd`, and `sqlite3.cmd` live in `C:\Users\Veritas\AppData\Roaming\npm`.
- Git for Windows is installed at `C:\Users\Veritas\AppData\Local\Programs\Git\cmd\git.exe`; use the full path if plain `git` is unavailable.
- Obsidian CLI compatibility wrappers also live under `C:\Users\Veritas\AppData\Roaming\npm`.
- ClawHub CLI shims live in `C:\Users\Veritas\.openclaw\tools\node\npm`; if `openclaw skills check` says `clawhub` is missing while `openclaw skills search` works, verify this folder is in user PATH and remember existing OpenClaw processes may need restart/new sessions to inherit the change.

If a binary appears missing, verify wrapper/full-path reality before concluding the tool is not installed.

## Windows command false positives

Some failures are shell/path problems, not workflow failures:
- Avoid passing path wildcards such as `tmp\wf75-*.json` as if every tool will expand them. Use `rg -g "*.json" <pattern> tmp` or `Get-ChildItem` to enumerate files first.
- When launching tools from Python `subprocess` without `shell=True`, resolve shims with `shutil.which(...)` before execution; bare shim names can fail even when PATH checks appear to pass.
- Decode subprocess output with UTF-8 plus replacement when capturing OpenClaw output that may include symbols.

Classify noisy command failures with:

```powershell
python scripts\veritas_harness_failure_classifier.py --text "<error text>" --write
```

## File-operation posture

- Inspect before editing.
- Back up core files, skills, config, and control surfaces before modifying them.
- Use `edit` or `apply_patch` for targeted workspace edits.
- Use Python for larger structured rewrites or UTF-8-safe file generation.
- Do not mutate config, credential, startup, service, plugin, or runtime files outside the workspace without explicit approval.

## Validation patterns

For coding/workflow changes, choose the smallest honest gate:

```powershell
python -m py_compile scripts\changed_file.py
python scripts\targeted_test.py
python scripts\validate_canonical_ownership.py
python scripts\validate_dashboard_state.py --write
```

For skill/operator changes:

```powershell
openclaw skills check
openclaw status
```

Run `openclaw config validate` only when config was inspected/changed or config truth matters.

## Exec approval posture

- Approvals are two-layer: OpenClaw exec policy plus host-local durable approvals in `~/.openclaw\exec-approvals.json`.
- Scheduled Python chains should use narrow exact-command durable approvals, not broad interpreter allowlists.
- Never execute `/approve` through shell/tools; it is a user-facing approval command.

## Scheduled-chain caution

- Do not force natural finance windows just to prove cron if that would create duplicate state-history/freshness noise.
- For exact timing or reminders, use cron rather than `Start-Sleep`, polling loops, or background sleep.

## Update rule

After a meaningful workspace pass, ask:

1. Did PowerShell syntax, encoding, PATH, wrapper, approval, or Windows service behavior affect the work?
2. Did a workaround become repeatable?
3. Would adding one concise rule here prevent a future false start?

If yes, update this skill in the same closeout pass and validate with `openclaw skills check`.
