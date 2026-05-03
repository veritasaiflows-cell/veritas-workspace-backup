# Coverage Universe

## Purpose

Define the default research universe. Every name here has a documented reason to exist. If a name has no thesis, it does not belong.

This file is the permanent foundation. The Watchlist tells you what is actionable now. This file tells you why every name is in the system at all.

---

## Ownership boundary

- This note owns thesis coverage and promotion logic. It does **not** own the live machine-tracked universe or deployment entitlement.
- The machine-tracked universe currently lives in `tmp/portfolio-config.json` and is surfaced operationally through [[02. Markets/Watchlist]], [[03. Portfolio/Deployment Trigger Sheet]], and [[03. Portfolio/Technical Entry and Invalidation Sheet]].
- Current machine lanes: **10 execution**, **8 watch** (`AMD`, `AMZN`, `CAT`, `CVX`, `LLY`, `LNG`, `PLTR`, `RTX`), **2 macro** (`TLT`, `SLV`), **2 speculative** (`SMCI`, `KTOS`).
- Workflow 11 closed the written-thesis residue on 2026-05-03 for `CAT`, `CVX`, `LLY`, and `SMCI`; they are now represented here explicitly instead of living only as machine-tracked operational entries. `GLD` remains research-only and is not in the current machine-tracked universe.

---

## Structure

Each entry uses four fields:

- **Tier** — Core candidate | Tactical | Speculative | Sector monitor
- **Status** — In portfolio draft | Active watch | Benched | Research needed
- **Thesis** — One-line investment argument
- **Key risk** — The single biggest thesis-breaker
- **Act when** — The condition that moves this from watch to action

## Tier definitions

- **Core candidate** — High-conviction, long-duration thesis. Eligible for 8–15% portfolio weight. Requires thesis, entry logic, and stop before initiating.
- **Tactical** — Event-driven or momentum setup with a defined catalyst and timeline. 4–7% weight. Explicit entry, target, and stop required.
- **Speculative** — Asymmetric, high-risk/high-reward. 1–3% weight maximum under normal rules. Binary outcomes acceptable if sized correctly, and anything above 3% requires explicit exception handling and review against `07. Risk/Risk Rules.md`.
- **Sector monitor** — Held for sector intelligence and macro read. Not currently actionable. No allocation until tier is explicitly upgraded.

---

## Written thesis coverage

*This section is the thesis layer. It is not a claim that every listed name is currently deployable or machine-tracked.*

---

## Energy

### XOM — ExxonMobil
- **Tier:** Core candidate
- **Status:** In portfolio draft — benched pending May 1 earnings requalification
- **Thesis:** Largest US integrated energy company with world-class cash generation, fortress balance sheet, and structural leverage to oil prices and geopolitical supply dynamics.
- **Key risk:** Sustained crude decline below $75/bbl erodes cash flow and buyback capacity; or demand destruction from accelerated energy transition.
- **Act when:** May 1 earnings requalification. Oil has recovered to Brent ~$99 / WTI ~$94 as of Apr 24 — the energy setup is improving. Entry band $142.50–$147.50 requires post-print evidence that the oil recovery is durable and XOM's guidance confirms it. Stop $139.50.

### LNG — Cheniere Energy
- **Tier:** Tactical
- **Status:** Active watch
- **Thesis:** Dominant US LNG export infrastructure operator with long-term take-or-pay contracts. Structural geopolitical beneficiary — Hormuz closure and Qatar LNG force majeure demonstrated the irreplaceable role of US LNG in global supply security.
- **Key risk:** Sustained LNG oversupply as new export capacity comes online globally; project execution delays.
- **Act when:** LNG complex stabilizes post-ceasefire. Confirm Cheniere had no contract disruptions during the Hormuz period. Entry requires a clean technical setup with defined levels. May 7 earnings window active.

