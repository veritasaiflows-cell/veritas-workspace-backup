# Workflow 15 - Script Performance and Payload Modularity Backlog

## Objective
- Preserve the next real optimization backlog without prematurely rewriting working code paths.

## Current State
- Two larger ideas are worth keeping named but should not be forced early:
  - add a freshness gate to `entry_band_fetch.py` so repeated runs stop refetching full history when local bundles are still fresh
  - split `scripts/dashboard_payload.py` only when a real feature or bug creates a natural seam

## Last Meaningful Progress
- The chain is currently functioning well enough that these items are scale/performance improvements, not present blockers.

## Outstanding
- Verify that `entry-band-data/*.json` contains everything needed for HTML regeneration before any fetch-skipping logic is introduced.
- Only modularize `dashboard_payload.py` when a real implementation seam appears; do not split it for aesthetics alone.

## Blockers / Trust Gaps
- Performance work can widen scope fast if it is opened before the hygiene and lifecycle layers are stable.

## Next Action
- Keep this deferred until there is either measurable chain-latency pain or a real payload-assembly feature seam.

## Key Files
- `scripts/entry_band_fetch.py` - future freshness gate home.
- `scripts/dashboard_payload.py` - future modularization candidate.

## Automation / Refresh Path
- Treat this as a backlog note, not an active implementation lane.
