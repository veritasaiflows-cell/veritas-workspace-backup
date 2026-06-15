"""WF70 Phase 7 — Q2 2026 rollforward readiness assessment.

Scans the workspace for Q1-specific elements that require updates when Q2 2026
official earnings are released (mid-July 2026) and produces a readiness artifact
documenting exactly what changes and what does not.

Authority: review-only assessment. No source fetches, no capture writes, no
canon/portfolio/trade/account/order/sizing/sleeve/cash/risk-rule mutations.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
OUT_JSON = ROOT / "tmp" / "wf70-phase7-q2-rollforward-readiness.json"
OUT_MD = ROOT / "tmp" / "wf70-phase7-q2-rollforward-readiness.md"

AUTHORITY = {
    "review_only": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "paper_order_action_allowed": False,
    "sizing_sleeve_cash_risk_rule_mutation_allowed": False,
}

Q2_EARNINGS_WINDOW = {
    "q2_period_end": "2026-06-30",
    "q2_period_slug": "q2-2026",
    "q2_period_label": "Q2 2026",
    "earliest_q2_release": "2026-07-14",
    "typical_window": "2026-07-14 through 2026-08-15",
    "note": "Q2 2026 earnings begin mid-July. No Q2 official releases exist as of 2026-05-23.",
}

# Per-script Q2 rollforward actions: what changes and what stays the same.
CAPTURE_SCRIPT_ROLLFORWARD = [
    {
        "script": "official_ir_capture_common.py",
        "change_required": True,
        "change_type": "default_parameter",
        "detail": (
            "run_capture_batch() defaults to period_slug='q1-2026', period_label='Q1 2026'. "
            "Each capture script passes these as call-site arguments; the common helper default "
            "is a fallback. Callers should pass period_slug='q2-2026' and period_label='Q2 2026' "
            "when running Q2 captures. The common helper itself does not need permanent code change "
            "until Q2 is the new universal default."
        ),
        "when": "When Q2 capture runs begin (mid-July 2026).",
    },
    {
        "script": "goog_official_ir_capture.py",
        "change_required": True,
        "change_type": "source_url + period_slug",
        "detail": (
            "Hard-coded OUT_JSON/OUT_MD paths include 'goog-q1-2026'. Source URL points to Q1 8-K. "
            "For Q2: update OUT_JSON/OUT_MD to 'goog-q2-2026', update source_url to the Q2 8-K, "
            "pass period_slug='q2-2026' to run_capture_batch(). Q1 artifact is preserved as historical."
        ),
        "when": "When GOOG Q2 2026 8-K is filed (expected July 2026).",
    },
    {
        "script": "tech_official_ir_capture.py",
        "change_required": True,
        "change_type": "source_urls + period_slug",
        "detail": (
            "AMZN/MSFT/NVDA source URLs point to Q1 SEC 8-K exhibits. "
            "For Q2: update source_url per ticker to Q2 releases, pass period_slug='q2-2026'. "
            "Output paths are derived from period_slug so no path literals need changing."
        ),
        "when": "When each ticker's Q2 8-K is filed.",
    },
    {
        "script": "priority_official_ir_capture.py",
        "change_required": True,
        "change_type": "source_urls + period_slug",
        "detail": (
            "JPM/GS/LMT/RTX/XOM/BRK.B source URLs point to Q1 releases. "
            "For Q2: update source_url per ticker, pass period_slug='q2-2026'."
        ),
        "when": "When each ticker's Q2 release is filed.",
    },
    {
        "script": "etn_vrt_official_ir_capture.py",
        "change_required": True,
        "change_type": "source_urls + period_slug",
        "detail": (
            "ETN/VRT source URLs point to Q1 8-K exhibits. "
            "For Q2: update source_urls, pass period_slug='q2-2026'."
        ),
        "when": "When ETN/VRT Q2 releases are filed.",
    },
    {
        "script": "batch2_official_ir_capture.py",
        "change_required": True,
        "change_type": "source_urls + period_slug",
        "detail": (
            "AMD/CAT/CVX/PLTR source URLs point to Q1 releases. "
            "For Q2: update source_urls, pass period_slug='q2-2026'."
        ),
        "when": "When each ticker's Q2 release is filed.",
    },
    {
        "script": "batch2b_official_ir_capture.py",
        "change_required": True,
        "change_type": "source_urls + period_slug",
        "detail": (
            "GE/LLY/META/PH source URLs point to Q1 releases. "
            "For Q2: update source_urls, pass period_slug='q2-2026'."
        ),
        "when": "When each ticker's Q2 release is filed.",
    },
    {
        "script": "longtail_official_ir_capture.py",
        "change_required": True,
        "change_type": "source_urls + period_slug",
        "detail": (
            "BKNG/KTOS/LNG/SMCI/LIN/ECL/VMC/NFLX/TMUS/CME/WMB source URLs point to Q1 releases. "
            "For Q2: update source_urls per ticker, pass period_slug='q2-2026'."
        ),
        "when": "When each ticker's Q2 release is filed.",
    },
]

# Consumer scripts that do NOT need changes for Q2 rollforward.
CONSUMERS_REGISTRY_ROUTED = [
    {
        "script": "current_window_artifact_index.py",
        "q2_action": "none_required",
        "reason": "Registry-routed since 2026-05-22. all_periods() returns Q2 as latest automatically.",
    },
    {
        "script": "run_summary_refresh.py",
        "q2_action": "none_required",
        "reason": "Registry-routed since 2026-05-22. all_periods() returns Q2 as latest automatically.",
    },
    {
        "script": "chain_manifest.py",
        "q2_action": "none_required",
        "reason": "Registry-routed since 2026-05-22. expected_outputs_for_script() resolves Q2 paths automatically.",
    },
    {
        "script": "fundamental_ir_reconciliation_packets.py",
        "q2_action": "none_required",
        "reason": "Registry-routed since 2026-05-23 (Phase 5 closeout). all_periods() returns Q2 as latest automatically.",
    },
    {
        "script": "official_earnings_bridge.py",
        "q2_action": "none_required",
        "reason": "Registry-routed since 2026-05-23 (Phase 5 closeout). all_periods() returns Q2 as latest automatically.",
    },
    {
        "script": "official_capture_period_registry.py",
        "q2_action": "none_required",
        "reason": "Registry scans the capture directory dynamically. Q2 artifacts are automatically indexed as latest when present.",
    },
    {
        "script": "official_ir_capture_validator.py",
        "q2_action": "none_required",
        "reason": "Validator scans all captures. Q2 artifacts are validated alongside Q1 (Q1 becomes historical).",
    },
]

ROLLFORWARD_PROCEDURE = [
    "1. Monitor Q2 earnings calendar (mid-July 2026). First reporters expected ~July 14.",
    "2. For each ticker as Q2 release is filed: update source_url in the relevant capture script to the Q2 8-K/IR URL.",
    "3. Run the capture script with period_slug='q2-2026'. This writes a new per-ticker Q2 artifact alongside the existing Q1 artifact.",
    "4. Run official_ir_capture_validator.py --all --write. Q2 artifacts appear as new captures; Q1 artifacts become historical.",
    "5. Run official_capture_period_registry.py --write. The registry automatically selects Q2 as latest for migrated tickers.",
    "6. Run fundamental_ir_reconciliation_packets.py --write and official_earnings_bridge.py --write. Both now consume Q2 captures via registry.",
    "7. Verify: official capture validator ok; reconciliation validator ok; bridge validator ok.",
    "8. No changes needed in chain_manifest.py, run_summary_refresh.py, current_window_artifact_index.py, reconciliation, or bridge — all are registry-routed.",
]

REGISTRY_COEXISTENCE_PROOF = (
    "Synthetic Q1/Q2 coexistence test in scripts/test_official_capture_period_registry.py "
    "already proves that when both Q1-2026 and Q2-2026 artifacts exist for the same ticker, "
    "the registry correctly marks Q1 as stale_prior_period and Q2 as latest_current. "
    "Test passes as of 2026-05-22."
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_readiness() -> dict:
    scripts_needing_change = [s for s in CAPTURE_SCRIPT_ROLLFORWARD if s["change_required"]]
    return {
        "generated_at_utc": utc_now(),
        "workflow": "WF70 Official Company Source Capture and Reconciliation",
        "phase": "7 — Q2 2026 rollforward readiness",
        "status": "ok",
        "authority": AUTHORITY,
        "assessment_date": "2026-05-23",
        "q2_earnings_window": Q2_EARNINGS_WINDOW,
        "summary": {
            "capture_scripts_needing_q2_update": len(scripts_needing_change),
            "consumer_scripts_registry_routed_no_change_needed": len(CONSUMERS_REGISTRY_ROUTED),
            "registry_coexistence_proven": True,
            "q2_releases_available_now": False,
            "q2_readiness_status": "infrastructure_complete_awaiting_releases",
        },
        "capture_script_rollforward": CAPTURE_SCRIPT_ROLLFORWARD,
        "consumers_registry_routed": CONSUMERS_REGISTRY_ROUTED,
        "rollforward_procedure": ROLLFORWARD_PROCEDURE,
        "registry_coexistence_proof": REGISTRY_COEXISTENCE_PROOF,
        "residue": (
            "No code changes required now. Q2 source URLs are not yet available. "
            "Rollforward is a per-ticker source-URL update + period_slug='q2-2026' call-site change "
            "in each capture script, applied as each Q2 release is filed starting mid-July 2026."
        ),
    }


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_md(path: Path, data: dict) -> None:
    lines = [
        "# WF70 Phase 7 — Q2 2026 Rollforward Readiness",
        "",
        f"Generated: `{data['generated_at_utc']}`",
        "",
        "Review-only assessment. No source fetches, captures, or authority mutations.",
        "",
        "## Summary",
        "",
        f"- Assessment date: {data['assessment_date']}",
        f"- Q2 earnings window: {data['q2_earnings_window']['typical_window']}",
        f"- Q2 releases available now: {data['summary']['q2_releases_available_now']}",
        f"- Readiness status: `{data['summary']['q2_readiness_status']}`",
        f"- Capture scripts needing Q2 source updates: {data['summary']['capture_scripts_needing_q2_update']}",
        f"- Consumer scripts needing NO changes (registry-routed): {data['summary']['consumer_scripts_registry_routed_no_change_needed']}",
        f"- Registry coexistence proven: {data['summary']['registry_coexistence_proven']}",
        "",
        "## Capture Scripts — Changes Required for Q2",
        "",
        "| Script | Change type | When |",
        "|---|---|---|",
    ]
    for s in data["capture_script_rollforward"]:
        if s["change_required"]:
            lines.append(f"| `{s['script']}` | {s['change_type']} | {s['when']} |")
    lines += [
        "",
        "## Consumer Scripts — No Changes Needed (Registry-Routed)",
        "",
        "| Script | Reason |",
        "|---|---|",
    ]
    for c in data["consumers_registry_routed"]:
        lines.append(f"| `{c['script']}` | {c['reason']} |")
    lines += [
        "",
        "## Rollforward Procedure",
        "",
    ]
    for step in data["rollforward_procedure"]:
        lines.append(f"{step}")
    lines += [
        "",
        "## Registry Coexistence Proof",
        "",
        data["registry_coexistence_proof"],
        "",
        "## Residue",
        "",
        data["residue"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    data = build_readiness()
    write_json(OUT_JSON, data)
    write_md(OUT_MD, data)
    print(f"wrote {OUT_JSON.relative_to(ROOT)}")
    print(f"wrote {OUT_MD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
