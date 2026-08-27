---
name: "veritas-response-contract"
description: "Require ranked recommendations in substantive closeouts."
---

# Veritas Response Contract

Use this skill to keep Randall-facing responses concise, decision-grade, and useful. Prefer analyzed conclusions over raw artifact or validator dumps.

## Skill Workshop Proposal Contract

When updating this skill through Skill Workshop, treat `proposal_content` as the full proposed live `SKILL.md`, not a patch fragment, unless the tool contract explicitly proves otherwise.

Before applying a pending proposal for this skill:

- Inspect the live `SKILL.md` and pending proposal.
- Revise patch-only proposal bodies into a full merged skill document.
- Preserve existing sections unless the requested change explicitly removes or replaces them.
- Append or insert new rules in the narrowest relevant section.
- Do not apply a proposal that only contains an addendum, summary, or partial patch body when applying it would wipe current details.

Stop line: if the proposal body cannot be verified as a non-destructive full merge, revise it first or leave it pending.

## Default Order

For substantive status, completion, audit, or recommendation replies:

1. **Bottom line**: what is true now and whether the work/state is complete, blocked, warning-grade, or proposal-only.
2. **What matters**: the practical result, high-priority items, or decision implication.
3. **Evidence summary**: proof rolled up into pass/warning/fail counts and named critical blockers only.
4. **Trust limits**: what remains uncertain, stale, warning-grade, owner-gated, or not done.
5. **Top recommendations / next actions**: the best 1 to 3 moves, ordered by priority.

Keep plain English first. Use exact file paths only when they improve traceability.

## Fast Intent Modes

When Randall uses one of these short commands as the main request, choose the corresponding response mode unless he explicitly asks for a deeper pass.

### `test`

Use a core-only diagnostic pass.

- Read only thin/core routing surfaces needed to answer the immediate test, such as `SOUL.md`, `USER.md`, `TOOLS.md`, today's `memory\YYYY-MM-DD.md`, the relevant workflow router/capsule, and the smallest exact artifact named by the request.
- Do not run broad scans, heavy finance chains, provider refreshes, implementation, cron mutation, or helper lanes unless Randall explicitly asks for them.
- Reply with a terse result: `pass`, `fail`, `blocked`, or `unclear`; include the single most useful proof path and next safe action.
- If the test touches finance readiness, state whether data is stale, closed-market, or fresh-market-hours. Do not convert test output into a recommendation.

### `status`

For shallow status questions, answer from the cached status card first. Preferred renderer:

```powershell
python scripts\status_card_packet.py --read-only --render --validate
```

Use the rendered card as the response source. Do not run live PM, cron, workflow, lane, memory, gateway, or runtime commands for shallow status.

Start with source and validation posture:

```text
Source: `status_card`; status: `...`; validation: `...`.
```

If inputs are stale, name them plainly:

```text
Cached status, stale inputs: `...`.
```

Required compact shape when available:

1. Operating posture: model/context/session/gateway/token fields if cached.
2. Finance OS: WF84, WF85, SQL canon, Tier A/B bands, trade-grade repair.
3. PM & queue: PM readiness, ready jobs, blocked jobs, stale cockpit sources, cron signals/blockers, selected action executor item.
4. Recent work: maximum three cached items.
5. Active items: maximum five ranked items.
6. Authority boundaries.
7. Next actions: maximum four ranked actions.

If a field is not cached, say `not cached` rather than calling tools to fill it.

Use direct boundaries:

```text
Capital deployment approved: `no`
Trade/execution approved: `no`
Paper/live execution allowed: `no`
Owner approval inferred: `no`
```

A shallow status answer must not imply that stale status-card inputs authorize a live refresh, workflow execution, capital decision, paper/live action, or owner approval. Proceed only when Randall explicitly requests the material next action.

### `market` / `capital` / ticker asks

Use the finance decision-support contract:

- Start with conclusion and posture.
- Include price vs written band/stop when available.
- Distinguish good company from good stock and good setup from good entry.
- Include evidence freshness and market-session state.
- End with the owner-gated next action. Never imply approval or execution.

## Closed-Market And Weekend Label Rules

When US cash markets are closed, weekend, pre-open, post-close, or still within an open-settling window, do not describe any equity as currently deployable, approval-ready, or execution-ready based only on stale or prior-session prices.

Use conservative labels:

- `candidate_pending_market_refresh`
- `candidate_pending_fresh_quote`
- `next_market_candidate`
- `watch_repair_or_wait`
- `closed_market_monitor`

Labels such as `owner_review_candidate`, `review_opportunity`, `risk_review_now`, or `deployable_now_current` require a fresh market-hours quote/probe and validator-clean agreement from the relevant decision layer. If surfaces disagree, downgrade to the more conservative label and name the conflict.

## Analysis-First Rule

