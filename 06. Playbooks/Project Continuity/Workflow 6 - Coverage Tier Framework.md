# Workflow 6 - Coverage Tier Framework

## Objective
- Define the operational coverage-tier model for the current 21-name machine-tracked universe.
- Keep operational coverage tiers distinct from thesis tiers so refresh entitlement, deployment surfaces, and ownership boundaries stay explicit.
- Finish the framework before any sector-expansion work opens.

## Current State
- Workflow 6 opened immediately after Workflow 5 closed with follow-up on 2026-05-02.
- Workflow 6 is now **closed with follow-up** after final QC confirmed the coverage-tier contract is landed honestly enough to hand off to Workflow 7.
- The machine-tracked universe is now segmented into **10 execution / 7 watch / 2 macro / 2 speculative** after the bounded daily-entitlement review.
- The framework draft, bounded normalization pass, validator/contract hardening pass, and final closure QC are complete.
- Final live validation still reads `0 critical / 5 warning`, but the remaining warnings are now explicit residue rather than framework blockers:
  - `band_staleness` remains real for `GOOG`, `LMT`, `AMZN`, `VRT`, `RTX`, `CAT`, and `AMD`.
  - `GS` still keeps the only live `state_vs_entry_band_conflict`, which remains acceptable because it is still an execution-entitled name.
  - `timing_sensitive_earnings_dates` remains warning-grade after a small safe stale-date fix (`BRK.B`), because the remaining `DATE CHANGED` alerts are either true unresolved manual timing dependencies (`NVDA`) or provider-vs-note-layer mismatches that should not be auto-greened without policy-level behavior changes or direct confirmation.
  - `macro_manual_dependency` and `policy_expectations_manual_dependency` remain accepted manual-trust dependencies outside Workflow 6 scope.

## Last Meaningful Progress
- Completed the first bounded inventory across `Coverage Universe`, `Watchlist`, `Deployment Trigger Sheet`, `Technical Entry and Invalidation Sheet`, `tmp/workbook-watchlist-board.csv`, `tmp/trigger-sheet.json`, `tmp/dashboard-validation.json`, and `tmp/portfolio-config.json`.
- Confirmed the current machine split is operationally coherent enough to draft from: **13 daily execution-entitled / 4 event-watch / 2 macro / 2 speculative**.
- Drafted the first compact operator-facing framework below instead of widening into thesis rewrites or new-sector work.
- Completed Workflow 6 pass 2: normalized explicit machine fields for `AMD`, `LNG`, `TLT`, and `SMCI` in `tmp/portfolio-config.json`, and fixed the `CVX` omission in `02. Markets/Watchlist.md` so the 21-name mirror is honest again.
- Completed Workflow 6 pass 3: hardened `band_refresh.py` and `dashboard_validation.py` so non-band-drift-entitled macro/speculative names (`KTOS`, `SLV`, `TLT`, `SMCI`) no longer count as live band-review debt, watch-lane names no longer raise false deployment-flow or in-band/WATCH conflicts, and real execution-lane drift warnings remain visible.
- Completed Workflow 6 pass 4: reviewed `AMZN`, `VRT`, `RTX`, `CAT`, and `GS` for real daily-execution entitlement; demoted `AMZN`, `RTX`, and `CAT` to event-watch, while keeping `VRT` and `GS` on the execution board because they still compete honestly for 30–90 day capital attention.
- Completed Workflow 6 pass 5: ran final QC with `python scripts/earnings_calendar_enrichment.py`, `python scripts/universe_consistency_check.py`, and `python scripts/validate_dashboard_state.py --write`; updated the stale `BRK.B` watchlist date in `scripts/earnings_calendar_enrichment.py`; confirmed the dashboard warning stack is now the expected 5-code residue (`band_staleness`, `state_vs_entry_band_conflict`, `timing_sensitive_earnings_dates`, `macro_manual_dependency`, `policy_expectations_manual_dependency`).

