#!/usr/bin/env python3
"""Regression tests for SQL-first cron/preflight posture."""

from __future__ import annotations

from finance_intelligence_state import entry_stop_refs_packet
from finance_sql_canon_access import DEFAULT_DB as FINANCE_CANON_DB
from sql_first_consumer_wiring_preflight import (
    FORBIDDEN_RECURRING_SQL_CHURN_SCRIPTS,
    REQUIRED_SQL_SUPPORT_SCRIPTS,
    build_payload,
    chain_manifest_probe,
)


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []

    chain = chain_manifest_probe()
    expect(chain["status"] == "ok", f"chain probe blocked: {chain}", errors)
    for window, result in chain["windows"].items():
        expect(result["status"] == "ok", f"{window} status blocked: {result}", errors)
        expect(
            result["required_sql_support_scripts"] == REQUIRED_SQL_SUPPORT_SCRIPTS,
            f"{window} missing required SQL support scripts: {result}",
            errors,
        )
        expect(
            not set(result["forbidden_sql_churn_scripts"]) & FORBIDDEN_RECURRING_SQL_CHURN_SCRIPTS,
            f"{window} contains forbidden recurring SQL churn scripts: {result}",
            errors,
        )

    payload = build_payload(["NVDA"])
    expect(payload["status"] == "ready_for_on_demand_sql_support_mode", f"payload blocked: {payload['blockers']}", errors)
    expect(payload["checks"]["chain_manifest_green"] is True, "chain manifest should be green", errors)
    expect(payload["checks"]["entry_stop_probe_green"] is True, "entry stop probe should be green", errors)
    expect(payload["checks"]["router_probe_green"] is True, "router probe should be green", errors)

    canon_packet = entry_stop_refs_packet(db_path=FINANCE_CANON_DB, ticker="NVDA", limit=1)
    refs = canon_packet.get("entry_stop_refs") or []
    expect(canon_packet["status"] == "ok", f"canon entry-stop packet blocked: {canon_packet}", errors)
    expect(len(refs) == 1, f"expected one canon reference row: {canon_packet}", errors)
    if refs:
        expect(
            refs[0].get("reference_source_surface") == "state/finance/finance-canon.sqlite:reference_levels",
            f"durable reference_levels fallback not used: {refs[0]}",
            errors,
        )
        expect(refs[0].get("entry_band_low") is not None, f"missing low reference: {refs[0]}", errors)
        expect(refs[0].get("entry_band_high") is not None, f"missing high reference: {refs[0]}", errors)
        expect(refs[0].get("stop_or_invalidation") is not None, f"missing invalidation reference: {refs[0]}", errors)

    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: SQL-first cron/preflight posture is green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
