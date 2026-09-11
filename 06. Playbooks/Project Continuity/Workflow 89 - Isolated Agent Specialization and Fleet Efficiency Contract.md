# Workflow 89 - Isolated Agent Specialization and Fleet Efficiency Contract

## D2A credit-source policy accepted - 2026-09-10 21:02 Phoenix <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

- Randall approved D2A: executor-store `trajectory_runtime_events` `model.completed` rows keyed by `run_id` are the required usage-credit source; `task_runs`-only credit is permanently disallowed. Missing usage stays PARTIAL/no-credit. No inference, backfill, invoice claim, D2b/D2c/D1/D3, config, skill, or runtime change. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Helpers authorized for the first wiring slice: Spark 1.3 coder (`implementation-builder`, patch_draft) and GLM 5.3 QA (`qa-redteam`) on the actual applied diff. Main applies and accepts. Proof: `tmp/wf89-fleet-20260909/d2a-owner-acceptance.json`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- First slice is a new deterministic module plus tests, not a closeout-ledger rewrite. Credit is not granted to lanes until that module is Main-accepted and later wired. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

## Attribution contract v0.2 accepted as corrected candidate - 2026-09-10 Phoenix evening <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

- Randall's 19:38 direction: continue open WF89 items until an owner decision is needed; route Spark 1.3 coder, GLM 5.3 QA, GLM 5.3 Flash scout, Main integrator/governor only. Executed exactly: Flash scout run b46ad380, GLM QA runs af7d03c4 + 6d3a14b8, Spark coder run da422b72, zero Main-authored contract content. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Main integrated the corrected attribution contract v0.2 as the evidence-grounded CANDIDATE (`tmp/wf89-fleet-20260909/coder-attribution-20260910/attribution-contract-v0.2.md`, 14,991 bytes, clean UTF-8). QA chain: scout v0.1 -> GLM 5.3 live-store verification `pass_with_limits` (0 blocking, 21 verified, 6 corrected) -> Spark v0.2 -> GLM 5.3 full document check `pass` (0 blocking, 4 cosmetic; corrections 6/6, decision items 2/2, hypothesis framing and header ok). Acceptance/limits record: `tmp/wf89-fleet-20260909/attribution-contract-v02-acceptance.json`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Verified candidate semantics: 5-witness binding (task_runs spine + subagent_runs cross-match + executor session_nodes/session_windows + trajectory_runtime_events usage + session_state_events identity trail); token credit can come ONLY from executor-store trajectory_runtime_events model.completed events keyed by run_id (input/output/total/cost.total required; cacheRead/reasoningTokens optional; missing-usage = PARTIAL/no-credit, never inferred); task_runs has no token columns and can never alone credit; totalTokens snapshot doctrine upheld; legacy subagent_dispatch_bindings permanently non-creditable, no backfill. End-to-end binding verified on real WF89 run 2b2dc337 with usage {input:22425, output:4033, cacheRead:8704, reasoningTokens:3184, total:35162, cost:0.0734}. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- File-symlink feasibility stays an UNVERIFIED hypothesis: host privilege facts verified live (no SeCreateSymbolicLinkPrivilege, Developer Mode off, build 26200), but the existing-target symlink behavior assertion is from memory and can be settled only by an owner-authorized Phase D canary (New-Item -ItemType SymbolicLink, isolated fixture, immediate cleanup). Contract MUST NOT assert Windows symlink policy as fact. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- No code, config, skill, runtime, model/default, permission or startup file changed; only tmp/ documents written. No usage credit granted to any lane; credit-source acceptance is the pending Phase D owner decision. No fleet-readiness, activation or efficiency-gain claim. Owner decisions outstanding (details in acceptance artifact): D2a credit-source acceptance; D2b content-hash hardening; D2c generation-aggregation rule (generations up to 17 observed); D1 symlink canary authorization; D3 real-agent-state canary policy; B1-B3 skill profile schema/scope/location; C1-C3 legacy bindings disposition, legacy constants, lab/fixture cleanup; existing Builder prompt-edit question still unanswered. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

## Narrow blocker-wording checkpoint - 2026-09-10 Phoenix <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

- Main accepted the unchanged Muse Spark 1.3 Contributor High wording/regression draft after Grok 4.6 High independent static actual-diff QA passed with no blocking findings. Source acceptance: `tmp/wf89-blocker-20260910/main-source-acceptance.json`; review: `grok-qa-result.json` in that proof root; finalization evidence: `tmp/wf89-blocker-20260910/final-closeout.json`. Reviewer did not execute tests or compute hashes; the new substring/loose-OR test is bounded wording coverage, not proof-ingestion or fixture-safety validation. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- The WF89 blocker now cites the dated four native Windows DIRECTORY-JUNCTION denial cases and positive controls instead of the obsolete no-native-fixture assertion. Main's focused suite, two-file compile, exact Spark-span comparison and normalized full-module AST proof pass: all 43 other routes, all other WF89 fields, 44 total/P1 12 counts, authority gates and freshness logic remain unchanged. Existing stale-owner negative coverage uses WF75, not a new WF89 fixture. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- File-symlink coverage remains partial/unavailable; no universal reparse/race/OS or fixture-cleanup claim. Live credited attribution and historical accounting remain blocked; no accounting credit, activation or whole-fleet readiness follows. This is only the narrow source correction and derived-route synchronization, not WF89 completion, a new fixture, or a config/runtime/policy change. Earlier dated checkpoints remain historical evidence. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

