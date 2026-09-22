# Routing Change: Sol Primary + Isolated-Agent Plan - 2026-09-19

**Status:** routing change APPLIED and validated. Isolated-agent + thinking items are PLAN ONLY (not applied).
**Owner approval:** Randall, 2026-09-19 (explicit, this session).
**Backup:** `~\.openclaw\openclaw.json.pre-sol-routing-20260919-2254` (sha256 `DBD8AF5D73F8EA79E1EC394975D64B036C841DB4B477CA98EE5DB630F14F88DE`).

## 1. Applied change (done)

`agents.defaults.model` in `~\.openclaw\openclaw.json`:

| Position | Before | After |
|---|---|---|
| primary | `openai/gpt-6-astra` | **`openai/gpt-5.6-sol`** |
| fallback 1 | `ollama-cloud/glm-5.3:cloud` | **`zai/glm-5.3`** |
| fallback 2 | `ollama-cloud/kimi-k3:cloud` | **`anthropic/claude-opus-5`** |
| fallback 3 | `zai/glm-5.3` | **`ollama-cloud/glm-5.3:cloud`** |
| fallback 4 | `anthropic/claude-opus-5` | (removed - now fallback 2) |

`ollama-cloud/kimi-k3:cloud` is out of the chain. Applied via
`openclaw config patch --dry-run` then apply (2 validated updates). `openclaw config validate` -> **Config valid**.
Change applies without a gateway restart.

Thinking: `agents.defaults.thinkingDefault` was **already `"high"`** and remains so. Docs confirm Ollama
Cloud GLM/DeepSeek send native `high`/`max` effort, and Z.AI GLM-5.3 supports `high`. **No change needed**
for the requested "high on cloud models" - it is already the global default and inherits to every agent.

## 2. Evidence supporting the chain order

Cache hit rates (1,171 events, main store) put the direct routes far ahead of the cloud routes for the
same models:

| Route | Cache hit% |
|---|---|
| `zai/glm-5.3` | 87.7 |
| `kimi/k3` | 83.8 |
| `ollama-cloud/glm-5.3:cloud` | 45.9 |
| `ollama-cloud/kimi-k3:cloud` | 9.2 |

Reliability across all agent stores (completed events):

| Model | ok | err | err% | last ok |
|---|---|---|---|---|
| meta/muse-spark-1.3-contributor | 313 | 8 | 2.5 | 09-19 23:46 UTC |
| xai/grok-4.6 | 244 | 3 | 1.2 | 09-09 15:02 UTC |
| ollama-cloud/glm-5.3:cloud | 156 | 2 | 1.3 | 09-18 05:28 UTC |
| openai/gpt-5.6-sol | 98 | 34 | 25.8 | 09-20 03:11 UTC |
| openai/gpt-6-astra | 287 | 96 | 25.1 | 09-20 05:25 UTC |
| ollama-cloud/deepseek-v4.1-flash:cloud | 69 | 0 | 0.0 | 09-19 17:51 UTC |

**Caveat on OpenAI error rates:** most OpenAI errors are `This operation was aborted | 20` (client
abort / idle timeout), not provider rejection. Treat the 25% figures as ambiguous, not as provider
failure. Sol's last successful call was 09-20 03:11 UTC, so it is live.

## 3. Material conflict found (needs an owner decision)

The change works live, but it creates **drift against the workspace's own canonical routing policy**,
which still denies OpenAI models:

- `scripts/agent_fleet_policy.py`: `MAIN_PRIMARY = xai/grok-4.6`; `LEGACY_DENIED_MODELS` includes
  `openai/gpt-5.6-sol`, `openai/gpt-6-astra`, `openai/gpt-5.6-terra`, `openai/gpt-5.6-luna`.
  Its own header records `OPENAI-ROUTING-REMOVAL-20260910`: *"the OpenAI account is out of quota, so
  Astra/Sol/Terra/Luna are retired from every primary, fallback, and recovery position."*
