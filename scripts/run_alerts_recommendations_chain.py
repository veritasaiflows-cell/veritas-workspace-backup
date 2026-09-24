#!/usr/bin/env python3
"""Run the bounded alerts-and-recommendations finance chain."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Sequence

from finance_sql_canon_access import (
    DynamicEntitlementExternalGateError,
    DynamicEntitlementScope,
    FinanceSqlCanonAccess,
    require_dynamic_entitlement_external_gate,
    verify_dynamic_entitlement_payload,
)
from dynamic_entitlement_provider_policy import (
    ProviderPolicy,
    ProviderPolicyError,
    load_provider_policy,
    read_daily_budget,
    reserve_provider_calls,
    settle_provider_calls,
)
from phase3f_external_canary_approval import (
    Phase3FApprovalError,
    Phase3FCanaryAuthorization,
    _exclusive_durable_json_write,
    authorize_from_policy,
    recheck_phase3f_expiry,
    require_phase3f_input_bytes,
    skipped_phase3f_component_metrics,
    strict_canonical_evidence_json_object,
)


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
WINDOWS = {"morning", "midday", "post-close", "weekly"}
PHASE3F_POLICY_RUN_ROOT = "tmp/phase3f-policy-runs"

# Each component's upstream provider, so the policy's provider allowlist is
# enforced on the real path rather than only describing intent. Alert-level
# freshness reads Alpaca market-data GETs under the standing policy;
# analyst consensus remains on yfinance on its separate weekly contract.
COMPONENT_PROVIDERS = {
    "analyst_consensus": "yfinance",
    "alert_level_freshness": "alpaca_market_data",
}

AUTHORITY = {
    "review_only": True,
    "alerts_and_non_executing_recommendations_only": True,
    "writes_finance_canon": False,
    "maintains_portfolio_state": False,
    "maintains_simulated_account_state": False,
    "capital_or_order_authority": False,
    "paper_or_live_execution_allowed": False,
    "owner_approval_inferred": False,
}

RETIRED_STAGE_SCRIPTS = {
    "run_finance_refresh_chain.py",
    "band_refresh.py",
    "auto_apply_entry_band_maintenance.py",
    "auto_apply_position_sizing_semantic_sync.py",
    "portfolio_mutation_proposal_generator.py",
    "canon_volatile_execution_board_sync.py",
    "deployment_readiness_surface.py",
    "full_portfolio_view.py",
}

ALERT_TICKERS = [
    "ETN", "JPM", "NVDA", "GOOG", "MSFT", "GS", "VRT", "BRK.B", "XOM",
    "LMT", "RTX", "AMZN", "CAT", "LLY", "CVX", "PLTR", "AMD", "LNG",
]


def iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_dict(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def dynamic_entitlement_preview(
    client: FinanceSqlCanonAccess | None = None,
) -> tuple[DynamicEntitlementScope, dict[str, Any]]:
    """Resolve once for a provider-inert dynamic entitlement preview."""

    scope = (client or FinanceSqlCanonAccess()).dynamic_entitlement_scope()
    payload = scope.payload()
    verify_dynamic_entitlement_payload(payload, scope.fingerprint)
    return scope, {
        "scope": payload,
        "external_scope_gate": "not_enabled",
        "provider_calls": 0,
        "subprocess_stages": 0,
        "output_writes": 0,
    }


def child_scope_plan(scope_payload: dict[str, Any], fingerprint: str) -> dict[str, Any]:
    """Validate a parent-provided scope payload without querying guarded SQL."""

    verified = verify_dynamic_entitlement_payload(scope_payload, fingerprint)
    return {
        "fingerprint": verified,
        "member_count": len(scope_payload.get("members") or []),
        "source": scope_payload.get("source"),
    }


def digest_source_coherence(
    window: str,
    *,
    controller_path: Path | None = None,
    digest_path: Path | None = None,
) -> dict[str, Any]:
    controller_file = controller_path or (TMP / "alert-level-freshness-controller.json")
    digest_file = digest_path or (TMP / f"finance-alert-os-{window}-digest.json")
    controller = load_dict(controller_file)
    digest = load_dict(digest_file)
    source = digest.get("source_artifacts") if isinstance(digest.get("source_artifacts"), dict) else {}
    alert_source = source.get("alert_levels") if isinstance(source.get("alert_levels"), dict) else {}
    actual_hash = file_sha256(controller_file)
    errors: list[str] = []
    if not controller or not digest:
        errors.append("controller or digest proof is missing")
    if alert_source.get("sha256") != actual_hash:
        errors.append("digest controller hash does not match the exact controller bytes")
    if alert_source.get("generated_at_utc") != controller.get("generated_at_utc"):
        errors.append("digest controller generation does not match")
    if digest.get("summary") != controller.get("summary"):
        errors.append("digest summary does not match controller summary")
    if digest.get("status") != "ok" or (digest.get("validation") or {}).get("status") != "ok":
        errors.append("digest validation is not ok")
    status = "ok" if not errors else "error"
    return {
        "status": status,
        "controller_path": controller_file.relative_to(ROOT).as_posix() if controller_file.is_relative_to(ROOT) else str(controller_file),
        "digest_path": digest_file.relative_to(ROOT).as_posix() if digest_file.is_relative_to(ROOT) else str(digest_file),
        "controller_sha256": actual_hash,
        "controller_generated_at_utc": controller.get("generated_at_utc"),
        "digest_source_sha256": alert_source.get("sha256"),
        "digest_source_generated_at_utc": alert_source.get("generated_at_utc"),
        "alert_state_counts": (controller.get("summary") or {}).get("alert_state_counts"),
        "errors": errors,
    }


def stage_plan(
    window: str,
    *,
    send: bool = False,
    weekday_only: bool = False,
    write: bool = True,
) -> list[dict[str, Any]]:
    write_flag = ["--write"] if write else []
    stages: list[dict[str, Any]] = [
        {
            "name": "guarded_sql_access",
            "script": "finance_sql_canon_access.py",
            "args": [*write_flag, "--validate"],
            "critical": True,
        },
        {
            # Critical: a blocked quote proof deterministically fails
            # alert_level_freshness downstream, so treating it as a warning hid
            # the real root cause behind a decayed-freshness symptom.
            "name": "quote_snapshot_refresh",
            "script": "intraday_quote_snapshot_proof.py",
            "args": ["--symbols", *ALERT_TICKERS, "--timeout-seconds", "15"],
            "critical": True,
        },
    ]
    digest_args = ["--mode", window, *write_flag, "--write-md", "--validate"]
    if send:
        digest_args.append("--send")
    if weekday_only:
        digest_args.append("--weekday-only")
    stages.extend([
        {
            "name": "alert_level_freshness",
            "script": "alert_level_freshness_controller.py",
            "args": [*write_flag, "--validate"],
            "critical": True,
        },
        {
            "name": "recommendation_digest",
            "script": "finance_alert_os_digest.py",
            "args": digest_args,
            "critical": True,
        },
    ])
    return stages


def run_stage(stage: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    command = [sys.executable, str(ROOT / "scripts" / stage["script"]), *stage["args"]]
    started = time.perf_counter()
    try:
        run = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        returncode = run.returncode
        stdout_tail = run.stdout[-2000:]
        stderr_tail = run.stderr[-2000:]
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout_tail = str(exc.stdout or "")[-2000:]
        stderr_tail = str(exc.stderr or "")[-2000:]
        timed_out = True
    duration = round(time.perf_counter() - started, 3)
    return {
        "name": stage["name"],
        "script": stage["script"],
        "args": stage["args"],
        "critical": bool(stage["critical"]),
        "status": "ok" if returncode == 0 else "error",
        "returncode": returncode,
        "timed_out": timed_out,
        "duration_seconds": duration,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


RUN_RETENTION_DIR = TMP / "alerts-chain-runs"
# The midday window runs every 15 minutes on market days, so a per-window cap of
# 60 would rotate a Friday failure out before Monday review.
RUN_RETENTION_LIMIT = 400


def retain_run_payload(
    window: str,
    payload: dict[str, Any],
    *,
    retention_dir: Path | None = None,
) -> Path:
    """Keep a timestamped copy of each run.

    The stage scripts write to shared fixed paths, so a later window overwrites
    the artifacts of an earlier failure within minutes and destroys the evidence
    needed to diagnose it.
    """
    directory = retention_dir or RUN_RETENTION_DIR
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"{window}-{stamp}.json"
    write_json(path, payload)
    retained = sorted(directory.glob(f"{window}-*.json"))
    for stale in retained[:-RUN_RETENTION_LIMIT]:
        stale.unlink(missing_ok=True)
    return path


RECURRING_QUOTE_PROOF_REL = "tmp/intraday-alerts/quote-snapshot-proof.json"
RECURRING_QUOTE_VALIDATION_REL = "tmp/intraday-alerts/quote-snapshot-proof-validation.json"


def weekend_only_freshness_debt(controller_path) -> dict[str, Any]:
    """Decide whether review debt is pure weekend staleness (warning-grade).

    Eligible only when the controller artifact itself validates clean AND
    every row is a freshness_decay under market_closed_weekend_or_holiday
    whose quote is still the current last-completed session. Anything else
    (mixed states, non-weekend windows, quotes older than the last session,
    invalid proof) stays error-grade. Owner-approved 2026-09-20."""
    try:
        payload = json.loads(Path(controller_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return {"eligible": False, "reason": f"controller_unreadable:{type(exc).__name__}"}
    if not isinstance(payload, dict):
        return {"eligible": False, "reason": "controller_malformed"}
    if (payload.get("validation") or {}).get("status") != "ok":
        return {"eligible": False, "reason": "controller_validation_not_ok"}
    rows = payload.get("rows") or []
    if not rows:
        return {"eligible": False, "reason": "no_rows"}
    for row in rows:
        if not isinstance(row, dict):
            return {"eligible": False, "reason": "row_malformed"}
        if row.get("alert_state") != "freshness_decay":
            return {"eligible": False, "reason": f"non_decay_state:{row.get('alert_state')}"}
        if row.get("market_session_window") != "market_closed_weekend_or_holiday":
            return {"eligible": False, "reason": f"non_weekend_window:{row.get('market_session_window')}"}
        if row.get("quote_calendar_status") != "current_last_completed_session":
            return {"eligible": False, "reason": f"quote_not_last_session:{row.get('quote_calendar_status')}"}
    return {"eligible": True, "reason": "pure_weekend_decay_current_session",
            "ticker_count": len(rows)}


def emit_recurring_chain_receipts(
    window: str,
    result: dict[str, Any],
    *,
    quote_snapshot_json: bytes | None = None,
    quote_validation_json: bytes | None = None,
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Write the shared chain receipts the control-plane consumers read.

    The recurring dynamic lane does the same guarded-SQL and quote work the
    legacy stage plan did, but keeps it in exclusive or temporary storage, so
    the shared artifacts four consumers poll stopped advancing at the cutover
    while the alerts OS itself kept delivering. Receipts are emitted after the
    run and never change its outcome: a completed alerts run must not be failed
    by a bookkeeping write, and every receipt failure is reported in place.
    """
    stages: list[dict[str, Any]] = []
    started = time.perf_counter()
    # ROOT is the seam callers redirect; TMP is frozen at import and does not
    # follow it, so deriving paths here keeps a redirected run inside its own
    # tree instead of writing the real workspace proofs.
    tmp = ROOT / "tmp"
    quote_proof = ROOT / RECURRING_QUOTE_PROOF_REL
    quote_validation = ROOT / RECURRING_QUOTE_VALIDATION_REL

    # Same producer and arguments the legacy plan used: a local read-only canon
    # validation with no provider call and no canon mutation.
    guard = run_stage(
        {"name": "guarded_sql_access", "script": "finance_sql_canon_access.py",
         "args": ["--write", "--validate"], "critical": True},
        timeout_seconds,
    )
    stages.append(guard)

    quote: dict[str, Any] = {"name": "quote_snapshot_refresh",
                             "script": "phase3g_dynamic_execution._automatic_quote_intake",
                             "critical": True, "promoted_path": rel_to_root(quote_proof),
                             "promoted_validation_path": rel_to_root(quote_validation)}
    if quote_snapshot_json and quote_validation_json:
        try:
            # The intake already binds its validation to these shared paths; the
            # bytes promoted here are the exact bytes the run validated. The
            # validation sibling is promoted too because the intraday job's
            # contract requires both, and promoting one leaves a fresh snapshot
            # paired with a stale verdict.
            _atomic_promote_bytes(quote_proof, bytes(quote_snapshot_json))
            _atomic_promote_bytes(quote_validation, bytes(quote_validation_json))
            quote.update({"status": "ok",
                          "sha256": hashlib.sha256(bytes(quote_snapshot_json)).hexdigest(),
                          "validation_sha256": hashlib.sha256(bytes(quote_validation_json)).hexdigest()})
        except (OSError, ValueError) as exc:
            quote.update({"status": "error", "error": f"{type(exc).__name__}: {exc}"})
    else:
        quote.update({"status": "error", "error": "no_intake_snapshot_or_validation_bytes"})
    stages.append(quote)

    metrics = (result.get("component_metrics") or {}).get("alert_level_freshness") or {}
    freshness_stage = {"name": "alert_level_freshness", "critical": True,
                       "status": "ok" if metrics.get("status") in {"completed", "skipped_not_approved"} else "error",
                       "component_status": metrics.get("status")}
    stages.append(freshness_stage)

    recurring_digest = result.get("recurring_digest") or {}
    promotion = result.get("shared_promotion") or {}
    stages.append({"name": "recommendation_digest", "critical": True,
                   "status": "ok" if (recurring_digest.get("status") == "ok"
                                      and promotion.get("status") in {"ok", "ok_duplicate_suppressed"}) else "error",
                   "digest_status": recurring_digest.get("status"),
                   "shared_promotion_status": promotion.get("status"),
                   "digest_errors": recurring_digest.get("errors") or []})

    coherence = digest_source_coherence(
        window,
        controller_path=tmp / "alert-level-freshness-controller.json",
        digest_path=tmp / f"finance-alert-os-{window}-digest.json",
    )
    critical_errors = [stage["name"] for stage in stages if stage["status"] != "ok"]
    if result.get("status") != "completed":
        critical_errors.append(f"recurring_run_{result.get('status')}")
    if coherence["status"] != "ok":
        critical_errors.append("digest_source_coherence")
    warnings: list[str] = []
    # Owner-approved 2026-09-20: pure weekend staleness is warning-grade, never
    # error-grade — but only when it is the SOLE problem. Any companion failure
    # (guard, quote, digest, coherence) keeps the run red.
    if (set(critical_errors) <= {"alert_level_freshness", "recurring_run_completed_with_visible_debt"}
            and metrics.get("status") == "completed_with_review_debt"):
        tolerance = weekend_only_freshness_debt(tmp / "alert-level-freshness-controller.json")
        if tolerance["eligible"]:
            critical_errors = [e for e in critical_errors
                               if e not in {"alert_level_freshness", "recurring_run_completed_with_visible_debt"}]
            freshness_stage["status"] = "ok"
            freshness_stage["weekend_tolerance_applied"] = tolerance
            warnings.append(
                "weekend_freshness_debt_monitor_only:"
                f"{tolerance['ticker_count']}_tickers_decay_current_last_session")
    status = "error" if critical_errors else "ok"

    payload = {
        "schema": "veritas.alerts_recommendations_chain.v1",
        "generated_at_utc": iso_now(),
        "window": window,
        "status": status,
        "lane": "phase3f_dynamic_entitlement_recurring",
        "duration_seconds": round(time.perf_counter() - started, 3),
        "authority": dict(AUTHORITY),
        "run_id": result.get("run_id"),
        "results": stages,
        "summary": {
            "planned_stage_count": len(stages),
            "completed_stage_count": len(stages),
            "critical_errors": critical_errors,
            "warnings": warnings,
            "retired_stage_hits": [],
            "digest_source_coherence": coherence,
        },
        "validation": {"status": status, "errors": critical_errors, "warnings": warnings},
    }

    written: list[str] = []
    errors: list[str] = []
    for path in (tmp / f"alerts-recommendations-chain-{window}.json",
                 tmp / "alerts-recommendations-chain-current.json"):
        try:
            write_json(path, payload)
            written.append(rel_to_root(path))
        except OSError as exc:
            errors.append(f"{rel_to_root(path)}: {type(exc).__name__}: {exc}")
    try:
        written.append(rel_to_root(
            retain_run_payload(window, payload, retention_dir=tmp / "alerts-chain-runs")))
    except OSError as exc:
        errors.append(f"retain_run_payload: {type(exc).__name__}: {exc}")

    return {"status": status, "written": written, "write_errors": errors,
            "critical_errors": critical_errors, "warnings": warnings,
            "quote_snapshot_proof": quote["status"], "guarded_sql_access": guard["status"]}


