"""Cron proof wrapper for the bounded daily cyber-security audit.

Runs the audit script, verifies that its JSON artifact was regenerated after this
wrapper started, and writes a machine-checkable proof artifact for cron review.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AUDIT_SCRIPT = ROOT / "scripts" / "cyber_security_daily_audit.py"
AUDIT_JSON = ROOT / "tmp" / "cyber-security-daily-audit.json"
PROOF_JSON = ROOT / "tmp" / "cyber-security-daily-audit-cron-proof.json"


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


def main() -> int:
    started = utc_now()
    result = subprocess.run(
        [sys.executable, str(AUDIT_SCRIPT)],
        cwd=str(ROOT),
        text=True,
        capture_output=True,
        timeout=1500,
    )
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
    if result.returncode != 0:
        errors.append(f"audit script exited nonzero: {result.returncode}")
    if status == "critical" or stop_line is True:
        errors.append(f"audit stop line active: status={status!r} stop_line={stop_line!r}")

    proof_status = "ok" if not errors else "blocked"
    proof = {
        "generated_at_utc": iso_z(finished),
        "proof_status": proof_status,
        "runner_started_at_utc": iso_z(started),
        "runner_finished_at_utc": iso_z(finished),
        "command": f"{sys.executable} {AUDIT_SCRIPT}",
        "audit_exit_code": result.returncode,
        "audit_artifact": str(AUDIT_JSON.relative_to(ROOT)),
        "audit_generated_at_utc": audit.get("generated_at_utc") if audit else None,
        "artifact_fresh_for_runner": artifact_fresh,
        "audit_status": status,
        "audit_stop_line": stop_line,
        "operator_action_required": audit.get("operator_action_required") if audit else None,
        "next_action": audit.get("next_action") if audit else None,
        "errors": errors,
        "stdout_tail": tail(result.stdout),
        "stderr_tail": tail(result.stderr),
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
    return 0 if proof_status == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
