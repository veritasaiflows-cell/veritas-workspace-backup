# Fundamentals Durable-Derived Data

Durable-derived fundamental and official-source support data for WF65/WF66/WF70 finance research chains.

## Authority

- Derived evidence/provenance support only.
- Not canonical portfolio truth.
- Not owner approval.
- No portfolio/canon mutation authority.
- No deployment-state mutation, sizing, sleeve, cash, risk-rule, trade/account, paper/live execution, or money-movement authority.
- Generated rows must route back to source artifacts, company official sources, SEC/company IR where applicable, and canonical owner notes before judgment.

## Current files

- `fundamentals-quarterly-v1.jsonl` — durable quarterly fundamentals/history support rows.
- `company-ir-metadata.json` — company IR/source metadata support.
- `official-ir-capture-contract.json` — official-source capture contract support.

## Producers / consumers

Known consumers include finance chain/current-window routing and official/fundamental reconciliation surfaces such as `scripts/chain_manifest.py`, `scripts/current_window_artifact_index.py`, WF65/WF66/WF70 artifacts, and `tmp/current-window-artifacts.*`.

## Retention posture

Retain in place while finance chains and current-window artifact routing reference this path. Archive/move requires a separate reference scan, source/destination hashes, rollback route, validation, and main-session approval. Do not delete from broad archive cleanup.

## Validation posture

At minimum after path/contract changes, run relevant current-window/artifact validation plus:

```powershell
python scripts\artifact_index.py validate
python scripts\workspace_boundary_check.py
```

Stop if any output implies canonical mutation, owner approval, portfolio/trade/account authority, or if source provenance is missing.
