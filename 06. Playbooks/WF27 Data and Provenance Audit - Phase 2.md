# Retired Historical — WF27 Data and Provenance Audit - Phase 2

Lifecycle: Retired on 2026-08-29. The content below is dated methodology history and is not an active finance-state model, route, or authority surface.

Date: 2026-05-06  
Owner: Veritas  
Status: bounded methodology artifact for Workflow 27 Phase 2 only

## Purpose
- Audit the minimum honest data and provenance surfaces required for the accepted WF27 Phase 1 forecast questions.
- Identify what already exists in the current finance OS, who effectively owns each surface, and where freshness, survivorship, revision, or interpretation risks remain.
- Draw a hard line between allowed feature classes and blocked feature classes before any baseline-method draft.

## Phase boundary
This artifact covers **data and provenance audit only**.
It does **not** approve modeling, backtests, feature engineering beyond inventory, canon mutation, or predictive output in live notes.
If a target cannot be labeled honestly from current artifacts, that remains a blocker rather than an invitation to improvise.

## Evidence checked
Canonical note-layer surfaces:
- `06. Playbooks/WF27 Forecast Question Set - Phase 1.md`
- `02. Markets/Macro Regime Dashboard.md`
- `03. Portfolio/Portfolio Snapshot.md`
- `05. Intelligence/Weekly Positioning Review.md`
- `07. Risk/Risk Rules.md`
- `06. Playbooks/WF26 External Intelligence Manual Verification Pilot and Cadence Verdict - 2026-05-06.md`

