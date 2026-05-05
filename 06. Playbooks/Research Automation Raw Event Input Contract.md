# Research Automation Raw Event Input Contract

## Purpose
Define the exact v1 input object that WF21 will feed into `scripts/research_intake_packet.py` before any routing, weekly-brief, dashboard, or freshness-patch candidate handling begins.

This is the **pre-packet evidence object**.
It is not a verdict.
It is not a canonical mutation request.

## Top-level file shape
Accepted file shapes:
1. a JSON list of raw-event objects
2. a JSON object with one key: `events`, where `events` is a list of raw-event objects

## Required v1 event fields
Every v1 raw-event object must include these keys explicitly, even when the value is empty / false:
- `event_title` - string
- `event_datetime` - ISO-8601 datetime string
- `affected` - array of tickers, sleeves, or macro themes
- `source_tier` - one of `tier_1_primary`, `tier_2_trusted`, `tier_3_secondary`, `rumor_unverified`, `unknown`
- `event_class` - one of `company_event`, `macro_event`, `geopolitical_event`, `sector_readthrough`, `unresolved_truth`, `general_event`
- `verification_status` - one of `confirmed`, `partial`, `unresolved`, `contradicted`
- `event_summary` - string
- `tags` - array of normalized tags
- `stale_canonical_note` - boolean
- `rumor_heavy` - boolean
- `requires_primary_confirmation` - boolean
- `primary_evidence` - array of evidence objects
- `secondary_evidence` - array of evidence objects
- `contradiction_notes` - array of strings
- `open_questions` - array of strings
- `manual_notes` - string

## Optional v1 event fields
These are allowed but not required:
- `duplicate_of_packet_id` - string

## Evidence object shape
Each item in `primary_evidence` or `secondary_evidence` may include:
- `title` - string
- `source` - string
- `source_tier` - same allowed values as top-level `source_tier`
- `url` - string or null
- `published_at` - ISO-8601 datetime string or null
- `excerpt` - string or null
- `retrieved_at` - ISO-8601 datetime string or null

Minimum useful evidence object:
```json
{
  "title": "Company IR calendar",
  "source": "Company IR",
  "source_tier": "tier_1_primary"
}
```

## Required behavioral meanings
- `event_class` tells the system what kind of thing this is.
- `verification_status` tells the system whether the truth is settled or still open.
- `requires_primary_confirmation = true` means the event should stop-line if primary evidence is still missing.
- `stale_canonical_note = true` does **not** authorize mutation. It only marks possible freshness-review relevance.
- `rumor_heavy = true` should usually push the packet toward stop-line handling.
- `open_questions` must be used when the event is unresolved, contradictory, or especially sensitive in macro / geopolitical reporting.

## Unresolved-truth and geopolitical rule
Use this contract for unresolved truths and geopolitical verification, but do it honestly:
- unresolved does **not** mean unusable
- unresolved does mean the packet should remain a verification object until the source chain improves
- geopolitical items should prefer `event_class = geopolitical_event`
- if a geopolitical event is rumor-heavy, unattributed, or fast-moving without primary backing, keep it open and stop-line it rather than forcing a dashboard or thesis claim

## v1 stop-line expectations
A raw event should expect stop-line behavior when any of these are true:
- `verification_status` is `unresolved` or `contradicted`
- `rumor_heavy = true`
- `requires_primary_confirmation = true` but `primary_evidence` is empty
- the source chain is duplicate or circular
- contradiction notes exist without enough primary support

## Normalized tag guidance
Examples of useful v1 tags:
- `earnings`
- `earnings_date`
- `timing_confirmation`
- `macro`
- `policy`
- `fed_decision`
- `oil_shock`
- `production_disruption`
- `guidance_cut`
- `guidance_raise`
- `major_contract`
- `thesis_impairment`
- `technical_base`

## Minimal valid example
```json
[
  {
    "event_title": "NVDA timing confirmation remains unresolved after fresh calendar check",
    "event_datetime": "2026-05-03T16:30:00-07:00",
    "affected": ["NVDA"],
    "source_tier": "tier_2_trusted",
    "event_class": "company_event",
    "verification_status": "unresolved",
    "event_summary": "Fresh timing information suggests the note layer should remain cautious until primary confirmation is available.",
    "tags": ["earnings_date", "timing_confirmation"],
    "stale_canonical_note": true,
    "rumor_heavy": false,
    "requires_primary_confirmation": true,
    "primary_evidence": [
      {
        "title": "Company investor relations calendar",
        "source": "Company IR",
        "source_tier": "tier_1_primary",
        "url": "https://example.com/ir-calendar"
      }
    ],
    "secondary_evidence": [],
    "contradiction_notes": [],
    "open_questions": [
      "Has the issuer directly confirmed the date?"
    ],
    "manual_notes": ""
  }
]
```

## V1 operating rule for WF21
WF21 should use this object in this order:
1. collect raw events from the approved source bundle only
2. write them into this contract shape
3. run `python scripts\\research_intake_packet.py --input <file>`
4. review packet routes, stop lines, and open questions
5. promote only into allowed review surfaces
6. leave canonical notes manual-only

## Out of bounds
This input contract does not authorize:
- canonical note mutation
- thesis rewrite
- deployment-state change
- tracked-universe change
- publication decisions
- using unsourced rumor as settled truth