Status: **A1 and the three-file WF89 discovery repair are technically accepted with explicit limits. Broader assessment, an inactive startup-cleanup proposal, and an evidence-grounded attribution contract v0.2 candidate are accepted; four native Windows directory-junction denial cases pass and file-symlink coverage is CLOSED as host-evidenced denied-by-privilege (approved D1 canary, WinError 1314). D2a accepted: a QA-verified candidate credit reader now provides on-demand per-run observation (282 subagent runs: 124 CREDITABLE / 37 PARTIAL / 119 INCOMPLETE / 2 OBSERVABLE_ONLY) under a review-only posture with no credit granted. WF89 remains open on owner decisions only: D2b/D2c/D3, B specialization, C reconciliation, Builder prompt-edit, and credit-reader promotion to scripts/. No live startup, skill, model/default, permission or configuration change.**
Opened: 2026-09-09 (Phoenix)
Owner: Veritas Main
Route: this note; `openclaw.json` `agents.entries.*`; `scripts/agent_fleet_policy.py`; `veritas-isolated-agent-contract`; `veritas-model-routing-helper-lanes`

## Current governed checkpoint - 2026-09-09 21:36 MST

This section supersedes present-tense status claims below; the original review is retained as dated evidence, not live truth. This is the single WF89 continuity owner. The similarly named Specialization and Efficiency Contract note is a supplementary review, not a second execution queue. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

- Owner direction: proceed with review and local remediation; GLM 5.3 challenger, Muse Spark 1.3 coder, Grok 4.6 independent QA; High or Extra High effort. Main orchestrates, governs, integrates reviewed drafts, and performs final review only. No silent model substitutions or independent Main authorship. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Root: `WF89-FLEET-20260909`; proof root `tmp/wf89-fleet-20260909/`. Existing dirty work is preserved. Initial lane/resume checks found zero active leases, no resume target, and five historical register warnings. `workflow_router.py WF89 --answer all` returned `workflow_not_found`; registration is an in-scope continuity gap. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Baseline correction: live Main primary is Terra, not Sol; `agent_fleet_policy.MAIN_PRIMARY` already matches Terra following the 21:16 owner change. `MAIN_MODEL` remains Astra and the live fallback list exceeds policy; these are distinct questions, not permission to revert the owner change. This Main session is Astra. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Baseline correction: `tmp/persistent-transport-implementation-builder-20260909.json` exists and is timestamp-fresh at intake. It is a minimal v1 nonce/context record, not realistic source-payload or scoped-writeback proof. Historical extended v1 records conflict with the router's exact five-field v1 schema. Do not claim every proof expired or accept a weak proof as full readiness. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Baseline correction: shell-free receiver hash verification can use Main hashing an exact returned echo, as documented in the later research-scout proof; an echoed manifest hash alone is not independent source verification. Native task-text transport must not be relabeled staged attachment transport. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Execution friction: session-settings requests failed on incompatible single/batch-target fields; no setting changed and those attempts receive no successful work credit. Request High directly on bounded child runs instead. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

| Phase | Scope and acceptance | Gate/status |
|---|---|---|
| A0 | Reconcile current evidence; GLM challenges conclusions, ordering, telemetry semantics, and authority boundaries. | Challenge completed and Main-adjudicated; old reports still grant no readiness credit. |
| A1 | Add/repair deterministic metadata-only dispatch measurement and attribution with explicit unknown-versus-uninstrumented states; preserve historical ledgers. | Reader/current-window repair and task-only Grok QA gate accepted with limits; live credited attribution remains unproven. |
| A2 | Diagnose and repair bounded scheduler-history collection and proof validation where reproduced; preserve partial/failure evidence. | Historical timeout did not reproduce; no speculative patch or job edits. Empty successful sample is not scheduler-wide health proof. |
| B | Tool-compatible skill and context profiles, task/return budgets, prompt-injection and single-writer design, measured eval plan. | Prepare exact proposals; config/skill publication or policy changes need the applicable owner gate. No mandatory synthetic 20-run success cohort. |
| C | Main fallback/legacy-constant reconciliation, continuity-writer containment, lab disposition and preamble hygiene. | Inspect and prepare rollback-ready decisions; no deletion, agent retirement, bootstrap/doctrine or runtime changes by implication. |
| D | Run only authorized realistic canaries/acceptance, compare measured outcomes, final Main review and durable pickup. | No blanket production, billing, efficiency-improvement, or deployment claim beyond actual evidence. |

### Phase A1 dispatch checkpoint - 2026-09-09 22:00 MST

