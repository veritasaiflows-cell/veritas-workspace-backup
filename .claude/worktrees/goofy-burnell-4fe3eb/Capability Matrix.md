# Capability Matrix

## Summary

This machine now has the core Tier 1 toolchain installed for Veritas.

## Tier 1 readiness

- `obsidian` skill: **patched for Windows** and aligned to this workspace vault
- `obsidian` CLI: **installed** via npm (`obsidian` command)
- `clawhub`: **installed** via npm
- `rg` (ripgrep): **installed**
- `jq`: **installed**
- `gh` (GitHub CLI): **installed**
- `ffmpeg`: **installed**

## Notes

- Obsidian desktop is installed and the workspace root is the active vault target.
- The original Obsidian skill expected the wrong binary name (`obsidian-cli`) and a macOS-only vault config path. That has been corrected in the installed skill.
- New shells may be needed for fresh PATH resolution after installs.

## Immediate useful skills

- `obsidian`
- `skill-creator`
- `healthcheck`
- `node-connect`
- `clawhub`
- `session-logs`
- `coding-agent`
- `taskflow`
- `weather`

## Still dependency or auth gated

These may still need login, API keys, or additional binaries before they are truly operational:

- `github` (needs `gh auth` if not already authenticated)
- `gog`
- `mcporter`
- `summarize`
- `notion`
- `trello`
- `gemini`
- `openai-whisper-api`
- `sag`
- `xurl`

## Follow-up recommendation

Next best move is to audit auth/config readiness, not just binary presence. Binary installed does not mean usable.
