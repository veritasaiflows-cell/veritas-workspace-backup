# Script Guardrail/Evidence Documentation + SEC Smoke - 2026-05-19

## Result

- Documented `promotion_review_check.py` and `ranking_shadow_canon_check.py` in `scripts/README.md` as manual guardrails, not archive candidates and not chain/cron-owned by default.
- Ran bounded MSFT SEC evidence packet smoke test through the SEC skill venv.
- Ran validator and validator unit test.
- No chain/cron wiring, no archive/delete/move, no finance note/portfolio mutation, no paper/live order, no account action.

## SEC smoke proof

| Artifact | Status | Summary |
|---|---|---|
| `tmp/sec-evidence-packets/smoke-sec-evidence-2026-05-19.json` | `ok` | `{'critical': 0, 'tickers_checked': 1, 'warning': 0}` |
| `tmp/sec-evidence-packets/smoke-sec-evidence-validation-2026-05-19.json` | `ok` | `{'critical': 0, 'findings': 0, 'packets_checked': 1, 'warning': 0}` |

## Proof commands

```powershell
python -m py_compile scripts\promotion_review_check.py scripts\ranking_shadow_canon_check.py scripts\sec_evidence_packet.py scripts\sec_evidence_packet_validator.py
skills\sec\.venv\Scripts\python.exe scripts\sec_evidence_packet.py --tickers MSFT --forms 10-K 10-Q 8-K --filing-limit 1 --output tmp\sec-evidence-packets\smoke-sec-evidence-2026-05-19.json --markdown tmp\sec-evidence-packets\smoke-sec-evidence-2026-05-19.md
python scripts\sec_evidence_packet_validator.py --input tmp\sec-evidence-packets\smoke-sec-evidence-2026-05-19.json --output tmp\sec-evidence-packets\smoke-sec-evidence-validation-2026-05-19.json --write
python scripts\test_sec_evidence_packet_validator.py
```

Additional proof: JSON parse check passed for both smoke artifacts.

## Next recommendation

Compare GOOG official IR capture tools against current fundamental IR reconciliation/WF66, or run a broader Core 10 SEC packet smoke before considering any chain/cron wiring.
