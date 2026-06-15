# Alpaca Paper Trading Guardrails

## Purpose

Define the non-negotiable safety boundary for WF63 - Alpaca Paper Trading Readiness.

Paper trading is still brokerage execution. It must not be treated as harmless just because the account is simulated.

## Current authority

Current status: **Phase 1 GET-only proof passed; Randall explicitly approved Alpaca paper-only submit/cancel authority on 2026-05-17; Randall expanded the paper-only posture on 2026-05-19 to allow advisor-derived paper buy/sell packages during or after market hours under WF67 guardrails; on 2026-05-20 21:37 MST Randall explicitly approved paper-trading only full paper trading abilities when Randall approves the exact order. Live trading remains blocked. Current executable wrapper supports validated paper-only limit/market day orders and limit/GTC orders; market/GTC and broader capabilities remain blocked until separately implemented and validated.**

Allowed:
- readiness design
- paper/live isolation planning
- non-secret connector planning
- read-only account/positions/orders verification after explicit approval
- Phase 1 GET-only paper endpoint proof through `scripts/alpaca_read_only_connection_proof.py` when the short-lived kill switch is valid and only paper-specific credential env vars are present
- non-executable order previews
- shadow-mode evaluation
- read-only reconciliation of a manually placed paper order after explicit pilot approval
- paper-only order submission and cancellation after WF67 implements and validates the exact wrapper, paper/live isolation, kill switch, audit logging, secret redaction, and scoped paper-trade approval artifact
- advisor-derived paper buy/sell order packages during or after market hours when the package uses the approved WF67 wrapper, exact paper endpoint, scoped paper-trade artifact, fresh kill switch, clean guard validation, audit log, and main-session capital-package notification
- full paper-trading abilities only when Randall approves exact order terms and the requested paper capability has matching WF67 request schema, wrapper support, validator proof, fresh kill switch, risk checks, redacted audit log, and reconciliation; current executable single-order support is limit/market day orders and limit/GTC orders only

Not allowed:
- live order submission
- OpenClaw paper order submission/cancellation/sell before WF67 submit/cancel guardrails validate cleanly
- replace orders
- account setting changes
- money movement
- live endpoint use
- live credential use
- credential disclosure in notes/chat/logs
- inferred owner approval from clean validation

## Paper/live isolation requirements

Before any Alpaca API call:
- Base URL must be exactly `https://paper-api.alpaca.markets`.
- Live endpoint `https://api.alpaca.markets` must not be selected or used.
- Credentials must be explicitly paper-mode credentials.
- Credential names for a future connector must be paper-specific (`ALPACA_PAPER_API_KEY_ID`, `ALPACA_PAPER_API_SECRET_KEY`) and secret values must stay outside workspace artifacts.
- Any ambiguous credential source blocks the workflow.
- Any fallback from paper to live blocks the workflow.

## HTTP method restrictions

WF63 Phase 1 read-only mode allows only safe read operations.

Allowed method class in WF63:
- GET only

WF67 may introduce exactly scoped paper write methods only after the paper-execution guard validates:
- POST `/v2/orders` through the exact approved paper-submit wrapper only
- DELETE `/v2/orders/{id}` through the exact approved paper-cancel wrapper only

Plain English: a paper **sell** is allowed only as a normal scoped paper sell order through POST `/v2/orders`; do not use close-position, liquidation, or replacement endpoints.

Still blocked method/path classes:
- PATCH
- PUT
- live endpoint POST/DELETE
- any unwrapped POST/DELETE
- replace order
- close position
- liquidate
- transfer or money movement
- account setting mutation

## Order-preview rules

Order previews are not orders.

Every preview must include:
- ticker
- side
- order type
- limit price
- quantity or notional
- source proposal id
- risk check summary
- owner decision required
- owner approval granted false by default
- paper submit allowed false by default
- live submit allowed false
- trade or account action allowed false

Current scaffold owner:
- Generator: `scripts/alpaca_order_preview_generator.py`
- Validator: `scripts/alpaca_paper_readiness_validator.py --validate-order-previews`
- Artifact path: `tmp/alpaca-paper-readiness/order-previews/*.json`