### CVX — Chevron
- **Tier:** Tactical
- **Status:** Active watch
- **Thesis:** Integrated energy major with high-quality upstream assets, downstream balance, and strong capital-return posture. Useful secondary energy expression if the oil thesis strengthens beyond XOM or if portfolio construction later supports a second large-cap energy name.
- **Key risk:** Crude downcycle or weaker downstream margins could turn a secondary energy candidate into dead capital behind the stronger XOM setup.
- **Act when:** Only promote after XOM is requalified or deployed and sector allocation still has room for a second energy position. Define explicit entry band and stop before treating it as a real deployment candidate.

---

## Industrials and Infrastructure

### CAT — Caterpillar
- **Tier:** Tactical
- **Status:** Active watch
- **Thesis:** Global heavy-equipment leader with direct leverage to infrastructure, mining, energy, and industrial-capex cycles. Useful industrial cyclicals read-through when the regime supports real-economy capex rather than narrow AI-only concentration.
- **Key risk:** Cyclical demand can roll over quickly if global growth or commodity-linked capex weakens; without defined levels this remains a secondary industrial idea rather than a ready deployment candidate.
- **Act when:** Keep it watch-lane only until a fresh entry band and stop are defined and the post-print structure proves it deserves capital competition versus ETN and other stronger current setups.

---

## Defense and Aerospace

### LMT — Lockheed Martin
- **Tier:** Core candidate
- **Status:** Do not touch — repair mode. Setup invalidated April 23.
- **Thesis:** World's largest defense contractor with a $194B backlog, dominant F-35 franchise, THAAD and PAC-3 missile systems, and structural leverage to elevated global defense spending. Thesis intact at the sector level — RTX and NOC both beat and raised in the same reporting cycle, confirming defense demand is real. LMT's underperformance is company-specific, not a sector call.
- **Key risk:** F-35 TR-3/Block 4 software execution failure; defense budget top-line pressure; program delivery delays. Post-Apr-23 close at $509.68 — below all MAs including the 200-day. The earnings drop (~14%, ~$82) confirmed structural deterioration that was already visible before the print.
- **Act when:** A fresh base must form above $509.68 with at least 4–6 weeks of price stabilization. The old $590–$603 entry band is fully invalidated. New levels cannot be set until a new base is defined from post-report structure. Do not treat defense-sector strength as permission to re-enter LMT specifically until individual setup repairs.

### RTX — RTX Corporation
- **Tier:** Tactical
- **Status:** Active watch — beat-and-raised April 21
- **Thesis:** Defense and commercial aerospace hybrid with Pratt & Whitney jet engines and Raytheon missiles and sensors. Unique dual exposure to defense demand acceleration and commercial aviation recovery. Apr 21 beat-and-raise confirmed both thesis legs.
- **Key risk:** GTF engine inspection program costs remain a known drag; execution on defense program deliveries.
- **Act when:** Define entry band and stop before deploying. Setup still lacks decision-grade levels. Positive earnings read-through from April 21 improves conviction but does not substitute for levels.

### KTOS — Kratos Defense
- **Tier:** Speculative
- **Status:** Draft speculative sleeve candidate — explicit sizing review required
- **Thesis:** Asymmetric defense-tech play on unmanned systems, drones, and autonomous defense platforms. High optionality if the unmanned and autonomous warfare theme accelerates under sustained geopolitical pressure and AI-enabled defense modernization.
- **Key risk:** Execution risk is high; smaller company with lumpy contract wins; significant earnings volatility.
- **Act when:** Treat as a speculative sleeve candidate only. Monitor DoD autonomous systems budget signals and contract award announcements for thesis validation. Any sizing above 3% requires deliberate exception review.

---

## Technology and AI Infrastructure

### MSFT — Microsoft
- **Tier:** Core candidate
- **Status:** In portfolio draft — ⚠️ earnings alert active (April 29, after close)
- **Thesis:** Highest-quality AI-enabled technology platform with Azure cloud leadership, Copilot monetization across enterprise software, durable earnings power, and the strongest balance sheet in technology. The least fragile way to own the AI theme.
- **Key risk:** Azure growth deceleration or Copilot monetization disappointment; valuation still requires execution to justify at current prices.
- **Act when:** Post-earnings April 29. Azure growth above ~20% and Copilot revenue trajectory confirmed = accumulate on pullback to $393–$401 entry band. Stop $385.

