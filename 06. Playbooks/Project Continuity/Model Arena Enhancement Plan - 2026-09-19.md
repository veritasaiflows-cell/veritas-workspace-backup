# Model Arena Enhancement Plan — 2026-09-19

## Decision and status

Owner request: strengthen the internal arena for newer models, emphasizing capability, actual tool use, reasoning and generalization. Pricing, accounting and token-cost optimization are out of scope. The original planning deliverable was followed by explicit authorization to harden the harness. The bounded implementation is applied and Main-accepted after independent applied-source and frozen-seed delta reviews. No new service, recurring schedule, provider installation, comparison batch or automatic promotion is authorized by this plan alone.

Current acceptance: `tmp/arena-harness-p0-20260919/closeout.json`. Main verified 66 applied regression tests, targeted positive/negative Docker controls, real Linux symlink rejection, and missing/corrupt-live-metadata seed-integrity controls. Independent core QA passed; Main escalated and corrected a filework finding that had been labeled nonblocking, then obtained a fresh passing delta review. This is a bounded utility-hardening slice, not completion of every Priority 0 run-envelope/tool-trace item below. Before a new comparison, finish its exact trial envelope, matched candidate isolation and family-specific evaluator calibration. The unrelated missing historical WF88 proof file remains a separate workspace-validation issue.

Later owner-approved lane preparation converted persistent ID `oxalpha-functional-lab` into the **Model Arena Functional Lab** at a fresh synthetic workspace without changing its model, zero-fallback policy, tools, agent directory or Docker sandbox. Default GLM Flash proved all five allowed tools and verified artifacts; an explicit Grok override proved exact-model/no-fallback operation plus network/root-write containment. Independent QA passed with disclosed limits: the default final JSON was fenced, one earlier tool call failed before recovery, the lane is single-agent only, and `exec` remains capped at 30 seconds per call. This is transport/containment readiness, not a completed enhanced suite or model promotion. Proof: `tmp/arena-functional-lab-conversion-20260919/`.

Main owns integration and acceptance. Existing owner procedure: `model-capability-bench-authoring`. Existing components: `scripts/model_arena.py`, `scripts/arena_filework.py`, `data/evals/model-arena/README.md`, and the frozen `arena24-20260919` protocol/results. Extend these before inventing another harness. Do not modify or combine historical scores into a single leaderboard.

## What existing evidence establishes

- Earlier single-turn cases were saturated by both tested Flash models.
- Both completed the tested real-file bugfix, cross-file refactor and non-regressing feature addition. Those fixtures do not prove unrestricted repository competence.
- Repeated state tracking discriminated: DeepSeek was more consistent than GLM Flash in the sampled trajectories.
- Claim verdict accuracy, citation completeness and unknown-field completeness are different outcomes; neither model had uniformly complete evidence packets.
- Strict formatting must include intermediate visible narration as a separate field, not silently grade only the final object.
- Six multiline CLI prompts were truncated in the last comparison. They remain invalid transport attempts, not model capability failures. File-based delivery and exact received-prompt verification repaired the route.
- Lab registration themes are model-neutral. Functional-lab documentation corrections are applied and Main-verified. Two locked-lab documentation files remain blocked by its write restrictions; see `tmp/arena-harness-p0-20260919/followup-reconciliation.json`. A later owner-approved functional-lab conversion changed only its name, identity text and workspace path; model, tools and sandbox permissions remain unchanged.
- Independent source reasoning now confirms all four original oracle keys; the earlier timeout remains in history. Pin T2 array ordering, T3 source-ID rules and T4 read/absence evidence in the next fixture version, without changing old keys or scores.

## Priority 0 — trustworthy execution and grading

Owner: Engineering Builder; independent Engineering QA; Main acceptance.

