from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import (
    DynamicEntitlementExternalGateError,
    DynamicEntitlementScope,
    DynamicEntitlementScopeError,
    FinanceSqlCanonAccess,
    require_dynamic_entitlement_external_gate,
    verify_dynamic_entitlement_payload,
)
from phase3f_external_canary_approval import (
    PRODUCTION_ENVIRONMENT,
    Phase3FApprovalError,
    Phase3FCanaryAuthorization,
    create_phase3f_component_claim,
    phase3f_component_metrics_shell,
    require_phase3f_component_budget,
    require_phase3f_component_duration,
    verified_scope_tickers,
)

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
DEFAULT_OUTPUT = TMP / "analyst-consensus-current.json"
COVERAGE_PATH = TMP / "finance-data-coverage-current.json"

PROJECTION_FIELDS = (
    "source_status",
    "as_of",
    "source_lineage",
    "cross_check_conflict",
)
LINEAGE_FIELDS = (
    "provider",
    "provider_symbol",
    "source_url",
    "retrieval_method",
    "evidence_digest_sha256",
)
ALLOWED_SOURCE_STATUSES = {
    "auto_sourced_yfinance",
    "partial_yfinance",
    "missing_yfinance",
    "missing_or_partial",
    "unavailable",
}
ALLOWED_CROSS_CHECK_STATUSES = {"pass", "fail", "stale", "unavailable"}
RAW_EVIDENCE_FIELDS = (
    "current_price",
    "average_target",
    "median_target",
    "high_target",
    "low_target",
    "recommendation_period",
    "strong_buy_count",
    "buy_count",
    "hold_count",
    "sell_count",
    "strong_sell_count",
    "errors",
    "provider_messages",
)

AUTHORITY_BOUNDARY = {
    "derived_review_surface_only": True,
    "canonical_mutation_allowed": False,
    "portfolio_or_canon_apply_allowed": False,
    "sizing_cash_or_risk_rule_mutation_allowed": False,
    "owner_approval_inferred": False,
    "trade_execution_allowed": False,
    "paper_trade_submit_cancel_allowed": False,
    "live_trade_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "source_open_required_before_finance_claims": True,
}

