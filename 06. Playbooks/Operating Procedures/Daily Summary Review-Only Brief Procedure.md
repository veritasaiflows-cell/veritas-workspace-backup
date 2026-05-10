# Daily Summary Review-Only Brief Procedure

## Purpose
Explain how the new pre-market and post-close commercial-brief layer actually operates today.

## Trigger
Use this procedure when:
- the scheduled morning or post-close chain has already run
- the operator wants the enhanced commercial-style brief
- the operator needs to know whether anything must be run manually

## Read first
- `06. Playbooks/Project Continuity/Workflow 37 - Daily Summary Commercial Brief Hardening.md`
- `06. Playbooks/WF37 Phase 5 Manual Review Posture and Output Path - 2026-05-06.md`
- `tmp/run-summary-morning.json` or `tmp/run-summary-post-close.json`

## What is automatic
The scheduled chain now auto-generates:
- deterministic snapshot / machine-summary outputs
- the review-only packet input

Morning artifacts:
- `tmp/premarket-snapshot.json`
- `tmp/premarket-brief-input.json`
- `tmp/run-summary-morning.json`

Post-close artifacts:
- `tmp/postmarket-snapshot.json`
- `tmp/daily-executive-brief.json`
- `tmp/postclose-brief-input.json`
- `tmp/run-summary-post-close.json`

## What is not automatic
The scheduled chain does **not** currently:
- write the commercial brief draft into a canonical note
- send the commercial brief draft automatically in chat
- promote the brief into an official surface
- mutate owner notes

Approved non-canonical draft locations:
- `01. Dashboards/Review-Only Briefs/Pre-Market/YYYY-MM-DD.md`
- `01. Dashboards/Review-Only Briefs/Post-Close/YYYY-MM-DD.md`

## How the operator should use it
Normal operator path:
1. let the scheduled chain run
2. inspect the `review_only_brief` block in the relevant run-summary JSON if needed
3. ask Veritas to generate the review-only commercial brief for that window
4. let Veritas run lint before treating the draft as usable

Preferred operator prompts:
- "Generate today's review-only pre-market brief"
- "Generate today's review-only post-close brief"

## Script fallback
You do not normally need to run scripts yourself.
Only do this when debugging or deliberately operating at the script layer.

Packet rebuild:
```bash
python scripts/summary_brief_packet.py --window morning
python scripts/summary_brief_packet.py --window post-close
```

Draft lint:
```bash
python scripts/summary_brief_lint.py --packet tmp/premarket-brief-input.json --draft <draft-path>
python scripts/summary_brief_lint.py --packet tmp/postclose-brief-input.json --draft <draft-path>
```

## Proof that the packet is ready
Check the relevant run-summary file.
Required fields:
- `outputs.<window>_brief_input.status = ok`
- `review_only_brief.packet_ready = true`
- `review_only_brief.delivery_mode = manual_review_only`
- `review_only_brief.review_output_path` is populated

## Stop lines
Stop and do not treat the commercial brief as ready if:
- the packet output is missing or stale
- the run-summary status is `blocked` or `error`
- the packet or lint path suggests deployable-now authority
- the draft is not owner-cited
- the draft tries to clear blockers by itself

## Current truth
This is a useful review layer, not an autonomous briefing surface yet.
The packet layer is now cron-safe.
The human-readable commercial brief layer remains manual/review-only until repeated clean proof exists.