- GLM High challenge completed; Main accepted reproduction-first and one-capture-point scope, while correcting unsupported recommendations. Review: `tmp/wf89-fleet-20260909/a0-main-review.json`. Runtime usage was exposed even though the child prose said unavailable; metadata wins. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Confirmed root cause: both usage-reader entry points still read absent `sessions/sessions.json`, while live OpenClaw 2026.9.2 stores the session index in `agent/openclaw-agent.sqlite`. Baseline returns six missing sources, zero observations; supported CLI and allowlisted read-only SQLite fields expose current GLM model, High effort, lifecycle and token counters. `totalTokens` is a context snapshot, not total run consumption. Proof: `a1-baseline.json`; scoped repair contract `a1-contract.md`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Historical collector timeout did not reproduce: current bounded collection was ok in 2.941s with zero eligible jobs; no speculative timeout patch. Current model-run rollup is 1,680 logical rows with 881 model-observed audit rows but zero credited attribution, not zero observed metadata. Physical model-rollup history has 419 snapshots; coding history has 1,434 rows. Proof: `a2-collector-baseline.json`, `baseline-ledger-counts.json`, `a1-before-inventory.json`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Builder's occupied `/worktree` and part1 token-ledger sources are excluded. Three A1 inputs total 63,174 bytes; actual sandbox byte/hash preflight passed. Source before-images and excluded-file hashes frozen. Spark code attempt 1 is running at verified High in Docker, patch-draft only, under exact opaque dispatch binding. Main source edits and acceptance have not happened. Proof: `a1-builder-preflight.json`, `a1-approved-route.json`, `a1-dispatch-register.json`; lease `WF89::a1-sqlite-reader`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Initial route declarations correctly failed on review-only/write-mode mismatch and then selecting QA for a read-only implementation shape. Final project route uses the explicit owner-authorized local source-repair class, with Spark still draft-only and Main owning host writes; fresh realistic attachment-mount proof passes. The remaining warning is the task-specific baseline reference, reviewed by Main. Failed preflight packets remain as evidence; no validator was changed. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- WF89 remains active, not complete or fleet-ready. After Spark returns, Main verifies/applies the unchanged draft, runs the real focused suite and live metadata readback, then Grok independently QAs the frozen actual applied diff at High. Any material rejection gets one bounded Spark repair and fresh Grok QA; config/retirement/threshold/skill-publication gates remain separate. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

### A1 bounded repair checkpoint

- Spark attempt 1 returned a draft with 18 reported passing tests. Main rejected it before host application: sibling-agent root-link containment was incomplete; exact lookup could miss valid sessions after an unordered 512-row cap; existing canonical non-files could silently fall back; key negative cases were untested. Review and candidate hashes: `tmp/wf89-fleet-20260909/a1-draft-review.json`. These are Main preliminary findings, not a completed Grok QA pass. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Both host sources and all six excluded-file/worktree hash controls remain unchanged. Attempt 1 is preserved blocked/rejected, with zero acceptance credit. Runtime exposed 161,282 input / 78,675 output tokens; cache/billing semantics and credit are not inferred. Child scratch had been removed, so exact-path artifact recovery failed; no sandbox restart, cleanup, source modification, or broad search was used to compensate. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Attempt 2/retry 1 failed before substantive repair. Sanitized history proves frozen staging succeeded, but the first edit of `/tmp` was denied: filesystem tools require the isolated `/workspace` root. Main's handoff wrongly forbade it. Provider then hit an idle timeout (120s); no structured result or declared output artifacts survived. Proof: `a1-r2-failure.json`. This is a verified tool-root mismatch plus provider failure, not a second rejected implementation or permission-expansion need. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- The same first substantive repair now has one explicit clean-context transport recovery, attempt 3/retry 2, under `WF89::a1-sqlite-reader-r3`. Spark High; ordinary announcing run `8fe07b6b-ca8c-4f88-896b-fc2bc462f5de`, child `agent:implementation-builder:subagent:ac458454-e67b-4ae8-bad0-df1b9cf791d2`. Wait with `sessions_yield`, not collector wait. Current machine pickup: `tmp/wf89-fleet-20260909/current-handoff.json`. Deadline 15 minutes; model and role unchanged. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Corrected scratch/output scope is only `/workspace/wf89-a1-r3/` in this task's already-permitted isolated workspace. Retain two candidates, normalized patch and test log; return compact references/hashes, not source replay. Main retrieves only declared files after verifying exact task/container/workspace ownership. No shared `/worktree` access, config/sandbox/permission change, or cleanup is authorized. The earlier `/tmp`-only clause is superseded; do not bypass file-tool containment through another tool. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

### A1 recovered-candidate review - 2026-09-10 07:45 Phoenix

- This checkpoint supersedes the running/wait instructions above. Spark recovery settled. All four declared artifacts survive in the exact task-owned host workspace mount; direct container copy failed, but exact host-path recovery succeeded without searching other tasks or changing containment. Full hashes match Spark's recorded tool output. Proof: `a1-r3-recovery-proof.json`; candidate module SHA256 `17b1c2018374865a0e10ce9a59f0166432ea5c4b7877b0b5e09a37e8d02ed322`. Both original host sources and all six excluded controls remain unchanged. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Main reran the candidate's focused suite in scratch: exit 0. Independent synthetic probes nevertheless returned verified bound records for contradictory embedded/current session IDs and contradictory current-window timestamps. Deleting the current window silently yields bulk `ok`, zero valid and zero invalid. Proof: `a1-r3-main-probes.json`, `a1-r3-main-suite.txt`. Candidate remains unapplied; passing the supplied suite is insufficient. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Actual Spark model and High effort were verified via runtime status; counters are exposed (rounded display: 45k input, 22k output, 1.0m cached), not provider-unavailable. These are not exact billable amounts or acceptance credit. Failed/retry history remains intact. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- A kept Grok4.6 session is performing fresh raw-source readback before independent rejection adjudication. Its role is `preapply_rejection_adjudication`, NOT `actual_applied_diff` release QA. Frozen QA input: six files, 90,822 bytes, largest file 35,051 bytes; manifest `a1-r3-grok-input-manifest.json`. Main must verify transport, actual model/High and source-target integrity before accepting review evidence. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

