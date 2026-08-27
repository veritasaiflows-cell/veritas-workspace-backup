from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from market_data_utils import load_json_artifact
from source_freshness_classifier import classify_dashboard_source, summarize_source_freshness

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
SCRIPTS = Path(__file__).resolve().parent

EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

VAULT_NOTES = {
    "macro_regime": "02. Markets/Macro Regime Dashboard.md",
    "coverage_watchlist": "04. Research/Coverage and Watchlist.md",
    "portfolio_snapshot": "03. Portfolio/Portfolio Snapshot.md",
    "execution_board": "03. Portfolio/Execution Board.md",
    # Compatibility aliases for downstream clients during the canon-consolidation transition.
    "watchlist": "04. Research/Coverage and Watchlist.md",
    "technical_entry": "03. Portfolio/Execution Board.md",
    "trigger_sheet": "03. Portfolio/Execution Board.md",
    "coverage_universe": "04. Research/Coverage and Watchlist.md",
    "event_calendar": "05. Intelligence/Event Calendar.md",
    "weekly_brief": "05. Intelligence/Weekly Intelligence Brief.md",
    "risk_rules": "07. Risk/Risk Rules.md",
}

STATUS_ORDER = {
    "fresh": 0,
    "usable_with_caution": 1,
    "partial": 2,
    "stale": 3,
    "missing": 4,
}
SEVERITY_ORDER = {"info": 0, "warning": 1, "critical": 2}

SOURCE_SPECS: dict[str, dict[str, Any]] = {
    "market": {
        "label": "Market",
        "path": "tmp/market-state.json",
        "critical": True,
        "required_paths": [
            ("data.fed.target_low", "Fed lower bound"),
            ("data.fed.target_high", "Fed upper bound"),
            ("data.treasuries.10y", "10Y Treasury"),
            ("data.volatility.vix", "VIX"),
            ("data.equities.spx", "S&P 500"),
            ("data.fx.dxy", "DXY"),
        ],
    },
    "policy": {
        "label": "Policy expectations",
        "path": "tmp/policy-expectations.json",
        "critical": False,
        "required_paths": [
            ("data.current_target_range.low", "Policy lower bound"),
            ("data.current_target_range.high", "Policy upper bound"),
            ("data.next_fomc.meeting_date", "Next FOMC date"),
            ("data.next_fomc.distribution", "Next FOMC distribution"),
        ],
    },
    "credit": {
        "label": "Credit spreads",
        "path": "tmp/credit-spreads.json",
        "critical": False,
        "required_paths": [
            ("data.investment_grade_oas.value", "IG OAS"),
            ("data.high_yield_oas.value", "HY OAS"),
            ("data.stress_regime", "Stress regime"),
        ],
    },
    "breadth": {
        "label": "Market breadth",
        "path": "tmp/breadth-state.json",
        "critical": False,
        "required_paths": [
            ("data.equal_weight_vs_cap_weight.rsp_spy_ratio", "RSP/SPY ratio"),
            ("data.sector_participation.sectors_above_50dma", "Sectors above 50DMA"),
            ("data.major_index_breadth.breadth_regime", "Breadth regime"),
        ],
    },
    "technical": {
        "label": "Technical",
        "path": "tmp/technical-refresh.json",
        "critical": True,
        "required_paths": [("records", "Technical records")],
    },
    "deployment": {
        "label": "Deployment",
        "path": "tmp/deployment-check.json",
        "critical": True,
        "required_paths": [("records", "Deployment records")],
    },
    "earnings": {
        "label": "Earnings",
        "path": "tmp/earnings-calendar.json",
        "critical": False,
        "required_paths": [("records", "Earnings records")],
    },
    "portfolio": {
        "label": "Portfolio config",
        "path": "tmp/portfolio-config.json",
        "critical": True,
        "required_paths": [
            ("portfolio", "Portfolio block"),
            ("entry_bands", "Entry bands"),
            ("risk_thresholds", "Risk thresholds"),
        ],
    },
    "fundamentals": {
        "label": "Fundamental metrics",
        "path": "tmp/fundamental-metrics-current.json",
        "critical": False,
        "required_paths": [
            ("rows", "Fundamental metric rows"),
            ("summary", "Fundamental metrics summary"),
            ("authority", "Review-only authority block"),
        ],
    },
    "fundamental_ir": {
        "label": "Fundamental IR packets",
        "path": "tmp/fundamental-ir-reconciliation-packets.json",
        "critical": False,
        "required_paths": [
            ("packets", "IR reconciliation packets"),
            ("summary", "IR reconciliation summary"),
            ("authority", "Review-only authority block"),
        ],
    },
}


