# Loop Closure Review - WF74, WF88, Skills, Bootstrap, Wiki, Routing, OTEL - 2026-09-12

**Scope:** WF74, WF88, the skills layer, bootstrap files, wiki, routing files, and OTEL. Question asked: are the loops well established, are improvements closing, and is anything needing attention.

**Method:** read-only. Four parallel helper audits, then Main verification of every material claim against live artifacts, script source, and the live scheduler. No file was written outside this report. No script was run with `--write`.

**Authority:** review-only findings. Nothing here is an approval, and no remediation was applied.

---

## Verdict

**The loops are well *built* and poorly *closed*.** The machinery is real — 1,485 scripts, 57 live skills, 73 tracked cron jobs, a live OTEL collector, 44 routed workflows. What is missing is the closing half: improvements are generated faster than they are retired, and the health signals that should say so are structurally incapable of saying it.

Three findings are load-bearing:

1. **`blockers` is a hardcoded literal, not a computed signal.** No amount of staleness, validator warning, or overdue debt can ever raise a blocker. WF74 reports `blockers: []` while its own proof artifact is 15 days stale and that artifact internally declares two blockers of its own. The green light is not wired to anything.
2. **The main heartbeat has been failing for 7.6 days, right now.** Five consecutive timeouts. It is still firing every ~5h and still producing nothing. This is the only finding in this report that is actively degrading and not merely stale.
3. **The improvement loop's own anti-theater metric has tripped.** `anti_theater_status = blocked_by_overdue_backlog`. Only 7 of 42 tracked improvements ever became an applied fix — a 16.7% real-fix rate against a headline 78.6% "closure rate."

Nothing found here touches finance canon, capital, accounts, or execution authority. The damage is to trustworthiness of self-reported health, not to safety boundaries.

---

## 1. The blocker-detection defect (root cause of several symptoms)

In `scripts/workflow_routing_index.py`, every route's `blockers` field is a literal list written into the source:

- WF88's 14 blockers are string literals at lines **1426-1439**.
- `"blockers": []` appears as a literal at lines 2680, 2718, 2780, 2808, 2868, 2898, 2930, 2952.
- The **only** dynamic mutation is lines 2297-2301, appending `f"Canonical Active Workflows hold: ..."`, gated solely on `canonical_hold`.
- `scripts/workflow_router.py:216` copies the value verbatim.

Staleness is computed, but routed elsewhere — into `readiness`:

```python
elif material_context in {"aging", "stale", "missing"}:
    readiness = "refresh_required"
```

**Consequences, both verified:**

- **WF74 shows `blockers: []`** while `tmp/autonomy-spine-readiness-rollup.json` is 358h (14.9d) stale and that file's own `summary.blockers` reads `["wf87_runtime_gates_not_clean", "cron_cadence_not_clean"]`. The router does not surface its own proof artifact's declared blockers.
- **WF88's 14 blockers can never clear.** They are frozen prose. One is provably wrong: it asserts *"34 disabled cron rows still have active code/control refs and 11 review refs."* The fresh cron packet counts **31** disabled jobs total; the backing review artifact `tmp/wf88-cron-disabled-job-reference-review.json` reports `blocked_by_active_reference_count: 1` and `blocked_by_review_reference_count: 0`. Neither number is 34 or 11.

This one defect explains why WF88 is permanently `refresh_required` and why WF74 looks unblocked while stalled.

---

## 2. WF74 — Recursive Self-Improvement: generating, not retiring

Router state: `lifecycle=active`, `readiness=refresh_required`, `blockers=[]`, `authority_class=review_only`.

**Closure quality** (`tmp/improvement-ledger-current.json`, written today, `status: warning`):

| Metric | Value |
|---|---|
| Open / closed | 9 / 33 |
| Headline closure rate | 0.7857 |
| **Applied-fix closures** | **7** |
| **Applied-fix closure rate** | **0.1667** |
| Closed as `superseded` | 11 |
| Closed as `monitor_only` | 10 |
| Overdue open | 5 (3 high-priority) |
| `anti_theater_status` | **`blocked_by_overdue_backlog`** |

Two-thirds of "closures" are supersession or parking — renaming an item, not fixing it.

**Ledger churn:** `data/state-history/improvement-ledger.jsonl` holds 585 events with `historical_duplicate_title_extra_count: 560`. The same small set of items is re-appended rather than resolved.

