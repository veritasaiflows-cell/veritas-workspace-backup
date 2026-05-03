from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import load_json_artifact


WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT = TMP / "positioning-ranking.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load(name: str) -> Any | None:
    return load_json_artifact(TMP / name)


def bucket_from_action_state(action_state: str | None, deployment_state: str | None, below_stop: bool = False, earnings_blocked: bool = False) -> str:
    raw = f"{action_state or ''} {deployment_state or ''}".upper()
    if below_stop or "DO NOT TOUCH" in raw or "BELOW STOP" in raw:
        return "No-action"
    if "BLOCKED" in raw or earnings_blocked:
        return "Watch only"
    if "ALMOST" in raw:
        return "High priority"
    if "DEPLOYABLE" in raw:
        return "Highest priority"
    if "WATCH" in raw or "RESEARCH" in raw or "BENCH" in raw:
        return "Watch only"
    return "Secondary"


def score_bonus(trigger_rec: dict[str, Any], deployment_rec: dict[str, Any], regime_rec: dict[str, Any]) -> tuple[float, list[str]]:
    bonus = 0.0
    reasons: list[str] = []

    if trigger_rec.get("in_entry_band"):
        bonus += 2.0
        reasons.append("in entry band")
    elif deployment_rec.get("priority") == 2:
        bonus += 1.0
        reasons.append("near deployable zone")

    if trigger_rec.get("earnings_blocked"):
        bonus -= 4.0
        reasons.append("earnings blocked")

    days = trigger_rec.get("days_to_earnings")
    try:
        days_i = int(days)
    except Exception:
        days_i = None
    if days_i is not None and 0 <= days_i <= 7:
        bonus -= 2.0
        reasons.append("near earnings window")

    if trigger_rec.get("below_stop"):
        bonus -= 5.0
        reasons.append("below stop / broken")

    stance = str(regime_rec.get("stance", "")).lower()
    if "deployable" in stance:
        bonus += 1.0
        reasons.append("regime-score stance constructive")
    elif "blocked" in stance or "watch" in stance:
        bonus -= 1.0

    return bonus, reasons


def main() -> int:
    trigger = load("trigger-sheet.json") or {}
    deployment = load("deployment-check.json") or {}
    regime_scores = load("regime-scores.json") or {}

    trigger_map = {rec.get("ticker"): rec for rec in trigger.get("records", []) if rec.get("ticker")}
    deployment_map = {rec.get("ticker"): rec for rec in deployment.get("records", []) if rec.get("ticker")}
    regime_map = {rec.get("ticker"): rec for rec in regime_scores.get("records", []) if rec.get("ticker")}

    tickers = sorted(set(trigger_map) | set(deployment_map) | set(regime_map))
    rows: list[dict[str, Any]] = []
    for ticker in tickers:
        t = trigger_map.get(ticker, {})
        d = deployment_map.get(ticker, {})
        r = regime_map.get(ticker, {})
        base_total = float(r.get("total", 0) or 0)
        bonus, reasons = score_bonus(t, d, r)
        score = round(base_total + bonus, 2)
        priority_bucket = bucket_from_action_state(t.get("action_state"), t.get("deployment_state"), bool(t.get("below_stop")), bool(t.get("earnings_blocked")))
        rows.append(
            {
                "ticker": ticker,
                "priority_score": score,
                "priority_bucket": priority_bucket,
                "base_total": base_total,
                "score_bonus": bonus,
                "regime_fit": r.get("regime_fit"),
                "technical_posture_score": r.get("technical_posture"),
                "catalyst_risk_score": r.get("catalyst_risk"),
                "fundamental_conviction_score": r.get("fundamental_conviction"),
                "stance": r.get("stance") or t.get("action_state") or d.get("action_state"),
                "action_state": t.get("action_state") or d.get("action_state", ""),
                "deployment_priority": d.get("priority", ""),
                "days_to_earnings": t.get("days_to_earnings"),
                "in_entry_band": t.get("in_entry_band"),
                "earnings_blocked": t.get("earnings_blocked"),
                "below_stop": t.get("below_stop"),
                "portfolio_role": t.get("portfolio_role") or r.get("role", ""),
                "thesis_status": t.get("thesis_status") or r.get("thesis_status", ""),
                "why": t.get("why") or d.get("reason") or "",
                "ranking_notes": reasons,
            }
        )

    bucket_order = {
        "Highest priority": 0,
        "High priority": 1,
        "Secondary": 2,
        "Watch only": 3,
        "No-action": 4,
    }
    rows.sort(key=lambda rec: (bucket_order.get(rec["priority_bucket"], 99), -rec["priority_score"], rec["ticker"]))
    for idx, rec in enumerate(rows, start=1):
        rec["priority_rank"] = idx

    payload = {
        "generated_at_utc": utc_now_iso(),
        "status": "ok",
        "stale_after_hours": 24,
        "last_trading_day": trigger.get("last_trading_day") or deployment.get("last_trading_day") or regime_scores.get("last_trading_day"),
        "source_last_trading_day": {
            "trigger": trigger.get("last_trading_day"),
            "deployment": deployment.get("last_trading_day"),
            "regime_scores": regime_scores.get("last_trading_day"),
        },
        "scoring_regime": regime_scores.get("scoring_regime") or regime_scores.get("macro_regime", {}).get("label", ""),
        "records": rows,
    }
    OUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"status": "ok", "records": len(rows), "path": str(OUT)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
