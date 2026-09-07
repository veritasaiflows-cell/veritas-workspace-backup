# Cron Expansion QA / Retention Challenge

Generated: 2026-05-10 18:xx MST / 2026-05-11 UTC
Mode: read-only challenger pass. No config/auth/channel/network/canonical-finance-note mutations performed.

## Bottom-line verdict

The cron expansion is feasible, but it should be built as **artifact generation + review support**, not as autonomous publishing or canonical-state mutation.

Current live cron truth is narrow: `openclaw cron list` shows only the daily security audit job (`d2cbac10-f1fb-4060-8445-cb13f3dfc6be`). Historical finance cron ledger entries are useful design precedent, but **do not prove live finance scheduling**.

The highest-risk mistakes to avoid:
- moving existing `tmp/*.json` contracts and breaking consumers;
- scheduling overlapping jobs that write the same dashboard/run-summary/brief layers;
- producing a weekly PDF before the weekly note layer is actually judgment-complete;
- allowing WF43/WF55 outputs to imply probability, calibration, or model-driven deployment readiness.

## Recommended cron cadence

### 1. Finance morning refresh
- **Cadence:** weekdays 06:05 America/Phoenix.
- **Mechanism:** isolated cron job.
- **Command owner:** `python scripts\run_finance_refresh_chain.py morning`.
- **Primary outputs:** existing root contracts: `tmp/run-summary-morning.json`, `tmp/premarket-snapshot.json`, `tmp/premarket-brief-input.json`, `tmp/daily-review-objects-morning.json`, `tmp/sector-expansion-board.json`, dashboard/workbook artifacts.
- **Do not add PDF or archive tails here.** Morning should stay fast and decision-prep oriented.

### 2. Pre-market AI-reviewed brief artifact
- **Cadence:** weekdays 06:25 America/Phoenix, after the morning chain has had time to finish.
- **Recommended first implementation:** generate a **review-only human-facing markdown draft** from `tmp/premarket-brief-input.json`, then lint it.
- **Output location:** new generated markdown should live under a dedicated subfolder such as `tmp/reports/premarket/` or `tmp/intelligence/premarket/`, with an optional stable alias like `latest.md` plus dated files.
- **Canonical note mutation:** blocked. If a draft is later promoted to `01. Dashboards/Review-Only Briefs/`, that should remain review-only and non-canonical unless an explicit workflow allows more.

### 3. Post-close refresh
- **Cadence:** weekdays 13:20 America/Phoenix.
- **Mechanism:** isolated cron job.
- **Command owner:** `python scripts\run_finance_refresh_chain.py post-close`.
- **Primary outputs:** existing root contracts: `tmp/run-summary-post-close.json`, `tmp/postmarket-snapshot.json`, `tmp/daily-executive-brief.json`, `tmp/postclose-brief-input.json`, `tmp/daily-review-objects-post-close.json`, Command Center/workbook artifacts.

### 4. Post-close state-history append / validation
- **Cadence:** weekdays 13:45 America/Phoenix, or as a post-close chain tail only after the post-close run summary is fresh and non-blocked.
- **Recommended first implementation:** separate small cron job is safer than widening the main chain until proof is clean.
- **Commands:**
  1. verify `tmp/run-summary-post-close.json` freshness and `stop_line=false`;
  2. run `python scripts\state_history_capture.py append --window post-close`;
  3. run `python scripts\state_history_capture.py validate`.
- **Output owner:** `data/state-history/state-history-v1.jsonl` only.
- **Probability/modeling:** explicitly blocked. This cadence proves retention only.

### 5. Post-earnings catch-up
- **Cadence:** weekdays 15:30 America/Phoenix, retained only if it has a cheap stop gate that detects whether earnings packets actually require follow-up.
- **Command owner:** `python scripts\run_finance_refresh_chain.py post-earnings`.
- **Stop preference:** skip with a truthful no-op if no tracked post-earnings packet is active. Do not rerun just to freshen artifacts cosmetically.