**Regression signal:** `tmp/wf74-improvement-opportunity-queue.json` reports `regressed_after_completion_count: 2` — items previously closed that reopened. The loop is losing ground on work it already claimed.

**Downstream evidence is thin or frozen:**

- `tmp/rsi-outcome-scorecard.json` (6d stale): 7 live rows, `live_complete_stable_count: 0`, `missing_link_debt_item_count: 50`.
- `data/state-history/retrieval-live-eval.jsonl`: **3 rows**, all `draft_review_required`, newest 2026-08-09 (34d).
- `tmp/retrieval-live-eval.json`: 830h (35d) stale.

**Validators pass, and that is the problem.** `python -B scripts/wf74_rsi.py --validate-only` → ok, 29 checks, 0 failed. `python -B scripts/test_retrieval_live_eval.py` → 13 tests OK. Both check schema and contract shape; neither checks artifact freshness or backlog closure. They stay green while the loop stalls — which is exactly how a stalled loop goes unnoticed.

---

## 3. WF88 — OS 2.0: frozen at the decision layer

Router state: `readiness=refresh_required`, `owner_action_required=true`, next action *"Stop and seek a separate decision before Wave 2."*

**Blocker classification (14 total):**

| Class | Count | Character |
|---|---|---|
| Genuinely actionable | ~6 | Call Log intake, overdue ledger debt, retrieval gold review, frontier collection, RSI linkage, pilot execution gate |
| Clears on refresh | ~2 | DB duplication audit, retrieval artifacts |
| Permanent scope disclaimer | ~6 | "not an autonomy claim", "metadata-only", "do not duplicate the body guard" |

Roughly six items are real work. The rest are caveats occupying blocker slots, which is why the list never shrinks.

**Measurement scaffolds with zero data, verified:**

| Artifact | Age | Content |
|---|---|---|
| `tmp/frontier-capability-eval-spine.json` | 831h (35d) | 100 cases, 300 assignments, **0 results** |
| `tmp/advanced-capability-pilot-packet.json` | 842h (35d) | 6 pilots, **0 executed**, 0 promotion-ready |
| `tmp/wf88-decision-compiler.json` | 842h (35d) | still consumed by `agi_os_eval_gate_packet.py` |
| `tmp/retrieval-quality-scorecard.json` | 830h (35d) | fixture corpus 42/42, not live |

These have sat at zero for 35 days. They are either underfunded or should be retired; holding them open costs credibility in every rollup that cites them.

**Refresh coverage gap:** the daily "Runtime - WF88 Wiki Synthesis Refresh" cron runs 21 commands. `wf88_decision_compiler.py`, `retrieval_quality_scorecard.py`, and `rsi_outcome_scorecard.py` — the three stale secondaries — are **not among them**. Meanwhile the freshly-written control packet re-exports their August numbers under `wiki_*` keys, which makes 35-day-old data render as current.

**Cleanup is stalled.** `tmp/db-lifecycle-manifest.json` (327h stale): `archived_count: 2`, `delete_ready_count: 0`. Every apply path reads 0-ready. Nothing has moved since late August.

**One loop genuinely converges:** recommendation outcome grading — 415 rows, 316 graded, 304 later-outcome graded in `data/state-history/recommendation-outcome-grades.jsonl`. This is the model of what the others should look like.

---

## 4. Cron and heartbeat — the one live failure

`tmp/cron-control-packet.json`: `status: error`, `freshness.status: blocked`. 73 jobs tracked (42 enabled, 31 disabled), **6 blocked/urgent**.

**`heartbeat-main` is failing now.** Confirmed against the live scheduler, not just the artifact:

```
lastRunStatus:  error
lastRunError:   "cron: job execution timed out"
consecutive_errors: 5
lastRunAt:      2026-09-12 08:37:54 (4.9h ago)
expected artifact age: 183.5h (7.6 days)
```

It is still firing on schedule and still producing nothing. Seven and a half days of `HEARTBEAT.md` vigilance has silently not happened. Every other finding in this report is stale data; this one is an ongoing outage.

Also blocked: `Cron Reduction - Control Fail-Closed Dispatcher`, `Runtime - Cron Efficiency and Prompt Integrity Review`, `Runtime - Weekly OS Improvement Radar Proof Refresh`, `Runtime - Weekly OS Improvement Radar Review`.

