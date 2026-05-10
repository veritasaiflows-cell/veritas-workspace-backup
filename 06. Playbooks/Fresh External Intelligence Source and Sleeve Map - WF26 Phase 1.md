# Fresh External Intelligence Source and Sleeve Map - WF26 Phase 1

## Purpose

Define the smallest useful bounded source / sleeve map for Workflow 26 before any manual verification-object pilot or recurring cadence is considered.

This is a review-first design artifact.
It does **not** authorize canonical finance-note mutation, thesis rewrite, portfolio-posture change, or freeform source expansion.

## Phase 1 boundary

- stay downstream of the existing research-automation contracts
- stay tied to the current active finance surfaces instead of inventing a new universe
- allow fresh external intelligence to enter only as raw-event or packet candidates
- keep geopolitical and fast-moving items honest when truth is still unresolved
- block rumor-heavy, social, unattributed, or circular-source intake

## Pilot sleeve set

### 1. Active catalyst company lane
In scope now:
- **JPM**
- **NVDA**
- **ETN**
- **MSFT**
- **GOOG**

Why this lane exists:
- these names are already the live almost-deployable / catalyst-sensitive cluster across Watchlist, Portfolio Snapshot, and Weekly Positioning Review
- this lane keeps the pilot tied to real desk demand rather than broad research sprawl

### 2. Rates / credit / policy sleeve
In scope now:
- Fed policy path
- Treasury / curve context
- inflation-data and policy-release timing that could affect deployment confidence

Why this lane exists:
- it directly feeds the Macro Regime Dashboard and posture framing around JPM and overall selective-risk-on conditions

### 3. Energy / supply-shock sleeve
In scope now:
- oil / energy price shock context
- OPEC / EIA / official supply updates
- Hormuz or production-disruption verification objects when they matter to **XOM**, **CVX**, **LNG**, or the macro inflation view

Why this lane exists:
- the current macro and portfolio notes already treat energy pressure as a live regime variable and XOM as a benched but relevant follow-through case

### 4. Defense / geopolitical verification sleeve
In scope now:
- geopolitical escalation or procurement-policy developments that could matter to **LMT**, **RTX**, **KTOS**, or broader defense-risk framing
- high-sensitivity macro or geopolitical events that affect portfolio caution even when no immediate ticker action is allowed

Why this lane exists:
- defense and geopolitical risk matter to the note layer already, but they are exactly where rumor-driven drift is most dangerous

## Approved source map by lane

| Lane | Tier 1 primary sources | Tier 2 trusted corroboration | Tier 3 packet-only context | Blocked / stop-lined by default | Default downstream review surfaces |
|---|---|---|---|---|---|
| Active catalyst company lane | issuer IR releases, shareholder letters, decks, transcripts, SEC filings, issuer event calendars | Reuters, AP, Bloomberg / WSJ / FT when directly attributable to a primary event | calendar aggregators, transcript mirrors, market-data timing surfaces, yfinance-style calendar checks | social rumor, unattributed headlines, repost chains, AI summaries without source chain, anonymous blogs | thesis-review queue candidate, canonical freshness patch candidate, dashboard watch item |
| Rates / credit / policy sleeve | Federal Reserve / FRED, Treasury, BLS, BEA, official release calendars | Reuters, AP, Bloomberg / WSJ / FT with attributable policy or macro sourcing | futures/probability summaries, macro dashboards, secondary market-data recaps | unsourced Fed-cut chatter, social macro rumor, circular market-commentary chains | weekly intelligence, dashboard watch item, thesis-review queue candidate when high-materiality |
| Energy / supply-shock sleeve | EIA, IEA, OPEC communiques, company IR / filings when company-specific, official government energy or shipping statements when applicable | Reuters, AP, Bloomberg / FT / WSJ with attributable official or company sourcing | commodity dashboards, shipping or price summaries without direct owner-surface authority | tanker/social rumor feeds, unattributed shipping screenshots, anonymous outage claims, circular oil-headline chains | weekly intelligence, dashboard watch item, thesis-review queue candidate |
| Defense / geopolitical verification sleeve | DoD, White House, State Department, NATO, official ministry statements, company IR / filings when company-specific | Reuters, AP, Bloomberg / FT / WSJ with attributable official sourcing | think-tank or market commentary summaries used only as context, never as truth owner | social war maps, anonymous Telegram / X posts, unattributed escalation claims, repost loops | weekly intelligence, dashboard watch item, stop-line verification object unless confidence is strong |

