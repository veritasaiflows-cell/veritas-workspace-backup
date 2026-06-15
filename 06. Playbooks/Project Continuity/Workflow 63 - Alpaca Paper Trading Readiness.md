# Workflow 63 - Alpaca Paper Trading Readiness

## Objective

Open a safe path toward Alpaca paper trading without widening live-trading, brokerage, account, or money-movement authority prematurely.

WF63 starts as **read-only brokerage observability plus order-preview discipline**. It is not approval for OpenClaw to submit paper orders.

## Current state

Status: **Phase 1 GET-only paper connection proof passed; Randall approved paper-only submit/cancel posture on 2026-05-17; submit/cancel implementation moved to WF67 guardrail workflow**.

Randall made WF63 the priority on 2026-05-14. Parallel review found no active verified Alpaca/OpenClaw integration in the workspace. Existing finance workflows can generate capital-deployment recommendations and guarded note/model mutation proposals, but they do not create brokerage/API execution authority.

Current verdict:
- Randall explicitly approved the Phase 1 GET-only paper endpoint connection proof on 2026-05-15 at 08:19 MST, with redacted audit and no-submit constraints
- `scripts/alpaca_read_only_connection_proof.py` now owns the repeatable proof run: it creates a short-lived read-only kill switch, checks only paper-specific credential variable names, uses `GET` only against `https://paper-api.alpaca.markets`, writes redacted proof/audit artifacts, and has no submit/cancel/replace path
- after Randall configured paper-only credentials on 2026-05-17, the approved GET-only proof passed: account metadata, positions, and orders were read from the exact paper endpoint with status 200; secrets and raw response bodies were not persisted
- not yet ready for paper-order submission or cancellation by OpenClaw until WF67 wrapper/validator/approval artifacts validate cleanly
- not ready for live Alpaca integration
- not ready for scheduled or autonomous trading actions
- non-executable order previews and shadow-mode reports can now be generated from review-only recommendation/proposal objects, but they remain blocked surfaces and cannot become approval or brokerage authority
- Randall's 2026-05-17 paper-only submit/cancel approval is recorded as a narrow simulation-lane doctrine exception; it does not authorize live trading, replace orders, money movement, account settings changes, live endpoints/credentials, or inferred owner approval

## Existing Alpaca material / archived references

Archived-only material exists under:
- `09. Archive/temp-skill-inspect - Archived/portfolio-manager/portfolio-manager/SKILL.md`
- `09. Archive/temp-skill-inspect - Archived/portfolio-manager/portfolio-manager/README.md`
- `09. Archive/temp-skill-inspect - Archived/portfolio-manager/portfolio-manager/references/alpaca-mcp-setup.md`
- `09. Archive/temp-skill-inspect - Archived/portfolio-manager/portfolio-manager/scripts/test_alpaca_connection.py`

That package is Claude/Alpaca-MCP oriented and is not active OpenClaw infrastructure. No active Alpaca skill, MCP tool, connector script, or paper-trading workflow is verified in the live workspace.

Known dependency posture from read-only inspection:
- `requests` appears available
- `alpaca_trade_api`, `alpaca`, and `alpaca_py` were not found as active verified dependencies
- no workspace Python package manifest was found

## Phase 0 - Policy and architecture lock

Goal: define the WF63 contract before touching credentials or external Alpaca endpoints.

Allowed now:
- inspect workspace files
- create guardrail notes and readiness artifacts
- create validators that fail closed while credentials/connection proof are absent
- design read-only connector contracts
- generate non-executable order-preview schemas

Blocked now:
- entering or storing credentials in notes/chat
- checking environment variables for secrets without explicit approval
- mutating OpenClaw config/auth/runtime surfaces
- calling Alpaca APIs
- submitting, replacing, or cancelling paper orders
- any live endpoint or live credential use

Required Phase 0 proof:
- `07. Risk/Alpaca Paper Trading Guardrails.md`
- `tmp/alpaca-paper-readiness/phase-0-policy.json`
- `tmp/alpaca-paper-readiness/wf63-readiness-report.json`
- `tmp/dashboard-data.json` / `tmp/veritas-command-center.html` expose the WF63 readiness-only Command Center card.

