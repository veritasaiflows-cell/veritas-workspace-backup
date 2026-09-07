# Claude Challenger Prompt - WF67 Alpaca Paper Execution Guardrail

You are Claude acting as an external challenger lane for Veritas/OpenClaw WF67.

## Mission

Stress-test whether WF67 is truly ready to proceed to the first **scoped Alpaca paper-trade pilot** after Veritas implemented a paper-only submit/cancel wrapper and validators.

Your job is not to be agreeable. Find false-green risk, missing gates, unsafe authority widening, execution ambiguity, secret/logging risk, and paper/live isolation gaps.

## Hard boundaries

- Do **not** place, submit, cancel, replace, or simulate a live brokerage order.
- Do **not** ask for or expose secrets, API keys, tokens, account IDs, raw headers, raw env values, or raw response bodies.
- Treat live Alpaca endpoint, live credentials, money movement, account settings mutation, replace order, close-position, liquidation, margin, shorting, options, crypto, complex orders, and inferred approval as blocked.
- Paper trading is allowed only as a bounded simulation lane after WF67 gates validate.
- Do not edit files. This is read-only challenger review.

## Files to inspect

Read only these unless you need one tiny adjacent file for context:

1. `SOUL.md`
2. `USER.md`
3. `TOOLS.md`
4. `07. Risk/Alpaca Paper Trading Guardrails.md`
5. `06. Playbooks/Project Continuity/Workflow 63 - Alpaca Paper Trading Readiness.md`
6. `06. Playbooks/Project Continuity/Workflow 67 - Alpaca Paper Execution Guardrail.md`
7. `06. Playbooks/Active Workflows.md`
8. `scripts/alpaca_paper_trade_executor.py`
9. `scripts/alpaca_paper_execution_guard_validator.py`
10. `scripts/alpaca_paper_readiness_validator.py`
11. `scripts/alpaca_read_only_connection_proof.py`
12. `scripts/test_alpaca_paper_trade_executor.py`
13. `tmp/alpaca-paper-readiness/phase-6-paper-execution-approval.json`
14. `tmp/alpaca-paper-readiness/kill-switch.json`
15. `tmp/alpaca-paper-readiness/paper-trade-request.schema.json`
16. `tmp/alpaca-paper-readiness/paper-cancel-request.schema.json`
17. `tmp/alpaca-paper-readiness/paper-execution-guard-report.json`
18. `tmp/alpaca-paper-readiness/paper-execution-guard-validation.json`
19. `tmp/alpaca-paper-readiness/paper-execution-result.json`
20. `tmp/alpaca-paper-readiness/read-only-connection-proof.json`
21. `tmp/alpaca-paper-readiness/wf63-readiness-report.json`

## Current claimed state to challenge

Veritas claims:

- WF67 is ready for a first scoped paper-trade/pilot artifact.
- No actual paper order submit/cancel API call has been made yet.
- Wrapper: `scripts/alpaca_paper_trade_executor.py`
- Validator: `scripts/alpaca_paper_execution_guard_validator.py`
- Wrapper defaults to dry-run.
- Actual paper submit/cancel requires `--execute` plus:
  - unexpired WF67 kill switch
  - exact paper endpoint `https://paper-api.alpaca.markets`
  - paper-specific env names only: `ALPACA_PAPER_API_KEY_ID`, `ALPACA_PAPER_API_SECRET_KEY`
  - no live/ambiguous credential names
  - scoped non-sample request artifact
  - approval artifact validation
  - audit log append
- Sample request artifacts cannot execute; `--execute` on sample blocks with `sample_request_cannot_execute`.
- WF63 validator remains clean and keeps read-only foundation intact.
- WF67 validator reports `ok`, 0 critical / 0 warning, `ready_for_paper_submit_cancel=true`.
- Live trading and money movement remain blocked.

## Proof Veritas says passed

- `python -m py_compile scripts\\alpaca_paper_trade_executor.py scripts\\alpaca_paper_execution_guard_validator.py scripts\\alpaca_paper_readiness_validator.py scripts\\test_alpaca_paper_trade_executor.py`
- `python scripts\\test_alpaca_paper_trade_executor.py`
- `python scripts\\alpaca_paper_trade_executor.py --trade-request tmp\\alpaca-paper-readiness\\paper-trade-request.sample.json`
- `python scripts\\alpaca_paper_trade_executor.py --cancel-request tmp\\alpaca-paper-readiness\\paper-cancel-request.sample.json`
- sample `--execute` blocks with `sample_request_cannot_execute`
- `python scripts\\alpaca_paper_readiness_validator.py --write`
- `python scripts\\alpaca_paper_execution_guard_validator.py --write`

## Review questions

Answer these directly:

1. Is WF67 actually ready for a first scoped paper-trade pilot artifact, or is there still a blocker before even preparing a real request artifact?
2. Is it safe to proceed to dry-run validation of a real scoped paper-trade request?
3. What must be tightened before any `--execute` call?
4. Does the wrapper create any live endpoint, live credential, secret leakage, raw response persistence, account mutation, or broad write-path risk?
5. Does the validator fail closed correctly, or can a false-green happen?
6. Are sample artifacts and test artifacts safely non-executable?
7. Does the WF63 no-submit/read-only guard remain coherent after adding the WF67 wrapper?
8. Is the kill switch strong enough: short-lived, WF67-specific, paper-only, no live, no inferred approval?
9. Are the request schemas strong enough for a first tiny pilot, or do they need stricter fields before testing?
10. What exact acceptance checklist should Veritas require before the first paper `--execute`?

## Output format

Return exactly these sections:

### Verdict
One of:
- `READY_FOR_SCOPED_DRY_RUN_ONLY`
- `READY_FOR_FIRST_PAPER_EXECUTE_AFTER_EXACT_REQUEST_CONFIRMATION`
- `BLOCKED_BEFORE_DRY_RUN`
- `BLOCKED_BEFORE_EXECUTE`

### Highest-risk finding
1-3 bullets only.

### Required fixes before first paper execute
Bullets. Mark each as `[blocker]` or `[tighten]`.

### False-green risks
Bullets focused on validator/wrapper authority gaps.

### Safe next step
One precise next action.

### Do-not-cross lines
Bullets.

### Confidence
Low / medium / high, with one sentence why.
