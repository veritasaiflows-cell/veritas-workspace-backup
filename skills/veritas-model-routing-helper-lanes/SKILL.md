---
name: "veritas-model-routing-helper-lanes"
description: "Route Main and isolated agents by exact role-bound models."
---

# Veritas Model Routing And Helper Lanes

## Purpose

Choose the smallest reliable execution route that can earn Main acceptance without weakening truth, validation, privacy, or authority boundaries. The machine-readable owner is `scripts/project_implementation_router.py`; this skill explains how to apply its `veritas.execution_efficiency_policy.v1` contract.

Veritas Main remains the queue owner, final integrator, QC owner, acceptance owner, finance truth surface, and user-facing judgment owner. A route changes capability and cost, never authority.

## Required Route Order

Apply this order before spawning or implementing:

1. `model_free_command` — use when an explicit deterministic command and proof are both available. Model is null; thinking is `none`.
2. `codex_native_subagent` — opt-in only for bounded read-only work that is neither code implementation nor independent QA; use Terra low.
3. `main` — use explicitly configured Astra for integration, acceptance, and authority-sensitive judgment; Sol is Main's backup. Main does not author implementation code or substitute for independent QA.
4. `persistent_isolated_agent` — resolve stable IDs through `scripts/agent_fleet_policy.py` and the router: Opportunity Intelligence/Grok 4.6, Engineering QA/GLM 5.3, Finance Evidence/Terra, Finance Risk Challenger/GLM 5.3, Engineering Builder/Muse Spark 1.3 Contributor, Knowledge and Continuity/Luna. Require fresh strict agent-matched transport proof; writes additionally require scoped-writeback proof.

Keep IDs/workspace/auth/history stable; use display names in prose. Specialist automatic fallbacks stay empty. The shared policy owns closed recovery lists. Main may select one listed backup only in a NEW clean-context attempt from a verified checkpoint, preserving role/scope and reacquiring model/runtime/transport/lease proof when changed or stale. Review cannot use the patch-author model. Options and structural checks prove no readiness or dispatch/write authority. Unproven recovery stays blocked; never silently substitute Main.

Main alone may dispatch Sol architecture or Opus 5 advisory work on demand. Opus is never a persistent primary or automatic/recovery fallback. For Opus 5, keep the canonical ref `anthropic/claude-opus-5`, pin a dedicated session, and wait until live runtime is `claude-cli` before the role's work. Do not isolated-spawn Opus 5 from an Astra/Codex parent, pass `runtime: claude-cli` to `sessions_spawn`, or use a `claude-cli/` model prefix. Verify actual model/runtime per task; aliases are not provenance. Command-backed deterministic work stays model-free.

## Route Eligibility

### Model-free

Relevant command and proof must both be explicit. A declaration does not prove command execution; Main verifies the proof.

### Codex-native

Codex-native must be explicitly allowed and bounded read-only. Code implementation belongs to Muse Builder, including one-file fixes; independent QA belongs to GLM 5.3. Multi-file writes, broad work, sensitive authority, and ambiguous scope are ineligible. Deterministic commands may verify artifacts but do not grant code-authoring, acceptance, or unattended-repair authority.

The requested and actual backend/model/thinking must be captured. Native rollout provenance must remain `codex_native_subagent`; a later update cannot relabel it.

### Persistent isolated agent

Require both an explicit readiness expectation and a workspace-relative strict JSON proof, fresh within 24 hours, with status `ok`, matching agent identity, and an attested `attachment_context_transport`, `shared_main_workspace_access`, or scoped-worktree capability appropriate to the route. The expected model must exactly match the selected agent's live configured model; model-family substitution blocks dispatch. Missing, stale, malformed, escaped, unsupported, agent-mismatched, model-mismatched, or false-capability proof blocks dispatch. A read-only attachment draft is not writeback proof.

### Main exception

Main is not the default broad implementation lane. Record why Main is the smallest reliable route. Main/Astra owns final integration and authority-sensitive judgment; Muse authors implementation code and GLM 5.3 performs independent QA. A helper blockage does not authorize silent fallback to Main or model substitution.

### Owner-directed same-session model roles

