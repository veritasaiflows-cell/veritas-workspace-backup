# WF55 Outcome Ledger v2 Migration Preview

- Generated UTC: `2026-05-25T00:03:10Z`
- Validation status: **ok**
- Preview rows: **5**
- Critical findings: **0**
- Warning findings: **0**
- Durable v2 ledger written: **no**

## Boundary

No durable v2 JSONL, v1 sidecar, state-history, Call Log, portfolio/canon, paper/live/account mutation occurs in this preview slice.

## Event family counts

- call_log_resolution: 3
- paper_lifecycle: 2

## Blocked candidates

- **Call Log row #3 NVDA**: blocked_no_resolution_yet — Call Log row remains incomplete/open; no close/void/supersession evidence exists yet.
- **Call Log row #8 BRK.B**: blocked_no_resolution_yet — Call Log row remains incomplete/open; no close/void/supersession evidence exists yet.
- **Call Log row #10 VRT**: blocked_no_resolution_yet — Call Log row remains incomplete/open; no close/void/supersession evidence exists yet.
- **WF68 owner action/no-action follow-up**: blocked_no_appendable_event_yet — Later owner action, no-action, or outcome follow-up evidence is absent.
