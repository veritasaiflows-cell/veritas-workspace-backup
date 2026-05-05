# Research Automation Intake Packet Contract

## Purpose
Standardize the review object every research agent or multi-agent packet flow must produce before anything can touch dashboards, weekly intelligence, workbooks, thesis-review lanes, or freshness-patch candidates.

This is now the anchor contract for the WF20 human-gated review layer.

## Core rule
An intake packet is a **review object**, not a verdict.
It may recommend routing.
It may not silently mutate truth.

## Fail-closed rule
`canonical_mutation_allowed` defaults to `false` and stays `false` in v1.

If a packet recommends `canonical_freshness_patch_candidate`, that means:
- a patch proposal may be drafted later
- human review is still required
- no auto-apply is authorized

## Parallel roles
The intake layer may use bounded parallel roles, but each role stays subordinate to the packet contract.

| Role | Job |
|---|---|
| Event detector | identifies what happened |
| Materiality scorer | decides whether it matters to active theses, watchlist names, or portfolio posture |
| Thesis-drift agent | compares the event against existing thesis assumptions |
| Evidence QA agent | checks source quality, conflicts, duplicates, and missing context |
| Routing agent | decides where the packet should go: ignore, weekly brief, dashboard, thesis-review queue, or patch candidate |

These roles may prepare findings.
They do **not** own final canonical judgment.

## Required packet fields
Every packet must include:
- `packet_id`
- `created_at`
- `event_title`
- `event_datetime`
- `affected_tickers_or_themes`
- `source_tier`
- `primary_evidence`
- `secondary_evidence`
- `confidence_level`
- `materiality_level`
- `thesis_impact`
- `portfolio_posture_impact`
- `contradictions_uncertainty`
- `recommended_routing`
- `canonical_mutation_allowed` (default `false`)
- `stop_line_triggered`
- `next_required_review`
- `stale_canonical_note`
- `agent_findings`
- `routing_reason`
- `validation_errors`

## Source tier scale
- `tier_1_primary` - company filing, investor relations, transcript, official macro/policy source, exchange, regulator
- `tier_2_trusted` - high-quality trusted financial, macro, or geopolitical source
- `tier_3_secondary` - secondary analysis or lower-authority summary
- `rumor_unverified` - rumor, social, unattributed, or unsourced channel checks
- `unknown` - source quality not yet classified

## Confidence scale
- `low` - weak, rumor-heavy, conflicting, unattributed, or missing required evidence
- `medium` - decent evidence but unresolved contradiction, partial primary support, or context gap remains
- `high` - primary evidence exists or strong attributed corroboration exists with no live contradiction

## Materiality scale
- `low` - context only; unlikely to change live work this week
- `medium` - useful for watchlist, weekly intelligence, or dashboard watch handling
- `high` - could change thesis maintenance, deployment caution, queue priority, or canonical freshness review

## Routing classes
A packet may end in one of these routes only:
- `ignore`
- `archive_weekly_digest`
- `weekly_intelligence`
- `dashboard_watch_item`
- `thesis_review_queue`
- `canonical_freshness_patch_candidate`
- `stop_line_no_promotion`

## Routing logic
Use this simple routing model:
- low materiality + high confidence -> archive / weekly digest only
- medium materiality -> weekly intelligence or dashboard watch item
- high materiality -> thesis-review queue
- high materiality + stale canonical note -> canonical freshness patch candidate
- low confidence / rumor-heavy -> stop line, no promotion

## Mandatory truth language
Every packet must explicitly say:
- why it matters, or
- why it does not matter enough, or
- why it cannot be trusted enough yet

## Stop lines
A packet must stop instead of routing when:
- confidence is too low for the proposed route
- the event is rumor-heavy or source tier is unverified
- primary evidence is missing on a timing-critical or material claim
- duplicate reporting is being mistaken for confirmation
- unresolved contradiction exists without enough primary support
- the packet would smuggle in a thesis, deployment, or publication judgment
- owner-surface conflict exists and the packet cannot resolve it safely
- packet validation errors remain open

## Owner boundary
Packets may feed review surfaces.
Packets do not own canonical truth.

Allowed outputs:
- dashboard watch candidate
- weekly intelligence candidate
- thesis-review queue candidate
- canonical freshness patch candidate
- archive / digest candidate

Disallowed outputs:
- autonomous thesis rewrite
- autonomous portfolio posture change
- autonomous deployment-state change
- autonomous tracked-universe mutation
- autonomous canonical note mutation
- autonomous decision-grade publication

## Validation rule
Any packet validation error forces fail-closed behavior:
- `stop_line_triggered = true`
- `recommended_routing = stop_line_no_promotion`
- `canonical_mutation_allowed = false`
- `next_required_review = human review required`

## Relationship to WF16A and WF20
- Workflow 16A created and approved the intake-packet contract as a review-first research-automation surface.
- Workflow 20 inherits it as the anchor object for multi-agent cron-backed review flows.
- Any future cron-backed intake lane must emit this packet shape before a review surface can promote anything.

## Acceptance use
This contract is approved only when all are true:
- the schema is explicit
- source tier, confidence, and materiality definitions are explicit
- routing classes are explicit
- stop lines are explicit
- `canonical_mutation_allowed` remains default-no
- packets can show route, no-route, and stop-line outcomes honestly
- helper-role findings remain subordinate to human-gated review
