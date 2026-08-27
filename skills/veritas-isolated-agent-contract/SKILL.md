---
name: "veritas-isolated-agent-contract"
description: "Require v3 schema binding and actual post-apply diff/QA proof for isolated patch drafts."
---

# Veritas Isolated Agent Contract

## Purpose

Use persistent isolated agents and Codex-native subagents without confusing workspace separation, context transport, model routing, provenance, authority, or a draft with an applied change. This skill governs isolation mechanics; `scripts/project_implementation_router.py` owns execution-route selection.

## Distinguish The Runtime Forms

| Form | Runtime identity | Workspace/context | Best use | Not authority for |
|---|---|---|---|---|
| Persistent isolated agent | configured `agentId` with its own workspace, agent directory, session store, and tool policy | receives its own bootstrap; shared Main context requires proven transport | durable specialist persona or department | self-routing, self-acceptance, final truth |
| Codex-native subagent | task-scoped Codex session sharing the Main workspace | bounded task context; actual rollout metadata may be imported | narrow read-only work or eligible one-file implementation | broad multi-file work, hidden model/backend changes |
| OpenClaw sub-agent | child session of an OpenClaw agent | inherits the parent agent scope and bootstrap | background work inside that agent | a separate persistent persona |
| Bootstrap/capability packet | generated read-only context | current bounded doctrine and task contract | cold-start orientation | approval, canon, or execution authority |

OpenClaw does not discover agents from a fixed workspace folder. Use configured `agents.list[]` truth. Each persistent agent has an explicit workspace and agent directory. Workspace separation is organizational unless a separately proven sandbox is active.

## Route Selection

Use `veritas.execution_efficiency_policy.v1` in this order:

1. deterministic model-free command;
2. explicit eligible Codex-native route;
3. explicit Main exception;
4. persistent Terra helper with fresh strict transport proof.

A Main model exception must be explicit, approval-backed, and recorded. Do not silently use Main when persistent transport is unavailable. Do not select an isolated agent merely because parallelism is possible; the lane must be independently bounded and lower-cost or higher-quality than Main doing the same work.

## Persistent Context-Transport Gate

A persistent isolated agent may dispatch only when:

- Main explicitly expects transport readiness;
- a workspace-relative proof exists, is small, strict-schema, status `ok`, and no older than 24 hours;
- the proof attests the actual required capability: attachment readback for a patch-draft lane, or verified scoped writeback for an implementation lane;
- the referenced file resolves inside the workspace;
- the handoff has an explicit base path and frozen file inventory.

A tiny nonce proves only basic attachment delivery. It does not prove decompression, reader limits, source-file readback, hash verification, shell availability, or shared-workspace writeback. Missing, stale, malformed, path-escaping, unsupported, or false-capability proof fails closed. A valid proof attests capability; it does not itself enable transport. If transport is not actually available, rescope to an eligible native lane or stop. Never broaden Main implicitly.

## Patch-Draft Versus Implementation Lanes

Every persistent lane declares one of these mutually exclusive modes:

- **`patch_draft`** â€” the agent reads the frozen handoff and returns a unified diff or structured change proposal. Main applies any accepted diff, then validates the applied sources. The agent must never be described as having changed the shared workspace.
- **`scoped_worktree_implementation`** â€” the agent may write only after a fresh proof verifies its exact scoped writeback mount, path allowlist, and post-write diff/hash readback. Main still independently validates and accepts the applied sources.

Default to `patch_draft`. Granting a decoder or sandboxed shell does not grant shared-workspace writeback. Never solve a handoff problem by granting generic host shell, broad workspace access, elevation, network, session tooling, or execution authority.

## Frozen Handoff And Receiver Preflight

Each model-driven lane declares parent job, lane, phase, attempt, retry, expected backend/model/thinking, task shape, authority class, exact writes, deliverable, proof, next recipient, and stop lines.

The immutable handoff contains:

- workspace-relative base path;
- no more than 6 files, 120,000 bytes, and 30,000 estimated context tokens;
- sorted file paths, exact byte sizes, and SHA-256 hashes;
- contract hash and frozen snapshot ID;
- deterministic preflight fingerprint and status.