### Explicit narrow rescope approved - 2026-09-10 07:49 Phoenix

- Grok4.6 High returned the exact 2,104-byte source excerpt; Main hash-matched the actual echo. Substantive QA did NOT run: the implementation router emitted `qa_route_requires_glm` despite the owner-selected Grok assignment. The existing task-role override is pinned to an unrelated expired September 5 approval and was not reused. Proof: `a1-r3-grok-readback-proof.json`, `a1-r3-grok-review-route.json`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Main asked one scope decision; Randall selected **Approve narrow rescope**: Spark may repair current-session identity/lifecycle validation and add a task-scoped fail-closed Grok QA exception with regression tests, followed by Grok review and Main verification. No runtime defaults change. Immutable approval: `a1-rescope-owner-approval.json`, SHA256 `f29cfae109aaedb0412583489284d190fde60754ca5a5579aceefac471e7f86f`. The new exception approval expires after 24 hours; no existing transport/proof lifetime is extended. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Reader lane `WF89::a1-reader-rescope`: two source paths only, six frozen inputs / 93,943 bytes. It repairs the recovered candidate, not yet-applied host sources. Guard lane `WF89::a1-qa-gate`: exact router-gate replacement and two new WF89 exception/test modules, six inputs / 76,279 bytes. The 177,924-byte router is supplied as bounded frozen context plus its full original hash, so Main must validate the complete integration locally. Routes and leases passed with zero current admission errors. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Both kept Spark sessions were verified at actual Muse Spark1.3 / High / Docker. They write only separate task-local draft outputs, never the occupied shared Builder worktree. Session/run/output pickup lives in `current-handoff.json`. This is a newly authorized rescope, not an unapproved automatic replay; the old rejected candidate and all retries keep zero acceptance credit. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Exact owned-task metadata corroborates equal current-window/entry start and end fields in two real sessions. Prior Spark recovery exposed 44,781 input + 1,017,775 cache-read + 21,670 output tokens; gross 1,084,226 exceeds its old 1M gross budget and cache exceeds its old 800k budget. Preserve that incident rather than efficiency credit. Grok's runtime reports High while its index `thinkingLevel` is null; do not fill absent index telemetry from inference. Proof: `a1-rescope-live-lifecycle-metadata.json`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

### Final bounded A1 acceptance - 2026-09-10

This latest checkpoint supersedes all provisional running/unapplied instructions above. Main accepted only the five-file source slice, with the explicit limits below. The entire WF89 workflow, accounting, and fleet activation are not complete. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

- Both Spark High drafts were recovered from their exact task-owned workspace mounts; all four declared outputs per task hash-matched. Main applied unchanged reviewed source and the two exact router replacement spans. Five changed files: `isolated_agent_usage_metadata.py`, its test, `project_implementation_router.py`, and new `wf89_task_qa_exception.py` / test under `scripts/`. Original rollback bytes remain in `a1-rescope-host-before/`; all six excluded source/worktree controls remain unchanged. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Actual applied diff SHA256 `824edebbfed8d0801b1eff0a65abac307070dd832da414e5c51639f5a20106b5`; all five post-apply hashes were rechecked after QA. Main acceptance owner: `tmp/wf89-fleet-20260909/a1-main-acceptance.json`. Grok result: `a1-grok-applied-qa-result.json`, SHA256 `bf8ff49b0e7dfad9cb199c92f25f55524f28cb47f0efd20008c4c8dfb2c834e7`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Real host checks pass: both focused suites, five-file compile, full project-router regression, generated router example and packet-linter compatibility. Changed-file routing passes at narrow budget. The 27-function reader driver reports two Windows link skips; the 31-test gate suite reports one. Do not claim 58 fully exercised Windows tests or junction safety proof. Linux task test logs provide separate, not equivalent, link coverage. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Live read-only reader now observes all six specialist stores: 133 valid metadata records and 84 invalid/rejected records, versus the original six missing sources and zero observations. Each of Main's three original identity/time/orphan failures now rejects and surfaces warning/invalid evidence. Valid metadata observations are not dispatch-bound usage credit, accepted jobs, invoices, or a measured efficiency gain. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Full actual router admits only the scoped approved Grok QA shape; wrong root, write claims, wrong effort and missing effective transport proof still fail. GLM remains the default QA model. No runtime/config/defaults changed. The new owner receipt remains hash-pinned and expiring; changing an ignored mirror field is not equivalent to invalidating the effective transport proof. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- Actual Grok4.6 High reviewed all six frozen inputs / 112,737 bytes and the exact applied diff: `pass_with_limits`, no blocking code finding. It is independent static QA, not reviewer-executed tests or independent hash computation. One return-format-only follow-up recovered its truncated final result without repeating the review. Main verified the full recovered findings and accepted the narrow slice. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

