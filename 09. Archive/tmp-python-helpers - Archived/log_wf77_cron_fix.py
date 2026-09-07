from pathlib import Path
p=Path('memory/2026-05-27.md')
s=p.read_text(encoding='utf-8')
entry='''\n- 21:04 MST WF77 weekly analyst-consensus cron delivery fix applied from Randall approval. Updated existing isolated producer job `95da55c1-5288-4aab-972e-b730ad140c55` to `delivery.mode=none` so it no longer fail-closes on missing channel route, and expanded its payload to refresh yfinance analyst consensus, rebuild all coverage ticker cards via `--all-from-coverage`, validate coverage/router QA, and refresh/validate artifact index. Added paired main-session handoff job `9b3ee682-8d2c-41b5-ac9c-deca4fdff5a7` for Mondays 15:50 America/Phoenix to inspect weekly WF77 artifacts and report only blockers/material manual-review or consensus changes; clean/unremarkable state replies `NO_REPLY`. Verification: cron list now shows 25 active jobs; both WF77 jobs have delivery preview `not requested`; no channel route dependency remains. Boundaries unchanged: review-only, no canon/portfolio mutation, no owner approval inference, no sizing/cash/risk-rule change, no paper/live order, no brokerage/account action, no money movement, no config/auth/channel mutation.\n'''
if 'WF77 weekly analyst-consensus cron delivery fix applied' not in s:
    s=s.rstrip()+entry
p.write_text(s, encoding='utf-8')