## Inventory — current tracked universe

### Daily execution-entitled (10)
- `JPM`, `ETN`, `NVDA`, `GOOG`, `MSFT`, `BRK.B`, `XOM`, `LMT`, `VRT`, `GS`
- These names already own daily technical/deployment upkeep even when their current action state is bench, blocked, or repair.

### Event-driven watch (7)
- `CVX`, `AMD`, `LNG`, `PLTR`, `AMZN`, `RTX`, `CAT`
- These names are tracked for catalyst timing, sector read-through, and possible later promotion, but they do **not** currently earn daily execution-board treatment.

### Macro context (2)
- `SLV`, `TLT`
- These are macro/hedge expressions, not normal equity deployment-board names.

### Speculative monitor (2)
- `KTOS`, `SMCI`
- These are intentional asymmetric monitors, not default daily technical-maintenance names.

## Proposed operational tier set

### 1. Daily Execution Coverage
- **Meaning:** earns weekday technical upkeep and appears on deployment surfaces.
- **Owns:** `Deployment Trigger Sheet`, execution-ranked sections of the technical sheet, deployment checks, workbook technical-entitled surfaces.
- **Does not mean:** deployable now. A name can be daily-covered and still be blocked, benched, or in repair.
- **Refresh expectation:** weekday technical refresh plus event-driven state changes after earnings, invalidations, or major regime breaks.
- **Admission standard:** written thesis or active scorecard ownership, defined technical policy (band/stop or explicit repair framing), realistic 30–90 day deployment relevance, and explicit operator intent to compare it against live capital alternatives.
- **Demotion standard:** no realistic near/intermediate deployment role, duplicate-proxy status, or daily upkeep generates more noise than decision value for at least one real review cycle.

### 2. Event-Driven Watch Coverage
- **Meaning:** tracked for earnings, catalysts, and sector read-through, but excluded from the daily execution board.
- **Owns:** `Watchlist`, targeted technical-note sections when parity matters, calendar/earnings monitoring.
- **Refresh expectation:** at earnings, major catalysts, material sector moves, or explicit parity/cleanup passes.
- **Admission standard:** clear reason to exist and possible future promotion path, but daily upkeep is not yet justified.
- **Promotion standard:** explicit operator decision that the name now deserves daily execution comparison, plus technical entitlement and a real deployment path.

### 3. Macro Context Coverage
- **Meaning:** tracked as a macro, hedge, or regime-expression instrument rather than as a normal single-name deployment candidate.
- **Owns:** macro notes, watchlist summary visibility, and any workbook/dashboard summary surfaces that discuss regime posture.
- **Refresh expectation:** macro pass, regime change, or thesis-specific move.
- **Admission standard:** the instrument's job is to express or monitor regime risk, not to compete for standard equity-board slots.
- **Promotion standard:** explicit decision that the instrument should graduate into a more active deployment lane rather than remain a macro expression.

### 4. Speculative Monitor Coverage
- **Meaning:** intentional visibility for asymmetric names without granting default daily execution entitlement.
- **Owns:** thesis/watchlist summary visibility and targeted review around catalysts or sleeve decisions.
- **Refresh expectation:** earnings, contract/catalyst changes, thesis impairment, or deliberate speculative-sleeve review.
- **Admission standard:** explicit asymmetric thesis plus Tier 3 sizing posture under `07. Risk/Risk Rules.md`.
- **Promotion standard:** explicit sleeve decision, clearer technical entitlement, and evidence that recurring upkeep would improve real capital decisions rather than just satisfy curiosity.

## Boundary with thesis tiers
- Thesis tiers in `04. Research/Coverage Universe.md` answer **what the idea is** (`Core candidate`, `Tactical`, `Speculative`, `Sector monitor`).
- Operational coverage tiers answer **how the machine and note layer should maintain the name**.
- Do not collapse those axes:
  - a core thesis can still sit in **Daily Execution Coverage** or later be demoted if daily upkeep stops being worth it;
  - a speculative thesis can sit in **Speculative Monitor Coverage** or **Event-Driven Watch Coverage** without earning daily board treatment.

