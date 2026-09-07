# Retired Historical — WF27 Forecast Question Set - Phase 1

Lifecycle: Retired on 2026-08-29. The content below is dated methodology history and is not an active finance-state model, route, or authority surface.

Date: 2026-05-06  
Owner: Veritas  
Status: draft methodology artifact for Workflow 27 Phase 1 only

## Purpose
- Define the first bounded forecast questions that could honestly support this finance OS later.
- Keep the work decision-relevant, provenance-aware, and conservative.
- Explicitly block model theater, production modeling, and any direct portfolio authority at this stage.

## Phase boundary
This artifact covers **question and target selection only**.
It does **not** approve modeling, backtests, feature engineering, automation, or canon mutation.
Phase 2 must still audit the minimum honest data and provenance requirements before any baseline-method draft is allowed.

## Selection rules used
- Questions must map to current desk decisions already visible in the macro, portfolio, weekly-positioning, and risk-rule surfaces.
- Questions must be answerable with bounded, auditable targets rather than vague market-prediction language.
- Questions must improve sequencing, risk posture, or review prioritization rather than pretending to replace judgment.
- Questions must tolerate simple baselines first; if a naive baseline would already be strong, that should be measured before any ML widening.

## Forecast question set

### 1. Near-term regime stability question
- **Question:** Over the next 20 trading days, does the current macro posture remain in the same operating bucket (`restrictive pause / resilient growth / selective risk-on`) rather than downgrading into a materially more defensive state?
- **Target / horizon / metric:** 20-trading-day binary classification; primary metric = balanced accuracy vs naive persistence baseline, secondary = Brier score if probability framing is used later.
- **Decision relevance:** Helps decide whether the desk should keep a narrow selective risk-on stance, hold cash discipline steady, and avoid overreacting to single-day noise.
- **No-go uses:** Must not auto-rewrite the Macro Regime Dashboard, must not trigger autonomous posture changes, and must not be presented as a market-timing oracle.

### 2. Entry-band follow-through question for almost-deployable names
- **Question:** When a tracked name is labeled almost deployable and is in or near band, what is the probability that it delivers a favorable follow-through window over the next 10 trading days without first violating the written stop or invalidation logic?
- **Target / horizon / metric:** 10-trading-day event classification on tracked names; success means positive forward return above a defined threshold while avoiding stop/invalidation breach first. Primary metric = precision/recall or MCC against a simple class-imbalance-aware baseline.
- **Decision relevance:** Could later help rank which almost-deployable names deserve the next manual review first when the board is crowded and capital is limited.
- **No-go uses:** Must not auto-promote names to deployable-now, must not override catalyst windows or concentration rules, and must not replace the Deployment Trigger Sheet.

### 3. Catalyst-window disappointment risk question
- **Question:** For tracked names entering a major catalyst window (earnings or equivalent), what is the probability that the first 5 trading days after the event produce a negative outcome large enough to force a stricter review stance?
- **Target / horizon / metric:** 5-trading-day post-catalyst binary classification; event threshold should be defined conservatively in Phase 2/3. Primary metric = recall on downside-risk cases, with false-positive rate tracked explicitly.
- **Decision relevance:** Supports pre-event sizing caution, sequencing, and whether a name should stay conditional instead of being treated as cleanly actionable into the event.
- **No-go uses:** Must not be used to front-run earnings as a trading signal, must not justify leverage or oversized hedging, and must not substitute for post-earnings scorecard interpretation.

### 4. Sleeve-level concentration stress question
- **Question:** Over the next 20 trading days, is a correlated sleeve already near or above risk concentration limits likely to underperform the broader active board enough that adding exposure would worsen portfolio discipline?
- **Target / horizon / metric:** 20-trading-day relative-return classification or ranking between sleeves/active clusters; primary metric = rank correlation or directional hit rate against a naive equal-treatment baseline.
- **Decision relevance:** Fits the current need to avoid over-stacking the tech/AI cluster when the sleeve is already pressing or exceeding cap.
- **No-go uses:** Must not become a sector-rotation engine, must not auto-trim or auto-add positions, and must not override explicit risk caps or written thesis quality.

### 5. Fresh-intelligence review-priority question
- **Question:** When a fresh external intelligence item or macro/corporate development appears, how likely is it to require a real note-layer review within the next 7 calendar days rather than being logged as low-impact noise?
- **Target / horizon / metric:** 7-calendar-day triage classification using later-reviewed outcomes as labels; primary metric = precision at the high-priority class, with manual-review burden tracked as an operational cost.
- **Decision relevance:** Could later help route scarce review attention toward the freshest developments most likely to matter for macro, research-department, or portfolio desks.
- **No-go uses:** Must not self-promote raw events into canonical truth, must not mutate notes automatically, and must not bypass WF21/WF26 verification and routing contracts.

## Shared no-go doctrine for all questions
- No production model deployment.
- No autonomous portfolio, macro, research-department, or note-layer mutation.
- No probability output presented as certainty or as a replacement for written thesis judgment.
- No use of unapproved alt-data, rumor sources, or opaque feature classes before explicit approval.
- No claim that forecast usefulness is proven until naive baselines, walk-forward evaluation, and failure analysis are documented in later phases.

## Why these questions are the right first set
- They are tied to **actual current decisions** in the workspace: regime stability, almost-deployable prioritization, catalyst-window caution, concentration discipline, and fresh-intelligence routing.
- They are **bounded and auditable** enough to support a later provenance audit.
- They emphasize **decision support and triage** rather than fake precision about index levels or price targets.
- They can fail honestly; a negative result would still be useful because it would show where predictive support is not adding value.

## Explicitly deferred to Phase 2+
- exact label definitions and thresholds
- dataset inventory and ownership
- revision/freshness/survivorship rules
- allowed vs blocked feature classes
- baseline statistical methods
- walk-forward and benchmark design
- any implementation candidate beyond methodology framing