1. Use documented file-based prompt delivery. Verify exact received prompt/hash, actual user/tool roles, effective model/provider and fallback events for every trial. Test multiline code, quotes, non-ASCII, long lines and multi-turn session continuity before a batch.
2. Standardize an append-only attempt/result schema: suite/fixture/oracle version and hashes; case family and ID; repetition; trajectory/turn IDs; explicit permitted tools; requested/effective model and harness configuration; start/terminal status; timeout/cancellation; actual tool calls and artifact hashes; separate correctness, citation, format, boundaries and task-completion dimensions. No hidden reasoning, credentials, private account/customer data or secret-bearing payloads in evidence.
3. Inspect and repair the recorded `arena_filework.py` unregistered `args.usage` grading defect before using that runner. Keep capability grading independent of missing accounting inputs; do not build an accounting pipeline.
4. Preserve operational failures separately from capability outcomes: transport/config/harness errors, refusals, provider failures, model task failures and valid successes. Retain originals and label replacements explicitly. Every reported denominator identifies cases, attempts, repetitions, trajectories, turns or assertions; never treat these as interchangeable.
5. Calibrate every evaluator with a passing reference, a known-wrong seed, malformed output, a plausible but incorrect answer and a tool-trace violation. A broken evaluator blocks that case. Freeze keys before candidate runs; independent oracle review must actually return a verdict, not merely be requested.

Exit gate: exact transport controls pass; deterministic graders accept positive controls and reject seeded negatives; existing regression cases replay correctly; no permissions or accounting requirement added. Bounded tests only, no broad new model batch yet.

## Priority 1 — representative capability coverage

Build one well-validated case in each of six families first. Add structurally different fixtures later rather than many repetitions of a saturated puzzle.

| Family | Work to test | Required proof |
|---|---|---|
| Code and change discipline | Bugfix, hidden call site, feature without regression, minimal scoped edits | Pristine tests executed independently, protected files/diff budget, hidden references checked |
| State and changing rules | Queue/event replay, deduplication, cancellation, expiry, genuine rule change versus false correction | Deterministic state oracle; score every turn and whole trajectory |
| Evidence and uncertainty | Corrections, competing sources, unpublished figures, missing dates and citation completeness | Claim-to-source/line mapping, separate truth/citation/unknown scores |
| Actual tools and recovery | Missing file, bounded reader output, permission denial, recoverable tool failure | Observed calls/results and final artifacts, not self-reported actions |
| Continuity and instruction control | Compress a task handoff, resume from verified checkpoint, preserve blockers and acceptance status | Required facts retained; no false completion or authority escalation |
| Generalization and planning | Learn a new rule from examples, transfer it to a held-out domain, plan and execute a bounded dependency chain | Unseen checks, artifact state, constraint preservation, stop at a real blocker |

Treat the last family as **AGI-oriented capability proxies**, not an AGI certificate, consciousness claim or universal intelligence score. Distinguish reasoning-only performance, tool-assisted performance and autonomous completion under a fixed tool budget.

First comparison proposal after Priority 0: six distinct cases × two fresh repetitions × two nominated models = 24 task trajectories. Freeze turn, tool-call, elapsed-time and total-attempt limits before launch. Report preflight calls separately. Invalid attempts and any permitted replacements consume their declared budget; no retry-until-pass and no automatic batch expansion. Multi-turn trajectories are not multiple independent cases.

**Status 2026-09-19 — delivered as a frozen envelope.** `data/evals/model-arena/arena-six-20260919/envelope.json` covers all six families across ten turns, with keys derived rather than hand-written, 50/50 calibration controls passed, candidate isolation specified, zero retries, and a fixed 600-second per-turn operational timeout. Enrollment is open and does not imply promotion. Independent oracle review returned and corrected a real T1 key error before the freeze; a second cross-model oracle was dispatched but returned blocked without filesystem access, so one independent derivation stands. Expansion beyond this envelope is planned separately in `Model Arena Harder Benchmark Expansion Plan - 2026-09-19.md`. Its revision 3 scope is agentic AI only: reasoning, planning, tool use/recovery, terminal and artifact work, continuity, orchestration, verification and authority control; multimodal, PDF-rendering, image, video, audio and GUI-perception benchmarks are excluded.

