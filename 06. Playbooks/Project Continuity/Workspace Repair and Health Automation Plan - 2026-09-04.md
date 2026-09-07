# Workspace Repair and Health Automation Plan

Owner: Main. Requested by Randall, 2026-09-04 at 23:08 America/Phoenix.
Status: PLAN READY; EXECUTION DEFERRED until current lanes finish and gated changes receive scoped approval.

## Objective and authority

Restore reliable workspace operation, truthful health reporting, and bounded recovery so the alerts-and-recommendations loop can run unattended within its approved scope. Reuse existing health/PM/automation infrastructure rather than build another parallel control system.

This request authorizes planning, not immediate repairs, background execution, schedule changes, service restarts, or permanent autonomy expansion. No watcher or automatic start is armed by this plan. Main owns integration and final acceptance. Implementation starts only after a fresh preflight and execution instruction; gated actions require an exact approval packet.

Excluded: portfolio/account state, capital, orders, paper/live execution, credentials, public/customer delivery, broad cleanup, voice/UI features, automatic model promotion, and restarting retired WAVE2 work.

## Evidence baseline and limits

- Live `memory_search` in this planning turn failed: index built for `nomic-embed-text`, configuration expects `fts-only`. Recall is unavailable; this is a confirmed repair item, not an empty-memory conclusion. Use exact sources meanwhile.
- `tmp/concurrent-lane-register.json`, generated 2026-09-05T05:57:09Z, lists three leased lanes below. Older `tmp/current-active-lanes.json` (04:52:32Z) lists only one; it cannot establish current quiescence.
- `08. Audits/Workspace Routing Efficiency and Autonomy Review - 2026-09-04.md` records reachable gateway with Scheduled Task stopped, heartbeat delivery-route uncertainty, diagnostics-otel 2026.7.1 versus gateway 2026.9.1, routing/model drift, and WF84/WF85 refresh-required results. These are dated observations to reproduce, not newly verified runtime failures.
- Prior chat reports scheduler ownership/list failure, CLI hangs, blocked freshness proofs, and differing job/error counts. Do not reuse those counts as an execution baseline. Reconcile one timestamped live inventory with generated packets first; a stopped service is not proof that the reachable gateway is stopped, and successful Telegram input is not proof of heartbeat or automation output delivery.
- `state/pm-autonomy-policy.json` currently permits proof refresh/planning but disallows unattended code patches, schedule/config/runtime changes, and helper spawning without Main. Detection is not repair permission.

## Gate 0: wait for current owners; do not overlap

| Dependency | Lease / current owner route | Required handoff |
|---|---|---|
| Routing/bootstrap/model alignment | `RUNTIME::MULTI-MODEL-ISOLATED-AGENT-ALIGNMENT-20260904-V2::implementation-os`; Main routing sessions | Accepted diff, focused tests, independent QA, current model/dispatch proof, lease disposition |
| Phase 3G dynamic execution | `FINANCE-PHASE3G-20260904::dynamic-execution`; Phase 3 parent and Astra child | Main-accepted implementation, mocked execution tests, explicit unresolved gates, write release |
| Phase 3G coverage repair | `FINANCE-PHASE3G-20260904::coverage-repair`; Phase 3 parent Main | Accepted coverage semantics/tests, fresh evidence inventory, write release |

Session pickup routes (context only, not proof of acceptance):
- Routing review: `agent:main:dashboard:cb58a09a-815f-4693-a4fe-ef5874e07445`.
- Routing implementation: `agent:main:dashboard:08c52bc7-bf9c-411a-bd77-9609468bd9c8`.
- Phase 3 parent: `agent:main:dashboard:a932fb59-8f36-4b0a-97a9-d4eceb6d8e0b`.
- Phase 3 dynamic child: `agent:main:dashboard:4731c246-8752-41ef-aec9-a71d860e4b99`.

At execution pickup, inspect fresh sessions, current lane register and source lease owner; validate resume pointers using `python -B scripts\session_resume_checkpoint.py --validate`. A finished chat, expired lease, or old green projection is not accepted completion. If a lane ends blocked, obtain its explicit handoff and scope release before replanning the residual work. Never wait for Phase 3H burn-in merely to begin independent infrastructure diagnosis after code-lane release.

## Sequenced repair packages

### R1 - Establish one trustworthy baseline (P0)

**Depends on:** Gate 0. **Owner:** Main. **Scope:** bounded read-only diagnostics and a new timestamped evidence bundle.

1. Freeze current source hashes, dirty-file inventory, active leases, runtime version and effective non-secret routing metadata. Do not restore an old full config over concurrent changes.
2. Reproduce automation status/list failure using first-class tools; inspect exact affected job IDs and enabled/disabled status through supported read-only routes if listing fails. Do not directly edit scheduler SQLite or infer a global system-agent default as the fix.
3. Run documented gateway/status/doctor/security read-only checks with real process deadlines; keep output/exit code/elapsed time. Classify timeout, SQLite warning, configuration fault, stale evidence, intentional disablement, and historical failure separately. Do not assume SQLite caused every hang.
4. Reconcile producer timestamps and upstream source bindings for status, scheduler, heartbeat, PM, memory and finance. Record missing/unavailable proof as unknown, never green.

