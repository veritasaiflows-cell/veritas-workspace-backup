# Long Work Orchestration Governance Review — WF74 WF88 Self-Assessment, OTEL Evidence, and Grok Challenger Audit

- **Date:** 2026-09-14 (Phoenix time)
- **Requested by:** Randall (owner)
- **Author:** Veritas Main (truth integrator and final QC owner)
- **Subject session under review:** `agent:main:dashboard:1ee848e4-70e8-43d6-a11a-206e1ffe4893` ("Implement WF74 and WF88 fixes"), plus continuation `agent:main:dashboard:2f40e84d-95dc-44eb-8e93-878ec162ea07` and related LOOP-REPAIR-20260912 lanes
- **Challenger:** `xai/grok-4.6` (isolated subagent, read-only), run `4b93db02-4d6e-4f2b-b0ea-78e7b72e97e6`

---

## 1. Executive Summary

**Verdict: Accept the self-assessment's factual confessions, but the root-cause model is incomplete and partly misattributed. The proposed correction plan mostly restates doctrine that already existed and was already violated; without mechanical enforcement it will fail again the same way.**

The central finding — agreed by Main's own review, the OTEL packet, and the independent challenger — is:

> **"Long work" was not the failure. The wrong unit of work was the failure.** `LOOP-REPAIR-20260912` was an owner-authorized seven-priority *program* that was run as if it were one implementation job. A program cannot fit inside a helper lease. Treating it as one long loop made fragmentation, context replay, and unfinishable handoffs inevitable — not merely likely."

Long-running *programs* are fine. Long-running *implementation sessions* are not. The durable fix is not "bigger budgets" or "longer sessions"; it is a **finishable-slice dispatch discipline with a mechanically enforced harness contract**, plus separating owner-gated work before dispatch rather than after.

What actually landed is real but narrower than the cost implies: a 7-file corrective package (72 collected tests + manual checks), 3 skills reconciled, frozen retrieval corpus intact. Still open at review time: OTEL consumer repair (unapplied draft; recovery staged but unproven), scheduled-run proof (needs authenticated Control UI run), 979-file archive closeout (approved but guard-blocked), and the OTEL collector itself is **down**.

**Bottom-line actions (ranked, with verification criteria, in §7–8).**

---

## 2. Scope and Evidence Basis

Evidence reviewed for this report:

| Source | Result |
|---|---|
| Session history `1ee848e4…` (self-assessment session, model gpt-6-astra) | Full final self-assessment text recovered, incl. usage table (~1.05M Spark + ~747K GLM ≈ 1.80M reported tokens, last ~24h, 18 helper records, explicitly *not* a billing total; 9 earlier leases without receipts) |
| Continuation session `2f40e84d…` | OTEL consumer recovery staged 4 candidate files, testing stopped on import-path error; 15 interrupted pending inputs recorded |
| `tmp/otel-ops-control.json` (generated 2026-09-15T00:01Z, `otel_ops_control.py --write --write-db --multi-window --validate`) | **Status: blocked.** Collector 127.0.0.1:4318 NOT listening (timeout). 0 events in 24h. Exit code 1. |
| `tmp/otel-ops-window-summary.json` | All 5 windows blocked on collector health; weekly active baseline ~70.9 events/hour → current daily rate ratio 0.0 (drift reason: daily event rate deviates from weekly baseline) |
| `tmp/otel-ops-events.jsonl` | 27,253 historical event rows (21,881 metrics / 5,282 traces / 90 logs); **last event timestamp 2026-09-13T17:10:28Z** — telemetry went dark during the failed long-work window |
| `tmp/otel-tool-workflow-metadata.json` (2026-09-14T14:30Z) | 15,963 metadata rows, 1,015 unique tools; status ok (metadata surface works from logs even with collector down) |
| Memory: `memory/2026-09-12.md`, `2026-09-13.md`, `2026-09-14.md` | Program authorization, seven priorities, continuation ownership, partial OTEL recovery evidence |
| Challenger subagent transcript (grok-4.6) | Full read-only challenge: root-cause test, false-green test of corrections, long-work decision criteria, action ranking, top-3 changes |
| Owner skills | `ic-swarm-orchestrator`, `otel-operations-analyst`, `disciplined-implementation` (+ its live handoff doctrine), `veritas-model-routing-helper-lanes` |

