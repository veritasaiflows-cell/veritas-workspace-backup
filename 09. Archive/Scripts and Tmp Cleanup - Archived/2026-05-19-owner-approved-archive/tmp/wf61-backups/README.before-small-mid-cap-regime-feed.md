# Scripts

Durable repeatable helpers for the finance operating system.

## Rules

- Keep `scripts/` for supported tooling only.
- Keep `tmp/` for generated artifacts and staged render outputs only.
- Default to read-only behavior unless a script intentionally updates vault files.
- Prefer explicit inputs, explicit outputs, and visible freshness or warning states.
- Treat autonomous generation as proposal/review/report production by default: generated artifacts may rank, route, summarize, warn, and stage review objects, but they do not authorize portfolio mutation, owner approval, sizing, execution, trades, destructive cleanup, or broader canonical-note mutation.
- Archive one-off diagnostics, scratch helpers, and superseded planning notes instead of leaving them in the active operator surface.

## Requirements

```bash
pip install yfinance tzdata
```

Those are the minimum required Python dependencies for the current supported script surface.
On this Windows / Python 3.14 runtime, `tzdata` is required so `zoneinfo` can resolve market time zones reliably.

Optional dependencies for richer report generation:
```bash
pip install python-docx pillow
```

## Boundary note

- `scripts/` root remains the stable CLI surface documented across the workspace.
- Selected operator-only implementations now live under `scripts/operators/`.
- Root entrypoints such as `python scripts/apply_band_update.py` are intentionally preserved as thin compatibility wrappers so existing docs and operator habits do not break.
- Do not assume everything in `scripts/` root is chain-active; use `run_finance_refresh_chain.py` as the authoritative chain map.

## Artifact taxonomy

Use this taxonomy when deciding whether a generated file should stay active, become a report input, move to durable notes, or be archived.

| Class | Purpose | Examples | Authority |
|---|---|---|---|
| Canonical machine input | Current script-readable evidence used by downstream reports | `tmp/portfolio-config.json`, `tmp/technical-refresh.json`, `tmp/deployment-check.json`, `tmp/trigger-sheet.json`, `tmp/regime-scores.json`, `tmp/market-state.json` | Evidence input only; does not outrank canonical notes |
| Operator portfolio view | Clean human/machine communication layer for portfolio status | `tmp/full-portfolio-view.json`, `.md`, `.html`, `tmp/full-portfolio-view-validation.json` | Review-only report; no canon, portfolio, approval, execution, or trade authority |
| Decision/report surface | Ranked review objects, summaries, and guardrails for Veritas/Randall review | `tmp/daily-executive-brief.json`, `tmp/deployment-readiness-surface.json`, `tmp/daily-review-objects-*.json`, `tmp/market-intelligence-events-*.json`, guardrail reports | Review/proposal only unless a specific bounded note-sync path is approved |
| UI payload | Dashboard/web rendering support | `tmp/dashboard-data.json`, `tmp/dashboard-last.json`, `tmp/veritas-command-center.html` | Presentation only; not portfolio truth |
| Run/proof artifact | Chain evidence, validation, dry-runs, workflow proof, and current-window indexes | `tmp/run-chain-*.json`, `tmp/run-summary-*.json`, `tmp/current-window-artifacts.json`, `tmp/current-window-artifacts.md`, `tmp/wf*.json`, `tmp/wf*.md` | Audit/navigation evidence; archive by retention/reference policy |
| Scratch/research sidecar | One-off research, candidate packets, manual probes, temporary helpers | `tmp/materials-*`, `tmp/bkng-*`, `tmp/promotion-candidate-*`, `tmp/*.py` probes | Promote to `04. Research/` or `08. Audits/` only when accepted as durable; otherwise archive/expire after review |

Default portfolio communication source:
- use `tmp/full-portfolio-view.json/.md/.html` for “show me the portfolio,” “what matters today,” and portfolio-status summaries.
- treat `tmp/dashboard-data.json` as UI backend only.
- cron may generate reports, guardrails, proposals, archive suggestions, scoped eligible entry-band maintenance through `auto_apply_entry_band_maintenance.py --apply`, and the Sunday weekly minimum reference-band note refresh through `reference_band_note_sync.py --apply`; cron must not apply canonical portfolio/intelligence edits outside those approved band-maintenance/reference-visibility paths or perform cleanup moves.

## Governance validators

### `workspace_governance_truth_check.py`

Status: read-only validator

Checks boot-file approval boundaries, active workflow alignment across the Active Workflows surface, parallel queue, and IC registry, workspace-structure ownership text, active-control-surface model-routing policy drift, and safe channel/plugin config snippets when the OpenClaw CLI exposes them. It includes the operator-approved exception that WF40 may remain residual scheduled-proof watch without reclaiming the active workflow slot.

Run:
```bash
python scripts/workspace_governance_truth_check.py
python scripts/workspace_governance_truth_check.py --write
```

Writes with `--write` only:
- `tmp/workspace-governance-truth-check.json`

Notes:
- warnings are explicit but do not fail the run
- critical cross-surface contradictions exit nonzero
- config snippets are summarized only; the validator does not print owner IDs or raw config
- model-routing checks scan active control surfaces only and report bounded file/line/snippet evidence for stale disallowed provider/runtime wording

### `archive_suggester.py`

Status: read-only archive/cleanup suggestion report

Scans for conservative cleanup candidates without moving, deleting, or rewriting anything. It is a pre-automation guardrail: suggestions require owner approval and are not an apply plan.

Run:
```bash
python scripts/archive_suggester.py
python scripts/archive_suggester.py --include-tmp-md
```

Writes:
- `tmp/archive-suggestions.json`
- `tmp/archive-suggestions.md`

Notes:
- `apply_allowed=false` and `moves_performed=false` are hard boundaries
- protected surfaces include canonical finance notes, active workflow surfaces, `data/`, memory, scripts, and skills
- current v1 focuses on undocumented root `backups/`, executable helpers in `tmp/`, and runtime cache candidates
- use the report to decide what to promote/archive manually; do not treat it as auto-archive authority

### `cyber_security_daily_audit.py`

Status: bounded read-only security audit

Runs the current daily cyber-security / workspace-hardening audit for the local OpenClaw host. It combines `openclaw security audit --json`, a bounded `openclaw doctor` pass, skills inventory, workspace boundary/governance validators, and Windows firewall/antivirus checks. It writes report artifacts only under `tmp/`; it does not mutate config, notes, auth, or packages.

Run:
```bash
python scripts/cyber_security_daily_audit.py
```

Writes:
- `tmp/cyber-security-daily-audit.json`
- `tmp/cyber-security-daily-audit.md`

Notes:
- default posture is read-only / review-only
- `status=warning` is expected whenever real drift exists; do not rerun just to hide warning-grade truth
- `stop_line=true` is reserved for critical conditions where the audit should force human review
- `openclaw doctor` is treated as advisory because the current install can emit useful warnings and still hang or error during reinstall/runtime drift

## Supported active tooling

### `research_intake_packet.py`

Status: bounded review-only prototype

Builds fail-closed intake packets from raw research-event input for the approved research-automation contract. The script is a packet-prep surface only: it may recommend routing, but it never authorizes canonical mutation.

Run:
```bash
python scripts/research_intake_packet.py --init-sample
python scripts/research_intake_packet.py --input tmp/research-automation/raw-events.json
```

Writes:
- `tmp/research-automation/raw-events.json` (sample input when `--init-sample` is used)
- `tmp/research-automation/intake-packets-<timestamp>.json`

Notes:
- the exact pre-packet input shape is documented in `06. Playbooks/Research Automation Raw Event Input Contract.md`
- parallel role lanes are deterministic contract lanes in this first version (`event_detector`, `materiality_scorer`, `thesis_drift_agent`, `evidence_qa_agent`, `routing_agent`)
- unresolved truths and fast-moving geopolitical items can stay open as verification objects instead of being forced into fake certainty
- `canonical_mutation_allowed` stays `false`
- validation failures force `stop_line_no_promotion`
- this is an intake/review object, not a verdict or auto-apply surface

### `canonical_freshness_patch.py`

Status: bounded review-only prototype

Builds narrow canonical freshness patch proposals from explicit candidate input. It does not apply patches. It exists to prepare human-review packets for mechanical/alignment freshness work only.

Run:
```bash
python scripts/canonical_freshness_patch.py --init-sample
python scripts/canonical_freshness_patch.py --input tmp/research-automation/raw-freshness-candidates.json
```

Writes:
- `tmp/research-automation/raw-freshness-candidates.json` (sample input when `--init-sample` is used)
- `tmp/research-automation/freshness-patch-candidates-<timestamp>.json`

