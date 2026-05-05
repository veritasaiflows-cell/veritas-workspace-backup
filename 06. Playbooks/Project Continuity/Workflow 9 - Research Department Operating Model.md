# Workflow 9 - Research Department Operating Model

## Objective
- Define a real operating model for the research function without inventing fake org-chart theater.
- Turn the current finance stack into clearer desk ownership, owned outputs, refresh cadence, and handoff boundaries.

## Current State
- Workflow 9 is closed with follow-up after the 2026-05-02 normalization pass.
- The five-desk model is now accepted as a functional operating model for the live workspace, not as a fake staffed org chart.
- The Workflow 9 **Risk Rules ownership + refresh discipline** sub-pass is now fully closed: `07. Risk/Risk Rules.md` has explicit portfolio / deployment desk ownership, explicit review cadence, an honest freshness-reset rule, and operator-approved doctrine additions with tightened wording.
- The temporary pre-open maintenance items remain in the correct non-blocking state: BRK.B and CAT stay under explicit post-earnings manual hold until real Q2 confirmation exists, and NVDA's written recheck obligation remains due on or before the first post-close chain on **2026-05-13**.
- The Command Center ownership boundary is pinned down: it stays downstream and non-authoritative.
- The trust spine is materially stronger than it was before Workflow 8, and the operating model now reflects note ownership, trust gates, real cadence, and current maintenance cost more honestly.

## Last Meaningful Progress
- Closed Workflow 8 honestly after fixing the live Command Center mismatches, rerunning the full `post-close` chain with workbook build enabled, and updating the queue, registry, and Workflow 8 continuity note.
- Verified the same-window evidence now reads clean for the reopened scope: `tmp/dashboard-validation.json` `0 critical / 0 warning / 0 info`, workbook validation `ok/fresh/clean`, and dashboard acceptance `17/17`.
- Opened Workflow 9 with a bounded first draft that defines five real desks, their owned inputs/outputs, cadence, handoff rules, and non-goals.
- Completed the Risk Rules sub-pass on 2026-05-02: reviewed `07. Risk/Risk Rules.md` against the live selective-risk-on / reduced-confidence regime, kept the core tier sizes and single-name limits intact, and tightened the written contract around speculative-sleeve limits, correlated-sleeve / sector-cap escalation, catalyst-window escalation, and explicit freshness ownership.
- Completed the normalization pass after operator sign-off: made the approved Risk Rules additions canonical with tighter wording, clarified that desks are functional roles with explicit accountable ownership, aligned cadence language to real finance windows rather than every calendar day, and clarified that workbook packaging remains manual/staging under the current trust contract rather than a default every-window output.

## Outstanding
- No blocking work remains inside Workflow 9 after the normalization pass.
- Re-open this note only if desk ownership, cadence reality, or trust-boundary behavior materially changes.

## Blockers / Trust Gaps
- No hard blocker remains inside Workflow 9.
- Provider caveats and non-blocking manual dependencies still exist in domain surfaces, but they are now bounded by the operating model instead of being hidden workflow residue.
- NVDA's likely **May 20** date remains an explicitly unconfirmed timing path until the written recheck obligation is satisfied on or before **2026-05-13**.

## Next Action
- Use this note as the operating reference for the next queue steps. Workflow 25 is now the live downstream consumer that should operationalize the desk model with a real intake queue, coverage-admission reviews, and explicit handoffs to later source-bundle and fresh-intelligence workflows.

## Completed sub-pass - Risk Rules ownership + refresh discipline
- **Owner:** Portfolio / deployment desk inside Workflow 9
- **Executed:** 2026-05-02, ahead of the 2026-05-03 target
- **Review result:** the current tier sizes, normal single-position limits, stretch-position review threshold, and sector-cap range still fit the live regime and current portfolio posture.
- **Content updated:** `07. Risk/Risk Rules.md` now makes desk ownership, review cadence, and freshness-reset rules explicit; uses the operator-approved tighter wording for the speculative-sleeve cap; and carries approved escalation language for correlated-sleeve overstacking, sector-cap breaches, and catalyst-window sizing risk.
- **Acceptance result:** closed after explicit operator sign-off and reflected on the queue / registry / dashboard freshness surface.

