# Heartbeat Tasks

Use heartbeat for lightweight useful maintenance, not noise.

## Core rule

On a heartbeat poll:
1. check whether a materially new fact should be logged to today's daily note
2. promote only durable truths that clearly deserve promotion
3. keep `MEMORY.md` curated
4. check for safe continuation candidates only when an existing workflow/operator packet already defines the next bounded action
5. stay quiet if nothing important needs attention

If nothing meaningful needs attention, reply exactly `HEARTBEAT_OK`.

## Guardrails

- prefer silence at night unless something genuinely matters
- do not repeat old tasks just because they existed in prior chats
- do not turn heartbeat into a major project
- do not directly advance the workflow queue from heartbeat; at most flag a clear queue/registry/continuity contradiction, missing daily log entry, stale proof, or bounded continuation candidate
- do not run major phase work from heartbeat; if an existing operator packet/trust block proves a safe next action, heartbeat may queue or wake a bounded main-session/isolated follow-up instead of implementing it inline
- do not nag about commits during heartbeats
- do not append daily-note entries for unchanged state or routine rechecks
- if today's note already has the same topic, update/merge it instead of appending another bullet
- heartbeat is not a chain log or replay surface

## Safe continuation candidate pilot

Heartbeat may produce or refresh lightweight continuation signals when all are true:
- the workflow appears in `06. Playbooks/Active Workflows.md`
- the next action is already defined by a current operator packet, run summary, cron proof, or validated continuity note
- the action is read-only, report-only, validator-only, fixture-only, proposal-only, or bounded handoff-only
- no stop line requires Randall's decision first
- no canon/portfolio mutation, SQL import, external delivery, config/auth/channel/runtime change, cleanup move/delete/archive, paper/live execution, brokerage/account action, or owner approval inference is involved

Allowed heartbeat continuation actions:
- flag the candidate in chat or today's daily note when material
- refresh/classify current-window, ticker-debt, and cron-residue priority through the fixed bridge only: `python scripts\heartbeat_priority_handoff.py --write --validate`. It emits `tmp/heartbeat-priority-receipt.json` and can only route a dry-run main-session handoff; do not invoke `main_session_action_executor.py` or `main_session_escalation_consumer.py` directly from heartbeat.
- refresh a cheap review surface such as operator-packet validation when it does not perform major phase work
- wake or queue main-session review for an already-defined safe next action

Blocked heartbeat continuation actions:
- implementing a new workflow phase
- launching broad helper swarms
- changing cron definitions
- applying canonical notes or portfolio state
- running `main_session_escalation_consumer.py --execute-safe` or `main_session_action_executor.py --execute-safe`
- passing `--execute-safe` through any heartbeat continuation bridge
- invoking a priority bridge with `--context cron`, `--execute-one`, lane leasing, or agent/helper-launch flags; heartbeat must use `heartbeat_priority_handoff.py` with its fixed argv only
- importing SQL/ticker data
- changing customer/public delivery state
- paper/live trading or account actions

## Light finance freshness check

When useful, lightly check whether a live finance note is obviously stale relative to its own refresh policy.
If a major catalyst window or elapsed event makes a live note misleading, flag it or make a minimal cleanup.
Do not redo the full research stack from a heartbeat alone.

Main-session note/canon rule: Veritas / the main session is always responsible for keeping the notes layer and canon up to date. Heartbeat may flag or make minimal cleanup only when a live note is obviously misleading; broader canon reconciliation belongs to the main session, with owner-gated portfolio/trade boundaries preserved.

## WF58 / WF56 guarded portfolio-mutation watch

Randall approved the guarded portfolio note/model mutation workflow on 2026-05-14. Heartbeat may lightly check whether the scheduled finance-chain proof surfaces still preserve the approved posture:
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.md`
- `tmp/capital-deployment-recommendation-validation.json`
- `tmp/current-window-artifacts.json`

Heartbeat may flag or log a material issue when:
- the validator is blocked/critical
- the recommendation bundle is missing after a completed finance window
- authority widens unexpectedly (`proposal_apply_allowed=true`, per-packet approval inferred, trade/account action allowed, or packet-level apply flags true without a separate exact apply artifact)
- generated packets conflict with canonical owner notes in a way that could mislead a decision

Heartbeat must not run the full finance chain, self-apply a capital recommendation packet, infer approval from clean validation, touch trades/accounts/brokerage/money movement, or change sizing/sleeve/cash/risk-rule/execution entitlement from a heartbeat alone.
