# Veritas MCP Expansion Continuity Plan - 2026-09-27

Project: Veritas MCP usage expansion

- **Status:** Reviewed and strengthened 2026-09-27; expansion not implemented. Existing MCP works, but comprehensive freshness, lineage, bounded-output, and efficiency guarantees remain unproven.
- **Owner:** Main.
- **Continuity home:** This note.
- **Authority:** Read-only planning. This note grants no config, scheduler, plugin, network, credential, finance-canon, delivery, capital, account, order, or execution authority.

## Objective

Expand MCP into the workspace's preferred narrow read path for validated operational facts, starting with finance, while preserving routers and full-text search for discovery and owner workflows for refresh or mutation.

The target is faster, lower-context, source-coherent answers for Main, isolated helpers, and dashboards without creating a second finance system or broad filesystem/SQL access surface. Optimize accepted-answer accuracy and total retrieval cost, not the number of MCP servers or calls. MCP is an interface; deterministic producers and validators supply the guarantees.

## Review Decision - 2026-09-27

Keep the finance-only/read-only design, but strengthen the existing seven tools before broadening the catalog. The highest-value changes are exact input lineage, consistent typed results, bounded retrieval, and reusable model-free readers. Do not wait for the next Saturday merely to measure existing-tool adoption or draft independent contracts.

| Finding | Evidence and consequence | Plan correction |
|---|---|---|
| Stored funnel lineage is incomplete | `funnel()` checks the current controller against SQL, not the exact controller/thesis/macro/quote inputs that produced the stored ranking. A temporary-fixture reproduction returned the old band low 454.19 after SQL, guard, and controller coherently changed to 400; no stale status was returned. This proves a synthetic failure mode, not a wrong live recommendation. | Bind each produced packet to its exact input versions and validate that binding on reads; make this Phase 0A. |
| Today's tools are not uniformly bounded or typed | `get_thesis` returns the full record; funnel names, thesis flags, and renewal gate lists have no pagination/byte cap. Successful band/funnel results have no common status; some unavailable paths omit the boundary. | Retrofit existing tools, not just new tools. Add summary defaults, typed variants, explicit truncation and bounded detail. |
| Fresh-looking packets can contain old inputs | The live band response returned confidence 35 without its scale; renewal omitted finish time; funnel quote values have no per-quote timestamp. A newly generated response is not fresh source evidence. | Separate served/generated/source times, field freshness, market session, units, and validity. |
| Reload proof was underspecified | Installed docs say `openclaw mcp reload` affects only the calling CLI process; session-owned stdio runtimes can persist between turns. | Prove the Gateway consumer's loaded build, not just a fresh standalone probe. |
| Sequential gating leaves safe value idle | Natural weekly proof is necessary for scheduled recommendation reliability, not for routing measurements, schema design, or an independent operations proposal. | Separate technical, runtime, and natural-cycle acceptance; gate only dependent promotion. |

Review route: Main inspected local source and installed product docs, exercised three existing MCP tools, and ran a contained synthetic reproduction. No implementation helper was needed for this bounded plan edit; this is not independent code QA. No financial recommendation is made by this review.

## Current State - Measured 2026-09-27

- OpenClaw is `2026.9.4 (3a9d69d)`.
- One local stdio server, `veritas-data`, is registered through the official Python MCP SDK `mcp` 1.30.0.
- The config allowlist exposes exactly seven tools: reference band, thesis, recommendation funnel, thesis review, gap-repair report, weekly renewal packet, and alert-ledger verification.
- The seven tools are intended as read-only adapters; SQL uses `mode=ro`, ticker input is validated, and tools declare read-only annotations. Those annotations are hints, not an access-control boundary. The common denial envelope is not yet present on every unavailable/error branch.
- Earlier same-day baseline: standalone probe reported 7 tools and `scripts/test_veritas_mcp_server.py` had **22 passing tests**. This review rechecked version, doctor/probe (`ok`, no issues), and live band/funnel/renewal calls; it did not rerun the full suite. Existing tests are not proof of the new contract or the reproduced lineage gap.
- Live use has proven the value proposition: three parallel finance questions completed through typed calls without file discovery, and stale funnel data was withheld rather than presented as current.
- The live funnel returned the packet generated at 08:23 Phoenix on 2026-09-27. It passed existing guards; complete input lineage and the durable natural post-renewal refresh path remain unproven. Do not equate this with all source fields being current.
- No custom Veritas Plugin SDK package exists and no MCP endpoint is exposed outside the local OpenClaw workspace.
- The evaluated finance scope is becoming dynamic. New MCP list or batch tools must not assume 32 names and must remain bounded when the workspace monitors 300 or thousands of names.

