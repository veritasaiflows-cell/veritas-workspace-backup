---
name: bash-compatibility
description: Use when a task explicitly asks for Bash, WSL, Git Bash, POSIX shell snippets, Linux/macOS-style commands, or when adapting Bash-first docs/scripts inside Randall's native Windows OpenClaw workspace. This is an opt-in compatibility lane; PowerShell remains the default runtime.
---

# Bash Compatibility

## Purpose

Run or translate Bash-first work without confusing it with the workspace's native Windows / PowerShell posture.

Use this skill only when Bash is explicitly requested, when upstream instructions are Bash-only, or when a script must be checked for cross-platform behavior.

## Default posture

- PowerShell remains the default shell for this workspace.
- Bash is opt-in compatibility, not the production operating surface.
- Do not migrate cron jobs, finance chains, approvals, or workspace control commands to Bash unless a separate migration is approved and validated.
- Do not assume WSL, Git Bash, or Unix paths exist. Detect them first.

## Detection first

Before using Bash for real work, verify the available lane from PowerShell:

```powershell
Get-Command bash -ErrorAction SilentlyContinue
bash --version
```

If WSL behavior matters, also check:

```powershell
wsl.exe --status
wsl.exe --list --verbose
```

Record which lane is being used:

- `wsl`: Linux filesystem semantics and `/mnt/c/...` paths.
- `git-bash`: Windows process with POSIX-like shell semantics.
- `none`: translate the command to PowerShell instead.

If detection fails, do not pretend Bash is available.

## Path rules

PowerShell workspace path:

```text
C:\Users\Veritas\.openclaw\workspace
```

Likely WSL path:

```text
/mnt/c/Users/Veritas/.openclaw/workspace
```

Git Bash may accept:

```text
/c/Users/Veritas/.openclaw/workspace
```

Always confirm with `pwd` before running path-sensitive commands. Never mix Windows and WSL paths in the same command unless the tool explicitly supports it.

## Translation rules

When adapting Bash snippets to native PowerShell:

- Replace `&&` with `; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE };`.
- Replace `/` paths with workspace-relative backslash paths where practical.
- Replace `export NAME=value` with `$env:NAME='value'`.
- Replace `cat file | cmd` with `Get-Content -LiteralPath file | cmd` only when text encoding is safe.
- Prefer Python here-strings for complex JSON or multiline content.
- Do not use Bash redirection for workspace JSON proof artifacts unless encoding has been verified.

## Safe Bash usage

Use Bash directly only for bounded, reversible tasks such as:

- running upstream Bash-only examples after detection;
- checking POSIX shell compatibility;
- testing a portable script in WSL/Git Bash;
- translating Linux/macOS instructions into PowerShell-safe commands.

Avoid Bash for:

- scheduled finance chains;
- OpenClaw config/auth/channel/runtime mutation;
- approvals or `/approve` flows;
- credential handling;
- paper/live brokerage actions;
- destructive file operations;
- Windows service/startup changes.

## Validation

After a Bash compatibility pass, validate through the native workspace surface:

```powershell
openclaw skills check
```

For changed scripts, also run the native PowerShell/Python validation expected by the owning workflow. Passing in Bash alone is not enough for this Windows-native workspace.

## Closeout rule

State plainly:

- which Bash lane was used, if any;
- what was translated versus executed;
- whether native PowerShell validation also passed;
- any remaining portability or path risk.
