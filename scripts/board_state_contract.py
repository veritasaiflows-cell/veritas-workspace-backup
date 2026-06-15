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


# --- Canonical deployment-state contract -------------------------------------
#
# One normalizer that collapses the three scattered legacy fields
# (workflow_state, machine_state/deployment_state, action_state) plus already
# resolved surface_state into a single canonical decision object. Legacy fields
# stay as compatibility aliases; this is the additive layer that lets readers
# migrate without losing trace context.
#
# Resolution precedence: surface_state and base_surface_state are already fully
# resolved by deployment_readiness_surface.surface_state_for() (override rules
# applied), so they outrank the raw action_state/machine_state/workflow_state
# inputs. We read the most-resolved field available rather than re-deriving the
# override rules here, which keeps this contract from diverging from the writer.

DEPLOYMENT_STATUS_ENUM = frozenset(
    {
        "DEPLOYABLE_NOW",
        "ALMOST_DEPLOYABLE",
        "PROMOTION_REVIEW",
        "POST_EARNINGS_REVIEW",
        "NO_CHASE",
        "BELOW_STOP",
        "DO_NOT_TOUCH",
        "BENCH",
        "BLOCKED",
        "AUTHORITY_CONFLICT",
        "SYSTEM_HOLD",
        "WATCH",
        "ERROR",
    }
)

# raw human label (post canonical_action_state space, plus a few raw passthroughs)
# -> (deployment_status, status_reason, display_label)
_CANONICAL_STATUS_MAP: dict[str, tuple[str, str, str]] = {
    "DEPLOYABLE NOW": ("DEPLOYABLE_NOW", "in_band_ready", "deployable now"),
    "DEPLOYABLE": ("DEPLOYABLE_NOW", "in_band_ready", "deployable now"),
    "DEPLOYED": ("DEPLOYABLE_NOW", "in_band_ready", "deployable now"),
    "ALMOST DEPLOYABLE": ("ALMOST_DEPLOYABLE", "almost_ready", "almost deployable"),
    "ALMOST": ("ALMOST_DEPLOYABLE", "almost_ready", "almost deployable"),
    "ALMOST / NEAR-EARNINGS CAUTION": ("ALMOST_DEPLOYABLE", "near_earnings_caution", "almost — near-earnings caution"),
    "PROMOTION REVIEW": ("PROMOTION_REVIEW", "promotion_review_pending", "promotion review"),
    "POST-EARNINGS REVIEW": ("POST_EARNINGS_REVIEW", "post_earnings_review", "post-earnings review"),
    "BELOW STOP": ("BELOW_STOP", "below_stop", "below stop — exit/repair"),
    "DO NOT TOUCH": ("DO_NOT_TOUCH", "repair_mode_active", "do not touch — repair/stop"),
    "REPAIR": ("DO_NOT_TOUCH", "repair_mode_active", "do not touch — repair/stop"),
    "BENCH": ("BENCH", "bench_setup_not_ready", "bench — monitor, not ready"),
    "BLOCKED": ("BLOCKED", "blocked", "blocked"),
    "AUTHORITY CONFLICT": ("AUTHORITY_CONFLICT", "authority_conflict", "authority conflict — review"),
    "SYSTEM HOLD": ("SYSTEM_HOLD", "system_hold", "system hold"),
    "WATCH / RESEARCH NEEDED": ("WATCH", "watch_research_needed", "watch / research needed"),
    "WATCH": ("WATCH", "watch_research_needed", "watch / research needed"),
    "MACRO": ("WATCH", "watch_research_needed", "watch / research needed"),
    "ERROR": ("ERROR", "error", "error"),
}

_RESOLVED_STATE_KEYS = (
    "surface_state",
    "base_surface_state",
    "action_state",
    "deployment_state",
    "machine_state",
    "workflow_state",
)

_ABOVE_BAND_VALUES = frozenset({"ABOVE_BAND", "ABOVE BAND"})


