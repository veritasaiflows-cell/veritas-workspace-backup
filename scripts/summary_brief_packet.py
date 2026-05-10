from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
SCHEMA_VERSION = 1
WORKFLOW = "WF37"

OWNER_LAYERS = [
    "03. Portfolio/Portfolio Snapshot.md",
    "03. Portfolio/Deployment Trigger Sheet.md",
    "05. Intelligence/Weekly Positioning Review.md",
    "05. Intelligence/Event Calendar.md",
]

WINDOW_SPECS: dict[str, dict[str, Any]] = {
    "morning": {
        "output": TMP / "premarket-brief-input.json",
        "review_output": WORKSPACE / "01. Dashboards" / "Review-Only Briefs" / "Pre-Market" / "{date}.md",
        "target_note": "01. Dashboards/Pre-Market Brief/{date}.md",
        "review_window": "pre-market",
        "narrative_goal": "Produce a commercial-grade pre-market brief that highlights trust, catalysts, setup discipline, and owner-first routing without publishing deployable-now state.",
        "required": {
            "premarket_snapshot": TMP / "premarket-snapshot.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "market_state": TMP / "market-state.json",
            "trigger_sheet": TMP / "trigger-sheet.json",
            "earnings_calendar": TMP / "earnings-calendar.json",
        },
        "optional": {
            "dashboard_delta": TMP / "dashboard-delta.json",
            "deployment_check": TMP / "deployment-check.json",
        },
        "focus_questions": [
            "What actually matters before the open, and what only looks urgent?",
            "Which catalysts or unresolved truths materially limit confidence this morning?",
            "Which owner notes must be read before any name is treated as actionable?",
        ],
    },
    "post-close": {
        "output": TMP / "postclose-brief-input.json",
        "review_output": WORKSPACE / "01. Dashboards" / "Review-Only Briefs" / "Post-Close" / "{date}.md",
        "target_note": "01. Dashboards/Daily Executive Summary/{date}.md",
        "review_window": "post-close",
        "narrative_goal": "Produce a commercial-grade post-close brief that explains what changed, what matters for the next session, and what remains unresolved without turning the summary into a shadow deployment board.",
        "required": {
            "postmarket_snapshot": TMP / "postmarket-snapshot.json",
            "daily_executive_brief": TMP / "daily-executive-brief.json",
            "dashboard_validation": TMP / "dashboard-validation.json",
            "market_state": TMP / "market-state.json",
            "trigger_sheet": TMP / "trigger-sheet.json",
            "deployment_check": TMP / "deployment-check.json",
            "post_earnings_prep": TMP / "post-earnings-prep.json",
        },
        "optional": {
            "dashboard_delta": TMP / "dashboard-delta.json",
            "earnings_calendar": TMP / "earnings-calendar.json",
        },
        "focus_questions": [
            "What changed materially versus the prior dashboard run?",
            "Which names are closest to actionable without being misrepresented as deployable now?",
            "Which unresolved truths or trust warnings still block a cleaner conclusion?",
        ],
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only packet input for AI-authored daily summary briefs.")
    parser.add_argument("--window", required=True, choices=sorted(WINDOW_SPECS.keys()))
    return parser.parse_args()



def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")



def load_json(path: Path) -> dict[str, Any] | None:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else None



def generated_at_for(path: Path, data: dict[str, Any] | None) -> str:
    if data:
        for key in ("generated_at_utc", "generated_at"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value
    if not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")



def artifact_record(path: Path, required: bool) -> dict[str, Any]:
    data = load_json(path)
    return {
        "path": str(path.relative_to(WORKSPACE)).replace("\\", "/"),
        "required": required,
        "exists": path.exists(),
        "generated_at_utc": generated_at_for(path, data),
        "status": "ok" if data is not None or path.exists() else "missing",
    }



def validation_summary(validation: dict[str, Any] | None) -> dict[str, Any]:
    warnings = ((validation or {}).get("warnings") or []) if isinstance(validation, dict) else []
    summary = ((validation or {}).get("summary") or {}) if isinstance(validation, dict) else {}
    overall = str((validation or {}).get("overall") or "unknown")
    return {
        "overall": overall,
        "critical": int(summary.get("critical", 0) or 0),
        "warning": int(summary.get("warning", 0) or 0),
        "info": int(summary.get("info", 0) or 0),
        "warning_messages": [str(item.get("message")) for item in warnings if isinstance(item, dict) and item.get("message")],
    }



def trust_block(window: str, validation: dict[str, Any] | None, primary: dict[str, Any] | None) -> dict[str, Any]:
    validation_info = validation_summary(validation)
    blocked = validation_info["critical"] > 0
    if window == "post-close" and primary:
        blocked = blocked or bool(primary.get("trust_gate_blocked"))
    confidence = "review_required"
    if not blocked and validation_info["warning"] == 0:
        confidence = "bounded_clean"
    return {
        "consumer_posture": "review_only",
        "trust_level": confidence,
        "trust_gate_blocked": blocked,
        "validation": validation_info,
        "trust_reason": (primary or {}).get("trust_reason") or "dashboard validation governs trust posture",
    }



def state_summary(window: str, primary: dict[str, Any] | None, secondary: dict[str, Any] | None) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "deployable_now": list((primary or {}).get("deployable_now") or []),
        "almost_deployable": list((primary or {}).get("almost_deployable") or []),
        "blocked": list((primary or {}).get("blocked") or []),
    }
    if window == "post-close":
        summary["bench"] = list((secondary or {}).get("bench") or [])
        summary["below_stop"] = list((secondary or {}).get("below_stop") or [])
    return summary



def unresolved_truths(window: str, validation: dict[str, Any] | None, primary: dict[str, Any] | None) -> list[str]:
    items = []
    for message in validation_summary(validation)["warning_messages"]:
        items.append(message)
    if window == "morning":
        items.append("Do not publish deployable-now state from the packet alone; owner notes remain authoritative.")
    else:
        items.append("Do not treat post-close summary language as authority to promote, demote, or clear blockers without owner-note confirmation.")
    if primary and primary.get("trust_gate_blocked"):
        items.append(str(primary.get("trust_reason") or "Primary summary packet reported blocked trust state."))
    return items



def build_packet(window: str) -> dict[str, Any]:
    spec = WINDOW_SPECS[window]
    required_records = {name: artifact_record(path, True) for name, path in spec["required"].items()}
    optional_records = {name: artifact_record(path, False) for name, path in spec["optional"].items()}

    primary_key = "premarket_snapshot" if window == "morning" else "postmarket_snapshot"
    primary = load_json(spec["required"][primary_key])
    daily_brief = load_json(spec["required"].get("daily_executive_brief", Path("missing"))) if window == "post-close" else None
    validation = load_json(spec["required"]["dashboard_validation"])
    market_state = load_json(spec["required"]["market_state"])

    note_date = (
        (primary or {}).get("snapshot_date")
        or (daily_brief or {}).get("brief_date")
        or datetime.now().date().isoformat()
    )
    market_data_as_of = (
        (primary or {}).get("market_data_as_of")
        or (daily_brief or {}).get("market_data_as_of")
        or ((market_state or {}).get("last_trading_day") if market_state else None)
        or "unknown"
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "workflow": WORKFLOW,
        "generated_at_utc": utc_now(),
        "window": window,
        "review_window": spec["review_window"],
        "review_output_path": str(Path(str(spec["review_output"]).format(date=note_date)).relative_to(WORKSPACE)).replace("\\", "/"),
        "target_note": spec["target_note"].format(date=note_date),
        "target_posture": "commercial_review_brief",
        "consumer_posture": "review_only",
        "canonical_mutation_allowed": False,
        "market_data_as_of": market_data_as_of,
        "note_date": note_date,
        "owner_layers": OWNER_LAYERS,
        "source_artifacts": {
            "required": required_records,
            "optional": optional_records,
        },
        "trust": trust_block(window, validation, daily_brief if window == "post-close" else primary),
        "state_summary": state_summary(window, primary, daily_brief),
        "unresolved_truths": unresolved_truths(window, validation, daily_brief if window == "post-close" else primary),
        "focus_questions": list(spec["focus_questions"]),
        "narrative_goal": spec["narrative_goal"],
        "allowed_claims": [
            "freshness and review availability",
            "owner-first routing",
            "unresolved-truth warnings",
            "bounded orientation summary",
        ],
        "forbidden_claims": [
            "deployable-now publication from the brief alone",
            "owner-blocker clearance without owner-note confirmation",
            "silent conflict smoothing between owner notes",
            "portfolio-authority language or direct trade instruction",
        ],
        "required_citations": OWNER_LAYERS,
        "delivery_readiness": {
            "mode": "internal_review_only",
            "agent_write_ready": True,
            "cron_promotion_ready": False,
            "promotion_rule": "Require repeated clean review-only runs before any scheduled autonomous writer promotion.",
        },
    }



def main() -> None:
    args = parse_args()
    packet = build_packet(args.window)
    out_path = WINDOW_SPECS[args.window]["output"]
    atomic_write_json(out_path, packet)
    print(json.dumps({
        "status": "ok",
        "window": args.window,
        "output": str(out_path.relative_to(WORKSPACE)).replace('\\', '/'),
        "target_note": packet["target_note"],
        "consumer_posture": packet["consumer_posture"],
    }, indent=2))


if __name__ == "__main__":
    main()