### GOOG — Alphabet
- **Tier:** Core candidate
- **Status:** In portfolio draft — ⚠️ earnings alert active (April 29, after close)
- **Thesis:** Large-cap quality with dominant search, YouTube, and Google Cloud, plus AI optionality through Gemini and DeepMind. Better relative valuation than some mega-cap peers. Exceptional cash generation underwrites the thesis even if AI execution lags.
- **Key risk:** Search disruption from AI assistants; regulatory pressure; ad market cyclicality.
- **Act when:** Post-earnings April 29. Search revenue resilience and cloud growth confirmation = accumulate on pullback to $314–$321 entry band. Stop $305.50.

### NVDA — NVIDIA
- **Tier:** Core candidate
- **Status:** Active watch — do not chase current levels
- **Thesis:** Dominant AI infrastructure chip provider with Blackwell architecture, unmatched data center GPU revenue, and the clearest single-stock expression of AI capital expenditure as an investment theme.
- **Key risk:** Expectations are extremely high — any guidance miss creates violent downside. Crowding risk is real. Customer capex cycles can reverse faster than narrative suggests.
- **Act when:** Pullback to $186–$191 preferred entry band only. Never chase vertical moves. May 20 earnings window — timing-sensitive until confirmed. Stop $179.50.

### ETN — Eaton Corporation
- **Tier:** Core candidate
- **Status:** In portfolio draft — best current technical setup, earnings timing-sensitive (Apr 30–May 5 window)
- **Thesis:** Industrial quality company with dominant exposure to electrical infrastructure, grid modernization, data center power systems, and electrification. The cleanest way to express AI power demand without owning a pure concept stock. Fundamentals are real and durable.
- **Key risk:** Industrial capex cycle deceleration; data center power demand growth slows; multiple compression if industrial sentiment turns.
- **Act when:** Pullback to $388–$396 preferred entry band. Best MA posture in the portfolio — bullish 20>50>200 stack. Earnings timing-sensitive: confirm date before sizing. Stop $382.50.

### AMD — Advanced Micro Devices
- **Tier:** Tactical
- **Status:** Active watch — May 5 earnings
- **Thesis:** Credible AI chip challenger with MI300X GPU and EPYC server CPU. Material upside if NVDA supply constraints push hyperscalers to qualify AMD at scale. Significant earnings growth embedded in 2026 consensus estimates.
- **Key risk:** NVDA's execution and ecosystem advantage is substantial; AMD's AI GPU track record is still being established; highly timing-sensitive.
- **Act when:** May 5 earnings. Beat and strong MI300X demand guidance = upgrade to near-term tactical entry with defined levels.

### VRT — Vertiv Holdings
- **Tier:** Tactical
- **Status:** Active watch — beat-and-raised April 22, conviction upgraded, not yet deployable without levels
- **Thesis:** Data center power and thermal management infrastructure. Direct beneficiary of AI buildout capex with strong earnings growth. Apr 22 results beat and raised guidance, confirming that AI power and thermal demand is real and accelerating. Similar thematic exposure to ETN but smaller, higher-beta, and more volatile. The Apr 22 result is a positive read-through for ETN and the broader AI power infrastructure theme.
- **Key risk:** Crowded theme with elevated valuation; execution and supply chain risk; higher volatility than ETN; post-earnings extension risk if price outruns support.
- **Act when:** Define entry band and stop before considering deployment. Use the beat-and-raise as thesis confirmation — not as permission to chase. ETN first; VRT second. Entry only on a controlled, non-chasing setup with explicit levels.

