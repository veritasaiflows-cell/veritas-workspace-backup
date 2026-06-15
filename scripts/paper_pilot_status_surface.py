from __future__ import annotations

import argparse
import glob
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "alpaca-paper-readiness" / "paper-pilot-status-surface.json"
READINESS = ROOT / "tmp" / "alpaca-paper-readiness" / "wf63-readiness-report.json"
GUARD = ROOT / "tmp" / "alpaca-paper-readiness" / "paper-execution-guard-validation.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def load(path: Path) -> dict[str, Any]:
    value = load_json_artifact(path)
    return value if isinstance(value, dict) else {}


def as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def request_by_pilot() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for name in glob.glob(str(ROOT / "tmp" / "alpaca-paper-readiness" / "paper-trade-request.wf67-*.json")):
        path = Path(name)
        req = load(path)
        if not req:
            continue
        request_id = str(req.get("request_id") or "")
        # request_id examples: wf67-reviewed-packet-001-etn-passive-buy
        pilot_id = request_id
        for suffix in ("-etn-passive-buy", "-msft-marketable-buy"):
            if pilot_id.endswith(suffix):
                pilot_id = pilot_id[: -len(suffix)]
        source = req.get("source") if isinstance(req.get("source"), dict) else {}
        out[pilot_id] = {
            "path": rel(path),
            "request_id": request_id,
            "order": req.get("order") or {},
            "source_recommendation": source.get("recommendation_source"),
            "source_proposal_id": source.get("proposal_id"),
            "owner_or_pilot_scope": source.get("owner_or_pilot_scope"),
        }
    return out