**OTEL classification per `otel-operations-analyst`: `repair`** (collector not listening; drift outside threshold because the daily rate is zero against a live weekly baseline) — **and `owner-gated`** for the restart action. Per that skill's boundary, this report does not start the collector; it names the exact gated next step (§8).

---

## 3. The Self-Assessment Under Review (summary)

Main's own accounting of the 36-hour WF74/WF88 loop-repair effort, from the subject session:

1. **Fragmented work** into handoffs that were not reliably finishable; each handoff paid reorientation cost.
2. **Budgets contradicted workload**: 50–100KB context packets but 10–12 tool-call caps (e.g., the 4-file OTEL consumer implementation); workers stopped before testing/packaging.
3. **Repeatedly paid to rediscover basic harness problems**: wrong Python import path (`market_data_utils`, more than once), mismatched function header/return annotation, `b"ok"` bytes in a JSON fixture, `str` where `pathlib.Path` required, passing `-B` to pytest.
4. **QA became initial debugging** rather than independent verification; some submitted commands skipped new tests; one script invocation exited 0 while executing no tests; QA did catch genuine fail-open behavior.
5. **Context/reasoning poorly controlled**: GLM helpers at high thinking; Main at max thinking (~198K context, 3 compactions); one planning review ~126K tokens with 53K output.
6. **Continuity unreliable**: PASS reports coexisted with timeout statuses; resume files stale after work finished; task records "running" with no active helpers.

Main's proposed correction: stable reusable Windows test harness established before dispatch; realistic budgets (30–50 initial calls, checkpoints at 10–15 instead of hard stops, reserved capacity for test + one repair cycle + evidence); smaller necessary context; proof reuse; current checkpoints; separated owner-gated work. Explicitly "not simply give Spark more calls."

Usage facts Main reported: ~1.05M Spark 1.3 + ~747K GLM 5.3 ≈ **1.80M reported tokens** across 18 helper records in the last ~24h — explicitly not a verified billing total, excluding Main, earlier records, and cache accounting. **Nine earlier repair leases lack usage receipts.**

---

## 4. Challenger Review (read-only, `xai/grok-4.6`)

**Challenger classification per `ic-swarm-orchestrator`:** expected/preferred path `claude-cli/claude-opus-4-8` was not used; fallback `xai/grok-4.6` was verified live in the transcript (provider xai, model grok-4.6). **This is standard challenger evidence, not the preferred-path verdict. Remaining trust downgrade applies.**

Challenger headline: *"This is a symptom inventory with a few true lines, then a correction plan that mostly restates doctrine Main already had and already violated."*

### 4.1 Root cause: incomplete and partly misattributed

