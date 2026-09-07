from pathlib import Path

p = Path('memory/2026-05-27.md')
s = p.read_text(encoding='utf-8')
marker = '# 2026-05-27\n\n- 09:16 MST ETN canon drift repair completed'
first = s.find(marker)
second = s.find(marker, first + 1)
if second != -1:
    first_1912 = s.find('- 19:12 MST', second)
    s = s[:second] + (s[first_1912:] if first_1912 != -1 else '')
entry = '''
- 19:44 MST WF77 ticker-card resolver hardening completed after PLTR `latest_known_price: null` root cause. Fix preserved separate source artifacts and patched aggregation instead: `ticker_intelligence_card.py` now resolves latest price from Tuesday readiness -> deployment readiness -> technical refresh, and resolves band/stop from Tuesday readiness -> order-card risk check -> `tmp/portfolio-config.json`; missing readiness still remains blocking/context residue rather than erasing known price/band. Added card-level and router-QA validator checks so `technical_posture.latest_close` cannot coexist silently with null top-level `latest_known_price`, and card price/band/stop must resolve when technical close exists. Proof: `py_compile` ok; ticker-card validate-only `tmp/ticker-card-resolver-validate-summary-20260527.json` 42/0; live build `tmp/ticker-card-registry-build-summary-20260527-resolver.json` 42/0; coverage validate/write-contract ok; router QA `tmp/finance-intelligence-router-qa-2026-05-27-resolver.json` pass 390 checks / 0 errors / 0 warnings; PLTR card now has `latest_known_price=132.51`, price source `tmp/technical-refresh.json`, band 137.37-149.53 and stop 131.29 from `tmp/portfolio-config.json`, while still showing missing Tuesday position-sizing readiness and missing deployment-readiness surface residue. `artifact_index.py incremental` and `validate` ok 28/0.
'''
if 'WF77 ticker-card resolver hardening completed' not in s:
    s = s.rstrip() + entry
p.write_text(s, encoding='utf-8')
