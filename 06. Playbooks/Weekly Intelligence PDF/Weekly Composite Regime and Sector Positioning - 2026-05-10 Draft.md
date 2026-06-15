# Weekly Composite Regime and Sector Positioning - 2026-05-10 Draft

> QA note 2026-05-11: this Markdown draft is superseded by the regenerated First Format HTML/PDF for current pending-vs-approved promotion labels. Current sector board separation is pending promotion review: CAT, GS, LLY, NVDA; approved/promoted: ETN, JPM. Do not use older ETN/JPM pending-promotion wording in this draft as current state.

Status: **PDF-ready first draft / presentation layer only**  
Prepared for: Randall  
Prepared by: Veritas  
Local request window: 2026-05-10 evening MST  
Data refresh proof: `python scripts\run_finance_refresh_chain.py sunday`; `python scripts\validate_dashboard_state.py --write`  
Primary data as-of: market-state generated `2026-05-11T05:23:34Z`; sector board generated `2026-05-11T05:23:52Z`; dashboard validation generated `2026-05-11T05:23:53Z`

> **Authority boundary:** This document is a review memo, not an allocation instruction. Any sector tilt, sleeve change, ticker promotion/demotion, cash target, sizing change, execution entitlement, or portfolio mutation remains **owner-gated** and requires explicit Randall approval before application.

---

## Page 1 - Executive Verdict

### Bottom line

The current regime is **selective risk-on under a restrictive-policy pause**: growth remains resilient enough to keep risk appetite alive, credit and breadth are not flashing a stop line, but policy remains restrictive and the portfolio is already concentrated in Technology / AI-power exposure.

### Portfolio posture

Stay constructive, but do **not** chase. The right posture is **patient offense**: keep a short promotion-review queue, require entry discipline, and use underexposed sectors for research balance rather than forcing weak setups into the portfolio.

### What changed / what matters now

1. **Technology remains the only improving leadership sector**, but direct Technology exposure is already at the stated cap.
2. **Sector balance is thin**: Communication Services, Consumer Discretionary, Consumer Staples, Health Care, Materials, Real Estate, and Utilities are unrepresented or underexposed.
3. **The strict deployment surface shows zero clean deployable-now names**, with six names almost deployable and three do-not-touch names.
4. **ETN has a trust conflict**: the weekly brief artifact labels ETN deployable-now, while the stricter deployment-readiness surface downgrades it to almost-deployable because band-review debt remains active. Use the stricter surface for this PDF.
5. **No portfolio mutation is authorized** by this draft.

### Trust / validation panel

| Item                       | Current state                                        | Implication                                                                             |
| -------------------------- | ---------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Dashboard integrity        | Clean: 0 critical / 0 warning / 0 info issues        | The data package is usable for review.                                                  |
| Freshness classification   | `manual_dependency` / `review_required`              | Presentation-grade certainty is limited; portfolio config remains human-maintained.     |
| Presentation allowed flag  | `false` in strict validator terms                    | Treat this as an internal draft until visual/product QA and manual review are complete. |
| Canonical mutation allowed | `false`                                              | Do not write portfolio changes from this document.                                      |
| Capital action allowed     | `false`                                              | No trade, sizing, or allocation action is approved.                                     |
| Market-data caveat         | Mixed source dates; true pre-market tape unavailable | Use latest cash/futures context, not full live tape.                                    |

---

## Page 2 - Composite Macro Regime

### Regime read

| Signal | Current read | Portfolio meaning |
|---|---|---|
| Policy / Fed | Fed target range 3.50%-3.75%; next FOMC `2026-06-17`; next-meeting cut probability 0% from the current futures approximation | Restrictive pause remains the base case; do not assume an imminent policy tailwind. |
| Treasury curve | 2Y ~3.92%, 10Y ~4.364%, 2s10s about +44 bps | Curve is no longer signaling panic, but rates are still high enough to punish duration/speculation if growth cracks. |
| Credit | IG OAS ~0.79, HY OAS ~2.79; stress regime benign | Credit is not demanding broad defense yet. |
| Breadth | Broad/recovering breadth; 8 sectors above 50DMA | Participation is better than a narrow panic tape, but leadership is still selective. |
| Volatility | VIX ~17.19 | Volatility is controlled, not euphoric. |
| Dollar / commodities | DXY ~98.119; Brent ~105.40; WTI ~99.88 | Energy/inflation context remains material; do not ignore cost-pressure risk. |
| Futures / pre-market | Current yfinance responses did not provide true pre-market fields | Avoid pretending intraday/pre-market precision exists. |

### Deployment implication

