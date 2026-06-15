from __future__ import annotations

import copy
import io
import json
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from board_state_contract import legacy_state
from generate_dashboard import TMP, build_payload, compute_delta, inject_into_template, load_sources, write_json
import dashboard_payload
import macro_regime_refresh
import market_state_refresh
import policy_expectations_refresh
import trigger_sheet_refresh
import deployment_readiness_surface
import workbook_export
import earnings_calendar_enrichment

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
    TMP / "fundamental-metrics-current.json",
    TMP / "fundamental-ir-reconciliation-packets.json",
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


def get_path(data: Any, dotted_path: str) -> Any:
    cur = data
    for part in dotted_path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur



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
        "fundamentals": TMP / "fundamental-metrics-current.json",
        "fundamental_ir": TMP / "fundamental-ir-reconciliation-packets.json",
    }
    write_json(mapping[name], payload)



def _quiet_call(fn: Callable[[], Any]) -> tuple[Any, str]:
    """Run noisy producers without leaking expected fixture warnings to stdout.

    Dashboard acceptance deliberately creates missing/degraded policy, macro,
    and deployment fixtures. Their console warnings are useful when the case
    fails, but noisy and misleading when the suite passes. Preserve them in the
    report only on failure instead of surfacing them as live runtime warnings.
    """
    buffer = io.StringIO()
    with redirect_stdout(buffer), redirect_stderr(buffer):
        result = fn()
    return result, buffer.getvalue()


def run_case(base_sources: dict[str, dict[str, Any]], name: str, mutator: Callable[[dict[str, dict[str, Any]]], None], expectations: Callable[[dict[str, Any]], list[str]]) -> dict[str, Any]:
    local = {k: copy.deepcopy(v) if v is not None else None for k, v in base_sources.items()}
    mutator(local)
    for source_name, payload in local.items():
        if payload is not None:
            write_source(source_name, payload)
    built, producer_output = _quiet_call(lambda: build_payload(load_sources()))
    errors = expectations(built)
    result = {
        "name": name,
        "passed": len(errors) == 0,
        "errors": errors,
        "exec_freshness": built.get("exec_freshness"),
        "validation": built.get("validation", {}).get("summary", {}),
        "trust_summary": built.get("trust", {}).get("summary"),
    }
    if errors and producer_output:
        result["producer_output_tail"] = producer_output[-4000:]
    return result


def restore_sources(base_sources: dict[str, dict[str, Any]]) -> None:
    for source_name, payload in base_sources.items():
        if payload is not None:
            write_source(source_name, copy.deepcopy(payload))



def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def _expected_capital_recommendation_tickers(daily_review: dict[str, Any]) -> set[str]:
    """Return the ticker set the Command Center should render for capital recs.

    The acceptance contract is not a fixed historical ticker list. The Command
    Center must mirror the current daily-review/capital-recommendation source
    while preserving owner-review authority. This keeps the test from failing
    when market state legitimately moves the queue from one ticker set to
    another.
    """
    source_path = daily_review.get("source_path")
    source = read_json(Path(source_path)) if source_path and Path(source_path).exists() else {}
    recommendations = source.get("capital_deployment_recommendations") if isinstance(source.get("capital_deployment_recommendations"), list) else []
    if not recommendations:
        review_objects = source.get("review_objects") if isinstance(source.get("review_objects"), list) else []
        recommendations = [obj for obj in review_objects if obj.get("object_type") == "capital_recommendation"]
    if not recommendations:
        review_objects = source.get("review_objects") if isinstance(source.get("review_objects"), list) else []
        recommendations = [obj for obj in review_objects if obj.get("recommended_action") and obj.get("owner_approval_required") is True]
    return {str(item.get("ticker") or item.get("ticker_or_macro_sleeve") or "").upper() for item in recommendations if item.get("ticker") or item.get("ticker_or_macro_sleeve")}


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
        _quiet_call(market_state_refresh.main)
    return read_json(TMP / "market-state.json")


def run_macro_regime_refresh() -> dict[str, Any]:
    _quiet_call(macro_regime_refresh.main)
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
        macro_freshness = market_payload.get("macro_freshness") or {}
        expect(fed["target_low"] is None, "missing policy artifact should leave fed.target_low null", errors)
        expect(fed["target_high"] is None, "missing policy artifact should leave fed.target_high null", errors)
        expect(fed["cut_probability_next_meeting"] is None, "missing policy artifact should leave cut probability null", errors)
        expect(macro_freshness.get("status") == "blocked", f"missing policy should produce blocked macro_freshness, got {macro_freshness.get('status')}", errors)
        expect(get_path(macro_freshness, "routing.macro_regime_safe") is False, "missing policy should mark macro regime unsafe", errors)
        expect("policy_expectations_refresh.py" in get_path(fed, "remediation.owner"), "missing policy remediation owner missing", errors)
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
        contract = policy_payload.get("freshness_contract") or {}

        expect(policy_payload["status"] == "partial", f"expected policy artifact status partial, got {policy_payload['status']}", errors)
        expect(policy_payload.get("freshness_status") == "blocked", f"expected blocked freshness_status, got {policy_payload.get('freshness_status')}", errors)
        expect(contract.get("hard_fail_closed") is True, "expired policy should hard fail closed", errors)
        expect(contract.get("safe_for_macro_regime") is False, "expired policy should be unsafe for macro regime", errors)
        expect("expired_or_invalid_target_range" in (contract.get("categories") or []), "expired policy category missing", errors)
        expect(current_target["low"] is None and current_target["high"] is None, "expired target range should be nulled fail-closed", errors)
        expect(current_target["confirmed"] is False, "expired target range should mark confirmed=false", errors)
        expect(bool(current_target.get("invalid_reason")), "expired target range should carry invalid_reason", errors)
        expect(next_fomc["distribution"] == [], f"expired target range should clear distribution, got {next_fomc['distribution']}", errors)
        expect(next_fomc["implied_rate"] is None, "expired target range should not publish implied_rate as usable next-step output", errors)
        expect(next_two and next_two[0]["cut_probability"] is None, "expired target range should clear cut_probability in next_two_meetings", errors)

        market_payload = run_stubbed_market_state_refresh()
        fed = market_payload["data"]["fed"]
        market_contract = market_payload.get("macro_freshness") or {}
        expect(fed["target_low"] is None and fed["target_high"] is None, "market-state should carry null Fed bounds for expired target range", errors)
        expect(fed["target_invalid_reason"] == current_target.get("invalid_reason"), "market-state should preserve policy invalid_reason", errors)
        expect(fed["cut_probability_next_meeting"] is None, "market-state should not retain cut probability from invalid target range", errors)
        expect(market_contract.get("status") == "blocked", f"market macro freshness should be blocked, got {market_contract.get('status')}", errors)

        dashboard_payload = build_payload(load_sources())
        market_source = next(item for item in dashboard_payload["trust"]["sources"] if item["label"] == "Market")
        policy_source = next(item for item in dashboard_payload["trust"]["sources"] if item["label"] == "Policy expectations")
        warning_codes = {item["code"] for item in dashboard_payload["validation"]["warnings"]}
        expect(dashboard_payload["exec_freshness"] == "partial", f"expected partial exec_freshness, got {dashboard_payload['exec_freshness']}", errors)
        expect(market_source["status"] == "partial", f"expected market source partial, got {market_source['status']}", errors)
        expect(policy_source["status"] == "partial", f"expected policy source partial, got {policy_source['status']}", errors)
        expect("policy_expectations_partial" in warning_codes, "dashboard validation should flag policy_expectations_partial", errors)
        partial_warning = next((item for item in dashboard_payload["validation"]["warnings"] if item["code"] == "policy_expectations_partial"), {})
        expect(get_path(partial_warning, "details.remediation.command") == "python scripts\\policy_expectations_refresh.py", "partial policy warning should carry exact remediation command", errors)
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
        expect(get_path(macro_payload, "freshness_contract.status") == "blocked", "invalid policy shape should produce blocked macro freshness contract", errors)
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
        expect(get_path(macro_payload, "freshness_contract.routing.regime_confidence") in {"low", "medium"}, "credit shape guard should expose regime confidence downgrade", errors)
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
        expect(get_path(macro_payload, "freshness_contract.routing.owner_action_required") is True, "breadth shape guard should route owner/action repair", errors)
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


