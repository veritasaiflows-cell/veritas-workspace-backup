# WF67 Full-Portfolio / Basket Paper Scope Contract Draft

- **Status:** draft for Randall review only; **not executable**.
- **Workflow:** WF67 - Alpaca Paper Execution Guardrail.
- **Scope type:** full-portfolio / basket paper-simulation contract.
- **Model size:** `$100,000` paper-only portfolio simulation.
- **Authority boundary:** this contract does **not** authorize live trades, paper orders, account actions, money movement, canonical portfolio mutation, or inferred owner approval. Execution remains blocked until this scope is explicitly approved, encoded into scoped request artifacts, dry-run validated, and owner confirms exact order terms.
- **Approval source for paper capability:** `tmp/alpaca-paper-readiness/phase-6-paper-execution-approval.json`.
- **Draft source packet:** `tmp/deployment-build-final-executive-packet-2026-05-17.md`.

## 1. Contract truth fields

| Field | Required value |
|---|---|
| `paper_only` | `true` |
| `paper_endpoint` | `https://paper-api.alpaca.markets` only |
| `paper_credentials_only` | `ALPACA_PAPER_API_KEY_ID`, `ALPACA_PAPER_API_SECRET_KEY` only |
| `live_endpoint_allowed` | `false` |
| `live_credentials_allowed` | `false` |
| `live_submit_allowed` | `false` |
| `live_cancel_allowed` | `false` |
| `money_movement_allowed` | `false` |
| `account_settings_mutation_allowed` | `false` |
| `replace_order_allowed` | `false` |
| `close_position_or_liquidation_allowed` | `false` |
| `paper_results_promote_to_live_allowed` | `false` |
| `owner_approval_inferred_from_validation` | `false` |
| `raw_secret_or_header_persistence_allowed` | `false` |

## 2. Exact allowed basket universe

Only the symbols below may be considered by this draft scope. Any other ticker is blocked until a revised WF67 scope names it explicitly.

### First-call / single-name quality review universe

| Symbol | Role | Initial contract posture |
|---|---|---|
| `ETN` | First-call deploy-review candidate | Eligible for Tranche 1 only if fresh band/source/technical gates remain clean. |
| `LIN` | Materials quality candidate | Eligible after full promotion packet and primary-source refresh. |
| `CME` | Financial infrastructure candidate | Eligible after full promotion packet and primary-source refresh. |
| `PH` | Industrial compounder candidate | Eligible after promotion proof and ETN opportunity-cost comparison. |
| `WMB` | Energy infrastructure watch candidate | Watch/pullback only; not executable unless in-band and packet-clean. |
| `TMUS` | Communication Services monitor | Monitor only; requires chart repair/reclaim before any paper order. |

### Reserve / bond sleeve universe

| Symbol | Role | Paper model target cap |
|---|---|---:|
| `SGOV` | Preferred T-bill / cash-like core | `$6,000` |
| `SHY` | Short Treasury ballast | `$2,000` |
| `BND` | Aggregate bond diversifier | `$1,000` |
| `SCHP` | TIPS / inflation hedge | `$1,000` |

### ETF sleeve validation universe

| Symbol | Role | Paper model target cap |
|---|---|---:|
| `VTI` | Broad U.S. equity core | `$8,000` |
| `VXUS` | International core | `$7,000` |
| `ITA` | Defense/aerospace gap | `$5,000` |
| `XLI` | Industrials ETF | `$4,000` |
| `XLB` | Materials ETF | `$4,000` |
| `PAVE` | Infrastructure/reshoring ETF | `$3,000` |
| `XLE` | Energy/inflation hedge ETF | `$3,000` |
| `XLC` | Communication Services ETF | `$2,000` |

## 3. Explicitly blocked symbols / sleeves for this scope

The following are not allowed under this draft basket scope unless a later approved artifact explicitly changes status: `NVDA`, `MSFT`, `JPM`, `BRK.B`, `LMT`, `RTX`, `GE`, `XOM`, `LNG`, `BKNG`, `PLTR`, `KTOS`, `HYG`, `JNK`, and any unnamed symbol.

## 4. Tranche and notional caps

| Tranche | Cumulative deployment cap | Max new submitted notional | Eligible exposure |
|---:|---:|---:|---|
| 0 | `0%` | `$0` | Validators, issuer checks, and dry-run basket only. |
| 1 | `20%` | `$20,000` | `ETN` if still valid; `SGOV` / `SHY`; validated `VXUS` / `VTI` only if in-band/no-chase. |
| 2 | `40%` | `$20,000` | Add validated ETF gaps and 1-2 fully packeted quality names. |
| 3 | `60%` | `$20,000` | Add second-wave sector names after fresh bands and source checks. |
| 4 | `80%` | `$20,000` | Fill reserve/bond completion and validated ETF sleeve. |
| 5 | `100%` | `$20,000` | Only if macro/readiness, bands, and sector/correlation validators are clean; otherwise paper cash remains valid. |

Additional caps:
- **Max total submitted notional per regular trading day:** `$20,000` unless Randall separately approves a faster paper simulation.
- **Max aggregate open order notional:** `$20,000` across all open basket orders.
- **Max per-symbol order notional:** lesser of the symbol's remaining paper-model target cap, tranche remaining capacity, and the validator-approved order request amount.
- **Max per single order:** `$5,000` unless the scoped artifact sets a lower cap; reserve ETFs may use target-cap amounts if validators pass.
- **No all-at-once deployment:** the full `$100,000` model must not be submitted in one session under this draft.
- **Session spacing:** use at least one regular market session between tranches unless Randall explicitly approves acceleration.

