# Veritas Harness V2 - Governance and Efficiency Upgrade Plan

## Authorization And Scope

- **Owner decisions:** Randall approved **Wave 1** on 2026-08-22 at 08:42 MST and then approved **Wave 2 workspace-local implementation** on 2026-08-22.
- **Wave 1 objective:** restore workspace-local operating truth for cron contracts, workflow routing, and lane-register metadata integrity.
- **Historical Wave 2 objective:** first prove one trustworthy `job -> dispatch -> provider run -> usage receipt -> validator -> Main acceptance` record, then collect comparable jobs. Randall later retired the fixed cohort; the retirement section below owns current truth.
- **Waves 3-5:** durable queued proposals only. They remain unauthorized.
- **Wave 2 activation boundary:** source repair, tests, no-install packaging, rollback preparation, and continuity are authorized. Installing the candidate into the active package, restarting the gateway/service, or changing runtime/config/auth still requires a separate exact owner approval after candidate QA.
- **Hard stop lines:** no schedule, config, auth, credential, channel, finance, portfolio/canon, deletion, archive, external, or skill-application change. Generated proof does not grant any of those authorities.

## Baseline Assessment

Overall grade at authorization: **B** - approximately **B+ for governance/guardrails and C+ for operational cleanliness**.

The workspace generally fails closed and is difficult to mutate accidentally. The material weakness is efficiency proof: stale control surfaces, blocked cron jobs, incomplete run/token attribution, and insufficient comparable Main-accepted outcome cohorts. Risk governance is stronger than speed, cost, and route-quality measurement.

The Graphify/vector repair is a healthy baseline, not a V2 blocker: 341 vector sources, 2,764 chunks, zero stale chunks; 411 graph nodes, 482 edges; and 5/5 vector-to-Graphify bridge tests. Proof: `tmp/graphify-vector-integration-validation-20260821.json`.

## V2 Learning Policy

Continuously evaluate internal gaps. Create or update a skill only after repeated evidence shows that the existing route or skill cannot absorb the lesson. Skill changes remain review-only Skill Workshop proposals until Randall explicitly applies or rejects them.

Hermes and DeepSeek are research/evaluation inputs, not installation or runtime-migration targets. The transferable execution pattern is:

```text
task
-> frozen evidence/context
-> minimal route and capabilities
-> candidate work
-> deterministic verifier
-> Main acceptance
-> attributed outcome
-> friction cluster
-> review-only skill/routing proposal
```

No automatic skill application, route/model promotion, runtime migration, or self-modification is authorized.

## Execution Waves

### Wave 1 - Restore Operating Truth - Approved

1. **WF76 cron truth:** add and validate the missing expected-artifact/freshness contract for `Runtime - Semantic Memory Cache Maintenance`; classify remaining defects without changing scheduler state.
2. **WF73 routing truth:** refresh and validate the workflow routing JSON/SQLite index and prove WF71, WF74, and WF88 lookups fail closed only when genuinely stale.
3. **WF73 lane metadata truth:** classify unverifiable historical metadata without rewriting history, accept truthful historical terminal proof where `completed_at_utc` exists, and keep future identity omissions fail-closed.
4. **Main integration:** fresh independent read-only QA, continuity updates, and readiness/PM/control-surface refresh.

Wave 1 acceptance requires deterministic validators, Main review, zero active Wave 1 leases at closeout, and explicit reporting of any remaining warnings or telemetry limits.

### Wave 2 - Make Efficiency Measurable - Historical Plan; Cohort Retired

Wave 2 is deliberately recut around a single end-to-end acceptance gate. More scorecards or historical backfill do not count as progress until one newly dispatched implementation job produces a complete trusted record.

1. Activate one protected native one-shot implementation route only after exact owner approval of the verified package and gateway restart.
2. Prove one real terminal receipt containing job/lane identity, phase, attempt/retry, route/model, provider run identity, token/cache counters when exposed, latency, validator result, and Main acceptance.
3. If the first real receipt fails, stop and repair the producer; do not build another downstream scorecard.
4. Historical plan: after the first receipt, join OTEL, token, lane, validator, and outcome records. The later retirement decision removed the fixed job-count requirement.
5. Automatic route/model promotion remains disabled. Review efficiency on demand from trustworthy usage, elapsed time, retries, validation, acceptance, and defect evidence; make no token/dollar savings claim when attribution is unavailable.

### Wave 3 - Bounded Efficiency Pilots - Not Authorized

- Add deterministic changed-input prefilters to OS Audit Companion Packets, Status Card Freshness, and Future Session Packet.
- Test minimal route-specific tool/skill bundles.
- Run only a separately approved, value-defined non-finance pilot across existing routes; no fixed cohort minimum is required.
- Measure calls, turns, uncached/gross tokens, elapsed time, retry tax, validator results, and escaped defects.

