# Daily Summary SOP

## Purpose
Explain, in plain English, how pre-market and post-close summaries work now.

## Morning summary
What runs automatically:
- the morning finance refresh chain
- the deterministic pre-market snapshot
- the review-only pre-market packet JSON

What does not run automatically:
- the final human-readable enhanced commercial brief
- automatic chat delivery of that enhanced brief
- canonical owner-note mutation from that brief

What you do when you want the enhanced version:
- ask Veritas to generate today's review-only pre-market brief

Where things live:
- machine snapshot: `01. Dashboards/Pre-Market Snapshot/`
- review packet: `tmp/premarket-brief-input.json`
- review-only draft location: `01. Dashboards/Review-Only Briefs/Pre-Market/`

## Post-close summary
What runs automatically:
- the post-close finance refresh chain
- the deterministic post-market snapshot
- the machine daily executive summary
- the review-only post-close packet JSON

What does not run automatically:
- the final human-readable enhanced commercial brief
- automatic chat delivery of that enhanced brief
- canonical owner-note mutation from that brief

What you do when you want the enhanced version:
- ask Veritas to generate today's review-only post-close brief

Where things live:
- machine snapshot: `01. Dashboards/Post-Market Snapshot/`
- machine daily summary: `01. Dashboards/Daily Executive Summary/`
- review packet: `tmp/postclose-brief-input.json`
- review-only draft location: `01. Dashboards/Review-Only Briefs/Post-Close/`

## Simple operator rule
- automatic = evidence + packet
- manual = polished review brief
- canonical = owner notes only

## If you are unsure
Do not run raw scripts first.
Ask Veritas what is ready, what is manual, and what still needs review.
