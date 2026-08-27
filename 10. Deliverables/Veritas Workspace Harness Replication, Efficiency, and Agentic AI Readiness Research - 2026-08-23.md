# Veritas Workspace Harness Replication, Efficiency, and Agentic AI Readiness

## A non-audit research report and copy blueprint

**Prepared:** 2026-08-23, Phoenix, Arizona  
**Workspace:** Veritas/OpenClaw 2026.7.1-2  
**Purpose:** Explain how the proprietary workspace is being leveraged, identify the efficiencies already implemented, define what a new harness should copy, and map the additional work required to reach a defensible Level 10 for efficiency and agentic-AI readiness.

This is research and architecture guidance. It is not an audit, compliance opinion, security certification, autonomy approval, or claim that this workspace is AGI or ASI. All readiness claims remain local, review-only, and bounded by the workspace's existing authority rules.

---

## Executive summary

The Veritas workspace is not primarily a collection of prompts. It is a file-backed agent operating system.

Its proprietary value comes from the way it combines:

1. durable identity, mission, authority, and operating doctrine;
2. layered memory with exact retrieval, semantic retrieval, a compiled wiki, local vector indexes, and graph-assisted routing;
3. explicit workflow, cron, lane, artifact, validation, and closeout contracts;
4. structured truth in Markdown, JSON, SQLite, and append-only ledgers;
5. model-free routing before model work, with bounded model lanes only when they add value;
6. exact write leases, checkpoints, proof artifacts, and Main-session acceptance;
7. local, metadata-only OTEL observability with privacy stop lines;
8. scheduled automation that separates artifact freshness from scheduler status;
9. a self-improvement conveyor that can detect, classify, prioritize, and propose improvements without silently applying them; and
10. strong separation between research, recommendation, approval, mutation, and execution.

That combination is the real harness. A new harness should copy the control logic and contracts, not copy the workspace's accumulated file volume.

The current system is already advanced. It can recover from interrupted sessions, route named workflows, retrieve durable memory, produce review packets, coordinate concurrent lanes, validate changed surfaces, monitor cron and OTEL state, maintain append-only improvement history, and prevent many forms of accidental authority expansion. The current AGI-harness packet classifies it as `partial_ready_review_only_with_warnings`, with three passing gates, four warning gates, and no failed gates. The broader AGI OS evaluation has nine passing gates, eight warning gates, and no failed gates.

The most important current weakness is not the absence of more tools or more autonomous agents. It is incomplete end-to-end operational proof:

- dynamic `memory_search` works for the memory corpus, but combined all-corpus retrieval is degraded and the session-transcript corpus timed out during this research;
- the local semantic-memory cache is functional and uses Ollama's `nomic-embed-text` with FTS support, but one transitive source family currently leaves 672 chunks stale;
- the protected `job -> dispatch -> provider run -> usage receipt -> validator -> Main acceptance` chain has a verified no-install candidate, but the first live complete receipt has not been produced;
- implementation-token attribution still shows zero implementation token events against 597 gaps;
- helper-lane receipt verification is not yet strong enough to count helpers as fully auditable contributors;
- cron has a good contract and freshness spine, but its current snapshot still contains 15 blocked jobs and eight visible last-run scheduler exceptions;
- the evaluation contracts are ahead of the execution evidence: 100 frontier fixtures and 300 assignments are prepared, but no fully verified result rows exist;
- the improvement loop creates useful proposals, but overdue follow-through and closure maturity remain weaker than proposal generation.

The correct Level-10 path is therefore:

```text
reliable retrieval
-> complete correlation and receipts
-> semantic cron outcomes
-> machine-readable contract/dependency graph
-> outcome-linked evaluations
-> bounded transactional action engine
-> measured route optimization
-> resilient, sandboxed multi-agent execution
```

The directional research estimate is approximately **7.5/10 overall**, with governance and authority controls closer to 9/10, but execution attribution, evaluation evidence, retrieval reliability, and measured cost efficiency closer to 5.5-7/10. This is a maturity estimate for planning, not an audit score.

---

## 1. Scope, method, and evidence standard

### 1.1 Scope

This report covers:

- workspace architecture and leverage;
- memory, semantic search, vector retrieval, graph retrieval, and wiki retrieval;
- OTEL and metadata-only observability;
- cron automation and freshness contracts;
- task, workflow, lane, artifact, validation, and authority contracts;
- routing, checkpoints, multi-agent orchestration, and Main-session acceptance;
- structured truth, SQL/JSON support, artifact indexing, and provenance;
- evaluation, learning, prompt-book, and improvement loops;
- implemented efficiency mechanisms;
- a practical replication blueprint for a new harness;
- a Level-10 opportunity roadmap and measurable acceptance criteria.

It does not authorize or perform:

- runtime, gateway, collector, config, auth, credential, channel, or scheduler mutation;
- plugin installation or Skill Workshop application;
- archive, deletion, or destructive cleanup;
- finance-canon, portfolio, account, paper, live, or capital action;
- external delivery;
- raw prompt, response, tool-payload, secret, header, customer, or account-data capture.

### 1.2 Research method

The research used the workspace's own thin routing surfaces first, then opened exact owner and proof artifacts. Sources included doctrine files, the Startup Truth Index, workflow and orchestration standards, current readiness packets, memory probes, vector and graph packets, cron control and freshness packets, OTEL control, token and coding-outcome packets, improvement and prompt-book packets, and the Harness V2 continuity plan.

Generated `tmp/` packets are treated as timestamped proof and routing surfaces, not as canonical authority. Current claims are tied to the packet timestamps stated in this report. Where a live probe and an older packet disagree, the newer live probe or owner surface is identified explicitly.

### 1.3 Evidence quality

Three evidence classes are used:

| Evidence class | Meaning | Examples |
|---|---|---|
| Owner doctrine | Defines identity, authority, operating rules, or canonical policy | `SOUL.md`, `AGENTS.md`, `USER.md`, `TOOLS.md` |
| Durable owner state | Owns workflow, continuity, or structured truth | `state/workflows/`, `state/cron-contracts/`, finance SQLite, project continuity notes |
| Derived proof | Reports, routes, validates, or summarizes owner state | `tmp/agi-harness-readiness-packet.json`, `tmp/cron-control-packet.json`, `tmp/otel-ops-control.json` |

The harness's recurring rule is important: **routing proof is not authority**. A clean generated packet can support a decision, but it does not itself authorize a mutation, external action, or execution.

---

## 2. What the proprietary harness actually is

The workspace's proprietary setup is best understood as a contract-driven operating system around a capable model.

The model supplies reasoning and synthesis. The workspace supplies:

- identity;
- memory;
- truth ownership;
- context selection;
- tool and skill routing;
- action boundaries;
- workflow state;
- concurrency control;
- observability;
- validation;
- recovery;
- outcome measurement;
- and the rules for when the model must stop.

This division matters. Model intelligence without a harness is episodic. It can answer a question, but it does not reliably know which source owns truth, whether the data is fresh, whether an action is authorized, what another session changed, which validator proves completion, or how to recover after interruption.

The Veritas harness turns a general model into a persistent operating partner by making those conditions explicit and durable.

### 2.1 The core operating loop

```text
user objective
-> task-intake and authority classification
-> thin startup and memory retrieval
-> exact owner/source routing
-> workflow and lane contract
-> model-free or bounded model execution
-> proof artifact and validator
-> Main-session acceptance
-> queue/continuity update
-> OTEL, token, outcome, and improvement evidence
-> later review, repair proposal, or guarded promotion
```

Each arrow has an owning file, script, packet, or validator. That is the key difference between a workspace with many files and an actual harness.

### 2.2 Four control planes

The workspace can be simplified into four interacting control planes:

1. **Truth plane** — doctrine, canonical notes, SQL/JSON state, source lineage, and exact owner artifacts.
2. **Recall plane** — daily memory, durable memory, semantic memory, wiki retrieval, vector indexes, and graphs.
3. **Execution plane** — workflow routing, implementation routing, skills, cron, lanes, checkpoints, tools, and agents.
4. **Assurance plane** — validators, OTEL, token and outcome ledgers, QA, release contracts, rollback, and authority stop lines.

The assurance plane is not an afterthought. It is what prevents the other three planes from turning into automation theater.

---

## 3. Layered architecture of the current workspace

