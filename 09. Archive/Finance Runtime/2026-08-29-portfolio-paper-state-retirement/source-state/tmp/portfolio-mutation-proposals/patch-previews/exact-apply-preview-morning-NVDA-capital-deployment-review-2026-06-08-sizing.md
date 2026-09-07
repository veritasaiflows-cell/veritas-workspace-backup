# Exact Apply Preview - morning:NVDA:capital-deployment-review:2026-06-08

- Generated: `2026-06-08T13:13:01Z`
- Status: **ready_for_scoped_main_session_review**
- Input: `tmp/portfolio-mutation-proposals/semantic-patch-material/morning-NVDA-capital-deployment-review-2026-06-08-sizing.json`
- Authority: dry-run patch preview only; no owner-file writes, no portfolio mutation, no trade/account action.

## Summary

- Requested changes: 1
- Previewed file changes: 1
- Ready for main-session review: True
- Apply ready: False
- Approval artifact required: True

## Stop lines

- This artifact is an exact patch preview only; it does not mutate owner notes or portfolio config.
- Main-session portfolio mutation still requires explicit scoped Randall approval for the proposal id and exact diff.
- A clean preview does not grant owner approval, sizing, sleeve, cash, risk-rule, execution-entitlement, trade, or account authority.
- Phase 4 apply mode must be a separate approval-gated path and must run the post-apply validation chain.

## `03. Portfolio/Portfolio Snapshot.md`

```diff
--- a/03. Portfolio/Portfolio Snapshot.md
+++ b/03. Portfolio/Portfolio Snapshot.md
@@ -121,7 +121,7 @@
 ## WF64 semantic sync notes
 
 - WF64 sizing semantic sync (GOOG): draft_weight=`10%`, sizing_tier=`Tier 1`; source `tmp/portfolio-config.json`; proposal `morning:GOOG:capital-deployment-review:2026-06-08`; draft model only, no external-action sizing authority.
-- WF64 sizing semantic sync (NVDA): draft_weight=`5%`, sizing_tier=`Tier 2`; source `tmp/portfolio-config.json`; proposal `sunday:NVDA:capital-deployment-review:2026-06-07`; draft model only, no external-action sizing authority.
+- WF64 sizing semantic sync (NVDA): draft_weight=`5%`, sizing_tier=`Tier 2`; source `tmp/portfolio-config.json`; proposal `morning:NVDA:capital-deployment-review:2026-06-08`; draft model only, no external-action sizing authority.
 - WF64 sizing semantic sync (VRT): draft_weight=`0%`, sizing_tier=`Formal AI-power tactical challenger planning: Tier 2 starter $200-$350 / 2%-3.5% account-level as conditional proposal context only; 0% active model weight and no execution authority.`; source `tmp/portfolio-config.json`; proposal `sunday:VRT:capital-deployment-review:2026-06-07`; draft model only, no external-action sizing authority.
 - WF64 sizing semantic sync (ETN): draft_weight=`7%`, sizing_tier=`Tier 1`; source `tmp/portfolio-config.json`; proposal `sunday:ETN:capital-deployment-review:2026-06-07`; draft model only, no external-action sizing authority.
 - WF64 sizing semantic sync (GS): draft_weight=`7%`, sizing_tier=`Tier 2`; source `tmp/portfolio-config.json`; proposal `sunday:GS:capital-deployment-review:2026-06-07`; draft model only, no external-action sizing authority.

```
