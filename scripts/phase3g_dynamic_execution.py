"""Explicit, policy-bound dynamic CLI adapter; never a recurring cutover.

Alert inputs use the Phase 3F canonical reference-evidence schema and explicit
quote proof/validation files. Missing rows are debt, not a smaller scope.
No quote collection, digest generation, or external delivery is performed.
"""
from __future__ import annotations

import json
import sys
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import (
    FinanceSqlCanonAccess, require_dynamic_entitlement_external_gate,
    verify_dynamic_entitlement_payload,
)
from dynamic_entitlement_provider_policy import load_provider_policy
from phase3f_external_canary_approval import (
    strict_canonical_evidence_json_object, _resolve_safe_workspace_path,
    _exclusive_durable_json_write,
)


QUOTE_INTAKE_TIMEOUT_SECONDS = 15
PACKAGE_LIFETIME_SECONDS = 600
# Debt is deliberately not green: incomplete evidence must not exit 0 (owner decision 2026-09-05).
COMPLETED_STATUSES = ("completed",)


def add_arguments(parser: Any) -> None:
    parser.add_argument("--recurring-reference-inputs", action="store_true")
    parser.add_argument("--dynamic-run-id")
    parser.add_argument("--alert-reference-evidence", type=Path)
    parser.add_argument("--alert-quote-snapshot", type=Path)
    parser.add_argument("--alert-quote-validation", type=Path)
    if "--dry-run" not in parser._option_string_actions:
        parser.add_argument("--dry-run", action="store_true")