## Architecture Decisions

1. **Keep `veritas-data` finance-only and read-only.** It remains a thin adapter over guarded SQL, validated artifacts, and shared validators. It does not recreate ranking, freshness, or finance policy.
2. **Use MCP for supported structured retrieval, not generic workspace discovery or control.** Full-text/semantic search remains the route for unstructured notes/history; workflow routers remain the route for ownership, blockers, refresh, and approved action. Policy-filtered tool discovery is distinct from unrestricted filesystem search and is a valid catalog optimization.
3. **Separate future operations tooling.** If workspace-status demand is proven, create a separate proposal for a read-only `veritas-ops` MCP rather than mixing runtime, workflow, and finance tools in `veritas-data`.
4. **Fail closed on incoherent versions.** Current SQL, controller, funnel, thesis, universe/scope, and baseline-pin identities must be distinguishable. A later timestamp alone is not enough.
5. **Bound every response.** List/history tools require filters, limits, and pagination or top-N summaries. Never return an unbounded monitored universe.
6. **Share readers, not duplicate systems.** CLI validators, MCP, and any later UI should use the same pure read/validation functions. Scheduled producers continue model-free through existing approved entry points; do not add an LLM or an MCP round trip where a direct deterministic call is cheaper.
7. **Do not build a plugin merely to wrap reads or display a report.** Use existing report surfaces first; consider MCP Apps for a concrete interactive-view need. A native plugin needs a requirement MCP/existing tools cannot meet, such as a hook or Gateway method.
8. **Keep read paths side-effect-free and local.** No refresh-on-read, provider fetch, ranking recomputation, shell invocation, or hidden producer run. Return a typed blocker and the named owner route instead. A read-only tool must not become a confused deputy for a more privileged host process.

## Standard Response Contract

Specify and test one versioned contract for all seven existing tools before composites. Use concrete typed models/JSON schemas, not only generic `dict` outputs. Verify MCP `outputSchema`/structured results and the actual OpenClaw client projection; advertised schemas alone do not prove consumer validation.

| Contract group | Required semantics |
|---|---|
| Identity | `schema_version`, server build identity, producer/validator version, and an input-set or snapshot identity. |
| Result | `status`: `ok`, `partial`, `not_found`, `unavailable`, `stale_suppressed`, or `invalid_input`; stable reason codes plus bounded human explanation; data separate from metadata. Preserve upstream domain status under its own field. |
| Time | `served_at_utc` is request time; `generated_at_utc` is producer time; each source/field retains `as_of`, market-session/date basis, and applicable validity policy. Never replace missing source time with request time. |
| Provenance | Logical source IDs or workspace-relative safe references, content hashes/pins, exact dependency versions, and governed scope ID/hash/count. No credentials or arbitrary absolute host paths. |
| Meaning | Currency, units, confidence scale and cap, score meaning/calibration status, null/missing reasons. Do not infer scales from magnitude or confuse data confidence with thesis conviction. |
| Quality | Freshness/coherence/coverage status per component; required versus optional components; typed blocker and owner refresh route. `not_found` means the source was successfully queried, not that a dependency failed. |
| Bounds | Returned count, total matching count where known, `truncated`, stable ordering and snapshot-bound `next_cursor` where supported. Suppression is not a legitimate zero-candidate result. |
| Boundary | Read-only evidence and no inferred approval/canon/capital/account/order/execution authority on every outcome, including errors. Sanitize exception text. |

Composite tools must keep historical thesis evidence separate from current bands and prices. Suppress dependent conclusions when required inputs are incoherent; optional omissions may return `partial` with explicit field status. A healthy database is not an accepted thesis or an actionable recommendation. No automatic thesis acceptance.

