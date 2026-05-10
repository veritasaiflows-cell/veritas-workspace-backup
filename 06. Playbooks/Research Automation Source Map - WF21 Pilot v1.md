# Research Automation Source Map - WF21 Pilot v1

## Purpose

Turn WF21 Phase 1 into an explicit approved-source map for the first real review-packet lane.

This file defines what the pilot may ingest, what stays blocked, and which names/sleeves are in scope before any cron-backed packet cadence is considered.

## Pilot coverage set

Primary pilot names:
- **JPM**
- **NVDA**
- **ETN**
- **MSFT**
- **GOOG**

Pilot macro sleeve:
- **Rates / credit / policy**

Why this set:
- it matches the current near-deployable / review-relevant board cluster
- it keeps WF21 tied to real desk intake needs instead of broad research sprawl
- it gives one macro sleeve directly relevant to JPM and deployment timing without opening the broader geopolitical lane yet

## Tier 1 approved sources

### Company-event truth layer
Use as the preferred truth layer whenever available for JPM / NVDA / ETN / MSFT / GOOG:
- issuer investor-relations earnings releases
- issuer shareholder letters, prepared remarks, decks, and transcripts
- SEC filings (`8-K`, `10-Q`, `10-K`, material filing updates)
- issuer investor-relations event calendars for timing-critical confirmation

### Macro sleeve truth layer
Use as the preferred truth layer for rates / credit / policy:
- Federal Reserve / FRED target-range and rates series
- Treasury primary pages when timing or issuance matters
- BLS / BEA release pages when the macro event is data-driven
- ICE BofA credit series via FRED when available

## Tier 2 approved corroboration

Allowed for packet corroboration, faster detection, and context:
- Reuters
- Associated Press
- Wall Street Journal / Financial Times / Bloomberg when directly attributable
- clearly sourced major financial-media writeups tied to a named primary or attributable event

## Tier 3 packet-only / provisional sources

Allowed only as provisional packet context, never as silent canonical truth:
- yfinance timing/calendar surfaces
- transcript mirrors without issuer provenance
- market-data aggregators
- screening/calendar services without a direct issuer/regulator backing chain

## Blocked / stop-lined sources

Blocked by default:
- social rumor feeds
- unattributed rumor headlines
- AI summaries without a verifiable source chain
- repost chains quoting each other
- scraped calendars with no attributable evidence

## Review-window ownership

- **Morning:** carry forward unresolved post-earnings / timing objects only; do not invent a second writer lane.
- **Post-close:** primary manual packet-assembly window after the finance refresh chain finishes.
- **Sunday:** weekly macro sleeve synthesis plus unresolved verification objects.
- **Event-driven:** manual only in v1.

## Starter raw-event input

Starter file:
- `tmp/research-automation/raw-events-wf21-phase1-2026-05-05.json`

Current staged objects:
1. **ETN** post-earnings follow-up object with primary-source gap still visible
2. **AMD AI infrastructure read-through** object feeding NVDA / MSFT / GOOG / ETN context without promoting any of them
3. **NVDA timing confirmation** unresolved object
4. **Rates / credit / policy** macro sleeve object tied to JPM and deployment timing context

## Explicit no-go rules

- no freeform web trawling
- no per-ticker cron sprawl
- no autonomous canonical note mutation
- no autonomous deployment-state promotion
- no thesis/posture rewrite from Tier 2 or Tier 3 evidence alone

## Next operator step

1. review the starter raw-event file for scope creep and source-tier honesty
2. add a direct JPM / GOOG / MSFT company-source event only when there is a real new event, not just because coverage exists
3. run one manual post-close packet in Phase 2 after this source map is accepted
4. use the packet output to decide whether the Sunday packet design is worth drafting yet
