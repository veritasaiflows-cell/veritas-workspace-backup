# WF67 Full-Portfolio / Basket Paper Scope Validator Design

- **Status:** design only; no code changes, no API calls, no paper orders.
- **Purpose:** define the validation contract needed before WF67 can accept a staged $100k paper model / basket scope instead of the current 1-share / $500 pilot scope.
- **Execution posture:** dry-run first, then exact owner confirmation, then paper-only submission if every guard remains clean.
- **Current baseline:** `scripts/alpaca_paper_trade_executor.py` and `scripts/alpaca_paper_execution_guard_validator.py` hard-cap submit requests at `MAX_PILOT_QTY = 1` and `MAX_PILOT_NOTIONAL_USD = 500.0`. Those caps must remain the default unless an explicit full-portfolio scope artifact is passed and validates cleanly.
- **Authority boundary:** paper-only Alpaca simulation; no live endpoint, live credentials, money movement, account mutation, replacement, liquidation, close-position, margin/leverage/options/crypto, or inferred owner approval.

## 1. Recommended artifacts

### A. Full-portfolio scope artifact

Create a new artifact type, separate from individual order requests:

```json
{
  "schema_version": 1,
  "workflow": "WF67 - Alpaca Paper Execution Guardrail",
  "phase": "phase_6_paper_execution_guardrail",
  "artifact_type": "wf67_full_portfolio_paper_scope",
  "scope_id": "wf67-full-portfolio-YYYYMMDD-v1",
  "created_at_utc": "...",
  "approved_by": "Randall",
  "approval_text_or_pointer": "...",
  "authority": { ... },
  "portfolio_model": { ... },
  "tranche_controls": { ... },
  "allowed_symbols": [ ... ],
  "symbol_controls": { ... },
  "order_constraints": { ... },
  "execution_sequence": { ... },
  "required_validators": { ... },
  "audit": { ... }
}
```

This should be passed explicitly with a new parameter such as `--portfolio-scope tmp/...json`. Absence of this artifact means the existing pilot caps apply unchanged.

### B. Basket/tranche request artifact

Do **not** overload the single-order request as the portfolio authority source. Use a basket request that references the full scope:

```json
{
  "schema_version": 1,
  "workflow": "WF67 - Alpaca Paper Execution Guardrail",
  "artifact_type": "wf67_paper_basket_request",
  "request_id": "...",
  "portfolio_scope_id": "wf67-full-portfolio-YYYYMMDD-v1",
  "tranche_number": 1,
  "created_at_utc": "...",
  "orders": [ ... ],
  "risk_check": { ... },
  "source": { ... },
  "audit": { ... }
}
```

The executor can later expand this into validated single order submissions, but validation should treat the basket as one atomic guard decision: if any row fails, the basket blocks.

## 2. Required full-scope schema fields

### Identity and approval

Required:

- `schema_version: 1`
- `workflow: "WF67 - Alpaca Paper Execution Guardrail"`
- `phase: "phase_6_paper_execution_guardrail"`
- `artifact_type: "wf67_full_portfolio_paper_scope"`
- `scope_id` unique, non-sample, min length 12
- `created_at_utc`
- `expires_at_utc` or `valid_for_session_date`
- `approved_by: "Randall"`
- `approval_status: "approved_full_portfolio_paper_scope"`
- `approval_text_or_pointer` linking the exact owner approval / packet
- `source_packet: "tmp/deployment-build-final-executive-packet-2026-05-17.md"` or successor packet

Fail closed if approval is missing, stale, ambiguous, copied from the pilot-only approval, or only says guardrails are implemented pending scoped pilot.

### Authority block

Required constants:

```json
{
  "paper_only": true,
  "paper_submit_allowed": true,
  "paper_cancel_allowed": true,
  "full_portfolio_paper_scope_allowed": true,
  "basket_submit_allowed": true,
  "live_submit_allowed": false,
  "live_cancel_allowed": false,
  "live_endpoint_forbidden": true,
  "live_credentials_forbidden": true,
  "money_movement_allowed": false,
  "account_settings_mutation_allowed": false,
  "replace_order_allowed": false,
  "close_position_allowed": false,
  "liquidation_allowed": false,
  "short_sales_allowed": false,
  "margin_allowed": false,
  "leverage_allowed": false,
  "options_allowed": false,
  "crypto_allowed": false,
  "market_orders_allowed": false,
  "multi_leg_orders_allowed": false,
  "paper_results_promote_to_live_allowed": false,
  "no_inferred_approval": true,
  "dry_run_first_required": true,
  "explicit_owner_confirm_after_dry_run_required": true
}
```

### Portfolio model

Required:

- `model_name`: e.g. `$100k paper model simulation`
- `model_notional_usd`: `100000.0` max unless later explicitly approved
- `base_currency: "USD"`
- `target_sleeves` array with `{sleeve, target_pct, target_notional_usd, max_pct, max_notional_usd}`
- Required sleeve cap consistency: stock quality 54%, equity ETF 36%, reserve/cash-like/bonds 10% unless successor packet explicitly changes it.
- `cash_unallocated_allowed: true` — undeployed cash must be valid when gates fail.

### Tranche controls

Required:

- `tranche_count: 5`
- `max_tranche_notional_usd: 20000.0`
- `max_total_submitted_notional_per_day_usd`
- `max_aggregate_open_order_notional_usd`
- `max_cumulative_submitted_notional_usd`
- `min_sessions_between_tranches: 1` unless explicit faster-paper-simulation approval exists
- `current_tranche_number`
- `cumulative_prior_submitted_notional_usd`
- `cumulative_prior_filled_notional_usd`
- `post_submit_reconciliation_required: true`
- `post_close_reconciliation_required: true`
- `wf55_outcome_logging_required: true`

Recommended default caps from the packet:

| Cap | Default |
|---|---:|
| Full model max | `$100,000` |
| Tranche max | `$20,000` |
| Daily submitted notional max | `$20,000` unless explicit approval widens it |
| Aggregate open order notional max | `<= current tranche max` |
| Single-name per-order max | smaller of symbol cap and tranche remaining |
| ETF/reserve per-order max | smaller of symbol cap and tranche remaining |

### Allowed symbols

Each allowed symbol needs an explicit row:

```json
{
  "symbol": "ETN",
  "instrument_type": "equity",
  "sleeve": "stock_quality",
  "allowed_side": "buy",
  "max_order_notional_usd": 2500.0,
  "max_cumulative_notional_usd": 5000.0,
  "max_qty": null,
  "entry_band_required": true,
  "limit_price_required": true,
  "no_chase_required": true,
  "fresh_source_required": true,
  "technical_state_required": "not_below_stop_or_repair",
  "earnings_or_event_freeze_must_be_clear": true,
  "validator_refs": ["..."]
}
```

Initial allowed-symbol set should be only names in the deployment packet that have passed their required proof. The packet names the candidate queue, not automatic executable permission. Symbols should begin empty or limited to validated tranche-1 names until issuer/source/technical validators pass.

Minimum fields per symbol:

- `symbol`
- `instrument_type`: `equity`, `etf`, or `treasury_bond_etf`
- `sleeve`
- `allowed_side`: default `buy`; `sell` only if separately scoped
- `max_order_notional_usd`
- `max_daily_notional_usd`
- `max_cumulative_notional_usd`
- `max_open_order_notional_usd`
- `min_limit_price` / `max_limit_price` or `approved_limit_price`
- `entry_band_ref`
- `freshness_ref`
- `technical_ref`
- `source_packet_ref`
- `blocked_if_watch_only`, `blocked_if_repair`, `blocked_if_below_stop`, `blocked_if_above_band`

### Order constraints

Required constants:

