# Ticker Lane Templates

Use these templates to add or refresh a ticker without bloating canon.

## Coverage and Watchlist row

Use one row only. Keep state short.

```markdown
| TICKER | Sector / Theme | Coverage tier | Thesis pointer | Execution/action pointer | Source lineage |
```

Examples:

```markdown
| BKNG | Consumer Discretionary / Travel Services | Core candidate | thesis section | Execution Board pointer | Research + technical lineage |
| RTX | Defense | Tactical | thesis section | Execution Board pointer | Technical lineage |
```

Do not include bands, stops, thesis paragraphs, model weights, or event essays.

## Coverage and Watchlist thesis section

```markdown
### TICKER - Company / Asset Name
- **Lane:** Watch / Technical / Execution / Portfolio-weighted
- **Thesis:** One concise thesis paragraph or 2-3 bullets.
- **Why it belongs:** Sector/theme/portfolio gap it helps monitor.
- **Key risk:** The main reason the thesis could fail.
- **Act when:** Evidence that would justify promotion or deeper review.
- **Do not act when:** Evidence or state that keeps it benched.
- **Source-confidence / catalyst note:** Primary-confirmed, provider-estimated, manual hold, or unknown.
```

Coverage owns thesis and evidence caveats. It does not own live entry levels or model weights.

## Execution Board technical section

```markdown
### TICKER
- Close: **PRICE** *(source / as-of)*
- 20 / 50 / 200-day: **A / B / C**
- MA posture: **plain-English posture**
- Support: **LEVEL / ZONE**
- Resistance: **LEVEL / ZONE**
- Preferred entry / repair zone: **ZONE** *(label whether execution, watch, or repair only)*
- Explicit stop/reference: **LEVEL**
- Invalidation logic: one sentence.
- Stance: **Watch-only / Almost deployable / Repair / Do not touch / Deployable now** with reason.
- Catalyst state: source and confidence if relevant.
- Lane note: explain whether this is execution-board entitled.
```

Technical owns levels and invalidation. It does not grant deployment authority.

## Execution Board action row

Use only for execution-board-entitled names.

```markdown
| TICKER | Action state | Live condition / blocker | Authority note | Detail source |
```

Examples:

```markdown
| ETN | Deployable now | Owner-promoted conditional add; must remain inside written band and no-chase discipline applies | Manual-only; no automatic execution | Execution Board + Coverage and Watchlist |
| JPM | Almost deployable | Owner approval recorded, but action state is not live until reclaim or explicit band review | Approval is recorded; execution still fails closed | Execution Board |
```

Execution Board owns the current gate judgment and exact levels.

## Portfolio Snapshot row

Use only for model-weighted or portfolio-implication names.

```markdown
| TICKER | Sleeve role | Draft weight | Portfolio status | Detail source |
```

Examples:

```markdown
| MSFT | Core Technology quality | 10% | Draft core; almost deployable, not automatic | Coverage and Watchlist + Execution Board |
| BKNG | Consumer Discretionary candidate | 0% | Watch-only; no model weight or deployment authority | Coverage and Watchlist + Execution Board |
```

Snapshot owns weights, sleeve role, concentration, and portfolio-level implications. It does not own exact entry levels, stops, or full thesis detail.

## Review-only status-move proposal template

Use this only in `tmp/portfolio-mutation-proposals/` or a review packet, not as an applied canonical edit.

```markdown
### TICKER canonical status move proposal
- Current tuple: Watchlist / Trigger / Technical / Snapshot / Coverage / portfolio-config
- Proposed tuple: Watchlist / Trigger / Technical / Snapshot / Coverage / portfolio-config
- Mutation type: promotion / demotion / lane_change / execution_entitlement_change
- Evidence: thesis, macro/regime, technical, catalyst, risk/sizing, sector/correlation
- Owner conflicts found: yes/no, with surfaces named
- Proposed files to edit: list only
- Exact patch preview: link/path to generated diff artifact
- Owner decision required: yes
- Owner approval granted: no
- Apply allowed: no
```

## Sleeve / rebalance proposal template

Use this for portfolio-construction proposals. It may compute alternatives but must not rewrite `Portfolio Snapshot.md`, `Risk Rules.md`, or `tmp/portfolio-config.json` before approval.

```markdown
### Sleeve / rebalance proposal
- Scope: sleeve_change / rebalance / cash_target_change
- Current portfolio model: cash target, sleeves, weights, sector exposure, correlated sleeves
- Proposed portfolio model: cash target, sleeves, weights, sector exposure, correlated sleeves
- Risk-rule check: sector cap, single-name ceiling, speculative cap, catalyst exceptions
- Why now: evidence and source freshness
- Tradeoffs: what improves, what worsens, what remains uncertain
- Proposed files to edit: list only
- Exact patch preview: link/path to generated diff artifact
- Owner decision required: yes
- Owner approval granted: no
- Apply allowed: no
```

## Freshness footer pattern

```markdown
## Freshness

- Last updated: YYYY-MM-DD — short factual reason.
- Data as of: artifact/date if relevant.
- Refresh when: membership, lane, action state, weight, catalyst confidence, or technical state changes materially.
```
