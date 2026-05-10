# Command Center Full Truth Alignment Audit - 2026-05-09

## Retrieval Notes
- Type: audit
- Status: closed-with-follow-up
- Owner surface: `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- Authority: review-only
- Workflow: WF44/WF45/WF46/WF47 residue source
- Key entities: Command Center, decision objects, Promotion Review, LMT, source trust, authority vocabulary
- Source freshness: 2026-05-09 audit evidence
- Next action: keep LMT dual-layer owner-state / technical-risk rendering as bounded WF44 follow-up
- Archive posture: permanent-reference
- Tags: #veritas/audit #wf/WF44 #status/follow-up

## Scope Audited

Independent QA audit of `tmp/veritas-command-center.html` against the current generated artifact layer and finance decision surfaces, focused on whether the Command Center gives Randall a truthful enough operating view of deployment readiness, trust state, promotion review, repair/bench state, daily review objects, and market-intelligence escalations.

This was an audit only. I did not edit canonical finance notes or implementation scripts.

## Files Inspected

Primary rendered/generated surfaces:
- `tmp/veritas-command-center.html`
- `tmp/dashboard-data.json`
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/run-summary-post-close.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/daily-review-objects-post-close.json`
- `tmp/market-intelligence-events-post-close.json`
- `tmp/postclose-brief-input.json`
- `tmp/postmarket-snapshot.json`
- `tmp/daily-executive-brief.json`
- `tmp/deployment-check.json`
- `tmp/trigger-sheet.json`
- `tmp/market-state.json`
- `tmp/macro-regime.json`
- `tmp/policy-expectations.json`
- `tmp/credit-spreads.json`
- `tmp/band-proposals.json`

Generator / validation / rendering code inspected:
- `scripts/generate_dashboard.py`
- `scripts/dashboard_payload.py`
- `scripts/dashboard_core.py`
- `scripts/dashboard_validation.py`
- `scripts/validate_dashboard_state.py`
- `scripts/dashboard_run_summary_consumer.py`
- `scripts/dashboard-template.html`
- `scripts/dashboard-js/00-core.js`
- `scripts/dashboard-js/04-overview.js`
- `scripts/dashboard-js/05-deployment.js`
- `scripts/dashboard-js/09-macro.js`
- `scripts/dashboard-js/11-triggers.js`
- `scripts/dashboard-js/12-post-earnings.js`
- `scripts/dashboard-js/99-init.js`

Doctrine / continuity anchors:
- `SOUL.md`
- `AGENTS.md`
- `TOOLS.md`
- `memory/2026-05-09.md`

## Verdict

**Not fully truth-aligned yet.** The Command Center is usable as a technical/deployment dashboard with clean current validation, but it does **not** yet provide Randall the full current decision picture.

The strongest parts are the freshness/trust panel, deployment table, macro panel, trigger sheet, and review-only / non-trading language. The largest gaps are that the most important post-close decision objects are either hidden or under-rendered:

- ETN is correctly present in data as `PROMOTION REVIEW`, but the Overview action card, deployment strip, deployment overview, and trigger header do not render a promotion-review bucket.
- Daily review objects and market-intelligence escalations are generated and decision-relevant, but the Command Center does not ingest or render them.
- Some owner-state boundaries are split across surfaces: LMT is `DO NOT TOUCH` in the deployment-readiness/trigger layer but appears as `BELOW STOP` in the dashboard deployment board.
- Downstream artifact authority is inconsistent: the run summary says canonical note mutation is disabled, while `postmarket-snapshot.json` and `daily-executive-brief.json` say canonical mutation is allowed and point to written note paths.
- The run summary says `status=ok`, but its execution block still says `chain_status=running` / `chain_status_normalized=false`; the dashboard surfaces the `ok` status but not that execution ambiguity.

Bottom line: **visual polish is ahead of decision-object completeness.** The dashboard should not be treated as Randall's complete post-close command surface until the missing promotion-review, fresh-intelligence, and authority-gate gaps are closed.

## Closed/Passing Evidence

