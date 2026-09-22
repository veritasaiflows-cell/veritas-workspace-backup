# Ollama Cloud Prompt-Cache Diagnosis - 2026-09-19

**Status:** diagnosis complete; remediation requires owner approval (config + routing changes).
**Scope:** read-only evidence gathering. No config, schedule, channel, canon, or capital mutation.
**Owner:** Main (Veritas). Next action owner: Randall (routing/config decisions).

## Question

Why do Ollama Cloud models reach worse prompt-cache reuse than the same models served direct, and what should be done about it?

## Verdict (short)

Ollama Cloud reuses prompt prefixes **2-9x worse than the identical models on direct routes**, and the
workspace's configured `cacheRetention: "long"` is a **silent no-op for `api: "ollama"`**. Compounding
factors: the default fallback chain prefers the *worse*-caching GLM/Kimi routes, and in-session model
switching (44 switches across 72 ollama-cloud sessions) destroys cache lineage.

## Evidence

### 1. Per-model cache-hit rate (1,171 `model.completed` trajectory events, main agent store)

| Model | n | hit% |
|---|---|---|
| openai/gpt-5.6-sol | 131 | 92.1 |
| openai/gpt-5.6-terra | 77 | 92.6 |
| meta/muse-spark-1.3-contributor | 152 | 91.6 |
| xai/grok-4.6 | 185 | 89.4 |
| openai/gpt-6-astra | 384 | 86.6 |
| `zai/glm-5.3` (direct) | 28 | **87.7** |
| **`ollama-cloud/glm-5.3:cloud`** | 66 | **45.9** |
| `kimi/k3` (direct) | 30 | **83.8** |
| **`ollama-cloud/kimi-k3:cloud`** | 25 | **9.2** |
| `zai/glm-5.3-flash` (direct) | 12 | **92.7** |
| **`ollama-cloud/glm-5.3-flash:cloud`** | 44 | **21.9** |
| ollama-cloud/deepseek-v4.1-flash:cloud | 19 | 50.3 |

Same-model, same-prompt comparison: GLM-5.3 **45.9% vs 87.7%**, GLM-5.3-flash **21.9% vs 92.7%**,
Kimi K3 **9.2% vs 83.8%**.

### 2. Era boundary — historical zeros were partly an accounting gap

| Day | n | hit% |
|---|---|---|
| 2026-09-06 .. 2026-09-12 | 79 | **0.0** (every call) |
| 2026-09-14 .. 2026-09-20 | 77 | 59.7-99.1 |

A pre-2026-09-13 ollama-cloud event carries `promptCache: null` and `usage: null`. Cache hits first
appear 2026-09-14. Installed OpenClaw package (2026.9.4) is dated **2026-09-13**, and this build adds the
`prompt_eval_cached_count` -> `cacheRead` mapping (`dist/stream.runtime-dsT1Pq6T.mjs:483`,
`dist/stream-api-B6qU7HoH.d.ts:121`). Conclusion: the pre-09-13 zeros are not trustworthy as
provider behavior; **do not over-read ollama-cloud numbers before 2026-09-14.**

### 3. Interval vs cache hit

| gap | ollama-cloud hit% | direct hit% |
|---|---|---|
| first call | 34.7 | **92.5** |
| <1m | 43.5 | 54.1 |
| 1-5m | 20.0 | **93.3** |
| 5-15m | 16.7 | **93.1** |
| 15-60m | 63.6 | **95.5** |
| >60m | 66.7 | **96.8** |

Direct routes hold 93-97% across every gap; ollama-cloud is worst in the 1-15m band. A TTL story would
predict the opposite. Direct first-call already hits 92.5% (shared static prefix warm from other
sessions); ollama-cloud first-call is 34.7%, indicating little cross-session prefix sharing.

### 4. Mechanism — `cacheRetention` never reaches the Ollama transport

`dist/extra-params-BRsRRfgM.mjs:23` `resolveCacheRetention()` returns `undefined` unless the route is
Anthropic-family, Google-generative, OpenAI-family, or has an explicit cache `compat`. For
`api: "ollama"` all four are false and no `compat` is set, so the function **returns early**. Therefore
`agents.defaults.params.cacheRetention: "long"` is inert for every `ollama-cloud/*` model.

The direct routes get real cache control instead:
- `zai` = `api: "openai-completions"` -> OpenAI-family `prompt_cache_key` handling -> 87.7%
- `kimi` = `api: "anthropic-messages"` -> Anthropic `cache_control` checkpoints -> 83.8%
- `ollama-cloud` = `api: "ollama"` (native `/api/chat`) -> no cache-control path -> 9-46%

### 5. Bimodality — likely replica-level KV affinity (hypothesis, well-supported)

Raw ollama-cloud calls alternate between ~0% and ~98% hit with a **constant hit size** (glm-5.3-flash
~22,400; deepseek-v4.1-flash ~30,500-30,620). Sample session: monotonically growing input
(37k -> 43k -> 50k -> 57k -> 64k -> 71k -> 77k -> 83k -> 93k -> 95k) with `cacheRead = 0` on every turn.

