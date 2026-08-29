# MEMORY.md

Curated durable continuity only. Daily/session history lives in `memory/YYYY-MM-DD.md`; procedures live in `SOUL.md`, `AGENTS.md`, `TOOLS.md`, `USER.md`, skills, and owner notes.

## Identity And Relationship

- `SOUL.md` and `USER.md` own Veritas/Randall identity, relationship, timezone, style, and hard boundaries; do not duplicate or override them here.

## Durable Priorities

- Build a finance-first OpenClaw OS for market intelligence, portfolio decision support, AI/business opportunity intelligence, and workflow automation.
- Workspace files are the durable canonical financial database; generated artifacts are proof/review surfaces unless explicitly promoted.
- Keep notes/canon current only inside approved authority and exact validator-backed gates.
- Prepare evidence-backed portfolio-change proposals and capital-deployment recommendations while preserving human approval and trading/account boundaries.
- Preserve audit trails for important recommendations, decisions, assumptions, and workflow changes.

## Randall Preferences

- `USER.md` is authoritative. Durable shorthand: blunt truth, real-goal alignment, safe proactive repair, evidence-backed completion, plain English, and explicit uncertainty/next action.

## Durable Operating Decisions

- Daily continuity: `memory/YYYY-MM-DD.md`; curated durable continuity: this file.
- Doctrine hierarchy: `SOUL.md` -> `AGENTS.md` -> `USER.md` -> `TOOLS.md` -> procedures/skills -> `MEMORY.md` -> `HEARTBEAT.md` for heartbeat only.
- 2026-08-26: `IDENTITY.md` retired as a redundant SOUL.md mirror; identity lives in `SOUL.md` only.
- 2026-04-19: workspace pivoted to a finance-first operating model.
- 2026-04-23: `SOUL.md` became governing identity/boundary file; Veritas is the only active identity.
- Startup uses thin truth surfaces plus task-specific owners. Substantial/proof-heavy/phased work uses bounded helpers; main owns QC, queue, and synthesis.
- Durable scaling posture: WF84/WF85 is P0 finance; WF79-SMB is the resumed P1 monetization lane. Retail scaleout and WF80-WF83 remain paused until explicit resume. Current ordering comes from `06. Playbooks/Active Workflows.md` and live control packets, not this historical summary.
- Route/control posture: workflow, PM, cron, validation, and OTEL pickup should start from their control packets/capsules, then exact owner notes/artifacts. Generated SQL/JSON/SQLite/capsules are proof/routing only and never outrank canonical notes or approvals.
- Implementation posture: repeatable, report-only by default, reuse existing runners/manifests/validators, route proof by validation budget, and keep boot/core files route-only.
- 2026-06-29 MiniMax cron migration is historical proof only. Current live model/cron routing comes from `TOOLS.md`, `project_implementation_router.py`, and cron control; never infer current runtime state from the migration note. Historical proof: `tmp/minimaxm3-cron-promotion-phase2-final-summary-20260629.json`.
- Runtime posture: Python remains the workflow/finance spine; Go is read-only validator edge; Node owns cockpit/UI helpers.
- Heartbeat/PM/operator packets may refresh and report bounded handoffs only. They do not execute phases, spawn helpers, import SQL/tickers, launch customer output, mutate canon/portfolio/config/runtime, move/delete/archive, touch paper/live/account actions, or infer approval.
- Non-capital WF78 ticker tier/routing can be automated through validated artifacts. Capital deployment, execution, brokerage/account action, money movement, portfolio cash/sizing/execution mutation, destructive cleanup, config/auth/runtime mutation, and external/public action remain owner-gated.
- Archive/flattening requires no-loss/no-delete/proof-first posture: references, hashes, manifest, rollback, validation, and explicit owner approval when destructive.
- 2026-08-13 telemetry role split: OTEL is the local operational spine only (collector health, volume/drift, metadata-only tool/workflow failures); token/cost/model economics belong to the dispatch-binding plus Gateway usage-cost path (`isolated_agent_usage_metadata.py`, `token_usage_ledger.py`). Outcome-quality cohorts live in report-only `efficiency_cohort_ledger.py`; the router's `cohort_observation` block is report-only and never changes route order or promotion. Source: `memory/2026-08-13.md`.
- 2026-08-22 Harness V2 began with Randall's Wave 1-only approval for workspace-local truth repair and independent QA. Randall's later 2026-08-23 instructions explicitly resumed and completed the Wave 2 R3 rebuild. Waves 3-5 remain unauthorized; no schedule/service/runtime/finance/delete/archive/skill-apply authority is inferred. Exact owner plan: `06. Playbooks/Project Continuity/Veritas Harness V2 - Governance and Efficiency Upgrade Plan - 2026-08-22.md`.
- 2026-08-23 Wave 2 chronology: the first protected-dispatch candidate failed fresh QA on a HIGH SQLite-hydration identity-redaction bypass and its unaccepted artifacts were removed by approved cleanup; `tmp/wave2-closeout-summary-20260823.json` is truthful history for that attempt only. The later R3 rebuild is current truth: registry 99/99 and SQLite 10/10 passed, fresh independent QA returned PASS, and the accepted candidate is `tmp/wave2-rebuild-r3-artifacts/phase-i-fallback-fix/openclaw-2026.7.1.tgz`, 19,888,219 bytes, SHA-256 `c7ae764e27ecd5a54f2286f1b5bf3d85adb49b48d900deaac7484540862fd40a`.
- Randall gave the exact Wave 2 R3 install-only approval on 2026-08-23. Candidate SHA-256 `c7ae764e27ecd5a54f2286f1b5bf3d85adb49b48d900deaac7484540862fd40a` was installed globally with lifecycle scripts disabled; disk CLI/root/AI identity was `2026.7.1` / commit `0790d9f`. The approved memory-search hotfix SHA-256 `46dbfcb2f063d0b635a2c10f3c965f2bbb9b34d7e5cb5cecaa57611d50c07d66` was restored, candidate bundle hashes and process identities matched, and rollback was not invoked. At that install-only checkpoint no OpenClaw process was restarted. Randall's subsequent manual restart activated R3 and exposed the missing protected producer now superseded by R4. Historical R3 receipt: `tmp/wave2-rebuild-r3-artifacts/deployment-readiness-r1/wave2-r3-install-receipt-r1.json` (SHA-256 `73c4396738b243ab53fd0df172177408d06457c991bf11e8cd111446018cf7c5`).
- 2026-08-24 superseding Wave 2 disk truth: after R3 activation exposed the missing protected dispatch producer, Randall accepted the explicit Sol/ultra QA-route exception with zero route/efficiency/receipt/cohort credit and approved R4 install-only. R4 candidate SHA-256 `ce78658b60e8e2fafc078046138e286c8977b62b12a13862075bc3ae01051381` was installed with lifecycle scripts disabled; root/AI/CLI identity remains `2026.7.1` / commit `0790d9f`. The installed protected producer and identity-state bundle hashes match R4, and the approved R4 memory overlay SHA-256 `e59be8598de64350692c44b73909b45258d3454c1a1d807ae8b51b3379f89ff4` passed marker and syntax checks. Gateway PID `29844` stayed stable; no OpenClaw process was restarted or signaled and rollback was not invoked. Receipt: `tmp/wave2-rebuild-r3-artifacts/producer-restoration-r4/deployment-readiness-r4/wave2-r4-install-receipt-r1.json` (SHA-256 `12ff042798c3568f9e65923f2f2b9747100cf0c98bd54c2fc40e0e46960fdfa3`). Randall owns the manual restart/report-back gate; live R4 acceptance, the first protected receipt, and the comparable 10-job cohort remain pending, and Wave 3 is unauthorized.