**Determinism:** identical validated input versions, normalized arguments, and evaluation clock produce identical data, ordering, reasons, and semantic digest; request timestamps are excluded from that digest. Freeze time in tests. Tie-break lists explicitly; canonicalize hashing/serialization and numeric/null handling.

**Read consistency:** use a read-only SQL transaction/snapshot and immutable/versioned artifact identities, or check dependency identities before and after assembly and reject a changed read. Atomic file replacement alone does not make multiple files one snapshot. Do not hash only the SQLite main file as logical-state proof when committed state can reside in WAL.

**Proposed initial budgets, not current guarantees:** summary/detail envelopes at most 16 KiB/64 KiB; list default 20, hard maximum 100 items subject to the byte ceiling; batch maximum 20 unique tickers; at most 4 concurrent reads. Reject over-budget inputs, bound input-file reads too, and never silently cut off risk/invalidation fields. Tune budgets from the baseline before implementation acceptance, recording any change.

**Caching:** first measure whether needed. Cache parsed/validated inputs by exact dependency identity plus schema/policy version, not ticker or TTL alone; reevaluate time-dependent freshness at read time. A stale/error cached result cannot become `ok` without valid new evidence. Bound memory and cache lifetime; avoid rehashing the whole universe or rescanning the full ledger per ticker.

## Phased Plan

### Phase 0A - Harden the existing read contract

1. Define a per-tool source/validator/freshness/consumer matrix. Retrofit the envelope, typed errors, output budgets and summary/detail behavior across all seven tools. Preserve existing consumers through additive fields or an explicit versioned migration; test omitted/default arguments.
2. Close the reproduced lineage gap in the producer/shared validator: record exact controller, SQL/pin, scope, accepted-thesis set, quote, macro, earnings, and ranking-policy identities that actually produced a funnel. Verify those identities, not just the latest independently healthy controller. Reuse existing lineage formats where available; do not invent a second finance canon.
3. Validate source-specific freshness against existing owner policy, including closed markets, holidays, timezone-aware timestamps, missing/future timestamps, and revised data. Where policy is undefined, return unknown/unavailable and route the decision; do not invent a permissive TTL.
4. Add negative cases for coherent controller replacement without funnel regeneration; thesis/scope/macro changes; malformed/missing/oversized artifacts; SQL locks/timeouts; pagination drift; path traversal and Windows junction/symlink escape; and optional versus required failures. Stable empty, unavailable, and stale-suppressed responses must remain distinguishable.
5. Verify no network calls, producer calls, canon writes or write-capable SQL. Test rollback-journal and live-style WAL fixtures: committed WAL data must be visible. Do not add `immutable=1` to a live changing database; do not require absence of legitimate pre-existing WAL/SHM files as a universal read-only proof. Prove no logical database mutation, documenting any SQLite bookkeeping separately.

**Technical gate:** contract/golden/replay/negative tests green; exact existing-name allowlist parity; bounded results at 32, 300 and 3,000 synthetic names; Main acceptance and scoped rollback. These are test sizes, not hard-coded production scopes.

### Phase 0B - Producer ordering and real runtime acceptance

1. Close the weekly ordering gap: applied renewal -> validated SQL/pin -> controller -> funnel -> usable weekly review. Prefer dependency completion and successful publication over merely shifting clock times; serialize competing producers and preserve last-known-good provenance without presenting it as current.
2. Route the exact schedule/payload proposal through `cron-automation-manager`: job IDs, payload/contract diff, failure and skip behavior, bounded retry, rollback, and the natural-run receipt to collect. Prefer one existing deterministic chain over duplicate jobs. Randall must approve schedule/payload changes.
3. Test interrupted/failed renewal and producer failures; never publish a usable dependent packet after an unsuccessful prerequisite. Reading through MCP must not repair or regenerate the packet.
4. After separately approved deployment, prove the **Gateway-owned consumer** loaded the intended server build and schemas. A fresh CLI probe proves a separate process, not the existing chat runtime. `openclaw mcp reload` is CLI-process-local; use the documented owner-approved runtime replacement path and verify changed tools in both a fresh and a previously active consumer. Gateway restart, if required, is owner-operated.
5. Preserve the earlier standalone probe receipt; the preceding combined CLI inspection had a transient state-SQLite stabilization error. Diagnose recurrence as runtime evidence without automatically weakening MCP data guards.

