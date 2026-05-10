# Workflow 50 - Tmp Helper Archive Cleanup

## Retrieval Notes
- Type: workflow
- Status: queued / owner-approval-required
- Owner surface: `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- Authority: workspace cleanup only
- Workflow: WF50
- Key entities: `tmp/*.py`, archive manifest, workspace boundary check, `scripts/workspace_governance_truth_check.py`
- Source freshness: based on 2026-05-09 helper review and research pass
- Next action: get owner approval before moving or archiving files
- Archive posture: keep-active until cleanup completes
- Tags: #veritas/workflow #wf/WF50 #status/queued

## Objective

Remove durable executable helper residue from `tmp/` without losing useful evidence or creating script clutter.

## Current state

Research and implementation concluded that the six helpers should **not** be promoted as standalone scripts:

- `tmp/dump_bands.py`
- `tmp/find_band_refs.py`
- `tmp/find_disallowed_model_refs.py`
- `tmp/find_disallowed_openclaw_refs.py`
- `tmp/find_model_refs.py`
- `tmp/market_close_quick.py`

Useful durable idea already implemented:
- model-routing drift detection folded into `scripts/workspace_governance_truth_check.py`

Files that own the decision:
- `08. Audits/Tmp Python Helper Promotion Review - 2026-05-09.md`
- `tmp/tmp-helper-implementation-research.md`
- `scripts/workspace_governance_truth_check.py`
- `scripts/README.md`

## Boundary

Allowed:
- archive the six helper files after explicit owner approval
- write a short manifest with hashes, original paths, new paths, rationale, and proof results
- re-run validators

Not allowed without separate approval:
- deleting files without archive
- moving canonical notes, finance artifacts, runtime/config/auth files, or active workflow proof
- creating a new standalone market-data or search script
- rewriting historical memory to hide why the helpers existed

## Acceptance proof

Before archive:
- confirm owner approval
- hash the six helper files
- check references if destination/path changes matter

After archive:
- `python scripts\workspace_boundary_check.py` no longer warns on the six `tmp/*.py` helpers
- `python scripts\workspace_governance_truth_check.py --write --cli-timeout 1` remains warning-or-better with no model-policy criticals
- `python scripts\dashboard_truth_lint.py` remains ok
- archive manifest exists under `09. Archive/tmp-python-helpers - Archived/`

## Status

Queued. Waiting on owner approval for the archive move.