| Remaining gate | Current truth and next action |
|---|---|
| Live credited attribution | One exact historical terminal-binding lookup returned `dispatch_binding_missing_or_ambiguous`; investigate binding-store/lifecycle lineage and prove a correctly bound live canary without backfill or inferred credit. |
| Windows link/junction coverage | Three host tests skipped; obtain a bounded native Windows denial fixture under existing permissions, not privilege or sandbox expansion. |
| Historical accounting validation | A blocked August 24 canary has `isolated_source_reverification_mismatch`; full register validation is not green, while current active admission has no errors. Preserve the historical failure and inspect only its owner evidence. |
| Diagnostic specificity | Canonical failures collapse to generic labels, and a multi-match error is labeled not-found. Grok classifies both low/nonblocking; future scoped cleanup only. |
| Remaining WF89 work | B/C/D and workflow registration remain open. Skill publication, persistent role/default changes, runtime/tool expansion and lab retirement keep their separate owner gates. |

The repair/review write leases end here; technical acceptance is distinct from blocked accounting/activation. Main owns the next bounded attribution and Windows-proof scope. No further automatic rewrite, historical ledger rewrite, whole-workspace-green claim or fleet-readiness promotion follows from this acceptance. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

### Broader fleet-efficiency stage - 2026-09-10

Randall requested broader work at 10:34 Phoenix. This latest checkpoint supersedes older missing-WF89-route and no-native-junction-fixture statements above; earlier checkpoints remain dated evidence. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

- **Discovery repaired and accepted:** Spark High authored the exact routing-index entry, canonical Active Workflows row and focused tests. Main corrected a workspace-root command and a raw-versus-reconciled test assumption through Spark, then ran the real suite. WF89 resolves via JSON and SQLite; total routes44/P1 routes12; all43 earlier route calls are AST-identical. Exact aliases, fragment rejection, stale-owner rejection and authority boundaries pass. Grok4.6 High independently returned `pass_with_limits` against actual applied diff `d56ef981ab97eb2222a62a372c320752151b8c06e52b5605a849e42f80aafdc4`. This was not first-pass work. Proof owner: `tmp/wf89-fleet-20260909/broader/broader-stage-acceptance.json`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- **Native Windows evidence obtained without privilege changes:** four real directory-junction cases deny escape through the owning-agent root, canonical-store directory, legacy-store directory and approval-receipt parent. The three valid source controls and valid receipt control pass. Fixtures are retained under `broader/junction-probe-v1`; proof `broader/windows-junction-proof.json`. File-symlink tests still lack coverage; no claim covers every reparse type or race. The old static index no-fixture wording was flagged for a separate narrow refresh and does not outrank this newer proof. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- **Attribution cause narrowed:** the old custom binding store contains8 bindings/16 events with its newest reservation in August and no match for two exact September WF89 jobs; installed dist has no legacy table-name string. Current protected `task_runs` records do match requester, executor, child and run identity for both jobs. This is candidate successor provenance, not permission to bypass the old gate or grant usage credit. Same-session continuations can change task/session state, so immutable per-attempt capture and lifecycle semantics require a reviewed contract. Proof: `broader/binding-baseline.json`, `binding-producer-discovery.json`, `task-identity-proof.json`. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- **Specialization assessed, not activated:** all six specialists still have empty skill lists. Several old candidates are retired redirects; others require absent CLI/memory tools or the Windows host instead of Builder's actual Linux sandbox. The six-role compatibility/next-decision assessment is `broader/fleet-specialization-assessment.md`, grounded in current config projections and exact skill excerpts. No skills were authored, published or assigned, and no fallback or lab grant was changed. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- **Startup work stays draft-only:** a specific Builder prompt-change question received no answer, so no live startup/generator change was made. The inactive BOOTSTRAP proposal removes two paragraphs already retained in AGENTS, reducing that file9872→8993bytes (879bytes,8.9%); this is not measured token/latency savings or an activation-ready profile. A non-equivalent retired-pointer block was deliberately retained for review. Proof: `broader/builder-startup-inactive-proposal.json`. Live AGENTS/BOOTSTRAP hashes for the14 inspected specialist/lab files remain unchanged. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->
- **Bounded return worked:** registration QA used a29,288-byte packet and1600-character return cap; the complete verdict was recovered without an extra reformat model call. Source/regression corrections and all usage limitations remain visible; no fleet-efficiency or model-ranking promotion is inferred. Current global terminal-register issues (G6 missing incident metadata and the old attribution canary) remain outside this accepted registration slice. G6, graph freshness and the dated blocker wording were recorded as separate follow-up suggestions. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

Next material work: independently define/prove the current task-registry attribution contract; obtain explicit approval before a generator-integrated startup pilot or skill publication/assignment. Keep model pins, runtime permissions, schedules and lab disposition unchanged until their gates are approved. The registration/source-write stage is complete; broader activation is not. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

> Historical review below includes superseded model/state assertions and unapproved recommendations. Use the latest checkpoint and exact proof artifacts for current truth.

## Conclusion

The fleet is over-governed and under-used. Governance doctrine is mature and mostly correct; utilization is roughly 3% of session volume, per-lane attribution is 0%, and no specialist can load a single workspace skill. The bottleneck is not safety and not model choice — it is that the lanes are model pins with tool masks rather than specialists, and that we currently cannot measure whether any lane earns its keep.

Do measurement first (Phase A), then specialization (Phase B). Do not re-tune model pins until attribution is populated; today every pin is a prior, not a finding.

## Evidence

### Utilization

