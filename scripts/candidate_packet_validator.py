from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_CONFIG = ROOT / "tmp" / "portfolio-config.json"
DEPLOYMENT_CHECK = ROOT / "tmp" / "deployment-check.json"
EARNINGS_CALENDAR = ROOT / "tmp" / "earnings-calendar.json"
QUEUE_NOTE = ROOT / "06. Playbooks" / "Promotion Review Queue.md"
ALLOWED_GATE_VALUES = {"pass", "warning", "failed", "missing", "unknown"}
ALLOWED_LANES = {"execution", "watch", "macro", "speculative"}
ALLOWED_TIMING_POSTURES = {"clean", "blocked", "stale", "unknown"}
REQUIRED_FIELDS = {
    "schema_version": int,
    "generated_at_utc": str,
    "ticker": str,
    "proposed_lane": str,
    "source_surface": str,
    "thesis_evidence_source": str,
    "canonical_trigger_source": str,
    "canonical_portfolio_source": str,
    "thesis_exists": bool,
    "levels_exist": bool,
    "timing_posture": str,
    "portfolio_competition_assessed": bool,
    "sector_cap_checked": bool,
    "correlated_sleeve_checked": bool,
    "regime_score_total": (int, float),
    "regime_score_rank": int,
    "current_watch_state": str,
    "current_trigger_state": str,
    "entry_band_defined": bool,
    "invalidation_defined": bool,
    "sizing_tier_defined": bool,
    "catalyst_window_status": str,
    "sector": str,
    "correlated_sleeve": str,
    "sector_cap_check": dict,
    "five_gate_status": dict,
    "missing_gates": list,
    "promotion_blockers": list,
    "promotion_candidate": bool,
    "promotion_review_required": bool,
    "notes": list,
}
GATE_KEYS = [
    "thesis_gate",
    "macro_and_regime_gate",
    "technical_gate",
    "catalyst_gate",
    "risk_and_sizing_gate",
]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def error(msg: str) -> Dict[str, Any]:
    return {"ok": False, "error": msg}


def validate_types(packet: Dict[str, Any], errors: List[str]) -> None:
    for key, expected in REQUIRED_FIELDS.items():
        if key not in packet:
            errors.append(f"missing required field: {key}")
            continue
        if not isinstance(packet[key], expected):
            errors.append(f"field {key} has wrong type: expected {expected}, got {type(packet[key]).__name__}")
    extra = sorted(set(packet.keys()) - set(REQUIRED_FIELDS.keys()) - {"queue_entry_required", "queue_entry_present", "proposed_action_state", "candidate_weight_pct"})
    if extra:
        errors.append("unknown fields present: " + ", ".join(extra))


def validate_gate_shape(packet: Dict[str, Any], errors: List[str]) -> None:
    gates = packet.get("five_gate_status")
    if not isinstance(gates, dict):
        return
    if set(gates.keys()) != set(GATE_KEYS):
        errors.append("five_gate_status must contain exactly the five canonical gates")
        return
    for gate_name, status in gates.items():
        if status not in ALLOWED_GATE_VALUES:
            errors.append(f"gate {gate_name} has unknown status {status!r}")


def load_queue_tickers() -> set[str]:
    if not QUEUE_NOTE.exists():
        return set()
    text = QUEUE_NOTE.read_text(encoding="utf-8")
    tickers = set()
    for line in text.splitlines():
        if "|" not in line:
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if parts and parts[0].isupper() and 1 <= len(parts[0]) <= 8:
            tickers.add(parts[0])
    return tickers


def find_deployment_record(data: Dict[str, Any], ticker: str) -> Dict[str, Any] | None:
    for record in data.get("records", []):
        if record.get("ticker") == ticker:
            return record
    return None


def find_earnings_record(data: Dict[str, Any], ticker: str) -> Dict[str, Any] | None:
    for record in data.get("records", []):
        if record.get("ticker") == ticker:
            return record
    return None