### SMCI — Super Micro Computer
- **Tier:** Speculative
- **Status:** Active watch — speculative monitor only
- **Thesis:** High-beta AI infrastructure name with direct leverage to GPU-server demand and data-center buildout. It can work as a faster-moving speculative expression of AI hardware deployment if both governance overhang and price structure repair cleanly.
- **Key risk:** Accounting/governance overhang, extreme volatility, and crowding can overwhelm the thematic upside quickly. This is not a substitute for core AI-infrastructure exposure.
- **Act when:** Promote only if governance/restatement residue is resolved cleanly and a defined technical base forms with explicit entry and stop. Treat as Tier 3 max even if the thesis improves.

### PLTR — Palantir Technologies
- **Tier:** Tactical / Speculative
- **Status:** Active watch
- **Thesis:** AI and data analytics software with deep US government and defense roots. AIP (AI Platform) commercial expansion is the growth catalyst. Defense-AI convergence via government contracts is structurally durable.
- **Key risk:** Valuation is extreme relative to current revenue; commercial pivot must accelerate to justify the price; sentiment-driven volatility.
- **Act when:** Significant pullback or confirmed AIP commercial acceleration in earnings results.

---

## Healthcare

### LLY — Eli Lilly
- **Tier:** Sector monitor
- **Status:** Active watch — Workflow 7 pilot add, watch-lane only
- **Thesis:** Healthcare quality leader with durable diabetes cash flows, a powerful obesity / incretin franchise, and a pipeline that can justify keeping one healthcare name on the board as a defensive-growth diversifier versus the current tech-cyclical tilt.
- **Key risk:** Valuation can stay too rich for disciplined capital deployment, and reimbursement, supply, or competitive pressure could compress the risk/reward even if the business remains high quality.
- **Act when:** Keep it watch-lane only until valuation/setup justify real capital competition and explicit entry/stop levels are defined. If the healthcare sleeve remains one-name only, Lilly is the preferred first monitor unless evidence later makes JNJ or another defensive alternative cleaner.

---

## Financials

### JPM — JPMorgan Chase
- **Tier:** Core candidate
- **Status:** In portfolio draft — Q1 2026 reported April 14 (beat, NII guidance trimmed)
- **Thesis:** Highest-quality US financial institution with diversified revenue across retail banking, investment banking, trading, and asset management. Best-in-class ROTCE (23% Q1 2026). Macro-aligned but not macro-dependent.
- **Key risk:** NII compression as rates plateau or fall; credit deterioration in a hard landing; IB fee cycle reversal.
- **Act when:** Pullback to $300–$306 preferred entry band. Second-cleanest setup in the portfolio after ETN. Stop $295.50.

### GS — Goldman Sachs
- **Tier:** Tactical
- **Status:** Active watch
- **Thesis:** Capital markets-sensitive financial with best-in-class IB and trading franchise. Benefits from risk-on environments, M&A cycle activity, and equity issuance. Less interest-rate dependent than JPM in a rate-cutting scenario.
- **Key risk:** Capital markets revenue is highly cyclical; consumer business retreat cost and strategic pivot uncertainty remain recent history.
- **Act when:** Confirmed risk-on environment with improving deal and M&A activity. Secondary financial name after JPM is established. Define entry and stop before deploying.

---

## Large-Cap Platform Quality

### BRK.B — Berkshire Hathaway B
- **Tier:** Core candidate
- **Status:** In portfolio draft — benched on chart weakness
- **Thesis:** Diversified conglomerate with exceptional capital allocation track record, massive insurance float, and the optionality of Buffett deploying a historically large cash position at the right moment. Functions as a high-quality market proxy with embedded downside protection.
- **Key risk:** Succession risk post-Buffett; cash drag underperforms in a strong bull market; opportunity cost if no major deployment occurs.
- **Act when:** Market pullback into $465–$472 preferred entry band with MA structure repairing above the 481 level. Currently benched — price is in band but below all three MAs. Stop $459.50.

