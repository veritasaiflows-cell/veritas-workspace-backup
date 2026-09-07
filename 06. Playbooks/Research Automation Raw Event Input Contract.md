# Research Automation Raw Event Input Contract

## Purpose

Define the smallest source-backed event object accepted by research and alert automation.

## Required fields

- `event_id` — stable deterministic identifier
- `observed_at` — capture timestamp with timezone
- `published_at` — source publication timestamp when known
- `source_url` — exact source route
- `source_tier` — approved evidence tier
- `headline` — source-faithful title
- `summary` — concise factual summary
- `affected` — tickers, companies, sectors, market themes, or macro variables
- `event_type` — earnings, filing, guidance, policy, macro, geopolitical, supply, legal, product, or other
- `confidence` — high, medium, low, or unresolved
- `freshness_state` — current, aging, stale, or unknown
- `lineage_hash` — content/provenance hash when available

## Optional analysis fields

- `thesis_effect` — supports, neutral, pressures, contradicts, or unresolved
- `catalyst_effect`
- `risk_effect`
- `band_or_invalidation_relevance`
- `contradictions`
- `follow_up_needed`

## Rules

- Preserve source language and distinguish fact from interpretation.
- Missing publication time or uncertain identity must remain explicit.
- Duplicate events should collapse by stable identity and source lineage.
- The event object may trigger evidence repair, alert review, thesis review, or freshness decay.
- It may not mutate alert canon, create finance action-state, infer approval, or invoke account/order/execution paths.

## Output

Raw event objects are evidence inputs only. Promotion into a durable research conclusion or alert requires the relevant owner and validator.
