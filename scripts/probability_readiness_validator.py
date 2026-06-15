from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from market_data_utils import atomic_write_json, load_json_artifact
from probability_readiness_report import DEFAULT_OUT as DEFAULT_REPORT, OUTCOME_UPDATES, STATE_HISTORY, load_jsonl, parse_dt, rel, state_history_summary
from state_history_outcome_update import validate_file as validate_outcome_updates

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "probability-readiness-validation.json"

CHECKED_ARTIFACTS = [
    DEFAULT_REPORT,
    TMP / "historical-regime-event-library.json",
    TMP / "research-freshness-opportunity-review.json",
    TMP / "small-mid-cap-regime-feed.json",
    TMP / "sector-expansion-board.json",
    TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json",
    TMP / "capital-deployment-recommendation-validation.json",
    TMP / "daily-review-objects-post-close.json",
    TMP / "daily-review-objects-morning.json",
    TMP / "daily-review-objects-sunday.json",
]

FORBIDDEN_PATTERNS: dict[str, re.Pattern[str]] = {
    "win_probability_spaced": re.compile(r"\bwin\s+probability\b", re.IGNORECASE),
    "win_probability_key": re.compile(r"\bwin_probability\b", re.IGNORECASE),
    "win_rate_spaced": re.compile(r"\bwin\s+rate\b", re.IGNORECASE),
    "win_rate_key": re.compile(r"\bwin_rate\b", re.IGNORECASE),
    "deploy_probability_spaced": re.compile(r"\bdeploy\s+probability\b", re.IGNORECASE),
    "deploy_probability_key": re.compile(r"\bdeploy_probability\b", re.IGNORECASE),
    "expected_return_spaced": re.compile(r"\bexpected\s+return\b", re.IGNORECASE),
    "expected_return_key": re.compile(r"\bexpected_return\b", re.IGNORECASE),
    "calibrated_score": re.compile(r"\bcalibrated\s+score\b", re.IGNORECASE),
    "calibrated_readiness_score": re.compile(r"\bcalibrated\s+readiness\s+score\b", re.IGNORECASE),
    "model_ranked_hyphen": re.compile(r"\bmodel-ranked\b", re.IGNORECASE),
    "model_ranked_spaced": re.compile(r"\bmodel\s+ranked\b", re.IGNORECASE),
    "model_ranked_key": re.compile(r"\bmodel_ranked\b", re.IGNORECASE),
    "predicted_outcome": re.compile(r"\bpredicted\s+outcome\b", re.IGNORECASE),
    "unsupported_forecast_accuracy": re.compile(r"\bforecast\s+accuracy\b", re.IGNORECASE),
    "percent_chance": re.compile(r"\b\d+(?:\.\d+)?\s*%\s+chance\b", re.IGNORECASE),
    "percent_likelihood": re.compile(r"\b\d+(?:\.\d+)?\s*%\s+likelihood\b", re.IGNORECASE),
    "probability_numeric_label": re.compile(r"\bprobability\s*[:=]\s*\d+(?:\.\d+)?\s*%?\b", re.IGNORECASE),
}

AUTHORITY_KEYS_MUST_BE_FALSE = {
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "owner_approval_granted",
    "owner_approval_inference_allowed",
    "per_packet_owner_approval_inferred",
    "model_ranked_deployment_allowed",
    "model_driven_deployment_allowed",
    "capital_action_allowed",
    "proposal_apply_allowed",
    "calibrated_probability_allowed",
    "prediction_allowed",
    "return_projection_claim_allowed",
    "paper_or_live_execution_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
}