### AMZN — Amazon
- **Tier:** Tactical
- **Status:** Active watch — ⚠️ earnings alert active (April 29, after close)
- **Thesis:** AWS cloud platform plus improving retail operating leverage and advertising revenue growth. Broader platform quality than any single sector. AI infrastructure beneficiary via AWS. Potential upgrade to core candidate if April 29 earnings confirm the thesis.
- **Key risk:** AWS growth deceleration; retail margin pressure returning; high capital intensity ongoing.
- **Act when:** April 29 earnings. Strong AWS growth and operating leverage confirmation = upgrade to portfolio candidate and define entry band and stop before deploying.

---

## Macro and Alternatives

### GLD — SPDR Gold ETF
- **Tier:** Tactical
- **Status:** Active watch
- **Thesis:** Hard asset and macro hedge. Performs in geopolitical stress, dollar weakness, inflation persistence, or loss of confidence in monetary policy. Multiple of those conditions are at least partially present in the current regime.
- **Key risk:** Dollar strength; rising real yields; risk-on environments where gold underperforms equities.
- **Act when:** Geopolitical risk re-escalation or dollar weakness confirms a breakout above recent resistance. Define entry and stop before deploying.

### SLV — iShares Silver ETF
- **Tier:** Speculative
- **Status:** Draft speculative sleeve candidate — explicit sizing review required
- **Thesis:** Macro hedge with industrial metal overlay. Performs in inflation/stress environments like gold, plus benefits from electrification and solar panel demand. Higher beta than GLD with additional upside in a green infrastructure buildout.
- **Key risk:** Industrial demand slowdown; false breakouts; higher volatility than gold.
- **Act when:** Treat as a speculative sleeve candidate only. Monitor for breakout above key resistance or macro stress escalation that reinforces the hedge thesis. Any sizing above 3% requires deliberate exception review.

### TLT — iShares 20+ Year Treasury ETF
- **Tier:** Speculative
- **Status:** Benched
- **Thesis:** Tactical asymmetric duration play only if growth breaks decisively and the Fed pivots materially. Not a conviction long — a tail hedge instrument.
- **Key risk:** Wrong-way duration exposure if yields stay elevated or inflation re-accelerates. Painful in any hawkish surprise scenario.
- **Act when:** Labor market breaks sharply (unemployment trending toward 5%+) or growth data collapses in a way that forces a real Fed pivot. Not actionable in the current regime.

---

## Watch Pool

*Names held for sector intelligence or future elevation. No capital allocation until explicitly promoted to the Active Universe. Each entry has a single-line thesis and an elevation condition.*

| Ticker | Sector | Elevation Condition |
|---|---|---|
| NOC | Defense | Promote to tactical after LMT repair completes and a second defense core position is warranted |
| COP | Energy | Promote to tactical only if a purer E&P exposure is desired over an integrated major and oil thesis strengthens |
| EOG | Energy | Promote to tactical on confirmed oil structure improvement and desire for pure-play shale exposure |
| ET | Energy | Promote when income sleeve construction begins and midstream fundamentals support the yield |
| WMB | Energy | Promote when income sleeve construction begins |
| MPLX | Energy | Promote when income sleeve construction begins |
| GD | Defense | Promote to tactical if both defense and business jet cycles align simultaneously |
| LDOS | Defense | Promote to tactical if AI-defense convergence becomes a primary portfolio theme |
| BAH | Defense | Promote to tactical if government analytics spending accelerates materially |
| SAIC | Defense | No near-term catalyst identified — hold at monitor |
| EQIX | Tech / Infrastructure | Promote when a REIT or income component is added to the portfolio framework |
| ASML | Semiconductors | Promote on confirmed semiconductor capex upcycle with geopolitical export-restriction stability |
| AMAT | Semiconductors | Promote on confirmed semi capex upcycle |
| LRCX | Semiconductors | Promote on confirmed semi upcycle with reduced China regulatory risk |
| TIP | Macro | Promote if stagflation scenario materializes clearly in the data |
| HYG | Macro | Credit stress indicator only — not an investment candidate, track spread levels as a portfolio risk signal |
| SHY | Macro | Promote when cash reserve strategy is formalized |
| BTC | Macro | Promote only if Randall explicitly decides to add a crypto sleeve to the portfolio framework |

