from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
PORTFOLIO_CONFIG = ROOT / "tmp" / "portfolio-config.json"

CORRELATED_MAP = {
    "ai_power": {"Tech", "Industrials"},
    "large_cap_quality": {"Tech", "Financials"},
    "defense": {"Defense"},
    "energy": {"Energy", "Commodities"},
    "healthcare": {"Healthcare"},
    "financials": {"Financials"},
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def infer_sleeve(sector: str, explicit: str | None) -> str:
    if explicit:
        return explicit
    sector = sector.strip()
    for sleeve, sectors in CORRELATED_MAP.items():
        if sector in sectors:
            return sleeve
    return sector.lower().replace(" ", "_")


def current_sector_weights(config: Dict[str, Any]) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    for bucket in ("core", "tactical", "speculative"):
        for item in config.get("portfolio", {}).get(bucket, []):
            sector = item.get("sector", "Unknown")
            weights[sector] = weights.get(sector, 0.0) + float(item.get("weight", 0))
    return weights


def current_sleeve_weights(config: Dict[str, Any]) -> Dict[str, float]:
    weights: Dict[str, float] = {}
    for bucket in ("core", "tactical", "speculative"):
        for item in config.get("portfolio", {}).get(bucket, []):
            sleeve = infer_sleeve(item.get("sector", "Unknown"), None)
            weights[sleeve] = weights.get(sleeve, 0.0) + float(item.get("weight", 0))
    return weights


def main() -> int:
    parser = argparse.ArgumentParser(description="Check sector-cap and correlated-sleeve integrity for a candidate packet.")
    parser.add_argument("packet", help="Path to candidate packet JSON")
    args = parser.parse_args()

    packet = load_json(Path(args.packet))
    config = load_json(PORTFOLIO_CONFIG)
    sector_weights = current_sector_weights(config)
    sleeve_weights = current_sleeve_weights(config)
    max_sector = float(config.get("risk_thresholds", {}).get("max_sector_pct", 35))
    candidate_weight = float(packet.get("candidate_weight_pct", 0.0))
    sector = packet["sector"]
    sleeve = infer_sleeve(sector, packet.get("correlated_sleeve"))
    projected_sector = sector_weights.get(sector, 0.0) + candidate_weight
    projected_sleeve = sleeve_weights.get(sleeve, 0.0) + candidate_weight

    blockers: List[str] = []
    warnings: List[str] = []
    packet_sector_check = packet.get("sector_cap_check") or {}
    packet_sector_status = packet_sector_check.get("status")
    if packet_sector_status and packet_sector_status != "pass":
        blockers.append(f"packet sector_cap_check status is {packet_sector_status}")
    if packet.get("sector_cap_checked") is False:
        blockers.append("packet says sector cap was not checked")
    if packet.get("correlated_sleeve_checked") is False:
        blockers.append("packet says correlated sleeve was not checked")

    if projected_sector > max_sector:
        blockers.append(f"projected sector weight {projected_sector:.2f}% exceeds max {max_sector:.2f}%")
    elif projected_sector > max_sector - 2:
        warnings.append(f"projected sector weight {projected_sector:.2f}% is within 2% of cap {max_sector:.2f}%")

    if sleeve == "ai_power" and projected_sleeve > max_sector:
        blockers.append(f"correlated sleeve {sleeve} would rise to {projected_sleeve:.2f}% and worsen concentration")
    elif sleeve == "ai_power" and projected_sleeve > max_sector - 3:
        warnings.append(f"correlated sleeve {sleeve} would rise to {projected_sleeve:.2f}% and is near concentration cap")

    result = {
        "ok": not blockers,
        "sector": sector,
        "correlated_sleeve": sleeve,
        "candidate_weight_pct": candidate_weight,
        "current_sector_weight_pct": sector_weights.get(sector, 0.0),
        "projected_sector_weight_pct": projected_sector,
        "current_correlated_sleeve_weight_pct": sleeve_weights.get(sleeve, 0.0),
        "projected_correlated_sleeve_weight_pct": projected_sleeve,
        "max_sector_pct": max_sector,
        "packet_sector_cap_check_status": packet_sector_status,
        "warnings": warnings,
        "blockers": blockers,
    }
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