## Phase 1 - Read-only paper connection verification

Allowed only after Randall approves credential handling and connection scope:
- read Alpaca paper account metadata
- read paper positions
- read open/closed paper orders
- read paper portfolio history if useful

Blocked:
- `submit_order`
- cancel/replace order
- any POST/PATCH/DELETE
- live endpoint
- live credentials
- account settings changes

Credential/proof scaffolding artifacts:
- `06. Playbooks/Operating Procedures/Alpaca Paper Credential Handling Procedure.md`
- `tmp/alpaca-paper-readiness/read-only-connection-proof.schema.json`
- `tmp/alpaca-paper-readiness/phase-1-2-readiness-spec.json`

Required proof artifact, written by the approved Phase 1 connection runner:
- `tmp/alpaca-paper-readiness/read-only-connection-proof.json`

Current proof state:
- status `ok` as of `2026-05-18T01:16:56Z`
- base URL exactly `https://paper-api.alpaca.markets`
- account metadata, positions, and orders read checks are true
- live endpoint detected false; write methods available false; allowed methods `GET` only; blocked methods POST/PATCH/PUT/DELETE
- selected credential variable names are paper-specific: `ALPACA_PAPER_API_KEY_ID` and `ALPACA_PAPER_API_SECRET_KEY`
- secrets, headers, and raw response bodies were not persisted
- `tmp/alpaca-paper-readiness/kill-switch.json` was created as a short-lived read-only paper access gate with submit/live flags false
- `tmp/alpaca-paper-readiness/audit-log.jsonl` contains redacted read-only proof events only
- Claude safety audit returned **SAFE WITH GAPS** on 2026-05-15: no critical runtime safety failures, no API call, no submit path, no live endpoint path, and no secret exposure; main-session follow-up capped kill-switch TTL at 120 minutes, documented the live-endpoint split-string guard, added fail-closed unexpected-exception output, and aligned `phase-0-policy.json` / validator wording so non-executable preview and shadow scaffolding are explicit without implying brokerage authority

Required fields:
- status `ok|blocked`
- base URL exactly `https://paper-api.alpaca.markets`
- `account_mode=paper`
- `live_endpoint_detected=false`
- `write_methods_available=false`
- orders and positions read-only checks complete
- secrets redacted
- trade/account action allowed false

## Phase 2 - Paper/live isolation validator

Required validator:
- `scripts/alpaca_paper_readiness_validator.py` initially owns fail-closed policy/readiness checks.

Future dedicated validator may be split out as:
- `scripts/alpaca_paper_live_isolation_validator.py`

Fail closed if:
- read-only connection proof is required but absent
- base URL is not exactly paper API
- live endpoint appears in active Alpaca config or proof
- live or ambiguous credential variable names are selected for use
- order-submit paths are enabled
- HTTP wrapper allows non-GET methods
- secrets are printed or persisted

## Phase 3 - Order preview contract only

Goal: convert Veritas recommendations into **non-executable order intent previews**.

Artifact path:
- `tmp/alpaca-paper-readiness/order-previews/<id>.json`

Initial constraints:
- limit orders only
- no market orders
- no shorting
- no margin
- no leverage
- no options
- no crypto
- no bracket/OTO/OCO complexity
- `owner_decision_required=true`
- `owner_approval_granted=false`
- `paper_submit_allowed=false`
- `live_submit_allowed=false`
- `trade_or_account_action_allowed=false`

Current scaffold:
- `scripts/alpaca_order_preview_generator.py` converts current capital-deployment recommendation/proposal packets into non-executable preview artifacts under `tmp/alpaca-paper-readiness/order-previews/`.
- Current generated previews intentionally carry missing owner limit-price and sizing blockers where the source proposal lacks explicit owner-approved order inputs. That is correct fail-closed behavior, not a defect.
- `scripts/alpaca_paper_readiness_validator.py --validate-order-previews` validates preview authority flags, limit/day-only restrictions, blocked order classes, no-submit posture, and no portfolio/account mutation.

## Phase 4 - Dry-run / shadow mode

Goal: run order-preview generation across ordinary finance windows with zero broker writes.

