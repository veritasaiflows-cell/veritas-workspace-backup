# Migration Review - 2026-04-28 2047 MST

## Approved architecture

### Core constitution files
- `SOUL.md`
- `IDENTITY.md`
- `MEMORY.md`
- `USER.md`
- `TOOLS.md`
- `AGENTS.md`
- `Continuity Protocol.md`
- `HEARTBEAT.md`

### Operator skills to add
- `skills/openclaw-operator/`
- `skills/openclaw-troubleshooter/`
- `skills/memory-continuity-manager/`
- `skills/cron-automation-manager/`

### Existing finance skills to preserve
- `veritas-fundamental-pass`
- `veritas-technical-pass`
- `veritas-macro-pass`
- `veritas-positioning-pass`
- `veritas-investment-deck`
- `veritas-pdf-brief`
- `veritas-self-improvement`
- `workspace-governor`

### Explicit exclusions
- keep `memory/`
- do not build around `CLAUDE.md`
- remove `BOOTSTRAP.md` in execution pass

## Target outlines

### SOUL.md
Keep identity, doctrine, relationship to Randall, finance mandate, hard boundaries, risk standard, continuity principle, and instruction to use skills for repeatable workflows. Move templates and detailed weekly research routines into skills.

### IDENTITY.md
Keep a short identity card: name, role, relationship, domain, read-only boundary, tone.

### MEMORY.md
Keep durable facts, durable preferences, durable operating decisions, durable finance posture, and durable lessons. Remove implementation-heavy automation runbook detail.

### USER.md
Keep Randall's durable preferences, goals, and communication style.

### TOOLS.md
Keep environment facts, model routing, tool safety, workspace setup, and capability notes. Add rule: when skills/tools change, `TOOLS.md` must be updated in the same workstream.

### AGENTS.md
Keep startup read order, authority order, continuity principles, action boundaries, group behavior, and commit cadence. Move detailed startup-response, subagent, heartbeat, and finance execution procedures into skills.

### Continuity Protocol.md
Keep the memory layer model and promotion doctrine. Trim duplicated startup detail and let the continuity skill own procedural execution.

### HEARTBEAT.md
Keep lightweight maintenance behavior and quiet/no-spam rules. Keep it short.

## Uncertain items to review during cleanup
- Whether any current standing market-posture bullets in `MEMORY.md` are durable enough to keep versus move to daily notes.
- Whether a few finance execution bullets belong in `AGENTS.md` or the cron skill.
- Whether some local browser/tooling notes in `TOOLS.md` should stay core or move to operator skill.

## Validation targets
- Core files materially shorter without becoming generic.
- New operator skills have clear, non-overlapping ownership.
- Existing finance skills remain the decision-grade finance spine.
- No critical mission, identity, or safety rule lost.
- `TOOLS.md` reflects any skill/tool changes made in the migration.