def dispatch(args: Any, *, components: tuple[str, ...]) -> int | None:
    """Return None only for the unchanged legacy lane; reject before any work."""
    flags = {arg.split("=", 1)[0] for arg in sys.argv[1:] if arg.startswith("--")}
    dynamic = args.dynamic_entitlement_preview or args.dynamic_entitlement_scope
    reserved = {"--dynamic-run-id", "--recurring-reference-inputs", "--alert-reference-evidence",
                "--alert-quote-snapshot", "--alert-quote-validation"}
    if not dynamic:
        if (flags & reserved or args.scope_origin != "ad_hoc"
                or (args.dry_run and len(components) == 1)):
            return _print_error("dynamic_options_require_dynamic_scope")
        return None
    recurring = getattr(args, "recurring_reference_inputs", False)
    base_forbidden = {"--tickers", "--out", "--output",
                        "--merge-existing", "--quarantine-existing",
                        "--max-quote-age-hours", "--max-level-age-days", "--timeout-seconds",
                        "--provider-policy-status"}
    # Delivery intent (--send/--weekday-only) is preserved for the recurring
    # lane and honored only after verified shared-output promotion; no
    # external delivery is performed in this implementation phase.
    forbidden = flags & (base_forbidden if recurring else (base_forbidden | {"--send", "--weekday-only"}))
    preview = args.dynamic_entitlement_preview or args.dry_run
    if (forbidden or (args.dynamic_entitlement_preview and args.dynamic_entitlement_scope)
            or (preview and args.write) or (preview and flags & reserved)):
        return _print_error("dynamic_incompatible_cli_options")
    if not preview and (not args.write or args.scope_origin != "phase3f_dynamic_entitlement"):
        return _print_error("dynamic_execution_requires_write_and_policy_origin")
    if recurring and (preview or components != ("alert_level_freshness", "analyst_consensus")
                      or not hasattr(args,"window") or args.alert_reference_evidence is not None
                      or getattr(args, "alert_quote_snapshot", None) is not None
                      or getattr(args, "alert_quote_validation", None) is not None):
        return _print_error("recurring_reference_inputs_incompatible")
    delivery_intent = {
        "send_requested": bool(getattr(args, "send", False)),
        "weekday_only": bool(getattr(args, "weekday_only", False)),
        "perform_delivery": False,
        "reason": "implementation_phase_no_external_delivery",
    }
    try:
        import run_alerts_recommendations_chain as chain

        if recurring:
            # Analyst refresh remains owned by its separate weekly contract.
            components = ("alert_level_freshness",)
        policy = load_provider_policy(chain.ROOT)
        if datetime.now(timezone.utc) < policy.effective_at_utc:
            raise ValueError("provider_policy_not_effective")
        for component in components:
            if component not in policy.allowed_components:
                raise ValueError("provider_policy_component_not_allowed")
            policy.require_provider(chain.COMPONENT_PROVIDERS[component])
        inputs: dict[str, bytes] = {}
        if not preview:
            for name in ("alert_reference_evidence", "alert_quote_snapshot", "alert_quote_validation"):
                if recurring:
                    # Sealed reference evidence plus automatic policy-authorized
                    # quote intake supply every recurring input; explicit files
                    # are rejected by the compatibility check above.
                    continue
                path = getattr(args, name)
                if "alert_level_freshness" in components:
                    if path is None:
                        raise ValueError("dynamic_alert_explicit_inputs_required")
                    # Read only workspace-contained, non-reparse files; never accept an output path.
                    relative = path.relative_to(chain.ROOT) if path.is_absolute() else path
                    safe = _resolve_safe_workspace_path(
                        chain.ROOT.resolve(), relative, must_exist=True, must_not_exist=False,
                        code="dynamic_input_path_invalid",
                    )
                    if safe.stat().st_size > 10 * 1024 * 1024:
                        raise ValueError("dynamic_input_too_large")
                    raw = safe.read_bytes()
                    strict_canonical_evidence_json_object(raw, maximum_bytes=10 * 1024 * 1024)
                    inputs[name + "_json"] = raw
                elif path is not None:
                    raise ValueError("dynamic_analyst_does_not_consume_alert_inputs")
        if recurring:
            from phase3g_recurring_reference_inputs import acquire_reference_inputs
            bound = acquire_reference_inputs(
                max_scope_count=policy.max_scope_count,
                package_lifetime_seconds=PACKAGE_LIFETIME_SECONDS,
            )
            intake = _automatic_quote_intake(
                chain, policy, bound,
                args.dynamic_run_id or "recurring-" + uuid.uuid4().hex,
            )
            result = chain.run_policy_canary(
                components=components, run_id=intake["run_id"],
                dynamic_execution=True, recurring_reference_inputs=bound,
                recurring_window=args.window,
                alert_quote_snapshot_json=intake["snapshot_json"],
                alert_quote_validation_json=intake["validation_json"],
                delivery_intent=delivery_intent, **inputs)
            result["quote_intake"] = intake["receipt"]
            print(json.dumps(result,indent=2,sort_keys=True))
            return 0 if result["status"] in COMPLETED_STATUSES else 1
        client = FinanceSqlCanonAccess()
        scope = client.dynamic_entitlement_scope(
            envelope_name="standing_provider_policy", envelope_count=policy.max_scope_count,
        )
        verify_dynamic_entitlement_payload(scope.payload(), scope.fingerprint)
        if scope.integrity_breaches:
            return _print_error("dynamic_entitlement_scope_integrity_breach",
                                scope=scope.payload(), provider_calls=0,
                                debt="sealed_upstream_gate_requires_separate_scoped_repair")
        overflow = len(scope.memberships) > policy.max_scope_count or bool(scope.overflow_tickers)
        if not overflow:
            require_dynamic_entitlement_external_gate(
                scope, scope_origin="phase3f_dynamic_entitlement", workspace_root=chain.ROOT, policy=policy,
            )
        if preview:
            print(json.dumps({"status": "blocked_scope_overflow" if overflow else "planned",
                              "scope": scope.payload(), "provider_calls": 0,
                              "subprocess_stages": 0, "output_writes": 0}, sort_keys=True))
            return 1 if overflow else 0
        if overflow:
            # Exclusive, generated basename: never overwrite the legacy shared
            # debt path or accept a caller-selected output filename.
            path = chain.ROOT / chain.PHASE3F_POLICY_RUN_ROOT / ("overflow-" + uuid.uuid4().hex + ".json")
            _exclusive_durable_json_write(path, {
                "status": "fail_closed_zero_provider_calls", "scope": scope.payload(),
                "members": sorted(scope.memberships), "provider_calls": 0,
                "policy_max_scope_count": policy.max_scope_count,
            }, workspace_root=chain.ROOT, open_error_code="dynamic_overflow_debt_write_failed")
            return _print_error("provider_policy_scope_overflow", scope=scope.payload())
        require_dynamic_entitlement_external_gate(
            scope, scope_origin=args.scope_origin, workspace_root=chain.ROOT, policy=policy,
        )
        # prepare_policy_canary retains ownership of authorization, reservation,
        # receipt, and locks. This adapter returns the SAME snapshot, not SQL.
        class ResolvedScope:
            def dynamic_entitlement_scope(self, **kwargs: Any) -> Any:
                return scope

        result = chain.run_policy_canary(
            components=components, run_id=args.dynamic_run_id or "dynamic-" + uuid.uuid4().hex,
            client=ResolvedScope(), dynamic_execution=True, **inputs,
        )
        result["dynamic_scope"] = scope.payload()
        result["aliases"] = dict(sorted(scope.aliases.items()))
        result["guarded_sql_scope_reads"] = 1
        result["quote_collection"] = "not_run_separate_provider_gate_required"
        result["digest_and_external_delivery"] = "not_run"
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if result["status"] in COMPLETED_STATUSES else 1
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        # Work may already have a conservative reservation/claim. Do not assert
        # zero calls or refund unknown spend after an execution failure.
        return _print_error(str(exc))