**Inventory drift:** live scheduler reports **76** jobs; the workspace packet tracks **73**. `unregistered_enabled_count: 1` (`runtime-heartbeat-1315-check`).

---

## 5. Skills and bootstrap

**Governance index accounting is wrong.** `06. Playbooks/Skills Governance Index.md:20` claims *"44 canonical + 13 retired/deprecated fallbacks"* (=57). Reality: **50** distinct names across governance table rows, **57** live `SKILL.md` bodies, **58** directories.

**Eight skill directories appear in no governance table row:**

`qa-source-reasoning-review`, `qa-diff-safety-review`, `qa-evidence-separation-check`, `disciplined-implementation-linux-steps`, `patch-draft-bounded-linux`, `linux-workspace-proof-runner` (the six WF89 Phase B skills, mentioned in prose at line 24 but never added to the tables), plus **`sec`** and **`graphify-out`**.

`skills/graphify-out` is **not a skill** — no `SKILL.md`, contents are `cache/stat-index.json` and an AST cache blob. It is stray Graphify output sitting in the skills namespace. Maintained graph scope is `scripts/graphify-out` per Startup Truth Index:41.

**The core-skill proof gate is red — because the validator is stale, not the skill:**

```
python -B scripts/skill_core_proof_tier_audit.py --skills-dir skills --validate
→ validation.status: "blocked"
  critical / required_term_missing / term: "Luna"
  skill: veritas-model-routing-helper-lanes
```

`scripts/skill_core_proof_tier_audit.py:172` still requires the literal term "Luna". Luna (`openai/gpt-5.6-luna`) was moved into `LEGACY_DENIED_MODELS` (`scripts/agent_fleet_policy.py:39-46`) in the 2026-09-10 OpenAI removal. The skill correctly dropped the term; the validator did not. **Fix the validator, not the skill.** Note the same contract still requires "Terra" and "Sol" — "Terra" survives only via a deny-context sentence at `skills/veritas-model-routing-helper-lanes/SKILL.md:19`, and "Sol" passes only by accidental substring match. All three terms need re-basing.

**Bootstrap linter is red:**

```
python -B scripts/agent_bootstrap_linter.py --agents all --validate  → exit 1
errors: ["manifest runtime_tool_posture mismatch; effective configured posture is required",
         "known profile runtime_tool_posture mismatch"]
agent: implementation-builder   (agent_count 6, error_count 2)
```

Tool-policy drift on the one lane authorized to write code. The generator itself validates clean.

**Fleet policy — mostly agrees, one drift.** All six specialist pairings at `Startup Truth Index.md:59` match `agent_fleet_policy.py:52-68` exactly. But Main's fallback chain does not: Startup Index:58 and `MEMORY.md:22` say GLM 5.3 → Kimi K3 → zAI GLM 5.3 → Opus 5, while `agent_fleet_policy.py:50` has `MAIN_FALLBACKS = [GLM_MODEL, KIMI_MODEL, BUILDER_MODEL]` — Muse Spark, no zAI, no Opus.

**Retired models still asserted as live posture** in `Skills Governance Index.md:126,145,154` (Sol, Astra, Terra, Luna) and `skills/disciplined-implementation/SKILL.md:26` ("Main/Astra for integration") — Astra is denied and Main is Grok 4.6.

**Boot size:** `scripts/boot_surface_size_guard.py --validate` → exit 0, `status: warning`, 0 hard failures, 3 warnings. `MEMORY.md` 10,531 B (warn 10,000 / max 12,000); `AGENTS.md` 10,142 B; `Active Workflows.md` 22,386 B. Within hard limits, all three over soft.

**Doctrine ambiguity:** `TOOLS.md` self-declares retired, while `MEMORY.md:8` and `CLAUDE.md:4` still name it active doctrine, and `AGENTS.md:66-74` embeds a stale copy of its old text under a duplicate H1 (with an empty `### Local Runtime And Route Map` heading at line 64). `IDENTITY.md` is declared retired at `AGENTS.md:125` and `MEMORY.md:17` yet was modified 2026-09-05 and is still treated as live by `GEMINI.md:4`. `DREAMS.md` (87 KB, modified today) is referenced by no doctrine file.

---

## 6. Wiki and routing

**Wiki is small, honest, and half-stale.** 15 pages, 15/15 present per `scripts/wiki_bootstrap_validator.py --validate` (`bootstrap_warning_no_apply_authority`, 0 errors, 3 classified warnings). **0 broken source references** across 38 checked — genuinely good hygiene. The wiki does not overstate state; `README.md` reports `repair_required` / `warning` / `followup_required` accurately.

