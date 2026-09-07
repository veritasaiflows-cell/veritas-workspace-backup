# Review-Only Briefs

## Purpose
This folder holds non-canonical human-readable draft briefs built from validated alert and evidence packets.

## Authority rule
These briefs are:
- review-only
- operator-facing
- non-canonical
- not allowed to override owner notes

Canonical owner notes still win:
- `03. Alerts and Recommendations/Investor Profile.md`
- `03. Alerts and Recommendations/Alert Trigger Policy.md`
- `03. Alerts and Recommendations/Alert Bands and Invalidation Register.md`
- `03. Alerts and Recommendations/Alert Operations Board.md`
- `04. Research/Coverage Universe.md`
- `05. Intelligence/Event Calendar.md`

## Folder structure
- `Pre-Market/YYYY-MM-DD.md`
- `Post-Close/YYYY-MM-DD.md`

## Use rule
Only place drafts here after:
1. the scheduled window has already produced its packet JSON
2. the draft has been reviewed or linted against the packet contract
3. the draft remains clearly non-canonical

## Not allowed here
- autonomous owner-note writes
- direct trade instructions
- portfolio, account, order, or simulated-position state
- blocker clearance by summary language alone
- anything presented as a source-of-truth layer
