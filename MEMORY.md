# MEMORY.md

Curated cross-session continuity only. Daily chronology lives in `memory/YYYY-MM-DD.md`; current status lives in live owner artifacts; procedure lives in skills and playbooks.

## Scope And Ownership

- `SOUL.md` owns identity, mission, standards, and hard boundaries. `USER.md` owns Randall's preferences and durable goals. Do not mirror them here.
- `AGENTS.md`, `TOOLS.md`, the Startup Truth Index, and owner skills own startup, routing, implementation, status, cron, model, and response procedure.
- Current workflow, runtime, finance/alert, and approval truth must be read from their live canonical/control surfaces. Memory is a pointer, not execution or approval proof.
- Promote only durable decisions and lessons not already owned elsewhere. Do not paste generated promotion excerpts, score metadata, full status snapshots, command logs, or transient blockers into this file.

## Durable Historical Decisions

- 2026-04-19: the workspace pivoted to a finance-first operating model.
- 2026-04-23: `SOUL.md` became the governing identity and boundary file; Veritas is the sole active identity.
- 2026-08-29: the finance system pivoted from portfolio management to an **alerts-and-recommendations OS**. Active human canon moved to `03. Alerts and Recommendations/`. The old model, snapshot, rebalance log, and deployment packet were retired with hashes under `09. Archive/Finance Canon/2026-08-29-portfolio-management-retirement/`. Active canon and automation do not own sleeves, holdings, positions, allocations, weights, sizing, tranches, cash, rebalancing, or simulated account state. Guarded SQL retains alert evidence, source lineage, reference levels, thesis context, freshness, and recommendation-review state; the former WF78 tier-routing mirror is retired. Markdown retains human policy, thesis context, and alert interpretation. Paper/live execution is outside this OS.
- 2026-08-26: the redundant root `IDENTITY.md` mirror was retired. `SOUL.md` remains the identity owner.
- 2026-08-26: Randall retired the WAVE2 ten-job measurement cohort after repeated pre-provider control-plane failures. Preserve the valid R4/P0 runtime evidence and historical Job 1 credit, but do not resume that cohort. Any future effort requires a new, production-relevant pilot with an explicit user-value outcome and separate owner approval. Wave 3 remains unauthorized. Current owner: `06. Playbooks/Project Continuity/Veritas Harness V2 - Governance and Efficiency Upgrade Plan - 2026-08-22.md`; control: `state/workflow-control-overrides.json`.
- 2026-08-30: the custom OpenClaw `2026.7.1` runtime fork was retained at that date. Its dispatch-binding half was load-bearing after the WAVE2 retirement because isolated-lane token attribution failed closed without the v2 protected binding. Composition, live hashes, the unenforced `memory_search` phase-budget defect, and residue are documented in `migration-review.md`; source history is `memory/2026-08-30.md`.
- 2026-09-06: live runtime is official OpenClaw `2026.9.2` (`3928bad`). The 2026-08-30 custom `2026.7.1` fork is no longer the running binary; treat that note as historical. Isolated-lane token attribution and `memory_search` behavior must be re-proven against this stock build. Source: `memory/2026-09-06.md`.
- 2026-08-13: OTEL was separated from job-level model economics. Current ownership and routes live in `otel-operations-analyst`; source history is `memory/2026-08-13.md`.

## Durable Truth Pointers

- Current workflow priority and paused/resumed state: `06. Playbooks/Active Workflows.md`, workflow state/capsules, and current control packets.
- Current model, helper, implementation, and efficiency policy: `project_implementation_router.py`, `veritas-model-routing-helper-lanes`, `veritas-isolated-agent-contract`, and `disciplined-implementation`.
- Current cron and OTEL state: their control packets and `cron-automation-manager` / `otel-operations-analyst`.
- Canonical finance/alert truth: `03. Alerts and Recommendations/*`, `04. Research/Coverage and Watchlist.md`, risk notes, approved owner artifacts, and guarded SQL current-state proof. Generated packets and caches remain evidence routes, not capital, approval, account, or execution authority.
- Capital, reserve, investable amounts, holdings, allocations, sizing, and simulated account state are not system-owned finance canon. Owner-provided context may be used transiently for a recommendation without becoming maintained state.
- Retired paper workflow artifacts are historical or deny-only safety evidence. They are not an active operating route.
- Daily continuity: `memory/YYYY-MM-DD.md`. Resumable project state: its existing note under `06. Playbooks/Project Continuity/`. Long-work current state: its status packet and `state/long-work-jobs/` record.

## Durable Lessons

- If a decision matters and has no canonical owner, write it once in the correct durable surface.
- A tool or workflow is not ready until binary, auth, config, and actual runtime behavior are verified.
- Readiness audits and historical successes expire; revalidate before current claims or actions.
- Artifact coherence matters as much as individual command success. Shared vocabulary or JSON-contract changes require adjacent consumer and validator scans.
- Invalidation-threshold breach and near-alert states outrank softer watch or readiness language; make band/threshold math explicit.
- After changes affecting freshness or trust-sensitive artifacts, regenerate or refresh proof before judging closure.
- Workflow and artifact names drift; verify the exact live path before declaring something missing, blocked, or renamed.
- When two implementations of the same metric disagree, reconcile their inputs and ownership before accepting either conclusion.
- Efficiency means accepted outcomes with truthful elapsed time, retries, usage provenance, and defects--not the lowest raw token count. Current measurement policy lives in the routing and implementation skills.
- Use `memory_search` with `corpus=memory` for routine recall. `corpus=all` is structurally over the 15s tool deadline, its declared phase budgets are advisory rather than enforced, and its sessions corpus is off; reserve it for work that genuinely needs wiki content.
- A declared timeout constant proves intent, not enforcement. Verify a real cancellation path exists before trusting a budget; a race against uncancelled work can report "timed out" with an elapsed time far larger than the stated limit.
- Do not run `openclaw memory status --index` while the gateway is live. It opens a second writer against the same agent SQLite, and only full reindexes take a cross-process lock. `memory_index_chunks_vec` is created by a non-transactional `DROP`/`CREATE`, so a concurrent write inside that window fails with `no such table: memory_index_chunks_vec`. Plain `openclaw memory status` is read-only and safe.
- Semantic recall can degrade silently. A dropped or partially filled vector table raises no query-time error, only weaker results, so it must be detected rather than waited for. `semantic_memory_maintenance.py` now sweeps every agent store for a missing vec table or `vector_rows != chunks` drift.