Five pages are 31 days old: `decisions/` and `syntheses/` are 100% stale (one page each), `scorecards-and-evals/` is half stale. The source map self-labels 12 of its 31 tracked artifacts as `stale`.

**Index inversion:** `wiki/index.md` is 3 days old while six pages it indexes were written today. Its summary counters describe page bodies that have since changed. Cause: the "Runtime - WF88 Wiki Synthesis Refresh" cron is at **327.3h (13.6 days)**, status `standing_review_quiet`.

**Routing inventory:** 44 routes. 14 active (12 `refresh_required`, 2 `route_only`), 7 gated, 8 monitor, 15 paused. Freshness overall: **29 stale / 11 fresh / 2 aging**.

Five named routes have no match in the declared `source_authority` (`06. Playbooks/Active Workflows.md`): `WF-CHIEF-GATE`, `WF-FINANCE-CHAINS`, `WF-BOARD-CANON-GUARDRAILS`, `WF-SQL-INDEXES`, `WF-WORKSPACE-GOVERNOR`. Other apparent mismatches are composite-ID aliasing and not real gaps.

`scripts/project_implementation_router.py` has no read-only route dump — it requires `--title`/`--description` to emit anything, so its current routing posture cannot be inspected without constructing a task.

---

## 7. OTEL — collecting hard, analysing almost nothing

**It is live.** Config in `~/.openclaw/openclaw.json` `.diagnostics.otel`: `enabled: true`, endpoint `http://127.0.0.1:4318` (loopback), `sampleRate: 0.2`, traces+metrics on, `captureContent: false`, **no credential present**. Both digest crons are fresh (5.3h, 10.0h).

| File | Size | Newest record |
|---|---|---|
| `tmp/otel-collector/traces.jsonl` | 18.7 MB | 2026-09-12 |
| `tmp/otel-collector/metrics.jsonl` | **1,468,446,557 B (1.47 GB)** | 2026-09-12 |
| `tmp/otel-ops.sqlite` | 26 MB | 87,182 rows |

**The analysis loop reads the wrong file.** `scripts/otel_ops_control.py:29` sets `DEFAULT_LOG_GLOB = "tmp/otel-collector/*.err.log"` — the operations analyst consumes **collector error logs only**, never `traces.jsonl` or `metrics.jsonl`. Roughly 65% of the sqlite event store originates from `collector.err.log`. **OTEL is currently observability of the collector, not of the agent.**

Only two scripts read the real telemetry: `otel_runtime_metadata_probe.py` and `otel_token_cost_metadata_depth_packet.py`. What survives the trip to the scorecard is field *presence counts*, not values — `openclaw.cost.usd` observed **4 times against 8,323 reported spans**. Terminal state: `tmp/model-quality-scorecard.json` is `status: scaffold_active` with `attribution_coverage: 0.0012`.

**WF74's capsule claims a "Monitor/use loop with OTEL multi-window evidence through one scorecard owner."** That is literally true and materially weak: WF74's route carries **zero OTEL entries in `secondary_artifacts` and zero in `validator_commands`**. The system's own stop-line agrees — *"do not infer model quality or finance correctness from runtime counts."* The 1.47 GB of metrics is written and read by nothing in the analysis path.

**Housekeeping:** 979 of 992 files in `tmp/otel-collector/` are zero-byte `.pb` exports dating to May.

---

## Recommendations

Ranked by consequence. Items 1-3 are the ones that change whether this workspace can be trusted to report its own health.

**P0 — restore vigilance and honest signalling**

1. **Fix `heartbeat-main`.** Five consecutive timeouts, 7.6 days dark, still firing. Diagnose the timeout (likely payload too heavy for the interval), then either lighten the turn or raise the timeout. This is the only actively-degrading item.
2. **Make `blockers` computed, not literal.** In `scripts/workflow_routing_index.py`, derive blockers from proof-artifact staleness against each route's declared `freshness_sla`, from the proof artifact's own `summary.blockers`, and from validator status — instead of hardcoded lists at 1426-1439 and the eight literal `[]` sites. Until this lands, no capsule's `blockers` field should be cited as evidence of health.
3. **Re-base `scripts/skill_core_proof_tier_audit.py:172`.** Replace the retired `Luna` / `Terra` / `Sol` required terms with current model contract anchors. The core proof gate has been reporting `blocked` on a correct skill.

