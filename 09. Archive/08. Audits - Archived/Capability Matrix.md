# Capability Matrix

## Summary

Revalidated on 2026-04-18.
Operational readiness is stronger than this note previously claimed. Judge capability by three layers together: callable binary, auth state, and config state.

## Tier 1 readiness

- `obsidian` skill: aligned to this workspace vault
- `obsidian` CLI: callable from the current shell
- `clawhub`: callable and authenticated from the current shell
- `gh` (GitHub CLI): callable and authenticated from the current shell
- `rg` (ripgrep): callable from the current shell
- `jq`: callable from the current shell
- `ffmpeg`: callable from the current shell

## Notes

- Obsidian desktop is installed and the workspace root is the active vault target.
- Direct file-based vault work is fully usable now.
- API-key-based toolchains should still be treated separately from local CLI readiness.

## Immediate useful skills

- `obsidian`
- `skill-creator`
- `healthcheck`
- `node-connect`
- `clawhub`
- `taskflow`
- `weather`

## Still dependency or auth gated

These may still need login, API keys, or additional binaries before they are truly operational:

- `notion`
- `trello`
- `goplaces`
- `sag`
- `openai-whisper-api`
- `sherpa-onnx-tts`

## Follow-up recommendation

When readiness matters, re-check the live shell instead of trusting a past audit. Installed somewhere is not enough, and an old failure report can become false just as easily as an old success report.
