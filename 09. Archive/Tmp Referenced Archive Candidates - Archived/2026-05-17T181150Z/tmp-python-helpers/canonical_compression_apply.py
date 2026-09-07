from pathlib import Path

# Watchlist: compress state labels.
p = Path('02. Markets/Watchlist.md')
text = p.read_text(encoding='utf-8')
start = text.index('| Ticker | Sector | Coverage Tier | Current Deployment State | Canonical Source |')
end = text.index('\n---\n\n## Priority orientation', start)
watch_table = '''| Ticker | Sector | Coverage Tier | Current Deployment State | Canonical Source |
|---|---|---|---|---|
| JPM | Financials | Core candidate | Almost deployable / owner-approved but trigger not live | Trigger Sheet |
| ETN | Tech / AI Infrastructure | Core candidate | Deployable now / conditional add | Trigger Sheet |
| VRT | Tech / AI Infrastructure | Tactical | Watch / research needed | Trigger Sheet |
| NVDA | Tech / AI Infrastructure | Tactical | Wait / no chase | Trigger Sheet |
| MSFT | Tech / AI Infrastructure | Core candidate | Almost deployable | Trigger Sheet |
| BRK.B | Diversified Quality | Core candidate | Do not touch / repair | Trigger Sheet |
| RTX | Defense | Tactical | Active watch / repair | Technical Sheet |
| GOOG | Tech / AI Infrastructure | Core candidate | Almost deployable | Trigger Sheet |
| AMZN | Large-cap Quality | Tactical | Active watch | Technical Sheet |
| XOM | Energy | Core candidate | Do not touch / repair | Trigger Sheet |
| CVX | Energy | Tactical | Active watch | Coverage Universe |
| LMT | Defense | Core candidate | Do not touch / repair | Trigger Sheet |
| AMD | Tech / AI Infrastructure | Tactical | Active watch | Coverage Universe |
| BKNG | Consumer Discretionary / Travel Services | Core candidate | Active watch / repair | Coverage Universe + Technical Sheet |
| GS | Financials | Tactical | Almost deployable | Trigger Sheet |
| CAT | Industrials | Tactical | Active watch | Technical Sheet |
| LNG | Energy | Tactical | Active watch | Coverage Universe |
| PLTR | Tech / Defense | Tactical / Speculative | Active watch | Coverage Universe |
| KTOS | Defense | Speculative | Draft speculative sleeve | Coverage Universe |
| SLV | Macro | Speculative | Draft speculative sleeve | Coverage Universe |
| TLT | Macro | Speculative | Benched | Coverage Universe |
| SMCI | Tech / AI Infrastructure | Speculative | Active watch | Coverage Universe |
| LLY | Healthcare | Sector monitor | Active watch | Technical Sheet |'''
text = text[:start] + watch_table + text[end:]
text = text.replace('- Last updated: 2026-05-10 — BKNG index entry compressed to active watch / repair with ownership split across Coverage Universe and Technical Sheet. ETN remains deployable-now / conditional add; JPM remains owner-approved but trigger-not-live; NVDA remains wait / no chase; GOOG / GS / MSFT remain almost deployable.', '- Last updated: 2026-05-10 — canonical ownership compression v1 shortened all ticker rows to state labels and source pointers. Details live in Coverage Universe, Technical Sheet, Trigger Sheet, or Snapshot by lane.')
p.write_text(text, encoding='utf-8')

