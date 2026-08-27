---
title: Controlled RSI Harness Implementation Audit
date: 2026-08-09
owner: Veritas main
scope: Review of tmp/RSI_HARNESS_BUILD_SPEC.md against the live Veritas/OpenClaw architecture
authority: review-only; proposal and audit artifact only
status: complete-review-only
---

# Controlled RSI Harness Implementation Audit — 2026-08-09

## Executive conclusion

The build specification is a strong target design for a controlled Recursive System Improvement (RSI) harness. Its separation of optimizer, evaluator, promotion review, and human authority is substantially aligned with Veritas doctrine.

It should not be executed verbatim as an implementation directive.

The correct Veritas decision is:

> Adopt the specification as a governed design reference, then implement a narrow adapter layer inside WF74/WF88 using existing proof surfaces. Do not create a competing RSI control plane, do not grant automatic promotion authority, and do not begin with model optimization before attribution, outcome linkage, and evaluator isolation are trustworthy.

This audit is proposal-only. It did not create `veritas-lab`, change model routing, alter OpenClaw configuration, apply a skill, run external model evaluation, schedule RSI work, or promote any candidate.

## Scope and evidence

Primary source:

- `tmp/RSI_HARNESS_BUILD_SPEC.md`, proposed-build-contract, version 1.0.0, dated 2026-08-09.

Live Veritas source surfaces reviewed:

- `TOOLS.md`, `AGENTS.md`, `06. Playbooks/Startup Truth Index.md`, and `06. Playbooks/Active Workflows.md`.
- `06. Playbooks/Project Continuity/Workflow 74 - Veritas Recursive Self-Improvement Loop.md`.
- `skills/veritas-self-improvement/SKILL.md`.
- `skills/agi-harness-readiness-operator/SKILL.md`.
- `skills/veritas-model-routing-helper-lanes/SKILL.md`.
- `tmp/agi-harness-readiness-packet.json`.
- `tmp/agi-os-eval-gate-packet.json`.
- `tmp/rsi-outcome-scorecard.json`.
- `tmp/wf74-learning-loop-eval-harness.json`.
- `tmp/wf74-wf88-loop-trace.json`.
- `tmp/wf74-auto-patch-proposer.json`.
- `tmp/frontier-capability-eval-spine.json` and `tmp/frontier-capability-eval-collector.json`.
- `tmp/model-quality-scorecard.json`, `tmp/implementation-token-attribution-bridge.json`, `tmp/cron-control-packet.json`, and `tmp/otel-ops-control.json`.
- Prior self-improvement and model-routing audits in `08. Audits/` and recent daily memory.

## Current Veritas readiness snapshot

The existing architecture is real and useful, but it is not ready for autonomous model/prompt/route promotion:

| Surface | Current state | Meaning |
|---|---|---|
| AGI harness readiness | `partial_ready_review_only_with_warnings`; 5/7 gates pass | Review-only harness progress, not autonomy readiness |
| AGI OS eval | 12/17 pass; 5 warnings; 0 failures | Outcome, frontier-evidence, token-efficiency, pilot, and compiler warnings remain |
| RSI outcome scorecard | 5 live rows; 0 stable closures; 25 missing-link items | Fixtures pass, but real improvement causality is not mature |
| WF74 learning-loop harness | 18/18 cases pass; proof-worker-ready | Contract routing is healthy; real-world improvement evidence is still limited |
| Model attribution | 493 token-attribution gaps reported; only 4 completed model lanes stamped | Model/cost comparisons remain incomplete |
| Model-quality scorecard | `scaffold_active` | Explicitly not a model ranker |
| Frontier comparison | 100 frozen cases / 300 matched assignments; 0 result rows | Collection spine exists, ranking and promotion remain blocked |
| Frontier collector | `blocked_owner_approval_required` | External model execution and spend require a separate exact approval |
| Prompt book | 15/15 covered; 0 eval gaps | Not the current bottleneck |
| OTEL | Operationally healthy | Useful metadata telemetry, not proof of decision quality by itself |
| Cron | 6 blocked signals in current freshness/control surfaces | Operational proof needs repair before high-cost RSI cadence |

The most important implication is that Veritas currently has a proposal-and-proof loop, not a proven self-improvement loop. Passing deterministic fixtures does not establish session-over-session improvement.

## Findings

### F1 — High: the execution directive conflicts with Veritas authority doctrine

The specification says to “continue through safe, reversible work without repeatedly asking for permission.” That is acceptable only for a narrowly leased workspace write scope. It is unsafe as a general instruction because this workspace separately requires approval before configuration, authentication, runtime, startup, service, cron, external, destructive, Skill Workshop, or model-policy changes.