For a shell-free attachment lane, use a small raw UTF-8 manifest plus one raw UTF-8 attachment per source file. Keep each attachment and each individual line at or below a conservative 40 KB cap. Do not send gzip, base64 envelopes, or a large one-line JSON blob unless the receiver has freshly proven that exact decoding and reader shape.

Before dispatch, Main runs a receiver-capability preflight against the actual payload shape. It must prove, in the same agent/runtime mode:

1. multiline attachment readback at the intended cap;
2. each frozen source attachment can be read and hashes match the manifest;
3. the manifest is readable and its paths stay inside the declared base;
4. any required decoder/test command runs only in the approved sandbox; and
5. when implementation mode is requested, exact scoped writeback and post-write diff/hash readback.

A preflight failure is local and does not count as a model attempt. Record its typed reason and repair the handoff before dispatch.

Reject absolute paths, `..` escapes, symlink/reparse escapes, directories, case-folded duplicate paths, or budgets one unit over. Re-hash the frozen sources immediately before dispatch. For a completed `patch_draft`, do not falsely treat an authorized Main-applied change as frozen-input drift: validate immutable handoff metadata separately, then require each changed path to include its frozen before-hash/size and its actual post-apply workspace hash/size. Unchanged frozen files must still match their original hashes. A no-op, missing file, unlisted mutation, or path outside the frozen scope fails closed.

For v3 completion, the top-level manifest schema and handoff contract version must match exactly; compatibility wrappers cannot downgrade v3 proof. Require a real, bounded, hash-matched applied-diff artifact with normalized workspace-relative paths. Require a separate hash-matched QA-result artifact tied to the same frozen snapshot, applied-diff hash, changed paths, and post-apply hashes. QA commands must record a successful validation-runner invocation, output-artifact hash, and the exact changed paths/hashes they validated. Self-attested command lists, arbitrary hashes, and unrelated tests are not acceptance proof.

## Sandboxed Shell/Decoder Pilot

A persistent agent is shell-free by default. A shell/decoder pilot requires explicit owner approval and all of the following:

- Docker sandbox is live and independently verified before `exec` or `process` is permitted;
- one named agent only; no policy change for other agents;
- sandbox enabled for the agent, no network, no elevated tools, no host-workspace mount, no shared Main workspace, and no credential/config/channel/cron/session tooling;
- read-only root filesystem where the task permits it, with only an ephemeral scratch area;
- tight CPU, memory, PID, and wall-time limits;
- an exact allowlist of harmless decoder/test commands and a documented denial of arbitrary process behavior;
- positive proof that the allowed local command can process a benign supplied attachment; and
- negative proof that network, host-workspace reads, elevation, and forbidden commands remain blocked.

If Docker or the sandbox proof is unavailable, retain the shell-free path. Do not fall back to direct host execution. A successful pilot does not become standing shell authority; it expires unless renewed by a separately approved policy change.

## Retry Taxonomy And Attempt Accounting

Create a new session/run record for every dispatched attempt. Preserve the actual final successful-attempt identity; do not retain an earlier failed session as terminal provenance. Record exact attachment shape, byte/line limits, capability proof ID, typed failure code, first-attempt outcome, retry count, incident timestamps, 90-second provisional SLA, and terminal result.

Use at least these typed outcomes:

- `attachment_decode_unsupported`
- `attachment_reader_limit`
- `attachment_source_readback_failed`
- `attachment_hash_mismatch`
- `sandbox_unavailable`
- `sandbox_policy_denied`
- `scoped_writeback_unproven`
- `patch_draft_returned`
- `main_applied_after_draft`

Retries are never reported as first-pass success. A patch draft is not an applied patch. Exact repeats are idempotent; changed decisions/evidence receive a new sequence and monotonic timestamp.

## Codex-Native Eligibility And Provenance

Codex-native is opt-in. Allow:

- bounded read-only work at Terra low; or
- one exact leased implementation file at Terra medium when scope is single-surface and non-sensitive.

Reject multi-file, forbidden-path, shared-contract, broad, finance-sensitive, runtime/config/auth, external, destructive, or ambiguous implementation. Actual JSONL rollout import must consume only allowlisted metadata, require a unique safe completed subagent rollout, reconcile inclusive-cache usage, and preserve reasoning separately from total tokens.

For native imports, both expected and actual backend are immutable `codex_native_subagent`. Reject later attempts to relabel provenance. Hash and remove raw caller session, task, run, label, and role values at the sanitization boundary.

