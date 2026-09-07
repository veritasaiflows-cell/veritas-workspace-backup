# WF67 Full-Portfolio / Basket Paper Scope Safety QA

Generated: 2026-05-17 22:33 MST
Scope: safety checklist for any proposed expansion from single scoped WF67 paper pilots into full-portfolio or basket paper execution.
Authority basis reviewed: `SOUL.md`, `USER.md`, `07. Risk/Alpaca Paper Trading Guardrails.md`, `06. Playbooks/Project Continuity/Workflow 67 - Alpaca Paper Execution Guardrail.md`.

## Bottom line

Full-portfolio or basket paper execution is **not automatically authorized** by the current WF67 pilot state. WF67 currently supports tightly scoped paper-only submit/cancel through exact validated wrappers and explicit pilot artifacts. Any basket/full-portfolio expansion must be treated as a new bounded pilot class with its own explicit owner scope, schema/validator coverage, kill switch, audit proof, and per-order or bounded-basket approval artifact.

## Non-negotiable stop lines

Block immediately if any item is true:

1. **Live endpoint or live credentials**
   - Any use or fallback to `https://api.alpaca.markets`.
   - Any live credential variable, ambiguous credential source, or mixed paper/live environment.
   - Any non-paper account detection.

2. **Inferred approval**
   - Basket generated from recommendations, scores, rankings, dashboards, clean validators, or model confidence without explicit owner/pilot scope.
   - Treating paper pilot success as approval for broader autonomous paper trading or live execution.

3. **Over-broad symbols / unbounded basket**
   - Wildcard universe, entire portfolio, all watchlist names, all deployment candidates, or sector basket unless explicitly named and capped.
   - Missing ticker allowlist, max symbol count, max per-symbol quantity/notional, and max basket notional/loss.
   - Symbols outside approved asset class scope: no options, crypto, shorts, margin/leverage, multi-leg/bracket/OCO/OTO.

4. **Market orders or invented order terms**
   - Market orders remain blocked unless separately approved.
   - Limit/day only by default.
   - Missing, stale, or invented limit prices, quantities, notional caps, time-in-force, or risk limits block execution.

5. **Replace / close / liquidate paths**
   - Any replace order, close position, liquidate, transfer, money movement, or account settings mutation path blocks the workflow.
   - Basket support must not introduce generalized brokerage client write access.

6. **High-yield treated as cash**
   - Do not treat SGOV/T-bills/high-yield ETFs/income holdings as free cash or cash-equivalent deployment fuel without explicit portfolio/risk review.
   - Paper simulation must preserve the distinction between cash, fixed-income proxies, income sleeve holdings, and deployable cash.

7. **No kill switch / stale kill switch**
   - Missing, malformed, expired, disabled, too-broad, or live-enabled kill switch blocks all Alpaca calls.
   - Basket kill switch must name basket/full-portfolio pilot scope and short expiration; kill switch alone is never order approval.

8. **Stale bands / stale evidence**
   - Entry bands, recommendation packet prices, catalyst state, risk constraints, or source freshness must be current enough for the scope.
   - Stale or contradictory canon/recommendation artifacts block paper orders; do not “simulate anyway” from old data.

9. **Validator bypass**
   - No direct wrapper `--execute` unless basket request, approval artifact, paper/live isolation, execution guard, order preview/risk validation, audit log, and kill switch all validate cleanly.
   - No hand-edited artifact may bypass schema/risk validation.

10. **Raw secrets / order IDs / sensitive broker data leakage**
   - No API keys, secret keys, bearer tokens, auth headers, raw env values, raw response bodies, or full request headers in artifacts/chat/logs.
   - Persist order IDs only if explicitly handled/redacted according to the current audit/reconciliation policy. For basket reports, prefer stable internal pilot/order references and redacted broker identifiers.

## Required pre-flight checklist for basket/full-portfolio paper pilot

- [ ] Explicit Randall approval naming basket/full-portfolio paper-only scope.
- [ ] New or extended basket request schema with:
  - [ ] exact ticker allowlist,
  - [ ] side per ticker,
  - [ ] limit price per ticker,
  - [ ] qty/notional per ticker,
  - [ ] max per-order notional/loss,
  - [ ] max aggregate basket notional/loss,
  - [ ] max symbol count,
  - [ ] time-in-force `day`,
  - [ ] paper-only true,
  - [ ] live submit/cancel false,
  - [ ] no inferred approval true.
- [ ] Source artifact link for every line item; no orphan orders.
- [ ] Freshness check for each ticker’s price/band/catalyst/risk state.
- [ ] Concentration and sleeve/risk review; no high-yield/income asset treated as cash.
- [ ] Kill switch is unexpired, paper-only, scoped to this basket pilot, and short-lived.
- [ ] Paper endpoint and paper credentials only; live endpoint/credentials absent.
- [ ] Execution guard confirms only exact approved POST `/v2/orders` and DELETE `/v2/orders/{id}` wrapper paths are callable.
- [ ] Replace, close, liquidate, transfer, money movement, account mutation, live write paths remain blocked.
- [ ] Audit log initialized and secret redaction validator clean.
- [ ] Dry-run validates every line item and aggregate basket risk before any execute.
- [ ] Main-session final check confirms request matches approved scope.

## Execution controls if approved later

- Execute serially or in a bounded batch with fail-closed behavior; if one order fails safety validation, stop before submitting subsequent orders unless the approval artifact explicitly defines partial-submit behavior.
- Record per-order audit events with internal line IDs, request artifact ID, preview/source ID, validator status, kill-switch status, and redaction status.
- Reconcile after submit using read-only paper calls only.
- Cancel/leave-open behavior must be explicit: no blanket cancel, close, sell, or liquidate authority.
- Any filled paper positions remain paper-simulation state only and must not mutate real portfolio truth or imply live trade readiness.

## Post-flight validation

- [ ] WF67 guard validator clean with execution-result allowance only for post-execution proof.
- [ ] WF63/read-only foundation remains clean.
- [ ] Reconciliation artifact exists for each order or aggregate basket with redacted broker data.
- [ ] Dashboard/status surface preserves: paper simulation only, live submit false, account/money movement false, inferred approval false, promotion-to-live false.
- [ ] Continuity note updated with exact scope, result, blockers, and next owner-gated action.

## Main risk judgment

The largest safety risk in a full-portfolio/basket expansion is not a single bad paper fill; it is accidentally converting WF67 from a scoped simulation lane into a generalized execution engine. The minimum safe posture is: named symbols only, limit/day only, capped notional/loss, explicit owner scope, short-lived paper-only kill switch, validator-first execution, redacted audit trail, and no live/account/money/approval inference under any condition.
