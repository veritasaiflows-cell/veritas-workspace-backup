# Migration Review - 2026-04-29 0016 MST

## Execution status

### Completed in this pass
- created timestamped backups in `migration-backups/2026-04-29-0016/`
- added four operator skills:
  - `skills/openclaw-operator/`
  - `skills/openclaw-troubleshooter/`
  - `skills/memory-continuity-manager/`
  - `skills/cron-automation-manager/`
- condensed these core files:
  - `SOUL.md`
  - `IDENTITY.md`
  - `MEMORY.md`
  - `USER.md`
  - `TOOLS.md`
  - `AGENTS.md`
  - `Continuity Protocol.md`
  - `HEARTBEAT.md`

## Architecture now in force

### Core constitution files
- `SOUL.md`
- `IDENTITY.md`
- `MEMORY.md`
- `USER.md`
- `TOOLS.md`
- `AGENTS.md`
- `Continuity Protocol.md`
- `HEARTBEAT.md`

### Operator skills
- `skills/openclaw-operator/`
- `skills/openclaw-troubleshooter/`
- `skills/memory-continuity-manager/`
- `skills/cron-automation-manager/`

### Existing finance skills preserved as the finance spine
- `veritas-fundamental-pass`
- `veritas-technical-pass`
- `veritas-macro-pass`
- `veritas-positioning-pass`
- `veritas-investment-deck`
- `veritas-pdf-brief`
- `veritas-self-improvement`
- `workspace-governor`

## Deliberate non-actions

- kept `memory/` as the chronological daily-history layer; did not create a parallel `daily-memory/` tree
- did not delete `BOOTSTRAP.md` in the same pass; it remains a cleanup candidate
- did not delete or operationalize `CLAUDE.md`; it remains outside the active OpenClaw core constitution
- did not create generic duplicate finance skills that overlap with the existing Veritas finance stack
- kept the current OpenClaw version; no update to `2026.4.26`

## Review items still open

1. `BOOTSTRAP.md`
   - recommended next move: archive or remove after one final explicit cleanup decision
2. `CLAUDE.md`
   - recommended next move: archive or clearly label as non-core reference material
3. `06. Playbooks/Operating Model.md`
   - likely next move: trim or align to the new skills so it does not re-accumulate procedural sprawl
4. `scripts/README.md`
   - likely next move: keep as tooling reference, but split any overly long runbooks into skill references if it keeps growing

## Validation results

- core files are materially shorter:
  - `SOUL.md` 88 lines
  - `IDENTITY.md` 9 lines
  - `MEMORY.md` 44 lines
  - `USER.md` 11 lines
  - `TOOLS.md` 40 lines
  - `AGENTS.md` 75 lines
  - `Continuity Protocol.md` 67 lines
  - `HEARTBEAT.md` 18 lines
- `openclaw config validate` passed
- `openclaw skills check` passed with 20 eligible skills
- the four new operator skills loaded successfully
- bundled-skill allowlist posture remains intact
- no critical identity, mission, or safety rule was intentionally removed

## OpenClaw Update Prep - 2026-06-05 09:40 MST

Randall is about to update OpenClaw from `OpenClaw 2026.5.27 (27ae826)` on stable/pnpm. Pre-update posture:

- `openclaw status`: gateway local/reachable at `http://127.0.0.1:18789/`; gateway scheduled task installed/running; Tailscale exposure off; Telegram enabled/configured; 39 active sessions; 25 enabled cron jobs per current workspace proof.
- `openclaw config validate`: passed for `~\.openclaw\openclaw.json`.
- `openclaw skills check`: passed with 92 total, 50 eligible/visible, 49 command-available, 0 missing requirements, 0 blocked by allowlist.
- `openclaw security audit`: 0 critical, 3 warnings, 1 info. Warnings: loopback gateway has no trusted proxies configured; personal-assistant/multi-user heuristic due Telegram group allowlist and broad tools; unpinned npm plugin install records for `codex` and `diagnostics-otel`.
- `openclaw doctor`: no hard stop, but warnings exist: expired Anthropic and Gemini CLI auth, 1 explicit Anthropic session override, 57 orphan transcripts, 27 legacy `openai-codex/*` session route pins, 1 cron job with explicit model override, plaintext gateway/Telegram secret-bearing config fields, bootstrap files near size limits, memory search provider set to OpenAI without API key.
- `openclaw approvals get --json`: approvals file exists at `~\.openclaw\exec-approvals.json`; effective `tools.exec` policy is full security with ask off; hash `eb327f41aa8d5f56a94fd94b5ec022a1c08331aefa6c530c78ba78cb2d68b32a`.