**Acceptance:** one reproducible baseline listing each current incident, exact owner, severity, last observation, dependency, repair class and approval requirement. Deduplicate cascaded failures under their root incident. No fixed expected job count.

### R2 - Restore control-plane and unattended runtime reliability (P0)

**Depends on:** R1. **Owner:** Main runtime/automation owners. **Gated:** scheduler, config, service, plugin or runtime mutations.

- Ownership: resolve every current ownerless job against its intended owner, including disabled jobs that can break listing. Prefer exact per-job ownership fixes; preserve payload, schedule, enabled state, destination and failure policy. Do not assign every specialist job to Main by default.
- CLI/database responsiveness: isolate lock contention, duplicate processes and slow paths with bounded read-only evidence; prepare the smallest supported repair. No live database surgery or broad doctor-fix command.
- Startup: identify the actual port-owning process and Scheduled Task failure before changing either. Plan one supported startup owner, a rollback launch path, and an approved maintenance window. Never blindly start a second gateway.
- Plugin drift: verify diagnostics-otel compatibility and exact installed version before proposing an update. Preserve load-bearing local patches; no bulk upgrade.
- Routing: verify Telegram account ownership resolves to Main separately from conversation identity; test the intended heartbeat and automation output routes independently. Preserve existing allowlists and recipients.

**Acceptance:** automation listing succeeds across all pages; ownership is unambiguous; bounded CLI probes complete on three consecutive checks with measured durations; no new unclassified database error; approved restart returns the same intended gateway owner and routes. Reboot/logon continuity remains explicitly unproven until an owner-approved test. One approved harmless delivery proves the actual outbound route, not just inbound chat.

**Rollback:** exact job/config pre-images plus source hashes; revert only this package's fields after conflict check. Service/plugin changes get their own backup, restore procedure and post-restore health checks.

### R3 - Repair recall, lane accounting and stale proof (P1; recall availability is urgent)

**Depends on:** R1 and stable writer ownership from R2. **Owner:** Main memory/continuity owners; inherit accepted routing-lane outputs, do not rewrite them.

- Establish whether effective `fts-only` configuration is intentional before altering it. Reconcile embedding metadata with the selected supported backend; test FTS and semantic recall separately, and probe affected agent stores rather than declaring fleet health from Main alone.
- The recall tool suggests `openclaw memory status --index --agent main`; do NOT run it against the live gateway. Workspace history records concurrent vector-table rebuild risk. Inspect current docs/source and use an approved, backup-backed, exclusive-writer maintenance path if a rebuild is required. Provider cost and service interruption must be explicit.
- Refresh current-lane/resume projections only after accepted source updates. Distinguish active incident failures from irrecoverable historical attribution; never fabricate incident codes, tokens or dispatch identities, and never revive WAVE2 to make a validator green.
- Replace misleading stale summaries with source-bound current proof through their owning producers. Preserve historical artifacts and mark supersession in current owner surfaces; no deletion is implied.

**Acceptance:** known exact and semantic queries return appropriate current citations, or an intentionally FTS-only system is explicitly labeled without claiming semantic readiness. Wrong model/index metadata fails visibly. Active-lane projection matches accepted register state. Historical missing evidence remains honestly typed, not silently erased.

### R4 - Make existing health reporting truthful and visible (P1)

**Depends on:** R1-R3. **Owner:** Main plus bounded implementation lane. **Scope:** extend existing status/control packet and heartbeat consumers, not a second dashboard or parallel scheduler.

- Separate execution success, content health, source freshness, delivery success and repair result. Report `healthy`, `degraded`, `blocked`, `stale`, or `unknown`; the outer schema validator cannot declare readiness.
- Surface runtime/startup, automation ownership/execution, memory, lane integrity, finance evidence and delivery as separate dimensions. Each incident includes timestamp, root cause/evidence, owner, next action and recovery state.
- Audit fixed-path producer/consumer edges: require schema, age, future-date and source/run binding checks; retain per-run proof. Finance age must respect market calendar/session and source type rather than a single wall-clock rule.
- Design changed-only P0/P1 escalation and one recovery notice with durable dedupe, cooldown and bounded reminders. Preserve warnings without repeating them on every run. Separate notification delivery failure from healthy content.
- Inspect existing schedules first. Proposed cadence: reuse an existing roughly 15-30-minute operational check where available, one daily summary, and existing weekly review; exact IDs/times/destinations require an approval packet, not automatic creation here.
- A gateway-hosted watcher cannot report the gateway's total failure. An external watchdog is a separate optional, owner-approved host/delivery project; do not claim full outage coverage without it.