BORDERLINE_CONFIDENCE_VALUES = {"moderate", "guarded"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def snippet(text: str) -> str:
    return text.replace("\n", " ")[:160]


def authority_value_is_false(value: Any) -> bool:
    if value is False:
        return True
    if isinstance(value, dict) and value.get("allowed") is False:
        return True
    return False


def should_skip_false_authority_key(key: str, value: Any) -> bool:
    return key in AUTHORITY_KEYS_MUST_BE_FALSE and authority_value_is_false(value)


def walk_text(value: Any, path: str = "$") -> list[tuple[str, str, str, Any]]:
    found: list[tuple[str, str, str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if not should_skip_false_authority_key(str(key), item):
                found.append((child_path, "key", str(key), item))
            found.extend(walk_text(item, child_path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(walk_text(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        found.append((path, "value", value, None))
    return found


def scan_forbidden(path: Path, data: Any, findings: list[dict[str, Any]]) -> None:
    for json_path, kind, text, value in walk_text(data):
        for label, pattern in FORBIDDEN_PATTERNS.items():
            match = pattern.search(text)
            if not match:
                continue
            findings.append({
                "severity": "critical",
                "artifact": rel(path),
                "path": json_path,
                "kind": kind,
                "issue": "forbidden_probability_or_modeling_language",
                "label": label,
                "snippet": snippet(text),
            })


def allowed_standing_workspace_authority(path: Path, json_path: str, key: str, value: Any) -> bool:
    """Allow top-level bounded workspace-maintenance authority without weakening execution guards."""
    if key not in {"owner_approval_granted", "portfolio_mutation_allowed"} or value is not True:
        return False

    cap_recs = TMP / "portfolio-mutation-proposals" / "current-capital-deployment-recommendations.json"
    cap_validation = TMP / "capital-deployment-recommendation-validation.json"
    if path == cap_recs and json_path in {
        "$.owner_approval_granted",
        "$.portfolio_mutation_allowed",
        "$.authority.owner_approval_granted",
        "$.authority.portfolio_mutation_allowed",
    }:
        return True
    if path == cap_validation and json_path in {
        "$.authority.owner_approval_granted",
        "$.authority.portfolio_mutation_allowed",
    }:
        return True
    if path == DEFAULT_REPORT and json_path in {
        "$.evidence_artifacts.capital_deployment_recommendations.authority_snapshot.owner_approval_granted",
        "$.evidence_artifacts.capital_deployment_recommendations.authority_snapshot.portfolio_mutation_allowed",
        "$.evidence_artifacts.capital_deployment_recommendation_validation.authority_snapshot.owner_approval_granted",
        "$.evidence_artifacts.capital_deployment_recommendation_validation.authority_snapshot.portfolio_mutation_allowed",
    }:
        return True
    return False


def audit_authority(path: Path, data: Any, findings: list[dict[str, Any]]) -> None:
    if not isinstance(data, dict):
        return
    for json_path, _kind, key, value in walk_text(data):
        if key in AUTHORITY_KEYS_MUST_BE_FALSE and not authority_value_is_false(value):
            if allowed_standing_workspace_authority(path, json_path, key, value):
                continue
            findings.append({
                "severity": "critical",
                "artifact": rel(path),
                "path": json_path,
                "field": key,
                "issue": "authority_widening_detected",
                "value": value,
            })


def report_gate_checks(report: dict[str, Any] | None, history: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    if not isinstance(report, dict):
        findings.append({"severity": "critical", "artifact": rel(DEFAULT_REPORT), "issue": "probability readiness report is missing or unreadable"})
        return
    verdict = str(report.get("verdict") or "")
    realized = int(history.get("realized_outcome_count") or 0)
    if verdict == "READY":
        findings.append({"severity": "critical", "artifact": rel(DEFAULT_REPORT), "field": "verdict", "issue": "READY verdict is not allowed in WF55 first pass"})
    if realized == 0 and verdict not in {"SAFE_WITH_GAPS", "NOT_READY"}:
        findings.append({"severity": "critical", "artifact": rel(DEFAULT_REPORT), "field": "verdict", "issue": "verdict must be SAFE_WITH_GAPS or NOT_READY while realized outcomes are empty", "value": verdict})
    authority = report.get("authority") or {}
    if not isinstance(authority, dict) or authority.get("hard_false_authority_block") is not True:
        findings.append({"severity": "critical", "artifact": rel(DEFAULT_REPORT), "field": "authority.hard_false_authority_block", "issue": "report must carry hard-false authority block"})
    for key in AUTHORITY_KEYS_MUST_BE_FALSE:
        if key in authority and authority.get(key) is not False:
            findings.append({"severity": "critical", "artifact": rel(DEFAULT_REPORT), "field": f"authority.{key}", "issue": "report authority must be false", "value": authority.get(key)})
    for section in ("forecast_question_inventory", "outcome_label_taxonomy", "source_quality_gates", "probability_language_audit", "data_readiness_gaps", "limits", "historical_regime_analog_summary"):
        if section not in report:
            findings.append({"severity": "critical", "artifact": rel(DEFAULT_REPORT), "field": section, "issue": "required report section missing"})
    if realized == 0:
        for gate in report.get("source_quality_gates") or []:
            if isinstance(gate, dict) and gate.get("gate") == "retained_realized_outcomes" and gate.get("status") == "pass":
                findings.append({"severity": "critical", "artifact": rel(DEFAULT_REPORT), "field": "source_quality_gates.retained_realized_outcomes", "issue": "gate falsely passes while realized outcomes are empty"})


def historical_regime_library_checks(data_by_path: dict[Path, Any], findings: list[dict[str, Any]]) -> None:
    path = TMP / "historical-regime-event-library.json"
    data = data_by_path.get(path)
    if not isinstance(data, dict):
        findings.append({"severity": "warning", "artifact": rel(path), "issue": "historical_regime_event_library_missing"})
        return
    authority = data.get("authority") if isinstance(data.get("authority"), dict) else {}
    for key in ("calibrated_probability_allowed", "prediction_allowed", "model_ranked_deployment_allowed", "return_projection_claim_allowed", "capital_action_allowed", "paper_or_live_execution_allowed", "owner_approval_inference_allowed"):
        if authority.get(key) is not False:
            findings.append({"severity": "critical", "artifact": rel(path), "field": f"authority.{key}", "issue": "historical library authority must remain false", "value": authority.get(key)})
    events = data.get("events") if isinstance(data.get("events"), list) else []
    if len(events) < 10:
        findings.append({"severity": "critical", "artifact": rel(path), "field": "events", "issue": "historical library needs broad event coverage", "value": len(events)})
    small_large_count = int((data.get("summary") or {}).get("small_large_comparison_available_count") or 0)
    if small_large_count < 5:
        findings.append({"severity": "warning", "artifact": rel(path), "field": "summary.small_large_comparison_available_count", "issue": "small_large_comparison_coverage_thin", "value": small_large_count})
    if not any(str(row.get("start")) < "1990-01-01" for row in events):
        findings.append({"severity": "critical", "artifact": rel(path), "field": "events", "issue": "pre_1990_regimes_missing"})


def outcome_update_checks(findings: list[dict[str, Any]]) -> None:
    report = validate_outcome_updates(OUTCOME_UPDATES, STATE_HISTORY)
    for item in report.get("findings") or []:
        copied = dict(item)
        copied["artifact"] = rel(OUTCOME_UPDATES)
        findings.append(copied)


def state_history_checks(rows: list[dict[str, Any]], history: dict[str, Any], findings: list[dict[str, Any]]) -> None:
    for row_index, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or row.get("_parse_error"):
            continue
        captured_at = parse_dt(row.get("captured_at_utc"))
        future = row.get("future_outcomes") or {}
        if not isinstance(future, dict):
            continue
        for field in ("owner_decision_at_utc", "realized_outcomes_updated_at_utc"):
            future_dt = parse_dt(future.get(field))
            if future_dt and captured_at and future_dt <= captured_at:
                findings.append({
                    "severity": "critical",
                    "artifact": rel(STATE_HISTORY),
                    "row": row_index,
                    "field": field,
                    "issue": "future_outcome_timestamp_not_after_capture",
                    "captured_at_utc": row.get("captured_at_utc"),
                    "future_timestamp": future.get(field),
                })
    if float(history.get("history_span_days") or 0) < 30:
        findings.append({"severity": "warning", "artifact": rel(STATE_HISTORY), "issue": "history_span_below_30_days", "history_span_days": history.get("history_span_days")})
    if float(history.get("max_timestamp_gap_hours") or 0) > 48:
        findings.append({"severity": "warning", "artifact": rel(STATE_HISTORY), "issue": "timestamp_gap_above_48_hours", "max_timestamp_gap_hours": history.get("max_timestamp_gap_hours")})


def has_annotation(container: dict[str, Any], key: str) -> bool:
    direct_keys = {f"{key}_basis", f"{key}_annotation", f"{key}_metadata", f"{key}_calibration"}
    for direct in direct_keys:
        value = container.get(direct)
        if isinstance(value, str):
            text = value.lower()
            if "heuristic" in text and "uncalibrated" in text:
                return True
        if isinstance(value, dict):
            text = json.dumps(value, sort_keys=True).lower()
            if "heuristic" in text and "uncalibrated" in text:
                return True
    text = json.dumps(container, sort_keys=True).lower()
    return key in text and "heuristic" in text and "uncalibrated" in text and ("not_probability" in text or "non-predictive" in text or "not a probability" in text)


def borderline_annotation_checks(path: Path, data: Any, findings: list[dict[str, Any]]) -> None:
    def visit(value: Any, json_path: str = "$") -> None:
        if isinstance(value, dict):
            if "signal_score" in value and not has_annotation(value, "signal_score"):
                findings.append({"severity": "warning", "artifact": rel(path), "path": json_path, "field": "signal_score", "issue": "borderline heuristic field lacks explicit uncalibrated annotation"})
            if str(value.get("confidence") or "").lower() in BORDERLINE_CONFIDENCE_VALUES and not has_annotation(value, "confidence"):
                findings.append({"severity": "warning", "artifact": rel(path), "path": json_path, "field": "confidence", "issue": "borderline confidence field lacks explicit uncalibrated annotation"})
            for key, item in value.items():
                visit(item, f"{json_path}.{key}")
        elif isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{json_path}[{index}]")
    visit(data)


def sector_degraded_warning(data_by_path: dict[Path, Any], findings: list[dict[str, Any]]) -> None:
    sector = data_by_path.get(TMP / "sector-expansion-board.json")
    if isinstance(sector, dict) and str(sector.get("status") or "") == "degraded":
        findings.append({"severity": "warning", "artifact": "tmp/sector-expansion-board.json", "issue": "sector_expansion_board_degraded"})


def build_validation() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    outcome_rows = load_jsonl(OUTCOME_UPDATES)
    rows = load_jsonl(STATE_HISTORY)
    history = state_history_summary(rows, outcome_rows)
    data_by_path: dict[Path, Any] = {}
    for path in CHECKED_ARTIFACTS:
        if path.exists():
            data = load_json(path)
            data_by_path[path] = data
            scan_forbidden(path, data, findings)
            audit_authority(path, data, findings)
            borderline_annotation_checks(path, data, findings)
        else:
            if path == DEFAULT_REPORT:
                findings.append({"severity": "critical", "artifact": rel(path), "issue": "required report missing"})
    report = data_by_path.get(DEFAULT_REPORT)
    report_gate_checks(report if isinstance(report, dict) else None, history, findings)
    state_history_checks(rows, history, findings)
    outcome_update_checks(findings)
    sector_degraded_warning(data_by_path, findings)
    historical_regime_library_checks(data_by_path, findings)

    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warning = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "blocked" if critical else ("warning" if warning else "ok"),
        "checked_artifacts": [rel(path) for path in CHECKED_ARTIFACTS if path.exists() or path == DEFAULT_REPORT],
        "state_history_summary": history,
        "summary": {"critical": critical, "warning": warning, "findings": len(findings)},
        "findings": findings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the WF55 probability-readiness report and live artifact language/authority posture.")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_validation()
    if args.write:
        atomic_write_json(DEFAULT_OUT, report, indent=2)
        print(f"wrote {rel(DEFAULT_OUT)}")
    print(
        "probability_readiness_validator: "
        f"{report['status']} ({report['summary']['critical']} critical, {report['summary']['warning']} warning)"
    )
    return 1 if report["summary"]["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