| Layer | Current implementation | Why it improves leverage | What a new harness must copy |
|---|---|---|---|
| Identity and mission | `SOUL.md` and `IDENTITY.md` | Gives every session the same purpose and non-negotiable boundaries | A short canonical identity/mission contract |
| Human preferences | `USER.md` | Converts generic assistance into an owner-specific operating relationship | Explicit communication, timezone, risk, and approval preferences |
| Runtime map | `TOOLS.md` | Prevents environment rediscovery and unsafe assumptions | Exact platform, binary, route, and mutation rules |
| Session operating doctrine | `AGENTS.md` | Defines boot, orchestration, validation, continuity, and response behavior | One authoritative agent operating contract |
| Thin startup | `06. Playbooks/Startup Truth Index.md` and cached status front door | Reduces boot context and avoids broad scans | A T0 boot path with drilldown rules |
| Task intake | `skills/task-intake-contract/SKILL.md` | Converts vague requests into objective, authority, stop lines, and proof | A machine- and human-readable intake schema |
| Durable memory | `MEMORY.md` and `memory/YYYY-MM-DD.md` | Preserves decisions and chronological continuity | Separate durable rules from daily history |
| Semantic memory | Dynamic `memory_search` plus local vector SQLite/FTS | Recalls concepts without reading every file | Local embeddings, citations, freshness, and fallback |
| Compiled knowledge | `wiki/` and `state/wiki-retrieval/` | Gives cold sessions a curated synthesis and source map | A synthesis layer that routes back to owners |
| Structured truth | JSON, SQLite, registries, append-only ledgers | Makes state queryable and validator-friendly | Schemas, provenance, and explicit owner boundaries |
| Workflow routing | `workflow_router.py` and `state/workflows/` | Makes named work resumable without reconstructing chat | One route registry and capsule format |
| Skill routing | Active `skills/*/SKILL.md` packages | Loads procedures only when relevant | Small, versioned, governed skills |
| Implementation routing | `project_implementation_router.py` | Chooses deterministic work before expensive model work | A versioned route policy with fail-closed fallback |
| Concurrency | `concurrent_lane_manager.py` | Prevents two writers and makes handoffs recoverable | Exact write leases and terminal proof |
| Scheduled automation | Cron registry, contracts, freshness spine, control packet | Separates timing, artifacts, freshness, and escalation | Per-job expected outputs and semantic status |
| Observability | Local OTEL plus SQLite and metadata ledgers | Makes operations inspectable without raw-content capture | Correlation IDs, local retention, privacy fields |
| Validation and release | Changed-file routing, validator bundles, release contracts | Scales proof to risk and reduces unnecessary validation | Risk-budgeted tests, rollback, and acceptance |
| Learning loop | WF74/WF88 packets, improvement ledger, prompt book, eval gates | Converts friction into reviewable improvements | Detection, evidence, proposal, outcome, and no-auto-apply gates |
| Authority policy | Repeated false flags and stop lines in every layer | Prevents a clean technical result from becoming unauthorized action | Capability and action classes enforced at every boundary |

The design is intentionally repetitive at authority boundaries. Repeating `owner_approval_inferred=false` across independent artifacts is not elegant, but it is safer than relying on one global prompt that downstream systems may omit.

---

## 4. How the workspace is leveraged in practice

### 4.1 Files are the durable operating surface

Chat is transient. Files are continuity.

The workspace keeps:

- daily progress in `memory/YYYY-MM-DD.md`;
- durable cross-session rules in `MEMORY.md`;
- active queue state in workflow surfaces;
- resumable detail in project continuity notes;
- structured state in JSON and SQLite;
- generated proof in `tmp/`;
- reusable procedures in skills and playbooks;
- long-running job state in `state/long-work-jobs/`.

This lets a restarted or compacted session recover from shared state instead of relying on hidden model memory.

### 4.2 Main session is the truth integrator

The Main session is designed to:

- classify the request;
- choose sources;
- control scope and authority;
- decide the execution route;
- integrate helper outputs;
- resolve contradictions;
- accept or reject completion;
- update the queue and continuity;
- communicate the final judgment.

Helpers can inspect, draft, compare, implement bounded changes, or validate. They do not own final queue state, canonical conflict resolution, or final acceptance.

That separation is a major efficiency mechanism. It allows parallel work without losing one accountable integrator.

### 4.3 Generated packets compress state

The workspace has deliberately created compact front doors:

- status card;
- startup packet;
- future-session packet;
- workflow capsules;
- PM control packet;
- cron control packet;
- artifact index;
- wiki bootstrap proof;
- readiness packets.

These packets compress large operating surfaces into a few typed summaries. A shallow request can be answered from the front door. Material work follows hashes, source paths, and drilldown fields to exact owners.

The efficiency gain is context selectivity: the model reads what is needed for the decision instead of loading the entire workspace.

### 4.4 Fail-closed behavior is a productivity feature

Fail-closed contracts are often described as safety overhead. In this harness they also improve productivity.

A fail-closed route:

- prevents wasted work on stale or contradictory sources;
- blocks two-writer collisions;
- avoids polishing artifacts that cannot be accepted;
- forces missing proof to be visible early;
- prevents a helper from generating a plausible but unusable result;
- keeps unauthorized actions from creating costly recovery work.

The aim is not zero warnings. The aim is warnings that have an owner, class, and next action.

---

## 5. Memory, semantic search, vector retrieval, wiki, and graphs

### 5.1 The memory stack is layered

The workspace uses multiple memory forms because no single store is sufficient.

#### Daily chronological memory

`memory/YYYY-MM-DD.md` records recent work, incidents, decisions, and pickup points. It is optimized for temporal continuity and post-interruption recovery.

#### Durable curated memory

`MEMORY.md` stores decisions and rules that should survive beyond a day. It should not become a second daily log.

#### Exact excerpt retrieval

`memory_get` retrieves bounded line ranges from known memory or wiki paths. It is the low-ambiguity option when the source path is already known.

#### Semantic retrieval

`memory_search` uses embeddings to find conceptually related passages across memory, wiki, and optionally session transcripts. Results include source paths, line citations, vector scores, and text scores.

#### Local vector index

The local vector-memory path combines:

- Ollama embeddings;
- `nomic-embed-text:latest`;
- SQLite;
- full-text search;
- vector similarity;
- source hashes;
- source profiles;
- stale-source detection;
- hash-based fallback.

#### Compiled wiki

The 15-page compiled wiki is a curated synthesis and source map. Its retrieval mirror is page-granular and hash-checked. It improves cold-session routing without becoming a new authority layer.

#### Graph layers

The workspace has two distinct graph concepts:

1. vector-memory graph nodes and edges that connect sources, workflows, tickers, blockers, actions, and outcomes;
2. Graphify code/skill graphs that expose AST or semantic relationships in scripts and skills.

Graphs help answer relationship questions. They do not replace source-open review.

### 5.2 Current memory evidence

The current evidence is mixed but useful:

- a live memory-corpus query during this research returned correct pickup context from `memory/2026-08-23.md`;
- that query used the local Ollama provider and `nomic-embed-text`;
- the combined all-corpus route was partial because the session-transcript corpus exceeded the memory-search deadline;
- a separate session-corpus query timed out after 15 seconds and returned unavailable;
- `tmp/semantic-memory-all-corpus-benchmark.json` classifies all-corpus retrieval as degraded while memory-only and local fallback remain usable;
- `tmp/semantic-memory-maintenance.json` reports 347 sources, 2,805 chunks, FTS enabled, and Ollama embeddings, but one transitive finance-derived source currently makes 672 chunks stale;
- `tmp/vector-memory-graph-packet.json` reports 389 sources, 2,601 nodes, and 10,473 edges in its 2026-08-08 snapshot;
- `tmp/graphify-vector-integration-validation-20260821.json` passed five bridged retrieval/graph queries.

The graph-bridge validation also exposed useful missing relations:

- no explicit improvement -> QA -> promotion -> memory path;
- no explicit cross-component feedback/evaluation path;
- no explicit retrieval-refresh -> routing relation.

Those are not proof that the system lacks the behaviors. They show that the relationships are not yet encoded strongly enough for deterministic graph traversal.

### 5.3 Why the memory design is efficient

The stack avoids two common extremes:

- reading every file on every turn;
- trusting a semantic result without opening its source.

The intended retrieval pattern is:

```text
known exact fact
-> memory_get or exact owner file

unknown prior decision
-> memory_search
-> cited path
-> exact source excerpt

cold project orientation
-> compiled wiki
-> source map
-> exact owner

relationship question
-> vector/Graphify graph
-> path
-> exact owner
```

### 5.4 Current memory limitations

