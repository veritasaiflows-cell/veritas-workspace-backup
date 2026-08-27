# OTEL, Learning Loop, Session Carryover & Scorecard Audit — 2026-06-15

**Author:** Veritas (main session) · **Date:** 2026-06-15 (Mon, America/Phoenix)
**Scope:** OpenTelemetry stack, the cadence by which we learn from telemetry, how learnings reach new sessions, and how learning loops + scorecards are used to improve the system.
**Posture:** Review-only audit. No cron, config, or runtime changes were made. Findings are evidence-grounded and verified against live process/files (see Verification Log).

---

## Bottom line

The observability and learning machinery is **real, live, and privacy-clean — not theater.** A live `otelcol.exe` collector has been running continuously since 2026-06-10, the WF74 "Recursive Self-Improvement" loop genuinely turns telemetry into owner-gated improvement proposals and delivered today's digest to Telegram, and the core scorecards are fresh and consumed.

But the system is stronger at **producing** insight than at **propagating and closing** it. The four weak spots:

1. **Carryover to new sessions is double-manual and stale.** The hand-off packet that is supposed to carry learnings forward is ~22h stale, is not on any schedule, and only loads if the model chooses to read it. This is the weakest link in "making future sessions better."
2. **Learning depth is metadata-thin where it matters most.** Token coverage 12.8%, cost coverage **0%**, 171 "unknown" model rows — the loop cannot reliably learn model-routing economics. (The loop already flags this itself.)
3. **Self-assessment is partly wrong.** `otel_ops_control.py` audits a *different* collector config than the one actually running, producing contradictory "no token/cost captured" claims.
4. **Operational hygiene debt.** A 1.39 GB un-rotated collector log, three orphaned scorecards, a dead Python collector, and a stale privacy-governance packet.

None of these are safety/authority breaches. Privacy posture is intact (no content/secret capture, loopback-only, no external export).

---

## 1. OTEL telemetry stack

### What is collected
The **live** layer is the OpenClaw `diagnostics-otel` gateway plugin exporting OTLP to a local Go collector. Confirmed signal fields (23 types) include: `openclaw.tokens`, `openclaw.cost.usd`, `openclaw.context.tokens`, `openclaw.run.duration_ms`, `gen_ai.client.token.usage`, `gen_ai.request.model`, `gen_ai.operation.name`, provider/model/channel (webchat/telegram/cron), `model_call.duration_ms / request_bytes / response_bytes / time_to_first_byte_ms`, `errorCategory`, `failureKind`, `toolName`, `tool.source/owner/params.kind/execution.duration_ms`. A **derived** layer (`model_run_ledger`, `model_learning_metadata_ledger`, `otel_tool_workflow_metadata`, `coding_runtime_kpi_probe`) joins these with cron-run history and lane/workflow/session IDs into metadata-only ledgers.

### Storage (all local under `tmp\`)
- **JSON:** `otel-ops-control.json`, `otel-ops-window-summary.json`, `otel-learning-loop.json`, `otel-runtime-metadata-probe.json`, `model-run-ledger-current.json`, `model-learning-metadata-ledger.json` (1.05 MB), `otel-tool-workflow-metadata.json` (2.7 MB)
- **JSONL:** `otel-ops-events.jsonl` (3.6 MB), `data\state-history\model-run-ledger.jsonl`
- **SQLite:** `tmp\otel-ops.sqlite` (~4 MB; tables `otel_events`, `otel_action_candidates`; ~13,566 events)
- **Raw collector log:** `tmp\otel-collector\collector.err.log`

### Live status — confirmed running
`otelcol.exe` **PID 14632**, started **2026-06-10 08:19**, loopback `127.0.0.1:4318`, config `tools\otelcol\openclaw-local-otel-runtime-metadata.yaml` (verbosity **detailed**). Log actively written (last 2026-06-15 20:41 local). This is real continuous telemetry, **not** synthetic. Daily health: `collector_health=ok`, 1,737 events/day, 0 warnings/errors, drift ok.

> Note: the Python `scripts\local_otel_collector.py` is a **dead prototype** superseded by `otelcol.exe`. Its `tmp\otel-collector\*.pb` payloads are all 0-byte and `receipts.jsonl` froze 2026-06-10 — yet `otel_ops_control.py` still parses that frozen file.

### Cadence
- **OTEL Local Digest** (cron `Ops - OTEL Local Digest`, `40 7,15,21 * * *` America/Phoenix, isolated): **3×/day** at 07:40 / 15:40 / 21:40. Runs `wf74_model_quality_collection_cron_runner.py --write --write-md --validate` (the 25-step collection chain), refreshing all OTEL + ledger + scorecard artifacts.