### Wave 4 - Close WF74/WF88 Learning - Not Authorized

- Resolve 123 planning-follow-through gaps and two overdue high-priority improvements.
- Refresh WF88's ten stale inputs.
- Complete outcome linkage: zero stable linked RSI closures and 40 missing linkage/metric items at the baseline assessment.
- Collect results for the existing 100-fixture/300-assignment frontier evaluation.
- Convert only repeated, proven friction into review-only Skill Workshop proposals.

### Wave 5 - Cleanup - Not Authorized

- Refresh the exact cleanup packets before any decision.
- Keep the 19 `tmp` candidates, three DB archive candidates, cron cleanup, and script cleanup in separate approval packets.
- No script is deletion-ready at the baseline assessment; ten route-contraction files were already narrowed.
- Nothing may be moved, archived, or deleted without exact owner approval, reference proof, rollback, and validation.

## Required Workflow Order

1. **WF73** - routing, index, and boot truth.
2. **WF76 / cron control** - scheduler and artifact-contract health.
3. **WF71** - skill ownership and minimal capability exposure.
4. **WF74** - friction, evaluations, outcomes, and proposals.
5. **WF88** - OS2 integration, cleanup, decision compiler, and maturity gates.
6. **WF55** - later-outcome evidence.
7. Keep **WF67/WF78/WF84/WF85** isolated as finance guardrails, not V2 experimentation surfaces.

## Wave 1 Closeout Truth

- Semantic-memory cron contract: added and validated with zero drift and zero missing required fields. The job now classifies `fresh` / `quiet_success`; no schedule or job payload was changed. Proof: `state/cron-contracts/runtime-semantic-memory-cache-maintenance.json`, `tmp/cron-contract-validator-wave1-semantic-memory.json`, `tmp/cron-freshness-spine.json`.
- Remaining cron truth: 17 blocked/urgent jobs remain - seven repeated scheduler-failure cases and ten blocked-artifact/authority cases. Wave 1 classifies them; it does not claim to repair them.
- Workflow routing: 43 routes, zero critical findings, zero warnings, SQLite integrity clean; WF71, WF74, and WF88 lookups are restored. Proof: `tmp/workflow-routing-index-validation.json`.
- Lane register: zero validation errors and one intentional warning inventory covering 14 pre-Wave-1 terminal model-lane identity gaps. Those fields were not invented or backfilled. The single historical missing `ended_at_utc` is accepted from its valid `completed_at_utc`; future model-driven gaps remain critical. Proof: `tmp/concurrent-lane-register.json`.
- Route-efficiency credit: blocked for Main-executed Wave 1 lanes because provider counters are not job-scoped in the current session. Deterministic success is not counted as token/cost route evidence.
- Independent QA: the first read-only review rejected two fail-open boundaries. One bounded repair made active/unclassifiable model identity gaps critical and limited the non-complete `completed_at_utc` fallback to provably pre-cutoff rows. Focused and adjacent regression suites then passed; a fresh read-only reviewer returned PASS against source SHA-256 `fefaf100ece7cc4c8785150a75529566b81ff83997cf8751b29b33ddc48b6411`.
- Refreshed harness readiness remains review-only with 3 passes, 4 warnings, and zero failures. Refreshed PM validation is `ok`, while PM readiness remains yellow: 3 blocked, 1 stale, 3 needing validation, and 11 ready/complete across 18 lanes. These residual warnings are visible and were not widened into Wave 1 repair scope.

## Wave 2 Candidate Truth