- `is_denied_persistent_model("openai/gpt-5.6-sol")` -> **True**
- `scripts/project_implementation_router.py`: `MAIN_MODEL = fleet_policy.MAIN_PRIMARY` (Grok).
  Any Main-route packet now emits **`main_model_invalid`** and **`main_live_model_mismatch`**.
- `scripts/long_work_packet_linter.py` denies `LEGACY_DENIED_MODELS` in persistent specialist scope.
- Opus policy: `OPUS_ADVISORY` sets `automatic_fallback = False` and the fleet doctrine says Opus is
  never an automatic/recovery fallback. Placing `anthropic/claude-opus-5` in the live fallback chain
  conflicts with that standing text (it was your explicit instruction, so it is applied regardless).

**Important context - much of this drift pre-existed.** The old primary `openai/gpt-6-astra` is *also*
in `LEGACY_DENIED_MODELS`. Verified directly:

| Model tested against live config | `validate_main_route` result |
|---|---|
| `openai/gpt-6-astra` (OLD primary) | `main_model_invalid`, `main_live_model_mismatch` |
| `openai/gpt-5.6-sol` (NEW primary) | **NONE (accepted)** |
| `xai/grok-4.6` (policy target) | `main_model_invalid`, `main_live_model_mismatch` |

So the workspace was **already** in drift; this swap changes one denied model for another. Live routing
and the canonical policy have been out of sync since at least the astra promotion.

**Also stale:** the `OPENAI-ROUTING-REMOVAL-20260910` "out of quota" premise no longer holds - OpenAI
routes are producing successful completions today (astra and sol both). The policy note outlived its
fact.

**Decision needed (owner-gated; not applied):**
1. Update the canonical policy to match live routing (new primary, OpenAI un-denied, Anthropic allowed
   as fallback) - edits `scripts/agent_fleet_policy.py`, the router's `MAIN_MODEL`, linter matrices, and
   the fleet tests. Touches protected core files, so it needs explicit authority.
2. Or revert live routing to the policy target `xai/grok-4.6`.
3. Or leave the drift as-is (current state) and carry it knowingly.

## 4. Plan: change isolated agents to ollama (NOT applied)

Reality check first: **most isolated agents already use `ollama-cloud`.**

| Agent | Current primary | Already ollama-cloud? |
|---|---|---|
| qa-redteam | `ollama-cloud/glm-5.3:cloud` | yes |
| finance-redteam | `ollama-cloud/glm-5.3:cloud` | yes |
| finance-source-scout | `ollama-cloud/deepseek-v4.1-flash:cloud` | yes |
| docs-continuity-editor | `ollama-cloud/deepseek-v4.1-flash:cloud` | yes |
| oxalpha-lab | `ollama-cloud/glm-5.3-flash:cloud` | yes |
| oxalpha-functional-lab | `ollama-cloud/glm-5.3-flash:cloud` | yes |
| research-scout | `xai/grok-4.6` | no |
| marketing-outreach | `openai/gpt-5.6-luna` | no |
| implementation-builder | `meta/muse-spark-1.3-contributor` | no |

All six role-bound specialists match `agent_fleet_policy.SPECIALIST_PRIMARY` exactly, so the fleet is
already aligned with its policy today.

**The three non-ollama agents are deliberate role assignments, not leftovers:**
- `implementation-builder` = Muse Spark 1.3 is the **approved code-authoring model** (fleet doctrine:
  "Muse authors code by default"). Moving it to ollama would place code authorship on an untrusted/
  draft-labelled route and trip the linter's `ollama_trust_label_not_bounded` /
  `ollama_write_without_tool_loop_proof` rules.
- `research-scout` = Grok 4.6 at 1.2% error rate is the reliability leader.
- `marketing-outreach` = Luna, with a Z.ai fallback.

**Plan options, in order of risk:**

- **Option A (recommended, lowest risk):** treat "isolated agents on ollama" as already satisfied for
  the six role specialists; change nothing. Add an explicit `subagents` route if the intent was that
  *spawned* child work runs on ollama.
