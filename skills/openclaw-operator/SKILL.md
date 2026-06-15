---
name: "openclaw-operator"
description: "Add operator audit for lane-register compliance."
---

# Proposal: Operator Lane-Register Compliance Check

## Goal
Harden OpenClaw operator behavior so cross-surface implementation work can be audited through a durable register instead of relying on tree-scoped session visibility.

## Proposed Skill Update
Add this section after **Check live state before claiming anything about runtime**.

```markdown
## Cross-Surface Implementation Lane Audit

When checking whether Telegram, WebChat, main, helper, isolated, or cron-adjacent sessions are doing implementation work, inspect both runtime state and the durable lane register.

Runtime visibility is advisory:

- `sessions_list` may be tree-scoped and omit unrelated WebChat or Telegram sessions.
- `subagents(action=list)` only proves active/recent child lanes visible to the requester session.

Durable coordination state is authoritative for implementation collision checks:

```powershell
python scripts\concurrent_lane_manager.py --status --write --validate
```

Interpretation:

- Active lane count `0` means no implementation lane has been leased in the durable register.
- If another surface is actually editing/writing files while active lane count is `0`, that surface did not follow the lane-register protocol.
- `created_at_utc` is lane lifecycle/planning time.
- `started_at_utc` is actual running start time for new lanes.
- `ended_at_utc` / `completed_at_utc` is terminal closeout timing.
- Legacy lanes without `started_at_utc` cannot prove runtime duration.

For operator hardening or after-session audits, report:

1. active lane count
2. latest active/running lanes and write surfaces
3. latest completed implementation job from `state\implementation-completion-ledger.jsonl`
4. latest daily-memory completion entry when the user asks for memory state
5. any mismatch between runtime session activity and lane-register state

If a mismatch suggests a session bypassed the register, classify it as a governance gap, not proof that runtime visibility is broken.
```

## Validation Expected After Apply
- `openclaw skills check`
- `python scripts\concurrent_lane_manager.py --status --write --validate`
- spot-check latest implementation ledger and daily memory when answering job-completion questions

## Boundary
Audit/coordination only. No helper spawn, no cron mutation, no config/auth/runtime mutation, no cleanup/delete/archive, no canon/portfolio mutation, no paper/live/account action, no capital approval, and no owner approval inference.