## Current SQL And Finance Truth

- Canonical finance truth lives in `03. Portfolio/*`, `04. Research/Coverage and Watchlist.md`, risk notes, and approved owner artifacts.
- `state/finance/finance-canon.sqlite` is the guarded SQL-primary current-state/routing layer, never approval, capital, execution, customer activation, or ungated canon-mutation authority. Generated artifacts and caches remain proof/review surfaces unless exact gates promote them.
- SQL-first retail/customer use remains blocked pending retail-grade safety gates; keep SQLite stores separated by authority.

## Finance Authority Boundary

- `SOUL.md` owns canonical finance scope, authority gates, and hard boundaries; `AGENTS.md` owns the cron/automation limits. Do not restate them here.
- Active planning capital base: $10,000 flat as of 2026-05-18, with 10% target cash / $1,000 reserve and $9,000 investable planning capital.
- Keep separate: real $10k planning portfolio in `03. Portfolio/*` and Alpaca paper sandbox state in `tmp/wf67-paper-position-state.sqlite`.

## Finance Response Preferences

- `USER.md` owns answer detail. Start with the SQL guard/current state, then WF84/WF85 and exact source-open artifacts when stale, missing, contradictory, or material. Legacy packets are compatibility snapshots.
- Infrastructure-ready is not decision-data-ready. Use WF78 freshness and `trade_grade_data_readiness`; downgrade confidence and state gaps whenever true-fresh coverage or proof is insufficient.

## Durable Lessons

