# Challenge Review - WF74 / WF88 Self-Improvement and OTEL - Opus 5.5 - 2026-09-29

**Reviewer:** `claude-cli/claude-opus-5-5` (Opus 5.5), running as the session model of `agent:main:dashboard:654a8cd1-e495-4c8a-92db-46c9e57d3664`.
**Why in-session:** the owner asked for an Opus 5.5 challenge review before any work. Four dispatches failed about 1 s after admission with `session writer claim changed before transcript persistence`: two native subagents (`281a8cb4`, `b0657671`) and two swarm collectors (`swarm_1bad42ca…`, `swarm_485065d4…`). The alternate self-queued follow-up (`7294e3a1`) was then interrupted by the same error. The session had already been switched to Opus 5.5, so this review runs directly in the session instead of re-sending the message to itself.
**Authority:** read-only challenge. No script, config, cron, skill, or canon change was made; this document is the only file written. Nothing here is an approval.
**Request under review (Randall, 2026-09-29 21:28 Phoenix):** "Proceed with recommendations ensuring our self-improvement recommendations and our OTEL is being surfaced so we can address gaps, continue to improve and keep our workspace fast and efficient. Clean it up and ensure it is placed a good cadence. Before work starts, get a challenge review from Opus 5.5, use Sonnet 5.5 for code, z.ai/GLM5.3 for QA. Review both WF74 and WF88 self-improvement slices and ensure they are well connected and working end to end with most up to date best practices for AI."

---

## Verdict

**The request treats a closure-and-sensing problem as a visibility-and-cadence problem.** More surfacing and more cadence would make it worse. The loop already has about 25 derived packets for 6 open items, two nightly chains, and a nightly Main wake-up.

The three findings below decide whether this workspace can report its own health honestly:

1. **OTEL collects the right data, and the analysis layer does not read it.** The span stream already follows the OpenTelemetry GenAI conventions: `gen_ai.request.model`, `gen_ai.usage.*` tokens on 149 of 155 model calls, `error.type`, span status, and latency.
   - In the last 23.2 h it holds **68 error-status spans**.
   - `otel_ops_control` reports **0 warnings**, because it counts collector *batch* log lines.
   - The 2026-09-12 review found exactly this. A repair was attempted 09-14 and abandoned mid-lease, and it never landed. **17 days later nothing has changed.**