- `endpoint: "https://paper-api.alpaca.markets"`
- `allowed_methods: ["GET", "POST", "DELETE"]`
- `allowed_submit_path: "/v2/orders"`
- `allowed_cancel_path_prefix: "/v2/orders/"`
- `allowed_order_types: ["limit"]`
- `allowed_time_in_force: ["day"]`
- `regular_hours_only: true`
- `extended_hours_allowed: false`
- `market_orders_allowed: false`
- `fractional_allowed`: explicit true/false; if true, require notional orders and Alpaca support check
- `buy_only_initial_scope: true`
- `sell_allowed: false` unless separately scoped
- `cancel_allowed_for_scope_order_ids_only: true`
- `replace_allowed: false`

### Required validators

Required statuses should all be `ok` and fresh enough:

- WF67 guard validator clean
- WF63 paper/live isolation clean
- read-only proof clean
- kill switch unexpired and exact-paper endpoint
- dry-run basket result clean before execute
- owner confirmation after dry-run references exact basket request hash/path
- symbol entry-band validator clean
- no-chase validator clean
- source/issuer/official-source freshness clean
- ETF look-through validator clean for ETFs
- sector/sleeve/concentration cap validator clean
- catalyst/earnings freeze validator clean
- technical-state validator clean
- audit redaction validator clean
- post-submit reconciliation planned
- WF55 logging path available

## 3. Basket request fields

Each `orders[]` row should include:

- `symbol`
- `side` — initial full-scope should allow `buy` only
- `type: "limit"`
- `time_in_force: "day"`
- `limit_price`
- exactly one of `qty` or `notional`
- `estimated_notional_usd`
- `sleeve`
- `tranche_number`
- `entry_band_ref`
- `source_validator_ref`
- `technical_validator_ref`
- `risk_check_ref`
- `owner_scope_ref`
- `dry_run_preview_id` for execute pass

Basket-level `risk_check` required fields:

- `status: "ok"`
- `basket_estimated_notional_usd`
- `tranche_remaining_notional_usd`
- `daily_remaining_notional_usd`
- `aggregate_open_order_notional_after_submit_usd`
- `cumulative_model_notional_after_submit_usd`
- `per_symbol_caps_passed: true`
- `sleeve_caps_passed: true`
- `sector_caps_passed: true`
- `correlation_caps_passed: true`
- `cash_remaining_after_submit_usd`
- `max_loss_reviewed: true`
- `position_size_reviewed: true`

## 4. Validation rules

### Hard identity / authority rules

Block if:

- full-scope artifact is absent and basket or notional exceeds pilot caps
- artifact type, workflow, phase, scope id, or request id is wrong
- approval does not explicitly authorize full-portfolio / basket paper scope
- approval is not by Randall or lacks exact source pointer
- any forbidden authority field is true or missing
- any required paper-only / no-inferred-approval field is false or missing
- artifact is sample, test-only, stale, or says “do not execute”

### Pilot-preservation rule

Executor/validator behavior should branch like this:

1. **No `--portfolio-scope` passed:** keep existing behavior exactly — max `qty <= 1`, estimated notional `<= $500`, and `risk_check.max_notional_usd <= $500`.
2. **`--portfolio-scope` passed but invalid:** fail closed; do not widen caps.
3. **`--portfolio-scope` valid but basket request missing/invalid:** fail closed; do not widen caps.
4. **Valid full scope + valid basket:** apply the stricter of full-scope caps, symbol caps, tranche caps, daily caps, aggregate-open caps, cash remaining, and order-request values.
5. **Single-order request with full scope:** only allow widened cap if the order references `portfolio_scope_id`, an allowed symbol row, tranche id, and owner post-dry-run confirmation. Otherwise remain under pilot caps.

### Notional and cap rules

Block if:

- `estimated_notional_usd != qty * limit_price` when qty is used, outside small rounding tolerance
- basket estimated notional exceeds tranche remaining
- basket estimated notional exceeds daily remaining
- basket estimated notional plus current open order notional exceeds aggregate-open cap
- cumulative submitted/fill notional would exceed model max
- symbol order/daily/cumulative/open caps fail
- sleeve cap, sector cap, single-name cap, ETF concentration cap, or correlation cap fails
- cash/unallocated balance would go negative
- any order tries to use both `qty` and `notional`, or neither
- any price is zero/negative/non-numeric