Notes:
- `apply_allowed` stays `false`
- mechanical date / elapsed-event and post-catalyst status are the normal safe v1 classes
- cross-surface contradiction and thesis/posture change candidates are review-escalation or rejection cases, not auto-help surfaces
- this is a patch-proposal surface, not an apply surface

### `technical_refresh.py`

Status: live

Fetches closing prices and 20/50/200-day moving averages for tracked names, classifies posture, checks entry-band and stop status, and flags near-term earnings-blocked names.

Run:
```bash
python scripts/technical_refresh.py
```

Writes:
- `tmp/technical-refresh.json`

### `market_state_refresh.py`

Status: live

Fetches the core macro and market snapshot used by the operating stack, including SPX, VIX, Treasury context, DXY, energy, futures, sector snapshots, and actionable-name context. Supports partial-success reporting and freshness warnings.

Run:
```bash
python scripts/market_state_refresh.py
```

Writes:
- `tmp/market-state.json`

### `policy_expectations_refresh.py`

Status: live first-version policy layer

Builds the dedicated policy-expectations artifact used to separate Fed-path evidence from general macro narrative. The first version still carries explicit manual dependencies for the current target range and next FOMC date, but it fetches live FedWatch-style futures expectations when available and writes honest warning states when it cannot.

Run:
```bash
python scripts/policy_expectations_refresh.py
```

Writes:
- `tmp/policy-expectations.json`

Notes:
- this is the first dedicated policy layer, not the finished automation state
- the current target range and next FOMC meeting date are still manually maintained in the script until the broader policy workflow is wired
- the meeting distribution is a single-step 25bp approximation from one 30-day Fed Funds futures contract, not a full multi-outcome FedWatch tree

### `credit_spread_refresh.py`

Status: live first-version credit layer

Builds the dedicated credit-spread artifact used to add credit-stress context to regime and deployment work. Primary sourcing uses FRED / ICE BofA OAS series for investment-grade and high-yield spreads. When direct coverage is incomplete, the script degrades honestly into partial status and uses HYG/JNK/LQD proxy behavior to preserve directional context.

Run:
```bash
python scripts/credit_spread_refresh.py
```

Writes:
- `tmp/credit-spreads.json`

Notes:
- direct ICE BofA OAS series can lag by a trading day in FRED
- first version uses heuristic stress-regime thresholds and proxy degradation logic rather than a full credit model
- downstream consumers should treat non-`ok` output as lower-confidence credit state

### `full_portfolio_view.py`

Status: live review-only machine report

Builds a reusable full-portfolio view from the machine layer: portfolio config, technical refresh, deployment check, trigger sheet, regime scores, board/canon guardrail, daily executive brief, and market state. Writes JSON, Markdown, and HTML with graphics/tables. It is a report layer, not canon.

Run:
```bash
python scripts/full_portfolio_view.py --window post-close --write
python scripts/full_portfolio_view_validate.py --window post-close --write
```

Writes:
- `tmp/full-portfolio-view.json`
- `tmp/full-portfolio-view.md`
- `tmp/full-portfolio-view.html`
- `tmp/full-portfolio-view-validation.json`

Boundary:
- review-only; no canonical mutation, portfolio mutation, owner approval, sizing, execution entitlement, or trade authority
- market/theme views must use fresh workspace artifacts or fresh external/primary-source checks when decision-critical

### `portfolio_snapshot_patch_proposal.py`

Status: live review-only proposal generator

Reads `tmp/full-portfolio-view.json` and `03. Portfolio/Portfolio Snapshot.md`, then stages exact-text patch proposals when Snapshot freshness/header state lags the machine layer. It never applies edits.

Run:
```bash
python scripts/portfolio_snapshot_patch_proposal.py --write
```

Writes:
- `tmp/portfolio-snapshot-patch-proposal.json`
- `tmp/portfolio-snapshot-patch-proposal.md`

Boundary:
- cron may generate proposals only
- main session may apply bounded freshness/status sync after review
- no weight, cash, sleeve, sizing, owner-approval, execution-entitlement, promotion/demotion, or trade/action changes

### `current_window_artifact_index.py`

Status: live review-only chain index

Writes a stable current-window artifact map so operator prompts and downstream review can find the right run summary, review objects, report surfaces, guardrails, patch proposals, archive suggestions, and portfolio view without guessing which window just ran. It creates aliases by role only; it does not copy artifacts or promote generated reports into canon.

Run:
```bash
python scripts/current_window_artifact_index.py --window post-close --write
```

Writes:
- `tmp/current-window-artifacts.json`
- `tmp/current-window-artifacts.md`

Boundary:
- review-only index/navigation artifact
- no canonical mutation, portfolio mutation, deployment-state mutation, owner approval, execution entitlement, or trade authority
- optional artifacts may be missing when a window does not produce that role or when an advisory report has not been run

### WF56 portfolio proposal validators

Status: live review-only validator spine

These validators make portfolio-mutation proposal generation fail closed before any future patch/apply helper exists. They accept a proposal file, a directory of proposal JSON files, or a wrapper object with `proposals: [...]`. The default input is `tmp/portfolio-mutation-proposals/`.

Run:
```bash
python scripts/proposal_patch_scope_validator.py --write
python scripts/canonical_status_invariant_validator.py --write
python scripts/portfolio_pro_forma_risk_validator.py --write
python scripts/authority_vocabulary_consistency_check.py --write
python scripts/post_apply_validation_chain.py --write
```

Writes:
- `tmp/proposal-patch-scope-validation.json`
- `tmp/canonical-status-invariant-validation.json`
- `tmp/portfolio-pro-forma-risk-validation.json`
- `tmp/authority-vocabulary-consistency.json`
- `tmp/post-apply-validation-chain.json`

Contracts:
- `proposal_patch_scope_validator.py` allows only approved WF56 proposal surfaces: Watchlist, Execution Board, Execution Board, Portfolio Snapshot, Coverage and Watchlist, Risk Rules, `tmp/portfolio-config.json`, and `tmp/portfolio-mutation-proposals/`. It blocks absolute paths, `..` traversal, account/brokerage/secret surfaces, true authority flags, and apply-capable packets.
- `canonical_status_invariant_validator.py` requires complete current/proposed status tuples across Coverage and Watchlist, Execution Board, Portfolio Snapshot, and portfolio config; it requires owner-surface and field-delta metadata; it blocks jumps from do-not-touch/repair/below-stop/blocked/post-earnings review states to deployable-now without preserving review-only owner-decision gating.
- `portfolio_pro_forma_risk_validator.py` requires risk-rule, concentration, sector, correlated-sleeve, sleeve-delta, and cash-target blocks; it enforces the 25% sector cap, 15% normal single-name ceiling, declared sleeve/correlation caps, speculative-sleeve exception language, and configured cash floor when present.
- `authority_vocabulary_consistency_check.py` scans proposal/report artifacts for forbidden approval, execution, deployment-probability, win-probability, and guaranteed-return language while preserving safe review-only/no-authority phrasing.
- `post_apply_validation_chain.py` is dry-run/planned by default. `--execute` runs only after scoped owner approval and includes canonical ownership, portfolio config, dashboard/state, pipeline consistency, full portfolio view regeneration/validation, board/stale guardrails, and proposal-specific validators.

Boundary:
- clean validation is not approval
- cron may generate proposal objects and validator reports only
- no portfolio mutation, owner approval, sizing, sleeve/cash/risk-rule change, execution entitlement, trade/account action, or destructive cleanup is authorized by these scripts

### `canonical_note_patch_proposal.py`

Status: live review-only proposal generator

Builds canonical-note patch proposals from board/canon and stale-intelligence guardrail findings. Cron may run it to stage `tmp/canonical-note-patch-proposal.json` and `.md`, but it never applies edits. Main-session review is required before bounded freshness/status sync is applied to canonical notes.

Run:
```bash
python scripts/canonical_note_patch_proposal.py --write
```

Writes:
- `tmp/canonical-note-patch-proposal.json`
- `tmp/canonical-note-patch-proposal.md`

Notes:
- `cron_apply_allowed=false` is a hard boundary
- main-session apply is limited to review-only freshness/source-confidence/catalyst-state/technical-state/watch-repair-deployment-state sync
- portfolio mutation, owner approval, sizing, sleeve, execution entitlement, and trade/action changes remain out of bounds

### `stale_intelligence_guardrail.py`

Status: live read-only guardrail

Checks high-risk stale intelligence patterns in canonical finance notes: JPM appearing in deployable-now language after a stop breach, unquarantined Weekly Intelligence Brief placeholders/skeleton sections, stale Regime Matrix refresh-deadline text, and ETN deployable-note close/no-chase drift versus current artifacts.

Run:
```bash
python scripts/stale_intelligence_guardrail.py --write
```

Writes:
- `tmp/stale-intelligence-guardrail.json`
- `tmp/stale-intelligence-guardrail.md`

Notes:
- exits nonzero on critical stale-intelligence findings
- writes reports only; canonical note edits remain main-session gated

