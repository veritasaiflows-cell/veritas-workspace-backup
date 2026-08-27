	# Recursive Improvement & OTEL Learning Loop Review — 2026-06-19

**Author:** Veritas (main session) · **Date:** 2026-06-19 (Fri, America/Phoenix)
**Scope:** Whether Veritas is actually *using* its data loops (OTEL telemetry, WF74 recursive self-improvement, improvement ledger, scorecards, coding/decision/finance outcome ledgers) to get measurably better at coding, decision-making, planning, and orchestration.
**Posture:** Review-only. No cron, config, collector, or runtime changes made. All numbers verified live against running process + current artifacts (see Verification Log). Builds on the 2026-06-14 and 2026-06-15 audits.

---

## Bottom line

The machinery is **real, live, privacy-clean, and it has measurably improved itself in the last 5 days** — the 06-15 audit's recommendations were largely acted on (5/8 implemented; collector log cut from 1.39 GB → 7.7 MB; cost capture 0% → 10.5%; WF55 outcome grades 0 → 30; anti-theater closure KPIs added this morning). This is not theater: closures carry proof artifacts and validation commands.

But the system is still **far stronger at producing and routing insight than at grading outcomes.** The single structural gap that blocks "Veritas is measurably getting better" is the **ex-post grading leg**: across coding and decision-making, the loop captures *what was attempted* in rich detail but never fills in *whether it actually worked*. Until that closes, Veritas can propose, apply, and track improvements — but cannot prove it is getting better, only busier.

Plain-English verdict by domain:

| Domain | Loop maturity | Honest read |
|---|---|---|
| **Orchestration** | Closed loop, working | Strongest. Cron/workflow/lane friction now feeds the loop and converts into tracked follow-ups. |
| **Decision-making (finance)** | Measuring started, not compounding | WF55 just went 0 → 30 graded outcomes, but durable append is still blocked, so grades don't yet persist/compound. |
| **Coding** | Collects, doesn't yet learn | 421 outcome rows with full attribution/churn/proof — but `rework_required` / `regression_observed` are **null on every recent row**. First-pass-clean rate is uncomputable. |
| **Planning** | Implicit only | No dedicated signal. Plan quality is never separately captured or graded. |

---

## 1. What improved since the 06-14/15 audits (the loop improving itself)

Verified via `otel_recommendation_closeout.py` (5/8 implemented, 3 owner-gated) plus live artifacts:

- **R1 — log rotation: DONE.** `collector.err.log` is 7.7 MB (was 1.39 GB). `OTEL Collector Log Retention` cron runs 03:30 daily.
- **R2 — self-assessment fix: DONE.** `otel_ops_control.py:29` now audits the actually-running `openclaw-local-otel-runtime-metadata.yaml`, not the stale basic config. The contradictory "no token/cost captured" claim is gone.
- **R3 — carryover staleness guard: code DONE, schedule running.** `future_session_enhancement_packet.py` now has `freshness_state()` with stale flags + max-age + fallback to durable ledger history. `Future Session Packet Refresh` crons run 06:30 + 18:30. (Closeout still flags R3 because the *cron* half is owner-gated; functionally it is operating.)
- **R6 — broaden loop inputs: DONE.** `cron_signal`, `workflow_advancement`, and `wf87_shadow_outcome` now feed `otel_learning_loop` directly (visible in its `source_status` + recommendations), not just `model_quality_scorecard`.
- **Anti-theater KPIs: DONE (this morning, 2026-06-19).** `improvement_ledger.py` now emits `closure_rate`, `recurring_open_count`, `high_priority_overdue_open_count`, and `anti_theater_status`.
- **Cost/token capture: IMPROVED.** `otel_runtime_metadata_probe.py` was fixed to treat count/token/byte fields as metadata (raw content still blocked). Cost coverage 0% → 10.5%.
- **WF55 decision grading: STARTED.** 30 measurement grades now exist (was 0).

Remaining owner-gated: **R4** (token/cost config depth), **R5** (archive 2 stale scorecards), **R8** (dead collector hygiene — 2 candidates).

---

## 2. The core structural gap — ex-post outcome grading

