---
name: veritas-financial-planning-pass
description: Produce a bounded Veritas financial-planning/advisory synthesis that combines Randall's goals, constraints, portfolio posture, macro, fundamentals, technicals, risk, and probability-readiness gates into owner-gated portfolio recommendations. Use when Randall asks for financial-planner/advisor behavior, holistic portfolio guidance, allocation posture, capital-deployment priorities, scenario/stress planning, or intelligence-driven portfolio adjustment recommendations.
---

# Veritas Financial Planning Pass

## Purpose

Turn the Veritas finance OS into a bounded planner/advisor loop: synthesize goals, constraints, portfolio posture, market intelligence, and risk into practical recommendations while preserving owner-gated execution.

This skill does **not** authorize live trades, live brokerage/account actions, money movement, credential handling, owner-approval inference, tax/legal advice, insurance/estate advice, or ungated portfolio mutations. Randall's 2026-05-17 Alpaca paper-only submit/cancel approval is a separate simulation-lane authority and must route through WF63/WF67 guardrails, not planner output alone.

Plain-language posture: Veritas is Randall's bounded financial advisor / financial-planning analyst inside the workspace: it may synthesize advice, recommend portfolio adjustments, and route or perform standing-approved workspace portfolio/canon maintenance when exact WF64-style gates pass. Veritas is not a broker, custodian, accountant, attorney, tax adviser, or live execution system, and it cannot place live trades, move money, change real brokerage/account state, or infer owner approval for external live action. Paper trading is allowed only under the explicit Alpaca paper-only approval and WF63/WF67 controls.

## Required inputs

Read the smallest relevant stack:
- `USER.md`, `SOUL.md`, and `MEMORY.md` only when durable preferences/authority matter
- `03. Portfolio/Portfolio Snapshot.md`
- `03. Portfolio/Execution Board.md`
- `04. Research/Coverage and Watchlist.md`
- `07. Risk/Risk Rules.md`
- current macro/weekly posture, especially `02. Markets/Weekly Macro Snapshot/*.md` or `tmp/macro-regime.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
- `tmp/capital-deployment-recommendation-validation.json`
- `tmp/probability-readiness-report.json` and validation when probabilities/regression are mentioned

Use live artifacts over memory for mutable facts.

## Planner constraint block

Before recommendations, identify known and unknown constraints:
- time horizon
- liquidity/cash needs
- income needs
- drawdown tolerance
- concentration limits
- tax/liquidity constraints when known
- core/tactical/speculative sleeve boundaries
- current cash/dry-powder context if known
- owner-specific stop lines or pending decisions
- tax, retirement-account, estate, insurance, debt, employment-income, and outside-asset constraints when known

If a material constraint is unknown, do not invent it. State the assumption and keep the recommendation conditional. Do not ask Randall for every constraint by default; use known workspace facts, then ask only for the one missing constraint that would materially change the recommendation.

## Advisory synthesis workflow

1. **Portfolio reality** — current holdings, sleeves, concentration, cash/dry-powder if known, and current board state.
2. **Regime reality** — macro, rates/inflation, credit, breadth, sector leadership, and risk-on/risk-off posture.
3. **Candidate quality** — fundamentals, thesis quality, valuation discipline, and source freshness.
4. **Timing quality** — technical state, entry bands, stops, earnings/catalyst windows, no-chase/repair/blocked status.
5. **Risk fit** — concentration, sleeve role, downside/invalidation, opportunity cost, and whether cash outranks forced deployment.
6. **Recommendation packet** — action bucket, rationale, blocker, owner decision needed, and whether any workspace-canon maintenance proposal is eligible.
7. **Advice boundary check** — label any tax/legal/retirement/insurance/outside-account issue as a constraint or referral item, not as professional advice.
8. **Mutation routing** — if a workspace note/model update is warranted, route through the WF64/WF56 gated apply path governed by `veritas-bounded-portfolio-agent`. Main-session Veritas may apply exact validated workspace portfolio/canon mutations inside the standing-approved categories (`entry_band`, `earnings_state`, `ticker_state`, `sleeve`, `sizing`, `sector_posture`, and directly related portfolio artifacts) when proposal artifacts, approval/authority reference, validators, rollback, post-apply proof, and audit trail are present. Do not treat planner output alone as self-applying, owner approval, or trade/account authority.

## Probability/regression gate

Check WF55 before any probabilistic language.

Allowed while outcome depth is insufficient:
- heuristic-only
- uncalibrated
- scenario-weighted judgment
- evidence-depth flag
- retained-sample support/weakness only if outcome records exist

Blocked until WF55 validates enough retained outcomes:
- win probability / win rate
- deploy probability
- percent chance / percent likelihood
- expected return
- predicted outcome
- calibrated score/readiness score
- model-ranked deployment or promotion

Regression output, if later allowed, is review support only. It cannot grant owner approval, sizing, sleeve/cash/risk-rule changes, execution entitlement, or trade/account authority.

## Recommendation buckets

Use these buckets:
- **Add / increase review** — evidence supports owner review; no trade is placed.
- **Prepare / conditional add** — wait for band, catalyst clearance, source refresh, or risk condition.
- **Hold / maintain** — thesis intact, no fresh action.
- **Trim / reduce review** — risk or concentration warrants owner review.
- **Repair / monitor** — thesis or chart needs evidence before deployment.
- **Bench / avoid** — not portfolio-ready.

## Output format

### Planner verdict
- Posture: [selective offense / balanced / defensive / cash-first / mixed]
- Confidence: [High / Medium / Low]
- Main constraint: [known limiting factor]
- Authority: advisory recommendations plus gated workspace portfolio/canon maintenance when WF64/WF56 proof passes; live trade/account actions owner-gated; Alpaca paper submit/cancel only through WF63/WF67 paper-only guardrails and scoped paper-trade artifacts

### Portfolio recommendations
| Priority | Action bucket | Candidate / sleeve | Why now | Blocker / owner gate |
|---|---|---|---|---|

### Scenario / stress notes
- Base case:
- Bull case:
- Bear case:
- What would change the recommendation:

### Workspace follow-through
- Candidate canon/proposal updates:
- Required validators:
- Owner decisions required:

## Stop lines

Stop or downgrade confidence if:
- source freshness is stale/partial/contradictory/manual-required
- portfolio notes conflict with generated artifacts
- WF55 does not support probability/regression claims
- exact approval artifacts/validators are missing for a proposed workspace mutation
- a recommendation would imply live trade/account/brokerage/money-movement authority, or imply paper submit/cancel authority outside WF63/WF67 scoped approval artifacts
- tax/liquidity/cash constraints are material but unknown