### `board_canon_guardrail.py`

Status: live read-only guardrail

Checks below-stop and near-stop artifact states against the canonical board notes so stale softer labels like “almost deployable” or “active watch” cannot quietly survive after a stop breach. It writes proof artifacts only and does not mutate portfolio notes, deployment states, owner approval, or trade/account surfaces.

Run:
```bash
python scripts/board_canon_guardrail.py --write
```

Writes:
- `tmp/board-canon-guardrail.json`
- `tmp/board-canon-guardrail.md`

Notes:
- exits nonzero on critical stop/canon contradictions
- runs in the morning, post-close, and Sunday finance chains after fresh deployment/trigger/regime artifacts are built
- below-stop and near-stop states must outrank softer watch, almost-deployable, or owner-approved-history language

### `deployment_check.py`

Status: live

Reads cached technical and market-state outputs and produces a ranked deployment-readiness summary with freshness checks.

Run:
```bash
python scripts/deployment_check.py
```

Writes:
- `tmp/deployment-check.json`

### `market_intelligence_event_router.py`

Status: live review-only event/materiality router

Builds the bounded WF41-style v1 event packet from approved workspace artifacts. This is not broad news crawling. It routes existing dashboard trust warnings, macro warnings, promotion-review / near-deployable names, band-review debt, provider-calendar catalyst windows, and post-earnings prep packets into ranked owner-review events.

Run:
```bash
python scripts/market_intelligence_event_router.py --window morning
python scripts/market_intelligence_event_router.py --window post-close
```

Writes:
- `tmp/market-intelligence-events-morning.json`
- `tmp/market-intelligence-events-post-close.json`
- `tmp/market-intelligence-events-post-earnings.json`
- `tmp/market-intelligence-events-sunday.json`

Notes:
- remains strictly `review_only`
- every event keeps `owner_review_required=true`
- may rank and route events, but may not mutate thesis, portfolio state, canonical notes, config, or trades
- source quality is workspace-artifact based in v1; wider external-source automation still needs a separate approval/proof pass

Regression guard:
```bash
python scripts/test_market_intelligence_event_router.py
```

### `sector_correlation_check.py`

Status: live review-only WF53 concentration/correlation proof artifact

Builds `tmp/sector-correlation-check.json` from portfolio config, Risk Rules, portfolio notes, and generated finance artifacts. It computes sector exposure versus the 25% cap, highlights correlated-sleeve warnings such as Tech + AI-power, and keeps promotion-impact checks owner-gated. In the finance chain it runs before the sector expansion board and before daily review objects for morning, post-close, and Sunday windows.

Run:
```bash
python scripts/sector_correlation_check.py --window post-close --output tmp/sector-correlation-check.json
```

### `sector_expansion_board.py`

Status: live review-only WF53 daily sector expansion board

Builds `tmp/sector-expansion-board.json` and answers: “Where is sector leadership improving, where are we underexposed, and which names deserve promotion review?” It reviews all 11 SPDR sectors against SPY using 1d/5d/20d relative strength, 50DMA participation, portfolio exposure, tracked-universe candidates, promotion-review queue status, and concentration warnings. It is wired after `sector_correlation_check.py` and before `daily_review_objects.py` for morning, post-close, and Sunday chains.

Run:
```bash
python scripts/sector_expansion_board.py --window post-close --output tmp/sector-expansion-board.json
```

Notes:
- remains strictly `review_only`
- all authority flags stay false; no canonical mutation, watchlist promotion, sizing/allocation recommendation, trade execution, owner approval inference, or probability/modeling authority
- no SPY or no sector price history blocks; partial sector/provider data degrades rather than faking clean status

### `sector_dashboard_suite.py`

Status: live review-only WF53 HTML/CSV dashboard renderer

Builds a local presentation suite from `tmp/sector-expansion-board.json` using pandas. It writes an HTML dashboard plus CSV pivot surfaces for the sector table, leadership/underexposure pivot, exposure pivot, and promotion-review queue context. This is a presentation layer only; it does not mutate canonical notes, portfolio/deployment state, watchlist state, sizing, trade, approval, or probability authority.

Run:
```bash
python scripts/sector_dashboard_suite.py --input tmp/sector-expansion-board.json --output tmp/sector-dashboard-suite.html --csv-dir tmp
```

Writes:
- `tmp/sector-dashboard-suite.html`
- `tmp/sector-dashboard-sector-table.csv`
- `tmp/sector-dashboard-leadership-pivot.csv`
- `tmp/sector-dashboard-exposure-pivot.csv`
- `tmp/sector-dashboard-promotion-queue.csv`

Regression guard:
```bash
python scripts/test_sector_correlation_check.py
python scripts/test_sector_expansion_board.py
python scripts/test_sector_dashboard_suite.py
```

### `daily_review_objects.py`

Status: live review-only decision-prep layer

Builds the bounded daily review-object packet that ranks what matters, escalates only the highest-signal items, and prepares owner-gated capital-deployment recommendation objects from the native finance artifact stack. It consumes the read-only market-intelligence event router and fresh WF53 sector/correlation artifacts when present. Freshness gating is per artifact: stale sector board fields are not mixed into fresh correlation context, and stale correlation fields are not mixed into fresh sector-board context.

Run:
```bash
python scripts/daily_review_objects.py --window morning
python scripts/daily_review_objects.py --window post-close
```

Writes:
- `tmp/daily-review-objects-morning.json`
- `tmp/daily-review-objects-post-close.json`
- `tmp/daily-review-objects-post-earnings.json`
- `tmp/daily-review-objects-sunday.json`

Notes:
- remains strictly `review_only`
- every capital recommendation keeps `owner_approval_required=true`
- capital recommendations include deterministic final-advice fields (`thesis`, `setup_summary`, `catalyst_risk`, `sizing_risk_envelope`, `base_case`, `bull_case`, `bear_case`) sourced from existing artifacts/config without probability, expected-return, model-ranked claims, or per-name numeric sizing ranges/maxes
- may rank and recommend, but may not mutate canonical notes, change deployment state, or execute
- current known gaps stay explicit: wider external-source automation and state-history retention are not wired yet; sector/correlation context is consumed only when fresh enough and remains a manual fallback when absent, stale, or blocked

Regression guard:
```bash
python scripts/test_daily_review_objects.py
```

### `portfolio_mutation_proposal_generator.py`

Status: review-only capital-deployment proposal packet generator

Converts `daily_review_objects.py` capital-deployment recommendation objects into validator-readable proposal packets under `tmp/portfolio-mutation-proposals/`. The packets are tied to entry-band state from `tmp/band-proposals.json` and deployment state from `tmp/deployment-check.json`; they intentionally propose no direct state change and grant no portfolio, canonical, sizing, sleeve, cash, account-action, or owner-approval authority.

Run:
```bash
python scripts/portfolio_mutation_proposal_generator.py --window post-close --write
```

Writes:
- `tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json`

Chain placement:
- morning, post-close, and Sunday finance-chain tails
- runs after `daily_review_objects.py` and before downstream guardrails/discrepancy/index surfaces
- post-close also runs before `proposal_patch_scope_validator.py`, `canonical_status_invariant_validator.py`, `portfolio_pro_forma_risk_validator.py`, `authority_vocabulary_consistency_check.py`, and `post_apply_validation_chain.py`

Stop lines:
- generated packets are proposal/review artifacts only
- owner decision is required before any portfolio-state, canonical-note, size, sleeve, cash, or account action
- validator success is not owner approval and is not execution entitlement

Regression guard:
```bash
python scripts/test_portfolio_mutation_proposal_generator.py
python scripts/portfolio_mutation_proposal_schema_validator.py tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json
python scripts/proposal_patch_scope_validator.py tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json
python scripts/portfolio_pro_forma_risk_validator.py tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json
```

### `finance_discrepancy_resolver.py`

Status: review-only discrepancy queue generator

Aggregates discrepancy and guardrail findings from earnings-date source confidence, Event Calendar rollforward/apply, board/canon guardrails, stale-intelligence guardrails, canonical note patch proposals, and portfolio snapshot patch proposals. It writes an operator queue only; every candidate is `cron_apply_allowed=false` and `main_session_review_required=true`.

Run:
```bash
python scripts/finance_discrepancy_resolver.py --write
```

Writes:
- `tmp/finance-discrepancy-resolver.json`
- `tmp/finance-discrepancy-resolver.md`

Chain placement:
- morning, post-close, and Sunday finance-chain tails
- runs after canonical/portfolio patch proposals and before current-window artifact indexing
- does not run an apply path; it only queues review work

Regression guard:
```bash
python scripts/test_finance_discrepancy_resolver.py
```

### `ticker_monitoring_performance.py`

Status: live review-only WF54 current-state monitoring analytics

