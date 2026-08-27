---
name: "sec"
description: "Windows-first SEC docs, balanced fences, review-only boundaries."
---

# SEC Skill

17+ SEC filing tools for SEC EDGAR evidence work: 10-K, 10-Q, 8-K, beneficial ownership (13D/13G), insider transactions, proxy statements, company facts, filing search, and more.

## Github Open-Source

Please star Github if you like the skill.

https://github.com/lkcair/sec-finance-ai

Also available on OpenWebUI.

## Also Try Stocks And Crypto Finance Data Pull

https://github.com/lkcair/yfinance-ai

Available on OpenClaw as `openclaw skills install stocks`.

---

## Setup

The local Veritas workspace currently keeps an active dependency environment at `skills\sec\.venv`. Do not delete, move, rebuild, or update that environment unless Randall explicitly approves a separate dependency/footprint lane with backup, rollback, and smoke proof.

If a fresh setup or approved rebuild is ever needed from the SEC skill directory on Windows:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Linux/macOS fallback:

```bash
python3 -m venv .venv
.venv/bin/python3 -m pip install -r requirements.txt
```

## One-Shot Invocation Pattern

Use the Windows-first pattern from the workspace SEC skill directory:

```powershell
Set-Location C:\Users\Veritas\.openclaw\workspace\skills\sec
@'
import asyncio
import sys
sys.path.insert(0, "scripts")
from sec_finance_ai import Tools

t = Tools()

async def main():
    result = await t.METHOD(ARGS)
    print(result)

asyncio.run(main())
'@ | .\.venv\Scripts\python.exe -
```

Replace `METHOD(ARGS)` with any function below. Use the full local venv interpreter path when calling from outside the skill directory: `C:\Users\Veritas\.openclaw\workspace\skills\sec\.venv\Scripts\python.exe`.

## Common Calls

| Need | Method |
|---|---|
| Latest 10-K | `get_latest_10k(ticker='GME')` |
| Latest 10-Q | `get_latest_10q(ticker='GME')` |
| Recent 8-K filings | `get_recent_8k_filings(ticker='GME', limit=3)` |
| Beneficial ownership (13D/13G) | `get_beneficial_ownership(ticker='GME')` |
| Company filings index | `get_company_filings(ticker='GME', form_type='10-K', limit=5)` |
| Insider transactions | `get_insider_transactions(ticker='GME')` |
| Proxy statements (DEF 14A) | `get_proxy_statements(ticker='GME')` |
| Company facts / XBRL | `get_company_facts(ticker='GME')` |
| Search filings | `search_filings(ticker='GME', form_type='8-K')` |
| Self-test all tools | `run_self_test()` |

---

## All Available Functions

- `get_latest_10k(ticker)`
- `get_latest_10q(ticker)`
- `get_recent_8k_filings(ticker, limit=5)`
- `get_beneficial_ownership(ticker)`
- `get_insider_transactions(ticker)`
- `get_proxy_statements(ticker)`
- `get_company_filings(ticker, form_type=None, limit=10)`
  - `form_type` can be `'10-K'`, `'10-Q'`, `'8-K'`, `'13D'`, `'13G'`, `'DEF 14A'`, etc.; list and string values are accepted.
- `get_company_facts(ticker)`
- `get_company_concept(ticker, concept)`
- `get_filing_content(url)` - retrieve full text of any filing URL
- `analyze_8k_filing(ticker, limit=3)`
- `get_recent_ipos(limit=10)`
- `search_filings(ticker, form_type=None, start_date=None, end_date=None, limit=10)`
- `get_sec_api_status()` - check SEC endpoint health
- `get_available_functions()` - list all tools programmatically
- `run_self_test()` - validate environment and SEC connectivity

---

## Routing Guide

- Latest annual report -> `get_latest_10k`
- Latest quarterly report -> `get_latest_10q`
- Recent material events -> `get_recent_8k_filings` or `analyze_8k_filing`
- Major shareholders / activist investors -> `get_beneficial_ownership`
- Executive buying/selling -> `get_insider_transactions`
- Director elections and compensation -> `get_proxy_statements`
- Full filing history -> `get_company_filings`
- Structured XBRL data -> `get_company_facts`
- New IPO filings -> `get_recent_ipos`

---

## Veritas Local Safety Gate

Before any live SEC network retrieval, confirm `SEC_HEADERS` in `scripts/sec_finance_ai.py` uses a real SEC-compliant User-Agent that identifies the requester and contact email. Do not use the packaged placeholder `SEC-AI-Research-Agent (admin@example.com)` for live retrieval.

Current expected local value: `Veritas OpenClaw Research veritasaiflows@gmail.com`.

Outputs are official-source evidence inputs only. They do not authorize portfolio/canon mutation, sizing/allocation, owner approval, brokerage/account action, capital deployment, paper/live execution, money movement, external delivery, or trades.

## Notes

- All SEC tool functions are async; wrap them with `asyncio.run(main())`.
- Data comes directly from SEC EDGAR and does not require an API key.
- Rate limiting is handled internally for SEC guideline compliance.
- CIK lookup is automatic and supports ticker or direct CIK inputs.
- The local Veritas runtime is Windows/PowerShell. Linux/macOS examples are fallback only.
- SEC requires a valid User-Agent. If you get 403 errors, check `SEC_HEADERS` inside `scripts/sec_finance_ai.py` before retrying.

---

## Troubleshooting

- `ModuleNotFoundError`: you are not using the venv interpreter. Use `C:\Users\Veritas\.openclaw\workspace\skills\sec\.venv\Scripts\python.exe`.
- `403 Forbidden`: verify `SEC_HEADERS["User-Agent"]` inside `scripts/sec_finance_ai.py` is real and not the packaged placeholder.
- Empty results: very recent filings may take 24-48 hours to appear in EDGAR. Try an older ticker or a narrower form type.

---

## Quick Validation

Run this local import check anytime to confirm the venv and tool surface load without changing finance/canon/portfolio/account state:

```powershell
Set-Location C:\Users\Veritas\.openclaw\workspace\skills\sec
@'
import sys
sys.path.insert(0, "scripts")
from sec_finance_ai import Tools

t = Tools()
methods = [name for name in dir(t) if not name.startswith("_") and callable(getattr(t, name))]
print(len(methods))
print("\n".join(sorted(methods)))
'@ | .\.venv\Scripts\python.exe -
```

Networked SEC smoke tests are allowed only after the User-Agent is confirmed and the target is review-only evidence. They do not grant portfolio/canon/trade/account authority.
