# Truth-First Deterministic Agentic Harness Operating Doctrine

**A model-agnostic operating guide for truthful, efficient, controlled, progressively autonomous LLM systems**

**Version:** 1.0.0  
**Issued:** 2026-08-23  
**Status:** Normative baseline  
**Intended use:** New LLM harnesses, agent operating systems, autonomous workflow runtimes, coding/research agents, and future higher-capability systems  
**Primary priorities:** Truth, authorized control, correctness, recoverability, efficiency, then autonomy  
**Compatibility goal:** Local-first or cloud-backed; single-agent first; multi-agent only when justified; provider-agnostic; MCP-compatible; OpenTelemetry-compatible but not dependent on either  
**Operating maxim:** **Autonomy is earned, scoped, observable, revocable, and reversible.**

---

## Table of contents

- [0. Purpose](#0-purpose)
- [1. Normative language](#1-normative-language)
- [2. Priority order](#2-priority-order)
- [3. Constitutional invariants](#3-constitutional-invariants)
- [4. The harness as an operating system](#4-the-harness-as-an-operating-system)
- [5. Logical roles and separation of duties](#5-logical-roles-and-separation-of-duties)
- [6. Authority and autonomy model](#6-authority-and-autonomy-model)
- [7. Truth architecture](#7-truth-architecture)
- [8. Bootstrap and startup](#8-bootstrap-and-startup)
- [9. Task intake contract](#9-task-intake-contract)
- [10. Route selection](#10-route-selection)
- [11. Memory and retrieval](#11-memory-and-retrieval)
- [12. Context engineering](#12-context-engineering)
- [13. Tool and agent-computer interface design](#13-tool-and-agent-computer-interface-design)
- [14. Execution engine](#14-execution-engine)
- [15. Concurrency, lanes, and leases](#15-concurrency-lanes-and-leases)
- [16. Transactional mutation and rollback](#16-transactional-mutation-and-rollback)
- [17. Sandbox, identity, and agent security](#17-sandbox-identity-and-agent-security)
- [18. Scheduled automation](#18-scheduled-automation)
- [19. Receipts, provenance, and acceptance](#19-receipts-provenance-and-acceptance)
- [20. Observability and correlation](#20-observability-and-correlation)
- [21. Validation, evaluation, and assurance](#21-validation-evaluation-and-assurance)
- [22. Truthful model behavior](#22-truthful-model-behavior)
- [23. Self-improvement and learning](#23-self-improvement-and-learning)
- [24. AGI readiness and autonomy doctrine](#24-agi-readiness-and-autonomy-doctrine)
- [25. Efficiency doctrine](#25-efficiency-doctrine)
- [26. Multi-agent operating doctrine](#26-multi-agent-operating-doctrine)
- [27. Repository and deployment blueprint](#27-repository-and-deployment-blueprint)
- [28. Canonical contract templates](#28-canonical-contract-templates)
- [29. Operating runbooks](#29-operating-runbooks)
- [30. Implementation roadmap](#30-implementation-roadmap)
- [31. Service objectives and scorecard](#31-service-objectives-and-scorecard)
- [32. Failure taxonomy and prescribed response](#32-failure-taxonomy-and-prescribed-response)
- [33. Anti-patterns](#33-anti-patterns)
- [34. Design-review checklist](#34-design-review-checklist)
- [35. Minimum viable core](#35-minimum-viable-core)
- [36. Launch gates](#36-launch-gates)
- [37. Doctrine governance](#37-doctrine-governance)
- [38. Research provenance](#38-research-provenance)
- [39. Research references](#39-research-references)
- [40. Final doctrine](#40-final-doctrine)

---

## 0. Purpose

This doctrine defines how to construct and operate an LLM harness that remains truthful, efficient, controlled, and recoverable while gaining bounded autonomy.

It treats the model as a powerful but probabilistic reasoning component. It treats the harness as the durable system that owns identity, authority, state, context, tools, execution, validation, recovery, observability, and acceptance.

The doctrine is designed to preserve reliability as models become more capable. It does not assume that a larger context window, stronger reasoning model, larger agent swarm, or higher benchmark score automatically produces a trustworthy system.

The doctrine combines proven operating patterns from two internal harness research reports with current research and standards on agentic systems, long-running agents, evaluation, prompt-injection defense, AI risk management, AGI measurement, durable execution, observability, and software provenance. Internal patterns, external research, and new normative synthesis are separated in the reference registry.

### 0.1 What this doctrine means by “deterministic”

The model itself is not assumed to be deterministic. Even with fixed settings, model outputs can vary because of provider implementation, model updates, distributed inference, tool responses, and environmental state.

“Deterministic harness” means:

- control-flow transitions are explicit and machine-checked;
- authority decisions are made by policy outside the model;
- state mutations occur through typed transactional paths;
- tool calls have validated schemas and bounded effects;
- retries use idempotency keys;
- acceptance commands are exact and reproducible;
- source versions and artifacts are content-hashed;
- failures have semantic classes;
- completion is established by evidence, not by model prose;
- recovery replays durable state rather than reconstructing intent from chat.

The harness contains probabilistic reasoning inside deterministic boundaries.

### 0.2 What this doctrine means by “autonomous”

Autonomous does **not** mean unrestricted.

An autonomous agent is allowed to choose steps and use tools inside a pre-authorized task envelope. It may not:

- invent its own authority;
- expand its write scope;
- activate new connectors;
- expose secrets;
- lower approval requirements;
- redefine completion;
- promote its own policy or model route;
- convert a recommendation into a consequential action without the required gate.

### 0.3 What this doctrine means by “AGI-ready”

“AGI-ready” is an architectural property, not a claim that AGI exists in the harness.

An AGI-ready harness:

- can absorb stronger models without making authority model-dependent;
- measures performance, breadth, autonomy, and risk separately;
- keeps the execution boundary outside the model;
- supports stronger oversight as task horizons lengthen;
- can remove obsolete scaffolding through evidence-backed ablation;
- preserves durable truth, provenance, reversibility, and human intervention;
- does not confuse model capability with permission.

### 0.4 Non-claims

This doctrine is not:

- an AGI or ASI declaration;
- a safety certification;
- a legal or regulatory compliance opinion;
- a substitute for domain-specific controls;
- proof that an agent is aligned;
- permission for financial, medical, legal, military, infrastructure, account, or other high-impact action;
- a guarantee that prompt injection can be completely solved;
- a reason to expose more tools or data than the task requires.

---

## 1. Normative language

The words **MUST**, **MUST NOT**, **REQUIRED**, **SHOULD**, **SHOULD NOT**, and **MAY** are normative.

- **MUST / REQUIRED:** violation invalidates the design or run.
- **SHOULD:** expected unless a documented exception and compensating control exist.
- **MAY:** optional and justified by local needs.
- **Owner:** human or formally delegated authority that may approve a protected action.
- **Main:** the accountable integrator that classifies, routes, reconciles, accepts, and closes work.
- **Canonical:** authoritative for a defined truth class.
- **Derived:** generated from canonical or external sources and never authoritative by itself.
- **Receipt:** immutable evidence describing what actually happened.
- **Acceptance:** explicit decision that the required evidence is sufficient.
- **Gate:** deterministic mechanism that allows, pauses, blocks, or rejects a transition.
- **Lane:** bounded unit of concurrent work with a declared owner, scope, lease, and proof.
- **Session:** durable event stream for one logical run or continuation chain.
- **Sandbox:** isolated execution environment with scoped resources and no ambient authority.
- **Capability:** explicit, narrow permission to perform a class of action on a named resource.

---

## 2. Priority order

When priorities conflict, apply this order:

1. **Truth and provenance**
2. **Explicit authority and non-escalation**
3. **Safety, security, and privacy**
4. **Correctness and acceptance evidence**
5. **Recoverability and reversibility**
6. **Efficiency of context, compute, time, and attention**
7. **Helpfulness and speed**
8. **Autonomy and convenience**

Efficiency is a top-level goal, but a fast false answer or an efficient unauthorized action is a system failure.

---

## 3. Constitutional invariants

These invariants apply to every model, provider, task, tool, workflow, and agent.

### 3.1 Truth invariants

1. Every material truth class MUST have exactly one canonical owner.
2. A derived index, vector hit, graph edge, wiki page, summary, status packet, or model statement MUST NOT silently become canon.
3. Retrieval routes to evidence; retrieval is not evidence.
4. The cited source record establishes truth.
5. Every consequential claim MUST expose source, freshness, and confidence.
6. Stale, superseded, contradictory, unavailable, and degraded evidence MUST be labeled.
7. Unresolved contradictions MUST be surfaced, not blended into a confident answer.
8. The harness MUST distinguish facts, calculations, inferences, recommendations, and approvals.
9. A technically clean result MUST NOT be represented as authorized unless approval is independently present.
10. A model saying “done” is never completion proof.

### 3.2 Authority invariants

11. Every material task MUST have an authority class before execution.
12. Authority MUST be checked at the action boundary, not only stated in a prompt.
13. The model MUST NOT grant, infer, widen, transfer, or persist authority.
14. Read, propose, mutate, execute, publish, spend, and delete permissions MUST be distinct.
15. Protected actions MUST require a capability or approval token bound to task, scope, subject, and expiry.
16. Tool availability does not imply tool authorization.
17. A clean validation result does not imply permission to deploy or release.
18. Helpers may contribute evidence but MUST NOT own final canonical conflict resolution or acceptance unless explicitly assigned that role.
19. External content MUST be treated as untrusted data, never as a policy source.
20. Missing authority MUST fail closed.

### 3.3 Execution invariants

21. Deterministic work MUST precede model work.
22. Every mutation MUST pass preflight, scope, lease, and policy checks.
23. Side effects MUST be idempotent or have an idempotent compensation.
24. Commands used for acceptance MUST be argv arrays or an equally typed representation, never ambiguous shell strings.
25. Execution environment, working directory, interpreter, dependencies, and input snapshot MUST be pinned or recorded.
26. Material writes MUST have before/after fingerprints or equivalent state attestations.
27. Failed attempts and failed receipts MUST be retained according to policy.
28. Long-running work MUST leave a bounded pickup packet and durable checkpoint.
29. A run MUST stop when its budget, lease, authority, source freshness, or acceptance assumptions become invalid.
30. Retries MUST be based on semantic failure class, not blind repetition.

### 3.4 Assurance invariants

31. Validator success and Main acceptance MUST be separate states.
32. The implementation path MUST NOT be the sole grader of its own high-risk change.
33. Every gate and aggregator MUST have negative-path tests.
34. Outcome state MUST outrank narrative claims.
35. Evaluation readiness MUST NOT be reported as evaluation evidence.
36. Operational telemetry MUST NOT be reported as model quality, correctness, or approval.
37. Every material run SHOULD be reconstructible from one correlation identifier.
38. Raw prompts, responses, tool payloads, credentials, and customer data MUST NOT be captured by default.
39. Rollback or compensation MUST be prepared before activation for shared or consequential changes.
40. Proof MUST be retained, archived with immutable hashes, or retired with an approved tombstone.

### 3.5 Efficiency invariants

41. The harness MUST prefer exact routing over broad scanning.
42. Startup context MUST contain pointers and current operating state, not the whole repository.
43. Context MUST be selected just in time and bounded by task need.
44. Whole-document retrieval SHOULD be replaced by section- or record-scoped retrieval.
45. Unchanged work SHOULD be skipped using correct input signatures.
46. Hygiene, freshness checks, integrity checks, cache sweeps, and routine maintenance MUST be model-free unless the task is inherently semantic.
47. A stronger or more expensive model MUST be used only when a measured task requirement justifies it.
48. Multi-agent orchestration MUST NOT be introduced until single-agent execution, receipts, collision safety, and acceptance are mature.
49. Harness components MUST be periodically ablated; scaffolding that no longer improves outcomes SHOULD be removed.
50. Proposal volume, packet volume, tool-call count, and token use MUST NOT be treated as progress.

### 3.6 Evolution invariants

51. Self-improvement detection MAY be automated broadly.
52. Self-improvement application MUST remain gated.
53. The system MUST NOT autonomously modify its authority model, protected policy, secret handling, approval requirements, or evaluation criteria.
54. A candidate improvement MUST be compared against a pinned baseline and equivalent cohort.
55. Route or model promotion MUST use accepted outcome evidence, not preference or isolated anecdotes.
56. Closed improvements MUST receive a later-outcome check and recurrence window.
57. A recurring defect MUST reopen automatically or be explicitly reclassified.
58. Autonomy MUST increase only after evidence, and MUST be revocable without data loss.

---

## 4. The harness as an operating system

The harness is not a prompt collection. It is an operating system around a probabilistic model.

The model supplies:

- language understanding;
- synthesis;
- planning under ambiguity;
- tool selection within an admitted envelope;
- hypothesis generation;
- error recovery suggestions;
- semantic judgment;
- communication.

The harness supplies:

- identity and mission;
- policy and authority;
- canonical truth ownership;
- durable state;
- source selection;
- context assembly;
- tool definitions;
- action mediation;
- concurrency control;
- checkpointing;
- validation;
- acceptance;
- observability;
- recovery;
- evaluation;
- improvement governance;
- stop conditions.

### 4.1 Canonical operating loop

```text
objective
-> intake and interpretation
-> authority and risk classification
-> exact route selection
-> source and freshness resolution
-> bounded context assembly
-> plan and acceptance definition
-> preflight and admission
-> lease and capability issuance
-> model-free or model-guided execution
-> immutable receipts and artifact hashes
-> validation
-> Main acceptance or rejection
-> canonical state and continuity update
-> telemetry and outcome record
-> later evaluation, repair proposal, or guarded promotion
```

No arrow may be replaced by “the model probably handled it.”

### 4.2 Six control planes

#### Plane 1 — Governance

Owns identity, mission, policy, human preferences, authority classes, stop lines, risk appetite, and exception rules.

#### Plane 2 — Truth

Owns canonical documents, databases, event ledgers, claims, decisions, provenance, source lineage, and supersession.

#### Plane 3 — Recall

Owns exact retrieval, full-text search, vector search, graphs, curated synthesis, context assembly, freshness, and degraded fallback.

#### Plane 4 — Execution

Owns workflows, routes, tools, skills, sandboxes, lanes, leases, schedules, checkpoints, retries, and transactional actions.

#### Plane 5 — Assurance

Owns validators, graders, security policy, observability, receipts, rollback, incident response, release gates, and final acceptance.

#### Plane 6 — Evolution

Owns evaluations, feedback, model and route reviews, improvement candidates, baseline comparisons, later outcomes, and retirement.

The assurance plane surrounds the other planes. The evolution plane may propose changes to any plane, but may not apply protected changes without the appropriate authority.

### 4.3 Stable interfaces: brain, hands, session, canon, and gate

A future-proof harness SHOULD separate five abstractions:

- **Brain:** model plus orchestration loop.
- **Hands:** tools and sandboxes that read or change the world.
- **Session:** durable append-only event stream for the logical run.
- **Canon:** authoritative state and policy.
- **Gate:** deterministic reference monitor that admits actions.

The brain MAY be replaced without losing the session.  
A hand MAY fail and be reprovisioned without granting the brain credentials.  
The session MAY outlive a context window or process.  
Canon MUST remain independently readable.  
The gate MUST remain outside model control.

This separation keeps model upgrades from rewriting the control system.

---

## 5. Logical roles and separation of duties

A small harness may implement several roles in one process, but the roles MUST remain logically distinct.

### 5.1 Owner

The Owner:

- sets mission and risk appetite;
- approves protected policies and actions;
- resolves authority ambiguity;
- grants or revokes capabilities;
- accepts high-impact residual risk;
- may override a block only through a recorded exception path.

### 5.2 Main integrator

Main:

- interprets the objective;
- selects sources;
- classifies authority and risk;
- chooses the execution route;
- freezes context for helpers;
- reconciles conflicting outputs;
- inspects validation;
- accepts or rejects completion;
- updates canonical queue and continuity;
- communicates the final judgment.

Main is accountable even when helpers perform most execution.

### 5.3 Planner

The Planner:

- decomposes work;
- defines dependencies;
- identifies ambiguity;
- sets acceptance criteria;
- proposes budgets and checkpoints;
- has no implied mutation authority.

For high-impact work, the Planner SHOULD be separate from the Executor.

### 5.4 Executor

The Executor:

- acts only inside the admitted scope;
- uses issued capabilities;
- records tool and mutation receipts;
- stops on scope drift;
- does not self-accept.

### 5.5 Verifier or critic

The Verifier:

- inspects source, output, environment state, and receipts;
- runs deterministic graders first;
- reports failures and uncertainty;
- cannot expand scope or authority;
- does not mutate the subject under review unless explicitly placed in a separate repair lane.

### 5.6 Observer

The Observer:

- collects metadata;
- records health, latency, cost, failure, and outcome signals;
- is read-only by default;
- cannot convert signals into actions;
- should fail open for response delivery but fail visible for audit completeness.

### 5.7 Scheduler

The Scheduler:

- triggers jobs;
- does not define truth or completion;
- records timing and dispatch;
- delegates semantic status to the job contract.

### 5.8 Separation rule

For shared, security-sensitive, privacy-sensitive, financial, external, or destructive changes:

```text
planner != sole executor != sole verifier != acceptance authority
```

The same human may fill multiple roles in a small system, but the records and decisions must remain separate.

---

## 6. Authority and autonomy model

### 6.1 Authority classes

| Class | Meaning | Default agent posture | Required controls |
|---|---|---|---|
| A0 | Inspect public or authorized read-only data | autonomous | source allowlist, logging |
| A1 | Compute, classify, summarize, or derive without mutation | autonomous | provenance, bounded outputs |
| A2 | Draft, recommend, plan, or propose | autonomous | explicit “proposal” state |
| A3 | Reversible local mutation in an isolated workspace | bounded autonomous | lease, snapshot, diff, validation, rollback |
| A4 | Shared internal mutation or canonical-state update | supervised | explicit capability, transactional write, acceptance |
| A5 | External communication or consequential action | approval required | human review, destination and payload preview, receipt |
| A6 | Destructive, financial, legal, account, credential, production, or high-impact action | explicit owner approval per action or tightly bounded policy | two-person or policy gate where appropriate, rollback/compensation, immutable audit |
| AX | Prohibited action | never | hard block |

A task MAY contain multiple authority classes. The highest required class governs each transition, not necessarily the entire task.

### 6.2 Capability token

A capability MUST be:

- unforgeable or integrity-protected;
- bound to `task_id`, `correlation_id`, and principal;
- limited to exact resources and operations;
- time-limited;
- non-transferable unless explicitly allowed;
- revocable;
- recorded before use;
- checked server-side;
- unusable by the model outside the gate.

Example:

```json
{
  "capability_id": "cap_01J...",
  "task_id": "task_01J...",
  "correlation_id": "trace_01J...",
  "principal": "executor:lane-7",
  "authority_class": "A3",
  "operations": ["write", "rename"],
  "resources": ["src/parser.py", "tests/test_parser.py"],
  "forbidden": [".env", ".git/**", "config/**"],
  "issued_at_utc": "2026-08-23T18:00:00Z",
  "expires_at_utc": "2026-08-23T19:00:00Z",
  "approval_id": null,
  "signature": "..."
}
```

### 6.3 Autonomy is not a global setting

Autonomy MUST be assigned per:

- task class;
- resource;
- action;
- environment;
- data sensitivity;
- risk level;
- freshness window;
- time horizon;
- model/harness version;
- evidence maturity.

“Auto-approve everything” is not an autonomy policy. It is removal of the policy boundary. Automatic guardrails and human review serve different roles: gates validate behavior, while approval decides whether a sensitive action may proceed. [R27]

### 6.4 Stop lines

The harness MUST stop when any of the following becomes true:

- requested action exceeds authority;
- source is stale or contradicted and freshness is material;
- write scope changes;
- an undeclared secret or sensitive field appears;
- prompt injection or tool poisoning is suspected;
- the active lease expires;
- an input fingerprint changes after planning;
- acceptance criteria become impossible or ambiguous;
- retry budget is exhausted;
- cost, time, token, or tool budget is exceeded;
- validator or gate output is malformed;
- the tool destination differs from the approved destination;
- rollback is unavailable for a change that requires it;
- the agent cannot distinguish data from instructions;
- the outcome cannot be verified.

Stopping is a successful safety behavior, not a failure of helpfulness.

---

## 7. Truth architecture

### 7.1 Evidence classes

| Rank | Evidence class | Examples | Authority |
|---:|---|---|---|
| 1 | Owner doctrine and protected policy | governance files, signed policy, human approval record | defines rules and authority |
| 2 | Canonical current state | guarded SQLite rows, workflow queue, approved registry | owns current operational truth |
| 3 | Primary source evidence | source documents, API responses, repositories, external official records | establishes factual content |
| 4 | Verified receipt or attestation | command result, artifact hash, signed event, environment outcome | proves an execution claim |
| 5 | Derived routing or synthesis | indexes, graphs, wiki, status cards, summaries | accelerates lookup only |
| 6 | Model inference | analysis, hypothesis, recommendation | never self-proving |

A lower-ranked item may be more recent, but it does not automatically gain authority. The harness must reconcile rank, freshness, scope, and ownership.

### 7.2 Single-owner rule

Every important instruction or state field MUST have one owner.

When duplication is found:

1. identify the owner;
2. compare the copies;
3. resolve conflict explicitly;
4. retain the owner;
5. replace other copies with pointers or derived views;
6. add a drift test if recurrence is likely.

Duplication is not redundancy when the copies can diverge. It is competing truth.

### 7.3 Format-by-purpose rule

Use each format for the job it performs best.

- **Markdown:** doctrine, rationale, human decisions, runbooks, narrative continuity.
- **SQLite or equivalent transactional store:** current state, registries, joins, claims, tasks, runs, leases, provenance.
- **JSON:** typed packets, receipts, interchange, cached control views.
- **JSONL or append-only event table:** chronological history.
- **Git:** versioned human-meaningful source and code.
- **Content-addressed artifact store:** immutable outputs, archives, receipts, large evidence.
- **Vector/full-text/graph indexes:** derived recall.
- **Secrets vault:** credentials and tokens; never ordinary files or context.

### 7.4 Canonical database gateway

No harness component SHOULD open the canonical database directly.

A single access layer SHOULD enforce:

- foreign keys on every connection;
- transactions for every write;
- immutable primary identifiers and creation timestamps;
- UTC timestamps;
- provenance on writes;
- duplicate rejection instead of silent overwrite;
- prior-version snapshot on update;
- append-only events;
- read-only observer mode;
- integrity checks;
- schema migrations;
- replay/idempotency keys;
- explicit serialization of concurrent writers.

For SQLite, WAL can improve reader/writer concurrency, but durability settings must match the risk model. Multi-file atomicity assumptions must be explicit.

### 7.5 Claim records

Material claims SHOULD be stored as first-class records.

```json
{
  "claim_id": "claim_01J...",
  "subject": "routing-index",
  "predicate": "freshness_state",
  "value": "fresh",
  "claim_type": "verified",
  "source_refs": [
    {
      "source_id": "artifact_01J...",
      "path": "state/workflow-routing-index.json",
      "sha256": "...",
      "line_range": null
    }
  ],
  "observed_at_utc": "2026-08-23T18:10:00Z",
  "valid_until_utc": "2026-08-23T19:10:00Z",
  "owner": "routing-control-plane",
  "supersedes": ["claim_older"],
  "conflicts_with": [],
  "confidence": 1.0,
  "status": "active"
}
```

### 7.6 Contradiction and supersession

The harness MUST support:

- `supersedes`;
- `superseded_by`;
- `conflicts_with`;
- `derived_from`;
- `invalidates`;
- `valid_from`;
- `valid_until`;
- owner resolution state.

Retrieval SHOULD downrank superseded claims while preserving historical access.

### 7.7 Generated proof is not authority

A generated packet may be structurally valid while truthfully reporting a blocked or failed system. Therefore:

```text
packet_valid == true
does not imply
system_healthy == true
does not imply
action_authorized == true
```

This distinction MUST appear in status schemas and UI.

---

## 8. Bootstrap and startup

### 8.1 Lean bootstrap

The bootstrap SHOULD be small enough to load on every session without context obesity.

Recommended files:

```text
AGENT.md        identity, mission, behavior, pointers
GOVERNANCE.md   single-owner, authority, change placement, stop lines
USER.md         operator preferences, timezone, communication, approval style
TOOLS.md        runtime map, platform facts, tool and mutation rules
STARTUP.md      exact startup sequence and drilldown map
```

The bootstrap MUST contain policy and pointers, not every procedure.

Procedures belong in skills or runbooks.  
Current state belongs in canonical storage.  
Generated summaries belong in derived artifacts.  
Secrets belong nowhere in the bootstrap.

### 8.2 Deterministic startup brief

Every session SHOULD begin with one model-free status command that emits a bounded machine-readable brief.

Minimum fields:

```json
{
  "schema": "harness.startup_brief.v1",
  "generated_at_utc": "...",
  "workspace_version": "...",
  "canonical_integrity": "ok",
  "active_workflows": 3,
  "active_write_lanes": 0,
  "expired_leases": 0,
  "routing_freshness": "fresh",
  "retrieval_status": {
    "exact": "ok",
    "graph": "ok",
    "vector": "degraded"
  },
  "scheduler_status": "healthy_with_warnings",
  "hard_blocks": [],
  "warnings": ["vector_provider_unavailable"],
  "recommended_next_action": "resume:WF-1000"
}
```

The startup brief is a routing surface. Material work MUST drill into canonical owners.

### 8.3 Startup order

```text
load protected governance
-> run deterministic status brief
-> read active workflow or task capsule
-> retrieve recent continuity
-> resolve exact owners
-> load only the procedures and context required
```

A session MUST NOT scan the whole workspace to “understand everything.”

### 8.4 Context budget

Set an explicit default budget. A practical initial cap for a helper packet is:

- no more than six source files;
- no more than 120 KB raw text;
- approximately 30,000 tokens;
- sorted source hashes;
- one base path;
- one snapshot identifier.

These are starting defaults, not universal limits. The harness should tune them with measured outcome data.

---

## 9. Task intake contract

Every material request MUST become a typed task contract before action.

### 9.1 Required fields

```json
{
  "schema": "harness.task.v1",
  "task_id": "task_01J...",
  "correlation_id": "trace_01J...",
  "requested_by": "user",
  "objective": "Repair the parser and preserve behavior",
  "interpretation": "Fix only the failing CSV quote path",
  "non_goals": [
    "No parser rewrite",
    "No dependency changes"
  ],
  "authority_class": "A3",
  "risk_class": "narrow",
  "source_owners": [
    "src/parser.py",
    "tests/test_parser.py"
  ],
  "allowed_reads": ["src/parser.py", "tests/test_parser.py"],
  "allowed_writes": ["src/parser.py", "tests/test_parser.py"],
  "forbidden_writes": [".env", "config/**", "canonical/**"],
  "freshness_requirements": [],
  "acceptance": [
    {
      "type": "command",
      "argv": ["uv", "run", "--with", "pytest", "python", "-m", "pytest", "tests/test_parser.py", "-q"]
    }
  ],
  "stop_lines": [
    "scope_expansion",
    "dependency_change_required",
    "protected_surface_needed"
  ],
  "budgets": {
    "wall_clock_s": 1800,
    "model_calls": 20,
    "tool_calls": 100,
    "input_tokens": 150000,
    "output_tokens": 30000
  },
  "idempotency_key": "task_01J...:v1",
  "rollback_required": true,
  "response_contract": "conclusion_evidence_uncertainty_next_action"
}
```

### 9.2 Ambiguity handling

The harness SHOULD ask a clarifying question only when ambiguity blocks a safe and materially correct interpretation.

Otherwise it SHOULD:

1. state the bounded interpretation;
2. state non-goals;
3. choose the lowest authority route;
4. proceed within that scope;
5. stop if later evidence invalidates the interpretation.

### 9.3 Acceptance before execution

Acceptance criteria MUST be defined before mutation.

Bad:

> “Improve the system.”

Good:

> “Reduce p95 retrieval latency below 250 ms on the frozen 200-query set, preserve citation precision above 98%, produce no stale uncaveated result, and pass the existing security suite.”

### 9.4 Risk classes

| Risk | Typical scope | Minimum assurance |
|---|---|---|
| micro | one local artifact, reversible | deterministic check plus Main inspection |
| narrow | bounded component | focused tests plus diff review |
| shared | shared contract or multiple consumers | dependency-aware suite plus independent QA |
| sensitive | security, privacy, credentials, authority, money, production | threat review, independent QA, approval, rollback, audit |
| systemic | control-plane or policy change | staged rollout, canary, chaos/recovery proof, owner acceptance |

---

## 10. Route selection

### 10.1 Route order

The default route is:

1. exact deterministic command or query;
2. cached deterministic result whose signatures are current;
3. bounded workflow with predefined code paths;
4. single agent with narrow tools and explicit stop condition;
5. manager agent using specialists as tools;
6. multi-agent handoff or parallel swarm only with proven need;
7. blocked if source, authority, environment, or proof is missing.

There is no silent fallback to a more powerful, more expensive, or more privileged route.

### 10.2 Workflow versus agent

Use a **workflow** when the path is known and consistency matters.

Use an **agent** when:

- the path cannot be fully predefined;
- intermediate evidence changes the plan;
- tool selection requires semantic judgment;
- exception handling is open-ended;
- the expected value of flexibility exceeds latency, cost, and risk.

A single model call with retrieval is often better than an agent.  
A workflow is often better than a free-running agent.  
A single agent is often better than a swarm.

Current agent SDKs expose loops, tools, handoffs, sessions, tracing, guardrails, and resumable approvals, but those features still require the application to own storage, tool behavior, and approval decisions deliberately. [R8]

### 10.3 Model-free first

Examples of model-free routes:

- SQL lookup;
- exact file or section retrieval;
- schema validation;
- source-hash freshness;
- dependency traversal;
- artifact lookup;
- diff generation;
- test selection;
- cron health;
- lease collision detection;
- integrity check;
- route lookup;
- cache validation.

The model SHOULD receive the result, not repeat the computation.

### 10.4 Model routing

Model selection SHOULD consider:

- task complexity;
- ambiguity;
- tool-use reliability;
- required context;
- latency;
- cost;
- privacy;
- local availability;
- failure history;
- accepted outcome cohort.

A smaller model MAY replace a larger one only after like-for-like accepted evidence. A larger model MAY be used for planning, integration, or difficult repair while deterministic and smaller-model routes handle routine steps.

### 10.5 Route receipt

Every material route decision SHOULD record:

```json
{
  "route_policy_version": "v1.3",
  "selected_route": "single_agent_bounded",
  "model": "provider/model-id",
  "reason": "semantic repair judgment required",
  "alternatives_rejected": {
    "model_free": "no deterministic repair command",
    "multi_agent": "single artifact; coordination cost unjustified"
  },
  "authority_class": "A3",
  "context_snapshot": "ctx_01J...",
  "budget_id": "budget_01J..."
}
```

---

## 11. Memory and retrieval

### 11.1 Memory tiers

A robust stack SHOULD separate:

| Tier | Store | Best use |
|---|---|---|
| 0 | current session state | immediate dialogue and in-flight decisions |
| 1 | canonical SQL/state | exact IDs, status, ownership, current facts |
| 2 | exact source retrieval | paths, headings, phrases, dates, citations |
| 3 | graph | ownership, dependencies, impact, lineage, supersession |
| 4 | vector/hybrid index | paraphrase, conceptual recall, unknown wording |
| 5 | curated wiki/derived synthesis | cold orientation and source maps |
| 6 | chronological memory and archived session events | continuity and historical reconstruction |

No tier replaces another.

### 11.2 Retrieval decision procedure

```text
exact ID, path, date, status, or known owner
-> SQL or exact retrieval

relationship, dependency, impact, lineage, or supersession
-> graph

unknown wording, prior decision, concept, or paraphrase
-> vector or hybrid retrieval

cold project orientation
-> curated synthesis
-> owner source

every consequential result
-> open source
-> verify live hash and freshness
-> cite bounded excerpt
```

Closing rule:

> SQL finds exact structure. Graph finds relationships. Vector retrieval finds meaning. The source record establishes truth.

### 11.3 Approved source registry

Indexes MUST be built from an approved source registry, not arbitrary recursive scans.

Registry fields SHOULD include:

```json
{
  "source_path": "governance/authority.md",
  "source_family": "governance",
  "authority_class": "owner_doctrine",
  "source_type": "markdown",
  "chunking": "heading_sections",
  "sensitivity": "internal",
  "retention": "durable",
  "index_modes": ["full_text", "vector", "graph"],
  "exclude_patterns": []
}
```

Absolute-path traversal, parent traversal, secrets, credential stores, transient runtime data, and unauthorized directories MUST be rejected.

### 11.4 Section-scoped retrieval

Markdown and long text SHOULD be indexed by non-overlapping semantic sections.

Each section SHOULD preserve:

- source path;
- absolute line range;
- heading breadcrumb;
- section identifier;
- section hash;
- source hash;
- authority class;
- source family;
- retrieval mode;
- score;
- freshness;
- warnings.

Dedupe hybrid results by `(source_path, section_id)`.

### 11.5 Freshness

At query time, compare the live source hash with the indexed source hash.

States:

- `fresh`;
- `aging`;
- `stale`;
- `superseded`;
- `missing`;
- `unverifiable`.

Stale and superseded results SHOULD be quarantined from default answers. If returned for historical reasons, they MUST be labeled.

### 11.6 Degraded retrieval

If embeddings, graph traversal, or a corpus times out:

- return healthy corpus results;
- label each corpus status;
- fall back to exact full-text or local cache;
- do not silently call degraded output semantic output;
- preserve citations;
- expose the missing capability.

One failed corpus MUST NOT suppress healthy evidence from another.

### 11.7 Memory write policy

Memory writes MUST be intentional.

- Chronological events go to daily or event history.
- Durable policy requires explicit promotion.
- Decisions require source and owner.
- Preferences require provenance and expiry where appropriate.
- Model reflections are candidates, not durable truth.
- Raw chat is not canon.
- Summaries must point to source events.
- Sensitive data requires a separate retention policy.

### 11.8 Reflection memory

Research such as Reflexion shows that linguistic feedback can improve later attempts, but reflection memory can also preserve wrong explanations. Therefore:

- reflections MUST be tied to observed outcomes;
- failed hypotheses MUST remain distinguishable from accepted lessons;
- reflection SHOULD expire or be revalidated;
- reflection MUST NOT change authority;
- promotion to durable guidance requires evaluation.

### 11.9 Retrieval service objectives

Recommended targets:

- memory-only success: at least 99%;
- all-corpus partial-or-better success: at least 95%;
- citation correctness on frozen set: at least 98%;
- uncaveated stale results: zero;
- p95 exact retrieval: locally appropriate and measured;
- p95 hybrid retrieval: measured against task value, not vanity;
- automatic fallback: 100% for supported failure classes.

---

## 12. Context engineering

### 12.1 Context is a scarce resource

A larger context window does not remove the need for selection. Long context can dilute attention, increase cost, reduce cache efficiency, and expose more untrusted data.

The context objective is:

> Provide the smallest high-signal set of tokens that is sufficient for the current decision.

### 12.2 Context layers

Assemble context in this order:

1. protected system and governance;
2. task contract;
3. current workflow or phase;
4. exact source excerpts;
5. relevant tool schemas;
6. recent bounded events;
7. optional examples;
8. model-generated scratch state that is safe to retain.

### 12.3 Just-in-time retrieval

The agent SHOULD retrieve context when it becomes necessary rather than preloading every possible source.

Tools should return:

- bounded records;
- precise errors;
- line ranges;
- hashes;
- next-page or next-read tokens;
- summaries only when the raw bounded source is also reachable.

### 12.4 Session versus context window

The durable session is not the model context window.

The session SHOULD preserve an append-only event log outside the model. The harness MAY select, slice, compact, summarize, or transform events before passing them into a new context window.

Compaction is a convenience, not a source of truth. Raw events and artifacts must remain recoverable according to retention policy.

### 12.5 Pickup packet

A pickup packet SHOULD contain only:

- objective;
- authority class;
- task and workflow IDs;
- plan pointer and hash;
- current phase;
- accepted phase summaries;
- unresolved blockers;
- exact allowed writes;
- acceptance commands;
- source snapshot;
- next action;
- stop lines;
- receipt pointers.

It SHOULD exclude full transcripts and large raw tool output.

### 12.6 Context snapshot

Material helper work SHOULD receive a frozen context manifest:

```json
{
  "context_snapshot_id": "ctx_01J...",
  "created_at_utc": "...",
  "base_path": "...",
  "sources": [
    {"path": "src/parser.py", "sha256": "...", "bytes": 21940},
    {"path": "tests/test_parser.py", "sha256": "...", "bytes": 8840}
  ],
  "total_bytes": 30780,
  "estimated_tokens": 7700,
  "policy_version": "gov-4.2",
  "task_contract_sha256": "...",
  "fresh_until_utc": "..."
}
```

If an input changes materially, replan or explicitly rebase.

### 12.7 Context cache correctness

Cache keys MUST include all variables that can change the answer:

- source signatures;
- policy version;
- task class;
- user/tenant;
- time bucket;
- market or business date where relevant;
- model/harness version if output is model-derived;
- tool schema version;
- retrieval mode;
- permission scope.

A cache hit without a complete signature is an unverified guess.

---

## 13. Tool and agent-computer interface design

### 13.1 Tools are contracts

A tool is not merely a function. It is the boundary between probabilistic planning and real-world effects.

Each tool MUST declare:

- exact purpose;
- input schema;
- output schema;
- read/write/destructive classification;
- required authority;
- allowed resources;
- timeout;
- retry semantics;
- idempotency behavior;
- error taxonomy;
- data sensitivity;
- network behavior;
- approval requirement;
- audit fields.

### 13.2 Minimal viable tool set

Tools SHOULD be:

- narrow;
- non-overlapping;
- self-contained;
- easy to distinguish;
- deterministic where possible;
- concise in output;
- robust to malformed input;
- explicit about side effects.

If a human cannot tell which of two tools should be used, the agent will not reliably do better.

### 13.3 Prefer purpose-built interfaces

Research on agent-computer interfaces shows that interface design materially affects agent performance. [R23] Prefer:

- `read_file(path, start_line, end_line)` over an unrestricted shell;
- `apply_patch(paths, diff_hash)` over arbitrary text replacement;
- `run_validator(bundle_id)` over ad hoc test discovery;
- `query_state(table, filters)` over free-form SQL for ordinary use;
- `send_message(draft_id, approval_id)` over generic HTTP.

A general shell MAY remain available in isolated engineering sandboxes, but it SHOULD not be the default control surface for high-impact actions.

### 13.4 Command execution

Acceptance and protected commands MUST use typed argv.

```json
{
  "argv": ["uv", "run", "--with", "pytest", "python", "-m", "pytest", "tests/test_parser.py", "-q"],
  "cwd": "/workspace/project",
  "env_allowlist": ["PATH", "PYTHONUTF8"],
  "timeout_s": 180,
  "network": "denied"
}
```

Reject bare interpreter assumptions when environment drift is likely. Pin the interpreter or runner.

### 13.5 Tool-result trust

Tool output is data. It may contain:

- prompt injection;
- malicious markup;
- poisoned metadata;
- false claims;
- hidden instructions;
- credentials;
- adversarial filenames;
- oversized payloads.

The harness MUST label tool output by origin and MUST NOT allow it to override governance or task instructions.

### 13.6 Output bounds

Every tool SHOULD cap:

- rows;
- bytes;
- lines;
- execution time;
- recursive depth;
- file count;
- graph expansion;
- retries.

Tools SHOULD support pagination or continuation tokens instead of dumping entire stores into context.

### 13.7 MCP posture

MCP can standardize access to data and tools, but protocol compatibility is not security approval. Its current specification and security guidance treat authorization, server trust, and confused-deputy risks as separate implementation concerns. [R21][R29]

MCP integrations MUST:

- use supported authorization flows;
- validate server identity and metadata;
- minimize scopes;
- distinguish read, write, and destructive tools;
- keep approvals for consequential actions;
- treat remote tool descriptions and results as untrusted;
- prevent confused-deputy data flows;
- retain audit and correlation identifiers;
- avoid exposing vault credentials to the model or sandbox;
- maintain an allowlist and revocation path.

### 13.8 Tool change governance

A tool schema change can alter agent behavior as much as a prompt change. Therefore it MUST receive:

- versioning;
- consumer impact analysis;
- regression tests;
- security review when authority changes;
- staged rollout;
- rollback.



## 14. Execution engine

### 14.1 Execution is a state machine

Material work MUST execute through an explicit state machine rather than an unconstrained conversational loop. Interleaving reasoning with evidence-producing actions can improve grounded task solving, but the surrounding state machine—not the model’s private reasoning—must own transitions and effects. [R22]

```text
intake
-> classified
-> planned
-> context_frozen
-> admitted
-> leased
-> executing
-> validating
-> awaiting_acceptance
-> accepted
-> observed
-> closed
```

Permitted terminal and interruption states:

```text
blocked
failed_retryable
failed_terminal
cancelled
expired
rolled_back
superseded
```

Every transition MUST be:

- legal from the current state;
- recorded with UTC time;
- associated with an actor identity;
- associated with one correlation ID;
- justified by a typed reason;
- idempotent or protected by an idempotency key;
- rejected when a prerequisite is absent.

Prose such as “done,” “finished,” or “looks good” MUST NOT alter state.

### 14.2 Plan contract

A material plan MUST define:

```yaml
plan_id: UUID
task_id: UUID
workflow_id: string
plan_version: integer
plan_sha256: hex
objective: string
assumptions:
  - statement
phases:
  - phase_id: P0
    goal: string
    depends_on: []
    allowed_reads: []
    allowed_writes: []
    tool_capabilities: []
    acceptance_commands: []
    rollback: string
budgets:
  model_turns: integer
  tool_calls: integer
  elapsed_seconds: integer
  context_tokens: integer
  spend_usd: number|null
stop_lines: []
```

The plan hash MUST be pinned before execution. A material plan change creates a new plan version and requires re-admission when it changes scope, writes, authority, risk, or acceptance.

### 14.3 Phase discipline

A phase MUST be small enough to:

- have one principal result;
- have bounded writes;
- have a specific validator;
- be resumed without replaying the entire task;
- be rolled back or compensated independently where practical.

A phase MUST NOT begin until its declared dependencies are accepted.

The harness SHOULD prefer several independently verifiable phases over one broad opaque run. This reduces replay cost and confines failure.

### 14.4 Planner constraints

The planner MAY choose methods. It MUST NOT:

- grant capabilities;
- waive validation;
- alter authority class;
- redefine the user’s objective;
- convert uncertainty into fact;
- declare its own plan accepted;
- insert undeclared high-impact work as a convenience.

Planning is advisory until the control plane validates the plan contract.

### 14.5 Executor constraints

The executor receives only:

- the accepted phase goal;
- the frozen context manifest;
- required inputs;
- explicit capabilities;
- allowed paths;
- resource budgets;
- acceptance criteria;
- stop lines;
- the exact next transition it may request.

The executor MUST NOT inherit the planner’s broader context or credentials by default.

### 14.6 Critic constraints

A critic or verifier MAY:

- inspect evidence;
- challenge assumptions;
- run authorized read-only validators;
- identify missing proof;
- recommend rejection or rework.

It MUST NOT:

- rewrite the artifact it grades unless a separate repair lane is admitted;
- silently broaden tests;
- approve authority;
- alter canonical state;
- mark acceptance.

The critic is a source of assurance, not the Acceptance Authority.

### 14.7 Bounded iteration

Agent loops MUST have explicit limits:

- maximum model turns;
- maximum tool calls;
- maximum retries by failure class;
- maximum wall-clock time;
- maximum token and spend budgets;
- maximum repeated action signatures;
- maximum no-progress cycles.

A no-progress detector SHOULD compare:

- artifact hashes;
- state transitions;
- new evidence count;
- unresolved blocker count;
- repeated tool call signatures;
- repeated model conclusions.

When the loop consumes effort without changing evidence or state, it MUST stop and produce a blocker packet.

### 14.8 Failure classification

A failed attempt MUST be classified before retry:

| Class | Meaning | Default behavior |
|---|---|---|
| `input_invalid` | Required input malformed or absent | Stop; request or repair input |
| `authority_missing` | Capability or approval absent | Stop; never retry automatically |
| `dependency_blocked` | Upstream state unavailable | Wait or route to upstream owner |
| `transient_provider` | Temporary network/provider fault | Bounded backoff retry |
| `rate_limited` | Quota or rate bound reached | Respect reset; do not thrash |
| `tool_contract` | Tool schema or output invalid | Stop or use declared fallback |
| `environment_drift` | Runtime differs from pinned contract | Rebuild or re-admit |
| `validation_failed` | Result does not satisfy proof | Repair within scope or return |
| `collision` | Another writer owns overlapping scope | Wait, replan, or cancel |
| `prompt_injection` | Untrusted data attempted instruction control | Quarantine and escalate |
| `security_violation` | Sandbox, secret, or access rule violated | Terminate and investigate |
| `unknown` | Not safely classified | Fail closed |

Retries MUST NOT be credited as first-pass success.

### 14.9 Durable execution

Long-running execution MUST persist sufficient event history and checkpoints to recover after:

- model timeout;
- process crash;
- machine restart;
- provider outage;
- context compaction;
- operator pause;
- helper termination.

The replayable control logic MUST be deterministic with respect to recorded inputs and events. Side-effecting activities MUST be separated from replayable workflow decisions and made idempotent wherever possible. This is consistent with established durable-execution practice: deterministic workflow replay reconstructs decisions from history, while retried activities require idempotency to avoid duplicate effects. [R17][R18]

### 14.10 Event history

A workflow event SHOULD contain:

```json
{
  "event_id": "uuid",
  "correlation_id": "uuid",
  "workflow_id": "WF-001",
  "task_id": "uuid",
  "phase_id": "P2",
  "attempt": 2,
  "event_type": "validator.completed",
  "actor": "validator:python-tests",
  "occurred_at_utc": "2026-08-23T18:00:00Z",
  "input_hash": "sha256:...",
  "output_hash": "sha256:...",
  "status": "failed",
  "reason_code": "validation_failed",
  "metadata": {}
}
```

Event history MUST be append-only. Corrections append a superseding event; they do not rewrite history.

---

## 15. Concurrency, lanes, and leases

### 15.1 Lane as the unit of controlled concurrency

A lane is a bounded grant to perform one work chunk. Every material helper or concurrent executor MUST operate inside a lane.

A lane MUST declare:

```yaml
lane_id: UUID
parent_job_id: UUID
workflow_id: string
workstream: string
owner_actor: string
state: planned
lease:
  issued_at_utc: timestamp|null
  expires_at_utc: timestamp|null
allowed_reads: []
allowed_writes: []
forbidden_writes: []
capabilities: []
context_snapshot_id: string
plan_sha256: hex
attempt: 1
retry_of: null
acceptance_bundle_id: string
proof_artifacts: []
```

### 15.2 Lane state machine

```text
planned -> leased -> running -> complete
                         |-> blocked
                         |-> cancelled
                         |-> expired
```

A blocked lane MAY return to `planned` only through an explicit recovery transition.

A completed lane is immutable except for later audit, archival, or approved tombstoning.

### 15.3 Collision policy

At plan time and again at lease time, the control plane MUST detect overlapping writes, including:

- identical paths;
- parent/child path overlap;
- resolved symlink overlap;
- case-insensitive collisions on relevant filesystems;
- generated consumer overlap;
- canonical record overlap even when files differ.

An overlap between two active writers is a hard block, not a warning.

Read/read overlap is normally safe. Read/write overlap MAY proceed only when the reader is declared snapshot-consistent or the writer cannot invalidate its proof.

### 15.4 Protected surfaces

The following SHOULD be denied to ordinary lanes by default:

- credentials and secret stores;
- governance and authority owners;
- runtime policy;
- canonical schema;
- migration registry;
- lane register;
- approval records;
- production configuration;
- audit ledgers;
- release signing keys;
- live financial or external-action surfaces.

Access requires an explicit higher-authority lane with independent validation.

### 15.5 Finite leases

Every write lease MUST expire.

The harness MUST:

- reject expired leases;
- detect abandoned running lanes;
- prevent silent lease renewal;
- require fresh collision checks on renewal;
- record the reason and actor for renewal;
- notify the authority owner when repeated expiry indicates unhealthy work decomposition.

A lease is authority for the declared scope and duration only. It is not ownership of the workflow.

### 15.6 Completion proof

A lane MUST NOT complete without:

- the expected artifact or typed no-artifact outcome;
- proof paths that resolve;
- content hashes;
- validator results;
- source snapshot identity;
- a terminal receipt;
- no active write process remaining;
- release of the lease.

A plausible-looking path, model statement, or exit-code assertion is not proof.

### 15.7 Test gating during writes

Correctness proofs MUST NOT be computed over a changing source tree unless the proof explicitly targets a transactional snapshot.

When an active write lane overlaps the test surface, the test gate SHOULD:

- defer;
- name the blocking lane;
- or test an immutable snapshot.

A “green” result against a half-written tree is a false proof.

### 15.8 Helper isolation

Each helper SHOULD receive:

- one primary deliverable;
- one lane;
- one context snapshot;
- the minimum tool set;
- exact write bounds;
- exact proof requirements.

Do not bundle broad research, implementation, QA, documentation, queue mutation, and final synthesis into one helper lane. That creates ambiguous ownership and poor recovery.

---

## 16. Transactional mutation and rollback

### 16.1 The mutation protocol

Every consequential local mutation MUST follow:

```text
propose
-> classify
-> preview
-> acquire capability
-> acquire lease
-> snapshot
-> apply
-> validate
-> compare
-> accept or compensate
-> emit receipt
```

For high-impact external actions, insert explicit human approval immediately before the irreversible boundary.

### 16.2 Write admission

Before a write, the admission gate MUST verify:

- current route is fresh;
- task and workflow are executable;
- authority class permits the action;
- capability token is valid;
- actor identity matches the token;
- lane is active and unexpired;
- target is allowed and not forbidden;
- input and plan hashes match;
- prerequisite phases are accepted;
- rollback or compensation exists where required;
- resource budgets remain;
- no collision exists.

The gate MUST be read-only. It MUST NOT repair its own prerequisites while deciding whether a write is safe.

### 16.3 Idempotency

Every retryable side effect MUST use an idempotency key derived from stable business inputs, not from the current attempt.

Examples:

```text
create-report:{workflow_id}:{source_fingerprint}:{report_version}
send-draft:{message_digest}:{recipient_id}:{approval_id}
apply-migration:{database_id}:{migration_version}
refresh-index:{registry_hash}:{embedding_model}:{chunking_version}
```

A repeated key MUST:

- return the prior accepted result;
- or prove that no prior side effect occurred;
- or fail visibly when the prior payload conflicts.

It MUST NOT create a duplicate.

### 16.4 Optimistic and pessimistic controls

Use pessimistic locking or leases when:

- concurrent writes are likely;
- collision cost is high;
- scope is narrow and known.

Use optimistic checks when:

- contention is low;
- immutable snapshots exist;
- a compare-and-swap or version field can reject drift.

For canonical records, updates SHOULD require an expected version or source hash.

### 16.5 Before-and-after fingerprints

Acceptance of a code, configuration, index, or document transformation SHOULD record:

- source file count;
- ordered path list hash;
- content fingerprint;
- dependency-lock hash;
- environment identity;
- test input fingerprint;
- before and after timestamps.

The harness MUST distinguish:

1. intended artifact changes;
2. unrelated source drift during validation;
3. generated changes;
4. runtime/environment drift.

Validation is invalid when the source changed outside the admitted mutation between test start and test finish.

### 16.6 Rollback and compensation

Rollback MUST be designed before activation.

Use:

- exact file restore for local reversible writes;
- database transaction rollback before commit;
- inverse migration only when proven safe;
- versioned release rollback;
- compensating action for external side effects;
- quarantine and manual resolution when no safe inverse exists.

A compensation is not the same as erasing history. Both the original effect and the compensation MUST remain auditable.

### 16.7 Two-phase high-impact action

For irreversible or externally consequential action:

```text
prepare
-> render exact action
-> validate inputs
-> human approves exact digest
-> recheck freshness and authority
-> commit once
-> verify external outcome
-> record receipt
```

Approval MUST bind to:

- action type;
- target;
- payload digest;
- scope;
- maximum amount or impact;
- expiration;
- requesting actor.

Any material payload change invalidates approval.

### 16.8 Tombstones and archives

When proof artifacts are retired, the harness MUST retain one of:

- the live artifact;
- an immutable archive manifest and content hash;
- an approved tombstone naming what was removed, why, by whom, and under which retention rule.

Deleting evidence without lineage corrupts the ability to verify earlier acceptance.

---

## 17. Sandbox, identity, and agent security

### 17.1 Separate harness from compute

The trusted harness control plane SHOULD run outside model-directed compute.

The harness owns:

- orchestration;
- task and run state;
- identity;
- capabilities;
- approvals;
- audit;
- model routing;
- recovery;
- secret brokering;
- acceptance.

The sandbox owns:

- model-directed file operations;
- commands;
- packages;
- temporary processes;
- bounded network use;
- disposable execution state.

This boundary keeps trusted policy and credentials outside the environment that the model can manipulate. Current agent-platform guidance likewise treats the harness as the control plane and the sandbox as the execution plane. [R9]

### 17.2 Read-only by default

A new executor starts with:

- no network;
- no secrets;
- read-only filesystem;
- no host process access;
- no production tokens;
- no control-plane database write;
- strict CPU, memory, disk, process, and time ceilings.

Capabilities are added explicitly per lane.

### 17.3 Agent identity

Every model run, helper, tool proxy, scheduler, and human operator MUST have a durable actor identity.

Identity MUST be distinct from:

- model name;
- session ID;
- lane ID;
- API credential;
- user identity;
- service account.

The authorization check SHOULD evaluate the full tuple:

```text
principal
+ delegated user
+ task
+ workflow
+ lane
+ capability
+ target
+ time window
+ approval
```

NIST’s current agent identity work emphasizes identification, authentication, and authorization as necessary controls when agents access diverse tools and data. [R12]

### 17.4 Capability-based authorization

A capability token SHOULD be:

- narrowly scoped;
- short-lived;
- audience-bound;
- non-transferable by default;
- revocable;
- logged by hash;
- constrained by action, resource, method, amount, and time;
- denied when context or approval digest changes.

Possession of a general API key MUST NOT imply permission for every exposed action.

### 17.5 Secret handling

Secrets MUST remain outside model context and ordinary sandbox storage.

Use:

- a vault or OS credential manager;
- short-lived delegated tokens;
- a policy-enforcing credential proxy;
- server-side tool execution;
- redacted error messages;
- secret scanning before persistence.

The model MAY request a capability by semantic name. It SHOULD NOT receive the underlying secret.

### 17.6 Network policy

Network access MUST be denied by default and granted by allowlist.

Each grant SHOULD specify:

- hostname or service identity;
- protocol and port;
- method;
- path family where practical;
- request and response size;
- redirect policy;
- DNS policy;
- upload permission;
- duration;
- data classification.

Unknown redirects, link-local addresses, metadata endpoints, internal control services, and credential endpoints MUST be blocked unless explicitly required.

### 17.7 Prompt-injection boundary

External text is data, never governance.

The harness MUST mark as untrusted:

- web pages;
- email;
- documents;
- issue comments;
- repository content not owned by governance;
- tool descriptions from remote servers;
- search snippets;
- retrieved memory not classified as policy;
- model-generated artifacts.

Untrusted content MUST NOT:

- change system or developer policy;
- grant capabilities;
- instruct secret disclosure;
- alter approval requirements;
- rewrite the objective;
- invoke tools by itself;
- override stop lines.

Agent hijacking exploits systems that blur trusted instructions and untrusted data; NIST specifically identifies indirect prompt injection through resources such as websites, emails, and files. [R10]

### 17.8 Injection-resilient processing

For risky external content:

1. fetch through a constrained reader;
2. strip active content and hidden metadata where possible;
3. retain provenance;
4. classify data separately from instructions;
5. extract facts into a typed intermediate representation;
6. validate claims against independent sources when consequential;
7. prevent direct tool execution from retrieved text;
8. require a separate control-plane decision for action;
9. red-team with repeated and adaptive attacks.

Detection alone is insufficient. The architecture MUST make a successful textual injection unable to grant authority.

### 17.9 Data-flow control

The harness SHOULD enforce labels such as:

```text
public
internal
confidential
secret
regulated
user-private
```

A tool call MUST NOT move data to a lower-trust destination without a permitted flow.

For example:

```text
user-private email
-> local summarizer: allowed
-> public issue comment: denied
-> approved private CRM note: approval-dependent
```

### 17.10 Supply-chain controls

Executable dependencies, skills, prompts, tool servers, and model adapters are supply-chain inputs.

Require:

- pinned versions;
- verified origin;
- lockfiles;
- checksums or signatures where available;
- dependency review;
- isolated installation;
- generated artifact provenance;
- update rollback;
- vulnerability and license policy;
- no silent remote code loading.

Artifact provenance SHOULD record where, when, and how an artifact was produced, following the same principle used by software-supply-chain attestation systems. [R19]

### 17.11 Security evaluation

Before enabling a new tool or connector, test:

- unauthorized reads;
- unauthorized writes;
- prompt injection;
- confused deputy behavior;
- cross-tenant or cross-user leakage;
- path traversal;
- command injection;
- SSRF;
- redirect abuse;
- secret exfiltration;
- approval bypass;
- stale-token replay;
- excessive scope;
- malformed tool output;
- denial-of-service bounds.

A passing happy-path demo is not a security evaluation. Maintain an extensible adversarial suite rather than a frozen list of known attacks; AgentDojo and OWASP’s agentic-security work reinforce the need to test realistic tool tasks, prompt injection, and evolving attack classes. [R25][R26]

---

## 18. Scheduled automation

### 18.1 Deterministic hygiene only

Recurring hygiene SHOULD be model-free.

Examples:

- status generation;
- integrity checks;
- index refresh;
- freshness checks;
- lease expiry;
- cache eviction;
- alias validation;
- backup verification;
- schema validation;
- test execution;
- drift detection;
- candidate aggregation.

An LLM SHOULD NOT run merely because a clock fired. It MAY be invoked after a deterministic job produces a bounded review packet that genuinely requires judgment.

### 18.2 Job contract

Every enabled job MUST declare:

```yaml
job_id: A12
owner: retrieval-maintenance
schedule: "30 */6 * * *"
command_argv: []
no_agent: true
inputs: []
input_signature: string
expected_artifacts: []
freshness_slo: duration
dependencies: []
semantic_outcomes: []
retry_policy: {}
escalation: {}
authority_boundary: local_read_or_derived_write
```

### 18.3 Semantic outcomes

Scheduler exit status is transport information. The job MUST emit a semantic result:

- `work_performed_success`;
- `quiet_no_change_success`;
- `guarded_no_action_success`;
- `review_required`;
- `blocked_dependency`;
- `owner_gate`;
- `retryable_failure`;
- `terminal_failure`.

A correct no-change or guard outcome MUST NOT be labeled an error.

A structurally valid status packet MAY truthfully report that the system is blocked. Packet validity and operational health are different claims.

### 18.4 Artifact-first health

Job health MUST evaluate:

- scheduler registration;
- last dispatch;
- last semantic outcome;
- expected artifact existence;
- artifact validation;
- artifact freshness;
- upstream dependency state;
- escalation state.

`last_status=success` alone is weak evidence.

### 18.5 Changed-only execution

High-cost jobs SHOULD compute a deterministic input signature before doing work.

A signature MAY include:

- normalized input hashes;
- owner-record versions;
- dependency fingerprints;
- model and embedding version;
- chunking/schema version;
- time bucket;
- business date;
- environment version.

When the signature matches the last accepted success and no freshness boundary was crossed, emit a no-change receipt and skip model work.

False-skip tests are mandatory.

### 18.6 Dependency-root rollup

When one upstream failure blocks many jobs, the control plane SHOULD identify:

- root cause;
- directly blocked jobs;
- transitively blocked jobs;
- one owner;
- one repair action.

Do not create the illusion of many independent incidents.

### 18.7 Silent on green

Healthy recurring work SHOULD be quiet.

Notify when:

- state changes materially;
- a new blocker appears;
- an SLA is breached;
- authority is required;
- repeated failure crosses a threshold;
- a candidate for human review is ready.

Attention is a scarce resource. A harness that announces every healthy tick trains the operator to ignore it.

### 18.8 Automation self-tests

The automation layer MUST be tested for:

- wrapper-to-script resolution;
- schedule uniqueness;
- executable availability;
- declared expected artifacts;
- timeout behavior;
- malformed output;
- dependency ordering;
- exception paths;
- quiet-success behavior;
- escalation delivery;
- no-agent enforcement.

Schedulers and wrappers are production code, not incidental configuration.

## 19. Receipts, provenance, and acceptance

### 19.1 Completion is an evidence claim

The harness MUST distinguish:

- execution finished;
- artifact produced;
- validator passed;
- authority approved;
- Acceptance Authority accepted;
- later outcome remained good.

These are separate states.

### 19.2 Terminal receipt

Every material run MUST emit a terminal receipt.

```json
{
  "schema": "harness.execution_receipt.v1",
  "receipt_id": "uuid",
  "correlation_id": "uuid",
  "task_id": "uuid",
  "workflow_id": "WF-001",
  "plan_sha256": "sha256:...",
  "phase_id": "P2",
  "lane_id": "uuid",
  "actor": "executor:code-01",
  "model": {
    "provider": "provider",
    "model_id": "model",
    "model_version": "version-or-unavailable",
    "settings_hash": "sha256:..."
  },
  "context_snapshot_id": "ctx-...",
  "authority": {
    "class": "A2",
    "capability_hash": "sha256:...",
    "approval_id": null
  },
  "attempt": 1,
  "retry_of": null,
  "started_at_utc": "...",
  "ended_at_utc": "...",
  "semantic_outcome": "work_performed_success",
  "commands": [],
  "tool_calls": [],
  "artifacts": [],
  "source_snapshot_before": {},
  "source_snapshot_after": {},
  "validators": [],
  "rollback": {},
  "usage": {
    "input_tokens": null,
    "output_tokens": null,
    "cached_tokens": null,
    "estimated_cost_usd": null,
    "actual_billing_usd": null,
    "coverage": "unavailable"
  },
  "warnings": [],
  "acceptance_status": "pending"
}
```

Unknown counters MUST be `null` or explicitly unavailable. They MUST NOT be silently recorded as zero.

### 19.3 Command receipt

Each protected command MUST capture:

- argv array;
- explicit working directory;
- selected environment identity;
- allowlisted environment variables;
- timeout;
- network policy;
- start and end time;
- exit code;
- bounded stdout/stderr tails;
- full-output artifact hash when retained;
- source snapshot;
- execution actor;
- sandbox identity.

Shell strings SHOULD be rejected for acceptance commands.

### 19.4 Artifact attestation

A produced artifact SHOULD record:

```yaml
artifact_id: UUID
path_or_uri: string
sha256: hex
media_type: string
size_bytes: integer
producer_receipt_id: UUID
source_artifacts:
  - id
  - hash
generator:
  code_version: string
  model_version: string|null
  prompt_or_policy_hash: string|null
generated_at_utc: timestamp
authority_class: derived_proof
freshness:
  valid_until_utc: timestamp|null
  invalidation_keys: []
validation:
  status: passed|failed|unavailable
  receipt_ids: []
```

This is the agent-harness equivalent of verifiable provenance: the artifact can be traced through inputs, generator, environment, and validation.

### 19.5 Acceptance Authority

Only the designated Acceptance Authority may transition a material phase or task to `accepted`.

Acceptance requires:

1. the expected artifact or semantic no-action result;
2. valid receipt schema;
3. matching plan and context hashes;
4. required validators;
5. no undeclared writes;
6. authority compliance;
7. source stability;
8. review of material warnings;
9. rollback readiness when required;
10. queue and continuity consistency.

The Acceptance Authority MAY be:

- a deterministic rule for low-risk exact work;
- the Main integrator;
- a human owner;
- a designated independent reviewer.

The producing agent MUST NOT accept its own high-impact output.

### 19.6 Acceptance outcome

```json
{
  "schema": "harness.acceptance.v1",
  "acceptance_id": "uuid",
  "receipt_id": "uuid",
  "authority_actor": "main",
  "decision": "accepted",
  "decided_at_utc": "...",
  "criteria_results": [],
  "residual_risks": [],
  "follow_up": [],
  "later_outcome_due_at_utc": null
}
```

Possible decisions:

- `accepted`;
- `accepted_with_warning`;
- `rework_required`;
- `rejected`;
- `blocked_authority`;
- `blocked_evidence`;
- `superseded`.

### 19.7 Failed evidence is retained

Failed attempts, validators, and receipts MUST remain available according to retention policy. They are part of the system’s falsification history.

Do not overwrite a failed receipt with a passing rerun. Append a new attempt linked by `retry_of`.

### 19.8 Proof retention

Define retention classes:

| Class | Example | Minimum treatment |
|---|---|---|
| `ephemeral-debug` | non-material trace excerpt | short retention, no canon |
| `operational` | routine job receipt | bounded retention plus aggregate |
| `acceptance` | proof for accepted change | durable or immutable archive |
| `authority` | approval and capability record | durable, access-controlled |
| `security` | incident evidence | legal/security retention |
| `regulated` | domain-specific evidence | applicable policy |

A cleanup job MUST honor class, legal hold, active references, and archive state.

---

## 20. Observability and correlation

### 20.1 One correlation envelope

One immutable `correlation_id` MUST span:

```text
user request
-> task
-> workflow
-> plan
-> lane
-> model run
-> tool calls
-> sandbox commands
-> artifacts
-> validators
-> acceptance
-> later outcome
```

Use child span IDs for nested work and attempt IDs for retries.

Without this join key, telemetry becomes disconnected statistics.

### 20.2 Minimum event envelope

```json
{
  "event_id": "uuid",
  "correlation_id": "uuid",
  "parent_event_id": "uuid|null",
  "task_id": "uuid|null",
  "workflow_id": "string|null",
  "lane_id": "uuid|null",
  "phase_id": "string|null",
  "attempt": 1,
  "actor_type": "model|tool|scheduler|validator|human|control_plane",
  "actor_id": "string",
  "event_type": "tool.completed",
  "status": "success|blocked|failure",
  "reason_code": "string|null",
  "started_at_utc": "...",
  "ended_at_utc": "...",
  "duration_ms": 123,
  "metadata": {}
}
```

### 20.3 Metadata-only default

Default telemetry MAY include:

- route;
- provider and model identifiers;
- tool names;
- durations;
- result classes;
- retries;
- token counters;
- cache counters;
- error categories;
- byte and row counts;
- validator status;
- authority class;
- artifact hashes;
- context and handoff sizes.

Default telemetry MUST exclude:

- raw prompts;
- raw completions;
- tool arguments;
- tool results;
- document contents;
- secrets;
- headers;
- unredacted provider errors;
- user-private content.

Content capture requires a distinct, explicit, time-bounded authority path with retention and access controls.

### 20.4 Telemetry failure behavior

Ordinary telemetry writes SHOULD fail open with respect to delivering a user response, but fail visibly in the operational state.

Security, approval, and acceptance records are not optional telemetry. Failure to record those MUST block the protected action.

### 20.5 OpenTelemetry posture

The doctrine does not mandate OpenTelemetry.

Start with a stable internal event and correlation contract. Add an OTEL adapter when one or more of these are true:

- the harness spans multiple services or hosts;
- cross-vendor trace interoperability is needed;
- external observability tooling is justified;
- semantic conventions reduce custom integration cost;
- the operator routinely needs distributed causal traces.

GenAI semantic conventions can standardize model, token, and tool telemetry, but content fields can be sensitive and should remain opt-in. [R16]

OTEL MUST remain a transport and observability adapter. It does not own:

- truth;
- approval;
- acceptance;
- model quality;
- business correctness;
- self-improvement decisions.

### 20.6 Health is not quality

Operational telemetry can prove that:

- events arrived;
- tools ran;
- latency changed;
- errors occurred;
- a workflow reached a state.

It cannot, by itself, prove that:

- an answer is true;
- a decision is good;
- an action was authorized;
- an outcome was beneficial;
- the model is generally capable.

The harness MUST not convert activity volume into a quality score.

### 20.7 Error taxonomy

Errors SHOULD be recorded as normalized categories with bounded details:

```text
auth
permission
rate_limit
timeout
connection
provider_5xx
invalid_input
tool_contract
sandbox
validation
collision
stale_source
authority
prompt_injection
unknown
```

Store raw exception text only in a protected diagnostic path after secret and privacy review.

### 20.8 Metrics that matter

Prefer:

- first-pass acceptance by task class;
- retry tax;
- escaped defect rate;
- source-open citation correctness;
- stale-result leakage;
- task completion under authority;
- rollback success;
- recovery time;
- human correction rate;
- no-change skips;
- proposal-to-durable-closure conversion;
- intervention latency;
- operator attention burden.

Avoid vanity metrics such as total tool calls, total agent messages, or packet count without outcome context.

### 20.9 Operator cockpit

The primary status view SHOULD answer:

- Is canonical state healthy?
- Is retrieval fresh?
- Which workflows are executable?
- Which are blocked, and by what root cause?
- Are any leases expired or colliding?
- Did any protected action lack a complete receipt?
- Are scheduled artifacts fresh?
- Are validators current?
- Are approvals pending?
- Which issues require attention now?
- What changed since the previous accepted state?

A cockpit is a routing surface, not canon.

---

## 21. Validation, evaluation, and assurance

### 21.1 Validation layers

Use the smallest proof that is adequate for the risk.

| Level | Use | Minimum proof |
|---|---|---|
| V0 | read-only exact lookup | source-open check |
| V1 | derived artifact | schema, source hashes, deterministic checks |
| V2 | narrow local mutation | targeted tests, diff review, fingerprints |
| V3 | shared contract or broad code change | dependency-aware suite, independent review |
| V4 | security/privacy/authority change | adversarial tests, independent specialist review, rollback drill |
| V5 | high-impact external action | exact approval, precommit recheck, outcome verification |

### 21.2 Changed-surface routing

A validator router SHOULD select tests from:

- changed paths;
- changed schemas;
- declared dependencies;
- affected graph edges;
- authority class;
- security labels;
- historical defect patterns;
- generated consumers.

The router MUST fail closed when impact cannot be safely bounded.

### 21.3 Negative-path requirement

Every gate, aggregator, router, permission check, status rollup, and acceptance function MUST have at least one test where an upstream input fails.

An aggregator tested only with healthy inputs is effectively untested.

Required negative paths include:

- one failed child among healthy children;
- malformed child payload;
- missing child;
- stale child;
- contradictory child states;
- duplicate child;
- timeout;
- unauthorized action;
- expired lease;
- source drift;
- partial receipt;
- replayed idempotency key with mismatched payload.

### 21.4 Property and invariant testing

Critical control logic SHOULD use property-based or generative tests for invariants such as:

- no two active write lanes overlap;
- forbidden paths are never admitted;
- acceptance cannot precede validation;
- capability scope cannot expand during delegation;
- stale sources cannot be labeled fresh;
- retries cannot create duplicate side effects;
- a lower-trust instruction cannot override a higher-trust policy;
- a failed child cannot be erased by a healthy rollup;
- a superseded claim cannot outrank current owner truth.

### 21.5 Coverage policy

Line coverage is a diagnostic, not proof of correctness.

Use:

- decision-logic coverage;
- branch coverage for gates;
- subprocess-aware collection;
- mutation testing where practical;
- a coverage ratchet rather than an arbitrary vanity target;
- higher thresholds for authorization, concurrency, acceptance, and rollback code.

The concurrency authority, capability checker, and acceptance gate deserve stronger evidence than a report formatter.

### 21.6 Independent review

The implementation actor MUST NOT be the sole grader for:

- shared contracts;
- security;
- privacy;
- authority;
- migrations;
- broad refactors;
- model or tool promotions;
- high-impact external action.

Independent review may be deterministic, another model with isolated context, a specialist agent, or a human. Independence means it does not inherit the producer’s conclusions as facts.

### 21.7 Outcome versus transcript evaluation

Evaluate both:

1. **Outcome** — Did the environment reach the required state?
2. **Process** — Did the agent obey authority, use valid sources, avoid dangerous paths, and produce complete evidence?

An agent can reach the right answer by an unsafe process. It can also follow a reasonable process and fail because a dependency was unavailable. Both distinctions matter.

Agent evaluation should grade the model and harness together because tool design, prompts, context, permissions, and orchestration materially affect behavior. It should also use repeated trials for stochastic systems rather than trusting one run. [R5] End-to-end trace grading can expose wrong tool choice, bad handoffs, guardrail failures, and routing regressions that outcome-only grading misses. [R28]

### 21.8 Evaluation fixture

An evaluation case SHOULD define:

```yaml
fixture_id: eval-001
task_class: code_repair
input_snapshot: sha256
environment_manifest: sha256
allowed_tools: []
authority_class: A2
success_criteria: []
forbidden_outcomes: []
grader:
  deterministic_checks: []
  rubric_version: string
trials: 5
seed_policy: recorded_or_unavailable
retention: metadata_only_by_default
```

### 21.9 Matched comparisons

Route, model, prompt, or harness changes MUST be assessed on matched cohorts:

- same task class;
- same source snapshot;
- same authority;
- same tool availability;
- same acceptance standard;
- sufficient repeated trials;
- explicit missing-data treatment.

Do not pool unrelated easy and hard tasks into one success rate.

### 21.10 Promotion gate

A candidate route or model MUST NOT promote itself.

Promotion requires:

- frozen baseline;
- pinned candidate;
- trusted terminal receipts;
- sufficient trials;
- no regression on safety or authority;
- no unacceptable latency or cost regression;
- reviewed failure cases;
- explicit decision owner;
- rollback.

Fixture readiness is not execution evidence.

### 21.11 Post-deployment monitoring

Approval is not the end of oversight.

For promoted behaviors, monitor:

- drift;
- new failure modes;
- attack success;
- operator interventions;
- user corrections;
- cost and latency;
- recurrence of closed defects;
- external outcome quality.

Oversight MUST include the ability to interrupt, pause, revoke, and roll back—not merely a one-time approval. Current autonomy research similarly treats monitoring and intervention as core parts of oversight. [R6]

### 21.12 Chaos and recovery tests

Regularly simulate:

- process death;
- machine restart;
- lost model response;
- duplicate delivery;
- delayed tool result;
- provider outage;
- embedding outage;
- telemetry outage;
- stale lock;
- expired lease;
- partial write;
- corrupted derived packet;
- database busy condition;
- scheduler delay;
- malformed remote tool output.

Acceptance criteria MUST include recovery-time and data-loss objectives.

---

## 22. Truthful model behavior

### 22.1 Truth states

Every consequential statement SHOULD map to one of:

| State | Meaning |
|---|---|
| `verified` | Directly supported by current authoritative evidence |
| `supported` | Supported by credible evidence but not fully verified |
| `inferred` | Reasoned conclusion from stated evidence |
| `estimated` | Quantitative or directional estimate with method |
| `reported` | A source claims it; harness has not independently verified it |
| `conflicted` | Credible sources disagree |
| `stale` | Evidence exceeded freshness requirements |
| `unavailable` | Required evidence could not be obtained |
| `unknown` | No adequate basis exists |

The response generator MUST NOT convert `reported`, `inferred`, `stale`, or `unknown` into `verified`.

### 22.2 Response contract

For material answers, use:

```text
conclusion
-> evidence
-> uncertainty
-> risks or constraints
-> next decision or action
```

The response SHOULD be proportionate. A simple exact fact does not need a ceremony. A consequential recommendation does.

### 22.3 Evidence-to-claim check

Before finalizing a material claim, verify:

- the citation actually supports it;
- the source is authoritative for that claim type;
- freshness is adequate;
- a derived packet has not replaced its owner;
- contradictory evidence is disclosed;
- inference is labeled;
- quantities have units, dates, and denominators;
- “current” facts were checked at answer time.

### 22.4 No fabricated precision

The model MUST NOT invent:

- version numbers;
- counts;
- benchmark scores;
- dates;
- paths;
- command results;
- receipt IDs;
- citations;
- approval;
- tool execution;
- confidence percentages.

When exact evidence is absent, state the bounded uncertainty.

### 22.5 No completion theater

The model MUST NOT say:

- “fixed” without a validated change;
- “sent” without delivery evidence;
- “scheduled” without scheduler state;
- “approved” without the approval record;
- “tested” without a test receipt;
- “secure” without a defined security claim and evidence;
- “autonomous” merely because a loop can call tools;
- “AGI” based on one benchmark or impressive conversation.

### 22.6 Honest partial success

A result may be:

```text
complete
complete_with_warning
partial_usable
blocked
failed
unverified
```

Partial success SHOULD name:

- what completed;
- what did not;
- why;
- what evidence exists;
- what action would close the gap.

### 22.7 Correction protocol

When an earlier claim is wrong:

1. identify the claim;
2. state the corrected claim;
3. explain the evidence change or error class;
4. update or supersede the durable record;
5. preserve the historical record;
6. test whether the same error class exists elsewhere;
7. avoid laundering the correction as if it had always been known.

A truthful system must be able to correct itself visibly.

### 22.8 Confidence

Confidence labels MAY be used only when calibrated against a defined task class. Free-form “95% confident” language is usually false precision.

Prefer concrete uncertainty:

- source missing;
- one of three corpora unavailable;
- estimate depends on assumption X;
- two credible sources conflict;
- validation not run;
- evidence is older than the freshness SLO.

### 22.9 Refusal and safe stopping

The model MUST stop when:

- authority is absent;
- evidence required for a high-impact decision is unavailable;
- an external instruction conflicts with governance;
- a validator exposes a material unresolved failure;
- the requested action violates a stop line;
- the sandbox or identity boundary cannot be established.

A safe stop SHOULD still produce useful diagnostics and a bounded path forward.

---

## 23. Self-improvement and learning

### 23.1 Improvement conveyor

```text
telemetry / failures / corrections / outcomes
-> normalize signal
-> detect recurrence
-> create candidate
-> pin baseline
-> propose bounded change
-> human or designated authority reviews
-> isolated evaluation
-> decision
-> staged apply
-> validate
-> monitor later outcome
-> durable closure or reopen
```

Detection MAY be broad. Application authority MUST remain narrow.

### 23.2 Candidate schema

```yaml
candidate_id: UUID
signal_class: string
first_seen_at_utc: timestamp
last_seen_at_utc: timestamp
occurrences: integer
affected_task_classes: []
evidence_receipts: []
hypothesized_cause: string
proposed_surface: prompt|tool|route|code|policy|model
authority_required: string
baseline_validation_id: UUID|null
status: observation
```

### 23.3 Maturity states

```text
observation
-> candidate
-> evaluated
-> approved
-> applied
-> audited
-> retired
```

Only `audited` or `retired` counts as durable closure.

### 23.4 No autonomous self-amendment

The harness MUST NOT autonomously change:

- constitutional invariants;
- authority classes;
- stop lines;
- credential policy;
- approval policy;
- acceptance criteria;
- security controls;
- production model route;
- external spending or account policy.

It MAY automatically generate a proposed patch and evidence packet for review.

### 23.5 Baseline integrity

Evaluation MUST pin:

- baseline artifact;
- baseline validation ID;
- source snapshot;
- environment;
- model and settings;
- test count;
- task cohort;
- grading version.

A later baseline row MUST NOT silently replace the pinned comparison.

### 23.6 Evaluation gate

A candidate MUST fail closed when:

- baseline has zero tests;
- baseline failed;
- candidate and baseline use different task cohorts;
- source snapshots differ materially;
- safety or authority regresses;
- required usage data is missing and cost is part of the decision;
- repeated trials are insufficient;
- the candidate cannot be rolled back.

### 23.7 Closure KPI

The main self-improvement KPI is not proposal volume.

Measure:

- accepted proposals;
- time to accepted change;
- later-outcome success;
- recurrence rate;
- reopened defects;
- escaped defects;
- operator burden;
- net cost and latency effect.

A system that creates hundreds of proposals and closes none is not self-improving.

### 23.8 Reflection use

Model-generated reflection MAY help diagnose strategy, as research on verbal reinforcement and reflection suggests, but reflection is not evidence by itself. [R24]

Store a reflection only when linked to:

- a specific outcome;
- the evidence that triggered it;
- a bounded future applicability condition;
- an expiration or review rule.

Do not accumulate generic model advice as durable policy.

### 23.9 Harness ablation

As models improve, periodically test whether old scaffolding still helps.

For each harness component, ask:

- Which model limitation did this compensate for?
- Does it still improve accepted outcomes?
- Does it create latency, context, or failure modes?
- Can it be simplified or removed?
- Does removal change safety or authority?

Harness components encode assumptions about model limitations. Those assumptions can become stale. [R7]

### 23.10 Improvement authority boundary

An improvement agent can recommend changes to the harness. It cannot become the owner of the harness.

---

## 24. AGI readiness and autonomy doctrine

### 24.1 Do not confuse a harness with AGI

A reliable harness can make a non-general model:

- more persistent;
- more grounded;
- more useful;
- safer;
- more autonomous within a domain.

That does not establish artificial general intelligence.

AGI assessment should separate at least:

- task performance;
- breadth or generality;
- autonomy;
- reliability;
- risk.

DeepMind’s operational framing likewise separates performance, generality, and autonomy rather than treating AGI as one binary label. [R13]

### 24.2 AGI-ready means architecture-ready

In this doctrine, `AGI-ready` means the harness can safely accommodate stronger and more general models without handing them uncontrolled authority.

It requires:

- model-agnostic contracts;
- capability isolation;
- externalized state;
- source-grounded truth;
- deterministic control logic;
- sandbox separation;
- complete receipts;
- revocable identity;
- evals across diverse faculties;
- human intervention;
- graceful degradation;
- no dependence on a model’s claimed obedience.

### 24.3 Capability dimensions

Assess a model-harness system across separate dimensions:

1. reasoning and problem solving;
2. knowledge and retrieval use;
3. metacognition and uncertainty;
4. learning and adaptation;
5. planning over time;
6. tool and environment interaction;
7. social and communication competence;
8. creativity;
9. memory and continuity;
10. safety and authority adherence.

A single aggregate score hides failure modes. Emerging cognitive AGI frameworks similarly argue for multidimensional evaluation rather than one headline benchmark. [R14]

### 24.4 Autonomy envelope

Autonomy is a bounded envelope:

```yaml
domain: repository_maintenance
objectives:
  - keep indexes fresh
allowed_actions:
  - read approved sources
  - write derived indexes
  - run validators
forbidden_actions:
  - change governance
  - access credentials
  - push production
resource_limits:
  elapsed_minutes: 20
  tool_calls: 50
  spend_usd: 0.10
freshness_requirements: []
human_intervention:
  required_before: []
  interruptible: true
```

The envelope is the unit of autonomy, not the model.

### 24.5 Autonomy ladder

#### L0 — Advisory

- model produces information or recommendations;
- no persistent state mutation;
- source citations required where material.

#### L1 — Read-only grounded agent

- retrieves from approved sources;
- calls read-only tools;
- no writes;
- bounded context and telemetry.

#### L2 — Derived-work agent

- creates drafts, reports, indexes, and temporary artifacts;
- writes only derived surfaces;
- deterministic validation;
- no canonical or external mutation.

#### L3 — Reversible local operator

- performs scoped local writes under lease;
- idempotency and rollback;
- independent acceptance;
- no secrets or external side effects.

#### L4 — Scheduled bounded operator

- executes pre-approved recurring workflows;
- changed-only gates;
- semantic outcomes;
- automatic pause on drift or repeated failure.

#### L5 — Approval-gated external actor

- prepares external actions;
- human approves exact payload digest;
- narrow delegated credential;
- verifies external outcome;
- revocation and compensation.

#### L6 — Policy-bounded adaptive operator

- can replan within an approved objective and capability envelope;
- uses receipt-based state;
- requests authority expansion rather than assuming it;
- continuous monitoring and intervention.

#### L7 — High-impact autonomous operator

- reserved for domains with mature identity, formal policy, adversarial evaluation, complete audit, robust rollback or compensation, and demonstrated comparable outcomes;
- human governance remains external;
- constitutional and authority policy remain non-self-modifiable.

A system MUST earn each level per workflow. It does not receive one global level.

### 24.6 Promotion evidence

Autonomy promotion requires:

- stable task definition;
- repeated accepted outcomes;
- low escaped-defect rate;
- complete receipts;
- tested prompt-injection resistance;
- sandbox proof;
- reliable recovery;
- bounded costs;
- demonstrated intervention;
- no unresolved authority incidents;
- later-outcome evidence.

Ten clean demonstrations can support a pilot. They do not prove universal safety.

### 24.7 Task horizon

Longer apparent work duration is not itself stronger autonomy.

Measure task horizon by:

- task difficulty;
- reliability at that difficulty;
- number of independent decisions;
- recovery after interruption;
- authority adherence;
- outcome verification.

METR’s time-horizon methodology estimates the human task duration at which an agent reaches a given success probability; it explicitly does not mean the wall-clock time an agent can simply keep acting. [R15]

### 24.8 Intervention

Every autonomous workflow above L2 MUST support:

- pause;
- cancel;
- capability revocation;
- lease expiry;
- safe checkpoint;
- state inspection;
- rollback or compensation;
- postmortem.

An uninterruptible agent is not mature autonomy. It is unmanaged automation.

### 24.9 Stronger models increase the need for controls

As model capability rises:

- more tasks become feasible;
- tool use becomes more effective;
- longer plans become possible;
- mistakes may propagate farther;
- authority misuse can have greater impact.

Do not remove control because the model appears smarter. Remove scaffolding only when measured ablation shows it is unnecessary while safety and truth remain intact.

### 24.10 No AGI theater

The harness MUST reject claims such as:

- “AGI because it used many tools”;
- “AGI because it ran for hours”;
- “AGI because it improved its prompt”;
- “AGI because it passed one benchmark”;
- “AGI because it spawned agents”;
- “deterministic because temperature was zero.”

Determinism belongs to control logic and state transitions, not to the expectation that an LLM will always emit identical text.

## 25. Efficiency doctrine

### 25.1 Optimize accepted outcomes, not raw speed

The objective is:

```text
minimum total cost
subject to truth, authority, and acceptance
```

Total cost includes:

- model tokens;
- API spend;
- wall-clock time;
- tool and compute use;
- operator attention;
- retries;
- rework;
- escaped defects;
- recovery;
- security incidents;
- stale decisions.

A fast false answer is expensive. A cheap unauthorized action is expensive. A verbose trace that nobody can use is expensive.

### 25.2 Efficiency order

Optimize in this order:

1. eliminate unnecessary work;
2. use exact deterministic lookup;
3. use cached fresh proof;
4. retrieve the smallest relevant source unit;
5. use the smallest adequate model;
6. parallelize only independent work;
7. bound retries and output;
8. validate proportionally;
9. measure like-for-like outcomes;
10. simplify the harness when evidence supports it.

### 25.3 Avoid work before accelerating it

Before a model call, ask:

- Is the answer already in canonical state?
- Is a fresh accepted artifact available?
- Did inputs change?
- Can a deterministic script answer?
- Is this request a duplicate?
- Is the workflow blocked?
- Is authority absent?
- Can one bounded retrieval replace a broad scan?
- Can a smaller route meet the acceptance standard?

The highest-leverage optimization is often not making the call.

### 25.4 Thin startup

Startup SHOULD load only:

- identity and mission;
- authority boundaries;
- response contract;
- deterministic status brief;
- recent continuity pointer;
- task-relevant source routes.

Procedures, large histories, schemas, and domain references load on demand.

A large context window is not permission to preload the repository.

### 25.5 Section-level context

Index and retrieve at the smallest coherent unit:

- heading section;
- canonical record;
- function or class;
- graph neighborhood;
- bounded event window;
- exact line range.

Do not return a 900-line file when a 15-line section establishes the claim.

### 25.6 Context utility

For each context item, estimate:

```text
expected decision value
/ (tokens + distraction + staleness risk)
```

Remove low-value context, even when it is technically relevant.

Context engineering research treats context as finite and emphasizes selecting the smallest high-signal set for the current decision. [R3]

### 25.7 Caching rules

Cache only when:

- inputs have stable signatures;
- authority and user boundaries are part of the key;
- freshness is explicit;
- model, prompt, tool, and schema versions are represented;
- invalidation is tested;
- cache hits are observable;
- the uncached source remains available.

A cache MUST NOT hide a changed approval, revoked capability, or superseded claim.

### 25.8 Model routing

Model selection SHOULD consider:

- required reasoning depth;
- tool reliability;
- context length;
- latency;
- cost;
- privacy and locality;
- structured-output reliability;
- task-specific eval results;
- authority and data classification;
- provider availability.

Use the lowest-cost route that meets the task’s accepted quality and safety threshold. Do not route by marketing tier.

### 25.9 Escalation

Escalate to a stronger or more expensive model only when a defined trigger occurs:

- contradictory evidence;
- repeated validation failure;
- high uncertainty;
- long dependency chain;
- material risk;
- complex synthesis;
- poor task-class baseline for the current route.

Record the trigger in the route receipt.

### 25.10 Parallelism

Parallelize only when work units are:

- independent or dependency-ordered;
- collision-free;
- separately provable;
- bounded in context and writes;
- cheaper to merge than to execute sequentially.

Parallelism that creates merge ambiguity or duplicate retrieval is negative efficiency.

### 25.11 Batching

Batch:

- independent read-only queries;
- schema-compatible validations;
- small deterministic transformations;
- telemetry writes;
- index updates with shared snapshots.

Do not batch:

- actions requiring distinct approvals;
- writes with different rollback semantics;
- tasks whose failures need independent retry;
- heterogeneous requests that enlarge context and confuse acceptance.

### 25.12 Retry tax

Measure retry tax separately:

```text
retry_elapsed
retry_tokens
retry_tool_calls
duplicate_external_effects
human_recovery_time
```

A route with high final success but repeated retries may be worse than a slower route with high first-pass acceptance.

### 25.13 Output economy

Internal outputs SHOULD be machine-readable and bounded.

User-facing outputs SHOULD state the decision and material evidence without dumping the internal trace.

The model should not narrate every tool call unless the task requires an audit narrative.

### 25.14 Storage economy

Store:

- canonical facts;
- append-only decisions and events;
- proof required for acceptance;
- compact continuity;
- meaningful aggregate metrics.

Do not indefinitely store:

- duplicate context;
- raw chain-of-thought;
- unbounded tool dumps;
- every generated draft;
- temporary caches without retention;
- raw content telemetry by default.

### 25.15 Complexity budget

Every new component MUST justify:

- recurring problem solved;
- owner;
- source of truth;
- runtime and maintenance cost;
- failure modes;
- tests;
- observability;
- rollback;
- removal criteria.

Do not add a vector database, graph database, agent swarm, OTEL stack, message bus, or workflow engine because the architecture sounds sophisticated.

Start with plain files, SQLite, typed scripts, and one end-to-end receipt. Scale when measurements force the change.

### 25.16 Efficiency acceptance

An efficiency change is accepted only when it:

- preserves or improves accepted outcomes;
- preserves authority;
- does not increase escaped defects;
- has a matched baseline;
- accounts for retries and cache;
- labels actual versus estimated cost;
- avoids false skips;
- remains debuggable.

Token reduction without outcome preservation is not efficiency.

---

## 26. Multi-agent operating doctrine

### 26.1 Default to one agent

Use one capable agent plus deterministic tools until task structure justifies specialization.

Additional agents create:

- context transfer;
- synchronization;
- duplicated work;
- authority complexity;
- merge conflicts;
- attribution gaps;
- new failure paths.

Multi-agent architecture is not a maturity badge.

### 26.2 When to delegate

Delegate when:

- work decomposes into independent artifacts;
- specialist tools or expertise materially help;
- an independent verifier is required;
- parallel latency reduction outweighs merge cost;
- context isolation improves safety;
- one task can be expressed as a bounded contract.

### 26.3 Orchestration patterns

#### Sequential workflow

Use when each step has a stable dependency.

```text
retrieve -> analyze -> draft -> validate -> accept
```

#### Router-specialist

Use when task classification is reliable and specialists have distinct tools or policies.

```text
intake -> deterministic router -> specialist -> validator
```

#### Parallel fan-out/fan-in

Use when subproblems are independent.

```text
planner -> [worker A, worker B, worker C] -> integrator -> validator
```

#### Evaluator-optimizer

Use when quality criteria are explicit and iteration is bounded.

```text
producer -> evaluator -> repair -> evaluator -> stop
```

#### Manager-workers

Use for dynamic decomposition only after lane, receipt, and recovery maturity.

```text
manager -> task DAG -> capability-limited workers -> receipt-driven replan
```

Anthropic’s practical agent guidance recommends starting with simple composable workflows and adding autonomous agents only when flexibility is worth the latency, cost, and error risk. [R1]

### 26.4 Planner-worker separation

The planner produces a DAG:

```yaml
nodes:
  - node_id: N1
    objective: string
    dependencies: []
    lane_template: string
    proof: string
edges: []
global_stop_lines: []
```

The control plane validates the DAG before workers run.

A worker MAY request a replan. It MUST NOT create undeclared high-impact child work.

### 26.5 Delegation attenuation

A child capability MUST be equal to or narrower than the parent capability.

Delegation MUST NOT:

- extend expiration;
- add resources;
- weaken approval;
- cross user or tenant boundaries;
- expose parent secrets;
- grant governance mutation;
- permit onward delegation unless explicit.

### 26.6 Handoff packet

A handoff MUST contain:

- objective;
- authoritative sources;
- source snapshot;
- decisions already accepted;
- open questions;
- exact allowed writes;
- capabilities;
- budgets;
- acceptance;
- stop lines;
- parent correlation ID;
- return format.

It MUST NOT include the full conversation by default.

### 26.7 Integration

The integrator MUST:

- verify all child receipts;
- detect conflicting claims;
- open source evidence for consequential conclusions;
- resolve or expose contradictions;
- ensure no gaps between task DAG nodes;
- run integration validators;
- preserve child attribution;
- avoid crediting missing or invalid receipts.

A coherent narrative is not evidence that the parts are compatible.

### 26.8 Agent identity and attribution

Every child event MUST preserve:

- parent actor;
- child actor;
- delegated capability hash;
- model/provider;
- context snapshot;
- lane;
- attempt;
- artifact and validator receipts.

Do not merge helper activity into the Main agent’s identity.

### 26.9 Dynamic replanning

Replanning MAY occur when:

- a node fails;
- a dependency changes;
- new evidence invalidates an assumption;
- the original plan exceeds budget;
- a safer deterministic route becomes available.

Replanning MUST use terminal receipts and current state. It SHOULD NOT replay the entire conversation.

### 26.10 Termination

A manager MUST stop when:

- all required nodes are accepted;
- a stop line is reached;
- authority is missing;
- budget is exhausted;
- no-progress threshold is reached;
- critical evidence is unavailable;
- repeated replans fail;
- operator pauses the workflow.

### 26.11 Long-running sessions

Long work SHOULD use:

- an initialization phase;
- an environment manifest;
- task list or DAG;
- incremental agents;
- durable progress files;
- checkpoint receipts;
- bounded pickup packets;
- clean handoff between sessions.

Long-running agent research finds that context compaction alone is not enough; durable artifacts and clear incremental handoffs are needed across discrete sessions. [R2]

### 26.12 Brain, hands, and session log

For scalable execution, separate:

- **brain** — model reasoning;
- **hands** — sandboxes and tools;
- **session log** — durable event stream;
- **harness** — trusted orchestrator.

A hand is replaceable compute. Losing it MUST NOT erase canonical task state.

This separation also permits several hands per brain and several models over the same durable workflow without coupling authority to one container. [R4]

---

## 27. Repository and deployment blueprint

### 27.1 Minimal repository

```text
harness/
  README.md
  AGENT.md
  GOVERNANCE.md
  USER.md
  TOOLS.md
  SECURITY.md

  canonical/
    schema.sql
    db.py
    migrations/
    README.md

  contracts/
    task.schema.json
    workflow.schema.json
    plan.schema.json
    lane.schema.json
    capability.schema.json
    receipt.schema.json
    acceptance.schema.json
    telemetry.schema.json
    artifact.schema.json

  state/
    workflows/
    plans/
    implementation-jobs/
    lanes/
    approvals/
    claims/
    schedules/
    checkpoints/
    routing/
    retrieval/
    telemetry/

  memory/
    durable/
    daily/
    reflections/

  retrieval/
    registry.json
    fulltext/
    vector/
    graph/
    wiki/

  skills/
    task-intake/
    source-grounding/
    code-repair/
    validation/
    release/

  scripts/
    status/
    routing/
    retrieval/
    workflow/
    lanes/
    validation/
    release/
    telemetry/
    maintenance/

  tests/
    unit/
    integration/
    security/
    adversarial/
    recovery/
    fixtures/

  sandboxes/
    manifests/
    policies/

  continuity/
  artifacts/
  derived/
  archives/
  tmp/
```

### 27.2 Layer ownership

| Layer | Owner type | Mutable by |
|---|---|---|
| Constitutional doctrine | human governance owner | explicit governance change |
| User preferences | user or delegated owner | explicit preference write |
| Canonical state | canonical DB gateway | admitted transaction |
| Workflow state | workflow control plane | workflow transitions |
| Lane state | lane manager | lane commands |
| Derived indexes | deterministic producers | scheduled or admitted rebuild |
| Memory | memory manager | classified promotion |
| Skills | skill owner | reviewed version change |
| Telemetry | observer/recorder | append-only writer |
| Approvals | approval service | authorized human action |
| Archives | retention manager | governed lifecycle |

### 27.3 Single-writer principle

Each mutable truth family SHOULD have one write gateway.

Examples:

- all canonical SQL through `CanonicalDB`;
- all lane mutations through `LaneManager`;
- all workflow transitions through `WorkflowService`;
- all approvals through `ApprovalService`;
- all capabilities through `CapabilityBroker`.

Direct writes are forbidden even when technically possible.

### 27.4 Database minimum

A practical SQLite schema SHOULD include:

- `provenance`;
- `actors`;
- `users`;
- `tasks`;
- `workflows`;
- `plans`;
- `phases`;
- `lanes`;
- `capabilities`;
- `approvals`;
- `claims`;
- `decisions`;
- `events`;
- `artifacts`;
- `validation_results`;
- `acceptances`;
- `workflow_runs`;
- `run_metrics`;
- `source_freshness`;
- `relationships`;
- `routing_cache`;
- `version_history`;
- `idempotency_keys`.

SQLite is sufficient for a single-host or modest harness when access is transactional and centralized. Use WAL where appropriate, enable foreign keys on every connection, and rely on atomic commit semantics rather than ad hoc file updates. [R20]

### 27.5 Database gateway rules

The gateway MUST:

- enable foreign keys;
- set a busy timeout;
- use transactions;
- stamp UTC time;
- require provenance;
- prohibit mutable primary keys;
- preserve prior versions;
- append events;
- support read-only connections;
- run integrity checks;
- reject duplicate business keys;
- protect immutable evidence tables;
- expose domain methods rather than free-form writes.

### 27.6 Migration rules

Each migration MUST have:

- sequential version;
- checksum;
- forward plan;
- rollback or restore plan;
- fixture test;
- production preflight;
- backup requirement;
- schema compatibility window;
- post-migration validation.

The model MUST NOT invent or auto-apply schema migrations outside an approved migration lane.

### 27.7 Environment manifest

```yaml
manifest_version: 1
os: linux
architecture: x86_64
runtime:
  python: "3.13.5"
  node: null
package_locks:
  - path: uv.lock
    sha256: ...
tools:
  - name: git
    version: "2.49.0"
sandbox:
  network: denied
  cpu_limit: 2
  memory_mb: 4096
  disk_mb: 8192
mounts:
  - source: project
    target: /workspace/project
    mode: rw
secrets: []
```

Environment identity MUST be included in material receipts.

### 27.8 Deployment topology

A strong default:

```text
Operator UI
    |
Trusted Harness API
    |-- Canonical State
    |-- Capability Broker
    |-- Approval Service
    |-- Scheduler
    |-- Telemetry
    |-- Model Router
    |
Sandbox Gateway
    |-- Ephemeral/Resumable Sandbox A
    |-- Ephemeral/Resumable Sandbox B
    |-- Read-only Retrieval Worker
```

The model does not connect directly to the canonical database, secrets, or external services. It asks typed tools mediated by the harness.

### 27.9 Portability

Portable contracts MUST avoid:

- hard-coded user directories;
- host-specific separators;
- embedded credentials;
- provider-only state formats;
- undocumented environment assumptions;
- mutable global paths;
- local timezone ambiguity.

Use path abstraction, UTC internally, explicit locale where needed, environment discovery, and secret placeholders.

### 27.10 Clean-machine bootstrap

A bootstrap MUST:

1. verify prerequisites;
2. create directories;
3. initialize canonical schema;
4. install pinned dependencies;
5. validate policy files;
6. build a retrieval registry;
7. create sample workflows;
8. register deterministic jobs;
9. run the full self-test;
10. execute one sample task through receipt and acceptance;
11. prove backup and restore;
12. report missing optional integrations.

No user secret or historical residue should be required to prove the core harness.

---

## 28. Canonical contract templates

### 28.1 Workflow contract

```yaml
schema: harness.workflow.v1
workflow_id: WF-001
name: Retrieval Maintenance
owner: main
objective: Keep approved retrieval indexes fresh and validated.
scope:
  in:
    - retrieval registry
    - full-text index
    - vector index
  out:
    - governance mutation
    - arbitrary filesystem indexing
authority_class: A2
effective_status: active
dependencies:
  - canonical-integrity
blockers: []
stop_lines:
  - never index secrets or unapproved sources
freshness_slo: PT6H
default_route: deterministic
entry_checks:
  - registry_valid
  - embedding_route_known
acceptance:
  - both indexes validate
  - stale_source_count == 0
  - source counts reconcile
rollback:
  - restore last-known-good index
continuity_path: continuity/WF-001.md
```

### 28.2 Task contract

```yaml
schema: harness.task.v1
task_id: UUID
request_digest: sha256
objective: string
interpretation: string
non_goals: []
authority_class: A2
risk_class: narrow
source_surfaces: []
required_freshness: []
allowed_outputs: []
stop_lines: []
budgets:
  context_tokens: 30000
  model_turns: 12
  tool_calls: 50
  elapsed_seconds: 1800
acceptance:
  artifact: path
  validators: []
response_contract:
  - conclusion
  - evidence
  - uncertainty
```

### 28.3 Capability contract

```yaml
schema: harness.capability.v1
capability_id: UUID
principal: agent:executor-01
delegated_by: user:owner
task_id: UUID
lane_id: UUID
actions:
  - filesystem.read
  - filesystem.write
resources:
  allow:
    - project/src/module.py
    - project/tests/test_module.py
  deny:
    - project/.env
    - project/GOVERNANCE.md
network:
  mode: deny
limits:
  writes: 20
  bytes: 1000000
issued_at_utc: timestamp
expires_at_utc: timestamp
approval_id: null
nonce: random
signature: string
```

### 28.4 Lane contract

```yaml
schema: harness.lane.v1
lane_id: UUID
parent_job_id: UUID
workflow_id: WF-002
owner_actor: agent:executor-01
state: leased
allowed_reads: []
allowed_writes: []
forbidden_writes: []
lease_expires_at_utc: timestamp
plan_sha256: hex
context_snapshot_id: string
attempt: 1
acceptance_bundle_id: bundle-01
```

### 28.5 Context manifest

```yaml
schema: harness.context_snapshot.v1
context_snapshot_id: ctx-001
created_at_utc: timestamp
task_id: UUID
items:
  - source_id: canonical:task:123
    path_or_uri: canonical://tasks/123
    sha256: hex
    line_start: null
    line_end: null
    authority_class: canonical
    freshness_state: fresh
total_bytes: 42500
estimated_tokens: 11000
policy_hash: hex
tool_schema_hash: hex
```

### 28.6 Validation bundle

```yaml
schema: harness.validation_bundle.v1
bundle_id: VB-001
risk_level: V2
changed_surfaces: []
commands:
  - argv: ["python", "-m", "pytest", "tests/test_target.py", "-q"]
    cwd: project
    timeout_s: 180
required_independent_review: false
source_stability_required: true
acceptance_rule: all_required_pass
```

### 28.7 Pickup packet

```yaml
schema: harness.pickup.v1
task_id: UUID
workflow_id: WF-002
objective: string
status: blocked
plan_pointer: continuity/job-plan.md
plan_sha256: hex
current_phase: P2
accepted_phases:
  - P0
  - P1
blocker:
  class: environment_drift
  evidence: receipt-id
allowed_writes: []
acceptance_commands: []
next_action: Rebuild the pinned test environment and re-run P2.
stop_lines: []
```

Exclude raw transcripts and bulky receipts. Include references to them.

### 28.8 Improvement candidate

```yaml
schema: harness.improvement_candidate.v1
candidate_id: UUID
signal: validator_timeout
occurrences: 7
window: P7D
evidence_receipts: []
baseline_validation_id: UUID
proposed_change:
  surface: route
  description: string
authority_required: human_review
status: candidate
```

### 28.9 Approval record

```yaml
schema: harness.approval.v1
approval_id: UUID
approver: user:owner
action_type: external.send
target: recipient-id
payload_sha256: hex
constraints:
  max_count: 1
  expires_at_utc: timestamp
requested_by: agent:main
approved_at_utc: timestamp
consumed_at_utc: null
status: active
```

### 28.10 Semantic job result

```json
{
  "schema": "harness.job_result.v1",
  "job_id": "A12",
  "correlation_id": "uuid",
  "outcome": "quiet_no_change_success",
  "inputs_signature": "sha256:...",
  "artifacts": [],
  "root_cause": null,
  "next_action": null,
  "generated_at_utc": "..."
}
```

## 29. Operating runbooks

### 29.1 New-session startup

1. Load constitutional policy and user contract.
2. Run the deterministic status command.
3. Verify canonical integrity and migration state.
4. Inspect active workflows, blockers, and pending approvals.
5. Load recent continuity pointer, not full history.
6. Classify the current request into task, authority, and risk.
7. Select the source route.
8. Freeze only the context needed for the next decision.
9. Do not mutate state until admission succeeds.

Startup fails closed when governance, canonical state, or actor identity cannot be verified.

### 29.2 Exact factual answer

1. Parse exact anchors.
2. Query canonical state or exact source.
3. verify freshness.
4. retrieve the smallest supporting excerpt.
5. check contradiction and supersession.
6. answer with citation.
7. label unavailable or stale evidence honestly.

Do not invoke an agent loop when one exact lookup answers the question.

### 29.3 Research and synthesis

1. Define the research question and decision use.
2. Declare freshness and source-quality requirements.
3. search authoritative primary sources first.
4. preserve source metadata and access time.
5. separate source claims from inference.
6. reconcile conflicting evidence.
7. produce a claim-evidence matrix.
8. write the synthesis.
9. verify every consequential citation.
10. state uncertainty and unresolved gaps.

Research output is derived evidence, not automatic policy.

### 29.4 Code repair

1. Reproduce or establish the defect.
2. identify the smallest affected surface.
3. inspect graph/dependency routes before broad scanning.
4. create a plan with exact writes.
5. acquire a lane and capability.
6. snapshot the source.
7. implement the smallest coherent repair.
8. run targeted negative and positive tests.
9. run dependency-aware integration checks.
10. confirm source stability during validation.
11. emit a receipt.
12. obtain acceptance.
13. update continuity and close the lane.

Do not rewrite adjacent code merely because it could be cleaner.

### 29.5 New feature

1. Confirm objective and non-goals.
2. identify owner contracts and consumers.
3. define interface before implementation.
4. threat-model new authority or data flow.
5. add schema and negative-path tests.
6. implement behind a flag or bounded route.
7. validate on frozen fixtures.
8. stage rollout.
9. monitor outcomes.
10. remove the old route only after migration proof.

### 29.6 Canonical data update

1. Read through the canonical gateway.
2. establish expected record version.
3. classify authority.
4. preview exact delta.
5. begin transaction.
6. append provenance and prior version.
7. apply update.
8. append event.
9. validate constraints and integrity.
10. commit atomically.
11. emit receipt.
12. refresh or invalidate derived consumers.

No script opens the database for an ad hoc write.

### 29.7 External action

1. prepare exact target and payload.
2. resolve recipient or resource identity.
3. classify impact.
4. validate content and policy.
5. calculate payload digest.
6. request approval bound to that digest.
7. recheck target, freshness, and constraints.
8. acquire short-lived delegated credential.
9. execute exactly once with idempotency.
10. verify the external result.
11. record delivery or effect receipt.
12. revoke or expire the capability.

Drafting is not sending. Approval is not delivery.

### 29.8 Scheduled-job failure

1. read semantic result, not exit code alone.
2. identify root upstream cause.
3. determine whether artifact is absent, invalid, or stale.
4. check whether no-change or guard behavior was correct.
5. classify retryability.
6. suppress duplicate downstream incidents.
7. repair deterministic producer or dependency.
8. rerun within a bounded lease.
9. verify artifact and freshness.
10. close the root incident; downstream states should reconcile automatically.

### 29.9 Retrieval degradation

1. report per-corpus status.
2. exclude stale or corrupted units.
3. use exact/FTS fallback.
4. open source records.
5. label degraded mode.
6. continue with healthy corpora when sufficient.
7. create a maintenance item for the failed corpus.
8. do not present partial recall as complete recall.

### 29.10 Prompt-injection event

1. halt consequential action.
2. preserve the untrusted source and provenance in quarantine.
3. revoke unneeded capabilities.
4. identify attempted instruction and target.
5. inspect whether any tool or data flow was affected.
6. rotate credentials if exposure is plausible.
7. test adjacent attack variants.
8. patch the architectural boundary, not only the wording detector.
9. record incident and outcome.
10. resume only after independent security acceptance.

### 29.11 Expired or abandoned lane

1. prevent further writes.
2. snapshot available partial artifacts.
3. mark lane expired.
4. identify active processes.
5. terminate or isolate them.
6. validate workspace integrity.
7. create a pickup packet.
8. decide to renew, replan, or cancel.
9. re-run collision checks before a new lease.

### 29.12 Interrupted long job

1. load event history and pickup packet.
2. verify plan and context hashes.
3. identify last accepted phase.
4. inspect incomplete activity for possible side effects.
5. reconcile idempotency records.
6. restore or recreate sandbox from manifest.
7. resume only the next incomplete phase.
8. do not replay accepted side effects.
9. emit a recovery event.

### 29.13 Release

1. freeze release candidate and source hash.
2. build in a clean environment.
3. run required validators.
4. produce artifact provenance.
5. prepare rollback package.
6. review security and authority impacts.
7. approve exact candidate digest.
8. activate within change window.
9. run health and schema checks.
10. observe canary or bounded cohort.
11. accept or roll back.
12. preserve release and rollback receipts.

### 29.14 Incident response

1. stop or constrain affected capabilities.
2. preserve evidence.
3. establish current canonical truth.
4. classify security, authority, data, or correctness impact.
5. identify affected workflows and artifacts through lineage.
6. contain.
7. recover from known-good state.
8. validate.
9. communicate facts, uncertainty, and scope.
10. create corrective actions.
11. test the failure class.
12. monitor recurrence.

### 29.15 Self-improvement review

1. inspect normalized signal and recurrence.
2. open evidence receipts.
3. validate root-cause hypothesis.
4. confirm pinned baseline.
5. review proposed scope and authority.
6. decide reject, monitor, evaluate, or approve pilot.
7. run isolated matched evaluation.
8. inspect failure cases, not only aggregate score.
9. stage if approved.
10. measure later outcome and recurrence.
11. close only when the change stayed fixed.

---

## 30. Implementation roadmap

### Phase 0 — Constitution and threat model

Build:

- mission and priority order;
- governance owner;
- user contract;
- authority classes;
- stop lines;
- data classifications;
- high-impact action inventory;
- threat model.

Acceptance:

- every action class has an owner;
- external and irreversible actions are identified;
- generated output cannot imply approval;
- secrets and protected surfaces are named;
- the system can explain what it may and may not do.

### Phase 1 — Canonical state and single-writer gateways

Build:

- SQLite schema;
- transactional gateway;
- provenance;
- append-only events;
- version history;
- read-only observer mode;
- integrity tests;
- idempotency registry.

Acceptance:

- no direct database writes;
- rollback on failed transaction;
- duplicate business keys rejected;
- read-only observers physically cannot mutate;
- one exact state query answers current status.

### Phase 2 — Deterministic startup and workflow control

Build:

- status brief;
- task intake;
- workflow registry;
- aliases;
- overrides;
- continuity notes;
- router;
- freshness flags.

Acceptance:

- a new session orients from one bounded packet;
- active workflow returns owner, status, blocker, next action, and proof;
- stale routing is visibly unsafe;
- paused work cannot execute.

### Phase 3 — Lanes, capabilities, and admission

Build:

- actor registry;
- capability broker;
- lane register;
- collision detection;
- finite leases;
- protected-surface policy;
- write preflight.

Acceptance:

- no overlapping write leases;
- expired capability and lease are rejected;
- forbidden path tests pass;
- child delegation cannot expand authority;
- every material write has actor, lane, and task attribution.

### Phase 4 — Exact and section-scoped retrieval

Build:

- approved source registry;
- exact retrieval;
- section chunking;
- FTS;
- freshness and source hashes;
- citation checker;
- degraded fallback.

Acceptance:

- a source-open citation supports each test claim;
- stale units are labeled or excluded;
- retrieval returns bounded sections;
- arbitrary paths and secrets cannot enter the index;
- fallback remains useful and visible.

### Phase 5 — Plan, execution, receipt, and acceptance

Build:

- implementation plan contract;
- typed argv executor;
- source fingerprints;
- checkpointing;
- terminal receipts;
- independent acceptance;
- pickup packets.

Acceptance:

- one sample task survives restart;
- failed receipts are retained;
- a model statement cannot complete a task;
- source drift invalidates proof;
- acceptance is a separate transition.

This phase is the minimum credible autonomous harness. Do not scale agent count before it passes.

### Phase 6 — Sandboxes and security boundaries

Build:

- harness/compute split;
- read-only default sandbox;
- network allowlist;
- secret broker;
- data-flow labels;
- prompt-injection defenses;
- security test fixtures.

Acceptance:

- sandbox cannot reach undeclared paths, network, or credentials;
- prompt injection cannot grant a capability;
- high-risk remote tool output is quarantined;
- capability revocation stops further action;
- security events are correlated.

### Phase 7 — Deterministic automation

Build:

- job registry;
- no-agent hygiene;
- expected artifact contracts;
- semantic outcomes;
- changed-only signatures;
- root-cause rollup;
- quiet-success policy.

Acceptance:

- every enabled job has owner and expected output;
- correct no-change is success;
- high-cost unchanged jobs do not call a model;
- one upstream failure does not generate many false incidents;
- wrappers and schedules are tested.

### Phase 8 — Observability and SLOs

Build:

- correlation envelope;
- event ledger;
- run metrics;
- privacy redaction;
- operator cockpit;
- retention;
- optional OTEL adapter.

Acceptance:

- one correlation ID reconstructs a material run;
- raw content is absent by default;
- missing usage is explicit;
- telemetry failure cannot fake success;
- approval and acceptance record failures block action.

### Phase 9 — Graph and semantic memory

Build:

- local embeddings;
- hybrid retrieval;
- corpus separation;
- query planner;
- dependency graph;
- incremental invalidation;
- contradiction/supersession edges;
- curated wiki.

Acceptance:

- graph paths end at exact owners;
- stale chunks cannot rank as fresh;
- one failed corpus does not suppress healthy results;
- source changes invalidate only dependents;
- semantic similarity never establishes authority.

### Phase 10 — Evaluation and improvement

Build:

- frozen fixtures;
- trial runner;
- outcome and process graders;
- pinned baselines;
- improvement ledger;
- review queue;
- later-outcome checks;
- no-auto-apply guard.

Acceptance:

- trusted executed results exist;
- a candidate cannot promote itself;
- negative-path tests cover every gate;
- closed items have later-outcome evidence;
- proposal volume is not credited as improvement.

### Phase 11 — Bounded multi-agent execution

Build:

- task DAG;
- delegation attenuation;
- helper sandboxes;
- receipt-based fan-in;
- dynamic replanning;
- independent critic.

Acceptance:

- one owner and proof per node;
- no two-writer collision;
- invalid child receipt receives no success credit;
- failed node replans without replaying the full task;
- critic cannot expand authority.

### Phase 12 — External action pilot

Build:

- exact payload approval;
- delegated credential;
- idempotent external executor;
- external outcome verifier;
- compensation path;
- revocation.

Acceptance:

- payload change invalidates approval;
- duplicate delivery is prevented;
- external state is verified;
- operator can pause or revoke;
- no broader credential enters model context.

### Phase 13 — Resilience and portability

Build:

- clean-machine bootstrap;
- backup and restore;
- chaos tests;
- versioned migrations;
- portable paths;
- provider fallback;
- disaster-recovery runbook.

Acceptance:

- sample workflow survives restart and provider outage;
- RTO/RPO targets pass;
- clean install reproduces control planes without secrets;
- restore and rollback are routinely tested.

### Deployment rule

Do not move to the next phase merely because files exist. Move when the current phase has live, trusted acceptance evidence.

---

## 31. Service objectives and scorecard

### 31.1 Truth

| Measure | Target |
|---|---|
| Canonical owner coverage | 100% of material truth families |
| Citation correctness | ≥98% on frozen source-open set |
| Uncaveated stale results | 0 |
| Fabricated execution or citation claims | 0 |
| Superseded claims returned as current | 0 |
| Unresolved contradiction visibility | 100% |

### 31.2 Authority

| Measure | Target |
|---|---|
| Unauthorized protected actions | 0 |
| Owner approval inferred | 0 |
| Capability over-scope incidents | 0 |
| Expired capability accepted | 0 |
| High-impact action with exact payload approval | 100% |
| Revocation test success | 100% |

### 31.3 Execution

| Measure | Target |
|---|---|
| Supported material jobs with complete receipts | ≥95%, then 99% |
| Accepted tasks with source-stable validation | 100% |
| Active write collisions | 0 |
| Duplicate side effects under retry tests | 0 |
| Terminal lanes with proof/archive/tombstone | 100% |
| Recovery from interrupted sample workflow | 100% |

### 31.4 Retrieval

| Measure | Target |
|---|---|
| Exact retrieval p95 | locally defined, typically <100 ms |
| Memory-corpus success | ≥99% |
| Multi-corpus partial-or-better success | ≥95% |
| Stale chunks beyond maintenance SLO | 0 |
| Retrieval results with source/hash/freshness | 100% |
| Secret or unapproved source indexing | 0 |

### 31.5 Automation

| Measure | Target |
|---|---|
| Enabled jobs with contract | 100% |
| Enabled jobs with expected artifacts | 100% |
| Correct guards mislabeled as error | <1%, target 0 |
| No-agent deterministic hygiene | 100% where judgment not required |
| False changed-only skips | 0 on regression suite |
| Root-cause rollup coverage | 100% for dependency blocks |

### 31.6 Validation

| Measure | Target |
|---|---|
| Critical gates with negative-path tests | 100% |
| Authority/concurrency decision coverage | ≥85% branch or justified equivalent |
| Escaped defects | downward trend by task class |
| Validation p50/p95 | downward without defect regression |
| Independent review for required classes | 100% |
| Rollback drill pass rate | 100% for release candidates |

### 31.7 Efficiency

| Measure | Target |
|---|---|
| Unchanged expensive jobs invoking model | 0 |
| Per-task context size | task-class budget |
| First-pass acceptance | tracked by comparable class |
| Retry tax | downward trend |
| Operator attention per accepted workflow | downward trend |
| Actual/estimated cost labeling accuracy | 100% |
| Supported jobs with trusted usage or reason unavailable | ≥95% |

### 31.8 Learning

| Measure | Target |
|---|---|
| High-priority overdue improvements | 0 |
| Proposal-to-audited-closure conversion | upward trend |
| Reopened defect rate | downward trend |
| Baseline/candidate cohort match | 100% |
| Auto-applied governance changes | 0 |
| Promoted route with later-outcome monitoring | 100% |

### 31.9 Security and privacy

| Measure | Target |
|---|---|
| Raw content in default telemetry | 0 |
| Secrets in model context | 0 |
| Sandbox escape tests | 100% pass |
| Prompt-injection action success | 0 on maintained attack set |
| Data-flow violations | 0 |
| Connector activation without security evaluation | 0 |

### 31.10 Autonomy

| Measure | Target |
|---|---|
| Workflow with declared autonomy envelope | 100% of autonomous workflows |
| Autonomous action outside envelope | 0 |
| Pause/cancel/revoke test | 100% |
| Promotion with complete evidence | 100% |
| High-impact autonomous workflow without human governance | 0 |
| Intervention latency | within domain SLO |

### 31.11 Scorecard rules

- Report numerator and denominator.
- Segment by task class and authority class.
- Show missing-data rate.
- Do not pool retries with first-pass results.
- Do not call estimated cost actual billing.
- Do not score invalid telemetry as success.
- Show trend and confidence interval when trial counts permit.
- Retain representative failure cases.

---

## 32. Failure taxonomy and prescribed response

### 32.1 Truth failures

#### Hallucinated fact

Response:

- retract;
- identify unsupported claim;
- open authoritative source;
- correct durable record;
- add evaluation fixture.

#### Stale truth leakage

Response:

- quarantine stale unit;
- invalidate dependents;
- repair freshness owner;
- test retrieval exclusion.

#### Authority confusion

A derived report or semantic hit is treated as canon.

Response:

- route to owner;
- label derived surface;
- add owner-class check;
- repair duplicate instruction.

#### Contradiction blending

Response:

- preserve both claims;
- mark conflict;
- resolve by owner or disclose unresolved state;
- add supersession relationship.

### 32.2 Execution failures

#### False completion

Response:

- return state to pending or blocked;
- require terminal receipt;
- audit sibling workflows for same acceptance bypass.

#### Environment drift

Response:

- reject proof;
- pin interpreter and dependencies;
- recreate environment;
- rerun from stable snapshot.

#### Duplicate side effect

Response:

- contain;
- compensate if possible;
- add idempotency business key;
- test crash-after-effect-before-receipt.

#### Partial write

Response:

- stop writers;
- restore snapshot or complete transaction;
- validate integrity;
- improve atomic boundary.

#### No-progress loop

Response:

- stop;
- emit blocker packet;
- classify repeated action;
- replan or escalate.

### 32.3 Concurrency failures

#### Write collision

Response:

- reject newer lease;
- name overlap;
- re-scope or sequence work;
- verify no partial mutation.

#### Expired lease with active process

Response:

- revoke capability;
- isolate process;
- inspect changes;
- recover through a new lane.

#### Lost proof

Response:

- locate archive;
- verify hash;
- create approved tombstone only when retention permits;
- reject unverifiable historical acceptance where material.

### 32.4 Validation failures

#### Green-only tests

Response:

- add failing upstream fixture;
- test malformed and missing inputs;
- inspect every rollup for silent downgrade.

#### Validator deadlock

A producer cannot refresh an artifact because its own validator rejects stale state before regeneration.

Response:

- separate preflight from repair path;
- add controlled regeneration mode;
- retain last-known-good;
- test stale-to-fresh recovery.

#### Overbroad validation

Response:

- build dependency-aware bundle;
- cache immutable proof;
- preserve all tests for shared-contract changes.

#### Under-validation

Response:

- classify risk correctly;
- trace consumers;
- add integration/security proof.

### 32.5 Security failures

#### Prompt injection

Response defined in Runbook 29.10.

#### Credential exposure

Response:

- revoke and rotate;
- identify exposure window;
- inspect logs and external use;
- remove raw error paths;
- replace direct secret with brokered capability.

#### Confused deputy

Response:

- bind capability to delegated user, task, target, and action;
- block cross-context use;
- add authorization tests.

#### Tool schema poisoning

Response:

- disable tool version;
- verify signed/approved schema;
- revalidate descriptions as untrusted;
- inspect prior runs.

### 32.6 Observability failures

#### Missing correlation

Response:

- mark analytical coverage incomplete;
- add shared trace ID;
- do not infer causal linkage from timestamps alone.

#### Telemetry drops

Response:

- preserve user response when ordinary telemetry only;
- alert;
- classify coverage;
- block protected actions when approval or acceptance evidence is affected.

#### Raw-content leak

Response:

- stop collector;
- quarantine data;
- apply retention/deletion policy;
- rotate secrets if needed;
- patch collector redaction and tests.

### 32.7 Learning failures

#### Proposal backlog theater

Response:

- prioritize closure;
- cap new candidates;
- escalate overdue high-priority items;
- measure proposal-to-outcome conversion.

#### Bad promotion

Response:

- roll back;
- restore baseline;
- inspect cohort mismatch and safety regression;
- amend promotion gate.

#### Reflection poisoning

Response:

- remove unsupported reflection from durable memory;
- require outcome linkage and scope;
- test retrieval downranking.

---

## 33. Anti-patterns

The harness MUST actively reject these patterns.

### 33.1 Prompt-only governance

A long system prompt is not an enforcement layer.

### 33.2 One giant agent

One agent with all tools, all secrets, all files, and all authority is an incident waiting to happen.

### 33.3 Agent swarm by default

More agents increase coordination cost before they increase intelligence.

### 33.4 Vector database as truth

Similarity finds related text. It does not determine correctness or authority.

### 33.5 Whole-repository scans

Broad scans waste context, hide ownership, and make every repair expensive.

### 33.6 Whole-document retrieval

Returning a full document for one relevant section creates context noise and citation ambiguity.

### 33.7 Derived packet becomes canon

A generated packet can be fresh-looking and wrong. Owners outrank summaries.

### 33.8 Direct canonical writes

Bypassing the gateway bypasses provenance, versioning, validation, and rollback.

### 33.9 Infinite or vague retries

Retrying an unclassified failure wastes money and can duplicate side effects.

### 33.10 Exit code equals completion

An exit code without captured command, environment, output, source snapshot, and acceptance is weak evidence.

### 33.11 Model grades itself

The producer should not be the sole authority on whether its work is correct.

### 33.12 Scheduler green equals useful work

A job can exit successfully while producing stale, absent, or invalid artifacts.

### 33.13 Telemetry equals truth

Observability shows behavior, not correctness.

### 33.14 Approval by implication

A user asking for analysis does not approve mutation or external action.

### 33.15 Broad credentials

A general token turns a narrow model mistake into a broad security incident.

### 33.16 Secrets in context

Models and sandboxes should receive capabilities, not vault contents.

### 33.17 Content-capturing telemetry by default

Raw prompts and tool payloads create unnecessary privacy and security risk.

### 33.18 Cache without authority or invalidation

A fast stale answer is worse than a slower correct one.

### 33.19 Tests only on healthy inputs

This misses the exact failures gates exist to expose.

### 33.20 Validation during active writes

Testing a moving target can produce false proof.

### 33.21 Automatic self-promotion

A route, prompt, model, or skill cannot evaluate and promote itself.

### 33.22 Self-modifying constitution

The system’s authority boundaries must remain external to the system’s improvement loop.

### 33.23 AGI label inflation

Tool use, persistence, parallelism, or benchmark success do not by themselves establish AGI.

### 33.24 Infrastructure cosplay

Do not deploy a graph database, distributed trace stack, queue, Kubernetes cluster, or formal workflow engine before a real measured need exists.

### 33.25 Historical residue as architecture

Copy invariants, not every old script, warning, temporary packet, route, or workflow.

---

## 34. Design-review checklist

### Constitution

- [ ] Is the priority order explicit?
- [ ] Is truth above helpfulness?
- [ ] Is authority separate from capability?
- [ ] Are high-impact stop lines explicit?
- [ ] Can the model change constitutional rules? It must not.

### Truth

- [ ] Does every material truth family have one owner?
- [ ] Are derived views visibly non-authoritative?
- [ ] Are claims linked to source, time, freshness, and status?
- [ ] Are contradiction and supersession represented?
- [ ] Can a current answer open its exact source?

### Startup and context

- [ ] Is bootstrap small and pointer-based?
- [ ] Does startup begin with machine-readable state?
- [ ] Is context selected just in time?
- [ ] Are handoffs bounded?
- [ ] Can a session resume without full chat history?

### Retrieval

- [ ] Is the source registry approved?
- [ ] Are sections indexed rather than whole documents?
- [ ] Are path, lines, hash, freshness, and authority preserved?
- [ ] Does degraded retrieval label itself?
- [ ] Can stale results be excluded?
- [ ] Does source-open verification occur before consequential claims?

### Authority

- [ ] Does every action have an authority class?
- [ ] Are capabilities narrow and expiring?
- [ ] Are child grants attenuated?
- [ ] Are approvals bound to exact payload digests?
- [ ] Can capabilities be revoked?
- [ ] Is owner approval never inferred?

### Execution

- [ ] Is work governed by a state machine?
- [ ] Is the plan hash pinned?
- [ ] Are phases small and independently provable?
- [ ] Are loops bounded?
- [ ] Are retries classified?
- [ ] Are side effects idempotent?

### Concurrency

- [ ] Does every writer have a lane?
- [ ] Are collision checks performed at plan and lease?
- [ ] Are protected surfaces denied by default?
- [ ] Do leases expire?
- [ ] Can tests defer during active overlapping writes?
- [ ] Does completion require real proof paths?

### Sandboxes and security

- [ ] Is the trusted harness outside model-directed compute?
- [ ] Is read-only/no-network/no-secret the default?
- [ ] Are credentials brokered?
- [ ] Is untrusted content separated from instructions?
- [ ] Are data flows classified?
- [ ] Are prompt-injection and confused-deputy tests maintained?

### Automation

- [ ] Is deterministic hygiene no-agent?
- [ ] Does each job have expected artifacts?
- [ ] Are outcomes semantic?
- [ ] Are unchanged inputs skipped safely?
- [ ] Are failures rolled up to root cause?
- [ ] Is green behavior quiet?

### Evidence

- [ ] Does every material run have a correlation ID?
- [ ] Are receipts complete?
- [ ] Are failed receipts retained?
- [ ] Is source stability recorded?
- [ ] Is acceptance separate from execution?
- [ ] Is proof retained or tombstoned?

### Validation

- [ ] Is validation proportional to risk?
- [ ] Are negative paths mandatory?
- [ ] Are authority and concurrency gates tested deeply?
- [ ] Is independent review used where required?
- [ ] Are outcome and process both evaluated?
- [ ] Are model/harness evaluations repeated?

### Observability and privacy

- [ ] Is metadata-only the default?
- [ ] Are missing counters explicit?
- [ ] Can one correlation ID reconstruct a run?
- [ ] Is telemetry prevented from implying truth or approval?
- [ ] Is content capture separately authorized?
- [ ] Are retention and redaction tested?

### Learning

- [ ] Are candidates evidence-linked?
- [ ] Is the baseline pinned?
- [ ] Is apply human- or authority-gated?
- [ ] Is later outcome measured?
- [ ] Is recurrence tracked?
- [ ] Can the system change its own authority? It must not.

### Autonomy

- [ ] Is autonomy defined per workflow?
- [ ] Does the workflow have an envelope?
- [ ] Can it pause, cancel, revoke, and recover?
- [ ] Has prompt-injection resistance been tested?
- [ ] Are receipts and later outcomes complete?
- [ ] Was autonomy earned from evidence rather than declared?

### Efficiency

- [ ] Is unnecessary work eliminated before optimization?
- [ ] Are exact and deterministic routes first?
- [ ] Are context and output bounded?
- [ ] Are route comparisons matched?
- [ ] Are retries included in cost?
- [ ] Does each added component justify its complexity?

A critical unchecked item means the workflow is not ready for higher autonomy.

## 35. Minimum viable core

A new harness SHOULD begin with the following, and nothing broader until these work end to end:

1. one lean governance and agent contract;
2. one canonical SQLite gateway;
3. one deterministic startup brief;
4. one task and workflow contract;
5. one lane register and write-admission gate;
6. one approved exact/FTS retrieval index with section citations;
7. one sandbox profile;
8. one implementation plan and pickup packet;
9. one terminal receipt and acceptance record;
10. one no-agent scheduled integrity job;
11. one metadata-only correlation ledger;
12. one negative-path test suite;
13. one backup and rollback path;
14. one sample workflow that survives interruption.

The sample workflow MUST prove:

```text
request
-> task classification
-> exact retrieval
-> plan
-> capability
-> lease
-> sandbox execution
-> artifact
-> validator
-> acceptance
-> continuity update
-> terminal receipt
-> restart
-> successful resume or confirmed closure
```

Until this chain works, adding more models, agents, tools, graphs, or automation increases surface area without establishing reliability.

---

## 36. Launch gates

### Gate G0 — Governance

Pass only when:

- constitutional owner exists;
- authority classes and stop lines are explicit;
- model cannot amend them;
- user and actor identities are defined.

### Gate G1 — Truth

Pass only when:

- canonical owners are named;
- source-open claims work;
- derived state is labeled;
- freshness and supersession exist.

### Gate G2 — Mutation

Pass only when:

- every material write passes a gateway;
- capabilities and leases are enforced;
- rollback is available;
- direct bypass tests fail.

### Gate G3 — Evidence

Pass only when:

- receipts are complete;
- failed receipts persist;
- acceptance is separate;
- correlation spans the lifecycle.

### Gate G4 — Recovery

Pass only when:

- a running job survives forced interruption;
- idempotency prevents duplicate effects;
- pickup packet resumes boundedly;
- backup and restore pass.

### Gate G5 — Security

Pass only when:

- sandbox isolation is proven;
- secret brokering works;
- injection cannot grant authority;
- data-flow and connector tests pass.

### Gate G6 — Automation

Pass only when:

- jobs are deterministic where possible;
- expected artifacts and semantic outcomes exist;
- changed-only gates have false-skip tests;
- failure is quiet only when genuinely healthy.

### Gate G7 — Evaluation

Pass only when:

- task fixtures are frozen;
- negative paths cover gates;
- repeated trials exist for stochastic behavior;
- model and harness are graded together.

### Gate G8 — Learning

Pass only when:

- candidates are evidence-linked;
- baselines are pinned;
- application is externally gated;
- later outcomes and recurrence are measured.

### Gate G9 — Higher autonomy

Pass only when:

- the target workflow has repeated accepted evidence;
- intervention and revocation are tested;
- complete identity and receipt coverage exists;
- no unresolved authority or security incident remains.

A warning gate does not automatically block low-risk advisory work. A failed gate MUST block the capability that depends on it.

---

## 37. Doctrine governance

### 37.1 Ownership

This doctrine MUST have one human governance owner or governing body.

The owner controls:

- constitutional invariants;
- authority classes;
- approval rules;
- data classifications;
- autonomy promotion;
- exception process;
- doctrine version.

### 37.2 Change process

Governance SHOULD use a lifecycle risk process that maps, measures, manages, and reviews risks rather than treating safety as a one-time launch check. [R11]

A doctrine change requires:

1. change proposal;
2. reason and evidence;
3. affected contracts and consumers;
4. risk and threat analysis;
5. migration plan;
6. tests;
7. independent review;
8. owner approval;
9. version increment;
10. rollout and rollback;
11. post-change outcome review.

### 37.3 Exception process

An exception MUST be:

- explicit;
- narrow;
- time-bounded;
- owned;
- justified;
- logged;
- revocable;
- reviewed after use.

“Urgent” does not mean “uncontrolled.”

### 37.4 Versioning

Use semantic doctrine versioning:

- major — changes authority, constitutional priority, or trust model;
- minor — adds compatible controls or operating procedures;
- patch — clarifies wording without changing behavior.

Every runtime SHOULD record the doctrine version and hash in its receipts.

### 37.5 Periodic review

Review at least:

- after a material incident;
- before increasing autonomy;
- after a major model or provider change;
- after adding high-impact tools;
- after an architectural migration;
- on a regular governance cadence.

### 37.6 Simplification review

Every review SHOULD identify:

- duplicate owners;
- stale controls;
- unused tools;
- unmeasured components;
- old model compensations;
- oversized bootstrap content;
- unnecessary agent roles;
- derived artifacts with no consumer.

Deletion is an architectural improvement when evidence shows the component no longer earns its cost.

---

## 38. Research provenance

### 38.1 Internal operating evidence

This doctrine synthesizes proven or strongly motivated patterns from these supplied workspace studies:

- **Veritas Workspace Harness Replication, Efficiency, and Agentic AI Readiness Research — 2026-08-23.**
- **Leveraging the Efficiens Workspace: Harness Architecture, Measured Efficiencies, and a Replication Blueprint — 2026-08-23.**

Source-derived mechanisms include:

- the agent operating system framing;
- truth, recall, execution, and assurance separation;
- deterministic routing before model work;
- durable files and structured canonical state;
- exact write leases;
- Main or Acceptance Authority integration;
- source-open retrieval;
- section-scoped indexing;
- freshness and stale-source handling;
- canonical database gateways;
- transactional version history;
- argv-based acceptance;
- before/after fingerprints;
- bounded pickup packets;
- no-agent scheduled hygiene;
- semantic job outcomes;
- metadata-only telemetry;
- human-gated improvement;
- negative-path testing;
- evidence-gated autonomy.

This doctrine turns those mechanisms into one normative greenfield operating guide. It does not import the historical file volume, domain-specific residue, or current-state claims from either workspace.

### 38.2 External research contribution

External research informed or reinforced provisions on:

- choosing simple workflows before unconstrained agents;
- long-running session continuity;
- context engineering;
- separation of model reasoning from sandbox compute;
- evaluation of outcomes and trajectories;
- operational autonomy and intervention;
- removal of stale harness scaffolding;
- guardrails and approval boundaries;
- prompt-injection and agent-hijacking risk;
- agent identity and authorization;
- AGI capability dimensions;
- task-completion horizons;
- durable workflow replay and idempotency;
- provenance;
- agent-computer interface design;
- MCP security;
- GenAI observability;
- AI risk management.

### 38.3 Original synthesis

The following are prescriptive synthesis in this doctrine rather than claims copied verbatim from one source:

- the complete six-plane architecture;
- the authority-class system;
- the capability-token envelope;
- the combined execution state machine;
- the autonomy ladder;
- the launch gates;
- the integrated claim-state protocol;
- the full set of service objectives;
- the repository and contract blueprint;
- the unified runbooks and failure taxonomy.

These choices are proposed architecture. They require validation in the environment where the harness is deployed.

---

## 39. Research references

[R1] Anthropic, [Building Effective AI Agents](https://www.anthropic.com/engineering/building-effective-agents). Practical distinction between workflows and agents; recommends simple, composable patterns before adding autonomy.

[R2] Anthropic, [Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents). Durable progress artifacts, initializer/incremental-agent structure, and handoff across discrete context windows.

[R3] Anthropic, [Effective Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents). Treats context as finite and emphasizes curating the highest-value tokens.

[R4] Anthropic, [Scaling Managed Agents: Decoupling the Brain from the Hands](https://www.anthropic.com/engineering/managed-agents). Separates reasoning, execution environments, and session state.

[R5] Anthropic, [Demystifying Evals for AI Agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents). Covers agent evaluation, trajectories, outcomes, graders, and repeated trials.

[R6] Anthropic, [Measuring AI Agent Autonomy in Practice](https://www.anthropic.com/research/measuring-agent-autonomy). Frames autonomy operationally and emphasizes monitoring and intervention.

[R7] Anthropic, [Harness Design for Long-Running Application Development](https://www.anthropic.com/engineering/harness-design-long-running-apps). Highlights that harness components encode assumptions about model limitations and should be revisited.

[R8] OpenAI, [Agents SDK Guide](https://developers.openai.com/api/docs/guides/agents). Agent loops, state, tools, handoffs, guardrails, tracing, and resumable approval flows.

[R9] OpenAI, [Sandbox Agents](https://developers.openai.com/api/docs/guides/agents/sandboxes). Distinguishes the trusted harness control plane from sandbox execution.

[R10] NIST, [Strengthening AI Agent Hijacking Evaluations](https://www.nist.gov/news-events/news/2025/01/technical-blog-strengthening-ai-agent-hijacking-evaluations). Describes indirect prompt injection and the need for adaptive, repeated attack evaluation.

[R11] NIST, [Artificial Intelligence Risk Management Framework: Generative Artificial Intelligence Profile](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.600-1.pdf). Cross-sector risk-management guidance spanning governance, measurement, management, provenance, testing, and incident disclosure.

[R12] NIST NCCoE, [Accelerating the Adoption of Software and AI Agent Identity and Authorization](https://www.nccoe.nist.gov/sites/default/files/2026-02/accelerating-the-adoption-of-software-and-ai-agent-identity-and-authorization-concept-paper.pdf). Emerging identity, authentication, authorization, and audit considerations for agents.

[R13] Google DeepMind, [Levels of AGI for Operationalizing Progress on the Path to AGI](https://deepmind.google/research/publications/66938/). Separates performance, generality, and autonomy.

[R14] Google DeepMind, [Measuring Progress Toward AGI: A Cognitive Framework](https://blog.google/innovation-and-ai/models-and-research/google-deepmind/measuring-agi-cognitive-framework/). Multidimensional cognitive evaluation.

[R15] METR, [Task-Completion Time Horizons of Frontier AI Models](https://metr.org/time-horizons/). Reliability as a function of human task difficulty and duration.

[R16] OpenTelemetry, [Inside the LLM Call: GenAI Observability with OpenTelemetry](https://opentelemetry.io/blog/2026/genai-observability/). GenAI telemetry semantics and the sensitivity of opt-in content capture.

[R17] Temporal, [Event History and Deterministic Workflow Replay](https://docs.temporal.io/encyclopedia/event-history/event-history-java). Deterministic workflow decisions reconstructed from durable event history.

[R18] Temporal, [Activity Definition and Idempotency](https://docs.temporal.io/activity-definition). Why retryable side-effecting activities should be idempotent and granular.

[R19] SLSA, [Provenance](https://slsa.dev/spec/v1.2/provenance). Verifiable information about where, when, and how artifacts are produced.

[R20] SQLite, [Atomic Commit](https://www.sqlite.org/atomiccommit.html) and [Write-Ahead Logging](https://www.sqlite.org/wal.html). Transaction atomicity, crash behavior, snapshot reads, and WAL concurrency characteristics.

[R21] Model Context Protocol, [Specification](https://modelcontextprotocol.io/specification/2026-07-28), [Authorization](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/authorization), and [Security Best Practices](https://modelcontextprotocol.io/docs/2026-07-28/tutorials/security/security_best_practices). Standardized tool/context integration plus authorization and confused-deputy considerations.

[R22] Yao et al., [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629). Interleaves reasoning and environmental action.

[R23] Yang et al., [SWE-agent: Agent-Computer Interfaces Enable Automated Software Engineering](https://arxiv.org/abs/2405.15793). Shows that purpose-built agent-computer interfaces materially affect agent performance.

[R24] Shinn et al., [Reflexion: Language Agents with Verbal Reinforcement Learning](https://arxiv.org/abs/2303.11366). Uses outcome-linked linguistic reflection, while not making reflection itself proof.

[R25] OWASP, [Top 10 for Agentic Applications 2026](https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/). Operational security-risk framework for agents that plan and act.

[R26] Debenedetti et al., [AgentDojo](https://arxiv.org/abs/2406.13352). Dynamic prompt-injection tasks, defenses, and adaptive attacks for tool-using agents.

[R27] OpenAI, [Guardrails and Human Review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals). Automatic checks plus pause/resume approval decisions for sensitive actions.

[R28] OpenAI, [Evaluate Agent Workflows](https://developers.openai.com/api/docs/guides/agent-evals). End-to-end trace grading for tool choice, handoffs, guardrails, and regressions.

[R29] OpenAI, [Building MCP Servers for Plugins and API Integrations](https://developers.openai.com/api/docs/mcp). Consequential write approvals and prompt-injection/data-exfiltration considerations around remote tools.

### Reference-use rule

Research references are not runtime authority. Runtime decisions MUST route to current applicable policy, current official specifications, and the harness’s canonical owners. External guidance changes over time and MUST be freshness-checked before it is used for a consequential deployment decision.

---

## 40. Final doctrine

The model is probabilistic. The control plane must not be.

A trustworthy autonomous system is not created by giving an LLM more tools, a larger context window, more agents, or a more persuasive system prompt. It is created by surrounding the model with machinery that makes truth, authority, state, evidence, recovery, and stopping conditions explicit.

The operating standard is:

```text
Truth before fluency.
Determinism before model discretion.
Exact sources before semantic confidence.
Least authority before convenience.
No action without identity and scope.
No completion without proof.
No acceptance by the producer alone.
No autonomy without interruption and rollback.
No self-improvement without a pinned baseline and external governance.
No complexity without measured recurring value.
```

A strong harness lets the model reason broadly while forcing action to remain narrow, inspectable, recoverable, and honest.

That is the target: not an agent that merely appears intelligent, but an operating system in which increasingly capable intelligence can be useful without being allowed to invent truth, infer authority, hide failure, or outrun control.
