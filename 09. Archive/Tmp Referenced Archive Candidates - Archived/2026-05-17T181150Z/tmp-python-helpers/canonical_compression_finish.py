from pathlib import Path
p=Path('04. Research/Coverage Universe.md')
text=p.read_text(encoding='utf-8')
repls={
'- **Act when:** Post-earnings requalification path: oil structure (Brent >$100 sustained), EIA reads confirming demand, and 50-day reclaim. Entry band and stop require a fresh post-print technical pass — the Apr 24 levels ($142.50–$147.50 / stop $139.50) predate the May 1 print and should not be used without revalidation.':'- **Act when:** Post-earnings requalification path: oil structure stays supportive, EIA reads confirm demand, and the chart reclaims a decision-grade structure. Exact entry and invalidation levels belong in the Technical Sheet.',
'- **Act when:** LNG complex stabilizes post-ceasefire. Confirm Cheniere had no contract disruptions during the Hormuz period. Entry requires a clean technical setup with defined levels. May 7 earnings window active.':'- **Act when:** LNG complex stabilizes post-ceasefire and confirms no material contract disruption from the Hormuz period. Any entry setup requires a clean Technical Sheet update first.',
'- **Act when:** Only promote after XOM is requalified or deployed and sector allocation still has room for a second energy position. Define explicit entry band and stop before treating it as a real deployment candidate.':'- **Act when:** Only promote after XOM is requalified or deployed and sector allocation still has room for a second energy position. Exact levels belong in the Technical Sheet before any deployment review.',
'- **Act when:** Keep it watch-lane only until a fresh entry band and stop are defined and the post-print structure proves it deserves capital competition versus ETN and other stronger current setups.':'- **Act when:** Keep it watch-lane only until the post-print structure proves it deserves capital competition versus ETN and other stronger current setups. Exact levels belong in the Technical Sheet.',
'- **Key risk:** F-35 TR-3/Block 4 software execution failure; defense budget top-line pressure; program delivery delays. Post-Apr-23 close at $509.68 — below all MAs including the 200-day. The earnings drop (~14%, ~$82) confirmed structural deterioration that was already visible before the print.':'- **Key risk:** F-35 TR-3/Block 4 software execution failure; defense budget top-line pressure; program delivery delays. The post-report drawdown confirmed structural deterioration that was already visible before the print.',
'- **Act when:** A fresh base must form above $509.68 with at least 4–6 weeks of price stabilization. The old $590–$603 entry band is fully invalidated. New levels cannot be set until a new base is defined from post-report structure. Do not treat defense-sector strength as permission to re-enter LMT specifically until individual setup repairs.':'- **Act when:** A fresh post-report base must form with several weeks of price stabilization. New levels belong in the Technical Sheet after the base exists. Do not treat defense-sector strength as permission to re-enter LMT specifically until individual setup repairs.',
'- **Act when:** Define entry band and stop before deploying. Setup still lacks decision-grade levels. Positive earnings read-through from April 21 improves conviction but does not substitute for levels.':'- **Act when:** Setup still needs decision-grade Technical Sheet levels. Positive earnings read-through improves conviction but does not substitute for a defined setup.',
'- **Status:** In portfolio draft — ⚠️ earnings alert active (April 29, after close)':'- **Status:** In portfolio draft — post-earnings revalidated; almost deployable but still entry-dependent',
'- **Act when:** Post-earnings April 29. Azure growth above ~20% and Copilot revenue trajectory confirmed = accumulate on pullback to $393–$401 entry band. Stop $385.':'- **Act when:** Azure growth and Copilot revenue trajectory remain confirmed, and the Technical Sheet shows a disciplined pullback or repair setup. Exact entry and invalidation levels live outside this thesis note.',
'- **Act when:** Post-earnings April 29. Search revenue resilience and cloud growth confirmation = accumulate on pullback to $314–$321 entry band. Stop $305.50.':'- **Act when:** Search resilience and cloud growth remain confirmed, and the Technical Sheet shows a disciplined pullback setup. Exact entry and invalidation levels live outside this thesis note.',
'- **Act when:** Pullback to $186–$191 preferred entry band only. Never chase vertical moves. May 20 earnings window — timing-sensitive until confirmed. Stop $179.50.':'- **Act when:** Only after a disciplined pullback or post-earnings reset. Never chase vertical moves; timing and crowding caveats must remain explicit in the Trigger / Technical layers.',
'- **Status:** In portfolio draft — best current technical setup, earnings timing-sensitive (Apr 30–May 5 window)':'- **Status:** In portfolio draft — owner-approved conditional add; technical state owned by Trigger / Technical layers',
'- **Act when:** Pullback to $388–$396 preferred entry band. Best MA posture in the portfolio — bullish 20>50>200 stack. Earnings timing-sensitive: confirm date before sizing. Stop $382.50.':'- **Act when:** Owner-approved conditional add remains valid only while the Trigger / Technical layers confirm the setup and no-chase discipline. Exact levels and invalidation live outside this thesis note.',
'- **Status:** Active watch — May 5 earnings':'- **Status:** Active watch — post-earnings read-through only',
'- **Act when:** May 5 earnings. Beat and strong MI300X demand guidance = upgrade to near-term tactical entry with defined levels.':'- **Act when:** Strong AI accelerator demand and server CPU execution support a tactical upgrade, and the Technical Sheet defines a decision-grade setup.',
'- **Act when:** Define entry band and stop before considering deployment. Use the beat-and-raise as thesis confirmation — not as permission to chase. ETN first; VRT second. Entry only on a controlled, non-chasing setup with explicit levels.':'- **Act when:** Use the beat-and-raise as thesis confirmation, not as permission to chase. ETN remains first; VRT only competes for capital after the Technical Sheet shows a controlled setup.',
'- **Act when:** Promote only if governance/restatement residue is resolved cleanly and a defined technical base forms with explicit entry and stop. Treat as Tier 3 max even if the thesis improves.':'- **Act when:** Promote only if governance/restatement residue is resolved cleanly and the Technical Sheet confirms a base. Treat as Tier 3 max even if the thesis improves.',
'- **Act when:** Keep it watch-lane only until valuation/setup justify real capital competition and explicit entry/stop levels are defined. If the healthcare sleeve remains one-name only, Lilly is the preferred first monitor unless evidence later makes JNJ or another defensive alternative cleaner.':'- **Act when:** Keep it watch-lane only until valuation and setup justify real capital competition. If the healthcare sleeve remains one-name only, Lilly is the preferred first monitor unless evidence later makes JNJ or another defensive alternative cleaner.',
'- **Act when:** Pullback to $300–$306 preferred entry band. Second-cleanest setup in the portfolio after ETN. Stop $295.50.':'- **Act when:** Owner approval remains recorded, but the Trigger / Technical layers must show the live setup has repaired or been explicitly reviewed before action.',
'- **Act when:** Confirmed risk-on environment with improving deal and M&A activity. Secondary financial name after JPM is established. Define entry and stop before deploying.':'- **Act when:** Confirmed risk-on environment with improving deal and M&A activity, while the Technical Sheet shows a disciplined setup. Keep GS secondary to JPM.',
'- **Act when:** Market pullback into $465–$472 preferred entry band with MA structure repairing above the 481 level. Currently benched — price is in band but below all three MAs. Stop $459.50.':'- **Act when:** Market pullback and MA structure repair enough to justify ballast exposure again. Exact levels and invalidation belong in the Technical Sheet.',
'- **Status:** Active watch — ⚠️ earnings alert active (April 29, after close)':'- **Status:** Active watch — post-earnings setup still secondary',
'- **Act when:** April 29 earnings. Strong AWS growth and operating leverage confirmation = upgrade to portfolio candidate and define entry band and stop before deploying.':'- **Act when:** AWS growth and operating leverage remain constructive, and the Technical Sheet defines a disciplined setup before any promotion review.',
'- **Act when:** Reclaim and hold the 174–177 repair zone, preserve 161–164 support, and complete debt maturity / interest coverage review from the latest 10-Q/10-K notes before any deployment-grade recommendation. No capital deployment while below the 20/50/200DMA structure, and no canonical band apply while `repair_mode` / below-stop posture remains active.':'- **Act when:** Technical repair is confirmed in the Technical Sheet and debt maturity / interest coverage review is complete from the latest 10-Q/10-K notes. No capital deployment while repair-mode / below-stop posture remains active.',
'- **Act when:** Geopolitical risk re-escalation or dollar weakness confirms a breakout above recent resistance. Define entry and stop before deploying.':'- **Act when:** Geopolitical risk re-escalation or dollar weakness confirms the thesis and the Technical Sheet defines a setup before deployment review.',
'- **Act when:** Treat as a speculative sleeve candidate only. Monitor for breakout above key resistance or macro stress escalation that reinforces the hedge thesis. Any sizing above 3% requires deliberate exception review.':'- **Act when:** Treat as a speculative sleeve candidate only. Monitor for macro stress or hard-asset rotation that reinforces the hedge thesis. Any sizing above 3% requires deliberate exception review.',
'| LNG | Energy | Tactical | Active watch — May 7 earnings |':'| LNG | Energy | Tactical | Active watch |',
'| LMT | Defense | Core candidate | Do not touch — repair mode post Apr 23 |':'| LMT | Defense | Core candidate | Do not touch — repair mode |',
'| RTX | Defense | Tactical | Active watch — beat Apr 21, no levels yet |':'| RTX | Defense | Tactical | Active watch |',
'| MSFT | Technology | Core candidate | Almost deployable — post-earnings scorecard complete; still needs cleaner repair |':'| MSFT | Technology | Core candidate | Almost deployable |',
'| GOOG | Technology | Core candidate | Almost deployable — post-earnings scorecard complete; still needs pullback into band |':'| GOOG | Technology | Core candidate | Almost deployable |',
'| NVDA | Technology | Tactical | Wait / no chase — above band with May 20 timing and crowding risk |':'| NVDA | Technology | Tactical | Wait / no chase |',
'| AMD | Technology | Tactical | Active watch — earnings May 5 |':'| AMD | Technology | Tactical | Active watch |',
'| JPM | Financials | Core candidate | Almost deployable — owner approval recorded, but trigger not live below band |':'| JPM | Financials | Core candidate | Almost deployable |',
'| GS | Financials | Tactical | Almost deployable — tactical secondary to JPM, still above band |':'| GS | Financials | Tactical | Almost deployable |',
'| AMZN | Large-cap Quality | Tactical | Active watch — earnings Apr 29 |':'| AMZN | Large-cap Quality | Tactical | Active watch |',
'| BKNG | Consumer Discretionary | Core candidate | Active watch — technical repair required; earnings timing now provider-clear, not primary-confirmed |':'| BKNG | Consumer Discretionary | Core candidate | Active watch / repair |',
'- 2026-05-10 — BKNG artifact-confirmed cleanup: earnings timing moved from `UNKNOWN` to provider-clear (`2026-07-29`, not primary-confirmed), while technical repair / below-stop state keeps deployment and canonical band apply blocked.':'- 2026-05-10 — BKNG artifact-confirmed cleanup: earnings timing moved from `UNKNOWN` to provider-clear (`2026-07-29`, not primary-confirmed), while technical repair state keeps deployment and canonical band apply blocked.',
'- Next review: after direct BKNG earnings-date confirmation, after BKNG repair/reclaim evidence appears, or when durable thesis/key-risk/act-when conditions change materially':'- Next review: after direct BKNG earnings-date confirmation, after BKNG repair/reclaim evidence appears in the Technical Sheet, or when durable thesis/key-risk/act-when conditions change materially'
}
for old,new in repls.items():
    if old not in text:
        print('MISS:', old[:100])
    text=text.replace(old,new)