**P1 — close the loops that are open**

4. **Fix the `implementation-builder` `runtime_tool_posture` mismatch** (`scripts/agent_bootstrap_linter.py`, `..\workspaces\implementation-builder\agent.capabilities.json`). Tool-policy drift on the code-writing lane.
5. **Work the 5 overdue improvement items** (3 high-priority), oldest at ~74 days. `anti_theater_status` will not clear until they do, and it is correctly refusing to go green.
6. **Add `wf88_decision_compiler.py`, `retrieval_quality_scorecard.py`, and `rsi_outcome_scorecard.py` to the daily refresh cron**, and re-enable the WF88 wiki synthesis job (327h quiet). Until then, fresh-looking packets keep re-exporting 35-day-old numbers.
7. **Decide the Wave 2 pilot** — it is a single owner decision and is the sole gate on WF88 Wave 2.

**P2 — stop paying for scaffolding**

8. **Fund or retire the zero-result scaffolds:** frontier eval (0/100 results) and advanced-capability pilots (0/6 executed), both 35 days at zero. Either authorize collection or tombstone them and drop their blockers.
9. **Decide what OTEL is for.** Today it costs 1.47 GB of unread metrics to observe its own collector. Either point `otel_ops_control.py` at `traces.jsonl`/`metrics.jsonl` and deepen field capture toward real attribution, or cut `sampleRate`/`metrics` and stop paying for data nothing reads. Delete the 979 zero-byte `.pb` files (owner approval required — destructive).

**P3 — accounting hygiene**

10. **Reconcile the Skills Governance Index:** add the 6 WF89 skills and `sec` to the tables, correct the line 20 count (50 table rows vs 57 live bodies), and relocate `skills/graphify-out` out of the skills namespace.
11. **Purge retired OpenAI models** from `Skills Governance Index.md:126,145,154` and `skills/disciplined-implementation/SKILL.md:26`; reconcile `MAIN_FALLBACKS` between `agent_fleet_policy.py:50` and Startup Truth Index:58 / `MEMORY.md:22`.
12. **Settle `TOOLS.md` / `IDENTITY.md` status** across `MEMORY.md:8`, `CLAUDE.md:4`, `AGENTS.md:66-74,125`, `GEMINI.md:4`; remove the stale embedded TOOLS.md block and the empty heading at `AGENTS.md:64`. Decide whether the unreferenced 87 KB `DREAMS.md` has an owner.
13. **Resolve the 5 unmatched routes** (`WF-CHIEF-GATE`, `WF-FINANCE-CHAINS`, `WF-BOARD-CANON-GUARDRAILS`, `WF-SQL-INDEXES`, `WF-WORKSPACE-GOVERNOR`) and the 76-vs-73 cron inventory drift.

---

## What is actually healthy

Worth stating plainly, because the list above is long:

- **Authority boundaries held everywhere.** No finance canon, capital, account, paper, or live execution drift found. Every stalled loop stalled *safely*, on the correct side of its gate.
- **Wiki source integrity is clean** — 38 references checked, 0 broken, and no page overstates its state.
- **Recommendation outcome grading converges** — 415 rows, 304 later-outcome graded. Proof that these loops can close when data actually flows.
- **The fleet policy's six specialist pairings are exact** against doctrine.
- **The anti-theater metric worked.** It refused to show green. The instrumentation caught the stall even though the routing layer didn't.

---

*Findings are review-only. No remediation applied, no approval implied. Remediation of items 1, 9 (deletion), and any cron schedule change requires explicit owner approval per `AGENTS.md` action boundaries.*

---

## Closure status addendum — 2026-09-14 (Main)

Appended by Main. The review above is unchanged and remains the record of the 2026-09-12 findings. This section records what has since been fixed, verified, and what remains owner-gated. Implementation was performed by `meta/muse-spark-1.3-contributor` under bounded write leases; Main independently re-verified every edit against disk before acceptance.

### Closed and verified