- Root cause: downstream ledgers and validators existed, but the installed dispatcher did not emit a protected dispatch-time identity binding. Closeout enforcement could reject missing attribution but could not reconstruct counters that were never bound upstream.
- Historical first attempt: the original no-install candidate failed fresh independent QA on `raw_protected_task_identity_rehydration_bypass`. Its repair lane expired without accepted work, and Randall-approved cleanup removed that attempt's source/staging/candidate/rollback artifacts. `tmp/wave2-closeout-summary-20260823.json` remains the truthful closeout record for that attempt; it is not the current Wave 2 state.
- Current R3 rebuild: upstream commit `0790d9f593ad30c940ed93b5872a8cf6d6f3cf8c` was re-fetched and repaired. The accepted implementation canonicalizes or quarantines protected/malformed identities across hydration, persistence/cache, fallback successor construction, and session/thread routing.
- Fresh focused receipts passed: registry **99/99** and SQLite **10/10**. Fresh independent QA returned **PASS** in `tmp/wave2-rebuild-r3-artifacts/phase-j-independent-qa-result-r1.json`.
- Exact accepted no-install candidate: `tmp/wave2-rebuild-r3-artifacts/phase-i-fallback-fix/openclaw-2026.7.1.tgz`; 19,888,219 bytes; SHA-256 `c7ae764e27ecd5a54f2286f1b5bf3d85adb49b48d900deaac7484540862fd40a`.
- Version lineage is resolved but non-monotonic: the active runtime is `2026.7.1-2`, while the accepted candidate and its `@openclaw/ai` dependency identify as `2026.7.1`. Both root packages identify the same exact commit. The compared AI packages have 64 files each and identical code; only `package.json` and `npm-shrinkwrap.json` differ. Installing the accepted hash will therefore show the lower label even though it contains the newer accepted R3 patch. Repacking under a newer label would create a new candidate and require a new QA cycle.
- The accepted candidate contains the upstream memory-search bundle SHA-256 `43c9d3c83d1df72a73d3f31653b2f29c1deafd43a83fa5425839e049e63680be`; it does not contain the already-approved semantic-memory runtime repair. The current approved hotfix was preserved as `tmp/wave2-rebuild-r3-artifacts/deployment-readiness-r1/tools-DXHLX8MK.js.active-hotfix-rollback`, 36,616 bytes, SHA-256 `46dbfcb2f063d0b635a2c10f3c965f2bbb9b34d7e5cb5cecaa57611d50c07d66`. Any approved install must restore this exact overlay before restart.
- Current rollback proof now exists: root `2026.7.1-2` tarball SHA-256 `5bb525f36f471a41239615d321c441778c7e1c007018ed6d84b795be77803276`, paired AI tarball SHA-256 `72b985dc4501a720e3e626adfff83f24062d7c936e674a9c11fbbf583db58746`, plus the hotfix overlay above. The registry root matches 8,549 of 8,550 active non-`node_modules` package files; the overlay restores the sole deliberate difference. Candidate+overlay and rollback+overlay both passed isolated-prefix layout/version/hash smokes with lifecycle scripts explicitly disabled.
- Exact install, preservation, conditional rollback, and stop-line details are in `tmp/wave2-rebuild-r3-artifacts/deployment-readiness-r1/wave2-r3-install-rollback-decision-card-r1.json`.
- At that pre-install candidate checkpoint, the live OpenClaw package, gateway/service, config, and live state database remained unchanged. The first real complete receipt was still **not produced**, and the comparable cohort remained **0/10**.
- Historical packaging/path incidents and non-credit test timeouts remain recorded and receive no first-pass or route-efficiency credit. Actual OAuth billing remains unavailable; API-equivalent estimates must not be presented as actual subscription savings.

## Wave 2 R3 Acceptance - 2026-08-23

Status: **historical R3 checkpoint: code and independent QA accepted; exact candidate installed and pre-restart verified; Randall later completed the restart, which exposed the producer gap superseded by R4.**

- The original failed candidate and cleanup remain preserved as historical truth, but they no longer define the current Wave 2 state.
- Randall supplied the exact install-only approval. The accepted candidate SHA-256 `c7ae764e27ecd5a54f2286f1b5bf3d85adb49b48d900deaac7484540862fd40a` was installed globally with lifecycle scripts disabled. The installed CLI/root/AI identity is `2026.7.1` / commit `0790d9f`, and the two compiled subagent-registry bundles match the accepted candidate extraction.
- The approved memory-search overlay SHA-256 `46dbfcb2f063d0b635a2c10f3c965f2bbb9b34d7e5cb5cecaa57611d50c07d66` was restored; both required markers and JavaScript syntax passed. All actual pre-restart version/hash checks passed, so rollback was not invoked. The gateway/app-server process identities remained unchanged and no OpenClaw process was restarted. Install receipt: `tmp/wave2-rebuild-r3-artifacts/deployment-readiness-r1/wave2-r3-install-receipt-r1.json`.
- npm preserved one locked replacement-directory residue at `C:\Users\Veritas\AppData\Roaming\npm\node_modules\.openclaw-gfkeVokI` because the still-running process holds `vec0.dll`. Main did not attempt cleanup; it is not evidence of install failure and remains outside this install-only scope.
- At this historical R3 checkpoint, Wave 2 measurement was incomplete and no route-efficiency credit was claimed. The later R4/P0 acceptance and cohort-retirement sections supersede this checkpoint.

## Wave 2 R4 Acceptance - 2026-08-24

Status: **R4 engineering and post-restart P0 runtime acceptance passed; Randall later retired the comparable measurement cohort.**