**Runtime gate:** doctor/probe, loaded-build and changed-tool exercises, policy-denial checks, exact tool-filter parity, and rollback proof. **Scheduled-reliability gate:** coherent next natural post-renewal packet and downstream review. Until that gate, label scheduled reliability unproven. Phase 1 measurements, schema design and independent proposals may proceed; do not promote dependent recommendation use as reliable prematurely.

### Phase 1 - Make current tools the preferred internal read path

1. Use the smallest adequate route:

   | Need | Preferred route |
   |---|---|
   | Supported band, thesis, funnel, thesis-review, gap-repair, renewal or ledger fact | Existing exact MCP tool; request only what the task needs. Interpret today's envelope limitations explicitly. |
   | Repeated deterministic producer/validation task | Existing model-free entry point/shared library, not an agent repeatedly calling MCP. |
   | Freshness repair, ownership, approval or workflow action | Named owner router/workflow; MCP reports evidence and cannot execute the action. |
   | Unstructured prior decisions/history/source discovery | Existing memory/wiki/FTS or exact file reads, not another generic memory/filesystem MCP. |
   | MCP transport unavailable | One bounded documented retry for a transient transport failure, then the authorized exact owner read. Preserve the same validation; a stale-data rejection is not permission to bypass it. |
2. Stage any reusable routing-procedure changes through Skill Workshop; do not directly patch active skills from this plan.
3. Exercise ticker lookup, system/recommendation review, and isolated-helper evidence retrieval. Verify effective tool visibility separately for Main, the intended specialist, and headless automation before relying on inheritance; unavailable tools are a capability gap, not a reason to broaden all agents' grants.
4. Measure metadata only: tool/schema/build IDs, result/fallback code, cold/warm elapsed time, returned bytes, retrieval/model round trips, retry count, and Main acceptance. Capture tokens only if authoritative, otherwise `unavailable`; bytes are not token counts. Never retain raw prompts/responses/tool payloads, sensitive arguments, secrets or account identifiers in the measurement ledger.

**Acceptance gate:** a matched comparison against the current exact-file/CLI route on the same input snapshots, including healthy, stale, missing, invalid and large-scope cases. Require zero correctness/authority regressions, zero stale-as-current escapes, and exact supported-field parity. Report sample size, cold/warm p50/p95, bytes, calls and acceptance/rework separately; a small sample is exploratory. Proposed promotion target: at least 25% fewer retrieval round trips or returned bytes with no more than 10% p95 retrieval-latency regression; otherwise retain the simpler route. These are proposed decision thresholds, not measured savings or an automatic promotion rule.

### Phase 2 - Add the smallest high-value finance tranche

Propose one tool at a time after the relevant technical/runtime gates; require natural-cycle proof before claiming scheduled recommendation reliability:

1. `get_finance_health()` - compact existing SQL/quote/controller/funnel/thesis/repair/renewal/ledger validation results, provenance and blockers. Inspect itself as well as dependencies: transport availability is not data health. Read known refresh windows from the governed contract, label predictions, and return unknown when unavailable. Do not run a full ledger verification on every health lookup; return its last validated result with age/coverage, leaving `verify_alert_ledger` an explicit bounded operation.
2. `get_ticker_brief(ticker)` - a deterministic join of validated current bands, quote/time, accepted-thesis summary, earnings, macro fit, relative strength and funnel stage/reasons. No new scoring, model-written thesis or provider fetch. Maintain per-field source/as-of and partial/suppressed semantics.
3. Bounded multi-ticker retrieval **if comparisons dominate measured use**: benchmark a batch against limited parallel single-ticker calls. A batch can share one snapshot/validation pass; blindly issuing hundreds of single-name calls is not an efficiency design. Enforce ticker/input/output caps, per-item status, stable order and shared-snapshot semantics; never return the whole universe by default.
4. `get_recent_changes(ticker=None, since_cursor=..., limit=...)` only after durable source history exists. Bind the cursor to a validated cycle/snapshot, use stable change IDs, and signal expired cursor/history gaps. Never infer changes from model memory or a mutable current-only JSON file. No implicit per-session bookmark writes in a read tool.

