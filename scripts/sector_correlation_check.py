#!/usr/bin/env python3
"""Build a review-only sector and correlated-sleeve concentration proof artifact.

WF53 v1 is deliberately standalone: it reads existing workspace notes/artifacts and
writes tmp/sector-correlation-check.json. It does not wire consumers or mutate
canonical finance notes.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

WORKSPACE = Path(__file__).resolve().parents[1]

AUTHORITY_FALSE_FLAGS = [
    "canonical_mutation_allowed",
    "portfolio_mutation_allowed",
    "deployment_state_mutation_allowed",
    "watchlist_promotion_allowed",
    "sizing_allocation_recommendation_allowed",
    "trade_execution_allowed",
    "owner_approval_granted",
    "probability_or_modeling_authority",
]

OPTIONAL_FORBIDDEN_TRUE_FLAGS = [
    "model_driven_deployment_allowed",
    "model_training_enabled",
    "capital_action_allowed",
]

SOURCE_PATHS = {
    "portfolio_config": "tmp/portfolio-config.json",
    "deployment_surface": "tmp/deployment-readiness-surface.json",
    "trigger_sheet": "tmp/trigger-sheet.json",
    "band_proposals": "tmp/band-proposals.json",
    "risk_rules": "07. Risk/Risk Rules.md",
    "portfolio_snapshot": "03. Portfolio/Portfolio Snapshot.md",
    "watchlist": "04. Research/Coverage and Watchlist.md",
}


def daily_review_path_for_window(window: str) -> str:
    safe_window = window if window in {"morning", "post-close", "post-earnings", "sunday"} else "post-close"
    return f"tmp/daily-review-objects-{safe_window}.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return {"_json_error": f"Could not parse JSON: {path}"}


def source_time(doc: dict[str, Any] | None) -> str | None:
    if not isinstance(doc, dict):
        return None
    for key in ("generated_at_utc", "generated_at", "file_mtime_utc"):
        value = doc.get(key)
        if isinstance(value, str):
            return value
    return None


def parse_risk_rules(text: str | None, config: dict[str, Any] | None) -> tuple[dict[str, Any], list[str]]:
    issues: list[str] = []
    result: dict[str, Any] = {
        "max_single_sector_pct": None,
        "sector_warning_within_pct_of_cap": 5,
        "normal_single_position_max_pct": None,
        "speculative_sleeve_max_pct_without_exception": None,
    }

    if text:
        sector = re.search(r"Max single sector:\s*(\d+(?:\.\d+)?)%", text, re.IGNORECASE)
        normal = re.search(r"Normal max single position:\s*(\d+(?:\.\d+)?)%", text, re.IGNORECASE)
        speculative = re.search(r"exceed\s+(\d+(?:\.\d+)?)% total in the speculative sleeve", text, re.IGNORECASE)
        if sector:
            result["max_single_sector_pct"] = number(sector.group(1))
        if normal:
            result["normal_single_position_max_pct"] = number(normal.group(1))
        if speculative:
            result["speculative_sleeve_max_pct_without_exception"] = number(speculative.group(1))
    else:
        issues.append("Risk Rules note missing; using config thresholds if available.")

    thresholds = (config or {}).get("risk_thresholds", {}) if isinstance(config, dict) else {}
    result["max_single_sector_pct"] = result["max_single_sector_pct"] or thresholds.get("max_sector_pct")
    result["normal_single_position_max_pct"] = result["normal_single_position_max_pct"] or thresholds.get(
        "max_single_position_normal"
    )
    if result["speculative_sleeve_max_pct_without_exception"] is None:
        result["speculative_sleeve_max_pct_without_exception"] = 10

    for key in ("max_single_sector_pct", "normal_single_position_max_pct"):
        if result[key] is None:
            issues.append(f"Could not parse {key} from Risk Rules or portfolio config.")

    return result, issues


def number(value: Any) -> int | float:
    n = float(value)
    return int(n) if n.is_integer() else n


def normalize_sector(sector: str | None) -> str:
    if not sector:
        return "Unknown"
    value = sector.strip()
    aliases = {
        "Tech": "Technology",
        "Tech / AI Infrastructure": "Technology",
        "Tech / Defense": "Technology",
    }
    return aliases.get(value, value)


def portfolio_rows_from_config(config: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(config, dict):
        return []
    portfolio = config.get("portfolio", {})
    rows: list[dict[str, Any]] = []
    for sleeve in ("core", "tactical", "speculative"):
        for item in portfolio.get(sleeve, []) or []:
            ticker = item.get("ticker")
            weight = item.get("weight")
            sector = item.get("sector")
            if ticker and isinstance(weight, (int, float)):
                rows.append(
                    {
                        "ticker": ticker,
                        "weight": float(weight),
                        "sector": normalize_sector(sector),
                        "source_sector": sector or "Unknown",
                        "portfolio_sleeve": sleeve,
                    }
                )
    return rows


def parse_snapshot_sector_table(text: str | None) -> dict[str, float]:
    if not text:
        return {}
    table: dict[str, float] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|") or "---" in line or "Sector" in line:
            continue
        cells = [c.strip().replace("**", "") for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        sector = normalize_sector(cells[0])
        match = re.search(r"(\d+(?:\.\d+)?)%", cells[2])
        if match:
            table[sector] = float(match.group(1))
    return table


def sector_totals(rows: Iterable[dict[str, Any]]) -> dict[str, float]:
    totals: dict[str, float] = defaultdict(float)
    for row in rows:
        totals[row["sector"]] += float(row["weight"])
    return dict(totals)


def sector_status(weight: float, cap: float | int | None, warning_within: float | int) -> tuple[str, float | None]:
    if cap is None:
        return "unknown", None
    distance = round(float(cap) - float(weight), 2)
    if distance < 0:
        return "over_cap", distance
    if distance == 0:
        return "at_cap", distance
    if distance <= float(warning_within):
        return "near_cap", distance
    return "within_limit", distance


def build_sector_entries(rows: list[dict[str, Any]], policy: dict[str, Any]) -> list[dict[str, Any]]:
    cap = policy.get("max_single_sector_pct")
    warning = policy.get("sector_warning_within_pct_of_cap", 5)
    by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_sector[row["sector"]].append(row)

    entries: list[dict[str, Any]] = []
    for sector, items in sorted(by_sector.items()):
        total = round(sum(float(item["weight"]) for item in items), 2)
        status, distance = sector_status(total, cap, warning)
        entries.append(
            {
                "sector": sector,
                "tickers": [item["ticker"] for item in items],
                "draft_weight_pct": number(total),
                "risk_cap_pct": cap,
                "distance_to_cap_pct": distance,
                "status": status,
                "source": "portfolio-config.json; cross-checked against Portfolio Snapshot when parseable",
            }
        )
    return entries


def correlated_sleeves(rows: list[dict[str, Any]], sector_entries: list[dict[str, Any]], cap: int | float | None) -> list[dict[str, Any]]:
    weights = {row["ticker"]: float(row["weight"]) for row in rows}
    tech_ai_tickers = [ticker for ticker in ("MSFT", "GOOG", "NVDA", "ETN") if ticker in weights]
    total = round(sum(weights[t] for t in tech_ai_tickers), 2)
    direct_tech = next((s for s in sector_entries if s["sector"] == "Technology"), None)
    status = "warning" if cap is not None and total >= float(cap) else "within_limit"
    reason = (
        f"Direct Technology is {direct_tech['status'].replace('_', ' ')} at "
        f"{direct_tech['draft_weight_pct']}% vs {cap}% cap; AI-power correlated sleeve is {number(total)}% including ETN."
        if direct_tech
        else f"AI-power correlated sleeve is {number(total)}% including ETN."
    )
    return [
        {
            "sleeve": "Tech + AI-power",
            "tickers": tech_ai_tickers,
            "draft_weight_pct": number(total),
            "included_non_sector_tickers": [t for t in tech_ai_tickers if t == "ETN"],
            "status": status,
            "reason": reason,
            "review_only": True,
        }
    ]


def tracked_context(config: dict[str, Any] | None, sectors: dict[str, float]) -> list[dict[str, Any]]:
    universe = (config or {}).get("tracked_universe", {}) if isinstance(config, dict) else {}
    preferred = ["LLY", "CAT", "VRT", "AMZN", "AMD", "PLTR"]
    rows: list[dict[str, Any]] = []
    for ticker in preferred:
        item = universe.get(ticker)
        if not isinstance(item, dict):
            continue
        sector = normalize_sector(item.get("sector"))
        role = item.get("portfolio_role", "unknown")
        lane = item.get("coverage_lane", "unknown")
        state = item.get("workflow_state", "unknown")
        candidate_role = "diversification_watch" if sector not in sectors else "correlated_or_existing_sector_watch"
        rows.append(
            {
                "ticker": ticker,
                "sector": sector,
                "coverage_lane": lane,
                "portfolio_role": role,
                "workflow_state": state,
                "candidate_role": candidate_role,
                "promotion_impact": promotion_impact_phrase(sector, sectors),
                "eligible_for_promotion": False,
                "blockers": ["watch-lane or secondary review only", "explicit promotion and sizing review required"],
                "authority": authority_false_block(),
            }
        )
    return rows


def promotion_impact_phrase(sector: str, sectors: dict[str, float]) -> str:
    if sector not in sectors:
        return "would add a currently absent sector but remains owner-gated and review-only"
    return "would add to an already represented sector and remains owner-gated and review-only"


def promotion_checks(config: dict[str, Any] | None, sectors: dict[str, float], cap: int | float | None) -> list[dict[str, Any]]:
    universe = (config or {}).get("tracked_universe", {}) if isinstance(config, dict) else {}
    rows = portfolio_rows_from_config(config)
    weights = {row["ticker"]: float(row["weight"]) for row in rows}
    checks: list[dict[str, Any]] = []
    for ticker in ("GS", "LLY", "CAT", "VRT"):
        item = universe.get(ticker, {}) if isinstance(universe, dict) else {}
        sector = normalize_sector(item.get("sector"))
        model_weight = weights.get(ticker, 0.0)
        current = sectors.get(sector, 0.0)
        pro_forma = current if model_weight else current
        status, _ = sector_status(pro_forma, cap, 5)
        warnings: list[str] = []
        if ticker == "GS":
            warnings.append("secondary to JPM inside Financials")
        if sector == "Technology":
            warnings.append("Technology/AI correlation requires cap discipline")
        checks.append(
            {
                "ticker": ticker,
                "candidate_sector": sector,
                "current_sector_weight_pct": number(round(current, 2)),
                "candidate_model_weight_pct": number(round(model_weight, 2)),
                "pro_forma_sector_weight_pct": number(round(pro_forma, 2)),
                "cap_status_after": status,
                "correlated_sleeve_warnings": warnings,
                "review_only_verdict": "sector_context_available_owner_gated_not_deployable_authority",
                "eligible_for_promotion": False,
                "authority": authority_false_block(),
            }
        )
    return checks


def diversification_candidates(context: list[dict[str, Any]], sectors: dict[str, float]) -> list[dict[str, Any]]:
    candidates = []
    for item in context:
        if item["sector"] not in sectors and item["ticker"] in {"LLY", "CAT"}:
            candidates.append(
                {
                    "ticker": item["ticker"],
                    "sector": item["sector"],
                    "reason": f"{item['sector']} is absent from the model portfolio and may be useful for owner review diversification context.",
                    "status": "watch_review_only",
                    "eligible_for_promotion": False,
                }
            )
    return candidates


def authority_false_block() -> dict[str, bool]:
    return {flag: False for flag in AUTHORITY_FALSE_FLAGS}


def inspect_source_authority(daily: dict[str, Any] | None, deployment_surface: dict[str, Any] | None) -> tuple[list[str], list[str]]:
    issues: list[str] = []
    blockers: list[str] = []
    sources = [("daily_review_objects", daily), ("deployment_surface.system", (deployment_surface or {}).get("system", {}))]
    for label, doc in sources:
        if not isinstance(doc, dict):
            issues.append(f"{label} missing; authority could not be cross-checked.")
            continue
        for flag in AUTHORITY_FALSE_FLAGS + OPTIONAL_FORBIDDEN_TRUE_FLAGS:
            if doc.get(flag) is True:
                blockers.append(f"Forbidden authority flag true in {label}: {flag}")
    return issues, blockers


def build_source_quality(
    issues: list[str], blockers: list[str], artifacts: dict[str, dict[str, Any] | None]
) -> dict[str, Any]:
    classifications: list[str] = []
    for key in ("daily_review_objects", "band_proposals"):
        doc = artifacts.get(key)
        if not isinstance(doc, dict):
            continue
        if key == "daily_review_objects":
            freshness = doc.get("source_freshness", {})
            if isinstance(freshness, dict):
                classifications.append(str(freshness.get("overall_classification", "")))
                if freshness.get("trust_level") == "review_required":
                    issues.append("daily review source freshness requires review; artifact remains review-only.")
        if key == "band_proposals" and doc.get("status") == "needs_review":
            classifications.append("partial")
            issues.append("band proposals status=needs_review; band context is review debt only.")
    if blockers:
        classification = "contradictory" if any("contradict" in b.lower() for b in blockers) else "missing"
        trust = "blocked"
    elif any(c in {"partial", "stale", "missing"} for c in classifications) or issues:
        classification = "partial"
        trust = "review_required"
    else:
        classification = "fresh"
        trust = "clean"
    return {
        "overall_classification": classification,
        "trust_level": trust,
        "stop_line": bool(blockers),
        "issues": issues,
        "blockers": blockers,
    }


def source_generated_at(artifacts: dict[str, dict[str, Any] | None]) -> dict[str, str | None]:
    return {
        "portfolio_config": source_time(artifacts.get("portfolio_config")),
        "deployment_surface": source_time(artifacts.get("deployment_surface")),
        "trigger_sheet": source_time(artifacts.get("trigger_sheet")),
        "band_proposals": source_time(artifacts.get("band_proposals")),
        "daily_review_objects": source_time(artifacts.get("daily_review_objects")),
    }


def build_artifact(window: str) -> dict[str, Any]:
    source_paths = dict(SOURCE_PATHS)
    source_paths["daily_review_objects"] = daily_review_path_for_window(window)
    paths = {key: WORKSPACE / rel for key, rel in source_paths.items()}
    artifacts = {key: load_json(path) for key, path in paths.items() if path.suffix == ".json"}
    risk_text = read_text(paths["risk_rules"])
    snapshot_text = read_text(paths["portfolio_snapshot"])

    config = artifacts.get("portfolio_config")
    issues: list[str] = []
    blockers: list[str] = []

    policy, policy_issues = parse_risk_rules(risk_text, config)
    issues.extend(policy_issues)
    if policy.get("max_single_sector_pct") is None:
        blockers.append("Cannot parse Risk Rules max single sector cap.")

    rows = portfolio_rows_from_config(config)
    if not rows:
        blockers.append("Cannot parse model weights from portfolio-config.json.")

    sectors = sector_totals(rows)
    snapshot_sectors = parse_snapshot_sector_table(snapshot_text)
    if snapshot_text and not snapshot_sectors:
        issues.append("Portfolio Snapshot sector table could not be parsed; using portfolio-config weights.")
    for sector, snapshot_weight in snapshot_sectors.items():
        if sector == "Cash":
            continue
        config_weight = sectors.get(sector)
        if config_weight is not None and abs(config_weight - snapshot_weight) > 1.0:
            blockers.append(
                f"Portfolio Snapshot and portfolio-config sector totals contradict for {sector}: "
                f"snapshot={snapshot_weight} config={config_weight}."
            )

    auth_issues, auth_blockers = inspect_source_authority(
        artifacts.get("daily_review_objects"), artifacts.get("deployment_surface")
    )
    issues.extend(auth_issues)
    blockers.extend(auth_blockers)

    source_quality = build_source_quality(issues, blockers, artifacts)
    status = "blocked" if blockers else "degraded" if source_quality["trust_level"] == "review_required" else "ok"

    sector_entries = build_sector_entries(rows, policy) if rows else []
    sleeve_entries = correlated_sleeves(rows, sector_entries, policy.get("max_single_sector_pct")) if rows else []
    context = tracked_context(config, sectors)

    market_data_as_of = None
    trigger = artifacts.get("trigger_sheet")
    if isinstance(trigger, dict):
        market_data_as_of = trigger.get("last_trading_day")
    daily = artifacts.get("daily_review_objects")
    if not market_data_as_of and isinstance(daily, dict):
        market_data_as_of = daily.get("market_data_as_of")

    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "window": window,
        "status": status,
        "consumer_posture": "review_only",
        "owner_approval_required_for_capital": True,
        "market_data_as_of": market_data_as_of,
        "source_generated_at_utc": source_generated_at(artifacts),
        "authority": authority_false_block(),
        "risk_policy": policy,
        "source_quality": source_quality,
        "portfolio_exposure": {
            "model_weight_total_pct": number(round(sum(row["weight"] for row in rows), 2)) if rows else 0,
            "cash_pct": (config or {}).get("portfolio", {}).get("cash") if isinstance(config, dict) else None,
            "sectors": sector_entries,
            "correlated_sleeves": sleeve_entries,
        },
        "tracked_universe_context": context,
        "promotion_impact_checks": promotion_checks(config, sectors, policy.get("max_single_sector_pct")),
        "diversification_candidates": diversification_candidates(context, sectors),
        "current_limits": [
            "This artifact is concentration proof only; it is not a promotion, sizing, or trade system.",
            "All portfolio, deployment, watchlist, and owner-approval authority remains false and owner-gated.",
        ],
        "errors": blockers,
    }


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build review-only sector/correlation concentration proof JSON.")
    parser.add_argument("--window", default="post-close", help="Review window label to stamp into the artifact.")
    parser.add_argument("--output", default="tmp/sector-correlation-check.json", help="Output JSON path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    artifact = build_artifact(args.window)
    output = Path(args.output)
    if not output.is_absolute():
        output = WORKSPACE / output
    write_json(output, artifact)
    print(f"wrote {output} status={artifact['status']}")
    return 0 if artifact["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
