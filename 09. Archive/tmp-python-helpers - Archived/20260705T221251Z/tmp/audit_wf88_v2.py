"""Independent authority audit for WF88 v2 implementation pass."""
import json, sys, hashlib
from pathlib import Path

ROOT = Path(".").resolve()
violations = []
warnings = []

packets = {
    "wf88_os2": "tmp/wf88-os2-control-packet.json",
    "wf88_route_contraction": "tmp/wf88-route-contraction-packet.json",
    "wf88_source_open_classifier": "tmp/wf88-source-open-residue-classifier.json",
    "wf88_delete_readiness": "tmp/wf88-delete-readiness-packet.json",
    "wf87_governor": "tmp/wf87-paper-autonomy-runtime-governor.json",
}

# Forbidden keys that must be false in ALL packets
universal_forbidden = [
    "capital_deployment_approved", "capital_deployment_allowed",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed", "paper_submit_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "portfolio_mutation_allowed", "portfolio_or_canon_mutation_allowed",
    "canon_or_portfolio_mutation_allowed",
    "cash_sizing_risk_mutation_allowed",
    "owner_approval_inferred",
    "model_training_claim_allowed", "model_training_claim_allowed_now",
    "model_performance_claim_allowed_now",
    "customer_or_external_output_allowed", "customer_or_external_delivery_allowed",
    "raw_prompt_or_tool_capture_allowed",
]

# Packet-specific forbidden keys
packet_forbidden = {
    "wf88_os2": ["delete_allowed", "archive_allowed", "move_allowed", "apply_allowed",
                 "cron_schedule_mutation_allowed", "config_auth_runtime_mutation_allowed",
                 "sql_mutation_allowed", "canonical_note_mutation_allowed",
                 "autonomous_paper_submit_allowed"],
    "wf88_route_contraction": ["delete_allowed", "archive_allowed", "move_allowed", "apply_allowed",
                               "cron_schedule_mutation_allowed", "config_auth_runtime_mutation_allowed",
                               "sql_mutation_allowed"],
    "wf88_source_open_classifier": ["delete_allowed", "archive_allowed", "move_allowed", "apply_allowed",
                                     "sql_mutation_allowed", "default_runtime_blocker_authority"],
    "wf88_delete_readiness": ["delete_allowed_without_exact_owner_approval",
                              "archive_allowed_without_exact_owner_approval",
                              "script_deletion_allowed_now", "db_archive_apply_allowed_now",
                              "cron_mutations_allowed_now", "sql_mutation_allowed",
                              "canon_or_portfolio_mutation_allowed"],
    "wf87_governor": ["autonomous_paper_submit_allowed", "autonomous_paper_cancel_allowed",
                      "autonomous_paper_sell_allowed", "cron_direct_execution_allowed",
                      "delete_archive_or_cleanup_apply_allowed", "wf88_learning_owner"],
}

for name, path in packets.items():
    p = ROOT / path
    if not p.exists():
        violations.append(f"{name}: packet missing at {path}")
        continue
    data = json.load(open(p))
    ab = data.get("authority_boundary", data.get("summary", {}))
    
    # Check universal forbidden
    for k in universal_forbidden:
        if k in ab and ab[k] is True:
            violations.append(f"{name}: authority_boundary.{k} = True (MUST be false)")
    
    # Check packet-specific forbidden
    for k in packet_forbidden.get(name, []):
        if k in ab and ab[k] is True:
            violations.append(f"{name}: authority_boundary.{k} = True (MUST be false)")
    
    # Check summary-level
    s = data.get("summary", {})
    if name == "wf87_governor":
        if s.get("execution_allowed") is True:
            violations.append("wf87_governor: summary.execution_allowed = True")
        if s.get("phase_c_autonomous_paper_buy_ready") is True:
            violations.append("wf87_governor: summary.phase_c_autonomous_paper_buy_ready = True")
    if name == "wf88_delete_readiness":
        if s.get("delete_or_archive_performed") is True:
            violations.append("wf88_delete_readiness: summary.delete_or_archive_performed = True")
        if s.get("ready_for_full_deletion_without_owner_approval") is True:
            violations.append("wf88_delete_readiness: ready_for_full_deletion_without_owner_approval = True")