**Incumbent baseline executed 2026-09-19.** GLM 5.3 Flash and DeepSeek 4.1 Flash each produced 8 strict passes across 12 planned trajectories. GLM had 11 operationally eligible trajectories, 8/11 frozen factual passes, clean full-interaction format/tool compliance on all 11, and one T6 operational timeout retained without retry. DeepSeek completed all 12, produced 10/12 frozen factual passes and exact T4 read paths, but had only 9/12 full-format passes because two T4 trajectories narrated before tools and one T2 response appended prose. Repeated strict families were T2/T3/T4 for GLM and T3/T5/T6 for DeepSeek. This is a differentiated baseline, not a winner or routing decision. Evidence and limits: `data/evals/model-arena/arena-six-20260919/results/incumbent-baseline-20260919/report.md`.

## Priority 2 — evaluation discipline and reusable regression

- Freeze matched bootstrap, tools, source visibility, reasoning effort and runtime settings. Publish differences instead of pooling non-comparable runs. Counterbalance case order and use clean sessions/workspaces between repetitions.
- Keep public calibration cases separate from held-out fixtures and answer keys. Candidates must not see reference implementations, evaluator internals or peer outputs. Reuse a holdout only with an explicit contamination label; promote escaped real defects into versioned regression fixtures after sanitization.
- The QA workspace now contains key-review packets. Do not reuse it as a held-out candidate environment without fresh source-visibility/isolation proof. Add a tool-policy interpretation control: no prior executable approval is not evidence that an available tool actually denied a request; distinguish unattempted, denied and executed actions.
- Use deterministic grading where possible. For genuinely judgment-based work, use an explicit rubric and a different reviewer, blinded model labels when feasible, calibration examples and Main adjudication. An LLM judge is advisory, not an oracle.
- Record final JSON validity and whole-interaction contract compliance separately. Do not repair candidate output before scoring without retaining the original and labeling the repair.
- Restore pristine evaluator files and isolate candidate artifacts. Test wrong paths, extra writes, test tampering, unnecessary tool calls, prompt injection and unearned approval claims without giving candidates real secrets or real external-action authority.
- Report first-attempt success, whole-trajectory success, per-family repeated consistency, recovery outcomes and failure taxonomy. Show small sample limits. Do not declare a winner from an average of unrelated tasks or infer reliability from three repeats.
- Keep a versioned JSON result record and a concise Markdown model/role report. A dashboard or standalone application is optional later, not a prerequisite.

Exit gate: the same saved artifacts reproduce the same grades; invalid/missing proof cannot yield pass; candidate model identity is verified; holdout and harness contamination are explicit.

## Priority 3 — role decisions

Produce role cards for documentation, source evidence, engineering implementation and QA: proven tasks, known failure modes, tool permissions, accepted scope, and uncertainty. Compare new models against both incumbent models and saved regressions on matched task contracts.

Promotion is a separate explicit owner decision. Require successful checks in the actual target role, independence between author and reviewer, unchanged tool/sandbox boundaries, a rollback path and a named recovery model. A backup must not silently accept a primary's plausible wrong output.

Pricing, accounting, token-cost comparisons and cost optimization remain outside this plan. Capability gates and role cards do not depend on them; do not scrape price tables, reconstruct invoices or resurrect the dropped accounting project.

## Stop conditions and non-goals

Stop a batch on mismatched model, incomplete prompt delivery, leaked key, broken evaluator, insufficient isolation, unapproved tool/permission request or exhausted declared budget. Preserve the failure and exact blocker. Do not change production routing during benchmarking, infer finance/account/execution authority, install third-party benchmark packages or run unattended campaigns.

No claim of end-to-end readiness follows from a structural validator or one synthetic canary. Main must distinguish configured, tool-proven, task-proven and accepted production scope.

## Recommended next implementation request

Do not rerun or tune this baseline. Preserve the frozen envelope and use it unchanged for later model enrollment. If Randall wants another development step, choose either the separately planned harder-envelope expansion or bounded target-role trials; either path needs its own exact scope and promotion remains a separate owner decision.