def case_earnings_lifecycle_closeout_candidate() -> tuple[str, list[str]]:
    errors: list[str] = []
    config = {
        "earnings_date_watchlist": {
            "NVDA": {"date": "2026-05-20", "primary_confirmed": True},
            "MSFT": {"date": "2026-06-20", "primary_confirmed": True},
        },
        "tracked_universe": {
            "NVDA": {
                "last_earnings_date": "2026-05-20",
                "post_earnings_review_date": "2026-05-20",
                "post_earnings_review_confirmed": True,
            },
            "MSFT": {},
        },
    }
    records = [
        {"ticker": "NVDA", "next_earnings_date": "2026-05-20", "source": "yfinance", "date_source_class": "provider_estimate", "primary_confirmed": False},
        {"ticker": "MSFT", "next_earnings_date": "2026-06-20", "source": "yfinance", "date_source_class": "provider_estimate", "primary_confirmed": True},
    ]
    closeouts = earnings_calendar_enrichment.build_watchlist_lifecycle_closeouts(
        config=config,
        records=records,
        today=earnings_calendar_enrichment.date.fromisoformat("2026-05-23"),
    )
    earnings_calendar_enrichment.apply_closeout_hold_to_records(records, closeouts)
    expect([c.get("ticker") for c in closeouts] == ["NVDA"], f"expected only NVDA closeout candidate, got {closeouts}", errors)
    nvda = next(row for row in records if row["ticker"] == "NVDA")
    msft = next(row for row in records if row["ticker"] == "MSFT")
    expect(nvda.get("next_earnings_date") is None, "NVDA stale provider date should be held out after closeout", errors)
    expect(get_path(nvda, "lifecycle.status") == "post_event_review_confirmed_next_date_pending", f"NVDA lifecycle status missing: {nvda.get('lifecycle')}", errors)
    expect(msft.get("next_earnings_date") == "2026-06-20", "future watchlist date should remain active", errors)
    expect(get_path(closeouts[0], "authority.trade_or_account_action_allowed") is False, "closeout authority must not allow trade/account action", errors)
    return "earnings_lifecycle_closeout_candidate", errors



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
    for bucket in ("deployable", "promotionReview", "almost", "earningsPending", "riskOff"):
        expect(bucket in ta, f"today_action missing bucket '{bucket}'", errors)

    for bucket_key in ("deployable", "promotionReview", "almost"):
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
            "referenceBand", "executionBand",
        ):
            expect(field in sample, f"deployment_records[0] missing field '{field}'", errors)

    technical = payload.get("technical") or []
    expect(len(technical) > 0, "technical payload is empty — technical table cannot render", errors)
    if technical:
        sample = technical[0]
        for field in (
            "ticker", "close", "entry", "stop", "actionState", "actionReason",
            "triggerToday", "coverageLane", "coverageLaneLabel", "referenceBand", "executionBand",
        ):
            expect(field in sample, f"technical[0] missing field '{field}'", errors)

    reference_bands = payload.get("reference_bands") or {}
    expect((reference_bands.get("authority") or {}).get("reference_band_visibility_only") is True, "reference band payload must be visibility-only", errors)
    expect((reference_bands.get("authority") or {}).get("execution_band_mutation_allowed") is False, "reference band payload must not allow execution-band mutation", errors)
    ref_by_ticker = reference_bands.get("by_ticker") or {}
    expect(bool(ref_by_ticker), "reference_bands.by_ticker missing — Command Center would fall back to stale execution bands", errors)
    for ticker, band in ref_by_ticker.items():
        expect((band.get("authority") or {}).get("capitalActionAllowed") is False, f"{ticker} reference band must not allow capital action", errors)
        expect((band.get("authority") or {}).get("ownerApprovalInferred") is False, f"{ticker} reference band must not infer owner approval", errors)
        expect((band.get("authority") or {}).get("tradeOrAccountAuthority") is False, f"{ticker} reference band must not allow trade/account action", errors)
        if band.get("canonicalApplyEligible") is not True:
            expect("no execution entitlement" in str(band.get("authorityLabel") or "").lower(), f"{ticker} non-eligible reference band needs no-execution label", errors)
        if errors:
            break

    macro_regime = payload.get("macro_regime") or {}
    expect(bool(macro_regime.get("regime_label")), "macro_regime.regime_label missing — Macro tab banner blank", errors)
    expect(bool(macro_regime.get("policy_pillar")), "macro_regime.policy_pillar missing", errors)
    expect(bool(macro_regime.get("credit_pillar")), "macro_regime.credit_pillar missing", errors)
    expect(bool(macro_regime.get("breadth_pillar")), "macro_regime.breadth_pillar missing", errors)

    sectors_relative = payload.get("sectors_relative") or []
    expect(len(sectors_relative) > 0, "sectors_relative empty — sector RS card blank", errors)

    pe_window = (payload.get("post_earnings") or {}).get("window") or {}
    expect("back_trading_days" in pe_window, "post_earnings.window.back_trading_days missing — Phase 6 not applied", errors)

    dq = payload.get("decision_queue") or {}
    expect("daily_review" in dq, "decision_queue.daily_review missing", errors)
    expect("market_intelligence" in dq, "decision_queue.market_intelligence missing", errors)
    expect((dq.get("authority") or {}).get("owner_approval_required") is True, "decision queue must require owner approval", errors)

    wf = payload.get("workflow_focus") or {}
    top = wf.get("top_workflow") or {}
    expect(top.get("id") in {"WF63", "WF67"}, f"workflow_focus.top_workflow.id should be WF63 or WF67, got {top.get('id')!r}", errors)
    expect(top.get("paper_submit_allowed") is False, "workflow_focus paper_submit_allowed must be False", errors)
    expect(top.get("live_submit_allowed") is False, "workflow_focus live_submit_allowed must be False", errors)
    expect(bool(top.get("stop_lines")), "workflow_focus.top_workflow.stop_lines must be populated", errors)

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
    trigger_records = {row.get("ticker"): row for row in (read_json(TMP / "trigger-sheet.json").get("records") or []) if row.get("ticker")}

    etn_technical = technical.get("ETN", {})
    etn_deployment = deployment.get("ETN", {})
    etn_in_band = etn_technical.get("inBand") is True
    if etn_in_band:
        expect(etn_technical.get("actionState") == "DEPLOYABLE NOW", f"ETN in-band owner-approved setup should be DEPLOYABLE NOW, got {etn_technical.get('actionState')}", errors)
        expect(etn_deployment.get("state") == "DEPLOYABLE", f"ETN in-band owner-approved setup should be DEPLOYABLE, got {etn_deployment.get('state')}", errors)
    else:
        expect(etn_technical.get("actionState") == "ALMOST DEPLOYABLE", f"ETN outside live band should stay ALMOST DEPLOYABLE / no-chase, got {etn_technical.get('actionState')}", errors)
        expect(etn_deployment.get("state") == "ALMOST", f"ETN outside live band should stay ALMOST / no-chase, got {etn_deployment.get('state')}", errors)

    jpm_technical = technical.get("JPM", {})
    jpm_deployment = deployment.get("JPM", {})
    jpm_cards = [card for card in (payload.get("today_action") or {}).get("promotionReview") or [] if card.get("ticker") == "JPM"]
    jpm_below_stop = jpm_technical.get("belowStop") is True
    expect("JPM" not in (summary.get("deployable") or []), f"deployment_summary.deployable must not include JPM while below the formal trigger band, got {summary.get('deployable')}", errors)
    expect("JPM" not in (summary.get("promotion_review") or []), f"deployment_summary.promotion_review must not include JPM until formal-band reclaim/promotion, got {summary.get('promotion_review')}", errors)
    if jpm_below_stop:
        expect(jpm_technical.get("actionState") == "BELOW STOP", f"JPM technical state should resolve to BELOW STOP only when close < stop, got {jpm_technical.get('actionState')}", errors)
        expect(jpm_deployment.get("state") == "BELOW STOP", f"JPM deployment state should resolve to BELOW STOP only when close < stop, got {jpm_deployment.get('state')}", errors)
        expect("JPM" in (summary.get("below_stop") or []), f"deployment_summary.below_stop should include JPM when below stop, got {summary.get('below_stop')}", errors)
    else:
        expect(jpm_technical.get("actionState") == "ALMOST DEPLOYABLE", f"JPM above stop but below band should stay ALMOST DEPLOYABLE / trigger not live, got {jpm_technical.get('actionState')}", errors)
        expect(jpm_deployment.get("state") == "ALMOST", f"JPM above stop but below band should stay ALMOST, got {jpm_deployment.get('state')}", errors)
        expect("JPM" not in (summary.get("below_stop") or []), f"deployment_summary.below_stop should not include JPM unless close < stop, got {summary.get('below_stop')}", errors)
        expect("JPM" in (summary.get("almost") or []), f"deployment_summary.almost should include JPM while trigger is not live but stop is intact, got {summary.get('almost')}", errors)
    expect(not jpm_cards, f"today_action.promotionReview should not include JPM after formal-band resolution, got {jpm_cards}", errors)
    jpm_trigger = trigger_records.get("JPM") or {}
    jpm_band = jpm_trigger.get("entry_band") or {}
    expected_jpm_entry = jpm_band.get("label")
    expected_jpm_stop = f"{float(jpm_trigger.get('invalidation')):.2f}" if jpm_trigger.get("invalidation") is not None else None
    expect(jpm_technical.get("entry") == expected_jpm_entry, f"JPM technical row should mirror machine band {expected_jpm_entry}, got {jpm_technical.get('entry')}", errors)
    expect(jpm_technical.get("stop") == expected_jpm_stop, f"JPM technical row should mirror machine stop {expected_jpm_stop}, got {jpm_technical.get('stop')}", errors)
    expect(jpm_technical.get("proseConflict") is not True, f"JPM should no longer be proseConflict once formal-band state is resolved, got {jpm_technical}", errors)

    handoffs = {row.get("key"): row for row in ((payload.get("trust") or {}).get("handoff_proof_state") or [])}
    expect(handoffs.get("weekday_research", {}).get("state") == "PROVED", f"weekday research handoff should be PROVED, got {handoffs}", errors)
    for key in ("morning", "post_close", "sunday_weekly", "sunday_research"):
        expect(key in handoffs, f"handoff proof state missing {key}: {handoffs}", errors)
        expect(handoffs.get(key, {}).get("state") == "PENDING_FIRST_PROOF", f"{key} handoff should stay pending until main-session handoff proof exists, got {handoffs.get(key)}", errors)

    actionable_alias = (payload.get("today_action") or {}).get("actionable") or []
    expected_actionable = {"ETN"} if etn_in_band else set()
    expect({card.get("ticker") for card in actionable_alias} == expected_actionable, f"today_action.actionable alias should match clean deployable ETN state {expected_actionable}, got {actionable_alias}", errors)

    goog_technical = technical.get("GOOG", {})
    goog_deployment = deployment.get("GOOG", {})
    goog_in_band = goog_technical.get("inBand") is True
    if goog_in_band:
        expect(goog_technical.get("actionState") == "PROMOTION REVIEW", "GOOG in-band ALMOST setup should require PROMOTION REVIEW", errors)
        expect(goog_deployment.get("state") == "REVIEW", "GOOG in-band ALMOST setup should render as REVIEW", errors)
    else:
        expect(goog_technical.get("actionState") == "ALMOST DEPLOYABLE", "GOOG outside band should stay ALMOST DEPLOYABLE", errors)
        expect(goog_deployment.get("state") == "ALMOST", "GOOG outside band should stay ALMOST", errors)

    msft_technical = technical.get("MSFT", {})
    msft_deployment = deployment.get("MSFT", {})
    msft_in_band = msft_technical.get("inBand") is True
    msft_requires_review = (
        msft_technical.get("actionState") == "PROMOTION REVIEW"
        or msft_deployment.get("state") == "REVIEW"
    )
    if msft_in_band and msft_requires_review:
        expect(msft_technical.get("actionState") == "PROMOTION REVIEW", "MSFT in-band band-debt setup should stay PROMOTION REVIEW", errors)
        expect(msft_deployment.get("state") == "REVIEW", "MSFT in-band band-debt setup should render as REVIEW", errors)
    elif msft_in_band:
        expect(msft_technical.get("actionState") == "DEPLOYABLE NOW", "MSFT in-band owner-approved setup should be DEPLOYABLE NOW", errors)
        expect(msft_deployment.get("state") == "DEPLOYABLE", "MSFT in-band owner-approved setup should be DEPLOYABLE", errors)
    else:
        expect(msft_technical.get("actionState") == "ALMOST DEPLOYABLE", "MSFT owner-approved setup outside the live band should stay ALMOST DEPLOYABLE / no-chase", errors)
        expect(msft_deployment.get("state") == "ALMOST", "MSFT owner-approved setup outside the live band should stay ALMOST / no-chase", errors)

    deployable_bucket = set(summary.get("deployable") or [])
    almost_bucket = set(summary.get("almost") or [])
    promotion_bucket = set(summary.get("promotion_review") or [])
    if etn_in_band:
        expect("ETN" in deployable_bucket, f"deployment_summary.deployable should include in-band ETN, got {summary.get('deployable')}", errors)
        expect("ETN" not in almost_bucket, f"deployment_summary.almost should not include in-band ETN, got {summary.get('almost')}", errors)
    else:
        expect("ETN" not in deployable_bucket, f"deployment_summary.deployable should not include above-band/no-chase ETN, got {summary.get('deployable')}", errors)
        expect("ETN" in almost_bucket, f"deployment_summary.almost should include above-band/no-chase ETN, got {summary.get('almost')}", errors)
    if msft_in_band and msft_requires_review:
        expect("MSFT" not in deployable_bucket, f"deployment_summary.deployable should not include MSFT while band debt requires promotion review, got {summary.get('deployable')}", errors)
        expect("MSFT" in promotion_bucket, f"deployment_summary.promotion_review should include in-band MSFT while band debt remains open, got {summary.get('promotion_review')}", errors)
        expect("MSFT" not in almost_bucket, f"deployment_summary.almost should not include in-band promotion-review MSFT, got {summary.get('almost')}", errors)
    elif msft_in_band:
        expect("MSFT" in deployable_bucket, f"deployment_summary.deployable should include in-band owner-promoted MSFT, got {summary.get('deployable')}", errors)
        expect("MSFT" not in almost_bucket, f"deployment_summary.almost should not include in-band owner-promoted MSFT, got {summary.get('almost')}", errors)
    else:
        expect("MSFT" not in deployable_bucket, f"deployment_summary.deployable should not include no-chase MSFT above/below live band, got {summary.get('deployable')}", errors)
        expect("MSFT" in almost_bucket, f"deployment_summary.almost should include no-chase MSFT outside the live band, got {summary.get('almost')}", errors)
    expect("ETN" not in promotion_bucket, f"deployment_summary.promotion_review should no longer include owner-promoted ETN, got {summary.get('promotion_review')}", errors)
    if not msft_requires_review:
        expect("MSFT" not in promotion_bucket, f"deployment_summary.promotion_review should no longer include owner-promoted MSFT, got {summary.get('promotion_review')}", errors)
    if goog_in_band:
        expect("GOOG" in promotion_bucket, f"deployment_summary.promotion_review should include in-band GOOG, got {summary.get('promotion_review')}", errors)
        expect("GOOG" not in almost_bucket, f"deployment_summary.almost should not include in-band GOOG, got {summary.get('almost')}", errors)
    else:
        expect("GOOG" in almost_bucket, f"deployment_summary.almost should include out-of-band GOOG, got {summary.get('almost')}", errors)
        expect("GOOG" not in promotion_bucket, f"deployment_summary.promotion_review should not include out-of-band GOOG, got {summary.get('promotion_review')}", errors)
    etn_deployable_cards = [card for card in (payload.get("today_action") or {}).get("deployable") or [] if card.get("ticker") == "ETN"]
    if etn_in_band:
        expect(len(etn_deployable_cards) == 1, f"today_action.deployable should render in-band ETN exactly once, got {etn_deployable_cards}", errors)
    else:
        expect(not etn_deployable_cards, f"today_action.deployable should not render above-band/no-chase ETN, got {etn_deployable_cards}", errors)
    expect(summary.get("blocked") == [], f"deployment_summary.blocked should be empty after GOOG/MSFT correction, got {summary.get('blocked')}", errors)

    decision_queue = payload.get("decision_queue") or {}
    daily_review = decision_queue.get("daily_review") or {}
    cap_recs = daily_review.get("capital_recommendations") or []
    cap_count = (daily_review.get("counts") or {}).get("capital_recommendation_count")
    expect(cap_count == len(cap_recs), f"decision_queue should list every capital recommendation counted, count={cap_count}, listed={len(cap_recs)}", errors)
    expected_cap_tickers = _expected_capital_recommendation_tickers(daily_review)
    rendered_cap_tickers = {str(item.get("ticker") or "").upper() for item in cap_recs if item.get("ticker")}
    expect(rendered_cap_tickers == expected_cap_tickers, f"decision_queue capital recommendations should mirror current source tickers {sorted(expected_cap_tickers)}, got {cap_recs}", errors)
    for item in cap_recs:
        expect(item.get("type") == "capital_recommendation", f"capital recommendation item should preserve type, got {item}", errors)
        expect(item.get("route") == "owner_review", f"capital recommendation route must stay owner_review, got {item}", errors)
        expect(item.get("owner_review_required") is True, f"capital recommendation must require owner review, got {item}", errors)
        owner_question = str(item.get("owner_question") or "").lower()
        next_step = str(item.get("next_step") or "").lower()
        expect("owner" in owner_question or "approve" in next_step or "wait" in next_step or "review" in next_step, f"capital recommendation should carry owner-gated action language, got {item}", errors)

    lmt_technical = technical.get("LMT", {})
    lmt_trigger = trigger_records.get("LMT") or {}
    if lmt_technical.get("belowStop") is True:
        expect(lmt_technical.get("actionState") == "BELOW STOP", f"LMT below stop should be BELOW STOP, got {lmt_technical.get('actionState')}", errors)
    else:
        expect(lmt_technical.get("actionState") in {"BENCH", "DO NOT TOUCH"}, f"LMT above stop but repair-gated should be BENCH/DO NOT TOUCH, got {lmt_technical.get('actionState')}", errors)
        expect(str(lmt_trigger.get("why") or lmt_technical.get("actionReason") or "").lower().find("repair") >= 0 or str(lmt_trigger.get("why") or lmt_technical.get("actionReason") or "").lower().find("near-stop") >= 0, f"LMT above-stop repair state should preserve repair/near-stop reason, got {lmt_trigger or lmt_technical}", errors)
    expect(lmt_technical.get("triggerToday") is False, "LMT should not show triggerToday while repair/below-stop gated", errors)
    expect(technical.get("BRK.B", {}).get("actionState") == "BENCH", "BRK.B should stay BENCH", errors)
    expect(technical.get("BRK.B", {}).get("triggerToday") is False, "BRK.B should not show triggerToday while BENCH", errors)
    xom = technical.get("XOM", {})
    xom_reason = str(xom.get("actionReason") or "")
    expect(xom.get("actionState") == "BENCH", f"XOM should stay BENCH / repair, got {xom.get('actionState')}", errors)
    expect(xom.get("triggerToday") is False, "XOM should not show triggerToday while BENCH / repair", errors)
    expect(
        "repair" in xom_reason.lower() or "do not touch" in xom_reason.lower(),
        f"XOM reason should preserve repair/do-not-touch posture, got {xom_reason!r}",
        errors,
    )

    vrt_reason = str(technical.get("VRT", {}).get("actionReason") or "")
    expect(technical.get("VRT", {}).get("coverageLane") == "execution", f"VRT coverageLane should be execution, got {technical.get('VRT', {}).get('coverageLane')}", errors)
    expect(
        any(phrase in vrt_reason.lower() for phrase in ("levels are defined", "watch-only", "portfolio-review", "separate owner")),
        f"VRT reason should acknowledge defined levels/watch/review-only owner-gated posture, got {vrt_reason!r}",
        errors,
    )

    for ticker in ("CVX", "PLTR", "LNG"):
        row = technical.get(ticker, {})
        reason = str(row.get("actionReason") or "")
        expect(row.get("coverageLane") == "watch", f"{ticker} coverageLane should be watch, got {row.get('coverageLane')}", errors)
        expect(row.get("triggerToday") is False, f"{ticker} should not show triggerToday on the watch lane", errors)
        expect(
            "execution-board entitlement" in reason.lower() or "execution-board scope" in reason.lower() or "execution-board entitled" in reason.lower(),
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


def case_generic_authority_conflict_guard() -> tuple[str, list[str]]:
    name = "generic_authority_conflict_guard"
    errors: list[str] = []
    research_path = TMP / "research-freshness-opportunity-review.json"
    original_research = research_path.read_text(encoding="utf-8") if research_path.exists() else None
    try:
        baseline_payload = build_payload(load_sources())
        baseline_technical = {row["ticker"]: row for row in baseline_payload.get("technical") or []}
        baseline_deployment = {row["ticker"]: row for row in baseline_payload.get("deployment_records") or []}
        baseline_summary = baseline_payload.get("deployment_summary") or {}
        baseline_etn_action = baseline_technical.get("ETN", {}).get("actionState")
        baseline_etn_state = baseline_deployment.get("ETN", {}).get("state")
        baseline_etn_bucket = "deployable" if "ETN" in (baseline_summary.get("deployable") or []) else ("almost" if "ETN" in (baseline_summary.get("almost") or []) else None)

        research = json.loads(original_research or "{}")
        rows = research.setdefault("candidate_reviews", [])
        rows = [row for row in rows if row.get("ticker") != "ETN"]
        rows.append({
            "ticker": "ETN",
            "queue_judgment": "stale prose says trigger not live despite current machine state",
            "blocking_gate": "approval-on-hold / review-only",
            "next_action": "Sync stale prose; do not infer owner approval or execution authority",
            "below_stop_or_repair": False,
            "blocked_reasons": ["review-only owner hold"],
            "monitoring_flags": [],
        })
        research["candidate_reviews"] = rows
        research_path.write_text(json.dumps(research, indent=2), encoding="utf-8")

        payload = build_payload(load_sources())
        technical = {row["ticker"]: row for row in payload.get("technical") or []}
        deployment = {row["ticker"]: row for row in payload.get("deployment_records") or []}
        deployable_cards = [card for card in (payload.get("today_action") or {}).get("deployable") or [] if card.get("ticker") == "ETN"]
        summary = payload.get("deployment_summary") or {}
        actual_bucket = "deployable" if "ETN" in (summary.get("deployable") or []) else ("almost" if "ETN" in (summary.get("almost") or []) else None)
        expect(technical.get("ETN", {}).get("actionState") == baseline_etn_action, f"stale prose should preserve ETN technical state {baseline_etn_action}, got {technical.get('ETN')}", errors)
        expect(deployment.get("ETN", {}).get("state") == baseline_etn_state, f"stale prose should preserve ETN deployment state {baseline_etn_state}, got {deployment.get('ETN')}", errors)
        expect(actual_bucket == baseline_etn_bucket, f"stale prose should preserve ETN deployment summary bucket {baseline_etn_bucket}, got {summary}", errors)
        if baseline_etn_bucket == "deployable":
            expect(len(deployable_cards) == 1, f"deployable ETN should render exactly one deployable card, got {deployable_cards}", errors)
            for card in deployable_cards:
                expect((card.get("reviewOnlyNoApplyArtifact") is True), f"ETN deployable card must remain review-only/no-apply, got {card}", errors)
        else:
            expect(not deployable_cards, f"non-deployable ETN must not render a deployable card, got {deployable_cards}", errors)
    finally:
        if original_research is not None:
            research_path.write_text(original_research, encoding="utf-8")
    return name, errors


def case_wf63_command_center_readiness_only() -> tuple[str, list[str]]:
    """Command Center must surface WF63 readiness or WF67 scoped paper-pilot
    telemetry without implying general paper-order authority, live trading, or
    brokerage/account authority. WF58/WF56 remain monitors, not brokerage
    authority.
    """
    name = "wf63_command_center_readiness_only"
    errors: list[str] = []
    payload = build_payload(load_sources())

    wf = payload.get("workflow_focus") or {}
    top = wf.get("top_workflow") or {}
    monitors = wf.get("monitors") or []
    html = inject_into_template(payload, {"first_run": True, "changes": [], "summary": "test"})

    workflow_id = top.get("id")
    expect(workflow_id in {"WF63", "WF67"}, f"workflow_focus.top_workflow.id should be WF63 or WF67, got {workflow_id!r}", errors)
    expect("Alpaca" in str(top.get("title") or ""), f"top workflow title should reference Alpaca, got {top.get('title')!r}", errors)
    expect(
        top.get("paper_submit_allowed") is False,
        "paper_submit_allowed must be False for general/autonomous paper submit",
        errors,
    )
    expect(
        top.get("live_submit_allowed") is False,
        "live_submit_allowed must be False",
        errors,
    )
    status_text = str(top.get("paper_trading_status") or "")
    expect(
        "NOT READY" in status_text.upper() or "READ-ONLY" in status_text.upper() or ("SCOPED PAPER PILOT" in status_text.upper() and "PAPER SIMULATION ONLY" in status_text.upper()),
        f"paper_trading_status should state readiness-only or scoped paper-simulation posture, got {status_text!r}",
        errors,
    )
    expect(
        top.get("next_approval_gate"),
        "next_approval_gate must be populated",
        errors,
    )
    expect(
        ("Phase 1" in str(top.get("next_approval_gate") or "")) or (workflow_id == "WF67" and "reconciliation" in str(top.get("next_approval_gate") or "").lower()),
        f"next_approval_gate should reference Phase 1 or WF67 reconciliation, got {top.get('next_approval_gate')!r}",
        errors,
    )

    stop_lines = " ".join(str(s).lower() for s in (top.get("stop_lines") or []))
    if workflow_id == "WF67":
        for needle in (
            "paper simulation only",
            "no live trade",
            "no owner approval inferred",
            "no close",
            "paper results do not promote",
        ):
            expect(needle in stop_lines, f"WF67 stop lines must cover {needle!r}", errors)
        authority = top.get("authority") or {}
        for field in ("live_trading_allowed", "live_endpoint_allowed", "money_movement_allowed", "account_settings_mutation_allowed", "owner_approval_inferred", "promotion_to_live_allowed"):
            expect(authority.get(field) is False, f"WF67 authority.{field} must be false", errors)
        expect(top.get("scoped_paper_pilot_active") is True, "WF67 should mark scoped_paper_pilot_active=true", errors)
    else:
        for needle in (
            "no credentials in notes",
            "no alpaca api",
            "no paper",
            "no brokerage",
            "no money movement",
            "no config",
        ):
            expect(needle in stop_lines, f"WF63 stop lines must cover {needle!r}", errors)

    monitor_ids = {m.get("id") for m in monitors if isinstance(m, dict)}
    for required in ("WF58", "WF56", "WF60", "WF61"):
        expect(required in monitor_ids, f"workflow_focus.monitors should include {required}", errors)
    for monitor in monitors:
        if monitor.get("id") in {"WF56", "WF58"}:
            expect(
                monitor.get("brokerage_authority") is False,
                f"{monitor.get('id')} must be tagged brokerage_authority=False",
                errors,
            )

    # Forbidden phrases — these would imply paper trading is active or that
    # order submission has been authorized. The shape validator should also
    # catch them and we re-check them here for explicit signal.
    rendered_lower = html.lower()
    for phrase in (
        "paper trading is active",
        "paper trading has started",
        "paper orders enabled",
        "paper submit allowed",
        "order submission allowed",
    ):
        expect(
            phrase not in rendered_lower,
            f"Command Center must not contain phrase {phrase!r}",
            errors,
        )

    # WF63-specific shape warnings must NOT be present under healthy state.
    wf63_codes = [
        "workflow_focus_missing_top",
        "workflow_focus_wrong_top",
        "paper_submit_not_general_blocked",
        "live_submit_not_blocked",
        "paper_status_missing",
        "paper_status_misleading",
        "workflow_stop_lines_missing",
        "workflow_stop_line_missing_phrase",
        "workflow_next_gate_missing",
        "wf63_misleading_active_language",
        "wf67_authority_field_not_false",
        "wf67_paper_simulation_flag_missing",
        "workflow_focus_monitor_brokerage_authority",
    ]
    raised = {w["code"] for w in payload["validation"]["warnings"]}
    for code in wf63_codes:
        expect(code not in raised, f"WF63 invariant violation surfaced: {code}", errors)

    # And the rendered HTML must actually include the workflow + stop-line message.
    if workflow_id == "WF67":
        required_html = ("WF67", "Alpaca", "Scoped paper pilot", "paper simulation only", "No owner approval inferred")
    else:
        required_html = ("WF63", "Alpaca", "NOT READY FOR PAPER ORDERS", "Phase 1", "No paper or live order submit")
    for needle in required_html:
        expect(needle in html, f"rendered HTML missing {needle!r}", errors)

    # Overview hierarchy contract: decision/action content (deploymentStrip,
    # todayAction) must appear above the expanded WF63 detail block. The
    # compact ribbon is allowed at the top — the giant detail panel is not.
    ribbon_pos = html.find('id="workflowFocusRibbon"')
    detail_pos = html.find('id="workflowFocusDetail"')
    deploy_pos = html.find('id="deploymentStrip"')
    action_pos = html.find('id="todayAction"')
    expect(ribbon_pos > -1, "Overview must contain a compact workflowFocusRibbon", errors)
    expect(detail_pos > -1, "Overview must contain workflowFocusDetail panel", errors)
    expect(deploy_pos > -1, "Overview must contain deploymentStrip", errors)
    expect(action_pos > -1, "Overview must contain todayAction", errors)
    if deploy_pos > -1 and detail_pos > -1:
        expect(
            deploy_pos < detail_pos,
            "deploymentStrip must appear before workflowFocusDetail in the Overview",
            errors,
        )
    if action_pos > -1 and detail_pos > -1:
        expect(
            action_pos < detail_pos,
            "todayAction must appear before workflowFocusDetail in the Overview",
            errors,
        )
    if ribbon_pos > -1 and deploy_pos > -1:
        expect(
            ribbon_pos < deploy_pos,
            "workflowFocusRibbon should sit at the top of Overview, above deploymentStrip",
            errors,
        )

    return name, errors


def case_wf63_validator_fails_on_misleading_language() -> tuple[str, list[str]]:
    """If the workflow-focus block claims paper trading is live or authority
    is granted, the shape validator must escalate to critical so the build
    fails before publication.
    """
    name = "wf63_validator_fails_on_misleading_language"
    errors: list[str] = []
    payload = build_payload(load_sources())

    # 1) paper_submit_allowed flipped True should raise a critical warning.
    tampered = copy.deepcopy(payload)
    tampered_focus = tampered.get("workflow_focus") or {}
    top = tampered_focus.get("top_workflow") or {}
    top["paper_submit_allowed"] = True
    top["paper_trading_status"] = "Paper trading is active for OpenClaw orders"
    tampered_focus["top_workflow"] = top
    from dashboard_payload import _validate_payload_shape  # local import to access private helper
    warnings = _validate_payload_shape(
        today_action=tampered.get("today_action") or {},
        deployment_records=tampered.get("deployment_records") or [],
        macro_regime=tampered.get("macro_regime") or {},
        sectors_relative=tampered.get("sectors_relative") or [],
        post_earnings=tampered.get("post_earnings") or {},
        workflow_focus=tampered_focus,
    )
    codes = {w["code"] for w in warnings if w["severity"] == "critical"}
    expect("paper_submit_not_general_blocked" in codes, "flipping paper_submit_allowed=True must raise paper_submit_not_general_blocked", errors)
    expect("wf63_misleading_active_language" in codes, "asserting paper trading is active must raise wf63_misleading_active_language", errors)

    # 2) Dropping top workflow id must raise workflow_focus_wrong_top.
    tampered2 = copy.deepcopy(payload)
    tampered2_focus = tampered2.get("workflow_focus") or {}
    top2 = tampered2_focus.get("top_workflow") or {}
    top2["id"] = "WF58"
    tampered2_focus["top_workflow"] = top2
    warnings2 = _validate_payload_shape(
        today_action=tampered2.get("today_action") or {},
        deployment_records=tampered2.get("deployment_records") or [],
        macro_regime=tampered2.get("macro_regime") or {},
        sectors_relative=tampered2.get("sectors_relative") or [],
        post_earnings=tampered2.get("post_earnings") or {},
        workflow_focus=tampered2_focus,
    )
    codes2 = {w["code"] for w in warnings2 if w["severity"] == "critical"}
    expect("workflow_focus_wrong_top" in codes2, "wrong top workflow id must raise workflow_focus_wrong_top", errors)

    # 3) A monitor claiming brokerage authority must raise critical.
    tampered3 = copy.deepcopy(payload)
    tampered3_focus = tampered3.get("workflow_focus") or {}
    monitors3 = tampered3_focus.get("monitors") or []
    if monitors3:
        monitors3[0]["brokerage_authority"] = True
    tampered3_focus["monitors"] = monitors3
    warnings3 = _validate_payload_shape(
        today_action=tampered3.get("today_action") or {},
        deployment_records=tampered3.get("deployment_records") or [],
        macro_regime=tampered3.get("macro_regime") or {},
        sectors_relative=tampered3.get("sectors_relative") or [],
        post_earnings=tampered3.get("post_earnings") or {},
        workflow_focus=tampered3_focus,
    )
    codes3 = {w["code"] for w in warnings3 if w["severity"] == "critical"}
    expect(
        "workflow_focus_monitor_brokerage_authority" in codes3,
        "monitor claiming brokerage_authority=True must raise workflow_focus_monitor_brokerage_authority",
        errors,
    )

    return name, errors


def case_decision_queue_visibility() -> tuple[str, list[str]]:
    name = "decision_queue_visibility"
    errors: list[str] = []
    payload = build_payload(load_sources())
    html = inject_into_template(payload, {"first_run": True, "changes": [], "summary": "test"})
    dq = payload.get("decision_queue") or {}
    daily = dq.get("daily_review") or {}
    intel = dq.get("market_intelligence") or {}
    authority = dq.get("authority") or {}

    expect((daily.get("counts") or {}).get("review_object_count", 0) > 0, "daily review object count missing from decision queue", errors)
    expect((intel.get("counts") or {}).get("event_count", 0) > 0, "market-intelligence event count missing from decision queue", errors)
    expect(daily.get("escalations"), "daily review escalations missing from decision queue", errors)
    expect(daily.get("capital_recommendations"), "capital recommendations missing from decision queue", errors)
    expect(intel.get("escalations"), "market-intelligence escalations missing from decision queue", errors)
    expect(authority.get("canonical_mutation_allowed") is False, "decision queue must not allow canonical mutation", errors)
    expect(authority.get("trade_execution_allowed") is False, "decision queue must not allow trade execution", errors)
    for needle in ("Decision Queue", "Daily review", "Market intelligence", "review-only", "owner approval required", "ETN"):
        expect(needle in html, f"rendered HTML missing {needle!r}", errors)
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



def case_deployment_readiness_source_conflict_guard() -> tuple[str, list[str]]:
    name = "deployment_readiness_source_conflict_guard"
    errors: list[str] = []
    research_path = TMP / "research-freshness-opportunity-review.json"
    run_summary_path = TMP / "run-summary-post-close.json"
    original_research = research_path.read_text(encoding="utf-8") if research_path.exists() else None
    original_run_summary = run_summary_path.read_text(encoding="utf-8") if run_summary_path.exists() else None
    try:
        # This acceptance case verifies source-conflict mapping, not global
        # stop-line behavior. During a recovery run, the previous post-close
        # run summary may still be blocked before run_summary_refresh.py has
        # rebuilt it, which correctly moves every ticker to SYSTEM HOLD and
        # masks the JPM DO NOT TOUCH assertion. Pin a clean local summary so
        # the case remains independent of stale recovery state.
        run_summary_path.write_text(json.dumps({
            "window": "post-close",
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "status": "ok",
            "stop_line": False,
            "validation": {"exec_freshness": "usable_with_caution", "critical": 0, "warning": 0, "info": 0},
            "downstream": {"canonical_note_mutation_allowed": False, "presentation_allowed": False},
        }, indent=2), encoding="utf-8")

        deployment_readiness_surface.main()
        surface = read_json(TMP / "deployment-readiness-surface.json")
        groups = surface.get("groups") or {}
        deployable = {row.get("ticker") for row in groups.get("DEPLOYABLE NOW") or []}
        conflict_rows = [row for row in groups.get("AUTHORITY CONFLICT") or [] if row.get("ticker") == "JPM"]
        do_not_touch_rows = [row for row in groups.get("DO NOT TOUCH") or [] if row.get("ticker") == "JPM"]
        almost_rows = [row for row in groups.get("ALMOST DEPLOYABLE") or [] if row.get("ticker") == "JPM"]
        expect("JPM" not in deployable, f"deployment-readiness-surface DEPLOYABLE NOW group must not include JPM, got {sorted(deployable)}", errors)
        expect(not conflict_rows, f"deployment-readiness-surface AUTHORITY CONFLICT should not include JPM after formal-band resolution, got {groups.get('AUTHORITY CONFLICT')}", errors)
        jpm_rows = do_not_touch_rows or almost_rows
        expect(bool(jpm_rows), f"deployment-readiness-surface should include JPM either as DO NOT TOUCH when below stop or ALMOST DEPLOYABLE when above stop/below band, got groups={groups}", errors)
        if jpm_rows:
            jpm = jpm_rows[0]
            if do_not_touch_rows:
                jpm_surface_state = legacy_state(jpm, "surface_state")
                expect(jpm_surface_state == "DO NOT TOUCH", f"JPM below stop should be DO NOT TOUCH, got {jpm_surface_state}", errors)
            else:
                jpm_surface_state = legacy_state(jpm, "surface_state")
                expect(jpm_surface_state == "ALMOST DEPLOYABLE", f"JPM above stop but below band should be ALMOST DEPLOYABLE, got {jpm_surface_state}", errors)
            expect(jpm.get("prose_conflict") is False, f"JPM surface row should not carry prose_conflict after formal-band resolution, got {jpm}", errors)

        # Capture the machine-owned ETN bucket first. This case verifies that stale
        # research prose does not demote the current machine state into AUTHORITY
        # CONFLICT; it must not freeze a historical ETN deployable-now expectation
        # after price has legitimately moved above band/no-chase.
        baseline_surface = read_json(TMP / "deployment-readiness-surface.json")
        baseline_groups = baseline_surface.get("groups") or {}
        baseline_etn_bucket = next((
            bucket for bucket, rows_for_bucket in baseline_groups.items()
            if any(row.get("ticker") == "ETN" for row in (rows_for_bucket or []))
        ), None)

        research = json.loads(original_research or "{}")
        rows = [row for row in research.get("candidate_reviews", []) if row.get("ticker") != "ETN"]
        rows.append({
            "ticker": "ETN",
            "queue_judgment": "stale prose says trigger not live despite current machine state",
            "blocking_gate": "approval-on-hold / review-only",
            "next_action": "Sync stale prose; do not infer owner approval or execution authority",
            "below_stop_or_repair": False,
            "blocked_reasons": ["review-only owner hold"],
            "monitoring_flags": [],
        })
        research["candidate_reviews"] = rows
        research_path.write_text(json.dumps(research, indent=2), encoding="utf-8")
        deployment_readiness_surface.main()
        generic_surface = read_json(TMP / "deployment-readiness-surface.json")
        generic_groups = generic_surface.get("groups") or {}
        generic_etn_bucket = next((
            bucket for bucket, rows_for_bucket in generic_groups.items()
            if any(row.get("ticker") == "ETN" for row in (rows_for_bucket or []))
        ), None)
        etn_conflict = [row for row in generic_groups.get("AUTHORITY CONFLICT") or [] if row.get("ticker") == "ETN"]
        expect(generic_etn_bucket == baseline_etn_bucket, f"stale prose should preserve ETN machine bucket {baseline_etn_bucket}, got {generic_etn_bucket}", errors)
        expect(not etn_conflict, f"stale prose alone must not move ETN to AUTHORITY CONFLICT, got {generic_groups.get('AUTHORITY CONFLICT')}", errors)
    finally:
        if original_research is not None:
            research_path.write_text(original_research, encoding="utf-8")
        if original_run_summary is not None:
            run_summary_path.write_text(original_run_summary, encoding="utf-8")
        elif run_summary_path.exists():
            run_summary_path.unlink()
        deployment_readiness_surface.main()
    return name, errors



def case_auto_apply_clears_deployment_surface_band_debt() -> tuple[str, list[str]]:
    name = "auto_apply_clears_deployment_surface_band_debt"
    errors: list[str] = []
    proposal_path = deployment_readiness_surface.BAND_PROPOSALS_PATH
    audit_path = deployment_readiness_surface.AUTO_BAND_APPLY_PATH
    original_proposal = proposal_path.read_text(encoding="utf-8") if proposal_path.exists() else None
    original_audit = audit_path.read_text(encoding="utf-8") if audit_path.exists() else None
    try:
        proposal_path.write_text(json.dumps({
            "summary": {"blocking_review_tickers": ["ETN"]},
            "proposals": [{
                "ticker": "ETN",
                "canonical_apply_eligible": True,
                "data_date": "2026-05-12",
                "needs_review": True,
                "skip_reason": None,
            }],
        }), encoding="utf-8")
        audit_path.write_text(json.dumps({
            "status": "ok",
            "applied_date": "2026-05-12",
            "applied": [{"ticker": "ETN"}],
        }), encoding="utf-8")
        stale = deployment_readiness_surface.band_stale_tickers()
        expect("ETN" not in stale, f"eligible same-day auto-apply should clear ETN band debt, got {sorted(stale)}", errors)
    finally:
        if original_proposal is not None:
            proposal_path.write_text(original_proposal, encoding="utf-8")
        if original_audit is not None:
            audit_path.write_text(original_audit, encoding="utf-8")
    return name, errors


def case_event_risk_band_freeze_is_structured_review_debt() -> tuple[str, list[str]]:
    name = "event_risk_band_freeze_is_structured_review_debt"
    errors: list[str] = []
    proposal_path = TMP / "band-proposals.json"
    audit_path = TMP / "auto-band-apply.json"
    original_proposal = proposal_path.read_text(encoding="utf-8") if proposal_path.exists() else None
    original_audit = audit_path.read_text(encoding="utf-8") if audit_path.exists() else None
    try:
        proposal_path.write_text(json.dumps({
            "status": "needs_review",
            "summary": {"blocking_review_tickers": ["NVDA"]},
            "proposals": [{
                "ticker": "NVDA",
                "canonical_apply_eligible": False,
                "entry_band_method": "EARNINGS_FROZEN",
                "band_status": "EARNINGS_IMMINENT",
                "earnings_state": "IMMINENT",
                "data_date": "2026-05-12",
                "needs_review": True,
                "skip_reason": None,
            }],
        }), encoding="utf-8")
        audit_path.write_text(json.dumps({"status": "ok", "mode": "apply", "applied_date": "2026-05-12", "applied": []}), encoding="utf-8")
        payload = build_payload(load_sources())
        warnings = [w for w in payload["validation"]["warnings"] if w.get("code") == "band_staleness"]
        expect(len(warnings) == 1, f"expected one band_staleness warning, got {warnings}", errors)
        warning = warnings[0] if warnings else {}
        message = warning.get("message", "")
        details = warning.get("details", {})
        expect("event-risk band freeze" in message, f"event-risk freeze wording missing: {message!r}", errors)
        expect("Run auto_apply_entry_band_maintenance.py --apply" not in message, f"non-applyable freeze should not ask for auto-apply: {message!r}", errors)
        expect(details.get("event_risk_blockers") == ["NVDA"], f"event_risk_blockers missing/mis-set: {details}", errors)
        expect(details.get("pending_applyable_blockers") == [], f"pending applyable blockers should be empty: {details}", errors)
        parsed = workbook_export.parse_band_staleness(payload["validation"])
        expect(parsed == {"NVDA"}, f"workbook parser should consume structured blocker details, got {parsed}", errors)
    finally:
        if original_proposal is not None:
            proposal_path.write_text(original_proposal, encoding="utf-8")
        if original_audit is not None:
            audit_path.write_text(original_audit, encoding="utf-8")
    return name, errors


def case_post_apply_band_review_does_not_loop_auto_apply() -> tuple[str, list[str]]:
    name = "post_apply_band_review_does_not_loop_auto_apply"
    errors: list[str] = []
    proposal_path = TMP / "band-proposals.json"
    audit_path = TMP / "auto-band-apply.json"
    hygiene_path = TMP / "band-hygiene-freshness-controller.json"
    original_proposal = proposal_path.read_text(encoding="utf-8") if proposal_path.exists() else None
    original_audit = audit_path.read_text(encoding="utf-8") if audit_path.exists() else None
    original_hygiene = hygiene_path.read_text(encoding="utf-8") if hygiene_path.exists() else None
    try:
        proposal_path.write_text(json.dumps({
            "status": "needs_review",
            "summary": {"blocking_review_tickers": ["VRT"]},
            "proposals": [{
                "ticker": "VRT",
                "canonical_apply_eligible": True,
                "data_date": "2026-06-09",
                "needs_review": True,
                "skip_reason": None,
            }],
        }), encoding="utf-8")
        audit_path.write_text(json.dumps({
            "status": "ok",
            "mode": "dry_run",
            "applied_date": "2026-06-09",
            "applied": [],
        }), encoding="utf-8")
        hygiene_path.write_text(json.dumps({
            "status": "needs_review",
            "rows": [{
                "ticker": "VRT",
                "state": "post_apply_review_still_open",
                "auto_apply": {
                    "applied": True,
                    "applied_date": "2026-06-09",
                },
            }],
        }), encoding="utf-8")
        payload = build_payload(load_sources())
        warnings = [w for w in payload["validation"]["warnings"] if w.get("code") == "band_staleness"]
        expect(len(warnings) == 1, f"expected one band_staleness warning, got {warnings}", errors)
        warning = warnings[0] if warnings else {}
        message = warning.get("message", "")
        details = warning.get("details", {})
        expect("post-apply band review" in message, f"post-apply wording missing: {message!r}", errors)
        expect("Run auto_apply_entry_band_maintenance.py --apply" not in message, f"post-apply review should not loop auto-apply: {message!r}", errors)
        expect(details.get("pending_applyable_blockers") == [], f"pending applyable blockers should be empty: {details}", errors)
        expect(details.get("post_apply_review_blockers") == ["VRT"], f"post_apply_review_blockers missing/mis-set: {details}", errors)
    finally:
        if original_proposal is not None:
            proposal_path.write_text(original_proposal, encoding="utf-8")
        if original_audit is not None:
            audit_path.write_text(original_audit, encoding="utf-8")
        if original_hygiene is not None:
            hygiene_path.write_text(original_hygiene, encoding="utf-8")
        elif hygiene_path.exists():
            hygiene_path.unlink()
    return name, errors



def case_trigger_note_uses_current_execution_band() -> tuple[str, list[str]]:
    name = "trigger_note_uses_current_execution_band"
    errors: list[str] = []
    meta = {
        "trigger_condition": "Owner-approved Tier 1 explicit add only inside the 395.59 to 420.31 band; do not chase above 420.31; manual execution only"
    }
    band = {"low": 368.42, "high": 410.79, "stop": 349.15}
    text, source = trigger_sheet_refresh.build_technical_trigger(meta, {"reason": "owner-approved setup"}, band, "DEPLOYABLE NOW")
    expect("368.42 to 410.79" in text, f"trigger text should use current band, got {text!r}", errors)
    expect("420.31" not in text and "395.59" not in text, f"stale band leaked into trigger text: {text!r}", errors)
    expect(source == "generated_current_band_due_to_stale_config_range", f"unexpected source {source!r}", errors)
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



def case_neutral_deployment_evidence_shadow_display_only() -> tuple[str, list[str]]:
    name = "neutral_deployment_evidence_shadow_display_only"
    errors: list[str] = []
    payload = build_payload(load_sources())
    shadow = ((payload.get("trust") or {}).get("sql_canon") or {}).get("neutralDeploymentEvidenceShadowMetadata") or {}
    baseline_summary = copy.deepcopy(payload.get("deployment_summary") or {})
    baseline_today = copy.deepcopy(payload.get("today_action") or {})
    baseline_records = copy.deepcopy(payload.get("deployment_records") or [])
    expect(shadow.get("status") == "shadow_only_display_metadata", f"neutral shadow metadata missing/wrong status: {shadow}", errors)
    expect(shadow.get("current_field_permanent_hold") is True or shadow.get("currentFieldPermanentHold") is True, "deployment_proof_status must remain permanent hold", errors)
    expect(shadow.get("sql_canon_activation_allowed") is False or shadow.get("sqlCanonActivationAllowed") is False, "neutral deployment shadow must not allow SQL activation", errors)
    expect(shadow.get("sql_read_allowed_for_key") is False or shadow.get("sqlReadAllowedForKey") is False, "neutral deployment shadow must not be SQL-readable", errors)
    expect(shadow.get("cache_row_allowed") is False or shadow.get("cacheRowAllowed") is False, "neutral deployment shadow must not allow cache rows", errors)
    expect(shadow.get("dashboard_behavior_change_allowed") is False or shadow.get("dashboardBehaviorChangeAllowed") is False, "neutral deployment shadow must not allow dashboard behavior changes", errors)
    forbidden_blob = " ".join(str(v).lower() for v in (shadow.get("fallbackValues") or shadow.get("allowed_values") or []))
    for phrase in ("deployable", "deploy", "buy", "sell", "order", "trade", "approval", "promotion", "do not touch"):
        expect(phrase not in forbidden_blob, f"neutral deployment shadow values must not contain action word {phrase!r}: {shadow}", errors)
    payload2 = build_payload(load_sources())
    expect(payload2.get("deployment_summary") == baseline_summary, "neutral shadow metadata must not change deployment_summary", errors)
    expect(payload2.get("today_action") == baseline_today, "neutral shadow metadata must not change today_action", errors)
    expect(payload2.get("deployment_records") == baseline_records, "neutral shadow metadata must not change deployment_records", errors)
    return name, errors


def case_phase4a_sql_consumer_authority_guard_fail_closed() -> tuple[str, list[str]]:
    name = "phase4a_sql_consumer_authority_guard_fail_closed"
    errors: list[str] = []

    def blocked_guard(**_kwargs: Any) -> dict[str, Any]:
        return {
            "status": "blocked",
            "sql_read_allowed": False,
            "issues": ["test-forced blocked guard"],
            "cache_meta": {"authority_boundary": dashboard_payload.PHASE4A_SQL_CANON_BOUNDARY},
            "cache_rows": [],
        }

    with patched_attrs(dashboard_payload, build_phase4a_sql_consumer_authority_guard=blocked_guard):
        payload = build_payload(load_sources())
    sql_canon = (payload.get("trust") or {}).get("sql_canon") or {}
    technical = {row.get("ticker"): row for row in payload.get("technical") or []}
    nvda_proof = (technical.get("NVDA") or {}).get("sqlCanonProofMetadata") or {}
    fields = nvda_proof.get("fields") or {}
    expect(sql_canon.get("status") == "degraded_fallback_required", f"forced blocked guard should degrade to fallback, got {sql_canon}", errors)
    expect(sql_canon.get("sqlIsCanon") is False, "blocked guard must not mark SQL as canon", errors)
    expect("test-forced blocked guard" in (sql_canon.get("issues") or []), "blocked guard issue should surface in advisory metadata", errors)
    for field_name, field in fields.items():
        expect(field.get("readSource") == "generated_artifact_or_markdown_fallback", f"{field_name} should fall back when guard blocks: {field}", errors)
    expect(nvda_proof.get("tradeOrAccountActionAllowed") is False, f"proof metadata must not allow trade/account authority: {nvda_proof}", errors)
    expect(nvda_proof.get("ownerApprovalInferred") is False, f"proof metadata must not infer owner approval: {nvda_proof}", errors)
    return name, errors



def case_fundamental_trend_panel_review_only() -> tuple[str, list[str]]:
    name = "fundamental_trend_panel_review_only"
    errors: list[str] = []
    payload = build_payload(load_sources())
    trends = payload.get("fundamental_trends") or {}
    rows = trends.get("rows") or []
    authority = trends.get("authority") or {}
    ir_summary = trends.get("ir_packet_summary") or {}
    expect(rows, "fundamental_trends.rows should populate dashboard trend panel", errors)
    expect(ir_summary.get("packets", 0) > 0, f"fundamental_trends should expose IR packet summary, got {ir_summary}", errors)
    expect(authority.get("deployment_authority_allowed") is False, f"fundamental trends must not grant deployment authority, got {authority}", errors)
    expect(authority.get("portfolio_mutation_allowed") is False, f"fundamental trends must not grant portfolio mutation authority, got {authority}", errors)
    sample = rows[0] if rows else {}
    for field in ("ticker", "quality", "secStatus", "irStatus", "irPacketStatus", "adjustedEpsStatus", "guidanceStatus", "officialEarningsBridgeStatus", "officialEarningsBridgeReviewOnly", "officialEarningsBridgeManualRequired", "officialAdjustedEpsBridgeStatus", "officialGuidanceBridgeStatus", "officialEarningsReleaseUrl", "earningsUrl", "epsYoY", "revenueYoY", "netIncomeYoY", "dilutedSharesYoY", "fcfInterpretation", "fcfInterpretationNote", "fcfPerShare", "fcfPerShareYoY", "fcfPerShareYoYBase", "buybackYield", "netShareRepurchases", "sbcPctRevenue", "sbcPctFcf", "capitalReturnToFcf", "netDebtIssued", "netDebtInterpretation", "shareholderYield", "shareholderYieldPeriod", "fcfYield", "roicProxy", "valuationContext", "capitalAllocationQuality", "capitalAllocationAnomalies", "wf65BankNativeVersion", "bankNativeStatus", "bankNativeSecStatus", "cet1Ratio", "cet1RatioTrust", "cet1RatioStandardized", "cet1RatioAdvanced", "cet1RatioBasis", "tier1Ratio", "tier1RatioTrust", "tier1RatioStandardized", "tier1RatioAdvanced", "tier1RatioBasis", "riskBasedCapitalSourceUrl", "riskBasedCapitalNoDerivedRatio", "tier1LeverageRatio", "tier1LeverageRatioNote", "tbvPerShare", "tbvPerShareTrust", "priceToTbv", "tone"):
        expect(field in sample, f"fundamental trend row missing {field}: {sample}", errors)
    expect(sample.get("officialEarningsBridgeReviewOnly") is True, f"official earnings bridge must render as review-only: {sample}", errors)
    expect(sample.get("officialEarningsBridgeManualRequired") is True, f"official earnings bridge must remain manual-required: {sample}", errors)
    bank_rows = [row for row in rows if row.get("sector") == "Financials"]
    for bank in bank_rows:
        expect(bank.get("capitalAllocationQuality") == "bank_manual_review", f"Financials row should use bank_manual_review: {bank}", errors)
        expect(bank.get("fcfInterpretation") == "bank_structural", f"Financials row should label bank_structural FCF: {bank}", errors)
        if bank.get("freeCashFlow") is not None and bank.get("freeCashFlow") < 0:
            expect(bank.get("sbcPctFcf") is None, f"Financials row should suppress SBC/FCF when bank FCF denominator is structurally negative: {bank}", errors)
        expect(bank.get("wf65BankNativeVersion") == "v1_5_partial", f"Financials row should expose WF65 V1.5 partial bank-native schema: {bank}", errors)
        expect(bank.get("bankNativeSecStatus") == "partial", f"Financials row should expose SEC partial bank-native status after probe resolution: {bank}", errors)
        expect(bank.get("cet1Ratio") is not None and bank.get("cet1RatioTrust") == "manual_confirmed", f"CET1 should be official/manual_confirmed for bank rows: {bank}", errors)
        expect(bank.get("cet1RatioStandardized") is not None and bank.get("cet1RatioAdvanced") is not None, f"CET1 standardized/advanced framework values should be exposed: {bank}", errors)
        expect(bank.get("tier1Ratio") is not None and bank.get("tier1RatioTrust") == "manual_confirmed", f"Tier1 risk-based should be official/manual_confirmed for bank rows: {bank}", errors)
        expect(bank.get("tier1RatioStandardized") is not None and bank.get("tier1RatioAdvanced") is not None, f"Tier1 standardized/advanced framework values should be exposed: {bank}", errors)
        expect(bank.get("riskBasedCapitalSourceUrl") and bank.get("riskBasedCapitalNoDerivedRatio") is True, f"Bank risk-based ratios require official source URL and no-derived-ratio guard: {bank}", errors)
        if bank.get("ticker") == "JPM":
            expect(bank.get("tbvPerShare") == 108.87 and bank.get("tbvPerShareTrust") == "manual_confirmed", f"JPM TBV/share should use official manual-confirmed source: {bank}", errors)
        if bank.get("tier1LeverageRatio") is not None:
            expect("NOT" in str(bank.get("tier1LeverageRatioNote") or "").upper(), f"Tier1 leverage requires explicit NOT risk-based note: {bank}", errors)
        bad_codes = {item.get("code") for item in bank.get("capitalAllocationAnomalies") or []}
        expect(not ({"capital_returns_with_negative_fcf", "capital_return_exceeds_fcf", "debt_funded_capital_return_risk", "eps_fcf_per_share_divergence"} & bad_codes), f"Financials row carries industrial FCF anomaly code(s): {bad_codes}", errors)
    return name, errors



def _mutate_entry_band_contradiction(s: dict[str, Any], ticker: str = "ETN") -> None:
    tech = next(r for r in s["technical"]["records"] if r["ticker"] == ticker)
    band = s["portfolio"]["entry_bands"].get(ticker) or {}
    close = tech.get("close") or 300.0
    band_low = band.get("low")
    band_high = band.get("high")
    computed_in_band = (
        band_low is not None
        and band_high is not None
        and band_low <= close <= band_high
    )
    if band_low is None or band_high is None:
        band_low = round(close * 1.05, 2)
        band_high = round(close * 1.1, 2)
        s["portfolio"]["entry_bands"][ticker] = {
            **band,
            "low": band_low,
            "high": band_high,
            "label": f"{band_low}-{band_high}",
        }
        computed_in_band = False
    tech.update({"in_entry_band": not computed_in_band})


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
        # Stamp all sources with a fresh generated_at_utc so acceptance cases
        # start from a fresh baseline regardless of how old on-disk artifacts are.
        # Each test mutator then applies only its intended deviation.
        now_utc = datetime.now(timezone.utc).isoformat()
        for src in base_sources.values():
            if isinstance(src, dict) and "generated_at_utc" in src:
                src["generated_at_utc"] = now_utc
        for name, payload in base_sources.items():
            if payload is not None:
                write_source(name, payload)
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
            _mutate_entry_band_contradiction,
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
        restore_sources(base_sources)
        for case_fn in (
            case_market_state_missing_policy_artifact,
            case_policy_fail_closed_expired_target,
            case_dashboard_policy_manual_remediation_path,
            case_macro_regime_policy_distribution_shape_guard,
            case_macro_regime_credit_shape_guard,
            case_macro_regime_breadth_shape_guard,
        ):
            (case_name, case_errors), producer_output = _quiet_call(case_fn)
            result = {
                "name": case_name,
                "passed": len(case_errors) == 0,
                "errors": case_errors,
                "exec_freshness": None,
                "validation": {},
                "trust_summary": None,
            }
            if case_errors and producer_output:
                result["producer_output_tail"] = producer_output[-4000:]
            results.append(result)

        # Sprint 1 regression cases (2026-04-25 audit Priority 1 fixes)
        # Sprint 2 regression case (2026-04-30 dashboard refresh): payload-shape contract
        restore_sources(base_sources)
        for case_fn in (case_delta_summary_honesty, case_earnings_lifecycle_closeout_candidate, case_earnings_new_alert_visibility, case_trigger_note_uses_current_execution_band, case_neutral_deployment_evidence_shadow_display_only, case_phase4a_sql_consumer_authority_guard_fail_closed, case_fundamental_trend_panel_review_only, case_deployment_readiness_source_conflict_guard, case_auto_apply_clears_deployment_surface_band_debt, case_event_risk_band_freeze_is_structured_review_debt, case_post_apply_band_review_does_not_loop_auto_apply, case_payload_shape_contract, case_workflow8_command_center_alignment, case_generic_authority_conflict_guard, case_decision_queue_visibility, case_wf63_command_center_readiness_only, case_wf63_validator_fails_on_misleading_language):
            (case_name, case_errors), producer_output = _quiet_call(case_fn)
            result = {
                "name": case_name,
                "passed": len(case_errors) == 0,
                "errors": case_errors,
                "exec_freshness": None,
                "validation": {},
                "trust_summary": None,
            }
            if case_errors and producer_output:
                result["producer_output_tail"] = producer_output[-4000:]
            results.append(result)

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
