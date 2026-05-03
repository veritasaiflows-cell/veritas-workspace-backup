---
name: veritas-portfolio-update
description: Orchestrate the operational synchronization of the portfolio and watchlist "Board." Use this to reconcile script artifacts with the note layer, detect stale entry bands, manage earnings-blocker transitions, and ensure coherence across the Trigger Sheet, Technical Entry Sheet, and Portfolio Snapshot.
---

# Veritas Portfolio Update

This skill owns **Operational Coherence.** Its purpose is to ensure that what the scripts see in the market matches what the notes say in the vault. 

It does **not** decide on investment conviction; it ensures the *infrastructure* for that conviction is accurate.

## 1. Operational Input Phase

1. **Refresh the Spine:**
   Run `python scripts/run_finance_refresh_chain.py morning` (or `post-close`).
2. **Ingest Artifacts:**
   - Read `tmp/trigger-sheet.json` (Machine-readiness)
   - Read `tmp/band-proposals.json` (Staleness/Drift detections)
   - Read `tmp/deployment-check.json` (Freshness and ranking)
   - Read `tmp/portfolio-config.json` (The ground-truth configuration)

## 2. Integrity & Staleness Checks

Before updating notes, identify "Operational Friction":
1. **Stale Bands:** Check for `needs_review=true` in `tmp/band-proposals.json`. If bands are >7 days old or price has drifted >5% from midpoint, they MUST be flagged.
2. **Earnings Blockers:** Compare current dates against `tmp/earnings-calendar.json`. If a name is in-band but has earnings within 5 days, it must be marked "Blocked."
3. **Ghost Tickers:** Ensure every name in [[03. Portfolio/Portfolio Snapshot]] and [[02. Markets/Watchlist]] has a corresponding entry in the `Trigger Sheet`.

## 3. The Synchronized Update Order

To prevent internal contradictions, updates must follow this strict sequence:

1. **Phase A: The Technical Foundation**
   Update [[03. Portfolio/Technical Entry and Invalidation Sheet]] using `tmp/band-update-log.txt`. 
   *Rule: Never update a level without updating the `band_last_set` date.*

2. **Phase B: The Execution Layer**
   Update [[03. Portfolio/Deployment Trigger Sheet]].
   - Sync the "Current Price" and "Gap to Band."
   - Explicitly update the "Status" (e.g., `In-Band`, `Extended`, `Blocked`, `Repair`).

3. **Phase C: The Watchlist & Portfolio**
   - Update [[02. Markets/Watchlist]]: Sync prices and trigger status.
   - Update [[03. Portfolio/Portfolio Snapshot]]: Sync current posture and weightings.

4. **Phase D: The Orientation Surface**
   - Update [[01. Dashboards/Executive Brief]]: Summarize the sync (e.g., "3 bands refreshed, 2 names newly earnings-blocked").

## 4. Governance Rules

- **No Silent Sync:** If a ticker is removed from the `portfolio-config.json`, it must be explicitly moved to the `Archive` or `Bench` in the note layer, not just deleted.
- **Manual Overwrite Protection:** If a human has written a specific note (e.g., "Do not buy despite band"), the agent MUST preserve that judgment while updating the quantitative levels.
- **Verification Gate:** Every update MUST conclude with `python scripts/validate_dashboard_state.py --write`.

## Execution Procedure

When Randall asks to "Refresh the board" or "Update the portfolio":
1. `Research`: Run the relevant refresh chain and ingest JSON artifacts.
2. `Audit`: Identify stale bands and earnings blocks. Present a "Sync Plan" to the user.
3. `Action`: Execute the Synchronized Update Order (Phases A-D).
4. `Validation`: Run the dashboard validator and report any remaining "Critical" contradictions.