## First working mapping of the current universe

| Operational tier | Current names | Draft verdict |
|---|---|---|
| Daily Execution Coverage | `JPM`, `ETN`, `NVDA`, `GOOG`, `MSFT`, `BRK.B`, `XOM`, `LMT`, `VRT`, `GS` | Pass 4 right-sized the lane: keep the names that still have real 30–90 day capital relevance or live comparison value. |
| Event-Driven Watch Coverage | `CVX`, `AMD`, `LNG`, `PLTR`, `AMZN`, `RTX`, `CAT` | Watch lane now carries the secondary or underdefined names whose daily upkeep was not honestly changing capital decisions. |
| Macro Context Coverage | `SLV`, `TLT` | Clean match to the live 2-name macro lane. |
| Speculative Monitor Coverage | `KTOS`, `SMCI` | Clean match to the live 2-name speculative lane. |

## Admission / promotion / demotion / removal rules
- **Admission into the tracked universe at all:** thesis owner, reason to exist, named operational tier, and one canonical source note.
- **Event → Daily:** only when the name becomes a real candidate for the next deployment board or an important primary sleeve proxy that benefits from weekday upkeep.
- **Daily → Event:** when the name is mainly a read-through/secondary proxy, or repeated daily maintenance no longer improves capital decisions.
- **Speculative → Daily or Event:** only after explicit speculative-sleeve review and an intentional decision that the name deserves recurring upkeep.
- **Any tier → Macro:** only when the instrument's role is primarily hedge/regime expression rather than company deployment.
- **Removal from the tracked universe:** thesis no longer exists, duplicate proxy is no longer useful, or no honest promotion/use condition remains.

## Ambiguities / control-plane residue still open
- `PLTR` remains a thesis-hybrid (`Tactical / Speculative`) but operationally belongs in **Event-Driven Watch** unless and until an explicit speculative-sleeve or daily-execution promotion decision is made.
- `CAT`, `CVX`, and `SMCI` still have written-thesis residue in `Coverage Universe`; this framework identifies the operating lane but does **not** pretend the thesis-writeup debt is solved.
- Pass 4 closed the weaker-lane review with the smallest honest move: `AMZN`, `RTX`, and `CAT` no longer own execution-board cost; `VRT` and `GS` still do.
- The next control-plane pass should harden validators/contracts so event-watch, macro, and speculative names no longer leak into execution-flow warnings merely because downstream consumers still assume daily entitlement.

## Next Action
- Open `Workflow 7 - Sector Coverage Expansion Plan` as the next approved handoff, carrying forward the real warning residue without pretending Workflow 6 cleaned unrelated band, timing, or manual macro/policy debt.

## Key Files
- `04. Research/Coverage Universe.md` - thesis ownership boundary.
- `02. Markets/Watchlist.md` - active tracking-universe mirror.
- `03. Portfolio/Deployment Trigger Sheet.md` - execution-board ownership boundary.
- `03. Portfolio/Technical Entry and Invalidation Sheet.md` - daily technical-entitlement surface.
- `tmp/workbook-watchlist-board.csv` - live 21-name export showing the practical lane split and missing tier-field residue.
- `tmp/portfolio-config.json` - current control-plane semantics and tracked-universe field reality.
- `tmp/dashboard-validation.json` - warning evidence proving why lane/tier entitlement must stay explicit.

## Automation / Refresh Path
- Keep this framework upstream of Workflow 7 sector expansion.
- Treat tier changes as control-plane decisions, not incidental note edits.
- Validator/contract hardening is complete against the explicit lane fields; any later work should treat the remaining warning stack as separate upkeep/trust residue, not as evidence that the coverage-tier framework itself is still open.