Every loop has a strong **ex-ante** leg (capture what we're about to do, with attribution and proof) and a weak/missing **ex-post** leg (grade whether it held up). This is the same shape in all three "intelligence" domains:

### 2a. Coding (highest-leverage gap)
`data/state-history/coding-outcome-ledger.jsonl` — 421 rows, schema `veritas.coding_outcome_ledger.v1`. Rich on **process**: full model/session/run attribution, `edit_churn`, `acceptance_commands`, `proof_attached`, `validator_proxy_passed`, `duration_minutes`, lane contract. But the **outcome** fields are inert:
- `rework_required: null` and `regression_observed: null` on **all 40** most-recent rows.
- `later_review_status: "pending_later_regression_review"` — and nothing ever performs that later review.
- `validator_proxy_passed: true` reflects the **workspace-wide** `changed-file-validator-router` status (478 changed paths, budget `major`), **not** a test run scoped to that specific change.

Consequence: Veritas cannot compute first-pass-clean rate, rework rate, or regression rate — by model, by task type, or over time. The data needed to *get better at coding* is being logged but never closed.

### 2b. Decision-making (finance)
WF55 now has 30 measurement grades, but `model_quality_scorecard` reports `decision_quality = partial_ex_ante_and_wf55_measurement_active_durable_blocked`. Durable append is still off, so grades don't persist into the compounding history that would let decision quality trend across sessions.

### 2c. Planning
No dedicated capture at all. Plan→outcome fidelity (did the acceptance criteria hold, did scope/estimate match) is never recorded, so planning is the one domain Randall named that has no measurement surface.

### 2d. Closure-rate integrity
`closure_rate = 0.2632` (14 open / 5 closed) blends two very different closures:
- **Genuine applied fix** — e.g. "Repair blocked WF74 collection step" closed via `resolution_reason: latest_wf74_runner_steps_blocked_zero` with proof artifact + validation command. Real.
- **Signal vanished** — e.g. "Route blocked cron signals…" closed via `resolution_reason: latest_source_no_longer_emits_candidate`. The improvement may or may not have been made; the candidate just stopped appearing.

Both count equally toward the headline closure rate. The ledger is transparent (each row carries its `resolution_reason`), but the KPI itself can flatter the loop.

---

## 3. Other current findings

| # | Severity | Finding |
|---|---|---|
| F1 | Med-High | **Coding outcome grading absent** (§2a). `rework_required`/`regression_observed` null on all recent rows; first-pass-clean rate uncomputable. The richest ledger (421 rows) yields no coding-skill learning. |
| F2 | Medium | **Decision grades don't compound** (§2b). WF55 measurement active but durable append blocked; `decision_quality` cannot leave partial/blocked. |
| F3 | Medium | **Closure-rate conflation** (§2d). Applied-fix and signal-absence closures are indistinguishable in the headline KPI. |
| F4 | Medium | **Carryover is load-optional.** R3 code + cron landed, but new sessions still only benefit if the model *reads* the packet/ledger per the Startup Truth Index. No hard preload/contract enforces it. Weakest link in cross-session compounding. |
| F5 | Med | **Economics invisible on dominant paths.** 381 of 439 model rows — `openai/gpt-5.5` (122) + `unknown` (259) — have **zero** token/cost coverage. Only gpt-5.4 / 5.4-mini / spark (46 rows) are covered. Model-routing economics for the *main* model are unlearnable. (R4, owner-gated.) |
| F6 | Low-Med | **No planning-quality signal** (§2c). |
| F7 | Low-Med | **OTEL drift = review.** daily/weekly event ratio 3.90 — an artifact of today's collector restart (low weekly baseline), not a real anomaly. Self-flagged; no action beyond noting. |
| F8 | Low | **Hygiene debt persists** (R5/R8): 2 stale orphaned scorecards, 2 dead-collector candidates. Owner-gated archive. |
| F9 | Low | **Loop work uncommitted.** This morning's loop-critical edits (improvement_ledger, otel_runtime_metadata_probe, future_session_enhancement_packet, model_quality_scorecard, wf55 ledger) are in the working tree only. Consistent with 72h batch cadence, but the improvement-to-the-improvement-system is currently unpersisted to git. |

---

## 4. Recommendations (ranked)

| # | Rec | Why it matters | Risk / Authority |
|---|---|---|---|
| **REC-1** | **Close the coding ex-post leg.** Add a later-regression-review pass that fills `rework_required` / `regression_observed` on coding-outcome rows — triggered when a later lane re-touches the same files, a validator later fails, or a revert occurs — then compute first-pass-clean / rework / regression rates by model and task type. | The single biggest "get better at coding" unlock. Turns 421 inert rows into a real skill-trend signal. | Low. Workspace code (disciplined-implementation lane). |
| **REC-2** | **Unblock WF55 durable grading.** Flip the durable-append path (with the owner-gated design already scoped) so decision outcomes persist and compound; let `decision_quality` leave `durable_blocked`. | Decision-making can only improve if grades survive past one session. | Mixed — code + owner decision on durable-append policy. |
| **REC-3** | **Split closure_rate into `applied_fix_rate` vs `signal_absence_rate`.** Report both; keep `resolution_reason` as the discriminator. | Protects the anti-theater KPI from flattering itself. | Low. Workspace code. |
| **REC-4** | **Make carryover non-optional.** Strengthen the startup contract so the improvement ledger + future-session packet are *always* injected/read (doctrine hard-rule now; owner-gated preload hook if a true hook is wanted). | A learning loop that future sessions may skip isn't a loop. | Low (doctrine) → Mixed (hook = owner-gated). |
| **REC-5** | **Prepare the R4 token/cost depth card** for the dominant paths (gpt-5.5 + unknown attribution). Local-only, redacted, rollback, privacy scan — present as an approval card. | Makes main-model routing economics learnable; closes F5. | Owner decision (collector/runtime config). |
| **REC-6** | **Add a minimal planning-quality signal.** Capture plan→outcome fidelity (acceptance criteria held? scope/estimate match?) on meaningful lanes, reusing the coding-outcome schema pattern. | Brings the one unmeasured domain Randall named into the loop. | Low. Workspace code. |
| **REC-7** | **Hygiene (R5/R8):** archive the 2 stale scorecards + 2 dead-collector candidates via the gated reference-review path. | Removes confusion/maintenance debt. | Low; deletes are owner-gated reference-review. |
| **REC-8** | **Checkpoint the loop work** (F9) so the self-improvement gains are persisted to git. | Don't lose the improvement-system improvements. | Low; commit on request. |

**Suggested sequence:** REC-1 + REC-3 first (biggest coding-learning payoff + KPI integrity, both low-risk workspace code). Then REC-2 + REC-4 (compounding + carryover). REC-6 alongside. REC-5 is a standalone owner approval card. REC-7/REC-8 are hygiene.

---

## 5. Authority boundary

This review changed nothing. It ran review-only artifacts (`otel_recommendation_closeout.py`) and wrote this audit. No collector/runtime/cron/config mutation; no canon/portfolio/finance mutation; no capital/paper/live/account action; no owner-approval inference. All recommendations preserve existing boundaries: REC-1/3/6 are normal workspace-code lanes; REC-2/4/5/7 cross owner-gated config/policy/archive lines and require explicit Randall approval before implementation. OTEL stays loopback-only, metadata-only, no raw-content/secret capture.

## 6. Verification log (live, 2026-06-19 ~09:40 MST)

- `otelcol.exe` PID 32548, started 2026-06-19 09:04, loopback; `collector.err.log` 7.7 MB / last write 09:39 — **Get-Process / Get-Item**
- `otel-learning-loop.json` (gen 05:27Z): collector ok, 1703 daily events, 0 warn/err, drift `review` (ratio 3.90), token_cov 0.1048, cost_cov 0.1048, 259 unknown + 122 gpt-5.5 rows at 0 coverage, privacy_scan 0 findings — **read live**
- `improvement-ledger-current.json` (gen 05:27Z): 365 rows, open 14, closed 5, closure_rate 0.2632, overdue 0, hi-pri overdue 0, escalation due_soon, anti_theater `proposal_loop_with_closure_proof`; closed rows carry `resolution_reason` (mix of `…steps_blocked_zero` and `…source_no_longer_emits_candidate`) — **read live**
- `coding-outcome-ledger.jsonl`: 421 rows; recent rows full attribution/churn/proof but `rework_required`/`regression_observed` null on all 40 sampled; `validator_proxy` = global changed-file-router (478 paths, budget major) — **read live**
- WF55: 30 measurement grades; `model_quality_scorecard` decision_quality `partial_ex_ante_and_wf55_measurement_active_durable_blocked` — **memory 2026-06-19 + read**
- `otel_recommendation_closeout.py --write --validate`: implemented 5/8, owner_required 3, unresolved R3/R4/R5/R8, 2 stale scorecards, 2 dead-collector candidates — **ran live**
- `otel_ops_control.py:29` default config = `openclaw-local-otel-runtime-metadata.yaml` (F2 fixed); `future_session_enhancement_packet.py` freshness_state/fallback present (R3 code) — **grep**
- This morning's loop edits uncommitted (working tree); `git log` since 06-15 shows only checkpoint commits for these scripts — **git**
