#!/usr/bin/env python3
"""Compatibility cache over the active alert controller; no legacy data plane."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CONTROLLER = TMP / "alert-level-freshness-controller.json"
DIGEST = TMP / "finance-alert-os-digest.json"
OUT = TMP / "finance-cache-frontdoor.json"
SCHEMA = "veritas.alerts_os_cache_frontdoor.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_dict(path: Path) -> dict[str, Any]:
    value = load_json_artifact(path)
    return value if isinstance(value, dict) else {}


def build_payload(max_age_hours: float = 12.0) -> dict[str, Any]:
    del max_age_hours  # source freshness is owned by the controller, not re-derived here
    controller = load_dict(CONTROLLER)
    digest = load_dict(DIGEST)
    source_ok = (
        controller.get("status") == "ok"
        and isinstance(controller.get("rows"), list)
        and digest.get("status") in {"ok", "weekend_quiet", "duplicate_quiet", "sent"}
    )
    rows: list[dict[str, Any]] = []
    for source in controller.get("rows") or []:
        if not isinstance(source, dict):
            continue
        alert_state = str(source.get("alert_state") or "freshness_decay")
        rows.append({
            "ticker": source.get("ticker"),
            "alert_state": alert_state,
            "level_relationship_state": source.get("level_relationship_state"),
            "latest_price": source.get("latest_price"),
            "reference_low": source.get("reference_low"),
            "reference_high": source.get("reference_high"),
            "invalidation_threshold": source.get("invalidation_threshold"),
            "level_as_of_utc": source.get("level_as_of_utc"),
            "quote_as_of_utc": source.get("quote_as_of_utc"),
            "quote_data_date": source.get("quote_data_date"),
            "freshness_status": source.get("freshness_status"),
            "confidence": source.get("confidence"),
            "alert_fire_eligible": bool(source.get("alert_fire_eligible")),
            "reasons": source.get("reasons") if isinstance(source.get("reasons"), list) else [],
            "safe_to_answer_from_cache": source_ok and alert_state != "freshness_decay",
            "material_claim_requires_source_open": True,
            "review_only": True,
        })
    errors: list[str] = []
    if not source_ok:
        errors.append("active alert controller or digest is missing or not clean")
    status = "ok" if not errors else "blocked"
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "purpose": "thin read-only cache of active alert and recommendation proof",
        "source_artifacts": {
            "controller": "tmp/alert-level-freshness-controller.json",
            "digest": "tmp/finance-alert-os-digest.json",
        },
        "summary": {
            "ticker_count": len(rows),
            "cache_review_eligible_count": sum(1 for row in rows if row["safe_to_answer_from_cache"]),
            "fresh_intraday_alert_count": sum(1 for row in rows if row["alert_fire_eligible"]),
            "monitor_only_count": sum(1 for row in rows if row["alert_state"] == "monitor_only"),
        },
        "rows": rows,
        "authority_boundary": {
            "review_only": True,
            "writes_canon": False,
            "maintains_finance_state": False,
            "maintains_simulated_state": False,
            "capital_or_execution_authority": False,
            "owner_approval_inferred": False,
        },
        "validation": {"status": "ok" if not errors else "error", "errors": errors, "warnings": []},
    }


def row_by_ticker(payload: dict[str, Any], ticker: str) -> dict[str, Any]:
    key = ticker.upper()
    return next(
        (row for row in payload.get("rows") or [] if isinstance(row, dict) and str(row.get("ticker") or "").upper() == key),
        {},
    )


def load_or_build_payload(max_age_hours: float = 12.0, path: Path | None = None) -> dict[str, Any]:
    target = path or OUT
    cached = load_dict(target)
    if cached.get("schema") == SCHEMA and cached.get("status") == "ok":
        return cached
    return build_payload(max_age_hours=max_age_hours)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=OUT)
    sub = parser.add_subparsers(dest="command")
    ticker = sub.add_parser("ticker")
    ticker.add_argument("ticker")
    ticker.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    payload = build_payload()
    output = args.out if args.out.is_absolute() else ROOT / args.out
    if args.write:
        atomic_write_json(output, payload)
    shown: Any = row_by_ticker(payload, args.ticker) if args.command == "ticker" else payload
    print(json.dumps(shown, indent=2 if getattr(args, "pretty", False) else None, sort_keys=getattr(args, "pretty", False)))
    return 1 if args.validate and payload["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
