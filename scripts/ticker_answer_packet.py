"""Build ticker_answer_packet_v1 compatibility artifacts.

The trade-grade full-answer owner is now
`scripts/trade_grade_full_answer_assembler.py`. This script remains as a legacy
reader/writer compatibility wrapper for existing consumers that still expect
`tmp/ticker-answer-packets/<TICKER>.current.json`.

Authority boundary: this is a response/route layer only. It carries no canon,
portfolio, sizing, paper, live, brokerage, account, execution, or owner-approval
authority. Owner markdown (Execution Board, Coverage and Watchlist) stays canon;
the packet only points at source lineage and surfaces assembler-derived values.

Schema (ticker_answer_packet_v1) top-level answer fields:
  ticker, generated_at_utc, answer_confidence, confidence_by_domain, source_count,
  source_lineage, effective_price_context, action_state, price_band_stop,
  technical_posture, thesis_summary, bull_case, bear_case, latest_earnings,
  key_financial_metrics, analyst_consensus, portfolio_fit, blockers,
  recommended_next_action, authority_boundary.

Every field is classified in field_provenance so the consumer can tell canon vs
generated vs overlay vs missing vs review-only at a glance.

CLI:
  python scripts/ticker_answer_packet.py --ticker BRK.B --validate
  python scripts/ticker_answer_packet.py --all-from-coverage --validate
  python scripts/ticker_answer_packet.py --all-from-coverage --write --allow-legacy-write --validate
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS = WORKSPACE / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from wf78_legacy_42_tier_state import production_tickers as legacy_42_tier_tickers
from trade_grade_full_answer_assembler import build_legacy_answer_packet

TMP = WORKSPACE / "tmp"
CARD_DIR = TMP / "ticker-intelligence-cards"
PACKET_DIR = TMP / "ticker-answer-packets"
BUILD_SUMMARY_PATH = TMP / "ticker-answer-packet-build-summary.json"
UNIVERSE_PATH = WORKSPACE / "data" / "finance" / "universe-v1.json"
POST_CLOSE_LEDGER_PATH = TMP / "post-close-final-quote-ledger.json"
COVERAGE_MD_PATH = WORKSPACE / "04. Research" / "Coverage and Watchlist.md"

SCHEMA_VERSION = 1
ARTIFACT_TYPE = "ticker_answer_packet_v1"
STALE_AFTER_HOURS = 36

PACKET_ANSWER_FIELDS = [
    "ticker",
    "generated_at_utc",
    "answer_confidence",
    "confidence_by_domain",
    "source_count",
    "source_lineage",
    "effective_price_context",
    "action_state",
    "price_band_stop",
    "technical_posture",
    "thesis_summary",
    "bull_case",
    "bear_case",
    "latest_earnings",
    "key_financial_metrics",
    "analyst_consensus",
    "portfolio_fit",
    "blockers",
    "recommended_next_action",
    "authority_boundary",
]

# Mirrors scripts/finance_intelligence_router_qa.py so packets cannot widen authority.
FORBIDDEN_TRUE_FLAGS = {
    "canonical_mutation_allowed",
    "canonical_note_mutation_allowed",
    "portfolio_mutation_allowed",
    "owner_approval_inferred",
    "owner_approval_granted",
    "trade_execution_allowed",
    "trade_or_execution_allowed",
    "trade_or_account_action_allowed",
    "paper_trade_submit_cancel_allowed",
    "paper_order_execution_allowed",
    "paper_order_submit_allowed",
    "paper_order_cancel_allowed",
    "live_trade_allowed",
    "live_trade_or_account_action_allowed",
    "live_brokerage_or_account_action_allowed",
    "money_movement_allowed",
    "capital_deployment_allowed",
    "capital_deployment_approved",
    "sql_canon_migration_allowed",
    "generated_report_is_canonical",
    "generated_registry_or_card_is_canon",
    "tmp_artifact_promotion_allowed",
}

REVIEW_ONLY_AUTHORITY_BOUNDARY = {
    "artifact_role": "derived_ticker_answer_response_and_route_layer_only",
    "generated_packet_is_canon": False,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "sizing_apply_allowed": False,
    "cash_or_risk_rule_mutation_allowed": False,
    "paper_order_execution_allowed": False,
    "paper_order_submit_allowed": False,
    "paper_order_cancel_allowed": False,
    "live_trade_allowed": False,
    "live_brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "owner_approval_inferred": False,
    "sql_canon_migration_allowed": False,
    "source_open_required_before_final_recommendation_or_action_claim": True,
}

LEVEL_SCORE = {"high": 0.9, "medium": 0.6, "low": 0.3, "none": 0.1}
DECISION_RELEVANT_DOMAINS = ("action_state", "price_band_stop", "recommendation")
PERIPHERAL_DOMAINS = ("analyst", "sector_context")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> tuple[Any | None, str | None]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except FileNotFoundError:
        return None, "missing"
    except json.JSONDecodeError as exc:
        return None, f"json_decode_error:{exc}"
    except OSError as exc:
        return None, f"read_error:{exc}"


def parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def find_true_forbidden_flags(obj: Any, path: str = "$", hits: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
    if hits is None:
        hits = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            child = f"{path}.{key}"
            if key in FORBIDDEN_TRUE_FLAGS and value is True:
                hits.append({"path": child, "flag": key})
            find_true_forbidden_flags(value, child, hits)
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            find_true_forbidden_flags(value, f"{path}[{idx}]", hits)
    return hits


def card_path_for(ticker: str) -> Path:
    return CARD_DIR / f"{ticker}.current.json"


def packet_path_for(ticker: str) -> Path:
    return PACKET_DIR / f"{ticker}.current.json"


def coverage_tickers() -> tuple[list[str], str | None]:
    """Return the migrated legacy-42 answer universe, shadow Tier state first."""
    migrated = legacy_42_tier_tickers()
    if migrated:
        return migrated, None
    universe, err = load_json(UNIVERSE_PATH)
    if err:
        return [], f"universe:{err}"
    entries = universe.get("entries") if isinstance(universe, dict) else None
    if not isinstance(entries, list):
        return [], "universe:no_entries"
    tickers = sorted(
        {
            str(row.get("ticker", "")).upper()
            for row in entries
            if isinstance(row, dict)
            and row.get("ticker")
            and row.get("active") is True
            and row.get("universe_scope", "production_current_42") == "production_current_42"
        }
    )
    return tickers, None


# --------------------------------------------------------------------------- #
# Confidence scoring (Lane 3): each domain returns level + numeric + reasons.
# --------------------------------------------------------------------------- #

def _domain(level: str, reasons: list[str]) -> dict[str, Any]:
    return {"level": level, "score": LEVEL_SCORE[level], "reasons": reasons}


def score_action_state(card: dict[str, Any]) -> dict[str, Any]:
    rs = card.get("recommendation_support") or {}
    contract = rs.get("deployment_contract") or {}
    status = contract.get("deployment_status")
    raw = contract.get("raw_context") or {}
    reasons: list[str] = []
    if status:
        reasons.append(f"deployment_contract.deployment_status={status}")
    if raw.get("workflow_state"):
        reasons.append(f"workflow_state={raw.get('workflow_state')}")
    if raw.get("action_state"):
        reasons.append(f"action_state={raw.get('action_state')}")
    if status:
        return _domain("high", reasons or ["explicit deployment contract present"])
    return _domain("low", ["no explicit deployment_contract status; action state unresolved"])


def score_price_band_stop(card: dict[str, Any]) -> dict[str, Any]:
    pbs = card.get("price_band_stop") or {}
    ref = card.get("entry_stop_reference_metadata") or {}
    have = all(pbs.get(k) is not None for k in ("entry_band_low", "entry_band_high", "stop_or_invalidation"))
    price = card.get("latest_known_price")
    reasons: list[str] = []
    if have:
        reasons.append(f"band={pbs.get('entry_band_low')}-{pbs.get('entry_band_high')} stop={pbs.get('stop_or_invalidation')}")
    if price is not None:
        reasons.append(f"latest_known_price={price} ({pbs.get('price_source')})")
    if ref.get("status") == "available":
        reasons.append(f"owner reference levels available ({ref.get('source_lineage', {}).get('owner_source_path')})")
    if pbs.get("staleness_note"):
        reasons.append(f"staleness_note={pbs.get('staleness_note')}")
    if have and price is not None:
        level = "medium" if pbs.get("fresh_quote_required") else "high"
        if level == "medium":
            reasons.append("fresh in-band quote still required")
        return _domain(level, reasons)
    if have:
        return _domain("medium", reasons + ["levels present but no resolved price"])
    return _domain("low", reasons or ["band/stop levels missing"])


def score_technical(card: dict[str, Any]) -> dict[str, Any]:
    tech = card.get("technical_posture") or {}
    if not tech or tech.get("latest_close") is None:
        return _domain("low", ["technical posture missing or no close"])
    reasons = [
        f"ma_posture={tech.get('ma_posture')}",
        f"band_status={tech.get('band_status')}",
        f"data_date={tech.get('data_date')}",
    ]
    if tech.get("macro_gate"):
        reasons.append(f"macro_gate={tech.get('macro_gate')}")
    return _domain("high", reasons)


def score_official_earnings(card: dict[str, Any]) -> dict[str, Any]:
    earn = card.get("latest_earnings_performance") or {}
    recon = card.get("fundamental_reconciliation") or {}
    status = earn.get("status")
    if status != "available":
        return _domain("low", [f"latest_earnings_performance.status={status}"])
    reasons = [f"period_end={earn.get('period_end')}"]
    if recon.get("sec_status") == "matched":
        reasons.append("SEC companyfacts matched")
        level = "high"
    else:
        reasons.append(f"sec_status={recon.get('sec_status')}")
        level = "medium"
    if recon.get("company_ir_status") and recon.get("company_ir_status") != "matched":
        reasons.append(f"company_ir_status={recon.get('company_ir_status')}")
    return _domain(level, reasons)


def score_analyst(card: dict[str, Any]) -> dict[str, Any]:
    an = card.get("analyst_consensus_ratings_targets") or {}
    conf = an.get("confidence")
    n = sum(int(an.get(k) or 0) for k in ("strong_buy_count", "buy_count", "hold_count", "sell_count", "strong_sell_count"))
    reasons = [f"provider_confidence={conf}", f"rating_count={n}", f"provider={an.get('provider')}", f"tier={an.get('tier')}"]
    if an.get("stale"):
        reasons.append("provider marked stale")
        return _domain("low", reasons)
    if conf == "high" and n >= 10:
        return _domain("high", reasons)
    if conf == "medium" or (n >= 6 and conf != "low"):
        return _domain("medium", reasons)
    return _domain("low", reasons)


def score_portfolio_fit(card: dict[str, Any]) -> dict[str, Any]:
    fit = card.get("portfolio_fit_concentration") or {}
    if not fit:
        return _domain("low", ["portfolio_fit_concentration missing"])
    reasons = [
        f"tier={fit.get('wf78_tier')}",
        f"portfolio_role={fit.get('portfolio_role')}",
        f"coverage_lane={fit.get('coverage_lane')}",
    ]
    sized = fit.get("recommended_starter_notional") is not None or fit.get("recommended_target_notional") is not None
    if sized:
        reasons.append("sizing surface present")
        return _domain("high", reasons)
    reasons.append("no recommended sizing surface yet")
    return _domain("medium", reasons)


def score_sector_context(card: dict[str, Any]) -> dict[str, Any]:
    sec = card.get("current_sector_performance") or {}
    status = sec.get("status")
    if status == "available" and sec.get("relative_strength_vs_spy") is not None:
        return _domain("high", [f"sector={sec.get('sector')}", f"rs_vs_spy={sec.get('relative_strength_vs_spy')}"])
    return _domain("low", [f"current_sector_performance.status={status}", "no sourced relative strength / leadership read"])


def score_recommendation(card: dict[str, Any]) -> dict[str, Any]:
    rs = card.get("recommendation_support") or {}
    support = rs.get("support_level")
    actionability = rs.get("actionability")
    blockers = rs.get("blockers_or_gates") or []
    contract = rs.get("deployment_contract") or {}
    status = contract.get("deployment_status")
    reasons = [f"support_level={support}", f"actionability={actionability}", f"deployment_status={status}"]
    # A clear "do not touch / blocked / owner-gated" posture with enumerated gates is
    # a high-confidence answer: we are confident in the no-action recommendation.
    if status in {"DO_NOT_TOUCH"} or rs.get("posture_key") in {"blocked_stale", "blocked"}:
        reasons.append(f"explicit gate with {len(blockers)} enumerated blocker(s)")
        return _domain("high", reasons)
    if status and actionability:
        return _domain("medium", reasons)
    return _domain("low", reasons or ["recommendation support unresolved"])


def build_confidence(card: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    by_domain = {
        "action_state": score_action_state(card),
        "price_band_stop": score_price_band_stop(card),
        "technical": score_technical(card),
        "official_earnings": score_official_earnings(card),
        "analyst": score_analyst(card),
        "portfolio_fit": score_portfolio_fit(card),
        "sector_context": score_sector_context(card),
        "recommendation": score_recommendation(card),
    }
    decision_scores = [by_domain[d]["score"] for d in DECISION_RELEVANT_DOMAINS if d in by_domain]
    peripheral_scores = [by_domain[d]["score"] for d in PERIPHERAL_DOMAINS if d in by_domain]
    decision_avg = sum(decision_scores) / len(decision_scores) if decision_scores else 0.1
    peripheral_avg = sum(peripheral_scores) / len(peripheral_scores) if peripheral_scores else 0.1

    def level_of(score: float) -> str:
        if score >= 0.8:
            return "high"
        if score >= 0.5:
            return "medium"
        if score >= 0.25:
            return "low"
        return "none"

    decision_level = level_of(decision_avg)
    peripheral_level = level_of(peripheral_avg)
    overall_score = round(0.7 * decision_avg + 0.3 * peripheral_avg, 3)
    reasons = [
        f"decision-relevant domains ({', '.join(DECISION_RELEVANT_DOMAINS)}) = {decision_level}",
        f"peripheral context domains ({', '.join(PERIPHERAL_DOMAINS)}) = {peripheral_level}",
    ]
    low_domains = [d for d, v in by_domain.items() if v["level"] in {"low", "none"}]
    if low_domains:
        reasons.append("low/none domains: " + ", ".join(low_domains))
    answer_confidence = {
        "overall_level": decision_level,
        "overall_label": f"{decision_level}_for_action_and_band_gate",
        "score": overall_score,
        "decision_relevant_level": decision_level,
        "decision_relevant_score": round(decision_avg, 3),
        "peripheral_context_level": peripheral_level,
        "peripheral_context_score": round(peripheral_avg, 3),
        "reasons": reasons,
    }
    return answer_confidence, by_domain


# --------------------------------------------------------------------------- #
# Thesis prose (parsed from canon Coverage and Watchlist.md, best-effort).
# --------------------------------------------------------------------------- #

_COVERAGE_CACHE: dict[str, Any] = {}


def coverage_text() -> str | None:
    if "text" not in _COVERAGE_CACHE:
        try:
            _COVERAGE_CACHE["text"] = COVERAGE_MD_PATH.read_text(encoding="utf-8")
        except OSError:
            _COVERAGE_CACHE["text"] = None
    return _COVERAGE_CACHE["text"]


def parse_coverage_thesis(ticker: str) -> dict[str, Any]:
    text = coverage_text()
    if not text:
        return {"parse_status": "source_open_required", "note": "Coverage and Watchlist.md unreadable; open canon source."}
    pattern = re.compile(r"^###\s+" + re.escape(ticker) + r"\b.*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        return {"parse_status": "source_open_required", "note": f"No '### {ticker}' thesis section found in canon; open source."}
    start = match.end()
    nxt = re.compile(r"^#{2,3}\s", re.MULTILINE).search(text, start)
    body = text[start: nxt.start() if nxt else len(text)]
    label_keys = [
        ("Status", "owner_status"),
        ("Thesis", "thesis"),
        ("Key risk", "key_risk"),
        ("Key evidence", "key_evidence"),
        ("Catalyst state", "catalyst_state"),
        ("Act when", "act_when"),
    ]
    fields: dict[str, str] = {}
    for label, key in label_keys:
        lm = re.search(r"-\s+\*\*" + re.escape(label) + r":\*\*\s*(.+)", body)
        if lm:
            fields[key] = lm.group(1).strip()
    if "thesis" not in fields:
        return {"parse_status": "source_open_required", "note": f"'### {ticker}' section present but no parseable thesis; open source."}
    fields["parse_status"] = "parsed_from_canon"
    fields["source_path"] = rel(COVERAGE_MD_PATH)
    return fields


# --------------------------------------------------------------------------- #
# Effective price overlay (post-close ledger when present, else card price).
# --------------------------------------------------------------------------- #

_LEDGER_CACHE: dict[str, Any] = {}


def post_close_row(ticker: str) -> dict[str, Any] | None:
    if "rows" not in _LEDGER_CACHE:
        ledger, _ = load_json(POST_CLOSE_LEDGER_PATH)
        rows = {}
        if isinstance(ledger, dict):
            for row in ledger.get("rows") or []:
                if isinstance(row, dict) and row.get("ticker"):
                    rows[str(row["ticker"]).upper()] = row
        _LEDGER_CACHE["rows"] = rows
    return _LEDGER_CACHE["rows"].get(ticker.upper())


def build_effective_price_context(ticker: str, card: dict[str, Any]) -> dict[str, Any]:
    pbs = card.get("price_band_stop") or {}
    card_price = card.get("latest_known_price")
    card_source = pbs.get("price_source")
    fresh_required = bool(pbs.get("fresh_quote_required"))
    row = post_close_row(ticker)
    if row and row.get("status") == "ok" and row.get("close") is not None:
        return {
            "status": "available",
            "effective_price": row.get("close"),
            "price_source": rel(POST_CLOSE_LEDGER_PATH),
            "market_date": row.get("market_date"),
            "as_of_utc": row.get("retrieved_at_utc"),
            "post_close_overlay_applied": True,
            "fresh_quote_required": fresh_required,
            "card_latest_known_price": card_price,
            "card_price_source": card_source,
            "staleness_note": pbs.get("staleness_note"),
        }
    if card_price is not None:
        return {
            "status": "available",
            "effective_price": card_price,
            "price_source": card_source,
            "market_date": (card.get("technical_posture") or {}).get("data_date"),
            "as_of_utc": card.get("generated_at_utc"),
            "post_close_overlay_applied": False,
            "fresh_quote_required": fresh_required,
            "card_latest_known_price": card_price,
            "card_price_source": card_source,
            "staleness_note": pbs.get("staleness_note"),
        }
    return {
        "status": "missing",
        "effective_price": None,
        "price_source": None,
        "post_close_overlay_applied": False,
        "fresh_quote_required": fresh_required,
        "staleness_note": "no resolved price in card or post-close ledger",
    }


# --------------------------------------------------------------------------- #
# Packet assembly (Lane 2).
# --------------------------------------------------------------------------- #

def build_thesis_fields(ticker: str, card: dict[str, Any]) -> tuple[Any, Any, Any]:
    parsed = parse_coverage_thesis(ticker)
    tbe = card.get("thesis_bull_bear_entry_context") or {}
    if parsed.get("parse_status") == "parsed_from_canon":
        thesis_summary = {
            "status": "available",
            "summary": parsed.get("thesis"),
            "owner_status": parsed.get("owner_status"),
            "act_when": parsed.get("act_when"),
            "catalyst_state": parsed.get("catalyst_state"),
            "provenance": parsed.get("source_path"),
        }
        bull_case = {
            "status": "available",
            "primary": parsed.get("thesis"),
            "drivers": (tbe.get("bull_case_inputs") or []),
            "key_evidence": parsed.get("key_evidence"),
            "provenance": parsed.get("source_path"),
            "note": "Bull thesis from canon; quantified drivers require source-open of cited inputs.",
        }
        bear_case = {
            "status": "available",
            "primary": parsed.get("key_risk"),
            "factors": (tbe.get("bear_case_inputs") or []),
            "provenance": parsed.get("source_path"),
        }
        return thesis_summary, bull_case, bear_case
    # Fallback: card carries only structured input names, not prose.
    thesis_summary = {
        "status": "source_open_required",
        "summary": tbe.get("thesis"),
        "note": parsed.get("note"),
        "provenance": "tmp/ticker-intelligence-cards/%s.current.json" % ticker,
    }
    bull_case = {"status": "source_open_required", "drivers": tbe.get("bull_case_inputs") or [], "note": parsed.get("note")}
    bear_case = {"status": "source_open_required", "factors": tbe.get("bear_case_inputs") or [], "note": parsed.get("note")}
    return thesis_summary, bull_case, bear_case


def build_source_lineage(ticker: str, card: dict[str, Any], thesis_summary: dict[str, Any], eff_price: dict[str, Any]) -> list[dict[str, Any]]:
    lineage: list[dict[str, Any]] = []
    lineage.append({
        "kind": "primary_card",
        "role": "reconciled_intelligence_card",
        "path": rel(card_path_for(ticker)),
        "generated_at_utc": card.get("generated_at_utc"),
        "authority": "derived_review_only",
    })
    ref = card.get("entry_stop_reference_metadata") or {}
    owner_lineage = ref.get("source_lineage") or {}
    if owner_lineage.get("owner_source_path"):
        lineage.append({
            "kind": "canon_owner_note",
            "role": "entry_band_stop_owner_source",
            "path": owner_lineage.get("owner_source_path"),
            "source_timestamp": owner_lineage.get("source_timestamp"),
            "source_sha256": owner_lineage.get("source_sha256"),
            "authority": "canon",
        })
    if thesis_summary.get("provenance"):
        lineage.append({
            "kind": "canon_owner_note",
            "role": "thesis_bull_bear",
            "path": thesis_summary.get("provenance"),
            "authority": "canon",
        })
    if eff_price.get("post_close_overlay_applied"):
        lineage.append({
            "kind": "quote_overlay",
            "role": "post_close_effective_price",
            "path": rel(POST_CLOSE_LEDGER_PATH),
            "market_date": eff_price.get("market_date"),
            "authority": "derived_review_only",
        })
    for art in card.get("source_artifacts") or []:
        if isinstance(art, dict) and art.get("path"):
            lineage.append({
                "kind": "underlying_artifact",
                "role": "card_source_artifact",
                "path": str(art.get("path")).replace("\\", "/"),
                "generated_at_utc": art.get("generated_at_utc"),
                "exists": art.get("exists"),
                "authority": "derived_review_only",
            })
    return lineage


def build_packet(ticker: str) -> tuple[dict[str, Any] | None, list[str]]:
    return build_legacy_answer_packet(ticker)


def build_packet_legacy_pre_assembler(ticker: str) -> tuple[dict[str, Any] | None, list[str]]:
    issues: list[str] = []
    card, err = load_json(card_path_for(ticker))
    if err:
        return None, [f"card_{err}:{rel(card_path_for(ticker))}"]
    if not isinstance(card, dict):
        return None, [f"card_not_object:{rel(card_path_for(ticker))}"]

    answer_confidence, confidence_by_domain = build_confidence(card)
    eff_price = build_effective_price_context(ticker, card)
    thesis_summary, bull_case, bear_case = build_thesis_fields(ticker, card)
    source_lineage = build_source_lineage(ticker, card, thesis_summary, eff_price)

    rs = card.get("recommendation_support") or {}
    contract = rs.get("deployment_contract") or {}
    price_band_stop = card.get("price_band_stop") or {}
    raw_context = contract.get("raw_context") or {}
    raw_band_status = raw_context.get("band_status")
    action_band_status = raw_band_status if raw_band_status and raw_band_status != "UNKNOWN" else rs.get("band_status") or price_band_stop.get("band_status")
    action_state = {
        "status": "available" if contract.get("deployment_status") else "missing",
        "deployment_status": contract.get("deployment_status"),
        "display_label": contract.get("display_label"),
        "workflow_state": raw_context.get("workflow_state"),
        "band_status": action_band_status,
        "below_stop": raw_context.get("below_stop"),
        "support_level": rs.get("support_level"),
        "actionability": rs.get("actionability"),
    }

    blockers = []
    for item in rs.get("blockers_or_gates") or []:
        blockers.append({"kind": "gate", "detail": item})
    for item in card.get("missing_or_stale_evidence") or []:
        if isinstance(item, dict):
            blockers.append({"kind": "missing_or_stale_evidence", "family": item.get("family"), "severity": item.get("severity"), "detail": item.get("detail")})

    recommended_next_action = build_recommended_next_action(contract, rs, eff_price, action_state)

    fit = card.get("portfolio_fit_concentration") or {}
    portfolio_fit = {
        "status": "available" if fit else "missing",
        "sector": fit.get("sector"),
        "tier": fit.get("wf78_tier"),
        "wf78_auto_tier": fit.get("wf78_auto_tier"),
        "wf78_auto_state": fit.get("wf78_auto_state"),
        "wf78_tier": fit.get("wf78_tier"),
        "wf78_decision_grade_eligible": fit.get("wf78_decision_grade_eligible"),
        "portfolio_role": fit.get("portfolio_role"),
        "coverage_lane": fit.get("coverage_lane"),
        "monitoring_role": fit.get("wf78_monitoring_role"),
        "recommended_starter_notional": fit.get("recommended_starter_notional"),
        "recommended_target_notional": fit.get("recommended_target_notional"),
        "decision_note": fit.get("decision_note"),
    }

    analyst = card.get("analyst_consensus_ratings_targets") or {}
    analyst_consensus = {
        "status": analyst.get("status", "missing"),
        "consensus_rating": analyst.get("consensus_rating"),
        "average_target": analyst.get("average_target"),
        "median_target": analyst.get("median_target"),
        "high_target": analyst.get("high_target"),
        "low_target": analyst.get("low_target"),
        "implied_upside_downside_pct": analyst.get("implied_upside_downside_pct"),
        "counts": {
            "strong_buy": analyst.get("strong_buy_count"),
            "buy": analyst.get("buy_count"),
            "hold": analyst.get("hold_count"),
            "sell": analyst.get("sell_count"),
            "strong_sell": analyst.get("strong_sell_count"),
        },
        "provider": analyst.get("provider"),
        "provider_confidence": analyst.get("confidence"),
        "stale": analyst.get("stale"),
    }

    now = utc_now()
    packet: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": ARTIFACT_TYPE,
        "ticker": ticker,
        "generated_at_utc": now,
        "review_only": True,
        "source_card_generated_at_utc": card.get("generated_at_utc"),
        "freshness": {
            "stale_after_hours": STALE_AFTER_HOURS,
            "built_from_card_at_utc": card.get("generated_at_utc"),
            "note": "Router treats packet as stale if the underlying card is newer than source_card_generated_at_utc or if older than stale_after_hours.",
        },
        "answer_confidence": answer_confidence,
        "confidence_by_domain": confidence_by_domain,
        "source_count": len({row.get("path") for row in source_lineage if row.get("path")}),
        "source_lineage": source_lineage,
        "effective_price_context": eff_price,
        "action_state": action_state,
        "price_band_stop": card.get("price_band_stop") or {"status": "missing"},
        "technical_posture": card.get("technical_posture") or {"status": "missing"},
        "thesis_summary": thesis_summary,
        "bull_case": bull_case,
        "bear_case": bear_case,
        "latest_earnings": card.get("latest_earnings_performance") or {"status": "missing"},
        "key_financial_metrics": card.get("key_financial_metrics") or {"status": "missing"},
        "analyst_consensus": analyst_consensus,
        "portfolio_fit": portfolio_fit,
        "blockers": blockers,
        "recommended_next_action": recommended_next_action,
        "authority_boundary": dict(REVIEW_ONLY_AUTHORITY_BOUNDARY),
    }
    packet["field_provenance"] = build_field_provenance(packet, card, thesis_summary, eff_price)

    missing_answer_fields = [f for f in PACKET_ANSWER_FIELDS if f not in packet]
    if missing_answer_fields:
        issues.append("missing_answer_fields:" + ",".join(missing_answer_fields))
    return packet, issues


def build_recommended_next_action(contract: dict[str, Any], rs: dict[str, Any], eff_price: dict[str, Any], action_state: dict[str, Any]) -> dict[str, Any]:
    status = contract.get("deployment_status")
    band_status = action_state.get("band_status")
    if status == "DO_NOT_TOUCH":
        action = "Hold / no action. Do not deploy capital while in repair / below-band posture. Monitor for band reclaim and structure repair; any action requires explicit owner approval."
        urgency = "none"
    elif status in {"READY", "DEPLOYABLE", "DEPLOY_CANDIDATE"} and band_status in {"IN_BAND", "IN BAND"}:
        action = "Owner-review candidate: fresh in-band quote present. Prepare approval card only; execution requires explicit owner approval."
        urgency = "review"
    else:
        action = "Review-only. Open exact source artifacts before any readiness, recommendation, approval, or action claim."
        urgency = "review"
    return {
        "action": action,
        "urgency": urgency,
        "owner_approval_required": True,
        "execution_authorized": False,
        "based_on": {
            "deployment_status": status,
            "band_status": band_status,
            "effective_price": eff_price.get("effective_price"),
            "support_level": rs.get("support_level"),
        },
    }


def build_field_provenance(packet: dict[str, Any], card: dict[str, Any], thesis_summary: dict[str, Any], eff_price: dict[str, Any]) -> dict[str, str]:
    prov = {
        "ticker": "card_derived",
        "generated_at_utc": "generated",
        "answer_confidence": "generated",
        "confidence_by_domain": "generated",
        "source_count": "generated",
        "source_lineage": "generated",
        "effective_price_context": "overlay" if eff_price.get("post_close_overlay_applied") else "card_derived",
        "action_state": "card_derived",
        "price_band_stop": "card_derived_with_canon_owner_lineage",
        "technical_posture": "card_derived",
        "thesis_summary": "canon_owner_source" if thesis_summary.get("status") == "available" else "missing_source_open_required",
        "bull_case": "canon_owner_source" if packet["bull_case"].get("status") == "available" else "missing_source_open_required",
        "bear_case": "canon_owner_source" if packet["bear_case"].get("status") == "available" else "missing_source_open_required",
        "latest_earnings": "card_derived" if (card.get("latest_earnings_performance") or {}).get("status") == "available" else "missing",
        "key_financial_metrics": "card_derived" if (card.get("key_financial_metrics") or {}).get("status") == "available" else "missing",
        "analyst_consensus": "card_derived" if packet["analyst_consensus"].get("status") not in {"missing", None} else "missing",
        "portfolio_fit": "card_derived" if packet["portfolio_fit"].get("status") == "available" else "missing",
        "blockers": "card_derived",
        "recommended_next_action": "generated_review_only",
        "authority_boundary": "review_only_boundary",
    }
    return prov


# --------------------------------------------------------------------------- #
# Validation (Lane 6 hook).
# --------------------------------------------------------------------------- #

def check(name: str, passed: bool, detail: str, severity: str = "error") -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "severity": severity, "detail": detail}


def validate_packets(packets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for ticker, packet in sorted(packets.items()):
        missing = [f for f in PACKET_ANSWER_FIELDS if f not in packet]
        results.append(check(f"packet_all_answer_fields_present:{ticker}", not missing, f"missing={missing}"))
        forbidden = find_true_forbidden_flags(packet)
        results.append(check(f"packet_no_authority_widening:{ticker}", not forbidden, f"forbidden={forbidden}"))
        boundary = packet.get("authority_boundary") or {}
        results.append(check(
            f"packet_source_open_required:{ticker}",
            boundary.get("source_open_required_before_final_recommendation_or_action_claim") is True,
            "source-open must be required before final recommendation/action.",
        ))
        results.append(check(
            f"packet_review_only:{ticker}",
            packet.get("review_only") is True and boundary.get("generated_packet_is_canon") is False,
            "packet must be review_only and not canon.",
        ))
        conf = packet.get("confidence_by_domain") or {}
        domains_ok = all(isinstance(conf.get(d), dict) and conf[d].get("reasons") for d in ("action_state", "analyst", "sector_context"))
        results.append(check(f"packet_confidence_has_reasons:{ticker}", domains_ok, "confidence domains must carry reasons, not just a number."))
        # BRK.B is the proof anchor for the parallel plan acceptance criteria.
        if ticker == "BRK.B":
            results.append(check("brkb_action_state_high", conf.get("action_state", {}).get("level") == "high", f"action_state={conf.get('action_state', {}).get('level')!r}"))
            results.append(check("brkb_recommendation_high", conf.get("recommendation", {}).get("level") == "high", f"recommendation={conf.get('recommendation', {}).get('level')!r}"))
            results.append(check("brkb_analyst_low", conf.get("analyst", {}).get("level") == "low", f"analyst={conf.get('analyst', {}).get('level')!r}"))
            results.append(check("brkb_sector_low", conf.get("sector_context", {}).get("level") == "low", f"sector_context={conf.get('sector_context', {}).get('level')!r}"))
            astate = packet.get("action_state") or {}
            results.append(check("brkb_do_not_touch_state", astate.get("deployment_status") == "DO_NOT_TOUCH", f"deployment_status={astate.get('deployment_status')!r}"))
            results.append(check("brkb_no_execution_in_next_action", packet.get("recommended_next_action", {}).get("execution_authorized") is False, "recommended_next_action must not authorize execution."))
    return results


# --------------------------------------------------------------------------- #
# CLI.
# --------------------------------------------------------------------------- #

def write_packet(ticker: str, packet: dict[str, Any]) -> Path:
    PACKET_DIR.mkdir(parents=True, exist_ok=True)
    path = packet_path_for(ticker)
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def build_summary(results_by_ticker: list[dict[str, Any]], requested: list[str], validation: list[dict[str, Any]] | None) -> dict[str, Any]:
    built = [r for r in results_by_ticker if r["status"] == "built"]
    failed = [r for r in results_by_ticker if r["status"] != "built"]
    errors = [c for c in (validation or []) if not c["passed"] and c.get("severity") == "error"]
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "ticker_answer_packet_build_summary",
        "generated_at_utc": utc_now(),
        "review_only": True,
        "status": "pass" if not failed and not errors else "fail",
        "authority_boundary": dict(REVIEW_ONLY_AUTHORITY_BOUNDARY),
        "summary": {
            "requested": len(requested),
            "built": len(built),
            "failed": len(failed),
            "validation_errors": len(errors),
        },
        "field_contract": PACKET_ANSWER_FIELDS,
        "results": results_by_ticker,
        "validation_checks": validation or [],
        "stop_lines": [
            "Generated packet is a response/route layer only; not canon, not approval, not execution.",
            "Owner markdown (Execution Board, Coverage and Watchlist) remains canonical.",
            "No portfolio, sizing, paper, live, brokerage, account, or money-movement authority.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build ticker_answer_packet_v1 review-only consolidated answer packets.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--ticker", type=str, help="Build a single ticker, e.g. BRK.B")
    group.add_argument("--all-from-coverage", action="store_true", help="Build all production_current_42 coverage tickers.")
    parser.add_argument("--write", action="store_true", help="Write legacy compatibility packet JSON.")
    parser.add_argument(
        "--allow-legacy-write",
        action="store_true",
        help="Explicitly allow the deprecated compatibility writer. Prefer trade_grade_full_answer_assembler.py for active refreshes.",
    )
    parser.add_argument("--validate", action="store_true", help="Validate built packets; exit 1 on error.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the build summary to stdout.")
    args = parser.parse_args(argv)
    if args.write and not args.allow_legacy_write:
        print(json.dumps({
            "status": "blocked",
            "reason": "legacy_packet_write_requires_explicit_allow_legacy_write",
            "preferred_writer": "scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate",
            "archive_delete_apply_allowed": False,
        }))
        return 2

    if args.all_from_coverage:
        requested, err = coverage_tickers()
        if err:
            print(json.dumps({"status": "fail", "error": err}))
            return 1
    else:
        requested = [args.ticker.strip().upper()]

    packets: dict[str, dict[str, Any]] = {}
    results_by_ticker: list[dict[str, Any]] = []
    for ticker in requested:
        packet, issues = build_packet(ticker)
        if packet is None:
            results_by_ticker.append({"ticker": ticker, "status": "failed", "issues": issues})
            continue
        if args.write:
            written = write_packet(ticker, packet)
            results_by_ticker.append({
                "ticker": ticker,
                "status": "built",
                "path": rel(written),
                "answer_confidence_level": packet["answer_confidence"]["overall_level"],
                "issues": issues,
            })
        else:
            results_by_ticker.append({
                "ticker": ticker,
                "status": "built",
                "path": None,
                "answer_confidence_level": packet["answer_confidence"]["overall_level"],
                "issues": issues,
            })
        packets[ticker] = packet

    validation = validate_packets(packets) if args.validate else None
    summary = build_summary(results_by_ticker, requested, validation)
    if args.write:
        BUILD_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
        BUILD_SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