Builds `tmp/ticker-monitoring-performance.json` and `tmp/ticker-monitoring-performance.md` from deployment checks, price-trend signals, WF53 sector context, and WF43 state-history row counts. It measures monitoring state only: band/stop posture, repair/fail-closed names, catalyst flags, review debt, WF53 context, and whether history is present but still insufficient for outcome analytics.

Run:
```bash
python scripts/ticker_monitoring_performance.py --window post-close --output tmp/ticker-monitoring-performance.json
```

Notes:
- remains strictly `review_only`
- `fail_closed_tickers` means below-stop / repair fail-closed names only
- `blocked_or_review_required_tickers` carries broader band-review/catalyst/review debt
- outcome analytics stay disabled until realized-outcome retention exists and the probability-readiness gate passes
- no probability, expected-return, model-ranked deployment, watchlist promotion, sizing/allocation, trade execution, canonical mutation, or owner approval inference

Regression guard:
```bash
python scripts/test_ticker_monitoring_performance.py
```

### `state_history_capture.py`

Status: live append-only historical review writer; durable path approved, consumer wiring pending

Captures point-in-time post-close review state into JSONL history without mutating canonical notes, portfolio state, deployment state, owner approval, or trade execution surfaces.

Default durable output:
- `data/state-history/state-history-v1.jsonl`

Legacy proof artifact:
- `tmp/state-history-v1.jsonl` remains proof-only residue, not durable truth.

Run:
```bash
python scripts/state_history_capture.py sample --window post-close
python scripts/state_history_capture.py append --window post-close
python scripts/state_history_capture.py validate
```

Proof contract:
```bash
python -m py_compile scripts\state_history_capture.py scripts\test_state_history_capture.py
python scripts\test_state_history_capture.py
python scripts\state_history_capture.py sample --window post-close
python scripts\state_history_capture.py append --window post-close
python scripts\state_history_capture.py validate
```

Authority:
- historical review and provenance only
- no model training by default
- no model-driven deployment
- no canonical note mutation
- no portfolio/deployment mutation
- no trade execution
- no owner-approval inference

Stop lines:
- validation fails
- source provenance or hashes are missing
- known-at-time fields are mixed with realized future outcomes
- any authority flag widens beyond historical review

### `artifact_index.py`

Status: live derived retrieval index

Builds a read-only SQLite index from the current market-intelligence event packets and daily review-object packets. This is a retrieval and history helper only: the JSON artifacts and note layer remain the operating truth, and the SQLite DB must not be treated as canonical portfolio state.

Run:
```bash
python scripts/artifact_index.py rebuild
python scripts/artifact_index.py latest --limit 10
python scripts/artifact_index.py ticker ETN --limit 20
python scripts/artifact_index.py window post-close
python scripts/artifact_index.py capital --limit 20
python scripts/artifact_index.py trust --limit 20
```

Writes:
- `tmp/veritas-artifact-index.sqlite`
- SQLite sidecars may also appear under `tmp/` when WAL mode is active: `tmp/veritas-artifact-index.sqlite-wal` and `tmp/veritas-artifact-index.sqlite-shm`

Notes:
- derived index only; rebuild from source artifacts when in doubt
- enables fast lookup by ticker/sleeve, window, escalations, capital recommendations, and trust/freshness boundaries
- `latest` and `ticker` output include `source_file` and `list_name` so full-list rows, escalation rows, and capital-recommendation rows are distinguishable
- uses WAL, `busy_timeout`, explicit indexes, strict tables, and batch rebuild transactions
- not wired into `chain_manifest.py` yet; chain integration should be a later fail-soft pass after manual usefulness is proven

### `earnings_calendar_enrichment.py`

Status: live

Refreshes next confirmed earnings dates for the coverage universe and flags date changes only for operator-selected timing-sensitive baselines configured in `tmp/portfolio-config.json` under `earnings_date_watchlist`. Do not hardcode already-reported dates or broad quarter-ahead estimates in the script; use the Event Calendar and post-earnings workflow to roll the note layer forward.

Run:
```bash
python scripts/earnings_calendar_enrichment.py
```

Writes:
- `tmp/earnings-calendar.json` with provider dates plus explicit `date_source_class` and `primary_confirmed` fields. Provider/yfinance dates are `provider_estimate` / `primary_confirmed=false` unless a separate primary-source confidence pass supplies real official evidence.

### `earnings_date_source_confidence.py`

Status: live review-only

Builds a source-confidence packet for timing-sensitive earnings-date baselines configured in `tmp/portfolio-config.json -> earnings_date_watchlist`. It keeps provider dates visible while separating `provider_estimate_unconfirmed` from primary company/IR confirmation. A bare `primary_confirmed: true` config flag is not enough to upgrade confidence; it must include matching `primary_evidence` metadata with date, source/source_type, URL, and matched text. If the optional browser sidecar `tmp/earnings-date-browser-confirmation.json` exists, official-source browser evidence may primary-confirm a date; blocked or inconclusive primary-source fetches, including NVIDIA IR 403 behavior, remain visible trust limits rather than silently promoted.

Run:
```bash
python scripts/earnings_date_source_confidence.py
```

Writes:
- `tmp/earnings-date-source-confidence.json`
- `tmp/earnings-date-source-confidence.md`

Optional browser sidecar input:
- `tmp/earnings-date-browser-confirmation.json`
- accepted records must include official `source_type` (`company_ir`, `company_newsroom`, `company_release`, `sec_filing`, or `sec`), `confirmation_status=primary_confirmed`, a matching `evidence_date`, `url`, and visible `matched_text`
- browser evidence is review-only and does not authorize Event Calendar mutation by itself

Discrepancy response rule:
- when yfinance/provider dates are missing, contradictory, or not primary-confirmed, include official verification sites in the response/review packet
- for NVDA, include NVIDIA Investor Relations Events & Presentations, NVIDIA Newsroom, and SEC EDGAR

### `event_calendar_rollforward.py`

Status: live

Builds a read-only roll-forward review packet for `05. Intelligence/Event Calendar.md` by comparing dated ticker rows in the note against `tmp/earnings-calendar.json` provider dates, `tmp/earnings-date-source-confidence.json` confidence evidence, and tracked-universe policy in `tmp/portfolio-config.json`. It does **not** edit the vault note; it stages review-only proposals so provider-estimated next-quarter dates can be accepted, caveated, or rejected without silent canonical mutation.

Run:
```bash
python scripts/event_calendar_rollforward.py
```

Writes:
- `tmp/event-calendar-rollforward.json`
- `tmp/event-calendar-rollforward.md`

### `event_calendar_apply.py`

Status: live bounded apply helper

Applies Randall-approved daily-chain Event Calendar maintenance. It consumes `tmp/event-calendar-rollforward.json` and `tmp/earnings-date-source-confidence.json`, then updates only the auto-managed provider-estimated earnings roll-forward block plus narrow timing-source wording for already-dated timing-sensitive events such as NVDA. Provider-estimated rows remain explicitly non-primary-confirmed unless primary evidence is attached. This helper does not authorize portfolio mutation, deployment mutation, watchlist promotion, sizing, trade execution, or owner-approval inference.

Run:
```bash
python scripts/event_calendar_apply.py --dry-run
python scripts/event_calendar_apply.py --apply
```

Writes:
- `tmp/event-calendar-apply.json`
- `tmp/event-calendar-apply.md`
- `05. Intelligence/Event Calendar.md` only in `--apply` mode

### `trigger_sheet_refresh.py`

Status: live

Builds the machine-readable trigger layer from cached technical, deployment, macro, and earnings artifacts.

Run:
```bash
python scripts/trigger_sheet_refresh.py
```

Writes:
- `tmp/trigger-sheet.json`

### `post_earnings_prep.py`

Status: live

Builds a structured post-earnings interpretation packet from cached trigger, deployment, technical, earnings, and macro artifacts.

Run:
```bash
python scripts/post_earnings_prep.py
```

Writes:
- `tmp/post-earnings-prep.json`

### `post_earnings_note_targets.py`

Status: live

Translates post-earnings packets into selective candidate note updates and update intents.

Run:
```bash
python scripts/post_earnings_note_targets.py
```

Writes:
- `tmp/post-earnings-note-targets.json`

### `band_refresh.py`

Status: live

Reads `tmp/technical-refresh.json`, `tmp/portfolio-config.json`, and `tmp/earnings-calendar.json` to detect stale or miscalibrated entry bands. The proposal engine is now **Keltner-first, Dual-MA-gated, and SMA-envelope-audited**: it calculates EMA20/EMA50/SMA200, ATR20/ATRP20, trend-stack, method label, band type, band status, confidence, SMA-envelope audit levels, and earnings-state handling.

