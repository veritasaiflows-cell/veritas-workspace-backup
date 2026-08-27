# Continuity Protocol

## Purpose

Keep Veritas continuous across sessions without turning the workspace into noise.

## Memory layers

### Daily memory
File: `memory/YYYY-MM-DD.md`

Use for:
- what happened today
- setup changes
- discoveries and follow-ups
- rough context that may or may not deserve later promotion
- session-level market or portfolio context

Rule:
- capture only meaningful deltas
- one bullet per material change
- if the same topic already exists today, update or merge it instead of appending another bullet
- let queue, registry, continuity notes, and audits own pass-by-pass detail
- optimize for usefulness, not perfection

### Durable memory
File: `MEMORY.md`

Use for:
- durable facts
- Randall's durable preferences
- lasting operating decisions
- major finance rules, posture, or policy
- lessons that should change future behavior

Rule:
- promote only what will still matter later
- keep it curated

### Operating files
Files:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- `USER.md`
- `IDENTITY.md`

Use for:
- identity
- behavior rules
- environment facts
- stable conventions

Rule:
- these files define how Veritas operates
- Veritas / the main session is always responsible for keeping the notes layer and canon up to date by reconciling canonical notes against verified artifacts/evidence within approved authority boundaries
- they are not daily logs or procedural dump zones

## Routing rules

Write to the daily note when:
- a materially new fact or decision appeared
- meaningful work happened
- a tool or config changed
- a bug or constraint was discovered
- Randall gave a short-term instruction
- a follow-up is worth tracking

Do not write to the daily note when:
- the same state is already captured there
- the detail already lives cleanly in a continuity note, queue, registry, ledger, or audit
- the update is only "still active", "reran", "no change", or another status replay
- the note would become a chain log instead of a daily delta log

Promote to `MEMORY.md` when:
- the fact should persist across many sessions
- it changes future decision quality
- it reflects a durable preference or policy
- losing it would likely recreate the same mistake

Update an operating file or skill when:
- behavior rules changed
- environment posture changed
- a procedure became repeatable enough to deserve a skill

## Session resume transaction

The current task cursor is `tmp/current-resume.json`, owned by `scripts/session_resume_checkpoint.py` under schema `veritas.session_resume_checkpoint.v1`. `tmp/current-active-lanes.json` is the compact current-lane projection. Both are generated continuity/proof surfaces; neither is canon, approval, or execution authority.

Emit a checkpoint after every material implementation transition, before a likely compaction window, and whenever the exact next step changes. Do not wait for a memory-only pre-compaction flush: that flush may append durable memory only and must not rewrite the resume transaction.

Every material checkpoint must carry:

- checkpoint ID and sequence, parent job, workflow/lane/workstream, objective, and status
- last completed step, in-progress step, exact next action, and exact next command
- `already_completed_do_not_repeat`
- changed-file and proof-artifact hashes
- attempt/retry identity and current lease binding
- blocker, approval boundary, stop lines, continuity home, and freshness expiry
- explicit automatic-safety posture, exact-ID acknowledgement state, and durable terminal-execution receipt

Resume order is strict:

1. Read `tmp/current-resume.json` and `tmp/current-active-lanes.json`.
2. Run `python -B scripts\session_resume_checkpoint.py --validate`.
3. Stop on a missing/stale lease, missing identity, hash mismatch, expired checkpoint, or unresolved multiple-lane ambiguity.
4. Set `$resumeId = [string](Get-Content -LiteralPath 'tmp\current-resume.json' -Raw | ConvertFrom-Json).checkpoint_id`, then acknowledge it with `python -B scripts\session_resume_checkpoint.py --acknowledge $resumeId --acknowledged-by main-session --write --validate`.
5. Reject execution when `execution_gate.replay_blocked=true`. Exact denylist entries use `command:<exact_next_command>` or `action:<exact_next_action>`; either terminal receipt status (`succeeded` or `failed`) also blocks replay.
6. Execute only `exact_next_command`, only when `execution_gate.command_authorized=true`.
7. Immediately after success, run `python -B scripts\session_resume_checkpoint.py --record-execution $resumeId --execution-status succeeded --executed-by main-session --execution-proof-artifact 'tmp\changed-file-validator-router.json' --write --validate`. After failure, run the same command with literal `failed`. The matching receipt is idempotent, a conflicting outcome fails closed, proof is mandatory, and re-acknowledgement cannot authorize the command again.
8. Emit a successor checkpoint after the material transition. Changed content changes the checkpoint ID and resets both acknowledgement and execution receipt.

When Windows-native argument binding cannot preserve nested quotes or spaced paths, encode the unchanged command with these pasteable PowerShell lines: `$exactCommand = 'python -B scripts\test_session_resume_checkpoint.py'` then `$encodedCommand = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($exactCommand))`. Supply `$encodedCommand` through `--exact-next-command-base64` in the fully specified record command. The decoded text, not the transport encoding, is checkpointed and hashed.

If there is no valid current target, execution remains prohibited. Use this precedence for read-only discovery without inferring progress: active leased lane checkpoint -> exact workflow checkpoint -> named workflow continuity note -> PM queue -> general status. Multiple active lanes require an explicit lane-bound checkpoint; recency is not a selector. Any discovered action must first be converted into a fresh lane-bound canonical checkpoint, validated, and acknowledged by exact ID.

`tmp/handoff-current.json` is compatibility/history only. It never outranks `tmp/current-resume.json`, cannot be used after expiry or failed freshness/identity validation, and must not revive an old default workflow when current state is missing. Even a valid explicitly named legacy handoff is context-only until converted into a fresh canonical checkpoint. The full concurrent lane register remains historical/drilldown state; startup consumes the compact active projection first.

The checkpoint producer records and validates commands but never executes them. It cannot infer owner approval or grant runtime, config, external, finance, portfolio, paper, live-trading, account, capital, or destructive authority.

## Hygiene rules

- No mental notes
- Prefer short accurate notes over long vague notes
- Avoid duplicating the same rule across too many files
- Keep `MEMORY.md` curated
- If a lesson changes future behavior, update the right operating file or skill instead of burying it in a daily note

## Daily note compression rule

- Start daily bullets with a clear topic lead so duplicate detection is easy.
- Before appending, scan today's note for the same topic or opening phrase.
- If the topic is already present, update or collapse the existing bullet instead of adding another one.
- If automation or session-memory writes touched the note and duplicate bullets are suspected, run `python scripts/daily_note_dedupe.py memory/YYYY-MM-DD.md --apply` as the bounded cleanup step.
- If a workflow had many small actions, write one summary bullet and point to the owning continuity note or audit instead of replaying the full sequence.
- Daily notes are not queue copies, chain logs, or proof-run ledgers.

## Startup and heartbeat note

Session startup behavior lives in `AGENTS.md`.
Heartbeat behavior lives in `HEARTBEAT.md`.
Procedural continuity work belongs in `memory-continuity-manager`.
