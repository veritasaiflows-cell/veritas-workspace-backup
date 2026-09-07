from pathlib import Path
p = Path('06. Playbooks/Project Continuity/Workflow 77 - Finance Intelligence Coverage and Question Router.md')
s = p.read_text(encoding='utf-8')
entry = """
2026-05-27 19:44 MST: WF77 V1.4a ticker-card resolver hardening closed after PLTR exposed a top-level `latest_known_price: null` despite technical refresh containing a valid close. Preserved separate source artifacts; patched `scripts/ticker_intelligence_card.py` aggregation so latest price resolves Tuesday readiness -> deployment readiness -> technical refresh, and band/stop resolve Tuesday readiness -> order-card risk check -> `tmp/portfolio-config.json`. Missing Tuesday position-sizing or deployment-readiness rows remain explicit blocking/context residue and do not imply actionability. Added card validation and `scripts/finance_intelligence_router_qa.py` checks so a technical close cannot silently coexist with null top-level latest price, and price/band/stop must resolve when technical close exists. Proof: py_compile passed; `tmp/ticker-card-resolver-validate-summary-20260527.json` 42 cards / 0 errors; live build `tmp/ticker-card-registry-build-summary-20260527-resolver.json` 42 cards / 0 errors; coverage validate/write-contract passed; `tmp/finance-intelligence-router-qa-2026-05-27-resolver.json` passed 390 checks / 0 errors / 0 warnings; PLTR card now reports latest price 132.51 from `tmp/technical-refresh.json`, band 137.37-149.53 and stop 131.29 from `tmp/portfolio-config.json`; artifact index incremental + validate passed 28/28. Boundary unchanged: cards remain review/routing only and grant no canon/portfolio mutation, owner approval, sizing/cash/risk-rule change, paper/live execution, brokerage/account action, or money movement.
"""
if 'WF77 V1.4a ticker-card resolver hardening closed' not in s:
    marker = '2026-05-27 18:35 MST: WF77 V1.4 enriched ticker-card full-picture pass closed'
    idx = s.find(marker)
    if idx != -1:
        next_section = s.find('\n\n## ', idx)
        insert_at = next_section if next_section != -1 else len(s)
        s = s[:insert_at].rstrip() + '\n\n' + entry.strip() + '\n' + s[insert_at:]
    else:
        s = s.rstrip() + '\n\n' + entry.strip() + '\n'
s = s.replace('Use WF77 V1.4 as the default first route', 'Use WF77 V1.4a as the default first route')
p.write_text(s, encoding='utf-8')