- **Completed-one-shot contract lifecycle defect** (`scripts/cron_contract_validator.py`, `scripts/test_cron_contract_validator.py`). A fired `deleteAfterRun` one-shot was being reported as `missing_live_job`/error, which fail-closed the entire cron control chain. The validator now recognizes the OpenClaw invariant that such a job is deleted only on success, and classifies past-due + `deleteAfterRun` + absent-from-live as `completed_one_shot`/`info`. Verified: tests `ok`; `status=warning contracts=44 drift=0 missing=0`; `completed_one_shot_count=2`, `missing_live_job_count=0`, `errors []`. The future-dated 2026-09-17 preflight contract is correctly untouched. `cron_control_digest_runner.py` now returns `status=ok validation=ok` end to end.
- **Root-attempt lane lineage defect** (`scripts/concurrent_lane_manager.py`, `scripts/test_concurrent_lane_manager.py`). `validate_root_lineage()` raised `missing predecessor_lane_id for successor slice attempt` whenever a lane had siblings, making every root attempt permanently uncloseable once a retry existed. The fix exempts a lane that is itself referenced as another lane's `predecessor_lane_id`; the negative guard for genuinely unparented siblings is preserved and tested. Verified: `concurrent lane token closeout tests passed`, rc=0.
- **9 stale WF88 lease lanes closed.** All nine reached the honest terminal `blocked` state with truthful metadata (`current_main_session_counters_not_job_scoped` / `provider_usage_unavailable`), matching existing register precedent. Open lane count is now **0**; lane validation warnings 5 -> 4. `blocked` is the designed honest outcome where token attribution cannot be proven — forcing `complete` would require fabricating telemetry.
- **3 of 6 failing enabled cron jobs** now exit 0 when run manually with their exact production flags: Cron Reduction Control Fail-Closed Dispatcher, Ops OTEL Local Digest, Runtime Future Session Packet Refresh. Note that `openclaw cron list --all --json` still shows 8 enabled jobs with an `error` `lastRunStatus`, because that field records the last *scheduled* run — all of which predate these fixes. Those entries clear on each job's next scheduled fire; scheduled-path proof is therefore still pending for them.
- **`future_session_enhancement_packet.py`** exits 0 with all prior CRITICALs cleared (`status=warning validation=warning wf74=ok pm=ok cron=ok escalation_consumer=warning`).

### Diagnosed, remediation owner-gated

- **Both finance Telegram jobs are timing out, not erroring.** `openclaw cron runs <jobId> --json` returns full run history (the 2026-09-13 note that this access was denied is superseded). Today both jobs recorded `status: send_failed` at **120994 ms** (midday) and **120493 ms** (morning) — exactly the `--timeout-seconds 120` transport budget. Every prior run of each job succeeded in 24-44 s. The gateway is healthy (`openclaw health`: ok, probe 146 ms, event loop p99 46.8 ms, Telegram `tokenStatus available`, `restartPending false`), so this is not a gateway stall. A timed `--dry-run` through the exact `windows-node-direct` argv takes **39.3 s** for CLI cold-boot alone. The OpenClaw package was updated **2026-09-13 15:53 local**, between the last success (Sep 11) and the first failure (Sep 14) — a strong correlation, not yet a proven mechanism.

  **Correction, same day, from owner testimony:** Randall confirmed he received this morning's alerts. Only two enabled jobs can deliver to Telegram (the morning and midday digests) and all 22 `Retired —` finance jobs are disabled with no run since 2026-08-28/29, so the delivery came from the job that reported `send_failed`. **The message is delivered and the CLI wrapper then fails to exit inside the 120 s budget.** `deliver()` catches `subprocess.TimeoutExpired` and returns `ok: False`, but the timeout kills the local wrapper, not the send the gateway already performed.

  Two consequences, and the second is the real risk:

  1. **The health signal is inverted** — these jobs report failure on success, which is the dangerous direction for an alerting system to be wrong in.
  2. **Duplicate-send protection is defeated.** `sent_keys[digest_key]` is written only when `result["ok"]`, so a timed-out-but-delivered run records nothing. Any re-run for the same date+mode+message will send Randall a second copy. The state file confirms this: no entry after 2026-09-11 despite confirmed delivery on 2026-09-14.

  Remediation requires owner approval because it mutates cron payloads: raise `--timeout-seconds` from 120 to 240 and job `timeoutSeconds` from 240 to 360, or reduce the ~39 s CLI cold-boot. A more correct fix also distinguishes "transport timeout" from "delivery failed" so dedupe state is not silently lost — that is a code change to `finance_alert_os_digest.py`, separately scoped. No manual `--send` was issued.

