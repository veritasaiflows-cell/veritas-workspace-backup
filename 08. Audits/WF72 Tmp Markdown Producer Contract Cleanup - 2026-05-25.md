# WF72 Tmp Markdown Producer Contract Cleanup - 2026-05-25

## Retrieval Notes
- Owner: WF72 / workspace governance cleanup.
- Status: consolidation rollup, not source canon.
- Machine proof: `tmp/wf72-producer-contract-rollup-2026-05-25.json`.
- Boundary: no portfolio/canon/trade/account/config/auth/channel/runtime authority; generated artifacts remain proof/review surfaces.

## Executive result
Generated UTC: `2026-05-25T17:25:27Z`

Reviewed `50` retained `tmp/*.md` reports after runtime-cache deletion. Zero unreferenced tmp Markdown remains; remaining reports are retained because active references exist.

## Current classification
- `continuity_referenced_tmp_markdown_reviewed_retained`: 4
- `generated_artifact_referenced_tmp_markdown_reviewed_retained`: 21
- `script_referenced_tmp_markdown_reviewed_retained`: 25

## Workflow-family grouping
- `advisor_wf67_intraday`: 2
- `archive_cleanup`: 7
- `cron_authority`: 5
- `finance_canon_sync`: 18
- `next_level_workspace`: 1
- `other`: 10
- `runtime_telemetry_openclaw`: 6
- `security`: 1

## Producer-contract inspection
- `direct_or_likely_runtime_output_contract`: 7
- `documentation_reference_not_runtime_producer`: 15
- `registry_or_index_reference_path_contract`: 25

## Consolidation decisions
- `archive_cleanup`: Keep current tmp sidecars referenced for now; future producer should emit one current archive-governance rollup plus JSON companions, not repeated standalone MD.
- `cron_authority`: Consolidate future cron authority Markdown into one durable audit/current rollup; JSON contract artifacts remain in tmp.
- `finance_canon_sync`: Do not merge current proof sidecars into canon. Future finance chain should prefer current-window map plus compact summary, with durable closeouts only at phase boundaries.
- `runtime_telemetry_openclaw`: Use existing major-closeout/cache scorecard surfaces as current rollups; avoid new one-off Markdown unless there is a material change.
- `advisor_wf67_intraday`: Retain exact path contracts until WF67/WF68 producers are explicitly retargeted; these are decision-support proof surfaces.
- `other`: Review opportunistically only when the owning workflow is touched; no standalone broad move.

## New producer rule
For future producers, prefer JSON as machine truth plus one current/durable Markdown rollup per workflow family; avoid creating new one-off tmp Markdown for routine reruns.

## Current move/delete result
- Files moved/deleted in this consolidation phase: `0`
- Reason: all remaining files have active references; moving without producer/registry retargeting would create breakage risk.

## Next safe action
When touching an owning producer, retarget that family to JSON-primary output plus one current/durable Markdown rollup, then archive superseded sidecars with reference updates and hashes.