## Cross-lane operating rules

1. **One outlet is not multiple confirmations.** Duplicate stories tracing back to the same wire, official, or repost chain count as one source path.
2. **Tier 3 never becomes silent canon.** Tier 3 may help detection or packet context, but it cannot clear a material truth claim by itself.
3. **Geopolitical speed does not overrule verification.** Fast-moving items may enter as verification objects, but they do not earn dashboard, thesis, or posture implications without source-quality support.
4. **Rumor-tier geopolitical and energy chatter stays verification-only.** If an energy / shipping / sanctions / escalation item is still rumor-tier or unattributed, it may not become even a dashboard-watch surface; it remains a stop-lined verification object until Tier 1 or Tier 2 attributable evidence exists.
5. **Current universe only.** This pilot does not authorize new tickers, new thematic sleeves, or broad source-widening beyond the lanes above.
6. **Owner surfaces stay manual.** Watchlist, Portfolio Snapshot, Macro Regime Dashboard, and Weekly Positioning Review remain human-reviewed outputs.

## Unresolved-truth handling rules

### Raw-event posture
- every fast-moving or sensitive item must enter the `Research Automation Raw Event Input Contract` with an explicit `verification_status`
- use `event_class = geopolitical_event` for geopolitical items and `unresolved_truth` posture when the truth chain is still open
- set `requires_primary_confirmation = true` whenever timing, policy, supply disruption, or posture relevance would be unsafe without better proof

### Stop-line posture
Stop-line the item instead of promoting it when any of these are true:
- primary evidence is missing for a timing-critical or material claim
- the event is rumor-heavy, unattributed, or sourced through repost chains
- contradiction notes remain unresolved
- the apparent corroboration chain is duplicate or circular
- the event would effectively smuggle in a thesis, deployment, or macro-regime judgment

### Honest-open posture
- unresolved items may remain open across review windows
- an unresolved geopolitical or supply-shock item is still useful if it is clearly labeled as unresolved and routed as a verification object rather than forced into false certainty
- `canonical_mutation_allowed` remains `false` in all Phase 1 and Phase 2 pilot outputs

## Downstream consumer map

| Lane | Review-first consumer surfaces | Ownership-safe handoff rule | Explicitly not allowed |
|---|---|---|---|
| Active catalyst company lane | research-department intake / thesis-review object, canonical freshness patch candidate, dashboard watch item | company developments must feed the research department first per `Research Department Downstream Handoff Contract.md`; only after desk review may they request portfolio / deployment review | direct Trigger Sheet state change, direct Portfolio Snapshot mutation, autonomous note rewrites |
| Rates / credit / policy sleeve | weekly intelligence input, dashboard watch item, Macro Regime Dashboard review candidate | macro developments may inform weekly intelligence or macro-dashboard review, but packet output alone may not rewrite regime canon or portfolio posture | direct macro-regime wording change from packet output alone |
| Energy / supply-shock sleeve | weekly intelligence input, held-open verification object, research-department intake / thesis-review object when attributable and materially company-relevant | portfolio surfaces only see a downstream handoff after reviewed evidence says XOM / LNG / energy follow-through deserves separate portfolio or deployment review | autonomous energy-sleeve posture change, automatic XOM requalification, rumor-tier dashboard visibility |
| Defense / geopolitical verification sleeve | weekly intelligence input, held-open verification object, research-department intake object when attributable and company-relevant | geopolitical developments may create desk review or weekly review objects, but portfolio/deployment surfaces stay downstream of explicit reviewed handoff only | direct posture escalation, direct ticker promotion, autonomous publication language changes |

## Acceptance language for Phase 1

Phase 1 is clean enough to accept only when all are true:
1. each live lane names approved Tier 1 and Tier 2 sources explicitly
2. blocked / stop-lined source classes are explicit
3. the pilot sleeve set stays bounded to current desk needs and current tracked names
4. unresolved-truth handling is explicit and contract-compatible
5. downstream consumers are explicit and manual-only

## Next operator step

- review this map against the current macro / portfolio / weekly surfaces and `Research Department Downstream Handoff Contract.md`
- if it stays low-noise and ownership-safe, mark Phase 1 complete and keep any later Phase 2 work limited to one real manual verification-object pilot