def validate_packet(packet: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[str] = []
    blockers: List[str] = []
    validate_types(packet, errors)
    validate_gate_shape(packet, errors)
    if errors:
        return {"ok": False, "errors": errors, "blockers": blockers}

    if packet["schema_version"] != 1:
        errors.append("schema_version must be 1")
    if packet["proposed_lane"] not in ALLOWED_LANES:
        errors.append("proposed_lane must be one of execution/watch/macro/speculative")
    if packet["timing_posture"] not in ALLOWED_TIMING_POSTURES:
        errors.append("timing_posture must be one of clean/blocked/stale/unknown")
    if packet["promotion_review_required"] is not True:
        errors.append("promotion_review_required must stay true")
    if packet["source_surface"].strip().lower() == "watchlist":
        blockers.append("watchlist is the only source surface")
    if not packet["thesis_exists"]:
        blockers.append("thesis_exists is false")
    if not packet["portfolio_competition_assessed"]:
        blockers.append("portfolio competition was not assessed")
    if not packet["sector_cap_checked"]:
        blockers.append("sector cap check was not performed")
    if not packet["correlated_sleeve_checked"]:
        blockers.append("correlated sleeve check was not performed")

    config = load_json(PORTFOLIO_CONFIG)
    tracked = config.get("tracked_universe", {})
    ticker = packet["ticker"]
    if ticker not in tracked:
        blockers.append(f"ticker {ticker} missing from tracked_universe")
        return {"ok": False, "errors": errors, "blockers": blockers}

    tracked_record = tracked[ticker]
    if packet["proposed_lane"] == "execution" and tracked_record.get("coverage_lane") != "execution" and packet["promotion_candidate"]:
        blockers.append("execution promotion candidate is not currently execution-lane entitled")
    if tracked_record.get("sector") != packet["sector"]:
        blockers.append("sector mismatch vs portfolio-config")
    if packet["current_watch_state"] != tracked_record.get("workflow_state"):
        blockers.append("current_watch_state does not match portfolio-config workflow_state")
    if bool(packet["sizing_tier_defined"]) != bool(tracked_record.get("sizing_tier")):
        blockers.append("sizing_tier_defined mismatch vs portfolio-config")

    entry_band = config.get("entry_bands", {}).get(ticker)
    if packet["entry_band_defined"] != bool(entry_band and entry_band.get("low") is not None and entry_band.get("high") is not None):
        blockers.append("entry_band_defined mismatch vs portfolio-config entry_bands")
    if packet["invalidation_defined"] != bool(entry_band and entry_band.get("stop") is not None):
        blockers.append("invalidation_defined mismatch vs portfolio-config entry_bands")
    if packet["levels_exist"] != bool(packet["entry_band_defined"] and packet["invalidation_defined"]):
        blockers.append("levels_exist must equal entry_band_defined and invalidation_defined")

    deployment = load_json(DEPLOYMENT_CHECK)
    dep_record = find_deployment_record(deployment, ticker)
    if dep_record is None:
        blockers.append("ticker missing from deployment-check")
    else:
        expected_state = dep_record.get("action_state", "").replace(" ALMOST", "ALMOST").strip()
        if packet["current_trigger_state"] != dep_record.get("action_state"):
            blockers.append("current_trigger_state does not match deployment-check action_state")
        if dep_record.get("action_state", "").startswith("WATCH") and packet["promotion_candidate"]:
            blockers.append("watch-only deployment state cannot be promotion_candidate")

    earnings = load_json(EARNINGS_CALENDAR)
    earnings_record = find_earnings_record(earnings, ticker)
    if earnings_record is None:
        blockers.append("ticker missing from earnings-calendar")
    else:
        next_date = earnings_record.get("next_earnings_date")
        if next_date is None:
            blockers.append("earnings date missing")

    gates = packet["five_gate_status"]
    bad_gates = [name for name, status in gates.items() if status != "pass"]
    if bad_gates:
        blockers.append("non-passing gates: " + ", ".join(sorted(bad_gates)))
    if sorted(packet["missing_gates"]) != sorted(name for name, status in gates.items() if status in {"missing", "warning", "failed", "unknown"}):
        blockers.append("missing_gates does not reflect non-pass gate statuses")

    status = packet["catalyst_window_status"]
    if status in {"blocked", "unknown"}:
        blockers.append(f"catalyst window status is {status}")
    if packet["timing_posture"] in {"blocked", "stale", "unknown"}:
        blockers.append(f"timing_posture is {packet['timing_posture']}")

    sector_check = packet["sector_cap_check"]
    if sector_check.get("status") != "pass":
        blockers.append("sector_cap_check is not pass")
    if sector_check.get("status") == "pass" and not packet["sector_cap_checked"]:
        blockers.append("sector_cap_check status is pass but sector_cap_checked is false")

    if packet["promotion_candidate"]:
        needed = [
            packet["thesis_evidence_source"].strip(),
            packet["canonical_trigger_source"].strip(),
            packet["canonical_portfolio_source"].strip(),
            packet["entry_band_defined"],
            packet["invalidation_defined"],
            packet["sizing_tier_defined"],
            status == "clear",
            sector_check.get("status") == "pass",
            not bad_gates,
        ]
        if not all(needed):
            blockers.append("promotion_candidate true without satisfying minimum gate logic")

    proposed = packet.get("proposed_action_state")
    if proposed in {"DEPLOYABLE", "DEPLOYABLE NOW"}:
        queue_required = packet.get("queue_entry_required", True)
        queue_present = packet.get("queue_entry_present")
        if queue_present is None:
            queue_present = ticker in load_queue_tickers()
        if not queue_required:
            blockers.append("DEPLOYABLE proposal must require queue entry")
        if not queue_present:
            blockers.append("DEPLOYABLE proposal missing queue entry")
    elif proposed == "ALMOST" and packet.get("queue_entry_required"):
        blockers.append("ALMOST should not require queue entry by default")

    combined_blockers = list(dict.fromkeys(blockers + list(packet["promotion_blockers"])))
    ok = not errors and not combined_blockers
    return {"ok": ok, "errors": errors, "blockers": combined_blockers}


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail-closed validator for promotion candidate packets.")
    parser.add_argument("packet", help="Path to candidate packet JSON")
    args = parser.parse_args()
    packet_path = Path(args.packet)
    packet = load_json(packet_path)
    result = validate_packet(packet)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