Session-store file counts, `C:\Users\Veritas\.openclaw\agents\<id>\sessions\`, read 2026-09-09:

| Agent | Session files | First | Last |
|---|---|---|---|
| main | 3,557 | 2026-05-19 | 2026-09-09 |
| qa-redteam | 30 | 2026-07-03 | 2026-09-09 |
| finance-source-scout | 22 | 2026-07-05 | 2026-09-06 |
| finance-redteam | 19 | 2026-07-05 | 2026-09-09 |
| implementation-builder | 18 | 2026-08-10 | 2026-09-09 |
| research-scout | 16 | 2026-07-03 | 2026-09-09 |
| docs-continuity-editor | 4 | 2026-09-06 | 2026-09-06 |
| oxalpha-lab | 0 | never | never |
| oxalpha-functional-lab | 0 | never | never |

The six specialists total 109 files against Main's 3,557 (~3%). `docs-continuity-editor` has four sessions, all created 2026-09-06 and all since deleted; it has never been used for real work. Both lab agents have never run.

`data/state-history/coding-outcome-ledger.jsonl` (1,433 rows, 2026-06-12 → 2026-09-09) records `actual_execution_backend` as: `null` 1,279, `main` 83, `model_free_command` 60, `persistent_isolated_agent` **9**, `codex_native_subagent` 2.

### Attribution

`data/state-history/model-run-ledger.jsonl`, receipt generated 2026-09-09T04:46:37Z:

- `model_attribution_coverage: 0.0`
- `model_attribution_recent_coverage: 0.0` (30-day window)
- `cost_rows: 0`, `token_rows: 0`, `api_equivalent_cost_rows: 0`
- `lane_audit_only_uncredited_rows: 1616` of `row_count: 1671`
- `cron_run_collection_status: "timeout"` on the latest run

`veritas-model-routing-helper-lanes` defines six efficiency metrics (uncached input tokens per accepted job, gross replay tokens, first-pass acceptance, elapsed time to accepted proof, retry tax, escaped defects). None are populated. The skill already disables automatic route promotion, which is the right posture given this — but it means the routing table has never been validated against outcomes.

### Reliability

From the 60 most recent live sessions:

| Agent | Failed / total | Notes |
|---|---|---|
| research-scout | 3 / 5 | incl. `main` session titled "test", "Grok token-ledger QA plan", "AGI readiness · Phase gates" |
| finance-redteam | 2 / 6 | "GLM token-ledger challenge", `main` |
| qa-redteam | 1 / 6 | "AGI readiness · Behavioral acceptance matrix" |
| implementation-builder | 2 / 16 | canary failed then succeeded on retry |
| finance-source-scout | 0 / 2 | — |

Specialist `fallbacks` are `[]` by design, so a single provider hiccup is a terminal lane failure requiring a Main-selected clean-context retry. That design is defensible for provenance, but it converts transient provider errors into full restarts, and research-scout — pinned to a single vendor with no in-lane recovery — carries the worst rate.

Ruled out as causes: the builder sandbox is healthy. Docker 29.7.2 responds, and all 13 configured bind sources under `workspaces\implementation-builder\` exist.

### Specialization gap

Every specialist entry in `openclaw.json` has `"skills": []`. No lane can load any of the ~75 workspace skills. All procedure must be re-inlined by Main into each handoff, inside the frozen budget of 6 files / 120,000 bytes / 30,000 estimated tokens set by `veritas-isolated-agent-contract`. The lanes are therefore model pins plus tool masks, not specialists.

### Context preamble

Per OpenClaw docs (`concepts/agent-workspace.md`, `concepts/context.md`), injected workspace files are `AGENTS.md`, `SOUL.md`, `IDENTITY.md`, `USER.md`, `BOOTSTRAP.md`, and optional `MEMORY.md`. Injected characters per lane:

| Agent | Injected chars | ~tokens | BOOTSTRAP.md share |
|---|---|---|---|
| finance-source-scout | 19,265 | ~4,800 | 12,017 (62%) |
| finance-redteam | 18,232 | ~4,560 | 11,447 (63%) |
| implementation-builder | 17,605 | ~4,400 | 9,872 (56%) |
| qa-redteam | 16,650 | ~4,160 | 9,131 (55%) |
| research-scout | 16,593 | ~4,150 | 9,072 (55%) |
| docs-continuity-editor | 16,164 | ~4,040 | 9,358 (58%) |

All are within the 20,000-char per-file and 80,000-char total caps, so nothing is truncated. But this is paid on every spawn, and two structural problems sit inside it:

1. OpenClaw defines `BOOTSTRAP.md` as a **one-time first-run ritual, to be deleted after the ritual completes**. The workspace has repurposed it as a permanently regenerated operating packet, and the role packets state it "must not be deleted." It is now the majority of each lane's preamble and duplicates content already in `AGENTS.md`.
2. Retired `TOOLS.md` boilerplate was migrated *into* `AGENTS.md`, producing a duplicate `## Tools` heading and injected text that reads "Do not treat this file as injected operating doctrine" — while being injected. The same pattern exists in the workspace root `AGENTS.md`.

### Dead lanes holding live grants

`oxalpha-lab` and `oxalpha-functional-lab` were built to evaluate "OpenRouter stealth/ox-alpha". `plugins.entries.openrouter.enabled` is `false`. Both are pinned to `openai/gpt-5.6-luna`, not any ox-alpha model. Neither has ever run a session. `oxalpha-functional-lab` holds `sandbox.workspaceAccess: "rw"` — a writable sandbox lane for a purpose that no longer exists. `tools.agentToAgent.allow` grants `oxalpha-lab`, but `agents.entries.main.subagents.allowAgents` does not list it; `oxalpha-functional-lab` appears in neither. Both grants are orphaned.