def deployment_raw_context(record: dict[str, Any] | None) -> dict[str, Any]:
    """Return the canonical raw_context when present, otherwise the record itself."""
    if not isinstance(record, dict):
        return {}
    if isinstance(record.get("raw_context"), dict):
        return record["raw_context"]
    contract = record.get("deployment_contract")
    if isinstance(contract, dict) and isinstance(contract.get("raw_context"), dict):
        return contract["raw_context"]
    return record


def legacy_state(record: dict[str, Any] | None, field: str, default: Any = None) -> Any:
    """Compatibility accessor for legacy state fields.

    Readers should use canonical deployment_status when they can. When they need
    the legacy vocabulary for scoring, history, or compatibility output, read it
    through raw_context first so generated top-level aliases can later be removed.
    """
    if field not in {*_RESOLVED_STATE_KEYS, "band_status", "below_stop"}:
        raise KeyError(f"unsupported legacy deployment-state field: {field}")
    context = deployment_raw_context(record)
    value = context.get(field)
    if value is None and field == "machine_state":
        value = context.get("deployment_state")
    return default if value is None else value


def _clean_label(value: Any) -> str:
    return " ".join(str(value or "").strip().upper().split())


def _effective_raw_label(record: dict[str, Any]) -> str:
    for key in _RESOLVED_STATE_KEYS:
        label = _clean_label(record.get(key))
        if label:
            return label
    return ""


def deployment_contract(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize any deployment/trigger/portfolio record into the canonical
    deployment-state contract. Pure function; never mutates the input."""
    raw_label = _effective_raw_label(record)
    band_status = _clean_label(record.get("band_status"))
    below_stop = bool(record.get("below_stop"))

    if raw_label in _CANONICAL_STATUS_MAP:
        status, reason, display = _CANONICAL_STATUS_MAP[raw_label]
    else:
        # Fall back through the existing action-state collapse for unknowns.
        collapsed = canonical_action_state(raw_label) if raw_label else "WATCH / RESEARCH NEEDED"
        status, reason, display = _CANONICAL_STATUS_MAP.get(
            collapsed, ("WATCH", "watch_research_needed", "watch / research needed")
        )

    # Stop-breach outranks softer states (Execution Board doctrine).
    if below_stop:
        status, reason, display = "BELOW_STOP", "below_stop", "below stop — exit/repair"

    # A healthy/ready setup trading above its entry band is a distinct decision:
    # do not chase here, but the name is not broken. Only applies to ready-ish
    # states, never to stop/repair/blocked.
    if status in {"DEPLOYABLE_NOW", "ALMOST_DEPLOYABLE"} and band_status in _ABOVE_BAND_VALUES:
        status, reason, display = "NO_CHASE", "no_chase_above_band", "in band setup but extended — no chase"

    record_authority = record.get("authority") if isinstance(record.get("authority"), dict) else {}
    authority = {
        **record_authority,
        "review_only": True,
        "paper_order_execution_allowed": False,
        "capital_deployment_approved": False,
        "trade_or_execution_approved": False,
    }

    return {
        "deployment_status": status,
        "status_reason": reason,
        "display_label": display,
        "raw_context": {
            "workflow_state": record.get("workflow_state"),
            "machine_state": record.get("machine_state") or record.get("deployment_state"),
            "action_state": record.get("action_state"),
            "surface_state": record.get("surface_state"),
            "base_surface_state": record.get("base_surface_state"),
            "band_status": record.get("band_status"),
            "below_stop": below_stop,
        },
        "authority": authority,
    }


def format_user_state(record: dict[str, Any]) -> str:
    """Compact user-facing rendering: `DEPLOYMENT_STATUS / status_reason / display_label`."""
    contract = deployment_contract(record)
    return f"{contract['deployment_status']} / {contract['status_reason']} / {contract['display_label']}"


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