- **Option B (bounded):** move `research-scout` and `marketing-outreach` to
  `ollama-cloud/deepseek-v4.1-flash:cloud` (0.0% error, 69 ok - the most reliable ollama route).
  Keeps code authorship on Muse. Requires editing two `agents.entries.*.model` blocks + updating
  `SPECIALIST_PRIMARY` so the linter does not flag `specialist_model_mismatch`.
- **Option C (broad):** move all three including `implementation-builder`. **Not recommended** - it
  contradicts the approved code-authoring split and weakens the linter's trust boundary.

**Subagent lever (if "isolated" meant spawned children):** `agents.defaults.subagents` accepts
`model` and `thinking`. Currently only `archiveAfterMinutes`/`maxConcurrent` are set, so subagents
inherit the agent's model. Setting `agents.defaults.subagents.model = "ollama-cloud/deepseek-v4.1-flash:cloud"`
would route spawned children to ollama. Requires owner approval - it changes every spawn's cost and
capability surface. **Not applied.**

## 5. Open items

- `ollama-cloud/kimi-k3:cloud` still exists in `modelPolicy.allow`, `agents.defaults.models` (alias
  `ollamakimi3`), and the provider catalog. It is only removed from the *chain*. It is still selectable
  by explicit ref/session pin. Optional cleanup, not done.
- `anthropic/claude-opus-5` has **no completed events in any of the 10 agent stores**, and the
  `anthropic` provider block lists no models (only `agentRuntime.id: claude-cli`). Claude CLI 2.1.139
  **is** installed. So the Anthropic leg is configured and plausibly functional but **unproven by
  trajectory evidence**. Treat it as unverified until an actual run lands.
- `num_ctx: 1048576` is still set on all five ollama-cloud models. Prompt sizes in the last 6,000 calls:
  p50 135,816 / p90 266,751 / p99 1,619,838 / max 9,220,011. 14 sessions exceeded 524k. A cap would
  reduce cold-prefill cost on the no-cache cloud route, but 34 sessions exceed 262k, so a 256k cap
  would truncate real work. **Not applied** - needs a chosen target and an acceptance test.
- The `scripts/test_agent_fleet_policy.py` suite **errors under pytest** (`fixture 'errors' not found`,
  11 errors) but **passes when run as a script** (`ok: agent_fleet_policy tests passed`, exit 0). This is
  a pre-existing test-harness style issue, not caused by this change.

## 6. Policy realignment APPLIED (2026-09-19 23:30 MST)

Owner authority: Randall, explicit ("Approve to update the policy files"). Follow-through on the drift in section 3.

### Canonical owner updated

`scripts/agent_fleet_policy.py`:

| Constant | Before | After |
|---|---|---|
| `MAIN_MODEL` / `MAIN_PRIMARY` | `xai/grok-4.6` | **`openai/gpt-5.6-sol`** |
| `MAIN_FALLBACKS` | `[glm-5.3, kimi-k3, muse-spark]` | **`[zai/glm-5.3, anthropic/claude-opus-5, ollama-cloud/glm-5.3:cloud]`** |
| `LEGACY_DENIED_MODELS` | included `openai/gpt-5.6-sol` | **Sol removed** (it is the live Main primary) |
| `SPECIALIST_PRIMARY["research-scout"]` | `xai/grok-4.6` | **`ollama-cloud/deepseek-v4.1-flash:cloud`** |
| `OPUS_ADVISORY` | - | added `main_chain_fallback: True` (Main chain only) |

Added `SOL_MODEL` and `ZAI_MODEL` constants. Header records `SOL-PRIMARY-REALIGN-20260919` and notes the
2026-09-10 out-of-quota premise no longer holds. Opus stays denied as a persistent specialist and stays out
of specialist automatic fallbacks; it is allowed only in Main's owner-directed chain.

### Live config updated

