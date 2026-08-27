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

## Promoted From Short-Term Memory (2026-08-27)

<!-- openclaw-memory-promotion:memory:memory/2026-08-25-2100.md:116:146 -->
- | Artifact Index | ✅ 0 stale files | | Wiki Bootstrap | ✅ Warning (classified, non-blocking) | **Wave 2 R4 remains healthy and ready for the 10-job measurement cohort.** user: What progress has Wave 2 R4 rmade? assistant: Let me check the current state of Wave 2 R4 progress, including any post-restart receipts and cohort status. assistant: The efficiency cohort ledger is from Aug 16 and hasn't been updated since the R4 activation. Let me check for any newer cohort data or protected dispatch receipts.... [score=0.928 recalls=10 avg=0.713 source=memory/2026-08-25-2100.md:116-146]
<!-- openclaw-memory-promotion:memory:memory/2026-08-25.md:1:13 -->
- # 2026-08-25 ## Wave 2 activation v3 ready; owner confirmation pending - Job 1 and the 10-job Wave 2 measurement-cohort manifest are frozen. Independent QA passed and is bound to the unchanged activation packet at `tmp/implementation-builder-scoped-worktree/scoped-worktree-activation-packet-v3.json`. - Activation packet v3 SHA-256: `efcf7cb852fc44ffd2054caa76eec4015b84ff1372907ba20fbbdd68a16d84c1`. Exact activation batch SHA-256: `845ddce8d0fd498b4d9ebc19ea827f2f11730dc8a2ae27d78e9b0571b070c9f2`. - Live configuration matched the required preimage when checked; apply and rollback dry-runs passed.... [score=0.908 recalls=12 avg=0.718 source=memory/2026-08-25.md:1-13]
<!-- openclaw-memory-promotion:memory:memory/2026-08-25.md:19:28 -->
- The separately approved K3/Ollama config repair was serialized behind activation and must re-read/re-hash the new config postimage before any later apply or test. ## Wave 2 Job 1 dispatch admission blocked after explicit owner authorization - Randall authorized the frozen Wave 2 Job 1 dispatch and the sequential 10-job cohort on the fixed Terra/low route. The frozen roster and all 24 primary/reserve preimages remain intact and clean; current cohort credit remains `0/10`. - Do not launch Job 1 yet: `project_implementation_router.py` permits low thinking only for read-only work, while Job 1 is a two-file scoped-worktree write.... [score=0.900 recalls=8 avg=0.689 source=memory/2026-08-25.md:19-28]
<!-- openclaw-memory-promotion:memory:memory/2026-08-25-2100.md:138:178 -->
- | Manual Restart | ✅ Complete | Gateway PID 29844 → 34060 | | P0 Protected Canary | ✅ **PASS** | A2 attempt successful, trusted receipt generated | | Runtime Acceptance | ✅ **PASS** | `wave2_runtime_acceptance: pass` | ### First Protected Receipt Details | Metric | Value | |--------|-------| | Receipt ID | `79880a8400a983133eece26645a75d098a7901d9c5236536ab7ca8e1e5402d69` | | Lane | `RUNTIME::HARNESS-V2-WAVE2-R4-POSTRESTART-20260824::protected-read-only-canary-a2` | | Model | `openai/gpt-5.6-terra` (low thinking) | | Backend | `persistent_isolated_agent` ✅ | | Input Tokens | 5,008 | | Output Tokens | 14 | | Total Tokens | 5,022 /... [score=0.868 recalls=8 avg=0.688 source=memory/2026-08-25-2100.md:138-178]
<!-- openclaw-memory-promotion:memory:memory/2026-08-23.md:42:45 -->
- Required pickup: reclassify scope/root cause, add stable Git status/diff inventory equality and a bound inventory digest at both checkpoints, revalidate immediately before downstream worktree consumption, freeze a new candidate, rerun deterministic validation, and obtain fresh independent QA. Canonical decision proof: `tmp/implementation-builder-scoped-worktree/independent-qa-r1.json`; integration proof: `tmp/implementation-builder-scoped-worktree/router-scoped-worktree-r1-applied.json`.... [score=0.857 recalls=7 avg=0.755 source=memory/2026-08-23.md:42-45]
<!-- openclaw-memory-promotion:memory:memory/2026-08-26-1322.md:88:105 -->
- Bottom line: 3 WAVE2 lanes are genuinely open; the WF74 compaction lane is closed as blocked/rejected. The immediate control-plane issue is stale `current-resume.json` pointing at the rejected WF74 lane. assistant: Sent the corrected current-lane status to Telegram. user: Provide the az time of when each opened lame assistant: Phoenix/AZ times (MST) for the current WAVE2 lanes: • `WAVE2::ten-job-cohort-20260826` — opened Aug 25, 2026 at 10:08:54 PM MST. Still running; lease expires Aug 26 at 4:08:54 AM MST. • `WAVE2::job1-zero-credit-calibration-20260826-a5` — opened Aug 25 at 10:20:09 PM MST.... [score=0.854 recalls=9 avg=0.716 source=memory/2026-08-26-1322.md:88-105]
<!-- openclaw-memory-promotion:memory:memory/2026-08-26.md:1:7 -->
- # 2026-08-26 ## Wave 2 isolated-agent cohort pickup - Randall explicitly directed Veritas to continue the recommended repair path and complete the fixed ten-job Wave 2 cohort until it is ready for Wave 3 review. This direction does not itself authorize Wave 3, route-policy promotion, config/auth/runtime mutation, finance/canon/portfolio action, or external execution. - Correction to the 2026-08-25 calibration incident: Terra connected and completed attachment/hash checks, tests, compilation, and candidate edits; the model connection failed only at the final-response turn.... [score=0.851 recalls=8 avg=0.738 source=memory/2026-08-26.md:1-7]
<!-- openclaw-memory-promotion:memory:memory/2026-08-26.md:9:15 -->
- Provider dispatch is still blocked on the exact owner approval card; Randall's general continuation instruction did not satisfy the controller's exact cohort-dispatch gate. Pending card: header `WAVE2-COHORT-10-JOB-LOW-ROUTE-APPROVAL-V2`, `approval_id=wave2-cohort-10-job-dispatch-20260826`, `scope_sha256=ae3d50483e4f9f722b4460d1bfb9d985d59ed352809a76e6c0465a64c3b863d8`, expiry `2026-08-27T05:20:21Z`. - After exact approval, jobs must run strictly sequentially through `implementation-builder` as `persistent_isolated_agent` on `openai/gpt-5.6-terra` with low thinking.... [score=0.850 recalls=8 avg=0.735 source=memory/2026-08-26.md:9-15]
<!-- openclaw-memory-promotion:memory:memory/2026-08-26.md:14:21 -->
- Randall directed an immediate hold after Job 2 expanded into a packaging/admission/QA repair loop. `workflow_control_override.py hold WAVE2 --validate` recorded `status=on_hold` at `2026-08-26T22:09:40Z` (15:09:40 MST). Resume requires a separate minimal nine-job restart contract and Randall's explicit resume. - Current cohort truth at disposition: Job 1 is the only qualifying credit (`1/10`); Job 2 Attempt 1 is blocked before source preflight with `packaging_path_error`, and its incident history remains immutable.... [score=0.846 recalls=8 avg=0.722 source=memory/2026-08-26.md:14-21]
<!-- openclaw-memory-promotion:memory:memory/2026-08-26.md:31:37 -->
- Randall issued the exact `WAVE2-NINE-JOB-RESTART-APPROVAL-V1` at approximately 16:33 MST. Main verified the packet and qualification hashes, all six frozen instrument hashes, clean controller status (`1/10`, Job 2 next), zero active lane collisions, and two clean Job 2 pre-dispatch worktree inventories, then removed the WAVE2 hold. - Job 2 Attempt 2 stopped before admission or provider dispatch when the binding producer returned `measurement_cohort_binding_frozen_reference_invalid`.... [score=0.830 recalls=6 avg=0.755 source=memory/2026-08-26.md:31-37]