### Privacy posture — intact
`captureContent.enabled=false` and all five subkeys false (inputMessages / outputMessages / toolInputs / toolOutputs / systemPrompt); OTLP logs export off; loopback-only; hashed request IDs only; no headers/secrets. Live scan of the learning loop returned **0 privacy findings**. Allowed = metadata (model/provider, token/cost/latency numbers, tool names, IDs, status/failure categories). Blocked = raw prompts/responses/tool payloads/system prompts/secrets/customer-account data.

### Freshness — current
All live OTEL artifacts regenerated **2026-06-15 18:15–18:17 local** (today). Collector log live to 20:41.

---

## 2. Learning cadence & loop — WF74 "Recursive Self-Improvement"

WF74 (tier P1, `route_only`, "review-only; no self-modification/authority expansion") **is** the learning loop. Every component hard-codes `auto_apply_allowed=False`, `code_mutation_allowed=False`, `owner_approval_inferred=False`.

### Pipeline (single runner `wf74_model_quality_collection_cron_runner.py`, ~22 ordered steps)
1. **Collect** — `otel_ops_control`, `otel_tool_workflow_metadata`, `coding_outcome_ledger`, `validator_timing_ledger`, `finance_response_quality_slice`, `model_run_ledger`
2. **Synthesize** — `otel_learning_loop.py` → `tmp/otel-learning-loop.json` (metadata-only recommendations)
3. **Rank** — `wf74_improvement_opportunity_queue.py` → scored opportunities tagged with a `proposal_gate`
4. **Propose** — `wf74_reflection_to_proposal_autopilot.py` → bounded proposals
5. **Patch-plan** — `wf74_auto_patch_proposer.py` → target files, tests, rollback, lane contract (`auto_apply_eligible` hardcoded False)
6. **Persist** — `improvement_ledger.py` → append-only `data/state-history/improvement-ledger.jsonl` + `tmp/improvement-ledger-current.json` (SLA + carry-forward)
7. **Notify** — `wf74_learning_loop_telegram_digest.py`; **Rollup** — `wf74_operating_control_loop.py`

### Automated vs gated
Automated: collection, ranking, proposal + patch-plan drafting, ledger persistence, Telegram delivery. **Human gate is at APPLY** — patches need a scoped implementation lane; skill/config/finance/execution changes need explicit Randall approval. Forbidden patch targets include `SOUL.md`, `AGENTS.md`, `03. Portfolio/`, `state/finance/`, credentials.

### Real output today (2026-06-16T01:17Z gen)
Two proposals, both owner-gated, 0 auto-apply:
- `wf74-proposal-876e11ae8497` (collector_config / owner_decision_required): "Owner-gated OTEL field-depth decision packet is ready… hold collector config unchanged."
- `wf74-proposal-9a211288c836` (execution / exact_owner_approval_required): "Maintain execution as proposal-only and exact-owner-gated."

### Daily digest — delivered
`WF74 - Learning Loop Telegram Digest` (`15 18 * * *`, isolated). Today: mode=send, after-6pm gate passed, **reached Randall** (`send_result.ok=true`, Telegram message ID 3231). Delta-gated so identical signatures don't re-send.

### Is the loop closed?
**Partially — by design.** insight → proposal → persist → notify is fully closed and automated. The **apply → measure** leg is manual: a human runs an implementation lane, and improvement is recorded in hand-written closeout artifacts. Proven historical full closure exists, e.g. `tmp/wf74-model-path-runtime-stamping-closeout.json` (2026-06-12): a proposal became an applied patch to `concurrent_lane_manager.py`, tests passed, and `model_attribution_coverage` measurably rose to 0.431. But there is **no automated outcome measurement** — the loop does not re-check a metric after an item is marked applied.

### Weekly touchpoint
`Runtime - Weekly OS Improvement Radar Review` (Sun 16:30, **main session**) prompts a human to review friction surfaces and report a proposal; it explicitly forbids creating patches/commits "from this reminder alone." It does **not** auto-consume scorecard JSON.

---

## 3. Carryover to new sessions

### Mechanism
Per `AGENTS.md` → `06. Playbooks/Startup Truth Index.md`, a new/post-compaction session loads `SOUL.md`, `USER.md`, `TOOLS.md`, the Startup Truth Index, today's + yesterday's daily notes, then `MEMORY.md` and workflow capsules. Two surfaces carry *learnings* forward:
1. **`tmp/future-session-enhancement-packet.json`** (`future_session_enhancement_packet.py`) — bundles PM/cron/WF74 state, capsules, improvement-ledger summary, challenger policy, stop-lines. Listed in Startup Truth Index step 4 + Load Map and TOOLS.md.
2. **`improvement_ledger`** (`tmp/improvement-ledger-current.json` + durable `data/state-history/improvement-ledger.jsonl`) — the true append-only learning carry-forward; Startup Truth Index Load Map says "Load in new sessions before recommending OS/WF74 improvements."