### 6. Sunday weekly refresh
- **Cadence:** Sunday 08:00 America/Phoenix.
- **Command owner:** `python scripts\run_finance_refresh_chain.py sunday`.
- **Primary outputs:** existing root contracts: `tmp/run-summary-sunday.json`, `tmp/weekly-macro-snapshot.json`, `tmp/weekly-intelligence-brief.json`, Command Center/workbook artifacts.
- **Important caveat:** current weekly scripts generate machine scaffolds / placeholders. They do not prove the weekly note layer is judgment-complete.

### 7. Weekly Intelligence PDF
- **Cadence:** Sunday late afternoon/evening only if the weekly note layer is coherent; suggested 18:10 America/Phoenix as a packaging/check window.
- **Recommended first implementation:** scheduled **PDF readiness check** before scheduled PDF creation.
- **Do not generate the PDF blindly after the Sunday chain.** The PDF spec requires the note layer to be judgment-completed and conflicts to resolve in favor of notes.
- **Allowed output path if generated:** `06. Playbooks/Weekly Intelligence PDF/Weekly Intelligence PDF - YYYY-MM-DD.pdf` per product spec, or a staging path under `tmp/reports/weekly-pdf/` if still draft/review-only.

### 8. Archive / retention job
- **Cadence:** weekly Sunday 19:30 America/Phoenix, after Sunday refresh/PDF readiness windows.
- **Recommended first implementation:** dry-run report only for at least one cycle.
- **Apply mode:** owner-approved only, manifest + hashes required, and only for allowlisted non-contract files.

## Overlap risks

1. **Morning vs premarket brief writer**
   - Risk: brief writer reads `tmp/premarket-brief-input.json` while morning chain is still writing it.
   - Mitigation: require fresh run summary and matching packet timestamp; schedule at least 15-20 minutes after morning chain.

2. **Post-close chain vs state-history append**
   - Risk: state-history captures a half-built or stale post-close surface.
   - Mitigation: state append must require fresh `tmp/run-summary-post-close.json`, `stop_line=false`, no critical dashboard validation, and no active `run-chain-post-close.json` status of `running`/`recovering`.

3. **Post-close chain vs Command Center generation**
   - Risk: multiple jobs write `tmp/veritas-command-center.html`, `tmp/dashboard-data.json`, `tmp/dashboard-last.json`, and `tmp/dashboard-validation.json`.
   - Mitigation: Command Center writes should remain inside the finance chain or a single downstream summary-integrator job, not multiple sibling writers.

4. **Sunday chain vs weekly PDF**
   - Risk: PDF packages machine placeholders (`_[judgment]_`) as if complete.
   - Mitigation: PDF job must stop if weekly notes contain unresolved placeholders, stale validation, or mismatch with `tmp/weekly-intelligence-brief.json` / `tmp/weekly-macro-snapshot.json`.

5. **Archive job vs live contracts**
   - Risk: archive moves `tmp/*.json`, `.csv`, `.html`, or `.sqlite` files used by scripts/dashboard/workbook consumers.
   - Mitigation: root `tmp/*.json` contracts stay in place unless every consumer is scanned and patched. Archive job should start with reports and manifests only.

6. **Post-earnings catch-up vs post-close refresh**
   - Risk: both write post-earnings prep/targets and dashboard surfaces.
   - Mitigation: keep at least 90 minutes between jobs; post-earnings job should be no-op if no active packets exist.

## Exact stop lines

### Global cron stop lines
- Stop if live cron state, ledger, and handoff disagree and the job would rely on stale historical assumptions.
- Stop if any job would mutate config, auth, network/channel, plugin, browser, credentials, portfolio state, deployment state, or trade/account state.
- Stop if source artifacts are stale/missing and the run would present a fresh conclusion anyway.
- Stop if `presentation_allowed`, `canonical_note_mutation_allowed`, `portfolio_mutation_allowed`, `deployment_state_mutation_allowed`, `trade_execution_allowed`, or `owner_approval_granted` becomes true unexpectedly.
- Stop if a generated artifact conflicts with canonical notes and the workflow would treat the artifact as higher authority.