- **The unit of work was wrong.** The owner authorized a seven-priority program (refresh/scheduled proof, debt closure, outcome linkage, aggregate QA, governance, pilot/frontier disposition, OTEL + cleanup approvals). That is not an implementation job. "You cannot fit a program into a lease."
- **Slice design failed, not "the budget."** Live doctrine (`disciplined-implementation`) already caps handoffs (~6 files / 120KB / 30k estimated tokens, one bounded repair + one QA rerun, then *rescope*). Dispatching a 4-file OTEL implementation with a 10–12 call cap was Main choosing an unfinishable lease — planning malpractice, not a platform limit. "Budgets contradicted workload" blames the cap instead of the slice.
- **Context replay is the tax, not the disease.** Unfinishable handoffs force reorientation; reorientation without machine-checked checkpoints (frozen snapshot id, applied hashes, *collected* test receipt, remaining-work contract) forces rediscovery. That loop is why 36 hours produced both the spend and the unfinished OTEL repair.
- **Harness rediscovery is the most damning and least owned.** The import-path/fixture/annotation/pytest mistakes are workspace invariants. A one-command preflight would have failed in 1–2 calls. Paying Spark ~1.05M reported tokens to relearn them is orchestrator failure, not a model-quality story.
- **Omitted root cause (larger than thinking-level):** the 2026-09-11 "Spark/GLM cannot touch files" diagnosis was later recorded as **wrong** (Randall disproved it; the real issue was claude-cli spawns inheriting an MCP-only tool schema — write-capable helpers needed a different transport). That wrong capability model produced Main-authored files, fake coder/QA roles, and fragmented recoveries across multiple days. The self-assessment barely names it. *(Main accepts this finding — its omission was self-protective.)*
- **QA-as-debug is a role violation,** not a token problem: doctrine requires independent QA on the *applied* diff after deterministic preflight; GLM was used as a debugger of unfinished Spark work, guaranteeing spend and PASS/FAIL noise.
- **Continuity failure is isomorphic to the object-level bug:** the program was repairing stale health/producer-consumer lies while being run on PASS-vs-timeout, stale resume files, and "running" with no helpers. Main was operating an untrusted control plane to repair an untrusted control plane.
- **Token theater:** leading with Spark+GLM spend makes helpers the villain; the unmeasured term is Main replay + compaction + wrong-diagnosis recovery (~198K context, 3 compactions, a 126K-token planning review with 53K output at max thinking).
- **"What landed" is success-washing:** "72 collected tests" without suite name/collection command, while OTEL is unfinished, scheduled-run proof is open, the archive is guard-blocked, and the collector is down.

### 4.2 False-green risk in the proposed corrections

Which corrections are load-bearing vs. theater:

| Proposed correction | Challenger test result |
|---|---|
| Stable reusable harness | **Load-bearing only if** versioned, one-command, fail-closed preflight. Otherwise theater. |
| 30–50 calls with checkpoints at 10–15 | **Papers over the slice problem.** Narrative checkpoints don't reject unfinishable leases; the gate must be deterministic. |
| Reserved test/repair/evidence capacity | Soft reservations won't survive 36-hour multi-helper jobs without enforcement. |
| Smaller necessary context | Wishful without a packet cap that is checked at dispatch. |
| Proof reuse | Needs **hash-equal enforcement** (applied diff hash == lease postimage hash), not restatement. |
| Current checkpoints | Checkpoints that don't kill stale resume files will go stale again — same recursion. |
| Separated owner-gated work | Must be the **first cut** at planning time, not a trailing correction; mixed context leaks to helpers. |

### 4.3 Is "long work is not the best way" right?

Challenger: **yes, with precision.** Long-running programs are fine; long-running implementation sessions are not. The unit should be a **finishable change**: one applied diff, one collected test receipt, one independent QA, one accept/reject.

Decision criteria for Main-owned session vs. helper handoffs:

- **Main-owned single session better:** 1–3 files, known producer-consumer path, verification of already-authored diffs, cross-cutting one-line fixes.
- **Helper handoffs better:** >4 files, multiple subsystems, Main already near compaction, owner-gated items present, expensive thinking models in play.
- **Either is wrong if:** the slice is not finishable inside its lease, or the harness status isn't green before dispatch.

### 4.4 Action ranking (challenger)

1. **Harness engineering** — highest ROI; eliminates the rediscovery tax.
2. **Finishable-slice dispatch compiler** — a deterministic gate that rejects unfinishable leases before dispatch (files×context×budget×validation-surface check).
3. **Usage receipts bound to leases** — no lease closes without a receipt; kills the "9 leases, no receipts" accounting hole.
4. RSI/improvement-ledger routing of the recurring friction (the harness rediscovery class, the QA-as-debug class, the stale-resume class).
5. Skills/doctrine updates — only after 1–3 exist mechanically; restating doctrine that was already violated adds nothing.

### 4.5 Challenger verdict

**Accept-with-corrections**: the self-assessment's effect inventory is honest, but the root-cause model is incomplete (wrong unit of work, slice-design failure, omitted tool-policy misdiagnosis), and the correction plan is only real if mechanically enforced.