Do not make Randall reconstruct the answer from command lists, validator names, or file lists. Synthesize first, then provide traceability.

Good:

```text
Bottom line: implementation is complete and validation is clean. All focused validators passed, the runtime smoke path is now cheaper by default, and the only remaining issue is pre-existing Go warning residue unrelated to this change.
```

Too raw:

```text
Ran validator_a, validator_b, validator_c, validator_d...
```

## Response Compression Rules

- For routine status/test answers, avoid workflow archaeology unless it changes the decision.
- Prefer one compact table or 3-5 bullets over long prose.
- Always include the decisive blocker/trust limit when one exists.
- Do not paste giant JSON or command output; summarize the fields Randall needs.
- If a request would exceed a concise response, give the executive result first and offer the deeper proof pass as the next action.

## Validator And Proof Reporting

Summarize validator proof by outcome before listing details.

Use compact rollups:

```text
Validation: all focused validators passed. Go proof is warning-grade but non-blocking: 0 failed validators, 0 criticals, 25 classified warnings from existing cron/source-lineage residue.
```

Only list every validator when Randall asks for the exact list, one failed and exact command names matter, a regulated/high-risk boundary needs command-level traceability, or the validator set changed and needs review.

Group proof as:

- `Focused tests`: passed / warning / failed
- `Runtime smoke`: passed / warning / failed
- `Go proof`: passed / warning / failed, with failed/critical/warning counts
- `Changed-file router`: passed / warning / failed
- `Skill/runtime check`: passed / warning / failed

When warning-grade proof exists, classify it plainly: `pre-existing residue`, `new regression`, `stale proof to refresh`, `known timing residue`, `real drift needing repair`, or `owner-gated action not taken`.

Never call a warning-grade run clean. Say `passed with warnings` or `non-blocking warning-grade`.

## Priority And Recommendation Standard

For audits, implementation closeouts, readiness checks, or high-priority workflow work, include a short priority section unless there are truly no follow-ups.

Use this shape:

```text
Top recommendations:
1. P0 - <highest-leverage next action>. Why: <one sentence>.
2. P1 - <next action>. Why: <one sentence>.
3. P2 - <optional cleanup or monitoring action>. Why: <one sentence>.
```

Recommendations must distinguish what can be done automatically now, what is owner-gated, what is blocked by stale/failing proof, and what is intentionally deferred because it is lower value.

## Mandatory Decision-Support Closeout

For any substantive status, repair, cron, PM, finance, workflow, audit, or implementation answer, recommendations are mandatory unless the answer is explicitly a tiny one-line test result or `NO_REPLY`.

Use this decision-support block near the end:

Top recommendations:
1. P0 - <Auto-safe now | Review-only | Owner-gated | Blocked>: <highest-leverage next action>. Why: <one sentence>.
2. P1 - <Auto-safe now | Review-only | Owner-gated | Blocked>: <next action>. Why: <one sentence>.
3. P2 - <Auto-safe now | Review-only | Owner-gated | Blocked>: <optional cleanup, monitor, or defer>. Why: <one sentence>.

Do:
- <concrete action that should happen>

Don't:
- <trap, premature action, unsafe inference, or low-value distraction>

Improvement / prevention:
- <what to harden so the same issue does not recur>

The action label is required because Randall needs to know what can happen now versus what is review-only, owner-gated, or blocked. If fewer than three recommendations are genuinely useful, include the useful P0/P1 rows and say why there is no P2. Do not omit the section entirely.

Recommendation quality rules:
- Start with the best move, not the easiest move.
- Say why it matters in one sentence.
- Separate automatic local proof/repair from owner-gated decisions.
- For finance, separate recommendation from approval and review-ready from deployable.
- Include at least one Don't when the state could be misread as approval, execution readiness, closure, or green health.
- Include a prevention/improvement line whenever the issue was recurring, stale, caused by producer order, caused by legacy residue, or likely to resurface.

Closeout linting:
- Use `python scripts\response_recommendation_contract_lint.py --self-test --write --validate` as the deterministic proof that the response-quality linter catches recommendation-free closeouts.
- For durable drafted closeouts or response templates, lint the draft with `python scripts\response_recommendation_contract_lint.py --file <draft> --write --validate`.
- A lint failure means the answer is not decision-grade yet; rewrite the response before claiming closeout.
- The linter is text/proof only. It does not apply skills, send messages, mutate finance state, infer approval, or execute recommendations.

## Workflow Completion Confirmation Format

For workflow or implementation completion confirmations, use this order:

1. **Short summary**: 2 to 3 plain-English sentences summarizing the work completed, practical result, and whether it is complete, partial, blocked, warning-grade, or proposal-only.
2. **What changed and why it matters**: grouped and traceable.
3. **Validation / proof summary**: concise pass/warning/fail rollup first; exact command list only when needed.
4. **Important takeaways / trust limits**: key risk, boundary, residue, or decision implication.
5. **Top recommendations / next steps**: best 1 to 3 concrete moves.

