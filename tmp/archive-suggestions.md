# Workspace Archive Suggestions

Generated: `2026-05-10T04:13:11Z`

## Verdict

- Status: `review_required`
- This is read-only. No files were moved, deleted, or rewritten.
- Owner approval is required before any archive/apply action.
- Canonical finance notes, active workflow surfaces, durable `data/` state, scripts, skills, and memory are protected from automatic archive.

## Counts

- Suggestions: 9
- Suggestions with inbound references: 7

## Suggestions

### `backups/`
- Kind: `undocumented_root_backup_surface`
- Confidence: `low`
- Reference count: `47`
- Recommendation: classify as active migration backup, archive under `09. Archive/`, or remove only after owner approval and reference check
- Proposed destination: `09. Archive/backups - Archived/`
- Apply allowed: `False`
- Blockers: root `backups/` is not documented as an active root entitlement; inbound references found; inspect before moving

### `tmp/dump_bands.py`
- Kind: `tmp_executable_helper`
- Confidence: `low`
- Reference count: `6`
- Recommendation: promote to scripts/ if durable; otherwise archive out of active tmp/ after owner approval
- Proposed destination: `09. Archive/tmp-python-helpers - Archived/dump_bands.py`
- Apply allowed: `False`
- Blockers: executable helper lives in generated-artifact tmp/ surface; inbound references found; promote/archive only after inspecting current use

### `tmp/find_band_refs.py`
- Kind: `tmp_executable_helper`
- Confidence: `low`
- Reference count: `6`
- Recommendation: promote to scripts/ if durable; otherwise archive out of active tmp/ after owner approval
- Proposed destination: `09. Archive/tmp-python-helpers - Archived/find_band_refs.py`
- Apply allowed: `False`
- Blockers: executable helper lives in generated-artifact tmp/ surface; inbound references found; promote/archive only after inspecting current use

### `tmp/find_disallowed_model_refs.py`
- Kind: `tmp_executable_helper`
- Confidence: `low`
- Reference count: `6`
- Recommendation: promote to scripts/ if durable; otherwise archive out of active tmp/ after owner approval
- Proposed destination: `09. Archive/tmp-python-helpers - Archived/find_disallowed_model_refs.py`
- Apply allowed: `False`
- Blockers: executable helper lives in generated-artifact tmp/ surface; inbound references found; promote/archive only after inspecting current use

### `tmp/find_disallowed_openclaw_refs.py`
- Kind: `tmp_executable_helper`
- Confidence: `low`
- Reference count: `6`
- Recommendation: promote to scripts/ if durable; otherwise archive out of active tmp/ after owner approval
- Proposed destination: `09. Archive/tmp-python-helpers - Archived/find_disallowed_openclaw_refs.py`
- Apply allowed: `False`
- Blockers: executable helper lives in generated-artifact tmp/ surface; inbound references found; promote/archive only after inspecting current use

### `tmp/find_model_refs.py`
- Kind: `tmp_executable_helper`
- Confidence: `low`
- Reference count: `6`
- Recommendation: promote to scripts/ if durable; otherwise archive out of active tmp/ after owner approval
- Proposed destination: `09. Archive/tmp-python-helpers - Archived/find_model_refs.py`
- Apply allowed: `False`
- Blockers: executable helper lives in generated-artifact tmp/ surface; inbound references found; promote/archive only after inspecting current use

### `tmp/market_close_quick.py`
- Kind: `tmp_executable_helper`
- Confidence: `low`
- Reference count: `7`
- Recommendation: promote to scripts/ if durable; otherwise archive out of active tmp/ after owner approval
- Proposed destination: `09. Archive/tmp-python-helpers - Archived/market_close_quick.py`
- Apply allowed: `False`
- Blockers: executable helper lives in generated-artifact tmp/ surface; inbound references found; promote/archive only after inspecting current use

### `scripts/__pycache__/`
- Kind: `runtime_cache`
- Confidence: `medium`
- Reference count: `0`
- Recommendation: safe cleanup candidate after confirming no process is relying on it; do not treat as operating evidence
- Proposed destination: none / cleanup-only candidate
- Apply allowed: `False`
- Blockers: deletion is destructive; keep as approval-gated even for cache cleanup

### `scripts/operators/__pycache__/`
- Kind: `runtime_cache`
- Confidence: `medium`
- Reference count: `0`
- Recommendation: safe cleanup candidate after confirming no process is relying on it; do not treat as operating evidence
- Proposed destination: none / cleanup-only candidate
- Apply allowed: `False`
- Blockers: deletion is destructive; keep as approval-gated even for cache cleanup