Read-only. Does not modify `portfolio-config.json` or the note layer. Routine eligible band maintenance is now handled by `auto_apply_entry_band_maintenance.py --apply`; proposals are `canonical_apply_eligible=true` only when they are execution-lane, band-defined, decision-grade workflow states with clear earnings state and approved band status (`IN_BAND` / `NEAR_BAND`). Earnings-imminent, earnings-timing-window, above-band-wait, below-stop/reclaim, watch-lane, underdefined, and non-execution proposals remain review-only / non-applyable.

Run:
```bash
python scripts/band_refresh.py
```

Writes:
- `tmp/band-proposals.json`

Depends on:
- `tmp/technical-refresh.json` (must be fresh)
- `tmp/portfolio-config.json` (must contain `band_last_set` in each entry_bands entry)

Band proposal maintenance workflow:
1. Run `band_refresh.py` - review `tmp/band-proposals.json` for any `needs_review=true` entries and their `entry_band_method`, `band_status`, `trend_stack`, `earnings_state`, and `canonical_apply_eligible` values.
2. Daily finance chains now run `auto_apply_entry_band_maintenance.py --apply` immediately after `band_refresh.py`. This applies only machine-eligible `canonical_apply_eligible=true` maintenance proposals to `tmp/portfolio-config.json` and `03. Portfolio/Execution Board.md`, with an audit at `tmp/auto-band-apply.json/.md`.
3. The Sunday finance chain runs `reference_band_note_sync.py --apply` after eligible auto-apply and before entry-band/status consumers. This writes fresh calculated reference bands for all complete tracked proposals into the Execution Board with restrictive authority labels and audit proof at `tmp/reference-band-note-sync.json/.md`.
4. Non-applyable proposals remain review-only/monitor-only. Automatic band maintenance and reference-band refreshes do not create trade, sizing, sleeve, cash, risk-rule, owner-approval, or execution authority.
5. Use `apply_band_update.py` only for explicit operator/manual override flows.

Regression guards:
```bash
python scripts/test_entry_band_automation.py
python scripts/test_auto_apply_entry_band_maintenance.py
python scripts/test_reference_band_note_sync.py
```
Checks same-day band-age honesty, workflow badge color rendering, earnings-imminent non-applyability, live protection for unsafe watch-lane / underdefined / timing-window / above-band-wait / below-stop proposals, and the scoped automatic apply/note-sync contract.

### `reference_band_note_sync.py`

Status: live weekly minimum reference-band note sync

Synchronizes fresh calculated reference bands from `tmp/band-proposals.json` into `03. Portfolio/Execution Board.md` without touching execution bands in `tmp/portfolio-config.json`. It is intended to keep the note layer from going stale while preserving the distinction between chart-context reference levels and gated execution bands.

Run:
```bash
python scripts/reference_band_note_sync.py --dry-run
python scripts/reference_band_note_sync.py --apply
```

Writes:
- `03. Portfolio/Execution Board.md` (`--apply` only)
- `tmp/reference-band-note-sync.json`
- `tmp/reference-band-note-sync.md`

Chain placement:
- Sunday finance chain only, after `auto_apply_entry_band_maintenance.py --apply` and before `entry_band_fetch.py`
- provides the weekly minimum note-layer reference-band refresh; Command Center daily reference-band display is generated from `tmp/band-proposals.json` in `dashboard_payload.py`

Authority boundary:
- reference-band visibility only
- no execution-band mutation, no owner approval inference, no sizing/sleeve/cash/risk-rule authority, no trade/account action
- non-eligible names must carry restrictive labels such as reference-only, no execution entitlement, repair, below-stop, timing-window, above-band-wait, or watch/reference lane

### `apply_band_update.py`

Status: live

Implementation location:
- CLI entrypoint preserved at `scripts/apply_band_update.py`
- underlying implementation now lives at `scripts/operators/apply_band_update.py`

Manual override applier for band proposals generated by `band_refresh.py`. Reads `tmp/band-proposals.json`, presents each `needs_review=true` / `canonical_apply_eligible=true` proposal for confirmation (or accepts all eligible proposals with `--all`), writes approved changes back to `tmp/portfolio-config.json`, and writes a formatted summary to `tmp/band-update-log.txt` for pasting into the Execution Board. Routine eligible daily maintenance is now handled by `auto_apply_entry_band_maintenance.py --apply` inside the finance chains.

Approved updates now stamp `band_last_set` from the proposal/trading data date when available, instead of the current UTC wall-clock date, so Arizona-session note sync does not drift a day ahead.

Never auto-commits without human review unless `--all` is explicitly passed. For scheduled daily maintenance, prefer `auto_apply_entry_band_maintenance.py --apply`, which has narrower eligibility gates and writes an explicit audit artifact.

Run:
```bash
# Review and confirm each proposal interactively
python scripts/apply_band_update.py

# Apply only specific tickers
python scripts/apply_band_update.py --tickers ETN NVDA

# Preview without writing
python scripts/apply_band_update.py --dry-run

# Accept all needs_review proposals non-interactively
# Only canonical_apply_eligible=true proposals are included; unsafe/review-only proposals are skipped.
python scripts/apply_band_update.py --all
```

Writes:
- `tmp/portfolio-config.json` (updated entry bands and band_last_set dates)
- `tmp/band-update-log.txt` (formatted note-layer update summary)

After running: use `python scripts/band_note_sync.py` to generate an exact note-sync report, then update `03. Portfolio/Execution Board.md` from the helper output and `tmp/band-update-log.txt` if owner-note mutation is approved.

### `band_note_sync.py`

Status: live

Implementation location:
- CLI entrypoint preserved at `scripts/band_note_sync.py`
- underlying implementation now lives at `scripts/operators/band_note_sync.py`

Thin note-sync helper for entry-band upkeep. Compares `tmp/portfolio-config.json` against the canonical `03. Portfolio/Execution Board.md` and emits a review report showing exact band/stop lines that need syncing. It does not rewrite the note layer.

Run:
```bash
python scripts/band_note_sync.py
```

Writes:
- `tmp/band-note-sync.md`
- `tmp/band-note-sync.json`

Use this after manual `apply_band_update.py` overrides or any direct band/config edit when you want a precise note-sync checklist. Routine eligible daily maintenance should use `auto_apply_entry_band_maintenance.py --apply`, which writes both the bounded note sync and `tmp/auto-band-apply.json/.md` audit proof.

### `validate_canonical_ownership.py`

Validates the note-layer ownership contract across `Coverage and Watchlist.md`, `Execution Board.md`, and `Portfolio Snapshot.md`. It checks that Coverage and Watchlist remains the consolidated universe/thesis surface, Execution Board owns execution/watch technical sections and compressed action-state rows, Snapshot no longer carries legacy thesis/entry/stop tables, archived pre-consolidation originals are preserved, and retired Watchlist / Technical / Trigger / Coverage Universe redirect stubs no longer live in active canon folders.

```powershell
python scripts/validate_canonical_ownership.py
python scripts/test_canonical_ownership.py
```

Outputs:

- `tmp/canonical-ownership-validation.json`

This is a canon-hygiene validator only. A clean result does not authorize portfolio mutation, deployment-state mutation, trading, or owner-approval inference.

### `generate_dashboard.py`

Status: live

Builds the normalized dashboard payload, computes the delta vs the prior run, runs trust and contradiction checks, and renders the staged dashboard surface from the static template.

Trust rules now enforced in the generator:
- degraded, partial, stale, missing, manual, and unconfirmed inputs must stay visible in payload and UI
- integrity warnings are emitted instead of being silently smoothed away
- business logic for trust, contradictions, compliance checks, and operator warnings lives in Python rather than the template where practical
- payload now carries both gated `executionBand` fields from `tmp/portfolio-config.json` and fresh `referenceBand` / `reference_bands.by_ticker` fields from `tmp/band-proposals.json`; reference bands are visibility-only and carry explicit no-approval/no-trade/no-sizing authority flags

Run:
```bash
python scripts/generate_dashboard.py
```

Writes:
- `tmp/dashboard-data.json`
- `tmp/dashboard-delta.json`
- `tmp/dashboard-last.json`
- `tmp/dashboard-validation.json`
- `tmp/veritas-command-center.html`

Depends on:
- `scripts/dashboard-template.html`
- upstream JSON artifacts in `tmp/`
- `tmp/portfolio-config.json`

### `validate_dashboard_state.py`

Status: live

Runs the dashboard trust and integrity validator without rendering HTML. Use this as the lightweight closure check before trusting the derived dashboard after note, config, or script changes.

Run:
```bash
python scripts/validate_dashboard_state.py --write
```

Optional strict mode:
```bash
python scripts/validate_dashboard_state.py --strict
```

Writes when `--write` is used:
- `tmp/dashboard-validation.json`

Exit codes:
- `0` = no critical issues
- `1` = warnings present in `--strict` mode
- `2` = critical contradictions detected

### `test_dashboard_acceptance.py`