### The gap (weakest link in "getting better over time")
- **Model-dependent, not enforced.** No hook/preload injects the packet. Carryover happens only if the model both *regenerates* and *reads* these files per the Startup Truth Index.
- **Stale.** `future-session-enhancement-packet.json` last modified **2026-06-14 22:27**, while its inputs (`improvement-ledger-current.json`, `model-quality-scorecard.json`) refreshed **2026-06-15 18:17** and today's daily note is 20:10. A new session reading it without regenerating gets ~22h-old state.
- **No staleness signal.** The packet's validator flags only *missing* inputs and `validation!=ok`; it does **not** warn when an input is stale-but-present. A session can trust a "status=ok" packet built on day-old scorecards.
- **Not scheduled.** Neither `future_session_enhancement_packet.py` nor `startup_brief_packet.py` is invoked by any cron contract.

---

## 4. Scorecards

| Scorecard | Measures | Last-modified | Consumed by | Health |
|---|---|---|---|---|
| `model_quality_scorecard` | Model output quality (impl/perf/decision) | 2026-06-15 18:17 | **Hub**: WF74 loop, future-session packet, PM packets, learning ledger, cron-freshness | Fresh + consumed |
| `veritas_harness_scorecard` | Readiness/validation pass-rate across proof surfaces | 2026-06-15 20:10 | Broad: model-quality, python_go gates, PM, retail/wf75 | Fresh + consumed |
| `wf87_shadow_outcome_scorecard` | Paper-autotrader shadow-decision outcomes | 2026-06-15 14:37 | Deep: WF55/WF86/WF87 autonomy chain, cron-freshness | Fresh + consumed |
| `workflow_advancement_scorecard` | Autonomy-spine advancement readiness | 2026-06-15 15:25 | autonomy-spine rollup, cron-freshness | Fresh + consumed |
| `cron_signal_scorecard` | Cron operator signal/escalation quality | 2026-06-15 15:12 | escalation-trigger, cron-freshness, PM job queue | Fresh + consumed |
| `runtime_performance_scorecard` | SQL/Go latency, parity, runtime KPIs | 2026-06-14 18:47 | model-quality, harness, python_go gates | Consumed, ~1d stale |
| `openclaw_cache_efficiency_scorecard` | Tool-result cache hit/efficiency | 2026-05-30 20:35 | only `automation_health_dashboard` | **Stale 16d, weak/orphaned** |
| `wf73_route_efficiency_scorecard` | JSON-vs-SQLite routing lookup latency | 2026-06-07 15:14 | none (self-ref only) | **Stale 8d, orphaned** |
| `retrieval_quality_scorecard` | Workspace/artifact SQLite retrieval quality | 2026-05-24 17:05 | none (self-ref only) | **Stale 22d, orphaned/dead** |
| `post_earnings_scorecard` | Per-ticker post-earnings interpretation MD | on-demand | human-read earnings note | Standalone by design |

> Distinct from the orphaned `wf73-efficiency-scorecard.json`: a separate `route_efficiency_scorecard.py` (`route-efficiency-scorecard.json`, 2026-06-14) **is** consumed by `model_quality_scorecard`.

### Feedback gap
The automated learning loop consumes only **one** scorecard directly — `model_quality_scorecard` (which internally folds in harness + runtime-perf + route-efficiency). **cron-signal, workflow-advancement, wf87-shadow, cache-efficiency, retrieval-quality do not feed the improvement ledger.** They feed escalation, dashboards, and autonomy rollups in parallel silos, so their friction signals never become OS-improvement candidates automatically.

---

## Findings (ranked)

| # | Severity | Finding |
|---|---|---|
| F1 | Med-High | `collector.err.log` is **1.39 GB with no rotation** (verbosity `detailed`); SQLite/JSONL ledgers also grow unbounded. Disk-growth risk. |
| F2 | Medium | **Config-target mismatch**: `otel_ops_control.py:29` audits `openclaw-local-otel.yaml` (basic) but the live process runs `openclaw-local-otel-runtime-metadata.yaml` (detailed). The ops packet's "no token/cost captured" claim contradicts the live data. Self-assessment is partly wrong. |
| F3 | Medium | **Session carryover is double-manual + stale + has no staleness signal.** The future-session packet is ~22h old, unscheduled, and only loads if the model reads it. Weakest link in cross-session improvement. |
| F4 | Medium | **Learning depth thin**: token coverage 12.8%, cost coverage **0%**, 171 "unknown" model rows. Model-routing economics not reliably learnable. (Loop self-flags `token_cost_metadata_depth`.) |
| F5 | Low-Med | **Three orphaned/stale scorecards** (retrieval-quality 22d, cache-efficiency 16d, wf73-efficiency 8d) with no real consumer — maintenance debt + confusion risk. |
| F6 | Medium | **Narrow loop inputs**: only `model_quality_scorecard` reaches the improvement ledger; cron-signal / workflow-advancement / wf87-shadow friction never becomes an OS-improvement candidate. |
| F7 | Low-Med | **Apply→measure leg is manual**; no automated outcome measurement of whether an applied improvement actually helped. |
| F8 | Low | **Doc/dead-code hygiene**: stale privacy packet (`openclaw-otel-privacy-packet.json`, 2026-05-24, still says "not enabled" though plugin is live); dead `local_otel_collector.py` + 0-byte `.pb` files + frozen `receipts.jsonl` still parsed by `otel_ops_control.py`. |