def load_json(path: Path) -> dict | None:
    if not path.exists():
        print(f"  WARN: {path} not found, section will show incomplete")
        return None
    data = load_json_artifact(path)
    if isinstance(data, dict):
        return data
    print(f"  WARN: {path} unreadable, section will show incomplete")
    return None


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def age_hours(ts_str: str | None) -> float:
    if not ts_str:
        return 9999.0
    try:
        gen = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - gen).total_seconds() / 3600
    except Exception:
        return 9999.0


def parse_datetime(ts_str: str | None) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
    except Exception:
        return None


def parse_date(date_str: str | None) -> datetime | None:
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        return None


def get_path(data: Any, dotted_path: str) -> Any:
    cur = data
    for part in dotted_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def is_missing_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list | tuple | set | dict):
        return len(value) == 0
    return False


def status_worse(current: str, candidate: str) -> str:
    return candidate if STATUS_ORDER[candidate] > STATUS_ORDER[current] else current


def severity_worse(current: str, candidate: str) -> str:
    return candidate if SEVERITY_ORDER[candidate] > SEVERITY_ORDER[current] else current


def status_badge(status: str) -> dict[str, str]:
    mapping = {
        "fresh": {"label": "Fresh", "tone": "ok"},
        "usable_with_caution": {"label": "Caution", "tone": "warn"},
        "partial": {"label": "Partial", "tone": "warn"},
        "stale": {"label": "Stale", "tone": "bad"},
        "missing": {"label": "Missing", "tone": "bad"},
    }
    return mapping[status]


def tone_from_severity(severity: str) -> str:
    return {"info": "info", "warning": "warn", "critical": "bad"}[severity]


def fmt_num(value: Any, decimals: int = 2, prefix: str = "", suffix: str = "") -> str:
    if value is None:
        return "—"
    try:
        return f"{prefix}{float(value):,.{decimals}f}{suffix}"
    except Exception:
        return "—"


def fmt_pct(value: Any, decimals: int = 1) -> str:
    return fmt_num(value, decimals=decimals, suffix="%")


def fmt_date_label(date_str: str | None, today: datetime | None = None) -> str:
    if not date_str:
        return "Unconfirmed"
    dt = parse_date(date_str)
    if not dt:
        return date_str
    base = dt.strftime("%Y-%m-%d")
    if not today:
        return base
    delta = (dt.date() - today.date()).days
    if delta == 0:
        return f"{base} (Today)"
    if delta == 1:
        return f"{base} (Tomorrow)"
    if delta > 1:
        return f"{base} ({delta}d)"
    if delta == -1:
        return f"{base} (Yesterday)"
    return f"{base} ({delta}d)"


def describe_overall_status(status: str) -> str:
    return {
        "fresh": "Execution context is fresh enough for dashboard use.",
        "usable_with_caution": "Execution context is usable with caution. Manual or unconfirmed dependencies remain visible.",
        "partial": "Execution context is partial. Some critical inputs are degraded or incomplete.",
        "stale": "Execution context is stale. Refresh before relying on execution signals.",
        "missing": "Execution context is missing one or more critical inputs. Do not trust the dashboard as healthy.",
    }[status]


