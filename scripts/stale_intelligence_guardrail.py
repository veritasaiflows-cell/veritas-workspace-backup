from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "stale-intelligence-guardrail.json"
OUT_MD = TMP / "stale-intelligence-guardrail.md"

WPR = WORKSPACE / "05. Intelligence" / "Weekly Positioning Review.md"
WIB = WORKSPACE / "05. Intelligence" / "Weekly Intelligence Brief.md"
REGIME = WORKSPACE / "02. Markets" / "Regime Scoring Matrix.md"
TECH = WORKSPACE / "03. Portfolio" / "Execution Board.md"
TECH_ARTIFACT = TMP / "technical-refresh.json"
TRIGGER_ARTIFACT = TMP / "trigger-sheet.json"
CONFIG_ARTIFACT = TMP / "portfolio-config.json"

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def records_by_ticker(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(r.get("ticker")): r for r in data.get("records", []) or [] if isinstance(r, dict) and r.get("ticker")}


def add(finding_list: list[dict[str, Any]], severity: str, surface: Path, code: str, message: str, evidence: str = "") -> None:
    finding_list.append({
        "severity": severity,
        "surface": str(surface.relative_to(WORKSPACE)),
        "code": code,
        "message": message,
        "evidence": evidence[:600],
    })


def section_between(text: str, start_marker: str, end_pattern: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        return ""
    rest = text[start + len(start_marker):]
    m = re.search(end_pattern, rest, flags=re.M)
    if not m:
        return rest
    return rest[: m.start()]


def current_deployable_section(text: str) -> str:
    return section_between(text, "**Deployable now:**", r"^\s*-?\s*\*\*[^\n]+:\*\*")


def ticker_section(text: str, ticker: str) -> str:
    m = re.search(rf"(?ms)^###\s+{re.escape(ticker)}\b.*?(?=^###\s+|^---\s*$|\Z)", text)
    return m.group(0) if m else ""


def extract_note_close(section: str) -> float | None:
    m = re.search(r"Close:\s*\*\*([0-9]+(?:\.[0-9]+)?)\*\*", section)
    if not m:
        return None
    return float(m.group(1))


def evaluate() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    wpr = read_text(WPR)
    wib = read_text(WIB)
    regime = read_text(REGIME)
    tech = read_text(TECH)
    technical = records_by_ticker(load_json(TECH_ARTIFACT))
    trigger = records_by_ticker(load_json(TRIGGER_ARTIFACT))
    config = load_json(CONFIG_ARTIFACT)
    bands = config.get("entry_bands", {}) if isinstance(config.get("entry_bands"), dict) else {}

    deployable_section = current_deployable_section(wpr)
    if "JPM" in deployable_section:
        add(findings, "critical", WPR, "jpm_still_in_deployable_now", "Weekly Positioning Review still lists JPM in the current Deployable now section.", deployable_section)
    if re.search(r"JPM[^\n]{0,120}(deployable-now|DEPLOYABLE NOW|Deployable now)", wpr):
        # Allow explicit references to stale deployable language only when it says invalidated/stale/history nearby.
        stale_hits = [line for line in wpr.splitlines() if "JPM" in line and re.search(r"deployable-now|DEPLOYABLE NOW|Deployable now", line)]
        bad = [line for line in stale_hits if not re.search(r"stale|invalidated|history|not current|only|not deployable|do not touch|secondary", line, re.I)]
        if bad:
            add(findings, "critical", WPR, "jpm_deployable_language_unqualified", "Weekly Positioning Review has unqualified JPM deployable-now language.", "\n".join(bad))

    last_updated = re.search(r"\*\*Last updated:\*\*\s*([0-9]{4}-[0-9]{2}-[0-9]{2})", wpr)
    if last_updated and last_updated.group(1) < "2026-05-11":
        add(findings, "warning", WPR, "weekly_positioning_last_updated_stale", f"Weekly Positioning Review last_updated is {last_updated.group(1)}, before the May 11 repair pass.")

    if "_[Fill" in wib or "_[" in wib:
        if "Draft-only / not canonical" not in wib and "Draft-only machine skeleton" not in wib:
            add(findings, "critical", WIB, "weekly_intelligence_placeholders_not_quarantined", "Weekly Intelligence Brief contains unfilled placeholders without a draft-only quarantine label.")
    if "Week of May 4–10" in wib and "Draft-only machine skeleton" not in wib:
        add(findings, "critical", WIB, "weekly_intelligence_machine_section_not_draft_labeled", "Machine-generated May 4-10 section is not explicitly labeled draft-only.")
    current_notice = re.search(r"^## Current-state notice.*?([0-9]{4}-[0-9]{2}-[0-9]{2})\b", wib, flags=re.M)
    if not current_notice or current_notice.group(1) < "2026-05-11":
        add(findings, "warning", WIB, "weekly_intelligence_current_notice_missing", "Weekly Intelligence Brief lacks a current-state warning that the canonical note has stale/skeleton sections.")


    if re.search(r"Next refresh due:.*Apr 29|Next refresh due:.*MSFT/GOOG/AMZN prints", regime):
        add(findings, "warning", REGIME, "regime_next_refresh_due_past_event", "Regime Scoring Matrix still references a past-event refresh due line.")
    if "144.57" in regime and "previously surfaced" not in regime:
        add(findings, "critical", REGIME, "regime_xom_stale_close_visible", "Regime Scoring Matrix still exposes XOM 144.57 without marking it as stale/incorrect.")

    etn_section = ticker_section(tech, "ETN")
    etn_artifact = technical.get("ETN", {})
    etn_trigger = trigger.get("ETN", {})
    note_close = extract_note_close(etn_section)
    artifact_close = etn_artifact.get("close")
    try:
        if note_close is not None and artifact_close is not None:
            artifact_close_float = float(artifact_close)
            # Morning/intraday technical refreshes can move by small amounts while the
            # note remains directionally current. Keep the guardrail focused on real
            # stale-note risk, not harmless live-price ticks.
            stale_close_tolerance = max(0.5, artifact_close_float * 0.01)
            if abs(note_close - artifact_close_float) > stale_close_tolerance:
                severity = "critical" if etn_trigger.get("action_state") == "DEPLOYABLE NOW" else "warning"
                add(findings, severity, TECH, "etn_deployable_close_stale", f"ETN note close {note_close:.2f} differs from artifact close {artifact_close_float:.2f}.", etn_section)
    except (TypeError, ValueError):
        pass
    band = bands.get("ETN", {}) if isinstance(bands.get("ETN"), dict) else {}
    try:
        if artifact_close is not None and band.get("high") is not None:
            close = float(artifact_close)
            high = float(band["high"])
            no_chase_visible = bool(re.search(r"no-chase|no chase|do not chase|near the upper", etn_section or tech, re.I))
            if high and 0 <= (high - close) / high <= 0.01 and not no_chase_visible:
                add(findings, "critical", TECH, "etn_no_chase_missing", "ETN is within 1% of band top but the Execution Board does not make no-chase discipline visible.", etn_section)
    except (TypeError, ValueError):
        pass

    summary = {
        "critical": sum(1 for f in findings if f["severity"] == "critical"),
        "warning": sum(1 for f in findings if f["severity"] == "warning"),
        "finding_count": len(findings),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": "critical" if summary["critical"] else ("warning" if summary["warning"] else "ok"),
        "authority": {
            "posture": "read_only_stale_intelligence_guardrail",
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_execution_allowed": False,
        },
        "summary": summary,
        "findings": findings,
    }


def render_md(report: dict[str, Any]) -> str:
    lines = ["# Stale Intelligence Guardrail", ""]
    lines.append(f"- Generated: `{report['generated_at_utc']}`")
    lines.append(f"- Status: **{report['status']}**")
    s = report["summary"]
    lines.append(f"- Summary: {s['critical']} critical / {s['warning']} warning")
    lines.append("- Authority: read-only; no canonical mutation, portfolio mutation, or trade execution")
    lines.append("")
    if not report["findings"]:
        lines.append("No stale-intelligence findings detected by this guardrail.")
    else:
        for f in report["findings"]:
            lines.append(f"- **{f['severity'].upper()}** `{f['surface']}` `{f['code']}` — {f['message']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check stale intelligence and current-state contradictions in canonical finance notes.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    report = evaluate()
    if args.write:
        OUT_JSON.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
        OUT_MD.write_text(render_md(report), encoding="utf-8")
        print(f"wrote {OUT_JSON}")
        print(f"wrote {OUT_MD}")
    s = report["summary"]
    print(f"stale_intelligence_guardrail: {report['status']} ({s['critical']} critical, {s['warning']} warning)")
    for f in report["findings"][:20]:
        print(f"  - [{f['severity']}] {f['surface']} {f['code']}: {f['message']}")
    if s["critical"]:
        return 2
    if args.strict and s["warning"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