**Acceptance:** offline tests inject missing, stale, malformed, future-dated and source-mismatched proof; all prevent false green. Repeated unchanged errors dedupe, worsening escalates, recovery announces once, and failed delivery remains visible. Approved live test demonstrates surfaced content in the intended destination.

### R5 - Add a narrow, auditable recovery envelope (P1)

**Depends on:** R4 and explicit standing-envelope approval. **Owner:** Main. **Default:** detect and propose until approved.

Candidate allowlist: retry eligible read-only transient fetches under existing budgets; regenerate specifically approved derived proof; refresh exact derived indexes only through their established safe writer route. Reuse existing repair handlers before creating another broker.

Each handler must declare exact input/output scope, preconditions, per-incident lock/idempotency key, bounded attempts and total deadline, resource budget, before/after evidence, independent postcondition, rollback and escalation. Honor Retry-After. Stop on unknown error, repeated failure, concurrent writer, or authority mismatch; use a circuit breaker to prevent repair storms.

Never auto-change code, prompts, models, credentials, config, schedules, services or plugins; delete/archive files; widen scope; or mutate finance canon without its exact existing approval gate. Successful detection or a suggested handler is not permission to execute it.

**Acceptance:** sandboxed failure injection proves one repair at most per incident, idempotent retry, concurrency exclusion, enforced budget/deadline, successful postcondition, rollback/failure escalation, and denial of forbidden writes. Begin with shadow classification, then an approved minimal handler, not fleet-wide automatic repair.

### R6 - Accept the full non-executing finance loop (P0 dependency, then burn-in)

**Depends on:** accepted existing Phase 3 outputs, R2 operational reliability, R4 truth/delivery checks; can progress while R5 stays proposal-only.

- Re-measure the eligible universe and actual observed coverage after the coverage lane finishes. Prior 18/32 and zero-coverage claims are historical, not new acceptance criteria. Distinguish a faulty observer from truly absent evidence; do not generate bands merely to fill a counter.
- Verify the complete dependency chain: eligible scope -> authorized provider refresh -> quotes/evidence/lineage -> reference bands and freshness -> alert evaluation -> WF84/WF85 non-executing review outputs -> attention queue -> intended digest delivery -> run-bound evidence/health receipt.
- Identify a canonical queue owner and ensure unresolved scope/evidence has an explicit monitor-only, blocked or review-required disposition. Do not turn missing data into an actionable signal.
- Existing Phase 3 owner supplies the recurring-cutover packet: exact current job IDs, old/new payloads, schedules/timezone, provider budgets (including quote-provider coverage), approval boundaries, rollout order and rollback. Do not assume four or five jobs from old notes.
- Apply only after scoped approval and independent QA. Test offline first, then a separately authorized non-delivery provider canary, then approved natural scheduled delivery. Never force all jobs to clear history.
- Phase 3H acceptance requires one complete market week of natural-run evidence under the accepted configuration, including each recurring contract's scheduled occurrence. Use the actual exchange calendar; weekends/holidays do not count as sessions. Material cutover changes restart the affected burn-in evidence window.

**Acceptance:** all in-scope instruments have valid evidence or honest exception dispositions; no stale/current mislabeling; no missing scheduled runs without escalation; provider budgets and boundaries hold; run IDs connect refresh, decision output and confirmed delivery. WF84/WF85 and boundary validators are current. Phase 3 stays open until its own 3H acceptance, even if workspace infrastructure repairs finish sooner.

## QA, approval and closeout contract

- Use Sonnet (`anthropic/claude-sonnet-4-6`) as independent QA for finance closeout, retaining Randall's Phase 3 instruction; propose the same independent reviewer for repair packages. Verify actual dispatch/model identity, bounded read-only scope and returned evidence. No silent reviewer substitution or QA credit for a timed-out/mismatched run.
- Main alone accepts each package after reproducing the original failure, reviewing the exact diff, running focused regressions and verifying rollback. Local tests do not establish service reboot continuity or external delivery.
- Before gated application provide exact targets/job IDs, minimal diff, source hashes, approved write lease, proof commands, exposure/cost/downtime impact, rollback, stop conditions and requested authority. This plan is not that approval.
- Preserve user-owned dirty work. Skill edits use Skill Workshop and explicit publication authority; protected core/config files remain Main-owned. No cleanup hidden in repair scope.
- Report four separate milestones: (1) control plane reliable, (2) health reporting truthful/delivered, (3) bounded recovery accepted, (4) finance Phase 3 accepted. Do not compress them into a premature all-green label.
- Final proof records remaining owner-gated items, elapsed time, retries, escaped QA defects and truthful usage availability. No invented savings, attribution or invoice claims.

## Next action / durable pickup

After Randall requests execution and current owners hand off, Main opens this note, rechecks all three leases and accepted outputs, then executes R1 only. Rebaseline removes work already fixed by those lanes. Present the exact R2 approval packet before any scheduler/runtime/service mutation. This note is the sole repair-plan pickup; current owner artifacts remain the sources of truth.
