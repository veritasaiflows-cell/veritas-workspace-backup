# Workflow 27 - Predictive Analytics and Forecasting Readiness

## Objective
- Define the honest path for statistical forecasting, predictive analytics, and machine-learning support inside the finance OS.
- Prevent model theater by forcing data provenance, target definitions, backtesting discipline, and decision-boundary clarity before any predictive output is allowed near live recommendations.
- Build a roadmap for forecast-support tools that can improve decision quality without pretending to predict markets cleanly.

## Why this lane exists
- Randall wants the finance OS to explore predictive analytics, machine learning, and statistical methods for forward-looking decision support.
- That is the right long-term direction, but it becomes dangerous fast if it starts before the research department, source intake, and evidence/provenance layers are stable.
- This workflow exists to make predictive work real and evidence-based rather than aspirational buzzwords.

## Current State
- closed with follow-up on 2026-05-06 after the bounded methodology and provenance pass
- upstream research-intake, freshness, and retrieval-hardening gates are now organized enough to start the methodology/data-readiness pass
- still intentionally blocked from live decision influence; this remains a methodology and data-readiness lane, not a “ship a model” lane
- Phase 1 now has an explicit bounded artifact in `06. Playbooks/WF27 Forecast Question Set - Phase 1.md`
- QA forced the right constraint before advance: forecast questions must stay observable-state-first and must carry explicit forbidden-interpretation language so they do not drift into portfolio authority
- Phase 2 now has an explicit data/provenance audit in `06. Playbooks/WF27 Data and Provenance Audit - Phase 2.md`
- Phases 3-4 now have an explicit baseline-method and decision-boundary contract in `06. Playbooks/WF27 Baseline Methods and Decision-Boundary Contract - Phases 3-4.md`
- The honest conclusion is conservative: the methodology spine is now explicit, but frozen historical state and review-outcome retention are still prerequisites before any real modeling should reopen
- closeout audit: `08. Audits/WF27 Predictive Readiness Methodology Audit - 2026-05-06.md`

## Scope
- define the first forecastable question set that is actually useful for this workspace
- define target variables, horizons, and success metrics
- define data-quality and provenance requirements
- define acceptable statistical baseline methods before ML widening
- define backtest, walk-forward, and failure-analysis rules
- define what predictive outputs may and may not influence in portfolio decision support

## Phase 1 question-shape rule
- every proposed forecast question must target an **observable market, event, or state variable**, not a portfolio action
- every proposed forecast question must include a short **forbidden interpretation** line stating that the question does **not** authorize deployment, sizing, promotion, demotion, or posture change by itself
- reject Phase 1 questions that behave like hidden buy/sell/rank instructions, vague regime theater, or black-box portfolio guidance

## Phase 2 label-reconstruction rule
- Phase 2 must **not** treat deployment-state labels such as `deployable now`, `almost deployable`, `in band`, or `near band` as clean historical targets or features until owner precedence, point-in-time reconstruction rules, and stale-note handling are defined explicitly.

## Out of Scope
- live trading automation
- black-box model authority over portfolio actions
- model outputs presented as certainty
- broad alt-data ingestion without explicit approval
- immediate production ML pipelines

## Sequential phase approach

### Phase 1 - question and target selection
Required outputs:
- 3-5 bounded forecast questions
- horizon and metric for each
- decision relevance and no-go use cases

### Phase 2 - data and provenance audit
Required outputs:
- required datasets and owners
- freshness / survivorship / revision-risk notes
- feature classes allowed vs blocked
- gaps that block honest modeling

### Phase 3 - baseline methods
Required outputs:
- baseline statistical methods (regime probabilities, event studies, factor / breadth / spread composites, simple classification baselines)
- evaluation methodology
- benchmark against naive baselines
- explicit fail conditions

### Phase 4 - decision-boundary contract
Required outputs:
- where forecast outputs may appear
- where they are forbidden from acting directly
- trust-language rules for human-facing notes
- next implementation candidates only if the baseline work proves useful

## Acceptance Gates
Workflow 27 should not close unless all are true:
1. the first bounded forecast question set is explicit
2. data/provenance requirements are explicit
3. baseline statistical methods are explicit before ML widening
4. backtest / walk-forward rules are explicit
5. decision-boundary rules are explicit and conservative

## Next Action
- Hand the queue to Workflow 23. If predictive work reopens later, start with state-history and label-retention hardening rather than modeling.

## Key Files
- `06. Playbooks/WF27 Forecast Question Set - Phase 1.md`
- `06. Playbooks/WF27 Data and Provenance Audit - Phase 2.md`
- `06. Playbooks/WF27 Baseline Methods and Decision-Boundary Contract - Phases 3-4.md`
- `08. Audits/Parallel Finance OS Research/2026-05-04 - Bounded Parallel Lanes and Script Roadmap/Research Note.md`
- `06. Playbooks/Project Continuity/Workflow 25 - Research Department Completion and Coverage Admission Operations.md`
- `06. Playbooks/Project Continuity/Workflow 26 - Fresh External Intelligence and Geopolitical Verification Pilot.md`
- `02. Markets/Macro Regime Dashboard.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `07. Risk/Risk Rules.md`

## Automation / Refresh Path
- methodology first
- modeling later
- production influence only after explicit backtest and operator-boundary approval
