# WF37 Phase 5 Manual Review Posture and Output Path - 2026-05-06

## Decision
The scheduled `morning` and `post-close` chains now auto-generate the review-only commercial-brief packets, but they do **not** auto-generate or auto-deliver the final commercial brief drafts.

## What is automatic now
The following scheduled windows now produce packet inputs without operator intervention:
- `tmp/premarket-brief-input.json`
- `tmp/postclose-brief-input.json`

Those packet writes are now part of the live chain order in `scripts/run_finance_refresh_chain.py` via `scripts/chain_manifest.py`.

## What remains manual
These steps remain manual / review-only:
1. generate the human-readable commercial brief draft
2. lint that draft with `scripts/summary_brief_lint.py`
3. decide whether the draft is useful enough to share or archive

Approved non-canonical draft locations:
- `01. Dashboards/Review-Only Briefs/Pre-Market/YYYY-MM-DD.md`
- `01. Dashboards/Review-Only Briefs/Post-Close/YYYY-MM-DD.md`

No canonical owner note may be mutated from this path.
No autonomous delivery is approved from this path.

## Operator communication path
Current communication is machine-readable, not chat-push:
- `tmp/run-summary-morning.json` now includes a `review_only_brief` block
- `tmp/run-summary-post-close.json` now includes a `review_only_brief` block
- that block names:
  - the packet path
  - the non-canonical review output path
  - whether the packet is ready
  - the intended target note path if a review draft is later created
  - the exact next operator action

Current explicit truth:
- the packet is auto-generated
- the commercial brief draft is not auto-written to a note
- no chat delivery is configured yet

## Default operator action
Normal use should be:
- ask Veritas to generate today's review-only pre-market brief, or
- ask Veritas to generate today's review-only post-close brief

That is the preferred operator path.
You do **not** need to run the raw scripts yourself unless you are debugging or intentionally operating at the script layer.

## Script-level fallback
If direct script use is needed for debugging:
```bash
python scripts/summary_brief_packet.py --window morning
python scripts/summary_brief_packet.py --window post-close
python scripts/summary_brief_lint.py --packet tmp/premarket-brief-input.json --draft <draft-path>
python scripts/summary_brief_lint.py --packet tmp/postclose-brief-input.json --draft <draft-path>
```

## Why the manual boundary stays
The packet layer is now safe enough for cron because it is read-only, bounded, and fail-closed.
The human-readable commercial brief layer is not promoted because:
- repeated clean runs are not yet proved
- no delivery posture is approved
- no owner-note write authority is approved
- lint is still phrase-based, not full semantic adjudication

## Next gate
Before any automation promotion beyond the packet layer:
- prove repeated clean brief-generation runs for both windows
- decide whether drafts stay in `tmp/` or move to a dedicated non-canonical review folder
- decide whether any delivery path should exist at all
- keep cron/native promotion fail-closed until those proofs are real
