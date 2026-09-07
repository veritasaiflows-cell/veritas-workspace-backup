# Cron Expansion Orchestration Handoff

## User approval
Randall approved continuing in orchestration mode on 2026-05-10 18:00 MST.

## Requested outcomes
1. Rebuild/reprove finance cron jobs.
2. Add pre-market AI-reviewed brief artifact.
3. Add weekly PDF intelligence brief.
4. Add post-close state-history/outcome append cadence.
5. Add archive/retention job.
6. Include these summaries in Command Center refreshed as part of the chain for easy access.
7. Improve workspace cleanliness; explain and fix the generated markdown-vs-json organization problem without breaking script contracts.

## Hard boundaries
- No config/auth/external-channel/plugin/browser/network mutation.
- No canonical finance note mutation unless an existing bounded workflow explicitly already allows it.
- No portfolio/deployment state mutation, trades, or owner approval inference.
- All finance outputs are review-support only.
- WF55 probability-readiness gate remains active; no probability/modeling/calibration language until prerequisites exist.
- WF43 durable history has only 2 rows and no realized-outcome update flow.

## Current live cron truth
`cron list` currently shows only:
- `d2cbac10-f1fb-4060-8445-cb13f3dfc6be` Security Audit - Daily Bounded Hardening, daily 17:10 America/Phoenix.

Historical notes mention finance cron jobs, but live cron state wins. Finance cron jobs need rebuild/reproof.

## Current workflow truth
- Active workflow: WF55 probability-readiness report / validator gate.
- WF40 stays residual scheduled-proof watch while WF55 remains active.
- WF43 durable-proof-passed: `data/state-history/state-history-v1.jsonl` has 2 validated rows.
- WF52 bounded Event Calendar apply path implemented.
- WF53 sector/correlation v1 implemented / QA accepted.
- WF54 ticker monitoring analytics v1 implemented; `outcome_analytics_ready=false`.

## Existing relevant scripts/artifacts
- Finance chain: `scripts/run_finance_refresh_chain.py`, `scripts/chain_manifest.py`.
- Morning chain already produces `tmp/premarket-snapshot.json`, `tmp/premarket-brief-input.json`, `tmp/daily-review-objects-morning.json`, `tmp/sector-expansion-board.json`, `tmp/ticker-monitoring-performance.json` standalone.
- Sunday chain produces `tmp/weekly-macro-snapshot.json`, `tmp/weekly-intelligence-brief.json`, `tmp/run-summary-sunday.json`.
- State history: `scripts/state_history_capture.py validate|sample|append`.
- Command Center: inspect `scripts/generate_dashboard.py`, `scripts/dashboard_payload.py`, and existing dashboard data artifacts.
- PDF skill exists as `veritas-pdf-brief` but actual PDF generation path may require inspection; do not assume libraries are installed.

## Acceptance target
Produce the smallest safe implementation path. Prefer new scripts/artifacts under a clean generated-artifact structure for new human-facing outputs, while preserving existing `tmp/*.json` contracts unless all consumers are patched.

Recommended artifact organization posture unless inspection proves better:
- Keep machine-consumed live JSON at existing `tmp/*.json` paths for compatibility.
- Put new human-facing generated reports under `tmp/reports/` or `tmp/intelligence/` with dated names or stable latest aliases.
- Put archive manifests under `tmp/archive/` or `09. Archive/generated-artifacts/` only if safe.
- Do not bulk-move existing artifacts in this pass.

## Required proof
At minimum:
- Python compile for any changed/new scripts.
- Targeted tests or direct script runs for new artifacts.
- `python scripts\state_history_capture.py validate` for WF43 append cadence.
- `openclaw cron list` after cron creation/update.
- One safe controlled run where practical, or explicit reason why not.
- Direct inspection that authority flags remain review-only/false.

## Summary question to answer
Why use `tmp/` for markdown? Answer: because generated markdown is still generated output; but for operator cleanliness, new human-facing markdown should use a dedicated subfolder instead of mixing with machine JSON at root. Existing root `tmp/*.md` should be archived/cleaned only via a retention job with manifests/hashes and consumer scan.
