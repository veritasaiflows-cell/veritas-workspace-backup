# WF72 entry/stop SQL activation first-slice approval request

- Generated: 2026-05-24T21:00:15Z
- Status: `approval_required_not_approved_not_activation_ready`
- Recommended first slice: `NVDA` / 6 exact metadata keys

## Exact keys

- `NVDA:reference_price_low`
- `NVDA:reference_price_high`
- `NVDA:reference_invalidation_level`
- `NVDA:reference_level_source_timestamp`
- `NVDA:reference_level_source_sha256`
- `NVDA:reference_level_owner_source_path`

## Values from worker preflight

```json
{
  "reference_price_low": 198.47,
  "reference_price_high": 216.66,
  "reference_invalidation_level": 187.9,
  "reference_level_source_timestamp": "2026-05-22",
  "reference_level_source_sha256": "c8e57255981f3c1410236b6ec11ca5a2ed296e7a413d2f66d3e6e41d64d38d64",
  "reference_level_owner_source_path": "03. Portfolio/Execution Board.md"
}
```

## If Randall approves

Use this exact approval wording or equivalent:

> Approved: WF72 entry/stop SQL reference-metadata first slice for exactly NVDA:reference_price_low, NVDA:reference_price_high, NVDA:reference_invalidation_level, NVDA:reference_level_source_timestamp, NVDA:reference_level_source_sha256, NVDA:reference_level_owner_source_path; metadata/proof cache only; no portfolio/canon/trade/account/paper/live/action-state authority.

Approval would still only authorize the next proof/activation pass for this exact slice. It would not authorize broad SQL finance canon, portfolio mutation, owner approval inference, dashboard action-state changes, or trade/account/paper/live authority.