FIELD_CONTRACT = {
    "per_ticker_required_fields": list(PROJECTION_FIELDS),
    "source_lineage_required_fields": list(LINEAGE_FIELDS),
    "consumer_projection_policy": (
        "Analyst direction, recommendation counts, and targets are quarantined source evidence. "
        "They may affect only source_lineage.evidence_digest_sha256 and are not consumer decision inputs."
    ),
    "cross_check_policy": (
        "cross_check_conflict is pass|fail|stale|unavailable and defaults to unavailable until "
        "a real official-source cross-check exists."
    ),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def tracked_tickers_from_coverage() -> list[str]:
    data = load_json(COVERAGE_PATH)
    if isinstance(data, dict) and isinstance(data.get("ticker_coverage"), dict):
        return sorted(str(ticker).upper() for ticker in data["ticker_coverage"])
    return []


def yahoo_symbol(ticker: str) -> str:
    # Provider identity only. Enrollment remains owned by the explicit caller.
    return ticker.replace(".", "-")


def finite_number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return round(number, 4)
    except (TypeError, ValueError):
        return None


def int_or_none(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def latest_recommendation_row(recommendations: Any) -> dict[str, Any] | None:
    if recommendations is None or not hasattr(recommendations, "to_dict"):
        return None
    try:
        rows = recommendations.to_dict(orient="records")
    except Exception:  # noqa: BLE001 - external library object shape can drift.
        return None
    if not rows:
        return None
    for row in rows:
        if isinstance(row, dict) and str(row.get("period")) == "0m":
            return row
    return rows[0] if isinstance(rows[0], dict) else None


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return finite_number(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)


def evidence_digest(raw: dict[str, Any]) -> str:
    payload = {field: json_safe(raw.get(field)) for field in RAW_EVIDENCE_FIELDS}
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def normalized_cross_check(value: Any) -> str:
    normalized = str(value or "unavailable").strip().lower()
    return normalized if normalized in ALLOWED_CROSS_CHECK_STATUSES else "unavailable"


def source_status_from_raw(raw: dict[str, Any]) -> str:
    declared = str(raw.get("source_status") or raw.get("status") or "").strip()
    if declared in ALLOWED_SOURCE_STATUSES:
        return declared
    return "unavailable"


def valid_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def normalize_lineage(ticker: str, raw: dict[str, Any]) -> dict[str, str]:
    """Return the exact lineage schema; nested decision fields are never preserved."""

    existing = raw.get("source_lineage") if isinstance(raw.get("source_lineage"), dict) else {}
    provider = str(existing.get("provider") or raw.get("provider") or "yfinance")
    symbol = str(existing.get("provider_symbol") or raw.get("provider_symbol") or yahoo_symbol(ticker))
    source_url = str(
        existing.get("source_url")
        or raw.get("source_url")
        or f"https://finance.yahoo.com/quote/{symbol}/analysis"
    )
    retrieval_method = str(
        existing.get("retrieval_method")
        or "yfinance.Ticker.get_analyst_price_targets+get_recommendations"
    )
    existing_digest = existing.get("evidence_digest_sha256")
    digest = existing_digest if valid_sha256(existing_digest) else evidence_digest(raw)
    return {
        "provider": provider,
        "provider_symbol": symbol,
        "source_url": source_url,
        "retrieval_method": retrieval_method,
        "evidence_digest_sha256": digest,
    }


def normalize_projection(ticker: str, row: Any) -> dict[str, Any]:
    """Contract analyst evidence to the only four fields consumers may see."""

    raw = row if isinstance(row, dict) else {}
    if set(raw) == set(PROJECTION_FIELDS) and isinstance(raw.get("source_lineage"), dict):
        return {
            "source_status": source_status_from_raw(raw),
            "as_of": raw.get("as_of"),
            "source_lineage": normalize_lineage(ticker, raw),
            "cross_check_conflict": normalized_cross_check(raw.get("cross_check_conflict")),
        }
    return {
        "source_status": source_status_from_raw(raw),
        "as_of": raw.get("as_of") or raw.get("accessed_at_utc") or raw.get("as_of_date"),
        "source_lineage": normalize_lineage(ticker, raw),
        "cross_check_conflict": normalized_cross_check(raw.get("cross_check_conflict")),
    }


class Phase3FAnalystProviderObserver:
    """Privacy-safe observable boundary counters for the Phase 3F child."""

    def __init__(
        self,
        authorization: Phase3FCanaryAuthorization,
        *,
        now: datetime | None = None,
        started_monotonic: float | None = None,
    ) -> None:
        self.authorization = authorization
        self.fixed_now = now
        self.started_monotonic = (
            time.perf_counter()
            if started_monotonic is None
            else float(started_monotonic)
        )
        self.ticker_construction_attempts = 0
        self.ticker_construction_completed = 0
        self.ticker_construction_failed = 0
        self.provider_method_attempts = 0
        self.provider_method_completed = 0
        self.provider_method_failed = 0
        self.method_durations_seconds: list[float] = []
        self.method_counts = {
            "get_analyst_price_targets": {"attempted": 0, "completed": 0, "failed": 0},
            "get_recommendations": {"attempted": 0, "completed": 0, "failed": 0},
        }

    def _now(self) -> datetime:
        return self.fixed_now or datetime.now(timezone.utc)

    def _require_duration(self) -> None:
        require_phase3f_component_duration(
            self.authorization,
            component_id="analyst_consensus",
            duration_seconds=time.perf_counter() - self.started_monotonic,
            now_utc=self._now(),
        )

    def before_construction(self) -> None:
        self._require_duration()
        require_phase3f_component_budget(
            self.authorization,
            component_id="analyst_consensus",
            provider_method_attempts=self.provider_method_attempts,
            retries=0,
            now_utc=self._now(),
        )
        self.ticker_construction_attempts += 1

    def after_construction(self, *, success: bool) -> None:
        if success:
            self.ticker_construction_completed += 1
        else:
            self.ticker_construction_failed += 1

    def before_method(self, method: str) -> float:
        self._require_duration()
        if method not in self.method_counts:
            raise RuntimeError("phase3f_provider_method_unknown")
        next_count = self.provider_method_attempts + 1
        require_phase3f_component_budget(
            self.authorization,
            component_id="analyst_consensus",
            provider_method_attempts=next_count,
            retries=0,
            now_utc=self._now(),
        )
        self.provider_method_attempts = next_count
        self.method_counts[method]["attempted"] += 1
        return time.perf_counter()

    def after_method(self, method: str, started: float, *, success: bool) -> None:
        duration = max(0.0, time.perf_counter() - started)
        self.method_durations_seconds.append(duration)
        if success:
            self.provider_method_completed += 1
            self.method_counts[method]["completed"] += 1
        else:
            self.provider_method_failed += 1
            self.method_counts[method]["failed"] += 1

    def metrics(
        self,
        duration_seconds: float,
        *,
        status: str | None = None,
    ) -> dict[str, Any]:
        result = phase3f_component_metrics_shell(
            "analyst_consensus",
            status=status
            or (
                "completed"
                if self.provider_method_failed == 0
                and self.ticker_construction_failed == 0
                else "completed_with_provider_failures"
            ),
            provider_method_attempts=self.provider_method_attempts,
            provider_method_completed=self.provider_method_completed,
            provider_method_failed=self.provider_method_failed,
            duration_seconds=duration_seconds,
        )
        result.update({
            "ticker_construction_attempts": self.ticker_construction_attempts,
            "ticker_construction_completed": self.ticker_construction_completed,
            "ticker_construction_failed": self.ticker_construction_failed,
            "provider_methods": {
                method: dict(counts)
                for method, counts in sorted(self.method_counts.items())
            },
            "method_duration_seconds_total": round(
                sum(self.method_durations_seconds), 6
            ),
        })
        return result


class Phase3FProviderConstructionFailure(RuntimeError):
    """Sanitized provider-construction failure; raw exception text is discarded."""


class Phase3FProviderImportFailure(RuntimeError):
    """Sanitized provider-import failure; raw exception text is discarded."""


def fetch_ticker(
    ticker: str,
    *,
    provider_observer: Phase3FAnalystProviderObserver | None = None,
    _provider_module: Any = None,
) -> dict[str, Any]:
    """Perform the unchanged two-method provider read and return a quarantine projection."""

    if _provider_module is None:
        try:
            import yfinance as yf  # local import keeps local migration provider-free
        except Exception:  # noqa: BLE001 - production child returns only a stable code.
            if provider_observer is not None:
                raise Phase3FProviderImportFailure(
                    "phase3f_provider_import_failed"
                ) from None
            raise
    else:
        yf = _provider_module

    symbol = yahoo_symbol(ticker)
    accessed_at = utc_now()
    raw: dict[str, Any] = {
        "ticker": ticker,
        "provider_symbol": symbol,
        "provider": "yfinance",
        "source_url": f"https://finance.yahoo.com/quote/{symbol}/analysis",
        "accessed_at_utc": accessed_at,
        "errors": [],
    }
    if provider_observer is not None:
        provider_observer.before_construction()
    try:
        ticker_obj = yf.Ticker(symbol)
    except Exception:  # noqa: BLE001 - observer retains only success/failure counts.
        if provider_observer is not None:
            provider_observer.after_construction(success=False)
            raise Phase3FProviderConstructionFailure(
                "phase3f_provider_construction_failed"
            ) from None
        raise
    if provider_observer is not None:
        provider_observer.after_construction(success=True)
    stderr_capture = io.StringIO()
    method_started = (
        provider_observer.before_method("get_analyst_price_targets")
        if provider_observer is not None
        else time.perf_counter()
    )
    try:
        with contextlib.redirect_stderr(stderr_capture):
            targets = ticker_obj.get_analyst_price_targets()
    except Exception as exc:  # noqa: BLE001 - provider failure stays hashed, never a decision input.
        targets = None
        raw["errors"].append(f"price_target_error:{type(exc).__name__}")
        if provider_observer is not None:
            provider_observer.after_method(
                "get_analyst_price_targets", method_started, success=False
            )
    else:
        if provider_observer is not None:
            provider_observer.after_method(
                "get_analyst_price_targets", method_started, success=True
            )
    method_started = (
        provider_observer.before_method("get_recommendations")
        if provider_observer is not None
        else time.perf_counter()
    )
    try:
        with contextlib.redirect_stderr(stderr_capture):
            recommendations = ticker_obj.get_recommendations()
        recommendation = latest_recommendation_row(recommendations)
    except Exception as exc:  # noqa: BLE001 - provider failure stays hashed, never a decision input.
        recommendation = None
        raw["errors"].append(f"recommendations_error:{type(exc).__name__}")
        if provider_observer is not None:
            provider_observer.after_method(
                "get_recommendations", method_started, success=False
            )
    else:
        if provider_observer is not None:
            provider_observer.after_method(
                "get_recommendations", method_started, success=True
            )
    captured = stderr_capture.getvalue().strip()
    if captured:
        raw["provider_messages"] = captured.splitlines()[-4:]

    if isinstance(targets, dict):
        raw.update({
            "current_price": finite_number(targets.get("current")),
            "average_target": finite_number(targets.get("mean")),
            "median_target": finite_number(targets.get("median")),
            "high_target": finite_number(targets.get("high")),
            "low_target": finite_number(targets.get("low")),
        })
    else:
        raw.update({
            "current_price": None,
            "average_target": None,
            "median_target": None,
            "high_target": None,
            "low_target": None,
        })
    target_evidence_usable = any(
        raw.get(field) is not None
        for field in ("average_target", "median_target", "high_target", "low_target")
    )
    if not target_evidence_usable and not any(str(error).startswith("price_target_error:") for error in raw["errors"]):
        raw["errors"].append("price_target_empty")

    if isinstance(recommendation, dict):
        raw.update({
            "recommendation_period": recommendation.get("period"),
            "strong_buy_count": int_or_none(recommendation.get("strongBuy")),
            "buy_count": int_or_none(recommendation.get("buy")),
            "hold_count": int_or_none(recommendation.get("hold")),
            "sell_count": int_or_none(recommendation.get("sell")),
            "strong_sell_count": int_or_none(recommendation.get("strongSell")),
        })
    else:
        raw.update({
            "recommendation_period": None,
            "strong_buy_count": None,
            "buy_count": None,
            "hold_count": None,
            "sell_count": None,
            "strong_sell_count": None,
        })
    recommendation_evidence_usable = any(
        raw.get(field) is not None
        for field in ("strong_buy_count", "buy_count", "hold_count", "sell_count", "strong_sell_count")
    )
    if not recommendation_evidence_usable and not any(
        str(error).startswith("recommendations_error:") for error in raw["errors"]
    ):
        raw["errors"].append("recommendations_empty")

    if target_evidence_usable and recommendation_evidence_usable:
        raw["source_status"] = "auto_sourced_yfinance"
    elif target_evidence_usable or recommendation_evidence_usable:
        raw["source_status"] = "partial_yfinance"
    else:
        raw["source_status"] = "missing_yfinance"

    return normalize_projection(ticker, raw)


def artifact_shell(
    rows: dict[str, dict[str, Any]],
    *,
    generated_at_utc: Any,
    source_as_of_utc: Any,
    source_artifacts: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 3,
        "artifact_type": "analyst_consensus_current",
        "generated_at_utc": generated_at_utc,
        "status": "placeholder_manual_required",
        "consumer_posture": "quarantined_source_evidence_only_not_decision_input",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source": {
            "provider": "yfinance",
            "provider_ready": True,
            "retrieval_method": "yfinance.Ticker.get_analyst_price_targets and get_recommendations",
            "as_of_utc": source_as_of_utc,
            "notes": "Provider evidence is retained only as a lineage digest; source-open review remains required.",
        },
        "field_contract": FIELD_CONTRACT,
        "quarantine": {
            "active": True,
            "decision_input_allowed": False,
            "confidence_or_completeness_input_allowed": False,
            "official_cross_check_available": False,
        },
        "tickers": {ticker: rows[ticker] for ticker in sorted(rows)},
        "source_artifacts": list(source_artifacts or []),
        "review_notes": [
            "Analyst direction, recommendation counts, and targets are not emitted as consumer inputs.",
            "The evidence digest is lineage only and grants no recommendation, approval, canon, or execution authority.",
            "cross_check_conflict remains unavailable until a real official-source cross-check exists.",
        ],
    }


def build_artifact(
    tickers: list[str],
    *,
    provider_observer: Phase3FAnalystProviderObserver | None = None,
    generated_at_utc: str | None = None,
    _provider_module: Any = None,
) -> dict[str, Any]:
    rows = {
        ticker: fetch_ticker(
            ticker,
            provider_observer=provider_observer,
            _provider_module=_provider_module,
        )
        for ticker in tickers
    }
    generated_at = generated_at_utc or utc_now()
    return artifact_shell(
        rows,
        generated_at_utc=generated_at,
        source_as_of_utc=generated_at,
        source_artifacts=[rel(COVERAGE_PATH)] if COVERAGE_PATH.exists() else [],
    )


def _build_phase3f_analyst_component_with_authorization(
    *,
    authorization: Phase3FCanaryAuthorization,
    now: datetime | None = None,
    _test_provider_module: Any = None,
) -> dict[str, Any]:
    """Run only the immutable approved scope and return an in-memory artifact."""

    started = time.perf_counter()
    observed_at = now or datetime.now(timezone.utc)
    tickers = verified_scope_tickers(
        authorization,
        component_id="analyst_consensus",
        now_utc=observed_at,
    )
    require_phase3f_component_budget(
        authorization,
        component_id="analyst_consensus",
        provider_method_attempts=0,
        retries=0,
        now_utc=observed_at,
    )
    if authorization.approval.environment == PRODUCTION_ENVIRONMENT:
        if _test_provider_module is not None:
            raise Phase3FApprovalError("phase3f_test_provider_forbidden_in_production")
        provider_module = None
    else:
        if not bool(
            getattr(_test_provider_module, "__phase3f_test_fixture__", False)
        ):
            raise Phase3FApprovalError(
                "phase3f_test_authorization_provider_import_forbidden"
            )
        provider_module = _test_provider_module
    claim_path, claim_sha256 = create_phase3f_component_claim(
        authorization,
        component_id="analyst_consensus",
        now_utc=observed_at,
    )
    observer = Phase3FAnalystProviderObserver(
        authorization,
        now=now,
        started_monotonic=started,
    )
    generated = observed_at.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    try:
        artifact = build_artifact(
            list(tickers),
            provider_observer=observer,
            generated_at_utc=generated,
            _provider_module=provider_module,
        )
    except (Phase3FProviderImportFailure, Phase3FProviderConstructionFailure) as exc:
        duration = time.perf_counter() - started
        final_now = observed_at if now is not None else datetime.now(timezone.utc)
        require_phase3f_component_duration(
            authorization,
            component_id="analyst_consensus",
            duration_seconds=duration,
            now_utc=final_now,
        )
        import_failure = isinstance(exc, Phase3FProviderImportFailure)
        error_code = (
            "phase3f_provider_import_failed"
            if import_failure
            else "phase3f_provider_construction_failed"
        )
        metrics_status = (
            "blocked_provider_import_failed"
            if import_failure
            else "blocked_provider_construction_failed"
        )
        return {
            "artifact": {
                "schema": "veritas.phase3f.analyst_component_failure.v1",
                "status": "blocked",
                "error": error_code,
                "record_id": authorization.approval.record_id,
                "scope_fingerprint": authorization.scope.fingerprint,
                "scope_payload_sha256": authorization.scope.payload_sha256,
                "component_claim_path": claim_path.relative_to(
                    authorization.approval.workspace_root
                ).as_posix(),
                "component_claim_sha256": claim_sha256,
                "raw_provider_payload_retained": False,
                "external_baseline_blocked": True,
            },
            "metrics": observer.metrics(
                duration,
                status=metrics_status,
            ),
        }
    expected_attempts = 2 * len(tickers)
    if (
        observer.ticker_construction_attempts != len(tickers)
        or observer.ticker_construction_completed != len(tickers)
        or observer.ticker_construction_failed != 0
        or observer.provider_method_attempts != expected_attempts
        or tuple(artifact.get("tickers", {})) != tickers
    ):
        raise RuntimeError("phase3f_provider_observability_incomplete")
    require_phase3f_component_budget(
        authorization,
        component_id="analyst_consensus",
        provider_method_attempts=observer.provider_method_attempts,
        retries=0,
        now_utc=observed_at if now is not None else datetime.now(timezone.utc),
    )
    duration = time.perf_counter() - started
    require_phase3f_component_duration(
        authorization,
        component_id="analyst_consensus",
        duration_seconds=duration,
        now_utc=observed_at if now is not None else datetime.now(timezone.utc),
    )
    artifact["phase3f_canary"] = {
        "record_id": authorization.approval.record_id,
        "scope_fingerprint": authorization.scope.fingerprint,
        "scope_payload_sha256": authorization.scope.payload_sha256,
        "receipt_sha256": authorization.receipt_sha256,
        "component_claim_path": claim_path.relative_to(
            authorization.approval.workspace_root
        ).as_posix(),
        "component_claim_sha256": claim_sha256,
        "membership_resolver_invocations": 0,
        "sql_reads": 0,
        "parent_is_only_output_writer": True,
        "external_baseline_blocked": True,
    }
    return {
        "artifact": artifact,
        "metrics": observer.metrics(duration),
    }


def quarantine_existing_artifact(existing: dict[str, Any]) -> dict[str, Any]:
    """Normalize the current artifact without importing or calling the provider."""

    existing_rows = existing.get("tickers") if isinstance(existing.get("tickers"), dict) else {}
    if (
        existing.get("schema_version") == 3
        and existing.get("status") == "placeholder_manual_required"
        and existing.get("consumer_posture") == "quarantined_source_evidence_only_not_decision_input"
        and existing.get("field_contract") == FIELD_CONTRACT
        and all(
            isinstance(row, dict)
            and set(row) == set(PROJECTION_FIELDS)
            and row.get("source_status") in ALLOWED_SOURCE_STATUSES
            and row.get("cross_check_conflict") in ALLOWED_CROSS_CHECK_STATUSES
            and isinstance(row.get("source_lineage"), dict)
            and set(row["source_lineage"]) == set(LINEAGE_FIELDS)
            and valid_sha256(row["source_lineage"].get("evidence_digest_sha256"))
            for row in existing_rows.values()
        )
    ):
        return existing

    rows = {
        str(ticker).upper(): normalize_projection(str(ticker).upper(), row)
        for ticker, row in existing_rows.items()
    }
    source = existing.get("source") if isinstance(existing.get("source"), dict) else {}
    artifact = artifact_shell(
        rows,
        generated_at_utc=existing.get("generated_at_utc"),
        source_as_of_utc=source.get("as_of_utc"),
        source_artifacts=existing.get("source_artifacts") if isinstance(existing.get("source_artifacts"), list) else [],
    )
    artifact["migration"] = {
        "mode": "quarantine_existing_local_no_provider",
        "source_schema_version": existing.get("schema_version"),
        "provider_calls": 0,
        "generated_source_and_row_times_preserved": True,
    }
    return artifact


def merge_existing_artifact(output: Path, refreshed: dict[str, Any], tickers: list[str]) -> dict[str, Any]:
    existing = load_json(output)
    if not isinstance(existing, dict):
        return refreshed

    merged_rows: dict[str, dict[str, Any]] = {}
    existing_rows = existing.get("tickers") if isinstance(existing.get("tickers"), dict) else {}
    for ticker, row in existing_rows.items():
        normalized = str(ticker).upper()
        merged_rows[normalized] = normalize_projection(normalized, row)
    refreshed_rows = refreshed.get("tickers") if isinstance(refreshed.get("tickers"), dict) else {}
    for ticker, row in refreshed_rows.items():
        normalized = str(ticker).upper()
        merged_rows[normalized] = normalize_projection(normalized, row)

    generated_at = utc_now()
    artifact = artifact_shell(
        merged_rows,
        generated_at_utc=generated_at,
        source_as_of_utc=generated_at,
        source_artifacts=refreshed.get("source_artifacts") if isinstance(refreshed.get("source_artifacts"), list) else [],
    )
    artifact["merge_policy"] = {
        "enabled": True,
        "refreshed_tickers": list(tickers),
        "existing_artifact": rel(output),
        "note": "Refreshed rows replaced matching rows; every refreshed and preserved row was normalized to the quarantine projection.",
    }
    return artifact


def validate_artifact(artifact: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str, severity: str = "error") -> None:
        checks.append({"name": name, "passed": bool(passed), "severity": severity, "detail": detail})

    boundary = artifact.get("authority_boundary", {})
    allowed_true = {"derived_review_surface_only", "source_open_required_before_finance_claims"}
    forbidden_true = [key for key, value in boundary.items() if key not in allowed_true and value is True]
    add("authority_boundary_no_forbidden_true_flags", not forbidden_true, json.dumps(forbidden_true))
    add("source_open_required", boundary.get("source_open_required_before_finance_claims") is True, "source-open must remain required")
    add("artifact_fails_closed", artifact.get("status") == "placeholder_manual_required", str(artifact.get("status")))
    add(
        "consumer_posture_quarantined",
        artifact.get("consumer_posture") == "quarantined_source_evidence_only_not_decision_input",
        str(artifact.get("consumer_posture")),
    )
    retired_scope_blocks = {
        "".join(("tier", "_sets")),
        "".join(("manual_review", "_queue")),
    }
    forbidden_top_level = sorted(set(artifact).intersection(retired_scope_blocks))
    add("no_legacy_scope_or_queue_blocks", not forbidden_top_level, json.dumps(forbidden_top_level))

    rows = artifact.get("tickers", {})
    add("ticker_map_present", isinstance(rows, dict) and bool(rows), f"tickers={len(rows) if isinstance(rows, dict) else 0}")
    invalid_shapes: list[str] = []
    invalid_statuses: list[str] = []
    invalid_cross_checks: list[str] = []
    invalid_lineage: list[str] = []
    sourced: list[str] = []
    if isinstance(rows, dict):
        for ticker, row in rows.items():
            if not isinstance(row, dict) or set(row) != set(PROJECTION_FIELDS):
                invalid_shapes.append(str(ticker))
                continue
            if row.get("source_status") not in ALLOWED_SOURCE_STATUSES:
                invalid_statuses.append(str(ticker))
            if row.get("source_status") in {"auto_sourced_yfinance", "partial_yfinance"}:
                sourced.append(str(ticker))
            if row.get("cross_check_conflict") not in ALLOWED_CROSS_CHECK_STATUSES:
                invalid_cross_checks.append(str(ticker))
            lineage = row.get("source_lineage")
            digest = lineage.get("evidence_digest_sha256") if isinstance(lineage, dict) else None
            if (
                not isinstance(lineage, dict)
                or set(lineage) != set(LINEAGE_FIELDS)
                or not all(isinstance(lineage.get(field), str) and lineage.get(field) for field in LINEAGE_FIELDS[:-1])
                or not valid_sha256(digest)
            ):
                invalid_lineage.append(str(ticker))
    add("rows_are_exact_four_field_projection", not invalid_shapes, json.dumps(invalid_shapes))
    add("source_status_values_allowed", not invalid_statuses, json.dumps(invalid_statuses))
    add("cross_check_values_allowed", not invalid_cross_checks, json.dumps(invalid_cross_checks))
    add("lineage_digest_present", not invalid_lineage, json.dumps(invalid_lineage))
    add("at_least_one_provider_row_sourced", bool(sourced), f"sourced={len(sourced)}")
    add(
        "field_contract_exact",
        (
            (artifact.get("field_contract") or {}).get("per_ticker_required_fields") == list(PROJECTION_FIELDS)
            and (artifact.get("field_contract") or {}).get("source_lineage_required_fields") == list(LINEAGE_FIELDS)
        ),
        json.dumps(artifact.get("field_contract") or {}),
    )
    return checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh quarantined analyst source evidence using yfinance.", allow_abbrev=False)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--tickers", nargs="*", help="Explicit caller-owned tickers. Defaults to the coverage registry when available.")
    parser.add_argument("--merge-existing", action="store_true", help="Merge refreshed rows into the existing output after normalizing every row.")
    parser.add_argument("--quarantine-existing", action="store_true", help="Normalize the existing artifact locally with zero provider imports or calls.")
    parser.add_argument("--dynamic-entitlement-preview", action="store_true", help="Report the guarded dynamic A+B scope with zero provider calls or output writes.")
    parser.add_argument("--dynamic-entitlement-scope", action="store_true", help="Request future dynamic provider scope; denied until the Phase 3F/3G positive gate exists.")
    parser.add_argument(
        "--scope-origin",
        default="ad_hoc",
        choices=("ad_hoc", "phase3f_dynamic_entitlement"),
        help="Reserved provenance for a future approved dynamic external-scope gate.",
    )
    parser.add_argument("--write", action="store_true", help="Write the output artifact. Without --write, prints compact summary only.")
    parser.add_argument("--validate", action="store_true", help="Validate generated or existing artifact.")
    from phase3g_dynamic_execution import add_arguments
    add_arguments(parser)
    return parser.parse_args()