### Morning / post-close refresh stop lines
- Required run summary missing or stale for the window.
- `run-chain-<window>.json` reports `failed`, `recovering`, or unfinished state after the chain should be complete.
- `tmp/dashboard-validation.json` has critical contradictions.
- `tmp/dashboard-acceptance-report.json` missing after chain run.
- Any required root JSON contract is missing after the chain.

### Brief writer stop lines
- Input packet missing, stale, or mismatched to the latest run summary.
- Packet authority is not review-only or `canonical_mutation_allowed` is not false.
- Draft contains trade/order/account language, approval inference, or uncited owner-state claims.
- Lint fails.

### WF43 state-history stop lines
- `python scripts\state_history_capture.py validate` fails.
- Any row lacks source provenance/hash.
- Any row rewrites/interprets future outcomes as known-at-time facts.
- Any authority field implies model training, model-driven deployment, canonical mutation, portfolio/deployment mutation, trade execution, or owner approval.
- `future_outcomes` is prefilled without a separate explicit owner-decision/outcome update event.

### WF55 / probability-readiness stop lines
- Any output says win probability, deploy probability, expected return, calibrated score, model-ranked deployment, or probability-driven recommendation before prerequisites exist.
- State history has only presence/provenance rows and no realized-outcome update flow.
- `outcome_analytics_ready=false` or equivalent is present but ignored.
- Known-at-time and realized-outcome fields are mixed.

### Weekly PDF stop lines
- Weekly note layer has unresolved `_[judgment]_` placeholders or obvious machine-scaffold sections.
- `validate_dashboard_state.py --write` has not been run after the Sunday refresh.
- PDF source notes and structured artifacts disagree.
- PDF lacks visible trust/risk limits.
- PDF would be presented as canonical truth rather than a packaging layer.

### Archive / retention stop lines
- Candidate has inbound references and no explicit allowlist/owner approval.
- Candidate is a root `tmp/*.json` contract, root dashboard/workbook artifact, SQLite index, current Command Center HTML, run summary, chain state, `portfolio-config.json`, or durable `data/` file.
- Archive move lacks manifest, hash, source path, destination path, and restore note.
- Applying cleanup would delete rather than move/archive, unless explicitly approved.

## Retention recommendations

### Durable state history / WF43
- **Path:** `data/state-history/state-history-v1.jsonl`.
- **Retention:** indefinite append-only; do not auto-delete or compact in v1.
- **Archive policy:** annual copy/snapshot is acceptable, but do not move the active JSONL path.
- **Minimum active evidence:** keep all raw rows while row count is low. Current durable rows: 2.
- **Backup expectation:** include in workspace backup/checkpoint strategy before relying on it for analytics.

### Owner decisions and realized outcomes
- **Retention:** indefinite once an update flow exists.
- **Rule:** append/update future-outcome fields only through explicit outcome-update workflow with provenance.
- **No hindsight rewriting:** never rewrite original known-at-time fields.

### Probability readiness / analytics
- **Current state:** blocked for probability/calibration language.
- **Retention:** keep readiness/gate reports for 180 days in generated-artifact form; promote accepted methodology/contracts into playbooks.
- **Readiness threshold:** 5 rows may support minimal outcome-analytics plumbing checks; calibrated probability should require materially more realized outcomes and an explicit owner reopening. Do not treat 5 rows as probability readiness.

### Daily generated reports
- **Canonical/dashboard note outputs:** keep normal note-layer history unless a separate workspace-governor policy says otherwise.
- **Review-only generated markdown under `tmp/reports/`:** keep 30 days active; archive monthly if useful; delete only with owner-approved cleanup policy.
- **Root latest JSON contracts:** keep as stable latest pointers. Do not rotate/move without patching consumers.