### Entry discipline rules

Block each order if:

- symbol is not in the validated allowed-symbol list
- current price / limit price is above written entry band without explicit no-chase override
- technical state is below stop, repair, do-not-touch, watch-only, or unresolved
- issuer/official/source freshness is stale, missing, partial, or contradictory
- ETF look-through is missing for ETF orders
- unresolved earnings/catalyst/event freeze exists
- market is outside regular hours or `extended_hours` is requested
- order is market, stop, trailing, bracket/OCO/OTO, short, margin/leverage, option, crypto, replace, close, liquidate, or account mutation

### Dry-run and owner confirmation rules

Block execute if:

- dry-run has not been run after the exact latest basket/scope hash
- dry-run result status is not `validated_dry_run`
- owner confirmation does not reference exact basket path/hash, scope id, tranche, total notional, and symbols
- kill switch was created before the final owner confirmation or is expired
- audit log does not show redacted dry-run event

Recommended hash fields:

- `scope_sha256`
- `basket_request_sha256`
- `dry_run_result_sha256`
- `owner_confirmation_text_or_pointer`

## 5. Fail-closed checks to preserve existing safety

The validator should explicitly report `status: blocked` for:

- missing full-scope artifact when basket/full-notional mode is requested
- invalid JSON/schema
- wrong endpoint or live endpoint literal
- ambiguous or live credential env names present
- missing paper-specific credentials for execute
- expired kill switch
- stale validators or missing validator refs
- request/result/audit contains secret-shaped text
- raw response body or headers persistence enabled
- cancellation request for an order id not created under the same scope/request/audit chain
- any attempt to close positions, liquidate, replace, transfer, mutate account settings, or promote paper result to live

## 6. Suggested validator output

```json
{
  "schema_version": 1,
  "workflow": "WF67 - Alpaca Paper Execution Guardrail",
  "artifact_type": "wf67_full_portfolio_scope_validation",
  "generated_at_utc": "...",
  "status": "ok|blocked",
  "mode": "pilot|full_portfolio_basket",
  "pilot_caps_preserved": true,
  "cap_source": "pilot_defaults|validated_full_portfolio_scope",
  "effective_caps": {
    "max_order_notional_usd": 500.0,
    "max_qty": 1,
    "max_tranche_notional_usd": null,
    "max_daily_notional_usd": null,
    "max_aggregate_open_order_notional_usd": null
  },
  "summary": { "critical": 0, "warning": 0 },
  "findings": [],
  "ready_for_dry_run": false,
  "ready_for_execute": false,
  "live_trading_allowed": false,
  "money_movement_allowed": false
}
```

When full scope validates, `effective_caps` should show the full-scope-derived caps, but `pilot_caps_preserved` should still be true to indicate defaults remain pilot-only unless the validated artifact is actively present.

## 7. Minimal implementation path later

1. Add JSON schema for `wf67_full_portfolio_paper_scope`.
2. Add JSON schema for `wf67_paper_basket_request`.
3. Add validator functions only; no API behavior changes first.
4. Add explicit CLI args such as `--portfolio-scope` and `--basket-request`.
5. Keep current single-order validator unchanged for default mode.
6. Add branch that computes effective caps only after full-scope + basket validation passes.
7. Add dry-run-only basket output.
8. Only after dry-run, owner confirmation, and audit proof, consider execute-path expansion.

## Bottom line

The safe contract is: current pilot caps remain the default and cannot be widened by implication. A full-portfolio/basket paper mode needs a separate Randall-approved scope artifact, a basket request referencing it, clean validators, dry-run-first proof, exact owner confirmation after dry-run, and stricter-of-all-caps enforcement before any paper-only submission.