def serialize_artifact(artifact: dict[str, Any]) -> str:
    return json.dumps(artifact, indent=2, sort_keys=True) + "\n"


def dynamic_entitlement_preview(
    client: FinanceSqlCanonAccess | None = None,
) -> tuple[DynamicEntitlementScope, dict[str, Any]]:
    """Resolve and prove the A+B scope locally, without importing yfinance."""

    scope = (client or FinanceSqlCanonAccess()).dynamic_entitlement_scope()
    payload = scope.payload()
    verify_dynamic_entitlement_payload(payload, scope.fingerprint)
    return scope, {
        "scope": payload,
        "external_scope_gate": "not_enabled",
        "provider_calls": 0,
        "output_writes": 0,
    }


def enforce_explicit_ticker_boundary(
    tickers: list[str],
    client: FinanceSqlCanonAccess | None = None,
) -> list[str]:
    """Keep ad-hoc requests, but block a disguised full dynamic provider scope."""

    scope = (client or FinanceSqlCanonAccess()).dynamic_entitlement_scope()
    canonicalized: list[str] = []
    for raw_ticker in tickers:
        normalized = str(raw_ticker).strip().upper()
        canonicalized.append(
            scope.aliases.get(normalized)
            or scope.aliases.get(normalized.replace(".", "-"))
            or scope.aliases.get(normalized.replace("-", "."))
            or normalized
        )
    if set(scope.tickers).issubset(set(canonicalized)):
        raise DynamicEntitlementScopeError("dynamic_entitlement_scope_requires_gate")
    return sorted(dict.fromkeys(canonicalized))