def rel_to_root(path: Path) -> str:
    return path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)


def policy_run_id(now: datetime | None = None) -> str:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return "policy-" + moment.strftime("%Y%m%dT%H%M%SZ")


def write_policy_scope_overflow_debt(
    policy: ProviderPolicy,
    scope: DynamicEntitlementScope,
    *,
    run_id: str,
) -> Path:
    """Enumerate members and record the fail-closed overflow the policy declares."""

    path = TMP / "dynamic-entitlement-scope-overflow-debt.json"
    write_json(path, {
        "schema": "veritas.dynamic_entitlement.scope_overflow_debt.v1",
        "status": "fail_closed_zero_provider_calls",
        "generated_at_utc": iso_now(),
        "run_id": run_id,
        "policy_path": Path(policy.path).relative_to(ROOT).as_posix(),
        "policy_max_scope_count": policy.max_scope_count,
        "observed_scope_count": len(scope.memberships),
        "scope_fingerprint": scope.fingerprint,
        "members": sorted(scope.memberships),
        "provider_calls": 0,
        "owner_action": (
            "Raise max_scope_count in the standing provider policy, or reduce "
            "Tier A+B membership. No provider call was made."
        ),
    })
    return path


def prepare_policy_canary(
    *,
    components: Sequence[str],
    run_id: str,
    client: FinanceSqlCanonAccess | None = None,
    now_utc: datetime | None = None,
    input_hashes: dict[str, str] | None = None,
    run_root: str = PHASE3F_POLICY_RUN_ROOT,
    policy_path: Path | None = None,
) -> tuple[ProviderPolicy, Phase3FCanaryAuthorization, dict[str, Any]]:
    """Resolve scope, admit it against the standing policy, and reserve budget.

    Budget is reserved before the authorization is handed to any child, so a
    crash after this point can only underspend, never overspend.
    """

    policy = load_provider_policy(ROOT, policy_path=policy_path)
    access = client or FinanceSqlCanonAccess()
    # The envelope tracks the policy ceiling rather than a fixed count so
    # membership growth admits normally instead of reading as overflow.
    scope = access.dynamic_entitlement_scope(
        envelope_name="standing_provider_policy",
        envelope_count=policy.max_scope_count,
    )
    if len(scope.memberships) > policy.max_scope_count or scope.overflow_tickers:
        write_policy_scope_overflow_debt(policy, scope, run_id=run_id)
        raise Phase3FApprovalError("provider_policy_scope_overflow")
    require_dynamic_entitlement_external_gate(
        scope,
        scope_origin="phase3f_dynamic_entitlement",
        workspace_root=ROOT,
        policy=policy,
    )
    for component_id in components:
        provider_id = COMPONENT_PROVIDERS.get(component_id)
        if provider_id is None:
            raise ProviderPolicyError("provider_policy_component_provider_unknown")
        policy.require_provider(provider_id)
    authorization = authorize_from_policy(
        policy,
        scope,
        components=components,
        run_id=run_id,
        run_root=run_root,
        workspace_root=ROOT,
        input_hashes=input_hashes,
        now_utc=now_utc,
    )
    provider_calls = sum(
        dict(authorization.approval.envelope.max_provider_method_attempts).get(name, 0)
        for name in components
    )
    reservation = (
        reserve_provider_calls(
            policy,
            provider_calls,
            now_utc=now_utc,
            run_id=run_id,
        )
        if provider_calls
        else {
            **read_daily_budget(policy, now_utc=now_utc),
            "reserved_this_run": 0,
            "run_id": run_id,
        }
    )
    return policy, authorization, reservation