Initial preview restrictions:
- limit or market day orders only when the scoped request and current approval artifact support them; market orders require explicit owner-approval fields
- day time-in-force only unless separately reviewed
- no shorts
- no margin
- no leverage
- no options
- no crypto
- no multi-leg/bracket/OTO/OCO orders

If a source recommendation lacks an explicit owner-approved limit price or quantity/notional, the preview must remain non-executable and carry an owner-input blocker rather than inventing order terms.

## Shadow-mode rules

Shadow mode is not paper trading.

The shadow-mode report must include:
- `would_submit=false`
- no Alpaca endpoint calls
- no brokerage write methods used
- no paper-account state mutation
- no portfolio-canon mutation
- owner decision required
- owner approval granted false
- paper submit allowed false
- live submit allowed false
- trade or account action allowed false

Current scaffold owner:
- Generator/report: `scripts/alpaca_order_preview_generator.py`
- Validator: `scripts/alpaca_paper_readiness_validator.py --validate-shadow-mode`
- Artifact path: `tmp/alpaca-paper-readiness/shadow-mode-report.json`

## Kill switch

Default posture: blocked.

Any future connector must check a kill-switch artifact before Alpaca access. Missing, malformed, expired, or disabled kill-switch state blocks all Alpaca calls, including read-only calls.

Required future artifact:
- `tmp/alpaca-paper-readiness/kill-switch.json`

Minimum fields:
- `alpaca_access_enabled`
- `read_only_enabled`
- `paper_submit_enabled`
- `live_submit_enabled`
- `expires_at_utc`
- `approved_by`
- `approval_note`

Initial valid values for WF63 Phase 1 may only enable read-only paper access. Paper submit and live submit must remain false. Phase 1 kill-switch TTL must be short-lived and is capped in the runner at 120 minutes maximum.

Phase 5 manual-pilot reconciliation may also only use read-only paper access. For Phase 5, valid kill-switch state is constrained to:
- `alpaca_access_enabled=true`
- `read_only_enabled=true`
- `paper_submit_enabled=false`
- `live_submit_enabled=false`
- short expiration
- explicit approval note naming read-only reconciliation only

Any future Phase 6 paper-submit kill switch would require a separate Randall-approved doctrine exception and must name the exact paper-submit wrapper, approved endpoint/method scope, expiration, disable/rollback path, and paper-only isolation proof. Kill-switch state alone never grants owner approval for an order.

## No-submit guard

Default posture: no submit path may exist.

Before any Phase 6 approval, the no-submit guard must fail closed if active workspace code contains or exposes:
- submit order
- cancel/replace order
- close position or liquidation
- transfer or money movement
- account setting mutation
- non-GET Alpaca order/account write methods
- live endpoint fallback or live credential selection

Required future artifact:
- `tmp/alpaca-paper-readiness/no-submit-guard-report.json`

Minimum fields:
- generated timestamp
- scanned paths
- excluded archived/documentation paths
- forbidden pattern findings
- runtime HTTP method policy
- endpoint mode policy
- submit/cancel/replace callable status
- result `ok|blocked`
- reason codes

Phase 6/WF67 now requires a different guard mode that proves only the exact approved paper-submit/cancel wrapper exists while replace/live/account/money-movement paths remain blocked. Randall approved the paper-only submit/cancel authority on 2026-05-17, but code remains blocked until the WF67 wrapper, approval artifact, validator mode, kill switch, and audit proof exist and validate cleanly.

## Audit log

Any future Alpaca connector must write append-only audit events under:
- `tmp/alpaca-paper-readiness/audit-log.jsonl`

Audit events must redact secrets and include:
- timestamp UTC
- workflow
- phase
- event id
- actor (`veritas|script|randall_manual_attestation|validator`)
- action
- method class
- endpoint mode
- endpoint path class without query secrets
- request intent
- preview id if applicable
- approval artifact id if applicable
- validator statuses
- kill-switch status
- no-submit guard status
- blocked/allowed/observed/reconciled/mismatch/error result
- reason code
- artifact paths
- redaction status
- secret material present false

Secret-redaction rules:
- Never persist or print API keys, secret keys, bearer tokens, auth headers, account secrets, raw environment values, or full request headers.
- Replace any detected secret-shaped value with `[REDACTED]`.
- If redaction occurs, preserve only non-secret context and mark `redaction_status="redacted"`.
- Any unredacted secret in an artifact, log, note, or chat is a critical incident and blocks the workflow.

