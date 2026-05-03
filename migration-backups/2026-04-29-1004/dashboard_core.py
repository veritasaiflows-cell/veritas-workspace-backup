from __future__ import annotations

import json
import re
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
SCRIPTS = Path(__file__).resolve().parent

EASTERN = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)

VAULT_NOTES = {
    "macro_regime": "02. Markets/Macro Regime Dashboard.md",
    "watchlist": "02. Markets/Watchlist.md",
    "portfolio_snapshot": "03. Portfolio/Portfolio Snapshot.md",
    "technical_entry": "03. Portfolio/Technical Entry and Invalidation Sheet.md",
    "trigger_sheet": "03. Portfolio/Deployment Trigger Sheet.md",
    "coverage_universe": "04. Research/Coverage Universe.md",
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
}


def load_json(path: Path) -> dict | None:
    if not path.exists():
        print(f"  WARN: {path} not found, section will show incomplete")
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


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
        "technical": load_json(TMP / "technical-refresh.json"),
        "deployment": load_json(TMP / "deployment-check.json"),
        "earnings": load_json(TMP / "earnings-calendar.json"),
        "portfolio": load_json(TMP / "portfolio-config.json"),
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
        return {
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
        }

    tags: list[str] = []
    issues: list[str] = []
    status = "fresh"
    raw_status = src.get("status", "ok")
    generated_at = src.get("generated_at_utc")

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
    if not fresh:
        status = status_worse(status, "stale")
        tags.append("stale")
        issues.append(f"age {round(ah, 1)}h exceeds {stale_after_hours}h freshness window ({session} mode)")

    if raw_status != "ok":
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
        if src.get("freshness_notes"):
            tags.append("mixed_dates")
            issues.extend([f"freshness note: {note}" for note in src.get("freshness_notes", [])])
            if status == "fresh":
                status = "usable_with_caution"
    elif name == "earnings":
        changed = [alert for alert in src.get("watchlist_alerts", []) if "DATE CHANGED" in alert]
        if changed:
            tags.extend(["unconfirmed", "timing_sensitive"])
            issues.append(f"{len(changed)} timing-critical earnings date change(s) still require verification")
            if status == "fresh":
                status = "usable_with_caution"

    missing_required: list[str] = []
    for dotted_path, label in spec.get("required_paths", []):
        value = get_path(src, dotted_path)
        if is_missing_value(value):
            missing_required.append(label)
    if missing_required:
        status = status_worse(status, "partial")
        tags.append("missing_fields")
        issues.append("missing required fields: " + ", ".join(missing_required))

    return {
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