Required amendment:

> Continue autonomously only inside an explicit workspace lane, exact allowed-write set, and validator contract. Stop at every owner-gated or external boundary even when the proposed change appears reversible.

The specification must not override `AGENTS.md`, `TOOLS.md`, `SOUL.md`, the live lane register, or workflow-specific gates.

### F2 — High: the proposed `veritas-lab` layout risks creating a second control plane

The specification correctly says it must extend Veritas, but then proposes a large parallel tree containing its own registries, database, datasets, traces, graders, experiments, promotion engine, reports, integrations, and a new CLI.

That duplicates existing owners:

- WF74 owns self-improvement intake, scoring, opportunity routing, proposals, and closure rules.
- WF88 owns downstream learning/wiki/decision routing and later-outcome visibility.
- OTEL owns operational telemetry.
- Existing ledgers own model runs, tokens, helper events, outcomes, lanes, and checkpoints.
- `data/evals/` and `data/wf74-learning-loop-evals/` already own evaluation fixtures.
- Existing validators, PM packets, Skill Workshop, and release contracts already own application gates.

Recommendation: do not create the full `veritas-lab/` tree initially. Build a contract-and-adapter slice against these owners. A new database or top-level package requires a demonstrated schema gap, a named owner, a migration/rollback plan, and an explicit anti-sprawl decision.

Ownership recommendation: WF88 should remain the cross-surface integration and decision-compiler owner; WF74 should remain the bounded self-improvement proposal, learning-loop, and closure router. Existing collectors, ledgers, validators, PM packets, and Skill Workshop remain their own evidence or application owners. This is a routing and ownership decision, not permission to create a new department or control plane.

### F3 — High: hidden-evaluator isolation is not stated consistently

Section 6.1 correctly says real hidden cases must not live in the optimizer-visible repository. Section 16.2 later says real hidden cases remain “in this workspace,” which is ambiguous and could mean the optimizer-visible workspace.

That must be resolved before implementation:

- The optimizer may receive only suite ID, hash, counts, category counts, and approved aggregate results.
- Real protected cases must live in a separately permissioned evaluator workspace or approved trusted service.
- The evaluator must return an allowlisted aggregate bundle, never raw hidden prompts, labels, or failure content that permits iterative tuning.
- A path under the normal shared workspace is not hidden merely because an agent is instructed not to read it.
- The current isolated-agent contract treats a workspace as a default working directory, not a hard sandbox. Physical access-denial, symlink, credential, network-egress, and production-write tests must pass before the word “hidden” is used.

The current frontier collector is honest about this limitation: it is verifier-ready, but has no execution results and no independent trusted attestation.

### F4 — High: trace/output requirements can violate the current privacy boundary

The specification asks RunRecord to retain tool calls and results, stdout/stderr references, final output references, and immutable traces. Veritas currently prohibits raw prompt, response, tool-payload, secret, header, and sensitive transcript capture.

The controlled implementation must store metadata and redacted references only:

- run, workflow, case, model, effort, tool-manifest, prompt/config hashes;
- token, cost, latency, retry, stop, validator, and authority-event metadata;
- sanitized failure class and artifact hashes;
- explicitly approved synthetic or public fixture outputs.

Raw payloads must not enter the RSI database, OTEL export, candidate workspace, audit packet, or external service. “Content-addressed output” is not automatically safe if the content itself is sensitive.

### F5 — High: local integrity evidence must not be called independent attestation

The specification uses signed aggregate results and promotion evidence. Local HMAC or hash chains can provide tamper evidence, but they do not prove provider origin, independent execution, independent grading, or human identity.

The audit and implementation contracts must distinguish:

1. local schema and hash integrity;
2. local runtime tamper evidence;
3. separate-process evaluator evidence;
4. provider/external execution attestation;
5. Randall’s explicit scoped approval.

Only the evidence actually present may support a ranking or promotion claim.

### F6 — Medium: the model strategy is aligned but must use exact route metadata

The model-role table is directionally correct and agrees with current routing:

- Sol for Veritas main, final integration, and authority-sensitive judgment;
- Terra for helper, builder, candidate, and routine evaluation work;
- Luna only for proven low-cost mechanical classification/proof paths;
- Python/tests for deterministic authority.

The specification’s Ultra policy is also correct: do not nest Ultra-style multi-agent orchestration inside every OpenClaw helper.

Every experiment must record exact provider/model ID, snapshot or alias, reasoning effort, mode, context settings, tool manifest, prompt/config hashes, and pricing metadata. “Sol,” “Terra,” or “Luna” alone is insufficient. The audit does not authorize a route change.

### F7 — Medium: generic promotion thresholds need suite-specific calibration

