# Workflow 45 - Shared Stale Source Fail-Soft Classifier

## Objective
- Build a shared machine-readable classifier for fresh/current/stale/partial/missing/contradictory/manual-dependency source states.
- Make downstream surfaces degrade honestly without presenting fake-green states.

## Current State
- Queued from `08. Audits/Stale Source Fail-Soft Hardening Plan - 2026-05-09.md`.
- Existing dashboard freshness logic is useful but spread across dashboard/run-summary/readiness surfaces.
- WF36 artifact SQLite index remains manual-only until this fail-soft contract is designed and proven.

## Last Meaningful Progress
- Finance chain now runs cleanly after XOM repair-mode and dashboard validator alignment.
- Audit plan identified `dashboard_core.py`, `run_summary_refresh.py`, `deployment_readiness_surface.py`, `daily_review_objects.py`, `market_intelligence_event_router.py`, and `artifact_index.py` as the main integration surfaces.
- 2026-05-09 bounded WF45 slice added `scripts/source_freshness_classifier.py` and `scripts/test_source_freshness_classifier.py`.
- Classifier now distinguishes `fresh`, `current`, `manual_dependency`, `partial`, `stale`, `contradictory`, and `missing`, with mutation/capital authority fail-closed.
- Bounded consumers now include dashboard source assessments, dashboard payload/validation, market-intelligence packets, and daily-review packets. Live validation can be integrity-clean while source trust is still `partial / review_required`.
- Main-session QC passed py_compile, direct classifier tests, dashboard validation write, market-intelligence router, daily-review objects, both adjacent tests, artifact-index tests, and direct JSON inspection.

## Outstanding
- Prove or wire artifact-index metadata so a fresh SQLite rebuild cannot hide stale upstream finance artifacts before any chain integration is considered.
- Propagate source-freshness blocks into run-summary and deployment-readiness surfaces in a later bounded slice if needed.
- Decide stable stale thresholds by source family only after observing repeat runs; do not overfit thresholds from one weekend run.

## Blockers / Trust Gaps
- No chain integration for `scripts/artifact_index.py` until classifier behavior is further proven and retrieval outputs visibly carry source freshness / provenance.
- Clean dashboard validation must not be translated into clean source trust if upstream artifacts are stale, manual, partial, or contradictory.
- Canonical note mutation and capital deployment remain owner-gated.

## Next Action
- Treat WF45 Slice A as implemented/QC-passed. Next safe follow-up is either artifact-index freshness metadata hardening or run-summary/deployment-readiness propagation, but keep chain integration blocked.

## Key Files
- `08. Audits/Stale Source Fail-Soft Hardening Plan - 2026-05-09.md` - source plan.
- `scripts/dashboard_core.py` - current source assessment logic.
- `scripts/dashboard_payload.py` - dashboard trust payload consumer.
- `scripts/dashboard_validation.py` - contradiction/warning validator.
- `scripts/run_summary_refresh.py` - run summary trust/finalizer owner.
- `scripts/deployment_readiness_surface.py` - deployment readiness consumer.
- `scripts/artifact_index.py` - derived retrieval index, currently manual-only.
- `06. Playbooks/Project Continuity/Workflow 36 - Workspace Retrieval Index and SQLite Knowledge Layer.md` - SQL boundary.

## Acceptance Gate
- [passed] Classifier contract distinguishes fresh/current/stale/partial/missing/contradictory/manual_dependency with explicit degradation behavior.
- [passed] Tests prove stale/missing/partial/manual source states fail soft or fail closed as appropriate.
- [pending follow-up] Artifact index output or procedure references classifier state before any scheduled/chain consumption.
- [passed] No canonical finance note mutation, deployment mutation, or owner approval inference is introduced.

## Automation / Refresh Path
- Starts as local script/test contract only.
- Later consumers may embed classifier blocks in generated artifacts after proof.