The macro backdrop supports **reviewing quality add candidates**, not broad automatic deployment. The constructive case depends on credit staying benign, breadth staying broad enough, and rates not re-accelerating into a fresh valuation headwind.

---

## Page 3 - Sector Leadership and Underexposure

### Sector board answer

- **Leadership improving:** Technology.
- **Underexposed:** Communication Services, Consumer Discretionary, Consumer Staples, Health Care, Materials, Real Estate, Utilities.
- **Promotion-review candidates:** CAT, ETN, GS, JPM, LLY, NVDA.
- **Concentration warning:** Direct Technology is at cap at 25%; AI-power correlated sleeve is elevated at 32% including ETN.

### Sector table

| Sector | Current read | Portfolio exposure / gap | Review action |
|---|---|---|---|
| Technology | Improving leadership | 25% direct exposure; at cap | Do not chase more broad Technology. Review only the best entry-disciplined candidates. |
| Industrials | Deteriorating sector read, but with quality tracked names | 7% exposure; within limit | Keep CAT / ETN on promotion review; separate company quality from sector tape. |
| Financials | Deteriorating sector read, but tracked bank/brokerage candidates remain relevant | 21% exposure; near cap | Keep JPM / GS as disciplined review candidates; avoid doubling exposure without owner approval. |
| Health Care | Deteriorating sector read | 0% exposure; underexposed | LLY deserves promotion review, but no automatic promotion. |
| Consumer Discretionary | Deteriorating sector read | 0% exposure; underexposed | BKNG remains watch/repair context, not deployable. Continue research and entry repair work. |
| Communication Services | Deteriorating sector read | 0% exposure; underexposed | Research gap; do not force exposure without a quality candidate and technical setup. |
| Consumer Staples | Deteriorating sector read | 0% exposure; underexposed | Defensive research gap; useful if macro worsens. |
| Materials | Deteriorating sector read | 0% exposure; underexposed | Research gap; wait for leadership improvement or specific thesis. |
| Real Estate | Deteriorating sector read | 0% exposure; underexposed | Keep on watch; rate-sensitive and not a priority until rate pressure improves. |
| Utilities | Deteriorating sector read | 0% exposure; underexposed | Defensive/income research gap; not a chase candidate. |
| Energy | Deteriorating sector read | 10% exposure; within limit | XOM remains do-not-touch; wait for repair and energy-context confirmation. |

---

## Page 4 - Sector Tilt / Weight Proposal Layer

All items below are **`proposal_for_review`** only. They are not applied allocation state.

| Sector | Proposed tilt | Rationale | Owner-gated blocker |
|---|---|---|---|
| Technology | Hold / avoid broad overweight expansion | Leadership is improving, but exposure is already at the direct cap and AI-power correlation is elevated. | Any added exposure requires explicit owner approval and a name-specific entry/invalidation case. |
| Industrials | Selective positive review | CAT / ETN keep the sector relevant, but broad sector leadership is not improving. | ETN band-review debt and CAT promotion-review proof must be resolved before any applied change. |
| Financials | Neutral-to-selective review | JPM / GS are high-signal candidates, but the sector is near cap and sector read is deteriorating. | Any additional Financials exposure must pass concentration and tactical sizing review. |
| Health Care | Research-positive / candidate review | Underexposed sector with LLY as a named promotion-review candidate. | LLY requires current thesis, valuation, technical, and catalyst review before promotion. |
| Consumer Discretionary | Research-only | Underexposed, but BKNG remains repair/watch context. | Need repaired technical state and clean post-event/fundamental support. |
| Staples / Utilities | Defensive research queue | Both are underexposed and useful if the regime deteriorates. | No current leadership signal; require candidate screen before proposal. |
| Materials / Real Estate | Low-priority research watch | Underexposed but no leadership confirmation. | Rate/commodity sensitivity and weak leadership block promotion. |
| Energy | Hold / repair-only | Exposure exists; XOM is do-not-touch and energy tape is deteriorating. | Needs repair through technical levels and supportive energy context. |

### Practical implication

The document should **not** recommend a simple Technology overweight. The better action is to build a controlled review queue around Industrials, Financials, and Health Care while using Staples/Utilities as defensive research candidates if macro risk rises.

---

## Page 5 - Names That Matter

### Strict board state

| Bucket | Names | Meaning |
|---|---|---|
| Deployable now | None | No name clears the strict current deployment surface. |
| Almost deployable | ETN, GOOG, GS, JPM, MSFT, NVDA | Good candidates or owner-approved setups with unresolved entry, band, timing, or trust constraints. |
| Watch / research needed | VRT | Levels exist, but promotion is not approved. |
| Do not touch | BRK.B, LMT, XOM | Repair / below-stop / bench posture remains active. |

