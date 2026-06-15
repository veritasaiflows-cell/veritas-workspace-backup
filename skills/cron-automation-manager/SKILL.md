---
name: "cron-automation-manager"
description: "Require xhigh for bounded Spark cron canaries."
---

# Spark Cron Canary and Helper Effort Rule

Use `codex/gpt-5.3-codex-spark` only for bounded, script-owned cron canaries and bounded QA/audit/pre-work helper lanes until monitor proof is clean. Do not migrate cron globally.

## Mandatory Thinking Posture

Every Spark cron job or Spark helper/subagent lane must use `xhigh` thinking.

Reason:
- Spark is cheap enough that lower effort is not worth the quality risk by default.
- The 2026-06-07 WF79 effort comparison showed Spark quality improved materially at `xhigh`.
- Spark high still repeated a path-hallucination family; Spark xhigh produced the best Spark result with clean referenced paths.

Do not lower Spark thinking effort unless repeated measured proof shows lower effort is equally reliable for the same task family.

## Eligible Spark Cron Jobs

Use Spark only for:
- isolated `agentTurn` jobs where scripts do the real work
- exact-command proof refreshers
- known JSON artifact inspection
- compact `NO_REPLY` or status response contracts
- jobs with no external delivery by default
- jobs with no cron/config/auth/runtime mutation
- jobs with no canon/portfolio mutation
- jobs with no paper/live/brokerage/account action
- jobs with no owner approval inference

## Eligible Spark Helper Lanes

Use Spark only for:
- bounded QA/audit/pre-work challenger lanes
- narrow proof/canary lanes
- path/contract sanity checks where main session verifies output
- distinct-output JSON artifacts, unless a later workflow explicitly widens scope

## Do Not Use Spark For

Do not use Spark for:
- primary implementation ownership
- main-session continuation or PM dispatcher judgment
- finance synthesis
- portfolio/canon maintenance judgment
- paper execution readiness interpretation
- weekly multi-skill finance refreshes with broad evidence synthesis
- any job whose correctness depends on nuanced stop-line interpretation rather than script validators
- any lane where a wrong path, fragile command, or over-broad scope would create operational risk without main verification

## Canary Monitoring Pattern

1. Pick one or two low-risk isolated jobs with recent successful baseline runs.
2. Set `payload.model` to `codex/gpt-5.3-codex-spark` and `payload.thinking` to `xhigh`.
3. Preserve schedule, session target, delivery, timeout, and stop lines.
4. Record baseline model, required thinking posture, and duration in a monitor artifact.
5. Let jobs run in their natural window; do not force market-window finance jobs just to test model routing.
6. Validate with `python scripts\cron_spark_canary_monitor.py --write --validate` plus `tmp/cron-freshness-spine.json` and recent cron run history.
7. If monitor status is blocked, roll the canary jobs back to the prior model before expanding.
8. Expand only after at least one clean natural run per canary and no missed warnings, false `NO_REPLY`, duration regression, path/command hallucination, or authority drift.

## Boundary

This rule authorizes model/thinking selection for bounded cron canaries and QA/audit/pre-work challenger lanes only. It does not authorize cron expansion, external delivery, config/auth/runtime mutation, finance/canon/portfolio mutation, paper/live/account action, implementation ownership, or owner approval inference.