def pilot_from_submit(path: Path, data: dict[str, Any], requests: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pilot_id = str(data.get("pilot_id") or path.stem.replace("paper-submit-reconciliation.", ""))
    observed = (data.get("observed_redacted") or [{}])[0] if isinstance(data.get("observed_redacted"), list) else {}
    req = requests.get(pilot_id, {})
    order = req.get("order") if isinstance(req.get("order"), dict) else {}
    filled_qty = as_float(observed.get("filled_qty")) or 0.0
    status = str(data.get("status") or observed.get("status") or "unknown")
    performance_state = "filled_monitoring" if filled_qty > 0 else "not_started_unfilled"
    return {
        "pilot_id": pilot_id,
        "ticker": str(observed.get("symbol") or order.get("symbol") or "").upper(),
        "side": observed.get("side") or order.get("side"),
        "qty": as_float(observed.get("qty")) or order.get("qty"),
        "order_type": observed.get("type") or order.get("type"),
        "limit_price": as_float(observed.get("limit_price")) or order.get("limit_price"),
        "status": "accepted_unfilled" if status == "ok" and filled_qty == 0 else status,
        "filled_qty": filled_qty,
        "filled_avg_price": None,
        "position_observed": False,
        "paper_order_id_present": bool(observed.get("paper_order_id_present")),
        "submitted_at": observed.get("submitted_at"),
        "expires_at": observed.get("expires_at"),
        "source_recommendation": req.get("source_recommendation"),
        "source_proposal_id": req.get("source_proposal_id"),
        "source_artifacts": [rel(path)] + ([req.get("path")] if req.get("path") else []),
        "performance_state": performance_state,
        "paper_pnl_available": False,
    }


def pilot_from_position(path: Path, data: dict[str, Any], requests: dict[str, dict[str, Any]]) -> dict[str, Any]:
    pilot_id = str(data.get("pilot_id") or path.stem.replace("paper-position-reconciliation.", ""))
    orders = data.get("orders_observed_redacted") if isinstance(data.get("orders_observed_redacted"), list) else []
    positions = data.get("positions_observed_redacted") if isinstance(data.get("positions_observed_redacted"), list) else []
    order_obs = orders[0] if orders else {}
    req = requests.get(pilot_id, {})
    order = req.get("order") if isinstance(req.get("order"), dict) else {}
    filled_qty = as_float(order_obs.get("filled_qty")) or 0.0
    position_observed = bool(positions)
    performance_state = "filled_monitoring" if filled_qty > 0 or position_observed else "not_started_unfilled"
    return {
        "pilot_id": pilot_id,
        "ticker": str(order_obs.get("symbol") or order.get("symbol") or "").upper(),
        "side": order_obs.get("side") or order.get("side"),
        "qty": as_float(order_obs.get("qty")) or order.get("qty"),
        "order_type": order_obs.get("type") or order.get("type"),
        "limit_price": as_float(order_obs.get("limit_price")) or order.get("limit_price"),
        "status": data.get("status") or order_obs.get("status") or "unknown",
        "filled_qty": filled_qty,
        "filled_avg_price": as_float(order_obs.get("filled_avg_price")),
        "position_observed": position_observed,
        "paper_order_id_present": bool(order_obs.get("paper_order_id_present")),
        "submitted_at": order_obs.get("submitted_at"),
        "expires_at": order_obs.get("expires_at"),
        "hold_policy": data.get("hold_policy"),
        "source_recommendation": req.get("source_recommendation"),
        "source_proposal_id": req.get("source_proposal_id"),
        "source_artifacts": [rel(path)] + ([req.get("path")] if req.get("path") else []),
        "performance_state": performance_state,
        "paper_pnl_available": position_observed,
    }


def build_surface() -> dict[str, Any]:
    guard = load(GUARD)
    readiness = load(READINESS)
    requests = request_by_pilot()
    pilots: dict[str, dict[str, Any]] = {}

    for name in glob.glob(str(ROOT / "tmp" / "alpaca-paper-readiness" / "paper-submit-reconciliation.wf67-*.json")):
        path = Path(name)
        data = load(path)
        if data:
            pilot = pilot_from_submit(path, data, requests)
            pilots[pilot["pilot_id"]] = pilot
    for name in glob.glob(str(ROOT / "tmp" / "alpaca-paper-readiness" / "paper-position-reconciliation.wf67-*.json")):
        path = Path(name)
        data = load(path)
        if data:
            pilot = pilot_from_position(path, data, requests)
            pilots[pilot["pilot_id"]] = pilot

    pilot_rows = sorted(pilots.values(), key=lambda row: (str(row.get("submitted_at") or ""), str(row.get("pilot_id") or "")))
    active = [p for p in pilot_rows if str(p.get("status") or "").lower() in {"accepted", "accepted_unfilled", "submitted"}]
    filled = [p for p in pilot_rows if (as_float(p.get("filled_qty")) or 0.0) > 0 or p.get("position_observed") is True]
    status = "ok" if guard.get("status") == "ok" and readiness.get("status") == "ok" else "warning"
    findings: list[dict[str, Any]] = []
    if guard.get("status") != "ok":
        findings.append({"severity": "warning", "issue": "wf67_guard_not_ok", "status": guard.get("status")})
    if readiness.get("status") != "ok":
        findings.append({"severity": "warning", "issue": "wf63_readiness_not_ok", "status": readiness.get("status")})

    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": status,
        "workflow": "WF67 - Alpaca Paper Execution Guardrail",
        "authority": {
            "paper_simulation_only": True,
            "scoped_paper_submit_cancel_allowed": guard.get("ready_for_paper_submit_cancel") is True,
            "general_autonomous_paper_submit_allowed": False,
            "live_trading_allowed": False,
            "live_endpoint_allowed": False,
            "money_movement_allowed": False,
            "account_settings_mutation_allowed": False,
            "owner_approval_inferred": False,
            "promotion_to_live_allowed": False,
        },
        "summary": {
            "pilot_count": len(pilot_rows),
            "active_pilot_count": len(active),
            "filled_or_position_observed_count": len(filled),
            "paper_pnl_available": any(p.get("paper_pnl_available") is True for p in pilot_rows),
        },
        "pilots": pilot_rows,
        "findings": findings,
        "source_artifacts": [rel(GUARD), rel(READINESS)],
        "stop_lines": [
            "Paper simulation only; no live trade/account/money movement authority.",
            "No owner approval inferred from recommendation packets, validation, or paper fills.",
            "No close/cancel/sell unless Randall explicitly instructs inside WF67 guardrails.",
            "Paper results do not promote a ticker to live deployment or portfolio mutation authority.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build read-only WF67 paper pilot status surface.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    args = parser.parse_args()
    surface = build_surface()
    if args.write:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        atomic_write_json(output, surface)
        print(f"paper_pilot_status_surface_written status={surface.get('status')} pilots={len(surface.get('pilots') or [])} path={rel(output)}")
    else:
        print(json.dumps(surface, indent=2, ensure_ascii=False))
    return 0 if surface.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
