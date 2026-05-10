# OpenClaw Reinstall Recovery Checklist

## Retrieval Notes
- Type: procedure
- Status: active
- Owner surface: `skills/openclaw-troubleshooter/SKILL.md`
- Authority: procedure
- Workflow: none
- Key entities: OpenClaw reinstall, restart recovery, Python, Obsidian CLI, SQLite, rg, jq, skills, cron
- Source freshness: 2026-05-09 recovery lessons
- Next action: use after any reinstall/update/restart before trusting finance automation
- Archive posture: permanent-reference
- Tags: #veritas/runtime #status/active #retrieval/recovery

## Purpose
Recover the workspace after an OpenClaw reinstall, update, or restart without mistaking installed tools, stale artifacts, or old job IDs for live readiness.

## Lesson from 2026-05-09
The reinstall/restart recovery was not one step. The workspace only became usable again after runtime tools, retrieval tools, Python dependencies, skills, finance artifacts, cron jobs, and continuity surfaces were all re-verified.

## Return-to-service sequence

### 1. Confirm runtime baseline
```bash
openclaw status
openclaw doctor
openclaw skills check
```
Record any persistent warnings instead of hiding them. On 2026-05-09, plugin-skill symlink creation still warned with `EPERM`, but skills were visible and usable.

### 2. Verify local execution dependencies
```bash
python --version
python -m pip show yfinance
```
If package installs are needed, get approval when the install changes the machine. On 2026-05-09, Python was verified as `3.13.13`; `yfinance` was installed with approval and then finance scripts could refresh entry-band outputs.

### 3. Verify retrieval tools
```bash
obsidian-cli --version
sqlite3 --version
rg --version
jq --version
```
Current known-good 2026-05-09/10 proof:
- Python `3.13.13`
- `notesmd-cli` / Obsidian CLI `v0.3.6`
- SQLite `3.53.1`
- ripgrep `15.1.0`
- jq `1.8.1`

### 4. Verify path/wrapper facts
Check `TOOLS.md` for the current Windows wrapper truth:
- Obsidian CLI wrappers under `C:\Users\Veritas\AppData\Roaming\npm`
- SQLite wrapper `sqlite3.cmd`
- `rg.cmd` and `jq.cmd`
- active runtime posture: native Windows
Do not assume the live OpenClaw process inherited PATH changes until a command works from the session.

### 5. Restore finance artifact confidence
Run the smallest meaningful script proof before acting on old outputs.
Examples:
```bash
python scripts\entry_band_fetch.py ETN --html --quiet
python scripts\validate_dashboard_state.py --write
python scripts\run_finance_refresh_chain.py post-close
```
If a chain fails, fix the real contradiction before designing new layers.

### 6. Verify scheduled workflows survived restart
```bash
openclaw cron list
```
Then inspect job history/proof artifacts for important jobs. If a job ID changed after restart/rebuild, update the queue, ledger, and continuity notes.

### 7. Reconcile trust surfaces
Update only the surfaces that changed:
- `TOOLS.md` for durable environment facts
- `memory/YYYY-MM-DD.md` for chronological recovery steps
- workflow continuity notes for live job IDs, blockers, and next proof
- relevant skills/procedures when the failure pattern is reusable

## Stop lines
- A tool is installed but not callable from OpenClaw.
- A cron job exists but its wrapper proof is stale, blocked, or missing.
- A finance artifact is stale relative to a note-layer change.
- A config/auth/channel/runtime change would be required; ask first.
- A secret appears in chat, logs, or files; rotate and scan before claiming clean recovery.

## Proof standard
Return-to-service is only real when the specific workflow that matters has a fresh proof artifact or validator run. `openclaw status` alone is not enough.