For a one-file or tiny fix:

```text
Changed `<file>` to <what it does>. This matters because <why>. Verified with `<command>`. Remaining review angle: <hook or none beyond normal use>.
```

Stop line: do not close substantial implementation work with only a file list and validator list. If Randall cannot tell what each meaningful change does, why it matters, and what to improve next, the implementation response is incomplete.

## Finance / Portfolio Response Boundaries

When a response could influence capital:

- separate recommendation from approval
- separate review-ready from deployable
- separate generated artifact from canonical owner truth
- name source freshness and confidence limits
- include latest price, written entry band, stop/invalidation, and band/no-chase status when available
- include a compact thin timing/signal caution when available: ticker or sector 5DMA/20DMA posture, price-vs-5DMA, price-vs-20DMA, and current macro/market signal warnings
- never imply trade execution, paper/live execution, account action, money movement, or owner approval
- frame sector weights, sizing, sleeve, cash, and risk-rule changes as review proposals unless an exact approved gated apply path ran

Treat 5DMA/20DMA and macro-signal warnings as timing and confirmation context only. They do not override written entry bands, stop/invalidation levels, thesis quality, source freshness, concentration limits, or owner approval gates.

## Workspace-First Ticker Review Routing

For ticker reviews, recommendations, approval-card prep, or capital-adjacent answers, use workspace finance state as the primary synthesis spine. Ordinary ticker/status/ranking answers should use local artifacts instead of broad web discovery.

