# Startup Truth Index

Thin startup/post-compaction pickup map. It routes to canonical owners; it does not replace them.

## Authority

- `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`, and `MEMORY.md` keep doctrine/runtime/continuity authority.
- `06. Playbooks/Active Workflows.md` owns live queue state; workflow continuity notes own resume detail.
- Canonical finance notes own portfolio truth. `tmp/` artifacts own generated proof/review packets only.
- Do not add durable boot/control surfaces unless this file and Active Workflows cannot own the route.

## Minimum Boot Path

1. Read T0: `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`; then this index. Validate compact resume state before Active Workflows.
2. Read `tmp/current-resume.json` and `tmp/current-active-lanes.json`; run `python -B scripts\session_resume_checkpoint.py --validate` before aliases, workflow notes, queues, or packets.
3. Reject an exact denylist match or consumed receipt. Otherwise acknowledge the exact ID and run only an authorized command. Record exactly one literal terminal outcome, `succeeded` or `failed`, then emit its successor; re-acknowledgement never restores consumption.
4. Search today's/yesterday's daily memory and, for direct-main/prior-decision work, `MEMORY.md`. The future-session packet is lower-precedence global context.
5. For named work, run `python -B scripts\workflow_router.py WF74 --answer summary` (replace WF74 with the named workflow) or read its fresh state capsule; indexes route proof only.
6. For material/high-risk work use `skills/task-intake-contract/SKILL.md`; for implementation/helper/QA use `skills/disciplined-implementation/SKILL.md`, exact lane leases/read-only declarations, smallest complete proof, and proof-backed closeout. Use the documented workflow-control override route to pause/resume.

## Post-Compaction Resume Transaction

- Pointer: `tmp/current-resume.json` (`veritas.session_resume_checkpoint.v1`); compact active state: `tmp/current-active-lanes.json`. The historical lane register is drilldown only.
- Precedence: active leased lane checkpoint -> exact workflow checkpoint -> named workflow continuity note -> PM queue -> general status.
- Multiple unresolved lanes, stale/missing lease or identity, hash drift, and expired freshness hard-stop pickup. Resume fields include exact steps/command, do-not-repeat list, hashes, attempt/lease, stop lines, and authority boundary.
- Exact-ID acknowledgement is idempotent; execution is not. Either terminal receipt consumes the command until changed content creates a successor. Use `--exact-next-command-base64` when Windows quotes/spaces cannot survive native binding. Emit after material transitions and before the memory-only compaction flush; the producer never executes or expands authority.

## Implementation Efficiency Contract

Material implementation must consume `veritas.execution_efficiency_policy.v1` from `scripts/project_implementation_router.py`; prose summaries do not outrank that contract.

1. Prefer `model_free_command` when an explicit deterministic command and proof are both available.
2. Use `codex_native_subagent` only by explicit opt-in for bounded read-only work on Terra/low or one exact leased implementation file on Terra/medium.
3. Use Main/Sol only for an explicit quick fix, final integration, or authority-sensitive judgment exception.
4. Route other bounded helper work to `persistent_isolated_agent` on Terra only after a fresh strict context-transport proof passes. Missing transport proof blocks dispatch; it does not authorize silent Main fallback.
5. Before dispatch, freeze an explicit base path, at most 6 files / 120,000 bytes / 30,000 estimated tokens, sorted hashes, manifest, and snapshot. Record phase, parent job, attempt/retry, and expected/actual route.
6. Any actual backend/model/thinking mismatch blocks closeout. Publish a provisional incident update within 90 seconds and keep retry metrics separate from first-pass results.
7. Micro work uses deterministic proof plus Main verification; narrow work uses focused tests plus Main; shared/major or privacy/security/authority/finance/repeated-failure work requires fresh independent QA after deterministic preflight.
8. Compare like-for-like accepted outcomes. Require at least 10 comparable Main-accepted jobs before treating a route as mature evidence; automatic ranking/promotion remains disabled.

New-session projections: `future_session_enhancement_packet.py` carries the full compact policy plus coding-outcome evidence; `startup_brief_packet.py` consumes that policy; `status_card_packet.py` shows a shallow summary without claiming an unobserved actual route. A missing/malformed policy blocks material implementation dispatch, not shallow status retrieval.

Shallow greeting/status: read `tmp/veritas-status-card-frontdoor.json` or run `python -B scripts\status_card_packet.py --read-only --frontdoor --render --validate`, then stop. If missing/invalid, run `python -B scripts\startup_brief_packet.py --write --validate`.

Routine encounter rules live in `06. Playbooks/Operating Procedures/Veritas Encounter Contract.md`; it grants no authority.

## Load Map

- Identity/boundaries: `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md`.
- Queue/resume: current resume checkpoint and compact active lanes first; then this index, workflow router/capsules, Active Workflows, and the exact continuity owner.
- Continuity: daily memory for recent deltas; `MEMORY.md` for durable decisions.
- Status/new session: cached status card, startup fallback, then future-session packet after compaction.
- Implementation: task intake, router, lane manager, disciplined-implementation, exact proof lookup, changed-file validator.
- PM/cron: PM control plus action/escalation consumers; cron control or WF73 ordered audit. Heartbeat is no-execute.
- Wiki: synthesis producer plus semantic bootstrap proof; wiki routes to owners and never grants apply authority.
- Improvement/token/OTEL: metadata-only ledgers and operational proof; no raw capture, standalone quality claim, or authority expansion.
- Finance: canonical notes/SQL/JSON owners plus finance skills; generated artifacts remain review-only.

