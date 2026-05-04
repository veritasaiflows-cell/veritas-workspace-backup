# Obsidian CLI Runtime Note

## Purpose

Keep the Obsidian / vault automation path honest after the OpenClaw reinstall.

## Current live state

- Windows host uses the Yakitrak / NotesMD vault CLI binary: `C:\Users\Veritas\AppData\Roaming\npm\notesmd-cli.exe`
- Compatibility wrappers exist at:
  - `C:\Users\Veritas\AppData\Roaming\npm\obsidian-cli.cmd`
  - `C:\Users\Veritas\AppData\Roaming\npm\obsidian.cmd`
- Default vault: `workspace` -> `C:\Users\Veritas\.openclaw\workspace`
- `openclaw skills check` now shows the bundled `obsidian` skill ready again

## Startup check

At startup, when note-layer work may matter, confirm:
1. `obsidian-cli` resolves on PATH
2. `obsidian-cli list-vaults --default` returns the `workspace` vault
3. if Obsidian behavior matters for the task, prefer a real CLI check over assumption

## Verified audit

Vault-wide audit run on 2026-05-03:
- directories tested with `obsidian-cli list`: **295 / 295 passed**
- markdown files tested with `obsidian-cli print`: **707 / 707 passed**
- failures: **0**

Artifact:
- `tmp/obsidian-cli-audit.json`

## Real limits

- The CLI is strong for vault navigation and markdown-note operations.
- Hidden config surfaces like `.obsidian/*.json` can be listed reliably, but they are not note targets in the same way normal markdown files are.
- Do not confuse the legacy npm package named `obsidian-cli` with the real markdown-vault CLI; the false-match package was removed during recovery.
