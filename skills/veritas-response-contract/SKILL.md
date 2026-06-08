---
name: veritas-response-contract
description: Keep Veritas user-facing responses consistent across sessions. Use for workflow completion confirmations, status replies, closeout summaries, audit/results reports, file-change summaries, and decision/recommendation responses that need concise proof, risk, and next action formatting.
---

# Veritas Response Contract

Use this skill to keep Randall-facing responses consistent, decision-grade, and easy to scan.

## Default order

For substantive status, completion, audit, or recommendation replies:

1. **Conclusion** — what is true now.
2. **Changes / evidence** — what changed and where proof lives.
3. **Trust limits** — what remains uncertain, blocked, stale, or owner-gated.
4. **Next action** — the concrete next move.

Keep plain English first. Use exact file paths only when they improve traceability.

## Workflow completion confirmation format

For WF completion confirmations, use this order:

1. **Short summary** — 2 to 3 plain-English sentences summarizing the work completed and the practical result. Put this before the file-change table.
2. **File-change table** — grouped and traceable.
3. **Validation / proof** — tests, validators, inspection, or named blocker.
4. **Important takeaways** — what Randall should remember or care about.
5. **Suggested next steps / recommendations** — the best 1 to 3 concrete moves.

Recommended table:

| File / area | Change applied | Why it matters | Proof / status |
|---|---|---|---|
| `path/to/file.md` | Short verb phrase | Plain-English purpose | Test, validator, or inspected state |

Rules:
- Use **3 to 4 columns maximum**.
- If many files changed, group related files by area instead of dumping a huge row-per-file table.
- The opening summary should be concise but not vague; say what changed, why it matters, and whether the workflow is complete, partial, or blocked.
- The ending section must include:
  - **Important** — the key risk, boundary, result, or decision implication.
  - **Recommended next steps** — concrete next moves, ordered by usefulness.
- Keep recommendations owner-gated when finance, portfolio, allocation, or execution authority is involved.
- Do not claim completion unless every requested item is handled or explicitly marked `[blocked]`.

## Finance / portfolio response boundaries

When a response could influence capital:
- separate recommendation from approval
- separate review-ready from deployable
- when providing portfolio allocation/current holdings, include current/latest available price, written entry band, stop/invalidation level, and band-position/no-chase status when available; if unavailable, say unavailable rather than omitting risk context
- name source freshness and confidence limits
- never imply trade execution or owner approval
- distinguish live trade/account authority from Randall's Alpaca paper-only approvals: 2026-05-17 submit/cancel and 2026-05-19 advisor-derived paper buy/sell packages; paper execution still requires `wf67-paper-trading-operator` / WF63/WF67 guardrails, scoped paper-trade/pilot/advisor-package artifacts, fresh kill switch, audit log, paper/live isolation proof, and main-session capital-package notification
- frame sector weights as **review proposals** unless an exact validator-backed gated apply is explicitly approved
- for planner/advisor-style answers, include the known planning constraint that matters most: time horizon, liquidity/cash need, drawdown tolerance, concentration, tax/liquidity, or sleeve boundary
- treat tax, legal, retirement-account, insurance, estate, debt, employment-income, and outside-account issues as constraints/referral items unless Randall supplies exact facts and asks for non-professional scenario framing
- block probability, expected-return, win-rate, percent-likelihood, calibrated-score, and model-ranked language unless WF55 retained-outcome validation explicitly allows it; otherwise say heuristic-only / uncalibrated / scenario-weighted
- use `veritas-financial-planning-pass` when the response needs holistic planner/advisor synthesis rather than a single-ticker or single-workflow answer

### Market-state intelligence hardening

For broad market, macro, finance-stack, portfolio-status, or capital-action intelligence to Randall, include a compact balanced market-state block before any recommendation.

Required checks when current artifacts exist:
- **Market state:** use `tmp/market-state.json`, `tmp/macro-regime.json`, `tmp/regime-scores.json`, and `tmp/macro-judgment-draft.json` before broad regime claims.
- **Source/trust state:** state whether the evidence stack is `ok`, `warning`, `degraded`, stale, missing, or manually dependent.
- **Macro/event context:** name CPI/PPI/PCE/labor/rates/dollar/energy/geopolitical items that matter now, using `tmp/macro-metrics-current.json`, `tmp/macro-event-calendar.json`, and the macro judgment draft when available.
- **Portfolio implication:** connect regime context to patience, selectivity, repair posture, concentration risk, or deployment readiness, using `tmp/deployment-readiness-surface.json` when available.
- **Recommended capital posture:** frame as owner-gated posture only, such as hold cash, selective review, prepare packet, wait for event, stagger only after fresh gates, or avoid chase. Do not turn this into trade/account execution authority.
- **Counterweight:** include at least one serious bull/base/bear or upside/downside caveat when recommending posture changes.
- **Boundary:** explicitly preserve review-only / owner-gated / no live trade/account / no paper execution unless an exact separate WF67 approval path is active.

If `tmp/macro-judgment-draft.json` is missing or its validation is not `ok`, do not present a final macro judgment as automated truth. Say the market view is partial and identify the missing/stale dependency.

## Financial status opportunity radar

For normal financial status responses, include a compact **Opportunity radar** block when WF60/WF61 or current research artifacts have fresh material signal. Keep it short so it refreshes Randall without burying the main portfolio answer.