Status: live

Runs the formal dashboard acceptance harness against controlled temporary mutations of the current `tmp/` artifacts, then restores the originals.

Covers:
- missing market field
- partial macro feed
- stale source
- contradiction surfacing
- earnings-date change visibility
- coherent blocker or stop or in-band state transition behavior

Run:
```bash
python scripts/test_dashboard_acceptance.py
```

Writes:
- `tmp/dashboard-acceptance-report.json`

Use this before declaring future dashboard hardening work accepted.

### `equity_visual_report.py`

Status: live reusable report generator

Builds a reusable visual Word report core for a public equity using live market data, analyst context, valuation metrics, real ticker-level annual history when available from yfinance, and auto-generated PNG panels staged in `tmp/`.

Run:
```bash
python scripts/equity_visual_report.py RTX
python scripts/equity_visual_report.py MSFT --out "06. Playbooks\\MSFT Visual Report.docx"
```

Writes:
- `tmp/<ticker>-price-panel.png`
- `tmp/<ticker>-history-panel.png`
- `tmp/<ticker>-visual-report-data.json`
- Word report output path, defaulting to `06. Playbooks/<TICKER> Visual Report - <date>.docx`

Notes:
- this is the reusable report core, not the full company-specific earnings or segment overlay system
- ticker-specific earnings, guidance, and segment panels can be layered on top when curated quarter data exists
- use this when you want a decision-grade visual report shell without rebuilding layout logic each time

### `equity_ppt_report.py`

Status: live generic first-version PowerPoint generator

Builds a PowerPoint deck from the generated visual-report assets and staged JSON payloads.

Run:
```bash
python scripts/equity_ppt_report.py RTX
```

Writes:
- `06. Playbooks/<TICKER> Deck - <date>.pptx`

Notes:
- current version now supports a generic deck path for any ticker with generated visual-report assets
- optional ticker-specific overlays such as earnings and segment panels are included automatically when matching PNG assets exist in `tmp/`
- use this when the user wants a presentation rather than a memo or Word report

### `premarket_snapshot.py`

Status: live intelligence-layer writer

Reads the cached morning-chain artifacts and produces the daily Pre-Market Snapshot deliverable. Quantitative sections auto-populate; no judgment slots are emitted at this stage - the daily executive brief is the place for narrative.

Run:
```bash
python scripts/premarket_snapshot.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/dashboard-validation.json`
- `tmp/earnings-calendar.json`
- `tmp/dashboard-delta.json`

Writes:
- `01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md`
- `tmp/premarket-snapshot.json`

Idempotency:
- If a session-written file already exists at the canonical path, the script writes to `YYYY-MM-DD-machine.md` so the human/agent version takes precedence.
- Re-runs over a machine-owned file overwrite in place.

### `postmarket_snapshot.py`

Status: live intelligence-layer writer

Reads the cached post-close artifacts and produces the daily Post-Market Snapshot - day summary, tracked-name day results, what changed since the prior dashboard run, open triggers for tomorrow, and tomorrow's catalysts.

Run:
```bash
python scripts/postmarket_snapshot.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/dashboard-delta.json`
- `tmp/post-earnings-prep.json`
- `tmp/earnings-calendar.json`
- `tmp/dashboard-validation.json`

Writes:
- `01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md`
- `tmp/postmarket-snapshot.json`

Idempotency: same session-precedence rule as `premarket_snapshot.py`.

### `daily_executive_brief.py`

Status: live intelligence-layer writer