- If something matters, write it down. No mental notes.
- A tool/workflow is not ready until binary, auth, config, and actual runtime behavior are verified.
- On Windows, scheduled automation and environment variables can drift; verify live process reality.
- Readiness audits expire; revalidate old successes/failures before relying on them.
- If strategy changes, dashboards, memory, navigation, and startup surfaces must change with it.
- Artifact coherence matters as much as individual script success.
- Shared vocabulary/JSON contract changes require adjacent consumer and validator scans.
- Stop-breached and near-stop states outrank softer watch/almost/approval-history language; make stop/band math explicit.
- After code changes affecting freshness/trust-sensitive artifacts, regenerate or freshen proof before judging closure.
- Workflow names drift; verify exact live path before claiming a workflow is missing, blocked, or renamed.

## Silent Replies

When no response is needed, reply exactly:
NO_REPLY

## Promoted Continuity Index

- Persistent-agent doctrine and bootstrap ownership live in `skills/veritas-isolated-agent-contract/SKILL.md`; source history: `memory/2026-07-03.md:59-62`.
- Fleet roles and terminology: six configured persistent isolated agents; task-scoped children are bounded subagents/helper lanes. Main owns routing, QC, acceptance, and final synthesis. Source: `memory/2026-08-09.md:18-23`.
- Efficiency route: deterministic/model-free first; explicitly eligible bounded native Terra next; persistent Terra only with fresh transport proof; Main/Sol only for explicit quick fix, final integration, or authority-sensitive judgment. Exact live owner: `scripts/project_implementation_router.py`; do not promote defaults before 10 comparable Main-accepted jobs; automatic promotion stays disabled.
- Token/cost truth: cache-inclusive provider counters require provenance and fork-baseline subtraction; API-equivalent cost is not an invoice; unavailable usage needs a controlled reason. Source history: `memory/2026-08-09.md:1-8`, `memory/2026-08-11.md`.
- Startup/wiki truth is enforced by live bootstrap/status/wiki validators. Historical findings in `memory/2026-07-03.md:345-351` must not override current proof.
- Completion-ledger status is eligibility history, not live runtime proof. Source history: `memory/2026-06-18-2110.md:59-80`.
- Historical cron observations, including `memory/2026-04-23.md:58-64`, expire; inspect current cron control before claims or actions.

## Promoted From Short-Term Memory (2026-08-28)

