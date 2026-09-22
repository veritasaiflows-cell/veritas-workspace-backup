# Workflow 89 - Isolated Agent Specialization and Efficiency Contract

## Objective

Make the six-specialist isolated-agent fleet actually dispatchable, measurably efficient, and genuinely specialized — without widening authority. The governance layer is already ahead of external practice; the failure is activation energy and absent telemetry, not missing controls.

Status: supplementary historical review. Current governed WF89 state and the sole execution queue live in `Workflow 89 - Isolated Agent Specialization and Fleet Efficiency Contract.md` following Randall's 2026-09-09 21:29 MST direction. This note grants no config, dispatch, capital, or execution authority. Its original present-tense findings require live revalidation. <!-- project: github.com/veritasaiflows-cell/veritas-workspace-backup -->

## Review Basis

Read 2026-09-09 from live evidence, not from prior claims:

- Live `agents.entries.*` in `~/.openclaw/openclaw.json` (9 entries: main, 6 specialists, 2 oxalpha eval lanes).
- `data/state-history/coding-outcome-ledger.jsonl` (1,433 rows carrying `coding_outcome`).
- `data/state-history/model-run-ledger.jsonl` (latest rollup: 1,671 rows).
- `tmp/fleet-alignment-20260905/production-readiness-20260906/*transport-proof.json` (6 agents).
- `scripts/agent_fleet_policy.py`, `skills/veritas-isolated-agent-contract`, `skills/veritas-model-routing-helper-lanes`.
- `06. Playbooks/Project Continuity/Agent Fleet Alignment - 2026-09-05.md`.
- External practice scan (2025-2026): Anthropic engineering, Cognition, Cursor, Amp, Codex/Claude Code docs, MAST (Berkeley, NeurIPS 2025).

## Findings

### F1 - The fleet is dormant and currently un-dispatchable (highest severity)

Of 1,433 recorded coding lanes, `actual_execution_backend` was `persistent_isolated_agent` **9 times (0.6%)**. All 9 were in August 2026, all on `openai/gpt-5.6-terra`. September 2026 recorded **zero** isolated dispatches. `main` took 83, `model_free_command` 60, and 1,279 rows (89%) recorded no backend at all.

Four of six specialists — Opportunity Intelligence/Grok, Engineering QA/GLM, Engineering Builder/Muse, Knowledge and Continuity/Luna — have **no recorded production dispatch** in the coding ledger.

All six fleet transport proofs carry `expires_at_utc: 2026-09-08T03:37:48Z`. The most recent builder proof expired `2026-09-09T14:25:00Z`. At review time (`2026-09-10T04:16Z`) **every proof in the workspace is expired, for every agent**. Under the fleet's own 24-hour attachment-proof rule, no specialist can be dispatched without a fresh canary first. The 2026-09-06 production declaration was explicitly a 24-hour bounded window, and it lapsed without renewal.

This is the core problem. Every other finding is downstream of it.

### F2 - Zero cost and token telemetry; the efficiency policy is unmeasurable

`token_usage` records `token_attributed: false` with `token_attribution_source: "not_exposed_by_runtime"`. The model-run rollup reports `model_attribution_coverage: 0.0`, `cost_rows: 0`, `token_rows: 0`, and `model_attribution_recent_coverage: 0.0` over a 30-day window. `provider_usage_unavailable` appears 820 times.

`veritas-model-routing-helper-lanes` defines efficiency as uncached input tokens per accepted job, gross replay tokens, first-pass acceptance, retry tax, and escaped defects. **None of these are currently computable.** Route policy is therefore asserted, not evidenced — and honestly so, since the skill already disables automatic promotion.

### F3 - Specialization is model + one prose line, nothing else

All six specialists carry `skills: []`. Per OpenClaw's config contract an empty list means *no skills*, so each specialist runs with zero procedural knowledge and must be hand-carried by Main on every dispatch.

Four of six (research-scout, qa-redteam, finance-source-scout, finance-redteam) share an **identical** tool allowlist: `read, web_search, web_fetch`. Their only differentiators are the primary model and a one-sentence `identity.theme`. Two of them (qa-redteam, finance-redteam) even share the same model, GLM 5.3.

Worse, `read` is close to useless for them: each has a separate workspace, bootstraps set `host_path_direct_reads_allowed=false`, `memory_search` is not in any allowlist, and neither `wiki/**` nor `state/wiki-retrieval` is reachable. Everything must arrive as attachments inside the ≤6 files / 120,000 bytes / 30,000 token frozen budget. That budget-building is the activation energy behind F1.

