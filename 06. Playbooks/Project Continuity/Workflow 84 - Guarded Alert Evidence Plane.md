# Workflow 84 — Guarded Alert Evidence Plane

## Status

Active P0 evidence lane for the alerts-and-recommendations OS. Read-only and fail-closed.

## Objective

Provide the smallest trustworthy evidence plane needed to determine current alert state and support a non-executing recommendation.

## Inputs

- guarded SQL validation: `tmp/finance-sql-canon-access-validation.json`;
- active alert canon: `03. Alerts and Recommendations/`;
- explicit quote proof: `tmp/intraday-alerts/quote-snapshot-proof.json`;
- quote validation: `tmp/intraday-alerts/quote-snapshot-proof-validation.json`;
- alert-state/freshness controller: `tmp/alert-level-freshness-controller.json`.

## Output Contract

For each covered ticker, surface only the evidence needed for review:

- ticker and timeframe;
- evidence/source date and lineage;
- freshness and confidence;
- thesis and material risks;
- alert band and invalidation context;
- uncertainty or suppression reason.

Stale, missing, conflicted, or unverified evidence must lower confidence or block a material recommendation. A successful producer run proves only the checks that its validators cover.

## Current Route

1. `python scripts\finance_sql_canon_access.py --write --validate`
2. `python scripts\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate`
3. `python scripts\workflow_router.py WF84 --answer all --write-capsules --validate`

Primary proof: `tmp/finance-sql-canon-access-validation.json`.

## Acceptance

- guarded SQL passes integrity, authority, scope, lineage, and freshness checks;
- quote proof covers the explicit active alert universe and reports missing/stale observations truthfully;
- the alert controller validates and emits deterministic review states;
- no retired finance producer is required by this route;
- all output remains evidence and review context, never approval.

## Phase 3 And Phase 4 Alignment - 2026-09-29

Aligned at Randall's direction (2026-09-29: "align all work done in phase 3 and phase 4 to wf85 and wf84"):

- **Phase 3 / dynamic entitlement:** the standing provider policy (approved 2026-09-02) governs external evidence collection over the 32-name guarded-SQL Tier A+B scope with a daily aggregate call budget (worst-case reservation, settle-to-actual), fail-closed overflow with a member-enumerating debt artifact, and no scope truncation. First bounded run: 64/64 provider attempts, zero failures; `ITA` returned no analyst data (ETF data-availability gap, not a defect), and its artifact remains quarantined at `placeholder_manual_required`. Phase 3D observed-entitlement coverage reports quote/session, reference-level, lineage, freshness, analyst, card, and queue evidence through one frozen source registry (`tmp/tier-entitlement-v091-phase3d-observed-coverage.json`); undefined recency and absent queue owner remain visibly non-observed. 3G scheduler cutover is still open pending a separate owner decision.
- **Phase 4 / future guarded mutation path:** the tier transaction writer (P4-3a, QA-accepted, committed `1646a4cd`) and the reference-level onboarding writer (P4-3b, QA-accepted, committed `fdae1df1`, not pushed) are the only sanctioned future mutation path for the canon this plane reads. Both are production-capable but blocked: no production journal, decision directory, or `phase4-tier-cutover.json` exists, and Randall alone creates the cutover approval. Whole-DB `--rollback` remains hermetic-only.
- **Known inverse limit:** a captured row-level inverse CAS-refuses (fail-closed) after any later canon write touches its rows — including another onboarding or the weekly g6 renewal — so undo is practical only until the next canon write.
- **Recurring canon writes today:** the weekly g6 renewal and the Sat 10-03 Option B renewal (clears 31 stale labels; scope-change stop rule active) remain the only standing writes; Stage 2 weekly screening (`weekly_screening_refresh.py`, cron `e6532249`) is read-side evidence for promotion review candidates.
- **No authority change:** this evidence route remains read-only and fail-closed. Phase 3/4 add no canon-write, approval, capital, account, or execution authority to WF84.

## Stop Lines

- No maintained holdings or simulated account state.
- No canon write from this evidence route.
- No capital, account, order, money-movement, or execution authority.
- No stale-context suppression to manufacture a green status.

Last updated: 2026-09-29 Phoenix / 2026-09-30 UTC.