After measured demand, consider bounded `get_alert_history`, `get_band_history` and `get_evidence_lineage`. Prefer detail through an existing tool's narrow parameter over a new tool name when it preserves a clear schema and permission boundary.

Adding tool names requires both source/tests and an owner-approved update to the MCP tool allowlist. Code presence alone does not make a tool available.

**Acceptance gate:** typed input/output and compatibility tests; read-only/WAL-aware proof; same-version/freshness/replay/race tests; bounded bytes, memory and execution time; cold/warm and scale measurements; changed-tool live exercise; independent QA proportional to finance consequence; Main acceptance. Pin dependency versions and inspect tool/schema/annotation drift after upgrades; rollback the scoped release/config diff, never the whole shared configuration.

### Phase 3 - Workspace operations pilot, separate from finance

If recurring operations questions show retrieval overhead, draft a separate `veritas-ops` proposal over already-generated, redacted proof artifacts. This proposal need not wait for a finance weekly-cycle gate; deployment still needs its own approval and contract proof:

- status-card summary;
- named workflow summary and next action;
- active-lane summary;
- automation health summary;
- skill/runtime validation summary.

Start with only status-card summary and named-workflow summary/next action; add the other capabilities only if measured use justifies them. Reuse router outputs and validators rather than reimplementing workflow/authority rules. Do not duplicate a native tool that already answers the question more cheaply. It must not expose arbitrary file reads, shell/exec, generic SQLite, scheduler mutation, config/auth data, raw session transcripts, or secrets. Pilot one Main task and one isolated helper task before broader registration; missing helper capability remains explicitly unproven.

**Acceptance gate:** explicit owner approval for the new server/config entry, capability review, narrow allowlist, redaction tests, probe green, rollback, and no collision with existing routers.

### Phase 4 - Catalog efficiency and consumer capabilities, only on demand

Installed OpenClaw docs establish the following options; they are not enabled, verified, or authorized merely by appearing here:

| Capability | When it earns a pilot | Guard / proof |
|---|---|---|
| Tool Search / deferred schemas | Catalog/schema overhead is measured, not assumed; it may matter across the whole agent catalog, not just seven MCP tools. | Generic OpenClaw Tool Search is experimental; compare direct exposure with the smallest supported mode on the actual runtime/model. Codex-native discovery is a separate surface. No global enablement by this plan. |
| Code Mode | Several dependent reads/joins currently require model round trips and a typed composite is insufficient. | Generic OpenClaw Code Mode is opt-in and experimental, distinct from Codex Code Mode and shell `exec`. Use only the live callable schema; it does not make model-written code deterministic or replace shared validators. Approval and rollback required. |
| MCP resources | Bounded, immutable evidence/schema detail is reused by a named consumer. | Exact allowlisted resource IDs/URI templates and size limits; no arbitrary paths/URLs. Generated `resources_list`/`resources_read` utility tools also pass tool filters and require deliberate approval. Not a second workspace index. |
| MCP prompts | A named non-OpenClaw client needs a versioned prompt template. | Defer for internal use: skills already own procedures. Prompts/descriptions are untrusted data, never authority. Do not duplicate or silently override skills. |
| Existing dashboard/report surface | The user requests a report or dashboard using accepted evidence. | Reuse the response contract, visibly label partial/stale state, and verify actual rendering. No separate data store, assumed automatic MCP binding, or polling model loop. |
| MCP Apps | A named consumer needs an interactive view beyond an existing report. | Supported by installed docs but opt-in; dedicated sandbox origin/listener, same-server policy checks and renewed interaction authority. Config/network/runtime approval and rendering/security proof required. Not grounds to install a native plugin first. |
| External client / new data-source MCP | A named consumer or evidence gap is not met by current tools. | Separate auth/data-egress/least-privilege/supply-chain review. Existing Yahoo/SEC routes are not replaced merely to add an MCP. `openclaw mcp serve` is a conversation bridge, not automatic republication of `veritas-data`. |
| Native plugin | A concrete hook/command/provider/Gateway/UI integration cannot be met by approved existing surfaces. | Pin experimental SDK/version, narrow capabilities, owner approval and post-update compatibility/rollback proof. |

