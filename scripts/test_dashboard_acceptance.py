from __future__ import annotations

import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable

from generate_dashboard import TMP, build_payload, compute_delta, inject_into_template, load_sources, write_json
import macro_regime_refresh
import market_state_refresh
import policy_expectations_refresh

OUT_REPORT = TMP / "dashboard-acceptance-report.json"
TARGET_FILES = [
    TMP / "market-state.json",
    TMP / "technical-refresh.json",
    TMP / "deployment-check.json",
    TMP / "earnings-calendar.json",
    TMP / "portfolio-config.json",
    TMP / "policy-expectations.json",
    TMP / "credit-spreads.json",
    TMP / "breadth-state.json",
    TMP / "macro-regime.json",
]


@contextmanager
def preserved_tmp_files() -> Any:
    original = {path: path.read_text(encoding="utf-8") for path in TARGET_FILES if path.exists()}
    try:
        yield
    finally:
        for path, content in original.items():
            path.write_text(content, encoding="utf-8")


@contextmanager
def patched_attrs(obj: Any, **replacements: Any) -> Any:
    missing = object()
    original = {name: getattr(obj, name, missing) for name in replacements}
    try:
        for name, value in replacements.items():
            setattr(obj, name, value)
        yield
    finally:
        for name, value in original.items():
            if value is missing:
                delattr(obj, name)
            else:
                setattr(obj, name, value)



def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))



def write_source(name: str, payload: dict[str, Any]) -> None:
    mapping = {
        "market": TMP / "market-state.json",
        "technical": TMP / "technical-refresh.json",
        "deployment": TMP / "deployment-check.json",
        "earnings": TMP / "earnings-calendar.json",
        "portfolio": TMP / "portfolio-config.json",
        "policy": TMP / "policy-expectations.json",
        "credit": TMP / "credit-spreads.json",
        "breadth": TMP / "breadth-state.json",
    }
    write_json(mapping[name], payload)



def run_case(base_sources: dict[str, dict[str, Any]], name: str, mutator: Callable[[dict[str, dict[str, Any]]], None], expectations: Callable[[dict[str, Any]], list[str]]) -> dict[str, Any]:
    local = {k: copy.deepcopy(v) if v is not None else None for k, v in base_sources.items()}
    mutator(local)
    for source_name, payload in local.items():
        if payload is not None:
            write_source(source_name, payload)
    built = build_payload(load_sources())
    errors = expectations(built)
    return {
        "name": name,
        "passed": len(errors) == 0,
        "errors": errors,
        "exec_freshness": built.get("exec_freshness"),
        "validation": built.get("validation", {}).get("summary", {}),
        "trust_summary": built.get("trust", {}).get("summary"),
    }



def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _stub_last_close(_ticker: str) -> tuple[float | None, str | None]:
    return 100.0, "2026-05-01"


def _stub_fred_latest(_series_id: str, api_key: str | None = None, timeout: int = 20) -> tuple[float | None, str | None, str | None]:
    del api_key, timeout
    return 4.0, "2026-05-01", None


def _stub_snapshot(ticker: str) -> dict[str, Any]:
    base_price = {
        "ES=F": 5050.0,
        "NQ=F": 17750.0,
        "SPY": 500.0,
        "XLI": 120.0,
        "XLF": 40.0,
        "XLK": 210.0,
        "XLE": 95.0,
        "ETN": 300.0,
        "JPM": 200.0,
        "NVDA": 150.0,
    }.get(ticker, 100.0)
    prev = round(base_price * 0.99, 4)
    return {
        "last_price": base_price,
        "previous_close": prev,
        "regular_market_previous_close": prev,
        "change": round(base_price - prev, 4),
        "change_pct": round(((base_price - prev) / prev) * 100, 4) if prev else None,
        "open": base_price,
        "day_high": round(base_price * 1.01, 4),
        "day_low": round(base_price * 0.99, 4),
        "volume": 1000,
        "pre_market_price": None,
        "pre_market_change_pct": None,
        "pre_market_as_of": None,
        "market_phase": "regular",
        "source": "acceptance stub",
        "available": True,
        "note": None,
    }