def settled_call_count(metrics: dict[str, dict[str, Any]], reserved_this_run: int) -> int:
    """Total observed provider calls, falling back to the full reservation.

    A component that does not report an integer attempt count has not proven it
    spent nothing, so its reservation must stay consumed. Refunding on a missing
    or malformed key would hand back budget that was really spent.
    """
    total = 0
    for row in metrics.values():
        if not isinstance(row, dict):
            return reserved_this_run
        value = row.get("provider_method_attempts")
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return reserved_this_run
        total += value
    return total


def run_policy_canary(
    *,
    components: Sequence[str],
    run_id: str | None = None,
    alert_reference_evidence_json: bytes | None = None,
    alert_quote_snapshot_json: bytes | None = None,
    alert_quote_validation_json: bytes | None = None,
    client: FinanceSqlCanonAccess | None = None,
    now_utc: datetime | None = None,
    dynamic_execution: bool = False,
    recurring_reference_inputs: Any = None,
    recurring_window: str | None = None,
    delivery_intent: dict[str, Any] | None = None,
    delivery_sender: Any = None,
) -> dict[str, Any]:
    """Run approved components under the standing policy with parent-only writes."""

    recurring_manifest = None
    if recurring_reference_inputs is not None:
        from phase3g_recurring_reference_inputs import ReferenceInputs
        if type(recurring_reference_inputs) is not ReferenceInputs:
            raise Phase3FApprovalError("recurring_reference_inputs_untrusted")
        # New recurring path accepts only the directly acquired sealed package,
        # never raw v1 files with a self-authored sidecar. Check before policy,
        # receipt, reservation or component execution.
        recurring_manifest = recurring_reference_inputs.verify()
        if (client is not None or alert_reference_evidence_json is not None
                or not dynamic_execution or tuple(components) != ("alert_level_freshness",)
                or recurring_window not in WINDOWS):
            raise Phase3FApprovalError("recurring_inputs_incompatible")
        scope = recurring_reference_inputs._scope_for_execution()
        class CapturedScopeClient:
            def dynamic_entitlement_scope(self, **kwargs: Any) -> DynamicEntitlementScope:
                recurring_reference_inputs.verify()
                return scope
        client = CapturedScopeClient()
        alert_reference_evidence_json = recurring_reference_inputs.evidence
        import alert_level_freshness_controller as quote_owner
        try:
            snapshot = strict_canonical_evidence_json_object(bytes(alert_quote_snapshot_json or b""), maximum_bytes=10*1024*1024)
            validation = strict_canonical_evidence_json_object(bytes(alert_quote_validation_json or b""), maximum_bytes=2*1024*1024)
        except Phase3FApprovalError:
            raise
        except Exception as exc:
            raise Phase3FApprovalError("recurring_quote_contract_malformed") from exc
        if not isinstance(snapshot.get("snapshots"), list) or any(not isinstance(row, dict) for row in snapshot["snapshots"]):
            raise Phase3FApprovalError("recurring_quote_contract_malformed")
        try:
            quote_clean = quote_owner.quote_proof_is_clean(snapshot,validation)
        except Phase3FApprovalError:
            raise
        except Exception as exc:
            raise Phase3FApprovalError("recurring_quote_contract_malformed") from exc
        if not quote_clean:
            raise Phase3FApprovalError("recurring_quote_proof_invalid")
        observed = [r.get("symbol") for r in snapshot["snapshots"]]
        if any(not isinstance(t, str) or not t for t in observed):
            raise Phase3FApprovalError("recurring_quote_contract_malformed")
        aliases = {alias:t for t in scope.tickers for alias in (t,t.replace(".","-"),t.replace("-","."))}
        if any(t not in aliases for t in observed):
            raise Phase3FApprovalError("recurring_quote_scope_invalid")
        canonical_symbols = [aliases[t] for t in observed]
        if len(canonical_symbols) != len(set(canonical_symbols)):
            raise Phase3FApprovalError("recurring_quote_scope_invalid")
    elif recurring_window is not None:
        raise Phase3FApprovalError("recurring_reference_inputs_required")

    resolved_run_id = run_id or policy_run_id(now_utc)
    supplied_inputs = {
        "alert_reference_evidence": alert_reference_evidence_json,
        "alert_quote_snapshot": alert_quote_snapshot_json,
        "alert_quote_validation": alert_quote_validation_json,
    }
    if "alert_level_freshness" in components:
        if any(value is None for value in supplied_inputs.values()):
            raise Phase3FApprovalError("phase3f_alert_bound_inputs_required")
    # Under the standing policy the parent supplies these bytes, so the hash
    # binding is a parent/child consistency check rather than an owner attestation.
    input_hashes = {
        name: hashlib.sha256(bytes(value)).hexdigest()
        for name, value in supplied_inputs.items()
        if value is not None
    }
    if recurring_manifest is not None:
        input_hashes["recurring_reference_provenance"] = hashlib.sha256(recurring_reference_inputs.provenance).hexdigest()
    policy, authorization, reservation = prepare_policy_canary(
        components=components,
        run_id=resolved_run_id,
        client=client,
        now_utc=now_utc,
        input_hashes=input_hashes,
    )
    approval = authorization.approval
    if recurring_manifest is not None:
        recurring_reference_inputs.verify()
        if (authorization.scope.payload_sha256 != recurring_manifest["scope_payload_sha256"]
                or authorization.scope.fingerprint != recurring_manifest["scope_fingerprint"]):
            raise Phase3FApprovalError("recurring_sealed_scope_mismatch")
        require_phase3f_input_bytes(approval, name="recurring_reference_provenance", raw=recurring_reference_inputs.provenance)
    components = set(approval.envelope.approved_components)
    component_results: dict[str, dict[str, Any]] = {}
    metrics: dict[str, dict[str, Any]] = {}
    component_hashes: dict[str, str] = {}

    if "alert_level_freshness" in components:
        for name, raw_value in sorted(supplied_inputs.items()):
            raw = bytes(raw_value or b"")
            require_phase3f_input_bytes(approval, name=name, raw=raw)
            payload = strict_canonical_evidence_json_object(
                raw,
                maximum_bytes=10 * 1024 * 1024,
            )
            _exclusive_durable_json_write(
                approval.output_path(name),
                payload,
                workspace_root=approval.workspace_root,
                open_error_code="phase3f_bound_input_write_failed",
            )
        import alert_level_freshness_controller as alert_child

        # Owner-approved 2026-09-20: the weekly digest is a weekend review
        # product, so it evaluates quotes against the 84h weekly tolerance.
        # All other windows keep the 36h default (None).
        weekly_quote_age = (
            alert_child.WEEKLY_WINDOW_MAX_QUOTE_AGE_HOURS
            if recurring_window == "weekly" else None
        )
        alert_result = alert_child._build_phase3f_alert_component_with_authorization(
            authorization=authorization,
            reference_evidence_json=bytes(alert_reference_evidence_json or b""),
            quote_snapshot_json=bytes(alert_quote_snapshot_json or b""),
            quote_validation_json=bytes(alert_quote_validation_json or b""),
            max_quote_age_hours=weekly_quote_age,
            **({"dynamic_execution": True} if dynamic_execution else {}),
        )
        component_hashes["alert_level_freshness"] = _exclusive_durable_json_write(
            approval.output_path("alert_level_freshness"),
            alert_result["artifact"],
            workspace_root=approval.workspace_root,
            open_error_code="phase3f_component_output_write_failed",
        )
        component_results["alert_level_freshness"] = alert_result["artifact"]
        metrics["alert_level_freshness"] = alert_result["metrics"]
    else:
        metrics["alert_level_freshness"] = skipped_phase3f_component_metrics(
            "alert_level_freshness"
        )

    if "analyst_consensus" in components:
        import analyst_consensus_refresh as analyst_child

        analyst_result = analyst_child._build_phase3f_analyst_component_with_authorization(
            authorization=authorization,
        )
        if dynamic_execution:
            members = json.loads(authorization.scope.canonical_bytes)["members"]
            rows = analyst_result["artifact"].get("tickers", {})
            analyst_result["artifact"]["dynamic_entitlement"] = {
                "members": members,
                "decision_grade_debt": [row["ticker"] for row in members if not row["decision_grade_eligible"]],
                "evidence_debt": [row["ticker"] for row in members
                                  if rows.get(row["ticker"], {}).get("source_status") != "auto_sourced_yfinance"],
            }
            if (analyst_result["artifact"]["dynamic_entitlement"]["evidence_debt"]
                    and analyst_result["metrics"].get("status") == "completed"):
                analyst_result["metrics"]["status"] = "completed_with_review_debt"
        _exclusive_durable_json_write(
            approval.output_path("analyst_consensus"),
            analyst_result["artifact"],
            workspace_root=approval.workspace_root,
            open_error_code="phase3f_component_output_write_failed",
        )
        component_results["analyst_consensus"] = analyst_result["artifact"]
        metrics["analyst_consensus"] = analyst_result["metrics"]
    else:
        metrics["analyst_consensus"] = skipped_phase3f_component_metrics(
            "analyst_consensus"
        )

    recheck_phase3f_expiry(approval)
    # A crash before this point deliberately leaves the reservation open: the
    # actual spend is unknown, so the budget must not be handed back.
    if reservation.get("reserved_this_run"):
        try:
            reservation = settle_provider_calls(
                policy,
                settled_call_count(metrics, int(reservation["reserved_this_run"])),
                now_utc=now_utc,
                run_id=resolved_run_id,
            )
        except ProviderPolicyError as exc:
            # A run crossing the Phoenix day boundary cannot settle against the
            # day it reserved on. Losing the proof of completed provider work is
            # worse than losing the refund, and leaving the reservation open
            # keeps the budget consumed, which is the safe direction.
            reservation = dict(reservation)
            reservation["settlement_error"] = str(exc)
    proof_status = (
        "completed"
        if all(
            row.get("status") in {"completed", "skipped_not_approved"}
            for row in metrics.values()
        )
        else "completed_with_visible_debt"
    )
    proof = {
        "schema": "veritas.tier_entitlement.phase3f.canary_proof.v2",
        "status": proof_status,
        "authorization_source": "standing_provider_policy",
        "run_id": approval.record_id,
        "policy_path": Path(policy.path).relative_to(ROOT).as_posix(),
        "policy_sha256": approval.decision_packet_sha256,
        "scope_fingerprint": authorization.scope.fingerprint,
        "scope_payload_sha256": authorization.scope.payload_sha256,
        "scope_count": authorization.scope.count,
        "receipt_sha256": authorization.receipt_sha256,
        "approved_components": list(approval.envelope.approved_components),
        "daily_budget": reservation,
        "component_metrics": {
            name: metrics[name] for name in sorted(metrics)
        },
        "parent_only_output_writer": True,
        "raw_provider_payload_retained": False,
        "credentials_or_tokens_retained": False,
        "guarded_sql_tier_or_membership_writes": 0,
        "canon_mutations": 0,
        "recommendations_generated": 0,
        "owner_approval_inferred": False,
    }
    if recurring_manifest is not None:
        # Bind retained provenance and a local digest into the existing exclusive
        # run proof. Shared promotion happens only after the exclusive
        # controller and digest validate; external delivery never runs here.
        import finance_alert_os_digest as digest_owner
        controller = component_results["alert_level_freshness"]
        digest_errors = digest_owner.controller_semantic_errors(controller)
        age = digest_owner.controller_age_hours(controller, datetime.now(timezone.utc))
        if (controller.get("status") != "ok" or (controller.get("validation") or {}).get("status") != "ok"
                or age is None or age < -digest_owner.CLOCK_SKEW_TOLERANCE_HOURS
                or age > digest_owner.DEFAULT_MAX_CONTROLLER_AGE_HOURS):
            digest_errors.append("recurring_controller_not_current_valid_evidence")
        proof["recurring_reference_provenance"] = recurring_manifest
        proof["recurring_reference_provenance_sha256"] = input_hashes["recurring_reference_provenance"]
        authorized_at = datetime.now(timezone.utc)
        proof["authorized_at_utc"] = authorized_at.strftime("%Y-%m-%dT%H:%M:%SZ")
        proof["acquisition_to_authorization_latency_seconds"] = _acquisition_latency_seconds(
            recurring_manifest, authorized_at)
        proof["acquired_source_headroom"] = {
            key: recurring_manifest.get(key)
            for key in ("database_bytes", "capture_bytes", "capture_headroom_bytes",
                        "source_observation_count", "acquisition_latency_seconds")
        }
        # Truthfully named membership-selection evidence: this run performs
        # zero additional SQL membership selections and rehydrates the sealed
        # capture instead; the single acquisition transaction is evidenced by
        # the worker session below, never by a hardcoded count claim.
        proof["guarded_sql_membership_selection_evidence"] = {
            "additional_membership_selections_in_this_run": 0,
            "second_selection_performed": False,
            "acquisition_snapshot_semantics": recurring_manifest.get("snapshot_semantics"),
            "acquisition_session_id": recurring_manifest.get("session_id"),
            "scope_fingerprint": authorization.scope.fingerprint,
            "scope_payload_sha256": authorization.scope.payload_sha256,
        }
        proof["recurring_digest"] = {
            "status": "blocked" if digest_errors else "ok", "errors": digest_errors,
            "window": recurring_window, "controller_sha256": component_hashes["alert_level_freshness"],
            "summary": controller.get("summary"),
            "message_preview": None if digest_errors else digest_owner.build_message(recurring_window,controller),
            "external_delivery": "not_run",
        }
        proof["quote_collection"] = "automatic_policy_authorized_intake_settled_separate_reservation"
        proof["analyst_cadence"] = "not_run_separate_weekly_contract"
        if digest_errors:
            proof_status = proof["status"] = "completed_with_visible_debt"
            proof["shared_promotion"] = {
                "status": "not_attempted",
                "reason": "exclusive_controller_or_digest_invalid",
                "errors": list(digest_errors),
            }
        else:
            proof["shared_promotion"] = _promote_recurring_shared_outputs(
                window=str(recurring_window),
                controller=controller,
                message=str(proof["recurring_digest"]["message_preview"]),
                run_id=approval.record_id,
                scope_fingerprint=authorization.scope.fingerprint,
            )
            if proof["shared_promotion"].get("status") not in ("ok", "ok_duplicate_suppressed"):
                proof_status = proof["status"] = "completed_with_visible_debt"
        proof["delivery"] = _stash_delivery_record(
            delivery_intent=delivery_intent,
            delivery_sender=delivery_sender,
            window=str(recurring_window),
            controller_sha256=proof["shared_promotion"].get("controller_sha256"),
            scope_fingerprint=authorization.scope.fingerprint,
            promotion=proof["shared_promotion"],
            digest_errors=digest_errors,
            authorized_at=authorized_at,
        )
    proof_sha = _exclusive_durable_json_write(
        approval.output_path("canary_proof"),
        proof,
        workspace_root=approval.workspace_root,
        open_error_code="phase3f_canary_proof_write_failed",
    )
    return {
        "status": proof_status,
        "run_id": approval.record_id,
        "component_results": component_results,
        "component_metrics": metrics,
        "daily_budget": reservation,
        "canary_proof_sha256": proof_sha,
        **({"recurring_digest": proof["recurring_digest"],
            "recurring_reference_provenance_sha256": proof["recurring_reference_provenance_sha256"],
            "shared_promotion": proof.get("shared_promotion"),
            "delivery": proof.get("delivery"),
            "acquisition_to_authorization_latency_seconds": proof.get("acquisition_to_authorization_latency_seconds"),
            "guarded_sql_membership_selection_evidence": proof.get("guarded_sql_membership_selection_evidence")}
           if recurring_manifest is not None else {}),
    }


