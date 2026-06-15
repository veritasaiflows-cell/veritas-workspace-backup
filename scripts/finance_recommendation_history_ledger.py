#!/usr/bin/env python3
"""Build a review-only historical finance recommendation ledger.

This normalizes recommendation and tracking rows from WF55/WF74/WF78/WF85
surfaces into one feature-ready history table. It is for later lookback and
calibration review only; it does not approve, rank, trade, or mutate canon.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"

DEFAULT_JSON = TMP / "finance-recommendation-history-ledger.json"
DEFAULT_MD = TMP / "finance-recommendation-history-ledger.md"
WF55_CURRENT = TMP / "recommendation-outcome-ledger-current.json"
WF74_CORRECTNESS = TMP / "finance-recommendation-correctness-ledger-current.json"
WF78_HUMAN_REVIEW = TMP / "wf78-deployment-readiness-human-review.json"
WF85_DECISION_CARDS = TMP / "trade-grade-decision-cards.json"
WF85_DECISION_FACTORY = TMP / "finance-decision-factory.json"
WF77_PRICE_STATE = ROOT / "data" / "market" / "price-snapshots" / "wf77-price-state-current.json"

SCHEMA = "veritas.finance_recommendation_history_ledger.v1"
ROW_SCHEMA = "veritas.finance_recommendation_history_ledger.row.v1"

AUTHORITY_FLAGS = {
    "review_only": True,
    "historical_analytics_only": True,
    "recommendation_approval_surface": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_or_live_execution_allowed": False,
    "paper_submit_allowed": False,
    "paper_cancel_allowed": False,
    "paper_sell_allowed": False,
    "live_endpoint_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "portfolio_or_canon_mutation_allowed": False,
    "cash_sizing_or_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
    "model_training_enabled": False,
    "predictive_performance_claim_allowed": False,
    "model_ranked_deployment_allowed": False,
}

DANGEROUS_TRUE_KEYS = {
    "capital_action_allowed",
    "capital_deployment_approved",
    "trade_or_execution_approved",
    "trade_execution_allowed",
    "trade_or_account_action_allowed",
    "paper_or_live_execution_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed",
    "paper_submit_allowed",
    "paper_cancel_allowed",
    "paper_sell_allowed",
    "paper_trade_allowed",
    "live_trade_allowed",
    "live_endpoint_allowed",
    "live_brokerage_or_account_action_allowed",
    "brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "portfolio_mutation_allowed",
    "canonical_mutation_allowed",
    "canon_or_portfolio_mutation_allowed",
    "portfolio_or_canon_mutation_allowed",
    "cash_sizing_or_risk_rule_mutation_allowed",
    "owner_approval_granted",
    "owner_approval_inferred",
    "owner_approval_inference_allowed",
    "model_training_enabled",
    "model_ranked_deployment_allowed",
    "model_driven_deployment_allowed",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def numeric(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return round((numerator / denominator) * 100.0, 4)


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:18]


def abs_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def load_json_checked(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    if not path.exists():
        return {}, {"path": rel(path), "exists": False, "status": "missing", "parse_error": None}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, {"path": rel(path), "exists": True, "status": "parse_error", "parse_error": str(exc)}
    except OSError as exc:
        return {}, {"path": rel(path), "exists": True, "status": "read_error", "parse_error": str(exc)}
    if not isinstance(value, dict):
        return {}, {"path": rel(path), "exists": True, "status": "invalid_shape", "parse_error": "top-level JSON is not an object"}
    return value, {"path": rel(path), "exists": True, "status": "ok", "parse_error": None}


def source_artifact(path: Path, payload: dict[str, Any], meta: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": rel(path),
        "exists": meta.get("exists"),
        "status": meta.get("status"),
        "generated_at_utc": payload.get("generated_at_utc") or payload.get("created_at_utc"),
        "schema": payload.get("schema") or payload.get("schema_version"),
    }


def compact_text(value: Any, limit: int = 360) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    return text[:limit] if text else None


def checkpoint_counts(scorecard: dict[str, Any]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for checkpoint in as_list(scorecard.get("checkpoints")):
        status = str(as_dict(checkpoint).get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return dict(sorted(counts.items()))


def first_present(*values: Any) -> Any:
    for value in values:
        if value not in (None, ""):
            return value
    return None


def price_index(wf77: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in as_list(wf77.get("rows")):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        price_state = as_dict(row.get("price_state"))
        card = as_dict(row.get("card_price_context"))
        out[ticker] = {
            "latest_price": numeric(price_state.get("latest_close") or card.get("card_latest_known_price")),
            "market_date": price_state.get("data_date"),
            "price_source": price_state.get("source") or card.get("card_path"),
            "band_status": card.get("fresh_price_band_status") or card.get("card_band_status"),
            "band_low": numeric(card.get("entry_band_low")),
            "band_high": numeric(card.get("entry_band_high")),
            "stop": numeric(card.get("stop_or_invalidation")),
            "fresh_quote_required": card.get("card_fresh_quote_required"),
            "tier": row.get("tier"),
            "coverage_lane": row.get("coverage_lane"),
            "monitoring_role": row.get("monitoring_role"),
            "ma_posture": price_state.get("ma_posture"),
        }
    return out


def infer_band_status(price: float | None, low: float | None, high: float | None, stop: float | None, current: Any = None) -> str | None:
    if current not in (None, ""):
        return str(current)
    if price is None:
        return None
    if stop is not None and price < stop:
        return "BELOW_STOP"
    if low is not None and price < low:
        return "BELOW_BAND"
    if high is not None and price > high:
        return "ABOVE_BAND"
    if low is not None and high is not None:
        return "IN_BAND"
    return None


def market_context(
    ticker: str,
    prices: dict[str, dict[str, Any]],
    *,
    price: Any = None,
    band_status: Any = None,
    band_low: Any = None,
    band_high: Any = None,
    stop: Any = None,
    price_source: Any = None,
    price_as_of: Any = None,
) -> dict[str, Any]:
    supplement = prices.get(ticker.upper(), {})
    resolved_price = first_present(numeric(price), supplement.get("latest_price"))
    resolved_low = first_present(numeric(band_low), supplement.get("band_low"))
    resolved_high = first_present(numeric(band_high), supplement.get("band_high"))
    resolved_stop = first_present(numeric(stop), supplement.get("stop"))
    resolved_band = infer_band_status(resolved_price, resolved_low, resolved_high, resolved_stop, first_present(band_status, supplement.get("band_status")))
    band_width = None
    if resolved_low is not None and resolved_high is not None:
        band_width = resolved_high - resolved_low
    return {
        "price": resolved_price,
        "price_as_of": first_present(price_as_of, supplement.get("market_date")),
        "price_source": first_present(price_source, supplement.get("price_source")),
        "band_status": resolved_band,
        "band_low": resolved_low,
        "band_high": resolved_high,
        "stop_or_invalidation": resolved_stop,
        "wf77_enriched": bool(supplement),
        "price_band_position_pct": pct((resolved_price - resolved_low) if resolved_price is not None and resolved_low is not None else None, band_width),
        "price_vs_band_low_pct": pct((resolved_price - resolved_low) if resolved_price is not None and resolved_low is not None else None, resolved_low),
        "price_vs_band_high_pct": pct((resolved_price - resolved_high) if resolved_price is not None and resolved_high is not None else None, resolved_high),
        "price_vs_stop_pct": pct((resolved_price - resolved_stop) if resolved_price is not None and resolved_stop is not None else None, resolved_stop),
    }


def base_features(market: dict[str, Any], extra: dict[str, Any] | None = None) -> dict[str, Any]:
    status = str(market.get("band_status") or "")
    features = {
        "in_entry_band": status == "IN_BAND",
        "below_band": status == "BELOW_BAND",
        "below_stop": status == "BELOW_STOP",
        "above_band": status in {"ABOVE_BAND", "ABOVE_BAND_WAIT"},
        "no_chase": status in {"ABOVE_BAND", "ABOVE_BAND_WAIT"},
        "has_price": market.get("price") is not None,
        "has_entry_band": market.get("band_low") is not None and market.get("band_high") is not None,
        "has_stop": market.get("stop_or_invalidation") is not None,
        "price_band_position_pct": market.get("price_band_position_pct"),
        "price_vs_band_low_pct": market.get("price_vs_band_low_pct"),
        "price_vs_band_high_pct": market.get("price_vs_band_high_pct"),
        "price_vs_stop_pct": market.get("price_vs_stop_pct"),
    }
    features.update(extra or {})
    return features


def normalized_authority(source: dict[str, Any] | None = None) -> dict[str, Any]:
    flags = dict(AUTHORITY_FLAGS)
    source = source or {}
    flags["source_review_only"] = first_present(source.get("review_only"), as_dict(source.get("authority_boundary")).get("review_only"), as_dict(source.get("authority_flags")).get("review_only"))
    flags["source_owner_approval_inferred"] = first_present(source.get("owner_approval_inferred"), as_dict(source.get("authority_boundary")).get("owner_approval_inferred"))
    flags["source_capital_deployment_approved"] = first_present(source.get("capital_deployment_approved"), as_dict(source.get("authority_boundary")).get("capital_deployment_approved"))
    flags["source_paper_or_live_execution_allowed"] = first_present(source.get("paper_or_live_execution_allowed"), as_dict(source.get("authority_boundary")).get("paper_or_live_execution_allowed"))
    return flags


def make_row(
    *,
    source_family: str,
    source_path: Path,
    source_row_index: int,
    source_generated_at_utc: Any,
    ticker: str,
    recommendation: dict[str, Any],
    market: dict[str, Any],
    features: dict[str, Any],
    authority_source: dict[str, Any] | None = None,
    source_artifacts: list[Any] | None = None,
) -> dict[str, Any]:
    rec_id = str(recommendation.get("recommendation_id") or "")
    observed = first_present(recommendation.get("observed_at_utc"), recommendation.get("generated_at_utc"), source_generated_at_utc)
    row_id = "finhist_" + stable_id(source_family, rel(source_path), source_row_index, ticker.upper(), rec_id, observed)
    return {
        "schema": ROW_SCHEMA,
        "row_id": row_id,
        "source_family": source_family,
        "source_path": rel(source_path),
        "source_row_index": source_row_index,
        "source_generated_at_utc": source_generated_at_utc,
        "observed_at_utc": observed,
        "ticker": ticker.upper(),
        "recommendation": recommendation,
        "market_context": market,
        "feature_fields": features,
        "authority_flags": normalized_authority(authority_source),
        "source_authority_drift_paths": authority_true_paths(authority_source or {}),
        "source_artifacts": source_artifacts or [rel(source_path)],
    }


def rows_from_wf55(payload: dict[str, Any], path: Path, prices: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated = payload.get("generated_at_utc")
    for idx, row in enumerate(as_list(payload.get("tracked_rows"))):
        if not isinstance(row, dict):
            continue
        source_payload = as_dict(row.get("payload"))
        ticker = str(row.get("ticker") or source_payload.get("ticker") or "").upper()
        if not ticker:
            continue
        scorecard = as_dict(row.get("forward_scorecard"))
        known = as_dict(scorecard.get("known_at_time"))
        market = market_context(
            ticker,
            prices,
            price=first_present(source_payload.get("current_price"), source_payload.get("anchor_price"), known.get("anchor_price")),
            band_status=first_present(source_payload.get("entry_band_status"), known.get("band_status")),
            band_low=first_present(source_payload.get("entry_band_low"), known.get("entry_band_low")),
            band_high=first_present(source_payload.get("entry_band_high"), known.get("entry_band_high")),
            stop=first_present(source_payload.get("stop_or_invalidation"), known.get("stop_or_invalidation")),
            price_source=source_payload.get("source_artifact_path"),
            price_as_of=row.get("observed_at_utc"),
        )
        features = base_features(market, {
            "event_family": row.get("event_family"),
            "event_subtype": row.get("event_subtype"),
            "decision_status": source_payload.get("decision_status"),
            "current_status": source_payload.get("current_status"),
            "follow_up_required": source_payload.get("follow_up_required"),
            "quote_freshness_status": first_present(source_payload.get("quote_freshness_status"), known.get("quote_freshness_status")),
            "forward_scorecard_status": scorecard.get("status"),
            "checkpoint_status_counts": checkpoint_counts(scorecard),
            "outcome_grade_assigned": scorecard.get("outcome_grade_assigned"),
        })
        recommendation = {
            "recommendation_id": source_payload.get("recommendation_id") or row.get("object_id") or row.get("ledger_event_id"),
            "recommendation_source": source_payload.get("recommendation_source") or source_payload.get("source_artifact_path"),
            "recommendation_type": source_payload.get("recommendation_type"),
            "recommendation_posture": source_payload.get("current_status"),
            "current_status": source_payload.get("current_status"),
            "decision_status": source_payload.get("decision_status"),
            "thesis_or_summary": compact_text(first_present(source_payload.get("base_case"), source_payload.get("event_summary"))),
            "bear_case": compact_text(source_payload.get("bear_case")),
            "observed_at_utc": row.get("observed_at_utc"),
        }
        artifacts = [art.get("path") for art in as_list(as_dict(row.get("provenance")).get("source_artifacts")) if isinstance(art, dict) and art.get("path")]
        rows.append(make_row(
            source_family="WF55_RECOMMENDATION_TRACKING",
            source_path=path,
            source_row_index=idx,
            source_generated_at_utc=generated,
            ticker=ticker,
            recommendation=recommendation,
            market=market,
            features=features,
            authority_source=row,
            source_artifacts=artifacts or None,
        ))
    return rows


def rows_from_wf74(payload: dict[str, Any], path: Path, prices: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated = payload.get("generated_at_utc")
    for idx, row in enumerate(as_list(payload.get("rows"))):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        market = market_context(
            ticker,
            prices,
            price=row.get("close"),
            band_status=row.get("entry_band_status"),
            band_low=row.get("band_low"),
            band_high=row.get("band_high"),
            stop=row.get("stop_or_invalidation"),
            price_source=row.get("source_artifact"),
            price_as_of=row.get("generated_at_utc"),
        )
        freshness = as_dict(row.get("source_freshness"))
        features = base_features(market, {
            "process_correctness_status": row.get("process_correctness_status"),
            "outcome_quality_status": row.get("outcome_quality_status"),
            "daily_review_state": row.get("daily_review_state"),
            "source_freshness_status": freshness.get("overall_classification"),
            "source_trust_level": freshness.get("trust_level"),
            "owner_review_required": freshness.get("owner_review_required"),
            "failed_check_count": len(as_list(row.get("failed_checks"))),
            "wf55_exact_recommendation_id_present": row.get("wf55_exact_recommendation_id_present"),
        })
        recommendation = {
            "recommendation_id": row.get("recommendation_id"),
            "recommendation_source": row.get("source_artifact"),
            "recommendation_type": "wf74_process_correctness_row",
            "recommendation_posture": row.get("recommendation_posture"),
            "current_status": row.get("daily_review_state"),
            "decision_status": row.get("status"),
            "generated_at_utc": row.get("generated_at_utc"),
        }
        rows.append(make_row(
            source_family="WF74_RECOMMENDATION_CORRECTNESS",
            source_path=path,
            source_row_index=idx,
            source_generated_at_utc=generated,
            ticker=ticker,
            recommendation=recommendation,
            market=market,
            features=features,
            authority_source=row,
        ))
    return rows


def rows_from_wf78(payload: dict[str, Any], path: Path, prices: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated = payload.get("generated_at_utc")
    for idx, row in enumerate(as_list(payload.get("rows"))):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        market = market_context(
            ticker,
            prices,
            price=row.get("latest_known_price"),
            band_status=row.get("band_status"),
            band_low=row.get("entry_band_low"),
            band_high=row.get("entry_band_high"),
            stop=row.get("stop_or_invalidation"),
            price_source=row.get("owner_source_path"),
            price_as_of=row.get("owner_source_timestamp"),
        )
        features = base_features(market, {
            "auto_tier": row.get("auto_tier"),
            "route_state": row.get("route_state"),
            "priority_score": row.get("priority_score"),
            "review_status": row.get("review_status"),
            "band_context_group": row.get("band_context_group"),
            "no_chase": row.get("no_chase"),
            "human_review_posture": row.get("human_review_posture"),
            "deployment_surface_existing_row_present": row.get("deployment_surface_existing_row_present"),
            "residual_blocker_present": bool(row.get("residual_blocker")),
        })
        recommendation = {
            "recommendation_id": row.get("packet_id") or f"wf78:{ticker}:{idx}",
            "recommendation_source": row.get("owner_source_path"),
            "recommendation_type": "wf78_deployment_readiness_review",
            "recommendation_posture": row.get("proposed_non_executing_review_action"),
            "current_status": row.get("review_status"),
            "decision_status": row.get("human_review_posture"),
            "thesis_or_summary": compact_text(row.get("readiness_impact")),
        }
        rows.append(make_row(
            source_family="WF78_DEPLOYMENT_READINESS_REVIEW",
            source_path=path,
            source_row_index=idx,
            source_generated_at_utc=generated,
            ticker=ticker,
            recommendation=recommendation,
            market=market,
            features=features,
            authority_source=row,
        ))
    return rows


def rows_from_wf85_cards(payload: dict[str, Any], path: Path, prices: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated = payload.get("generated_at_utc")
    for idx, row in enumerate(as_list(payload.get("cards"))):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        price = as_dict(row.get("current_price"))
        band = as_dict(row.get("entry_band"))
        stop = as_dict(row.get("stop_or_invalidation"))
        freshness = as_dict(row.get("source_freshness"))
        market = market_context(
            ticker,
            prices,
            price=price.get("latest_known_price"),
            band_status=band.get("band_status"),
            band_low=band.get("low"),
            band_high=band.get("high"),
            stop=stop.get("level"),
            price_source=price.get("source"),
            price_as_of=first_present(price.get("quote_time_utc"), price.get("market_date")),
        )
        features = base_features(market, {
            "auto_tier": row.get("auto_tier"),
            "auto_state": row.get("auto_state"),
            "primary_state": row.get("primary_state"),
            "queue_state": row.get("queue_state"),
            "decision_state": row.get("decision_state"),
            "owner_action_required": row.get("owner_action_required"),
            "source_freshness_status": freshness.get("status"),
            "quote_freshness_status": freshness.get("quote_freshness_status"),
            "fresh_quote_required": freshness.get("fresh_quote_required"),
            "evidence_family_count": len(as_list(row.get("evidence_family_status"))),
        })
        thesis = as_dict(row.get("thesis_snapshot"))
        recommendation = {
            "recommendation_id": f"wf85-card:{ticker}:{row.get('decision_state') or row.get('queue_state')}",
            "recommendation_source": rel(path),
            "recommendation_type": "wf85_trade_grade_decision_card",
            "recommendation_posture": row.get("decision_state"),
            "current_status": row.get("queue_state"),
            "decision_status": row.get("decision_state"),
            "thesis_or_summary": compact_text(thesis.get("summary")),
            "base_case": compact_text(row.get("base_case")),
            "bear_case": compact_text(row.get("bear_case")),
            "generated_at_utc": generated,
        }
        rows.append(make_row(
            source_family="WF85_TRADE_GRADE_DECISION_CARD",
            source_path=path,
            source_row_index=idx,
            source_generated_at_utc=generated,
            ticker=ticker,
            recommendation=recommendation,
            market=market,
            features=features,
            authority_source=row,
            source_artifacts=[item.get("path") for item in as_list(row.get("source_drillback")) if isinstance(item, dict) and item.get("path")] or None,
        ))
    return rows


def rows_from_wf85_factory(payload: dict[str, Any], path: Path, prices: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated = payload.get("generated_at_utc")
    for idx, row in enumerate(as_list(payload.get("decision_ledger"))):
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").upper()
        if not ticker:
            continue
        quote = as_dict(row.get("quote"))
        market = market_context(
            ticker,
            prices,
            price=first_present(row.get("current_price"), quote.get("current_price")),
            band_status=row.get("current_band_status"),
            band_low=row.get("entry_band_low"),
            band_high=row.get("entry_band_high"),
            stop=row.get("stop_or_invalidation"),
            price_source=quote.get("source"),
            price_as_of=first_present(quote.get("quote_time_utc"), quote.get("market_date")),
        )
        features = base_features(market, {
            "auto_tier": row.get("auto_tier"),
            "queue_state": row.get("queue_state"),
            "gate_verdict": row.get("gate_verdict"),
            "gate_veto_count": len(as_list(row.get("gate_vetoes"))),
            "card_preparable": row.get("card_preparable"),
            "wf67_request_generation_status": row.get("wf67_request_generation_status"),
            "disposition": row.get("disposition"),
            "blocked_reason_present": bool(row.get("blocked_reason")),
            "quote_freshness_status": row.get("quote_freshness_status"),
        })
        recommendation = {
            "recommendation_id": f"wf85-decision-factory:{ticker}:{row.get('disposition') or idx}",
            "recommendation_source": rel(path),
            "recommendation_type": "wf85_finance_decision_factory_row",
            "recommendation_posture": row.get("disposition"),
            "current_status": row.get("queue_state"),
            "decision_status": row.get("gate_verdict"),
            "thesis_or_summary": compact_text(row.get("blocked_reason")),
            "generated_at_utc": generated,
        }
        rows.append(make_row(
            source_family="WF85_FINANCE_DECISION_FACTORY",
            source_path=path,
            source_row_index=idx,
            source_generated_at_utc=generated,
            ticker=ticker,
            recommendation=recommendation,
            market=market,
            features=features,
            authority_source=row,
            source_artifacts=[row.get("owner_card_path"), row.get("wf67_request_path")],
        ))
    return rows


def load_inputs(paths: dict[str, Path]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    payloads: dict[str, dict[str, Any]] = {}
    metas: list[dict[str, Any]] = []
    for key, path in paths.items():
        payload, meta = load_json_checked(path)
        payloads[key] = payload
        metas.append({"key": key, **meta})
    return payloads, metas


def build_ledger(paths: dict[str, Path] | None = None, now: str | None = None) -> dict[str, Any]:
    paths = paths or default_paths()
    payloads, metas = load_inputs(paths)
    prices = price_index(payloads["wf77_price_state"])
    rows: list[dict[str, Any]] = []
    rows.extend(rows_from_wf55(payloads["wf55_current"], paths["wf55_current"], prices))
    rows.extend(rows_from_wf74(payloads["wf74_correctness"], paths["wf74_correctness"], prices))
    rows.extend(rows_from_wf78(payloads["wf78_human_review"], paths["wf78_human_review"], prices))
    rows.extend(rows_from_wf85_cards(payloads["wf85_decision_cards"], paths["wf85_decision_cards"], prices))
    rows.extend(rows_from_wf85_factory(payloads["wf85_decision_factory"], paths["wf85_decision_factory"], prices))
    rows.sort(key=lambda row: (str(row.get("ticker") or ""), str(row.get("source_family") or ""), str(row.get("row_id") or "")))
    family_counts: dict[str, int] = {}
    band_counts: dict[str, int] = {}
    for row in rows:
        family = str(row.get("source_family") or "unknown")
        family_counts[family] = family_counts.get(family, 0) + 1
        band = str(as_dict(row.get("market_context")).get("band_status") or "UNKNOWN")
        band_counts[band] = band_counts.get(band, 0) + 1
    ledger = {
        "schema": SCHEMA,
        "generated_at_utc": now or utc_now(),
        "status": "ok",
        "purpose": "Review-only normalized history ledger for future recommendation lookback and calibration.",
        "authority_flags": dict(AUTHORITY_FLAGS),
        "sources": {
            key: source_artifact(path, payloads[key], next((meta for meta in metas if meta["key"] == key), {}))
            for key, path in paths.items()
        },
        "summary": {
            "row_count": len(rows),
            "source_family_counts": dict(sorted(family_counts.items())),
            "ticker_count": len({row["ticker"] for row in rows if row.get("ticker")}),
            "band_status_counts": dict(sorted(band_counts.items())),
            "wf77_price_context_ticker_count": len(prices),
            "rows_with_price": sum(1 for row in rows if as_dict(row.get("market_context")).get("price") is not None),
            "rows_with_entry_band": sum(1 for row in rows if as_dict(row.get("feature_fields")).get("has_entry_band") is True),
            "rows_with_stop": sum(1 for row in rows if as_dict(row.get("feature_fields")).get("has_stop") is True),
            "rows_with_forward_scorecard": sum(1 for row in rows if as_dict(row.get("feature_fields")).get("forward_scorecard_status")),
            "sparse_source_count": sum(1 for meta in metas if meta.get("status") == "missing"),
            "parse_critical_source_count": sum(1 for meta in metas if meta.get("status") in {"parse_error", "read_error", "invalid_shape"}),
        },
        "rows": rows,
        "source_load": metas,
        "stop_lines": [
            "Historical analytics only; no recommendation approval, capital deployment, paper/live execution, account action, money movement, or owner approval inference.",
            "Sparse historical data should be treated as a coverage gap, not a validation failure.",
        ],
    }
    ledger["validation"] = validate_ledger(ledger)
    if ledger["validation"]["status"] == "critical":
        ledger["status"] = "blocked"
    elif ledger["validation"]["status"] == "warning":
        ledger["status"] = "warning"
    return ledger


def authority_true_paths(value: Any, prefix: str = "") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{prefix}.{key}" if prefix else str(key)
            if key in DANGEROUS_TRUE_KEYS and item is True:
                paths.append(child)
            paths.extend(authority_true_paths(item, child))
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            paths.extend(authority_true_paths(item, f"{prefix}[{idx}]"))
    return paths


def validate_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for key, expected in AUTHORITY_FLAGS.items():
        if as_dict(ledger.get("authority_flags")).get(key) is not expected:
            findings.append({"severity": "critical", "issue": "ledger_authority_mismatch", "field": key, "expected": expected})
    seen_ids: set[str] = set()
    for meta in as_list(ledger.get("source_load")):
        if as_dict(meta).get("status") in {"parse_error", "read_error", "invalid_shape"}:
            findings.append({"severity": "critical", "issue": "source_parse_critical", "source": meta})
    for idx, row in enumerate(as_list(ledger.get("rows")), start=1):
        if not isinstance(row, dict):
            findings.append({"severity": "critical", "issue": "row_invalid_shape", "row_index": idx})
            continue
        row_id = str(row.get("row_id") or "")
        if not row_id:
            findings.append({"severity": "critical", "issue": "row_id_missing", "row_index": idx})
        elif row_id in seen_ids:
            findings.append({"severity": "critical", "issue": "duplicate_row_id", "row_id": row_id})
        else:
            seen_ids.add(row_id)
        for key, expected in AUTHORITY_FLAGS.items():
            if as_dict(row.get("authority_flags")).get(key) is not expected:
                findings.append({"severity": "critical", "issue": "row_authority_mismatch", "row_id": row_id, "field": key, "expected": expected})
        drift = authority_true_paths(row)
        source_drift = as_list(row.get("source_authority_drift_paths"))
        if source_drift:
            drift.extend(str(item) for item in source_drift)
        if drift:
            findings.append({"severity": "critical", "issue": "row_authority_drift", "row_id": row_id, "paths": drift})
        if not row.get("ticker"):
            findings.append({"severity": "warning", "issue": "row_missing_ticker", "row_id": row_id})
        if as_dict(row.get("market_context")).get("price") is None:
            findings.append({"severity": "warning", "issue": "row_missing_price_context", "row_id": row_id})
    critical = sum(1 for item in findings if item.get("severity") == "critical")
    warnings = sum(1 for item in findings if item.get("severity") == "warning")
    return {
        "status": "critical" if critical else ("warning" if warnings else "ok"),
        "critical": critical,
        "warnings": warnings,
        "findings": findings,
    }


def render_md(ledger: dict[str, Any]) -> str:
    summary = as_dict(ledger.get("summary"))
    lines = [
        "# Finance Recommendation History Ledger",
        "",
        f"- Generated UTC: `{ledger.get('generated_at_utc')}`",
        f"- Status: `{ledger.get('status')}`",
        f"- Validation: `{as_dict(ledger.get('validation')).get('status')}`",
        f"- Rows: `{summary.get('row_count')}` across `{summary.get('ticker_count')}` tickers",
        f"- Rows with price / band / stop: `{summary.get('rows_with_price')}` / `{summary.get('rows_with_entry_band')}` / `{summary.get('rows_with_stop')}`",
        "",
        "## Source Families",
        "",
    ]
    for family, count in as_dict(summary.get("source_family_counts")).items():
        lines.append(f"- `{family}`: `{count}`")
    lines.extend(["", "## Band Status", ""])
    for status, count in as_dict(summary.get("band_status_counts")).items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend([
        "",
        "## Boundary",
        "",
        "Review-only historical analytics. No approval, execution, account, capital, canon, portfolio, model-training, or owner-approval inference authority.",
        "",
        "## Sample Rows",
        "",
    ])
    for row in as_list(ledger.get("rows"))[:20]:
        market = as_dict(row.get("market_context"))
        rec = as_dict(row.get("recommendation"))
        lines.append(
            f"- `{row.get('ticker')}` `{row.get('source_family')}` "
            f"price=`{market.get('price')}` band=`{market.get('band_status')}` "
            f"posture=`{rec.get('recommendation_posture')}` id=`{rec.get('recommendation_id')}`"
        )
    validation = as_dict(ledger.get("validation"))
    if validation.get("findings"):
        lines.extend(["", "## Validation Findings", ""])
        for finding in as_list(validation.get("findings"))[:30]:
            lines.append(f"- `{finding.get('severity')}` `{finding.get('issue')}`: `{finding.get('row_id') or finding.get('field') or finding.get('source')}`")
    return "\n".join(lines) + "\n"


def default_paths() -> dict[str, Path]:
    return {
        "wf55_current": WF55_CURRENT,
        "wf74_correctness": WF74_CORRECTNESS,
        "wf78_human_review": WF78_HUMAN_REVIEW,
        "wf85_decision_cards": WF85_DECISION_CARDS,
        "wf85_decision_factory": WF85_DECISION_FACTORY,
        "wf77_price_state": WF77_PRICE_STATE,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wf55-current", type=Path, default=WF55_CURRENT)
    parser.add_argument("--wf74-correctness", type=Path, default=WF74_CORRECTNESS)
    parser.add_argument("--wf78-human-review", type=Path, default=WF78_HUMAN_REVIEW)
    parser.add_argument("--wf85-decision-cards", type=Path, default=WF85_DECISION_CARDS)
    parser.add_argument("--wf85-decision-factory", type=Path, default=WF85_DECISION_FACTORY)
    parser.add_argument("--wf77-price-state", type=Path, default=WF77_PRICE_STATE)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    paths = {
        "wf55_current": abs_path(args.wf55_current),
        "wf74_correctness": abs_path(args.wf74_correctness),
        "wf78_human_review": abs_path(args.wf78_human_review),
        "wf85_decision_cards": abs_path(args.wf85_decision_cards),
        "wf85_decision_factory": abs_path(args.wf85_decision_factory),
        "wf77_price_state": abs_path(args.wf77_price_state),
    }
    ledger = build_ledger(paths)
    out = abs_path(args.json_out)
    md_out = out.with_suffix(".md")
    if args.write:
        atomic_write_json(out, ledger)
    if args.write_md:
        atomic_write_text(md_out, render_md(ledger))
    if not args.quiet:
        summary = as_dict(ledger.get("summary"))
        validation = as_dict(ledger.get("validation"))
        print(
            "status={status} validation={validation} rows={rows} tickers={tickers} critical={critical} warnings={warnings} out={out}".format(
                status=ledger.get("status"),
                validation=validation.get("status"),
                rows=summary.get("row_count"),
                tickers=summary.get("ticker_count"),
                critical=validation.get("critical"),
                warnings=validation.get("warnings"),
                out=rel(out) if args.write else None,
            )
        )
        for finding in as_list(validation.get("findings")):
            print(f"  [{finding.get('severity')}] {finding.get('issue')}: {finding.get('row_id') or finding.get('source') or finding.get('field')}")
    if args.validate and as_dict(ledger.get("validation")).get("status") == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
