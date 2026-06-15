from __future__ import annotations

"""Review-only WF70 official capture period registry/latest selector.

This script scans validator-clean official IR capture artifacts and emits a
period-aware registry so future-quarter captures can coexist with historical Q1
captures without stale prior-period evidence being treated as current.

It is a proof/index surface only. It does not fetch sources, edit captures,
mutate canon/portfolio state, infer owner approval, or authorize execution.
"""

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPTURE_DIR = ROOT / "tmp" / "official-ir-captures"
DEFAULT_JSON = ROOT / "tmp" / "wf70-official-capture-period-registry.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")

AUTHORITY = {
    "review_only": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "deployment_authority_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "paper_order_action_allowed": False,
    "sizing_sleeve_cash_risk_rule_mutation_allowed": False,
}

FORBIDDEN_TRUE_AUTHORITY = [
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_authority_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
    "proposal_apply_allowed",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "brokerage_account_action_allowed",
    "money_movement_allowed",
    "sizing_allocation_action_allowed",
    "sizing_sleeve_cash_risk_rule_authority",
]

CURRENT_STATES = {
    "latest_current",
    "latest_partial",
    "new_source_detected_not_captured",
    "parser_failed_or_manual_required",
    "stale_prior_period",
    "missing_official_source",
    "not_yet_due",
}

ADDRESSING_STATUSES = {"official_captured", "not_disclosed_in_release", "partial", "not_applicable"}

CAPTURE_SCRIPT_BY_TICKER = {
    "GOOG": "goog_official_ir_capture.py",
    "ETN": "etn_vrt_official_ir_capture.py",
    "VRT": "etn_vrt_official_ir_capture.py",
    "AMZN": "tech_official_ir_capture.py",
    "MSFT": "tech_official_ir_capture.py",
    "NVDA": "tech_official_ir_capture.py",
    "BRK.B": "priority_official_ir_capture.py",
    "GS": "priority_official_ir_capture.py",
    "JPM": "priority_official_ir_capture.py",
    "LMT": "priority_official_ir_capture.py",
    "RTX": "priority_official_ir_capture.py",
    "XOM": "priority_official_ir_capture.py",
    "AMD": "batch2_official_ir_capture.py",
    "CAT": "batch2_official_ir_capture.py",
    "CVX": "batch2_official_ir_capture.py",
    "PLTR": "batch2_official_ir_capture.py",
    "GE": "batch2b_official_ir_capture.py",
    "LLY": "batch2b_official_ir_capture.py",
    "META": "batch2b_official_ir_capture.py",
    "PH": "batch2b_official_ir_capture.py",
    "BKNG": "longtail_official_ir_capture.py",
    "KTOS": "longtail_official_ir_capture.py",
    "LNG": "longtail_official_ir_capture.py",
    "SMCI": "longtail_official_ir_capture.py",
    "LIN": "longtail_official_ir_capture.py",
    "ECL": "longtail_official_ir_capture.py",
    "VMC": "longtail_official_ir_capture.py",
    "NFLX": "longtail_official_ir_capture.py",
    "TMUS": "longtail_official_ir_capture.py",
    "CME": "longtail_official_ir_capture.py",
    "WMB": "longtail_official_ir_capture.py",
}


@dataclass(frozen=True)
class OfficialCapturePeriod:
    ticker: str
    period_end: str | None
    period_slug: str
    alias_base: str
    json_path: Path
    validation_path: Path
    current_state: str
    capture_script: str


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def rel_posix(path: Path | str) -> str:
    resolved = Path(path)
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def alias_base_for_ticker(ticker: str) -> str:
    safe = ticker.lower().replace(".", "_").replace("-", "_")
    return f"{safe}_official_ir_capture"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def period_slug_from_path(path: Path, ticker: str) -> str:
    stem = path.stem
    prefix = ticker.lower() + "-"
    return stem[len(prefix):] if stem.lower().startswith(prefix) else stem


def validation_for(capture_path: Path) -> Path:
    return capture_path.with_name(capture_path.stem + "-validation.json")


def capture_paths(capture_dir: Path = CAPTURE_DIR) -> list[Path]:
    return sorted(
        path for path in capture_dir.glob("*.json")
        if not path.name.endswith("-validation.json") and path.name != "all-validation.json"
    )


def authority_clean(capture: dict[str, Any]) -> bool:
    if capture.get("review_only") is not True or capture.get("resolved_for_apply") is not False:
        return False
    authority = capture.get("authority") if isinstance(capture.get("authority"), dict) else {}
    return all(authority.get(key) is False for key in FORBIDDEN_TRUE_AUTHORITY)