## Approval model

Clean validation is not approval.

Randall approval must be explicit for each phase transition:
1. Phase 1 read-only connection
2. Phase 3 order-preview generation from live recommendations
3. Phase 5 manual paper-order pilot reconciliation
4. OpenClaw paper-submit/cancel path

Phase 6/WF67 paper execution is a narrow doctrine exception because the prior doctrine said Veritas must not submit orders.

Phase 6/WF67 paper-only submit/cancel authority is **approved in principle** by Randall's 2026-05-17 instruction. Phase 7 advisor-derived paper buy/sell package authority is approved by Randall's 2026-05-19 21:23 MST instruction. No implementation may submit/cancel/sell until the exact wrapper and validator stack exists and the scoped request, kill switch, and audit log are clean. Replace, close-position, liquidation, transfer, live endpoint, live credentials, money movement, and account-mutation code remain blocked.

Required Phase 6/WF67 doctrine-exception checklist before implementation:
- Randall's 2026-05-17 approval is recorded as the exception to the standing no-order-submission boundary.
- Exception is paper-only, scoped, revocable, and never live.
- Exact wrapper, endpoint, method, order type, size/notional limits, risk checks, and rollback path are named.
- Per-order owner approval remains required; validation does not infer approval.
- Independent audit proves paper/live isolation, secret redaction, kill-switch blocking, audit logging, and failure-closed behavior.
- Approval artifact validates before submit/cancel-capable code runs.

Required approval artifact:
- `tmp/alpaca-paper-readiness/phase-6-paper-execution-approval.json`

Current artifact exists and records approval in principle, but implementation remains blocked until WF67 validators, wrapper, kill switch, audit log, and scoped paper-trade/pilot artifacts are clean. Any draft, missing, expired, non-paper-only, live-enabled, or ambiguous artifact blocks Phase 6/WF67.

## Phase 5 manual paper-pilot reconciliation

Phase 5 remains manual order placement by Randall plus read-only OpenClaw reconciliation afterward.

Required artifact:
- `tmp/alpaca-paper-readiness/manual-pilot-reconciliation.json`

Minimum artifact fields:
- schema version, workflow, phase, reconciliation id, generated timestamp, and status
- source order-preview id/path and preview validator status
- Randall manual-placement attestation with `placed_manually_in_alpaca_ui=true`
- read-only observation proof: paper endpoint, paper account mode, GET-only methods, live endpoint detected false
- comparison of preview versus observed paper order/fill/position delta
- validation summary for isolation, no-submit guard, kill switch, audit log, and secret redaction
- authority truth fields: OpenClaw submission false, cancel/replace false, paper submit allowed false, live submit allowed false, trade/account action allowed false, next phase authorized false
- owner review required and explicit statement that reconciliation does not authorize Phase 6

## Relationship to other workflows

- WF56/WF58 can produce recommendation/proposal objects.
- Those objects may feed non-executable order previews later.
- They do not grant brokerage authority.
- Canonical note/model mutation approval does not equal paper trading approval.
- Paper trading proof does not change real portfolio truth.

## Final approval criteria before WF67 paper submit/cancel can be called ready

Minimum criteria:
- WF63 continuity note exists.
- WF67 continuity note exists.
- This guardrail note exists.
- Phase 0 policy artifact validates.
- Phase 6/WF67 approval artifact validates.
- Credential-handling procedure and read-only proof schema exist with no secrets.
- Read-only paper connection proof validates.
- Paper/live isolation validates.
- Paper-execution guard validates and allows only the exact wrapper.
- Paper-trade request and paper-cancel request schemas validate.
- Order-preview schema and risk validators pass.
- Shadow mode runs clean across ordinary windows or is explicitly superseded by a scoped pilot artifact.
- Kill switch blocks when disabled/missing and enables only short-lived paper submit/cancel when explicitly set.
- Audit log validates and contains no secrets.
- First paper submit/cancel uses a bounded scoped paper-trade/pilot artifact.
- Main-session final check confirms the request matches the approved scope.