Known-good workspace proof immediately before update:

- Retail/source-trust blockers closed: `automation_stack_hardening_pass.py --write --validate`, `retail_truth_routing_contract.py --write --validate`, `retail_answer_harness.py --write --validate`, `retail_automation_control_plane.py --write --validate`, `wf78_phase_runner.py --phase all-safe --write --validate`, and `veritas_harness_scorecard.py --write --validate` all validated ok.
- PM state was green; PM queue ok; no customer/external output, SQL-first promotion, Python fallback retirement, canon/portfolio mutation, paper/live/brokerage/account action, or owner approval inference.

Post-update recovery checklist:

1. Run `openclaw --version`, `openclaw status`, `openclaw doctor`, `openclaw config validate`, and `openclaw skills check`.
2. Confirm `~\.openclaw\openclaw.json`, `~\.openclaw\exec-approvals.json`, workspace `skills\`, plugin skill links, gateway scheduled task, and startup persistence survived.
3. If `openclaw skills check` reports plugin-skill symlink errors (`EPERM` / `WinError 1314`), treat it as Windows symlink privilege/Developer Mode, not as lost skill doctrine.
4. Re-run workspace proof before trusting finance/cron/retail output: `python scripts\cron_freshness_spine.py --write --validate`; `python scripts\retail_truth_routing_contract.py --write --validate`; `python scripts\retail_answer_harness.py --write --validate`; `python scripts\retail_automation_control_plane.py --write --validate`; `python scripts\wf78_phase_runner.py --phase all-safe --write --validate`; `python scripts\veritas_harness_scorecard.py --write --validate`; `python scripts\pm_program_state.py --write --write-db --validate`; `python scripts\pm_implementation_job_queue.py --write --write-db --validate`.
5. Do not run `openclaw doctor --fix`, archive orphan transcripts, rewrite legacy session pins, alter secrets, or change cron/channel/config/service state unless Randall approves the exact mutation after the update.

## OpenClaw Post-Update Validation - 2026-06-05 09:45 MST

Randall completed the update. New runtime baseline is `OpenClaw 2026.6.1 (2e08f0f)`.

Runtime and config proof:

- `openclaw --version`: `OpenClaw 2026.6.1 (2e08f0f)`.
- `openclaw status --deep`: gateway local/reachable at `http://127.0.0.1:18789/`; update up to date; gateway service scheduled task installed/running; Telegram OK; Tailscale off; 39 active sessions; memory enabled; 0 active/queued/running tasks; security audit still 0 critical / 3 warnings / 1 info.
- `openclaw config validate`: passed.
- `openclaw skills check`: passed with 92 total, 50 eligible/visible, 49 command-available, 0 missing requirements, 0 allowlist blocks.
- `openclaw doctor`: warnings only. Known warnings after update: legacy plugin install index conflict for `codex` and `diagnostics-otel`; Telegram group allowlist empty for group messages; expired Anthropic auth and soon-expiring Gemini auth; 1 explicit Anthropic session override; 57 orphan transcripts; 1 cron job with explicit model override; plaintext secret-bearing config fields; plugin install index legacy state. No `doctor --fix` action was run.
- `openclaw security audit`: 0 critical, 3 warnings, 1 info. Warnings remain trusted proxy config absent on loopback gateway, personal-assistant/multi-user heuristic, and unpinned npm plugin install records for `codex` and `diagnostics-otel`.

Workspace proof after update:

- `cron_freshness_spine.py --write --validate`: validation `ok`; spine status `warning` because 2 enabled jobs require attention; 25 enabled, 16 disabled, 23 fresh, 0 stale, 0 blocked, 0 unregistered.
- `retail_truth_routing_contract.py --write --validate`: `ok`, 8 routes, A2 live complete.
- `retail_answer_harness.py --write --validate`: `ok`, 40 checks, 9 seeded-bad cases blocked as expected.
- `retail_automation_control_plane.py --write --validate`: `ok`, review-only; 8 routes; customer-safe retail output remains blocked; SQL support mode only.
- `wf78_phase_runner.py --phase all-safe --write --validate`: `ok`, 13 steps, 0 failures.
- `veritas_harness_scorecard.py --write --validate`: `ok`, 71/71 pass, 0 warnings.
- `automation_stack_hardening_pass.py --write --validate`: `ok`, 132 checks, 0 critical, 0 warnings.
- `pm_program_state.py --write --write-db --validate`: `ok`; readiness green, average 81.2, 13 lanes, 0 blocked/gated/stale, 4 needing validation.
- `pm_implementation_job_queue.py --write --write-db --validate`: `ok`; 14 jobs, 10 ready, 0 blocked; expected warnings for collision group and owner-decision jobs.

Post-update boundaries:

- Runtime is usable, but warnings remain review items rather than silent fixes.
- No config/auth/channel/service/plugin/session cleanup mutation was performed.
- No customer/external output, SQL-first promotion, Python fallback retirement, canon/portfolio mutation, paper/live/brokerage/account action, or owner approval inference was performed.

## OpenClaw Post-Update Validation - 2026-06-16 08:46 MST

Randall updated OpenClaw to `OpenClaw 2026.6.6 (8c802aa)`. Post-update runtime baseline:

- `openclaw --version`: `OpenClaw 2026.6.6 (8c802aa)`.
- `openclaw status --deep`: gateway local/reachable at `http://127.0.0.1:18789/`; update up to date; deps ok; gateway scheduled task installed/registered/running; Tailscale exposure off; Telegram OK; event loop healthy; default model `openai/gpt-5.5`; one dashboard session remains explicitly pinned to `anthropic/claude-opus-4-6`.
- `openclaw config validate`: passed for `~\.openclaw\openclaw.json`.
- `openclaw skills check`: passed with 96 total, 54 eligible/visible, 53 command-available, 0 missing requirements, 0 allowlist blocks.
- Retrieval/runtime tools verified: Python `3.13.13`, SQLite `3.53.1`, ripgrep `15.1.0`, jq `1.8.1`, and `obsidian-cli`/`notesmd-cli` `v0.3.6`.
- Durable lane register: `concurrent_lane_manager.py --status --write --validate` reported 0 active lanes before the note-update lane was opened.

Doctor/security posture:

- `openclaw doctor`: warnings only. Current review items: Telegram group allowlist is empty for group messages; Anthropic auth expiring in about 8 hours; Gemini CLI auth expiring in under 1 hour; 10 explicit Anthropic session overrides; 22 orphan transcript files; 51 cron model overrides; legacy cron job storage normalization recommended by `doctor --fix`; plaintext secret-bearing config fields; four blocked TaskFlow records pointing at missing tasks; bootstrap injected chars at 87% of configured limit.
- `openclaw security audit`: 0 critical, 2 warnings, 1 info. Warnings remain trusted-proxies absent on loopback gateway and personal-assistant/multi-user heuristic due Telegram group allowlist plus broad local runtime tools.
- No `openclaw doctor --fix`, orphan transcript archive, auth refresh, secret migration, channel/config/service/plugin mutation, session reset, or cron normalization was performed. Those remain explicit-owner-approval items.

Workspace proof after update:

- `python scripts\future_session_enhancement_packet.py --write --write-md --validate`: status `ok`, validation `ok`.
- `python scripts\cron_control_packet.py --write --validate`: status `ok`, but escalation signal count `7`; next safe action is to inspect escalation signals and source artifacts.
- `python scripts\cron_freshness_spine.py --write --validate`: validation `ok`, status `blocked`; 51 enabled jobs, 31 fresh, 3 stale/monitor-only, 7 urgent blocked, 0 missing expected artifact contracts, 0 unregistered enabled jobs, 4 live scheduler last-run exceptions.
- Current urgent finance/workflow blockers are artifact-level review states, not an OpenClaw install failure: morning/midday paper recommendation cards, WF68 intraday alert producer, WF78 daily freshness/promotion proof, WF85 paper deployment radar, WF85 post-refresh radar, and WF87 autonomy command center refresh.
- `tmp\run-chain-post-close.json` still shows stale `running` state from `2026-06-16T06:07:15Z` at `fundamental_metrics_refresh.py`, while no Python process is active. Treat full post-close chain reliability as not clean until a recovery/repair pass resolves this stale-running artifact.

