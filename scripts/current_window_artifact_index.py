from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
import official_capture_period_registry as _registry

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "current-window-artifacts.json"
OUT_MD = OUT_JSON.with_suffix(".md")
SCHEMA_VERSION = 1

WINDOW_ALIASES = {"full": "post-close"}
WINDOWS = ("morning", "post-close", "post-earnings", "sunday")

COMMON_ARTIFACTS: dict[str, str] = {
    "run_chain": "tmp/run-chain-{window}.json",
    "run_summary": "tmp/run-summary-{window}.json",
    "dashboard_validation": "tmp/dashboard-validation.json",
    "dashboard_acceptance": "tmp/dashboard-acceptance-report.json",
    "deployment_readiness_surface": "tmp/deployment-readiness-surface.json",
    "daily_price_trend_signals": "tmp/daily-price-trend-signals.json",
    "market_intelligence_events": "tmp/market-intelligence-events-{window}.json",
    "daily_review_objects": "tmp/daily-review-objects-{window}.json",
    "board_canon_guardrail": "tmp/board-canon-guardrail.json",
    "stale_intelligence_guardrail": "tmp/stale-intelligence-guardrail.json",
    "canonical_note_patch_proposal": "tmp/canonical-note-patch-proposal.json",
    "finance_discrepancy_resolver": "tmp/finance-discrepancy-resolver.json",
    "capital_deployment_recommendations": "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.json",
    "capital_deployment_recommendations_md": "tmp/portfolio-mutation-proposals/current-capital-deployment-recommendations.md",
    "capital_deployment_recommendation_validation": "tmp/capital-deployment-recommendation-validation.json",
    "bank_native_sec_concept_probe": "tmp/bank-native-sec-concept-probe.json",
    "fundamental_metrics_current": "tmp/fundamental-metrics-current.json",
    "fundamental_metrics_validation": "tmp/fundamental-metrics-validation.json",
    "fundamental_metrics_history": "data/fundamentals/fundamentals-quarterly-v1.jsonl",
    "fundamental_ir_metadata": "data/fundamentals/company-ir-metadata.json",
    "fundamental_ir_reconciliation_packets": "tmp/fundamental-ir-reconciliation-packets.json",
    "fundamental_ir_reconciliation_validation": "tmp/fundamental-ir-reconciliation-validation.json",
    "official_earnings_bridge": "tmp/official-earnings-bridge.json",
    "official_earnings_bridge_validation": "tmp/official-earnings-bridge-validation.json",
    "watchlist_promotion_radar": "tmp/watchlist-promotion-radar.json",
    "archive_suggestions": "tmp/archive-suggestions.json",
}

# Official IR capture aliases populated from the period registry so future-quarter
# rollforward is a registry edit, not a path-string edit here. Tickers listed here
# are the historical alias set surfaced in the current-window artifact index;
# long-tail tickers are tracked in chain_manifest expected_outputs but intentionally
# not surfaced as stable index aliases.
_INDEX_ALIAS_TICKERS = {
    "GOOG", "ETN", "VRT", "AMZN", "MSFT", "NVDA",
    "JPM", "GS", "XOM", "LMT", "RTX", "BRK.B",
    "AMD", "CAT", "CVX", "PLTR", "GE", "LLY", "META", "PH",
}
for _entry in _registry.all_periods():
    if _entry.ticker not in _INDEX_ALIAS_TICKERS:
        continue
    COMMON_ARTIFACTS[_entry.alias_base] = _registry.rel_posix(_entry.json_path)
    COMMON_ARTIFACTS[f"{_entry.alias_base}_validation"] = _registry.rel_posix(_entry.validation_path)
del _entry

WINDOW_ARTIFACTS: dict[str, dict[str, str]] = {
    "morning": {
        "snapshot": "tmp/premarket-snapshot.json",
        "brief_packet": "tmp/premarket-brief-input.json",
        "review_brief_json": "tmp/reports/premarket-review-brief-latest.json",
        "review_brief_html": "tmp/reports/premarket-review-brief-latest.html",
        "full_portfolio_view": "tmp/full-portfolio-view.json",
        "full_portfolio_view_validation": "tmp/full-portfolio-view-validation.json",
        "portfolio_snapshot_patch_proposal": "tmp/portfolio-snapshot-patch-proposal.json",
    },
    "post-close": {
        "snapshot": "tmp/postmarket-snapshot.json",
        "brief_packet": "tmp/postclose-brief-input.json",
        "daily_executive_brief": "tmp/daily-executive-brief.json",
        "market_today_answer_packet": "tmp/market-today-answer-packet.json",
        "full_portfolio_view": "tmp/full-portfolio-view.json",
        "full_portfolio_view_validation": "tmp/full-portfolio-view-validation.json",
        "portfolio_snapshot_patch_proposal": "tmp/portfolio-snapshot-patch-proposal.json",
        "state_history": "data/state-history/state-history-v1.jsonl",
    },
    "post-earnings": {
        "post_earnings_prep": "tmp/post-earnings-prep.json",
        "post_earnings_note_targets": "tmp/post-earnings-note-targets.json",
    },
    "sunday": {
        "snapshot": "tmp/postmarket-snapshot.json",
        "weekly_macro_snapshot": "tmp/weekly-macro-snapshot.json",
        "weekly_intelligence_brief": "tmp/weekly-intelligence-brief.json",
        "weekly_printable_brief_json": "tmp/reports/weekly-intelligence-brief-printable-latest.json",
        "weekly_printable_brief_html": "tmp/reports/weekly-intelligence-brief-printable-latest.html",
        "daily_executive_brief": "tmp/daily-executive-brief.json",
        "full_portfolio_view": "tmp/full-portfolio-view.json",
        "full_portfolio_view_validation": "tmp/full-portfolio-view-validation.json",
        "portfolio_snapshot_patch_proposal": "tmp/portfolio-snapshot-patch-proposal.json",
    },
}

