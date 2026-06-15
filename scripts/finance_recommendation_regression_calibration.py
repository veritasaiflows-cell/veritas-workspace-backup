#!/usr/bin/env python3
"""Build a conservative recommendation regression/calibration report.

This report is review-only. It explains what historical outcome evidence is
available and whether it is ready for calibration diagnostics. It never ranks
capital deployment, authorizes action, or claims predictive skill.
"""
from __future__ import annotations

import argparse
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

PERFORMANCE_DIGEST = TMP / "finance-decision-performance-digest.json"
SHADOW_SCORECARD = TMP / "wf87-shadow-outcome-scorecard.json"
RECOMMENDATION_LEDGER = TMP / "recommendation-outcome-ledger-current.json"
DEFAULT_JSON = TMP / "finance-recommendation-regression-calibration.json"
DEFAULT_MD = TMP / "finance-recommendation-regression-calibration.md"

SCHEMA = "veritas.finance_recommendation_regression_calibration.v1"
MIN_GROUP_SAMPLE = 2
MIN_REGRESSION_PAIRS = 4
MIN_WALK_FORWARD_ROWS = 20
MIN_WALK_FORWARD_PAIRS = 10

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "historical_calibration_only": True,
    "explanation_only": True,
    "predictive_skill_claim_allowed_now": False,
    "model_performance_claim_allowed_now": False,
    "model_training_enabled": False,
    "model_ranking_claim_allowed_now": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "owner_approval_inferred": False,
}

FORBIDDEN_TRUE_KEYS = {
    key for key, value in AUTHORITY_BOUNDARY.items()
    if value is False
}