<!-- openclaw-memory-promotion:memory:memory/2026-08-22.md:216:225 -->
- **Lesson.** When a gate reads permanently red, check whether a *second* implementation of the same metric is reading green before assuming the metric is merely pessimistic. ## Harness V2 Wave 2 - protected dispatch receipt candidate Randall authorized Wave 2 on 2026-08-22. I recut it around one real acceptance gate rather than another broad scorecard: `job -> dispatch -> provider run -> usage receipt -> validator -> Main acceptance`. The workspace-local producer/consumer implementation, tests, clean staging checks, no-install packaging, and rollback preparation are complete.... [score=0.883 recalls=7 avg=0.707 source=memory/2026-08-22.md:216-225]
<!-- openclaw-memory-promotion:memory:memory/2026-06-12.md:91:91 -->
- 2026-06-13 02:06 UTC: Completed Randall-approved third parallel implementation wave. Helpers shipped: PM visibility route standardization, WF78 human review surface, and WF85 market-hours refresh readiness precheck. `OpenClaw Parallel Work Plan.md` now has the durable pre-spawn route: run lane-register status, then `parallel_operator_visibility.py --write --validate`, then launch helpers only after active lanes/write leases/PM readiness are clear.... [score=0.871 recalls=7 avg=0.706 source=memory/2026-06-12.md:91-91]
<!-- openclaw-memory-promotion:memory:memory/2026-08-26.md:58:64 -->
- Randall explicitly retired the WAVE2 ten-job measurement cohort at `2026-08-27T02:02:16Z` (19:02:16 MST). `state/workflow-control-overrides.json` now preserves WAVE2 as `on_hold` with a no-resume condition: any future work needs a new, explicitly scoped decision for a distinct production-relevant pilot with a clear user-value acceptance target. - This retires only the active 10-job measurement cohort. It does not delete evidence, invalidate the valid Job 1 credit, roll back the installed R4/P0 evidence, change config/runtime, or authorize any Wave 3 action.... [score=0.859 recalls=5 avg=0.684 source=memory/2026-08-26.md:58-64]
<!-- openclaw-memory-promotion:memory:memory/2026-06-29.md:30:31 -->
- Refreshed token/model/cache efficiency scope after Randall asked how to gain efficiency. `token_efficiency_scorecard.py --write --validate` reported 426 token events, 23.20M total tokens, $8.30 estimated cost, 15 cron candidates, 14 API-call-reduction candidates, 11 prompt-compression candidates, 4 failure-cost candidates, and 308 implementation token-attribution gaps.... [score=0.849 recalls=5 avg=0.729 source=memory/2026-06-29.md:30-31]
<!-- openclaw-memory-promotion:memory:memory/2026-08-26.md:51:59 -->
- ## Wave 2 active-cohort reassessment - After the second pre-provider Job 2 failure, Veritas recommended ending WAVE2 as an active nine-job cohort: it has become a control-plane repair loop, with only Job 1 credited and no production/user-facing result from the remaining work. This is a recommendation, not an owner-approved abort. - Preserve all evidence and the valid Job 1 credit; keep WAVE2 on hold. Do not delete artifacts, retry Job 2, or resume the cohort. Any future revisit needs separate owner authorization and should begin as a value-defined, production-relevant pilot rather than another measurement-cohort repair cycle.... [score=0.843 recalls=6 avg=0.734 source=memory/2026-08-26.md:51-59]
<!-- openclaw-memory-promotion:memory:memory/2026-07-06.md:266:269 -->
- Randall approved full implementation of the `token_efficiency_promotion_gate` plan. Used `agi-harness-readiness-operator`, `cron-automation-manager`, `disciplined-implementation`, and `task-intake-contract` discipline. Opened and closed `WF88::token-efficiency-finance-fallback-proof-20260706` as L3 local code/proof work with exact writes only. - Added same-day changed-input prefilter proof to `scripts/ticker_card_freshness_owner_runner.py`.... [score=0.835 recalls=4 avg=0.741 source=memory/2026-07-06.md:266-269]
<!-- openclaw-memory-promotion:memory:memory/2026-08-11.md:30:31 -->
- Efficiency should optimize accepted outcomes, not the lowest raw token count: track first-pass acceptance, uncached tokens per accepted job, gross replay volume, time to accepted proof, retry tax, and escaped defects across like-for-like cohorts. Proposed route ladder: model-free deterministic proof; Luna/low for proven read-only status; Terra/medium for narrow single-owner implementation; Terra/high for cross-contract, privacy/authority-sensitive work and independent QA; Sol/high or ultra for Main integration, unresolved ambiguity, repeated failure, or final authority-sensitive judgment.... [score=0.816 recalls=3 avg=0.715 source=memory/2026-08-11.md:30-31]
<!-- openclaw-memory-promotion:memory:memory/2026-08-26.md:17:23 -->
- Restart proposal is recorded at `tmp/implementation-builder-scoped-worktree/cohort-run-20260826/wave2-hold-disposition-and-nine-job-restart-proposal-20260826.json`: one exact job lane at a time, 15-minute per-job cap, five-minute early checkpoint, zero same-pass repair attempts, focused test/compile plus Main acceptance, and stop-on-first-substantive-failure. ## Wave 2 nine-job pre-resume hardening completed - Randall approved the narrow zero-credit hardening pass. Main patched only the Wave 2 controller/worktree manager and their tests; no provider/cohort job was dispatched, no credit was awarded, and WAVE2 was not resumed.... [score=0.810 recalls=6 avg=0.715 source=memory/2026-08-26.md:17-23]
<!-- openclaw-memory-promotion:memory:memory/2026-08-26-1322.md:79:94 -->
- • Its next action is manual review of the three attempt-3 QA results and a newly scoped repair cycle. Important inconsistency: `tmp/current-resume.json` still carries an old active lease saying that lane is running, while the lane register says blocked. The resume checkpoint is therefore stale and cannot be trusted for automatic continuation; its own `safe_to_execute_automatically` is false. The actual register currently shows 3 open/running WAVE2 lanes: 1. `WAVE2::job1-zero-credit-calibration-20260826-a5` — implementation-builder, calibration; lease current to 11:20:09Z.... [score=0.810 recalls=6 avg=0.715 source=memory/2026-08-26-1322.md:79-94]
<!-- openclaw-memory-promotion:memory:memory/2026-07-04.md:115:120 -->
- Token efficiency candidates: top API-call reduction candidates were `PM - Autonomous Implementation Proof Worker`, `Finance - Ticker Card Freshness Owner Runner`, `Finance - Autonomy Spine Readiness Rollup`, `Runtime - Future Session Packet Refresh`, and `PM - GPT-5.5 Auto Implementation Proof Runner`. Best next engineering pattern is a deterministic changed-input predispatch source-hash gate that writes `skipped_unchanged` proof rather than mutating cron schedules.... [score=0.807 recalls=6 avg=0.536 source=memory/2026-07-04.md:115-120]
