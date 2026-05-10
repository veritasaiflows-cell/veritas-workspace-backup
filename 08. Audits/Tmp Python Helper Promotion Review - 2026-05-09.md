# Tmp Python Helper Promotion Review - 2026-05-09

## Verdict

Do **not** promote the six `tmp/*.py` helpers as standalone scripts.

They are useful evidence of real operator needs, but promoting them one-for-one would make the workspace more cluttered, not more truthful. The better path is:

1. Archive the six files after owner approval.
2. Preserve only two durable ideas:
   - a lightweight model/config policy check inside `scripts/workspace_governance_truth_check.py`
   - an optional simple entry-band summary command only if repeated use proves it saves time
3. Keep `tmp/` as generated/staged output, not durable tooling.

## File-by-file determination

| Helper | Determination | Why |
|---|---|---|
| `tmp/dump_bands.py` | Do not promote as-is | Useful quick view of `tmp/portfolio-config.json` entry bands, but too small/special-purpose for a standalone durable script. If this is repeatedly useful, fold it into an existing portfolio-config or validation surface as a read-only summary mode. |
| `tmp/find_band_refs.py` | Archive | It is just a hard-coded text search over playbooks and memory. `rg` or `scripts/workspace_index.py --search` does this better without another script. |
| `tmp/find_disallowed_model_refs.py` | Do not promote as-is; fold concept into governance validator if needed | The purpose is valuable: catch stale/disallowed model-routing language. But the script is hard-coded, partly duplicative, and too easy to false-positive on historical notes. Durable version belongs in `workspace_governance_truth_check.py` with explicit allowed/disallowed patterns and exclusions. |
| `tmp/find_disallowed_openclaw_refs.py` | Archive after any useful pattern is folded into governance validator | Duplicates `find_disallowed_model_refs.py` with a wider root. Standalone promotion would add confusion. |
| `tmp/find_model_refs.py` | Archive | Too broad. It returns many legitimate `openai-codex/gpt-5.5` references and historical references. Useful for one-off diagnosis, not durable truth. |
| `tmp/market_close_quick.py` | Do not promote as-is | It produces a fast yfinance close/change snapshot, but overlaps with `market_state_refresh.py`, `technical_refresh.py`, and the finance chain. It lacks the trust/freshness/error contract those scripts already carry and produced a Python UTC deprecation warning when run. If a quick market tape is needed, add a bounded mode to an existing market-state script instead of creating a second market-data surface. |

## Truth and efficiency impact

### What improves truth

- `tmp/` stops looking like it contains supported tooling.
- Workspace boundary checks become meaningful instead of repeatedly warning on known residue.
- Model-routing drift gets checked in the governance validator rather than by an undocumented scratch script.
- Market data stays in the existing finance chain surfaces with freshness/provenance, rather than a second quick script that can look authoritative without the same guardrails.

### What improves efficiency

- Fewer one-off files to inspect during audits.
- Faster operator choice: use `rg` / `workspace_index.py --search` for text lookup, use existing market/technical refresh scripts for finance data, use governance validator for model/config drift.
- No new script taxonomy needed.

## Recommended next action

Smallest useful cleanup path:

1. Add one narrow model-policy residue check to `scripts/workspace_governance_truth_check.py` only if we want this guardrail permanent.
2. Then archive the six helper files under `09. Archive/tmp-python-helpers - Archived/` with a short manifest and hashes.
3. Re-run:
   - `python scripts/workspace_boundary_check.py`
   - `python scripts/dashboard_truth_lint.py`
   - `python scripts/workspace_governance_truth_check.py --write`

Do not create six new durable scripts.