def normalize_records(records: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    return records if isinstance(records, list) else []


def load_sources() -> dict[str, dict | None]:
    return {
        "market": load_json(TMP / "market-state.json"),
        "policy": load_json(TMP / "policy-expectations.json"),
        "credit": load_json(TMP / "credit-spreads.json"),
        "breadth": load_json(TMP / "breadth-state.json"),
        "technical": load_json(TMP / "technical-refresh.json"),
        "deployment": load_json(TMP / "deployment-check.json"),
        "earnings": load_json(TMP / "earnings-calendar.json"),
        "portfolio": load_json(TMP / "portfolio-config.json"),
        "fundamentals": load_json(TMP / "fundamental-metrics-current.json"),
        "fundamental_ir": load_json(TMP / "fundamental-ir-reconciliation-packets.json"),
        # band_proposals is loaded directly in build_validation — not a dashboard display source
        # and must not be included here or assess_source() will KeyError on SOURCE_SPECS lookup
    }


def get_market_session(dt: datetime) -> str:
    dt_et = dt.astimezone(EASTERN)
    if dt_et.weekday() >= 5:
        return "weekend"
    t = dt_et.time()
    if t < MARKET_OPEN:
        return "pre_open"
    if t < MARKET_CLOSE:
        return "open"
    return "post_close"


def assess_source(name: str, src: dict | None) -> dict[str, Any]:
    spec = SOURCE_SPECS[name]
    if src is None:
        result = {
            "key": name,
            "label": spec["label"],
            "source": spec["path"],
            "critical": spec["critical"],
            "generated_at": None,
            "age_h": None,
            "stale_after_hours": None,
            "status": "missing",
            "fresh": False,
            "tags": ["missing"],
            "issues": ["source file not found"],
            "manual_fields": [],
            "raw_status": "missing",
        }
        result["source_state"] = classify_dashboard_source(result)
        return result

    tags: list[str] = []
    issues: list[str] = []
    status = "fresh"
    raw_status = src.get("status", "ok")
    generated_at = src.get("generated_at_utc")
    portfolio_manual_contract = name == "portfolio" and bool(src.get("manual_review_policy") or src.get("manual_review_fields"))

    now = datetime.now(timezone.utc)
    session = get_market_session(now)

    stale_after_hours = src.get(
        "stale_after_hours",
        src.get("stale_after_days", 7) * 24 if "stale_after_days" in src else 48,
    )

    # Priority 2.3: Session-aware freshness
    if name in {"market", "technical", "deployment"}:
        if session in {"pre_open", "open"}:
            stale_after_hours = min(stale_after_hours, 4.0)
        elif session == "post_close":
            stale_after_hours = min(stale_after_hours, 18.0)

    ah = age_hours(generated_at)
    fresh = ah < stale_after_hours
    if not fresh and portfolio_manual_contract:
        tags.extend(["manual", "manual_review_policy"])
        issues.append(
            f"portfolio generated_at age {round(ah, 1)}h exceeds {stale_after_hours}h; "
            "manual review policy controls this source until portfolio/risk/universe inputs change"
        )
    elif not fresh:
        status = status_worse(status, "stale")
        tags.append("stale")
        issues.append(f"age {round(ah, 1)}h exceeds {stale_after_hours}h freshness window ({session} mode)")

    if raw_status == "manual":
        tags.append("manual")
        issues.append("upstream status=manual")
        if status == "fresh":
            status = "usable_with_caution"
    elif raw_status != "ok":
        status = status_worse(status, "partial")
        tags.append("partial")
        issues.append(f"upstream status={raw_status}")

    manual_fields: list[str] = []
    if name == "portfolio":
        tags.append("manual")
        manual_fields = ["all"]
        issues.append("human-maintained config, update when note-layer posture or risk rules change")
        if status == "fresh":
            status = "usable_with_caution"
    elif name == "market":
        fed = get_path(src, "data.fed") or {}
        macro_freshness = src.get("macro_freshness") if isinstance(src.get("macro_freshness"), dict) else {}
        if macro_freshness:
            routing = macro_freshness.get("routing") if isinstance(macro_freshness.get("routing"), dict) else {}
            issues.append(f"macro freshness: {macro_freshness.get('summary') or macro_freshness.get('status')}")
            if macro_freshness.get("status") in {"warning", "blocked"} and status == "fresh":
                status = "usable_with_caution" if not routing.get("macro_regime_safe") is False else "partial"
        if fed.get("manual_update_required"):
            tags.extend(["manual", "macro_manual_dependency"])
            manual_fields.append("fed_target_range")
            issues.append("Fed target range is manually maintained")
            if status == "fresh":
                status = "usable_with_caution"
        if fed.get("cut_probability_next_meeting") is None:
            tags.extend(["unconfirmed", "macro_manual_dependency"])
            manual_fields.append("fedwatch_cut_probability")
            issues.append("FedWatch cut probability is not wired and remains null")
            if status == "fresh":
                status = "usable_with_caution"
        freshness_notes = src.get("freshness_notes") or []
        if freshness_notes:
            if "mixed_source_dates" in freshness_notes:
                tags.append("mixed_dates")
            issues.extend([f"freshness note: {note}" for note in freshness_notes])
            if status == "fresh":
                status = "usable_with_caution"
    elif name == "policy":
        policy_data = src.get("data", {}) if isinstance(src.get("data"), dict) else {}
        contract = src.get("freshness_contract") if isinstance(src.get("freshness_contract"), dict) else {}
        if contract:
            freshness_status = contract.get("freshness_status")
            if freshness_status and freshness_status not in {"fresh", "current", "ok"}:
                tags.append(f"policy_{freshness_status}")
                issues.append(f"policy freshness: {contract.get('policy_status') or freshness_status}")
                if contract.get("hard_fail_closed"):
                    status = status_worse(status, "partial")
                elif status == "fresh":
                    status = "usable_with_caution"
        manual_deps = policy_data.get("manual_dependencies", []) if isinstance(policy_data.get("manual_dependencies"), list) else []
        if manual_deps:
            tags.extend(["manual", "policy_manual_dependency"])
            for dep in manual_deps:
                if isinstance(dep, dict):
                    field = dep.get("field") or dep.get("label") or "policy_dependency"
                    manual_fields.append(str(field))
                    detail = dep.get("detail") or dep.get("label") or field
                    issues.append(f"manual dependency: {detail}")
            if status == "fresh":
                status = "usable_with_caution"
        freshness_notes = src.get("freshness_notes") or []
        if freshness_notes:
            if "mixed_source_dates" in freshness_notes:
                tags.append("mixed_dates")
            issues.extend([f"freshness note: {note}" for note in freshness_notes])
            if status == "fresh":
                status = "usable_with_caution"
        if src.get("warnings"):
            tags.append("warning_notes")
            issues.extend([f"warning: {note}" for note in src.get("warnings", [])])
            if status == "fresh":
                status = "usable_with_caution"
        if get_path(src, "data.next_fomc.distribution") in (None, []):
            tags.extend(["unconfirmed", "policy_manual_dependency"])
            manual_fields.append("next_fomc_distribution")
            issues.append("Next FOMC distribution is missing")
            status = status_worse(status, "partial")
    elif name == "credit":
        credit_data = src.get("data", {}) if isinstance(src.get("data"), dict) else {}
        source_mode = credit_data.get("source_mode", "primary")
        if source_mode == "fallback":
            tags.append("fallback_proxy_only")
            issues.append("Credit spreads are using proxy basket only (HYG/JNK/LQD), not direct OAS series")
            if status == "fresh":
                status = "usable_with_caution"
        elif source_mode == "mixed":
            tags.append("mixed_sources")
            issues.append("Credit spreads are using a mix of direct OAS and proxy sources")
            if status == "fresh":
                status = "usable_with_caution"
        if src.get("warnings"):
            tags.append("warning_notes")
            issues.extend([f"warning: {w}" for w in src.get("warnings", [])])
            if status == "fresh":
                status = "usable_with_caution"
    elif name == "breadth":
        breadth_data = src.get("data", {}) if isinstance(src.get("data"), dict) else {}
        breadth_regime = breadth_data.get("major_index_breadth", {}).get("breadth_regime")
        if breadth_regime in ("narrow", "deteriorating"):
            tags.append("narrow_participation")
            issues.append(f"Breadth regime is {breadth_regime} — index strength may not reflect broad participation")
            if status == "fresh":
                status = "usable_with_caution"
        if src.get("warnings"):
            tags.append("warning_notes")
            issues.extend([f"warning: {w}" for w in src.get("warnings", [])])
            if status == "fresh":
                status = "usable_with_caution"
    elif name == "earnings":
        timing_sensitive_alerts = src.get("timing_sensitive_alerts", []) if isinstance(src.get("timing_sensitive_alerts"), list) else []
        if timing_sensitive_alerts:
            tags.extend(["unconfirmed", "timing_sensitive"])
            issues.append(f"{len(timing_sensitive_alerts)} timing-critical earnings alert(s) still require verification")
            if status == "fresh":
                status = "usable_with_caution"

    missing_required: list[str] = []
    for dotted_path, label in spec.get("required_paths", []):
        value = get_path(src, dotted_path)
        if is_missing_value(value):
            missing_required.append(label)
    if name == "credit" and missing_required:
        credit_data = src.get("data", {}) if isinstance(src.get("data"), dict) else {}
        if credit_data.get("source_mode") in {"mixed", "fallback"} and credit_data.get("stress_regime") and credit_data.get("fallback_proxies"):
            issues.append("direct credit fields missing but proxy basket preserved stress-regime context: " + ", ".join(missing_required))
            missing_required = []
            if status == "fresh":
                status = "usable_with_caution"

    if missing_required:
        status = status_worse(status, "partial")
        tags.append("missing_fields")
        issues.append("missing required fields: " + ", ".join(missing_required))

    result = {
        "key": name,
        "label": spec["label"],
        "source": spec["path"],
        "critical": spec["critical"],
        "generated_at": generated_at,
        "age_h": round(ah, 1) if ah < 9000 else None,
        "stale_after_hours": stale_after_hours,
        "status": status,
        "fresh": status in {"fresh", "usable_with_caution"},
        "tags": sorted(set(tags), key=tags.index),
        "issues": issues,
        "manual_fields": manual_fields,
        "raw_status": raw_status,
    }
    result["source_state"] = classify_dashboard_source(result)
    return result


def get_vault_freshness() -> dict[str, Any]:
    notes = {}
    now = datetime.now(timezone.utc)
    for key, rel_path in VAULT_NOTES.items():
        abs_path = WORKSPACE / rel_path
        status = "missing"
        age_h = None
        last_updated_date = None

        if abs_path.exists():
            mtime = datetime.fromtimestamp(abs_path.stat().st_mtime, tz=timezone.utc)
            age_h = round((now - mtime).total_seconds() / 3600, 1)
            status = "fresh" if age_h < 168 else "stale"

            try:
                content = abs_path.read_text(encoding="utf-8")[:2000]
                match = re.search(r"Last updated:\s*(\d{4}-\d{2}-\d{2})", content, re.IGNORECASE)
                if match:
                    last_updated_date = match.group(1)
            except Exception:
                pass

        notes[key] = {
            "label": rel_path.split("/")[-1].replace(".md", ""),
            "path": rel_path,
            "status": status,
            "age_h": age_h,
            "last_updated_date": last_updated_date,
        }
    return notes


def build_provenance(source_status: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    provenance: dict[str, dict[str, Any]] = {}
    for key, info in source_status.items():
        provenance[key] = {
            "source": info["source"],
            "generated_at": info["generated_at"],
            "stale_after_hours": info["stale_after_hours"],
            "quality": info["status"],
            "stale": info["status"] == "stale",
            "manual_fields": info["manual_fields"],
            "tags": info["tags"],
            "issues": info["issues"],
        }
    return provenance
