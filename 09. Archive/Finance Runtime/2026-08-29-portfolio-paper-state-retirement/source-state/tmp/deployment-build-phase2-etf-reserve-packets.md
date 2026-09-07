# Deployment Build Phase 2 — ETF / Reserve Promotion Packets

- Generated: 2026-05-17 22:18 MST subagent lane
- Status: review-only promotion packet draft
- Authority: no live trade, paper trade, account action, brokerage instruction, canonical portfolio/model apply, or owner-approval inference
- Source basis: `07. Risk/Risk Rules.md`, `tmp/quality-bench-international-etf-lane.md`, `tmp/quality-bench-bond-cash-lane.md`, `tmp/quality-diversification-integrated-review-2026-05-17.md`, `tmp/market-state.json`, `tmp/macro-regime.json`
- External data: no web used in this pass. **Issuer sponsor-check required** before any gated apply or deployability claim.

## Regime and portfolio context

Current artifacts classify the regime as **restrictive pause / resilient growth / selective risk-on / large-cap quality bias**, with policy hold dominant, benign credit, broad but deteriorating/recovering breadth, VIX 18.43, 10Y ~4.595%, 2Y ~3.82%, 3M T-bill ~3.588%, HY OAS 2.76%, IG OAS 0.76%, Brent/WTI elevated, and futures soft. This supports deliberate diversification and cash-like ballast, but not yield chasing or automatic deployment.

Integrated planning model remains review-only:

| Layer | Account-level planning target | Practical rule |
|---|---:|---|
| Stock quality sleeve | 54% | Broaden quality bench; avoid all-Tech top-three concentration. |
| Equity ETF sleeve | 36% | Use ETFs for geography/sector gaps after holdings look-through. |
| Reserve / bonds / cash-like sleeve | 10% | Cash-first ballast; high yield is not reserve cash. |

## Required validation before any apply or deployment claim

1. **Issuer sponsor-check required:** current issuer pages for expense ratio, AUM/liquidity, index, duration/yield where applicable, holdings/country/sector weights, distribution/tax notes, securities lending, and fund structure.
2. **ETF look-through validator:** top holdings, sector, country, duration/credit quality where applicable, and overlap with proposed stock sleeve and ETF sleeve.
3. **Portfolio pro-forma validator:** risk caps, sector caps, single-name exposure, correlated AI-power/Tech/credit/duration/currency sleeves, and preserved 10% cash/reserve treatment.
4. **Technical / entry discipline:** no chase; define buy zone, invalidation, review cadence, and event-risk window.
5. **Gated apply path:** WF64/WF56-style exact proposal, patch preview, authority artifact, validators, backup/rollback, post-apply proof, and audit trail.

---

## Packet 1 — VXUS / IXUS

| Field | Packet |
|---|---|
| Role | **Primary international equity core / ex-U.S. geography diversifier.** VXUS preferred; IXUS acceptable equivalent backup after issuer validation. |
| Why | The draft portfolio is U.S.-centric and heavily exposed to U.S. large-cap quality, Tech/AI infrastructure, Financials, Energy, Industrials, Defense, and Materials. A broad total ex-U.S. ETF adds developed + emerging exposure in one operationally simple sleeve. |
| Main risk | Currency drag, EM/China/Taiwan/geopolitical risk, lower ROE/shareholder-return culture versus U.S. quality, and hidden overlap in global semis/financials/energy/industrials/materials. |
| Validation required | Issuer sponsor-check; expense/AUM/liquidity/index refresh; country/sector/top-holding look-through; China/Taiwan/Korea and semiconductor/financials weights; overlap with VTI, sector ETFs, ETN/MSFT/GOOG/NVDA/JPM/GS/XOM; technical band and no-chase check. |
| Target concept | Integrated review suggests **VXUS 7% account-level** inside the 36% equity ETF sleeve. Earlier lane framed **5%–8% of risk assets** / roughly **4.5%–7.2% account-level** if 10% reserve is preserved. |
| Deployability verdict | **Promote to validation queue, not deployable yet.** Best default international candidate, but requires issuer/holdings/technical/pro-forma validation and owner-gated decision. |

## Packet 2 — VEA / IEFA fallback

| Field | Packet |
|---|---|
| Role | **Conservative developed ex-U.S. fallback** if Randall deliberately wants to avoid EM/China exposure at launch. VEA preferred; IEFA acceptable backup after issuer validation. |
| Why | Provides non-U.S. developed-market exposure with less state-policy/EM risk than total ex-U.S. ETFs. Cleaner first-stage international sleeve if geopolitical or China/Taiwan risk budget is intentionally low. |
| Main risk | Leaves EM/demographic growth absent; still carries currency, Europe/Japan concentration, rate/geopolitical risk, and potentially lower growth/profitability than U.S. large-cap quality. |
| Validation required | Issuer sponsor-check; expense/AUM/liquidity/index refresh; country/sector/top holdings; Europe/Japan concentration; overlap with ETF/stock sleeve; explicit confirmation that EM is intentionally excluded or deferred; technical band. |
| Target concept | **Replacement for VXUS/IXUS international allocation**, not additive by default. Use the same approximate **5%–8% risk-asset / ~7% account-level** planning slot only if VXUS is rejected for EM risk. |
| Deployability verdict | **Fallback promote-to-validation only.** Cleaner risk profile than VXUS/IXUS on EM exposure, but incomplete geography diversification and still not deployable without checks. |

---

## Packet 3 — SGOV

