# Heartbeat Tasks

Use heartbeat for lightweight useful maintenance, not noise.

## Core rule

On a heartbeat poll:
1. check whether a materially new fact should be logged to today's daily note
2. promote only durable truths that clearly deserve promotion
3. keep `MEMORY.md` curated
4. stay quiet if nothing important needs attention

If nothing meaningful needs attention, reply exactly `HEARTBEAT_OK`.

## Guardrails

- prefer silence at night unless something genuinely matters
- do not repeat old tasks just because they existed in prior chats
- do not turn heartbeat into a major project
- do not advance the workflow queue from heartbeat; at most flag a clear queue/registry/continuity contradiction or missing daily log entry
- do not nag about commits during heartbeats
- do not append daily-note entries for unchanged state or routine rechecks
- if today's note already has the same topic, update/merge it instead of appending another bullet
- heartbeat is not a chain log or replay surface

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
- `tmp/current-window-artifacts.md`

Heartbeat may flag or log a material issue when:
- the validator is blocked/critical
- the recommendation bundle is missing after a completed finance window
- authority widens unexpectedly (`proposal_apply_allowed=true`, per-packet approval inferred, trade/account action allowed, or packet-level apply flags true without a separate exact apply artifact)
- generated packets conflict with canonical owner notes in a way that could mislead a decision

Heartbeat must not run the full finance chain, self-apply a capital recommendation packet, infer approval from clean validation, touch trades/accounts/brokerage/money movement, or change sizing/sleeve/cash/risk-rule/execution entitlement from a heartbeat alone.