text=text.replace('- 2026-05-10 — BKNG artifact-confirmed cleanup:', '- 2026-05-10 — Canonical ownership compression v1 thinned exact level/trigger details from Coverage; BKNG artifact-confirmed cleanup:')
p.write_text(text, encoding='utf-8')

p=Path('03. Portfolio/Technical Entry and Invalidation Sheet.md')
text=p.read_text(encoding='utf-8')
start=text.index('## Current ranking after precision pass')
end=text.index('## Data-quality note', start)
summary='''## Technical condition summary

This section summarizes technical state only. Deployment priority, owner approval state, and portfolio action authority live in [[03. Portfolio/Deployment Trigger Sheet]].

- **Constructive / needs discipline:** ETN, GOOG, MSFT, GS, NVDA, VRT.
- **Repair or weak structure:** BRK.B, XOM, LMT, RTX, BKNG.
- **Watch-lane technical carryovers:** AMZN, CAT, LLY, and other monitored names remain non-execution-board-entitled unless explicitly promoted.

'''
text=text[:start]+summary+text[end:]
start=text.index('## Bottom line')
bottom='''## Bottom line

- This sheet owns technical condition, levels, repair zones, and invalidation.
- It does not grant owner approval, portfolio weight, trade authority, or deployment state.
- Use [[03. Portfolio/Deployment Trigger Sheet]] for live action state and [[03. Portfolio/Portfolio Snapshot]] for weight/concentration context.
- **Confidence:** usable with caution — dashboard validation is clean on critical/warning count, but monitor-only band-review items and source-confidence caveats still require judgment.
'''
text=text[:start]+bottom
p.write_text(text, encoding='utf-8')
