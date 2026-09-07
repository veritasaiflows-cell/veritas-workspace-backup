from __future__ import annotations

from pathlib import Path
import json
import re

ROOT = Path(r"C:\Users\Veritas\.openclaw\workspace")

# 1) Patch chain_manifest.py to insert WF70/WF66 evidence spine builder/validator after reconciliation packets.
path = ROOT / "scripts" / "chain_manifest.py"
text = path.read_text(encoding="utf-8")
needle = '{"script": "fundamental_ir_reconciliation_packets.py", "args": ["--write"], "category": "fundamentals", "expected_outputs": ["tmp/fundamental-ir-reconciliation-packets.json", "tmp/fundamental-ir-reconciliation-packets.md"], "depends_on": ["official_ir_capture_validator.py"], "recovery_posture": "fail_chain"},\n'
insert = needle + '            {"script": "wf70_wf66_official_evidence_spine.py", "args": [], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine.json", "tmp/wf70-wf66-official-evidence-spine.md", "tmp/wf70-wf66-official-evidence-spine-validation.json", "tmp/wf70-wf66-official-evidence-spine-validation.md"], "depends_on": ["fundamental_ir_reconciliation_packets.py"], "recovery_posture": "fail_chain"},\n            {"script": "wf70_wf66_official_evidence_spine.py", "args": ["--validate-only"], "category": "validation", "expected_outputs": ["tmp/wf70-wf66-official-evidence-spine-validation.json", "tmp/wf70-wf66-official-evidence-spine-validation.md"], "depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},\n'
if '"script": "wf70_wf66_official_evidence_spine.py"' not in text:
    text = text.replace(needle, insert)
    text = text.replace('"depends_on": ["fundamental_ir_reconciliation_packets.py"], "recovery_posture": "fail_chain"},\n            {"script": "official_earnings_bridge.py"', '"depends_on": ["wf70_wf66_official_evidence_spine.py"], "recovery_posture": "fail_chain"},\n            {"script": "official_earnings_bridge.py"')
    path.write_text(text, encoding="utf-8")

# 2) Create machine-readable cron authority contract.
contract = {
    "status": "active_contract",
    "adopted_at_mst": "2026-05-23 23:57",
    "owner": "Veritas main session + Cron Automation Manager",
    "source_approval": "Randall approved broader cron automation authority for cleanups, small implementations, recurring workflows, and financial notes/canon auto-update on 2026-05-23 23:57 MST.",
    "global_boundaries": {
        "live_trading_allowed": False,
        "account_or_money_movement_allowed": False,
        "paper_execution_allowed_only_through_wf67": True,
        "config_auth_channel_service_runtime_mutation_allowed": False,
        "deletes_allowed": False,
        "owner_approval_inference_allowed": False,
        "external_actions_allowed": False
    },
    "tiers": [
        {"tier":"T0","name":"Observe/report","cron_can":"status, warnings, run summaries, ledger rows","cron_cannot":"mutate notes/canon/archive","proof":"cron history + visible proof surface"},
        {"tier":"T1","name":"Review-only artifact/dashboard refresh","cron_can":"write tmp packets, dashboards, reports, SQL proof/index/staging","cron_cannot":"canonical/portfolio mutation or approval language","proof":"fresh artifact + validators + hard-false authority flags"},
        {"tier":"T2","name":"Patch proposal / semantic preview","cron_can":"generate canonical-note patch proposals, portfolio proposals, exact previews, verifier reports","cron_cannot":"apply patches or imply eligibility","proof":"proposal/schema/scope/freshness/authority validators"},
        {"tier":"T3","name":"Main-session bounded freshness/status sync","cron_can":"wake/handoff main session to inspect artifacts and apply bounded freshness/status sync","cron_cannot":"unattended direct cron note write","proof":"worker artifact + completed current-window run + main-session inspection + audit"},
        {"tier":"T4","name":"Exact gated workspace portfolio/canon maintenance","cron_can":"generate proposal/verifier; existing narrow applies only where already approved","cron_cannot":"broaden direct apply, trade/account/cash/risk/execution changes","proof":"scoped proposal + diff hash + approval artifact + backups + post-apply validation"},
        {"tier":"T4A","name":"Future narrow cron-direct maintenance candidate","cron_can":"nothing now; inactive placeholder","cron_cannot":"any current direct apply","proof":"future exact category approval + repeated scheduled proof + lock + rollback + QA"},
        {"tier":"T5","name":"Bounded auto-archive movement","cron_can":"archive-only moves under approved policy","cron_cannot":"delete or move protected/canonical/current-window/script/skill/config files","proof":"clean reference check + manifest/log + main-session report"},
        {"tier":"TX","name":"Blocked","cron_can":"nothing","cron_cannot":"live/paper-outside-WF67, credentials, config/service, deletes, approval inference","proof":"separate explicit approval required"}
    ],
    "financial_notes_and_canon": {
        "cron_default": "T1/T2 generate and validate artifacts/proposals/previews",
        "main_session_sync": "T3 bounded freshness/status sync after inspection",
        "gated_apply": "T4 only through exact WF64/WF56-style gates or existing narrow approved helpers",
        "cron_direct_apply": "T4A inactive unless future exact category promotion passes repeated proof",
        "standing_categories": ["entry_band", "earnings_state", "ticker_state", "sleeve", "sizing", "sector_posture"],
        "direct_apply_existing_narrow_helpers": ["event_calendar_apply.py --apply", "auto_apply_entry_band_maintenance.py --apply", "canon_volatile_execution_board_sync.py --apply --strict-exit"]
    }
}
(ROOT / "tmp" / "cron-automation-authority-contract.json").write_text(json.dumps(contract, indent=2), encoding="utf-8")

# 3) Create markdown contract summary.
lines = ["# Cron Automation Authority Contract", "", "Status: `active_contract`", "", "## Tiers", ""]
for t in contract["tiers"]:
    lines.append(f"- **{t['tier']} - {t['name']}**: can {t['cron_can']}; cannot {t['cron_cannot']}; proof: {t['proof']}.")
lines.extend(["", "## Financial notes and canon", "", "- Cron default: T1/T2 proposal, preview, verifier, and reporting.", "- Main-session sync: T3 bounded freshness/status sync after proof inspection.", "- Gated apply: T4 exact WF64/WF56-style apply or existing narrow approved helpers only.", "- T4A cron-direct canon apply is inactive until separately promoted with repeated proof, lock, rollback, audit, and QA.", "", "## Hard no", "", "No live trading/account/money movement, no paper execution outside WF67, no config/auth/channel/service/runtime mutation, no deletes, no external actions, no owner-approval inference."])
(ROOT / "tmp" / "cron-automation-authority-contract.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

print("implemented staged files")
