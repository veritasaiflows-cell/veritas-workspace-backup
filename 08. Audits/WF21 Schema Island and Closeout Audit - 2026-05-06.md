# WF21 Schema Island and Closeout Audit - 2026-05-06

## Scope audited
- Schema Island Fix claim for `tmp/deployment-history.json` and the `scripts/dashboard_payload.py` history write path.
- Database-readiness Gap 1: `schema_version` coverage for the six most-queried artifacts.
- WF21 closeout readiness: packet proof, Phase 3 design-only posture, review-only boundaries, and queue advancement into WF31.
- Finance-surface restoration after the dashboard acceptance fixture mutation.

## Files inspected
- `scripts/dashboard_payload.py`
- `scripts/test_dashboard_acceptance.py`
- `scripts/market_state_refresh.py`
- `scripts/deployment_check.py`
- `scripts/trigger_sheet_refresh.py`
- `scripts/deployment_readiness_surface.py`
- `scripts/validate_dashboard_state.py`
- `tmp/deployment-history.json`
- `tmp/trigger-sheet.json`
- `tmp/deployment-check.json`
- `tmp/market-state.json`
- `tmp/deployment-readiness-surface.json`
- `tmp/portfolio-config.json`
- `tmp/dashboard-validation.json`
- `tmp/dashboard-acceptance-report.json`
- `tmp/run-summary-morning.json`
- `tmp/pipeline-state-consistency.json`
- `tmp/research-automation/intake-packets-20260506-021940.json`
- `tmp/research-automation/intake-packets-20260506-152048.json`
- `06. Playbooks/Research Automation Review Window Cron Design - WF21 Phase 3.md`
- `06. Playbooks/OpenClaw Parallel Pilot Queue.md`
- `06. Playbooks/IC Project Registry.md`
- `06. Playbooks/Project Continuity/Workflow 21 - Recurring Source Bundle and Review Window Pilot.md`

## Top findings
1. **Schema Island Fix is verified for `deployment-history.json`.** The live artifact has 50 entries; every entry now carries `schema_version: 2`, every entry has `generated_at_utc`, and the old history-entry fields `actionState`, `belowStop`, `inBand`, and top-level `generated_at` are absent from history entries and their technical rows. The `dashboard_payload.py` write path now emits snake_case history records while preserving the dashboard DTO input shape.
2. **The broader “only artifact in the system using camelCase” claim must be narrowed.** A recursive tmp scan still finds camelCase/dashboard DTO fields in `tmp/dashboard-data.json` and `tmp/dashboard-last.json`, plus `generated_at` in entry-band artifacts. That is not a regression in `deployment-history.json`, but it means the true closeout claim is: *deployment-history was the schema island fixed this pass; presentation payloads and other legacy generated artifacts are separate contracts and are not globally normalized yet.*
3. **Database-readiness Gap 1 is closed for the six named artifacts.** `schema_version: 1` is now present in `trigger-sheet.json`, `deployment-check.json`, `market-state.json`, `deployment-readiness-surface.json`, `portfolio-config.json`, and `dashboard-validation.json`. The five script-owned artifacts now have `SCHEMA_VERSION = 1` writer constants; `portfolio-config.json` was normalized to a scalar schema version with the prior malformed metadata preserved under `schema_notes` rather than left in the version field.
4. **Finance-surface restoration is clean enough for closeout.** `python scripts\run_finance_refresh_chain.py morning` completed successfully after the `BRK.B`/`LMT` acceptance expectation repair. The live run summary is `status: ok`, `stop_line: false`, with `canonical_note_mutation_allowed: false` preserved.
5. **WF21 should close with a HOLD verdict, not widen.** The two real packet runs are useful, but not strong enough to justify live cron activation yet: post-close produced 4 packets with 1 freshness candidate, 1 thesis-review item, 1 stop-line, and 1 dashboard watch item; Sunday produced 4 packets with 1 archive item, 1 thesis-review item, and 2 stop-lines. The repeated NVDA timing stop-line and Oil/Hormuz verification stop-line prove the fail-closed design works, but also show the lane still needs manual operator review before any recurring schedule goes live.

## Recommended next pass
- Open **WF31 - Runtime Continuity, Memory Indexing, and Scheduled-Proof Hardening** as the active workflow.
- Keep the remaining DB-readiness work as explicitly deferred follow-up, not hidden residue: query abstraction, portfolio static/operational split, state archive, judgment-section extraction, and artifact catalog should be handled in a later bounded DB/retrieval-hardening pass or WF36 follow-up, not smuggled into WF21 closeout.

## Validation run
- `python scripts\run_finance_refresh_chain.py morning` -> completed successfully; warning only: 2 tickers below stop.
- `tmp/dashboard-acceptance-report.json` -> 17 passed / 0 failed / 17 total.
- `python scripts\pipeline_state_consistency_check.py` -> `Status: ok`, `Contradictions: 0`.
- Schema-version check -> six named artifacts all report scalar `schema_version: 1`.
- Deployment-history schema check -> 50 entries, all `schema_version: 2`, all with `generated_at_utc`, zero history camelCase hits for the migrated fields.

## Intentionally deferred items
- Do not activate the WF21 Phase 3 cron design yet. WF21 closes at review-only proof plus design, with HOLD as the verdict.
- Do not normalize dashboard presentation DTO camelCase in this pass; that is a separate dashboard/API contract question and could break the command-center surface if changed casually.
- Do not split `portfolio-config.json` or add `universe_query.py`, `state_archiver.py`, `note_extractor.py`, or `artifact_catalog.py` inside WF21 closeout. Those remain valid DB-readiness recommendations but are not prerequisites for closing the review-window pilot.
- Do not edit canonical finance notes from this closeout. The finance refresh restored generated artifacts only; canonical mutation remains manual and disallowed by the scheduled windows.