For any approved runtime pilot, preserve tool policy, session/agent denials and server filters; compare correctness, selection failures and end-to-end cost. Local stdio runs with host process permissions, not a security sandbox by virtue of being out-of-process. Never broaden grants to make a benchmark pass. Inspect effective request/connect timeouts and parallel-call hints before proposing changes; annotations/hints do not prove concurrency safety. Measure cold starts and retained per-session process/memory overhead before changing idle lifetime or transport. Repeated failures should fall back honestly, not cause reconnect or retry storms.

## Automation and Refresh Truth

Phoenix schedule snapshot carried forward from the earlier 2026-09-27 inventory; not independently re-inventoried in this plan review. Re-read exact job IDs, enabled state, payloads and contracts before drafting a change:

| Producer | Schedule | Role |
|---|---:|---|
| Intraday alert freshness refresh | Every 15 minutes, 06:00-13:45 Mon-Fri | Refreshes the shared controller. |
| Weekday morning alerts/recommendations refresh | 06:05 Mon-Fri | Dedicated morning chain. |
| Weekday post-close refresh | 13:20 Mon-Fri | Post-close chain. |
| Weekly fundamentals/thesis review | 08:00 Saturday | Refreshes thesis flags and currently invokes the funnel producer. |
| Weekly band renewal | 09:00 Saturday | May apply new reference levels after the Saturday funnel. |
| Weekly Main review | 09:30 Saturday | Consumes renewal, thesis, and funnel packets. |
| Sunday weekly alerts/recommendations refresh | 08:00 Sunday | Refreshes the controller but does not by itself prove the funnel producer reran. |

The cadence is evidence, not authority. Any repair must preserve contracts, fail closed, and prove the natural post-renewal run before promotion.

## Work Matrix

| Work item | Current state | Next action | Approval / stop line | Proof |
|---|---|---|---|---|
| Existing-tool contract and exact lineage | Pending; source gaps inspected, lineage failure reproduced synthetically | Specify Phase 0A source/schema/compatibility/test contract | Implementation needs its own scoped lease; no policy/canon mutation | Regression closes reproduced failure; bounded typed variants and replay proof |
| Post-renewal controller/funnel coherence | Pending; packet returned, recurrence unproven | Draft smallest governed dependency-chain repair | Randall approval before schedule/payload mutation | Natural post-renewal packet plus automation-contract validation |
| Current MCP adoption | Ready for bounded measurement, not blanket freshness trust | Compare existing tools against exact owner reads | No authority expansion; skill publication through Workshop only | Matched metadata-only scorecard and Main-accepted correctness |
| Runtime build and catalog proof | Pending specification | Bind source/schema identities to the actual Gateway consumer | Runtime/config changes require approval | Live changed-tool calls; old/fresh-session and denial tests |
| Finance health, ticker brief, bounded batch, changes | Proposal-only; ordered by validated demand | Start health after shared contract; history tools await history | Owner approval for new tool allowlist/config | Technical/runtime gates, measured benefit, Main acceptance |
| `veritas-ops` server | Demand-gated, independent of finance cadence | Measure status/workflow retrieval overhead | Explicit config/security approval required | Two-tool proposal, redaction/capability review and consumer proof |
| Tool Search/Code Mode/resources/Apps | Demand-gated; documented capabilities only | Select one measured bottleneck and smallest pilot | No inferred feature, config, resource or app authority | Runtime-specific comparison and rollback |
| External MCP/native plugin | Deferred | Require named consumer or unmet evidence/integration need | Network/plugin/auth/runtime approval required | Consumer contract, security review and rollback |

## Blockers and Trust Gaps

