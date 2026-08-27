# Workspace Efficiency and Speed Audit and Deferred Execution Plan — 2026-08-24

## Control status

| Field | Value |
|---|---|
| Status | Audit complete; recommendations and contracts are proposal-only |
| Human owner | Randall |
| Main integrator | Veritas main session |
| Audit date | 2026-08-24 Phoenix / 2026-08-25 UTC |
| Machine contract | state/workspace-efficiency-speed-execution-contract.json |
| Upstream governance owner | 06. Playbooks/Project Continuity/Veritas Harness V2 - Governance and Efficiency Upgrade Plan - 2026-08-22.md |
| Execution authority | Not granted by this document |

Randall authorized writing this audit and its deferred execution contracts into the workspace. That authorization does not approve a cron, scheduler, configuration, authentication, channel, plugin, startup, service, runtime, OpenClaw core, finance-canon, portfolio, account, paper/live execution, archive, or deletion change.

## Decision

The workspace has real speed opportunities, but the highest-return work is narrower than a broad refactor:

1. Remove model turns from scheduled jobs that only execute fixed deterministic commands.
2. Reconcile the one current cron-contract drift before changing any other cron payload.
3. Repair the status-card and retrieval freshness chain so healthy wiki and durable-memory routes are not disabled by one stale finance-derived source.
4. Separate current-lane admission safety from historical lane-audit debt while preserving the full audit trail.
5. Make exact leased paths the default validation scope.
6. Collect the required ten-job comparable Harness V2 cohort before changing model routes or claiming realized efficiency.

The normal five-command validator path is already within its ten-second target. A broad validator rewrite is not justified.

## Truth and measurement limits

- Actual billed cost is not recorded. API-equivalent estimates are partial and are not invoices.
- Historical token totals identify opportunity; they do not prove future savings.
- Usage timestamps cover only 18.4337% of token events, and API-equivalent pricing covers 15.4217%.
- Implementation token attribution is incomplete: one implementation event is recorded against 597 gaps.
- Startup timing observations were single local samples and should be treated as directional.
- Route or model promotion remains blocked until ten comparable Main-accepted jobs have trusted receipts.
- Every source below must be refreshed and re-hashed before future implementation because this is a deferred plan.

## Audit baseline

### Token and scheduled-work concentration

The 2026-08-25 token-efficiency scorecard observed 830 events and 42,694,193 total tokens. Its six leading active contract-backed candidates account for 8,406,052 observed historical tokens across 190 runs:

| Rank | Job | Runs | Observed tokens | Tokens/run | Current payload posture |
|---:|---|---:|---:|---:|---|
| 1 | Runtime - OS Audit Companion Packets Refresh | 32 | 2,271,631 | 70,988.47 | Luna agentTurn; fixed commands; no pre-model gate |
| 2 | Runtime - Status Card Freshness Refresh | 77 | 1,834,068 | 23,819.06 | Luna agentTurn; one deterministic runner; no pre-model gate |
| 3 | Runtime - Future Session Packet Refresh | 26 | 1,293,130 | 49,735.77 | Command; changed-input gate already present |
| 4 | Finance - Daily Canon Drift Freshness Gate | 18 | 1,146,862 | 63,714.56 | Command; changed-input gate already present |
| 5 | Cron Reduction - Control Fail-Closed Dispatcher | 20 | 1,020,321 | 51,016.05 | Command; changed-input gate already present |
| 6 | Finance - WF87 Autonomy Command Center Refresh | 17 | 840,040 | 49,414.12 | Command; runtime prefilter candidate |

The top two deterministic agentTurn jobs alone represent 4,105,699 observed tokens across 109 runs. A script-level gate inside an already-spawned agent does not avoid the model call; the skip decision must occur before model spawn.

The PM Terra proof runner is another deterministic agentTurn candidate. Its contract runs two named scripts, and the first script already has a changed-input prefilter. Full model-token avoidance requires an approved payload conversion to a command route.

### Cron correctness and failure tax

- Current contract validator: 43 contracts, 58 live jobs, one drift, no missing live jobs, no unsupported live routes, and no prompt-integrity or prompt-bloat findings.
- Drift owner: state/cron-contracts/finance-daily-sql-canon-tier-routing-sync.json.
- Contract expectation: Luna/low. Live payload: model and thinking are null, consistent with a model-free command.
- Preferred future direction: verify and codify the intended model-free payload. Do not restore an unnecessary model call merely to make the validator green.
- The latest morning, control, and post-close digest failures spent a combined 87.604 seconds failing the same contract validator.
- Cron freshness surface: 58 jobs, 57 enabled, 25 blocked/urgent, 30 quiet successes, 13 fresh, two stale, and 16 live last-run exceptions.