- The R3 restart passed reachability/configuration/guard checks but exposed a release-blocking gap: R3 omitted the protected dispatch-binding producer and expected the wrong raw protected-ID shape. No protected canary was dispatched and no receipt/cohort credit was claimed.
- R4 restores the producer and corrected identity contract. Candidate SHA-256 `ce78658b60e8e2fafc078046138e286c8977b62b12a13862075bc3ae01051381` passed 118/118 focused tests, source typecheck, seven architecture gates, build/UI/package/extraction proof, and independent engineering QA with zero findings.
- Randall explicitly accepted the independent QA result from actual `openai/gpt-5.6-sol`/ultra despite the expected Terra/low mismatch. Route conformance and all route/efficiency/receipt/cohort credit remain zero.
- Randall then approved exact install-only. R4 was installed globally with lifecycle scripts disabled. The installed CLI/root/AI identity is `2026.7.1` / commit `0790d9f`; protected producer SHA-256 is `2bf2111202fbc5ca01478e8c7e822ae28b7a4f843efb01de9c18708d76276410`, and identity-state SHA-256 is `968e60c3d70d5344aa6154dcc0c0f54304351751b7ca69d0d0645cb96c73679e`.
- Installed memory baseline SHA-256 `acfa7639a357f0cf31b37d379edf1907ccb43b69c9e1e656fc816328f74f26f0` matched before applying overlay SHA-256 `e59be8598de64350692c44b73909b45258d3454c1a1d807ae8b51b3379f89ff4`; marker and syntax checks passed. Rollback was not invoked.
- Gateway PID `29844` remained stable. No restart, signal, service control, config mutation, canary, cleanup, or Wave 3 action occurred. Install receipt: `tmp/wave2-rebuild-r3-artifacts/producer-restoration-r4/deployment-readiness-r4/wave2-r4-install-receipt-r1.json`.
- npm again preserved locked residue at `C:\Users\Veritas\AppData\Roaming\npm\node_modules\.openclaw-gfkeVokI` because the running process holds `vec0.dll`. It was not cleaned within install-only authority.
- Randall's manual restart activated R4. The first post-restart canary transport attempt failed before dispatch because `sandbox=require` rejected a supplied `cwd` override; it produced no child run, binding, receipt, or credit and is terminal/blocked.
- Randall then authorized exactly one corrected P0 attempt. The corrected canary omitted `cwd`, ran through the conforming `persistent_isolated_agent` / `openai/gpt-5.6-terra` / low route, returned the exact `WAVE2_R4_PROTECTED_CANARY_OK` marker, and made zero tool calls.
- The protected core ledger contains one reservation, one accepted event, and one `terminal:ok` event. Trusted receipt `79880a8400a983133eece26645a75d098a7901d9c5236536ab7ca8e1e5402d69` reconciles 5,008 input, 0 cached input, 0 cache write, 14 output, and 5,022 total tokens over 202,979 ms. The source cost `$0.01273` is an OpenClaw estimate, not an invoice or OAuth billing claim.
- P0 proof is `tmp/wave2-rebuild-r3-artifacts/producer-restoration-r4/deployment-readiness-r4/wave2-r4-post-restart-acceptance-r1.json`. P0 and Wave 2 runtime acceptance passed. Randall later retired the comparable measurement cohort; the retirement section below supersedes the former count-based gate. Wave 3 remains unauthorized.

## Next Decision Gate

Wave 1 is complete and closed. Wave 2 R4 is installed, restart-activated, and P0 runtime-accepted with one complete protected receipt. The former comparable measurement cohort is retired and must not resume. Any future measurement work requires a separately approved, production-relevant pilot with an explicit user-value outcome. No route/model promotion or Wave 3 action is authorized.

## Wave 2 Measurement Cohort Retirement - 2026-08-26

Status: **retired as active work by Randall; evidence preserved, no deletion or rollback.**

- The ten-job measurement cohort produced one valid Job 1 credit, then repeated pre-provider Job 2 control-plane failures. The second restart passed frozen-artifact, worktree, binding, and route checks but failed controller admission with `artifact_reference_invalid`; no provider work, source write, usage receipt, cohort credit, or Wave 3 action followed.
- This retirement applies to the comparable measurement cohort only. It does not reverse R4 installation, the protected P0 runtime acceptance, or any preserved historical artifact. It does not authorize a runtime/config/auth change, another WAVE2 repair, or a Wave 3 promotion.
- The control override now prohibits resuming this cohort. A future effort must be a separately approved, production-relevant pilot with an explicit user-value outcome and one-task acceptance criterion.

### Lessons adopted for future improvements

1. Require a direct value target before launching a multi-job measurement program; instrumentation alone is not sufficient payoff.
2. Require one exact, end-to-end no-provider admission preflight from binding through controller before an owner-approved dispatch attempt.
3. Treat a repeated control-plane failure as a disposition point, not an invitation to keep rebuilding the harness.
4. Reuse the proven isolated-agent transport/P0 evidence only in a small, value-defined pilot; do not revive the retired cohort to obtain benchmark count.

Next safe action: leave WAVE2 inactive and use these constraints when Randall later selects a concrete production-relevant pilot.