- `tmp/veritas-command-center.html` exists and is readable.
- `tmp/dashboard-data.json` is embedded into the HTML and includes current generated state as of `2026-05-09 23:04 UTC`, data as of `2026-05-08`, with `exec_freshness=usable_with_caution`.
- `tmp/dashboard-validation.json` is clean: `0 critical`, `0 warning`, `0 info`.
- `tmp/dashboard-acceptance-report.json` passed `17/17` cases, including `workflow8_command_center_alignment`.
- Current deployment facts are mostly represented in data:
  - `DEPLOYABLE NOW`: none.
  - `PROMOTION REVIEW`: ETN.
  - `ALMOST DEPLOYABLE`: GOOG, GS, JPM, MSFT, NVDA.
  - `DO NOT TOUCH`: BRK.B, LMT, XOM in `tmp/deployment-readiness-surface.json` / `tmp/trigger-sheet.json`.
  - `BELOW STOP`: CVX, LMT, LNG, RTX in `tmp/deployment-check.json`.
  - `BENCH`: BRK.B, XOM in dashboard deployment records.
- Review-only and non-execution boundaries are visible in several places:
  - HTML subtitle: `Derived operating surface — never canonical truth`.
  - HTML footer: `Trust follows upstream status, not visual polish`.
  - `tmp/run-summary-post-close.json` has `presentation_allowed=false` and `canonical_note_mutation_allowed=false`.
  - `tmp/postclose-brief-input.json` has `consumer_posture=review_only` and `canonical_mutation_allowed=false`.
  - `tmp/market-intelligence-events-post-close.json` has `trade_execution_allowed=false`, `deployment_state_mutation_allowed=false`, and `canonical_mutation_allowed=false`.

## Findings

### 1. Promotion Review is present in data but under-rendered in the Command Center overview

- **Evidence / source file:**
  - `tmp/dashboard-data.json` contains `deployment_summary.promotion_review = ["ETN"]` and `today_action.promotionReview = [ETN]`.
  - `scripts/dashboard_payload.py:798` emits `promotionReview` into `today_action`.
  - `scripts/dashboard-js/04-overview.js:95-100` renders Deployable, Almost, Blocked, Earnings Pending, and Risk-Off sections, but does not render `ta.promotionReview`.
  - `scripts/dashboard-js/04-overview.js:116-123` builds the deployment strip without a promotion-review cell.
  - `scripts/dashboard-js/04-overview.js:143-151` builds the deployment overview without a promotion-review row.
  - `scripts/dashboard-js/11-triggers.js:57-63` builds trigger summary chips without `summary.promotion_review`.
- **Why it matters:** ETN is the main current owner-gated candidate. The exact distinction Randall needs is `deployable-now` vs `promotion-review` vs `almost`. The overview currently makes `DEPLOYABLE NOW` empty and `ALMOST` visible, but does not prominently show the one name that is closest to action while still owner-gated.
- **Severity:** High.
- **Owner / affected surface:** Command Center Overview, Today's Action Card, Deployment Readiness overview, Trigger Sheet header.
- **Recommended fix:** Add a first-class `Promotion review` section/card/count wherever deployment readiness is summarized. Do not fold ETN into deployable or almost. Suggested label: `Promotion review — in band, owner approval still required`.
- **Acceptance proof:**
  - `tmp/veritas-command-center.html` renders `Promotion review` in the Overview action card and Trigger Sheet summary.
  - ETN appears under Promotion Review, not Deployable Now and not Almost.
  - `python scripts\test_dashboard_acceptance.py` includes and passes a case asserting promotion-review visibility.
  - `python scripts\validate_dashboard_state.py --write` remains clean.

### 2. Daily review objects and market-intelligence escalations are generated but absent from the Command Center