Post-update boundary:

- OpenClaw 2026.6.6 itself is installed and reachable; core config, skills, gateway, Telegram, local retrieval tools, and future-session packet generation are usable.
- Cron/finance control state is not green because review-only finance artifacts are blocked and one stale post-close chain marker remains. Do not infer capital deployment, paper/live execution, account action, or owner approval from any generated packet.

## OpenClaw Post-Update Validation - 2026-06-29 19:10 MST

Randall updated OpenClaw to `OpenClaw 2026.6.10 (aa69b12)`. Post-update runtime baseline:

- `openclaw --version`: `OpenClaw 2026.6.10 (aa69b12)`.
- `openclaw status --deep`: gateway local/reachable at `http://127.0.0.1:18789/`; update up to date; deps ok; gateway scheduled task installed/registered/running; Tailscale exposure off; Telegram OK; gateway app version `2026.6.10`; default model `openai/gpt-5.5`; two dashboard sessions remain explicitly pinned to non-default Ollama Cloud models.
- OTEL is running locally from `tools\otelcol\otelcol.exe` with config `tools\otelcol\openclaw-local-otel-runtime-metadata.yaml`; listener proof shows `127.0.0.1:4318` and `127.0.0.1:8888` owned by the collector process.
- `python scripts\otel_ops_control.py --write --write-db --multi-window --validate`: status `ok`; collector health `ok`; 24h window has 1,707+ events, 1,436+ metric batches, 271 trace batches, zero daily warnings/errors, and drift `ok`.
- `openclaw config validate`: passed for `~\.openclaw\openclaw.json`.
- `openclaw skills check`: passed with 100 total, 58 eligible/visible, 57 command-available, 0 missing requirements, 0 allowlist blocks.
- Retrieval/runtime tools verified: Python `3.13.13`, SQLite `3.53.1`, ripgrep `15.1.0`, jq `1.8.1`, and `obsidian-cli`/`notesmd-cli` `v0.3.6`.

Doctor/security posture:

- `openclaw doctor`: warnings only. Current review items: Telegram group allowlist is empty for group messages; Anthropic auth expired and Gemini CLI auth close to expiry; 12 explicit Anthropic session overrides; 154 orphan transcript files; 9 cron payloads still ask isolated agent turns to run shell/process commands and need scoped command conversion; plaintext secret-bearing config fields; four blocked TaskFlow records pointing at missing tasks; bootstrap injected chars at the configured 60,000-char ceiling with `MEMORY.md` truncated.
- `openclaw security audit --deep`: 0 critical, 2 warnings, 1 info. Warnings remain trusted-proxies absent on loopback gateway and personal-assistant/multi-user heuristic due Telegram group allowlist plus broad local runtime tools.
- No `openclaw doctor --fix`, orphan transcript archive, auth refresh, secret migration, channel/config/service/plugin mutation, session reset, cron store mutation, or cron command conversion was performed in this validation pass.

Workspace proof after update:

- `python scripts\cron_contract_validator.py --require-contracts --fail-on-drift --fail-on-prompt-bloat --write --validate`: status `ok`, 34 contracts, drift `0`, missing `0`, prompt-integrity errors `0`.
- `python scripts\cron_freshness_spine.py --write --validate`: validation `ok`, status `blocked`; 49 enabled jobs, 47 quiet-success, 0 stale, 0 missing expected artifact contracts, 2 urgent blocked jobs.
- Current urgent cron blockers are domain/workflow proof states, not an OTEL install failure: `Ops - OTEL Local Digest` and `WF74 - Learning Loop Telegram Digest`, both tracing to WF74/model-quality/finance source-open repair debt.
- WF74/status front doors were refreshed after the update. `status_card_packet.py --write --validate` now returns validation `ok` with `stale_input_warning`; PM queue top ready job is `pm-wf74-finance-source-open-quality-repair`.
- `python scripts\fast_path_qa.py --write --validate`: status `ok`, 15 checks.
- `python scripts\wf73_control_plane_audit.py --write --validate`: validation `ok`, status `warning` from bootstrap size pressure.
- `python scripts\go_binary_freshness_guard.py --write --validate`: status `ok`, stale `0`, missing `0`.
- `python scripts\go_fast_proof_validators.py --profile implementation --write --validate`: failed `0`, critical `0`, warnings classified; cron warnings reflect the two active blockers and one stale delivery-channel mismatch in `runtime-cron-efficiency-review`; SQL source-artifact hash drift remains warning residue.
- `python scripts\changed_file_validator_router.py --write --validate`: status `ok`; `python scripts\validator_bundle_router.py --write --validate`: status `ok`, selected 83, failed 0.