def validation_clean(validation: dict[str, Any]) -> bool:
    summary = validation.get("summary") if isinstance(validation.get("summary"), dict) else {}
    return validation.get("status") == "ok" and int(summary.get("critical", 0) or 0) == 0


def capture_status_counts(capture: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    captures = capture.get("captures") if isinstance(capture.get("captures"), dict) else {}
    for block in captures.values():
        if isinstance(block, dict):
            counts[str(block.get("status") or "missing_status")] += 1
    return dict(sorted(counts.items()))


def state_for(capture: dict[str, Any], is_latest_valid: bool) -> str:
    if not is_latest_valid:
        return "stale_prior_period"
    counts = capture_status_counts(capture)
    if counts.get("manual_required", 0) > 0:
        return "parser_failed_or_manual_required"
    # Partial/not-disclosed/not-applicable fields can be fully valid when the
    # official source explicitly supports that state. They are still current;
    # field-level status carries the caveat.
    return "latest_current"


def build_registry(capture_dir: Path = CAPTURE_DIR) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    by_ticker: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path in capture_paths(capture_dir):
        validation_path = validation_for(path)
        capture = load_json(path)
        validation = load_json(validation_path) if validation_path.exists() else {}
        ticker = str(capture.get("ticker") or path.stem.split("-")[0]).upper()
        counts = capture_status_counts(capture)
        entry = {
            "ticker": ticker,
            "company_name": capture.get("company_name"),
            "period_end": capture.get("period_end"),
            "period_slug": period_slug_from_path(path, ticker),
            "alias_base": alias_base_for_ticker(ticker),
            "capture_artifact": rel(path),
            "validation_artifact": rel(validation_path) if validation_path.exists() else None,
            "validation_status": validation.get("status") if validation else "missing_validation",
            "validation_clean": validation_clean(validation),
            "authority_clean": authority_clean(capture),
            "review_only": capture.get("review_only") is True,
            "resolved_for_apply": capture.get("resolved_for_apply") is True,
            "source_type": (capture.get("source") or {}).get("source_type") if isinstance(capture.get("source"), dict) else None,
            "source_url": (capture.get("source") or {}).get("source_url") if isinstance(capture.get("source"), dict) else None,
            "status_counts": counts,
            "manual_required_remaining": counts.get("manual_required", 0),
            "addressed_fields": sum(counts.get(status, 0) for status in ADDRESSING_STATUSES),
            "current_state": "unclassified",
            "capture_script": CAPTURE_SCRIPT_BY_TICKER.get(ticker),
            "expected_outputs": [
                rel(path),
                rel(validation_path),
            ] if validation_path.exists() else [rel(path)],
        }
        if not entry["capture_script"]:
            findings.append({"severity": "critical", "code": "missing_capture_script_mapping", "ticker": ticker, "artifact": rel(path)})
        if not entry["validation_clean"]:
            findings.append({"severity": "warning", "code": "validation_not_clean", "ticker": ticker, "artifact": rel(path)})
        if not entry["authority_clean"]:
            findings.append({"severity": "critical", "code": "authority_not_clean", "ticker": ticker, "artifact": rel(path)})
        by_ticker[ticker].append(entry)

    latest: dict[str, dict[str, Any]] = {}
    historical: list[dict[str, Any]] = []
    for ticker, ticker_entries in sorted(by_ticker.items()):
        sorted_entries = sorted(ticker_entries, key=lambda item: (str(item.get("period_end") or ""), str(item.get("period_slug") or ""), str(item.get("capture_artifact") or "")))
        valid_entries = [item for item in sorted_entries if item["validation_clean"] and item["authority_clean"]]
        latest_entry = valid_entries[-1] if valid_entries else sorted_entries[-1]
        for item in sorted_entries:
            item["current_state"] = state_for(item, item is latest_entry)
            if item["current_state"] not in CURRENT_STATES:
                findings.append({"severity": "critical", "code": "invalid_current_state", "ticker": ticker, "state": item["current_state"]})
            entries.append(item)
            if item is latest_entry:
                latest[ticker] = item
            else:
                historical.append(item)

    critical = sum(1 for item in findings if item["severity"] == "critical")
    warning = sum(1 for item in findings if item["severity"] == "warning")
    state_counts: dict[str, int] = defaultdict(int)
    for item in entries:
        state_counts[item["current_state"]] += 1

    return {
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else "warning" if warning else "ok",
        "workflow": "WF70 Official Company Source Capture and Reconciliation",
        "purpose": "Review-only period-aware registry/latest selector for official IR captures.",
        "authority": AUTHORITY,
        "capture_dir": rel(capture_dir),
        "summary": {
            "tickers": len(by_ticker),
            "captures": len(entries),
            "latest_selected": len(latest),
            "historical_captures": len(historical),
            "critical": critical,
            "warning": warning,
            "state_counts": dict(sorted(state_counts.items())),
        },
        "rollforward_states": sorted(CURRENT_STATES),
        "latest_by_ticker": {ticker: latest[ticker] for ticker in sorted(latest)},
        "captures": sorted(entries, key=lambda item: (item["ticker"], str(item.get("period_end") or ""), item["capture_artifact"])),
        "findings": findings,
        "consumer_contract": {
            "latest_selector_rule": "Use latest_by_ticker[ticker] only when validation_clean=true, authority_clean=true, review_only=true, and current_state starts with latest_ or not_yet_due.",
            "stale_rule": "Do not use stale_prior_period as current-period evidence after newer official evidence is known.",
            "failure_rule": "If a newer official source is detected but not captured/validated, emit new_source_detected_not_captured or parser_failed_or_manual_required instead of carrying prior-quarter values forward.",
        },
    }


def all_periods(capture_dir: Path = CAPTURE_DIR, latest_only: bool = True) -> list[OfficialCapturePeriod]:
    registry = build_registry(capture_dir)
    source = registry["latest_by_ticker"].values() if latest_only else registry["captures"]
    periods: list[OfficialCapturePeriod] = []
    for item in source:
        json_path = ROOT / str(item["capture_artifact"])
        validation = item.get("validation_artifact")
        periods.append(
            OfficialCapturePeriod(
                ticker=str(item["ticker"]),
                period_end=item.get("period_end"),
                period_slug=str(item.get("period_slug") or ""),
                alias_base=str(item.get("alias_base") or alias_base_for_ticker(str(item["ticker"]))),
                json_path=json_path,
                validation_path=ROOT / str(validation) if validation else validation_for(json_path),
                current_state=str(item.get("current_state") or ""),
                capture_script=str(item.get("capture_script") or ""),
            )
        )
    return periods


def expected_outputs_for_script(script: str, capture_dir: Path = CAPTURE_DIR) -> list[str]:
    return [
        output
        for period in all_periods(capture_dir)
        if period.capture_script == script
        for output in (rel_posix(period.json_path),)
    ]


def validation_outputs(capture_dir: Path = CAPTURE_DIR) -> list[str]:
    return [rel_posix(period.validation_path) for period in all_periods(capture_dir)]


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_md(path: Path, data: dict[str, Any]) -> None:
    lines = [
        "# WF70 Official Capture Period Registry",
        "",
        f"Generated: `{data['generated_at_utc']}`",
        "",
        "Review-only latest-selector/index artifact. It does not mutate canon, portfolio state, trades, accounts, paper orders, sizing, sleeves, cash, or risk rules, and it does not infer owner approval.",
        "",
        "## Summary",
        "",
    ]
    for key, value in data["summary"].items():
        lines.append(f"- {key}: `{value}`")
    lines += ["", "## Latest by ticker", "", "| Ticker | Period end | State | Capture | Validation | Manual required |", "|---|---:|---|---|---|---:|"]
    for ticker, item in data["latest_by_ticker"].items():
        lines.append(
            f"| {ticker} | {item.get('period_end')} | {item.get('current_state')} | `{item.get('capture_artifact')}` | `{item.get('validation_artifact')}` | {item.get('manual_required_remaining')} |"
        )
    lines += ["", "## Consumer contract", ""]
    for value in data["consumer_contract"].values():
        lines.append(f"- {value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build review-only WF70 official capture period registry/latest selector.")
    parser.add_argument("--capture-dir", default=str(CAPTURE_DIR))
    parser.add_argument("--output", default=str(DEFAULT_JSON))
    parser.add_argument("--md-output", default=None)
    parser.add_argument("--write-md", action="store_true", help="Also write the optional human-readable Markdown digest.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    registry = build_registry(Path(args.capture_dir))
    if args.write:
        write_json(Path(args.output), registry)
        if args.write_md or args.md_output:
            write_md(Path(args.md_output) if args.md_output else DEFAULT_MD, registry)
    print(json.dumps(registry, indent=2, sort_keys=True))
    return 1 if registry["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