| Field | Packet |
|---|---|
| Role | **T-bill / cash-like reserve core.** Primary vehicle for the preserved reserve sleeve; BIL/SHV remain backups. |
| Why | Reserve purpose is optionality and low-volatility dry powder. With Fed target 3.50%–3.75%, hold probability 100%, and 3M T-bill near 3.588%, cash-like Treasury exposure still earns enough to justify patience while risk-asset setups validate. |
| Main risk | Reinvestment risk if rates fall; not a growth asset; small yield/price/friction/tax differences can matter; fund mechanics must be confirmed. |
| Validation required | Issuer sponsor-check; current SEC yield/distribution/yield-to-maturity/expense; T-bill maturity profile; liquidity/spread; tax/account treatment; verify it is classified as reserve/cash-like and not risk-asset exposure. |
| Target concept | **6% account-level**, equal to **60% of the 10% reserve**. |
| Deployability verdict | **Best reserve-core candidate, validation required.** Review-ready for issuer/yield/tax/liquidity check; no account action authority. |

## Packet 4 — SHY

| Field | Packet |
|---|---|
| Role | **Short-duration Treasury ballast** within reserve sleeve. |
| Why | Modest step-out from T-bills to add limited duration exposure without converting reserve into a rate bet. Fits restrictive-pause regime better than aggressive intermediate/long duration. |
| Main risk | Duration mark-to-market loss if yields rise; less cash-like than SGOV; may underperform cash if curve/pricing moves unfavorably. |
| Validation required | Issuer sponsor-check; duration, yield, maturity distribution, expense/liquidity; current price vs moving averages/support; stress check for rate backup; confirm reserve classification remains limited-duration ballast. |
| Target concept | **2% account-level**, equal to **20% of the 10% reserve**. |
| Deployability verdict | **Useful small ballast, not deployable until validated.** Keep subordinate to SGOV. |

## Packet 5 — BND

| Field | Packet |
|---|---|
| Role | **Intermediate / aggregate bond diversifier** for small recession/risk-off convexity. |
| Why | Adds broader rate/credit ballast potential if growth rolls over, while keeping size small because current credit is benign and rate risk remains meaningful with 10Y near 4.595%. |
| Main risk | Duration drawdown if yields rise; aggregate-bond credit exposure is not pure cash; can correlate poorly during inflation/rate shocks. |
| Validation required | Issuer sponsor-check; effective duration, SEC yield, credit-quality mix, Treasury/MBS/corporate split, expense/liquidity; rate-shock scenario; overlap with SHY/SCHP reserve sleeve. |
| Target concept | **1% account-level**, equal to **10% of the 10% reserve**. AGG/IEI/IEF alternatives remain possible after validation. |
| Deployability verdict | **Small diversifier only.** Promote to validation; do not increase without explicit recession/rate-cut thesis. |

## Packet 6 — SCHP

| Field | Packet |
|---|---|
| Role | **TIPS / inflation hedge** inside reserve sleeve. |
| Why | Elevated Brent/WTI and inflation sensitivity justify a small inflation-protection sleeve, but not a dominant allocation absent a stronger inflation-shock thesis. |
| Main risk | Real-rate duration risk; can lose value if real yields rise; inflation hedge may lag if inflation concern fades or nominal cash yields stay attractive. |
| Validation required | Issuer sponsor-check; duration, real yield, index, expense/liquidity, distribution/tax treatment; scenario check vs SGOV/SHY/BND; technical/entry band. |
| Target concept | **1% account-level**, equal to **10% of the 10% reserve**. TIP is an alternative after validation. |
| Deployability verdict | **Small inflation hedge only.** Promote to validation; no larger allocation without explicit inflation thesis. |

## Packet 7 — HYG / JNK

| Field | Packet |
|---|---|
| Role | **High-yield credit watch-only / separate risk sleeve candidate. Not cash, not reserve ballast.** |
| Why | HY yields may look attractive and spreads are benign/tightening, but HY OAS at 2.76% means compensation for credit risk is not compelling enough to treat as dry powder. If used later, it belongs in risk assets, not the reserve. |
| Main risk | Credit beta, equity-like drawdowns in stress, liquidity/spread widening, downgrade/default cycle, false safety from yield. Current benign credit can reverse quickly. |
| Validation required | Issuer sponsor-check; yield, duration, spread, credit-quality/default exposure, sector concentration, liquidity/spread, drawdown history; explicit separate risk-sleeve classification; no reserve labeling. |
| Target concept | **0% reserve allocation. Watch-only.** If later considered, require separate risk-budget and owner approval, likely outside the 10% reserve. |
| Deployability verdict | **Do not promote to reserve. Watch-only.** High yield is not a cash substitute and should not receive reserve capital in this model. |

---

## Promotion queue recommendation

| Priority | Candidate | Queue action | Reason |
|---:|---|---|---|
| 1 | SGOV | Issuer/yield/liquidity validation | Anchor for preserved reserve; lowest-drama ballast. |
| 2 | VXUS / IXUS | Issuer/holdings/country/overlap validation | Fills most important ETF geography gap. |
| 3 | SHY | Duration/yield validation | Modest reserve step-out. |
| 4 | BND + SCHP | Duration/inflation sleeve validation | Keep small and scenario-specific. |
| 5 | VEA / IEFA | Fallback validation only if EM risk rejected | Conservative international alternative. |
| 6 | HYG / JNK | Watch-only monitor | Do not classify as reserve. |

## Bottom line

- **International core:** VXUS preferred, IXUS backup; VEA/IEFA only if EM/China exposure is intentionally deferred.
- **Reserve sleeve:** SGOV 6%, SHY 2%, BND 1%, SCHP 1% account-level as review-only target concepts.
- **High yield:** HYG/JNK remain 0% reserve and watch-only.

Nothing here is deployable or canonical until issuer sponsor-checks, ETF look-through, technical bands, pro-forma risk validators, and owner-gated approval paths are complete.