Current generated evidence surfaces:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/weekly-intelligence-brief.json`
- `tmp/post-earnings-prep.json`

## Current usable data surfaces and effective owners

| Surface | Effective owner | What it currently provides | Freshness / provenance posture | Main risks |
|---|---|---|---|---|
| `tmp/market-state.json` | macro refresh / market-state script layer | SPX, VIX, rates, curve, DXY, oil, breadth, credit regime, futures context, generated timestamps, per-field source dates | Explicit `generated_at_utc`, `last_trading_day`, source dates, 24h stale rule | mixed-source panel, FRED 2Y one-day lag, policy expectations still simplified, no true pre-market tape |
| `02. Markets/Macro Regime Dashboard.md` | macro desk note layer | human-authored operating bucket, confidence, regime interpretation, invalidation conditions | human judgment with explicit as-of date and refresh policy | categorical regime labels are interpretive and may revise after the fact; not yet stored as a machine-stable history series |
| `tmp/trigger-sheet.json` | deployment / technical review layer | per-ticker workflow state, action state, entry band, stop, earnings timing, MA posture, in-band flag, timestamps | explicit generation time, state fields, last-trading-day, warning surface | workflow states are judgment-bearing; earnings dates can change in provider feed; current file is cross-sectional snapshot, not a historical panel |
| `03. Portfolio/Portfolio Snapshot.md` | portfolio desk | draft weights, sleeve totals, cash, concentration warnings, posture summary | human-authored with as-of date | draft allocations can be rewritten; not a clean machine label source for historical targets |
| `05. Intelligence/Weekly Positioning Review.md` | weekly positioning desk | weekly posture, actionable list, catalyst map, risk focus | human-authored but mixed with partially templated remnants | stale or conflicting sections can coexist in the same note; not safe as raw label source without curation |
| `tmp/post-earnings-prep.json` | post-earnings prep layer | current post-earnings packet window, freshness metadata, warnings | explicit timestamps and window contract | packet list was empty in the checked artifact; event labeling is not yet a complete historical scorecard store |
| `tmp/weekly-intelligence-brief.json` | weekly brief generator | summary of deployable/almost-deployable sets and trust gate status | explicit generated time and mutation permission flag | generated summary can conflict with later trigger-sheet state; one checked artifact still reflected an older state where names appeared deployable now |
| WF21/WF26 intake artifacts under `tmp/research-automation/` plus WF26 verdict note | research intake / verification lane | bounded external events, routing outcomes, unresolved-object handling | strongest provenance when tied to approved-source packet contracts | sparse history, manual verification dependency, unresolved objects intentionally remain unresolved |
| `07. Risk/Risk Rules.md` | portfolio / deployment desk | sizing tiers, sector caps, escalation triggers, catalyst-window rules | canonical doctrine with last-reviewed date | doctrine changes over time and is not yet encoded as a versioned machine-readable series |

## Question-by-question minimum data requirements

### 1. Near-term regime stability question
**Question:** Does the current macro operating bucket hold over the next 20 trading days?

**Minimum required datasets / owners**
- `02. Markets/Macro Regime Dashboard.md` — owner: macro desk; source for the human-declared operating bucket and confidence.
- `tmp/market-state.json` — owner: market-state script layer; source for observable state variables underlying the regime call.
- Optional later derived history store — not yet present; needed to freeze prior regime labels rather than reconstruct them from overwritten notes.

**Freshness / revision / survivorship risks**
- Dashboard regime buckets are human-judgment categories and may be revised after new evidence.
- Current dashboard note is overwritten in place, so historical label reconstruction is fragile.
- Market-state fields are better timestamped, but some components are mixed-source and one-day lagged.

**Allowed feature classes now**
- Observable macro state: rates, curve shape, VIX, SPX level/return, DXY, oil, breadth, credit regime from `tmp/market-state.json`.
- Calendar proximity to major macro events already named in canonical notes.
- Prior frozen regime bucket only if a historical archive is created later.

**Blocked feature classes now**
- Human-written forward interpretation prose from later notes as if it were objective ground truth.
- Any portfolio decision outputs, position weights, or deployment labels as substitute macro targets.
- Unapproved alternative macro sentiment feeds or opaque third-party nowcasts.

**Honest blocker**
- No machine-stable historical series of regime bucket labels exists yet; current note-layer overwrite behavior blocks honest supervised labeling without creating a frozen history artifact first.

### 2. Entry-band follow-through question for almost-deployable names
**Question:** For tracked names labeled almost deployable and near band, does 10-day follow-through arrive before stop/invalidation breach?

**Minimum required datasets / owners**
- `tmp/trigger-sheet.json` — owner: deployment/technical layer; source for workflow state, action state, entry band, stop, and ticker-level posture.
- Historical price series for tracked tickers — currently implied by refresh scripts/providers, but not stored as a canonical workspace artifact in the checked evidence.
- `07. Risk/Risk Rules.md` — owner: portfolio/deployment desk; source for tiering and concentration rules that define what later use is allowed.
- `03. Portfolio/Portfolio Snapshot.md` — owner: portfolio desk; source for sleeve/concentration context, but not a target label source.

**Freshness / revision / survivorship risks**
- Trigger-sheet states are only current snapshots; there is no checked historical panel of daily workflow state and band membership.
- Entry bands and stops can be revised after fresh technical review, so later reconstruction may create hindsight bias.
- Active universe survivorship risk is high if only current tracked names are used and dropped names disappear from training history.

**Allowed feature classes now**
- Same-day observable technical state captured at decision time: workflow state, in-band flag, MA posture, stop distance, earnings-days-to-event, sector/sleeve membership.
- Same-day market context from `tmp/market-state.json`.
- Explicit catalyst-window flags and concentration-cap status.

**Blocked feature classes now**
- Any future note text explaining why the trade worked or failed.
- Post-hoc rewritten entry bands or revised stops not frozen at the decision timestamp.
- Relative ranking labels derived from actual later promotion decisions by the desk.

**Honest blocker**
- The workspace currently lacks a frozen daily historical snapshot series for trigger-sheet state and canonical price-aligned labels, so this question cannot be modeled honestly yet without first creating state-history retention.

### 3. Catalyst-window disappointment risk question
**Question:** For tracked names entering a major catalyst window, does the first 5 trading days after the event produce a materially negative outcome?

**Minimum required datasets / owners**
- `tmp/trigger-sheet.json` — owner: deployment/technical layer; current next-earnings dates, timing sensitivity, and pre-event state.
- `tmp/post-earnings-prep.json` plus post-earnings workflow artifacts — owner: post-earnings layer; evidence that an event window existed and was processed.
- Post-earnings scorecards / note targets under `05. Intelligence/Earnings/` — referenced by workflow, but not audited here as a complete historical dataset.
- Historical price series around event dates.

**Freshness / revision / survivorship risks**
- Provider earnings dates can move; trigger-sheet itself warns that some dates need IR verification.
- `post-earnings-prep.json` is a process artifact, not yet a durable event-history dataset.
- Event thresholds for “disappointment” are not defined yet and must be locked before label generation.

**Allowed feature classes now**
- Pre-event observable state: entry-band relation, MA posture, workflow state, days-to-earnings, crowding/catalyst flags, sector context.
- Verified earnings/event date once primary-source confirmed.
- Post-event outcome labels only from frozen price windows, not from discretionary note tone.

**Blocked feature classes now**
- Analyst commentary, retrospective scorecard language, or inferred thesis sentiment as targets.
- Unverified provider date changes treated as ground truth.
- Any external alt-data surprise scores or option-implied event analytics not already approved in the workspace.

**Honest blocker**
- Event-date verification is not consistently primary-sourced, and the workspace does not yet expose a durable, timestamped historical event panel linking pre-event state to post-event outcomes.

### 4. Sleeve-level concentration stress question
**Question:** Is a correlated sleeve near/above risk concentration limits likely to underperform enough that adding exposure would worsen discipline?

**Minimum required datasets / owners**
- `03. Portfolio/Portfolio Snapshot.md` — owner: portfolio desk; current sleeve weights and cap-overage warnings.
- `07. Risk/Risk Rules.md` — owner: portfolio/deployment desk; canonical cap ranges and escalation rules.
- `tmp/trigger-sheet.json` — owner: deployment/technical layer; per-name sleeve membership and action state.
- Historical return series for sleeve members and benchmark board constituents.

**Freshness / revision / survivorship risks**
- Portfolio Snapshot draft weights are judgmental and can change even without deployment.
- Sleeve definitions are currently embedded in notes rather than a versioned machine schema.
- Current board composition changes over time, creating survivorship and composition-drift risk.

**Allowed feature classes now**
- Explicit written sleeve weights/caps and over-cap flags.
- Observable same-day market regime context and relative sector behavior from `tmp/market-state.json`.
- Ticker membership in current sleeves if frozen at timestamp.

**Blocked feature classes now**
- Future discretionary portfolio adds/trims as labels.
- Any hidden “good company exception” overrides that violate the written cap doctrine.
- Freeform narrative concentration concern without a frozen quantitative state record.

**Honest blocker**
- No durable historical sleeve-state ledger exists that records draft weight totals, cap distance, and active-board composition through time; without that, concentration-stress labeling will drift into hindsight reconstruction.

### 5. Fresh-intelligence review-priority question
**Question:** Is a fresh external event likely to require real note-layer review within 7 days rather than being low-impact noise?

**Minimum required datasets / owners**
- WF21/WF26 intake packet artifacts under `tmp/research-automation/` — owner: research intake lane; source for bounded event objects, routes, and unresolved outcomes.
- `06. Playbooks/WF26 External Intelligence Manual Verification Pilot and Cadence Verdict - 2026-05-06.md` — owner: research-intake methodology layer; source for allowed routing logic and stop-line doctrine.
- Downstream review-surface references (macro dashboard, weekly positioning, portfolio snapshot, watchlist, research reviews) — owners vary by desk.

**Freshness / revision / survivorship risks**
- Manual verification remains a core dependency; sparse packet history means small-sample bias would be severe.
- Some important objects are intentionally unresolved, so absence of note mutation is not the same as low importance.
- Downstream review completion is distributed across notes and not yet captured in a single machine-readable closure field.

**Allowed feature classes now**
- Source tier, attribution quality, sleeve mapping, routing outcome, unresolved/stop-line status, event type, and desk target from intake packet contracts.
- Calendar recency and duplicate/corroboration flags from the intake process.

**Blocked feature classes now**
- Raw rumor/geopolitical chatter that WF26 explicitly keeps verification-only.
- Auto-promoting canon mutations as labels of event importance.
- Open-web text embeddings or unapproved NLP feature extraction over arbitrary source text.

**Honest blocker**
- The lane has useful bounded packet artifacts, but not enough durable reviewed-history volume or a single authoritative “review happened / did not happen” label store to support honest modeling yet.

## Cross-question allowed feature classes
Use only feature classes that are already observable, timestamped, and tied to an approved workspace owner:
- machine-generated market-state fields with explicit source dates
- frozen trigger-sheet state fields captured at decision time
- explicit catalyst-window timing once verified
- written risk-rule caps and sizing tiers
- bounded WF21/WF26 routing metadata and source-tier tags
- simple calendar context (days to event, trading-day window, day-of-week, month) only if derived transparently

## Cross-question blocked feature classes
Do not use these unless a later workflow explicitly approves and operationalizes them:
- autonomous note text or embeddings from canon notes as “truth”
- unapproved alternative data, social sentiment, rumor feeds, options-flow products, or broker-only data
- future desk actions as hidden labels for what the model “should” have predicted
- any feature requiring reconstruction from overwritten notes without a frozen timestamped archive
- any target derived from portfolio P&L or deployment decisions instead of the observable-state question itself

## Real gaps that block honest modeling now
1. **No frozen historical state store for trigger-sheet and regime labels.** Current artifacts are snapshots and overwritten notes, not durable labeled history.
2. **No canonical historical price/event panel in the audited workspace surfaces.** Outcome labeling would otherwise depend on ad hoc external pulls at model time.
3. **Provider event-date revision risk remains visible.** Earnings timing is not consistently primary-confirmed.
4. **Sleeve / concentration state is not versioned mechanically.** Portfolio draft weights and board composition can drift without a historical ledger.
5. **Review-outcome labels for external-intelligence triage are not centralized.** Packet routing exists, but “real note-layer review happened” is not stored as a simple durable label.
6. **Human-interpretive categories are not yet frozen as machine contracts.** Regime bucket and stricter-review outcomes can change after the fact.
7. **Sample size is currently too thin in several lanes.** Post-earnings packets and WF26 review objects are useful process evidence, not yet robust modeling datasets.

## Minimum prerequisite work before Phase 3 can stay honest
- Create a frozen daily archive for `tmp/market-state.json` and `tmp/trigger-sheet.json` or equivalent machine-stable history tables.
- Create an event-history ledger that records verified earnings/catalyst dates, pre-event state, and post-event outcome windows.
- Define one canonical historical source for price-return labeling inside the workspace rather than re-pulling mutable provider data later.
- Add a small explicit review-outcome field for WF21/WF26 objects so review-priority labels are observable rather than inferred.
- Keep regime labels and sleeve-state snapshots versioned if they are going to be forecast targets.

## Conclusion
The workspace already has enough **real operating surfaces** to define worthwhile forecast questions, but not enough **frozen historical provenance** to model them honestly yet. The biggest next step is not smarter modeling; it is preserving timestamped state so Phase 3 baselines can be evaluated without hindsight, survivorship drift, or label invention.