Cron state remains owner-gated. Any future patch needs an exact preimage, diff, backup, rollback, validator proof, and natural-run verification.

### Validation and lane scaling

- Normal validation profile: five commands in 7.235 seconds against a ten-second target; no measured command failures.
- Unscoped changed-file routing saw 501 relevant paths and generated 230 recommendations.
- The shared validator bundle selected 228 commands, ran none, and failed preflight with required_trade_grade_producer_excluded_by_budget.
- The lane register was about 5.99 MB with more than 1,500 rows, overwhelmingly terminal history.
- The lane manager already exposes summary.open_lanes. The remaining scaling problem is that downstream parallel admission requires the entire historical register validation to be green.
- Historical route/proof debt must remain visible; it should not be deleted, rewritten, or silently downgraded.

### Startup, status, and retrieval

- Compact status-card frontdoor: 7,928 bytes. A direct cached read took about 30 ms in one local sample.
- The read-only status-card command took about 1.082 seconds; an empty Python startup took about 986 ms. This makes repeated process startup the dominant cost for shallow reads.
- One literal read of twelve startup surfaces was about 149,302 bytes, versus 10,132 bytes for the status frontdoor plus wiki index.
- Latest status-card freshness runner failed after executing one of five steps because WF84 routing metadata was stale. The emitted repair command was python scripts/workflow_routing_index.py --write --write-db --validate.
- Vector-memory index: 353 sources, 2,828 chunks, and 672 stale chunks, all attributed to one finance-derived source, tmp/finance-vector-retrieval-summary.json.
- Semantic-memory maintenance correctly classified that finance-only staleness and selected no_refresh_needed.
- status_card_packet.py currently treats the raw index error as total local-fallback unavailability.
- The compiled wiki is structurally healthy: 15 of 15 pages, page-granular mirror, matching hashes, and zero page mismatches.
- The wiki bootstrap fallback claim relies on an old benchmark while the current frontdoor reports fallback unavailable. The stale benchmark claim should expire.

This is a classification and freshness-chain problem. It is not proof that an OpenClaw runtime or plugin patch is required.

### Harness V2

The R4 protected receipt gate and Wave 2 runtime acceptance passed. Measurement acceptance is still pending: zero of ten comparable Main-accepted jobs have been collected. Wave 3 and route/model promotion remain unauthorized.

The single P0 receipt used 5,022 tokens, returned 14 output tokens, took 202,979 ms, and used no tools. It proves acceptance plumbing, not steady-state performance.

## Dependency order

| Order | Packet | Dependency |
|---:|---|---|
| 0 | WES-06 operator fast path | May be adopted immediately; no mutation |
| 1 | WES-00 evidence refresh and preflight | Required before every future execution session |
| 2 | WES-01 cron drift reconciliation | Must precede cron payload conversion |
| 3 | WES-03 freshness/retrieval repair and WES-04 lane/validator scaling | May proceed in separate leased lanes after WES-00 |
| 4 | WES-02 deterministic cron payload conversion | Requires WES-01 green and relevant runners green |
| 5 | WES-05 Harness V2 cohort measurement | Ongoing observation; no route change |

## Deferred execution packets

### WES-00 — Refresh evidence and freeze an execution snapshot

- Route state: preflight.
- Authority: model-free, review-only local proof refresh. No live cron or runtime mutation.
- Objective: eliminate stale-plan execution by regenerating referenced proofs, re-hashing exact targets, checking current pause/authority state, and leasing exact writes.
- Required owners: token-efficiency scorecard, cron predispatch plan, cron contract validator, cron freshness/control surfaces, status-card runner, semantic-memory maintenance, lane manager, validator timing ledger, and R4 acceptance.
- Contract:
  1. Run the implementation router for the selected packet.
  2. Refresh only the proof surfaces needed by that packet.
  3. Compare current hashes to this audit; classify every delta before implementation.
  4. Check workflow pause state and the lane register.
  5. Lease exact writable paths and declare phase, parent job, attempt, expected route, stop lines, and validation budget.
- Acceptance: all required JSON parses; current timestamps and hashes are recorded; no owner pause or write collision is ignored; implementation does not start on stale proof.
- Rollback: none required for read-only checks; generated proof refreshes remain non-authoritative.
- Stop line: any changed authority boundary, active collision, stale material owner, or newly red preflight returns the packet to Main for reclassification.