### Candidate notes

| Name | Sector / sleeve | Current state | Next review trigger |
|---|---|---|---|
| ETN | Industrials / AI-power adjacency | Almost deployable under strict surface; weekly artifact conflict exists | Resolve band-review debt; owner-approved Tier 2 add only inside 395.59-420.31 and no chase above band. |
| NVDA | Technology / AI core | Almost deployable; timing-sensitive with next earnings `2026-05-20` | Pullback into 186-191 only; do not chase above current levels. |
| JPM | Financials | Almost deployable; owner-approved setup but currently below live band | Reclaim or enter approved 306.82-318.12 band, or require explicit band review. |
| GS | Financials | Almost deployable; just above band top | Tactical only if it fits size discipline and JPM remains primary bank setup. |
| MSFT | Technology | Almost deployable; slightly above band top | Pullback into 389.64-412.56 or stronger support repair. |
| GOOG | Communication Services / mega-cap tech adjacency | Almost deployable; above band after post-print move | Pullback into 330.01-349.37 with structure holding; no chase. |
| CAT | Industrials | Promotion-review candidate from sector board | Needs current technical / thesis / catalyst confirmation before any lane change. |
| LLY | Health Care | Promotion-review candidate in underexposed sector | Needs updated valuation/thesis/entry review before promotion. |
| VRT | Industrials / AI-power infrastructure | Watch / research needed | Pullback into 295.49-326.63 with support holding; secondary to ETN unless setup improves. |
| BRK.B | Financials / quality compounder | Do not touch / repair | Only actionable on clear repair through 481 plus improving posture. |
| LMT | Industrials / defense | Do not touch / below stop | No trigger until after earnings and a fresh post-event base. |
| XOM | Energy | Do not touch / repair | Needs stabilization above 141.97 and 50DMA reclaim with supportive energy context. |

---

## Page 6 - Risks, Invalidation, and Next Actions

### What breaks the current read

- Credit spreads widen materially from benign levels.
- Breadth rolls over from broad/recovering into narrow deterioration.
- Rates re-accelerate and pressure long-duration growth / high-multiple names.
- Energy strength turns into a sustained inflation shock rather than a sector-specific opportunity.
- Technology leadership stays strong but concentration risk prevents clean additional exposure.
- Source freshness remains manual-dependent or conflicting when a capital decision is being considered.

### What would upgrade the posture

- Strict deployment surface shows at least one clean deployable-now name without trust conflicts.
- ETN/JPM/GS/NVDA band-review debt resolves with fresh technical confirmation.
- Underexposed sectors produce quality candidates with both thesis strength and clean entry logic.
- Validation moves from review-required/manual-dependency toward presentation-ready without hiding caveats.

### What would downgrade the posture

- VIX spikes with credit widening.
- Breadth participation falls while Technology remains the only support.
- More names fall into repair / below-stop states.
- Policy expectations shift more restrictive, or inflation/energy stress forces a risk-off posture.

### Next actions

1. **Visual product workflow:** open a dedicated workflow to turn this draft into a visually stable PDF product with a reusable layout, trust panel, sector table, and proposal-for-review labeling.
2. **Resolve ETN trust conflict:** reconcile weekly brief `deployable_now` language against the stricter deployment-readiness surface before any external/polished use.
3. **Run targeted promotion-review packets:** CAT, ETN, GS, JPM, LLY, NVDA, with LLY prioritized for underexposed Health Care balance and ETN/NVDA checked for concentration risk.
4. **Build defensive research queue:** Staples and Utilities candidates only if macro risk rises or leadership improves.
5. **Keep mutation boundary explicit:** no weights, sleeve changes, promotions, or cash targets applied from this draft.

---

## Source lineage

Canonical / note layer:
- `06. Playbooks/Composite Regime and Sector Positioning PDF Candidate.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `02. Markets/Macro Regime Dashboard.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `07. Risk/Risk Rules.md`

Structured artifact layer:
- `tmp/market-state.json`
- `tmp/sector-expansion-board.json`
- `tmp/sector-correlation-check.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/dashboard-validation.json`
- `tmp/weekly-intelligence-brief.json`
- `tmp/run-summary-sunday.json`

Validation proof:
- Sunday finance chain completed before draft creation.
- Dashboard validation wrote `tmp/dashboard-validation.json` with clean integrity counts but review-required/manual-dependency freshness posture.

## Draft disposition

This draft is ready for **internal PDF productization**, not final distribution. The next workflow should improve visual hierarchy, chart/table design, and export mechanics while preserving the trust limits and owner-gated authority boundaries.