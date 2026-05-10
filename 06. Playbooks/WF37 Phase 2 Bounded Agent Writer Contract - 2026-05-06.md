# WF37 Phase 2 Bounded Agent Writer Contract - 2026-05-06

## Purpose
Define the exact review-only contract for future agent-written commercial briefs that consume:
- `tmp/premarket-brief-input.json`
- `tmp/postclose-brief-input.json`

This contract is for commercial presentation quality.
It is not authority transfer.

## Writer posture
- consumer posture: `review_only`
- canonical mutation allowed: `false`
- owner notes remain authoritative
- any future scheduled writer must stay fail-closed until repeated clean proof exists

## Allowed inputs
The writer may use:
- the packet JSON
- the named owner layers in `required_citations`
- the deterministic snapshot note for the same window

The writer may not rely on:
- chat memory alone
- `tmp/` artifacts not named in the packet
- convenience summaries that bypass the owner notes

## Required output shape

### Morning brief
The brief should answer, in this order:
1. what matters before the open
2. trust / freshness condition
3. closest setup cluster in owner-first language
4. catalyst watchlist for the session
5. what to read before acting

### Post-close brief
The brief should answer, in this order:
1. bottom line for the session
2. what changed since the prior dashboard run
3. what matters for the next session
4. closest actionable names in owner-first language
5. unresolved truths and stop lines

## Sentence-shape rules
Allowed sentence types:
- owner-first routing
- bounded orientation summary
- unresolved-truth warning
- freshness / availability signal
- review sequencing

Preferred verbs:
- read
- review
- confirm
- reconcile
- watch
- defer
- keep review-only

Disallowed verbs unless already quoted from an owner note and explicitly attributed:
- buy
- add now
- promote
- clear
- confirm deployable
- resolved now
- ready now

## Required wording behavior
When the brief names a ticker, it must use one of these forms:
- "Read [owner note] before changing posture on [ticker]."
- "[Ticker] remains owner-bound / review-only / unresolved in the current stack."
- "Fresh interpretation exists for [ticker], but deployable state still belongs to [owner note]."

## Required citation rule
Every materially decision-sensitive paragraph must cite at least one owner layer from the packet.
The writer must not cite the packet as if it were canon.

## Required unresolved-truth behavior
If the packet contains validation warnings, trust-gate blockers, or unresolved truths:
- they must be stated explicitly
- they may not be rewritten into cleaner confidence language
- they must appear before any action-style routing paragraph

## Stop lines
Reject or degrade the draft if:
- it publishes deployable-now state not already present in owner notes
- it clears a blocker without owner-note confirmation
- it smooths over owner-note conflict
- it removes or softens a packet unresolved-truth warning
- it makes the dashboard / brief easier to trust than the owner note path

## Minimal acceptance for first live writer trial
A first live writer trial is acceptable only if:
- the packet is present and current
- the output uses owner-first citations
- unresolved truths remain visible
- no forbidden verbs or authority shapes appear
- the draft is useful as a commercial brief without becoming a shadow decision board