Default content:
- **Improving leadership:** sectors/factors from `tmp/research-freshness-opportunity-review.*` / `tmp/sector-expansion-board.*`
- **Underexposed lanes:** sectors or sleeves where portfolio exposure is thin but evidence is only review-level
- **Promotion-review queue:** names that deserve packet review, not automatic promotion
- **Diversification feed:** WF61 small/mid/fund/commodity cues, especially whether signal is improving, neutral, deteriorating, or tactical-only
- **Action boundary:** one sentence saying review-only / owner-gated / no trade authority / no ungated portfolio mutation authority

Do not include this block when artifacts are stale, missing, or unchanged unless Randall specifically asks for a broad status refresh. If source artifacts are degraded, say so plainly and downgrade the opportunity language to “review cue,” not “opportunity-ready.”

## WF78 tier-funnel response pattern

For WF78 routing, monitoring, or promotion replies, explain promotion by tier question and authority boundary, not by vague quality language.

Use this order:
1. **Current state** - the live counts/caps and whether the relevant gate artifacts are trusted.
2. **Transition question** - D->C asks monitorability, C->B asks research-worthiness, B->A asks scarce Tier A superiority.
3. **Gate result** - name the exact verdict: `eligible_for_admission`, `eligible_for_owner_approval`, `blocked_missing_evidence`, `blocked_decay_state`, `blocked_batch_nomination_limit`, `blocked_tier_b_cap`, `blocked_not_validated`, `blocked_tier_a_full_no_challenger_win`, or other actual gate verdict.
4. **Owner packet** - state whether the packet is actionable now, needs evidence, needs validation, state repair, capacity/competition blocked, routed elsewhere, or no-action.
5. **Boundary** - state what the result does not authorize.
6. **Next action** - give the next evidence, packet, gate, or owner decision required.

Plain-English tier meanings:
- Tier D = can we trust the identity/source/provider state enough to watch it?
- Tier C = is it monitorable and worth cheap radar?
- Tier B = is it worth scarce research time?
- Tier A = is it one of the best scarce deployment-quality names?

Do not say a ticker was promoted, admitted, deployment-ready, paper-ready, or portfolio-ready unless an approved owner decision and the proper gated apply path actually exist. A clean gate can produce eligibility or an owner packet; it does not make the owner decision.

### Leadership/research pass carry-forward

When a research pass identifies improving leadership, underexposed lanes, or promotion-review candidates, later finance responses should carry the lesson forward until the next fresher WF60/WF61 packet replaces it. Prefer the machine digest when present: `tmp/research-freshness-opportunity-review.json -> response_recommendation_digest`.

Response pattern:
- **Leadership improving:** sectors/factors that improved, with freshness/degraded-state caveat.
- **Best review candidates:** names in portfolio-review / conditional-watch / blocked-or-deferred buckets.
- **Why not automatic:** exact blocker such as below-stop, earnings window, concentration, stale source, missing thesis, or owner gate.
- **Boundary:** no promotion, sizing, sleeve/cash/risk-rule, deployment, trade/account action, or owner approval is inferred.

Do not turn “improving leadership” into a probability, expected-return, regression, or win-rate claim unless WF55 says retained outcome history supports that language.

## Canon-change confirmation addendum

When confirming a finance canon change, especially an Execution Board, entry-band, stop, watch/repair/deployment-state, or thesis/regime-status change, include a compact market-context block before or beside the file/proof summary.

Required context when available:
- current or latest reliable price, with date/source
- 3-day and 5-day moving averages, or say unavailable if the current artifact stack does not provide them
- relevant 20/50/200-day posture when the change touches deployment, repair, or reclaim state
- thesis voice: one sentence on whether the thesis is intact, improving, deteriorating, or merely watchable
- regime voice: one sentence on how the current macro/sector/portfolio regime affects priority, patience, or risk
- authority boundary: whether the change is visibility-only, review-only, deployable, blocked, or owner-gated

Do not bury the answer in file-change tables alone. Randall should be able to tell in one glance why the canon changed, whether the setup is actually actionable, and what regime/thesis context argues for or against urgency.

## PDF / presentation responses

When discussing PDF candidates:
- identify product type first
- state source stack and trust gate
- name target page count
- define the first draft output path
- keep PDF as presentation layer, not truth layer

## Model-improvement and training claims

When explaining WF74, RSI, training datasets, fine-tuning, or model improvement:

- State whether the work changes base-model weights, creates a fine-tuned derivative, improves routing/evals, or only improves harness behavior.
- Default claim: OpenClaw harness improvements change operating context, evidence, routing, and guardrails; they do not retrain the base model.
- Do not imply model ranking, investment correctness, or training readiness from OTEL metrics, validator success, cron success, or RSI observations alone.
- For fine-tuning discussion, require clean candidate data, redaction review, held-out evals, regression cases, and owner approval before any upload or training call.
- Finance examples are eval-only boundary fixtures unless a future gated process explicitly approves a different use.
- User-facing answers should separate: `implemented`, `review-only candidate`, `needs redaction`, `blocked`, and `requires owner approval`.

Required stop line for these topics: no raw prompt/chat export, no external upload, no training/fine-tuning call, no base-model retraining, no WF55 outcome grading, no portfolio/canon mutation, no capital deployment, no paper/live/account action, and no owner approval inference unless an exact approved gate says otherwise.