# Portfolio Snapshot: compress posture line and owned tables.
p = Path('03. Portfolio/Portfolio Snapshot.md')
text = p.read_text(encoding='utf-8')
text = text.replace('- **Current priority order:** **ETN** is the only current deployable-now name after explicit owner approval and a still-in-band 2026-05-08 close. **JPM** owner approval remains recorded, but the latest machine close at 302.10 is below the formal 306.82–318.12 band and close to 301.17 invalidation, so it fails closed to **almost deployable / trigger not live** until reclaim or explicit band review. **NVDA** is **wait / no chase** after the rerun showed 215.20 above the 197.01–210.84 band and the May 20 timing window remains active. **GOOG**, **GS**, and **MSFT** remain **almost deployable** candidates only. **BRK.B**, **LMT**, and **XOM** remain do-not-touch / repair. GS remains tactical and secondary to JPM inside the 10% cash / 25% sector-cap posture.', '- **Current priority order:** ETN is the only deployable-now / conditional-add name. JPM is owner-approved but trigger-not-live. NVDA is wait / no chase. GOOG, GS, and MSFT are almost deployable. BRK.B, LMT, and XOM remain bench / repair. Detail lives in the Trigger Sheet and Technical Sheet, not this snapshot.')
start = text.index('## Core holdings')
end = text.index('## Sector allocation vs. Risk Rules caps', start)
portfolio_sections = '''## Core holdings

This table owns draft model role and weight only. Thesis detail belongs in [[04. Research/Coverage Universe]]; trigger and level detail belongs in [[03. Portfolio/Deployment Trigger Sheet]] and [[03. Portfolio/Technical Entry and Invalidation Sheet]].

| Ticker | Sleeve role | Draft weight | Portfolio status | Detail source |
|---|---:|---:|---|---|
| MSFT | Core Technology quality | 10% | Draft core; almost deployable, not automatic | Coverage + Trigger |
| JPM | Core Financials | 14% | Owner approval recorded; trigger not live | Coverage + Trigger |
| GOOG | Core Technology quality | 10% | Draft core; almost deployable on better entry | Coverage + Trigger |
| XOM | Core Energy | 10% | Bench / repair until follow-through improves | Coverage + Trigger |
| LMT | Core Defense | 10% | Repair mode; stance suspended | Coverage + Trigger |
| BRK.B | Diversified quality ballast | 12% | Repair mode; bench state holds | Coverage + Trigger |

## Tactical positions

| Ticker | Sleeve role | Draft weight | Portfolio status | Detail source |
|---|---:|---:|---|---|
| ETN | AI-power / electrification tactical | 7% | Deployable now / conditional add; manual-only | Coverage + Trigger |
| NVDA | AI leader tactical | 5% | Wait / no chase | Coverage + Trigger |
| GS | Tactical Financials secondary | 7% | Almost deployable; secondary to JPM | Coverage + Trigger |

## Speculative sleeve

| Ticker / Asset | Sleeve role | Draft weight | Portfolio status | Detail source |
|---|---:|---:|---|---|
| KTOS | Defense-tech asymmetry | 2% | Draft speculative sleeve | Coverage Universe |
| SLV | Macro / metals hedge | 3% | Draft speculative sleeve | Coverage Universe |

## Watch now

Watch-only names carry no model weight and no deployment authority unless separately promoted.

| Ticker | Portfolio implication | Detail source |
|---|---|---|
| AMZN | Large-cap quality monitor | Coverage + Technical |
| BKNG | Consumer Discretionary candidate; no model weight | Coverage + Technical |
| VRT | AI-power monitor, secondary to ETN | Coverage + Trigger |
| LLY | Healthcare diversification monitor | Coverage + Technical |
| CAT | Industrial read-through monitor | Coverage + Technical |
| RTX | Defense repair monitor | Coverage + Technical |
| TLT | Duration / macro monitor | Coverage Universe |

'''
text = text[:start] + portfolio_sections + text[end:]
start = text.index('## Risk flags')
end = text.index('## Freshness and refresh policy', start)
risk = '''## Risk flags

- This is still a model draft, not an execution-ready account snapshot.
- Draft weights are not live allocations and do not grant trade authority.
- ETN is the only current deployable-now / conditional-add name in the owner layer, and it remains manual-only.
- JPM approval remains recorded, but the live trigger is not green until reclaim or explicit band review.
- GOOG, GS, MSFT, and NVDA require better entry quality or event resolution before any deployment escalation.
- BRK.B, LMT, and XOM remain bench / repair.
- Direct Tech is already at the written cap; the broader AI-power sleeve still needs concentration discipline.
- If total model drawdown exceeds 6% to 8%, force a full review.

'''
text = text[:start] + risk + text[end:]
start = text.index('## Recommended review actions')
recs = '''## Recommended review actions

1. Use [[03. Portfolio/Deployment Trigger Sheet]] for live decision state.
2. Use [[03. Portfolio/Technical Entry and Invalidation Sheet]] for exact bands, stops, repair zones, and invalidation.
3. Use [[04. Research/Coverage Universe]] for thesis, key risk, and act-when conditions.
4. Revisit draft weights only when blocker status, setup quality, thesis conviction, or concentration posture actually changes.
5. Keep watch-only and repair-mode names explicitly benched until new evidence changes their lane.
'''
text = text[:start] + recs
text = text.replace('- **Last updated:** 2026-05-10', '- **Last updated:** 2026-05-10 — canonical ownership compression v1')
text = text.replace('- **Data as of:** 2026-05-08 close with fresh ETN / NVDA entry-band rerun outputs and BKNG repair-mode artifact sync', '- **Data as of:** 2026-05-08 close for current trigger/technical surfaces')
text = text.replace('- **Next refresh due:** after ETN follow-through confirmation, after LNG / NFP follow-up, after NVDA May 20 timing resolution, after BKNG primary earnings-date confirmation or repair-zone reclaim, and when real setup quality changes justify another weight review', '- **Next refresh due:** when a model weight, sleeve role, concentration limit, or portfolio-level status changes materially')
p.write_text(text, encoding='utf-8')

