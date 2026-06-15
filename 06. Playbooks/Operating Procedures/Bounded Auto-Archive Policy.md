# Bounded Auto-Archive Policy

## Purpose

Randall approved bounded workspace archive folders and automatic movement of deprecated files on 2026-05-23, with a main-session report after each apply.

This policy keeps cleanup useful without turning archive into hidden deletion or a second control plane.

## Archive roots

- `09. Archive/Auto Archive - Generated Residue/`
- `09. Archive/Deprecated Files - Auto Archived/`
- `09. Archive/Archive Logs/`

## Allowed automatic archive scope

Veritas may auto-archive without asking again only when all are true:

1. The file is inside the workspace.
2. The file is non-canonical, non-config, non-credential, and non-runtime-critical.
3. The file is clearly generated residue, deprecated output, duplicate accidental build output, or obsolete scratch/proof residue.
4. There is no active static reference from live workflow/control surfaces, validators, scripts, or canonical notes.
5. The move is archive-only, not delete.
6. A manifest/log is written under `09. Archive/Archive Logs/` or `tmp/`.
7. The main session reports the moved path(s), destination, reason, and validation proof.

## Still requires explicit approval

Ask Randall first before archiving/moving/deleting:

- canonical finance notes
- active workflow continuity notes
- `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, `MEMORY.md`, `HEARTBEAT.md`
- scripts that may still be operator entrypoints
- skills
- config/auth/channel/service/runtime files
- credentials, tokens, private keys, account files
- current-window artifacts or validator inputs used by live workflows
- any broad cleanup batch where active references are uncertain
- deletes of any kind

## Reporting contract

Every auto-archive apply report should include:

- files moved
- destination
- reason/classification
- reference check used
- validation run, if applicable
- residue or skipped files

## Response-length rule

For long cleanup/RSI/status updates, prefer short Web UI chunks plus file-backed proof artifacts. Do not hide important results only in vault files when the user needs to read them in WebChat or Command Center.
