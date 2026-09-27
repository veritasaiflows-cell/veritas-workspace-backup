"""Current alerts-OS evidence adapter and non-executing repair-debt projection.

This is the opt-in Phase 3G adapter for the Phase 3D measurement owner, not a
second tier, band, recommendation, or approval owner. No provider is invoked.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Any, Callable, Mapping

from finance_sql_canon_access import (
    DynamicEntitlementScope, FinanceSqlCanonAccess, REFERENCE_LEVEL_LINEAGE_FIELDS,
    verify_dynamic_entitlement_payload,
)
from market_calendar_freshness import classify_quote_freshness
from phase3f_external_canary_approval import (
    _is_lexically_contained, _path_has_reparse_component,
)
from tier_entitlement_phase3d_observed_coverage import (
    ArtifactSnapshot, ENROLLED_NOT_OBSERVED, NO_OWNER_SURFACE, OBSERVED,
    ROOT, _canonical_artifact_rows, _coverage_counts, _read_artifact,
    _safe_parse_utc, _scope_summary, _sha256, _time_metadata,
)

DEFAULT_OUTPUT = ROOT / "tmp/tier-entitlement-phase3g/current-coverage.json"
CONTROLLER_PATH = ROOT / "tmp/alert-level-freshness-controller.json"
ANALYST_PATH = ROOT / "tmp/analyst-consensus-current.json"
MAX_CONTROLLER_HOURS = 6.0  # Existing digest freshness contract.
MAX_LEVEL_HOURS = 14 * 24.0  # Existing controller reference-age contract.
MAX_QUOTE_HOURS = 36.0  # Existing controller quote-age ceiling.
MAX_ANALYST_HOURS = 7 * 24.0  # Review contract: weekly analyst context.


def _positive_number(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _age_error(stamp: Any, now: datetime, limit_hours: float) -> str | None:
    _, seconds, reason = _time_metadata(stamp, now)
    if reason:
        return reason
    return "stale_evidence" if seconds is None or seconds > limit_hours * 3600 else None


def _source_error(source: ArtifactSnapshot, now: datetime, limit_hours: float) -> str | None:
    if source.error:
        return source.error
    if not isinstance(source.payload, Mapping) or not source.sha256:
        return "source_unbound"
    return _age_error(source.payload.get("generated_at_utc"), now, limit_hours)


def _cell(state: str, reason: str, *, source: ArtifactSnapshot | None,
          stamp: Any, now: datetime, limit: float | None, owner: str) -> dict[str, Any]:
    as_of, age, timestamp_error = _time_metadata(stamp, now)
    return {
        "state": state, "reason": reason, "owner_surface": owner,
        "artifact_path": source.path if source else None,
        "artifact_sha256": source.sha256 if source else None,
        "evidence_as_of_utc": as_of, "age_seconds": age,
        "age_basis": "source_evidence_age_not_queue_wait",
        "timestamp_error": timestamp_error, "recency_limit_hours": limit,
    }


def _validated_controller_relative_path(name: Any) -> Path | None:
    """Lexically validate a controller-directed relative JSON path.

    Returns the in-workspace candidate without reading any content, else
    None. Defensive hardening only: the inherited ``_read_artifact`` still
    resolves and enforces workspace containment before reading bytes, so no
    exploit is claimed and no atomic TOCTOU elimination is asserted.
    """
    if not isinstance(name, str) or not name.strip():
        return None
    if "\x00" in name:
        return None
    if not name.lower().endswith(".json"):
        return None
    # Reject Windows absolute/drive/UNC shapes explicitly even on POSIX hosts.
    windows = PureWindowsPath(name)
    if windows.is_absolute() or windows.drive or windows.root:
        return None
    if Path(name).is_absolute():
        return None
    # Split on both separators so a Windows-style traversal cannot hide.
    parts = name.replace("\\", "/").split("/")
    for part in parts:
        if part in ("", ".", ".."):
            return None
        if ":" in part:  # Alternate-data-stream shape.
            return None
        if part != part.rstrip(". "):  # Windows trailing-dot/space alias.
            return None
    root = ROOT.resolve()
    candidate = root.joinpath(*parts)
    if not _is_lexically_contained(candidate, root):
        return None
    try:
        if _path_has_reparse_component(candidate, root):
            return None
    except OSError:
        return None
    return candidate


def _source_from_controller(controller: ArtifactSnapshot, key: str, default: str) -> ArtifactSnapshot:
    sources = (controller.payload or {}).get("source_artifacts", {})
    name = sources.get(key, default) if isinstance(sources, Mapping) else default
    if not isinstance(name, str):
        return ArtifactSnapshot(default, None, None, "source_path_invalid")
    candidate = _validated_controller_relative_path(name)
    if candidate is None:
        return ArtifactSnapshot(default, None, None, "source_path_invalid")
    return _read_artifact(candidate)


def build_current_alerts_coverage(
    *, client: FinanceSqlCanonAccess | None = None,
    scope: DynamicEntitlementScope | None = None,
    controller: ArtifactSnapshot | None = None,
    quote: ArtifactSnapshot | None = None,
    quote_validation: ArtifactSnapshot | None = None,
    analyst: ArtifactSnapshot | None = None,
    lineage_reader: Callable[[str], Mapping[str, Any]] | None = None,
    run_as_of_utc: str | None = None,
) -> dict[str, Any]:
    """Measure present owners once; queue enrollment never counts as review.

    An orchestrator may supply its already-resolved scope; this adapter then
    verifies it without resolving membership again. Local reference reads are
    evidence reads, not alternate membership predicates.
    """
    from alert_level_freshness_controller import (
        quote_evaluation_policy, quote_proof_is_clean, reference_lineage,
    )

    now, error = (_safe_parse_utc(run_as_of_utc) if run_as_of_utc
                  else (datetime.now(timezone.utc), None))
    if now is None or error:
        raise ValueError("invalid_run_as_of_utc")
    access = client or FinanceSqlCanonAccess()
    resolver_calls = 0
    if scope is None:
        scope = access.dynamic_entitlement_scope(envelope_name="phase3g_coverage", envelope_count=None)
        resolver_calls = 1
    verify_dynamic_entitlement_payload(scope.payload(), scope.fingerprint)
    if set(scope.tickers) != set(scope.memberships):
        raise ValueError("scope_membership_parity_failure")
    # Structural seal: ANY nonempty integrity_breaches rejects before artifact,
    # reference/lineage, cell, or queue work. No string-shape exceptions: even
    # a fabricated debt-shaped string must not bypass this gate. Eligibility
    # debt (decision_grade_eligible=false) is evidence-only intake debt and is
    # NOT checked here; it never appears in integrity_breaches per contract.
    if tuple(getattr(scope, "integrity_breaches", None) or ()):
        raise ValueError("structural_scope_integrity_breach")
    controller = controller or _read_artifact(CONTROLLER_PATH)
    quote = quote or _source_from_controller(controller, "quote_snapshot", "tmp/intraday-alerts/quote-snapshot-proof.json")
    quote_validation = quote_validation or _source_from_controller(
        controller, "quote_snapshot_validation", "tmp/intraday-alerts/quote-snapshot-proof-validation.json")
    analyst = analyst or _read_artifact(ANALYST_PATH)
    lineage_reader = lineage_reader or reference_lineage

    def rows_from(source: ArtifactSnapshot, key: str, symbol_key: str):
        value = (source.payload or {}).get(key)
        pairs = (list(value.items()) if isinstance(value, Mapping) else
                 [(r.get(symbol_key, ""), r) for r in value if isinstance(r, Mapping)]
                 if isinstance(value, list) else [])
        return _canonical_artifact_rows(scope, [(str(s), r) for s, r in pairs if isinstance(r, Mapping)])

    quotes, quote_issues, quote_debt = rows_from(quote, "snapshots", "symbol")
    controllers, controller_issues, controller_debt = rows_from(controller, "rows", "ticker")
    analysts, analyst_issues, analyst_debt = rows_from(analyst, "tickers", "ticker")
    controller_error = _source_error(controller, now, MAX_CONTROLLER_HOURS)
    if (controller.payload or {}).get("schema") != "veritas.alert_level_freshness_controller.v1":
        controller_error = controller_error or "controller_schema_mismatch"
    quote_error = _source_error(quote, now, MAX_QUOTE_HOURS)
    quote_error = quote_error or _source_error(quote_validation, now, MAX_QUOTE_HOURS)
    if not quote_proof_is_clean(dict(quote.payload or {}), dict(quote_validation.payload or {}),
                                expected_artifact_identity=quote.path):
        quote_error = quote_error or "quote_proof_not_clean"
    analyst_error = _source_error(analyst, now, MAX_ANALYST_HOURS)

    rows: dict[str, dict[str, Any]] = {}
    repair_queue: list[dict[str, Any]] = []
    material_states = {"invalidation_alert", "thesis_change", "catalyst_alert"}
    for ticker in scope.tickers:
        member = scope.memberships[ticker]
        row: dict[str, Any] = {"ticker": ticker, "tier": member.tier,
                              "decision_grade_eligible": member.decision_grade_eligible, "evidence": {}}
        evidence = row["evidence"]
        qrow, crow, arow = quotes.get(ticker, {}), controllers.get(ticker, {}), analysts.get(ticker, {})

        qstamp = qrow.get("source_timestamp_utc")
        qreason = quote_error or quote_issues.get(ticker)
        if not qrow:
            qreason = qreason or "quote_source_row_missing"
        elif not _positive_number(qrow.get("price")):
            qreason = qreason or "quote_price_invalid"
        qreason = qreason or _age_error(qstamp, now, MAX_QUOTE_HOURS)
        if not qreason:
            _, age_seconds, _ = _time_metadata(qstamp, now)
            policy = quote_evaluation_policy(dict(qrow), age_seconds / 3600, MAX_QUOTE_HOURS,
                quote_proof=dict(quote.payload or {}), quote_validation=dict(quote_validation.payload or {}),
                expected_artifact_identity=quote.path)
            # Re-evaluate the source timestamp against today's calendar instead
            # of trusting a historical producer's 'current' label indefinitely.
            current = classify_quote_freshness(qstamp, now)
            calendar_current = current.get("calendar_freshness_status") in {
                "fresh_intraday", "current_last_completed_session", "market_closed_expected_stale"}
            if not policy["calendar_current"] or not calendar_current:
                qreason = "quote_not_current"
        evidence["quote_session"] = _cell(ENROLLED_NOT_OBSERVED if qreason else OBSERVED,
            qreason or "quote_source_current", source=quote, stamp=qstamp, now=now,
            limit=MAX_QUOTE_HOURS, owner="scripts/intraday_quote_snapshot_proof.py")

        reference, lineage, reference_error = None, {}, None
        try:
            reference = access.reference_level(ticker)
        except Exception:
            # ANY reference-reader failure (KeyError/programming, guard
            # RuntimeError, sqlite3.Error, OSError) is systemic: a guard or
            # programming failure must not masquerade as per-ticker debt and
            # must not retry remaining members. Sanitized: the original
            # message is never propagated. BaseException (cancellation,
            # KeyboardInterrupt, SystemExit) is never caught.
            raise RuntimeError("coverage_reference_system_failure") from None
        try:
            raw_lineage = lineage_reader(ticker)
            lineage = {} if raw_lineage is None else dict(raw_lineage)
        except (TypeError, KeyError, ValueError, AttributeError):
            # Malformed lineage shape stays explicit per-ticker debt with
            # valid quote observations preserved.
            reference_error = "guarded_reference_read_error"
            lineage = {}
        except Exception:
            # SQL/OS/guard/runtime/resource failures abort distinctly.
            # Sanitized: the original message is never propagated.
            raise RuntimeError("coverage_lineage_system_failure") from None
        stamp = lineage.get("level_as_of_utc")
        checks = lineage.get("artifact_checks", [])
        fields = lineage.get("fields", [])
        required_fields = {"reference_price_low", "reference_price_high", "reference_invalidation_level"}
        field_names = [f.get("field_name") for f in fields if isinstance(f, Mapping)]
        lreason = reference_error
        if not lineage or not fields:
            lreason = lreason or "lineage_record_missing"
        elif (len(field_names) != len(REFERENCE_LEVEL_LINEAGE_FIELDS)
              or set(field_names) != REFERENCE_LEVEL_LINEAGE_FIELDS):
            lreason = lreason or "lineage_field_set_incomplete_or_duplicate"
        elif lineage.get("lineage_validation_ok") is not True or not checks or any(
            c.get("hash_matches") is not True for c in checks if isinstance(c, Mapping)
        ) or any(not isinstance(c, Mapping) for c in checks):
            lreason = lreason or "lineage_not_clean"
        field_ages = [_age_error(f.get("source_generated_at_utc"), now, MAX_LEVEL_HOURS)
                      for f in fields if isinstance(f, Mapping)]
        lreason = lreason or next((x for x in field_ages if x), None) or _age_error(stamp, now, MAX_LEVEL_HOURS)
        evidence["lineage"] = _cell(ENROLLED_NOT_OBSERVED if lreason else OBSERVED,
            lreason or "current_hash_checked_reference_lineage", source=None, stamp=stamp, now=now,
            limit=MAX_LEVEL_HOURS, owner="scripts/alert_level_freshness_controller.py:reference_lineage")
        evidence["lineage"]["source_bindings"] = [
            {k: c.get(k) for k in ("path", "expected_sha256", "actual_sha256", "hash_matches")}
            for c in checks if isinstance(c, Mapping)]
        rreason = reference_error
        values = [getattr(reference, name, None) for name in sorted(required_fields)]
        if reference is None or not all(_positive_number(v) for v in values):
            rreason = rreason or "reference_level_missing_or_invalid"
        elif reference.reference_price_low > reference.reference_price_high:
            rreason = rreason or "reference_band_inverted"
        rreason = rreason or lreason
        evidence["reference_level"] = _cell(ENROLLED_NOT_OBSERVED if rreason else OBSERVED,
            rreason or "current_guarded_reference", source=None, stamp=stamp, now=now,
            limit=MAX_LEVEL_HOURS, owner="FinanceSqlCanonAccess.reference_level")

        areason = analyst_error or analyst_issues.get(ticker)
        apayload = analyst.payload or {}
        if not arow:
            areason = areason or "analyst_source_row_missing"
        elif apayload.get("status") == "placeholder_manual_required":
            areason = areason or "analyst_placeholder_manual_required"
        elif apayload.get("status") != "ok" or apayload.get("tier_sets") is not None:
            areason = areason or "analyst_quarantined"
        elif arow.get("source_status") != "auto_sourced_yfinance" or arow.get("cross_check_conflict") != "pass":
            areason = areason or "analyst_unavailable_partial_or_not_cross_checked"
        lineage_a = arow.get("source_lineage", {})
        if not isinstance(lineage_a, Mapping) or not lineage_a.get("source_url") or not lineage_a.get("evidence_digest_sha256"):
            areason = areason or "analyst_lineage_missing"
        areason = areason or _age_error(arow.get("as_of"), now, MAX_ANALYST_HOURS)
        evidence["analyst_symbol"] = _cell(ENROLLED_NOT_OBSERVED if areason else OBSERVED,
            areason or "weekly_cross_checked_analyst_context", source=analyst, stamp=arow.get("as_of"),
            now=now, limit=MAX_ANALYST_HOURS, owner="scripts/analyst_consensus_refresh.py")

        freason = controller_error or controller_issues.get(ticker)
        if not crow:
            freason = freason or "controller_row_missing"
        elif crow.get("validation_status") != "ok" or crow.get("freshness_status") not in {
                "current_intraday", "current_last_completed_session_monitor"}:
            freason = freason or "controller_evidence_review_required"
        freason = freason or qreason or rreason
        evidence["freshness"] = _cell(ENROLLED_NOT_OBSERVED if freason else OBSERVED,
            freason or "current_alert_evaluation", source=controller,
            stamp=(controller.payload or {}).get("generated_at_utc"), now=now,
            limit=MAX_CONTROLLER_HOURS, owner="scripts/alert_level_freshness_controller.py")
        evidence["recommendation_card"] = _cell(NO_OWNER_SURFACE,
            "current_recommendation_compiler_not_verified", source=None, stamp=None,
            now=now, limit=None, owner="WF85:Main_synthesis")
        evidence["queue"] = _cell(ENROLLED_NOT_OBSERVED,
            "repair_routing_present_review_not_observed", source=None, stamp=None,
            now=now, limit=24.0, owner="scripts/tier_entitlement_phase3d_observed_coverage.py:repair_queue")
        row["band_dependent_claims_blocked"] = bool(qreason or rreason or freason or not member.decision_grade_eligible)
        row["recommendation_complete"] = False
        # A reviewed incident is never inferred from an aged/conflicted source.
        incident = (not freason and crow.get("alert_state") in material_states)
        for evidence_class, cell in evidence.items():
            if cell["state"] == OBSERVED or evidence_class == "queue":
                continue
            priority = "P0" if incident else ("P1" if member.tier == "A" else "P2")
            next_step = {
                "quote_session": "Collect and validate missing/current quote evidence through the existing provider gate.",
                "reference_level": "Prepare source-backed reference repair; apply only through the exact canon gate.",
                "lineage": "Reconcile current source hashes, complete field lineage, and evidence age.",
                "analyst_symbol": "Refresh permitted secondary evidence and source-open cross-check; keep unavailable evidence quarantined.",
                "freshness": "Re-evaluate only after prerequisite evidence is repaired; do not overwrite timestamps to appear current.",
                "recommendation_card": "Main must join primary fundamentals, filings, catalysts, scenarios and contradiction review before synthesis.",
            }[evidence_class]
            repair_queue.append({"id": _sha256([ticker, evidence_class]), "ticker": ticker,
                "tier": member.tier, "evidence_class": evidence_class, "priority": priority,
                "reason": cell["reason"], "evidence_age_seconds": cell["age_seconds"],
                "source_path": cell["artifact_path"], "source_sha256": cell["artifact_sha256"],
                "owner": "Veritas Main", "next_step": next_step, "state": "pending_review",
                "first_seen_utc": None, "reviewed_at_utc": None, "queue_age_seconds": None,
                "queue_age_status": "unavailable_no_review_ledger", "review_interval_hours": 24,
                "automatic_action": False})
        rows[ticker] = row
    repair_queue.sort(key=lambda x: (x["priority"], -(x["evidence_age_seconds"] or 0), x["ticker"], x["evidence_class"]))
    return {
        "schema": "veritas.tier_entitlement.phase3g.current_coverage.v1",
        "status": "coverage_debt" if repair_queue else "review_only_projection",
        "generated_at_utc": now.isoformat().replace("+00:00", "Z"),
        "scope": _scope_summary(scope), "resolver_invocation_count": resolver_calls,
        "authority": {"projection_only": True, "gate_input": False, "automatic_action": False},
        "rows": list(rows.values()), "coverage_counts": _coverage_counts(rows),
        "source_presence_counts": {"quote_session": len(quotes), "controller": len(controllers), "analyst_symbol": len(analysts)},
        "artifact_symbol_debt": {"quote_session": quote_debt, "controller": controller_debt, "analyst_symbol": analyst_debt},
        "repair_queue": repair_queue,
        "repair_queue_summary": {"queued": len(repair_queue), "reviewed": None, "deferred": None,
            "oldest_queue_age_seconds": None, "review_sla_proven": False,
            "reason": "routing_projection_is_not_an_observed_review_ledger"},
        "capacity": {"provider_calls": 0, "provider_capacity_proven": False,
            "research_review_capacity_proven": False, "scope_truncation": False},
        "cutover_complete": False, "burn_in_complete": False,
    }


def safe_output_path(path: Path) -> Path:
    resolved, root = path.resolve(), ROOT.resolve()
    try:
        parts = resolved.relative_to(root).parts
    except ValueError as exc:
        raise ValueError("coverage_output_outside_workspace") from exc
    if (len(parts) < 3 or parts[0] != "tmp" or
            not (parts[1] == "tier-entitlement-phase3g" or parts[1].startswith("phase3g-")) or
            resolved.suffix.lower() != ".json"):
        raise ValueError("coverage_output_requires_distinct_phase3g_tmp_json")
    return resolved