- Strict three-consecutive-day probe evidence from the original trial was not recorded for 2026-09-24 and 2026-09-25; current operational proof is green but historical acceptance evidence is partial.
- The earlier 89-job inventory found no dedicated scheduled post-renewal producer; that count is a dated observation, not a current invariant. Exact-input lineage also remains incomplete independently of the schedule gap.
- Confidence units have changed across historical artifacts; the MCP must declare the current scale instead of returning an unlabeled number.
- Dynamic-scope and scale-out work is active elsewhere. MCP expansion must consume the governed live scope and must not reintroduce a static 32-name constant.
- Current workspace has unrelated dirty Phase 4 work and leased lanes. Later implementation must acquire its own non-overlapping writes. The documentation review's active admission passed; global lane accounting remained error-grade. An expired Phase 4 slice-1a lease was marked blocked for safety, not completed or accepted, after its owning session failed the coordination request; its owner must review and re-lease before resuming.
- No matched latency/token study, helper/headless capability proof, new-schema runtime proof, or independent implementation QA was performed in this documentation review. No performance improvement is claimed yet.

## Next Action

Prepare one bounded Phase 0 change packet with separate approvals: **A**, existing-tool schema/bounds/exact-lineage fixes and regression/compatibility tests; **B**, exact producer ordering, affected automation contracts, Gateway activation proof, rollback and next natural-cycle receipt. Start the existing-seven-tool matched baseline alongside proposal preparation; it requires no new server or permissions. New implementation/deployment is a subsequent task, not authorized by this documentation update. Do not mutate schedules, allowlists, runtime, configuration or canon from this plan.

## Key Files and Proof Routes

- `scripts/veritas_mcp_server.py` - live MCP server.
- `scripts/test_veritas_mcp_server.py` - MCP safety and behavior tests.
- `scripts/recommendation_funnel.py` - recommendation producer and coherence guards.
- `scripts/weekly_thesis_review.py` - current scheduled funnel caller.
- `scripts/run_alerts_recommendations_chain.py` - controller producer and shared-output promotion.
- `06. Playbooks/OpenClaw Extension Roadmap - MCP Plugins SDK - 2026-09-23.md` - historical extension decisions; its zero-server headline and `mcp remove` rollback examples need reconciliation (follow-up documented here only; no separate task created). Current installed docs use `openclaw mcp unset`; do not execute rollback from a stale note.
- `06. Playbooks/Project Continuity/Phase 4 Proposal Route Acceptance - 2026-09-26.md` - current recommendation/freshness trust boundaries.
- `06. Playbooks/Project Continuity/Phase 4 Unified Monitoring and Scale-Out Plan - 2026-09-27.md` - dynamic-scope and scale target.
- `tmp/alert-level-freshness-controller.json` and `tmp/recommendation-funnel.json` - current derived evidence, never authority.
- `tmp/mcp-plan-review-20260927/plan-before.md` and `review-proof.json` - original plan preimage and bounded review receipt; temporary supporting proof, not new canon.

Product capability sources (installed docs root: `C:\Users\Veritas\AppData\Roaming\npm\node_modules\openclaw\docs`): `tools/mcp.md`, `cli/mcp/registry.md` (resource/prompt projection, filters, session lifetime and process-local reload), `tools/tool-search.md`, `tools/code-mode.md`, and `cli/mcp/apps.md`. Recheck after a host update. A documented capability is not proof it is exposed to this session.

Validation routes:

```powershell
python -B -m pytest -p no:cacheprovider scripts\test_veritas_mcp_server.py -q
openclaw mcp list --json
openclaw mcp doctor veritas-data --probe
openclaw mcp probe veritas-data
```

Run tests against contained fixtures with production artifact pre/post checks. Add neighboring producer/shared-validator regressions for implementation acceptance. No validator result substitutes for loaded Gateway-build proof or natural-cycle evidence. Runtime, config, or scheduler rollback remains a separately approved scoped operation.

## Stop Lines

- No generic SQL, arbitrary filesystem/search, write/apply/delete, workflow-execution, or scheduler-control MCP tools.
- No raw prompts, responses, transcripts, credentials, private account data, or unrestricted telemetry retention.
- No finance-canon, tier, thesis, alert, recommendation-policy, portfolio, account, capital, order, or execution mutation through MCP.
- No plugin, config, tool-allowlist, network exposure, credential, runtime, service, or schedule change without Randall's explicit approval.
- Generated packets and MCP outputs are evidence only; exact owner artifacts and validators retain authority.