- **Evidence / source file:**
  - `tmp/daily-review-objects-post-close.json` has `review_object_count=16`, `escalated_count=3`, and `capital_recommendation_count=1`.
  - Its escalations include `system-trust-ceiling`, BRK.B fresh-intelligence, and ETN fresh-intelligence.
  - Its capital recommendation is GS with `recommended_action=wait_for_band`, `owner_approval_required=true`, and `macro_regime_check=DEGRADED`.
  - `tmp/market-intelligence-events-post-close.json` has `event_count=22`, `escalated_count=5`, top tickers/sleeves BRK.B, ETN, GOOG, JPM, LMT, all routed to `risk_review`.
  - Static search found no dashboard ingestion/render path for `daily-review`, `market-intelligence`, `review_objects`, or `capital_deployment` in `scripts/dashboard_core.py`, `scripts/dashboard_payload.py`, `scripts/dashboard-js/`, `scripts/generate_dashboard.py`, `scripts/dashboard_validation.py`, or `scripts/test_dashboard_acceptance.py`.
  - `tmp/veritas-command-center.html` does not contain the strings `daily-review`, `market-intelligence`, `review_objects`, `capital_deployment`, or `Fresh-intelligence` outside unrelated embedded/generated context.
- **Why it matters:** The dashboard is currently closer to a market/deployment board than a full command center. Randall would not see the generated Fresh-intelligence review queue, top escalations, or the GS capital recommendation from the Command Center, even though those artifacts are exactly what the finance OS is supposed to produce and rank.
- **Severity:** High.
- **Owner / affected surface:** `scripts/dashboard_payload.py`, `scripts/dashboard-js/*`, `tmp/veritas-command-center.html`, dashboard acceptance tests.
- **Recommended fix:** Add a `Daily Intelligence` or `Decision Queue` panel/tab that ingests `daily-review-objects-<window>.json` and `market-intelligence-events-<window>.json`, showing at minimum: counts, top escalations, top review objects, capital recommendations, owner questions, and authority boundaries.
- **Acceptance proof:**
  - Dashboard payload includes `daily_review` and `market_intelligence` blocks with source paths, generated timestamps, counts, top escalations, and authority fields.
  - Rendered HTML shows the three daily-review escalations and five market-intelligence escalations by ticker/title/route.
  - Acceptance test fails if current-window daily review or market-intelligence artifacts exist but are not surfaced.

### 3. Owner-state and technical-risk state are still conflated for some repair / do-not-touch names

- **Evidence / source file:**
  - `tmp/deployment-readiness-surface.json` groups LMT under `DO NOT TOUCH` with BRK.B and XOM.
  - `tmp/trigger-sheet.json` also places LMT under `DO NOT TOUCH` with repair-mode language.
  - `tmp/deployment-check.json` places LMT under `BELOW STOP` with `close 506.51 is below stop -- do not deploy`.
  - `tmp/dashboard-data.json` renders LMT as `BELOW STOP` in `deployment_records` and includes it in `deployment_summary.below_stop`, while `deployment_summary.bench` has only BRK.B and XOM.
  - `tmp/postclose-brief-input.json` similarly lists `bench=[BRK.B, XOM]` and `below_stop=[CVX, LMT, LNG, RTX]`, with no promotion-review or do-not-touch bucket.
- **Why it matters:** Below-stop is a technical fact; do-not-touch / repair is an owner-state boundary. LMT needs both facts visible. If the dashboard collapses owner-state do-not-touch into below-stop, Randall loses the reason the name is off-limits and the UI weakens the repair-mode discipline that was just fixed for XOM.
- **Severity:** Medium-high.
- **Owner / affected surface:** Deployment Board, Overview summary, post-close brief input state summary, deployment-readiness surface integration.
- **Recommended fix:** Preserve dual-layer state in the dashboard: primary owner state plus secondary technical-risk flags. Example: `DO NOT TOUCH / below stop` for LMT, while CVX/LNG/RTX can remain `BELOW STOP / watch-lane monitor only` if they are not owner-layer repair names.
- **Acceptance proof:**
  - LMT appears in a do-not-touch/repair bucket and also carries a below-stop risk flag.
  - BRK.B and XOM remain bench/repair.
  - CVX, LNG, RTX remain below-stop watch-lane monitor names unless owner-state data says otherwise.
  - Acceptance coverage explicitly checks owner-state precedence and secondary below-stop visibility.

### 4. Canonical mutation authority is contradictory across post-close outputs