---

## Recommendations (ranked)

| # | Rec | Risk | Authority |
|---|---|---|---|
| R1 | Add rotation/size-cap for `collector.err.log` + retention policy for the growing SQLite/JSONL ledgers. Consider lowering collector verbosity `detailed`→`normal` if the extra detail isn't consumed. | Low (rotation script = workspace); **verbosity change = owner-gated config** | Mixed |
| R2 | Fix `otel_ops_control.py` to audit the actually-running `-runtime-metadata.yaml`, removing the contradictory field-inventory claims. | Low | Workspace code (disciplined-implementation lane) |
| R3 | **Highest carryover win.** Schedule `future_session_enhancement_packet` regeneration (e.g. after the 18:15 WF74 digest + an early-morning run) **and** add a staleness warning to its validator (warn when an input is older than N hours, not just missing). | Low (validator code = workspace); **cron add = owner-gated** | Mixed |
| R4 | Prepare the owner-gated, local-only, redacted **token/cost metadata-depth config patch** the loop already recommends, so model-routing economics become learnable. Present as an approval card. | Owner decision | Config — owner-gated |
| R5 | Decide the three orphaned scorecards: wire `retrieval-quality` / `cache-efficiency` into `model_quality_scorecard` (so they feed the loop), or archive via the gated reference-review path. `wf73-efficiency` looks like a one-shot baseline → archive. | Low | Workspace (archive = gated reference-review) |
| R6 | Broaden the loop: feed `cron_signal`, `workflow_advancement`, and `wf87_shadow_outcome` scorecard deltas into `otel_learning_loop` / `improvement_opportunity_queue` so non-model friction also becomes improvement candidates. | Low-Med | Workspace code |
| R7 | Add a lightweight automated outcome-measurement step: when an improvement-ledger item is marked applied, re-read the target metric and record before/after, closing the measure leg instead of relying on hand-written closeouts. | Medium | Workspace code |
| R8 | Refresh/retire the stale privacy packet; propose the dead Python collector + 0-byte `.pb` cruft for archival; stop `otel_ops_control.py` parsing the frozen `receipts.jsonl`. | Low | Workspace (deletes = gated reference-review) |

**Suggested sequencing:** R1 + R2 + R3 first (reliability + the contradiction + the carryover gap — biggest payoff, lowest risk). Then R5/R8 hygiene. Then R6/R7 design upgrades. R4 is a standalone owner decision (approval card).

---

## Verification log (checked live, 2026-06-15)

- `otelcol.exe` PID 14632 running since 2026-06-10 08:19; live config `openclaw-local-otel-runtime-metadata.yaml` — **Get-CimInstance / Get-Process**
- `collector.err.log` = 1391.7 MB, mtime 2026-06-15 20:41 — **Get-Item**
- `future-session-enhancement-packet.json` mtime 2026-06-14 22:27 vs sources 2026-06-15 18:17 — **Get-Item**
- Orphaned scorecards: retrieval-quality 2026-05-24, cache-efficiency 2026-05-30, wf73-efficiency 2026-06-07 — **Get-Item**
- `otel-learning-loop.json`: collector_health ok, 1737 events/day, token_coverage 0.1279, cost_coverage 0.0, 171 unknown model rows, privacy_scan 0 findings — **read live**
- `otel_ops_control.py:29` default config = `openclaw-local-otel.yaml` (mismatch vs live) — **grep**
- Cron cadence (OTEL digest 07:40/15:40/21:40; WF74 digest 18:15; weekly radar Sun 16:30) — **live cron list**
- WF74 pipeline, gating, today's 2 owner-gated proposals, Telegram delivery (msg 3231), historical closeout examples — **sub-agent deep-dive, artifacts dated 2026-06-16T01:17Z**

## Authority boundary

This audit changed nothing. All recommendations preserve existing boundaries: no raw-content/secret capture, loopback-only, no external export, no auto-apply, no finance/capital/execution authority. Cron and collector-config changes (R1 verbosity, R3 cron, R4 config) require explicit owner approval before implementation; workspace code/validator/hygiene changes (R2, R5–R8) are eligible for a normal disciplined-implementation lane with proof.
