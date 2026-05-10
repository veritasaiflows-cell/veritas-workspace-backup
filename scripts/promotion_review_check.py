from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
TECHNICAL_REFRESH = TMP / "technical-refresh.json"
DEPLOYMENT_CHECK = TMP / "deployment-check.json"
TRIGGER_SHEET = TMP / "trigger-sheet.json"
PORTFOLIO_CONFIG = TMP / "portfolio-config.json"
EARNINGS_CALENDAR = TMP / "earnings-calendar.json"
QUEUE_NOTE = ROOT / "06. Playbooks" / "Promotion Review Queue.md"
TECHNICAL_SHEET = ROOT / "03. Portfolio" / "Technical Entry and Invalidation Sheet.md"
TRIGGER_NOTE = ROOT / "03. Portfolio" / "Deployment Trigger Sheet.md"
PORTFOLIO_SNAPSHOT = ROOT / "03. Portfolio" / "Portfolio Snapshot.md"
RISK_RULES = ROOT / "07. Risk" / "Risk Rules.md"
OUT_DEFAULT = TMP / "promotion-review-check-{ticker}.json"
SCHEMA_VERSION = 1

BLOCKED_DAYS = 7
WARNING_DAYS = 14
AUTO_APPROVAL_GATE_PATTERN = {
    "thesis": "pass",
    "macro_regime": "pass",
    "technical": "pass",
    "catalyst": "clear",
    "risk_sizing": "warning",
}
AUTO_APPROVAL_SCOPE = "workspace deployment-status approval only; no trade execution and no automatic canonical note mutation"


def load_json(path: Path, required: bool = True) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise FileNotFoundError(path)
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def age_hours(value: str | None) -> float | None:
    dt = parse_ts(value)
    if not dt:
        return None
    return round((datetime.now(timezone.utc) - dt).total_seconds() / 3600, 2)


def is_stale(payload: dict[str, Any], default_hours: float) -> tuple[bool, float | None, float]:
    age = age_hours(payload.get("generated_at_utc"))
    stale_after = payload.get("stale_after_hours", default_hours)
    try:
        stale_after = float(stale_after)
    except (TypeError, ValueError):
        stale_after = default_hours
    return bool(age is None or age > stale_after), age, stale_after


def find_record(payload: dict[str, Any], ticker: str) -> dict[str, Any] | None:
    for rec in payload.get("records", []) or []:
        if rec.get("ticker") == ticker:
            return rec
    return None


def queue_contains(ticker: str) -> bool:
    if not QUEUE_NOTE.exists():
        return False
    text = QUEUE_NOTE.read_text(encoding="utf-8", errors="replace")
    return any(line.strip().startswith(f"| {ticker} ") or line.strip().startswith(f"|{ticker}|") for line in text.splitlines())


def note_contains(path: Path, ticker: str) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return ticker in text


def catalyst_status(trigger_rec: dict[str, Any], earnings_rec: dict[str, Any] | None) -> tuple[str, list[str]]:
    blockers: list[str] = []
    days = trigger_rec.get("days_to_earnings")
    if days is None and earnings_rec:
        as_of = load_json(EARNINGS_CALENDAR, required=False).get("as_of_date")
        next_date = earnings_rec.get("next_earnings_date")
        if as_of and next_date:
            try:
                days = (datetime.fromisoformat(next_date).date() - datetime.fromisoformat(as_of).date()).days
            except ValueError:
                days = None
    if days is None:
        blockers.append("earnings/catalyst timing is unknown")
        return "unknown", blockers
    if days < 0:
        return "clear", blockers
    if days <= BLOCKED_DAYS:
        blockers.append(f"earnings in {days} days")
        return "blocked", blockers
    if days <= WARNING_DAYS:
        blockers.append(f"earnings in {days} days -- timing-sensitive promotion review block")
        return "warning", blockers
    return "clear", blockers


def run_packet_validator(packet_path: Path) -> dict[str, Any]:
    try:
        from candidate_packet_validator import validate_packet
        packet = load_json(packet_path)
        return validate_packet(packet)
    except Exception as exc:  # fail closed
        return {"ok": False, "errors": [f"packet validator failed: {exc}"], "blockers": []}


