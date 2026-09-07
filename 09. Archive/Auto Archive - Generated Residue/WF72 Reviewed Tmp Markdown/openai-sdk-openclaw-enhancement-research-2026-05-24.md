# OpenAI SDK / Agents SDK research for OpenClaw enhancement - 2026-05-24

## Bottom line

Yes, the OpenAI SDK ecosystem can help OpenClaw, but the highest-value path is not a wholesale rewrite. OpenClaw already ships as a Node/npm package, already depends on `openai` (`^6.36.0` in OpenClaw 2026.5.4), already supports OpenAI Responses paths, and already has mature prompt-cache and session-pruning docs. The best enhancements are thin, local, measurable layers around cache diagnostics, prompt-prefix stability, structured-output validators, agent/eval traces, and optional SDK lab adapters.

Keep the portfolio planning base at $10k unless Randall explicitly changes it. Paper account equity near $100k is simulation capacity, not the planning base.

## Source notes

- OpenAI Libraries page: recommends official JS/TS SDK (`openai`) for direct API calls; Agents SDK for code-first orchestration, tools, handoffs, guardrails, tracing, sandbox execution; community libraries are unverified/use at own risk.
- OpenAI Prompt Caching: automatic on recent models; exact prefix match; static content at beginning, dynamic at end; 1024+ tokens threshold; `prompt_cache_key`; `prompt_cache_retention`; cached token counters in usage; up to 80% latency and 90% input-cost improvement when well-shaped.
- Responses migration docs: Responses is recommended for new projects, agentic by default, built-in tools, stateful context, multimodal, better cache utilization in OpenAI internal tests, structured output differences, function-calling differences.
- Agents SDK docs: code-first workflows when the app owns tools, approvals, state, handoffs, and tracing; install `@openai/agents zod`; traces show model/tool/handoff/guardrail runs; guardrails and human review support interruptions/resumable state.
- OpenClaw local docs: prompt caching uses `cacheRetention`, `prompt_cache_key`, `prompt_cache_retention: 24h` for OpenAI direct long cache; context pruning `cache-ttl`; system prompt stable prefix/volatile suffix boundary; cache trace diagnostics; `/status` reports cacheRead/cacheWrite.
- Current session status: OpenClaw 2026.5.4, model `openai-codex/gpt-5.5`, 70k input / 394 output, 48% cache hit, 66k cached, 114k/272k context.

## Priority enhancements

### P0 - no-runtime-mutation analysis/proof first

1. Cache efficiency scorecard
   - Build `scripts/openclaw_cache_efficiency_scorecard.py` to parse session/status/log usage where available.
   - Metrics: cacheRead ratio, context growth, static prefix churn suspects, tool-result bloat, compaction count, cache hit trend by agent/session.
   - Output: `tmp/openclaw-cache-efficiency-scorecard.json/.md`.
   - Boundary: read-only/report-only.

2. Prompt-prefix churn auditor
   - Compare stable boot/core file sizes and high-churn injected surfaces.
   - Flag volatile content that appears above cache boundary: timestamps, dynamic runtime blocks, oversized daily history, repeated tool outputs, large skills metadata, repeated generated artifacts.
   - Output exact recommended moves: keep durable rules in core; move procedures to skills; use memory tools on demand; avoid injecting large generated artifacts.

3. Tool-result slimming policy
   - Identify repeated large reads/fetches and add local guidance/tests for excerpting and artifact pointers.
   - Prefer SQL cockpit/proof lookup before broad file scans.
   - Add warnings when tool result payloads exceed thresholds and could be replaced by artifact paths + summaries.

4. Structured-output validator layer for finance/automation artifacts
   - Use Zod-style schema design concepts, but implement in existing Python/JSON validator surface first for workspace consistency.
   - Priority schemas: WF67 order card, WF68 advisor packet, sector matrix, capital recommendation packet, archive manifest, cron report packet.
   - Benefit: fewer malformed artifacts, safer guardrail gates, less prompt text spent explaining output format.

### P1 - OpenClaw Node/npm enhancement candidates

5. Provider request telemetry capture
   - Where safe/local, expose normalized request_id, provider processing time, rate-limit headers, cached tokens, model, endpoint family, retry count, timeout status.
   - Never log secrets or full prompts by default.
   - Useful for diagnosing slow/failing model routes and cache misses.

6. Responses API feature audit for OpenClaw provider path
   - Confirm which configured models use Responses vs Chat Completions vs Codex runtime.
   - Verify `store:false`/state handling where privacy-sensitive.
   - Confirm `prompt_cache_key` and `prompt_cache_retention` behavior for current model/auth path.
   - Output a compatibility matrix before changing code.

7. Optional OpenAI Agents SDK lab adapter
   - Prototype outside core runtime first.
   - Use for isolated research/planning workflows where Agents SDK tracing, handoffs, guardrails, and resumable approvals add value.
   - Do not replace OpenClaw’s native subagent/session runtime until proof shows value.
   - Candidate lab: one bounded “research scout” with web/file tools and trace output; no finance execution authority.

8. Evals/trace-grading-inspired local regression suite
   - Extend WF74 into agent-workflow evals: correct tool choice, no approval inference, no live-trade leakage, uses SQL cockpit before broad scans, respects cache-friendly output limits, follows WF67 exact approval gate.
   - Use local fixtures first; consider OpenAI trace grading only after privacy/retention policy is decided.

### P2 - after proof / optional

9. Realtime/voice interface experiments
   - Useful for low-latency spoken reviews, not core finance automation.
   - Requires separate channel/audio/privacy decision.

10. Hosted/file-search/tool-native experiments
   - Could help external corpus retrieval, but OpenClaw already has local file/SQL/memory retrieval.
   - Do not move private workspace/finance corpus into hosted file search without explicit policy/retention approval.

11. Prompt optimizer / eval dataset loop
   - Useful once WF55 outcome ledger and trace-quality datasets mature.
   - Not ready for finance performance claims until WF55 readiness advances.

## Recommended implementation sequence

1. Build report-only cache efficiency scorecard.
2. Add prompt-prefix churn/read-size audit with exact file/surface recommendations.
3. Add WF67 order-card schema/validator hardening and sample invalid fixtures.
4. Add provider route compatibility matrix: Responses/Completions/Codex, cacheRetention, store/state handling, request telemetry availability.
5. Extend WF74 eval fixtures to cover cache/tool-choice/approval-path behavior.
6. Only then prototype `@openai/agents` as a lab lane if it gives better tracing/approval interruptions than OpenClaw native subagents.

## Guardrails

- No config/auth/runtime/package mutation without exact approval.
- No adding unaudited dependencies directly into the live OpenClaw package.
- No hosted file-search upload of private workspace data without explicit retention/privacy decision.
- No finance probability/win-rate claims until WF55 readiness is no longer NOT_READY.
- No paper/live execution authority expansion from SDK tooling.
