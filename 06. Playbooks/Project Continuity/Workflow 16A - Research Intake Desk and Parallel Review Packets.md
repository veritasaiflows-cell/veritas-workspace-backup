# Workflow 16A - Research Intake Desk and Parallel Review Packets

## Objective
- Stand up the review-first research intake desk for company news, geopolitics, macro/policy shocks, management response tracking, and thesis-drift detection.
- Use parallel agents as a **contract-building and QA layer**, not as a freeform research swarm.
- Define the first three research-control-plane contracts before any recurring research cron is activated.

## Current Phase
- Held behind Workflow 17 / Workflow 18 protocol hardening
- Design / contract-definition only

## What this workflow owns
1. **Source Bundle Contract**
2. **Intake Packet Contract**
3. **Routing / Promotion Contract**

This workflow does **not** own canonical note mutation.
That belongs to Workflow 16B and remains gated even there.

## Operating posture
- Main Veritas session remains the manager, integrator, and trust owner.
- Worker lanes are role-bound and isolated.
- Workers can propose, challenge, and QA contracts or packet outputs.
- Workers do not mutate canonical notes.
- Workers do not move queue state.
- Workers do not publish final verdicts.
- Workers do not become a standing freeform research department.

## Phase 1 - Source Bundle Contract
### Parallel roles
| Agent | Job |
| --- | --- |
| Source-quality agent | Propose approved source tiers across filings, IR, earnings calls/transcripts, trusted financial media, macro data, and geopolitical sources |
| Coverage-gap agent | Check whether the bundle misses important sources by ticker, sector, macro sleeve, or geopolitical risk |
| Noise/risk agent | Define excluded sources, rumor rules, duplicate-event handling, and stop lines |
| Workflow integration agent | Decide what belongs in cron, what stays manual, and what can surface into dashboard / workbook / weekly brief review artifacts |

### Contract output
The source bundle contract must answer:
- approved source tiers
- approved sources by category
- blocked / low-confidence sources
- refresh cadence by source type
- ticker / macro sleeve coverage map
- what belongs in cron
- what requires manual review
- what is only allowed into review packets
- stop lines for rumor-heavy, low-confidence, duplicate, or unsourced events

### Best first version
Start narrow:
- company filings / IR
- earnings transcripts
- major financial news
- macro calendar / Fed / rates / inflation
- oil and geopolitical risk sources
- sector-specific sources for active names only

Do not try to build the full research universe at once.

## Phase 2 - Intake Packet Contract
### Parallel roles
| Agent | Job |
| --- | --- |
| Event detector | Identify what happened |
| Materiality scorer | Decide whether it matters to active theses, watchlist names, or portfolio posture |
| Thesis-drift agent | Compare the event against existing thesis assumptions |
| Evidence QA agent | Check source quality, conflicts, duplicates, and missing context |
| Routing agent | Decide where the packet should go: ignore, weekly brief, dashboard, thesis-review queue, or patch candidate |

### Required intake packet fields
Every packet must include:
- event title
- date / time
- affected ticker(s), sleeve, or macro theme
- source tier
- primary evidence
- secondary evidence
- confidence level
- materiality level
- thesis impact
- portfolio posture impact
- contradictions / uncertainty
- recommended routing
- canonical mutation allowed? **default: no**
- stop line triggered? yes / no
- next required human or agent review

## Phase 3 - Routing / Promotion Contract
### Routing logic
Use this baseline:
- low materiality + high confidence -> archive / weekly digest only
- medium materiality -> weekly intelligence or dashboard watch item
- high materiality -> thesis-review queue
- high materiality + stale canonical note -> canonical freshness patch candidate
- low confidence / rumor-heavy -> stop line, no promotion

### Required handoff decisions
The routing contract must define:
- what can appear in the dashboard as a watch/review item
- what can flow into workbook staging
- what belongs only in weekly intelligence
- what escalates to thesis-review queue
- what can become a canonical freshness patch candidate
- what must stop instead of routing anywhere

## Safe automation boundary
- scheduled source pulls or fetched packet assembly
- isolated review runs that write packet artifacts only
- contradiction scans and escalation tags
- synthesis prep for the main session

## Still human-gated
- final thesis impact judgment
- note promotion into watchlist / coverage / portfolio layers
- source disputes that require manual adjudication
- any recommendation that materially changes capital posture
- any decision to mutate canonical notes

## Review windows to define
- premarket
- post-close
- Sunday weekly synthesis
- event-driven ad hoc windows only if explicitly approved later

## Acceptance condition
- one approved source bundle
- one packet schema
- one routing / promotion contract
- one escalation taxonomy with stop lines
- one orchestrator-owned synthesis path
- no canonical note mutation in the first live version
- no live recurring research cron before these contracts are approved

## Next Action
- Wait for Workflow 17 / Workflow 18 closure.
- Then execute Phase 1 -> Phase 2 -> Phase 3 in order.
- Hand the approved routing / packet contracts to Workflow 16B.