### Config drift

`scripts/agent_fleet_policy.py` sets `MAIN_MODEL = "openai/gpt-6-astra"` and the generated bootstraps repeat "Veritas Main model: `openai/gpt-6-astra`". Live config sets `agents.entries.main.model.primary` to `openai/gpt-5.6-sol`. Policy and config disagree on Main's primary model, and the disagreement is being propagated into every lane's injected packet.

Separately, observed session models diverge from configured primaries — `qa-redteam` ran "G6 matrix Sol final QA" on `gpt-5.6-sol` against a configured primary of `glm-5.3`. Per-session pinning by Main is legitimate, but it means "configured primary" is not "what ran," which is exactly what the broken attribution layer was supposed to record.

## External practice (2026-09-09 web research)

Primary/official sources:

- **Anthropic, *How we built our multi-agent research system*.** Opus lead + Sonnet subagents beat single-agent Opus by 90.2% on their internal research eval. Token usage alone explains 80% of BrowseComp performance variance. Agents use ~4× chat tokens; multi-agent ~15×. Stated anti-indication: multi-agent is a poor fit where agents must share context or have many inter-dependencies, and "most coding tasks involve fewer truly parallelizable tasks than research." Their appendix recommends subagents **write outputs to the filesystem and return lightweight references** to avoid telephone through the coordinator. Their documented early failure was spawning 50 subagents for simple queries; the fix was effort-scaling rules in the orchestrator prompt.
- **Anthropic, *Effective context engineering for AI agents*.** Names context rot, attention budget, just-in-time context, progressive disclosure, compaction, tool-result clearing. Calls bloated/ambiguous tool sets the most common failure mode. Test offered: if a human engineer cannot say which tool applies, the agent cannot either.
- **Anthropic, *Building effective agents*.** Names orchestrator-workers and routing (cheap model for easy queries, strong model for hard) as distinct patterns.
- **Claude Code subagent docs.** Non-fork subagents see none of the parent conversation but do inherit the full memory-file hierarchy; Explore/Plan deliberately skip it to stay fast and cheap. Subagent `description` text sits in parent context permanently. Parallel writers are handled with git worktrees; agent teams do **not** auto-isolate and require manual file partitioning. Model pins rot across versions — Explore's model default changed between releases.
- **Claude Code secure-deployment docs.** Isolation table (sandbox-runtime / Docker / gVisor / VM). Hardened flags: `--cap-drop ALL`, `no-new-privileges`, seccomp, `--read-only` + tmpfs, `--pids-limit`, non-root, read-only code mounts. Explicit: permission command-parsing "is a permission gate, not a sandbox"; host-allowlist proxies do not do TLS inspection, so `--network none` is strictly stronger. Sandboxing cut permission prompts 84% internally, and approval fatigue is itself named a security failure.
- **Simon Willison, *The lethal trifecta*.** Private data + untrusted content + external communication. Guardrails advertising "95% of attacks caught" are quoting a failing grade; the only reliable mitigation is architectural — break one leg.
- **RouteLLM (Ong et al., ICLR 2025).** >85% cost reduction on MT Bench retaining 95% of GPT-4 quality. **Important caveat:** this is per-query *difficulty* routing between a strong/weak pair, and routers trained on Arena data performed near-random on MMLU. It is not evidence for role-based cross-vendor pinning.

Contested:

- **Cognition, *Don't Build Multi-Agents*.** Argues for sharing full traces rather than messages, and that conflicting implicit decisions across agents produce incoherent output. Notes Claude Code deliberately never parallelizes *writing* subagents. Directly tensions Anthropic's post; both can hold — Anthropic's win is breadth-first research, Cognition's warning is construction.
- **Traversal, *The Bitter Lesson for Agent Harnesses*.** Argues routers, standalone summarizers, and fixed sequences each freeze a cognitive decision into a component boundary and cap the system at the designer's foresight. Argument, not measurement, and in tension with Anthropic's shipped orchestrator-worker design.

Where evidence is genuinely thin: role-specific multi-model pinning (no controlled study found), per-agent "earning its keep" methodology (no published framework — our ledger design is ahead of the literature, but only if it actually fills), and whether multi-agent helps coding at all, where Anthropic and Cognition converge on "less than you'd think."

## Recommendations

### Phase A — Measurement (blocking; do first)

- **A1. Repair lane attribution.** Make every `persistent_isolated_agent` dispatch stamp agent id, expected/actual model path, session reference, and token usage into `coding-outcome-ledger.jsonl` and `model-run-ledger.jsonl`. Acceptance: `model_attribution_recent_coverage` ≥ 0.80 over the trailing 30 days after 20 dispatches. Until then no pin change may be justified on quality grounds.
- **A2. Fix the `cron_run_collection_status: "timeout"` regression** in the run-ledger collector; it currently returns zero jobs.
- **A3. Build ~20-case per-lane eval sets** from real historical assignments. Use a **single** judge call emitting 0.0–1.0 plus pass/fail — Anthropic found one judge more consistent than several specialized ones. Rubric: factual accuracy, citation accuracy, completeness, source quality, tool efficiency. Use end-state checkpoints, not turn-by-turn, for the write-capable lanes.