## Historical Source Index

- Finance-first pivot and identity history: `memory/2026-04-19.md`, `memory/2026-04-23.md`, and `memory/2026-08-26.md`.
- Persistent-agent and helper-lane history: `memory/2026-07-03.md`, `memory/2026-08-09.md`, and `memory/2026-08-11.md`.
- Token/cost attribution history: `memory/2026-08-09.md`, `memory/2026-08-11.md`, and `memory/2026-08-13.md`.
- Harness V2/WAVE2 history: `memory/2026-08-22.md` through `memory/2026-08-26.md` and the Harness V2 owner plan.
- Boot and skills consolidation: `memory/2026-08-28.md` and `08. Audits/Core Boot And Skills Alignment Audit - 2026-08-28.md`.

## Promoted From Short-Term Memory (2026-09-03)

<!-- openclaw-memory-promotion:memory:memory/2026-08-14.md:35:40 -->
- Authority boundary preserved: JSON lane register remains primary; Postgres was not required or contacted, no service/install/runtime/config/network/credential change was allowed, no SQL execution/control authority was granted, and no finance/canon/portfolio/paper/live/brokerage/account action was authorized. ## 17:00 MST - Approved memory_search runtime patch and wiki performance review - Randall approved a scoped runtime patch/reload for the OpenClaw `memory_search` tool, with rollback and post-patch probes for `corpus=all`, `corpus=memory`, and `corpus=wiki`, plus a wiki performance/efficiency review.... [score=0.905 recalls=6 avg=0.711 source=memory/2026-08-14.md:35-40]
<!-- openclaw-memory-promotion:memory:memory/2026-09-01.md:10:13 -->
- Tier Entitlement v0.9.1 — Phase 3 roadmap and 3C pickup: The session-defined Phase 3 sequence is: **3A** dynamic guarded-SQL scope contract; **3B** shared local resolver and provider-disabled gate/preview; **3C** offline promotion compatibility; **3D** observed-entitlement coverage; **3E** changed-only Tier C material-attention queue; **3F** instrumented external canary; **3G** separately approved recurring scheduler/payload cutover; **3H** one-market-week burn-in and acceptance.... [score=0.891 recalls=6 avg=0.649 source=memory/2026-09-01.md:10-13]
<!-- openclaw-memory-promotion:memory:memory/2026-09-01.md:35:40 -->
- Phase 3F and 3G are prepared but still owner-gated. Current dynamic flags are intentionally preview/gate-only; `require_dynamic_entitlement_external_gate()` always denies and the dynamic CLI paths do not execute provider work. A future bounded 3F implementation must add a hash-bound, expiring one-shot approval-record verifier and canary-only execution path before any external canary can even be considered. A later 3G cutover separately depends on a Main-accepted 3F canary and may then propose changes to four named recurring contracts.... [score=0.866 recalls=6 avg=0.737 source=memory/2026-09-01.md:35-40]
<!-- openclaw-memory-promotion:memory:memory/2026-07-05.md:28:37 -->
- Expansion recommendation: keep semantic hybrid memory as proof-grade recall, not hot-path exact lookup; use FTS/workspace/artifact SQL for fast exact routing, and expand workflow memory by adding narrow workflow-checkpoint config/output patterns plus authority-labeled source families for each new workflow. ## Vector Memory Optimization And Source Registry - 09:59 MST - Randall approved proceeding with the vector-memory benchmark recommendations.... [score=0.821 recalls=5 avg=0.743 source=memory/2026-07-05.md:28-37]
<!-- openclaw-memory-promotion:memory:memory/2026-07-05.md:55:64 -->
- Retrieval hot-path guidance stands: use FTS/workspace/artifact SQL for exact routing first, then semantic hybrid memory for proof-grade recall when exact search is not enough. - Best next workflow-memory expansion targets remain WF78 -> WF84/WF85, WF75/WF79, WF73, and WF67, with all finance/execution/customer boundaries preserved. - Sunday finance refresh handoff remains blocked for broad weekly/canonical promotion because full Sunday closure surfaces are stale/incomplete; only the refreshed 2026-07-05 sub-artifacts should be treated as review-only evidence.... [score=0.814 recalls=5 avg=0.719 source=memory/2026-07-05.md:55-64]
<!-- openclaw-memory-promotion:memory:memory/2026-07-02.md:31:42 -->
- Randall approved proceeding with P1 after the P0 closeout. Created durable audit note `08. Audits/Skill Consolidation Matrix - 2026-07-02.md`. - Matrix covers all 47 live workspace skill bodies with current recommendation counts: 34 keep, 8 merge candidates, 4 review, and 1 already deprecated fallback (`technical-chart-pass`). - No live skill body, Skill Workshop proposal lifecycle, external install, finance/canon/portfolio state, capital/paper/live/account action, config/runtime surface, archive/delete path, or SEC `.venv` footprint was changed.... [score=0.802 recalls=4 avg=0.738 source=memory/2026-07-02.md:31-42]
