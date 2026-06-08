---
name: cron-automation-manager
description: Design and maintain scheduled OpenClaw automation safely. Use when planning or rebuilding cron workflows, deciding heartbeat versus cron responsibilities, or validating that scheduled finance chains produce coherent artifacts without false precision.
---

# Cron Automation Manager

## Purpose

Own scheduled workflow design without letting automation drift into fiction.

## When to Use

Use this skill when:
- scheduling a new reminder or recurring job
- rebuilding workspace cron after resets
- deciding whether work belongs in heartbeat or cron
- validating morning, post-close, or event-driven automation chains
- checking for stale or overlapping scheduled workflows

## Inputs to Check First

Inspect before scheduling:
- `HEARTBEAT.md`
- `AGENTS.md`
- `MEMORY.md`
- `06. Playbooks/Operating Model.md`
- `06. Playbooks/Cron Job Protocol.md`
- `06. Playbooks/Cron Job Retrofit Checklist.md`
- `06. Playbooks/Automation Run Summary Contract.md`
- `06. Playbooks/Cron Run Ledger.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `scripts/README.md`
- current cron state
- the upstream artifacts or files the job depends on

## Procedure

1. Decide whether the need is heartbeat or cron.
2. Use the `Cron Job Protocol.md` job-card fields in order so the design is symmetrical with sibling jobs.
3. Define the smallest schedule that solves the real problem.
4. Identify dependencies, artifacts, freshness assumptions, downgrade rules, and any shared state/JSON contracts the run depends on.
5. Prefer one owner for each workflow window.
6. Avoid overlapping jobs that write the same layer.
7. Define the operator-facing response contract and the machine-readable proof surface together.
8. Validate coherence after scheduling with list/show/run/runs plus artifact inspection.
9. If the chain depends on shared vocab or contract changes, inspect at least one downstream consumer or validator before calling the scheduled path clean.
10. Record durable automation rules in the right file.

If one skill clearly owns the recurring workflow, explicitly name that skill's `SKILL.md` in the run packet's **Read first** list. That is guidance rather than hard enforcement, but it reduces drift for scheduled runs.

For research or freshness automation, do not schedule until these are explicit:
- approved source bundle
- owner layer
- review window
- stop lines
- canonical mutation posture

WF60/WF61 research opportunity jobs should also emit an operator-facing recommendation digest when the upstream artifacts support it. The digest must name improving leadership, underexposed lanes, portfolio-review/conditional-watch/deferred candidates, and the exact authority boundary. It is a response/handoff aid only: cron may not use it to promote names, change sleeves, adjust sizing/cash/risk rules, or infer owner approval.

## Scheduling Rules

- Use cron for exact timing, delayed reminders, or isolated background work.
- Use heartbeat for lightweight periodic maintenance only.
- Prefer isolated jobs unless current-session binding is explicitly needed.
- Verify the live cron `agentTurn` model allowlist before setting an explicit model. On 2026-05-31 the Gateway accepted `openai/gpt-5.5` and rejected `openai-codex/gpt-5.5` for isolated cron payloads.
- Do not emulate timers with polling loops.
- If a recurring job clearly belongs to one local skill, do not assume the run will infer that skill from context; name it explicitly.
- If upstream artifacts are partial, stale, or manual, the workflow must downgrade confidence instead of speaking with false precision.
- If a chain window will later feed SQL/index consumers, keep the SQL layer read-only and update the consumer contract before allowing the index to influence queue movement or judgment.

## WF75 PM Continuation Cron Pattern

For WF75 and SMB Workflow Clarity, cron may materially advance the queue only by producing or waking review-only handoff packets.

Allowed cron/reminder actions:
- refresh generic/service-run proof packets after their route is stable
- refresh dry-run SMB automation blueprints and validation artifacts
- refresh PM program state, lane scoreboard, next actions, blocker register, and main-session handoff
- wake the main session to continue the selected bounded review-only action
- report blockers, stale proof, failed validators, or authority drift

Blocked cron/reminder actions:
- activating Zapier, Make, n8n, Pipedream, CRM, phone, SMS, email, ad, payment, POS, or payroll automations
- customer outreach
- external delivery
- customer-data ingestion or retention
- CRM/phone/ad/email/payment/POS/payroll credential use
- customer-system implementation
- public launch or compliance claims
- canon/portfolio mutation
- paper/live/account action
- config/auth/runtime mutation
- owner approval inference

The current PM continuation dispatcher should read `tmp/pm-main-session-handoff.json` and only continue the selected action when status is `ready_for_main_session` and validation is ok. If it touches WF75 or SMB artifacts, including `tmp/wf75-smb-automation-blueprints.json`, it should finish with `python scripts\wf75_closeout_refresh.py --write --validate`, then refresh PM state and heartbeat candidates.

### Node/SQL cockpit efficiency pattern

When a WF75/SMB cron produces stable service-state artifacts, prefer this pattern:

1. Cron writes or refreshes JSON proof packets and the derived SQLite control-plane rows once.
2. Node cockpit reads `state/pm-cockpit-source-registry.json`.
3. Node exposes read-only, allowlisted SQL rows through `/api/sql/service-state`.
4. Reminders and main-session handoffs inspect structured row state before waking Randall or reparsing broad JSON bundles.

Allowed row uses:
- detect stale service runs
- show queue status
- summarize artifact refs and QA events
- prove authority flags remain false
- select a bounded review-only handoff

Blocked row uses:
- SQL-as-canon promotion
- customer-data import or retention
- external delivery
- customer-system writeback
- config/auth/runtime mutation
- canon/portfolio mutation
- paper/live/account action
- owner approval inference

### SQL coverage guard

The dedicated daily SQL/control-plane coverage job is `SQL Coverage - Daily Control Plane Guard`, scheduled for 14:55 America/Phoenix on weekdays after the workspace index freshness guard.

Owner script:
- `python scripts\sql_coverage_guard.py --write --write-md --validate`

Proof artifacts:
- `tmp/sql-coverage-guard.json`
- `tmp/sql-coverage-guard.md`

The guard refreshes and validates workspace/artifact indexes, JSON-to-SQL promotion index, SMB generic service-state SQLite, WF75 closeout/service-state SQLite, PM program state SQLite, and PM cockpit validation. It must remain read-only coverage proof only and must not authorize SQL-as-canon, customer-data import, external delivery, customer-system writeback, canon/portfolio mutation, paper/live/account action, credential use, or owner approval inference.

### Current consolidation posture

As of 2026-06-04:
- `scripts/automation_stack_hardening_pass.py --write --validate` is the JSON-first cron/skill/WF72-A2 hardening pass. Use it after cron load reductions, skill-routing changes, SQL consumer-authority proof changes, or quick-routing posture changes. Current A2 posture is live complete/read-only: 265 fallback keys, Go guard `ok`, Python fallback retained, no SQL write/import or SQL-first customer/retail promotion. The pass is report-only: no cron mutation, skill mutation, SQL write/import, canon/portfolio/customer/paper/live/account/config authority, or owner-approval inference.
- `scripts/cron_freshness_spine.py --write --validate` is the first main-session cron freshness route. It reads the cron ledger and operating-leverage spine, requires every enabled cron to have an expected-artifact contract, and writes `tmp/cron-freshness-spine.json`. The scorecard consumes this spine; hardening fails if enabled jobs are unregistered, lack artifact contracts, or are blocked.
- Quick routing should inspect this hardening pass plus `tmp/cron-freshness-spine.json`, `artifact_index.py`, PM state, cron scorecard, WF78 runner, and workflow owner artifacts before waking main or suggesting implementation. Cron may refresh proof or wake Veritas; it must not execute the routed workflow inline.
- `PM - Main Session Continuation Dispatcher` runs twice daily at `20 7,14 * * *` America/Phoenix; repeated same-action handoffs quiet as `recently_dispatched` during the PM cooldown window unless proof becomes stale/blocked.
- `Cron - Main Session Failure and Action Watchdog` runs twice daily at `0 7,14 * * *` America/Phoenix after dedicated producer/handoff jobs, control digests, SQL coverage, and operating-leverage escalation narrowed proof checks.
- Spawned helper work uses `scripts/helper_lane_manifest.py --write --validate` -> `tmp/helper-lane-active-manifest.json` plus `scripts/helper_completion_handshake.py --manifest ... --write --validate`; non-terminal lanes block synthesis until required closeout artifacts exist. After main-session integration, refresh the handshake in idle mode so completed lanes do not keep waking synthesis.
- `scripts/escalation_trigger.py --write --validate` suppresses the generic aggregate heartbeat `OWNER_DECISION` signal; it still escalates concrete `BLOCKED` signals and specific owner-decision sources.
- `Finance - WF68 Intraday Alert Producer` runs 4x per weekday at `5 6,8,10,12 * * 1-5` America/Phoenix; the prior every-30-minute cadence is retired for load reduction. The 2026-06-03 repair uses a single stable wrapper entrypoint and blocks stale execution-ready router state on failure.
- `Finance - WF68 Telegram Shadow Alert Notifier`, `Finance - Main Session WF68 Intraday Alert Handoff`, and `Runtime Pilot - Main Session WF68/WF72 Snapshot Refresh and Handoff` are paused for load reduction. WF68 now uses reduced-cadence producer artifacts plus the once-daily grouped digest and operating-leverage escalation for urgent blockers/owner decisions.
- `WF75 PM Weekly Artifact Builder` remains enabled; `WF75 PM Weekly Main Intelligence Handoff` is paused. PM dispatcher, heartbeat candidates, and operating-leverage escalation carry follow-up only when proof warrants it.
- `Workspace Index - Daily Post-Close Freshness Guard` is disabled because `SQL Coverage - Daily Control Plane Guard` is the broader superset for workspace/artifact/SQL coverage.
- `scripts/post_close_control_digest.py --write --write-md --validate` is the consolidation proof gate for the post-close cluster. It reads the post-close run summary, research freshness, paper-position SQLite, SQL coverage, canon-drift gate, cron ledger, PM state, and WF75 service-state surfaces into `tmp/post-close-control-digest.json/.md`. Expected suspended legacy weight warnings and review-only opportunity-radar degradation are audit-visible info, not wake triggers, when required sources are fresh and authority flags remain false.
- `Finance - Post-Close Control Digest Consolidated Handoff` runs weekdays at `12 15 * * 1-5` America/Phoenix as an isolated/no-delivery proof refresh. It replaces the separate weekday post-close artifact/note handoff plus weekday research opportunity handoff and should not wake main unless later escalation surfaces detect a real `BLOCKED` / `MAIN_HANDOFF_REQUIRED` / `OWNER_DECISION` signal.
- `Finance - Main Session Canon Drift Gate Handoff` is weekend-only at `10 15 * * 0,6` America/Phoenix; weekday canon-drift escalation is covered by the consolidated post-close digest after the daily canon gate runs.
- `Finance - Main Session Post-Close Artifact/Note Sync Handoff` and `Finance - Main Session Research Opportunity Sync Handoff` are disabled and retained for audit/rollback.
- `scripts/morning_control_digest.py --write --write-md --validate` is the consolidation proof gate for the morning cluster. It reads the morning run summary, sector allocation matrix, current-window index, WF68 runtime/handoff proof, SQL coverage, cron ledger, PM state, and service-state SQLite caches into `tmp/morning-control-digest.json/.md`. Expected suspended legacy weight warnings are audit-visible info, not wake triggers, when the chain is otherwise clean.
- `Finance - Morning Control Digest Proof Refresh` runs weekdays at `5 7 * * 1-5` America/Phoenix as an isolated proof refresh. The separate weekday morning main-session handoff is disabled after clean weekday `NO_REPLY` proof; morning awareness now depends on the digest plus cron freshness spine/scorecard/escalation.
- `Security Audit - Daily Bounded Hardening` remains enabled; the separate security main-session proof handoff is disabled after a clean forced producer run. Security awareness now flows through machine-readable audit proof -> cron freshness spine -> cron scorecard -> operating-leverage escalation.
- `Finance - Main Session Sunday Research Opportunity Sync Handoff` is disabled after merging its inspection duties into `Finance - Main Session Sunday Weekly Artifact/Note Sync Handoff`; Sunday research reset/producer proof remains enabled.
- Keep safety-critical producer/handoff pairs intact unless a replacement digest has live proof, returns clean authority boundaries, and preserves producer evidence.

Morning digest operator semantics:
- `NO_REPLY`: proof is clean; the separate morning handoff is eligible for the next consolidation review.
- `MAIN_HANDOFF_REQUIRED`: degraded/stale/warning proof needs Veritas review, but no safety-critical stop line is present.
- `BLOCKED`: missing required source, critical source status, or forbidden authority widening; do not replace morning handoffs until fixed.

Post-close digest operator semantics:
- `NO_REPLY`: proof is clean; no main-session wake needed.
- `MAIN_HANDOFF_REQUIRED`: degraded/stale/warning proof needs Veritas review, but no safety-critical stop line is present.
- `BLOCKED`: missing required source, critical source status, or forbidden authority widening; do not consolidate more cron handoffs until fixed.

Post-close digest boundaries:
- review-only, no cron state/schedule mutation by itself
- no SQL writes or SQL-as-canon
- no customer import/delivery/writeback
- no canon/portfolio mutation
- no paper/live/account/credential/config action
- no owner approval inference

## Safety Rules

- Do not schedule jobs against assumptions you have not verified.
- Do not let two jobs silently compete over the same notes or artifacts.
- Keep reminder text readable as a reminder when it fires.
- Validate the resulting artifacts, not just the job creation command.
- If a safe forward fix exists for a broken cron path, take it before stopping at diagnosis.
- If a workflow depends on an automation trust block, fail closed when the trust block is missing, blocked, mismatched, or anything other than explicit read-only approval.

## Machine-readable trust block consumer pilot

Workflow 29 Phase 4 bounded pilot consumer:
- `python scripts/cron_trust_block_consumer.py --trust-block tmp/automation-trust-block.json --require-workflow <workflow>`

Consumer read rule for this pilot:
1. read only the normalized trust-block artifact produced by `scripts/automation_trust_block.py`
2. require `status=ok`
3. require `consumer.cron_read_allowed=true`
4. require `consumer.allowed_posture=read_only`
5. if an expected workflow name is supplied, require an exact workflow match
6. otherwise stop with blocked status and do not widen automation behavior

Pilot boundary:
- this consumer path only answers whether a cron-facing workflow may proceed in its already-approved **read-only artifact-generation posture**
- it must not authorize canonical note mutation, scheduler expansion, or destructive/apply behavior

## Files This Skill May Read

- core files
- `06. Playbooks/Operating Model.md`
- `scripts/README.md`
- relevant notes or generated artifacts
- cron state and run history

## Files This Skill May Edit

- cron jobs
- `HEARTBEAT.md`
- `TOOLS.md`
- daily notes
- operator references when the workflow standard changes

## Output Format

Use this structure:
- scheduling goal
- chosen mechanism: heartbeat or cron
- job card
- dependency chain
- operator action still required
- risk or trust downgrade rules
- validation result

## Memory Update Rules

- log meaningful scheduling changes in the daily note
- promote durable automation policy to `TOOLS.md` or `MEMORY.md`
- keep one clear source of truth for each recurring workflow
- if a new scheduling pattern becomes standard, update `06. Playbooks/Cron Job Protocol.md` instead of inventing a second doctrine note

## Veritas portfolio-agent cron boundary

When cron jobs feed WF64/WF56 bounded portfolio-agent work, use `veritas-bounded-portfolio-agent` for authority boundaries. Cron may generate truth/proposal/verifier/standing-approval artifacts, but direct portfolio/canon apply remains category-gated and must not touch brokerage, accounts, credentials, money movement, or live trades.

## WF67 / paper-trading cron boundary

When cron jobs or reminders feed advisor-derived paper packages, name `wf67-paper-trading-operator` in the run packet's **Read first** list. Cron may inspect artifacts, report capital-package notifications, and generate review/scoped request artifacts, but paper submit/cancel/sell still requires WF67 wrapper, exact paper endpoint, scoped request, fresh short-lived kill switch, clean guard validation, paper-specific credentials, redacted audit log, and main-session notification. Cron must never use live endpoints/credentials, money movement, account mutation, close-position/liquidation endpoints, or infer approval from alert/validator quality.

## Approved Entry-Band Maintenance Exception

Randall's 2026-06-07 band-maintenance doctrine allows the system to maintain fresh reference bands and routine technical entry-band/stop levels only inside the bounded `entry_band` gate.

Cron may run approved scoped entry-band/reference-band visibility paths when all of these stay true:
- the proposal is source-fresh, posture-preserving, and validator-clean
- the row is marked eligible by the owning gate
- outputs preserve review/workspace-maintenance posture
- capital deployment, trade/order execution, sizing/cash/risk-rule changes, and account actions remain false

Cron must not handle exceptions, policy changes, invalidation/reclaim judgment, or capital/execution decisions. Those remain Randall/main-session decisions with exact gates and proof.

## WF74 Model-Quality Collection Cron Pattern

The WF74 model-quality/performance/finance-correctness collection path should stay consolidated behind one stable runner:

```powershell
python scripts\wf74_model_quality_collection_cron_runner.py --write --write-md --validate --include-harness
```

Scheduled owner job:
- `Ops - OTEL Local Digest`
- Schedule: `40 7,15,21 * * *` America/Phoenix
- Session: isolated
- Delivery: none

Expected proof artifacts:
- `tmp/wf74-model-quality-collection-cron-runner.json`
- `tmp/otel-ops-control.json`
- `tmp/cron-spark-canary-monitor.json`
- `tmp/model-run-ledger-current.json`
- `tmp/finance-recommendation-correctness-ledger-current.json`
- `tmp/model-quality-scorecard.json`
- `tmp/cron-control-packet.json`

Cron freshness contract:
- Register the job in `scripts/cron_freshness_spine.py` with the runner, OTEL ops, model-run ledger, finance-correctness ledger, and model-quality scorecard as expected artifacts.

Allowed:
- refresh local OTEL digest
- refresh Spark canary monitor
- refresh model/run ledger
- refresh finance recommendation ex-ante correctness ledger
- refresh WF74 model-quality scorecard
- refresh artifact index, harness, cron operator ledger, and cron control packet

Blocked:
- external telemetry export
- raw prompt/tool/system/content capture
- runtime/config mutation from the scheduled run
- WF55 later outcome grade assignment
- model-ranking claims from thin samples
- investment-correctness claims from telemetry or runtime speed
- portfolio/canon mutation
- capital deployment approval
- paper/live/account action
- owner approval inference

Downgrade rules:
- If session attribution coverage is 0, report model-vs-model comparison as blocked.
- If token/cost fields are missing, report cost/token performance as unavailable.
- If WF55 graded rows are 0 or durable append is false, report decision quality as ex-ante only, later outcomes blocked.
- If any authority flag widens, the cron path is blocked, not warning.

## Training/eval candidate cron boundaries

Cron may refresh review-only proof artifacts used by WF74, RSI, and future-session startup packets. Cron must not become a hidden training pipeline.

Allowed cron posture:

- Run the single WF74 owner collection job and duplication audit.
- Refresh local metadata-only candidate indexes when explicitly scheduled through an approved owner job.
- Validate that generated candidate artifacts preserve `external_upload_allowed=false`, `training_or_finetune_call_allowed=false`, and `model_weight_mutation_allowed=false`.

Blocked cron posture:

- No raw prompt/chat export.
- No secret, credential, brokerage/account, or unredacted memory capture.
- No OpenAI fine-tuning, reinforcement fine-tuning, file upload, dataset upload, or model deployment call.
- No duplicate component collectors outside the WF74 owner job.
- No model ranking or WF55 outcome grading from cron success alone.

If a future scheduled candidate builder is approved, it must remain metadata-only, route through `wf74_cron_duplication_audit.py`, and expose its output through the future-session packet as review evidence only.