# Check route contraction files actually exist and are narrowed
rc = json.load(open(ROOT / "tmp/wf88-route-contraction-packet.json"))
rc_files = rc.get("route_contraction_files", [])
contracted_count = 0
for f in rc_files:
    fp = ROOT / f["path"]
    if not fp.exists():
        warnings.append(f"Route contraction file missing: {f['path']}")
    else:
        # Check for authority-narrowing markers
        content = fp.read_text(errors="replace").lower()
        has_report_only = any(m.lower() in content for m in f.get("expected_markers", []))
        if has_report_only:
            contracted_count += 1
        else:
            warnings.append(f"Route contraction file {f['path']} missing expected markers: {f.get('missing_markers', [])}")

# Check delete readiness - verify tmp files exist and have zero active references
dr = json.load(open(ROOT / "tmp/wf88-delete-readiness-packet.json"))
tmp_rows = dr.get("tmp_delete_microbatch", {}).get("rows", [])
for r in tmp_rows:
    if r.get("active_reference_count", 0) > 0:
        warnings.append(f"Delete candidate {r['path']} has {r['active_reference_count']} active references")
    if r.get("delete_allowed_now") is True:
        violations.append(f"Delete candidate {r['path']} delete_allowed_now = True")

# Check source-open classifier
soc = json.load(open(ROOT / "tmp/wf88-source-open-residue-classifier.json"))
if soc.get("summary", {}).get("default_runtime_blocker_count", 1) > 0:
    warnings.append(f"Source-open classifier shows {soc['summary']['default_runtime_blocker_count']} default runtime blockers (should be 0)")

# Check WF88 control packet canonical action states
os2 = json.load(open(ROOT / "tmp/wf88-os2-control-packet.json"))
for row in os2.get("canonical_action_state", []):
    auth = row.get("authority", "")
    if "execution" in auth.lower() and "no" not in auth.lower() and "review" not in auth.lower():
        violations.append(f"OS2 action {row.get('id')} authority='{auth}' implies execution")
    if "delete" in auth.lower() and "no" not in auth.lower() and "owner" not in auth.lower():
        violations.append(f"OS2 action {row.get('id')} authority='{auth}' implies delete without owner gate")

print("=" * 80)
print("WF88 V2 INDEPENDENT AUTHORITY AUDIT")
print("=" * 80)
print(f"Packets checked: {len(packets)}")
print(f"Route contraction files checked: {len(rc_files)}")
print(f"Route contraction files narrowed: {contracted_count}/{len(rc_files)}")
print(f"Delete microbatch candidates: {len(tmp_rows)}")
print(f"Universal forbidden fields checked per packet: {len(universal_forbidden)}")
print()

if violations:
    print(f"VIOLATIONS: {len(violations)}")
    for v in violations:
        print(f"  ❌ {v}")
else:
    print("VIOLATIONS: 0")

if warnings:
    print(f"\nWARNINGS: {len(warnings)}")
    for w in warnings:
        print(f"  ⚠️ {w}")
else:
    print("WARNINGS: 0")

print()
print("KEY SUMMARY FIELDS:")
os2s = os2.get("summary", {})
print(f"  WF88 canonical_action_count: {os2s.get('canonical_action_count')}")
print(f"  WF88 route_contraction_contracted: {os2s.get('route_contraction_contracted_or_narrowed_count')}")
print(f"  WF88 source_open_default_runtime_blockers: {os2s.get('source_open_default_runtime_blocker_count')}")
print(f"  WF88 tmp_delete_ready_after_owner_approval: {os2s.get('tmp_delete_ready_after_owner_approval_count')}")
print(f"  WF88 script_deletion_ready_now: {os2s.get('script_deletion_ready_now_count')}")
print(f"  WF88 recommendation_graded_rows: {os2s.get('recommendation_later_outcome_graded_rows')}")
print(f"  WF88 scoreable_decisions: {os2s.get('scoreable_decision_count')}")
print(f"  WF87 execution_allowed: {os2s.get('wf87_execution_allowed')}")
print(f"  WF87 runtime_status: {os2s.get('wf87_runtime_status')}")

if violations:
    sys.exit(1)
else:
    print("\nAUDIT RESULT: CLEAN")
    sys.exit(0)