def build_review(ticker: str, packet_path: Path | None = None, require_queue: bool = True) -> dict[str, Any]:
    ticker = ticker.upper()
    blockers: list[str] = []
    warnings: list[str] = []

    technical = load_json(TECHNICAL_REFRESH)
    deployment = load_json(DEPLOYMENT_CHECK)
    trigger = load_json(TRIGGER_SHEET)
    config = load_json(PORTFOLIO_CONFIG)
    earnings = load_json(EARNINGS_CALENDAR)

    technical_stale, technical_age, technical_stale_after = is_stale(technical, 36)
    deploy_stale, deploy_age, deploy_stale_after = is_stale(deployment, 24)
    trigger_stale, trigger_age, trigger_stale_after = is_stale(trigger, 24)
    earnings_stale, earnings_age, earnings_stale_after = is_stale(earnings, 24 * float(earnings.get("stale_after_days", 7)))
    if technical_stale:
        blockers.append(f"technical-refresh stale or missing timestamp (age_h={technical_age}, stale_after_h={technical_stale_after})")
    if deploy_stale:
        blockers.append(f"deployment-check stale or missing timestamp (age_h={deploy_age}, stale_after_h={deploy_stale_after})")
    if trigger_stale:
        blockers.append(f"trigger-sheet stale or missing timestamp (age_h={trigger_age}, stale_after_h={trigger_stale_after})")
    if earnings_stale:
        blockers.append(f"earnings-calendar stale or missing timestamp (age_h={earnings_age}, stale_after_h={earnings_stale_after})")

    deploy_tech_ts = (((deployment.get("freshness") or {}).get("technical_file") or {}).get("generated_at_utc"))
    trigger_tech_age = (trigger.get("freshness") or {}).get("technical_age_hours")
    if deploy_tech_ts is None:
        blockers.append("deployment-check does not expose source technical timestamp")
    elif technical.get("generated_at_utc") and deploy_tech_ts != technical.get("generated_at_utc"):
        blockers.append("deployment-check technical source timestamp does not match technical-refresh")
    if trigger_tech_age is None:
        warnings.append("trigger-sheet does not expose a source technical timestamp; using trigger freshness only")

    tech_rec = find_record(technical, ticker)
    dep_rec = find_record(deployment, ticker)
    trig_rec = find_record(trigger, ticker)
    earn_rec = find_record(earnings, ticker)
    tracked = (config.get("tracked_universe") or {}).get(ticker, {})
    band = (config.get("entry_bands") or {}).get(ticker, {})

    if tech_rec is None:
        blockers.append("ticker missing from technical-refresh")
        tech_rec = {}
    if dep_rec is None:
        blockers.append("ticker missing from deployment-check")
        dep_rec = {}
    if trig_rec is None:
        blockers.append("ticker missing from trigger-sheet")
        trig_rec = {}
    if not tracked:
        blockers.append("ticker missing from portfolio-config tracked_universe")
    if earn_rec is None:
        blockers.append("ticker missing from earnings-calendar")

    action_state = str(dep_rec.get("action_state") or trig_rec.get("action_state") or "").upper()
    if action_state != "PROMOTION REVIEW":
        blockers.append(f"state is {action_state or 'missing'}, not PROMOTION REVIEW")
    if dep_rec.get("in_entry_band") is not True and trig_rec.get("in_entry_band") is not True:
        blockers.append("ticker is not confirmed in entry band")
    if dep_rec.get("below_stop") or trig_rec.get("below_stop"):
        blockers.append("ticker is below stop")

    if band.get("low") is None or band.get("high") is None:
        blockers.append("entry band missing from portfolio-config")
    if band.get("stop") is None:
        blockers.append("stop/invalidation missing from portfolio-config")
    if not tracked.get("sizing_tier"):
        blockers.append("sizing tier missing from portfolio-config")
    if not tracked.get("thesis_status"):
        blockers.append("thesis status missing from portfolio-config")
    if not tracked.get("macro_fit"):
        blockers.append("macro/regime fit missing from portfolio-config")

    queue_present = queue_contains(ticker)
    if require_queue and not queue_present:
        blockers.append("Promotion Review Queue row missing")

    owner_surfaces = {
        "technical_sheet": note_contains(TECHNICAL_SHEET, ticker),
        "trigger_note": note_contains(TRIGGER_NOTE, ticker),
        "portfolio_snapshot": note_contains(PORTFOLIO_SNAPSHOT, ticker),
        "risk_rules": RISK_RULES.exists(),
        "promotion_queue": queue_present,
    }
    if not owner_surfaces["trigger_note"]:
        blockers.append("Deployment Trigger Sheet owner surface does not reference ticker")
    if not owner_surfaces["portfolio_snapshot"]:
        blockers.append("Portfolio Snapshot owner surface does not reference ticker")
    if not owner_surfaces["technical_sheet"]:
        blockers.append("Technical Entry and Invalidation Sheet does not reference ticker")
    if not owner_surfaces["risk_rules"]:
        blockers.append("Risk Rules owner surface missing")

    cat_status, cat_blockers = catalyst_status(trig_rec, earn_rec)
    blockers.extend(cat_blockers)

    packet_result = None
    if packet_path:
        packet_result = run_packet_validator(packet_path)
        if not packet_result.get("ok"):
            blockers.append("candidate packet validator did not pass")

    gate_status = {
        "thesis": "pass" if tracked.get("thesis_status") else "missing",
        "macro_regime": "pass" if tracked.get("macro_fit") else "missing",
        "technical": "pass" if (dep_rec.get("in_entry_band") is True and not dep_rec.get("below_stop") and band.get("stop") is not None) else "failed",
        "catalyst": cat_status,
        "risk_sizing": "warning" if tracked.get("sizing_tier") else "missing",
    }
    if gate_status["risk_sizing"] == "warning":
        warnings.append("sizing tier exists, but explicit owner sizing approval is still required")

    shadow_canon = {
        "ok": True,
        "blockers": [],
        "note": "deployment-check has no deployable-now record for this ticker; review checker is non-authorizing",
    }
    if action_state in {"DEPLOYABLE", "DEPLOYABLE NOW"} and not queue_present:
        shadow_canon = {"ok": False, "blockers": ["deployable state without queue row"]}
        blockers.extend(shadow_canon["blockers"])

    blockers = list(dict.fromkeys(blockers))
    warnings = list(dict.fromkeys(warnings))
    auto_approval_blockers: list[str] = []
    if action_state != "PROMOTION REVIEW":
        auto_approval_blockers.append("action_state is not PROMOTION REVIEW")
    if tracked.get("coverage_lane") != "execution":
        auto_approval_blockers.append("coverage_lane is not execution")
    if tracked.get("workflow_state") not in {"ALMOST", "PROMOTION REVIEW"}:
        auto_approval_blockers.append("workflow_state is not ALMOST/PROMOTION REVIEW")
    if not queue_present:
        auto_approval_blockers.append("Promotion Review Queue row missing")
    missing_owner_surfaces = [name for name, present in owner_surfaces.items() if not present]
    if missing_owner_surfaces:
        auto_approval_blockers.append("owner surfaces missing: " + ", ".join(missing_owner_surfaces))
    for gate_name, expected in AUTO_APPROVAL_GATE_PATTERN.items():
        if gate_status.get(gate_name) != expected:
            auto_approval_blockers.append(f"{gate_name} gate is {gate_status.get(gate_name)!r}, expected {expected!r}")
    if blockers:
        auto_approval_blockers.append("readiness blockers are present")

    auto_approved = not auto_approval_blockers

    if blockers:
        status = "blocked"
    elif auto_approved:
        status = "auto_approved"
    else:
        status = "review_ready"

    if "ticker is not confirmed in entry band" in blockers or "ticker is below stop" in blockers:
        queue_judgment = "reject / return to almost"
    elif auto_approved:
        queue_judgment = "approve for deployable-now"
    else:
        queue_judgment = "hold in promotion review"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "ticker": ticker,
        "status": status,
        "ok": not blockers,
        "authorization_required": not auto_approved,
        "non_authorizing": False if auto_approved else True,
        "canonical_mutation_allowed": False,
        "deployable_now_authorized": auto_approved,
        "trade_execution_authorized": False,
        "auto_approval_scope": AUTO_APPROVAL_SCOPE,
        "action_state": action_state or None,
        "coverage_lane": tracked.get("coverage_lane"),
        "workflow_state": tracked.get("workflow_state"),
        "freshness": {
            "technical_age_hours": technical_age,
            "technical_stale_after_hours": technical_stale_after,
            "earnings_age_hours": earnings_age,
            "earnings_stale_after_hours": earnings_stale_after,
            "deployment_age_hours": deploy_age,
            "deployment_stale_after_hours": deploy_stale_after,
            "trigger_age_hours": trigger_age,
            "trigger_stale_after_hours": trigger_stale_after,
        },
        "machine_state": {
            "in_entry_band": dep_rec.get("in_entry_band"),
            "below_stop": dep_rec.get("below_stop"),
            "close": dep_rec.get("close") or trig_rec.get("close") or tech_rec.get("close"),
            "entry_band": {"low": band.get("low"), "high": band.get("high"), "label": band.get("label")},
            "stop": band.get("stop"),
            "days_to_earnings": trig_rec.get("days_to_earnings"),
        },
        "gate_status": gate_status,
        "queue_entry_present": queue_present,
        "owner_surfaces": owner_surfaces,
        "shadow_canon": shadow_canon,
        "packet_result": packet_result,
        "automated_queue_judgment": queue_judgment,
        "auto_approval": {
            "approved": auto_approved,
            "criteria": AUTO_APPROVAL_GATE_PATTERN,
            "scope": AUTO_APPROVAL_SCOPE,
            "blockers": auto_approval_blockers,
        },
        "allowed_owner_judgments": ["approve for deployable-now", "hold in promotion review", "reject / return to almost"],
        "blockers": blockers,
        "warnings": warnings,
        "next_action": "auto-approved for deployable-now status inside the workspace review layer; no trade execution or canonical note mutation was performed" if auto_approved else ("owner review may proceed, but deployable-now remains unauthorized until explicit approval" if not blockers else "clear blockers before owner promotion review"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only fail-closed promotion-review readiness checker.")
    parser.add_argument("--ticker", required=True, help="Ticker to review, e.g. JPM")
    parser.add_argument("--packet", help="Optional candidate packet JSON to include in the gate check")
    parser.add_argument("--out", help="Optional output JSON path. Defaults to tmp/promotion-review-check-<ticker>.json when --write is used.")
    parser.add_argument("--write", action="store_true", help="Write the JSON result to tmp/ or --out path")
    parser.add_argument("--require-queue", action="store_true", default=True, help="Require a Promotion Review Queue row")
    args = parser.parse_args()

    packet_path = Path(args.packet) if args.packet else None
    result = build_review(args.ticker, packet_path=packet_path, require_queue=args.require_queue)
    print(json.dumps(result, indent=2))
    if args.write:
        out = Path(args.out) if args.out else Path(str(OUT_DEFAULT).format(ticker=args.ticker.upper()))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
