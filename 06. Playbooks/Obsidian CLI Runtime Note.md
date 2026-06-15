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

## Canonical finance note lookup procedure

Use this for note-layer navigation and inspection only. Obsidian CLI is not generated-artifact proof, not a validator, not an apply engine, and not portfolio/trade/account authority.

1. Confirm the vault route:
   ```powershell
   obsidian-cli list-vaults --default
   ```
   Expected default vault: `workspace` -> `C:\Users\Veritas\.openclaw\workspace`.
2. Search by title/content when the exact note title is uncertain:
   ```powershell
   obsidian-cli search-content "Execution Board" --no-interactive --format json --page-size 5
   obsidian-cli search-content "Coverage and Watchlist" --no-interactive --format json --page-size 5
   ```
3. Print/open the note by title, not by full filesystem path, when using `print`:
   ```powershell
   obsidian-cli print "Execution Board"
   obsidian-cli print "Coverage and Watchlist"
   obsidian-cli print "Portfolio Snapshot"
   obsidian-cli print "Risk Rules"
   obsidian-cli print "Active Workflows"
   ```
4. If content will support a finance/readiness claim, inspect the canonical Markdown file itself after the CLI lookup. SQL/artifact rows can route evidence, but the Markdown owner note remains the canonical note layer.

Canonical finance note map:

| Owner surface | Canonical note | Use |
|---|---|---|
| Execution / technical action state | `03. Portfolio/Execution Board.md` | Per-ticker action state, bands/stops, deployment technical posture |
| Portfolio model / sleeve posture | `03. Portfolio/Portfolio Snapshot.md` | Portfolio model, sleeve/cash/risk posture, snapshot freshness |
| Coverage universe / thesis state | `04. Research/Coverage and Watchlist.md` | Universe membership, thesis/watch state, coverage routing |
| Risk policy | `03. Portfolio/Risk Rules.md` | Risk limits and policy boundaries |
| Workflow queue | `06. Playbooks/Active Workflows.md` | Current workflow priority and next action ownership |

Stop lines:
- Do not use Obsidian CLI results to infer owner approval, trade/account/paper authority, or portfolio/canon mutation permission.
- Do not bulk move/rename/delete finance notes without explicit approval and link-impact proof.
- Do not let Obsidian search output replace source-artifact, validator, or SQL cockpit proof for generated-artifact claims.
