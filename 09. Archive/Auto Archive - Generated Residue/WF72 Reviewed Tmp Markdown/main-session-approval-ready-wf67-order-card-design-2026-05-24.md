# Main-Session Approval-Ready WF67 Order Card Design

Generated: 2026-05-25T02:58:28Z

## Core answer

Main session should be allowed to choose and prepare proposed paper-order terms as advice, but final paper execution remains blocked until Randall approves the exact request artifact/order card after dry-run and guard proof.

## Workflow
1. **capital_alert** ? VRT/CME/PH/etc. proposal-ready alert with fresh quote, band, stop, starter/target sizing, blocker, and risk note. Authority: review/proposal only.
2. **main_session_order_decision_card** ? Main session selects proposed ticker/side/notional-or-qty/order-type/TIF/limit based on sizing/risk rules and writes an approval-ready order card. Authority: recommended terms only; not approval.
3. **wf67_request_artifact** ? Generate exact WF67 paper request artifact from the order card. Authority: artifact generation only.
4. **preapproval_dry_run_and_guard** ? Run dry run and paper/live isolation guard validation. If guard requires kill switch, expected status is approval_pending_or_kill_switch_missing, not executable. Authority: proof only.
5. **randall_final_approval_card** ? Ask Randall to approve the exact package: ticker, side, qty/notional, type, TIF, limit if any, max notional/loss, source artifacts, guard status, and kill-switch requirement. Authority: human decision point.
6. **execution_window_only_after_approval** ? After exact approval, create fresh short-lived kill switch, rerun guard validation, then execute through WF67 wrapper only if clean. Authority: paper-only execution under WF67; live still blocked.

## Implementation gap

Current wf67_advisor_paper_request_generator.py builds from WF68 advisor packets. To make main session fully capable, add or extend a request generator that accepts a main-session order decision card/capital recommendation artifact directly, then emits the WF67 request artifact for dry-run/guard proof.

## Boundary

Main session may recommend exact paper-order terms and prepare proof. It may not infer approval or execute. Kill switch + execution happen only after Randall approves the exact package. Live trading remains blocked.
