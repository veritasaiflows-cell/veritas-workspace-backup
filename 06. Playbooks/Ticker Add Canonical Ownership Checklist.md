# Ticker Add Canonical Ownership Checklist

Purpose: add a ticker without spreading duplicate truth across the finance canon.

## Authority boundary

Adding a ticker to the research or watch layer is not a deployment decision.
No checklist step grants trade authority, owner approval, model weight, promotion, or deployment state.

## Before adding

1. Classify the lane:
   - **Watch** — research/monitor only; no execution-board entitlement.
   - **Technical** — tracked with levels/invalidation, but not necessarily deployable.
   - **Execution** — belongs on the deployment board because it can become actionable under written gates.
   - **Portfolio-weighted** — has draft model weight or sleeve role in the portfolio snapshot.
2. Confirm the ticker exists in the machine spine before treating it as operational:
   - `tmp/portfolio-config.json` / tracked universe
   - earnings coverage if catalyst timing matters
   - technical/band artifact if levels matter
3. Decide which canonical note owns each fact before writing.

## Canonical ownership map

| Fact type | Owner | Do not duplicate into |
|---|---|---|
| Membership, tier, high-level state, source pointer | `04. Research/Coverage and Watchlist.md` | Thesis, levels, stops, weights |
| Thesis, key risk, act-when conditions, evidence caveats | `04. Research/Coverage and Watchlist.md` | Coverage and Watchlist, Snapshot, Execution Board |
| Price structure, support/resistance, bands, stops, invalidation | `03. Portfolio/Execution Board.md` | Coverage and Watchlist, Snapshot |
| Deployable/almost/blocked/do-not-touch judgment and live gate blocker | `03. Portfolio/Execution Board.md` | Coverage and Watchlist, Coverage and Watchlist |
| Draft weights, sleeve role, concentration, portfolio-level implication | `03. Portfolio/Portfolio Snapshot.md` | Coverage and Watchlist, Execution Board, Coverage and Watchlist |

## Add-flow by lane

### Watch lane

Required:
- Add or update one row in `Coverage and Watchlist.md`.
- Add or update a thesis section in `Coverage and Watchlist.md`.
- If price levels are already being monitored, add a concise technical section in `Execution Board.md`.

Forbidden:
- No model weight.
- No deployment-board row unless explicitly promoted.
- No exact band/stop detail in `Coverage and Watchlist.md`.

### Technical lane

Required:
- `Coverage and Watchlist.md` row points to `Execution Board` or `Coverage and Watchlist + Execution Board`.
- `Execution Board.md` owns levels, repair state, stop/reference, and invalidation.
- `Coverage and Watchlist.md` owns thesis and key risk.

Forbidden:
- Do not imply deployable state from an in-band technical condition.
- Do not copy the technical section into `Execution Board.md` unless the ticker is execution-board entitled.

### Execution lane

Required:
- `Execution Board.md` row states action state, live blocker/condition, authority note, and source pointer.
- `Execution Board.md` owns exact levels/invalidation.
- `Coverage and Watchlist.md` owns thesis.
- `Coverage and Watchlist.md` remains a terse index row.

Forbidden:
- No thesis paragraphs in the Execution Board.
- No full support/resistance stack in the Execution Board.
- No owner approval inferred from clean validation or a favorable score.

### Portfolio-weighted lane

Required:
- `Portfolio Snapshot.md` carries draft weight, sleeve role, concentration impact, and portfolio implication.
- Other notes point back to Snapshot only when the weight/sleeve fact matters.

Forbidden:
- Do not put model weights in Coverage and Watchlist, Coverage and Watchlist, or Execution Board.
- Do not treat draft weights as live allocations.

## Canonical status move packet

Any status move that changes capital-action meaning is a portfolio mutation proposal, not a routine freshness sync.

Before drafting a move, define the before/after tuple:

| Surface | Tuple field owned here |
|---|---|
| `04. Research/Coverage and Watchlist.md` | index label / tracking state only |
| `03. Portfolio/Execution Board.md` | action state, live blocker, execution entitlement, authority note |
| `03. Portfolio/Execution Board.md` | technical stance, levels, stop/reference, invalidation |
| `03. Portfolio/Portfolio Snapshot.md` | sleeve role, draft weight, portfolio status, concentration implication |
| `04. Research/Coverage and Watchlist.md` | thesis lane, evidence caveat, act-when / do-not-act-when logic |
| `tmp/portfolio-config.json` | `coverage_lane`, `workflow_state`, `portfolio_role`, `daily_technical_priority`, `entry_policy`, `sizing_tier` |

Required before apply:
- proposal artifact under `tmp/portfolio-mutation-proposals/`
- explicit Randall approval for the exact move
- proposed patch scope limited to the approved owner surfaces
- post-apply ownership and dashboard validation

Forbidden:
- no status move from a clean score, validator pass, queue row, or generated packet alone
- no deployable / execution-lane entitlement without explicit owner approval
- no weight, sleeve, sizing, or risk-rule mutation hidden inside a status move

## Validation

After adding or compressing ticker ownership, run:

```powershell
python scripts\validate_canonical_ownership.py
python scripts\validate_dashboard_state.py --write
```

A clean ownership validator means the note layer follows the ownership map. It does not mean the ticker is deployable.