### F4 - Context-economy knobs available in OpenClaw are entirely unset for specialists

Set on specialists today: `name, workspace, agentDir, model, models, identity, skills, tools` (plus `sandbox` on the builder).

Never set on any specialist, though OpenClaw supports per-agent overrides for all of them:

| Knob | Current effective value | Consequence |
|---|---|---|
| `contextInjection` | `"always"` (only `main` sets `continuation-skip`) | 34–43 KB of bootstrap re-injected on **every** turn |
| `bootstrapMaxChars` / `bootstrapTotalMaxChars` | global 80,000 | a web scout gets the same budget as the builder |
| `thinkingDefault` | global `"high"` | high-effort reasoning on extraction and scouting lanes |
| `params.cacheRetention` | unset | no prompt caching anywhere in the fleet |
| `timeoutSeconds` | unset (600 s default) | observed lanes ran 106, 99, 67, 56, 52, 52 minutes |
| `utilityModel` | unset | title/narration work falls to primaries |
| `contextLimits`, `skillsLimits` | unset | no per-role prompt budget |

The routing skill states thinking is "an explicit route field, not a blanket default" — the live config contradicts it fleet-wide.

### F5 - Two proofs report `status: ok` despite failed byte verification

`finance-source-scout` and `research-scout` transport proofs both carry `evidence.byte_count_match: false` (scout reports `reported_bytes: -1`) while the envelope still says `status: "ok"` and `attachment_context_transport: true`.

The isolated-agent contract requires rejecting false-capability proof. The proof generator is not enforcing its own predicate. This is a validation hole, not a cosmetic one: a proof that says ok on a failed byte match cannot gate anything.

### F6 - A second writer runs unsandboxed

`implementation-builder` is properly contained: Docker, `readOnlyRoot`, `network: none`, `capDrop: ALL`, `user: 65534`, 512 MB, 1 CPU, 64 PIDs, `workspaceAccess: none`, explicit read-only role binds plus one `rw` scoped-worktree mount. This is good and matches external best practice.

`docs-continuity-editor` holds `write, edit, apply_patch` with **no `sandbox` block at all**. Its only containment is workspace separation — which the isolated-agent contract itself warns is "not a sandbox." It is a second concurrent writer, which is precisely the pattern Cognition and Cursor identify as the main multi-agent failure source.

### F7 - Policy module has drifted from live config

`scripts/agent_fleet_policy.py` declares `MAIN_PRIMARY = "openai/gpt-6-astra"` and `MAIN_FALLBACKS = ["openai/gpt-5.6-sol"]`. Live config sets `main.model.primary = "openai/gpt-5.6-sol"` with six fallbacks including grok, glm, kimi, and opus-5. `validate_policy_maps()` only checks specialist maps, so this drift passes validation silently.

### F8 - Stale evaluation lanes

`oxalpha-lab` and `oxalpha-functional-lab` (OpenRouter stealth-model evaluation) retain leftover synthetic artifacts and `__pycache__`, and lack `BOOTSTRAP.md` and `agent.capabilities.json`. `oxalpha-functional-lab` holds `workspaceAccess: "rw"` plus `write, edit, apply_patch, exec`. If the evaluation is finished, these are standing write-capable agents with no current purpose.

## External Practice Comparison

Where Veritas is **ahead** of published practice:

- Frozen, hash-pinned handoffs with contract hashes and snapshot IDs. No public harness documents anything this rigorous.
- `patch_draft` as the default return mode. Cognition's 2026 conclusion — "multi-agent systems work best today when writes stay single-threaded and the additional agents contribute intelligence rather than actions" — is already Veritas doctrine.
- Reviewer-cannot-be-author enforcement, matching Devin Review's finding that cross-context review catches ~2 bugs/PR (~58% severe) and works best when coder and reviewer share no context.
- Builder sandbox posture matches Anthropic's stated requirement that filesystem *and* network isolation are both mandatory.

Where Veritas is **behind**:

- **Return-size discipline.** Anthropic targets a subagent burning tens of thousands of tokens but returning **1,000–2,000**. Claude Code caps tool responses at **25,000 tokens**. Veritas bounds the *inbound* handoff rigorously and the *outbound* return not at all.
- **Effort scaling.** Anthropic's orchestrator prompt encodes explicit rules (simple = 1 agent / 3–10 calls; comparison = 2–4 agents; complex = 10+) after an early version spawned 50 subagents for one query. Veritas has thinking tiers but no agent-count or tool-call budget by task class.
- **Artifact-reference returns.** The consensus fix for the "game of telephone" is to have subagents write artifacts and return references. Veritas returns full drafts through the transport.
- **Caching.** Unused. Anthropic notes extended thinking's default `clear_thinking` causes cache misses unless `keep: "all"`.
- **Cost attribution.** Cursor measured workers carrying ≥69% of tokens while the frontier planner drove ~2/3 of dollar cost — a conclusion only reachable with working telemetry (F2).

