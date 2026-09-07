# Alerts and Recommendations OS Operating Model

## Objective

Deliver truthful, fresh, efficient market alerts and evidence-backed, non-executing recommendations. Never let a polished surface outrank source lineage, current evidence, or a validator.

## Ownership Map

| Layer | Owner |
|---|---|
| Preferences and objectives | `03. Alerts and Recommendations/Investor Profile.md` |
| Generic alert conditions and states | `03. Alerts and Recommendations/Alert Trigger Policy.md` |
| Ticker-level thesis, levels, invalidation, and review dates | `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md` |
| Read-only routes and governance | `03. Alerts and Recommendations/Alert Operations Board.md` |
| Research scope | `04. Research/Coverage Universe.md` |
| Market context | `02. Markets/Macro Regime Dashboard.md` |
| Workflow lifecycle | `06. Playbooks/Active Workflows.md` |
| Structured evidence and proof | guarded SQL and validated `tmp/` artifacts |

Generated artifacts are evidence, mirrors, or routing aids. They are not canon or approval.

## Direct Chain

Use `python scripts/run_alerts_recommendations_chain.py <morning|midday|post-close|weekly> --timeout-seconds 120 --write --validate`.

The chain is:

1. guarded SQL validation
2. explicit high-attention quote snapshot
3. alert freshness controller
4. alert and recommendation digest

Each stage fails closed on missing lineage, stale evidence, invalid schema, or upstream failure. Warning-grade facts stay warning-grade.

## Output Contract

Every material recommendation exposes ticker, timeframe, evidence date, freshness, confidence, thesis, base/bull/bear view, risks, alert-band and invalidation context, uncertainty, and Randall's decision point.

## Automation Boundary

Cron may refresh evidence, validate lineage, classify alert states, deduplicate alerts, and build non-executing recommendation packets. It must not create or maintain account, capital, order, execution, or simulated-account state.

## Truth Rules

- Static levels are read from guarded canon and are never silently re-derived or auto-applied.
- A scheduler-green result proves only that its named contract passed.
- Closed-market context must be labeled truthfully; it is not fabricated intraday freshness.
- Stale or conflicting evidence lowers confidence or suppresses output.
- Owner-provided objectives or limits may inform a response transiently but do not become maintained system state.