`agents.entries["research-scout"].model.primary` -> `ollama-cloud/deepseek-v4.1-flash:cloud` (fallbacks `[]`).
Applied via `openclaw config patch` after a validated dry run.

### Dependents reconciled

- `project_implementation_router.py`: `MAIN_MODEL` resolves to Sol via the policy; added `RESEARCH_MODEL`
  so the research route reads the policy instead of a hardcoded Grok.
- `agent_bootstrap_generator.py`: research-scout `default_model`/`upgrade_model` -> DeepSeek.
- `long_work_packet_linter.py`, `agent_bootstrap_linter.py`: stale Main-model text corrected.
- `cron_contract_validator.py`, `model_run_ledger.py`, `token_usage_ledger.py`: guidance strings no longer
  name Grok as the Main model.
- Skills `veritas-model-routing-helper-lanes`, `veritas-isolated-agent-contract`: Main doctrine updated.
- Tests updated: `test_agent_fleet_policy`, `test_long_work_packet_linter`, `test_agent_bootstrap_generator`,
  `test_project_implementation_router`, `test_project_implementation_router_scoped_worktree`.

### Verification (original complaint resolved)

| Check | Result |
|---|---|
| `validate_main_route(Sol)` | **NONE (accepted)** |
| `validate_main_route(old astra)` | `main_model_invalid`, `main_live_model_mismatch` |
| `router.MAIN_MODEL` | `openai/gpt-5.6-sol` |
| End-to-end Main route packet | `status: proposed`, model Sol, backend `main`, **errors NONE** |
| policy vs generator vs router vs linter | **OVERALL ALIGNED: True** |
| `validate_policy_maps` | `status=ok` |
| `openclaw config validate` | Config valid |
| Core suite (5 files) | **PASS** |
| `long_work_packet_linter --example --validate` | `status=ok critical=0 warnings=0` |

### Known pre-existing failures (proven NOT caused by this change)

Each isolated by re-running under the pre-edit policy values:

1. **`test_project_implementation_router_scoped_worktree.py`** - 25 failures. Under the pre-edit policy the
   same 25 fail (`run=36 failures=25`). The suite expects V2/V3 transport-proof schema behavior the
   uncommitted router work does not yet provide. Independent of this change.
2. **`test_skill_core_proof_tier_audit.py`** - 2 failures: term `Alert Bands and Invalidation Register`
   missing from `veritas-entry-policy-opportunity-surface` (finance skill, unrelated). The routing-skill term
   failures in the same test **were** caused by this change and are now fixed.
3. **`test_harness_task_model_roles.py`** - 3 failures: frozen fixture
   `tmp/harness-convergence-20260905/role-inputs/owner-approval-snapshot-v2.json` does not exist and was never
   tracked in git.
4. **`agent_bootstrap_linter.py --agents all --validate`** - `PermissionError` on
   `workspaces/implementation-builder/TOOLS.md`, which is a **directory**, not a file. Environmental.

### Deliberately NOT changed

`scripts/task_scoped_model_role_contract.py` keeps `PARENT_MAIN_MODEL = "openai/gpt-6-astra"`. It is bound to
frozen owner approval `APPROVAL_SHA256` with `VALID_UNTIL_UTC = 2026-09-06T05:12:00Z` and is already expired.
Rewriting it would falsify a frozen approval record, so it stays historical evidence.

## 7. Provenance

Applied with: `openclaw config patch --file tmp/sol-routing.patch.json5` (dry-run validated first).
Probes (read-only): `tmp/prove_drift.py`, `tmp/probe_final_routing.py`, `tmp/probe_chain_health.py`,
`tmp/probe_context_sizes.py`, `tmp/show_specialist_delta.py`, `tmp/dump_agents_full.py`.
Store: `~/.openclaw/agents/*/agent/openclaw-agent.sqlite`, `trajectory_runtime_events`.
No schedule, channel, auth, finance canon, portfolio, capital, account, or delivery mutation was made.