Dissent worth respecting: Cognition's *Don't Build Multi-Agents* still holds for parallel-writer swarms, and MAST (200 traces, 7 frameworks) attributes ~59% of multi-agent failures to specification and coordination rather than model capability — with ChatDev at 33.33% correctness and prompt/topology fixes yielding only +15.6%. The lesson is that structure, not prompting, is the lever. Veritas's read-mostly + single-writer shape is the correct one; it just is not running.

## Recommendations

Ordered by evidence strength, not ambition.

### R1 - Fix measurement before tuning anything (prerequisite)

Nothing in R2–R6 can be validated while F2 stands. Establish, in priority order:

1. A cheap, deterministic **dispatch record** written by Main at every isolated dispatch — agent, expected/actual model, thinking, handoff bytes, wall-clock, return bytes, outcome, retry count. Wall-clock and byte counts are observable today even when provider token usage is not.
2. Honest separation of `provider_usage_unavailable` from *never instrumented*. 89% of lanes recording no backend is an instrumentation gap, not an unavailability finding.
3. A per-agent scorecard keyed on: dispatches attempted, dispatches completed, first-pass acceptance, median wall-clock, median handoff bytes, median return bytes.

Accept that OAuth-routed models may never expose tokens. Wall-clock, byte, retry, and acceptance metrics do not require provider cooperation and are sufficient for route decisions.

### R2 - Collapse the canary tax (directly addresses F1)

The 24-hour attachment-proof expiry means any dispatch after a one-day gap starts with six canaries. In practice that cost has stopped dispatch entirely.

Proposed, for Randall's decision:

- Make canary renewal a **single batched command** producing all six proofs in one pass, rather than per-agent ad hoc work.
- Consider a **just-in-time single-agent canary**: prove only the agent about to be dispatched, at dispatch time, instead of maintaining fleet-wide readiness.
- Consider extending attachment-proof validity to **72 hours** for read-only lanes while holding write lanes at the current 7-day scoped-writeback rule with its existing preflight gate. Read-only lanes cannot corrupt state, so proof staleness carries materially less risk than for the builder.
- Retire the standing "fleet is production-ready" declaration in favour of per-dispatch readiness. A 24-hour fleet-wide declaration is guaranteed to be false most of the time.

This is the single highest-leverage change. It requires an explicit decision because it touches a governance threshold.

### R3 - Specialize by capability, not just by model (addresses F3)

- Assign each specialist a **narrow skill allowlist** instead of `skills: []`. Candidates: finance-source-scout → `veritas-fundamental-pass`, `sec`; finance-redteam → `veritas-response-contract`; qa-redteam → `workspace-qa-pass`; docs-continuity-editor → `project-continuity-manager`, `memory-continuity-manager`; research-scout → `veritas-intelligence-effort-router`. This is the cheapest specialization available and directly reduces per-dispatch hand-carrying.
- **Split the duplicated GLM challenger role.** qa-redteam and finance-redteam share GLM 5.3 and both have recorded GLM rate-limit failures. Amp's principle — the role stays stable while the model changes — argues for decorrelating these two reviewers onto different vendors so a single provider outage or rate limit cannot take out both challenge lanes.
- **Add an outbound return budget.** Adopt Anthropic's 1,000–2,000 token distillation target for scouts and a hard cap (25,000 tokens is the shipped precedent) for all lanes. Specify return *shape* per role, not just inbound payload.
- **Prefer artifact references over inline drafts** where the builder's scoped worktree already provides a written surface.

### R4 - Set the per-agent context knobs (addresses F4)

Config change; requires approval. Proposed profile:

- `contextInjection: "continuation-skip"` on all six specialists.
- Per-agent `bootstrapTotalMaxChars` sized to role — scouts materially lower than the builder.
- Per-agent `thinkingDefault` replacing the fleet-wide `"high"`: low for scouts and extraction, medium for QA and bounded implementation, high reserved for cross-contract challenge. This makes the config match the routing skill it already claims to follow.
- `params: { cacheRetention: "long" }` evaluated for the repeat-dispatch lanes.
- Per-agent `timeoutSeconds` reflecting real lane shape, given observed 52–106 minute runs.