*(Note: the challenger's final top-3 list was truncated in transit; Main reconstructed it from the challenger's own reasoning summary, and marks those three items as challenger-derived but Main-integrated in §8. No challenger claim is promoted to accepted canon beyond what its recovered text supports.)*

---

## 5. Main's Integration and Acceptance

**Accepted challenger findings:** all root-cause corrections in §4.1 (wrong unit of work; slice design failure; harness rediscovery as orchestrator failure; omitted 09-11 tool-policy misdiagnosis; QA-as-debug role violation; control-plane recursion; token theater; success-washing). These are consistent with the primary evidence and Main's own confessions, and they sharpen them.

**Partially accepted:** "30–50 calls" — Main keeps the direction (budgets must match slice size) but demotes it below the deterministic gate; the challenger is right that a soft number is not a control.

**No challenger claim overrides:** source truth (memory, transcripts, packets), finance canon, authority boundaries, or owner approval. Challenger output is standard-path evidence (fallback model), read-only, unverified beyond its transcript.

**Main's added finding from live OTEL evidence (challenger had it only from memory):** the collector was down at review time with the last event at 2026-09-13T17:10Z — meaning the workspace had **zero live telemetry for the entire final stretch of the failed work and for this review's window**. Any efficiency or attribution claim about the last ~30 hours of the program is therefore built on displayed usage records and receipts, not collector-backed evidence. This is a material claim limit on every number in §3.

---

## 6. Answering the Owner's Question: "Maybe long work is not the best way to approach implementation jobs?"

**Correct instinct, wrong target.** The failure was not the clock; it was the shape of the work:

- Do run **long programs** — weeks if needed — as sequences of finishable, independently proven slices.
- Do **not** run **long implementation sessions** — single giant leases or chained unfinishable handoffs — for multi-file, multi-subsystem work.
- The operating rule that should be canonized: **a program is a queue of finishable changes; a finishable change is one applied diff + one collected test receipt + one QA + one accept/reject; nothing is dispatched without a green one-command preflight; owner-gated items are extracted before dispatch, never interleaved.**

Under that rule, the LOOP-REPAIR program would have been ~7–12 slices, each closable in one helper lease, with Main integrating at each boundary — instead of one 36-hour replay loop.

---

## 7. Ranked Workspace Actions

| Rank | Action | Why first | Verification (pass/fail) |
|---|---|---|---|
| 1 | **Harness engineering**: one versioned, one-command, fail-closed Windows preflight (`scripts/` — import-path check, pytest invocation contract, fixture schema check, `Path` vs `str`, UTF-8) required green before *any* helper dispatch | Kills the rediscovery tax that burned ~1M+ tokens relearning invariants | Pass: preflight, run cold in an isolated subagent, fails in ≤2 calls on each known invariant class; Pass: no helper dispatched with harness status != green |
| 2 | **Finishable-slice dispatch gate**: deterministic compiler/check that rejects leases where slice (files×context×validation surface) cannot close inside budget+time; forces *rescope* instead of mid-lease stops | The 4-file/10–12-call OTEL slice and its predecessors were predictable failures | Pass: replay of the LOOP-REPAIR dispatch list through the gate flags every lease that actually failed, before dispatch; Pass: a known-good small lease passes |
| 3 | **Lease-bound usage receipts**: no lease closes without a usage receipt; backfill the 9 missing ones from gateway usage records where recoverable | Restores truthful accounting; kills token theater | Pass: 100% of leases in the register have receipt-or-explicitly-unrecoverable markers; Pass: next program's reported total reconciles to receipts |
| 4 | **Stale-checkpoint killer**: applied-hash equality + resume-file invalidation on acceptance | Kills the PASS-vs-timeout / stale-resume recursion | Pass: after next accepted slice, no resume file claims pending work that finished |
| 5 | **Owner-gate extraction at planning time**: collector restart, archive apply, cron/schedule changes pulled out of implementation lanes into their own approval-tracked items | Owner-gated work was blocking closable slices | Pass: next implementation packet contains zero owner-gated items |
| 6 | **RSI / improvement-ledger routing**: route the three recurring friction classes (harness rediscovery, QA-as-debug, stale-resume) into `veritas-self-improvement`/WF74 with this report as source evidence | Durable capture instead of chat-only lessons | Pass: each class appears in the actionable queue with an owner and next action |
| 7 | **Skill/doctrine update** (`disciplined-implementation`, `veritas-model-routing-helper-lanes`): codify the finishable-change unit, harness-first rule, QA-on-applied-diff-only rule | Only after 1–5 exist mechanically; otherwise restated doctrine | Pass: Skill Workshop proposal staged with this report as lineage; applied only through the exact gate |

