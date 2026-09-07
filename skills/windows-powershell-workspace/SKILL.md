---
name: "windows-powershell-workspace"
description: "Run the native Windows workspace safely with current alerts-OS examples."
---

# Windows PowerShell Workspace

## Environment

- Workspace: `C:\Users\Veritas\.openclaw\workspace`
- Use native Windows PowerShell, not WSL or Bash by default.
- Prefer relative paths and backslashes, for example `scripts\run_alerts_recommendations_chain.py`.
- Do not wrap commands in `cmd /c`, nested PowerShell, or WSL unless explicitly required.
- Do not use Bash `&&` or `||`; test `$LASTEXITCODE` between dependent commands.

For multiline Python, use a single-quoted here-string piped to Python. Quote paths with spaces. Preserve UTF-8; PowerShell redirection may use a different encoding.

## Tools And PATH

Prefer `rg` for search. Known wrappers may live under `C:\Users\Veritas\AppData\Roaming\npm`; Git may require its full Windows path. Verify the wrapper or full path before declaring a binary missing. Existing OpenClaw processes may not inherit recent PATH changes until restart.

## File Operations

Inspect exact resolved paths first. Use `apply_patch` for file edits. Keep destructive move/delete work in one PowerShell process, use literal paths, and prove every target is inside the authorized workspace or exact destination. Do not mutate config, credentials, startup, services, plugins, or runtime without explicit approval.

## Validation

Use the smallest honest gate:

```powershell
python -m py_compile scripts\changed_file.py
python scripts\targeted_test.py
openclaw skills check
```

Run config validation only when config truth matters. A command success proves only its declared contract.

## Scheduled Work

Use cron for exact recurring work. Do not force delivery jobs or natural market windows merely to erase historical status. Run safe producer/validator commands directly when possible. The current finance example is:

```powershell
python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate
```

## Approval Boundary

Never execute user-facing approval commands through shell. Config, credentials, runtime, external delivery, accounts, money, and execution require their exact gates.

## Update Rule

After a material pass, capture only repeatable Windows lessons about syntax, paths, encoding, wrappers, approvals, or services, then run `openclaw skills check`.