ROLE_ORDER = [
    "run_summary",
    "run_chain",
    "snapshot",
    "brief_packet",
    "review_brief_json",
    "weekly_printable_brief_json",
    "daily_executive_brief",
    "market_today_answer_packet",
    "deployment_readiness_surface",
    "daily_review_objects",
    "full_portfolio_view",
    "full_portfolio_view_validation",
    "canonical_note_patch_proposal",
    "portfolio_snapshot_patch_proposal",
    "finance_discrepancy_resolver",
    "capital_deployment_recommendations",
    "capital_deployment_recommendations_md",
    "capital_deployment_recommendation_validation",
    "bank_native_sec_concept_probe",
    "fundamental_metrics_current",
    "fundamental_metrics_validation",
    "fundamental_metrics_history",
    "fundamental_ir_metadata",
    "goog_official_ir_capture",
    "goog_official_ir_capture_validation",
    "etn_official_ir_capture",
    "etn_official_ir_capture_validation",
    "vrt_official_ir_capture",
    "vrt_official_ir_capture_validation",
    "amzn_official_ir_capture",
    "amzn_official_ir_capture_validation",
    "msft_official_ir_capture",
    "msft_official_ir_capture_validation",
    "nvda_official_ir_capture",
    "nvda_official_ir_capture_validation",
    "jpm_official_ir_capture",
    "jpm_official_ir_capture_validation",
    "gs_official_ir_capture",
    "gs_official_ir_capture_validation",
    "xom_official_ir_capture",
    "xom_official_ir_capture_validation",
    "lmt_official_ir_capture",
    "lmt_official_ir_capture_validation",
    "rtx_official_ir_capture",
    "rtx_official_ir_capture_validation",
    "brk_b_official_ir_capture",
    "brk_b_official_ir_capture_validation",
    "amd_official_ir_capture",
    "amd_official_ir_capture_validation",
    "cat_official_ir_capture",
    "cat_official_ir_capture_validation",
    "cvx_official_ir_capture",
    "cvx_official_ir_capture_validation",
    "ge_official_ir_capture",
    "ge_official_ir_capture_validation",
    "lly_official_ir_capture",
    "lly_official_ir_capture_validation",
    "meta_official_ir_capture",
    "meta_official_ir_capture_validation",
    "ph_official_ir_capture",
    "ph_official_ir_capture_validation",
    "pltr_official_ir_capture",
    "pltr_official_ir_capture_validation",
    "fundamental_ir_reconciliation_packets",
    "fundamental_ir_reconciliation_validation",
    "official_earnings_bridge",
    "official_earnings_bridge_validation",
    "watchlist_promotion_radar",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_window(window: str) -> str:
    return WINDOW_ALIASES.get(window, window)


def rel_path(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def load_dict(path: Path) -> dict[str, Any] | None:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else None


def generated_at(path: Path, data: dict[str, Any] | None) -> str | None:
    if data:
        for key in ("generated_at_utc", "generated_at", "completed_at_utc", "started_at_utc"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if path.exists():
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return None


def status_from_data(path: Path, data: dict[str, Any] | None) -> str:
    if not path.exists():
        return "missing"
    if data is None and path.suffix.lower() == ".json":
        return "unreadable"
    if data:
        raw = str(data.get("status") or data.get("overall_status") or "").strip().lower()
        if raw in {"critical", "failed", "error", "blocked"}:
            return "critical"
        if raw in {"warning", "partial", "usable_with_caution", "completed_with_recovery", "recovering"}:
            return "warning"
    return "ok"


def artifact_record(role: str, template: str, window: str) -> dict[str, Any]:
    rel = template.format(window=window)
    path = WORKSPACE / rel
    data = load_dict(path) if path.suffix.lower() == ".json" else None
    artifact_window = data.get("window") if isinstance(data, dict) else None
    return {
        "role": role,
        "path": rel_path(path),
        "exists": path.exists(),
        "status": status_from_data(path, data),
        "generated_at_utc": generated_at(path, data),
        "artifact_window": artifact_window,
        "window_match": artifact_window in (None, "", window),
    }


def build_index(window: str) -> dict[str, Any]:
    window = normalize_window(window)
    templates = {**COMMON_ARTIFACTS, **WINDOW_ARTIFACTS[window]}
    artifacts = [artifact_record(role, templates[role], window) for role in sorted(templates)]
    artifacts_by_role = {item["role"]: item for item in artifacts}
    role_aliases = {
        role: artifacts_by_role[role]["path"]
        for role in ROLE_ORDER
        if role in artifacts_by_role and artifacts_by_role[role]["exists"]
    }
    missing_required = [role for role in ("run_summary", "run_chain", "daily_review_objects") if role in artifacts_by_role and not artifacts_by_role[role]["exists"]]
    stale_cross_window = [item["role"] for item in artifacts if item["exists"] and not item["window_match"]]
    critical_or_unreadable = [item["role"] for item in artifacts if item["status"] in {"critical", "unreadable"}]
    status = "ok"
    if missing_required or stale_cross_window or critical_or_unreadable:
        status = "warning"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "window": window,
        "status": status,
        "summary": {
            "artifact_count": len(artifacts),
            "existing_artifact_count": sum(1 for item in artifacts if item["exists"]),
            "missing_required_roles": missing_required,
            "cross_window_artifact_roles": stale_cross_window,
            "critical_or_unreadable_roles": critical_or_unreadable,
        },
        "authority": {
            "posture": "review_only_current_window_artifact_index",
            "standing_authority_scope": "main_session_bounded_workspace_canon_portfolio_maintenance",
            "canonical_mutation_allowed": True,
            "canonical_note_mutation_allowed": True,
            "portfolio_mutation_allowed": True,
            "deployment_state_mutation_allowed": True,
            "owner_approval_granted": True,
            "artifact_mutation_allowed_by_this_index": False,
            "trade_execution_allowed": False,
            "paper_trade_submit_cancel_allowed_by_this_index": False,
            "generated_report_is_canonical": False,
        },
        "role_aliases": role_aliases,
        "artifacts": artifacts,
        "notes": [
            "This is a stable index of current-window artifact paths, not a copy of portfolio truth.",
            "Missing optional artifacts can be normal when that window does not produce the role or when an advisory report has not been run.",
        ],
        "rendered_outputs": {"json": rel_path(OUT_JSON)},
    }


def render_md(index: dict[str, Any]) -> str:
    summary = index["summary"]
    lines = ["# Current-Window Artifact Index", ""]
    lines.append(f"- Generated: `{index['generated_at_utc']}`")
    lines.append(f"- Window: `{index['window']}`")
    lines.append(f"- Status: **{index['status']}**")
    lines.append("- Authority: main-session standing canon/portfolio maintenance authority acknowledged; this index itself is review-only and grants no trade or paper-submit authority")
    lines.append(f"- Existing artifacts: {summary['existing_artifact_count']} / {summary['artifact_count']}")
    if summary["missing_required_roles"]:
        lines.append(f"- Missing required roles: {', '.join(summary['missing_required_roles'])}")
    if summary["cross_window_artifact_roles"]:
        lines.append(f"- Cross-window artifact roles: {', '.join(summary['cross_window_artifact_roles'])}")
    if summary["critical_or_unreadable_roles"]:
        lines.append(f"- Critical/unreadable roles: {', '.join(summary['critical_or_unreadable_roles'])}")
    lines.append("")
    lines.append("## Stable role aliases")
    for role, path in index.get("role_aliases", {}).items():
        lines.append(f"- `{role}` → `{path}`")
    lines.append("")
    lines.append("## Artifact table")
    lines.append("| Role | Status | Exists | Window match | Path |")
    lines.append("|---|---|---:|---:|---|")
    for artifact in index["artifacts"]:
        lines.append(
            f"| `{artifact['role']}` | {artifact['status']} | {str(artifact['exists']).lower()} | {str(artifact['window_match']).lower()} | `{artifact['path']}` |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a review-only current-window artifact index/alias map.")
    parser.add_argument("--window", default="post-close", choices=[*WINDOWS, "full"])
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true", help="Also write optional Markdown digest beside the JSON index.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    index = build_index(args.window)
    if args.write:
        atomic_write_json(OUT_JSON, index, indent=2)
        print(f"wrote {OUT_JSON}")
        if args.write_md:
            atomic_write_text(OUT_MD, render_md(index))
            print(f"wrote {OUT_MD}")
    print(
        "current_window_artifact_index: "
        f"window={index['window']} status={index['status']} "
        f"existing={index['summary']['existing_artifact_count']}/{index['summary']['artifact_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
