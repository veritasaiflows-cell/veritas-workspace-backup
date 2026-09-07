# Exact Apply Preview - post-close:GS:capital-deployment-review:2026-05-17

- Generated: `2026-05-17T05:50:28Z`
- Status: **ready_for_scoped_main_session_review**
- Input: `tmp/portfolio-mutation-proposals/semantic-patch-material/post-close-GS-capital-deployment-review-2026-05-17-entry_band.json`
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

## `03. Portfolio/Execution Board.md`

```diff
--- a/03. Portfolio/Execution Board.md
+++ b/03. Portfolio/Execution Board.md
@@ -308,6 +308,7 @@
 - Support: **924** (20-day / refreshed band top zone), then **873** (50-day)
 - Resistance: current extension zone above the refreshed band top at **923.51**
 - Preferred entry band: **894.64 to 935.77** (auto-applied band maintenance 2026-05-15; KELTNER_MA_CONSTRAINED / NEAR_BAND)
+- WF64 entry-band semantic sync: config low/high/stop = **894.64 to 935.77 / stop 866.76**; source `tmp/portfolio-config.json`; proposal `post-close:GS:capital-deployment-review:2026-05-17`; workspace maintenance only, no external-action authority.
 - Reference band: **888.11 to 926.22** / reference stop **860.36** (weekly reference refresh 2026-05-12; KELTNER_MA_CONSTRAINED / NEAR_BAND; data as of 2026-05-12)
 - Explicit stop: **866.76**
 - Invalidation logic: loses the 50-day and breaks the uptrend; do not chase while price remains above the refreshed band.

```
