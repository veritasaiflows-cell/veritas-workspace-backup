#!/usr/bin/env python3
"""Phase 3 G6 hermetic full-chain PACKET (declared subset, five classes).

Not the G5 139/273 suite. Runs a DECLARED subset of existing hermetic
tests covering exactly five classes: success, failure, overflow, debt,
cancellation. Writes tmp/phase3-main-only-20260905/g6-hermetic-20260907/
g6-hermetic-full-chain-packet.json. Does not claim G6 complete.

No network, no SQL providers, no cron, no --send.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

SCHEMA = "veritas.phase3.g6_hermetic_full_chain_packet.v1"
PACKAGE_LIFETIME_SECONDS = 600
G6_COMPLETE = False
NEXT_GATE = "bounded_real_run"
AUTHORITY_BOUNDARY = (
    "packet_only; g6_complete=false; bounded real run is a later gate; "
    "no external delivery; no network/providers/cron/send"
)
PYTEST_TIMEOUT_SECONDS = 180

ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = (
    ROOT
    / "tmp/phase3-main-only-20260905/g6-hermetic-20260907/g6-hermetic-full-chain-packet.json"
)

CLASSES: dict[str, list[str]] = {
    "success": [
        "scripts/test_phase3g_recurring_integration.py::test_full_guard_assembler_sealed_component_retained_digest_no_provider[False]",
        "scripts/test_phase3g_recurring_integration.py::test_recurring_cli_acquires_once_and_excludes_weekly_analyst",
        "scripts/test_phase3g_dynamic_execution.py::DynamicExecutionTests::test_standalone_consumers_really_execute",
    ],
    "failure": [
        "scripts/test_phase3g_recurring_integration.py::test_recurring_rejects_before_policy_reservation_or_writes[untrusted]",
        "scripts/test_phase3g_dynamic_execution.py::DynamicExecutionTests::test_sql_tier_conflict_and_fingerprint_fail_closed",
        "scripts/test_phase3g_recurring_reference_inputs.py::test_full_guard_failure_returns_no_package",
    ],
    "overflow": [
        "scripts/test_phase3g_dynamic_execution.py::DynamicExecutionTests::test_overflow_retains_all_members_without_calls",
        "scripts/test_phase3g_debt_scope.py::DebtScopeTest::test_overflow_keeps_full_membership",
    ],
    "debt": [
        "scripts/test_phase3g_recurring_integration.py::test_full_guard_assembler_sealed_component_retained_digest_no_provider[True]",
        "scripts/test_phase3g_debt_scope.py::DebtScopeTest::test_debt_label_never_confers_readiness",
        "scripts/test_phase3g_alert_coverage.py::test_unbound_quote_payload_is_visible_debt",
    ],
    "cancellation": [
        "scripts/test_phase3g_recurring_reference_inputs.py::test_deadline_kills_stalled_worker_and_reaps_it[file]",
        "scripts/test_phase3g_recurring_reference_inputs.py::test_deadline_kills_stalled_worker_and_reaps_it[sql]",
        "scripts/test_phase3g_coherent_reference_read.py::test_guard_sql_is_actually_interrupted",
    ],
}

EXPECTED_CLASSES = ("success", "failure", "overflow", "debt", "cancellation")


def utc_now_iso() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def all_nodeids() -> list[str]:
    ids: list[str] = []
    for cls in EXPECTED_CLASSES:
        ids.extend(CLASSES[cls])
    return ids


def pytest_command(nodeids: list[str]) -> list[str]:
    return [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider", *nodeids]


def run_pytest(nodeids: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        pytest_command(nodeids),
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=PYTEST_TIMEOUT_SECONDS,
    )


def build_packet(pytest_returncode: int, stdout_tail: str, stderr_tail: str) -> dict:
    all_ok = pytest_returncode == 0
    classes: dict[str, dict] = {}
    for cls in EXPECTED_CLASSES:
        nodeids = list(CLASSES[cls])
        classes[cls] = {
            "nodeids": nodeids,
            "count": len(nodeids),
            "passed": all_ok,
            "failed_nodeids": [] if all_ok else list(nodeids),
            "status": "ok" if all_ok else "failed",
        }
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now_iso(),
        "status": "ok" if all_ok else "blocked",
        "classes": classes,
        "package_lifetime_seconds": PACKAGE_LIFETIME_SECONDS,
        "g6_complete": G6_COMPLETE,
        "next_gate": NEXT_GATE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "validation": {
            "pytest_returncode": pytest_returncode,
            "pytest_command": pytest_command(all_nodeids()),
            "pytest_timeout_seconds": PYTEST_TIMEOUT_SECONDS,
            "all_classes_present": True,
            "all_passed": all_ok,
            "stdout_tail": (stdout_tail or "")[-2000:],
            "stderr_tail": (stderr_tail or "")[-2000:],
        },
    }


def validate_packet(packet: dict) -> list[str]:
    errors: list[str] = []
    if packet.get("schema") != SCHEMA:
        errors.append("bad schema: %r" % (packet.get("schema"),))
    classes = packet.get("classes")
    if not isinstance(classes, dict):
        return errors + ["classes missing or not an object"]
    for cls in EXPECTED_CLASSES:
        entry = classes.get(cls)
        if not isinstance(entry, dict):
            errors.append("class missing: %s" % cls)
            continue
        if entry.get("status") != "ok" or entry.get("passed") is not True:
            errors.append("class not passed: %s" % cls)
        if not entry.get("nodeids"):
            errors.append("class has no nodeids: %s" % cls)
    validation = packet.get("validation") or {}
    rc = validation.get("pytest_returncode")
    if rc != 0:
        errors.append("pytest nonzero: %r" % (rc,))
    if validation.get("all_passed") is not True:
        errors.append("validation.all_passed is not true")
    if packet.get("g6_complete") is not False:
        errors.append("g6_complete must be false (packet is not the real run)")
    if packet.get("status") not in ("ok", "blocked"):
        errors.append("status must be ok|blocked")
    return errors


def parse_args(argv=None):
    p = argparse.ArgumentParser(
        description="G6 hermetic full-chain PACKET (declared subset)."
    )
    p.add_argument("--write", action="store_true", help="Write the JSON packet.")
    p.add_argument(
        "--validate",
        action="store_true",
        help="Exit 1 if any class missing/failed or pytest nonzero.",
    )
    p.add_argument(
        "--out",
        default=str(OUT_PATH),
        help="Output JSON path (default: phase3 packet path).",
    )
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    nodeids = all_nodeids()
    try:
        proc = run_pytest(nodeids)
        rc = proc.returncode
        out = proc.stdout or ""
        err = proc.stderr or ""
    except subprocess.TimeoutExpired as exc:
        raw_out = exc.stdout
        raw_err = exc.stderr
        out = raw_out if isinstance(raw_out, str) else ""
        err = raw_err if isinstance(raw_err, str) else ""
        rc = 124
        err = (err + "\nTIMEOUT after %ds" % PYTEST_TIMEOUT_SECONDS).strip()
    packet = build_packet(rc, out, err)
    if args.write:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
    if args.validate:
        errors = validate_packet(packet)
        if errors:
            print("BLOCKED: " + "; ".join(errors), file=sys.stderr)
            print(json.dumps(packet, indent=2))
            return 1
    if not args.write and not args.validate:
        print(json.dumps(packet, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