## Auth And Tool Isolation

- Each persistent agent loads its own agent-scoped auth profile surface; Main auth may only act as the configured fallback.
- Do not clone OAuth refresh tokens.
- Do not copy static credentials without explicit approval and need.
- Tool policy must be least-privilege and role-specific.
- External bindings, channels, cron schedules, services, network exposure, sandbox changes, and runtime/config/auth mutation require separate owner approval.

## Wiki Context Supply

Isolated agents cannot reach the WF88 wiki. Configured tool allowlists contain no `memory_search`, and bootstraps set `host_path_direct_reads_allowed=false`. Neither the canonical `wiki/**/*.md` pages nor the `state/wiki-retrieval` mirror is reachable from an isolated lane.

Main is therefore the only wiki reader. When an assignment depends on accumulated WF88 routing knowledge:

- Main runs `memory_search` with `corpus=wiki`, opens the named owner artifacts, and attaches the smallest sufficient excerpt inside the frozen handoff.
- The excerpt counts against the handoff budget like any other context file.
- A supplied excerpt is routing and evidence only. It is never canon, approval, execution, finance, or freshness proof, and it never substitutes for the current JSON/validator artifact it points to.
- Wiki retrieval is lexical, not semantic. A paraphrased query can return nothing even when the content exists, so a null result is not evidence of absence; confirm against `wiki/index.md` before concluding a route is missing.
- If a lane needs wiki context that was not supplied, it stops and requests it from Main rather than inferring it.

Never write an agent instruction to query a corpus its tool policy does not grant. Expanding an agent allowlist to include retrieval tools is a runtime/config mutation and requires separate owner approval.

## Bootstrap And Startup Truth

Generated agent bootstraps must project:

- current profile revision;
- Main as sole router, final QC, acceptance, judgment, and user-facing integration owner;
- the versioned efficiency policy;
- persistent Terra as the configured helper family with Sol helper upgrades disabled;
- exact transport and handoff requirements;
- role-specific read/write/tool boundaries;
- the wiki context-supply route, including truthful direct-retrieval capability;
- privacy-safe attribution and `provider_usage_unavailable` fallback;
- no finance, external, runtime/config, or execution authority expansion.

`scripts/agent_bootstrap_generator.py` produces these packets and `scripts/agent_bootstrap_linter.py` validates them. A generated packet never outranks `SOUL.md`, `AGENTS.md`, `TOOLS.md`, this skill, or exact owner artifacts.

## Usage And Outcome Attribution

Capture expected and actual backend/model/thinking, cache-inclusive token counters, uncached input, output, reasoning metadata, handoff size, duration, QA result, Main acceptance, and retry tax when exposed. Join using deterministic privacy-safe attempt identity; ambiguous or conflicting identities fail closed. Never invent usage.

Incidents and invalid telemetry retain cost evidence but never count as completion, first-pass success, QA pass, Main acceptance, or cohort eligibility. Actual billed cost and OAuth impact remain unknown unless directly observed by an authoritative source.

## Validation

Before acceptance verify:

- live configured agent/workspace/tool policy;
- route eligibility and transport/sandbox proof;
- manifest-schema/contract-version match, frozen metadata, and actual post-apply file hashes;
- expected/actual route conformance;
- supplied wiki excerpts resolve to named owner artifacts and claim no authority;
- typed attempt/retry and incident SLA;
- metadata-only privacy boundary;
- focused tests and risk-budgeted QA;
- Main verification and acceptance evidence.

For a Main-applied patch draft, QA must inspect and test the applied source files and their diffâ€”not only the agent's proposed diff.

## Stop Lines

Stop when transport cannot be proven, context exceeds budget, source files mutate after freeze, actual route differs, identity is ambiguous, privacy-safe sanitization fails, required proof is stale, an instruction assumes a tool the agent's policy does not grant, a sandbox precondition fails, or work needs config/auth/channel/runtime/cron/finance/execution/external/destructive authority not explicitly granted.

## Closeout

Report selected runtime form, lane mode, exact agent/session privacy-safe reference, expected and actual route, transport/sandbox proof, handoff snapshot, attempts/retries, usage availability, validators, QA result, Main acceptance, remaining limitations, and owner-gated actions.

