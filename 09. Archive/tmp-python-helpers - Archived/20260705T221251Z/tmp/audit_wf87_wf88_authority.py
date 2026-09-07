"""Independent authority audit for WF87/WF88 first slice."""
import json, sys

violations = []

# WF87
wf87 = json.load(open("tmp/wf87-paper-autonomy-runtime-governor.json"))
ab87 = wf87.get("authority_boundary", {})
forbidden_true_87 = [
    "capital_deployment_approved", "trade_or_execution_approved",
    "paper_or_live_execution_allowed", "autonomous_paper_submit_allowed",
    "autonomous_paper_cancel_allowed", "autonomous_paper_sell_allowed",
    "owner_approval_inferred", "brokerage_or_account_action_allowed",
    "money_movement_allowed", "portfolio_or_canon_mutation_allowed",
    "cash_sizing_risk_mutation_allowed", "cron_direct_execution_allowed",
    "delete_archive_or_cleanup_apply_allowed", "wf88_learning_owner",
]
for k in forbidden_true_87:
    v = ab87.get(k)
    if v is True or v == "true":
        violations.append(f"WF87 authority_boundary.{k} = {v} (MUST be false)")

# Check summary-level fields
s87 = wf87.get("summary", {})
if s87.get("execution_allowed") is True:
    violations.append("WF87 summary.execution_allowed = True (MUST be false)")
if s87.get("phase_c_autonomous_paper_buy_ready") is True:
    violations.append("WF87 summary.phase_c_autonomous_paper_buy_ready = True (MUST be false)")

# WF88
wf88 = json.load(open("tmp/wf88-os2-control-packet.json"))
ab88 = wf88.get("authority_boundary", {})
forbidden_true_88 = [
    "delete_allowed", "archive_allowed", "move_allowed", "apply_allowed",
    "cron_schedule_mutation_allowed", "config_auth_runtime_mutation_allowed",
    "sql_mutation_allowed", "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed", "cash_sizing_risk_mutation_allowed",
    "paper_or_live_execution_allowed", "autonomous_paper_submit_allowed",
    "brokerage_or_account_action_allowed", "money_movement_allowed",
    "customer_or_external_output_allowed", "model_training_claim_allowed",
    "raw_prompt_or_tool_capture_allowed", "owner_approval_inferred",
]
for k in forbidden_true_88:
    v = ab88.get(k)
    if v is True or v == "true":
        violations.append(f"WF88 authority_boundary.{k} = {v} (MUST be false)")

# Check summary-level fields
s88 = wf88.get("summary", {})
if s88.get("model_performance_claim_allowed_now") is True:
    violations.append("WF88 summary.model_performance_claim_allowed_now = True (MUST be false)")

# Check canonical action states for authority leaks
for row in wf88.get("canonical_action_state", []):
    auth = row.get("authority", "")
    if "execution" in auth.lower() and "no" not in auth.lower() and "review" not in auth.lower():
        violations.append(f"WF88 action {row.get('id')} authority='{auth}' looks like execution authority")
    if "delete" in auth.lower() and "no" not in auth.lower():
        violations.append(f"WF88 action {row.get('id')} authority='{auth}' looks like delete authority")

# Check responsibility split doesn't put learning under WF87
rs = wf87.get("responsibility_split", {})
wf87_owns = rs.get("wf87_owns", [])
for item in wf87_owns:
    if "learning" in item.lower() or "cleanup" in item.lower() or "experiment" in item.lower():
        violations.append(f"WF87 owns '{item}' - should be WF88")

wf88_owns = rs.get("wf88_owns", [])
for item in wf88_owns:
    if "paper" in item.lower() and "autonomy" in item.lower():
        violations.append(f"WF88 owns '{item}' - should be WF87")
    if "brokerage" in item.lower() or "execute" in item.lower():
        violations.append(f"WF88 owns '{item}' - WF88 must not own execution")

if violations:
    print("VIOLATIONS FOUND:")
    for v in violations:
        print(f"  ❌ {v}")
    sys.exit(1)
else:
    print("AUTHORITY AUDIT CLEAN: 0 violations")
    print(f"  WF87 forbidden fields checked: {len(forbidden_true_87)}")
    print(f"  WF88 forbidden fields checked: {len(forbidden_true_88)}")
    print(f"  WF87 responsibility split: {len(wf87_owns)} WF87 items, {len(wf88_owns)} WF88 items")
    print(f"  WF88 canonical action rows: {len(wf88.get('canonical_action_state', []))}")
    sys.exit(0)