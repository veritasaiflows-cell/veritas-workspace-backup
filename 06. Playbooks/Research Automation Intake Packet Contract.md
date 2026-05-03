# Research Automation Intake Packet Contract

## Purpose
Standardize the review object that research automation produces before anything can route into dashboard, weekly, thesis-review, or freshness-patch lanes.

## Core rule
A packet is a review object, not a verdict.
It may recommend routing.
It may not silently mutate truth.

## Required packet fields
Every packet must include:
- `packet_id`
- `event_title`
- `event_time`
- `window` (`premarket`, `post-close`, `sunday`, `event-driven`)
- `affected_scope` (ticker(s), sleeve, macro theme)
- `source_tier`
- `primary_evidence`
- `secondary_evidence`
- `confidence` (`low`, `medium`, `high`)
- `materiality` (`low`, `medium`, `high`, `critical`)
- `thesis_impact`
- `portfolio_posture_impact`
- `contradictions_or_uncertainty`
- `recommended_routing`
- `canonical_mutation_allowed` (default `false`)
- `stop_line_triggered`
- `next_required_review`

## Materiality scale
- **Low** - context only; unlikely to change live work this week
- **Medium** - useful for watchlist, weekly brief, or dashboard watch language
- **High** - could change thesis maintenance, deployment caution, or current queue priority
- **Critical** - could change immediate risk posture, force a same-session review, or invalidate a near-term decision

## Confidence scale
- **Low** - weak or conflicting sourcing; packet should usually stop or stay provisional
- **Medium** - decent evidence but unresolved contradiction or partial primary support remains
- **High** - primary evidence exists or strong attributed corroboration exists with no live contradiction

## Packet output classes
A packet may end in one of these classes:
- `no_route`
- `archive_digest`
- `dashboard_watch`
- `weekly_intelligence`
- `thesis_review_queue`
- `freshness_patch_candidate`

## Mandatory truth language
Every packet must say one of:
- why it matters
- why it does not matter enough
- why it cannot be trusted enough yet

## Stop lines
A packet must stop instead of routing when:
- confidence is too low for the proposed route
- primary evidence is missing on a timing-critical claim
- duplicate reporting is being mistaken for confirmation
- the event implies a thesis or deployment change that has not been adjudicated
- owner-surface conflict exists and the packet cannot resolve it safely

## Owner boundary
Packets may feed review surfaces.
Packets do not own canonical truth.

## Example use
- high-confidence, low-materiality item -> archive or weekly digest
- high-confidence, medium-materiality item -> dashboard watch or weekly intelligence
- high-confidence, high-materiality item -> thesis-review queue
- high-confidence stale-note case -> freshness patch candidate
- low-confidence or contradictory item -> stop line / no route

## Acceptance use
This contract is approved for Workflow 16A when:
- the schema is explicit
- materiality and confidence definitions are explicit
- stop lines are explicit
- canonical mutation remains default-no
- packets can show both route and no-route outcomes honestly