The most important memory limitations are:

- session-transcript semantic retrieval is not reliable under the current deadline;
- combined corpus search is not yet a dependable one-call experience;
- one stale transitive source can invalidate hundreds of chunks;
- graph relations lag behind some real operating relationships;
- semantic similarity can route to a relevant source but cannot prove authority, freshness, or correctness;
- the workspace contains a large chronological history, so index partitioning and retrieval SLOs matter increasingly.

### 5.5 What a new harness should copy

A new harness should implement memory in this order:

1. durable Markdown memory with a clear daily/durable split;
2. exact line-based retrieval;
3. citations and source hashes;
4. local FTS;
5. local embeddings;
6. stale-source detection;
7. corpus separation;
8. automatic local fallback;
9. curated wiki synthesis;
10. graph relationships only after the source and ownership model is stable.

Do not start with a vector database and assume memory is solved. Without ownership, citations, freshness, and exact-source routing, vector memory merely makes stale information easier to find.

---

## 6. OTEL and privacy-safe observability

### 6.1 Current OTEL architecture

OTEL is used as an operational evidence plane, not as a raw conversation archive.

The current control packet shows:

- local collector on `127.0.0.1:4318`;
- metrics and traces;
- multi-window drift analysis;
- local JSONL/SQLite support;
- metadata-only tool, workflow, session, and lane fields;
- privacy scanning;
- no external export;
- no raw prompt, response, or tool-payload capture;
- no runtime or collector mutation from the report packet.

`tmp/otel-ops-control.json` was generated at 2026-08-23T04:40:06Z and validated `ok`.

### 6.2 Current OTEL evidence

For the 24-hour window in that packet:

- 1,715 events;
- 1,437 metric batches;
- 278 trace batches;
- 413,206 reported data points;
- 761 spans;
- zero warning or error events;
- daily-versus-weekly event-rate ratio of 1.7307, inside the configured 0.25x-2.5x drift band.

The metadata-only tool/workflow packet reported:

- 14,711 rows;
- 890 unique tool names;
- 14,711 workflow-attributed rows;
- 14,695 session-attributed rows;
- 1,382 failed or blocked classifications;
- privacy scan `ok`.

The local OTEL SQLite integrity check was `ok`.

### 6.3 What OTEL currently proves

OTEL can help answer:

- Is the collector reachable?
- Are metrics and traces arriving?
- Is event volume drifting?
- Which tools and workflows are represented?
- Which metadata-classified actions were blocked or failed?
- Is operational volume changing across 1h, 6h, 24h, 7d, and 30d windows?

It does not currently prove:

- model quality;
- financial correctness;
- execution readiness;
- actual billed cost;
- complete provider/model identity;
- complete token usage;
- end-to-end job acceptance.

The control packet explicitly states that model/provider, token usage, cost, raw payloads, and some latency fields are not reliably available from the basic collector log alone.

### 6.4 Why this observability posture is efficient

The design collects enough metadata to diagnose routing and workflow behavior without paying the privacy, security, and storage cost of raw content capture.

It also preserves a critical boundary:

```text
operational event
!= model quality
!= finance correctness
!= action approval
```

That prevents telemetry from becoming an accidental decision engine.

### 6.5 What a new harness should copy

A new harness should use a single correlation envelope across:

- parent job;
- workflow;
- workstream;
- lane;
- phase;
- attempt/retry;
- session;
- provider run;
- tool call;
- validator;
- Main acceptance;
- later outcome.

Only metadata required for correlation and performance analysis should be retained by default. Raw content should require a separate, explicit, time-bounded authority path.

---

## 7. Cron as an automation control plane

### 7.1 Cron is more than a schedule

In the Veritas workspace, a cron job has several separable truths:

- live scheduler state;
- expected output artifacts;
- artifact freshness;
- artifact validation;
- semantic signal class;
- escalation class;
- owner and repair command;
- authority boundary.

This is more robust than treating `last_status=success` as proof that useful work completed.

### 7.2 Core cron surfaces

The principal surfaces are:

- per-job cron contracts under `state/cron-contracts/`;
- `tmp/cron-freshness-spine.json`;
- `tmp/cron-control-packet.json`;
- cron scorecards;
- patch manager and contract validator;
- escalation consumer;
- owner workflow packets.

The freshness spine requires enabled jobs to have registry rows and expected artifacts. Its output is designed as the first read for cron health.

### 7.3 Current cron snapshot

The freshness spine generated at 2026-08-23T16:06:34Z shows:

- 58 total jobs;
- 57 enabled and one disabled;
- 40 quiet-success jobs;
- 22 fresh jobs;
- 15 blocked jobs;
- one needs-review job;
- one stale job;
- eight visible last-run scheduler exceptions;
- zero unregistered enabled jobs;
- zero enabled jobs missing an expected-artifact contract.

Its validator is `ok` even though the operational status is `blocked`. That distinction is correct: the packet is structurally valid and truthfully reports blocked work.

The current blocked set includes scheduler failures, finance-refresh dependencies, semantic-memory freshness, weekly improvement radar proof, and owner/authority-gated artifact states. Some visible scheduler errors are semantically harmless or intentionally fail closed; others represent genuine broken producer or proof chains.

### 7.4 Implemented cron efficiencies

The cron system already includes:

- artifact-first health rather than scheduler-only health;
- quiet-success and `NO_REPLY` behavior;
- attention buckets that separate urgent, new/changed, monitor-only, and quiet;
- expected-artifact contracts;
- deterministic producer commands;
- predispatch changed-input checks for selected jobs;
- market-date signatures to prevent invalid cross-day skips;
- review-only control packets that cannot mutate schedules;
- separate owner-gated schedule/config changes;
- main-session escalation routing.

The ticker-card prefilter is a strong example: unchanged inputs can avoid a model/agent turn, but the signature includes the Phoenix market date so a skip cannot cross a trading day.

### 7.5 Current cron efficiency gap

Cron still has three forms of avoidable drag:

1. **Status semantics:** a correct guard can exit nonzero and still appear as scheduler error.
2. **Blocked-chain fan-out:** one stale upstream artifact can make several downstream jobs look independently broken.
3. **Redundant execution:** only a subset of jobs has a proved changed-input gate.

Level 10 requires every job to return a semantic result class such as:

- `work_performed_success`;
- `quiet_no_change_success`;
- `guarded_no_action_success`;
- `review_required`;
- `blocked_dependency`;
- `owner_gate`;
- `retryable_failure`;
- `terminal_failure`.

Scheduler status should then be derived from the semantic result, not guessed from exit code alone.

---

## 8. The contract mesh

The workspace's strongest proprietary feature is its contract mesh. Contracts exist at multiple levels and reinforce one another.

### 8.1 Doctrine contracts

`SOUL.md`, `AGENTS.md`, `USER.md`, and `TOOLS.md` define:

- who the agent is;
- what it is optimizing for;
- how it works with Randall;
- which truth sources outrank others;
- what it may do autonomously;
- what requires approval;
- what is always blocked.

### 8.2 Task-intake contracts

The task-intake skill converts natural language into:

- objective;
- interpretation;
- non-goals;
- authority class;
- source surfaces;
- approach;
- debugging loop;
- cleanup scope;
- stop lines;
- acceptance proof;
- response contract.

This prevents hidden scope expansion and makes completion testable.

### 8.3 Workflow contracts

Major workflows name:

- objective and scope;
- out-of-scope boundaries;
- entry checklist;
- execution posture;
- owner layer;
- review window;
- acceptance gates;
- closeout checklist;
- checkpoint decision;
- next pass;
- adjacent candidates;
- key files;
- canonical mutation posture.

A workflow is not complete because a note sounds finished. It is complete when the named acceptance proof passes and the queue, registry, continuity, and closeout state agree.

### 8.4 Route contracts

`veritas.execution_efficiency_policy.v1` owns implementation route selection.

The current route order is:

1. deterministic/model-free command with proof;
2. explicitly eligible bounded Codex-native Terra lane;
3. explicit Main quick-fix, integration, or authority-sensitive exception;
4. persistent isolated Terra only with fresh strict context-transport proof;
5. blocked when transport or authority proof is missing.

There is no silent fallback to Main.

### 8.5 Lane contracts

Each meaningful lane can name:

- workflow and workstream;
- owner;
- exact read-first surfaces;
- exact allowed writes;
- forbidden writes;
- acceptance commands;
- phase;
- parent job;
- session and model metadata;
- attempt and retry identity;
- resource budgets;
- proof artifacts;
- terminal status.

