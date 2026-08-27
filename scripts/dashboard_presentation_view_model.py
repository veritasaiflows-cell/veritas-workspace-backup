"""Build a compact dashboard presentation view model.

The view model is the UI-facing contract for the compact WF79 route. It is
fed by the dashboard DTO and adapter, not by embedding the full legacy
`dashboard-data.json` payload.

Authority: presentation/retrieval only. No proof deletion, dashboard behavior
replacement, canon/portfolio mutation, SQL-canon promotion, customer/public
output, paper/live/account action, or owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_daily_actionability_snapshot import OUT as ACTIONABILITY_SNAPSHOT, build_snapshot, write_snapshot

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DTO = TMP / "dashboard-presentation-dto.json"
ADAPTER = TMP / "dashboard-presentation-adapter.json"
COMPAT = TMP / "dashboard-presentation-compatibility-proof.json"
OUT = TMP / "dashboard-presentation-view-model.json"

FINANCE_PANEL_LABELS = {
    "command_today": "Today",
    "trust_and_freshness": "Trust",
    "deployment": "Capital",
    "market_macro": "Macro",
    "portfolio": "Portfolio",
    "technical": "Technicals",
    "fundamentals_earnings": "Fundamentals",
}

FINANCE_PANEL_ORDER = tuple(FINANCE_PANEL_LABELS)
NON_FINANCE_PANEL_IDS = {"workflow_pm"}
PM_COCKPIT_ROUTE = "http://127.0.0.1:8765/"

AUTHORITY_FALSE_FLAGS = (
    "dashboard_payload_replaced",
    "proof_deletion_allowed",
    "archive_or_cleanup_allowed",
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "sql_canon_promotion_allowed",
    "customer_or_public_output_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "owner_approval_inferred",
)


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def is_empty(value: Any) -> bool:
    return value is None or value == "" or value == [] or value == {}


def tone_for(severity: str, state: str) -> str:
    value = f"{severity} {state}".lower()
    if "critical" in value or "blocked" in value or "stale" in value:
        return "bad"
    if "warning" in value or "review" in value or "caution" in value:
        return "warn"
    if "ok" in value or "fresh" in value:
        return "ok"
    return "info"


def compact_join(items: list[Any], *, limit: int = 4) -> str:
    values = [str(item) for item in items if item]
    if not values:
        return "none"
    shown = values[:limit]
    suffix = f" (+{len(values) - limit} more)" if len(values) > limit else ""
    return ", ".join(shown) + suffix


def route_map(adapter: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    by_panel: dict[str, list[dict[str, Any]]] = {}
    for route in as_list(adapter.get("routes")):
        if not isinstance(route, dict):
            continue
        panel_id = route.get("compact_panel_id") or "_metadata"
        by_panel.setdefault(str(panel_id), []).append(route)
    return by_panel


def ensure_actionability_snapshot() -> dict[str, Any]:
    snapshot = build_snapshot()
    write_snapshot(snapshot)
    return snapshot


def actionability_overrides(panel_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    buckets = as_dict(snapshot.get("capital_buckets"))
    stale_sources = as_list(snapshot.get("stale_required_sources"))
    refresh_blockers = as_list(snapshot.get("refresh_blockers"))
    router = as_dict(snapshot.get("finance_warning_router"))
    if panel_id == "command_today":
        return {
            "headline": "Daily finance actionability after the latest refresh.",
            "state": snapshot.get("actionability_status"),
            "freshness": snapshot.get("source_freshness_status"),
            "severity": "critical" if snapshot.get("actionability_status") == "refresh_required_before_actionability" else "warning",
            "primary_reason": compact_join(refresh_blockers) if refresh_blockers else snapshot.get("actionability_reason"),
            "owner_action_required": "Refresh before relying on actionability." if snapshot.get("actionability_allowed") is False else "Review-only; owner approval still required for any capital or execution action.",
        }
    if panel_id == "trust_and_freshness":
        return {
            "headline": "Trust, freshness, and proof status for the finance snapshot.",
            "state": snapshot.get("source_trust_level"),
            "freshness": snapshot.get("source_freshness_status"),
            "severity": "critical" if stale_sources else ("warning" if router.get("caveat_section_count") else "info"),
            "primary_reason": f"{len(stale_sources)} stale required source(s); {router.get('caveat_section_count', 0)} caveat section(s); next refresh {snapshot.get('next_refresh_due')}.",
        }
    if panel_id == "deployment":
        owner_review = as_dict(buckets.get("owner_review"))
        pullback = as_dict(buckets.get("pullback_only"))
        below_stop = as_dict(buckets.get("below_stop"))
        deployable = as_dict(buckets.get("deployable_now"))
        return {
            "headline": "Capital review funnel: deployable, owner-review, pullback, below-stop.",
            "state": "review_only_capital_funnel",
            "freshness": snapshot.get("source_freshness_status"),
            "severity": "warning" if owner_review.get("count") or pullback.get("count") or below_stop.get("count") else "info",
            "primary_reason": (
                f"deployable={deployable.get('count', 0)}, owner_review={owner_review.get('count', 0)}, "
                f"pullback_only={pullback.get('count', 0)}, below_stop={below_stop.get('count', 0)}; "
                f"owner_review_names={compact_join(as_list(owner_review.get('tickers')))}"
            ),
        }
    if panel_id == "market_macro":
        return {
            "headline": "Macro and energy caveats for the daily finance read.",
            "state": snapshot.get("macro_posture") or snapshot.get("macro_status"),
            "freshness": snapshot.get("source_freshness_status"),
            "severity": "warning" if snapshot.get("macro_status") == "warning" or snapshot.get("energy_status") == "warning" else "info",
            "primary_reason": snapshot.get("macro_caveat") or snapshot.get("energy_caveat") or "Macro/energy caveats loaded.",
        }
    if panel_id == "fundamentals_earnings":
        return {
            "headline": "Fundamentals and earnings caveats for decision-grade use.",
            "state": snapshot.get("fundamentals_status"),
            "freshness": snapshot.get("source_freshness_status"),
            "severity": "critical" if snapshot.get("fundamentals_critical_count") else ("warning" if snapshot.get("fundamentals_warning_count") else "info"),
            "primary_reason": f"critical={snapshot.get('fundamentals_critical_count')}, warnings={snapshot.get('fundamentals_warning_count')}",
        }
    return {}


def compact_panel(panel: dict[str, Any], routes: list[dict[str, Any]], snapshot: dict[str, Any]) -> dict[str, Any]:
    panel_id = str(panel.get("id") or "")
    overrides = actionability_overrides(panel_id, snapshot)
    severity = str(panel.get("severity") or "info")
    state = str(panel.get("state") or "unknown")
    severity = str(overrides.get("severity") or severity)
    state = str(overrides.get("state") or state)
    proof_refs = [str(ref) for ref in as_list(panel.get("proof_ref")) if ref]
    if panel_id in FINANCE_PANEL_LABELS and relpath(ACTIONABILITY_SNAPSHOT) not in proof_refs:
        proof_refs.append(relpath(ACTIONABILITY_SNAPSHOT))
    route_sections = [str(route.get("section")) for route in routes if route.get("section")]
    return {
        "id": panel_id,
        "label": FINANCE_PANEL_LABELS.get(panel_id, panel_id),
        "headline": overrides.get("headline") or panel.get("headline"),
        "state": state,
        "freshness": overrides.get("freshness") or panel.get("freshness"),
        "severity": severity,
        "tone": tone_for(severity, state),
        "primary_reason": overrides.get("primary_reason") or panel.get("primary_reason"),
        "owner_action_required": overrides.get("owner_action_required") or panel.get("owner_action_required"),
        "authority_summary": panel.get("authority_summary"),
        "source_sections": as_list(panel.get("source_sections")),
        "route_sections": route_sections,
        "route_count": len(routes),
        "source_row_count": panel.get("source_row_count"),
        "proof_ref": proof_refs,
        "drilldown": {
            "source_ref": panel.get("source_ref"),
            "proof_ref": proof_refs,
            "legacy_passthrough_available": any(route.get("source_ref") for route in routes),
        },
    }


def build_view_model() -> dict[str, Any]:
    snapshot = ensure_actionability_snapshot()
    dto = as_dict(read_json(DTO)) if DTO.exists() else {}
    adapter = as_dict(read_json(ADAPTER)) if ADAPTER.exists() else {}
    compat = as_dict(read_json(COMPAT)) if COMPAT.exists() else {}
    routes_by_panel = route_map(adapter)
    source_panels = [panel for panel in as_list(dto.get("panels")) if isinstance(panel, dict)]
    panel_lookup = {str(panel.get("id")): panel for panel in source_panels}
    panels = []
    for panel_id in FINANCE_PANEL_ORDER:
        panel = panel_lookup.get(panel_id)
        if isinstance(panel, dict):
            panels.append(compact_panel(panel, routes_by_panel.get(panel_id, []), snapshot))
    metadata_routes = routes_by_panel.get("_metadata", [])
    route_counts = as_dict(as_dict(adapter.get("summary")).get("route_counts"))
    return {
        "schema_version": "dashboard_presentation_view_model.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok",
        "title": "Veritas Finance Command Center",
        "source_payload_embedded": False,
        "source_artifacts": {
            "dto": relpath(DTO),
            "adapter": relpath(ADAPTER),
            "compatibility_proof": relpath(COMPAT),
            "finance_daily_actionability_snapshot": relpath(ACTIONABILITY_SNAPSHOT),
        },
        "authority": {
            "review_only": True,
            "dashboard_payload_replaced": False,
            "proof_deletion_allowed": False,
            "archive_or_cleanup_allowed": False,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "sql_canon_promotion_allowed": False,
            "customer_or_public_output_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "summary": {
            "panel_count": len(panels),
            "critical": sum(1 for panel in panels if panel.get("severity") == "critical"),
            "warning": sum(1 for panel in panels if panel.get("severity") == "warning"),
            "info": sum(1 for panel in panels if panel.get("severity") == "info"),
            "finance_panel_count": len(panels),
            "non_finance_panel_count": len([panel for panel in source_panels if str(panel.get("id")) in NON_FINANCE_PANEL_IDS]),
            "workflow_pm_migrated_to_pm_cockpit": True,
            "adapter_mode": adapter.get("adapter_mode"),
            "route_counts": route_counts,
            "metadata_route_count": len(metadata_routes),
            "compact_dto_pct_of_payload": as_dict(compat.get("size")).get("compact_dto_pct_of_payload"),
            "current_html_replacement_safe": False,
            "compact_route_default_ready": True,
        },
        "daily_actionability": {
            "snapshot": relpath(ACTIONABILITY_SNAPSHOT),
            "generated_at_utc": snapshot.get("generated_at_utc"),
            "operating_window": snapshot.get("operating_window"),
            "daily_packet_window": snapshot.get("daily_packet_window"),
            "market_data_as_of": snapshot.get("market_data_as_of"),
            "latest_required_input_generated_at_utc": snapshot.get("latest_required_input_generated_at_utc"),
            "snapshot_newer_than_latest_required_input": snapshot.get("snapshot_newer_than_latest_required_input"),
            "actionability_status": snapshot.get("actionability_status"),
            "actionability_mode": snapshot.get("actionability_mode"),
            "actionability_permission": snapshot.get("actionability_permission"),
            "actionability_allowed": snapshot.get("actionability_allowed"),
            "actionability_reason": snapshot.get("actionability_reason"),
            "refresh_blockers": snapshot.get("refresh_blockers"),
            "capital_buckets": snapshot.get("capital_buckets"),
            "deployable_now_count": snapshot.get("deployable_now_count"),
            "owner_review_count": snapshot.get("owner_review_count"),
            "pullback_only_count": snapshot.get("pullback_only_count"),
            "below_stop_count": snapshot.get("below_stop_count"),
            "blocked_or_stale_count": snapshot.get("blocked_or_stale_count"),
            "fundamentals_status": snapshot.get("fundamentals_status"),
            "fundamentals_warning_count": snapshot.get("fundamentals_warning_count"),
            "fundamentals_critical_count": snapshot.get("fundamentals_critical_count"),
            "fundamentals_caveats": snapshot.get("fundamentals_caveats"),
            "macro_status": snapshot.get("macro_status"),
            "macro_posture": snapshot.get("macro_posture"),
            "macro_caveat": snapshot.get("macro_caveat"),
            "energy_status": snapshot.get("energy_status"),
            "energy_caveat": snapshot.get("energy_caveat"),
            "source_freshness_status": snapshot.get("source_freshness_status"),
            "source_trust_level": snapshot.get("source_trust_level"),
            "stale_required_sources": snapshot.get("stale_required_sources"),
            "finance_warning_router": snapshot.get("finance_warning_router"),
            "proof_artifacts": snapshot.get("proof_artifacts"),
            "authority_boundary": snapshot.get("authority_boundary"),
            "next_refresh_due": snapshot.get("next_refresh_due"),
        },
        "pm_cockpit_route": {
            "url": PM_COCKPIT_ROUTE,
            "label": "Veritas PM Cockpit",
            "purpose": "Workflows, lanes, handoffs, sources, closeout, SMB/Retail/Academy/SQL, and non-finance notes.",
        },
        "metadata_strip": [
            {
                "section": route.get("section"),
                "route_kind": route.get("route_kind"),
                "source_ref": route.get("source_ref"),
                "reason": route.get("reason"),
            }
            for route in metadata_routes
        ],
        "panels": panels,
        "next_gate": {
            "required_before_legacy_payload_replacement": [
                "parallel renderer proof stays green",
                "view model acceptance stays green",
                "current dashboard acceptance stays green",
                "rollback route remains documented",
            ],
            "rollback": "Keep tmp/dashboard-data.json and tmp/veritas-command-center.html as the stable legacy route.",
        },
    }


def validate(model: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    authority = as_dict(model.get("authority"))
    if authority.get("review_only") is not True:
        findings.append({"severity": "critical", "issue": "review_only_not_true"})
    for flag in AUTHORITY_FALSE_FLAGS:
        if authority.get(flag) is not False:
            findings.append({"severity": "critical", "issue": "authority_flag_not_false", "flag": flag, "value": authority.get(flag)})
    if model.get("source_payload_embedded") is not False:
        findings.append({"severity": "critical", "issue": "source_payload_embedded"})
    panels = as_list(model.get("panels"))
    if len(panels) != len(FINANCE_PANEL_ORDER):
        findings.append({"severity": "critical", "issue": "expected_finance_panel_count", "actual": len(panels), "expected": len(FINANCE_PANEL_ORDER)})
    if any(as_dict(panel).get("id") in NON_FINANCE_PANEL_IDS for panel in panels):
        findings.append({"severity": "critical", "issue": "non_finance_panel_present"})
    actionability = as_dict(model.get("daily_actionability"))
    if not actionability.get("actionability_status"):
        findings.append({"severity": "critical", "issue": "missing_daily_actionability_status"})
    for key in ("market_data_as_of", "next_refresh_due", "actionability_permission", "proof_artifacts", "authority_boundary"):
        if is_empty(actionability.get(key)):
            findings.append({"severity": "critical", "issue": "daily_actionability_missing_field", "field": key})
    if as_dict(model.get("summary")).get("workflow_pm_migrated_to_pm_cockpit") is not True:
        findings.append({"severity": "critical", "issue": "workflow_pm_not_migrated_to_pm_cockpit"})
    if as_dict(model.get("pm_cockpit_route")).get("url") != PM_COCKPIT_ROUTE:
        findings.append({"severity": "critical", "issue": "missing_pm_cockpit_route"})
    for panel in panels:
        panel = as_dict(panel)
        for key in ("id", "label", "headline", "state", "freshness", "severity", "primary_reason", "authority_summary"):
            if panel.get(key) in {None, ""}:
                findings.append({"severity": "critical", "issue": "panel_missing_field", "panel": panel.get("id"), "field": key})
        if panel.get("authority_summary") != "review_only_no_approval_no_execution":
            findings.append({"severity": "critical", "issue": "panel_authority_not_clamped", "panel": panel.get("id")})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Build compact dashboard presentation view model.")
    parser.add_argument("--write", action="store_true", help="Write tmp/dashboard-presentation-view-model.json.")
    parser.add_argument("--validate", action="store_true", help="Return nonzero on critical validation failures.")
    args = parser.parse_args()
    model = build_view_model()
    findings = validate(model) if args.validate else []
    model["validation"] = {
        "status": "ok" if not any(f.get("severity") == "critical" for f in findings) else "blocked",
        "critical": sum(1 for f in findings if f.get("severity") == "critical"),
        "warning": sum(1 for f in findings if f.get("severity") == "warning"),
        "findings": findings,
    }
    if args.write:
        OUT.write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    print(
        "dashboard_presentation_view_model: "
        f"{model['validation']['status']} ({model['summary']['panel_count']} panels)"
    )
    return 1 if args.validate and model["validation"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