The proposed sample counts, confidence thresholds, cost limits, and percentage tolerances are useful starting points, not universal constitutional values. They must be calibrated to the suite, variance, protected-case severity, and decision consequence.

The promotion engine must never allow a composite score to compensate for an authority, freshness, security, schema, or critical factual failure. It should report a Pareto result across quality, critical-error rate, cost, latency, reliability, and maintenance complexity.

For finance workflows, fast engineering metrics and slow later-outcome evidence must remain separate. Runtime quality, citation validity, and rule compliance cannot be converted into investment-correctness claims.

### F8 — Medium: new OpenClaw agents and a new RSI skill are premature

The specification’s proposed `rsi-orchestrator`, builder, visible evaluator, adversary, hidden evaluator, and promotion auditor are reasonable future roles. They are not authorized additions.

Current doctrine requires:

- live config-schema validation;
- explicit model and sandbox policy;
- isolated workspaces and narrow tools;
- lane-register ownership and closeout;
- no channel bindings or gateway/config tools;
- exact Randall approval before configuration changes.

The current `veritas-self-improvement` skill already owns RSI routing and no-auto-apply boundaries. A new `skills/rsi-harness/SKILL.md` should not be created until an actual reusable gap survives the visible pilot and goes through Skill Workshop. The first implementation should extend or adapt current owners, not add skill directories by anticipation.

### F9 — Medium: the document itself needs normalization before machine use

The supplied file contains escaped Markdown/YAML markers, mojibake characters, and a malformed `primary_workspace` value (`C:\\Users\\Veritas.openclaw\\workspace` rather than the actual workspace path). Its headings and frontmatter may not parse as intended.

Before treating it as a machine contract, create a corrected version or normalization patch and validate:

- YAML/frontmatter parsing;
- Markdown headings and code fences;
- UTF-8 encoding;
- Windows path resolution;
- command syntax against the live OpenClaw/PowerShell environment.

This audit does not rewrite the source specification because the user requested review and audit, not source replacement.

### F10 — Medium: GitHub and branch operations are assumptions, not authority

The specification assumes an existing private GitHub repository, branch creation, commits, and draft pull requests. Those may be useful later, but repository status, remote ownership, credentials, branch policy, and external delivery must be verified separately.

No branch creation, commit, remote action, or pull request is implied by this audit. Any implementation must use the current lane/register and worktree protocol rather than running `git switch -c` from an agent instruction.

## Architecture comparison and recommended ownership

| Specification concept | Existing Veritas owner | Recommendation |
|---|---|---|
| System/champion version | model-quality scorecard, model-run ledger, route manifests, workflow state | Add only missing identity fields; do not create a parallel champion DB |
| Candidate manifest | WF74 auto-patch proposer, decision docket, PM jobs, Skill Workshop proposals, lane register | Use the existing proposal/lease/closeout chain |
| Eval cases and suites | `data/evals/`, `data/wf74-learning-loop-evals/`, prompt-book fixtures | Extend with frozen partitions and provenance; preserve source ownership |
| Run records | OTEL metadata, model-run ledger, token ledger, agent-message ledger, checkpoints | Add attribution at producers; do not capture raw content |
| Deterministic grades | WF74 outcome harness, AGI OS gates, changed-file and contract validators | Reuse and add only missing deterministic graders |
| Rubric/pairwise grades | WF74/WF88 review-only evaluation surfaces | Calibrate judges and keep their output non-authoritative |
| Hidden evaluation | Frontier eval spine and collector contract | Keep execution blocked until separate evaluator isolation and approval exist |
| Promotion decision | WF74 docket, PM/Skill Workshop/owner packet, release contract | Produce `APPROVAL_PENDING`; never auto-promote |
| Rollback | lane closeout, backups, release contract, workflow controls | Require exact candidate diff and tested rollback evidence |
| CLI | Existing `scripts\wf74_*`, `scripts\agi_*`, and validators | Add a thin route only if it reduces duplication; do not begin with a new `python -m rsi` control plane |

If the frontier comparison is later approved, the first external/model-backed pilot should use the existing frontier spine and collector—including its request renderer, rubric, budget reservation, HMAC/hash evidence, and attestation envelope. Do not create a parallel budget ledger, champion registry, or ranking path.

## Controlled implementation plan

### Gate 0 — Accept the design as proposal-only

Correct the source document’s authority language, hidden-evaluator wording, path/encoding defects, and ownership map. Record the implementation branch/worktree only when a separate implementation lane is approved.

### Gate 1 — Repair measurement before optimization

Prioritize:

