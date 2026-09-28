---
name: "veritas-model-routing-helper-lanes"
description: "Model routing and route changes; policy reconciliation; cache, efficiency and frozen-contract reviews. Verify role-bound models and accepted outcomes."
---

# Veritas Model Routing And Helper Lanes

## Purpose

Choose the smallest reliable route that can earn Main acceptance within truth, validation, privacy and authority boundaries. Owner: `scripts/project_implementation_router.py`, contract `veritas.execution_efficiency_policy.v1`.

Veritas Main remains the queue owner, final integrator, QC owner, acceptance owner, finance truth surface, and user-facing judgment owner. A route changes capability and cost, never authority.

## Required Route Order

Apply this order before spawning or implementing:

1. `model_free_command` — use when an explicit deterministic command and proof are both available. Model is null; thinking is `none`.
2. `codex_native_subagent` — fail-closed: its model `openai/gpt-5.6-terra` is in `LEGACY_DENIED_MODELS` and no fresh capability proof exists, so do not dispatch it. Use GLM 5.3 for helper review instead.
3. `main` — resolve Main and any configured fallback from live OpenClaw global/session selection for integration, acceptance, and authority-sensitive judgment. Main does not author implementation code or substitute for independent QA.
4. `persistent_isolated_agent` — resolve stable IDs, exact role primaries and closed recovery lists through `scripts/agent_fleet_policy.py` and the router. Preserve current role bindings and code-author/independent-QA separation. Require fresh strict agent-matched transport proof. Persistent host-worktree writes require scoped-writeback proof (7-day validity and `scoped_writeback_preflight.py`); an attachment-only `patch_draft` uses its 24-hour readback proof, returns a diff, and leaves host source application to Main. Use the lane-mode gate in `veritas-isolated-agent-contract` rather than treating a v1 draft as writeback. Role rationale: the accepted six-family baseline (`data/evals/model-arena/arena-six-20260919/results/incumbent-baseline-20260919/main-acceptance.json`) rates DeepSeek 4.1 Flash stronger overall and GLM 5.3 Flash stronger on exact-format/tool work; evidence only.

Keep IDs/workspace/auth/history stable; use display names in prose. Specialist automatic fallbacks stay empty. The shared policy owns closed recovery lists. Build production spawn arguments only through `sessions_spawn_dispatch_contract`; require policy primary and live config to match before dispatch, and verify the actual model receipt at closeout. Main may select one listed backup only in a NEW clean-context attempt from a verified checkpoint, preserving role/scope and reacquiring model/runtime/transport/lease proof when changed or stale. Review cannot use the patch-author model. Options and structural checks prove no readiness or dispatch/write authority. Unproven recovery stays blocked; never silently substitute Main.

Main alone may dispatch Opus 5 advisory work on demand. Main fallback selection belongs to live configuration; Opus 5 remains barred as an isolated-agent persistent primary or recovery fallback. Grok 4.6 is an approved Main-selected recovery candidate for some specialists (`SPECIALIST_RECOVERY`), never an automatic fallback. For Opus 5, keep the canonical ref `anthropic/claude-opus-5`, pin a dedicated session, and wait until live runtime is `claude-cli` before the role's work. Do not isolated-spawn Opus 5 from a Sol/Grok/Codex parent, pass `runtime: claude-cli` to `sessions_spawn`, or use a `claude-cli/` model prefix. Verify actual model/runtime per task; aliases are not provenance. For an approved default-model, fallback-order or effort-level change, follow [Approved Route Change](references/route-change.md); when the owner authorizes reconciling the policy to live, follow [Policy Reconciliation](references/policy-reconciliation.md).

## Route Eligibility

### Model-free

Relevant command and proof must both be explicit. A declaration does not prove command execution; Main verifies the proof.

### Codex-native

Codex-native is fail-closed while its Terra route stays denied (route order item 2). Helper review uses GLM 5.3. Code implementation belongs to Muse Spark 1.3 Contributor, including one-file fixes; independent QA belongs to GLM 5.3. Multi-file writes, broad work, sensitive authority, and ambiguous scope are ineligible. Deterministic commands may verify artifacts but do not grant code-authoring, acceptance, or unattended-repair authority.

The requested and actual backend/model/thinking must be captured. Native rollout provenance must remain `codex_native_subagent`; a later update cannot relabel it.

### Persistent isolated agent

