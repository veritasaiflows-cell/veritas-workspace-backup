from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_REPORT = TMP / "full-portfolio-view.json"
OUT_JSON = TMP / "full-portfolio-view-validation.json"
AUTHORITY_FALSE_FIELDS = [
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "owner_approval_granted",
    "sizing_or_weight_change_allowed",
    "trade_execution_allowed",
    "generated_report_is_canonical",
]
REQUIRED_TOP_LEVEL = [
    "schema_version",
    "generated_at_utc",
    "window",
    "market_data_as_of",
    "source_artifacts",
    "authority",
    "summary",
    "records",
    "rendered_outputs",
]
REQUIRED_RECORD_FIELDS = ["ticker", "source_provenance", "action_bucket"]
STALE_THEME_PHRASES = [
    "etn is the only deployable",
    "etn is the only current deployable",
    "jpm is below stop",
    "jpm approval remains recorded but",
    "msft/goog/nvda are prepare/wait",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def add(errors: list[dict[str, Any]], code: str, message: str, severity: str = "critical", **extra: Any) -> None:
    errors.append({"severity": severity, "code": code, "message": message, **extra})


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for field in REQUIRED_TOP_LEVEL:
        if field not in report:
            add(findings, "missing_top_level_field", f"Missing top-level field `{field}`", field=field)
    authority = report.get("authority") if isinstance(report.get("authority"), dict) else {}
    for field in AUTHORITY_FALSE_FIELDS:
        if authority.get(field) is not False:
            add(findings, "authority_not_fail_closed", f"Authority field `{field}` must be false", field=field)
    if not report.get("market_data_as_of"):
        add(findings, "market_data_as_of_missing", "Report must declare market_data_as_of")
    records = report.get("records") if isinstance(report.get("records"), list) else []
    if not records:
        add(findings, "records_missing", "Report must include at least one portfolio record")
    tickers: set[str] = set()
    for idx, record in enumerate(records):
        if not isinstance(record, dict):
            add(findings, "record_not_object", f"Record {idx} is not an object", index=idx)
            continue
        ticker = str(record.get("ticker") or "")
        if not ticker:
            add(findings, "record_ticker_missing", f"Record {idx} is missing ticker", index=idx)
        else:
            if ticker in tickers:
                add(findings, "duplicate_ticker", f"Ticker `{ticker}` appears more than once", ticker=ticker)
            tickers.add(ticker)
        for field in REQUIRED_RECORD_FIELDS:
            if field not in record:
                add(findings, "record_field_missing", f"Record `{ticker or idx}` missing `{field}`", ticker=ticker, field=field)
        if not record.get("source_provenance"):
            add(findings, "record_provenance_missing", f"Record `{ticker or idx}` has no source provenance", ticker=ticker)
    trigger_artifact = next((a for a in report.get("source_artifacts", []) if isinstance(a, dict) and a.get("name") == "trigger_sheet"), {})
    trigger_last_day = trigger_artifact.get("last_trading_day")
    if trigger_last_day and report.get("market_data_as_of") and trigger_last_day != report.get("market_data_as_of"):
        add(
            findings,
            "artifact_date_mismatch",
            "Trigger-sheet last trading day does not match report market_data_as_of",
            severity="warning",
            trigger_last_trading_day=trigger_last_day,
            market_data_as_of=report.get("market_data_as_of"),
        )
    for artifact in report.get("source_artifacts", []) or []:
        if isinstance(artifact, dict) and artifact.get("exists") is False:
            add(findings, "source_artifact_missing", f"Source artifact `{artifact.get('name')}` is missing", artifact=artifact.get("name"))
    summary = report.get("summary", {}) if isinstance(report.get("summary"), dict) else {}
    hidden_tickers = set(summary.get("deployable_now_review_only", [])) | set(summary.get("prepare_or_wait", [])) | set(summary.get("do_not_touch", [])) | set(summary.get("watch", [])) | set(summary.get("bench_or_repair", [])) | set(summary.get("monitor", []))
    if tickers and not hidden_tickers.issubset(tickers):
        add(findings, "summary_ticker_not_in_records", "Summary references tickers not present in records", severity="warning", extra=sorted(hidden_tickers - tickers))
    market_view = report.get("market_view") if isinstance(report.get("market_view"), dict) else {}
    themes = market_view.get("current_investment_themes") if isinstance(market_view.get("current_investment_themes"), list) else []
    theme_text = " ".join(
        str(theme.get("read") or "").lower()
        for theme in themes
        if isinstance(theme, dict)
    )
    for phrase in STALE_THEME_PHRASES:
        if phrase in theme_text:
            add(
                findings,
                "stale_theme_language",
                f"Market/theme prose contains stale hard-coded language: `{phrase}`",
                phrase=phrase,
            )
    critical = sum(1 for f in findings if f["severity"] == "critical")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "critical" if critical else ("warning" if warning else "ok"),
        "summary": {"critical": critical, "warning": warning, "finding_count": len(findings)},
        "authority": {
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_execution_allowed": False,
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the review-only full portfolio view report.")
    parser.add_argument("--path", default=str(DEFAULT_REPORT))
    parser.add_argument("--window", default=None, help="Accepted for chain-manifest consistency; report carries its own window.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    report_path = Path(args.path)
    if not report_path.is_absolute():
        report_path = WORKSPACE / report_path
    report = read_json(report_path)
    validation = validate_report(report)
    if args.write:
        OUT_JSON.write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
        print(f"wrote {OUT_JSON}")
    print(
        "full_portfolio_view_validate: "
        f"{validation['status']} ({validation['summary']['critical']} critical, {validation['summary']['warning']} warning)"
    )
    for finding in validation["findings"][:20]:
        print(f"  - [{finding['severity']}] {finding['code']}: {finding['message']}")
    return 2 if validation["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