def main() -> int:
    args = parse_args()
    from phase3g_dynamic_execution import dispatch
    dynamic_result = dispatch(args, components=("analyst_consensus",))
    if dynamic_result is not None:
        return dynamic_result
    output = Path(args.output)

    if args.dynamic_entitlement_preview or args.dynamic_entitlement_scope:
        scope, preview = dynamic_entitlement_preview()
        errors: list[str] = []
        status = "planned"
        if args.dynamic_entitlement_scope:
            try:
                require_dynamic_entitlement_external_gate(scope, scope_origin=args.scope_origin)
            except DynamicEntitlementExternalGateError as exc:
                status = "error"
                errors.append(str(exc))
        print(json.dumps({
            "status": status,
            "dynamic_entitlement": preview,
            "errors": errors,
        }, indent=2, sort_keys=True))
        return 1 if errors else 0

    if args.quarantine_existing:
        existing = load_json(output)
        if not isinstance(existing, dict):
            print(json.dumps({"status": "error", "output": rel(output), "error": "existing_artifact_missing_or_invalid"}, indent=2, sort_keys=True))
            return 1
        artifact = quarantine_existing_artifact(existing)
        if args.write:
            output.parent.mkdir(parents=True, exist_ok=True)
            serialized = serialize_artifact(artifact)
            if not output.exists() or output.read_text(encoding="utf-8") != serialized:
                output.write_text(serialized, encoding="utf-8")
    else:
        tickers = [str(ticker).upper() for ticker in (args.tickers or tracked_tickers_from_coverage())]
        tickers = sorted(dict.fromkeys(tickers))
        try:
            if args.tickers:
                tickers = enforce_explicit_ticker_boundary(tickers)
            if args.scope_origin == "phase3f_dynamic_entitlement":
                scope = FinanceSqlCanonAccess().dynamic_entitlement_scope()
                require_dynamic_entitlement_external_gate(scope, scope_origin=args.scope_origin)
        except DynamicEntitlementScopeError as exc:
            print(json.dumps({
                "status": "error",
                "error": str(exc),
                "provider_calls": 0,
                "output_writes": 0,
            }, indent=2, sort_keys=True))
            return 1
        if args.write or not output.exists():
            artifact = build_artifact(tickers)
            if args.merge_existing and output.exists():
                artifact = merge_existing_artifact(output, artifact, tickers)
            if args.write:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(serialize_artifact(artifact), encoding="utf-8")
        else:
            loaded = load_json(output)
            artifact = loaded if isinstance(loaded, dict) else build_artifact(tickers)

    checks = validate_artifact(artifact) if args.validate else []
    failed = [check for check in checks if not check["passed"] and check["severity"] == "error"]
    rows = artifact.get("tickers", {}) if isinstance(artifact.get("tickers"), dict) else {}
    summary = {
        "status": "ok" if not failed else "error",
        "artifact_status": artifact.get("status"),
        "consumer_posture": artifact.get("consumer_posture"),
        "output": rel(output),
        "ticker_count": len(rows),
        "sourced_count": sum(
            1 for row in rows.values()
            if isinstance(row, dict) and row.get("source_status") in {"auto_sourced_yfinance", "partial_yfinance"}
        ),
        "missing_count": sum(
            1 for row in rows.values()
            if isinstance(row, dict) and row.get("source_status") in {"missing_yfinance", "missing_or_partial", "unavailable"}
        ),
        "checks_total": len(checks),
        "checks_failed": len(failed),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