The current research lane demonstrates the design: it leases exactly one report path and does not authorize runtime, schedule, config, finance, or archive writes.

### 8.6 Artifact and schema contracts

JSON packets commonly include:

- `schema`;
- `generated_at_utc`;
- `status`;
- `purpose`;
- `authority_boundary`;
- `source_artifacts`;
- `summary`;
- `validation`;
- `blocked_actions` or `stop_lines`.

The repeated envelope lets generic consumers route and validate many different packet families.

### 8.7 Validation contracts

Validation is risk-budgeted:

- micro: deterministic proof plus Main verification;
- narrow: focused tests plus Main verification;
- shared/major or sensitive: deterministic preflight plus one fresh independent review;
- repeated rejection: return to Main for root-cause and scope reclassification.

The changed-file router and validator bundle choose the smallest adequate proof instead of running every test for every change.

### 8.8 Authority contracts

Authority is expressed positively and negatively:

- review-only;
- local-only;
- proposal-only;
- code mutation allowed or false;
- cron schedule mutation allowed or false;
- runtime/config mutation allowed or false;
- finance/canon mutation allowed or false;
- paper/live/account action allowed or false;
- owner approval inferred or false.

This makes authorization machine-visible and lets leak guards fail closed.

### 8.9 Why contracts create efficiency

Contracts reduce:

- time spent reconstructing intent;
- repeated clarification;
- incorrect source selection;
- unnecessary model calls;
- merge collisions;
- broad validation;
- false completion;
- recovery cost after interruption;
- authority mistakes.

The opportunity is to compile more of this mesh into one queryable dependency graph so contracts do not have to be rediscovered across prose and JSON.

---

## 9. Execution routing, helper lanes, and checkpointed work

### 9.1 Model-free first

The fastest and most reliable route is used when a deterministic command plus proof already exists.

Examples include:

- status packet rendering;
- workflow routing;
- artifact lookup;
- schema validation;
- freshness checks;
- SQL integrity checks;
- targeted tests;
- changed-file validator selection.

Model work is reserved for ambiguity, synthesis, implementation judgment, contradiction resolution, or final integration.

### 9.2 Context is frozen before material helper work

The helper contract limits first-pass context to:

- at most six files;
- 120,000 bytes;
- approximately 30,000 context tokens;
- sorted hashes;
- one explicit base path;
- a snapshot identifier.

This reduces replay cost, makes repairs incremental, and gives QA a stable baseline.

### 9.3 Narrow lanes

One child lane should own one primary artifact, validator, or finding set. Broad review, implementation, documentation, continuity, and final synthesis should not be bundled into one helper prompt.

That design responds directly to prior timeout patterns where useful inspection was lost because the child had too much context and too many deliverables.

### 9.4 Main acceptance

Helper output is notification until:

- the artifact exists;
- the expected source hash is known;
- validation ran;
- Main inspected the result;
- the route/model matches expectation;
- the queue and continuity are updated.

This is the difference between “an agent said it finished” and a trusted result.

### 9.5 Current helper-auditability gap

The current readiness packet reports 1,447 historical agent-message events but zero receipt-verified helper events in the older snapshot. The newer message ledger has 1,463 terminal events and no identity or integrity conflicts, but still carries a metadata-supplement warning.

The Harness V2 Wave 2 candidate addresses the upstream cause by reserving a protected dispatch binding before native one-shot execution. The candidate passed no-install package proof, but the live package and gateway were not changed. Therefore:

- first complete trusted receipt: not yet produced;
- comparable Main-accepted cohort: 0/10;
- route/model promotion: not allowed.

### 9.6 Long-work and interruption recovery

Long-running vector jobs and other resumable tasks use:

- durable status;
- source manifests;
- event logs;
- chunk-level progress;
- resume commands;
- validation.

The current report itself recovered from a gateway restart using daily memory and the lane register. That is practical evidence that continuity is not dependent on one uninterrupted model turn.

---

## 10. Structured truth, SQL, indexes, and source ownership

### 10.1 Markdown and structured state have different jobs

The workspace deliberately separates:

- Markdown for policy, narrative, reasoning, decisions, and human context;
- JSON for typed proof and interchange;
- SQLite for queryable current state, lineage, registries, and joins;
- append-only JSONL or ledgers for history.

This avoids forcing every truth into one format.

### 10.2 SQL-first support without authority leakage

The finance data plane is a strong example of structured harness design.

The current cron control packet reports:

- SQLite integrity `ok`;
- foreign keys `ok`;
- required tables and views present;
- 300-row universe and routing coverage;
- 3,521 source-lineage rows;
- 684 consumer-migration rows;
- 14 proof-backed production answer rows.

It also reports a warning that the tier-routing mirror was built from an older router generation. The packet can identify the mismatch without granting permission to mutate canon.

That pattern is portable beyond finance:

```text
canonical owner
-> guarded structured mirror
-> query/view
-> derived packet
-> source-open verification
-> gated apply, if any
```

### 10.3 Artifact indexes and workflow routing

The workspace uses:

- `artifact_index.py` for proof lookup and stop-line routing;
- `workflow_router.py` for named workflow lookup;
- JSON and SQLite routing indexes;
- workflow capsules for compact state;
- source lineage to trace derived outputs.

The current workflow-routing index contains 43 routes. Its snapshot reports 12 fresh, three aging, 26 stale, and two not-applicable freshness states. The route index remains useful, but the stale count is a reminder that indexes must be refreshed or age-qualified.

### 10.4 Scale evidence

The workspace currently contains approximately:

- 51 active `SKILL.md` files;
- 1,368 top-level Python scripts under `scripts/`;
- 498 Python test files;
- 37 built Go validator/helper binaries;
- 44 workflow-state JSON files;
- 43 per-file cron contracts;
- 15 compiled wiki pages;
- 311 dated memory Markdown files.

This scale demonstrates substantial capability. It also demonstrates why routing, reuse-before-new-script rules, artifact lifecycle, and dependency graphs are essential. A new harness should copy the architecture, not reproduce 1,368 scripts as a starting condition.

---

## 11. Validation, QA, release, and rollback

### 11.1 Proof is proportional to risk

The workspace avoids two bad extremes:

- no validation because the change looks small;
- full-system validation for every tiny edit.

Risk, scope, shared semantics, and authority determine the proof budget.

### 11.2 Changed-file routing

The validator router can:

- inspect the changed paths;
- classify task type;
- choose exact validators;
- order dependencies;
- enforce command safety;
- run only when explicitly requested.

The current validator-bundle proof shows a two-path scoped change selecting three commands with a narrow budget, zero failures, and no execution until the explicit execute flag.

### 11.3 Independent QA

Shared, major, repeated-failure, privacy, security, authority, or finance-semantic changes require an independent review after deterministic preflight. The implementation lane does not grade its own closeout.

### 11.4 Rollback is part of release

The Harness V2 Wave 2 package work produced:

- a no-install candidate tarball with SHA-256;
- a separate exact rollback package with SHA-256;
- staged build and packaging proof;
- explicit gateway/runtime non-mutation;
- an activation gate requiring fresh approval.

This is a strong pattern: prepare rollback before activation, not after failure.

### 11.5 Current artifact-lifecycle debt

At the report's pre-closeout snapshot, the concurrent-lane register had one active lane and 1,463 terminal lanes. Active-lane ownership, write scope, and lease checks were clean. However, the global validator reported a critical historical proof-existence failure because older terminal lanes reference proof artifacts that are no longer present.

This does not invalidate the current active lease. It reveals a Level-10 lifecycle requirement:

- either proof must be retained for the declared retention period;
- or it must be archived with an immutable manifest;
- or the lane must hold a durable content hash and tombstone explaining approved retirement.

Deleting temporary artifacts without preserving proof lineage makes old accepted work harder to verify.

---

## 12. Learning, evaluations, prompt book, and self-improvement

### 12.1 The intended learning conveyor

```text
OTEL / failures / outcomes / friction
-> metadata normalization
-> improvement opportunity
-> append-only improvement ledger
-> route classification
-> PM job, validator ticket, Skill Workshop proposal, owner packet, or monitor-only
-> bounded implementation
-> validation and Main acceptance
-> later-outcome check
-> durable closure or recurrence
```

The important design choice is that detection and proposal are automated more broadly than application.

### 12.2 Current improvement evidence

`tmp/actionable-improvement-queue.json` reports:

- 13 open inputs;
- 13 deduplicated action items;
- zero orphans;
- zero missing contracts;
- three WF74 fix-now items;
- one active follow-up;
- eight monitor-only items;
- auto-apply disabled.

`tmp/improvement-ledger-current.json` reports:

- 590 append-only historical rows;
- 13 latest open items;
- 27 latest closed items;
- seven actionable open items;
- three high-priority open items;
- seven overdue open items;
- two high-priority overdue items.

The top recurring item is cron regression repair. The ledger correctly distinguishes historical rows from current debt.

### 12.3 Proposal generation

The auto-patch proposer currently has:

- eight plans;
- five patch-plan routes;
- one Skill Workshop request;
- six owner-gated plans;
- zero auto-apply candidates;
- zero applied changes.

That is the right authority posture for an emerging self-improvement system.

### 12.4 Prompt book

The metadata-only prompt book currently has:

- 15 entries;
- coverage across operations, RSI, finance, PM, and product;
- all 15 covered by fixtures;
- zero eval gaps;
- no stored prompt text;
- raw capture blocked;
- no skill or doctrine auto-apply.

This proves reusable prompt-family governance. It does not prove the prompts outperform alternatives in live conditions.

### 12.5 Evaluation gates

The AGI OS evaluation packet reports:

- 17 gates;
- nine passing;
- eight warning;
- zero failing.

Passing evidence includes:

- multiple later-outcome memory packets;
- recommendation and finance later-outcome signals;
- graph memory;
- checkpointed execution;
- a 42-fixture WF88 retrieval regression set with 42 passes;
- a frontier capability evaluation contract with 100 fixtures and 300 assignments;
- privacy-safe advanced pilot contracts.

Warning evidence includes:

- coding follow-through;
- token-efficiency promotion;
- implementation-token attribution;
- zero frontier execution results;
- insufficient RSI closure durability;
- zero executed advanced-capability pilots;
- WF88 decision-compiler warnings;
- helper-message receipt verification.

The distinction is critical: **a ready evaluator is not evaluation evidence**.

### 12.6 Learning-loop reality

The WF74 collection runner currently completes 15 of 16 steps. Its model-quality scorecard is blocked, while OTEL collection, coding outcomes, prompt variants, proposal routing, and several other components continue to produce useful evidence.

It reports:

- 1,351 coding outcome rows;
- 799 ex-post graded rows;
- 92.37% first-pass-clean rate across the eligible coding cohort;
- 26 retries;
- 90.38% planning follow-through clean rate;
- eight current improvement opportunities;
- zero auto-apply.

But model and session attribution coverage in the model-run ledger is only 0.65%, implementation token events remain zero, and the improvement backlog has overdue items. The workspace is therefore a real learning environment, but not yet a fully closed learning system.

---

## 13. Implemented efficiency catalog

| Efficiency already implemented | How it works | Primary gain | Current limit |
|---|---|---|---|
| Thin T0 startup | Reads doctrine, Startup Truth Index, recent memory, then drills down | Lower boot tokens and faster orientation | Some downstream indexes are stale |
| Cached status front door | Shallow status uses one compact packet | Avoids regenerating PM/cron/workflow state | Warnings still require drilldown |
| Workflow capsules | Named workflow lookup returns summary/next/blockers/helper | Fast resumption after compaction | 26 routes were stale in the cited snapshot |
| Exact memory retrieval | Known paths use bounded line excerpts | Low ambiguity and low context | Requires knowing the source path |
| Semantic memory | Local embeddings plus citations | Concept recall across long history | All-corpus/session route is degraded |
| FTS plus vector fusion | Lexical and semantic signals complement each other | Better precision than either alone | Stale transitive sources can contaminate many chunks |
| Local hash fallback | Retrieval remains possible if dynamic tool times out | Graceful degradation | Fallback is not yet automatically invisible |
| Compiled wiki | Curated 15-page synthesis with source map | Faster cold-session comprehension | Synthesis warnings still require source-open checks |
| Graph routing | Vector and Graphify relations expose paths | Faster relationship questions | Some real control relations are missing |
| Model-free first | Deterministic commands take priority | Lower latency, cost, and variance | Requires good CLI/proof coverage |
| Versioned route policy | One machine owner selects route and effort | Prevents ad hoc model choice | Trusted cohort evidence is incomplete |
| Narrow context handoff | Six-file/120 KB/30k-token cap with hashes | Less replay and cleaner QA | Enforcement depends on route metadata |
| Exact write leases | Lanes declare allowed writes and owner | Prevents concurrent collisions | Historical register proof retention is incomplete |
| Attempt/retry identity | Incidents and retries are separate from first-pass success | Honest efficiency measurement | Provider usage can still be unavailable |
| Risk-budgeted QA | Micro, narrow, shared, and major proof levels | Avoids both under- and over-testing | Validator inventory remains large |
| Changed-file validator routing | Selects exact validators from scope | Reduces full-suite drag | Shared dependencies still require human judgment |
| Go validator binaries | Performance-sensitive deterministic checks are compiled | Faster repeated validation | Freshness guard is required after source changes |
| Artifact index | Routes to proof, provenance, and stop lines | Avoids broad `tmp/` scans | Index is derived and can become stale |
| SQL/JSON structured truth | Queryable current state and lineage | Less Markdown parsing and duplication | Guarded mirror freshness must be maintained |
| Cron expected-artifact contracts | Jobs are judged by outputs, not only exit status | More truthful automation health | Semantic exit classes are incomplete |
| Quiet-success behavior | Healthy jobs do not create chat noise | Lower attention cost | Some correct guards still appear as errors |
| Changed-input prefilters | Unchanged inputs can skip expensive work | Fewer model/API calls | Promotion-ready proof count is still zero in the token packet |
| Market-date signatures | Prevents a stale cross-day skip | Correctness-preserving caching | Domain-specific signatures must be maintained |
| Local OTEL | Collects operational metadata and drift | Observability without external exposure | Provider tokens/cost are incomplete |
| Metadata-only privacy | No raw prompt/response/tool payload capture | Lower privacy and security risk | Limits deep semantic failure analysis |
| Append-only improvement ledger | Preserves history and current debt separately | Enables recurrence and closure analysis | Overdue follow-through remains |
| No-auto-apply self-improvement | Detection and proposal are automated, application is gated | Prevents self-modification theater | More Main review is required |
| Prompt-book fixtures | Reusable prompt families have coverage metadata | Regression visibility | Fixture coverage is not outcome superiority |
| Checkpointed execution | Long chains persist state and proof | Recovery after restarts and timeouts | Not all chains have equal granularity |
| Rollback-first packaging | Candidate and rollback are prepared together | Lower activation risk | Live activation still needs exact approval |

---

## 14. Replication blueprint for a new harness

### 14.1 Replication principle

Copy the invariants, not the accumulated implementation.

The essential invariants are:

- one owner for each truth class;
- generated proof never silently becomes canon;
- every material task has an authority class and acceptance proof;
- deterministic work precedes model work;
- model lanes have exact context, write scope, budgets, and terminal proof;
- memory returns citations and routes to exact sources;
- scheduled work has expected artifacts and semantic outcomes;
- telemetry is correlated and privacy-bounded;
- improvement detection is broader than apply authority;
- Main acceptance is explicit;
- owner-gated actions stay owner-gated.

### 14.2 Recommended minimal repository shape

```text
harness/
  AGENT.md
  SOUL.md
  USER.md
  TOOLS.md
  MEMORY.md
  memory/
  skills/
  playbooks/
    Startup Truth Index.md
    Major Workflow Contract Standard.md
    Automation Orchestration Protocol.md
  workflows/
  state/
    workflows/
    cron-contracts/
    lanes/
    memory-index/
    telemetry/
  scripts/
    status/
    routing/
    memory/
    cron/
    telemetry/
    validation/
    release/
  wiki/
  tmp/
  deliverables/
```

### 14.3 Phase 0 — define identity and authority

Build:

- mission and operating standard;
- human preferences;
- doctrine hierarchy;
- action classes;
- stop lines;
- source-ownership rules.

Acceptance:

- every high-risk action class has an explicit owner gate;
- no generated packet can imply approval;
- the agent can explain what it may inspect, propose, change locally, or never do.

### 14.4 Phase 1 — establish durable truth and memory

Build:

- daily memory;
- curated durable memory;
- exact excerpt retrieval;
- source paths and line citations;
- retention and promotion rules.

Acceptance:

- a new session can retrieve a prior decision and its exact source;
- daily history does not automatically become durable policy;
- memory writes are append-safe.

