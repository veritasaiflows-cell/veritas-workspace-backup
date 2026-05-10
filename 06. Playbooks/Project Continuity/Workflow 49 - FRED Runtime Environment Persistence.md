# Workflow 49 - FRED Runtime Environment Persistence

## Objective
- Make FRED-backed macro inputs reliably available to OpenClaw child processes without storing API keys in workspace files or chat-derived artifacts.

## Current State
- Queued from finance-chain cleanup residue.
- FRED-backed 2Y/credit inputs worked when `FRED_API_KEY` was passed ephemerally to child script runs.
- The OpenClaw runtime did not inherit `FRED_API_KEY` persistently from process, user, machine, or checked registry environment surfaces at the time of inspection.
- The key was exposed in chat and should be rotated.

## Last Meaningful Progress
- Ephemeral script run proved the key works and materially cleans macro inputs.
- Workspace scan for the exposed key prefix found no workspace file hits after the run.

## Outstanding
- Rotate the exposed FRED key outside chat.
- Configure the replacement key in the correct Windows environment scope for the OpenClaw runtime user/process.
- Restart or refresh OpenClaw/Gateway inheritance safely.
- Verify scripts see the key without embedding it in commands, files, logs, or chat.

## Blockers / Trust Gaps
- Do not write API keys into workspace files, config notes, logs, shell history, or generated artifacts.
- Do not claim FRED-backed macro precision is reliable until the runtime can inherit the key without per-command injection.

## Next Action
- Operator-gated runtime/config pass after Randall rotates or confirms the replacement key is installed in the correct environment scope.

## Key Files
- `scripts/policy_expectations_refresh.py`
- `scripts/credit_spread_refresh.py`
- `scripts/market_state_refresh.py`
- `tmp/policy-expectations.json`
- `tmp/credit-spreads.json`
- `tmp/market-state.json`
- `TOOLS.md` - environment rule surface.

## Acceptance Gate
- OpenClaw child process sees `FRED_API_KEY` without the key being passed in chat/tool command text.
- FRED-backed macro refresh scripts run and produce current 2Y/credit inputs without `FRED_API_KEY not set` warnings.
- Secret-prefix scan of workspace returns no hits.

## Automation / Refresh Path
- Operator-gated because it touches credentials/runtime environment.
