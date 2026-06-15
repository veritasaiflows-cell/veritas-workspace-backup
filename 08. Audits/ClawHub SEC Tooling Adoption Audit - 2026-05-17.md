# ClawHub SEC Tooling Adoption Audit - 2026-05-17

## Verdict

Adopt path should start with **inspection only**, then optional install of `sec` after dependency/source review. Do **not** install `sec-edgar-tools` or `pipeworx-sec` into the Veritas OS yet.

## Candidates reviewed

| Candidate | Source reviewed | Fit | Adoption verdict | Reason |
|---|---|---|---|---|
| `sec` | ClawHub page + linked public repo page metadata | High | Inspect/install candidate after owner-aware dependency review | Direct SEC EDGAR retrieval, company facts, 10-K/10-Q/8-K, ownership, insider/proxy functions; no API key stated; rate limiting claimed |
| `sec-edgar-tools` | ClawHub page | Low / risky | Reject for now | Page mixes SEC retrieval with trading pipeline, target selection, execution semantics, A-share defaults, generated blueprint quality warning, and low evidence verify ratio |
| `pipeworx-sec` | ClawHub page | Medium but external-service dependent | Inspect later, do not install now | Simple EDGAR/MCP interface, but routes through external gateway endpoint; needs network/privacy/security review before use |

## `sec` safe-use conditions

Before install/use:
- inspect installed files, `requirements.txt`, and scripts before running setup
- confirm no credentials, brokerage endpoints, account actions, or writes outside the skill directory
- verify SEC User-Agent behavior and rate limiting
- run self-test only after dependency review
- treat outputs as source evidence, not canonical truth
- require Veritas validators / official-source bridge checks before portfolio or canon implications

Allowed use after approval:
- official SEC filing retrieval
- company facts / XBRL retrieval
- 10-K, 10-Q, 8-K, DEF 14A, 13D/13G, Form 4 evidence support
- WF65/WF66 evidence bridge support
- fundamental-pass source verification

Blocked use:
- no trade/account/brokerage action
- no portfolio mutation from SEC retrieval alone
- no direct promotion/sizing/sleeve decision without WF64 gated proposal/validation
- no probability/regression claims from filings alone

## 2026-05-17 inspection/install result

Installed `sec@1.2.3` to `skills/sec` after owner approval.

Inspection findings:
- files: `SKILL.md`, `requirements.txt`, `_meta.json`, `.clawhub/origin.json`, `scripts/sec_finance_ai.py`
- dependencies installed in local skill venv: pandas, pydantic, requests, beautifulsoup4, lxml, python-dateutil and their transitive dependencies
- network behavior: uses SEC public endpoints via `requests.get` / session GET calls
- no obvious subprocess, shell, file-delete, credential, brokerage, order-placement, or POST/PUT/PATCH/DELETE behavior found in static scan
- local import/function listing passed from `skills/sec/.venv`
- `openclaw skills check` sees `sec` as ready/visible

Stop line resolved:
- Packaged placeholder `SEC_HEADERS` User-Agent was replaced after Randall provided the contact string: `Veritas OpenClaw Research veritasaiflows@gmail.com`.
- Added a local safety gate to `skills/sec/SKILL.md`: live SEC network retrieval requires a real requester/contact User-Agent.

Validation after User-Agent patch:
- `Select-String` confirmed `scripts/sec_finance_ai.py` line 108 uses the Veritas User-Agent.
- Import/function listing passed from `skills/sec/.venv`.
- `openclaw skills check` completed with `sec` ready/visible; unrelated residues remain plugin symlink EPERM for browser skill and missing `clawhub` bin.
- Tiny SEC retrieval self-test passed: `get_company_filings(ticker='AAPL', form_type='10-K', limit=1)` returned Apple Inc., CIK `0000320193`, latest 10-K filing date `2025-10-31`, accession `0000320193-25-000079`, primary document `aapl-20250927.htm`.

## Recommended next gate

Keep `sec` as official-source evidence tooling subordinate to WF65/WF66 validators. Next useful implementation is a small Veritas wrapper or usage note that calls only approved retrieval functions, stamps provenance, and writes review-only SEC evidence packets rather than directly mutating canonical notes or portfolio state.
