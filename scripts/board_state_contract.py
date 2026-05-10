from __future__ import annotations

from typing import Any

CANONICAL_ACTION_STATE_MAP = {
    "DEPLOYABLE": "DEPLOYABLE NOW",
    "DEPLOYABLE NOW": "DEPLOYABLE NOW",
    "DEPLOYED": "DEPLOYABLE NOW",
    "ALMOST": "ALMOST DEPLOYABLE",
    "ALMOST DEPLOYABLE": "ALMOST DEPLOYABLE",
    "PROMOTION REVIEW": "ALMOST DEPLOYABLE",
    "ALMOST / NEAR-EARNINGS CAUTION": "ALMOST / NEAR-EARNINGS CAUTION",
    "BLOCKED": "BLOCKED",
    "POST-EARNINGS REVIEW": "POST-EARNINGS REVIEW",
    # BENCH is a first-class state: chart-weak / setup not ready, but not fundamentally impaired.
    # Distinct from DO NOT TOUCH (below stop / repair / broken) so consumers can surface the
    # difference rather than collapsing actionable information.
    "BENCH": "BENCH",
    "REPAIR": "DO NOT TOUCH",
    "BELOW STOP": "DO NOT TOUCH",
    "DO NOT TOUCH": "DO NOT TOUCH",
    "WATCH": "WATCH / RESEARCH NEEDED",
    "WATCH / RESEARCH NEEDED": "WATCH / RESEARCH NEEDED",
    "MACRO": "WATCH / RESEARCH NEEDED",
    "ERROR": "ERROR",
    "SYSTEM HOLD": "SYSTEM HOLD",
}

ACTIONABLE_STATES = frozenset({"DEPLOYABLE NOW", "ALMOST DEPLOYABLE"})
REVIEW_STATES = frozenset({*ACTIONABLE_STATES, "BLOCKED"})

STATE_ORDER = {
    "DEPLOYABLE NOW": 0,
    "ALMOST DEPLOYABLE": 1,
    "ALMOST / NEAR-EARNINGS CAUTION": 2,
    "POST-EARNINGS REVIEW": 3,
    "BLOCKED": 4,
    # BENCH: monitor but do not deploy — less severe than DO NOT TOUCH, more active than WATCH
    "BENCH": 5,
    "SYSTEM HOLD": 6,
    "DO NOT TOUCH": 7,
    "WATCH / RESEARCH NEEDED": 8,
    "ERROR": 9,
}


def canonical_action_state(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return "WATCH / RESEARCH NEEDED"
    return CANONICAL_ACTION_STATE_MAP.get(raw, raw)


def state_sort_rank(value: Any) -> int:
    return STATE_ORDER.get(canonical_action_state(value), 99)


def record_state(record: dict[str, Any]) -> str:
    return canonical_action_state(
        record.get("action_state") or record.get("deployment_state") or record.get("workflow_state")
    )


def record_sort_key(record: dict[str, Any]) -> tuple[int, str]:
    return (state_sort_rank(record_state(record)), str(record.get("ticker") or ""))


def filter_records_by_states(records: list[dict[str, Any]], allowed_states: set[str] | frozenset[str]) -> list[dict[str, Any]]:
    normalized = {canonical_action_state(state) for state in allowed_states}
    return [record for record in records if record_state(record) in normalized]


def actionable_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(filter_records_by_states(records, ACTIONABLE_STATES), key=record_sort_key)


def review_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(filter_records_by_states(records, REVIEW_STATES), key=record_sort_key)


def _tracked_universe(portfolio_config: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    universe = (portfolio_config or {}).get("tracked_universe") or {}
    if not isinstance(universe, dict):
        return {}
    return {str(ticker): meta for ticker, meta in universe.items() if isinstance(meta, dict)}


def _quote_target_for_ticker(ticker: str, universe: dict[str, dict[str, Any]]) -> dict[str, str]:
    meta = universe.get(ticker) or {}
    yfinance = str(meta.get("yfinance") or ticker)
    return {"key": ticker, "ticker": yfinance, "label": ticker}


def execution_priority_quote_targets(portfolio_config: dict[str, Any] | None) -> list[dict[str, str]]:
    universe = _tracked_universe(portfolio_config)
    candidates: list[tuple[int, str, dict[str, str]]] = []

    for ticker, meta in universe.items():
        if str(meta.get("coverage_lane") or "").lower() != "execution":
            continue
        if not bool(meta.get("daily_technical_priority")):
            continue
        if canonical_action_state(meta.get("workflow_state")) not in REVIEW_STATES:
            continue
        candidates.append((state_sort_rank(meta.get("workflow_state")), ticker, _quote_target_for_ticker(ticker, universe)))

    candidates.sort(key=lambda item: (item[0], item[1]))
    return [target for _, _, target in candidates]


def resolve_market_snapshot_targets(
    trigger_hint: dict[str, Any] | None,
    portfolio_config: dict[str, Any] | None,
) -> dict[str, Any]:
    universe = _tracked_universe(portfolio_config)
    trigger_records = (trigger_hint or {}).get("records") or []
    if not isinstance(trigger_records, list):
        trigger_records = []

    active_review_records = review_records([record for record in trigger_records if isinstance(record, dict)])
    seen: set[str] = set()
    targets: list[dict[str, str]] = []

    for record in active_review_records:
        ticker = str(record.get("ticker") or "").strip()
        if not ticker or ticker in seen:
            continue
        targets.append(_quote_target_for_ticker(ticker, universe))
        seen.add(ticker)

    if targets:
        return {
            "source": "trigger_sheet_review_states",
            "target_count": len(targets),
            "targets": targets,
        }

    fallback_targets = execution_priority_quote_targets(portfolio_config)
    deduped_fallback: list[dict[str, str]] = []
    for target in fallback_targets:
        ticker = target["key"]
        if ticker in seen:
            continue
        deduped_fallback.append(target)
        seen.add(ticker)

    return {
        "source": "portfolio_config_execution_priority",
        "target_count": len(deduped_fallback),
        "targets": deduped_fallback,
    }