Post-update boundary:

- OpenClaw 2026.6.10 itself is installed and reachable; core config, skills, gateway, Telegram, local retrieval tools, and OTEL collector are usable.
- Workspace control state is not fully green because WF74/learning-loop cron blockers, finance evidence warning-router blocker, bootstrap size pressure, and doctor warning residue remain. Do not infer capital deployment, paper/live execution, account action, external/customer readiness, runtime/config authority, or owner approval from any generated packet.

## GPT-5.6 Family Transition - 2026-08-07 17:28 MST

- Current runtime baseline: OpenClaw `2026.7.1-2`; main/default model `openai/gpt-5.6-sol`; local loopback gateway reachable; OpenAI OAuth profile healthy.
- Registered `openai/gpt-5.6-terra` and `openai/gpt-5.6-luna` in the allowed model map. Added aliases `sol`, `terra`, and `luna`.
- Preserved `openai/gpt-5.5` as an allowed rollback model only. It is not the default or first fallback. Existing agent and cron assignments were intentionally unchanged pending representative-workload evaluation.
- Backup: `C:\Users\Veritas\.openclaw\backups\openclaw-pre-gpt56-family-20260807.json`; its initial SHA-256 matched the source config.
- Proof: `openclaw config validate` passed; model status resolved all three GPT-5.6 entries; OpenAI catalog listed Sol/Terra/Luna; bounded live probes returned `LUNA_OK` and `TERRA_OK` from the intended models with no fallback.
- Official model posture: Sol is frontier capability, Terra balances intelligence and cost, and Luna targets cost-sensitive high-volume work. Migration should retain the existing reasoning level as a baseline and compare one level lower on representative tasks before changing routing.
- Remaining transition work: benchmark representative Veritas workloads, assign tier routes deliberately, observe quality/latency/token behavior, then decide whether to retire GPT-5.5 rollback and revise GPT-5.4 helper/cron assignments.

### Resource-Constrained Benchmark And Fallback Update - 2026-08-07 17:39 MST

- Randall set `openai/gpt-5.5` as the first/primary fallback after Sol. `openai/gpt-5.4` remains second fallback and continues to own the six persistent bounded helper assignments as the proven tool/write baseline.
- `openclaw models status --json` confirms the saved default chain starts Sol -> GPT-5.5 -> GPT-5.4. The already-open WebChat session retained its pre-change cached fallback display even after a session-default reset; new sessions should use the saved chain, while this session requires recreation or a separately approved gateway restart for display/runtime refresh.
- Ran one identical no-tool composite workload across Sol, Terra, and Luna at `medium` and `low` reasoning: six calls total, strict JSON output, no retries, no expanded test suite.
- All six cells passed every required finance stop line, workflow-reconciliation field, model-routing field, JSON-shape requirement, and authority statement. All actual model IDs matched the requested model; fallback use was zero.
- Total measured usage: 149,667 tokens including 23,808 cached-input tokens and 6 calls. Estimated API-equivalent cost from published model rates: about $0.31; OAuth/plan accounting may differ.
- Average latency: Sol 13.58s, Terra 10.96s, Luna 10.71s. Across this small deterministic workload, low effort was not consistently faster than medium and did not improve correctness; do not apply a blanket reasoning downgrade from this result.
- Proof artifact: `tmp/gpt56-representative-benchmark-20260807.json`.
- Migration interpretation: keep Sol medium for main/final integration; use GPT-5.4 as stability fallback and control comparator; next test Terra on a read-only tool call and disposable edit/test loop, and Luna on a read-only tool call plus deterministic extraction/packet generation. Promote one route at a time only after path-specific proof.