Generates the autonomous Daily Executive Summary in the established 7-section template. Quantitative sections auto-populate (executive bottom line, execution context, what changed since the prior dashboard run, today's catalysts, closest actionable names with dollar/percent gap to band, trigger conditions, recommended actions). Confidence grade is derived from the dashboard validation summary.

Run:
```bash
python scripts/daily_executive_brief.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/technical-refresh.json`
- `tmp/post-earnings-prep.json`
- `tmp/dashboard-validation.json`
- `tmp/deployment-check.json`
- `tmp/earnings-calendar.json`
- `tmp/dashboard-delta.json`

Writes:
- `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md`
- `tmp/daily-executive-brief.json`

Critical rule: never overwrite a session-written brief. If the canonical file exists and was NOT auto-generated by this script, the script writes to `YYYY-MM-DD-machine.md` so the agent version takes precedence.

### `summary_brief_packet.py`

Status: bounded review-only packet producer for AI-authored commercial briefs

Builds the machine-side handoff packet for a future bounded agent writer. This script does **not** write canonical notes or publish a brief by itself. It packages owner layers, trust posture, source artifact status, state summary, unresolved-truth constraints, and allowed / forbidden claim shapes for either the morning or post-close window.

Current live posture:
- the scheduled `morning` and `post-close` chains now run this packet producer automatically
- packets are generated under `tmp/` as review-only handoff objects
- any human-readable draft should live under `01. Dashboards/Review-Only Briefs/`
- no review brief is auto-delivered or auto-written to a canonical note yet

Run:
```bash
python scripts/summary_brief_packet.py --window morning
python scripts/summary_brief_packet.py --window post-close
```

Writes:
- `tmp/premarket-brief-input.json`
- `tmp/postclose-brief-input.json`

Key rule: output is `review_only` and `canonical_mutation_allowed: false`. The packet is a bounded writer input, not a second truth surface or an authorization surface.

### `summary_brief_lint.py`

Status: bounded validator for future AI-authored commercial briefs

Checks a draft brief against its packet contract. Current v1 coverage is intentionally simple and fail-closed: review-only posture, owner citation presence, unresolved-truth visibility, and forbidden authority / trade language.

Run:
```bash
python scripts/summary_brief_lint.py --packet tmp/premarket-brief-input.json --draft tmp/wf37-safe-draft.md
```

Typical use:
- run after a bounded agent writer produces a draft
- block promotion if the draft bypasses owner notes or publishes state it does not own

### `weekly_macro_snapshot.py`

Status: live intelligence-layer writer

Generates the Weekly Macro Snapshot with 8 sections - regime assessment, Fed and rates, inflation/growth pulse, energy and commodities, FX, geopolitical flags, key events next week, regime posture and portfolio implication. Sections requiring qualitative narrative (inflation/growth detail, geopolitical flags, posture call) are emitted with explicit `_[judgment]_` placeholders.

Run:
```bash
python scripts/weekly_macro_snapshot.py
```

Reads:
- `tmp/market-state.json`
- `tmp/regime-scores.json`
- `tmp/earnings-calendar.json`

Writes:
- `02. Markets/Weekly Macro Snapshot/YYYY-Www.md` (ISO week label)
- `tmp/weekly-macro-snapshot.json`

Idempotency: same session-precedence rule. Re-runs over a machine-owned file overwrite in place.

### `weekly_intelligence_brief.py`

Status: live intelligence-layer writer

Appends a structured, machine-populated section to `05. Intelligence/Weekly Intelligence Brief.md`. Mirrors the SOUL-defined 8-section weekly intelligence routine: macro pulse, energy sweep, geopolitical scan, earnings radar, analyst/institutional flow, technical check, sentiment gauge, recommended actions. Sections requiring qualitative interpretation are emitted with `_[judgment]_` placeholders.

Run:
```bash
python scripts/weekly_intelligence_brief.py
```

Reads:
- `tmp/market-state.json`
- `tmp/trigger-sheet.json`
- `tmp/earnings-calendar.json`
- `tmp/post-earnings-prep.json`
- `tmp/technical-refresh.json`
- `tmp/regime-scores.json`
- `05. Intelligence/Weekly Intelligence Brief.md` (read for idempotency)

Writes:
- `05. Intelligence/Weekly Intelligence Brief.md` (new section appended)
- `tmp/weekly-intelligence-brief.json`

Idempotency: if the current week's heading is already present in the WIB, the script prints a delta report and does NOT overwrite or duplicate the section. Same pattern as `weekly_review_skeleton.py`.

### `equity_pdf_report.py`

Status: live first-version PDF brief generator

Builds a fixed-layout PDF brief from the generated visual-report JSON and PNG assets.

Run:
```bash
python scripts/equity_pdf_report.py RTX
```

Writes:
- `06. Playbooks/<TICKER> PDF Brief - <date>.pdf`

Notes:
- this is the first PDF path for printable/shareable finance briefs
- it reuses the report JSON and generated PNG panels rather than duplicating the full research workflow
- use this when the user wants a clean PDF deliverable instead of Word or PowerPoint

### `regime_scoring_refresh.py`

Status: live controlled machine-companion ranking writer

Scores every tracked name against the current macro regime and writes the derived score artifact. It is also approved to update bounded scoring/ranking/freshness blocks in `02. Markets/Regime Scoring Matrix.md`.

Run:
```bash
python scripts/regime_scoring_refresh.py
```

Reads:
- `tmp/portfolio-config.json`
- `tmp/trigger-sheet.json`
- `tmp/technical-refresh.json`
- `tmp/earnings-calendar.json`
- `tmp/macro-regime.json`

Writes:
- `tmp/regime-scores.json`
- bounded sections of `02. Markets/Regime Scoring Matrix.md`

Authority:
- `Regime Scoring Matrix.md` is a controlled machine-companion ranking note, not final canonical deployment truth
- final action authority remains with `03. Portfolio/Execution Board.md`, `03. Portfolio/Portfolio Snapshot.md`, `07. Risk/Risk Rules.md`, and explicit owner approval
- no portfolio mutation, deployment-state mutation, trade execution, or owner-approval inference is allowed

Proof:
```bash
python scripts/test_regime_scoring_authority.py
```

### `positioning_ranking_refresh.py`

Status: live structured ranking artifact builder

Builds `tmp/positioning-ranking.json` as the structured capital-priority source for workbook exports and future positioning surfaces.

Run:
```bash
python scripts/positioning_ranking_refresh.py
```

Reads:
- `tmp/trigger-sheet.json`
- `tmp/deployment-check.json`
- `tmp/regime-scores.json`

Writes:
- `tmp/positioning-ranking.json`

Notes:
- merges regime score totals with deployability context and event risk into one ranking artifact
- intended to replace markdown parsing as the priority-rank source
- now wired into the refresh chains after `trigger_sheet_refresh.py`

### `workbook_export.py`

Status: live workbook export normalizer

Builds workbook-ready CSV exports from the current `tmp/` artifact stack for the minimum-viable Veritas operating workbook.

Run:
```bash
python scripts/workbook_export.py
```

Writes:
- `tmp/workbook-control-panel.csv`
- `tmp/workbook-watchlist-board.csv`
- `tmp/workbook-deployment-ranking.csv`
- `tmp/workbook-earnings-tracker.csv`
- `tmp/workbook-technical-drift.csv`
- `tmp/workbook-export-manifest.json`

Notes:
- normalizes raw machine labels into workbook vocabularies instead of exposing raw JSON states directly
- leaves unavailable fields blank rather than inventing fake precision
- intended to run after validation, not during half-built chains
- consumes `tmp/band-note-sync.json` when present so workbook surfaces can show note-parity gaps like missing technical-note sections without mutating the canonical note
- export manifest now carries per-export checksum, row-count, file-size, and source-freshness metadata so later workbook packaging can detect stray CSV edits instead of trusting `tmp/` blindly
- now wired into the `morning`, `post-close`, `post-earnings`, and `sunday` refresh chains immediately after `validate_dashboard_state.py --write`

### `workbook_template.py`

Status: live first-version workbook generator

Boundary note:
- stays in `scripts/` root because `python scripts/run_finance_refresh_chain.py <window> --build-workbook` can call it as a manual packaging tail

Builds the first `.xlsx` workbook template from the current workbook CSV exports.

Run:
```bash
python scripts/workbook_template.py
```

Manual chain-tail parity path:
```bash
python scripts/run_finance_refresh_chain.py morning --build-workbook
```

Reads:
- `tmp/workbook-control-panel.csv`
- `tmp/workbook-watchlist-board.csv`
- `tmp/workbook-deployment-ranking.csv`
- `tmp/workbook-earnings-tracker.csv`
- `tmp/workbook-technical-drift.csv`
- `tmp/workbook-export-manifest.json`

Writes:
- `06. Playbooks/Workbooks/Veritas Operating Workbook.xlsx`
- `tmp/workbook-build-validation.json`

Notes:
- uses a control-panel sheet plus four filtered operating-table sheets
- includes first-pass conditional formatting for deployable / blocked / stale / priority states
- includes a control-panel legend plus basic date/number formatting for cleaner scanning
- designed as the first workbook template, not a final styled reporting product
- consumes the live export layer rather than parsing raw JSON directly
- validates manifest row counts and SHA-256 checksums before packaging; missing or mismatched export inputs abort the build instead of silently packaging stray CSV state
- surfaces package age and upstream warning-grade status inside the workbook control panel so stale/manual packaging remains visible
- remains an operator-invoked staging package by default; scheduled workbook packaging stays fail-closed until the Workflow 5 trust contract is upgraded explicitly

### `veritas_technical_pass_validate.py`

Status: Workflow 29 pilot validator

Bounded sidecar validator for the `veritas-technical-pass` skill. Proves the skill's local file contract still exists and that the skill still names the canonical four-state model plus minimum technical-output requirements.

Run:
```bash
python scripts/veritas_technical_pass_validate.py --write
```

Writes when `--write` is used:
- `tmp/veritas-technical-pass-validation.json`

Exit codes:
- `0` = file contract and required skill clauses present
- `2` = missing referenced files or missing required contract clauses

Notes:
- this is a Tier 2 local-proof pilot, not a live chart or workflow-quality validator
- keeps scope intentionally narrow to the file-contract-heavy `veritas-technical-pass` skill

### `automation_trust_block.py`

Status: Workflow 29 pilot validator/normalizer

Builds and validates the first machine-readable automation trust block for the bounded `automation-hardening-manager` -> `cron-automation-manager` producer/consumer path.

Run:
```bash
python scripts/automation_trust_block.py --input scripts/testdata/automation-trust-block-approved.json --write
```

Writes when `--write` is used:
- `tmp/automation-trust-block.json`

Exit codes:
- `0` = trust block is valid and approved for the pilot's read-only consumer posture
- `2` = trust block is missing required fields or fails the pilot approval rules

Notes:
- `approve` is only valid when `trust_level=automation_ready`, `trust_gates_missing=[]`, and consumer posture is `read_only`
- this artifact is a bounded cron-facing trust gate, not a scheduler-expansion or note-mutation permission slip

### `cron_trust_block_consumer.py`

Status: Workflow 29 pilot fail-closed consumer

Reads the normalized automation trust block and exits non-zero unless cron may safely continue in the already-approved read-only posture.

Run:
```bash
python scripts/cron_trust_block_consumer.py --trust-block tmp/automation-trust-block.json --require-workflow "finance scheduled artifact generation pilot"
```

Exit codes:
- `0` = trust block explicitly allows the bounded read-only consumer posture
- `2` = missing/blocked/mismatched/unsafe trust state

Notes:
- intentionally narrow consumer: requires `status=ok`, `cron_read_allowed=true`, and `allowed_posture=read_only`
- fail closed when the trust block is absent, invalid, blocked, or workflow-mismatched

### WF38 promotion-review automation checks

Status: live bounded foundation, review-verdict automation only

These scripts support the sector-expansion / promotion-review gate chain. Candidate packets remain review-only and do not authorize ticker promotion or canonical note mutation. `promotion_review_check.py` may now auto-approve the workspace review verdict only when the exact bounded gate pattern passes; it still does not authorize trade execution or automatic canonical note mutation.

Run:
```bash
python scripts/candidate_packet_validator.py tmp/wf38-fixtures/passing_packet.json
python scripts/portfolio_integrity_check.py tmp/wf38-fixtures/passing_packet.json
python scripts/catalyst_window_check.py tmp/wf38-fixtures/passing_packet.json
python scripts/ranking_shadow_canon_check.py
python scripts/promotion_review_check.py --ticker JPM --write
python scripts/promotion_review_check.py --ticker NVDA --write
python scripts/test_wf38_authority.py
```

Files:
- `scripts/schemas/candidate_packet_schema.json`
- `scripts/candidate_packet_validator.py`
- `scripts/portfolio_integrity_check.py`
- `scripts/catalyst_window_check.py`
- `scripts/ranking_shadow_canon_check.py`
- `scripts/promotion_review_check.py`

Notes:
- `ALMOST DEPLOYABLE` does not require a Promotion Review Queue row by default.
- `DEPLOYABLE` / `DEPLOYABLE NOW` requires a queue row unless an explicit written threshold override exists.
- Catalyst status vocabulary is `clear`, `warning`, `blocked`, or `unknown`.
- Coverage and Watchlist is thesis/research context only; it is not the candidate-packet authority gate, deployment owner, universe-membership owner, or dashboard consistency surface.
- The candidate-packet thesis field is `thesis_evidence_source`; do not reintroduce canonical-thesis wording for research context.
- `promotion_review_check.py` auto-approves only the workspace review verdict when all of these are true: thesis `pass`, macro/regime `pass`, technical `pass`, catalyst `clear`, risk/sizing `warning`, action state `PROMOTION REVIEW`, execution lane, ALMOST/PROMOTION REVIEW workflow state, queue row present, all owner surfaces present, and no readiness blockers.
- Auto-approval leaves `canonical_mutation_allowed=false` and `trade_execution_authorized=false`; owner-note updates remain separate and explicit.
- Correlated-sleeve taxonomy is currently local to `portfolio_integrity_check.py` and should be centralized later if this chain widens.

### `run_finance_refresh_chain.py`

Status: live operating-window runner

Runs explicit refresh chains by operating window instead of treating the whole workflow as one generic pass.

Supported windows:

1. `morning`
   - data spine: `earnings_calendar_enrichment.py`, `earnings_date_source_confidence.py`, `event_calendar_rollforward.py`, `market_state_refresh.py`, `technical_refresh.py`, `regime_scoring_refresh.py`, `band_refresh.py`, `entry_band_fetch.py --all-tracked --html`, `generate_entry_band_status.py`, `deployment_check.py`, `trigger_sheet_refresh.py`
   - dashboard surface: `test_dashboard_acceptance.py`, `generate_dashboard.py`, `validate_dashboard_state.py --write`
   - intelligence layer: `premarket_snapshot.py` - writes `01. Dashboards/Pre-Market Snapshot/YYYY-MM-DD.md`
   - review-only brief packet: `summary_brief_packet.py --window morning` - writes `tmp/premarket-brief-input.json`
2. `post-close` (default)
   - data spine: `earnings_calendar_enrichment.py`, `earnings_date_source_confidence.py`, `event_calendar_rollforward.py`, `market_state_refresh.py`, `technical_refresh.py`, `regime_scoring_refresh.py`, `band_refresh.py`, `entry_band_fetch.py --all-tracked --html`, `generate_entry_band_status.py`, `deployment_check.py`, `trigger_sheet_refresh.py`, `post_earnings_prep.py`, `post_earnings_note_targets.py`
   - dashboard surface: `test_dashboard_acceptance.py`, `generate_dashboard.py`, `validate_dashboard_state.py --write`
   - intelligence layer: `postmarket_snapshot.py` - writes `01. Dashboards/Post-Market Snapshot/YYYY-MM-DD.md`; `daily_executive_brief.py` - writes `01. Dashboards/Daily Executive Summary/YYYY-MM-DD.md` (machine-sidecar pattern preserves any session-written brief)
   - review-only brief packet: `summary_brief_packet.py --window post-close` - writes `tmp/postclose-brief-input.json`
3. `post-earnings`
   - `earnings_calendar_enrichment.py`
   - `earnings_date_source_confidence.py`
   - `event_calendar_rollforward.py`
   - `post_earnings_prep.py`
   - `post_earnings_note_targets.py`
   - `generate_dashboard.py`
   - `validate_dashboard_state.py --write`
4. `sunday`
   - data spine: full earnings + source-confidence + Event Calendar roll-forward + market + technical + regime score rebuild, plus `weekly_review_skeleton.py`, band, entry-band, deployment, trigger, post-earnings, `call_log_sync.py`
   - dashboard surface: `test_dashboard_acceptance.py`, `generate_dashboard.py`, `validate_dashboard_state.py --write`
   - intelligence layer: `weekly_macro_snapshot.py` - writes `02. Markets/Weekly Macro Snapshot/YYYY-Www.md`; `weekly_intelligence_brief.py` - appends a new section to `05. Intelligence/Weekly Intelligence Brief.md` (idempotent on week-heading); plus `postmarket_snapshot.py` and `daily_executive_brief.py` so the Sunday session opens with a primed daily brief as well
5. `full`
   - alias for `post-close` to preserve compatibility with the older one-shot command

Run:
```bash
python scripts/run_finance_refresh_chain.py
python scripts/run_finance_refresh_chain.py morning
python scripts/run_finance_refresh_chain.py post-earnings
python scripts/run_finance_refresh_chain.py --list
python scripts/run_finance_refresh_chain.py morning --dry-run
python scripts/run_finance_refresh_chain.py morning --build-workbook
```

### `dashboard-template.html`

Status: live support file

Static presentation shell consumed by `generate_dashboard.py`. Presentation belongs here, not business logic.

### `prompts/post_earnings_vault_update_v1.md`

Status: live support file

Reusable prompt artifact for the agent-driven post-earnings vault update pass.

## Generated artifact contract

`tmp/` is the machine-artifact surface. Active expected outputs currently include:
- `tmp/technical-refresh.json`
- `tmp/market-state.json`
- `tmp/band-proposals.json` - band staleness proposals from `band_refresh.py`
- `tmp/band-update-log.txt` - formatted note-layer summary from `apply_band_update.py`
- `tmp/deployment-check.json`
- `tmp/earnings-calendar.json`
- `tmp/trigger-sheet.json`
- `tmp/post-earnings-prep.json`
- `tmp/post-earnings-note-targets.json`
- `tmp/portfolio-config.json`
- `tmp/dashboard-data.json`
- `tmp/dashboard-delta.json`
- `tmp/dashboard-last.json`
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/veritas-command-center.html`
- `tmp/premarket-snapshot.json` - structured summary from `premarket_snapshot.py`
- `tmp/postmarket-snapshot.json` - structured summary from `postmarket_snapshot.py`
- `tmp/daily-executive-brief.json` - structured summary from `daily_executive_brief.py`
- `tmp/weekly-macro-snapshot.json` - structured summary from `weekly_macro_snapshot.py`
- `tmp/weekly-intelligence-brief.json` - structured summary from `weekly_intelligence_brief.py`
- `tmp/run-summary-morning.json` - workflow-level closure summary for the morning window
- `tmp/run-summary-post-close.json` - workflow-level closure summary for the post-close window
- `tmp/run-summary-post-earnings.json` - workflow-level closure summary for the post-earnings window
- `tmp/run-summary-sunday.json` - workflow-level closure summary for the sunday window
- `tmp/current-window-artifacts.json` / `.md` - review-only current-window artifact index and role-alias map
- `tmp/workbook-build-validation.json` - manifest/checksum validation result for workbook packaging

Generated artifacts are evidence and staging surfaces. They do not outrank the canonical note layer.
Report visuals generated into `tmp/` are presentation assets, not canonical research truth by themselves.

`tmp/portfolio-config.json` is the machine-readable portfolio and execution config spine. It now carries tracked-universe policy, yfinance symbol mapping, coverage tiers, workflow semantics, and entry-band metadata. Scripts should read tracked names and execution semantics from this file instead of hardcoding local universe lists or band maps.

## Operating-window sequence

Use the chain that matches the real decision window.

The refresh runner is now the default orchestration entrypoint. Prefer it over manually calling long script sequences in cron prompts or ad hoc operator instructions.

Workbook packaging rule:
- default chain runs stop at `workbook_export.py`
- add `--build-workbook` only when you intentionally want a manual staging workbook package after the export layer is fresh
- leaving the flag off preserves the current fail-closed posture for scheduled workbook packaging

### Morning readiness

Use before the session or pre-open when the goal is to read the current board, not rebuild every catalyst workflow.

```bash
python scripts/run_finance_refresh_chain.py morning
```

### Post-close refresh

Use after the close as the default full rebuild for the next session. This is the main convenience path.

```bash
python scripts/run_finance_refresh_chain.py post-close
```

This refreshes the earnings-date layer before trigger generation, then stages post-earnings prep and note-target artifacts so they are not left to memory.

### Post-earnings refresh

Use after a material company report lands when the close-level artifacts already exist and the main need is closure-state follow-up.

```bash
python scripts/run_finance_refresh_chain.py post-earnings
```

### Sunday weekly rebuild

Use once on Sunday to fully prime the next week - full earnings + market + technical + regime score rebuild, weekly positioning review scaffold, weekly macro snapshot, weekly intelligence brief append, and a primed daily executive brief. Designed so the Sunday weekly review session opens against a complete artifact set.

```bash
python scripts/run_finance_refresh_chain.py sunday
```

### Validation placement

`generate_dashboard.py` still emits the inline validation payload used by the dashboard, but the independent closure check now belongs at the end of each operating-window chain:

```bash
python scripts/validate_dashboard_state.py --write
```

That final validator run is the last trust gate before the derived dashboard is treated as decision support.

Scheduled-window closure now has one more layer after validation:
- `run_summary_refresh.py --window <window>` writes the machine-readable workflow summary
- `dashboard_run_summary_consumer.py --window <window>` propagates that trust state into the command center payload and rendered HTML
- `current_window_artifact_index.py --window <window> --write` writes a stable review-only map of the current run's reports, guardrails, proposals, and proof artifacts

This keeps stop lines, missing required outputs, fallback/manual dependencies, and current artifact locations visible instead of letting a rendered dashboard fake success.

### Operator rule

If a workflow needs more than one artifact-refresh script in sequence, default to `run_finance_refresh_chain.py` unless there is a concrete reason to run a narrower step directly.

## Governance note

The active operator surface above is intentionally narrow. Temporary diagnostics, scratch helpers, historical raw dumps, and superseded implementation plans belong in archive if they still matter, not in `scripts/` or `tmp/`.