DIRECT_SIGNAL_FIELDS = (
    "signal_score",
    "recommendation_score",
    "decision_score",
    "confidence_score",
    "conviction_score",
    "trade_grade_numeric",
    "composite_score",
    "rank_score",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def parse_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def load_dict(path: Path) -> dict[str, Any]:
    value = load_json_artifact(path)
    return value if isinstance(value, dict) else {}


def first_numeric(*objects: dict[str, Any]) -> tuple[float | None, str | None]:
    for obj in objects:
        for field in DIRECT_SIGNAL_FIELDS:
            value = parse_float(obj.get(field))
            if value is not None:
                return value, field
    return None, None


def band_position_signal(known: dict[str, Any]) -> tuple[float | None, str | None]:
    anchor = parse_float(known.get("anchor_price") or known.get("current_price") or known.get("entry_price"))
    low = parse_float(known.get("entry_band_low") or known.get("band_low") or known.get("current_band_low"))
    high = parse_float(known.get("entry_band_high") or known.get("band_high") or known.get("current_band_high"))
    if anchor is None or low is None or high is None or high <= low:
        return None, None
    return round((anchor - low) / (high - low), 6), "band_position_pct"


def extract_signal(*objects: dict[str, Any]) -> tuple[float | None, str | None]:
    direct, source = first_numeric(*objects)
    if direct is not None:
        return direct, source
    for obj in objects:
        band_signal, band_source = band_position_signal(obj)
        if band_signal is not None:
            return band_signal, band_source
    return None, None


def row_id(*parts: Any) -> str:
    return "|".join(str(part or "") for part in parts)


def extract_wf55_rows(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in as_list(ledger.get("tracked_rows")):
        if not isinstance(item, dict):
            continue
        payload = as_dict(item.get("payload"))
        scorecard = as_dict(item.get("forward_scorecard"))
        known = as_dict(scorecard.get("known_at_time"))
        ticker = str(item.get("ticker") or payload.get("ticker") or "").upper()
        signal, signal_source = extract_signal(payload, scorecard, known, item)
        checkpoints = [cp for cp in as_list(scorecard.get("checkpoints")) if isinstance(cp, dict)]
        if not checkpoints:
            rows.append(
                {
                    "evidence_id": row_id("wf55", item.get("ledger_event_id"), ticker, "no_checkpoint"),
                    "source": "wf55_recommendation_outcome_ledger",
                    "ticker": ticker,
                    "horizon": "unknown",
                    "status": "pending_no_checkpoint",
                    "pending": True,
                    "signal": signal,
                    "signal_source": signal_source,
                    "forward_return_pct": None,
                    "return_source": None,
                    "group_key": "wf55:unknown",
                }
            )
            continue
        for checkpoint in checkpoints:
            observed = parse_float(checkpoint.get("observed_price"))
            abs_return = parse_float(checkpoint.get("absolute_return_pct"))
            rel_return = parse_float(checkpoint.get("relative_return_pct"))
            return_value = abs_return if abs_return is not None else rel_return
            status = str(checkpoint.get("status") or "unknown")
            horizon = str(checkpoint.get("horizon_days") or "unknown")
            scored = return_value is not None and observed is not None
            rows.append(
                {
                    "evidence_id": row_id("wf55", item.get("ledger_event_id"), ticker, horizon),
                    "source": "wf55_recommendation_outcome_ledger",
                    "ticker": ticker,
                    "horizon": f"{horizon}d" if horizon != "unknown" else "unknown",
                    "status": "scored" if scored else status,
                    "pending": not scored,
                    "signal": signal,
                    "signal_source": signal_source,
                    "forward_return_pct": return_value,
                    "return_source": "absolute_return_pct" if abs_return is not None else "relative_return_pct" if rel_return is not None else None,
                    "group_key": f"wf55:{horizon}d",
                    "entry_band_status": known.get("band_status") or payload.get("entry_band_status"),
                }
            )
    return rows


def extract_shadow_rows(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for score in as_list(scorecard.get("scores")):
        if not isinstance(score, dict):
            continue
        signal, signal_source = extract_signal(score)
        directional = parse_float(score.get("directional_return_pct"))
        raw = parse_float(score.get("return_pct"))
        return_value = directional if directional is not None else raw
        scored = score.get("scoreable") is True and return_value is not None
        rows.append(
            {
                "evidence_id": row_id("shadow", score.get("decision_id")),
                "source": "wf87_shadow_outcome_scorecard",
                "ticker": str(score.get("ticker") or "").upper(),
                "horizon": "next_regular_session",
                "status": "scored" if scored else str(score.get("outcome_status") or "unknown"),
                "pending": not scored,
                "signal": signal,
                "signal_source": signal_source,
                "forward_return_pct": return_value,
                "return_source": "directional_return_pct" if directional is not None else "return_pct" if raw is not None else None,
                "group_key": "wf87_shadow:next_regular_session",
                "entry_band_status": score.get("entry_band_status"),
                "outcome_label": score.get("outcome_label"),
            }
        )
    return rows


def mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def slope_correlation(pairs: list[tuple[float, float]]) -> dict[str, Any]:
    if len(pairs) < MIN_REGRESSION_PAIRS:
        return {
            "status": "insufficient_numeric_pairs",
            "pair_count": len(pairs),
            "minimum_pair_count": MIN_REGRESSION_PAIRS,
            "slope": None,
            "intercept": None,
            "correlation": None,
            "r_squared": None,
        }
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    sxx = sum((x - x_mean) ** 2 for x in xs)
    syy = sum((y - y_mean) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return {
            "status": "zero_variance",
            "pair_count": len(pairs),
            "minimum_pair_count": MIN_REGRESSION_PAIRS,
            "slope": None,
            "intercept": None,
            "correlation": None,
            "r_squared": None,
        }
    sxy = sum((x - x_mean) * (y - y_mean) for x, y in pairs)
    slope = sxy / sxx
    intercept = y_mean - slope * x_mean
    correlation = sxy / math.sqrt(sxx * syy)
    return {
        "status": "computed_review_only",
        "pair_count": len(pairs),
        "minimum_pair_count": MIN_REGRESSION_PAIRS,
        "slope": round(slope, 6),
        "intercept": round(intercept, 6),
        "correlation": round(correlation, 6),
        "r_squared": round(correlation * correlation, 6),
        "interpretation": "Univariate in-sample diagnostic only; not a deployment ranker or predictive skill claim.",
    }


def grouped_average_returns(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        if parse_float(row.get("forward_return_pct")) is None:
            continue
        groups.setdefault(str(row.get("group_key") or "unknown"), []).append(row)
    output: list[dict[str, Any]] = []
    for key in sorted(groups):
        values = [float(row["forward_return_pct"]) for row in groups[key]]
        output.append(
            {
                "group_key": key,
                "sample_count": len(values),
                "minimum_sample_for_group_average": MIN_GROUP_SAMPLE,
                "average_forward_return_pct": round(mean(values) or 0.0, 6) if len(values) >= MIN_GROUP_SAMPLE else None,
                "status": "computed_review_only" if len(values) >= MIN_GROUP_SAMPLE else "insufficient_group_sample",
                "tickers": sorted({str(row.get("ticker") or "") for row in groups[key] if row.get("ticker")}),
            }
        )
    return output


def signal_coverage(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    scored = [row for row in rows if parse_float(row.get("forward_return_pct")) is not None]
    signal_rows = [row for row in rows if parse_float(row.get("signal")) is not None]
    paired = [row for row in scored if parse_float(row.get("signal")) is not None]
    by_source: dict[str, int] = {}
    for row in signal_rows:
        source = str(row.get("signal_source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1
    return {
        "evidence_row_count": total,
        "scored_row_count": len(scored),
        "pending_row_count": total - len(scored),
        "signal_present_count": len(signal_rows),
        "numeric_signal_and_return_pair_count": len(paired),
        "signal_coverage_ratio": round(len(signal_rows) / total, 6) if total else 0.0,
        "paired_signal_coverage_ratio": round(len(paired) / len(scored), 6) if scored else 0.0,
        "signal_sources": dict(sorted(by_source.items())),
    }


def readiness_classification(coverage: dict[str, Any], regression: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = int(coverage.get("scored_row_count") or 0)
    pairs = int(coverage.get("numeric_signal_and_return_pair_count") or 0)
    paired_ratio = float(coverage.get("paired_signal_coverage_ratio") or 0.0)
    source_groups = {str(row.get("group_key") or "unknown") for row in rows if parse_float(row.get("forward_return_pct")) is not None}
    if scored == 0:
        classification = "not_ready_no_scored_outcomes"
    elif scored < MIN_WALK_FORWARD_ROWS:
        classification = "not_ready_insufficient_sample"
    elif pairs < MIN_WALK_FORWARD_PAIRS:
        classification = "not_ready_insufficient_numeric_signal_pairs"
    elif paired_ratio < 0.5:
        classification = "not_ready_low_signal_coverage"
    elif len(source_groups) < 2:
        classification = "research_ready_single_group_only"
    else:
        classification = "walk_forward_design_candidate_review_only"
    return {
        "classification": classification,
        "minimum_scored_rows_for_walk_forward": MIN_WALK_FORWARD_ROWS,
        "minimum_numeric_pairs_for_walk_forward": MIN_WALK_FORWARD_PAIRS,
        "scored_rows": scored,
        "numeric_pairs": pairs,
        "scored_group_count": len(source_groups),
        "regression_status": regression.get("status"),
        "predictive_skill_claim_allowed_now": False,
        "capital_ranking_allowed_now": False,
    }


def confidence_penalties(coverage: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    penalties: list[dict[str, Any]] = []
    scored = int(coverage.get("scored_row_count") or 0)
    pending = int(coverage.get("pending_row_count") or 0)
    pairs = int(coverage.get("numeric_signal_and_return_pair_count") or 0)
    paired_ratio = float(coverage.get("paired_signal_coverage_ratio") or 0.0)
    groups = {str(row.get("group_key") or "unknown") for row in rows if parse_float(row.get("forward_return_pct")) is not None}
    if scored < MIN_WALK_FORWARD_ROWS:
        penalties.append({"code": "small_scored_sample", "severity": "high", "detail": f"{scored} scored rows; need at least {MIN_WALK_FORWARD_ROWS} before walk-forward claims."})
    if pairs < MIN_WALK_FORWARD_PAIRS:
        penalties.append({"code": "few_numeric_signal_pairs", "severity": "high", "detail": f"{pairs} numeric signal/return pairs; regression remains diagnostic only."})
    if paired_ratio < 0.5:
        penalties.append({"code": "low_paired_signal_coverage", "severity": "medium", "detail": f"paired coverage is {paired_ratio:.2f}."})
    if pending > scored:
        penalties.append({"code": "pending_outcomes_dominate", "severity": "medium", "detail": f"{pending} pending rows versus {scored} scored rows."})
    if len(groups) < 2 and scored:
        penalties.append({"code": "single_scored_group", "severity": "medium", "detail": "Scored rows come from fewer than two horizon/source groups."})
    penalties.append({"code": "no_out_of_sample_validation", "severity": "high", "detail": "No pre-registered out-of-sample split is present in this report."})
    return penalties


def anti_curve_fit_warnings(coverage: dict[str, Any], regression: dict[str, Any]) -> list[str]:
    warnings = [
        "Do not optimize thresholds, weights, or ticker routing from this report.",
        "Treat any computed slope/correlation as in-sample explanation only.",
        "Require a pre-registered walk-forward split before using diagnostics in a decision process.",
    ]
    if int(coverage.get("scored_row_count") or 0) < MIN_WALK_FORWARD_ROWS:
        warnings.append("Sample size is too small for a predictive skill or expected-return claim.")
    if regression.get("status") != "computed_review_only":
        warnings.append("Regression was not computed because numeric paired evidence is insufficient or degenerate.")
    return warnings


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in FORBIDDEN_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{index}]"))
    return paths


def validate_report(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    boundary = as_dict(report.get("authority_boundary"))
    for key, expected in AUTHORITY_BOUNDARY.items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    drift = authority_true_paths(report)
    if drift:
        errors.append("authority_drift_detected")
    readiness = as_dict(report.get("walk_forward_readiness"))
    if readiness.get("classification") != "walk_forward_design_candidate_review_only":
        warnings.append(str(readiness.get("classification") or "walk_forward_not_ready"))
    if as_dict(report.get("regression_diagnostics")).get("status") != "computed_review_only":
        warnings.append("regression_not_computed")
    if int(as_dict(report.get("sample_counts")).get("scored_row_count") or 0) < MIN_WALK_FORWARD_ROWS:
        warnings.append("insufficient_sample_no_predictive_skill_claim")
    return {
        "status": "critical" if errors else "warning" if warnings else "ok",
        "errors": errors,
        "warnings": warnings,
        "authority_drift_paths": drift,
    }


def build_report(paths: dict[str, Path]) -> dict[str, Any]:
    performance = load_dict(paths["performance_digest"])
    shadow = load_dict(paths["shadow_scorecard"])
    ledger = load_dict(paths["recommendation_ledger"])
    rows = extract_wf55_rows(ledger) + extract_shadow_rows(shadow)
    rows.sort(key=lambda row: (str(row.get("ticker") or ""), str(row.get("source") or ""), str(row.get("horizon") or "")))
    coverage = signal_coverage(rows)
    pairs = [
        (float(row["signal"]), float(row["forward_return_pct"]))
        for row in rows
        if parse_float(row.get("signal")) is not None and parse_float(row.get("forward_return_pct")) is not None
    ]
    regression = slope_correlation(pairs)
    grouped = grouped_average_returns(rows)
    readiness = readiness_classification(coverage, regression, rows)
    report = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow_id": "WF87",
        "status": "review_only_calibration_not_ready" if readiness["classification"] != "walk_forward_design_candidate_review_only" else "review_only_walk_forward_design_candidate",
        "purpose": "Conservative calibration diagnostics for historical recommendation/shadow outcome evidence.",
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        "decision_contract": {
            "outputs_are_explanation_and_calibration_only": True,
            "cannot_rank_capital_deployment": True,
            "cannot_authorize_capital_or_trade_action": True,
            "cannot_infer_owner_approval": True,
            "cannot_mutate_portfolio_or_canon": True,
            "sample_size_must_gate_predictive_claims": True,
        },
        "source_artifacts": {key: rel(path) for key, path in paths.items()},
        "source_status": {
            "performance_digest_status": performance.get("status"),
            "shadow_scorecard_status": shadow.get("status"),
            "recommendation_ledger_status": ledger.get("status"),
        },
        "sample_counts": coverage,
        "grouped_average_forward_returns": grouped,
        "regression_diagnostics": regression,
        "walk_forward_readiness": readiness,
        "confidence_penalties": confidence_penalties(coverage, rows),
        "anti_curve_fit_warnings": anti_curve_fit_warnings(coverage, regression),
        "evidence_rows": rows,
        "next_safe_action": "Keep accumulating scored forward outcomes; design a pre-registered walk-forward split only after sample and signal coverage gates are met.",
        "stop_lines": [
            "No predictive skill claim from small samples.",
            "No capital deployment ranking or approval from calibration diagnostics.",
            "No paper/live execution, account action, portfolio/canon mutation, or owner approval inference.",
        ],
    }
    report["validation"] = validate_report(report)
    if report["validation"]["status"] == "critical":
        report["status"] = "blocked_authority_or_contract_error"
    return report


def render_md(report: dict[str, Any]) -> str:
    counts = as_dict(report.get("sample_counts"))
    regression = as_dict(report.get("regression_diagnostics"))
    readiness = as_dict(report.get("walk_forward_readiness"))
    lines = [
        "# Finance Recommendation Regression Calibration",
        "",
        f"- Generated UTC: `{report.get('generated_at_utc')}`",
        f"- Status: `{report.get('status')}`",
        f"- Validation: `{as_dict(report.get('validation')).get('status')}`",
        f"- Evidence rows: `{counts.get('evidence_row_count')}`",
        f"- Scored / pending rows: `{counts.get('scored_row_count')}` / `{counts.get('pending_row_count')}`",
        f"- Numeric signal/return pairs: `{counts.get('numeric_signal_and_return_pair_count')}`",
        f"- Walk-forward readiness: `{readiness.get('classification')}`",
        f"- Regression: `{regression.get('status')}`; slope `{regression.get('slope')}`; correlation `{regression.get('correlation')}`",
        "",
        "## Decision Contract",
        "",
        "Outputs are explanation/calibration only. They cannot rank capital deployment, authorize action, infer owner approval, or mutate portfolio/canon surfaces.",
        "",
        "## Confidence Penalties",
    ]
    for penalty in as_list(report.get("confidence_penalties")):
        lines.append(f"- `{penalty.get('code')}` ({penalty.get('severity')}): {penalty.get('detail')}")
    lines.extend(["", "## Anti-Curve-Fit Warnings"])
    for warning in as_list(report.get("anti_curve_fit_warnings")):
        lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only finance recommendation regression calibration report")
    parser.add_argument("--performance-digest", type=Path, default=PERFORMANCE_DIGEST)
    parser.add_argument("--shadow-scorecard", type=Path, default=SHADOW_SCORECARD)
    parser.add_argument("--recommendation-ledger", type=Path, default=RECOMMENDATION_LEDGER)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {
        "performance_digest": abs_path(args.performance_digest),
        "shadow_scorecard": abs_path(args.shadow_scorecard),
        "recommendation_ledger": abs_path(args.recommendation_ledger),
    }
    report = build_report(paths)
    json_out = abs_path(args.json_out)
    md_out = abs_path(args.md_out)
    if args.write:
        atomic_write_json(json_out, report)
    if args.write_md:
        atomic_write_text(md_out, render_md(report))
    if not args.quiet:
        counts = as_dict(report.get("sample_counts"))
        regression = as_dict(report.get("regression_diagnostics"))
        readiness = as_dict(report.get("walk_forward_readiness"))
        print(
            "status={status} validation={validation} rows={rows} scored={scored} pairs={pairs} "
            "regression={regression} readiness={readiness} out={out}".format(
                status=report.get("status"),
                validation=as_dict(report.get("validation")).get("status"),
                rows=counts.get("evidence_row_count"),
                scored=counts.get("scored_row_count"),
                pairs=counts.get("numeric_signal_and_return_pair_count"),
                regression=regression.get("status"),
                readiness=readiness.get("classification"),
                out=rel(json_out) if args.write else None,
            )
        )
    if args.validate and report["validation"]["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