### Sol / Terra / Luna Operational Migration - 2026-08-07 18:05 MST

- Promoted the GPT-5.6 family to active operating routes: Sol for main/final integration, Terra for serious/routine helpers, and Luna low for proven deterministic cron/status/proof agent turns. GPT-5.5 remains primary fallback; GPT-5.4 remains rollback/control.
- Migrated all six persistent GPT-5.4 helpers to Terra and regenerated their bootstrap/capability surfaces. Backup: `C:\Users\Veritas\.openclaw\backups\openclaw-pre-terra-agent-migration-20260807.json`.
- Cron posture is now 36 model-free commands, 3 main-session system events, 8 Luna agent turns, 2 Terra agent turns, and 1 opaque internal memory turn. Schedules, delivery, and timeouts were preserved.
- Luna status-card canary passed with exact quiet output, no fallback, and 25.1-second completion. Cron contracts were reconciled to drift 0/missing 0.
- Active core playbooks and routing producers were updated. Four governed skill updates were created as pending Skill Workshop proposals and were not applied.
- Durable audit: `08. Audits/GPT-5.6 Model Family Migration Audit - 2026-08-07.md`.
- Honest residue: three pre-existing bootstrap-generator structural tests remain red; current cron/PM/status surfaces still show domain/workflow attention unrelated to model installation.

## Custom 2026.7.1 Runtime Fork - Updated 2026-08-31

This section closes a real documentation gap. The first two local runtime patches were installed on
2026-08-20 and 2026-08-23/24 but were never recorded here; the third was installed on 2026-08-31.
`TOOLS.md` names this file as the authoritative migration/security review surface.

### What is installed

- The build reports `2026.7.1` while stock reports `2026.7.1-2`, at the same upstream commit
  `0790d9f593ad30c940ed93b5872a8cf6d6f3cf8c`. The version-label difference is cosmetic drift in the
  service launcher, not a different upstream base.
