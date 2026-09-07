# WF72 dashboard handoff SQL adoption proof

- Generated: 2026-05-23T01:55:05Z
- Status: ok
- SQL boundary: `derived_review_only_index_not_canon_not_apply`
- Semantic result: existing handoff proof states preserved; SQL adds provenance/health metadata only.
- State counts: `{"PENDING_FIRST_PROOF": 4, "PROVED": 1}`
- Proof: py_compile, artifact_index_tests_passed, artifact_index validate ok, dashboard_handoff_sql_tests_passed.

## Handoff rows

| Lane | State | Source | SQL match | SQL status |
|---|---|---|---:|---|
| weekday_research | PROVED | `tmp/research-freshness-opportunity-review.json` | False | None |
| morning | PENDING_FIRST_PROOF | `tmp/run-summary-morning.json` | True | blocked |
| post_close | PENDING_FIRST_PROOF | `tmp/run-summary-post-close.json` | True | critical |
| sunday_weekly | PENDING_FIRST_PROOF | `tmp/weekly-intelligence-brief.json` | False | None |
| sunday_research | PENDING_FIRST_PROOF | `tmp/sunday-research-review.json` | False | None |
