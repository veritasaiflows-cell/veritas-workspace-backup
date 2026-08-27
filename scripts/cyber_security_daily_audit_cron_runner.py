"""Cron proof wrapper for the bounded daily cyber-security audit.

Runs the audit script, verifies that its JSON artifact was regenerated after this
wrapper started, and writes a machine-checkable proof artifact for cron review.
"""

from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts" / "cyber_security_daily_audit.py"
AUDIT_JSON = ROOT / "tmp" / "cyber-security-daily-audit.json"
PROOF_JSON = ROOT / "tmp" / "cyber-security-daily-audit-cron-proof.json"
OPENCLAW_HOME = Path.home() / ".openclaw"
PREFILTER_MAX_AGE_HOURS = 30.0
PREFILTER_UNCHANGED_WARNING_MAX_AGE_HOURS = 96.0


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_z(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_utc(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if len(text) > limit else text


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_file_state(label: str, path: Path) -> dict[str, Any]:
    return {
        "label": label,
        "path": rel(path),
        "exists": path.exists(),
        "sha256": sha256_file(path),
    }


def build_input_signature() -> dict[str, Any]:
    sources = [
        source_file_state("openclaw_config", OPENCLAW_HOME / "openclaw.json"),
        source_file_state("exec_approvals", OPENCLAW_HOME / "exec-approvals.json"),
        source_file_state("producer:cyber_security_daily_audit_cron_runner", Path(__file__).resolve()),
        source_file_state("producer:cyber_security_daily_audit", AUDIT_SCRIPT),
        source_file_state("workspace_boundary_check", ROOT / "scripts" / "workspace_boundary_check.py"),
        source_file_state("dashboard_truth_lint", ROOT / "scripts" / "dashboard_truth_lint.py"),
        source_file_state("workspace_governance_truth_check", ROOT / "scripts" / "workspace_governance_truth_check.py"),
    ]
    body = json.dumps(sources, sort_keys=True, separators=(",", ":"))
    return {
        "algorithm": "sha256",
        "hash": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "source_count": len(sources),
        "sources": sources,
    }


def filtered_signature_hash(signature: dict[str, Any], *, excluded_labels: set[str]) -> str | None:
    sources = signature.get("sources")
    if not isinstance(sources, list):
        return None
    filtered = [
        source
        for source in sources
        if isinstance(source, dict) and str(source.get("label") or "") not in excluded_labels
    ]
    if not filtered:
        return None
    body = json.dumps(filtered, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def age_hours(value: Any, now: datetime | None = None) -> float | None:
    parsed = parse_utc(value)
    if parsed is None:
        return None
    now = now or utc_now()
    return (now - parsed).total_seconds() / 3600


def prefilter_decision(
    proof_path: Path,
    audit_path: Path,
    current_signature: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    previous_proof = load_json(proof_path)
    previous_audit = load_json(audit_path)
    previous_signature = previous_proof.get("input_signature") if isinstance(previous_proof.get("input_signature"), dict) else {}
    proof_age = age_hours(previous_proof.get("generated_at_utc"), now)
    audit_age = age_hours(previous_audit.get("generated_at_utc"), now)
    previous_audit_input_hash = filtered_signature_hash(
        previous_signature,
        excluded_labels={"producer:cyber_security_daily_audit_cron_runner"},
    )
    current_audit_input_hash = filtered_signature_hash(
        current_signature,
        excluded_labels={"producer:cyber_security_daily_audit_cron_runner"},
    )
    source_unchanged = bool(
        (previous_signature.get("hash") and previous_signature.get("hash") == current_signature.get("hash"))
        or (
            previous_audit_input_hash
            and current_audit_input_hash
            and previous_audit_input_hash == current_audit_input_hash
        )
    )
    previous_proof_ok = previous_proof.get("proof_status") == "ok" and not previous_proof.get("errors")
    previous_audit_acceptable = previous_audit.get("status") != "critical" and previous_audit.get("stop_line") is not True
    proof_fresh = proof_age is not None and proof_age <= PREFILTER_MAX_AGE_HOURS
    audit_fresh = audit_age is not None and audit_age <= PREFILTER_MAX_AGE_HOURS
    unchanged_warning_fresh = (
        previous_audit.get("status") == "warning"
        and proof_age is not None
        and audit_age is not None
        and proof_age <= PREFILTER_UNCHANGED_WARNING_MAX_AGE_HOURS
        and audit_age <= PREFILTER_UNCHANGED_WARNING_MAX_AGE_HOURS
    )
    can_reuse = source_unchanged and previous_proof_ok and previous_audit_acceptable and (
        (proof_fresh and audit_fresh) or unchanged_warning_fresh
    )
    if not previous_proof:
        reason = "missing_previous_proof"
    elif not previous_signature.get("hash"):
        reason = "missing_previous_input_signature"
    elif not source_unchanged:
        reason = "source_signature_changed"
    elif not previous_proof_ok:
        reason = "previous_proof_not_ok"
    elif not previous_audit_acceptable:
        reason = "previous_audit_stop_line_or_critical"
    elif proof_fresh and audit_fresh:
        reason = "unchanged_inputs_and_fresh_security_proof"
    elif unchanged_warning_fresh:
        reason = "unchanged_inputs_and_reusable_warning_security_proof"
    elif not proof_fresh:
        reason = "previous_proof_not_fresh"
    elif not audit_fresh:
        reason = "previous_audit_not_fresh"
    else:
        reason = "unchanged_inputs_and_fresh_security_proof"
    return {
        "status": "reuse_existing_audit" if can_reuse else "refresh_required",
        "can_reuse_existing_audit": can_reuse,
        "reason": reason,
        "source_unchanged": source_unchanged,
        "previous_proof_exists": bool(previous_proof),
        "previous_audit_exists": bool(previous_audit),
        "previous_proof_age_hours": round(proof_age, 3) if proof_age is not None else None,
        "previous_audit_age_hours": round(audit_age, 3) if audit_age is not None else None,
        "max_age_hours": PREFILTER_MAX_AGE_HOURS,
        "unchanged_warning_max_age_hours": PREFILTER_UNCHANGED_WARNING_MAX_AGE_HOURS,
        "previous_proof_status": previous_proof.get("proof_status"),
        "previous_audit_status": previous_audit.get("status"),
        "previous_audit_stop_line": previous_audit.get("stop_line"),
        "previous_input_hash": previous_signature.get("hash"),
        "current_input_hash": current_signature.get("hash"),
        "previous_audit_input_hash_without_runner": previous_audit_input_hash,
        "current_audit_input_hash_without_runner": current_audit_input_hash,
        "meaning": "Reuse is allowed when security inputs are unchanged and prior proof/audit are non-critical, using a longer warning-only TTL to avoid rerunning unchanged audits into scheduler timeouts.",
    }


def write_reuse_proof(
    *,
    started: datetime,
    finished: datetime,
    audit: dict[str, Any],
    input_signature: dict[str, Any],
    prefilter: dict[str, Any],
) -> dict[str, Any]:
    proof = {
        "generated_at_utc": iso_z(finished),
        "proof_status": "ok",
        "mode": "unchanged_input_skip",
        "runner_started_at_utc": iso_z(started),
        "runner_finished_at_utc": iso_z(finished),
        "command": f"{sys.executable} {AUDIT_SCRIPT}",
        "audit_exit_code": None,
        "audit_artifact": str(AUDIT_JSON.relative_to(ROOT)),
        "audit_generated_at_utc": audit.get("generated_at_utc"),
        "artifact_fresh_for_runner": True,
        "audit_reused_because_inputs_unchanged": True,
        "audit_status": audit.get("status"),
        "audit_stop_line": audit.get("stop_line"),
        "operator_action_required": audit.get("operator_action_required"),
        "next_action": audit.get("next_action"),
        "errors": [],
        "stdout_tail": "",
        "stderr_tail": "",
        "input_signature": input_signature,
        "prefilter": prefilter,
    }
    PROOF_JSON.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    return proof


def run_audit_script() -> dict[str, Any]:
    """Run the bounded audit without allowing a timeout to crash the cron wrapper."""
    try:
        completed = subprocess.run(
            [sys.executable, str(AUDIT_SCRIPT)],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            timeout=1500,
        )
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return {
            "returncode": None,
            "stdout": tail(stdout),
            "stderr": tail(stderr),
            "timed_out": True,
        }


def timeout_warning_allowed(audit: dict[str, Any], generated_at: datetime | None, now: datetime) -> bool:
    """A timed-out refresh may preserve only a recent non-critical audit as warning proof."""
    audit_age = (now - generated_at).total_seconds() / 3600 if generated_at else None
    return bool(
        audit
        and audit.get("status") != "critical"
        and audit.get("stop_line") is not True
        and audit_age is not None
        and audit_age <= PREFILTER_MAX_AGE_HOURS
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force-refresh", action="store_true", help="Bypass the changed-input prefilter and rerun the full audit.")
    parser.add_argument("--prefilter-only", action="store_true", help="Report whether the existing proof can be reused.")
    args = parser.parse_args()

    started = utc_now()
    input_signature = build_input_signature()
    prefilter = prefilter_decision(PROOF_JSON, AUDIT_JSON, input_signature, now=started)
    if args.prefilter_only:
        print(json.dumps(prefilter, indent=2))
        return 0
    if not args.force_refresh and prefilter.get("can_reuse_existing_audit"):
        audit = load_json(AUDIT_JSON)
        proof = write_reuse_proof(
            started=started,
            finished=utc_now(),
            audit=audit,
            input_signature=input_signature,
            prefilter=prefilter,
        )
        print(json.dumps({
            "generated_at_utc": proof["generated_at_utc"],
            "proof_status": proof["proof_status"],
            "mode": proof["mode"],
            "artifact_fresh_for_runner": proof["artifact_fresh_for_runner"],
            "audit_status": proof["audit_status"],
            "audit_stop_line": proof["audit_stop_line"],
            "operator_action_required": proof["operator_action_required"],
            "next_action": proof["next_action"],
            "errors": proof["errors"],
        }, indent=2))
        return 0

    result = run_audit_script()
    finished = utc_now()

    errors: list[str] = []
    audit: dict[str, Any] = {}
    if not AUDIT_JSON.exists():
        errors.append(f"missing audit artifact: {AUDIT_JSON}")
    else:
        try:
            audit = json.loads(AUDIT_JSON.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"audit artifact is not valid JSON: {exc}")

    generated_at = parse_utc(audit.get("generated_at_utc")) if audit else None
    artifact_fresh = bool(generated_at and generated_at >= started)
    if generated_at is None:
        errors.append("audit generated_at_utc is missing or unparsable")
    elif not artifact_fresh:
        errors.append(
            "audit artifact is stale for this cron proof: "
            f"generated_at_utc={iso_z(generated_at)} runner_started_at_utc={iso_z(started)}"
        )

    status = audit.get("status") if audit else None
    stop_line = audit.get("stop_line") if audit else None
    if result.get("timed_out"):
        errors.append("audit script timed out after 1500s")
    elif result.get("returncode") != 0:
        errors.append(f"audit script exited nonzero: {result.get('returncode')}")
    if status == "critical" or stop_line is True:
        errors.append(f"audit stop line active: status={status!r} stop_line={stop_line!r}")

    timeout_warning = bool(result.get("timed_out")) and timeout_warning_allowed(audit, generated_at, finished)
    proof_status = "warning" if timeout_warning else ("ok" if not errors else "blocked")
    operator_action = "MAIN_SESSION_REQUIRED" if timeout_warning else ("BLOCKED" if errors else "NO_REPLY")
    proof = {
        "status": proof_status,
        "generated_at_utc": iso_z(finished),
        "proof_status": proof_status,
        "runner_started_at_utc": iso_z(started),
        "runner_finished_at_utc": iso_z(finished),
        "command": f"{sys.executable} {AUDIT_SCRIPT}",
        "audit_exit_code": result.get("returncode"),
        "audit_timed_out": bool(result.get("timed_out")),
        "audit_artifact": str(AUDIT_JSON.relative_to(ROOT)),
        "audit_generated_at_utc": audit.get("generated_at_utc") if audit else None,
        "artifact_fresh_for_runner": artifact_fresh,
        "audit_status": status,
        "audit_stop_line": stop_line,
        "operator_action_required": audit.get("operator_action_required") if audit else None,
        "next_action": audit.get("next_action") if audit else None,
        "operator_action": operator_action,
        "errors": errors,
        "stdout_tail": tail(result.get("stdout") or ""),
        "stderr_tail": tail(result.get("stderr") or ""),
        "input_signature": input_signature,
        "prefilter": prefilter,
    }
    PROOF_JSON.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    stdout_proof = {
        key: proof[key]
        for key in (
            "generated_at_utc",
            "proof_status",
            "runner_started_at_utc",
            "runner_finished_at_utc",
            "audit_exit_code",
            "audit_generated_at_utc",
            "artifact_fresh_for_runner",
            "audit_status",
            "audit_stop_line",
            "operator_action_required",
            "next_action",
            "errors",
        )
    }
    print(json.dumps(stdout_proof, indent=2))
    return 0 if proof_status in {"ok", "warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