### 14.5 Phase 2 — create the thin startup path

Build:

- one Startup Truth Index;
- one cached status front door;
- one future-session/compaction packet;
- named drilldown rules.

Acceptance:

- shallow status needs one packet;
- material work can find an exact owner in two hops;
- startup does not load the whole repository.

### 14.6 Phase 3 — add workflow and task contracts

Build:

- task-intake schema;
- workflow registry;
- continuity template;
- workflow router;
- acceptance and closeout fields.

Acceptance:

- a named workflow returns status, next action, blocker, owner, and proof;
- a restarted session can resume without chat reconstruction;
- paused or gated work fails closed.

### 14.7 Phase 4 — add deterministic routing and validation

Build:

- implementation route policy;
- model-free command registry;
- changed-file validator router;
- risk budgets;
- release and rollback contract.

Acceptance:

- deterministic work never spawns a model unnecessarily;
- each change class has the smallest adequate proof;
- shared contracts regenerate downstream consumers before closeout.

### 14.8 Phase 5 — add lane and checkpoint control

Build:

- lease register;
- exact allowed writes;
- parent job, phase, attempt, retry, model, and budget fields;
- long-work checkpoint format;
- Main acceptance state.

Acceptance:

- two active lanes cannot own the same write;
- a timed-out job leaves a usable partial artifact;
- a lane cannot complete without proof or an explicit unavailable classification.

### 14.9 Phase 6 — add scheduled automation

Build:

- cron registry;
- per-job expected-artifact contract;
- freshness spine;
- semantic result classes;
- quiet-success policy;
- escalation router;
- changed-input prefilters.

Acceptance:

- every enabled job has an owner and expected output;
- no-change is a success, not an error;
- stale downstream artifacts identify the upstream blocker;
- schedule mutation is separate from proof refresh.

### 14.10 Phase 7 — add observability

Build:

- local OTEL collector;
- correlation envelope;
- multi-window health;
- metadata-only tool/workflow/session fields;
- local SQLite index;
- privacy validator.

Acceptance:

- every material job can be traced through dispatch, tools, validation, and acceptance;
- no raw content is captured by default;
- operational health is not mislabeled as quality or approval.

### 14.11 Phase 8 — add semantic and graph retrieval

Build:

- local FTS;
- embeddings;
- source-hash invalidation;
- corpus-specific indexes;
- query fallback;
- curated wiki;
- graph bridge.

Acceptance:

- exact citations are returned;
- stale sources are excluded or clearly flagged;
- all-corpus failure degrades to working corpus-specific retrieval;
- graph paths end at source owners.

### 14.12 Phase 9 — add learning and evaluation

Build:

- append-only outcomes;
- improvement ledger;
- recurrence and SLA fields;
- prompt-book metadata;
- evaluation fixtures;
- proposal router;
- no-auto-apply guard.

Acceptance:

- a detected problem becomes a routed item;
- a closed item has acceptance and later-outcome evidence;
- fixture readiness is distinct from execution evidence;
- a skill or model route cannot promote itself.

### 14.13 Phase 10 — harden portability and resilience

Build:

- environment manifest;
- local installer/bootstrap;
- secrets abstraction;
- sandbox profiles;
- backup and restore;
- chaos and restart drills;
- versioned migrations.

Acceptance:

- a clean machine can reproduce the harness without copying secrets;
- the system recovers after an interrupted turn;
- state migrations and rollback are deterministic;
- no host-specific path is embedded in portable contracts.

### 14.14 What to copy, parameterize, and leave behind

| Copy exactly as a pattern | Parameterize | Do not blindly copy |
|---|---|---|
| Doctrine hierarchy | User identity and timezone | Randall-specific finance preferences |
| Authority classes | Domain stop lines | Credentials, account identifiers, endpoints |
| Task and workflow contract schemas | Workflow names and schedules | Historical `tmp/` artifacts |
| Exact source ownership | Canonical data domains | The entire 1,368-script inventory |
| Model-free-first routing | Allowed models and providers | Old route names without current proof |
| Lane leases and Main acceptance | Context and resource budgets | Historical lane residue |
| Memory citations and fallback | Corpus definitions | Stale semantic chunks |
| Cron expected-artifact model | Cadence and review windows | Scheduler errors treated as universal failure |
| OTEL metadata envelope | Retention and sampling | Raw prompts/responses/tool payloads |
| Risk-budgeted validation | Test suites and binaries | Domain-specific finance mutation rules in a non-finance harness |
| Improvement proposal gating | Skill and eval families | Auto-apply from recommendations |

---

## 15. Directional Level-10 readiness model

This model is for prioritization. It is not an audit score.

| Dimension | Directional current maturity | Level-10 condition |
|---|---:|---|
| Truth ownership and doctrine | 9.0 | Every truth class has one owner and machine-visible lineage |
| Authority and safety boundaries | 9.0 | Capability checks are enforced transactionally at every action |
| Startup and recovery | 8.5 | Sub-second/low-context boot and deterministic interruption recovery |
| Exact and semantic retrieval | 7.0 | Corpus SLOs, automatic fallback, zero stale-result leakage |
| Structured state and provenance | 8.5 | Full dependency and lineage graph with transactional migrations |
| Workflow and contract architecture | 8.5 | Contracts compiled and checked across all producers/consumers |
| Cron automation | 6.5 | Semantic outcomes, low blocked rate, changed-only by default |
| OTEL and observability | 7.5 | End-to-end correlated receipts with privacy-safe coverage |
| Multi-agent orchestration | 7.0 | Receipt-verified helpers, sandboxing, reliable closeout |
| Validation and rollback | 8.5 | Risk-based proof, property tests, routine rollback drills |
| Outcome evaluation and learning | 6.5 | Executed matched evals and durable later-outcome closure |
| Token/cost/latency efficiency | 5.5 | Trusted job-level usage, comparable cohorts, measured optimization |
| Portability and lifecycle | 6.5 | Reproducible bootstrap, retention policy, clean artifact lifecycle |

The directional aggregate is approximately **7.5/10**.

The main reason the score is not higher is evidence maturity. The harness has many of the right contracts, but several of the most important loops stop before a fully trusted terminal record or later outcome.

---

## 16. Additional efficiency opportunities required for Level 10

### P0. Reliability and truth gaps

#### 16.1 Make memory retrieval an SLO-backed service

**Problem:** memory-only retrieval works, but combined all-corpus and session retrieval can time out.

**Implement:**

- separate memory, wiki, and session indexes and deadlines;
- query planner that fans out within a global budget;
- return partial results with per-corpus status;
- automatically fall back to local vector/FTS;
- cache query embeddings;
- shard sessions by recency and source family;
- add p50/p95 latency and timeout telemetry;
- exclude stale sources before scoring.

**Acceptance:**

- 99% of memory-only queries complete inside the target SLO;
- 95% of all-corpus queries return at least two healthy corpora;
- session timeouts do not suppress memory/wiki results;
- fallback is automatic and cited;
- no stale-source result is presented without a freshness label.

#### 16.2 Build incremental invalidation instead of broad rebuilds

**Problem:** one transitive source currently makes 672 chunks stale.

**Implement:**

- content-hash dependency DAG;
- chunk-level invalidation;
- transitive source lineage;
- priority rebuild queue;
- quarantine of stale chunks from default retrieval;
- freshness watermark per corpus.

**Acceptance:**

- changed source invalidates only dependent chunks;
- stale chunk count returns to zero within the maintenance SLO;
- queries cannot rank quarantined chunks as fresh.

#### 16.3 Produce the first complete protected execution receipt

**Problem:** the no-install candidate exists, but no live complete receipt exists.

**Implement after exact owner approval:**

- install only the verified candidate and paired package;
- restart with rollback ready;
- run health/schema checks;
- dispatch one protected native one-shot job;
- join dispatch, provider run, usage, validator, and Main acceptance.

**Acceptance:**

- one terminal record contains every required identifier;
- hashes reconcile across runtime and workspace;
- rollback is tested;
- a failed first receipt stops downstream scorecard expansion.

#### 16.4 Extend correlation through the full job lifecycle

**Problem:** OTEL, lane, token, validator, and outcome rows are not fully joined.

**Implement:**

- one immutable `correlation_id`;
- child span and attempt IDs;
- provider-run binding;
- validator-result binding;
- Main-acceptance binding;
- later-outcome binding.

**Acceptance:**

- every material job can be reconstructed from one correlation ID;
- helper and Main events are distinguishable;
- missing provider counters are explicitly classified, never silently zero.

