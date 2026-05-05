# Research Automation Source Bundle Contract

## Purpose
Define what evidence the research-automation lane may trust, how strongly it may trust it, and what belongs in cron, manual review, or packet-only handling.

## Core rule
Research automation may only assemble review packets from approved sources.
It may not treat broad web noise as canonical truth.

## Bounded parallel roles
The source-bundle contract is a good fit for bounded parallel challenge lanes before cron widens.

| Role | Job |
|---|---|
| Source-quality agent | proposes approved source tiers and category-level source sets |
| Coverage-gap agent | checks whether the bundle misses important sources by ticker, sector, macro sleeve, or geopolitical risk |
| Noise/risk agent | defines excluded sources, rumor rules, duplicate-event handling, and stop lines |
| Workflow integration agent | decides what belongs in cron, what stays manual, and what may enter review packets only |

These lanes may challenge or extend the contract.
They do not authorize new live sources by themselves.

## Source tiers

### Tier 1 - Primary / authoritative
Use as the preferred truth layer whenever available.

- SEC filings and company IR releases
- Company earnings releases, shareholder letters, presentation decks, and transcripts from issuer-controlled surfaces
- Federal Reserve, Treasury, BLS, BEA, EIA, OPEC, company/regulator primary pages
- Exchange or regulator notices for dated market events

### Tier 2 - High-confidence secondary
Use for context, fast detection, and corroboration.
Do not let Tier 2 silently override Tier 1 on timing-critical or judgment-heavy issues.

- Reuters
- Associated Press
- Wall Street Journal / Financial Times / Bloomberg when directly available and attributable
- Clearly sourced major financial-media writeups

### Tier 3 - Context only / provisional
Useful for watchlisting, not enough for direct canonical trust on their own.

- yfinance-style calendar/date surfaces
- market-data aggregators
- transcript mirrors without issuer provenance
- sector blogs or newsletters with identifiable sourcing

### Blocked / stop-lined by default
- social rumor feeds
- anonymous-source headlines without primary backing
- AI summaries without source chain
- repost chains quoting each other
- scraped calendars with no attributable evidence

## Contract output
The source bundle contract should answer:
- approved source tiers
- approved sources by category
- blocked / low-confidence sources
- refresh cadence by source type
- ticker / macro sleeve coverage map
- what belongs in cron
- what requires manual review
- what is only allowed into review packets
- stop lines for rumor-heavy, low-confidence, duplicate, or unsourced events

## Coverage map
The v1 research lane covers only:
- active deployment-board names
- current portfolio and tactical names
- explicitly tracked watch names that already matter to the live board
- macro / policy releases that can change regime posture
- oil, LNG, shipping, Hormuz, and related energy-geopolitical sleeves

Do not widen into broad universe maintenance in this phase.

## Best first version
Do not try to build the full research universe immediately.

Start with:
- company filings / IR
- earnings transcripts
- major financial news
- macro calendar / Fed / rates / inflation
- oil and geopolitical risk sources
- sector-specific sources for active names only

Expand only after the source bundle proves useful and low-noise.

## Refresh cadence by source type
- company filings / IR: event-driven and post-close review windows
- earnings transcripts / prepared remarks: post-close and post-earnings windows
- macro primary sources: release windows plus Sunday synthesis
- energy / geopolitical primary sources: event-driven detection plus Sunday synthesis
- Tier 2 financial media: packet corroboration only after a primary or clearly attributable event exists

## Cron posture
### Allowed in scheduled packet assembly
- Tier 1 pulls
- Tier 2 corroboration pulls
- stale-surface detection against known owner notes
- contradiction scans

### Not allowed in scheduled packet assembly without new approval
- freeform web trawling
- per-ticker cron proliferation
- social/news rumor ingestion
- canonical note mutation
- portfolio-posture or thesis judgment promotion

## Manual-review requirements
Keep manual review mandatory when any of these are true:
- a date change is still provider-only
- primary and secondary sources conflict
- geopolitical reporting is fast-moving and attribution quality is mixed
- the event would alter deployment posture, thesis quality, or macro regime wording
- the packet would need cross-surface truth arbitration

## Stop lines
Stop packet promotion when:
- evidence is rumor-heavy or unattributed
- the source chain is duplicate or circular
- a Tier 3 source is trying to carry a Tier 1 decision
- the macro/policy layer is degraded enough that the event cannot be interpreted safely
- an owner-surface contradiction exists and the packet cannot resolve it cleanly

## Owner boundary
This contract governs evidence intake only.
It does not own:
- routing decisions beyond the allowed/blocked evidence boundary
- canonical note mutation
- final portfolio or thesis judgment

## Acceptance use
This contract is approved for Workflow 16A when:
- source tiers are explicit
- blocked sources are explicit
- cron-vs-manual boundaries are explicit
- stop lines are explicit
- the active coverage map stays narrow and review-first
