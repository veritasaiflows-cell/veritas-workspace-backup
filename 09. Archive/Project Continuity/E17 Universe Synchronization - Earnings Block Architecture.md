# E17 Universe Synchronization - Earnings Block Architecture

## Purpose
Define the explicit semantics for the earnings-block window to prevent long-dated earnings from incorrectly contaminating execution states (Phase 3 Sub-Pass 1).

## The Contamination Map (Current State)
Currently, earnings blocking is over-broad, time-blind, and inappropriately located.

1. **Source of Truth:** `tmp/portfolio-config.json` tags names with `"earnings_policy": "block_pre_earnings"` (e.g., GOOG, MSFT, AMZN).
2. **The Leakage Point:** `scripts/technical_refresh.py` blindly converts this policy into a permanent `earnings_blocked = True` boolean in `tmp/technical-refresh.json`, without any awareness of the actual earnings date.
3. **Execution Contamination:** `scripts/deployment_check.py` inherits `earnings_blocked = True` unconditionally and forces the `action_state` to `"BLOCKED"` regardless of distance to earnings.
4. **Surface Contamination:** 
   - `scripts/trigger_sheet_refresh.py` classifies them as "blocked".
   - `scripts/dashboard_payload.py` categorizes them as "Earnings Pending".
   - `scripts/workbook_export.py` labels them as "Blocked by catalyst".

As a result, a ticker like MSFT is permanently blocked for 90 days out of the quarter, even when earnings are months away.

## The New Earnings-Block Contract
An earnings block MUST only activate if both of the following conditions are met:
1. The ticker's `portfolio-config.json` explicitly states `"earnings_policy": "block_pre_earnings"`.
2. The ticker's `next_earnings_date` (from `earnings-calendar.json`) is within **14 calendar days** of the current `last_trading_day`.

## Architectural Realignment
The technical layer (`technical_refresh.py`) should NOT be responsible for determining earnings-based deployment blockages. It is a technical-sourcing script, not an execution orchestrator.

**Remediation Steps for Sub-Pass 2:**
1. **Strip from Technical:** Remove `build_earnings_blocked` and the `earnings_blocked` boolean entirely from `scripts/technical_refresh.py` and `tmp/technical-refresh.json`.
2. **Empower Deployment Check:** Inject `tmp/earnings-calendar.json` and `tmp/portfolio-config.json` directly into `scripts/deployment_check.py`.
3. **Calculate Dynamically:** `deployment_check.py` will calculate the exact distance to earnings and apply the 14-day window contract, setting the state to `BLOCKED` only when mathematically valid.
4. **Align Downstream:** Update `dashboard_payload.py`, `workbook_export.py`, and `trigger_sheet_refresh.py` to stop looking for a raw `earnings_blocked` boolean on the technical record, and instead rely cleanly on the `"BLOCKED"` action state emitted by the fixed deployment check.
