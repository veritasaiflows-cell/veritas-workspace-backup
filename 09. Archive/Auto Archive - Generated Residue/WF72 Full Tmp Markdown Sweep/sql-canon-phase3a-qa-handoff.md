# SQL Canon Phase 3A Independent QA / Challenge Handoff

Generated: 2026-05-23 14:38 MST
Mode: Spawn read-only / distinct-output QA
Runtime budget: 2400 seconds

## Objective
Independently challenge the Phase 3A SQL canon/cache architecture and dry-run promotion artifacts before any Phase 3B or approved write-path design.

## Current truth
- Phase 2 SQL/Markdown reconciliation is report-only and validated clean.
- Phase 3A currently emits dry-run artifacts only; SQL is not canon and no SQL/Markdown/portfolio writes are authorized.
- Current Phase 3A dry-run candidates are limited to NVDA `post_earnings_review_confirmed` and `earnings_lifecycle_status`.
- Main-session preliminary review found no blocking authority breach, but noted cosmetic Markdown proof rendering (`#### NVDA`) and the need for independent challenge before any write-path work.

## Read first
1. `tmp/sql-canon-phase2-phase3-plan.md`
2. `tmp/sql-canon-field-registry.json`
3. `tmp/sql-markdown-reconciliation.json`
4. `tmp/sql-reconciliation-validation.json`
5. `tmp/sql-canon-phase3a-architecture.json`
6. `tmp/sql-canon-phase3a-dry-run-promotion.json`
7. `tmp/sql-canon-phase3a-validation.json`
8. `scripts/artifact_index.py` around Phase 2/Phase 3A functions
9. `scripts/test_artifact_index.py` Phase 2/Phase 3A tests

## Do not touch
- Do not edit canonical Markdown finance notes.
- Do not create SQL canon/cache tables or a new database.
- Do not apply portfolio/canon mutations.
- Do not infer owner approval or execution authority.
- Do not move workflow queue state.

## Challenge questions
1. Does Phase 3A preserve the Phase 2 boundary: review-only, non-canon, non-apply?
2. Are all promotion candidates clean Phase 2 matches with source lineage, freshness timestamp, owner/mirror note proof, and registry owner?
3. Are disallowed field families blocked, especially entry bands, weights, cash, sizing, sleeves, sector posture, owner approval, risk rules, account/brokerage/trade/paper/live state, and credentials?
4. Could any wording in JSON/Markdown imply SQL canon ownership, owner approval, readiness, or write authority?
5. Is the future storage recommendation safe against proof-cockpit rebuild/reset?
6. Are tests and validators strong enough, or do they allow false-green behavior?
7. Are there hidden downstream consumers that would misread these dry-run artifacts?

## Required deliverable
Write final QA findings to `tmp/sql-canon-phase3a-qa-findings.md`.

Required sections:
- review scope
- files inspected
- blocking findings
- non-blocking findings
- proof assessment
- recommended next repair

## Stop lines
Stop and report if:
- any artifact implies SQL is canon or write authority exists;
- any candidate lacks source lineage/freshness/note proof;
- any excluded field family is promotable;
- the durable storage design would be erased by `artifact_index.py rebuild`;
- consumer behavior could change without parity proof.