2. **The WF74 queue is mostly rows that cannot be closed by work.** Of 6 open ledger items (after tonight's 21:40 run):
   - Two are standing "learning input" monitors, open since June and re-emitted 19 times each.
   - One is time-gated measurement accrual labelled "overdue".
   - One is a **dead loop that cannot close by design**: its producer is not wired into any runner, and its recommended fix runs the wrong script.
   - "Overdue" ages count from the first-ever sighting, including periods when the item was closed.
3. **The only WF74→Main escalation path has not produced a trustworthy signal in 8 nights.**
   - False "scoreboards unreadable" alarms on 09-22 through 09-26.
   - `DataCloneError` on 09-27 and six times on 09-28.
   - Converted to systemEvent+trigger at 09:30 today; tonight's 22:05 run is its first scheduled run, **unproven**.
   - By design it never re-escalates an item that stays stuck.

**Cadence verdict:** the schedule is already sensible (21:40 digest → 22:05 gate → 22:12 WF88 refresh; 10-minute watchdog; 03:30/03:45 retention; Sunday radar). **No schedule change is recommended.** Every fix below is a script change inside the existing jobs.

---

## Challenges to the plan as proposed

| Proposed | Challenge | Evidence |
|---|---|---|
| Surface self-improvement + OTEL more, at a good cadence | Surfacing is not the bottleneck; closure is. Since 09-12 the overdue count moved from 5 (3 high-priority) to 4 (2), and the ledger grew 585 → 603 rows (576 duplicate-title extras). Add sensing where it is missing (spans), and remove rows elsewhere. | `tmp/improvement-ledger-current.json`; 09-12 review §2 |
| Prior Main's #1: close the 22 planning follow-through gaps | This is lane bookkeeping. The P1 job's acceptance criteria are "completed lanes carry proof and acceptance commands" and "clean rate improves". It optimises a hygiene metric and does not improve sensing or speed. **Demote to P2**; do it opportunistically. | `tmp/wf74-autonomy-work-router.json` `pm_job_candidates[pm-wf74-planning-followthrough-gap-regression]` |
| Improve the metadata failure taxonomy before raising OTEL volume | The 14 MB `otel-tool-workflow-metadata.json` parses prose as tool names. Its 1,033 "unique tools" include `=`, `Bounded`, `Decision`, `Main`, and cron job names, so its "2,414 blocked/status-review" count is not reliable. Replace it with span-derived tool data (`gen_ai.tool.name`) instead of tuning it. | `tmp/otel-tool-workflow-metadata.json` `summary.tool_name_counts` |
| "Most up to date best practices for AI" | The instrumentation already meets current practice (OTel GenAI semantic conventions, `captureContent:false`). The practice gap is downstream. Derive SLIs from spans (error rate by `error.type`, p95 latency, TTFT, tokens and cache by model, failovers). Escalate on SLO breach with a cancellation/rate-limit taxonomy. Keep improvement claims eval-gated; the RSI gate already correctly refuses (6 real rows vs 30 minimum, 0% vs 80% lineage). | span sample below; `tmp/rsi-outcome-scorecard.json` `maturity_gate` |
| Refresh packets by hand to assess state | A partial manual refresh (20:44-20:46) produced split-brain. The router said cron `green_no_repair_required`, while the docket, ledger, actionable queue and dispatcher still said "active cron regression / fix_now 7". Tonight's 21:40 runner healed most of it (fix_now 7→2, open 8→6). **Refresh only through the runners.** | packet `generated_at_utc` comparison 20:45 vs 21:40 |

---

## Verified findings (ranked)

**F1 - OTEL analysis is blind to span-level failures (P1).**
- **Where the analyzer looks:** `scripts/otel_ops_control.py` reads collector `*.err.log` batch lines, so `summary.by_severity = {info: 1885}` and `drift.daily_warning_or_error_count = 0`.
- **What the span file actually holds.** Sample: `tmp/otel-collector/traces.jsonl` (7.3 MB), last 3 MB, **3,931 spans from 09-28 22:31 to 09-29 21:43 (23.2 h)**, sampled at `sampleRate 0.2`. It contains **68 error-status spans**:

  | Span | Errors / detail |
  |---|---|
  | `openclaw.model.call` | 23 (12 `aborted`, 4 `rate_limit`, 4 `Error`, 3 `unknown`) |
  | `openclaw.run` | 14 |
  | `openclaw.harness.run` | 12 (`Error`) |
  | `openclaw.tool.execution` | 8 |
  | `openclaw.liveness.warning` | 8 |

- **Latency:** `openclaw.tool.execution` p95 is 163 s; `openclaw.run` p95 is 348 s.
- **By model:**
  - `xai/grok-4.7`: 2 of 2 calls failed (`Error`).
  - `anthropic/claude-opus-5-5` (claude-code stdio-live): 3 of 5 `unknown` errors, coinciding with tonight's failed Opus dispatches.
  - `anthropic/claude-haiku-4-5` (claude-code stdio): 16 of 33 errors, but 12 are `aborted` (probably auxiliary-call cancellation) and 4 are `rate_limit`. **This is not a 48% failure rate.**
  - `openai/gpt-6-sol`: 2 of 99. GLM 5.3 (ollama-cloud and zai): 0 of 11.
- **Why a taxonomy is required:** without one, a span-based alert would cry wolf on the Haiku cancellations the way the gate did.
- **The metrics sink is equally unused.** It already carries `openclaw.session.stuck`, `openclaw.queue.wait_ms`, `openclaw.gateway.event_loop.delay_max_ms`, `gen_ai.client.token.usage`, and `openclaw.cost.usd`. These are the "keep the workspace fast" signals, and nothing in WF74 consumes them.

**F2 - Dead loop: `otel_telemetry_stale_or_missing` cannot close (P1, cheap).**
- `otel_ops_control.py:40` expects `tmp/otel-token-cost-metadata-depth-owner-packet.json`. The file does not exist.
- Its producer, `scripts/otel_token_cost_metadata_depth_packet.py`, is referenced only by its own test and is in neither nightly runner.
- The action row recommends `otel_runtime_metadata_probe.py`, a different script, so following the recommended action can never clear it.
- Open 374 h, marked overdue.
- Secondary: `ALLOWED_RUNTIME_FIELDS` in `otel_runtime_metadata_probe.py` has no `gen_ai.usage.*` or `openclaw.model_call.usage.*` span attributes, so span-level token depth is invisible to the probe.

**F3 - Escalation gate: 8 nights without a trustworthy signal, and no re-escalation (P1).**
- **Run history** (`openclaw cron runs e3c1b7a8-… --json`):
  - 09-22 to 09-26: "unreadable" false alarms, each costing a Main turn.
  - 09-27 and 09-28: `DataCloneError` (known 2026.9.6 Windows env-Proxy bug, upstream #157067 / PR #158789).
  - 09-29 09:30: job updated to systemEvent+trigger and force-run ok.
- The trigger fires only when `signature` changes. An item that stays open never re-surfaces, which is how an item reaches 90 days.
- The payload also tells Main nightly that "the G8 observation window is active". G8 closed 2026-09-23 (`memory/2026-09-23.md`), so the text misroutes work as "post-G8 backlog".

**F4 - Ledger semantics inflate debt (P1).** Of the 6 open rows (21:40 tonight), 2 are rows that cannot be closed:
- `cron_signal_learning_input` and `workflow_advancement_learning_input` are `monitor_only_standing`, open since 06-16, 19 recurrences each, and still counted in `latest_open_count`.
- `Track WF87 shadow outcomes` is time-gated accrual labelled `overdue`.
- "Regressed after completed pass" items keep their original `opened_at_utc` (2026-08-16) with recurrence 2-3, so age spans closed intervals. Episode age is not tracked separately.
- `Close remaining workflow-maturity follow-ups` gets two incompatible next actions. The queue says "keep visible, do not re-open the completed job". The docket classifies it `fix_now: open a narrow implementation lane and patch the deterministic local blocker`.

**F5 - Split-brain risk from partial refresh (P2).** See the challenge table. The nightly runner heals it. `tmp/actionable-improvement-queue.json` is produced only by the 22:12 chain, so it lags the 21:40 digest by 32 minutes every night and still showed `cron_blocked_count 3` at 21:41.

**F6 - Duplicate nightly work behind a no-op flag (P2).**
- 13 steps run in both the 21:40 digest (36 steps) and the 22:12 refresh (44 steps, about 74 s), 32 minutes apart. Examples include `token_usage_ledger` (24.5 s), `coding_outcome_ledger` (9 s), `otel_ops_control` (6.3 s) and the WF74 chain.
- `wf88_daily_actionability_refresh.py` reports `reuse_fresh_wf74: true` with `fresh_max_age_minutes: 120`, but every step's `reuse_artifacts` is `[]` and all executed.
- Modest cost (about 45 s per night). The flag claims an optimisation that does not happen.

**F7 - Unreliable 14 MB metadata packet (P2).** See the challenge table. It is written nightly by step 1 of the 21:40 digest.

**F8 - Collector hygiene residue (P3, owner-gated).**
- `tmp/otel-collector/` holds 1.1 GB, mostly the live `metrics.jsonl` (567 MB, under daily retention; down from 1.47 GB on 09-12).
- The 979 zero-byte `.pb` files from May are still present. Archive was approved 09-14 but blocked by the forbidden-path guard, and has been untouched for 15 days.
- `logs.jsonl` is 0 bytes.

**F9 - WF88 scaffolds held at zero (owner decision, carried since 09-12).**
- Frontier eval: 100 fixtures, 0 results.
- Advanced pilot: 0 calls.
- The Wave 2 / measured-pilot decision is "parked with Randall".
- These produce standing claim-limits and blockers every night.

**What is healthy (do not touch):**
- Collector (listening, about 78 events/hour, weekly ratio 1.01, `hold_config`).
- Retention jobs.
- WF74 auto-apply is 0, with no authority drift.
- The RSI maturity gate refuses correctly.
- The recommendation outcome grading loop (316 graded).
- Both nightly chains exit 0.
- GLM 5.3 routes: 0 errors in the window.

---

## Bounded implementation plan (safe now)

Code by Sonnet 5.5, QA by GLM 5.3, acceptance by Main. Each slice is sized to finish inside one lease, following the 09-14 lesson.

| Slice | Change | Files (max) | Acceptance tests |
|---|---|---|---|
| **S1 - Span SLI rollup** (F1, F2) | New metadata-only module. Bounded tail read of `traces.jsonl` (time window, byte cap). Per span name: count, error count by `error.type` and `openclaw.errorCategory`, p50/p95 duration. Per provider/model: calls, errors, TTFT p95, input/output/cache tokens from `gen_ai.usage.*`. Also counts failovers, liveness warnings and memory pressure. Taxonomy: `aborted` = cancellation and `rate_limit` = capacity, neither counted as failure. `Error`/`unknown` = failure. Wire it into `otel_ops_control.py` as `span_slis` plus threshold-based `actions`. Replace the missing `token_depth` input with span token coverage, and fix the wrong recommended command. | `scripts/otel_span_sli_rollup.py` (new), `scripts/test_otel_span_sli_rollup.py` (new), `scripts/otel_ops_control.py` (hook ≤40 lines) | (a) Fixture JSONL with known errors, latency and tokens matches hand-computed values. (b) Privacy: output holds only allowlisted keys, numbers and enumerations, never `openclaw.error` free text. (c) ≤3 s on the live file. (d) `otel_ops_control.py --write --write-db --multi-window --validate` passes. (e) On live data it reports the non-zero error spans, and the Haiku `aborted` calls do not raise a failure action. (f) `otel_telemetry_stale_or_missing` clears on the next digest. |
| **S2 - Ledger/docket semantics** (F4) | Standing monitors and learning-inputs move out of open/overdue KPIs, kept in a visible `standing` list. Accrual rows get an `accruing` state with an expected-evidence date instead of `overdue`. Episode age and lifetime age are tracked separately. The docket stops applying the generic `fix_now` template to rows whose route says "do not re-open". | `scripts/improvement_ledger.py`, `scripts/wf74_decision_docket.py`, their tests | Fixture tests for each rule. The live run moves standing rows to `standing` without dropping any: the no-orphan validator passes and the total row count is conserved. Workflow-maturity row next actions agree. |
| **S3 - Gate re-escalation** (F3), after S2 | In the Python prefilter only (`wf74_scoreboard_rollup_trigger.py`): if the same actionable set persists ≥7 days, roll the signature once per ISO week so the unchanged JS trigger re-fires with "still open N days". **No cron JSON change.** | `scripts/wf74_scoreboard_rollup_trigger.py`, test | Unit: same set under 7 days gives a stable signature; at 7 days or more it changes once per week. `cron_contract_validator.py` passes with no pin drift. |
| **S4 - Make reuse real** (F6) | Reuse WF74 artifacts in the 22:12 chain only when fresh (≤120 min) **and** `validation.status == ok`; otherwise execute. | `scripts/wf88_daily_actionability_refresh.py`, test | Fresh fixtures give 13 steps reused with byte-identical artifacts. A stale or failed fixture re-executes. Full live run still reports 44/44 accounted. |
| **S5 - Retire the prose classifier** (F7), after S1 proves out | Swap the classifier's tool-name source to span `gen_ai.tool.name`, or drop the step. Deleting the existing 14 MB artifact is destructive and **asks first**. | TBD after S1 | TBD |

Explicitly **not** in scope: the 22-gap planning bookkeeping (P2, opportunistic), collector config, and any schedule change.

## Owner-gated (not actioned; needs Randall)

- **G1 - 979 zero-byte `.pb` files.** Either approve a guard-scoped archive through the governed cleanup route, or declare them accepted residue and stop surfacing them. They cost only directory clutter.
- **G2 - WF88 scaffolds.** Fund or tombstone the frontier eval (0 of 100) and the advanced pilot (0 calls). Decide Wave 2. Recommendation: tombstone both until a concrete pilot is wanted, which removes their nightly blockers.
- **G3 - Gate payload text.** Remove the stale "G8 observation window is active" line. This is a cron payload/contract edit and should be bundled with any future gate change.
- **G4 - Schedules and collector config.** No change recommended.

## Route blockers for the requested model split

- Anthropic-model spawns (claude-cli runtime) failed 4/4 at transcript persistence tonight; the self-queued follow-up failed the same way. The root cause is not established.
- From a claude-cli session, `sessions_spawn` children are MCP-only and have no file read, write, or exec. **Sonnet 5.5 code therefore goes through the native Agent tool.** GLM 5.3 QA goes through `sessions_spawn` with the diff pasted inline, kept small and sequential (GLM times out on packets over 100 KB).
- The DataCloneError bug (#157067) does not affect this loop's jobs, which are command or systemEvent.

## Evidence index

- Session transcript: failed spawns and self-delivery, seq 133-169. Owner request, seq 129.
- `tmp/otel-ops-control.json`, `tmp/otel-collector/traces.jsonl`, `tmp/otel-collector/metrics.jsonl`
- `scripts/otel_ops_control.py:37-40`, `scripts/otel_runtime_metadata_probe.py:38-73,350-366`
- `scripts/otel_token_cost_metadata_depth_packet.py:25`
- `tmp/improvement-ledger-current.json` and `tmp/wf74-decision-docket.json` (both 2026-09-30T04:40Z)
- `tmp/wf74-autonomy-work-router.json`
- `tmp/wf88-daily-actionability-refresh.json`, `tmp/wf74-model-quality-collection-cron-runner.json`
- `openclaw cron list --json`, `openclaw cron runs e3c1b7a8-d56c-48f5-a0f8-3ca6f12ab132 --json`
- `tmp/rsi-outcome-scorecard.json`, `tmp/otel-tool-workflow-metadata.json`
- `08. Audits/Loop Closure Review - WF74 WF88 Skills Bootstrap Wiki Routing OTEL - 2026-09-12.md` §2, §7, and closure addenda
- `08. Audits/Long Work Orchestration Governance Review - WF74 WF88 OTEL Grok Challenger - 2026-09-14.md`
- `memory/2026-09-23.md` (G8 closed)

---

## Correction addendum - Main, 2026-09-29 ~22:30 Phoenix (supersedes parts of the plan above)

The disciplined-implementation owner-decision pre-check, run before dispatching any code, changed the plan in three ways.

**1. S1 (span SLI rollup) is owner-gated, not "safe now".**
- `state/owner-decisions/otel-recommendations.json` records Randall's `decline_and_retire_the_recommendation` for `token_cost_metadata_depth` (2026-09-12T15:17:06Z, webchat ask_user).
- The depth packet's option 3 was a review-only `traces.jsonl` token reader. It was not chosen and is marked `not_started_requires_separate_owner_approval`.
- Its preconditions are still open:
  - `traces.jsonl` has no retention policy;
  - `openclaw.error` free-text redaction must be validated first;
  - the counting basis must be labelled.
- S1 reads `traces.jsonl`, so it needs a deliberate re-raise. The new evidence (68 error spans, latency p95) concerns errors and latency, not the token coverage that was declined. That is a new question for Randall and cannot be inferred from "proceed".

**2. F2 had a deeper root cause.** The fix is to honor the decision, not to wire up the retired producer. Verified defects:
- **Seam break.** `otel_learning_loop.build_payload()` reads `telemetry_context` from `tmp/otel-ops-control.json`, which never contains it. `otel_ops_control.py` writes it only to `tmp/otel-ops-window-summary.json`. The loop's telemetry status is therefore permanently `missing` (`tmp/otel-learning-loop.json` → `learning_summaries.otel_health.telemetry_status = missing`). The ledger row `otel_telemetry_stale_or_missing` could never clear, whatever the depth packet said.
- **Latent defect.** The embedded `token_depth` row never carried `generated_at_utc`. The loop's per-row timestamp check would have rejected it even with a pending packet.
- **Stale gate.** Both files still required a *pending* owner packet 17 days after Randall retired the question. No runner regenerates that packet.
- **Wrong remediation text.** The action recommended the runtime-probe command even though the probe was fresh and valid.

The fix is lane `WF74::otel-telemetry-seam-20260929`, contract `tmp/impl-otel-telemetry-seam-20260929/contract.md`. It does the following:
- The producer reads the owner-decision store fail-closed and copies only id/decision/decided_by/decided_at, never free text.
- The consumer reads the window packet and cross-checks the retirement against the same store.
- The recommended command follows whichever input actually failed.
- There is no collector, config, cron, or capture change.

**3. Re-ranked "safe now": only the F2 correction.**
- S2 changes debt accounting, which is anti-theater-sensitive.
- S3 would increase Telegram escalations, which is outward-facing. Both are owner decisions now.
- S4 is low value and deferred.
- S5 depends on S1.

**Process note.** In a git worktree with `core.autocrlf=true`, `tools/otelcol/openclaw-local-otel-runtime-metadata.yaml` checks out with CRLF, its SHA-256 no longer matches the approved `c9b51de5…`, and two approval-identity tests fail on an untouched baseline. That is an environment artifact, not a code defect. Check out that file with LF before validating in a worktree.