### Weekly PDFs
- **Finished PDFs:** keep indefinitely as deliverables, preferably under `06. Playbooks/Weekly Intelligence PDF/` or a dated yearly archive once old.
- **Draft PDFs / render intermediates:** keep 30 days in `tmp/reports/weekly-pdf/` or equivalent.
- **Visual/render temp assets:** keep 14-30 days unless referenced by a finished PDF manifest.

### Command Center / dashboard artifacts
- **Latest root artifacts:** keep in `tmp/` because scripts and dashboard consumers expect them there.
- **Historical snapshots:** if desired, create dated copies under `tmp/reports/command-center/` or `09. Archive/generated-artifacts/`, but do not move root latest files.
- **`dashboard-last.json` / `deployment-history.json`:** unsafe to archive casually because they support delta/history behavior.

### General tmp artifacts
- **Root `tmp/*.json` machine contracts:** protected by default.
- **One-off `.md` / `.txt` QA reports:** archive after 14-30 days when not part of the active workflow.
- **Tmp Python helpers:** promote to `scripts/` if durable, otherwise archive only after owner approval and inbound-reference scan.
- **Large schemas/cache artifacts:** keep if still used for config/schema/workspace indexing; otherwise require owner-approved cleanup.

## New markdown under tmp: yes, but only under a subfolder

New human-facing generated markdown should **not** be mixed into root `tmp/` beside machine JSON contracts.

Recommended pattern:
- machine-consumed latest JSON remains at existing `tmp/*.json` paths;
- new human-facing generated markdown goes under `tmp/reports/<product>/` or `tmp/intelligence/<product>/`;
- optionally write `latest.md` plus dated immutable files;
- include a sidecar JSON manifest with source artifact paths, hashes, authority flags, and lint result;
- only promote into note-layer folders when the owning workflow explicitly allows it.

This keeps `tmp/` honest: generated output can live there, but root `tmp/` should remain mostly stable machine-contract files.

## How to avoid breaking existing JSON contracts

- Do **not** bulk-move existing root `tmp/*.json` artifacts.
- Keep current root paths stable for all files named in `chain_manifest.py`, `dashboard_payload.py`, `dashboard_core.py`, workbook scripts, run-summary consumers, and tests.
- If a new dated/organized artifact is needed, write a second copy or manifest under a subfolder while preserving the root latest path.
- Before moving or renaming any root artifact, run a repo-wide consumer scan with exact filename search and patch every consumer/test/docs reference in the same implementation pass.
- Prefer compatibility aliases over path migration for this pass.
- New report generators should take explicit `--output` paths and default to subfolders, while still reading existing root JSON inputs.

## Safe archive candidates, with conditions

Safe-ish candidates only after owner approval + inbound-reference scan + manifest/hash:
- tmp executable helpers: `dump_bands.py`, `find_band_refs.py`, `find_disallowed_model_refs.py`, `find_disallowed_openclaw_refs.py`, `find_model_refs.py`, `market_close_quick.py`, plus newer one-off helpers such as `add_bkng_to_config.py`, `bkng_tjx_pass_data.py`, `list_sec_dir.py` if not needed.
- old one-off QA/research markdown not tied to active WF55/WF40/WF43 closeout, e.g. older `wf23-*`, `wf36-*`, `wf37-*`, `wf41-*` implementation reports after promotion/closure is verified.
- proof-only legacy state files under `tmp/` such as `tmp/state-history-v1.jsonl`, samples, and `tmp/state-history-test.jsonl` once durable `data/state-history/state-history-v1.jsonl` is backed up and current validators do not read the tmp versions.
- large research one-offs from the Consumer Discretionary/BKNG pass, but only if their conclusions have been promoted to the appropriate research/watchlist layer or kept in a dated research archive.
- runtime caches like `scripts/__pycache__/` and `scripts/operators/__pycache__/`, still approval-gated because deletion is destructive.

## Unsafe-to-move artifacts