def _automatic_quote_intake(chain: Any, policy: Any, bound: Any, run_id: str) -> dict[str, Any]:
    """Policy-authorized automatic quote intake over the acquired A+B scope.

    Fail-before-reservation order: provenance/expiry verification, scope
    overflow, then policy authorization for the read-only Alpaca market-data
    GET. Only then is the maximum policy-permitted quote HTTP attempt count
    reserved; the single permitted GET runs through the existing read-only
    proof runner as a subprocess, and the observed attempt count is settled
    afterward. A crash or unparsable attempt log leaves the reservation
    consumed. No secrets, raw headers, raw bodies, account identifiers, or
    brokerage endpoints are retained; only sanitized proof bytes continue.
    """
    import shutil
    import subprocess
    import tempfile
    from dynamic_entitlement_provider_policy import (
        authorize_market_data_get,
        max_quote_http_attempts,
        reserve_provider_calls,
        settle_provider_calls,
    )
    from phase3f_external_canary_approval import strict_canonical_evidence_json_object

    bound.verify()  # expired or untrusted inputs fail before any reservation.
    evidence = strict_canonical_evidence_json_object(bound.evidence, maximum_bytes=10 * 1024 * 1024)
    tickers = list(evidence.get("tickers") or [])
    if not tickers or any(not isinstance(ticker, str) or not ticker for ticker in tickers):
        raise ValueError("recurring_scope_empty")
    if len(tickers) > policy.max_scope_count:
        raise ValueError("provider_policy_scope_overflow")
    authorize_market_data_get(
        policy,
        provider_id="alpaca_market_data",
        method="GET",
        url="https://data.alpaca.markets/v2/stocks/snapshots",
    )
    budget = max_quote_http_attempts(policy)
    quote_run_id = run_id + "-quotes"
    reserve_provider_calls(policy, budget, run_id=quote_run_id)

    workdir = Path(tempfile.mkdtemp(dir=str(chain.TMP), prefix="recurring-quote-intake-"))
    snap = workdir / "quote-snapshot.json"
    mark = workdir / "quote-snapshot.md"
    val = workdir / "quote-snapshot-validation.json"
    try:
        proc = subprocess.run(
            [sys.executable, str(chain.ROOT / "scripts" / "intraday_quote_snapshot_proof.py"),
             "--symbols", *tickers,
             "--timeout-seconds", str(QUOTE_INTAKE_TIMEOUT_SECONDS),
             "--retry-attempts", str(budget),
             "--attempt-budget", str(budget),
             "--output", str(snap),
             "--markdown-output", str(mark),
             "--validation-output", str(val)],
            cwd=chain.ROOT, text=True, encoding="utf-8", errors="replace",
            capture_output=True,
            timeout=QUOTE_INTAKE_TIMEOUT_SECONDS * budget + 30,
            check=False,
        )
    except Exception as exc:
        settle_provider_calls(policy, budget, run_id=quote_run_id)
        shutil.rmtree(workdir, ignore_errors=True)
        raise ValueError("recurring_quote_intake_failed") from exc
    try:
        observed = len((json.loads(proc.stdout or "") or {}).get("provider_attempt_log") or [])
    except Exception:
        observed = budget
    if type(observed) is not int or observed < 0 or observed > budget:
        observed = budget
    settlement = settle_provider_calls(policy, observed, run_id=quote_run_id)
    try:
        if proc.returncode != 0 or not snap.is_file() or not val.is_file():
            raise ValueError("recurring_quote_intake_failed")
        snapshot_json = snap.read_bytes()
        validation_json = val.read_bytes()
        try:
            strict_canonical_evidence_json_object(snapshot_json, maximum_bytes=10 * 1024 * 1024)
            strict_canonical_evidence_json_object(validation_json, maximum_bytes=2 * 1024 * 1024)
        except Exception as exc:
            raise ValueError("recurring_quote_contract_malformed") from exc
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    return {
        "run_id": run_id,
        "snapshot_json": snapshot_json,
        "validation_json": validation_json,
        "receipt": {
            "provider": "alpaca_market_data",
            "endpoint_class": "market_data_read_only_get_not_brokerage",
            "symbols": tickers,
            "attempts_reserved": budget,
            "attempts_observed": observed,
            "settlement": settlement,
            "secrets_or_raw_bodies_retained": False,
        },
    }


def _print_error(error: str, **extra: Any) -> int:
    print(json.dumps({"status": "error", "error": error, **extra}, sort_keys=True))
    return 1