## 5. Order constraints

Allowed only after validated dry-run and explicit owner confirmation of exact terms:
- Paper orders only.
- Buy-only initial basket scope.
- Limit orders only.
- Day time-in-force only.
- Regular-hours only.
- Named symbol, side, limit price, quantity or notional, tranche id, source packet, risk check, and owner approval artifact required.
- No chase above written band; limit must be at/below approved limit or inside written entry band.
- Current source, issuer/official-source, technical, catalyst, sector, and correlation gates must be clean.
- ETF look-through must be complete before ETF order eligibility.
- Cash / unallocated paper cash is valid when a candidate fails gates.

Blocked order/action classes:
- Market orders.
- Sell, short, margin, leverage, options, crypto.
- Multi-leg, bracket, OCO, OTO orders.
- Replace orders.
- Close-position / liquidation endpoints.
- Transfers, money movement, account settings mutation.
- Live endpoint or live credentials.
- Scheduled/autonomous paper execution without a separate exact schedule/pilot artifact and validator proof.

## 6. Required owner approval fields per tranche/order artifact

Every executable request artifact derived from this draft must contain explicit owner fields. Blank, stale, ambiguous, or inferred approval blocks execution.

```json
{
  "owner_approval_required": true,
  "owner_approval_granted": false,
  "approved_by": null,
  "approved_at_local": null,
  "approval_text_or_reference": null,
  "approved_scope_id": null,
  "approved_tranche_id": null,
  "approved_symbols": [],
  "approved_max_total_submitted_notional_usd": null,
  "approved_max_per_symbol_notional_usd": null,
  "approved_order_type": "limit",
  "approved_time_in_force": "day",
  "approved_regular_hours_only": true,
  "approved_buy_only": true,
  "paper_only_acknowledged": true,
  "live_trading_acknowledged_blocked": true
}
```

## 7. Kill-switch constraints

Execution remains blocked unless a short-lived WF67 kill switch exists and validates at execution time.

Required state:
- `alpaca_access_enabled=true`
- `paper_submit_enabled=true` only for the approved execution window
- `paper_cancel_enabled=true` only if cancel scope is approved
- `live_submit_enabled=false`
- endpoint exactly `https://paper-api.alpaca.markets`
- approval note names this scope, tranche, and paper-only submit/cancel wrapper
- expiration is short-lived and unexpired

Missing, malformed, expired, disabled, live-enabled, non-paper, or ambiguous kill-switch state blocks all submit/cancel calls.

## 8. Dry-run-first sequence

Mandatory sequence before any basket paper submit:

1. Create tranche-specific scoped request artifact derived from this contract.
2. Run basket/order preview validation with all authority fields false-by-default except the explicitly approved paper scope.
3. Run WF67 paper-execution guard validator; require `ok`, 0 critical, 0 warning unless a non-safety warning is explicitly accepted in writing.
4. Run WF63 paper readiness/isolation validator; require `ok`, 0 critical, 0 warning.
5. Run dry-run submit through the approved wrapper with no API write.
6. Main session verifies symbol list, tranche cap, limit prices, quantity/notional, source packet, kill switch, and audit setup.
7. Randall confirms exact paper-only order terms.
8. Only then may the approved wrapper submit paper orders for the approved tranche/request artifact.

## 9. Reconciliation and WF55 logging

After every submit, cancel, expiry, fill, partial fill, or observed paper position change:

- Run read-only reconciliation of paper orders/positions.
- Preserve redacted result artifacts; do not persist secrets, headers, raw credential values, or raw response bodies.
- Record audit-log event ids from `tmp/alpaca-paper-readiness/audit-log.jsonl`.
- Rerun WF67 guard validator with execution-result allowance where appropriate.
- Rerun WF63 readiness/isolation validator.
- Append WF55/state-history outcome rows for fills, misses, cancellations, expirations, accepted-unfilled orders, position opens, and later closes.
- Keep paper P/L and lifecycle state separate from real portfolio truth.

## 10. Stop lines

Stop immediately and do not submit/cancel if any condition appears:

- Live endpoint, live credentials, or non-paper account is detected.
- Symbol is not named in this contract or the approved tranche artifact.
- Order terms are missing, invented, stale, above band, or not owner-approved.
- Candidate is below stop, repair-state, do-not-touch, watch-only without reclaim, or event-frozen.
- ETF look-through or issuer/source validation is missing for ETF orders.
- Kill switch is missing, expired, malformed, disabled, or live-enabled.
- Validator returns any critical/warning not explicitly accepted as non-safety.
- Secrets, headers, auth material, raw credentials, or unredacted sensitive response data appear in logs/artifacts/chat.
- Wrapper can submit/cancel outside a scoped artifact.
- Generated recommendation, score, dashboard state, clean validator, or this draft is treated as owner approval.
- Any path attempts live trading, money movement, account settings mutation, replace, close-position, liquidation, options, crypto, margin, leverage, shorting, or market orders.

## 11. Current status / next required action

This file is a **draft scope contract only**. Next safe action is main-session review and Randall approval or edits. If approved, the next implementation artifact should be a Tranche 0 / Tranche 1 **dry-run-only** basket request; no paper API write is authorized by this draft.