- **Evidence / source file:**
  - `tmp/run-summary-post-close.json` says `downstream.canonical_note_mutation_allowed=false` with reason `scheduled windows remain fail-closed for canonical note mutation in v1`.
  - `tmp/postclose-brief-input.json` says `canonical_mutation_allowed=false` and `consumer_posture=review_only`.
  - `tmp/postmarket-snapshot.json` says `canonical_mutation_allowed=true` and `wrote_to=01. Dashboards\Post-Market Snapshot\2026-05-09.md`.
  - `tmp/daily-executive-brief.json` says `canonical_mutation_allowed=true`, `confidence_grade=high`, and `wrote_to=01. Dashboards\Daily Executive Summary\2026-05-09.md`.
  - Both referenced note paths exist.
- **Why it matters:** The system cannot simultaneously claim scheduled windows are fail-closed for canonical note mutation and emit downstream artifacts saying canonical mutation was allowed. This is the clearest authority-boundary contradiction found. It can mislead future automation into treating note writes as approved canonical mutation.
- **Severity:** High.
- **Owner / affected surface:** `run_summary_refresh.py`, `postmarket_snapshot.py`, `daily_executive_brief.py`, summary/post-close brief chain, dashboard trust model.
- **Recommended fix:** Reconcile the authority vocabulary. Either:
  1. rename these summary writes as non-canonical/dashboard-note writes and set `canonical_mutation_allowed=false`, or
  2. deliberately change the run-summary downstream gate to acknowledge the specific note writes as approved.

  The safer near-term fix is option 1: keep scheduled post-close outputs review/dashboard-only until owner approval explicitly promotes them.
- **Acceptance proof:**
  - No generated artifact says `canonical_mutation_allowed=true` when the corresponding run summary says canonical note mutation is disabled.
  - Validator or acceptance test checks the cross-artifact authority contract.
  - Post-close brief input, run summary, postmarket snapshot, and daily executive brief use the same authority vocabulary.

### 5. Run summary says `ok`, but execution state still says `running`; dashboard does not surface the ambiguity

- **Evidence / source file:**
  - `tmp/run-summary-post-close.json` top-level `status=ok` and `stop_line=false`.
  - The same file has `execution.chain_status=running`, `chain_status_raw=running`, `chain_status_normalized=false`, and `chain_status_reason=runtime state not safe to normalize`.
  - `scripts/dashboard_run_summary_consumer.py` propagates only `status`, `stop_line`, `presentation_allowed`, and `canonical_note_mutation_allowed` into dashboard trust, and inserts a `Workflow window status` alert based on top-level status.
- **Why it matters:** The dashboard can tell Randall the window finished `ok` while hiding that the chain-status finalization is ambiguous. That is not a trade/execution issue, but it is a trust-state issue. It matters because the Command Center is supposed to distinguish usable, done, and verified from merely generated.
- **Severity:** Medium.
- **Owner / affected surface:** `run_summary_refresh.py`, `dashboard_run_summary_consumer.py`, Command Center trust banner/alerts.
- **Recommended fix:** Fix run-summary finalization semantics, or render a visible `workflow execution ambiguous` warning whenever `chain_status_normalized=false` or `chain_status` is not a completed/ok terminal state.
- **Acceptance proof:**
  - A clean chain produces a terminal normalized execution state, not `running`.
  - If normalization remains false, the dashboard alert tone is warning/bad and explicitly says execution finalization is ambiguous.
  - Existing run-summary tail-order tests plus a dashboard consumer test cover this case.

## Missing Workflow Items

### Workflow: Command Center Promotion Review Visibility Pass

- **Owner surface:** `scripts/dashboard_payload.py`, `scripts/dashboard-js/04-overview.js`, `scripts/dashboard-js/11-triggers.js`, `scripts/test_dashboard_acceptance.py`.
- **Stop line:** Do not call the Command Center decision-complete if a non-empty `promotion_review` bucket is absent from Overview and Trigger Sheet summary.
- **Acceptance proof:** ETN appears under `Promotion review` in the rendered overview and trigger header; deployable-now remains zero; acceptance test covers the bucket.

### Workflow: Command Center Daily Intelligence / Decision Queue Panel

- **Owner surface:** Dashboard payload and rendering layer, sourced from `tmp/daily-review-objects-<window>.json` and `tmp/market-intelligence-events-<window>.json`.
- **Stop line:** If current-window review/event artifacts exist but are not ingested, the dashboard must show a missing-decision-objects warning or fail validation.
- **Acceptance proof:** Rendered Command Center shows review-object count, escalation count, capital recommendations, top review objects, top event escalations, owner questions, and authority boundary.