### WES-01 — Reconcile the SQL canon tier-routing cron contract drift

- Route state: owner_config_decision.
- Authority: Randall approval required before any live cron or scheduler mutation.
- Objective: make the contract reflect the verified intended live command route without adding a model call.
- Exact target: state/cron-contracts/finance-daily-sql-canon-tier-routing-sync.json plus its live scheduler payload only if an approved diff requires it.
- Baseline drift: payload.model expected openai/gpt-5.6-luna but actual null; payload.thinking expected low but actual null.
- Contract:
  1. Verify the live command, schedule, timezone, delivery, timeout, expected artifact, and authority boundary.
  2. Produce an exact proposal, preimage, diff hash, backup, rollback command, and post-change validator list.
  3. Prefer contract/schema alignment to the intended model-free command.
  4. Present the exact patch to Randall. Do not apply from this plan.
  5. After approval, use cron_patch_manager.py and the cron automation contract.
- Acceptance: contract drift count is zero; schedule/cadence/delivery and authority are unchanged; expected artifact remains fresh; all direct consumers are no longer blocked by this drift; at least one natural scheduled run is verified.
- Rollback: restore the captured contract and live payload preimages, rerun the contract validator, and preserve the failed attempt proof.
- Stop line: if live behavior is not unambiguously model-free, or contract/schema cannot represent it safely, stop for an owner decision.

### WES-02 — Convert deterministic agentTurn cron payloads to guarded commands

- Route state: owner_config_decision.
- Authority: Randall approval required for every exact cron payload diff.
- Objective: avoid model spawn when scheduled work is only a fixed command chain.
- Candidate contracts:
  - state/cron-contracts/runtime-os-audit-companion-packets-refresh.json
  - state/cron-contracts/runtime-status-card-freshness-refresh.json
  - state/cron-contracts/pm-auto-implementation-gpt55.json
- Contract:
  1. Handle each job as a separate patch with its own backup and rollback.
  2. Preserve schedule, timezone, expected artifacts, timeouts, quiet-delivery semantics, fail-closed behavior, and all authority stop lines.
  3. Put changed-input comparison before model spawn. For these deterministic paths, the approved target should be a command payload rather than an agentTurn wrapper.
  4. An unchanged signature must emit explicit skipped_unchanged proof and reuse only artifacts whose freshness contract permits reuse.
  5. A changed signature must run the existing deterministic path and update the successful signature only after validation passes.
- Acceptance: unchanged input performs no model turn; changed input produces semantically equivalent artifacts; failure output remains bounded; contract validator is green; manual proof and at least two natural scheduled runs pass per job.
- Measurement: report changed-input frequency, skip rate, gross/uncached tokens, elapsed time, failure rate, and retry tax. Do not claim dollar savings without billing data.
- Rollback: one-command restore of the prior payload and contract, followed by contract validation and a manual proof run.
- Stop line: no cadence reduction, model reroute, authority expansion, or job merge is bundled into the conversion.

### WES-03 — Repair the status-card, artifact-index, and retrieval freshness chain

- Route state: patch_plan.
- Authority: workspace code changes require a new scoped implementation session; no OpenClaw core/plugin/runtime change is authorized.
- Objective: make shallow status reliable and keep healthy durable-memory/wiki retrieval available while a finance-derived source is stale.
- Narrow lane A targets:
  - scripts/status_card_freshness_runner.py
  - scripts/workflow_routing_index.py
  - scripts/artifact_index.py
  - scripts/test_workflow_routing_index.py
  - scripts/test_artifact_index.py
  - add scripts/test_status_card_freshness_runner.py only if the existing tests cannot cover the runner sequence
- Narrow lane B targets:
  - scripts/status_card_packet.py
  - scripts/semantic_memory_maintenance.py
  - scripts/vector_memory_index.py only if the classifier contract requires it
  - scripts/test_status_card_packet.py
  - scripts/test_semantic_memory_maintenance.py
- Contract:
  1. Refresh or validate the workflow routing index before WF84/WF85 capsule generation.
  2. Refresh the artifact index once at the relevant batch closeout, not once per shallow read.
  3. Classify stale sources by family: a stale finance-derived source remains blocked for finance claims but does not disable healthy memory/wiki retrieval.
  4. Expire benchmark-backed fallback claims when the benchmark exceeds its freshness contract.
  5. Keep frontdoor reads cached and bounded.
