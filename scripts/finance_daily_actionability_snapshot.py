"""Build the daily finance actionability snapshot for the Command Center.

The snapshot is a small presentation contract for WF79. It summarizes the
latest finance refresh state, capital-review buckets, fundamentals caveats,
macro/energy caveats, and proof routes. It is review-only and never grants
capital, execution, brokerage, account, or canon/portfolio mutation authority.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover - ancient Python fallback only.
    ZoneInfo = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
OUT = TMP / "finance-daily-actionability-snapshot.json"

PHOENIX_TZ = "America/Phoenix"
STALE_DAILY_PACKET_HOURS = 24.0

BASE_SOURCE_FILES = {
    "dashboard": "dashboard-data.json",
    "deployment": "deployment-check.json",
    "fundamentals": "fundamental-metrics-validation.json",
    "macro": "macro-signal-spine.json",
    "energy": "macro-energy-supply.json",
    "warning_router": "finance-evidence-warning-router.json",
}

WINDOW_PACKET_FILES = {
    "pre_market": {
        "daily_review": "daily-review-objects-morning.json",
        "market_intelligence": "market-intelligence-events-morning.json",
    },
    "morning": {
        "daily_review": "daily-review-objects-morning.json",
        "market_intelligence": "market-intelligence-events-morning.json",
    },
    "midday": {
        "daily_review": "daily-review-objects-morning.json",
        "market_intelligence": "market-intelligence-events-morning.json",
    },
    "post_close": {
        "daily_review": "daily-review-objects-post-close.json",
        "market_intelligence": "market-intelligence-events-post-close.json",
    },
    "after_hours": {
        "daily_review": "daily-review-objects-post-close.json",
        "market_intelligence": "market-intelligence-events-post-close.json",
    },
    "post_earnings": {
        "daily_review": "daily-review-objects-post-earnings.json",
        "market_intelligence": "market-intelligence-events-post-earnings.json",
    },
    "sunday": {
        "daily_review": "daily-review-objects-sunday.json",
        "market_intelligence": "market-intelligence-events-sunday.json",
    },
}

AUTHORITY_FALSE_FLAGS = (
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "sql_canon_promotion_allowed",
    "customer_or_public_output_allowed",
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "owner_approval_inferred",
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_z(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def read_json(path: Path) -> dict[str, Any]:
    try:
        return as_dict(json.loads(path.read_text(encoding="utf-8")))
    except FileNotFoundError:
        return {}


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def artifact_generated_at(path: Path, payload: dict[str, Any]) -> datetime | None:
    for key in ("generated_at_utc", "generated_at", "as_of_utc", "updated_at_utc"):
        parsed = parse_datetime(payload.get(key))
        if parsed:
            return parsed
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
    return None


def artifact_record(name: str, path: Path, payload: dict[str, Any], now: datetime) -> dict[str, Any]:
    generated = artifact_generated_at(path, payload)
    age_hours = round((now - generated).total_seconds() / 3600, 2) if generated else None
    return {
        "name": name,
        "path": relpath(path),
        "exists": path.exists(),
        "generated_at_utc": iso_z(generated),
        "age_hours": age_hours,
        "status": payload.get("status") or as_dict(payload.get("validation")).get("status"),
    }


def phoenix_now(now: datetime) -> datetime:
    if ZoneInfo is None:
        return now.astimezone(timezone.utc)
    return now.astimezone(ZoneInfo(PHOENIX_TZ))


def operating_window(now: datetime) -> str:
    local = phoenix_now(now)
    if local.weekday() == 6:
        return "sunday"
    clock = local.time()
    if clock < time(6, 30):
        return "pre_market"
    if clock < time(10, 30):
        return "morning"
    if clock < time(13, 0):
        return "midday"
    if clock < time(15, 30):
        return "post_close"
    return "after_hours"


def source_files_for_window(window: str) -> dict[str, str]:
    return {**BASE_SOURCE_FILES, **WINDOW_PACKET_FILES.get(window, WINDOW_PACKET_FILES["post_close"])}


def next_weekday(value: datetime) -> datetime:
    candidate = value
    while candidate.weekday() >= 5:
        candidate += timedelta(days=1)
    return candidate


def next_refresh_due(now: datetime) -> str:
    local = phoenix_now(now)
    schedule = (
        time(7, 20),
        time(12, 15),
        time(13, 30),
    )
    for due_time in schedule:
        if local.time() < due_time:
            due = local.replace(hour=due_time.hour, minute=due_time.minute, second=0, microsecond=0)
            return iso_z(due.astimezone(timezone.utc)) or ""
    due = next_weekday((local + timedelta(days=1)).replace(hour=7, minute=20, second=0, microsecond=0))
    return iso_z(due.astimezone(timezone.utc)) or ""


def list_field(payload: dict[str, Any], *keys: str) -> list[str]:
    value: Any = payload
    for key in keys:
        value = as_dict(value).get(key)
    return [str(item) for item in as_list(value) if item]


def stale_required_sources(dashboard: dict[str, Any]) -> list[dict[str, Any]]:
    source_freshness = as_dict(dashboard.get("source_freshness") or as_dict(dashboard.get("trust")).get("source_freshness"))
    rows: list[dict[str, Any]] = []
    for source in as_list(source_freshness.get("sources")):
        source = as_dict(source)
        if source.get("required") is True and str(source.get("classification")) == "stale":
            rows.append(
                {
                    "source_key": source.get("source_key"),
                    "path": source.get("path"),
                    "classification": source.get("classification"),
                    "age_hours": source.get("age_hours"),
                    "stale_after_hours": source.get("stale_after_hours"),
                    "criticality": source.get("criticality"),
                }
            )
    return rows


def daily_packet_stale(record: dict[str, Any]) -> bool:
    age = record.get("age_hours")
    return record.get("exists") is not True or not isinstance(age, (int, float)) or age > STALE_DAILY_PACKET_HOURS


def latest_generated_at(records: dict[str, dict[str, Any]]) -> datetime | None:
    values = [parse_datetime(record.get("generated_at_utc")) for record in records.values()]
    parsed = [value for value in values if value is not None]
    return max(parsed) if parsed else None


def build_snapshot(*, tmp: Path = TMP, now: datetime | None = None) -> dict[str, Any]:
    current = (now or now_utc()).astimezone(timezone.utc)
    window = operating_window(current)
    source_files = source_files_for_window(window)
    paths = {name: tmp / filename for name, filename in source_files.items()}
    payloads = {name: read_json(path) for name, path in paths.items()}
    artifacts = {name: artifact_record(name, paths[name], payloads[name], current) for name in source_files}

    dashboard = payloads["dashboard"]
    deployment = payloads["deployment"]
    fundamentals = payloads["fundamentals"]
    macro = payloads["macro"]
    energy = payloads["energy"]
    warning_router = payloads["warning_router"]

    deployment_summary = as_dict(deployment.get("summary"))
    deployable = list_field(deployment, "summary", "deployable")
    promotion_review = list_field(deployment, "summary", "promotion_review")
    entry_policy_review = list_field(deployment, "summary", "entry_policy_review")
    almost = list_field(deployment, "summary", "almost")
    below_stop = list_field(deployment, "summary", "below_stop")
    blocked = list_field(deployment, "summary", "blocked") + list_field(deployment, "summary", "error")
    watch = list_field(deployment, "summary", "watch") + list_field(deployment, "summary", "bench")

    source_freshness = as_dict(dashboard.get("source_freshness") or as_dict(dashboard.get("trust")).get("source_freshness"))
    stale_sources = stale_required_sources(dashboard)
    router_summary = as_dict(warning_router.get("summary"))
    macro_summary = as_dict(macro.get("summary"))
    energy_summary = as_dict(energy.get("summary"))
    fundamentals_summary = as_dict(fundamentals.get("summary"))

    daily_review_stale = daily_packet_stale(artifacts["daily_review"])
    market_intelligence_stale = daily_packet_stale(artifacts["market_intelligence"])
    router_blocking = int(router_summary.get("blocking_section_count") or 0)
    fundamentals_critical = int(fundamentals_summary.get("critical") or 0)
    latest_input_generated = latest_generated_at(artifacts)
    snapshot_newer_than_inputs = latest_input_generated is None or current >= latest_input_generated
    refresh_blockers: list[str] = []
    if dashboard.get("exec_freshness") == "stale":
        refresh_blockers.append("dashboard_exec_freshness_stale")
    if source_freshness.get("presentation_allowed") is False:
        refresh_blockers.append("dashboard_presentation_not_allowed")
    refresh_blockers.extend(f"stale_required_source:{row.get('source_key')}" for row in stale_sources if row.get("source_key"))
    if daily_review_stale:
        refresh_blockers.append(f"daily_review_packet_stale:{source_files['daily_review']}")
    if market_intelligence_stale:
        refresh_blockers.append(f"market_intelligence_packet_stale:{source_files['market_intelligence']}")
    refresh_required = (
        dashboard.get("exec_freshness") == "stale"
        or source_freshness.get("presentation_allowed") is False
        or bool(stale_sources)
        or daily_review_stale
        or market_intelligence_stale
    )

    if refresh_required:
        actionability_status = "refresh_required_before_actionability"
        actionability_mode = "blocked_refresh_required"
        actionability_permission = "no"
        actionability_reason = "Refresh required before relying on actionability: " + ", ".join(refresh_blockers)
    elif router_blocking or fundamentals_critical:
        actionability_status = "blocked_by_evidence"
        actionability_mode = "blocked_evidence"
        actionability_permission = "no"
        actionability_reason = "Evidence warnings include a blocking section or critical fundamentals issue."
    elif deployable or promotion_review or entry_policy_review or almost:
        actionability_status = "review_only_actionability"
        actionability_mode = "review_only"
        actionability_permission = "review_only"
        actionability_reason = "Capital review buckets exist, but execution remains owner-gated."
    else:
        actionability_status = "monitor_only"
        actionability_mode = "monitor_only"
        actionability_permission = "review_only"
        actionability_reason = "No deployable-now or owner-review bucket is currently active."

    owner_review = sorted(set(promotion_review + entry_policy_review))
    all_blocked_or_stale = sorted(set(blocked + [str(row.get("source_key")) for row in stale_sources if row.get("source_key")]))

    return {
        "schema_version": "finance_daily_actionability_snapshot.v1",
        "generated_at_utc": iso_z(current),
        "operating_window": window,
        "daily_packet_window": window,
        "market_data_as_of": artifacts["deployment"].get("generated_at_utc") or artifacts["dashboard"].get("generated_at_utc"),
        "next_refresh_due": next_refresh_due(current),
        "latest_required_input_generated_at_utc": iso_z(latest_input_generated),
        "snapshot_newer_than_latest_required_input": snapshot_newer_than_inputs,
        "actionability_status": actionability_status,
        "actionability_mode": actionability_mode,
        "actionability_permission": actionability_permission,
        "actionability_allowed": actionability_status in {"review_only_actionability", "monitor_only"},
        "actionability_reason": actionability_reason,
        "refresh_blockers": refresh_blockers,
        "capital_buckets": {
            "deployable_now": {"count": len(deployable), "tickers": deployable},
            "owner_review": {"count": len(owner_review), "tickers": owner_review},
            "pullback_only": {"count": len(almost), "tickers": almost},
            "below_stop": {"count": len(below_stop), "tickers": below_stop},
            "blocked_or_stale": {"count": len(all_blocked_or_stale), "items": all_blocked_or_stale},
            "watch_research": {"count": len(watch), "tickers": watch},
        },
        "deployable_now_count": len(deployable),
        "owner_review_count": len(owner_review),
        "pullback_only_count": len(almost),
        "below_stop_count": len(below_stop),
        "blocked_or_stale_count": len(all_blocked_or_stale),
        "fundamentals_status": fundamentals.get("status"),
        "fundamentals_warning_count": int(fundamentals_summary.get("warning") or 0),
        "fundamentals_critical_count": fundamentals_critical,
        "fundamentals_caveats": as_dict(as_dict(warning_router.get("sections")).get("fundamentals")).get("caveats") or [],
        "macro_status": macro.get("status"),
        "macro_posture": macro_summary.get("macro_posture"),
        "macro_caveat": as_dict(as_dict(warning_router.get("sections")).get("macro_signal")).get("answer_caveat"),
        "energy_status": energy.get("status"),
        "energy_caveat": as_dict(as_dict(warning_router.get("sections")).get("energy_supply")).get("answer_caveat"),
        "source_freshness_status": source_freshness.get("overall_classification") or dashboard.get("exec_freshness"),
        "source_trust_level": source_freshness.get("trust_level"),
        "stale_required_sources": stale_sources,
        "finance_warning_router": {
            "status": warning_router.get("status"),
            "blocking_section_count": router_blocking,
            "caveat_section_count": int(router_summary.get("caveat_section_count") or 0),
            "caveat_sections": as_list(router_summary.get("caveat_sections")),
            "customer_output_allowed": bool(router_summary.get("customer_output_allowed")),
        },
        "daily_review_stale": daily_review_stale,
        "market_intelligence_stale": market_intelligence_stale,
        "required_inputs": artifacts,
        "proof_artifacts": {
            "dashboard": relpath(paths["dashboard"]),
            "deployment": relpath(paths["deployment"]),
            "fundamentals": relpath(paths["fundamentals"]),
            "macro": relpath(paths["macro"]),
            "energy": relpath(paths["energy"]),
            "warning_router": relpath(paths["warning_router"]),
            "daily_review": relpath(paths["daily_review"]),
            "market_intelligence": relpath(paths["market_intelligence"]),
        },
        "authority_boundary": {
            "review_only": True,
            "capital_review_is_owner_gated": True,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "customer_or_public_output_allowed": False,
            "capital_deployment_approved": False,
            "trade_or_execution_approved": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "money_movement_allowed": False,
            "owner_approval_inferred": False,
        },
        "source_notes": {
            "deployment_summary_keys": sorted(deployment_summary.keys()),
            "stale_daily_packet_hours": STALE_DAILY_PACKET_HOURS,
            "window_packet_files": WINDOW_PACKET_FILES,
            "serving_purpose": "Finance Command Center answers capital/actionability review. PM cockpit owns workflows, lanes, handoffs, sources, and non-finance state.",
            "pm_cockpit_url": "http://127.0.0.1:8765/",
        },
    }


def validate(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key in (
        "generated_at_utc",
        "operating_window",
        "market_data_as_of",
        "next_refresh_due",
        "latest_required_input_generated_at_utc",
        "actionability_status",
        "actionability_mode",
        "actionability_permission",
        "capital_buckets",
        "fundamentals_status",
        "macro_status",
        "energy_status",
        "source_freshness_status",
        "proof_artifacts",
        "authority_boundary",
    ):
        value = snapshot.get(key)
        if value is None or value == "" or value == []:
            findings.append({"severity": "critical", "issue": "missing_required_field", "field": key})
    authority = as_dict(snapshot.get("authority_boundary"))
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for flag in AUTHORITY_FALSE_FLAGS:
        if authority.get(flag) is not False:
            findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": flag, "value": authority.get(flag)})
    for name, record in as_dict(snapshot.get("required_inputs")).items():
        if as_dict(record).get("exists") is not True:
            findings.append({"severity": "critical", "issue": "required_input_missing", "input": name, "path": as_dict(record).get("path")})
    if snapshot.get("actionability_status") == "review_only_actionability" and snapshot.get("owner_review_count", 0) == 0 and snapshot.get("deployable_now_count", 0) == 0:
        findings.append({"severity": "warning", "issue": "review_actionability_without_capital_bucket"})
    return findings


def write_snapshot(snapshot: dict[str, Any], out: Path = OUT) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build finance daily actionability snapshot.")
    parser.add_argument("--write", action="store_true", help="Write tmp/finance-daily-actionability-snapshot.json.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero on critical validation failures.")
    args = parser.parse_args()
    snapshot = build_snapshot()
    findings = validate(snapshot) if args.validate else []
    snapshot["validation"] = {
        "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked",
        "critical": sum(1 for f in findings if f.get("severity") == "critical"),
        "warning": sum(1 for f in findings if f.get("severity") == "warning"),
        "findings": findings,
    }
    if args.write:
        write_snapshot(snapshot)
        print(f"wrote {relpath(OUT)}")
    print(
        "finance_daily_actionability_snapshot: "
        f"{snapshot['validation']['status']} ({snapshot['actionability_status']})"
    )
    return 1 if args.validate and snapshot["validation"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