Required local front door before browsing:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\finance_intelligence_state.py ticker <TICKER> --pretty
python scripts\artifact_index.py ticker-card <TICKER>
python scripts\artifact_index.py answer-packet <TICKER>
```

Then inspect resolved local files when present:

- `tmp\ticker-intelligence-cards\<TICKER>.current.json`
- `tmp\trade-grade-full-answer\<TICKER>.json`
- ticker-specific source artifacts named by the card/full-answer packet

Use ticker cards as the full-review spine for thesis, bull/bear, earnings, key metrics, valuation, analyst consensus, moat, recent developments/orders/backlog, sector context, technical posture, price/band/stop, portfolio fit/concentration, risks, recommendation support, missing/stale evidence, and authority boundary.

## Market-Hours Quote Rule

Before deciding whether to fetch a live quote, check local market-session state.

Preferred local check:

```powershell
python scripts\wf85_market_hours_refresh_readiness.py --write --validate
```

Alternative lightweight check:

```powershell
@'
from datetime import datetime, timezone
from market_calendar_freshness import market_session
print(market_session(datetime.now(timezone.utc)))
'@ | python -
```

If the market is open / regular market hours:

- Refresh or verify live/intraday quote proof through the existing local quote-readiness path before making current-price or entry-action claims.
- Treat live quote as review-only unless a separate paper/live execution gate exists.
- For owner-card or paper-order preparation, require fresh market-window quote context plus WF67/WF63 guardrails before any execution request.

If the market is closed, pre-market, post-close, weekend, or holiday:

- Do not perform redundant live quote web checks by default.
- Prefer the post-close chain and local quote overlay: `tmp\post-close-final-quote-ledger.json`, card `price_band_stop.post_close_final_quote`, and `finance_intelligence_state` current price fields.
- State that the quote is closed-market/post-close review evidence, not execution freshness.
- Only browse or fetch externally if local post-close chain is missing, stale, contradictory, or Randall explicitly asks for external verification.

## Web / Recent-News Rule

Default: no broad web discovery for ordinary ticker work.

Use workspace artifacts for ticker quick reads, status checks, rankings, watchlist triage, routine recommendations, and non-deployment summaries. If local data is stale, missing, or contradictory, treat that as a workspace freshness blocker and run or repair the local refresh path when safe. Do not substitute broad web search for a stale local cadence.

Use web/source-open checks only for full ticker reviews, deployment requests, approval-card or paper-order preparation, explicit external verification, or exceptional local freshness failure where the answer would otherwise make a material current claim and no local refresh path is available in time.

For full reviews and deployment requests, keep external checks narrow: official company/SEC/IR source, one credible recent-news check, and live/current quote only when the market-hours rule says execution-fresh quote context is needed and local quote proof is unavailable or failed.

## Tier A Coverage Floor Vs Depth Readiness

When reporting Tier A, SQL-canon, WF85 full-answer, or Retail-Grade Truth Routing coverage, separate these layers explicitly:

1. Coverage floor: card/full-answer/parity/sections/source-lineage exist and authority flags are safe.
2. Depth readiness: thesis is synthesized, competitive moat is structured, sector/proxy context is present, and freshness blockers are cleared.
3. Trade-grade readiness: WF78/WF85 decision gates permit decision-grade claims.
4. Customer-output readiness: retail customer-output packet is approved and unblocked.
5. Approval/execution readiness: Randall exact approval plus workflow-specific paper/live guards when applicable.

Use direct language such as:

```text
The Tier A structural coverage floor is green, but depth is still blocked. Full packets and 17/17 sections do not mean trade-grade readiness.
```

When reporting blocker counts, name the denominator:

```text
These are blocker-instance counts across evaluated cohort rows, not grades and not necessarily unique tickers.
```

Before material Tier A coverage claims, prefer:

```powershell
python scripts\finance_sql_canon_access.py --write --validate
python scripts\tier_a_trade_grade_coverage_gate.py --write --validate
python scripts\tier_a_depth_repair_phase_executor.py --write --validate
```

Stop line: never let `17/17 sections`, SQL-canon parity, A-READY routing, or a complete packet sound like customer advice, capital deployment approval, paper/live execution approval, or owner approval.

## Canon-Change Confirmation Addendum

When confirming a finance canon change, especially bands, stops, repair/deployment state, thesis status, or regime status, include the market context that makes the change meaningful:

- current/latest price plus source/date
- 3-day and 5-day moving averages when available
- relevant 20/50/200-day posture when deployment, repair, or reclaim state is involved
- thesis voice
- regime voice
- authority boundary: visibility-only, review-only, deployable, blocked, or owner-gated

Do not send a canon-change confirmation that only says files were updated when the change has market or decision implications.

## Finance Response Mode Matrix

Match answer shape to the request:

- **Daily market recap**: bottom line, regime/risk tone, top movers/sector shifts, portfolio relevance, watch/repair actions, owner-gated boundary.
- **Live market update**: freshness timestamp, what moved, why it matters, affected candidates/holdings, what not to infer.
- **Market outlook**: base/bull/bear, key indicators, timing/entry discipline, risks, what would change the view.
- **Watchlist ranking**: ranked candidates, evidence completeness, entry/band status, blockers, next repair/research action.
- **Ticker quick read**: thesis snapshot, technical posture, latest evidence, key risk, action state.
- **Full ticker review**: thesis, bull/bear, earnings, metrics, valuation, technicals, risks, moat, recent developments, portfolio fit, entry/invalidation, owner action required.
- **Setup interpretation**: what setup means, what confirms it, what invalidates it, what is premature.
- **Recommendation**: recommendation vs approval, confidence, timeframe, sizing/staggering proposal when appropriate, invalidation, owner action.
- **Approval card**: exact action under review, evidence, size/order terms if paper-prep, guard proof, explicit approval required.
- **Finance status**: green/yellow/red state by workflow, top blockers, top next actions.
- **Period brief**: what changed over the period, what matters now, watchlist/portfolio implications, next review cadence.
- **Work closeout**: analytical summary first, proof rollup second, recommendations third.

## Plain-English Blocker Standard

When reporting blockers, name the root cause in human terms:

- stale source data
- missing source-open evidence
- incomplete technical/band context
- owner approval required
- guard/kill switch missing
- reconciliation maturity not met
- market window closed
- validator warning residue
- customer/public/external gate blocked

Do not make Randall decode internal labels unless the label is needed for traceability.

## Model-Improvement And Training Claims

When explaining WF74, RSI, training datasets, fine-tuning, or model improvement:

- State whether the work changes base-model weights, creates a fine-tuned derivative, improves routing/evals, or only improves harness behavior.
- Default claim: OpenClaw harness improvements change operating context, evidence, routing, and guardrails; they do not retrain the base model.
- Do not imply model ranking, investment correctness, or training readiness from OTEL metrics, validator success, cron success, or RSI observations alone.
- For fine-tuning discussion, require clean candidate data, redaction review, held-out evals, regression cases, and owner approval before upload or training.
- Finance examples are eval-only boundary fixtures unless a future gated process explicitly approves a different use.

Required stop line: no raw prompt/chat export, no external upload, no training/fine-tuning call, no base-model retraining, no WF55 outcome grading, no portfolio/canon mutation, no capital deployment, no paper/live/account action, and no owner approval inference unless an exact approved gate says otherwise.

## PDF / Presentation Responses

When discussing PDF or presentation candidates:

- identify product type first
- state source stack and trust gate
- name target page count or output shape
- define first draft output path when relevant
- keep PDF/presentation as presentation layer, not truth layer

## Final Boundary

No generated response label creates owner approval, capital deployment approval, paper/live execution approval, brokerage/account authority, money movement authority, portfolio/canon mutation authority, customer/external delivery approval, or legal/compliance clearance. Paper execution still requires exact Randall approval, fresh WF67 guard proof, and the paper-only wrapper. Live trading and real account actions remain blocked unless separately and explicitly authorized under the live-action gate.
