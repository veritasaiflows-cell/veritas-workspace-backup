from __future__ import annotations

from typing import Any


def _text(value: Any, fallback: str = "?") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def format_delta_change(change: dict[str, Any]) -> str:
    change_type = _text(change.get("type"), "change_detected")
    ticker = _text(change.get("ticker"), "")
    source = _text(change.get("source"), "")

    if change_type == "new_ticker" and ticker:
        return f"**{ticker}** — added to the tracked set"
    if change_type == "action_state_change" and ticker:
        return f"**{ticker}** — action state {_text(change.get('from'))} → {_text(change.get('to'))}"
    if change_type == "below_stop_entered" and ticker:
        return f"**{ticker}** — entered below-stop"
    if change_type in {"below_stop_exited", "below_stop_recovered"} and ticker:
        return f"**{ticker}** — recovered above stop"
    if change_type == "new_blocker" and ticker:
        return f"**{ticker}** — new blocker surfaced"
    if change_type == "blocker_cleared" and ticker:
        return f"**{ticker}** — blocker cleared"
    if change_type == "exited_band" and ticker:
        return f"**{ticker}** — exited prior entry band"
    if change_type == "entered_band" and ticker:
        return f"**{ticker}** — entered entry band"
    if change_type == "earnings_date_change" and ticker:
        return f"**{ticker}** — earnings date {_text(change.get('from'))} → {_text(change.get('to'))}"
    if change_type == "source_status_change" and source:
        return f"**{source}** — source status {_text(change.get('from'))} → {_text(change.get('to'))}"
    if change_type == "exec_freshness_change":
        return f"**Execution freshness** — {_text(change.get('from'))} → {_text(change.get('to'))}"
    if ticker:
        return f"**{ticker}** — {change_type}"
    if source:
        return f"**{source}** — {change_type}"
    return f"**System** — {change_type}"
