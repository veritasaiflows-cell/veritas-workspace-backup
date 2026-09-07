# OS Optimization Cron Runtime Prework

Generated: 2026-05-24 14:52 MST

## Scope
Diagnose weekday morning cron job `63512442-b4cf-4c9c-a704-158e6bc36a9b` `sourceReplyDeliveryMode` error, assess WF72 note-drift weekly cadence design, and list safe fix/approval gates.

## Findings

### 1. Weekday morning cron error
- Live job: **Finance - Weekday Morning Review Refresh** / `63512442-b4cf-4c9c-a704-158e6bc36a9b`.
- Current live state from `openclaw cron show --json`: enabled, isolated, `delivery.mode=none`, `lastStatus=error`, `lastError=TypeError: Cannot read properties of undefined (reading 'sourceReplyDeliveryMode')`, next run Monday 06:05 America/Phoenix.
- The job definition itself already has a delivery object (`mode:none`, `bestEffort:true`) and is not requesting delivery; delivery preview shows `not requested`.
- Prior recovery artifact `tmp/cron-runtime-stale-dist-recovery.md` attributes the error to stale Gateway/OpenClaw hashed dist imports, not a finance-chain artifact failure. Gateway restart + temporary isolated cron smoke proved `agentTurn` execution recovered. The original job still displays the old error because it has not had a successful subsequent run.
- I did **not** force-run the heavy morning finance chain outside its natural pre-market window because it can mutate scoped entry-band maintenance and refresh window-specific artifacts, creating avoidable stale/noisy proof.

**Diagnosis:** current evidence supports “stale displayed last-run error after repaired Gateway runtime,” not an unproven bad morning job payload. If the next natural run fails with the same error after the 2026-05-22 recovery, escalate to OpenClaw runtime bug / scheduler-envelope repair.

### 2. WF72 note-drift weekly cadence
- WF72 note-drift is already folded into the scheduled WF76 Sunday review-only maintenance job `bd1c1f4d-b2e1-4307-9130-36f635f2a56c` at Sunday 18:05 America/Phoenix.
- The job runs `artifact_index.py note-drift --limit 100` and writes `tmp/wf72-sql-to-note-drift-report.json/.md`.
- Current note-drift artifact remains review-only: boundary `derived_review_only_index_not_canon_not_apply`, 18 candidates / 12 review-needed, all authority flags false (`canonical_note_mutation_allowed=false`, `proposal_apply_allowed=false`, `portfolio_mutation_allowed=false`, `trade_or_account_action_allowed=false`, `owner_approval_inferred=false`).
- Recommendation: **do not create a separate WF72 note-drift cron.** Keep it inside WF76 weekly maintenance to avoid competing drift/report jobs.

### 3. Validation snapshot
- `python scripts\cron_authority_matrix_validator.py --write` passed: `status=ok`, 16 checks, 0 critical, 0 warning.
- `python scripts\artifact_index.py validate` initially blocked on stale `tmp/deployment-readiness-surface.json`; running the scheduled job's own preceding step `python scripts\artifact_index.py incremental` refreshed 1 changed source and validation then passed: 28 checks / 0 failed / stale=0.
- This confirms the WF76 execute order (`incremental` before `validate`) is correct and should clear transient stale-index drift during the scheduled run.

## Smallest safe fix plan
1. **No payload patch before the next natural run.** The likely root cause was already repaired at Gateway/runtime level; the remaining error is a stale last-run state.
2. **Observe Monday 06:05 run** via cron watchdog/main-session inspection. Required proof: `openclaw cron show 635...` shows `lastStatus=ok` or a finance-chain artifact warning/blocker rather than `sourceReplyDeliveryMode`; inspect `tmp/run-summary-morning.json`, `tmp/run-chain-morning.json`, and authority fields.
3. **If the same TypeError repeats after the recovered runtime:**
   - Treat as scheduler/runtime incident, not finance-chain failure.
   - First safe action: inspect `openclaw cron show --json`, `openclaw cron list --json`, and relevant run history/artifacts.
   - Then request approval for Gateway/service restart or exact cron edit if needed.
4. **Only if payload repair is required:** apply an exact reviewed cron edit that preserves schedule/session/delivery and narrows unused tools if justified (e.g., remove unused `cron` from isolated finance worker `toolsAllow`), then validate with a safe isolated smoke or a controlled pre-market run.

## Approval gates / stop lines
- Gateway restart/service/runtime/config mutation requires explicit main-session/operator approval.
- Cron edit/patch requires exact reviewed patch and rollback plan; no silent scheduler mutation from this lane.
- Force-running the morning finance job outside its natural window requires explicit approval because it can refresh window-specific artifacts and perform scoped entry-band maintenance.
- No live trading/account/money movement, no paper execution outside WF67, no config/auth/channel/service mutation, no deletes, no cron-direct canon apply, no owner-approval inference.

## Rollback / recovery plan if a cron edit is approved later
- Export `openclaw cron show 63512442-b4cf-4c9c-a704-158e6bc36a9b --json` before editing.
- Apply only the exact changed field(s); preserve name, id, schedule, timezone, isolated session target, timeout, delivery `none`, and stop lines.
- Verify with `openclaw cron show --json` and delivery preview/list.
- Prefer next natural run proof; if a controlled run is approved, inspect run history plus `tmp/run-chain-morning.json`, `tmp/run-summary-morning.json`, dashboard/capital-validator artifacts, and authority flags.
- Roll back by restoring the pre-edit JSON fields if validation or runtime behavior regresses.