Required:
- `would_submit=false`
- no Alpaca order endpoint calls
- compare intended preview vs next-day paper-account state after manual activity only
- record missed, invalid, stale, or contradictory previews

Minimum proof before any manual pilot:
- several ordinary market-window dry runs
- clean paper/live isolation validator
- clean order-preview validator
- clean no-submit static/runtime guard
- kill-switch proof
- audit-log proof with no secrets

Current scaffold:
- `scripts/alpaca_order_preview_generator.py` writes `tmp/alpaca-paper-readiness/shadow-mode-report.json` with `would_submit=false`, no endpoint calls, no brokerage writes, and no portfolio/account mutation.
- `scripts/alpaca_paper_readiness_validator.py --validate-shadow-mode` validates the shadow-mode no-submit/no-call authority contract.
- `scripts/alpaca_paper_readiness_validator.py --write-no-submit-guard-report` writes `tmp/alpaca-paper-readiness/no-submit-guard-report.json`, a static active-surface scan that confirms no submit/cancel/replace/live-endpoint patterns exist outside allowed policy/validator references.
- Proof on 2026-05-15: compile passed; targeted scaffold test passed; WF63 validator returned `status=ok`, `0 critical`, `0 warning`, preview count `3`, shadow preview count `3` for preview/shadow scaffolding. Later no-submit guard proof returned `status=ok`, `0 critical`, `0 warning`. Full WF63 readiness remains blocked only because the read-only account/positions/orders connection proof is absent/blocked.

## Phase 5 - Owner-approved manual paper-order pilot only

Safe pilot shape:
1. Veritas generates one paper order preview.
2. Randall manually places the paper order in Alpaca UI.
3. OpenClaw performs read-only reconciliation afterward.
4. No OpenClaw API submit occurs.

Entry requirements before Phase 5 can start:
- Randall explicitly approves a single manual pilot reconciliation scope.
- Phase 1 read-only connection proof is clean and current.
- Phase 2 paper/live isolation validator is clean.
- Phase 3 order-preview validator is clean for the exact preview.
- Phase 4 shadow-mode report is clean enough for one manual pilot.
- no-submit static/runtime guard is clean: `tmp/alpaca-paper-readiness/no-submit-guard-report.json` shows no active submit/cancel/replace/live-endpoint path exists.
- kill switch exists, is unexpired, and enables read-only paper access only.
- audit log validator proves append-only logging and secret redaction.

Required artifact:
- `tmp/alpaca-paper-readiness/manual-pilot-reconciliation.json`

Minimum reconciliation artifact schema:
- `schema_version`
- `workflow="WF63 - Alpaca Paper Trading Readiness"`
- `phase="phase_5_manual_pilot_reconciliation"`
- `reconciliation_id`
- `generated_at_utc`
- `status` (`blocked|pending_owner_manual_order|reconciled|mismatch|invalid`)
- `authority` object with all of these exact truths: `read_only_reconciliation_allowed=true`, `openclaw_order_submission_performed=false`, `openclaw_cancel_replace_performed=false`, `paper_submit_allowed=false`, `live_submit_allowed=false`, `trade_or_account_action_allowed=false`, `next_phase_authorized=false`
- `source_preview` object: preview id/path, ticker, side, order type, limit price, quantity/notional, time in force, risk-check summary, preview validator status
- `owner_manual_order` object: Randall manual-placement attestation, Alpaca UI order id if Randall provides it, placed-at timestamp if known, and `placed_manually_in_alpaca_ui=true`
- `read_only_observation` object: observed-at timestamp, base URL exactly `https://paper-api.alpaca.markets`, `account_mode=paper`, HTTP methods used `["GET"]`, live endpoint detected false, order status/fill summary/position delta as read-only observations
- `comparison` object: preview-vs-observed match status, mismatches, stale-data warnings, and whether any observed account change lacks a matching Randall manual-order attestation
- `validation` object: paper/live isolation status, no-submit guard status, kill-switch status, audit-log status, secrets-redacted status
- `audit` object: audit event ids or offsets for preview generation, owner-attestation capture, read-only observation, reconciliation result, and validator result
- `owner_review` object: `owner_review_required=true`, recommended next action, and explicit statement that reconciliation does not authorize Phase 6