#### 16.5 Normalize cron semantic outcomes

**Problem:** correct guarded behavior can appear as scheduler error, while upstream failures fan out.

**Implement:**

- shared semantic exit schema;
- dependency root-cause rollup;
- guard/no-change success classes;
- retry policy by error type;
- quarantine repeated failures;
- changed-input gates for high-cost jobs.

**Acceptance:**

- zero correct guards classified as errors;
- blocked downstream jobs name one upstream cause;
- quiet-success rate increases without hiding failures;
- every enabled job has semantic status and expected artifacts.

#### 16.6 Repair the historical proof-retention contract

**Problem:** terminal lane records reference missing historical proof artifacts.

**Implement:**

- retention classes;
- archive manifest with content hashes;
- approved tombstone records;
- proof-path migration tool;
- validator that distinguishes unauthorized loss from approved retirement.

**Acceptance:**

- global lane-register validation is clean;
- every terminal lane has a live proof, immutable archive hash, or approved tombstone;
- no destructive cleanup occurs without owner approval.

### P1. Contract and execution efficiency

#### 16.7 Compile the contract mesh into a dependency graph

**Problem:** contracts are strong but distributed across prose, JSON, scripts, and registries.

**Implement:**

- canonical contract schema;
- producer/consumer registry;
- field ownership;
- authority class;
- freshness requirements;
- validator and rollback link;
- Graphify/AST extraction;
- drift detector.

**Acceptance:**

- changing a shared field lists every consumer and proof gate;
- orphaned producers and consumers are zero;
- authority changes require explicit owner review;
- graph paths resolve to exact files and lines.

#### 16.8 Add transactional local action execution

**Problem:** many actions are safe locally but still require custom orchestration.

**Implement:**

- `plan -> preview -> lease -> apply -> validate -> accept -> rollback` state machine;
- idempotency key;
- capability token;
- exact diff hash;
- timeout and compensation;
- immutable audit row.

**Acceptance:**

- reversible workspace actions are idempotent;
- partial failure restores the prior state;
- authority class is checked before execution;
- Main acceptance is separate from validator success.

#### 16.9 Make changed-only execution the default

**Problem:** selected jobs have prefilters, but changed-only proof is not broadly promotion-ready.

**Implement:**

- normalized input signatures;
- source-family hash;
- time-bucket and market-date components where relevant;
- last-success signature;
- deterministic no-change receipt;
- false-skip regression suite.

**Acceptance:**

- high-cost unchanged jobs spawn no model turn;
- no skip crosses an invalid freshness boundary;
- avoided calls, tokens, elapsed time, and defects are measured.

#### 16.10 Close implementation-token and cost attribution

**Problem:** 597 implementation token gaps and no implementation token events prevent credible savings claims.

**Implement:**

- trusted provider/runtime usage import;
- cache-aware token semantics;
- actual-vs-estimated cost labels;
- OAuth advisory separation;
- per-job token and elapsed budgets;
- incomplete-coverage warnings.

**Acceptance:**

- at least 95% of supported material jobs have reconciled usage or a controlled unavailable reason;
- actual billing is never inferred from API-equivalent estimates;
- retry tax and cached replay are visible.

#### 16.11 Collect ten comparable Main-accepted jobs

**Problem:** route optimization lacks a valid comparable cohort.

**Implement:**

- freeze a non-finance task cohort;
- require same task class and acceptance standard;
- compare model-free, bounded native, and persistent routes only where eligible;
- include elapsed time, calls, tokens, cache, retries, first-pass acceptance, and escaped defects.

**Acceptance:**

- ten comparable Main-accepted jobs per reviewed route;
- zero invalid telemetry rows receive success credit;
- no automatic route promotion;
- decision is documented as evidence, not preference.

#### 16.12 Reduce validator drag with dependency-aware bundles

**Problem:** the validator inventory is large and can create unnecessary release latency.

**Implement:**

- dependency graph;
- historical timing;
- flaky-test classification;
- parallel-safe command groups;
- budget ceiling;
- changed-schema downstream tests;
- cached unchanged proof where safe.

**Acceptance:**

- median validation time declines;
- escaped-defect rate does not rise;
- shared-contract changes still trigger all required consumers.

### P1. Evaluation and learning closure

#### 16.13 Execute the existing frontier evaluation contract

**Problem:** 100 fixtures and 300 assignments exist, but result evidence is zero.

**Implement:**

- isolated runner;
- source-identical inputs;
- trusted execution attestation;
- blinded or deterministic grading where possible;
- output artifact hashes;
- matched baseline/variant comparisons.

**Acceptance:**

- all assignments have trusted terminal records;
- fully verified result rows exist;
- ranking remains blocked until every analytical gate passes;
- raw content retention follows the privacy contract.

#### 16.14 Turn improvement closure into the primary self-improvement KPI

**Problem:** proposal generation is stronger than durable closure.

**Implement:**

- closure SLA;
- recurrence window;
- later-outcome check;
- “fixed, stayed fixed” state;
- overdue escalation;
- proposal-to-accepted-outcome conversion metric.

**Acceptance:**

- high-priority overdue count reaches zero;
- closure durability is measured;
- recurring issues reopen automatically;
- proposal volume is not treated as progress.

#### 16.15 Encode missing feedback graph relations

**Problem:** graph validation found missing explicit paths for QA/promotion/memory and retrieval-refresh/routing.

**Implement:**

- typed edges for `validated_by`, `promoted_to`, `remembered_in`, `invalidates`, `refreshes`, and `routes_to`;
- source-line citations;
- cycle and orphan checks.

**Acceptance:**

- improvement-to-outcome path is traversable;
- retrieval refresh identifies affected routes;
- graph does not infer edges from vector similarity alone.

#### 16.16 Add contradiction and supersession management

**Problem:** long-lived workspaces accumulate claims that were once true and are now stale.

**Implement:**

- assertion ID;
- source and timestamp;
- supersedes/superseded-by edges;
- conflict class;
- owner resolution;
- retrieval-time downranking of superseded claims.

**Acceptance:**

- current answers prefer non-superseded owner truth;
- unresolved contradictions are surfaced, not blended;
- historical evidence remains available.

### P2. Resilience, security, and frontier agentics

#### 16.17 Sandbox every helper by capability

**Problem:** write leases are strong, but runtime sandbox proof is a separate maturity gap.

**Implement:**

- read-only default;
- explicit filesystem mounts;
- command allowlist;
- network denied by default;
- secretless execution;
- per-lane capability token;
- resource ceilings.

**Acceptance:**

- helper cannot access undeclared paths or network;
- sandbox proof is attached to the lane;
- escape tests pass;
- absence of sandbox proof is visible.

#### 16.18 Add chaos and recovery drills

**Problem:** recovery works, but should be continuously proven.

**Implement:**

- simulated gateway restart;
- killed helper;
- stale lock;
- partial write;
- corrupted derived packet;
- unavailable embedding provider;
- OTEL outage;
- scheduler delay.

**Acceptance:**

- checkpoint recovery meets RTO/RPO targets;
- partial work is not mislabeled complete;
- rollback or fallback routes are deterministic.

#### 16.19 Introduce planner/executor/critic only after receipt maturity

**Problem:** adding more agents before proof maturity increases noise.

**Implement later:**

- planner creates bounded DAG;
- executor receives capability-limited nodes;
- critic verifies source/proof/authority;
- Main accepts the full plan;
- dynamic replanning uses terminal receipts.

**Acceptance:**

- every node has one owner and proof;
- no two-writer collision;
- failed nodes replan without replaying the full context;
- critic cannot expand authority.

#### 16.20 Build a portable harness bootstrap

**Problem:** proprietary knowledge is encoded across many local files and Windows-specific paths.

**Implement:**

- versioned harness manifest;
- environment detection;
- path abstraction;
- generated local config;
- secret placeholders;
- minimal sample workflows;
- self-test suite;
- migration and rollback.

**Acceptance:**

- clean-machine bootstrap reproduces the control planes;
- no secrets or account data are copied;
- all core contracts validate;
- a sample workflow survives restart and produces a complete receipt.

---

## 17. Prioritized roadmap

### First 30 days

1. Repair session/all-corpus memory-search reliability or formalize automatic corpus-specific fallback.
2. Clear the current semantic-memory stale transitive source.
3. Normalize cron semantic outcomes and repair the highest-impact blocked chains.
4. Complete fresh independent QA on the Wave 2 candidate.
5. If separately approved, activate the candidate and produce one complete protected receipt.
6. Define correlation-ID v1 across lane, provider, OTEL, validator, and acceptance.
7. Define proof-retention classes for historical terminal lanes.