def run_stubbed_market_state_refresh() -> dict[str, Any]:
    with patched_attrs(
        market_state_refresh,
        fetch_last_close=_stub_last_close,
        fetch_fred_latest=_stub_fred_latest,
        fetch_snapshot=_stub_snapshot,
    ):
        market_state_refresh.main()
    return read_json(TMP / "market-state.json")


def run_macro_regime_refresh() -> dict[str, Any]:
    macro_regime_refresh.main()
    return read_json(TMP / "macro-regime.json")



def case_missing_market_field(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expect(payload["exec_freshness"] == "partial", f"expected partial, got {payload['exec_freshness']}", errors)
    market = next(item for item in payload["trust"]["sources"] if item["label"] == "Market")
    expect(market["status"] == "partial", f"expected market partial, got {market['status']}", errors)
    expect(any("missing required fields" in issue for issue in market["issues"]), "missing-field issue not surfaced", errors)
    expect(payload["market"]["vix"] is None, "missing VIX should remain None, not fake zero", errors)
    return errors



def case_partial_macro_feed(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    market = next(item for item in payload["trust"]["sources"] if item["label"] == "Market")
    expect(payload["exec_freshness"] == "partial", f"expected partial, got {payload['exec_freshness']}", errors)
    expect(market["status"] == "partial", f"expected market partial, got {market['status']}", errors)
    expect(any("upstream status=partial" == issue for issue in market["issues"]), "partial upstream status not surfaced", errors)
    return errors


def case_market_sectors_invalid_shape(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    market = next(item for item in payload["trust"]["sources"] if item["label"] == "Market")
    warning_codes = {w["code"] for w in payload["validation"]["warnings"]}
    expect(payload["exec_freshness"] == "partial", f"expected partial, got {payload['exec_freshness']}", errors)
    expect(market["status"] == "partial", f"expected market partial, got {market['status']}", errors)
    expect(any("market-state.data.sectors" in issue for issue in market["issues"]), "market sectors shape issue not surfaced", errors)
    expect("market_sectors_invalid_shape" in warning_codes, "market_sectors_invalid_shape warning missing", errors)
    expect(payload["sectors_relative"] == [], f"expected empty sectors_relative, got {payload['sectors_relative']}", errors)
    return errors


def case_market_state_missing_policy_artifact() -> tuple[str, list[str]]:
    name = "market_state_missing_policy_artifact"
    errors: list[str] = []
    with preserved_tmp_files():
        policy_path = TMP / "policy-expectations.json"
        if policy_path.exists():
            policy_path.unlink()

        market_payload = run_stubbed_market_state_refresh()
        fed = market_payload["data"]["fed"]
        expect(fed["target_low"] is None, "missing policy artifact should leave fed.target_low null", errors)
        expect(fed["target_high"] is None, "missing policy artifact should leave fed.target_high null", errors)
        expect(fed["cut_probability_next_meeting"] is None, "missing policy artifact should leave cut probability null", errors)
        expect(
            any("Policy expectations artifact is missing" in warning for warning in market_payload.get("warnings", [])),
            "missing policy artifact warning not surfaced in market-state.json",
            errors,
        )

        dashboard_payload = build_payload(load_sources())
        market_source = next(item for item in dashboard_payload["trust"]["sources"] if item["label"] == "Market")
        policy_source = next(item for item in dashboard_payload["trust"]["sources"] if item["label"] == "Policy expectations")
        expect(dashboard_payload["exec_freshness"] == "partial", f"expected partial exec_freshness, got {dashboard_payload['exec_freshness']}", errors)
        expect(market_source["status"] == "partial", f"expected market source partial, got {market_source['status']}", errors)
        expect(policy_source["status"] == "missing", f"expected policy source missing, got {policy_source['status']}", errors)
    return name, errors


def case_policy_fail_closed_expired_target() -> tuple[str, list[str]]:
    name = "policy_fail_closed_expired_target"
    errors: list[str] = []
    with preserved_tmp_files():
        with patched_attrs(
            policy_expectations_refresh,
            fetch_adjacent_fomc_dates=lambda reference_date=None, timeout=20: ("2026-06-17", "2026-07-29", None),
            fetch_fedwatch_implied_rate=lambda next_fomc_zq_ticker, timeout=15: (3.50, "stub policy source", None, "primary"),
            CURRENT_TARGET_AUTO_SOURCE=False,
            CURRENT_TARGET_LOW=3.50,
            CURRENT_TARGET_HIGH=3.75,
            CURRENT_TARGET_DATE="2026-04-29",
            CURRENT_TARGET_CONFIRMED=True,
        ):
            policy_expectations_refresh.main()

        policy_payload = read_json(TMP / "policy-expectations.json")
        current_target = policy_payload["data"]["current_target_range"]
        next_fomc = policy_payload["data"]["next_fomc"]
        next_two = policy_payload["data"]["next_two_meetings"]

        expect(policy_payload["status"] == "partial", f"expected policy artifact status partial, got {policy_payload['status']}", errors)
        expect(current_target["low"] is None and current_target["high"] is None, "expired target range should be nulled fail-closed", errors)
        expect(current_target["confirmed"] is False, "expired target range should mark confirmed=false", errors)
        expect(bool(current_target.get("invalid_reason")), "expired target range should carry invalid_reason", errors)
        expect(next_fomc["distribution"] == [], f"expired target range should clear distribution, got {next_fomc['distribution']}", errors)
        expect(next_fomc["implied_rate"] is None, "expired target range should not publish implied_rate as usable next-step output", errors)
        expect(next_two and next_two[0]["cut_probability"] is None, "expired target range should clear cut_probability in next_two_meetings", errors)

        market_payload = run_stubbed_market_state_refresh()
        fed = market_payload["data"]["fed"]
        expect(fed["target_low"] is None and fed["target_high"] is None, "market-state should carry null Fed bounds for expired target range", errors)
        expect(fed["target_invalid_reason"] == current_target.get("invalid_reason"), "market-state should preserve policy invalid_reason", errors)
        expect(fed["cut_probability_next_meeting"] is None, "market-state should not retain cut probability from invalid target range", errors)

        dashboard_payload = build_payload(load_sources())
        market_source = next(item for item in dashboard_payload["trust"]["sources"] if item["label"] == "Market")
        policy_source = next(item for item in dashboard_payload["trust"]["sources"] if item["label"] == "Policy expectations")
        warning_codes = {item["code"] for item in dashboard_payload["validation"]["warnings"]}
        expect(dashboard_payload["exec_freshness"] == "partial", f"expected partial exec_freshness, got {dashboard_payload['exec_freshness']}", errors)
        expect(market_source["status"] == "partial", f"expected market source partial, got {market_source['status']}", errors)
        expect(policy_source["status"] == "partial", f"expected policy source partial, got {policy_source['status']}", errors)
        expect("policy_expectations_partial" in warning_codes, "dashboard validation should flag policy_expectations_partial", errors)
    return name, errors


def case_dashboard_policy_manual_remediation_path() -> tuple[str, list[str]]:
    name = "dashboard_policy_manual_remediation_path"
    errors: list[str] = []
    base_sources = load_sources()
    sources = {k: copy.deepcopy(v) if v is not None else None for k, v in base_sources.items()}
    sources["policy"] = None
    sources["market"]["data"]["fed"]["manual_update_required"] = True
    payload = build_payload(sources)
    fed_dep = next((dep for dep in payload["trust"]["manual_dependencies"] if dep["label"] == "Fed target range"), None)
    expect(fed_dep is not None, "Fed target range dependency missing from dashboard payload", errors)
    if fed_dep is not None:
        expect(
            "scripts/policy_expectations_refresh.py" in fed_dep["detail"],
            f"Fed target range remediation points at wrong file: {fed_dep['detail']}",
            errors,
        )
    return name, errors


def case_macro_regime_policy_distribution_shape_guard() -> tuple[str, list[str]]:
    name = "macro_regime_policy_distribution_shape_guard"
    errors: list[str] = []
    with preserved_tmp_files():
        base_sources = load_sources()
        local = {k: copy.deepcopy(v) if v is not None else None for k, v in base_sources.items()}
        local["policy"]["data"]["next_fomc"]["distribution"] = ["bad-item"]
        write_source("policy", local["policy"])
        write_source("credit", local["credit"])
        write_source("breadth", local["breadth"])

        macro_payload = run_macro_regime_refresh()
        expect(macro_payload["status"] == "partial", f"expected partial macro status, got {macro_payload['status']}", errors)
        expect(macro_payload["pillars"]["policy"]["key"] == "unknown", f"expected unknown policy pillar, got {macro_payload['pillars']['policy']['key']}", errors)
        expect(macro_payload["pillars"]["policy"]["hold_probability"] is None, "malformed distribution should clear hold_probability", errors)
        expect(
            any("policy-expectations.data.next_fomc.distribution" in warning for warning in macro_payload.get("warnings", [])),
            "policy distribution shape warning not surfaced",
            errors,
        )

        safe_sources = load_sources()
        safe_sources["policy"] = base_sources["policy"]
        safe_sources["credit"] = base_sources["credit"]
        safe_sources["breadth"] = base_sources["breadth"]
        dashboard_payload = build_payload(safe_sources)
        expect(dashboard_payload["macro_regime"]["status"] == "partial", f"dashboard should carry partial macro status, got {dashboard_payload['macro_regime']['status']}", errors)
    return name, errors


def case_macro_regime_credit_shape_guard() -> tuple[str, list[str]]:
    name = "macro_regime_credit_shape_guard"
    errors: list[str] = []
    with preserved_tmp_files():
        base_sources = load_sources()
        local = {k: copy.deepcopy(v) if v is not None else None for k, v in base_sources.items()}
        local["credit"]["data"]["high_yield_oas"] = ["bad-block"]
        local["credit"]["data"]["investment_grade_oas"] = {"value": "oops"}
        local["credit"]["data"]["stress_regime"] = {"bad": True}
        write_source("policy", local["policy"])
        write_source("credit", local["credit"])
        write_source("breadth", local["breadth"])

        macro_payload = run_macro_regime_refresh()
        expect(macro_payload["status"] == "partial", f"expected partial macro status, got {macro_payload['status']}", errors)
        expect(macro_payload["pillars"]["credit"]["key"] == "unknown", f"expected unknown credit pillar, got {macro_payload['pillars']['credit']['key']}", errors)
        expect(macro_payload["pillars"]["credit"]["hy_oas"] is None, "malformed HY OAS block should clear hy_oas", errors)
        expect(macro_payload["pillars"]["credit"]["stress_regime"] is None, "malformed stress_regime should clear stress_regime", errors)
        expect(
            any("credit-spreads.data.high_yield_oas" in warning or "credit-spreads.data.stress_regime" in warning for warning in macro_payload.get("warnings", [])),
            "credit shape warning not surfaced",
            errors,
        )

        safe_sources = load_sources()
        safe_sources["policy"] = base_sources["policy"]
        safe_sources["credit"] = base_sources["credit"]
        safe_sources["breadth"] = base_sources["breadth"]
        dashboard_payload = build_payload(safe_sources)
        expect(dashboard_payload["macro_regime"]["status"] == "partial", f"dashboard should carry partial macro status, got {dashboard_payload['macro_regime']['status']}", errors)
    return name, errors


def case_macro_regime_breadth_shape_guard() -> tuple[str, list[str]]:
    name = "macro_regime_breadth_shape_guard"
    errors: list[str] = []
    with preserved_tmp_files():
        base_sources = load_sources()
        local = {k: copy.deepcopy(v) if v is not None else None for k, v in base_sources.items()}
        local["breadth"]["data"]["major_index_breadth"] = ["bad-block"]
        local["breadth"]["data"]["sector_participation"] = "bad-block"
        local["breadth"]["data"]["equal_weight_vs_cap_weight"] = ["bad-block"]
        write_source("policy", local["policy"])
        write_source("credit", local["credit"])
        write_source("breadth", local["breadth"])

        macro_payload = run_macro_regime_refresh()
        expect(macro_payload["status"] == "partial", f"expected partial macro status, got {macro_payload['status']}", errors)
        expect(macro_payload["pillars"]["breadth"]["key"] == "unknown", f"expected unknown breadth pillar, got {macro_payload['pillars']['breadth']['key']}", errors)
        expect(macro_payload["pillars"]["breadth"]["breadth_regime"] is None, "malformed breadth block should clear breadth_regime", errors)
        expect(
            any("breadth-state.data.major_index_breadth" in warning or "breadth-state.data.sector_participation" in warning for warning in macro_payload.get("warnings", [])),
            "breadth shape warning not surfaced",
            errors,
        )

        safe_sources = load_sources()
        safe_sources["policy"] = base_sources["policy"]
        safe_sources["credit"] = base_sources["credit"]
        safe_sources["breadth"] = base_sources["breadth"]
        dashboard_payload = build_payload(safe_sources)
        expect(dashboard_payload["macro_regime"]["status"] == "partial", f"dashboard should carry partial macro status, got {dashboard_payload['macro_regime']['status']}", errors)
    return name, errors



def case_stale_source(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    market = next(item for item in payload["trust"]["sources"] if item["label"] == "Market")
    expect(payload["exec_freshness"] == "stale", f"expected stale, got {payload['exec_freshness']}", errors)
    expect(market["status"] == "stale", f"expected market stale, got {market['status']}", errors)
    expect(any("exceeds" in issue for issue in market["issues"]), "staleness issue not surfaced", errors)
    return errors



def case_contradiction(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    summary = payload["validation"]["summary"]
    codes = {w["code"] for w in payload["validation"]["warnings"]}
    expect(summary["critical"] >= 1, f"expected at least 1 critical contradiction, got {summary['critical']}", errors)
    expect("entry_band_mismatch" in codes, "entry_band_mismatch not flagged", errors)
    return errors



def case_earnings_date_change(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    deps = payload["trust"]["manual_dependencies"]
    warnings = {w["code"] for w in payload["validation"]["warnings"]}
    expect(any(dep["label"] == "MSFT" for dep in deps), "MSFT date-change dependency not surfaced", errors)
    expect("timing_sensitive_earnings_dates" in warnings, "timing-sensitive earnings warning missing", errors)
    return errors



def case_payload_shape_contract() -> tuple[str, list[str]]:
    """Lock the payload-shape contract that the dashboard view layer depends on.

    Catches silent breakage where a payload field gets renamed or dropped and
    the JS module would render blanks. Mirrors the shape validator in
    dashboard_payload._validate_payload_shape but enforces it as a hard
    pass/fail so the morning/post-close chain stops the bad build before it
    reaches the user.
    """
    name = "payload_shape_contract"
    errors: list[str] = []
    payload = build_payload(load_sources())

    ta = payload.get("today_action") or {}
    for bucket in ("deployable", "almost", "earningsPending", "riskOff"):
        expect(bucket in ta, f"today_action missing bucket '{bucket}'", errors)

    for bucket_key in ("deployable", "almost"):
        for card in ta.get(bucket_key) or []:
            for field in ("ticker", "close", "entryBand", "stop", "posture", "bandStatus"):
                expect(
                    field in card,
                    f"today_action.{bucket_key}[{card.get('ticker','?')}] missing field '{field}'",
                    errors,
                )
                if errors:
                    break
            if errors:
                break
        if errors:
            break

    drs = payload.get("deployment_records") or []
    expect(len(drs) > 0, "deployment_records is empty — Phase 4 join may be broken", errors)
    if drs:
        sample = drs[0]
        for field in (
            "ticker", "state", "close", "bandLabel", "bandLow", "bandHigh",
            "bandStatus", "bandPositionPct", "stop", "stopDistPct", "posture",
        ):
            expect(field in sample, f"deployment_records[0] missing field '{field}'", errors)

    technical = payload.get("technical") or []
    expect(len(technical) > 0, "technical payload is empty — technical table cannot render", errors)
    if technical:
        sample = technical[0]
        for field in (
            "ticker", "close", "entry", "stop", "actionState", "actionReason",
            "triggerToday", "coverageLane", "coverageLaneLabel",
        ):
            expect(field in sample, f"technical[0] missing field '{field}'", errors)

    macro_regime = payload.get("macro_regime") or {}
    expect(bool(macro_regime.get("regime_label")), "macro_regime.regime_label missing — Macro tab banner blank", errors)
    expect(bool(macro_regime.get("policy_pillar")), "macro_regime.policy_pillar missing", errors)
    expect(bool(macro_regime.get("credit_pillar")), "macro_regime.credit_pillar missing", errors)
    expect(bool(macro_regime.get("breadth_pillar")), "macro_regime.breadth_pillar missing", errors)

    sectors_relative = payload.get("sectors_relative") or []
    expect(len(sectors_relative) > 0, "sectors_relative empty — sector RS card blank", errors)

    pe_window = (payload.get("post_earnings") or {}).get("window") or {}
    expect("back_trading_days" in pe_window, "post_earnings.window.back_trading_days missing — Phase 6 not applied", errors)

    return name, errors


def case_state_transition(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    record = next(item for item in payload["technical"] if item["ticker"] == "ETN")
    expect(record["inBand"] is True, "ETN should be in band for transition case", errors)
    expect(record["triggerToday"] is True, "ETN should become triggerToday in coherent in-band state", errors)
    expect(record["actionState"] == "ALMOST", f"expected ALMOST, got {record['actionState']}", errors)
    expect(payload["validation"]["summary"]["critical"] == 0, "coherent state transition should not create critical contradiction", errors)
    return errors


def case_workflow8_command_center_alignment() -> tuple[str, list[str]]:
    name = "workflow8_command_center_alignment"
    errors: list[str] = []
    payload = build_payload(load_sources())
    technical = {row["ticker"]: row for row in payload.get("technical") or []}
    deployment = {row["ticker"]: row for row in payload.get("deployment_records") or []}
    summary = payload.get("deployment_summary") or {}

    for ticker in ("GOOG", "MSFT"):
        expect(technical.get(ticker, {}).get("actionState") == "ALMOST", f"{ticker} technical state should be ALMOST", errors)
        expect(deployment.get(ticker, {}).get("state") == "ALMOST", f"{ticker} deployment state should be ALMOST", errors)

    expect(sorted(summary.get("almost") or []) == ["ETN", "GOOG", "MSFT"], f"deployment_summary.almost should be ETN/GOOG/MSFT, got {summary.get('almost')}", errors)
    expect(summary.get("blocked") == [], f"deployment_summary.blocked should be empty after GOOG/MSFT correction, got {summary.get('blocked')}", errors)

    for ticker in ("BRK.B", "XOM"):
        expect(technical.get(ticker, {}).get("actionState") == "BENCH", f"{ticker} should stay BENCH", errors)
        expect(technical.get(ticker, {}).get("triggerToday") is False, f"{ticker} should not show triggerToday while BENCH", errors)

    vrt_reason = str(technical.get("VRT", {}).get("actionReason") or "")
    expect(technical.get("VRT", {}).get("coverageLane") == "execution", f"VRT coverageLane should be execution, got {technical.get('VRT', {}).get('coverageLane')}", errors)
    expect("levels are defined" in vrt_reason.lower() or "watch-only" in vrt_reason.lower(), f"VRT reason should acknowledge defined levels/watch-only posture, got {vrt_reason!r}", errors)

    for ticker in ("CVX", "PLTR", "LNG"):
        row = technical.get(ticker, {})
        reason = str(row.get("actionReason") or "")
        expect(row.get("coverageLane") == "watch", f"{ticker} coverageLane should be watch, got {row.get('coverageLane')}", errors)
        expect(row.get("triggerToday") is False, f"{ticker} should not show triggerToday on the watch lane", errors)
        expect(
            "execution-board entitlement" in reason.lower() or "execution-board scope" in reason.lower(),
            f"{ticker} reason should explain the lane constraint, got {reason!r}",
            errors,
        )

    rtx = technical.get("RTX", {})
    rtx_reason = str(rtx.get("actionReason") or "")
    expect(rtx.get("coverageLane") == "watch", f"RTX coverageLane should be watch, got {rtx.get('coverageLane')}", errors)
    expect(rtx.get("triggerToday") is False, f"RTX should not show triggerToday", errors)
    expect(
        "watch-lane" in rtx_reason.lower() or "execution-board entitled" in rtx_reason.lower(),
        f"RTX reason should keep explicit lane language even below stop, got {rtx_reason!r}",
        errors,
    )

    return name, errors



def case_delta_summary_honesty() -> tuple[str, list[str]]:
    """Regression case: compute_delta() must never claim 'No material changes'
    while reporting non-empty changes (delta-summary defect from 2026-04-25 audit).
    Builds a synthetic prior payload missing one ticker so a new_ticker change
    appears, then checks the summary string is honest.
    """
    name = "delta_summary_honesty"
    errors: list[str] = []
    payload = build_payload(load_sources())
    # Force a synthetic prior with one fewer ticker so new_ticker fires
    if not payload["technical"]:
        errors.append("no technical records available to build delta case")
        return name, errors
    dropped = payload["technical"][0]["ticker"]
    prior = copy.deepcopy(payload)
    prior["technical"] = [t for t in prior["technical"] if t["ticker"] != dropped]
    delta = compute_delta(payload, prior)
    has_new_ticker = any(c["type"] == "new_ticker" and c["ticker"] == dropped for c in delta["changes"])
    expect(has_new_ticker, f"expected new_ticker change for {dropped}, got {delta['changes']}", errors)
    expect(
        "No material changes" not in delta["summary"],
        f"delta summary lied: changes={len(delta['changes'])} but summary says {delta['summary']!r}",
        errors,
    )
    expect(
        "new ticker" in delta["summary"].lower(),
        f"delta summary should mention new ticker, got {delta['summary']!r}",
        errors,
    )
    return name, errors



def case_earnings_new_alert_visibility() -> tuple[str, list[str]]:
    """Regression case: NEW watchlist_alerts must surface as manual_dependencies
    (not just DATE CHANGED). Defect from 2026-04-25 audit section 3.2.
    """
    name = "earnings_new_alert_visibility"
    errors: list[str] = []
    base_sources = load_sources()
    sources = {k: copy.deepcopy(v) if v is not None else None for k, v in base_sources.items()}
    sources["earnings"]["watchlist_alerts"] = sources["earnings"].get("watchlist_alerts", []) + [
        "TESTNEW: NEW -- not in vault watchlist: 2026-08-01"
    ]
    payload = build_payload(sources)
    deps = payload["trust"]["manual_dependencies"]
    has_test = any(dep["label"] == "TESTNEW" for dep in deps)
    expect(has_test, f"NEW alert TESTNEW not surfaced as manual dependency. Deps: {[d['label'] for d in deps]}", errors)
    test_dep = next((dep for dep in deps if dep["label"] == "TESTNEW"), None)
    if test_dep is not None:
        expect(
            test_dep["status"] == "unconfirmed_addition",
            f"NEW alert should have status unconfirmed_addition, got {test_dep['status']}",
            errors,
        )
        expect(
            "NEW" in test_dep["detail"],
            f"NEW alert detail should preserve original text, got {test_dep['detail']!r}",
            errors,
        )
    return name, errors




def _mutate_state_transition(s: dict[str, Any]) -> None:
    """
    Set ETN into a fully coherent in-band state so the validator does not fire
    entry_band_mismatch and the dashboard has enough source health to surface
    triggerToday=True.
    """
    etn_tech = next(r for r in s["technical"]["records"] if r["ticker"] == "ETN")
    close = etn_tech.get("close") or 300.0
    band_low  = round(close * 0.98, 2)
    band_high = round(close * 1.02, 2)
    next(b for t, b in s["portfolio"]["entry_bands"].items() if t == "ETN").update(
        {"low": band_low, "high": band_high, "label": f"{band_low}-{band_high}"}
    )
    etn_tech.update({"in_entry_band": True, "earnings_blocked": False, "below_stop": False})
    next(r for r in s["deployment"]["records"] if r["ticker"] == "ETN").update(
        {"action_state": "ALMOST", "reason": "in band with constructive posture", "priority": 2}
    )

    for source_name in ("market", "policy", "credit", "breadth"):
        if isinstance(s.get(source_name), dict):
            s[source_name]["status"] = "ok"
            s[source_name]["warnings"] = []

    market_fed = (((s.get("market") or {}).get("data") or {}).get("fed") or {})
    market_fed.update({
        "target_low": 3.5,
        "target_high": 3.75,
        "cut_probability_next_meeting": 0.04,
        "manual_update_required": False,
        "target_invalid_reason": None,
    })

    market_meta = (s.get("market") or {}).setdefault("meta", {})
    market_meta["generated_at_utc"] = "2026-05-04T13:23:00+00:00"

    policy_data = (s.get("policy") or {}).setdefault("data", {})
    policy_data["current_target_range"] = {
        "low": 3.5,
        "high": 3.75,
        "as_of": "2026-05-01",
        "confirmed": True,
        "source": "acceptance stub",
        "invalid_reason": None,
    }
    policy_data["next_fomc"] = {
        "date": "2026-07-29",
        "days_until": 89,
        "distribution": [
            {"outcome": "hold", "probability": 0.96},
            {"outcome": "cut_25bp", "probability": 0.04},
        ],
        "implied_rate": 3.62,
    }
    (s.get("policy") or {}).setdefault("manual_dependencies", [])
    (s.get("policy") or {})["manual_dependencies"] = []
    (s.get("policy") or {})["generated_at_utc"] = "2026-05-04T13:23:00+00:00"


def main() -> int:
    results: list[dict[str, Any]] = []
    with preserved_tmp_files():
        base_sources = load_sources()
        results.append(run_case(
            base_sources,
            "missing_market_field",
            lambda s: s["market"]["data"]["volatility"].pop("vix", None),
            case_missing_market_field,
        ))
        results.append(run_case(
            base_sources,
            "partial_macro_feed",
            lambda s: s["market"].update({"status": "partial"}),
            case_partial_macro_feed,
        ))
        results.append(run_case(
            base_sources,
            "market_sectors_invalid_shape",
            lambda s: s["market"]["data"].update({"sectors": ["bad-block"]}),
            case_market_sectors_invalid_shape,
        ))
        results.append(run_case(
            base_sources,
            "stale_market_source",
            lambda s: s["market"].update({"generated_at_utc": "2026-04-20T00:00:00+00:00"}),
            case_stale_source,
        ))
        results.append(run_case(
            base_sources,
            "contradiction_entry_band",
            lambda s: next(r for r in s["technical"]["records"] if r["ticker"] == "ETN").update({"in_entry_band": True}),
            case_contradiction,
        ))
        results.append(run_case(
            base_sources,
            "earnings_date_change_visibility",
            lambda s: s["earnings"].update({
                "watchlist_alerts": s["earnings"].get("watchlist_alerts", []) + ["MSFT: DATE CHANGED -- vault has 2026-04-29, yfinance shows 2026-04-30"],
                "timing_sensitive_alerts": s["earnings"].get("timing_sensitive_alerts", []) + ["MSFT: DATE CHANGED -- vault has 2026-04-29, yfinance shows 2026-04-30"],
            }),
            case_earnings_date_change,
        ))
        results.append(run_case(
            base_sources,
            "state_transition_in_band_ready",
            _mutate_state_transition,
            case_state_transition,
        ))
        for case_fn in (
            case_market_state_missing_policy_artifact,
            case_policy_fail_closed_expired_target,
            case_dashboard_policy_manual_remediation_path,
            case_macro_regime_policy_distribution_shape_guard,
            case_macro_regime_credit_shape_guard,
            case_macro_regime_breadth_shape_guard,
        ):
            case_name, case_errors = case_fn()
            results.append({
                "name": case_name,
                "passed": len(case_errors) == 0,
                "errors": case_errors,
                "exec_freshness": None,
                "validation": {},
                "trust_summary": None,
            })

        # Sprint 1 regression cases (2026-04-25 audit Priority 1 fixes)
        # Sprint 2 regression case (2026-04-30 dashboard refresh): payload-shape contract
        for case_fn in (case_delta_summary_honesty, case_earnings_new_alert_visibility, case_payload_shape_contract, case_workflow8_command_center_alignment):
            case_name, case_errors = case_fn()
            results.append({
                "name": case_name,
                "passed": len(case_errors) == 0,
                "errors": case_errors,
                "exec_freshness": None,
                "validation": {},
                "trust_summary": None,
            })

    # Removed automatic HTML write. Gating belongs in the orchestration layer.
    passed = sum(1 for result in results if result["passed"])
    report = {
        "summary": {
            "passed": passed,
            "failed": len(results) - passed,
            "total": len(results),
            "all_passed": passed == len(results),
        },
        "results": results,
    }
    write_json(OUT_REPORT, report)
    print(json.dumps(report, indent=2))
    return 0 if report["summary"]["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