# Deployment Trigger Sheet: clarify role, compress board/recommendation.
p = Path('03. Portfolio/Deployment Trigger Sheet.md')
text = p.read_text(encoding='utf-8')
text = text.replace('- it owns deployable, almost deployable, blocked, and do-not-touch states\n- it owns entry bands, invalidation, and gate-based justification\n- it does not replace the weekly operating map or the portfolio-allocation note', '- it owns deployable, almost deployable, blocked, and do-not-touch states\n- it owns the live gate verdict and concise blocker / condition for execution-board names\n- exact levels, stops, support, resistance, and repair mechanics live in [[03. Portfolio/Technical Entry and Invalidation Sheet]]\n- thesis detail lives in [[04. Research/Coverage Universe]] and portfolio-weight context lives in [[03. Portfolio/Portfolio Snapshot]]')
start = text.index('## Current deployment board')
end = text.index('## Pull-the-trigger rule', start)
board = '''## Current deployment board

This board is intentionally compressed. It owns live execution state and blocker logic only; use the Technical Sheet for exact bands/stops and Coverage Universe for thesis detail.

| Ticker | Action state | Live condition / blocker | Authority note | Detail source |
|---|---|---|---|---|
| ETN | **Deployable now** | Owner-promoted conditional add; must remain inside written setup and respect no-chase discipline | Manual-only; no automatic execution | Technical Sheet + Coverage Universe |
| JPM | **Almost deployable** | Owner approval recorded, but trigger is not live until reclaim or explicit band review | Approval remains recorded; execution fails closed | Technical Sheet |
| GOOG | **Almost deployable** | Thesis confirmed; entry still needs pullback / better setup | Explicit promotion still required | Technical Sheet + Coverage Universe |
| MSFT | **Almost deployable** | Thesis confirmed; still needs cleaner repair / promotion | Explicit promotion still required | Technical Sheet + Coverage Universe |
| NVDA | **Wait / no chase** | Above written setup with timing and concentration caveats active | No deployable-now authority | Technical Sheet + Coverage Universe |
| GS | **Almost deployable** | Tactical secondary to JPM; entry discipline still required | Explicit promotion still required | Technical Sheet + Coverage Universe |
| VRT | **Watch / research needed** | Thematic fit is real, but ETN remains primary AI-power execution name | No quiet promotion | Technical Sheet + Coverage Universe |
| BRK.B | **Do not touch** | Repair / chart weakness still active | Bench state holds | Technical Sheet |
| XOM | **Do not touch** | Post-print follow-through still not clean enough | Bench state holds | Technical Sheet + Coverage Universe |
| LMT | **Do not touch** | Repair mode after failed setup | No re-entry case yet | Technical Sheet + Coverage Universe |

## Current priority order

- **Deployable now:** ETN.
- **Owner-approved but trigger not live:** JPM.
- **Wait / no chase:** NVDA.
- **Almost deployable:** GOOG, GS, MSFT.
- **Watch / repair:** BKNG and VRT, with BKNG details owned by Coverage Universe + Technical Sheet.
- **Bench / do not touch:** BRK.B, LMT, XOM.

'''
text = text[:start] + board + text[end:]
start = text.index('## Current recommendation')
end = text.index('## Freshness and update policy', start)
summary = '''## Current recommendation

- Keep the board manual and owner-gated.
- ETN is the only current deployable-now / conditional-add name.
- JPM remains owner-approved but trigger-not-live.
- GOOG, GS, MSFT, and NVDA need better entry quality, promotion, or timing resolution before escalation.
- BKNG and other watch-lane names remain review-only and do not enter the execution board without explicit promotion.

'''
text = text[:start] + summary + text[end:]
text = text.replace('- Last updated: 2026-05-10', '- Last updated: 2026-05-10 — canonical ownership compression v1')
text = text.replace('- Data as of: 2026-05-08 close with fresh ETN / NVDA entry-band rerun outputs in `tmp/entry-band-data/`; broader note-layer reconciliation remains selective rather than full-rewrite.', '- Data as of: 2026-05-08 close for current execution/technical artifacts; exact levels live in the Technical Sheet.')
text = text.replace('- Next refresh due: after BRK.B is interpreted and its stale machine-layer May 2 next-date is cleared or manually held, after Eaton primary-source post-earnings follow-up lands, after JPM either reclaims the written band or receives an explicit band review, after BKNG either confirms the July 29 provider date through primary sources or repairs through the 174–177 zone, or when MSFT / GOOG / VRT / GS follow-on note sync changes a real action state', '- Next refresh due: when an execution-board name changes action state, owner approval state, or live blocker status')
# remove long non-owner watch-list residue bullets from data-quality note by replacing trailing bullet block subset
old = '- `AMD`, `AMZN`, `BKNG`, `CAT`, `CVX`, `LLY`, `LNG`, `PLTR`, and `RTX` remain machine-tracked watch-lane names, but they are **not** part of the execution board in this note. Their current validation or monitor-only state is ownership residue / review context, not a hidden promotion into deployable status.\n- Treat **NVDA** as the main still-unresolved timing-sensitive next-earnings mismatch affecting deployment trust today, with a forced re-check due by the first post-close chain on **2026-05-13** if cleaner confirmation still has not landed. **BRK.B** timing is now homepage-level confirmed for May 2, but the machine layer still needs a post-report next-date cleanup so Workflow 9 does not inherit stale catalyst framing. XOM is no longer a "write the first interpretation" case; it is now a post-print follow-through case. GOOG and MSFT are no longer pending earnings review; they are now post-print entry-discipline cases.\n- **Deployable now** means the gates line up on paper; it does **not** cancel residual date-confirmation caution, crowding risk, normal size discipline, or later price movement out of the written trigger zone.\n'
new = '- Watch-lane names remain outside this execution board unless explicitly promoted. Their technical or thesis state is review context, not hidden deployment authority.\n- **Deployable now** means the gates line up on paper; it does **not** cancel source-confidence caveats, crowding risk, normal size discipline, or later price movement out of the written trigger zone.\n'
text = text.replace(old, new)
p.write_text(text, encoding='utf-8')

# Technical bottom line stale validation count cleanup.
p = Path('03. Portfolio/Technical Entry and Invalidation Sheet.md')
text = p.read_text(encoding='utf-8')
text = text.replace('- **Confidence:** usable with caution — 1 active dashboard warning (LNG blocking band review) plus 16 monitor-only band-review items', '- **Confidence:** usable with caution — dashboard validation is clean on critical/warning count, but monitor-only band-review items and source-confidence caveats still require judgment')
p.write_text(text, encoding='utf-8')