Expected effect is lower cost per dispatch and faster scout turnaround. Treat that as a hypothesis to be measured under R1, not a claimed result.

### R5 - Close the governance gaps (addresses F5, F6)

- Fix the proof generator so `byte_count_match: false` cannot coexist with `status: "ok"`. Re-canary the two agents whose current proofs carry the inconsistency.
- Decide `docs-continuity-editor`'s containment: either give it a Docker sandbox mirroring the builder's posture, or downgrade it to `patch_draft` return with writes applied by Main. The second is cheaper and matches the single-writer principle.
- Reconcile `agent_fleet_policy.py` main-model constants with live config, and extend `validate_policy_maps()` to cover the main entry so this drift cannot recur silently.

### R6 - Decide the oxalpha lanes (addresses F8)

Confirm whether the OpenRouter stealth evaluation is complete. If it is, archive both agents and their residue. A write-capable `rw` agent with no active purpose is standing exposure for no benefit.

## Preparing For Stronger Models

External evidence points one direction and one caution.

Direction: Anthropic states plainly that "smarter models require less prescriptive engineering" and that agentic design trends toward "progressively less human curation." Amp's contract — roles stay stable while models change — is the durable abstraction. Veritas's role-bound design already has this property; the fleet policy maps roles to models in one module, so a model upgrade is a data change.

Caution: model upgrades do **not** preserve prompt behaviour. Cursor had to drop GPT-5.6 Sol from a benchmark because it proved "more sensitive to literal and emphasized wording" and produced "runaway spirals unlike anything the other models produced." Tuning did not transfer.

The implication for this contract: as models improve, **loosen scope and reduce hand-holding, but do not reduce the validation budget until it has been re-measured on the new model**. Cognition's failed "Smart Friend" experiment adds the corollary that escalation only works when the primary is strong enough to know what to ask — so treat multi-model routing as a *capability router* (this model reviews better, that one writes tests better) rather than a difficulty escalator.

Concretely, keep model identity out of skills and prompts, keep it in `agent_fleet_policy.py`, and keep expected/actual model equality enforced at dispatch so an upgrade cannot pass silently.

## Sequencing

1. **R1** — measurement. Blocks meaningful evaluation of everything else.
2. **R5** — proof-predicate fix and second-writer decision. Governance correctness, low cost, no dependency.
3. **R2** — canary tax decision. Randall's call; unblocks actual usage.
4. **R3** — skill allowlists and challenger decorrelation.
5. **R4** — context knobs, measured against the R1 baseline.
6. **R6** — oxalpha disposition.

R3 and R4 are only worth doing after R1 and R2, because without dispatch volume and telemetry there is nothing to tune against.

## Key Proof

- `data/state-history/coding-outcome-ledger.jsonl` — 9/1,433 isolated dispatches; backend and model distribution.
- `data/state-history/model-run-ledger.jsonl` — `model_attribution_coverage: 0.0`, `cost_rows: 0`, `token_rows: 0`.
- `tmp/fleet-alignment-20260905/production-readiness-20260906/*transport-proof.json` — six proofs expiring `2026-09-08T03:37:48Z`; byte-match inconsistency on finance-source-scout and research-scout.
- `tmp/finance-digest-repair-20260908/builder-transport-proof.json` — most recent builder proof, expired `2026-09-09T14:25:00Z` (review ran `2026-09-10T04:16Z`).
- Live `agents.entries.*` projection — skills/tools/sandbox/knob coverage.
- `scripts/agent_fleet_policy.py` — main-model drift versus live config.

## Boundaries

- This note is review and proposal only. It grants no dispatch, config, capital, execution, account, external-delivery, or schedule authority.
- R2, R4, R5, and R6 all require explicit Randall approval before any change; R2 and R4 are config mutations and R6 is destructive.
- No agent was dispatched, no canary was run, no config was mutated, and no proof was regenerated during this review.
- Expired transport proofs remain expired. Nothing here revalidates them.
- Efficiency claims in R4 are stated as hypotheses. Under F2 there is currently no telemetry capable of confirming or refuting them.

## Next Action

Randall decides R2 (canary-tax threshold change) and the `docs-continuity-editor` containment question in R5. Those two are the gating decisions. R1 measurement work can begin without further approval since it is additive instrumentation inside the workspace, but it should not be started if R2 is declined — a fleet that will not be dispatched does not need a scorecard.
