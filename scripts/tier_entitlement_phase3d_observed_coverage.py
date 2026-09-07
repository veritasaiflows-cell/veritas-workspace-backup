#!/usr/bin/env python3
"""Read-only Phase 3D observed-entitlement coverage projection.

The producer projects evidence owned elsewhere for one guarded-SQL Tier A+B
snapshot.  It does not plan work, derive a market state, modify finance data,
or make a missing source look current.  The three evidence states are
deliberately narrow:

* ``observed`` -- the named source supplied valid, current output.
* ``enrolled_but_not_observed`` -- a member exists but that source is absent,
  stale, conflicted, or has no defined recency rule.
* ``no_owner_surface`` -- this phase found no active source that can prove the
  evidence class.

Writing a JSON proof is opt-in.  No provider, subprocess, scheduler, or
write-capable SQL path is imported or invoked here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from finance_sql_canon_access import DynamicEntitlementScope, FinanceSqlCanonAccess


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUOTE_ARTIFACT = ROOT / "tmp" / "alert-level-freshness-controller.json"
DEFAULT_ANALYST_ARTIFACT = ROOT / "tmp" / "analyst-consensus-current.json"
DEFAULT_OUTPUT = ROOT / "tmp" / "tier-entitlement-v091-phase3d-observed-coverage.json"

OBSERVED = "observed"
ENROLLED_NOT_OBSERVED = "enrolled_but_not_observed"
NO_OWNER_SURFACE = "no_owner_surface"
VALID_STATES = {OBSERVED, ENROLLED_NOT_OBSERVED, NO_OWNER_SURFACE}


@dataclass(frozen=True)
class EvidenceSourceDefinition:
    """One named projection input, never a new evidence owner."""

    evidence_class: str
    owner_surface: str | None
    producer: str | None
    artifact_path: str | None
    required_fields: tuple[str, ...]
    recency_limit: str | None
    absent_reason: str


# This registry intentionally names one source for each class.  A ``None``
# owner is an explicit gap, not permission to discover a substitute source.
EVIDENCE_SOURCE_REGISTRY = (
    EvidenceSourceDefinition(
        "quote_session",
        "scripts/alert_level_freshness_controller.py",
        "alert_level_freshness_controller",
        "tmp/alert-level-freshness-controller.json",
        ("ticker", "quote_as_of_utc", "quote_freshness_status", "validation_status"),
        "controller_reported_current_market_session_or_last_completed_session",
        "quote_source_row_missing",
    ),
    EvidenceSourceDefinition(
        "reference_level",
        "FinanceSqlCanonAccess.reference_level_records",
        "guarded_sql_reference_levels",
        None,
        ("source_status", "validator_status", "source_generated_at_utc"),
        None,
        "reference_record_missing",
    ),
    EvidenceSourceDefinition(
        "lineage",
        "FinanceSqlCanonAccess.reference_level_records",
        "guarded_sql_source_lineage",
        None,
        ("source_status", "validator_status", "lineage_inserted_at_utc"),
        None,
        "lineage_record_missing",
    ),
    EvidenceSourceDefinition(
        "freshness",
        "FinanceSqlCanonAccess.evidence_freshness",
        "guarded_sql_evidence_freshness",
        None,
        ("resolution_state", "card_generated_at_utc"),
        None,
        "freshness_record_missing",
    ),
    EvidenceSourceDefinition(
        "analyst_symbol",
        "tmp/analyst-consensus-current.json",
        "analyst_consensus_refresh",
        "tmp/analyst-consensus-current.json",
        ("ticker", "as_of", "source_status"),
        "weekly_refresh",
        "analyst_source_row_missing",
    ),
    EvidenceSourceDefinition(
        "recommendation_card",
        "FinanceSqlCanonAccess.ticker_states",
        "guarded_sql_current_ticker_state",
        None,
        ("has_production_card",),
        None,
        "recommendation_card_missing",
    ),
    EvidenceSourceDefinition(
        "queue",
        None,
        None,
        None,
        (),
        None,
        "no_active_queue_owner",
    ),
)
REGISTRY_BY_CLASS = {item.evidence_class: item for item in EVIDENCE_SOURCE_REGISTRY}
QUOTE_CURRENT_STATES = {
    "current_intraday",
    "current_last_completed_session",
    "current_but_not_intraday_fresh",
}


@dataclass(frozen=True)
class ArtifactSnapshot:
    path: str
    sha256: str | None
    payload: Mapping[str, Any] | None
    error: str | None = None


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _safe_parse_utc(value: Any) -> tuple[datetime | None, str | None]:
    """Parse date-only, offset, and nanosecond ISO timestamps without guessing."""

    if not isinstance(value, str) or not value.strip():
        return None, "missing_timestamp"
    text = value.strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            return datetime.combine(date.fromisoformat(text), datetime.min.time(), timezone.utc), None
        normal = text[:-1] + "+00:00" if text.endswith("Z") else text
        match = re.match(r"^(.*\.)(\d{7,})([+-]\d{2}:\d{2})$", normal)
        if match:
            normal = f"{match.group(1)}{match.group(2)[:6]}{match.group(3)}"
        parsed = datetime.fromisoformat(normal)
        if parsed.tzinfo is None:
            return None, "unparseable_timestamp"
        return parsed.astimezone(timezone.utc), None
    except ValueError:
        return None, "unparseable_timestamp"


def _time_metadata(value: Any, now: datetime) -> tuple[str | None, int | None, str | None]:
    parsed, reason = _safe_parse_utc(value)
    if parsed is None:
        return None, None, reason
    age_seconds = int((now - parsed).total_seconds())
    if age_seconds < 0:
        return parsed.isoformat().replace("+00:00", "Z"), None, "future_timestamp"
    return parsed.isoformat().replace("+00:00", "Z"), age_seconds, None


def _read_artifact(path: Path) -> ArtifactSnapshot:
    try:
        resolved = path.resolve()
        root = ROOT.resolve()
        if root not in (resolved, *resolved.parents):
            return ArtifactSnapshot(path=str(path), sha256=None, payload=None, error="artifact_path_outside_workspace")
        raw = resolved.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, Mapping):
            return ArtifactSnapshot(path=resolved.relative_to(root).as_posix(), sha256=None, payload=None, error="artifact_not_object")
        return ArtifactSnapshot(
            path=resolved.relative_to(root).as_posix(),
            sha256=hashlib.sha256(raw).hexdigest(),
            payload=payload,
        )
    except FileNotFoundError:
        return ArtifactSnapshot(path=str(path), sha256=None, payload=None, error="artifact_missing")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ArtifactSnapshot(path=str(path), sha256=None, payload=None, error="artifact_unreadable")


def _artifact_binding(
    definition: EvidenceSourceDefinition,
    artifact: ArtifactSnapshot | None,
    *,
    evidence_as_of_utc: Any = None,
    class_state: str | None = None,
    now: datetime,
) -> dict[str, Any]:
    generated = artifact.payload.get("generated_at_utc") if artifact and artifact.payload else None
    generated_utc, generated_age, generated_reason = _time_metadata(generated, now)
    evidence_utc, evidence_age, evidence_reason = _time_metadata(evidence_as_of_utc, now)
    return {
        "producer": definition.producer,
        "artifact_path": artifact.path if artifact else definition.artifact_path,
        "artifact_sha256": artifact.sha256 if artifact else None,
        "artifact_generated_at_utc": generated_utc,
        "artifact_generated_age_seconds": generated_age,
        "artifact_timestamp_reason": generated_reason,
        "evidence_as_of_utc": evidence_utc,
        "age": evidence_age,
        "age_seconds": evidence_age,
        "evidence_timestamp_reason": evidence_reason,
        "recency_limit": definition.recency_limit,
        "class_state": class_state,
    }


def _cell(
    definition: EvidenceSourceDefinition,
    state: str,
    reason: str,
    binding: Mapping[str, Any],
    *,
    detail: str | None = None,
) -> dict[str, Any]:
    if state not in VALID_STATES:
        raise ValueError(f"invalid coverage state: {state}")
    if not reason or not isinstance(reason, str):
        raise ValueError("coverage reason must be an enumerated non-empty string")
    result = {
        "state": state,
        "reason": reason,
        "producer": binding["producer"],
        "artifact_path": binding["artifact_path"],
        "artifact_sha256": binding["artifact_sha256"],
        "artifact_generated_at_utc": binding["artifact_generated_at_utc"],
        "artifact_generated_age_seconds": binding["artifact_generated_age_seconds"],
        "artifact_timestamp_reason": binding["artifact_timestamp_reason"],
        "evidence_as_of_utc": binding["evidence_as_of_utc"],
        "age": binding["age"],
        "age_seconds": binding["age_seconds"],
        "evidence_timestamp_reason": binding["evidence_timestamp_reason"],
        "recency_limit": binding["recency_limit"],
        "class_state": binding["class_state"],
    }
    if detail:
        result["detail"] = detail
    return result


def _scope_summary(scope: DynamicEntitlementScope) -> dict[str, Any]:
    return {
        "source": scope.source,
        "fingerprint": scope.fingerprint,
        "count": len(scope.tickers),
        "tier_breakdown": dict(scope.tier_breakdown),
        "integrity_breaches": list(scope.integrity_breaches),
        "envelope_name": scope.envelope_name,
        "envelope_count": scope.envelope_count,
        "scope_over_envelope": list(scope.overflow_tickers),
    }


def _canonical_artifact_rows(
    scope: DynamicEntitlementScope,
    source_rows: Iterable[tuple[str, Mapping[str, Any]]],
) -> tuple[dict[str, Mapping[str, Any]], dict[str, str], list[dict[str, str]]]:
    """Canonicalize through the immutable resolver aliases only.

    ``issues`` has keys only for A+B members whose source rows collide.  Other
    symbols stay as debt records and cannot expand the scope.
    """

    canonical_rows: dict[str, Mapping[str, Any]] = {}
    issues: dict[str, str] = {}
    debts: list[dict[str, str]] = []
    members = set(scope.tickers)
    for raw_symbol, row in source_rows:
        symbol = str(raw_symbol or "").strip().upper()
        canonical = scope.aliases.get(symbol)
        if not canonical:
            debts.append({"symbol": symbol, "reason": "unresolved_symbol"})
            continue
        if canonical not in members:
            debts.append({"symbol": symbol, "reason": "out_of_scope"})
            continue
        if canonical in canonical_rows:
            issues[canonical] = "alias_conflict"
            continue
        canonical_rows[canonical] = row
    return canonical_rows, issues, debts


def _blank_rows(scope: DynamicEntitlementScope) -> dict[str, dict[str, Any]]:
    return {
        ticker: {
            "ticker": ticker,
            "tier": scope.memberships[ticker].tier,
            "evidence": {},
        }
        for ticker in scope.tickers
    }


def _apply_quote_coverage(
    rows: dict[str, dict[str, Any]],
    scope: DynamicEntitlementScope,
    artifact: ArtifactSnapshot,
    now: datetime,
) -> tuple[list[dict[str, str]], int]:
    definition = REGISTRY_BY_CLASS["quote_session"]
    payload = artifact.payload or {}
    source = payload.get("rows")
    source_rows = (
        [(str(item.get("ticker") or ""), item) for item in source if isinstance(item, Mapping)]
        if isinstance(source, list)
        else []
    )
    canonical_rows, issues, debts = _canonical_artifact_rows(scope, source_rows)
    for ticker, output in rows.items():
        row = canonical_rows.get(ticker)
        class_state = str(row.get("quote_freshness_status")) if row else None
        binding = _artifact_binding(
            definition,
            artifact,
            evidence_as_of_utc=row.get("quote_as_of_utc") if row else None,
            class_state=class_state,
            now=now,
        )
        if artifact.error:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, artifact.error, binding)
        elif ticker in issues:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, issues[ticker], binding)
        elif not row:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, definition.absent_reason, binding)
        elif row.get("validation_status") != "ok":
            result = _cell(definition, ENROLLED_NOT_OBSERVED, "quote_validation_not_ok", binding)
        elif binding["evidence_timestamp_reason"]:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, binding["evidence_timestamp_reason"], binding)
        elif class_state not in QUOTE_CURRENT_STATES:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, "quote_not_current", binding)
        else:
            result = _cell(definition, OBSERVED, "quote_source_current", binding)
        output["evidence"][definition.evidence_class] = result
    return debts, len(canonical_rows)


def _apply_analyst_coverage(
    rows: dict[str, dict[str, Any]],
    scope: DynamicEntitlementScope,
    artifact: ArtifactSnapshot,
    now: datetime,
) -> tuple[list[dict[str, str]], int]:
    definition = REGISTRY_BY_CLASS["analyst_symbol"]
    payload = artifact.payload or {}
    source = payload.get("tickers")
    source_rows = (
        [(str(symbol), item) for symbol, item in source.items() if isinstance(item, Mapping)]
        if isinstance(source, Mapping)
        else []
    )
    canonical_rows, issues, debts = _canonical_artifact_rows(scope, source_rows)
    artifact_status = str(payload.get("status") or "")
    for ticker, output in rows.items():
        row = canonical_rows.get(ticker)
        class_state = str(row.get("source_status")) if row else artifact_status or None
        binding = _artifact_binding(
            definition,
            artifact,
            evidence_as_of_utc=row.get("as_of") if row else None,
            class_state=class_state,
            now=now,
        )
        if artifact.error:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, artifact.error, binding)
        elif ticker in issues:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, issues[ticker], binding)
        elif not row:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, definition.absent_reason, binding)
        elif artifact_status == "placeholder_manual_required":
            result = _cell(definition, ENROLLED_NOT_OBSERVED, "analyst_placeholder_manual_required", binding)
        elif binding["evidence_timestamp_reason"]:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, binding["evidence_timestamp_reason"], binding)
        elif not row.get("source_status"):
            result = _cell(definition, ENROLLED_NOT_OBSERVED, "analyst_source_status_missing", binding)
        else:
            result = _cell(definition, OBSERVED, "analyst_symbol_current", binding)
        output["evidence"][definition.evidence_class] = result
    return debts, len(canonical_rows)


def _apply_reference_and_lineage(
    rows: dict[str, dict[str, Any]],
    scope: DynamicEntitlementScope,
    client: FinanceSqlCanonAccess,
    now: datetime,
) -> str | None:
    definitions = (REGISTRY_BY_CLASS["reference_level"], REGISTRY_BY_CLASS["lineage"])
    try:
        records = client.reference_level_records(scope.tickers)
    except RuntimeError as exc:
        for output in rows.values():
            for definition in definitions:
                binding = _artifact_binding(definition, None, class_state="lineage_blocked", now=now)
                output["evidence"][definition.evidence_class] = _cell(
                    definition,
                    ENROLLED_NOT_OBSERVED,
                    "lineage_blocked",
                    binding,
                    detail=str(exc),
                )
        return str(exc)
    for ticker, output in rows.items():
        record = records.get(ticker)
        for definition in definitions:
            class_state = "source_and_validator_ok" if record else "record_missing_or_lineage_not_ok"
            binding = _artifact_binding(
                definition,
                None,
                evidence_as_of_utc=record.source_generated_at_utc if record else None,
                class_state=class_state,
                now=now,
            )
            if not record:
                result = _cell(definition, ENROLLED_NOT_OBSERVED, definition.absent_reason, binding)
            elif binding["evidence_timestamp_reason"]:
                result = _cell(definition, ENROLLED_NOT_OBSERVED, binding["evidence_timestamp_reason"], binding)
            elif record.source_status != "ok" or record.validator_status != "ok":
                result = _cell(definition, ENROLLED_NOT_OBSERVED, "lineage_status_not_ok", binding)
            else:
                # The contract deliberately has no reference/lineage age rule.
                result = _cell(definition, ENROLLED_NOT_OBSERVED, "recency_limit_undefined", binding)
            output["evidence"][definition.evidence_class] = result
    return None


def _apply_freshness_coverage(
    rows: dict[str, dict[str, Any]],
    client: FinanceSqlCanonAccess,
    now: datetime,
) -> list[str]:
    definition = REGISTRY_BY_CLASS["freshness"]
    errors: list[str] = []
    for ticker, output in rows.items():
        try:
            record = client.evidence_freshness(ticker)
        except RuntimeError as exc:
            record = None
            errors.append(str(exc))
        class_state = str(record.resolution_state) if record and record.resolution_state else "record_missing"
        binding = _artifact_binding(
            definition,
            None,
            evidence_as_of_utc=record.card_generated_at_utc if record else None,
            class_state=class_state,
            now=now,
        )
        if not record:
            reason = "guarded_read_error" if errors else definition.absent_reason
            result = _cell(definition, ENROLLED_NOT_OBSERVED, reason, binding)
        elif record.resolution_state != "current":
            result = _cell(definition, ENROLLED_NOT_OBSERVED, "freshness_state_not_observed", binding)
        elif binding["evidence_timestamp_reason"]:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, binding["evidence_timestamp_reason"], binding)
        else:
            # This branch exists for a future source that supplies a current
            # evidence timestamp; current workspace data intentionally does not.
            result = _cell(definition, OBSERVED, "freshness_source_current", binding)
        output["evidence"][definition.evidence_class] = result
    return errors


def _apply_card_coverage(
    rows: dict[str, dict[str, Any]],
    scope: DynamicEntitlementScope,
    client: FinanceSqlCanonAccess,
    now: datetime,
) -> str | None:
    definition = REGISTRY_BY_CLASS["recommendation_card"]
    try:
        states = client.ticker_states(scope.tickers)
    except RuntimeError as exc:
        states = {}
        error = str(exc)
    else:
        error = None
    for ticker, output in rows.items():
        record = states.get(ticker)
        class_state = "card_present" if record and record.has_production_card else "card_absent"
        binding = _artifact_binding(definition, None, class_state=class_state, now=now)
        if error:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, "guarded_read_error", binding, detail=error)
        elif not record or not record.has_production_card:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, definition.absent_reason, binding)
        else:
            result = _cell(definition, ENROLLED_NOT_OBSERVED, "recency_limit_undefined", binding)
        output["evidence"][definition.evidence_class] = result
    return error


def _apply_queue_coverage(rows: dict[str, dict[str, Any]], now: datetime) -> None:
    definition = REGISTRY_BY_CLASS["queue"]
    binding = _artifact_binding(definition, None, class_state="no_owner_surface", now=now)
    for output in rows.values():
        output["evidence"][definition.evidence_class] = _cell(
            definition,
            NO_OWNER_SURFACE,
            definition.absent_reason,
            binding,
        )


def _coverage_counts(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    counts = {item.evidence_class: {state: 0 for state in sorted(VALID_STATES)} for item in EVIDENCE_SOURCE_REGISTRY}
    for output in rows.values():
        for evidence_class, cell in output["evidence"].items():
            counts[evidence_class][cell["state"]] += 1
    return counts


def build_observed_coverage_proof(
    *,
    client: FinanceSqlCanonAccess | None = None,
    quote_artifact: ArtifactSnapshot | None = None,
    analyst_artifact: ArtifactSnapshot | None = None,
    run_as_of_utc: str | None = None,
    envelope_count: int | None = 32,
) -> dict[str, Any]:
    """Build the Phase 3D projection from one immutable entitlement scope."""

    now, now_reason = _safe_parse_utc(run_as_of_utc) if run_as_of_utc else (datetime.now(timezone.utc), None)
    if now is None or now_reason:
        raise ValueError("run_as_of_utc must be an ISO-8601 timestamp")
    access = client or FinanceSqlCanonAccess()
    scope = access.dynamic_entitlement_scope(
        envelope_name="phase3d_observed_coverage",
        envelope_count=envelope_count,
    )
    if set(scope.tickers) != set(scope.memberships):
        raise RuntimeError("guarded_sql_scope_membership_parity_failure")
    quote = quote_artifact or _read_artifact(DEFAULT_QUOTE_ARTIFACT)
    analyst = analyst_artifact or _read_artifact(DEFAULT_ANALYST_ARTIFACT)
    rows = _blank_rows(scope)

    quote_debts, quote_presence = _apply_quote_coverage(rows, scope, quote, now)
    analyst_debts, analyst_presence = _apply_analyst_coverage(rows, scope, analyst, now)
    reference_error = _apply_reference_and_lineage(rows, scope, access, now)
    freshness_errors = _apply_freshness_coverage(rows, access, now)
    card_error = _apply_card_coverage(rows, scope, access, now)
    _apply_queue_coverage(rows, now)

    if set(rows) != set(scope.tickers):
        raise RuntimeError("phase3d_row_scope_parity_failure")
    ordered_rows = [rows[ticker] for ticker in scope.tickers]
    coverage_tuples = [
        [output["ticker"], evidence_class, output["evidence"][evidence_class]["state"]]
        for output in ordered_rows
        for evidence_class in (item.evidence_class for item in EVIDENCE_SOURCE_REGISTRY)
    ]
    blockers = [item for item in (reference_error, card_error, *freshness_errors) if item]
    proof = {
        "schema": "veritas.tier_entitlement.phase3d.observed_coverage.v1",
        "status": "blocked" if blockers else "review_only_projection",
        "run_as_of_utc": now.isoformat().replace("+00:00", "Z"),
        "authority": {
            "projection_only": True,
            "side_effects": "none",
            "gate_input": False,
        },
        "scope": _scope_summary(scope),
        "resolver_invocation_count": 1,
        "evidence_source_registry": [asdict(item) for item in EVIDENCE_SOURCE_REGISTRY],
        "evidence_source_registry_fingerprint": _sha256([asdict(item) for item in EVIDENCE_SOURCE_REGISTRY]),
        "source_presence_counts": {
            "quote_session": quote_presence,
            "analyst_symbol": analyst_presence,
        },
        "artifact_symbol_debt": {
            "quote_session": quote_debts,
            "analyst_symbol": analyst_debts,
        },
        "rows": ordered_rows,
        "coverage_counts": _coverage_counts(rows),
        "coverage_fingerprint": _sha256(coverage_tuples),
        "integrity_breaches": list(scope.integrity_breaches),
        "inherited_blockers": ["external_baseline_blocked"],
        "blocking_errors": blockers,
    }
    return proof


def _validate_output_vocabulary(proof: Mapping[str, Any]) -> None:
    """Keep the projection structurally unusable as an action gate."""

    forbidden = ("allowed", "approval", "approved", "ready", "deployable", "execution")

    def walk(value: Any) -> Iterable[str]:
        if isinstance(value, Mapping):
            for key, nested in value.items():
                yield str(key)
                yield from walk(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from walk(nested)
        elif isinstance(value, str):
            yield value

    hits = sorted({word for word in walk(proof) for forbidden_word in forbidden if forbidden_word in word.lower()})
    if hits:
        raise RuntimeError(f"phase3d_output_vocabulary_blocked:{hits}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only Phase 3D entitlement coverage projection.")
    parser.add_argument("--write", action="store_true", help="write the named local proof; otherwise print JSON")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--as-of-utc", default=None)
    parser.add_argument("--envelope-count", type=int, default=32)
    parser.add_argument("--current-alerts", action="store_true", help="opt in to current alerts-OS evidence and repair-debt projection")
    args = parser.parse_args()
    if args.current_alerts:
        from phase3g_alert_coverage import DEFAULT_OUTPUT as CURRENT_OUTPUT, build_current_alerts_coverage, safe_output_path
        proof = build_current_alerts_coverage(run_as_of_utc=args.as_of_utc)
        encoded = json.dumps(proof, indent=2, sort_keys=True) + "\n"
        if args.write:
            output = safe_output_path(CURRENT_OUTPUT if args.output == DEFAULT_OUTPUT else args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(encoded, encoding="utf-8")
            print(output.relative_to(ROOT.resolve()).as_posix())
        else:
            print(encoded, end="")
        return 0
    proof = build_observed_coverage_proof(
        run_as_of_utc=args.as_of_utc,
        envelope_count=args.envelope_count,
    )
    _validate_output_vocabulary(proof)
    encoded = json.dumps(proof, indent=2, sort_keys=True) + "\n"
    if args.write:
        output = args.output.resolve()
        if ROOT.resolve() not in (output, *output.parents):
            raise ValueError("output path must stay inside workspace")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
        print(output.relative_to(ROOT.resolve()).as_posix())
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