## Queue Routing

Use the workflow router/capsules first, then Active Workflows or continuity notes only when source detail is needed.

- Primary finance route: WF78 evidence/freshness -> WF84 data plane -> WF85 decision OS; WF67 owns paper guards.
- WF86/WF87 paper autonomy remains shadow/reconciliation and exact-owner-approval gated.
- WF68 owns alerts; WF79 owns command-center views; WF72/WF73/WF71/WF76 own OS/control-plane routes.
- WF75 is paused as primary work unless Randall resumes it. WF80-WF83 remain hold/resume-later with public/customer/external action gated.
- For anything paused or blocked, read the capsule plus Active Workflows and stop before the gated action.

## Department And Skill Routing

- Material/high-risk task intake -> `task-intake-contract`; closeout/status -> `veritas-response-contract`; workflow pickup -> `project-continuity-manager`; memory -> `memory-continuity-manager`.
- Model/helper route -> `veritas-model-routing-helper-lanes`; isolation -> `veritas-isolated-agent-contract`; implementation -> `disciplined-implementation`; risk-budgeted review -> `workspace-qa-pass`.
- Serious finance challenger gates -> use `claude-cli/claude-opus-4-8` when available and verify actual subagent model path; labels are not proof.
- Runtime/control -> `openclaw-operator` / `openclaw-troubleshooter`; SEC/company evidence -> `sec`; paper guardrails -> `wf67-paper-trading-operator`.

## Script And Artifact Routing

- These are executable examples; where prose names alternatives, choose one rather than entering a pipe-separated pattern.
- Workflows: `python -B scripts\workflow_router.py WF74 --answer summary`; replace WF74 and choose summary, next, blockers, helper, or all. Rebuild with `python -B scripts\workflow_router.py --all --write-capsules --validate`.
- Startup: `python -B scripts\status_card_packet.py --read-only --frontdoor --render --validate`; fallback `python -B scripts\startup_brief_packet.py --write --validate`.
- WF74 pickup: `python -B scripts\main_session_greenkeeper_controller.py --refresh-frontdoors --execute-safe --write --validate --append-ledger`, then inspect `tmp/workflow-blocker-followups.json`. No schedule/state mutation.
- WF73 audit: `python -B scripts\wf73_control_plane_audit.py --write --validate`.
- WF88 wiki: `python -B scripts\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate`, then `python -B scripts\wiki_bootstrap_validator.py --write --validate`.
- Token route: refresh token ledger, budget, efficiency scorecard, and implementation attribution bridge before high-burn/cost claims. Preserve source semantics; unavailable/partial stays so. API-equivalent dollars are not billed cost, credits are estimates, OAuth is advisory, and no token surface may change schedules/models/runtime/auth/purchases.
- Compaction: `python -B scripts\session_resume_checkpoint.py --write --validate`, then `python -B scripts\future_session_enhancement_packet.py --write --write-md --validate`.
- Main pickup: escalation consumer for cron and action executor for PM, both `--context main_session --refresh-frontdoors --execute-safe --write --validate --append-ledger`. Heartbeat omits execute-safe and cannot spawn.
- Proof/concurrency example: `python -B scripts\artifact_index.py cockpit`; choose one documented lookup variant. Inspect lane syntax with `python -B scripts\concurrent_lane_manager.py --help`.
- Finance example for NVDA: `python -B scripts\finance_sql_canon_access.py --write --validate`, then `python -B scripts\finance_intelligence_state.py ticker NVDA --pretty`, then WF84/WF85.
- WF78 is non-capital repair/routing; WF84 is the structured data plane; WF85 is review/cards/assembler. Nothing generated is approval. Material status drills into exact packets; shallow status uses only the cached card.
- Validate with `python -B scripts\changed_file_validator_router.py --write --validate`; timing via `python -B scripts\validator_timing_ledger.py --profile normal`.
- WF80-WF83 stay hold/resume-later; route through their capsules if resumed. Archive candidates remain review-only pending references and owner approval. New helpers must pass reuse-before-new-script and system-aware implementation gates.

## Finance Truth Route

Markdown owns policy, narrative, decisions, reasoning, and audit context. `state/finance/finance-canon.sqlite` plus validated JSON own guarded structured ticker state, freshness, levels, lineage, tier, and universe fields. Generated packets/SQL/indexes remain review routes unless an exact apply gate says otherwise. WF78 freshness and WF85 review gates still apply; clean data is not customer, deployment, approval, or execution readiness.

Macro uses current metrics, energy, geopolitical, and judgment artifacts; review-only with no mutation/execution authority.

## Stop Lines

Stop before identity/doctrine rewrites; move/delete/archive; config/auth/channel/network/service/runtime mutation; brokerage/account/money/live-endpoint action; paper outside WF67; capital/trade/order action; finance mutation outside exact gates; or treating generated output as approval. Validated non-capital ticker routing may continue.

## Startup Behavior Rule

After compaction, validate the canonical resume checkpoint against compact active lanes before consulting lower-precedence packets or workflow routes. If it is missing, stale, blocked, or ambiguous, execution remains prohibited: use the declared precedence only for read-only discovery, emit and validate a fresh lane-bound checkpoint, acknowledge its exact ID, and only then execute. Do not rebuild the task from broad vault reads.