---

## Quick reference — written thesis layer

*Matches the written thesis blocks above, not the full 21-name machine-tracked universe.*

| Ticker | Sector | Tier | Status |
|---|---|---|---|
| XOM | Energy | Core candidate | Do not touch — interpreted; follow-through still required |
| LNG | Energy | Tactical | Active watch — May 7 earnings |
| CVX | Energy | Tactical | Active watch |
| CAT | Industrials | Tactical | Active watch |
| LMT | Defense | Core candidate | Do not touch — repair mode post Apr 23 |
| RTX | Defense | Tactical | Active watch — beat Apr 21, no levels yet |
| KTOS | Defense | Speculative | Draft speculative sleeve |
| MSFT | Technology | Core candidate | Almost deployable — post-earnings scorecard complete; still needs cleaner repair |
| GOOG | Technology | Core candidate | Almost deployable — post-earnings scorecard complete; still needs pullback into band |
| NVDA | Technology | Tactical | Deployable now — in band with crowding risk; disciplined tactical sizing only |
| ETN | Technology | Core candidate | Almost deployable — best current setup |
| AMD | Technology | Tactical | Active watch — earnings May 5 |
| VRT | Technology | Tactical | Watch / research needed — levels exist, conviction still secondary |
| SMCI | Technology | Speculative | Active watch — speculative monitor only |
| PLTR | Technology / Defense | Tactical / Speculative | Active watch |
| LLY | Healthcare | Sector monitor | Active watch — watch-lane only pilot |
| JPM | Financials | Core candidate | Deployable now |
| GS | Financials | Tactical | Deployable now — tactical secondary to JPM |
| BRK.B | Large-cap Quality | Core candidate | Portfolio draft — benched on chart |
| AMZN | Large-cap Quality | Tactical | Active watch — earnings Apr 29 |
| GLD | Macro | Tactical | Active watch |
| SLV | Macro | Speculative | Draft speculative sleeve |
| TLT | Macro | Speculative | Benched |

---

## Last updated

- 2026-04-19 — built out from ticker list by Claude
- 2026-04-22 — VRT risk framing upgraded after Apr 22 beat-and-raise
- 2026-04-24 — cleaned stale act-when language for LMT and timing-sensitive framing for ETN/NVDA
- 2026-04-26 — **Major revision:** pruned from 37 names to 19-name Active Universe + 20-name Watch Pool per vault efficiency audit. LMT status updated to repair mode / do not touch post-Apr-23 print. VRT status upgraded to reflect Apr-22 beat-and-raise conviction. NVDA promoted from Tactical to Core candidate tier. Act-when conditions refreshed across Energy and Defense sectors.
- 2026-05-02 — clarified ownership boundary between this thesis note and the 21-name machine-tracked universe; later same-day entitlement review demoted AMZN/RTX/CAT from execution to watch lane without changing thesis ownership here
- 2026-05-02 — Workflow 7 operator-approved a single Healthcare watch-lane pilot add: `LLY` entered the machine-tracked universe as a sector monitor without execution-lane promotion
- 2026-05-03 — Workflow 9B mirror-sync pass updated quick-reference deployment wording for GS/NVDA/JPM plus post-earnings wording for GOOG/MSFT/XOM/VRT so this table no longer contradicts the current trigger/technical surfaces
- 2026-05-03 — Workflow 11 closed the explicit written-thesis residue for `CAT`, `CVX`, `LLY`, and `SMCI` and used `LLY` as the bounded live intake pilot for the admission procedure
- Next review: after direct earnings-date confirmation and GOOG/MSFT post-earnings revalidation close the current E17 residue, or when durable thesis/key-risk/act-when conditions change materially