A shared single prefix cache should produce a stable rate, not 0/98 oscillation with a fixed hit size.
Requests distributed across multiple GPU workers, each holding a local KV cache, predicts this exactly:
consecutive calls landing on a warm worker hit; rerouting misses. Not proven - see Open items.

Independent corroboration: upstream `ollama/ollama` issue **#16714 "Ollama Cloud - Prompt Cache
Support"** (opened 2026-06-14, still open, updated 2026-08-22) reports the same gap in agentic loops by
benchmarking. Related: #15600 (closed feature request), #17489 (cached-input pricing vs zero-data
retention), #17247 (warm prefill cache across unload/reload).

### 6. Aggravating: fallback chain prefers the worse route

Configured (`agents.defaults.model`):

```
primary:   openai/gpt-6-astra
fallbacks: ollama-cloud/glm-5.3:cloud      <- 45.9% hit
           ollama-cloud/kimi-k3:cloud      <-  9.2% hit
           zai/glm-5.3                     <- 87.7% hit, SAME MODEL, comes last
           anthropic/claude-opus-5
```

The two poorest-caching routes sit ahead of the best-caching route for the same model. `kimi/k3`
(83.8%) is not in the chain at all.

### 7. Aggravating: `num_ctx: 1048576` on all five ollama-cloud models

A 1M-token context window on a route that does not reliably reuse prefixes means every miss re-prefills
an enormous prompt. Highest-observed prompt: 422,081 tokens at 0.2% hit.

### 8. Aggravating: in-session model churn

44 model switches across 72 sessions touching ollama-cloud. Example lineage:
`glm-5.3-flash -> kimi-k3 -> glm-5.3 -> kimi-k3 -> glm-5.3`. Every switch starts a new cache lineage
and forces a full cold prefill.

## Improvement plan (ranked)

Requires owner approval - all items are config/routing changes, not workspace writes.

1. **Reorder/repair the fallback chain (highest value, lowest risk).** Put `zai/glm-5.3` before
   `ollama-cloud/glm-5.3:cloud`, and consider `kimi/k3` in place of `ollama-cloud/kimi-k3:cloud`.
   Same models, ~2x better reuse, already configured. Exact diff review before apply.
2. **Stop treating `cacheRetention` as protection for ollama-cloud.** Either accept it as inert and
   document it, or test whether a `compat` cache flag is honored by native `/api/chat` (likely not -
   `/api/chat` is not OpenAI-compatible, so `supportsPromptCacheKey` / `cacheControlFormat` are almost
   certainly wrong to set). Do not assume the current global setting covers these routes.
3. **Pin model and thinking level per session; stop mid-conversation fallback hops.** Use
   `/model default` on drifting sessions. Keep any fallback hop inside one model family so the cache
   lineage survives.
4. **Cap `num_ctx` for ollama-cloud models** to a realistic window (e.g. 128k-256k) so a cache miss
   does not re-prefill 400k+ tokens.
5. **Prefer direct routes for cache-sensitive, long-session work** (Main, QA, review). Reserve
   ollama-cloud for bursty, short, or non-cache-sensitive jobs.
6. **Confirm or refute the replica-affinity hypothesis** with a controlled probe: identical prefix, N
   sequential calls, measure hit variance and whether hit size stays constant. If confirmed, the cause
   is provider-side routing and the only real mitigation is item 5.

## Open items / limits

- **Live provider-side probe was blocked.** A direct `/api/chat` call returned HTTP 401: the
  `ollama-cloud` provider block has **no `apiKey` field** (`auth: "api-key"` only), so the credential
  resolves inside the Gateway from the protected store. Could not authenticate from an outside process.
  Any confirmation must run *through* the Gateway on an ollama-cloud-pinned session.
- Replica-affinity remains a hypothesis; era-A zeros are an accounting artifact, not proof of provider
  failure.
- Sample sizes for some direct comparators are small (n=12-30) against ollama-cloud (n=25-66). The
  per-day table (79 consecutive zero-hit calls in era A) and the monotonic-growth sample sessions are
  the stronger evidence.
- Cost impact not established. All ollama-cloud models carry `cost: {input:0, output:0}` in config;
  actual billing is unknown, so this is framed as latency/quota, not dollars.

## Verification update - 2026-09-20 (is it working now?)

Re-probed with `tmp/probe_ollama_cache_now.py` and `tmp/probe_ollama_cache_answer.py` (read-only).

**Answer: yes for the era, with two real caveats.**

- ollama-cloud, era `>= 2026-09-14`: aggregate **78.8%** hit (n=97). Last 48h **83.2%** (n=70); last
  **24h 93.7%** (n=29; 23 of 29 calls >= 90%, 3 calls < 50%).