- **SQL Coverage - Daily Control Plane Guard** failed on its scheduled run but now passes (`status ok`, rc 0, 10/10 required commands ok, 15/15 proof artifacts present). `pm_control_packet` is one of its required commands, so the failure is consistent with the fail-closed cron chain still being blocked at that time — consistent, not proven.

### Routed, not fixed

- **Graphify Scripts Incremental Refresh** — `outcome: blocked`, `publication_not_supported`, `reason: fresh_node_foreign_source`, returncode 2, 125 changed files. Origin is `scripts/lib/graphify_incremental_owner.py` rejecting a node whose `source_file` is outside the declared source root. Graph output is derivation-only per doctrine, so this was routed to its owner rather than deep-dived here.

### Owner-gated — deliberately not actioned

These require Randall's explicit decision and were left untouched:

1. **OTEL collector is down.** Port 4318 is closed with no collector process; `otel_ops_control.py` raises `collector_not_listening` (critical, `action_type: runtime_review`, owner `openclaw-operator`). This blocks `Runtime - WF88 Wiki Synthesis Refresh` and also explains the 979 zero-byte `.pb` exports. Starting a service is a runtime mutation requiring approval.
2. **979-file `.pb` archive** (item 9 above). Approval exists, but the archive forbidden-path guard still blocks it and must not be overridden or evaded. Nothing has been moved or deleted.
3. **Re-arming the G7 cutover.** The contract-lifecycle error that blocked it is now resolved; per G7's own `next_action`, re-arming requires a fresh market-hours G6 receipt on a future trading day, then a re-read of live jobs/contracts and a rerun of all cutover gates. Phase 3 and G7-G9 remain open.
4. **A 23-file skill deletion** surfaced as a governance finding. Cause could not be determined from available evidence; reported, not repaired.

No finance canon, capital, account, paper, or live execution state was touched. No cron schedule was created, deleted, or modified. Main acceptance covers only the verified items listed under "Closed and verified".

## Closure addendum 2 — 2026-09-14 17:50 Phoenix (Main)

**Finance Telegram jobs — root cause corrected and fixed.** Earlier entries in this record treated these as delivery failures. That was wrong. Randall confirmed receipt of the alerts. Delivery succeeds; the CLI wrapper fails to exit inside the 120s budget, so `deliver()` returned `ok:False` and the dedupe key was never persisted — silent duplicate-send exposure, not missed alerts.

Two changes applied:

1. `scripts/finance_alert_os_digest.py` (Spark 1.3 implemented, Main verified) — transport timeout now yields `send_unconfirmed` (exit 0) and records the dedupe key with `"confirmed": false` plus warning `delivery_unconfirmed_transport_timeout`. Every other failure mode still yields `send_failed` exit 1. 29/29 tests pass.
2. Cron payloads via `openclaw cron edit` — morning `61590072` argv timeout 120→240 (outer stays 600); midday `0ef79012` argv 120→240 and outer 240→360. **Contracts updated in lockstep**, required because both pin `payload.argv` and `payload.timeoutSeconds` with `required: true`; a live-only change would have injected drift into the G8 window.

Rollback snapshot: `tmp/finance-send-timeout-20260914/`.

**G6/G7 reviewed — not affected.** All four G7 Path A cutover jobs retain `--dynamic-entitlement-scope`, enabled, last run ok; analyst `95da55c1` unchanged by design. The two finance jobs are disjoint from G7's set. Verification: `cron_contract_validator` drift=0, missing=0, completed_one_shot=2, errors=0; `cron_control_digest_runner --window control` status=ok validation=ok. First natural G8 sample remains 2026-09-15 06:00 Phoenix; no run forced.

**Future Session Packet Refresh P0 closed.** Root cause was a 32.8h-stale `tmp/current-active-lanes.json` still projecting the 9 WF88 lanes closed earlier that day. Regenerated (real count 3); closed one verified-complete lane and one unverifiable expired lane to honest `blocked`; extended the G7 lane lease to 2026-09-16T06:46Z with owner restored to `main`; recorded a fresh resume checkpoint. Packet now critical=0, exit 0.

**Remaining open.** Owner-gated: OTEL collector down on 4318 (blocks WF88 Wiki Synthesis and OTEL Local Digest), 979-file `.pb` archive. Newly identified: Graphify incremental refresh stage exits 2 on a resumable 127-file backlog — derivation-only, does not affect finance, canon, or G8.