## Key Files
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md` - queue order and Workflow 9 control state.
- `06. Playbooks/IC Project Registry.md` - active project status and next pass visibility.
- `09. Archive/Project Continuity/Command Center Chain Readiness Review.md` - archived Workflow 8 pickup point and preserved Command Center ownership-boundary record.
- `Home.md` - workspace navigation spine.
- `01. Dashboards/Executive Brief.md` - executive output surface.
- `01. Dashboards/This Week.md` - near-term operating priorities.
- `03. Portfolio/Portfolio Snapshot.md` - portfolio truth surface.
- `05. Intelligence/Weekly Positioning Review.md` - higher-order decision layer.

## Normalized model - real desks and ownership

### Ownership interpretation
- These desks are functional roles, not separate staffed operators.
- Unless a bounded helper lane is explicitly assigned for prep or comparison work, Veritas main session remains the accountable owner for each desk.
- Helper lanes may prepare inputs, inspect artifacts, or challenge conclusions, but they do not become the owning authority for canonical notes or queue movement by default.

### 1) Research governance / PM / audit desk
- **Owner:** Veritas main session
- **Purpose:** set queue order, define workflow scope, run QC, and prevent fake-green promotion
- **Owned inputs:** `06. Playbooks/OpenClaw Parallel Pilot Queue.md`, `06. Playbooks/IC Project Registry.md`, continuity notes, audit notes, live validation artifacts
- **Owned outputs:** queue movement, registry movement, workflow continuity notes, audit verdicts, trust-grade decisions
- **Cadence:** same-window after any meaningful workflow pass; explicit QC before advancement
- **Hard boundary:** this desk can promote or block work, but it does not get to invent research conclusions that the note-owning desks have not earned

### 2) Macro / regime desk
- **Owner:** Veritas main session (current accountable operator)
- **Purpose:** maintain the market regime frame that governs portfolio posture and deployment aggressiveness
- **Owned machine inputs:** `tmp/market-state.json`, `tmp/policy-expectations.json`, `tmp/macro-regime.json`, breadth/credit artifacts
- **Owned note outputs:** `02. Markets/Macro Regime Dashboard.md`, macro sections inside `01. Dashboards/Executive Brief.md` and `05. Intelligence/Weekly Positioning Review.md`
- **Cadence:** post-close refreshes, Sunday weekly rebuild, and event-driven policy/macro updates
- **Hard boundary:** automation may refresh data and draft summaries; final regime judgment, caveat wording, and portfolio implications stay human-gated in the note layer

### 3) Coverage / company intelligence desk
- **Owner:** Veritas main session (current accountable operator)
- **Purpose:** own the tracked universe, earnings-state truth, research queue, and post-earnings closure path
- **Owned machine inputs:** `tmp/earnings-calendar.json`, `tmp/post-earnings-prep.json`, `tmp/post-earnings-note-targets.json`, coverage config, source research artifacts
- **Owned note outputs:** `04. Research/Coverage Universe.md`, `05. Intelligence/Event Calendar.md`, post-earnings scorecards under `05. Intelligence/Earnings/`, targeted research notes
- **Cadence:** weekly universe review, pre/post-earnings windows, and catalyst-driven updates
- **Hard boundary:** automation may flag date drift, prep scorecard targets, and surface stale research; promotion/demotion, thesis interpretation, and canonical research conclusions stay human-gated

### 4) Portfolio / deployment desk
- **Owner:** Veritas main session (current accountable operator)
- **Purpose:** convert research and macro context into live action states, entry discipline, and risk-aware readiness
- **Owned machine inputs:** `tmp/portfolio-config.json`, `tmp/technical-refresh.json`, `tmp/deployment-check.json`, `tmp/trigger-sheet.json`, `tmp/band-proposals.json`, dashboard validation outputs
- **Owned note outputs:** `03. Portfolio/Deployment Trigger Sheet.md`, `03. Portfolio/Technical Entry and Invalidation Sheet.md`, `03. Portfolio/Portfolio Snapshot.md`, `07. Risk/Risk Rules.md`, execution sections of `01. Dashboards/This Week.md`
- **Cadence:** every post-close chain, after tracked earnings, and after material band/state changes
- **Risk Rules cadence:** review after any material regime change, before any aggressive deployment decision or sizing exception, and during weekly portfolio-positioning maintenance even when the underlying rules do not need rewriting
- **Freshness rule:** a same-window review with no rule changes may reset freshness only if the file is explicitly marked reviewed; silent carry-forward does not count
- **Hard boundary:** machine layers may compute bands, states, and contradictions; only the note layer can own final deploy / hold / bench language and tiering intent

### 5) Publishing / operator surface desk
- **Owner:** Veritas main session (current accountable operator)
- **Purpose:** package downstream views for fast operator consumption without becoming a second truth owner
- **Owned machine inputs:** dashboard payload/build outputs, workbook export/build-validation artifacts, executive brief scripts
- **Owned outputs:** Command Center HTML, dashboard summaries, scripted brief artifacts, and manually triggered workbook packages under the current degraded packaging contract
- **Cadence:** dashboard and Command Center refreshes can run each finance window once trustworthy upstream state exists; workbook packaging remains manual/staging and should run only when intentionally built under the current trust contract
- **Hard boundary:** downstream only. This desk cannot silently rewrite canonical notes or override note-owned judgment, and it must not treat staging/manual packaging as if it were already default safe automation

## Desk-to-desk handoff contract
- **Macro -> Portfolio:** regime changes can tighten or loosen deployment posture, but only after the note layer states the implication explicitly
- **Coverage -> Portfolio:** earnings interpretation and timing certainty can block, reopen, or downgrade setups; date drift alone does not equal thesis change
- **Portfolio -> Publishing:** dashboard/workbook surfaces inherit from trigger/note truth; they do not adjudicate disputed state themselves
- **Governance -> all desks:** no workflow advances unless execution mode and QC state are visible on queue + registry

## Practical cadence map
- **Post-close finance windows (normally active market days, not every calendar day):** macro refresh -> technical/deployment refresh -> validation -> selective note sync -> downstream refreshes where the current trust contract allows them
- **Pre-earnings / post-earnings:** coverage desk opens prep/closure path -> portfolio desk updates action state only if the evidence changed -> publishing refreshes after note/state sync
- **Weekly / Sunday rebuild:** macro/regime summary, coverage-universe hygiene, portfolio ranking review, and outstanding trust-debt triage
- **Ad hoc:** real catalyst, validator contradiction, or note/machine drift that would mislead a decision surface

## Explicit non-goals
- No fake org chart or pretend staffing model
- No second truth owner for Command Center or workbook
- No automatic thesis rewrites from machine artifacts
- No silent promotion of watch-lane names into execution-board status

## Explicit out-of-scope follow-ups after Workflow 9
- `NVDA`'s written recheck obligation remains a dated coverage/calendar task due on or before the first post-close chain on **2026-05-13**; it is not a blocker to Workflow 9 closure today.
- `BRK.B` and `CAT` remain correctly under manual post-earnings hold until real Q2 confirmation exists; no additional Workflow 9 action is required now.
- The missing `LLY` thesis block remains the first bounded live admission-model pilot before formal Workflow 11 drafting; it is not a Workflow 9 dependency.
- Workflow 10 is queued and waiting with named incidents already recorded; do not accelerate it unless a fresh session-lifecycle failure actually appears.
- Normal downstream note refresh still applies to operator surfaces after this workflow; Workflow 9 closure does not claim that every derivative note was rewritten in the same turn.

## Automation / Refresh Path
- Keep Workflow 9 in the main session unless a bounded helper lane is needed for comparison or structure prep.
- Do not let the department model outrun the trust-gated note/dashboard/workbook ownership rules.
- If this workflow pauses, resume from this note first.