### Phase B — Specialization (the actual objective)

- **B1. Assign skills per lane.** Highest-leverage single change. Proposed, subject to a tool-compatibility check first — a skill that calls `exec` inside a no-exec lane is worse than no skill — and capped at 3–4 per lane because skill entries cost prompt tokens:

  | Lane | Candidate skills |
  |---|---|
  | research-scout | `veritas-intelligence-effort-router` (read-only paths), `opportunity-recommendation-review-router` |
  | finance-source-scout | `veritas-fundamental-pass`, `veritas-post-earnings-sync`, `sec` |
  | finance-redteam | `veritas-response-contract`, `veritas-positioning-pass`, `veritas-macro-pass` |
  | qa-redteam | `code-review-auditor`, `workspace-qa-pass`, `security-review` |
  | implementation-builder | `disciplined-implementation`, `windows-powershell-workspace`, `safe-refactor-planner` |
  | docs-continuity-editor | `memory-continuity-manager`, `project-continuity-manager`, `wiki-maintainer` |

- **B2. Let the artifact-producing scouts write their own artifacts.** `qa-redteam` has a `review-packets/` directory and `research-scout` has `findings/`, but both deny `write`, so only Main can populate them. Granting workspace-scoped write implements Anthropic's "write to disk, return references" pattern and removes the coordinator-telephone tax. This does **not** open the lethal trifecta provided `fs.workspaceOnly` stays `true` and no messaging, network-write, or cross-context tool is added. **Config change — requires Randall's approval.**
- **B3. Decide `docs-continuity-editor`'s fate.** Four sessions, all deleted, unused since creation. Either give it a standing job — memory, wiki, and continuity sync after Main-accepted work — or retire it. Recommendation: give it the job. It is the one lane whose function Main currently performs inline at high context cost.
- **B4. Add effort-scaling rules** to `veritas-model-routing-helper-lanes`: simple lookup → no lane (Main direct or model-free); bounded comparison → 1 lane, 3–10 tool calls; broad cross-contract challenge → 2–4 lanes. We are paying roughly 4–15× tokens for fan-out and currently have no rule tying task shape to lane count.

### Phase C — Contraction and hygiene

- **C1. Retire or re-scope `oxalpha-lab` and `oxalpha-functional-lab`,** and remove the orphaned `agentToAgent` grant. Priority on `oxalpha-functional-lab`, which holds writable sandbox access for a dead purpose. **Config change — requires approval.**
- **C2. Cut the preamble below ~10,000 injected chars per lane.** Fold non-duplicated `BOOTSTRAP.md` content into `AGENTS.md` and stop regenerating a permanent bootstrap, or reduce it to volatile runtime facts only. Delete the migrated `TOOLS.md` self-negating boilerplate and the duplicate `## Tools` heading from every role packet and from the workspace root `AGENTS.md`.
- **C3. Resolve the Main model drift** between `agent_fleet_policy.MAIN_MODEL` (`gpt-6-astra`) and `agents.entries.main.model.primary` (`gpt-5.6-sol`). Decide which is authoritative, make them agree, and regenerate bootstraps.

### Phase D — Readiness for stronger models

- **D1. Re-label model pins as cost and blast-radius controls, not quality claims,** in `veritas-model-routing-helper-lanes`. The only rigorous routing evidence is difficulty-based and degrades out-of-distribution; Anthropic's multi-agent win confounds architecture with model mix. Add a pin review that reads the Phase-A attribution ledger once populated.
- **D2. Anti-scaffolding audit.** The router, the frozen 6-file handoff budget, and the fixed phase sequence are the three components most likely to become a ceiling under a stronger model. Add a standing trigger: whenever a lane's model is upgraded, re-test whether its scaffolding still helps or is now being routed around. Claude Code's own Explore-model default flipping across versions is the concrete precedent for pin rot.
- **D3. Treat scout output as untrusted content, not merely unaccepted output.** `AGENTS.md` currently says helper output is "untrusted until Main verifies" — that is a verification rule, not an injection-handling rule. The four web-reading lanes ingest untrusted pages and return prose into Main, which holds full authority. Add explicit instruction-injection handling to `veritas-isolated-agent-contract`. Note that Claude Code ships automated scanning of subagent reports for instruction-shaped patterns and its own docs say that is not a substitute for restricting reach.
- **D4. Apply the published Docker hardening flags** to any surviving sandbox lane: `no-new-privileges` and a custom seccomp profile are currently absent. `--network none` is already set and is stronger than a host allowlist, since allowlist proxies do not inspect TLS.

## Stop lines

- No `openclaw.json` mutation, tool-policy change, skill assignment, sandbox change, or agent retirement without Randall's explicit approval. Every Phase B/C item marked "config change" is blocked until then.
- No skill mutation outside Skill Workshop.
- No route promotion, pin change, or cohort claim from local counters until Phase A attribution is populated and validated.
- This note is a review-only contract. It grants no capital, trading, account, execution, external-delivery, or cron-mutation authority.
- Generated bootstraps and this note do not outrank `SOUL.md`, `AGENTS.md`, `USER.md`, or owner artifacts.

## Next action

Randall confirms scope and tier. Recommended: register as **P1** in `06. Playbooks/Active Workflows.md` and start Phase A only — A1 and A2 are internal instrumentation repairs inside existing approved boundaries and need no config change. Phases B and C need an explicit approval pass first.