- Acceptance: one positive production-equivalent run completes and validates all five of five steps; a separate negative test proves that the runner reports the exact failing step and exits fail-closed; artifact-index freshness is current; stale finance evidence remains excluded; healthy memory/wiki fallback remains available; 15/15 wiki mirror integrity remains green; focused tests and fresh independent QA pass.
- Rollback: restore each narrow lane's preimage; rebuild the prior status frontdoor; retain failing proof for diagnosis.
- Stop line: a reproduced OpenClaw-owned runtime/plugin failure is required before proposing any change outside workspace scripts.

### WES-04 — Decouple current-lane admission from historical debt and enforce exact validation scope

- Route state: patch_plan.
- Authority: workspace code changes require a new scoped implementation session. No archive or deletion is authorized.
- Objective: let current safe work proceed without concealing historical audit failures or fanning out hundreds of unrelated validators.
- Narrow lane A targets:
  - scripts/concurrent_lane_manager.py
  - scripts/parallel_lane_recommender.py
  - scripts/test_concurrent_lane_manager.py
  - scripts/test_parallel_lane_recommender.py
- Narrow lane B targets:
  - scripts/changed_file_validator_router.py
  - scripts/validator_bundle_router.py
  - scripts/test_changed_file_validator_router.py
  - scripts/test_validator_bundle_router.py
- Contract:
  1. Preserve the append-only full lane register and its historical errors.
  2. Add an explicit current-admission validation result covering active collisions, forbidden writes, lease freshness, ownership, and active-route conformance.
  3. Keep historical debt in a separate visible audit classification; never rewrite it green.
  4. Permit the parallel recommender to consume current-admission health only after tests prove every active safety failure remains fail-closed.
  5. Require exact --path inputs for scoped implementation validation. Reject unscoped shared/major fanout before command execution unless Main explicitly authorizes a broad audit.
  6. Select SQL, finance, Go, and other heavy validators only when exact paths require them.
  7. Consume canonical workflow pause state before scoring helper eligibility.
- Acceptance: a safe active lane is not blocked solely by pre-cutover terminal debt; active collisions and forbidden paths still hard-fail; all historical errors remain queryable; paused workflows are ineligible; two-file doc work does not select hundreds of commands; focused tests and independent QA pass.
- Rollback: revert the current-admission consumer switch while retaining any additive audit fields and all historical rows.
- Stop line: no compaction may delete, archive, mutate, or reinterpret historical evidence without separate owner approval.

### WES-05 — Complete the Harness V2 comparable measurement cohort

- Route state: monitor_only.
- Authority: no model-route promotion and no Wave 3 authority.
- Objective: collect ten comparable, Main-accepted jobs with trusted usage and outcome receipts.
- Contract: keep task shape, validation class, cache treatment, receipt semantics, and acceptance criteria comparable. Record gross and uncached tokens, elapsed time, retries, first-pass acceptance, escaped defects, and actual route.
- Acceptance: ten of ten jobs are comparable, trusted, and Main accepted; incident or missing-telemetry jobs receive no success credit.
- Next decision: only after the cohort is complete may Main recommend route tuning. Randall retains any authority-sensitive decision.
- Rollback: not applicable; this is observation only.

### WES-06 — Adopt the operator fast path

- Route state: operating_practice.
- Authority: safe now; no file or runtime mutation required.
- Practices:
  - Read tmp/veritas-status-card-frontdoor.json directly for shallow status.
  - Use wiki/index.md and targeted memory/wiki corpus retrieval before broad scans.
  - Batch independent reads and index lookups.
  - Reuse cached route/index/frontdoor artifacts when their freshness contract is green.
  - Prefer model-free commands for deterministic proof.
  - Freeze helper context to at most six files, 120,000 bytes, and 30,000 estimated tokens.
  - Write JSON proof by default; write Markdown only for durable human decisions such as this plan.
  - Validate only exact leased paths unless a broad audit is explicitly intended.
- Acceptance: operator responses preserve correctness and authority while avoiding unnecessary process launches, broad reads, repeated context transport, and unbounded output.
- Stop line: speed never outranks source freshness, finance authority, active collision safety, or artifact-level proof.

## Global acceptance contract

The program is complete only when:

1. WES-01 contract drift is zero.
2. Every approved WES-02 job proves no model spawn on unchanged input and equivalent deterministic output on changed input.
3. WES-03 preserves finance staleness guards while restoring truthful healthy retrieval visibility.
4. WES-04 preserves all historical evidence and active fail-closed safety while reducing unscoped validation fanout.
5. WES-05 reaches ten comparable accepted jobs before any route/model promotion.
6. Actual savings reports distinguish historical baseline, avoided work, API-equivalent estimate, and actual billed cost.
7. Every mutation has an exact approval, lease, preimage, diff, validation proof, rollback, natural-run proof where applicable, and Main acceptance.

## Immediate no-mutation recommendation

Adopt WES-06 now. At the next authorized implementation session, run WES-00 and prepare WES-01's exact cron-contract proposal first. Do not begin WES-02 until that drift is resolved and the relevant deterministic runners are green.

## Pickup contract

- Start packet: WES-00.
- First owner decision: approve or reject the exact WES-01 cron-contract/live-payload diff after it is prepared.
- Do not infer approval from this document.
- Re-run the implementation router and lane collision preflight.
- Re-hash every target and source artifact; this audit's hashes are observation anchors, not timeless preconditions.
- Use the machine contract as the execution checklist and this file as the decision narrative.
- Keep Veritas Harness V2 as the upstream model-routing authority. This plan neither authorizes Wave 3 nor replaces its cohort gate.

## Primary proof inventory

| Path | SHA-256 at audit |
|---|---|
| tmp/token-efficiency-scorecard.json | 8fe8886ca624154e9737e67688f5b23467def3f5e86d2805bc9b283a1ebb1e1a |
| tmp/cron-predispatch-efficiency-plan.json | e04ee45a468342b4cb801125df18330f771a2ba9dad59149dafa0cb4b48591bc |
| tmp/cron-contract-validator.json | 4c06f0924c015cec1a35927f0d0c7f112e2c7e36100a2a8e4db9f505e657c4f5 |
| tmp/cron-freshness-spine.json | f6a8d1702b8da0a00a64a65ab2d04f47619f4c7e389e085dd0bb59fbeb16e664 |
| tmp/validator-timing-ledger.json | 286e505c9cc95ffc4f603eb222737fa9019a35c78ae4975f57a21c2c7b55f95f |
| tmp/changed-file-validator-router.json | 7d8951952c3d8f911d689cd1a520690936ef86d624665c4801c89109717504f5 |
| tmp/validator-bundle-router.json | f5dba443d8236619b7f51d52fa8f16c90ada5a84b534787081aec053291de04a |
| tmp/veritas-status-card-frontdoor.json | 423261f9a2630bcada6eaba5f5a041c55b982e53a9fcb12e8fa270bd4777219d |
| tmp/status-card-freshness-runner.json | f18a0e2104e8c6f9af1fbd6967c82ec56c511ef76fc3bf009605943424469150 |
| tmp/vector-memory-index.json | 9fc7e9f9410a7b00d1e67e11c00e357b54c0c85733f6e5ae36629a99e22e2538 |
| tmp/semantic-memory-maintenance.json | 2f8f0fcf7eb4c6ebc624cc19303e5a4c9034b515c74717fd00dc05905473c18d |
| tmp/wiki-bootstrap-proof.json | 0ea6b38bb52391923567f8c70e1c984ed3784d6520ec5e9a3a40836d4ef6db10 |
| tmp/wave2-rebuild-r3-artifacts/producer-restoration-r4/deployment-readiness-r4/wave2-r4-post-restart-acceptance-r1.json | 7b79c8acef69d41772bba13705e3291bb8da052b3262418904c81d45aaabc29d |

These hashes preserve the audit snapshot. During independent QA, tmp/status-card-freshness-runner.json advanced to SHA-256 6ab19e8eca361ed35d86ca239442a19aecae6c8f7c6d2110a640fb53eb6d0bcf at 2026-08-25T02:02:49Z and reproduced the same wf84_capsule_refresh / routing_index_stale failure. The original audit hash remains above for provenance; WES-00 must capture a new execution snapshot before any later patch.

## Hard stop lines

- No live trading, money movement, brokerage/account action, paper execution, or inferred capital approval.
- No finance canon, portfolio cash/sizing/risk, or execution-entitlement mutation.
- No cron, scheduler, config, auth, channel, plugin, startup, service, runtime, or OpenClaw core mutation without a new exact owner approval.
- No archive, deletion, historical-ledger rewrite, or destructive cleanup.
- No Wave 3 start or model/route promotion from this audit.
- No savings claim that converts partial API-equivalent estimates into actual billed cost.
