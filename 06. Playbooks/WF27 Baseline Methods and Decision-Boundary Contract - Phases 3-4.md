# Retired Historical — WF27 Baseline Methods and Decision-Boundary Contract - Phases 3-4

Lifecycle: Retired on 2026-08-29. The content below is dated methodology history and is not an active finance-state model, route, or authority surface.

Date: 2026-05-06  
Owner: Veritas  
Status: bounded methodology artifact for Workflow 27 Phases 3-4 only

## Purpose
- Define the first acceptable baseline-method posture for WF27 without pretending current data readiness is better than it is.
- Lock the decision-boundary contract before any predictive output is allowed near live finance decisions.

## Phase boundary
This artifact does **not** approve live modeling now.
It defines what baseline methods would be acceptable **after** the Phase 2 provenance blockers are solved.
If frozen state history, event panels, and review-outcome labels are not available, the correct action is to stop rather than improvise.

## Shared prerequisites before any baseline run
- frozen daily history for `tmp/market-state.json` and `tmp/trigger-sheet.json` or equivalent machine-stable tables
- canonical historical price/event panel inside the workspace or another explicitly approved source-of-record
- verified event-date ledger for catalyst-window questions
- point-in-time reconstruction rule for deployment-state and band labels
- explicit review-outcome labels for WF21/WF26-style intake objects if the triage-priority question is kept

## Acceptable v1 baseline methods

### 1) Near-term regime stability
- **Allowed baseline methods:**
  - naive persistence baseline
  - simple logistic classification on frozen macro-state variables
  - probability calibration check with Brier score if probabilistic output is used
- **Primary benchmark:** naive persistence
- **Fail conditions:**
  - regime labels not frozen point-in-time
  - mixed-source lag makes label/feature timing ambiguous
  - model does not beat naive persistence after walk-forward testing

### 2) Entry-band follow-through for almost-deployable names
- **Allowed baseline methods:**
  - unconditional event-rate baseline
  - simple logistic or tree-free classification on frozen trigger-sheet state + market-state context
  - transparent class-imbalance-aware thresholding only
- **Primary benchmark:** unconditional hit-rate / stop-breach-rate baseline
- **Fail conditions:**
  - no frozen daily trigger-sheet history
  - labels rely on overwritten `almost deployable` / `in band` states
  - any method starts behaving like hidden promotion/ranking authority

### 3) Catalyst-window disappointment risk
- **Allowed baseline methods:**
  - event-study downside-frequency baseline
  - conservative binary classification on pre-event observable state only
- **Primary benchmark:** unconditional downside frequency for the same catalyst class
- **Fail conditions:**
  - event dates are not verified cleanly enough
  - disappointment threshold is not fixed before label creation
  - retrospective note tone leaks into targets/features

### 4) Sleeve-level concentration stress
- **Allowed baseline methods:**
  - naive equal-treatment or recent-relative-strength comparison baseline
  - simple relative-risk classification only after sleeve-state history exists
- **Primary benchmark:** naive equal-treatment baseline
- **Fail conditions:**
  - sleeve weights/caps are not versioned historically
  - board composition drift is not frozen point-in-time
  - output starts acting like a sector-rotation or auto-trim engine

### 5) Fresh-intelligence review-priority
- **Allowed baseline methods:**
  - rule baseline from source tier + route + unresolved status
  - simple triage classification only after later reviewed outcomes exist as explicit labels
- **Primary benchmark:** deterministic rules from current packet contract
- **Fail conditions:**
  - packet route labels are treated as final importance truth
  - downstream human review outcomes are inferred rather than stored
  - sparse history makes precision claims fake-clean

## Common evaluation posture
- walk-forward only; no random shuffle that leaks future state backward
- compare against naive baselines first
- prefer calibration, precision/recall, MCC, or balanced accuracy over raw accuracy where class imbalance matters
- record failure analysis explicitly; a non-useful model is an acceptable outcome
- stop immediately if performance depends on features that are not provenance-clean or point-in-time safe

## Decision-boundary contract

### Allowed appearances later, if prerequisites and baselines pass
- internal methodology notes
- bounded review-prep artifacts
- optional secondary context in research or weekly review prep, clearly labeled as experimental and non-authoritative

### Forbidden appearances
- direct portfolio deployment decisions
- automatic promotion/demotion of names
- automatic macro posture changes
- note-layer mutation from model output
- queue advancement or workflow judgment based on predictive output alone
- leverage, sizing, or tactical trading instructions

### Required trust language
Any later predictive output must state:
- the exact target and horizon
- baseline comparator used
- whether inputs were point-in-time safe
- confidence limits / known failure modes
- that the output is decision support only and does not authorize deployment, sizing, promotion, demotion, or posture change by itself

## Workflow verdict from Phases 3-4
- WF27 now has an honest methodology spine:
  - bounded forecast questions
  - bounded provenance audit
  - explicit allowed baselines
  - explicit decision-boundary contract
- The next useful work is **not** broader modeling.
- The next useful work is prerequisite state-history and label-retention hardening if Randall later wants predictive work reopened.