### Workflow: Post-Close Authority Vocabulary Reconciliation

- **Owner surface:** `run_summary_refresh.py`, `postmarket_snapshot.py`, `daily_executive_brief.py`, `summary_brief_packet.py`, and dashboard validation.
- **Stop line:** No artifact may claim canonical note mutation is allowed when the run summary says scheduled windows are fail-closed.
- **Acceptance proof:** Cross-artifact validator passes and all post-close outputs agree on review-only vs canonical-write authority.

### Workflow: Deployment State Dual-Layer Alignment

- **Owner surface:** `deployment_readiness_surface.py`, `dashboard_payload.py`, `postclose_brief_input` generation, dashboard acceptance tests.
- **Stop line:** Owner repair/do-not-touch state must not be hidden by below-stop technical state.
- **Acceptance proof:** LMT renders as do-not-touch/repair with below-stop flag; BRK.B/XOM remain bench/repair; CVX/LNG/RTX remain below-stop watch-lane monitor names.

### Workflow: Run Summary Completion Semantics Gate

- **Owner surface:** `run_summary_refresh.py`, `dashboard_run_summary_consumer.py`, `scripts/test_run_summary_tail_order.py`, dashboard acceptance tests.
- **Stop line:** Top-level `status=ok` is not enough if execution status remains `running` or unnormalized.
- **Acceptance proof:** Clean chain has terminal normalized execution status, or dashboard warns explicitly about ambiguous execution finalization.

## Recommended Next Pass

Run a bounded implementation pass titled **Command Center Decision Object Visibility Pass**.

Minimum scope:
1. Add promotion-review rendering to Overview and Trigger Sheet summary.
2. Ingest and render current-window daily review objects and market-intelligence events.
3. Add acceptance tests so these objects cannot silently disappear again.

Do **not** start with styling. Start with truth-contract coverage: what decision objects exist, where they render, and what test fails if they are missing.

In parallel or immediately after, run the **Post-Close Authority Vocabulary Reconciliation** because the canonical mutation contradiction is a trust-boundary issue, not a cosmetic dashboard issue.

## Validation Run

Commands run:

```powershell
python scripts\validate_dashboard_state.py --write
python scripts\test_dashboard_acceptance.py
python scripts\dashboard_truth_lint.py
python scripts\workspace_boundary_check.py
```

Results:
- `python scripts\validate_dashboard_state.py --write`: passed; wrote clean validation with `0 critical`, `0 warning`, `0 info`.
- `python scripts\test_dashboard_acceptance.py`: passed `17/17`.
- `python scripts\dashboard_truth_lint.py`: passed with `status=ok`, `0 findings`, `0 warnings`, `0 info`.
- `python scripts\workspace_boundary_check.py`: returned `status=warning` / process exit code `1` due existing unrelated workspace-boundary warnings:
  - undocumented `backups/` root directory entitlement,
  - several executable helper scripts living under `tmp/`,
  - runtime cache/info artifacts.

Notes:
- The dashboard acceptance run prints fixture market-refresh logs while exercising failure/shape cases. I re-inspected current live artifacts after the run; `tmp/market-state.json`, `tmp/policy-expectations.json`, and `tmp/macro-regime.json` remained at the expected `23:03` generation times and current values.
- Validators currently pass despite the findings above because they do not yet assert promotion-review overview rendering, daily-review/event ingestion, canonical-mutation cross-artifact consistency, or run-summary execution finalization visibility.

## Intentionally Deferred Items

- I did not inspect every canonical finance note for content parity; this audit was artifact/rendering alignment, not a full note-layer audit.
- I did not edit dashboard scripts or canonical notes.
- I did not validate browser-rendered DOM with a live browser; conclusions about missing rendered sections are based on static HTML/source inspection and JS render-path inspection.
- I did not resolve existing `workspace_boundary_check.py` warnings because they are outside the Command Center truth-alignment scope.
- I did not design the final UI layout for the proposed Daily Intelligence / Decision Queue panel; the next pass should define the minimal truth contract before presentation polish.