### Days 31-60

1. Collect the first comparable accepted-job cohort.
2. Implement the contract dependency graph.
3. Expand changed-input prefilters to the highest-cost unchanged jobs.
4. Close provider-usage and implementation-token gaps.
5. Execute the first bounded frontier-evaluation slice.
6. Add durable closure and recurrence metrics to the improvement loop.

### Days 61-90

1. Implement the reversible local transaction runner.
2. Add helper capability sandbox proof.
3. Run interruption and provider-outage drills.
4. Move route-efficiency decisions to like-for-like accepted cohorts.
5. Add contradiction/supersession handling to retrieval.
6. Build an operator cockpit around SLOs, not packet volume.

### Three to six months

1. Portable clean-machine bootstrap.
2. Full eval execution and later-outcome pipeline.
3. Planner/executor/critic pilot on low-risk local work.
4. Property-based authority and contract tests.
5. Automated dependency impact and incremental rebuilds.
6. Evidence-backed route review with no automatic promotion.

---

## 18. Level-10 metrics and service objectives

| Domain | Suggested Level-10 measure |
|---|---|
| Startup | p95 cold orientation under 10 seconds and under the defined context budget |
| Memory | 99% memory-corpus success; 95% all-corpus partial-or-better success; zero uncaveated stale results |
| Retrieval quality | Source-open precision and citation correctness above 98% on a frozen regression set |
| Vector freshness | Zero stale chunks beyond maintenance SLO |
| Workflow routing | 100% active workflows return owner, status, next action, blocker, and proof |
| Lane integrity | Zero active write collisions; 100% terminal lanes have proof/archive/tombstone |
| Receipt completeness | At least 95% supported material jobs fully correlated |
| Cron | Zero unregistered enabled jobs; zero missing contracts; semantic error misclassification below 1% |
| Changed-only | Avoided model calls measured with zero false skips in regression |
| OTEL | 99.9% local collector availability; privacy scan always clean |
| Validation | Lower p50/p95 time with no increase in escaped defects |
| First-pass quality | Measured by comparable task class, not pooled vanity rate |
| Retry tax | Separate elapsed, token, and failure cost; target downward trend |
| Evaluation | Trusted executed results, not only fixtures |
| Improvement closure | Zero overdue P0/P1 items; durable closure and recurrence measured |
| Authority | Zero owner-approval inference or unauthorized action |
| Privacy | Zero raw prompt/response/tool payload/secret capture outside an explicit gate |
| Recovery | Tested RTO/RPO for interrupted turns, stale locks, and provider outages |
| Cost | Trusted per-job usage coverage above 95%; estimates never labeled billing |

---

## 19. What not to copy

A new harness should not copy complexity for its own sake.

Do not copy:

- every historical script;
- every temporary packet;
- every old warning;
- every domain-specific finance rule;
- every legacy lane;
- every schedule;
- every model route;
- every prompt variant.

Do not confuse:

- more agents with more autonomy;
- more packets with more truth;
- more validators with better assurance;
- vector similarity with correctness;
- fixture coverage with outcome evidence;
- scheduler success with useful work;
- clean data with approval;
- a proposal with an applied improvement;
- a technically clean action with authorized action.

The new harness should begin with perhaps five workflows, five skills, one local memory index, one cron spine, one OTEL envelope, one lane register, and one end-to-end receipt. It should earn additional complexity only when a real recurring need appears.

---

## 20. Final conclusion

The Veritas workspace is already a sophisticated agent harness because it makes the invisible parts of reliable agent work explicit:

- what is true;
- who owns it;
- how it is retrieved;
- which action is authorized;
- what may run automatically;
- which model or deterministic route should be used;
- where writes are allowed;
- what proves completion;
- how failures are classified;
- how work survives interruption;
- how outcomes feed future improvement.

Its strongest differentiator is not raw model capability. It is disciplined state, contracts, proof, and authority.

The path to Level 10 is not a larger prompt or a larger agent swarm. It is closing the remaining loops:

1. retrieval that meets an SLO and degrades gracefully;
2. fresh vector state with incremental invalidation;
3. one fully correlated execution receipt, then a comparable cohort;
4. semantic cron outcomes and changed-only execution;
5. a compiled contract and dependency graph;
6. outcome-executed evaluation rather than fixture readiness;
7. durable improvement closure rather than proposal volume;
8. capability sandboxing and recovery drills;
9. a reversible transactional action engine;
10. portable bootstrap without secrets or historical residue.

When those conditions are met, the harness will be close to Level 10 in the practical sense that matters: efficient, observable, recoverable, truth-grounded, bounded, and increasingly autonomous inside explicit authority—without pretending that automation, scaffolding, or a high model score equals AGI.

---

## Source registry

### Doctrine and operating standards

- `SOUL.md`
- `AGENTS.md`
- `USER.md`
- `TOOLS.md`
- `06. Playbooks/Startup Truth Index.md`
- `06. Playbooks/Major Workflow Contract Standard.md`
- `06. Playbooks/Automation Orchestration Protocol.md`
- `06. Playbooks/Spawn and Closeout Governance Matrix.md`
- `skills/task-intake-contract/SKILL.md`
- `skills/project-continuity-manager/SKILL.md`
- `skills/agi-harness-readiness-operator/SKILL.md`

### Current and recent proof surfaces

- `tmp/agi-harness-readiness-packet.json` — generated 2026-08-23T00:56:40Z
- `tmp/agi-os-eval-gate-packet.json` — generated 2026-08-23T00:56:40Z
- `tmp/implementation-token-attribution-bridge.json` — generated 2026-08-17T23:10:52Z
- `tmp/cron-control-packet.json` — generated 2026-08-23T15:01:26Z
- `tmp/cron-freshness-spine.json` — generated 2026-08-23T16:06:34Z
- `tmp/otel-ops-control.json` — generated 2026-08-23T04:40:06Z
- `tmp/vector-memory-graph-packet.json` — generated 2026-08-08T07:04:39Z
- `tmp/semantic-memory-all-corpus-benchmark.json` — generated 2026-08-14T13:59:28Z
- `tmp/semantic-memory-maintenance.json` — generated 2026-08-23T13:15:01Z
- `tmp/graphify-vector-integration-validation-20260821.json` — generated 2026-08-21T23:30:00Z
- `tmp/wiki-bootstrap-proof.json` — generated 2026-08-23T05:12:21Z
- `tmp/workflow-routing-index.json` — generated 2026-08-23T02:51:16Z
- `tmp/agent-message-ledger-current.json` — generated 2026-08-23T17:33:07Z
- `tmp/token-efficiency-review-packet.json` — generated 2026-08-23T00:56:27Z
- `tmp/cron-efficiency-review-runner.json` — generated 2026-08-23T00:56:40Z
- `tmp/actionable-improvement-queue.json` — generated 2026-08-23T05:12:18Z
- `tmp/improvement-ledger-current.json` — generated 2026-08-23T05:12:15Z
- `tmp/wf74-auto-patch-proposer.json` — generated 2026-08-23T05:12:11Z
- `tmp/prompt-book-registry.json` — generated 2026-08-23T00:56:40Z
- `tmp/prompt-book-eval-gap-packet.json` — generated 2026-08-23T00:56:40Z
- `tmp/wf74-model-quality-collection-cron-runner.json` — generated 2026-08-23T04:42:40Z
- `tmp/validator-bundle-efficiency-proof.json` — generated 2026-08-12T06:17:29Z
- `tmp/route-efficiency-scorecard.json` — generated 2026-08-23T02:51:18Z
- `tmp/concurrent-lane-register.json` — refreshed during this research

### Continuity and replication sources

- `06. Playbooks/Project Continuity/Veritas Harness V2 - Governance and Efficiency Upgrade Plan - 2026-08-22.md`
- `memory/2026-08-23.md`
- `wiki/index.md`
- `state/wiki-retrieval/sources/WF88 Compiled Wiki.md`
- `state/cron-contracts/`
- `state/workflows/`

### Live research probes

- `memory_search(corpus="all")` returned correct memory results through Ollama/`nomic-embed-text` but skipped session transcripts because the corpus exceeded the deadline.
- `memory_search(corpus="sessions")` timed out after 15 seconds and returned unavailable.
- Exact file counts and source existence were checked locally on 2026-08-23.
