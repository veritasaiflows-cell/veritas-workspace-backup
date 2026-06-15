from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "portfolio-pro-forma-risk-validation.json"
CONFIG = ROOT / "tmp" / "portfolio-config.json"
REQUIRED_RISK_REFS = (
    "25% sector cap",
    "15% normal single-name ceiling",
    "speculative sleeve cap",
    "catalyst-window exception",
)


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_packets(path: Path) -> list[tuple[Path, dict[str, Any]]]:
    def expand(source: Path, data: Any) -> list[tuple[Path, dict[str, Any]]]:
        if isinstance(data, dict) and data.get("artifact_type") == "wf56_scoped_apply_approval":
            return []
        if isinstance(data, dict) and isinstance(data.get("proposals"), list):
            return [(source, item) for item in data["proposals"] if isinstance(item, dict)]
        if isinstance(data, dict) and (data.get("proposal_id") or data.get("mutation_type") or data.get("exact_patch_preview")):
            return [(source, data)]
        return []

    if path.is_dir():
        out = []
        for item in sorted(path.glob("*.json")):
            try:
                data = json.loads(item.read_text(encoding="utf-8"))
            except Exception:
                continue
            out.extend(expand(item, data))
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    packets = expand(path, data)
    if not packets:
        raise ValueError("proposal input must be a JSON object or directory of JSON objects")
    return packets


def pct(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_packet(source: Path, packet: dict[str, Any], config: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    mutation_type = packet.get("mutation_type")
    risk_text = json.dumps(packet.get("risk_rule_check") or {}, sort_keys=True).lower()
    for ref in REQUIRED_RISK_REFS:
        if ref.lower() not in risk_text:
            findings.append({"severity": "critical", "source": relpath(source), "issue": "missing risk-rule reference", "reference": ref})
    concentration = packet.get("concentration_check") or {}
    if not isinstance(concentration, dict) or concentration.get("status") not in {"pass", "warning", "review_required"}:
        findings.append({"severity": "critical", "source": relpath(source), "issue": "concentration_check.status missing or invalid"})
    single_name_after = pct(concentration.get("single_name_after_pct") or concentration.get("max_single_name_after_pct"))
    if single_name_after is not None and single_name_after > 15 and not concentration.get("written_exception"):
        findings.append({"severity": "critical", "source": relpath(source), "issue": "single-name exposure breaches 15% normal ceiling without written exception", "after_pct": single_name_after})
    for required_block in ("correlated_sleeve_exposure_before_after", "sleeve_deltas"):
        if required_block not in packet:
            findings.append({"severity": "critical", "source": relpath(source), "issue": f"missing required risk block: {required_block}"})
    proposed_cash = pct(packet.get("proposed_cash_target_pct"))
    current_cash = pct(packet.get("current_cash_target_pct"))
    if current_cash is None or proposed_cash is None:
        findings.append({"severity": "critical", "source": relpath(source), "issue": "current_cash_target_pct and proposed_cash_target_pct are required"})
    if proposed_cash is not None and not 0 <= proposed_cash <= 100:
        findings.append({"severity": "critical", "source": relpath(source), "issue": "proposed cash target must be between 0 and 100", "value": proposed_cash})
    min_cash = pct(config.get("min_cash_threshold_pct") or config.get("minimum_cash_pct") or config.get("cash_floor_pct"))
    if min_cash is not None and proposed_cash is not None and proposed_cash < min_cash:
        findings.append({"severity": "critical", "source": relpath(source), "issue": "proposed cash target below configured minimum cash threshold", "proposed_cash_target_pct": proposed_cash, "min_cash_threshold_pct": min_cash})
    sector_rows = packet.get("sector_exposure_before_after") or []
    if isinstance(sector_rows, list):
        for row in sector_rows:
            if not isinstance(row, dict):
                continue
            after = pct(row.get("after") or row.get("after_pct") or row.get("proposed_pct"))
            sector = row.get("sector") or "unknown"
            if after is not None and after > 25:
                findings.append({"severity": "critical", "source": relpath(source), "sector": sector, "issue": "pro-forma sector exposure breaches 25% cap", "after_pct": after})
    if mutation_type in {"sleeve_change", "rebalance", "cash_target_change"} and not sector_rows:
        findings.append({"severity": "critical", "source": relpath(source), "issue": "sleeve/rebalance proposal must include sector_exposure_before_after"})

    sleeve_deltas = packet.get("sleeve_deltas") or []
    if isinstance(sleeve_deltas, list):
        for row in sleeve_deltas:
            if not isinstance(row, dict):
                continue
            sleeve = str(row.get("sleeve") or row.get("name") or "").lower()
            after = pct(row.get("after_pct") or row.get("after") or row.get("proposed_pct"))
            cap = pct(row.get("cap_pct") or row.get("max_pct"))
            if cap is not None and after is not None and after > cap:
                findings.append({"severity": "critical", "source": relpath(source), "issue": "sleeve exposure breaches declared cap", "sleeve": sleeve or "unknown", "after_pct": after, "cap_pct": cap})
            if "spec" in sleeve and after is not None and after > 10 and not row.get("written_exception"):
                findings.append({"severity": "critical", "source": relpath(source), "issue": "speculative sleeve exceeds default cap without written exception", "sleeve": sleeve or "unknown", "after_pct": after})
    correlated = packet.get("correlated_sleeve_exposure_before_after") or []
    if isinstance(correlated, list):
        for row in correlated:
            if not isinstance(row, dict):
                continue
            after = pct(row.get("after_pct") or row.get("after") or row.get("proposed_pct"))
            cap = pct(row.get("cap_pct") or row.get("max_pct"))
            if cap is not None and after is not None and after > cap:
                findings.append({"severity": "critical", "source": relpath(source), "issue": "correlated sleeve exposure breaches declared cap", "after_pct": after, "cap_pct": cap, "group": row.get("group") or row.get("sleeve") or "unknown"})
    if packet.get("portfolio_mutation_allowed") is True or packet.get("trade_or_account_action_allowed") is True:
        findings.append({"severity": "critical", "source": relpath(source), "issue": "risk validation cannot grant mutation or trade authority"})
    return findings


def build_report(path: Path) -> dict[str, Any]:
    config = json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}
    packets = load_packets(path)
    findings: list[dict[str, Any]] = []
    for source, packet in packets:
        findings.extend(validate_packet(source, packet, config))
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok" if critical == 0 else "blocked",
        "authority": {"portfolio_mutation_allowed": False, "trade_or_account_action_allowed": False},
        "summary": {"packets_checked": len(packets), "critical": critical, "warning": warning},
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate pro-forma risk checks in review-only portfolio proposals.")
    parser.add_argument("input", nargs="?", default="tmp/portfolio-mutation-proposals")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report = build_report(ROOT / args.input)
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {OUT}")
    print(f"portfolio_pro_forma_risk_validator: {report['status']} ({report['summary']['critical']} critical, {report['summary']['warning']} warning)")
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