Require both an explicit readiness expectation and a workspace-relative strict JSON proof with status `ok`, matching agent identity, and an attested `attachment_context_transport`, `shared_main_workspace_access`, or scoped-worktree capability appropriate to the route. Attachment-readback proofs last 24 hours; scoped-worktree proofs follow route order item 4. The expected model must exactly match the selected agent's live configured model; model-family substitution blocks dispatch. Missing, stale, malformed, escaped, unsupported, agent-mismatched, model-mismatched, or false-capability proof blocks dispatch. A read-only attachment draft is not writeback proof.

### Main exception

Main is not the default broad implementation lane. Record why Main is the smallest reliable route while preserving the role assignments above. A helper blockage authorizes no silent fallback or substitution.

### Owner-directed same-session model roles

Only on an explicit owner request, follow the complete [same-session role procedure](references/task-role-contract-review.md#owner-directed-same-session-roles). Verify the actual model before each role, preserve scoped receipts and the non-independent-context disclosure, then restore Main and queue continuation.

## Frozen Task-Role Contract Review

Follow the complete [frozen-contract review procedure](references/task-role-contract-review.md#frozen-task-role-contracts) before reading consumers. Expiry or identity lock answers no; preserve immutable approval bindings and require a new approved contract instance for a new request. Finish with its bounded proposal, regression cases and truthful attribution.

## Delegation Decision

Before any helper dispatch, follow [Delegation Decision](references/delegation-decision.md). Default to no helper; delegate only for context load (builder, docs-continuity-editor), independent review (qa-redteam; finance implementation adds finance-redteam) or real web research (research-scout). It owns the dispatch path by runtime, credit rules, handoff and parallel caps. Finish when `python scripts\wf89_credit_reader.py` lists the run as CREDITABLE and the closeout names the reason that applied.

## Thinking Effort

- Low: deterministic reading, extraction, simple audit, or narrow proof.
- Medium: focused implementation, bounded repair, routine research, or ordinary QA.
- High: broad cross-contract challenge or serious bounded implementation where added depth is justified.

Do not use high effort merely because the task is called implementation. Thinking is an explicit route field, not a blanket default.

## Handoff And Validation Budget

Before dispatch, follow [Handoff Contract And Validation Budget](references/handoff-and-validation.md): at most 6 files, 120,000 bytes and 30,000 context tokens; risk-based QA; one repair plus one fresh QA pass.

## Closeout And Incident Contract

Closeout must record expected and actual backend/model/thinking, route conformance, authoritative usage or `provider_usage_unavailable`, duration, handoff size, QA verdict, Main acceptance, attempt/retry identity, and proof references. Any expected/actual mismatch fails closed.

For a failed or stalled lane, issue a provisional incident update within 90 seconds. Incident rows remain cost/retry evidence and never receive completed, first-pass, QA-pass, Main-accepted, or efficiency success credit.

## Efficiency Evaluation

For an on-demand economics review or token/cost-reducer check, follow [Accepted-Outcome Efficiency Review](references/efficiency-evaluation.md). It owns attempt accounting, cache and price semantics, missing-versus-zero handling, arithmetic checks, and comparison metrics; finish with verified coverage or explicitly unavailable values.

For a route whose prompt-cache reuse is in question, or before proposing a cache-sensitive route change, follow [Route Cache Reuse Review](references/route-cache-reuse-review.md). It owns per-route cache-eligibility, same-model cross-route comparison, readable-window separation, and the two multipliers (fallback order, context window). It does not repeat the accounting semantics owned by the efficiency review.

For requested multi-turn capability or correction-pressure tests, use Multi-Turn Model Evaluation (the `multi-turn-model-evaluation` skill). Verify user-message semantics before scoring rather than treating inter-session transport as an equivalent test.

Automatic route ranking and promotion are disabled. Evidence remains descriptive, and Main retains policy until an explicit change.

## Privacy

Store only allowlisted metadata and privacy-safe hashes. Never store raw prompts, responses, tool payloads, headers, secrets, credentials, account identifiers, or raw session/correlation values in routing or efficiency ledgers.

## Authority Boundary

Helpers may research, draft, implement bounded code, generate review-only proof, and challenge. They may not infer approval, accept their own work, make final finance judgments, mutate runtime/config/auth/channels/cron schedules, alter portfolio/canon outside an approved gate, contact external parties, execute paper/live trades, move money, or act on brokerage/account state.

## Closeout

Re-state the selected route and why it was the smallest reliable route; report actual route conformance, proof, outcome, usage availability, retry tax, residual risks, Main acceptance, and any owner-gated next action.
