from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[1]
QUEUE_NOTE = ROOT / "06. Playbooks" / "Promotion Review Queue.md"
DEPLOYMENT_CHECK = ROOT / "tmp" / "deployment-check.json"


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def queue_contains(ticker: str) -> bool:
    if not QUEUE_NOTE.exists():
        return False
    text = QUEUE_NOTE.read_text(encoding="utf-8")
    return any(line.strip().startswith(f"| {ticker} ") or line.strip().startswith(f"|{ticker}|") for line in text.splitlines())


def is_deployable_state(value: str) -> bool:
    normalized = (value or "").strip().upper()
    return normalized in {"DEPLOYABLE", "DEPLOYABLE NOW"}


def scan_deployment_check(path: Path) -> Dict[str, Any]:
    data = load_json(path)
    blockers = []
    records = []
    for record in data.get("records", []):
        ticker = record.get("ticker")
        action_state = record.get("action_state", "")
        if ticker and is_deployable_state(action_state):
            present = queue_contains(ticker)
            records.append({"ticker": ticker, "action_state": action_state, "queue_entry_present": present})
            if not present:
                blockers.append(f"{ticker} is {action_state} in deployment-check but missing Promotion Review Queue row")
    return {"ok": not blockers, "mode": "deployment_check_scan", "records_checked": len(data.get("records", [])), "deployable_records": records, "blockers": blockers}


def check_packet(path: Path) -> Dict[str, Any]:
    packet = load_json(path)
    proposed = packet.get("proposed_action_state", packet.get("current_trigger_state", ""))
    ticker = packet["ticker"]
    queue_required = is_deployable_state(proposed)
    queue_present = bool(packet.get("queue_entry_present")) or queue_contains(ticker)
    blockers = []
    if queue_required and not queue_present:
        blockers.append("queue entry required for DEPLOYABLE/DEPLOYABLE NOW candidate")
    if proposed == "ALMOST" and packet.get("queue_entry_required"):
        blockers.append("ALMOST should not require queue entry by default")
    return {
        "ok": not blockers,
        "mode": "packet_check",
        "ticker": ticker,
        "proposed_action_state": proposed,
        "queue_entry_required": queue_required,
        "queue_entry_present": queue_present,
        "blockers": blockers,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Check deployment-ranking shadow-canon drift against the Promotion Review Queue.")
    parser.add_argument("packet", nargs="?", help="Optional candidate packet JSON. If omitted, scan tmp/deployment-check.json.")
    parser.add_argument("--deployment-check", default=str(DEPLOYMENT_CHECK), help="Deployment-check JSON to scan when no packet is provided.")
    args = parser.parse_args()

    result = check_packet(Path(args.packet)) if args.packet else scan_deployment_check(Path(args.deployment_check))
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
