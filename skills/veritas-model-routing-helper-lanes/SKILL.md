---
name: "veritas-model-routing-helper-lanes"
description: "Versioned execution route ladder, bounded handoffs, proportional QA, and quality-weighted efficiency."
---

# Veritas Model Routing And Helper Lanes

## Purpose

Choose the smallest reliable execution route that can earn Main acceptance without weakening truth, validation, privacy, or authority boundaries. The machine-readable owner is `scripts/project_implementation_router.py`; this skill explains how to apply its `veritas.execution_efficiency_policy.v1` contract.

Veritas Main remains the queue owner, final integrator, QC owner, acceptance owner, finance truth surface, and user-facing judgment owner. A route changes capability and cost, never authority.

## Required Route Order

Apply this order before spawning or implementing:

1. `model_free_command` — use when an explicit deterministic command and proof are both available. Model is null; thinking is `none`.
2. `codex_native_subagent` — opt-in only for bounded read-only work or one exact leased implementation file. Use Terra low for read-only and Terra medium for eligible one-file implementation.
3. `main` — explicit exception only for a quick bounded fix, final integration, or authority-sensitive judgment. Use Sol high.
4. `persistent_isolated_agent` — the remaining bounded helper route. Use Terra at effort matched to scope, and dispatch only with fresh strict context-transport proof.

Never silently fall back from a blocked persistent route to Main/Sol. Never select Kimi or another provider as a default route. Luna low remains limited to already-proven deterministic scheduled agent turns; command-backed deterministic work stays model-free.

## Route Eligibility

### Model-free

Relevant command and proof must both be explicit. A declaration does not prove command execution; Main verifies the proof.

### Codex-native

Codex-native must be explicitly allowed. Read-only work must be bounded. One-file implementation additionally requires one exact non-forbidden path, a leased or distinct-output write mode, single-surface scope, and no sensitive authority. Multi-file, broad, finance-sensitive, runtime-sensitive, external, destructive, or ambiguous work is ineligible.

The requested and actual backend/model/thinking must be captured. Native rollout provenance must remain `codex_native_subagent`; a later update cannot relabel it.

### Persistent isolated agent

Require both an explicit readiness expectation and a workspace-relative strict JSON proof, fresh within 24 hours, with status `ok` and an attested `attachment_context_transport` or `shared_main_workspace_access` capability. Missing, stale, malformed, escaped, unsupported, or false-capability proof blocks dispatch.

### Main exception

Main/Sol is not the default implementation lane. Record the exception reason. Main may own final integration and authority-sensitive judgment even when helpers performed implementation or QA.

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

Optimize for accepted outcomes, not the smallest raw token number. Compare like-for-like cohorts using:

- uncached input tokens per Main-accepted job;
- gross replay tokens per Main-accepted job;
- first-pass acceptance;
- elapsed time to accepted proof;
- retry tax;
- escaped defects.

Invalid or partial telemetry remains unavailable/partial and receives no success credit. API-equivalent cost is not an invoice, OAuth capacity is advisory, and token counts do not prove quota consumption.

Automatic route ranking and promotion are disabled. A route becomes statistically reviewable only after at least 10 comparable Main-accepted jobs. Until then, evidence is descriptive and Main retains the current policy.

## Privacy

Store only allowlisted metadata and privacy-safe hashes. Never store raw prompts, responses, tool payloads, headers, secrets, credentials, account identifiers, or raw session/correlation values in routing or efficiency ledgers.

## Authority Boundary

Helpers may research, draft, implement bounded code, generate review-only proof, and challenge. They may not infer approval, accept their own work, make final finance judgments, mutate runtime/config/auth/channels/cron schedules, alter portfolio/canon outside an approved gate, contact external parties, execute paper/live trades, move money, or act on brokerage/account state.

## Closeout

Re-state the selected route and why it was the smallest reliable route; report actual route conformance, proof, outcome, usage availability, retry tax, residual risks, Main acceptance, and any owner-gated next action.
