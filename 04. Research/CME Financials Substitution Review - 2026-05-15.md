# CME Financials Substitution Review - 2026-05-15

## Scope and authority boundary

Review requested: whether **CME** should substitute for or sit beside **JPM / GS** inside the Financials allocation.

**Authority boundary:** review-only. This does not create sizing, sleeve, cash, portfolio-model, execution-entitlement, account, or trade authority. Any Financials weight change requires explicit owner approval plus the validator-backed gated apply path.

## Starting portfolio context

Current draft Financials exposure from [[03. Portfolio/Portfolio Snapshot]]:

| Name | Draft role | Draft weight | Current issue |
|---|---:|---:|---|
| JPM | Core Financials | 14% | Prior approval recorded, but trigger not live; below formal trigger band / authority conflict |
| GS | Tactical Financials | 7% | Almost deployable, but above band and secondary to JPM |
| CME | Watch / financial infrastructure | 0% | High-quality diversifier, but no allocation / no promotion authority |

- Current Financials draft weight: **21%**.
- Risk Rules max single sector: **25%**.
- Clean remaining room before cap: **~4%**.
- Therefore CME cannot be added at normal Tier 2 size without reducing JPM or GS, unless a deliberate sector-cap exception is approved. No exception is recommended here.

## Business / regime comparison

| Factor | JPM | GS | CME |
|---|---|---|---|
| Primary exposure | Large bank / credit / deposits / diversified financial services | Capital markets / advisory / trading / asset management | Exchange, clearing, rates/volatility/hedging infrastructure |
| Credit-cycle risk | Highest of the three | Moderate | Low direct credit risk |
| Rate/volatility benefit | Mixed; curve/credit quality matter | Benefits from capital markets activity | Directly benefits from rates, volatility, hedging volume |
| Balance-sheet risk | Bank balance sheet dominates stress case | Financial balance sheet + market activity | Cleaner, low leverage in prior packet |
| Current technical state | Trigger not live / authority conflict | Almost deployable / above band | Watch-only defined setup / near upper band |
| Portfolio role quality | Core if trigger repairs | Tactical secondary | Diversifier, not bank substitute for credit exposure |

## Substitution scenarios

### Scenario A — Keep JPM 14%, GS 7%, CME 0%

**Verdict:** default / current state.

Pros:
- Avoids unnecessary churn.
- Keeps prior JPM core thesis intact while trigger conflict resolves.
- Avoids forcing CME into a nearly full sector sleeve.

Cons:
- Leaves no financial-infrastructure diversification.
- GS remains a second cyclical Financials exposure while JPM trigger is not live.

Use if: JPM repairs, GS remains the preferred tactical add, and Financials sector room stays tight.

### Scenario B — Replace GS with CME as the secondary Financials candidate

**Verdict:** best substitution path if Randall wants CME exposure.

Illustrative draft structure:
- JPM: **14%** core placeholder, only if trigger conflict resolves.
- CME: **4%–7%** Tier 2 financial-infrastructure candidate.
- GS: bench / remove tactical draft weight or keep watch-only.

Pros:
- CME diversifies away from bank credit/capital-markets cyclicality.
- Cleaner balance-sheet profile than GS.
- Better fit if the regime remains restrictive with active rates/volatility/hedging demand.

Cons:
- CME valuation is not cheap.
- CME is still Financials-sector exposure and consumes cap room.
- Loses GS upside if capital-markets cycle accelerates.

Use if: the goal is cleaner Financials quality and less credit/advisory cyclicality, not maximum cyclical upside.

### Scenario C — Reduce JPM and add CME

**Verdict:** premature.

Pros:
- Reduces single-name bank concentration.
- Frees cap room for a different Financials type.

Cons:
- JPM was chosen as core Financials for quality and macro fit; reducing it before the trigger conflict is fully adjudicated is not cleaner than waiting.
- CME does not replace JPM's bank/credit/large-financial role; it complements it.

Use if: JPM thesis weakens, credit/curve context deteriorates, or trigger conflict fails into repair.

### Scenario D — Add CME on top of JPM + GS

**Verdict:** not recommended.

Reason: Financials are already **21%**; adding even a modest 4% CME sleeve takes the sector to the **25% cap**, leaving no error margin. Adding more than 4% breaches the cap without an explicit exception.

## Technical and trigger-state overlay

- **JPM:** approval recorded but trigger not live; must reclaim formal trigger band or pass explicit band review.
- **GS:** technically constructive but above preferred band; secondary to JPM unless promoted/sized.
- **CME:** defined watch-lane setup at **287.74–298.86**, stop **276.68**; near upper edge / no chase above 300 without review.

## Recommendation

**Do not add CME on top of JPM + GS.** If CME is promoted later, the cleanest path is to make it a **GS substitute**, not a third Financials allocation.

Recommended queue state:
1. Keep **JPM** as core Financials placeholder, but fail-closed until trigger conflict resolves.
2. Keep **CME** warm as the preferred Financials diversifier candidate.
3. Keep **GS** tactical / secondary; if CME becomes active, GS should be reduced or benched first.
4. Do not breach the 25% Financials cap.

## Next gate

Before any model proposal:
- refresh CME rate/volatility volume evidence;
- confirm CME valuation is still acceptable;
- decide whether CME replaces GS in the draft model;
- obtain explicit owner approval for any weight/sleeve change.

No trade, no owner approval inferred, no portfolio-model mutation.