1. model/session/token attribution gaps;
2. RSI correlation IDs, recurrence, closure, durability, and outcome links;
3. current cron proof blockers;
4. WF88 source-warning and decision-compiler follow-through;
5. trace-to-proposal-to-closeout linkage.

Do not spend the first implementation cycle on more candidate generation. Prompt-book coverage is already green; the bottleneck is trustworthy evidence conversion.

### Gate 2 — Build a minimal contract adapter

Map the specification’s `SystemVersion`, `CandidateManifest`, `EvalCase`, `RunRecord`, `GradeRecord`, and `PromotionDecision` concepts onto existing JSON/SQLite/history owners. Use one writer per experiment, immutable hashes, explicit redaction status, and no raw payload persistence.

Acceptance: schemas validate, forbidden-path checks work, metadata attribution is complete or explicitly classified unavailable, and no new control-plane authority appears.

### Gate 3 — Run a deterministic visible pilot

Use one narrow, file-contract-heavy, review-only workflow. Test:

- one champion;
- one deliberately worse challenger;
- one deliberately unsafe challenger;
- one legitimate single-hypothesis challenger.

Python and existing validators must reject the unsafe challenger without an LLM judge. The pilot must not touch finance canon, production skills, OpenClaw config, cron, paper/live/account surfaces, or external delivery.

### Gate 4 — Add calibrated visible champion/challenger evaluation

Use Terra for bounded candidate generation and routine grading, Sol only for material disagreement or architecture review, and model-free checks wherever possible. Compare equal inputs, tools, budgets, retries, and evaluator versions. Report paired deltas, uncertainty, missing runs, critical failures, cost, and latency.

The existing 100-case frontier design can be used later, but its collector remains owner-gated and has zero result rows. No model ranking follows from the frozen manifest alone.

### Gate 5 — Establish genuine protected-evaluator isolation

Prepare a separate evaluator workspace/agent or trusted service proposal. Validate the live OpenClaw schema and sandbox behavior before applying any config. Return only an allowlisted aggregate result. Keep the optimizer unable to read cases, labels, calibration examples, or raw hidden failures.

Do not claim hidden-eval protection while the evaluator and optimizer share a readable workspace.

### Gate 6 — Promotion preparation, canary, and rollback

The promotion engine may produce a decision packet, candidate diff, evidence hashes, protected-suite status, red-team result, cost/latency comparison, canary plan, and rollback package. It stops at `APPROVAL_PENDING`.

Keep these states separate: `LAB_CANDIDATE`, `EVALUATION_ELIGIBLE`, `APPROVAL_PENDING`, and `PRODUCTION_ROUTE_CHANGE`. Moving between them must never be inferred from a score, a model response, or a scheduled job.

For skills, the destination is a pending Skill Workshop proposal. For code, the destination is a leased implementation lane and reviewable diff. For config, model policy, runtime, cron, or external surfaces, the destination is an owner packet. No scheduled job may promote a champion.

### Gate 7 — Schedule only proven measurement

After manual pilot cycles prove budget, timeout, cancellation, trace completeness, and no authority leakage, schedule only read-only ingestion, deterministic validation, failure counts, and proposal reports. Keep hidden evaluation, canary authorization, promotion, merge, and deployment manual/on demand.

## Definition of controlled RSI for Veritas

Veritas may call the system a controlled RSI harness when it can demonstrate all of the following:

- repeated traces connect to evidence, failure class, candidate hypothesis, evaluation, and closure;
- candidates change one primary mutation family at a time;
- deterministic safety and contract graders run before model judges;
- champion and challenger use frozen, source-identical inputs;
- judge calibration and disagreement are measured;
- hidden/protected isolation is real or explicitly labeled unavailable;
- token, model, session, cost, latency, and tool attribution is complete or classified unavailable;
- critical authority/safety failures hard-block regardless of composite score;
- every candidate has immutable diff/hash and rollback evidence;
- the system can prepare an approval-ready recommendation but cannot approve, merge, deploy, mutate canon, or execute trades;
- post-change monitoring can identify regression and create an immutable rollback event.

This is system-level harness improvement, not base-model self-modification, AGI/ASI evidence, investment correctness, or autonomous authority.

## Final decision

**Status: proposal-only / implementation not yet authorized by this audit.**

The source build spec is suitable as a starting design after the ten findings above are corrected. The next safe implementation target is not a new autonomous RSI department. It is a narrow WF74/WF88 measurement-and-contract adapter that closes attribution and outcome debt, proves deterministic rejection and visible champion/challenger behavior, and preserves the current Sol-main/Terra-helper/Luna-deterministic routing doctrine.

No external, config, runtime, cron, finance, account, paper/live, Skill Workshop, or promotion action is implied.