When Randall explicitly directs Main-only work with named reviewer/QA models and no subagents, run each named role as its own sequential inference in the same Main session. Pin the session model to the named role's model, then verify the actual live model for that inference before doing the role's work; if the current inference is not the named model, reissue the caller-owned wake instead of claiming the role ran. Lease each role's writes as a bounded distinct-output lane, record the runtime backend distinction (for example `claude-cli/claude-opus-5` versus a requested provider path), and disclose that same-session roles are not clean-context independent review. Restore the primary Main model when the role's work ends and queue continuation through a caller-owned wake. The exception is task-scoped: it never becomes a persistent specialist, routing, or config change.

## Thinking Effort

- Low: deterministic reading, extraction, simple audit, or narrow proof.
- Medium: focused implementation, bounded repair, routine research, or ordinary QA.
- High: broad cross-contract challenge or serious bounded implementation where added depth is justified.

Do not use high effort merely because the task is called implementation. Thinking is an explicit route field, not a blanket default.

## Required Handoff Contract

Before dispatch, record:

- parent job, lane, phase, attempt number, and retry count;
- expected backend, exact model, and thinking;
- task shape, authority class, write scope, and exact leased writes;
- explicit workspace-relative base path;
- at most 6 files, 120,000 total bytes, and 30,000 estimated context tokens;
- sorted file inventory, sizes, SHA-256 hashes, manifest hash, and frozen snapshot ID;
- deterministic preflight status and proof;
- deliverable, acceptance criteria, stop lines, rollback note, next recipient, and timeout;
- fresh persistent transport proof when that backend is selected.

Re-use the same frozen snapshot for repair or QA when inputs did not change. If files changed, generate a new snapshot. Do not resend full transcript history when a bounded delta and exact owner files suffice.

## Validation Budget

- `micro`: deterministic proof plus Main verification.
- `narrow`: focused tests plus Main verification.
- `shared` or `major`: deterministic preflight followed by one fresh independent QA pass.

Independent QA is risk-based, not automatic for every patch. Use it for shared contracts, broad surfaces, finance/runtime/authority sensitivity, or judgment-heavy behavior. Cap ordinary rework at one bounded repair plus one fresh QA pass; after a second substantive rejection, stop and rescope rather than replaying the same large context.

## Closeout And Incident Contract

Closeout must record expected and actual backend/model/thinking, route conformance, authoritative usage or `provider_usage_unavailable`, duration, handoff size, QA verdict, Main acceptance, attempt/retry identity, and proof references. Any expected/actual mismatch fails closed.

For a failed or stalled lane, issue a provisional incident update within 90 seconds. Incident rows remain cost/retry evidence and never receive completed, first-pass, QA-pass, Main-accepted, or efficiency success credit.

## Efficiency Evaluation

Optimize for accepted outcomes, not the smallest raw token number. Review available like-for-like evidence when useful using:

- uncached input tokens per Main-accepted job;
- gross replay tokens per Main-accepted job;
- first-pass acceptance;
- elapsed time to accepted proof;
- retry tax;
- escaped defects.

Invalid or partial telemetry remains unavailable/partial and receives no success credit. API-equivalent cost is not an invoice, OAuth capacity is advisory, and token counts do not prove quota consumption.

Automatic route ranking and promotion are disabled. Randall may request an on-demand review from available token attribution, elapsed-time, retry, first-pass acceptance, and escaped-defect evidence. No fixed cohort pilot or minimum job count is required. Evidence remains descriptive, like-for-like comparisons are preferred when available, and Main retains policy until an explicit change.

## Privacy

Store only allowlisted metadata and privacy-safe hashes. Never store raw prompts, responses, tool payloads, headers, secrets, credentials, account identifiers, or raw session/correlation values in routing or efficiency ledgers.

## Authority Boundary

Helpers may research, draft, implement bounded code, generate review-only proof, and challenge. They may not infer approval, accept their own work, make final finance judgments, mutate runtime/config/auth/channels/cron schedules, alter portfolio/canon outside an approved gate, contact external parties, execute paper/live trades, move money, or act on brokerage/account state.

## Closeout

Re-state the selected route and why it was the smallest reliable route; report actual route conformance, proof, outcome, usage availability, retry tax, residual risks, Main acceptance, and any owner-gated next action.