- Per-model, era vs all-time: `glm-5.3:cloud` **92.8%** vs 44.0% (n=32);
  `deepseek-v4.1-flash:cloud` 80.0% (n=46); `glm-5.3-flash:cloud` **69.4%** vs 22.4% (n=21);
  `kimi-k3:cloud` 92.6% (n=2, too small to read).
- **Most of the apparent improvement is the instrumentation fix, not provider behavior.** Every
  pre-09-14 ollama-cloud event is 0.0%; the era floor is the 2026.9.4 build that maps
  `prompt_eval_cached_count` -> `cacheRead`. Era `glm-5.3:cloud` (92.8%) is now roughly at parity with
  direct `zai/glm-5.3` (87.7%), so the 45.9% vs 87.7% gap in the original diagnosis was inflated by
  the accounting artifact.
- **Remediation item 1 is effectively already applied.** The live fallback chain is now
  `openai/gpt-5.6-sol` -> `zai/glm-5.3` -> `anthropic/claude-opus-5` -> `ollama-cloud/glm-5.3:cloud`,
  so the worst-caching routes no longer lead the chain. Items 2-4 (cacheRetention inert, per-session
  model pinning, `num_ctx` still 1048576 on all five ollama-cloud models) remain open.
- **Residual defect still live: bimodality.** Same-day calls still alternate ~98% and ~42-44% with a
  near-constant hit size (~21.6k for deepseek-v4.1-flash). Example 2026-09-20: `21732/523 = 97.6%`
  immediately alongside `9482/12900 = 42.4%`. This keeps the replica/KV-affinity hypothesis open and
  is not explained by TTL.
- **Gap is not TTL-shaped.** Within-session consecutive calls, era: `<1m` 58.8% (n=15), `1-5m` 82.8%
  (n=9), `5-15m` 64.9% (n=6), `15-60m` 91.4% (n=9). Short gaps are the *worst* band - the opposite
  of what a TTL story predicts.
- Live confirmation from the current Main session: `71% hit - 273k cached, 0 new`.
- Worst remaining era calls cluster on 2026-09-19 15:30-15:46 (`deepseek-v4.1-flash:cloud`,
  `glm-5.3-flash:cloud`), each ~30k tokens at ~0% hit - cold lineage, not size.

## `num_ctx` cap semantics (added 2026-09-20, decision-grade correction)

Read the client before recommending, not after. Two independent knobs:

- `params.num_ctx` on an `api: "ollama"` model is forwarded as the native `/api/chat` `options.num_ctx`
  (`dist/stream.runtime-dsT1Pq6T.mjs:141` `resolveOllamaNativeNumCtx`: explicit `params.num_ctx` wins,
  else `model.contextTokens`, else Ollama's own model/env/VRAM/Modelfile policy). It is a **server-side**
  KV-allocation / context-limit request.
- OpenClaw's auto-compaction trigger reads `this.model.contextWindow`, **not** `num_ctx`
  (`dist/resource-loader-Bu_pVD2t.mjs:10089,10122` -> `shouldCompact(contextTokens, contextWindow, ...)`
  at `dist/compaction-DhVoBTx3.mjs:380`).

**Consequence:** lowering only `num_ctx` leaves the client gate at 1M while the server cap drops, so a
prompt between the two values can be rejected server-side before compaction ever fires - a new
fail-hard mode, not a self-healing one. Any `num_ctx` cap must be paired with a matching `contextWindow`
reduction to stay coherent.

**Measured blast radius (ollama-cloud, 170 calls with usage, `tmp/probe_numctx_token_share.py`):**

| cap | calls over cap | % of calls | sessions |
|---|---|---|---|
| 131072 | 23 | 13.5% | 11 |
| 262144 | 5 | 2.9% | 3 |

Max prompt by model: `glm-5.3:cloud` 185,284; `glm-5.3-flash:cloud` 155,876; `kimi-k3:cloud` 148,010;
`deepseek-v4.1-flash:cloud` 408,257; `deepseek-v4-flash:cloud` 311,347. Only the two deepseek entries
exceed 256k at all.

**Corrected claim:** a `num_ctx` cap bounds the *cost of a cache miss* (tokens re-prefilled) and caps
context loss; it does **not** raise the hit rate. The bimodal miss is replica affinity, not prompt size.

## Provenance

Probes (read-only, retained): `tmp/probe_ollama_cache_trend.py`, `tmp/probe_cache_gap.py`,
`tmp/probe_ollama_instrumentation.py`, `tmp/probe_promptcache_block.py`, `tmp/probe_key_shape.py`,
`tmp/dump_provider_config.py`, `tmp/probe_ollama_cloud_cache_live.py` (blocked on auth).
Source of truth for rates: `~/.openclaw/agents/main/agent/openclaw-agent.sqlite`
(`trajectory_runtime_events`, `model.completed`), 2026-09-06 .. 2026-09-20.
Client code: OpenClaw 2026.9.4 `dist/extra-params-BRsRRfgM.mjs`, `dist/stream.runtime-dsT1Pq6T.mjs`.
