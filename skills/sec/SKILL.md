---
name: sec
description: AI-Powered SEC Filing Integration skill. 17+ SEC filing tools for 10-K, 10-Q, 8-K, 13D/13G, insider transactions, proxy statements, company facts, and more. Works directly against the SEC EDGAR database.
---

# SEC Skill

17+ SEC filing tools. 10-K, 10-Q, 8-K, beneficial ownership (13D/13G), insider trading, proxy statements, company facts, and more.

## Github Open-Source
Please star Github if you like the skill.

https://github.com/lkcair/sec-finance-ai

Also available on OpenWebUI.

## Also try Stocks and Crypto Finance Data Pull
https://github.com/lkcair/yfinance-ai

Available on OpenClaw as "openclaw skills install stocks"

Also open-source.

---

## Setup (Run once)

From the skill directory:
```bash
python3 -m venv .venv
.venv/bin/python3 -m pip install -r requirements.txt
```

> **Windows:** use `.venv\Scripts\python.exe` instead of `.venv/bin/python3`.

## One-Shot Invocation Pattern (Works every time)

```bash
cd /home/openclaw/.openclaw/workspace/skills/sec && \
/home/openclaw/.openclaw/workspace/skills/sec/.venv/bin/python3 - << 'PY'
import asyncio, sys
sys.path.insert(0, 'scripts')
from sec_finance_ai import Tools
t = Tools()
async def main():
    result = await t.METHOD(ARGS)
    print(result)
asyncio.run(main())
PY
```

**Replace** `METHOD(ARGS)` with any function below. Always use the **full venv path** above.

---

## Common Calls (GME examples)

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
  (form_type can be: '10-K', '10-Q', '8-K', '13D', '13G', 'DEF 14A', etc. — accepts list or string)
- `get_company_facts(ticker)`
- `get_company_concept(ticker, concept)`
- `get_filing_content(url)` — retrieve full text of any filing URL
- `analyze_8k_filing(ticker, limit=3)`
- `get_recent_ipos(limit=10)`
- `search_filings(ticker, form_type=None, start_date=None, end_date=None, limit=10)`
- `get_sec_api_status()` — check SEC endpoint health
- `get_available_functions()` — list all tools programmatically
- `run_self_test()` — validate environment + SEC connectivity

---

## Routing Guide (Agent Decision Tree)

- Latest annual report → `get_latest_10k`
- Latest quarterly report → `get_latest_10q`
- Recent material events → `get_recent_8k_filings` or `analyze_8k_filing`
- Major shareholders / activist investors → `get_beneficial_ownership`
- Executive buying/selling → `get_insider_transactions`
- Director elections & compensation → `get_proxy_statements`
- Full filing history → `get_company_filings`
- Structured XBRL data → `get_company_facts`
- New IPO filings → `get_recent_ipos`

---

## Veritas local safety gate

Before any live SEC network retrieval, update `SEC_HEADERS` in `scripts/sec_finance_ai.py` with a real SEC-compliant User-Agent that identifies the requester and contact email. Do not use the packaged placeholder `SEC-AI-Research-Agent (admin@example.com)` for live retrieval. Outputs are evidence inputs only and do not authorize portfolio/canon mutation, sizing, owner approval, brokerage/account action, or trades.

## Notes

- All functions are async — wrap with `asyncio.run(main())`
- Data comes directly from SEC EDGAR (public, no API key required)
- Rate limiting is handled internally (compliant with SEC guidelines)
- CIK lookup is automatic — supports ticker or direct CIK
- Works on Linux, macOS, and Windows (adjust venv path for Windows)
- **Important**: SEC requires a valid User-Agent. The skill auto-handles this, but if you get 403 errors, check/edit `SEC_HEADERS` inside `scripts/sec_finance_ai.py`.

---

## Troubleshooting

- `ModuleNotFoundError` → You are not using the venv interpreter. Use the full path: `/home/openclaw/.openclaw/workspace/skills/sec/.venv/bin/python3`
- 403 Forbidden → Update the `User-Agent` inside `scripts/sec_finance_ai.py` (`SEC_HEADERS`)
- Empty results → Very recent filings may take 24–48h to appear in EDGAR. Try an older ticker.

---

## Quick Validation

Run this anytime to confirm everything works:
```bash
cd /home/openclaw/.openclaw/workspace/skills/sec && \
/home/openclaw/.openclaw/workspace/skills/sec/.venv/bin/python3 - << 'PY'
import asyncio, sys
sys.path.insert(0, 'scripts')
from sec_finance_ai import Tools
t = Tools()
async def main():
    print(await t.run_self_test())
asyncio.run(main())
PY
