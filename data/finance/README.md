# Finance Data Registry

`data/finance/` holds durable finance registries used for routing, rebuild, and audit proof.

## Current Contents

- `universe-v1.json` - WF78/WF77 ticker universe registry and rebuild/audit mirror for the finance SQL canon candidate. Current scope is 200 active rows: 42 legacy production answer-path rows plus 158 `review_100_monitor` rows.

## Authority

- Durable input, rebuild, and audit support for the finance universe layer.
- First-pass SQL machine canon candidate lives at `state/finance/finance-canon.sqlite`; this JSON file remains the rebuild/audit mirror.
- WF84 treats this file as a durable registry source, not fast-moving market data. It must pass schema, authority-boundary, ticker-count, and semantic-digest checks; age alone should not block WF84/WF85 freshness.
- Does not replace canonical owner notes in `03. Portfolio/`, `04. Research/`, `05. Intelligence/`, or `07. Risk/`.
- Grants no owner approval, portfolio/canon mutation, sizing/cash/risk-rule change, paper/live execution, brokerage/account action, or money movement authority.
- SQL, ticker-card, and dashboard consumers must preserve their own authority flags and validators.

## Retirement Plan

Do not retire `universe-v1.json` until WF84/WF85 have proof that every direct consumer either reads the WF84 JSON/SQLite interface or is an explicit producer/validator exception.

Retirement requires:

- consumer inventory showing no unsupported direct reads
- WF84 rebuild parity from the replacement source
- rollback/export path that can recreate this registry byte-for-byte or semantically
- DB lifecycle classification and owner approval for any archive/delete move
- preserved false authority flags for capital, execution, paper/live, account, and owner approval

Until those gates are clean, this file remains the durable universe registry and source-lineage input. WF84/WF85 may become the preferred consumer interface, but this registry stays retained.

## Producer And Proof

- Primary producers/validators: `scripts/finance_universe_validator.py`, `scripts/finance_sql_canon.py`, `scripts/finance_data_coverage.py`, `scripts/ticker_intelligence_card.py`, and `scripts/finance_intelligence_state.py`.
- Validation proof should route through the current WF77/WF78 artifacts and `scripts/artifact_index.py validate`.

## Retention

Keep durable registries here when they are reusable inputs across sessions. Generated proof, temporary packets, and one-off exports remain under `tmp/`.