Do not move in this pass:
- `tmp/portfolio-config.json` and `tmp/portfolio-config-validation.json`.
- All finance-chain root JSON contracts named by `chain_manifest.py`.
- `tmp/run-summary-*.json` and `tmp/run-chain-*.json`.
- `tmp/dashboard-data.json`, `tmp/dashboard-last.json`, `tmp/dashboard-delta.json`, `tmp/dashboard-validation.json`, `tmp/dashboard-acceptance-report.json`.
- `tmp/veritas-command-center.html` and `.last-good.html`.
- workbook CSVs and `tmp/workbook-export-manifest.json`.
- `tmp/deployment-history.json`.
- `tmp/veritas-artifact-index.sqlite`, `tmp/workspace-index.sqlite`, and SQLite sidecars if present.
- `data/state-history/state-history-v1.jsonl`.
- active workflow reports for WF40, WF43, WF54, WF55, and this cron expansion pass.
- `tmp/cron-tasks.json` until its origin/consumer status is understood.
- `tmp/openclaw-config-schema.json` unless replaced by a known fresh schema artifact and references are checked.

## Command Center integration challenge

`dashboard_payload.py` currently builds the decision queue using `_build_decision_queue("post-close")`. That means new summaries may not surface correctly unless the implementation adds explicit payload sections for:
- current run-summary status by window;
- premarket/postclose review brief packet/draft status;
- WF43 state-history row count and latest validation status;
- WF55 probability-readiness gate status;
- weekly PDF readiness/PDF artifact status;
- archive dry-run summary.

Recommendation: add these as **read-only summary cards** sourced from JSON manifests. Do not parse human markdown to drive Command Center state.

## PDF tooling challenge

Available PDF path is single-equity only: `scripts/equity_pdf_report.py` uses ReportLab and ticker visual-report assets. Weekly PDF standards/spec exist, but there is no inspected weekly PDF generator yet.

Implementation lane should therefore:
- first verify `reportlab` availability by compiling/importing or running a minimal generator test;
- create a dedicated weekly PDF generator only after the weekly note/artifact source stack is explicit;
- fail closed if weekly notes contain unresolved placeholders or validation is stale/warning beyond allowed disclosure;
- keep the PDF as presentation/archive, not canonical truth.

## Tests implementation lane must pass

Minimum proof set:
1. `python -m py_compile` for every changed/new script.
2. Targeted unit/regression tests for new path builders, retention classifiers, and authority/lint checks.
3. `python scripts\run_finance_refresh_chain.py morning --dry-run` and relevant dry-runs for changed manifests.
4. `python scripts\run_finance_refresh_chain.py post-close --dry-run`.
5. `python scripts\run_finance_refresh_chain.py sunday --dry-run` if weekly/PDF steps are touched.
6. `python scripts\state_history_capture.py validate`.
7. If appending state history: one controlled append only after fresh post-close summary proof, then validate again.
8. `python scripts\validate_dashboard_state.py --write` after Command Center payload changes.
9. Existing dashboard acceptance test if dashboard payload/rendering changes: `python scripts\test_dashboard_acceptance.py`.
10. Existing authority tests affected by finance vocab changes, at least `python scripts\test_postclose_authority.py` if post-close/daily-exec authority is touched.
11. If retention/archive changes: dry-run archive report with manifest, no moves, and exact protected-file list asserted.
12. Consumer scan for any moved/renamed artifact: exact `rg` on the old path and filename.
13. After cron creation/update: `openclaw cron list`, job detail/preview if available, one safe controlled run where practical, cron run history, and direct artifact inspection.
14. Direct JSON inspection that authority flags remain review-only/false.

## Implementation recommendation

Smallest safe path:
1. Restore/rebuild live finance cron jobs from the known window contracts, not from stale ledger proof.
2. Add new generated markdown under `tmp/reports/` or `tmp/intelligence/` without moving root JSON.
3. Add state-history append/validate as a separate post-close retention job with strict freshness gates.
4. Add weekly PDF readiness first; generate PDF only when note coherence is proven.
5. Add archive dry-run reporting first; apply later only after owner approval and safe-candidate manifest.
6. Surface all new states in Command Center via JSON summary cards, not markdown scraping.