**Explicitly not ranked (owner-gated, not taken):** collector restart/config change; OTEL consumer repair apply; 979-file archive apply; cron schedule edits; any capture-depth/config mutation.

---

## 8. OTEL Status and Exact Gated Next Steps

- **Current OTEL status: `repair` + `owner-gated`.** Collector 127.0.0.1:4318 not listening (timeout), 0 events/24h, last event 2026-09-13T17:10:28Z, weekly active baseline ~70.9 events/hour, drift flagged (daily rate 0.0).
- The metadata surface (`tmp/otel-tool-workflow-metadata.json`) still works from existing logs (15,963 rows, 1,015 tools) — so failure taxonomy routing (action 6) can proceed without the collector.
- **Exact gated next step for the collector:** owner approval to restart the local OTEL collector (runtime/service mutation is outside this review's authority). If approved, verify with `python scripts\otel_ops_control.py --write --write-db --multi-window --validate` and require the 1h window to show collector listening and events flowing before any scheduled-run proof is claimed.
- **Claim limit until then:** all usage/efficiency numbers in this report are displayed-record estimates, not collector-backed evidence.

---

## 9. Boundaries Honored

- Challenger was read-only; no file leases were granted; its output is untrusted-until-verified evidence, integrated by Main.
- No collector/runtime/config/cron/canon mutations were performed. No archive, delete, capital, or account action. No skill files were edited — skill changes are routed to Skill Workshop as proposals (action 7).
- OTEL ran only through the existing review-only control script.
- The interrupted pending inputs in the subject sessions were left untouched; they are owner-continuation material, not this report's scope.

## 10. Remaining Limits

1. The challenger ran on the fallback model (`xai/grok-4.6`), not the preferred `claude-cli/claude-opus-4-8` path; its verdict carries the standard-evidence downgrade.
2. The challenger's final top-3 list was truncated in delivery; Main reconstructed it from its reasoning summary and flagged the reconstruction explicitly (§4.5).
3. Live telemetry was dark for the review window; collector-backed corroboration of usage is impossible until the owner-gated restart.
4. The LOOP-REPAIR program itself is not closed by this report: OTEL consumer repair, scheduled-run proof, and archive closeout remain open with their existing owners.

## 11. Proof Appendix

- `python scripts\otel_ops_control.py --write --write-db --multi-window --validate` → status=blocked, exit 1, packets `tmp/otel-ops-control.json` / `tmp/otel-ops-window-summary.json` / `tmp/otel/control-loop.json` (2026-09-15T00:01–00:02Z)
- `tmp/otel-ops-events.jsonl`: 27,253 rows; last event 2026-09-13T17:10:28Z
- `tmp/otel-tool-workflow-metadata.json`: 15,963 rows, 1,015 tools, generated 2026-09-14T14:30Z
- Subject session history (self-assessment): `agent:main:dashboard:1ee848e4-70e8-43d6-a11a-206e1ffe4893`, final usage/failure accounting message
- Challenger transcript: `agent:main:subagent:a0986047-d486-4f03-80b3-74685d559944`, run `4b93db02-4d6e-4f2b-b0ea-78e7b72e97e6`, model xai/grok-4.6, read-only
- Memory: `memory/2026-09-12.md` (program authorization, seven priorities), `memory/2026-09-13.md` (continuation ownership, partial OTEL recovery), `memory/2026-09-14.md`

*This report is decision-grade evidence for the ranked actions in §7. It grants no approval: implementing actions 1–4 requires the normal implementation router path; action 7 requires Skill Workshop; every owner-gated item requires Randall's explicit approval.*