Phase 5 closeout rule:
- A clean reconciliation proves only that manual-paper-order reconciliation worked. It does not authorize OpenClaw submission, cancel/replace, live trading, portfolio mutation, or Phase 6.

## Phase 6 / WF67 - Bounded paper execution guardrail

Approved in principle by Randall on 2026-05-17 for Alpaca paper-only submit/cancel authority. Implementation remains gated and moves to WF67.

This phase crosses the prior standing `never submit orders` boundary even if paper-only. It requires a written doctrine exception, independent audit, paper-only submit/cancel wrapper, kill-switch proof, live-isolation proof, redacted audit log, and explicit scoped paper-trade/pilot artifact before any submit/cancel call.

Current Phase 6/WF67 architecture posture:
- Approval posture: paper-only submit/cancel approved by Randall on 2026-05-17.
- Implementation posture: not yet implemented; no submit/cancel-capable wrapper is ready.
- Live posture: live endpoint, live credentials, live trading, account settings changes, money movement, replace/close/liquidate, margin/short/options/crypto/complex order paths remain blocked.
- A validated approval artifact now records the paper-only doctrine exception at `tmp/alpaca-paper-readiness/phase-6-paper-execution-approval.json`.
- WF67 owns the implementation-readiness path; WF63 remains the read-only/proof foundation.
- Clean Phase 1 proof, Phase 4 shadow mode, or Phase 5 reconciliation is not per-order approval by itself.

Required doctrine-exception checklist before any paper submit/cancel implementation runs:
- Randall's 2026-05-17 approval is recorded as the conflict exception to the prior no-order-submission boundary.
- Exception is paper-only, scoped, revocable, and never live.
- Live endpoint and live credentials remain forbidden with no fallback.
- Submit scope starts with simple paper limit/day orders only; cancel scope is paper-order cancellation only; replace/market/short/margin/leverage/options/crypto/complex orders remain blocked unless separately approved.
- Independent audit confirms paper/live isolation, no live credential selection, no secret leakage, kill-switch behavior, audit logging, and failure-closed behavior.
- Approval names the exact wrapper, exact endpoint allowlist, exact risk caps, exact operator review step, and exact rollback/disable path.
- Approval artifact validates before any submit/cancel-capable code runs.
- A scoped paper-trade instruction or bounded pilot artifact remains required; model confidence, clean validation, and generated packet quality cannot infer approval.

Required Phase 6/WF67 approval artifact:
- Path: `tmp/alpaca-paper-readiness/phase-6-paper-execution-approval.json`
- Required fields: `schema_version`, `workflow`, `phase`, `approval_status`, `approved_by`, `approved_at_utc`, `doctrine_exception_acknowledged`, `paper_only=true`, `paper_submit_allowed=true`, `paper_cancel_allowed=true`, `live_submit_allowed=false`, `live_endpoint_forbidden=true`, `allowed_order_scope`, `blocked_order_scope`, `required_preview_validator_status`, `required_isolation_validator_status`, `required_guard_transition`, `required_kill_switch_state`, `required_audit_log_fields`, `secret_redaction_required=true`, `rollback_disable_path`, `scoped_paper_trade_artifact_required=true`, `no_inferred_approval=true`
- Any missing, expired, draft, contradictory, live-enabled, or ambiguous artifact blocks paper submit/cancel.

Guard requirements:
- Before WF67 implementation is complete: the guard must still fail if active submit/cancel/replace paths exist outside explicit documentation and future approved wrapper work.
- Runtime connector must deny live endpoint/credentials and deny all methods except the exact approved paper submit/cancel methods.
- The guard must prove no active replace, close-position, liquidation, transfer, account-setting, live endpoint, or money-movement path is callable.
- The guard report should live at `tmp/alpaca-paper-readiness/paper-execution-guard-report.json` and include scanned paths, allowed wrapper findings, forbidden-pattern findings, runtime-method policy, result, and timestamp.

Kill-switch requirements:
- Missing, malformed, expired, disabled, or contradictory kill-switch state blocks every Alpaca call.
- Paper submit/cancel kill switch must be short-lived, paper endpoint locked, wrapper-scoped, and immediately disableable.
- Kill-switch state never grants approval for a specific order without the scoped paper-trade/pilot artifact.