RECURRING_SHARED_CONTROLLER_REL = "tmp/alert-level-freshness-controller.json"
RECURRING_PROMOTION_PREIMAGE_BYTES_CAP = 10 * 1024 * 1024


def _shared_controller_path() -> Path:
    # Resolved from ROOT at call time: ROOT is the test redirect seam, TMP is
    # frozen at import, so a TMP-based path let a redirected test overwrite
    # the production controller (2026-09-23 S000/S001 pollution).
    return ROOT / RECURRING_SHARED_CONTROLLER_REL


def _shared_digest_path(window: str) -> Path:
    """Narrow shared target: the existing per-window digest output only."""
    return ROOT / "tmp" / f"finance-alert-os-{window}-digest.json"


def _acquisition_latency_seconds(manifest: dict[str, Any], authorized_at: datetime) -> float | None:
    """Authorization time minus the worker-recorded acquisition finish.

    None when the finish timestamp is absent or unparsable; never invented.
    """
    try:
        finished = manifest.get("acquisition_finished_at_utc")
        parsed = datetime.fromisoformat(str(finished).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return round((authorized_at - parsed.astimezone(timezone.utc)).total_seconds(), 3)
    except Exception:
        return None


def _capture_preimage(path: Path) -> dict[str, Any]:
    """Record exact prior existence/size/hash before the first shared write.

    Prior bytes are kept in memory (bounded by the caller) so rollback can
    restore exact bytes or absence; they are sanitized shared-output bytes.
    """
    rel = path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path)
    if path.is_symlink() or not path.is_file():
        return {"path": rel, "existed": False, "bytes": 0, "sha256": None, "raw": None}
    raw = path.read_bytes()
    return {"path": rel, "existed": True, "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(), "raw": raw}


def _atomic_promote_bytes(path: Path, raw: bytes) -> None:
    """Stage beside the target and atomically replace it."""
    import os
    import tempfile
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", dir=str(path.parent), prefix=path.name, suffix=".tmp", delete=False)
    try:
        with handle as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(handle.name, path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def _quarantine_promotion_evidence(*, run_id: str, window: str,
                                   staged: dict[str, bytes], receipt: dict[str, Any]) -> dict[str, Any]:
    """Quarantine mixed-mode evidence plus a machine-readable receipt."""
    qdir = ROOT / "tmp" / "recurring-promotion-quarantine"
    qdir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    names: list[str] = []
    for name, raw in staged.items():
        target = qdir / f"{stamp}-{run_id}-{name}.json"
        target.write_bytes(raw)
        names.append(target.relative_to(ROOT).as_posix() if target.is_relative_to(ROOT) else str(target))
    receipt_path = qdir / f"{stamp}-{run_id}-rollback-receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "dir": qdir.relative_to(ROOT).as_posix() if qdir.is_relative_to(ROOT) else str(qdir),
        "evidence": names,
        "receipt": receipt_path.relative_to(ROOT).as_posix() if receipt_path.is_relative_to(ROOT) else str(receipt_path),
    }


def _promote_recurring_shared_outputs(*, window: str, controller: dict[str, Any],
                                      message: str, run_id: str,
                                      scope_fingerprint: str) -> dict[str, Any]:
    """Transactionally promote exclusive artifacts to shared alerts outputs.

    Runs only after the exclusive controller and digest validate (caller
    gate). Targets are narrowly the existing shared controller and
    per-window digest paths. Preimage existence/bytes/hash are captured
    before the first write; writes stage then atomically replace; any
    failure restores exact prior bytes or absence, quarantines mixed-mode
    evidence, and returns a machine-readable rollback receipt. Unrelated
    files are never touched.
    """
    targets = {
        "controller": _shared_controller_path(),
        "digest": _shared_digest_path(window),
    }
    generated_at = controller.get("generated_at_utc")
    summary = controller.get("summary")
    if not isinstance(generated_at, str) or not generated_at or summary is None:
        return {"status": "not_attempted", "reason": "exclusive_controller_missing_promotion_fields"}
    staged = {
        "controller": (json.dumps(controller, indent=2, sort_keys=True).encode("utf-8") + b"\n"),
        "digest": (json.dumps({
            "window": window,
            "generated_at_utc": generated_at,
            "status": "ok",
            "source_artifacts": {"alert_levels": {"generated_at_utc": generated_at}},
            "summary": summary,
            "validation": {"status": "ok"},
            "message": message,
            "provenance": {"run_id": run_id, "scope_fingerprint": scope_fingerprint,
                            "recurring": True},
        }, indent=2, sort_keys=True).encode("utf-8") + b"\n"),
    }
    staged_controller_sha = hashlib.sha256(staged["controller"]).hexdigest()
    staged["digest"] = (json.dumps({
        **json.loads(staged["digest"].decode("utf-8")),
        "source_artifacts": {"alert_levels": {"sha256": staged_controller_sha,
                                                "generated_at_utc": generated_at}},
    }, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    preimages = {name: _capture_preimage(path) for name, path in targets.items()}
    if any((pre.get("raw") or b"") and len(pre["raw"] or b"") > RECURRING_PROMOTION_PREIMAGE_BYTES_CAP
           for pre in preimages.values()):
        return {"status": "not_attempted", "reason": "preimage_too_large",
                "preimages": {n: {k: p[k] for k in ("path", "existed", "bytes", "sha256")}
                               for n, p in preimages.items()}}
    try:
        prior_digest_raw = (preimages["digest"]["raw"] or b"")
        if preimages["digest"]["existed"]:
            try:
                prior_digest = json.loads(prior_digest_raw.decode("utf-8"))
                prior_sha = ((prior_digest.get("source_artifacts") or {}).get("alert_levels") or {}).get("sha256")
            except Exception:
                prior_sha = None
            if prior_sha == staged_controller_sha:
                return {"status": "ok_duplicate_suppressed", "reason": "shared_digest_already_current",
                        "controller_sha256": staged_controller_sha,
                        "digest_sha256": hashlib.sha256(staged["digest"]).hexdigest()}
    except Exception as exc:
        return {"status": "not_attempted", "reason": f"duplicate_check_failed: {type(exc).__name__}"}
    receipt: dict[str, Any] = {
        "schema": "veritas.recurring.shared_promotion_receipt.v1",
        "run_id": run_id,
        "window": window,
        "controller_sha256": staged_controller_sha,
        "digest_sha256": hashlib.sha256(staged["digest"]).hexdigest(),
        "preimages": {n: {k: p[k] for k in ("path", "existed", "bytes", "sha256")}
                       for n, p in preimages.items()},
    }
    promoted: list[str] = []
    try:
        for name, path in targets.items():
            _atomic_promote_bytes(path, staged[name])
            promoted.append(name)
        coherence = digest_source_coherence(window)
        if coherence["status"] != "ok":
            raise RuntimeError(f"shared_coherence_failed: {coherence['errors']}")
        receipt.update({"status": "ok", "promoted": promoted,
                        "coherence": {k: coherence[k] for k in ("controller_sha256", "alert_state_counts")}})
        return receipt
    except Exception as exc:
        restored: list[dict[str, Any]] = []
        restore_error: str | None = None
        for name, path in targets.items():
            if name not in promoted:
                continue
            try:
                prior = preimages[name]
                if prior["existed"]:
                    _atomic_promote_bytes(path, prior["raw"] or b"")
                else:
                    path.unlink(missing_ok=True)
                check = _capture_preimage(path)
                restored.append({"target": name, "path": prior["path"],
                                 "restored_prior_existence": prior["existed"],
                                 "hash_matches_preimage": check["sha256"] == prior["sha256"]})
            except Exception as restore_exc:
                restore_error = f"{name}: {type(restore_exc).__name__}"
        receipt.update({"status": "rolled_back" if restore_error is None else "rollback_failed",
                        "error": f"{type(exc).__name__}: {exc}",
                        "promoted_before_failure": promoted,
                        "restored": restored,
                        "restore_error": restore_error})
        receipt["quarantine"] = _quarantine_promotion_evidence(
            run_id=run_id, window=window, staged=staged, receipt=receipt)
        return receipt


def _stash_delivery_record(*, delivery_intent: dict[str, Any] | None, delivery_sender: Any,
                           window: str, controller_sha256: Any, scope_fingerprint: str,
                           promotion: dict[str, Any], digest_errors: list[Any],
                           authorized_at: datetime) -> dict[str, Any]:
    """Record delivery intent without performing external delivery.

    Delivery may occur only after verified shared-output promotion, preserves
    --send/--weekday-only semantics, and is deduplicated on the promotion
    receipt. The sender hook exists so tests can inject a mock; production
    dispatch passes None, so nothing is ever sent from this lane. A real
    external message is irreversible and therefore excluded from rollback.
    """
    intent = dict(delivery_intent or {})
    dedupe_key = hashlib.sha256(
        f"{window}|{controller_sha256}|{scope_fingerprint}".encode("utf-8")).hexdigest()
    record: dict[str, Any] = {
        "send_requested": bool(intent.get("send_requested")),
        "weekday_only": bool(intent.get("weekday_only")),
        "dedupe_key": dedupe_key,
        "performed": False,
        "reason": "implementation_phase_no_external_delivery",
        "gated_on": "verified_shared_output_promotion",
        "promotion_status": (promotion or {}).get("status"),
        "digest_errors": list(digest_errors or []),
    }
    if not record["send_requested"]:
        record["reason"] = "send_not_requested"
        return record
    if digest_errors or (promotion or {}).get("status") not in ("ok", "ok_duplicate_suppressed"):
        record["reason"] = "shared_promotion_not_verified"
        return record
    if (promotion or {}).get("status") == "ok_duplicate_suppressed":
        record["reason"] = "duplicate_suppressed"
        return record
    if record["weekday_only"]:
        phoenix_weekday = ((authorized_at - timedelta(hours=7)).weekday()
                           if authorized_at.tzinfo is not None else None)
        record["phoenix_weekday"] = phoenix_weekday
        if phoenix_weekday is not None and phoenix_weekday >= 5:
            record["reason"] = "weekday_only_weekend_suppressed"
            return record
    if delivery_sender is None:
        return record
    try:
        delivery_sender({"window": window, "controller_sha256": controller_sha256,
                         "scope_fingerprint": scope_fingerprint, "dedupe_key": dedupe_key})
    except Exception as exc:
        record["reason"] = f"sender_failed: {type(exc).__name__}"
        return record
    record["performed"] = True
    record["reason"] = "injected_sender_invoked_after_verified_promotion"
    return record


def policy_gate_status() -> dict[str, Any]:
    """Report standing-policy admissibility without calling a provider."""

    try:
        policy = load_provider_policy(ROOT)
    except ProviderPolicyError as exc:
        return {
            "status": "error",
            "error": str(exc),
            "policy_loaded": False,
            "guarded_sql_scope_reads": 0,
            "provider_method_attempts": 0,
            "child_invocations": 0,
        }
    scope = FinanceSqlCanonAccess().dynamic_entitlement_scope(
        envelope_name="standing_provider_policy",
        envelope_count=policy.max_scope_count,
    )
    errors: list[str] = []
    try:
        require_dynamic_entitlement_external_gate(
            scope,
            scope_origin="phase3f_dynamic_entitlement",
            workspace_root=ROOT,
        )
    except DynamicEntitlementExternalGateError as exc:
        errors.append(str(exc))
    return {
        "status": "error" if errors else "admissible",
        "errors": errors,
        "policy_loaded": True,
        "policy_path": Path(policy.path).relative_to(ROOT).as_posix(),
        "allowed_components": list(policy.allowed_components),
        "allowed_providers": list(policy.allowed_providers),
        "scope_count": len(scope.memberships),
        "max_scope_count": policy.max_scope_count,
        "scope_fingerprint": scope.fingerprint,
        "planned_provider_method_attempts": policy.attempt_budget(len(scope.memberships)),
        "daily_limit": policy.max_daily_provider_calls,
        "guarded_sql_scope_reads": 1,
        "provider_method_attempts": 0,
        "child_invocations": 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("window", choices=sorted(WINDOWS))
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--weekday-only", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--dynamic-entitlement-preview", action="store_true")
    parser.add_argument("--dynamic-entitlement-scope", action="store_true")
    parser.add_argument("--provider-policy-status", action="store_true")
    parser.add_argument(
        "--scope-origin",
        default="ad_hoc",
        choices=("ad_hoc", "phase3f_dynamic_entitlement"),
    )
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    from phase3g_dynamic_execution import add_arguments, dispatch
    add_arguments(parser)
    args = parser.parse_args()

    dynamic_result = dispatch(args, components=("alert_level_freshness", "analyst_consensus"))
    if dynamic_result is not None:
        return dynamic_result

    if args.provider_policy_status:
        incompatible = sorted(
            name
            for name, flag in (
                ("--send", args.send),
                ("--weekday-only", args.weekday_only),
                ("--dry-run", args.dry_run),
                ("--dynamic-entitlement-preview", args.dynamic_entitlement_preview),
                ("--dynamic-entitlement-scope", args.dynamic_entitlement_scope),
                ("--write", args.write),
            )
            if flag
        )
        if incompatible:
            payload: dict[str, Any] = {
                "status": "error",
                "error": "provider_policy_incompatible_cli_options",
                "incompatible": incompatible,
                "guarded_sql_scope_reads": 0,
                "provider_method_attempts": 0,
                "child_invocations": 0,
            }
        else:
            payload = policy_gate_status()
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0 if payload.get("status") == "admissible" else 1

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
            "window": args.window,
            "dynamic_entitlement": preview,
            "errors": errors,
        }, indent=2, sort_keys=True))
        return 1 if errors else 0

    plan = stage_plan(
        args.window,
        send=args.send,
        weekday_only=args.weekday_only,
        write=args.write,
    )
    retired_hits = sorted({stage["script"] for stage in plan if stage["script"] in RETIRED_STAGE_SCRIPTS})
    results: list[dict[str, Any]] = []
    started = time.perf_counter()
    if not args.dry_run and not retired_hits:
        for stage in plan:
            result = run_stage(stage, args.timeout_seconds)
            results.append(result)
            if result["status"] != "ok" and stage["critical"]:
                break
    critical_errors = [result["name"] for result in results if result["critical"] and result["status"] != "ok"]
    warnings = [result["name"] for result in results if not result["critical"] and result["status"] != "ok"]
    coherence = {"status": "not_run", "errors": []}
    if not args.dry_run and not critical_errors and not retired_hits:
        coherence = digest_source_coherence(args.window)
        if coherence["status"] != "ok":
            critical_errors.append("digest_source_coherence")
    if retired_hits:
        critical_errors.append("retired_stage_detected")
    status = "planned" if args.dry_run else ("error" if critical_errors else "ok")
    payload = {
        "schema": "veritas.alerts_recommendations_chain.v1",
        "generated_at_utc": iso_now(),
        "window": args.window,
        "status": status,
        "duration_seconds": round(time.perf_counter() - started, 3),
        "authority": dict(AUTHORITY),
        "plan": plan,
        "results": results,
        "summary": {
            "planned_stage_count": len(plan),
            "completed_stage_count": len(results),
            "critical_errors": critical_errors,
            "warnings": warnings,
            "retired_stage_hits": retired_hits,
            "digest_source_coherence": coherence,
        },
        "validation": {
            "status": "ok" if status in {"ok", "planned"} and not retired_hits else "error",
            "errors": critical_errors,
            "warnings": warnings,
        },
    }
    output = TMP / f"alerts-recommendations-chain-{args.window}.json"
    if args.write:
        write_json(output, payload)
        write_json(TMP / "alerts-recommendations-chain-current.json", payload)
        retain_run_payload(args.window, payload)
    print(json.dumps({
        "status": status,
        "window": args.window,
        "duration_seconds": payload["duration_seconds"],
        "critical_errors": critical_errors,
        "warnings": warnings,
        "output": output.relative_to(ROOT).as_posix(),
    }, indent=2))
    return 1 if args.validate and payload["validation"]["status"] != "ok" else 0


if __name__ == "__main__":
    raise SystemExit(main())
