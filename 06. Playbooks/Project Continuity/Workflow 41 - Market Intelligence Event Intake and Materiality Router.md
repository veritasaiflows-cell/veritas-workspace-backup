# Workflow 41 - Market Intelligence Event Intake and Materiality Router

## Objective
- Make fresh intelligence autonomous enough to catch important market, macro, geopolitical, sector, and earnings events daily without granting canonical mutation authority.
- Convert approved source-tier and coverage inputs into reviewable event/materiality packets that can route into thesis, risk, promotion, or deployment review.

## Workflow under review
- Daily fresh-intelligence intake and materiality routing for active names, promotion-review names, macro/geopolitical sleeves, sector expansion candidates, and earnings/calendar events.

## Current phase
- Artifact-derived v1 router hardening is implemented and main-session QC passed on 2026-05-09.
- The current router remains a workspace-artifact sidecar, not broad external/news intake.
- 2026-05-19 audit-directed update: the canonical audit at `08. Audits/Financial Advisor and Real-Time Alerting Readiness Audit - 2026-05-19.md` and Randall's follow-up direction make FA/advisor-grade monitoring plus real-time/intraday alerting the primary goal. WF41 is reopened as a dependency lane for WF68, but only for event/materiality semantics and alert routing contracts. It does not own intraday data plumbing or delivery.

## Recommended next phase
- Support WF68 by defining how intraday trigger packets become `thesis_review`, `risk_review`, `promotion_review`, `deployment_review`, `no_route`, or `unresolved_truth` events.
- Keep broader external/news source-tier expansion separate and owner-gated.
- Do not widen to autonomous thesis updates, watchlist promotion, deployment-state mutation, portfolio-note mutation, or external crawling.

## Safe automation boundary
- allowed automatically: read-only source checks against approved source-tier map, active-name and queue inspection, event packet generation, unresolved-truth packet generation, no-route decisions, and `tmp/` or review-folder packet writes
- blocked automatically: canonical note mutation, promotion/demotion mutation, deployment-state mutation, portfolio/risk-rule mutation, owner-approval inference, and any trade/account action

## Inputs
- approved source-tier map from WF26
- active names
- promotion-review names
- macro/geopolitical sleeves
- sector expansion candidates
- earnings/calendar events

## Outputs
- event packets
- unresolved-truth packets
- no-route decisions
- thesis-review candidates
- risk-review candidates
- promotion/deployment-review candidates

## Authority
- read-only
- packet writes to `tmp/` or a review folder only
- no canonical mutation

## Owner layer
- source-tier rules: WF26 source/sleeve map and any future approved source-tier successor
- routed event artifacts: `tmp/` or a dedicated review-packet folder
- final thesis/risk/deployment interpretation: owner notes and review queues, not the router

## Review window
- daily after the relevant source/calendar checks and before daily review-object generation
- likely windows: morning, post-close, Sunday weekly rebuild, and post-earnings only where event context is relevant

## Stop lines
- source-tier map is missing or stale enough to make source authority ambiguous
- event source conflicts cannot be resolved into a source-tier confidence label
- router cannot distinguish `no_route` from review-needed outcomes
- packet generation starts implying canonical state change or deployment authority
- key active-name / promotion-review / macro-sleeve inputs are missing

## Trust gates still missing
- explicit broader contract tying WF26 approved source tiers to any future external-intake WF41 packets
- repeated daily-window proof before any schedule widening beyond existing chain hooks

## Trust gates passed for artifact-derived v1
- `scripts/market_intelligence_event_router.py` now emits per-event `source_trust` and `source_freshness`.
- Partial/stale/non-clean packet source truth emits an `unresolved_truth` event.
- Empty material-event windows have an explicit `no_route` event contract.
- Output remains `consumer_posture=review_only`, owner-review-required, and canonical/deployment/trade mutation false.
- Main-session QC reran py_compile, router generation, router tests, daily-review generation, daily-review tests, and direct JSON inspection.

## Validation / evidence target
- compile / unit tests for router contract
- manual post-close packet generation proof
- review-object consumer proof showing packets are consumed as evidence only
- independent audit that router classifications do not create a second source of truth

## Next action
- Move WF41 artifact-derived v1 to monitoring/closeout after repeat proof, or reopen only for the broader owner-gated source-tier/external-intake design decision.

## Key files
- `06. Playbooks/Project Continuity/Workflow 41 - Market Intelligence Event Intake and Materiality Router.md`
- `06. Playbooks/Project Continuity/Workflow 26 - Fresh External Intelligence and Geopolitical Verification Pilot.md`
- `scripts/market_intelligence_event_router.py`
- `scripts/test_market_intelligence_event_router.py`
- `scripts/daily_review_objects.py`
- `06. Playbooks/Daily Review Objects Contract.md`