Audit-log requirements:
- Append-only JSONL under `tmp/alpaca-paper-readiness/audit-log.jsonl`.
- Required event fields: timestamp UTC, workflow, phase, event id, actor (`veritas|script|randall_manual_attestation|validator`), action, method class, endpoint mode, endpoint path class without query secrets, request intent, preview id if applicable, approval artifact id if applicable, validator statuses, kill-switch status, guard status, result (`allowed|blocked|observed|submitted|cancelled|reconciled|mismatch|error`), reason code, artifact paths, redaction status, and secret material present false.
- Secret-redaction rule: never persist or print API keys, secret keys, bearer tokens, auth headers, account secrets, raw environment values, or full request headers. Any detected secret-shaped value must be replaced with `[REDACTED]`, and the event must set `redaction_status="redacted"` plus a non-secret reason code.

## Required guardrails

- Paper/live isolation: paper endpoint only, no live fallback.
- Credential handling: secrets outside notes/chat/workspace artifacts; redacted output only.
- Paper submit/cancel remains disabled until WF67 validates the exact wrapper and guard transition; replace/live/account/money-movement paths remain forbidden.
- Kill switch: default disabled; missing kill-switch artifact blocks.
- Audit log: append-only JSONL under `tmp/alpaca-paper-readiness/`, redacted by default.
- Approval gates: clean validation never equals owner approval.
- Workflow separation: WF56/WF58 recommendations may feed previews but cannot become brokerage authority.

## Stop lines

Never under current WF63/WF67 posture:
- live trading
- paper order submission/cancellation outside the WF67 validated wrapper and scoped paper-trade/pilot artifact
- money movement
- account setting changes
- live endpoint or live credential use
- replace orders, close-position, liquidation, or transfer paths
- shorting, margin, leverage, options, crypto, or complex order types
- treating WF56/WF58 proposal validation as brokerage approval
- treating clean shadow mode as owner approval
- storing secrets in notes, memory, logs, or generated artifacts

## Dependencies / crosslinks

- WF56: proposal/apply guardrails for canonical note/model mutations only.
- WF58: capital recommendation packets can eventually feed non-executable previews.
- WF60/WF61: research/opportunity signals can inform candidates, not action authority.
- `07. Risk/Risk Rules.md`: risk sizing and escalation framework.
- `07. Risk/Alpaca Paper Trading Guardrails.md`: WF63-specific brokerage guardrails.

## Next action

WF63 Phase 1 read-only proof is complete. WF67 is now the active next workflow: design and validate the exact paper-only submit/cancel wrapper, guard transition, kill-switch mode, audit event contract, and scoped paper-trade/pilot artifact before any paper submit/cancel call.

## Key files / future proof artifacts

Current:
- `06. Playbooks/Project Continuity/Workflow 63 - Alpaca Paper Trading Readiness.md`
- `07. Risk/Alpaca Paper Trading Guardrails.md`
- `scripts/alpaca_paper_readiness_validator.py`
- `scripts/alpaca_order_preview_generator.py`
- `scripts/test_alpaca_order_preview_scaffolding.py`
- `tmp/alpaca-paper-readiness/phase-0-policy.json`
- `tmp/alpaca-paper-readiness/wf63-readiness-report.json`
- `tmp/alpaca-paper-readiness/order-previews/*.json`
- `tmp/alpaca-paper-readiness/shadow-mode-report.json`
- `06. Playbooks/Operating Procedures/Alpaca Paper Credential Handling Procedure.md`
- `tmp/alpaca-paper-readiness/read-only-connection-proof.schema.json`
- `tmp/alpaca-paper-readiness/phase-1-2-readiness-spec.json`
- `tmp/dashboard-data.json`
- `tmp/veritas-command-center.html`

Future:
- `tmp/alpaca-paper-readiness/read-only-connection-proof.json`
- `tmp/alpaca-paper-readiness/order-previews/*.json`
- `tmp/alpaca-paper-readiness/shadow-mode-report.json`
- `tmp/alpaca-paper-readiness/manual-pilot-reconciliation.json`
