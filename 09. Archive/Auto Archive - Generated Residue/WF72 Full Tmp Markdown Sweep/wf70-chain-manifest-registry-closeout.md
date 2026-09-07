# WF70 Chain Manifest Registry Closeout

- Status: `ok`
- Generated: `2026-05-22T23:55:26Z`
- Scope: `scripts/chain_manifest.py` official-capture expected outputs now route through `scripts/official_capture_period_registry.py` instead of duplicated static Q1 literals.
- Authority: review-only; no canon/portfolio/deployment/trade/account/paper order/sizing/sleeve/cash/risk-rule mutation and no owner-approval inference.

## No-drift proof

- full: matched `True` (76 -> 76 steps)
- morning: matched `True` (70 -> 70 steps)
- post-close: matched `True` (76 -> 76 steps)
- post-earnings: matched `True` (42 -> 42 steps)
- sunday: matched `True` (75 -> 75 steps)

- Excluded fields: `none`
- `q1-2026` literals remaining in `scripts/chain_manifest.py`: `0`

## Validation

- Registry summary: `{'captures': 31, 'critical': 0, 'historical_captures': 0, 'latest_selected': 31, 'state_counts': {'latest_current': 31}, 'tickers': 31, 'warning': 0}`
- Official capture validator: `{'captures_checked': 31, 'critical': 0, 'findings': 0, 'warning': 0}`
- Fundamental IR reconciliation validator: `31 packets / 0 findings`
- Official earnings bridge validator: `31 bridges / 0 findings`
- Capital deployment recommendation validator: `7 packets / 0 critical / 0 warning`

## Artifacts

- `tmp/wf70-proof/chain-manifest-registry-closeout-baseline.json`
- `tmp/wf70-proof/chain-manifest-registry-closeout-current.json`
- `tmp/wf70-proof/chain-manifest-registry-closeout-normalized-compare.json`
- `tmp/wf70-chain-manifest-registry-closeout.json`