- Three stacked local runtime overlays ride on that base:
  1. **Semantic-memory runtime hotfix (2026-08-20).** Preserves core-memory results on the
     `corpus=all` path when the optional wiki supplement is slow, and adds per-phase partial
     diagnostics. Rollback copies:
     `C:\Users\Veritas\.openclaw\backups\semantic-memory-runtime-20260820\`; preserved chunk
     `tools-DXHLX8MK.js.active-hotfix-rollback`, SHA-256
     `46dbfcb2f063d0b635a2c10f3c965f2bbb9b34d7e5cb5cecaa57611d50c07d66`.
  2. **Protected dispatch-binding producer (R3 -> R4, 2026-08-23/24).** Emits a dispatch-time
     identity binding (`openclaw_isolated_session_store_v2`) that the stock dispatcher does not
     produce. R3 shipped without carrying the approved memory hotfix forward; R4 restored both.
  3. **Memory-only non-session visibility fast path (2026-08-31).** Before the overlay,
     `memory_search` always created a session-visibility guard and loaded the scoped session store
     before examining hits. With this gateway's `tools.sessions.visibility=all`, that guard makes a
     local `sessions.list` gateway call; the session-store loader then reads and canonicalizes the
     current agent's session entries. Ordinary durable-memory hits were returned unchanged only
     after that needless work. The overlay returns early only when no hit has `source ===
     "sessions"`; transcript hits retain the original guard and store lookup. Rollback copy:
     `C:\Users\Veritas\.openclaw\backups\semantic-memory-runtime-20260831\tools-C_UMYlhe.js.pre-non-session-fast-path`.
- Pre-overlay verification 2026-08-31: `dist\tools-C_UMYlhe.js` hashed to
  `E59BE8598DE64350692C44B73909B45258D3454C1A1D807AE8B51B3379F89FF4` (36,616 bytes), matching the
  approved R4 overlay recorded in the Harness V2 owner plan. The rollback copy matches that hash.
- Post-overlay verification 2026-08-31: the active chunk hashes to
  `F58822CE50D023BB650510F90C939792F1377B6076B03F60F3C9C307E9C6F55E` (36,921 bytes), and the
  upgrade-survival detector reports all three memory-search behavior markers present and confirms
  that the non-session early return occurs before session-visibility setup.
- Post-reload validation 2026-08-31: `node --check` passed for the active chunk,
  `openclaw config validate` passed, and the focused detector suite passed 10/10. The live main
  index is clean (`dirty=false`, 476 files / 10,278 chunks, Ollama `nomic-embed-text`, semantic
  vectors available). Two live `corpus=memory` searches returned relevant results in 1,036 ms and
  430 ms. Direct `corpus=wiki` search succeeded; `corpus=all` completed in 3,975 ms with its
  explicit, expected warning that transcript hits are still excluded from the combined route.
- Owner record:
  `06. Playbooks/Project Continuity/Veritas Harness V2 - Governance and Efficiency Upgrade Plan - 2026-08-22.md`.

### Why the fork is retained

The WAVE2 measurement cohort that motivated the dispatch-binding work was retired on 2026-08-26, but
the binding is still load-bearing: `scripts/concurrent_lane_manager.py` trusts only
`openclaw_isolated_session_store_v2` and fails closed on v1 because v1 cannot prove which
caller/attempt dispatched a lane, and `scripts/token_usage_ledger.py` treats v2 as a trusted lane
token source. Removing the fork would break isolated-lane token attribution. Only
`scripts/wave2_measurement_cohort_controller.py` is genuinely orphaned; it has not been retired.

### Known defect carried by this fork

`runMemorySearchOptionalPhase` in `dist\tools-C_UMYlhe.js` races each phase against a `setTimeout`
but never cancels the underlying work - there is no `AbortController`, unlike
`runMemorySearchToolWithDeadline` in the same chunk. The declared phase budgets are therefore
advisory. Observed on 2026-08-30: the wiki phase reported "timed out after 5s" while its own
`elapsed_ms` was 17,151, and `corpus=all` measured `toolMs=25154` against a 15s tool deadline. The
declared budgets (5s memory init + 8s memory phase + 5s wiki supplement + overhead) exceed a 15s
deadline even when healthy, and the sessions corpus is hardcoded off.

This was **not** repaired. Fixing it means editing compiled JS and deepening fork debt for a path
with a safe workaround: prefer `corpus=memory` for routine recall and reserve `corpus=all` for cases
that genuinely need wiki content.

### Related runtime change made 2026-08-30

Ollama unloads the embedding model after roughly 5 minutes idle, and a cold `nomic-embed-text` load
measured 4,055-7,295 ms, so the first `memory_search` of a session paid that against the deadline.
No OpenClaw config knob exists for this; confirmed against the full config schema (the only
`keepAlive` field belongs to WhatsApp). Fixed outside the runtime by
`scripts/embedding_keepalive_guard.py`, which pins the model with `keep_alive: -1`, scheduled hourly
as cron job `3c3b13b7-6520-464b-91ee-d5fc6f2a086c` and governed by
`state/cron-contracts/runtime-embedding-keepalive-guard.json`. Cost: roughly 323 MB VRAM pinned.
Post-change proof: contract validator `status=ok contracts=28 drift=0 missing=0`; freshness spine
28 enabled, 0 unregistered, 0 missing expected-artifact contracts.

### Honest residue

- The prior transient `memory_index_chunks_vec` warning is a vector-table race, not a current
  `memory_search` failure. The existing maintenance detector checks every agent store for a missing
  vector table or vector-row drift; the current main store is healthy.
- Locked npm residue `C:\Users\Veritas\AppData\Roaming\npm\node_modules\.openclaw-gfkeVokI` from
  2026-08-24 is still present.
- The active main memory index has grown to 10,278 chunks from the 8,724 the 2026-08-20 hotfix was
  tuned against.
- Any future OpenClaw update will overwrite all three overlays.
  `scripts/semantic_memory_maintenance.py` detects loss of both memory-search overlays by behavior
  marker and deliberately does not auto-reapply them to an unfamiliar build; the dispatch-binding
  overlay has no equivalent automatic detector.
