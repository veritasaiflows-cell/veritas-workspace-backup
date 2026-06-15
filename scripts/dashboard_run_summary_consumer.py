from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from generate_dashboard import DATA_PATH, DELTA_PATH, OUT_PATH, inject_into_template
from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Propagate run-summary trust state into dashboard payload and HTML.")
    parser.add_argument("--window", required=True, choices=["morning", "post-close", "post-earnings", "sunday"])
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    data = load_json_artifact(path)
    return data if isinstance(data, dict) else {}


def artifact_index_trust_state(run_summary: dict[str, Any]) -> dict[str, Any]:
    """Expose derived SQLite artifact-index health without granting authority."""
    artifact_index = run_summary.get("artifact_index") if isinstance(run_summary.get("artifact_index"), dict) else {}
    if not artifact_index:
        return {
            "enabled": False,
            "status": "missing",
            "operator_action_required": True,
            "authority_boundary": "derived_review_only_index_not_canon_not_apply",
            "operator_next_action": "Refresh run_summary_refresh.py output so dashboard trust includes derived SQL artifact-index health.",
            "safety_counts": {},
            "checks": {},
            "drift_fingerprint_tables": 0,
        }
    return {
        "enabled": bool(artifact_index.get("enabled")),
        "status": artifact_index.get("status") or "unknown",
        "operator_action_required": bool(artifact_index.get("operator_action_required")),
        "authority_boundary": artifact_index.get("authority_boundary") or "derived_review_only_index_not_canon_not_apply",
        "operator_next_action": artifact_index.get("operator_next_action") or "",
        "safety_counts": artifact_index.get("safety_counts") if isinstance(artifact_index.get("safety_counts"), dict) else {},
        "checks": artifact_index.get("checks") if isinstance(artifact_index.get("checks"), dict) else {},
        "drift_fingerprint_tables": int(artifact_index.get("drift_fingerprint_tables") or 0),
    }


def upsert_run_summary_alert(payload: dict[str, Any], run_summary: dict[str, Any]) -> None:
    alerts = (payload.get("ui") or {}).setdefault("alerts", [])
    alerts = [a for a in alerts if a.get("title") != "Workflow window status"]
    status = str(run_summary.get("status") or "warning")
    execution = run_summary.get("execution") or {}
    artifact_index = artifact_index_trust_state(run_summary)
    sql_unhealthy = artifact_index.get("operator_action_required") or artifact_index.get("status") not in {"ok"}
    terminal_chain_statuses = {"ok", "failed", "completed_with_recovery"}
    chain_status = str(execution.get("chain_status") or "unknown")
    execution_ambiguous = chain_status not in terminal_chain_statuses or not bool(execution.get("chain_status_normalized"))
    tone = "bad" if status in {"blocked", "error"} else ("warn" if status == "warning" or execution_ambiguous or sql_unhealthy else "ok")
    failed_step = execution.get("failed_step") or {}
    detail_bits = [
        f"Window {run_summary.get('window', 'unknown')} finished with status {status}.",
    ]
    if execution_ambiguous:
        detail_bits.append(
            "Execution finalization is ambiguous "
            f"(chain_status={chain_status}, normalized={bool(execution.get('chain_status_normalized'))}); "
            "do not treat this window as fully terminal."
        )
    if execution.get("recovery_triggered") and failed_step.get("script"):
        detail_bits.append(
            f"Controlled recovery emitted a degraded trust snapshot after {failed_step.get('script')} failed"
            f" with exit code {failed_step.get('exit_code', 'unknown')}."
        )
    if run_summary.get("stop_line"):
        detail_bits.append("Stop line triggered; treat downstream surfaces as review-only.")
    fallback = (run_summary.get("fallback_state") or {}).get("reason")
    if fallback:
        detail_bits.append(fallback)
    blockers = run_summary.get("blockers") or []
    if blockers:
        detail_bits.append(blockers[0])
    if sql_unhealthy:
        detail_bits.append(
            "Derived SQL artifact-index health needs attention "
            f"(status={artifact_index.get('status')}, action_required={bool(artifact_index.get('operator_action_required'))}). "
            f"{artifact_index.get('operator_next_action') or 'Run artifact_index.py incremental and validate before relying on SQL cockpit outputs.'}"
        )
    generated_reports = (run_summary.get("generated_reports") or {}).get("outputs") or {}
    ready_reports = [meta.get("path") for meta in generated_reports.values() if isinstance(meta, dict) and meta.get("status") == "ok" and meta.get("path")]
    if ready_reports:
        detail_bits.append("Generated review reports ready: " + ", ".join(str(path) for path in ready_reports[:3]) + ".")
    alerts.insert(0, {
        "tone": tone,
        "title": "Workflow window status",
        "detail": " ".join(detail_bits),
    })
    payload.setdefault("ui", {})["alerts"] = alerts


def propagate_run_summary(payload: dict[str, Any], run_summary: dict[str, Any]) -> dict[str, Any]:
    payload["run_summary"] = run_summary
    payload.setdefault("trust", {})["run_summary"] = {
        "status": run_summary.get("status", "warning"),
        "stop_line": bool(run_summary.get("stop_line")),
        "presentation_allowed": bool((run_summary.get("downstream") or {}).get("presentation_allowed")),
        "canonical_note_mutation_allowed": bool((run_summary.get("downstream") or {}).get("canonical_note_mutation_allowed")),
    }
    payload.setdefault("trust", {})["artifact_index"] = artifact_index_trust_state(run_summary)
    upsert_run_summary_alert(payload, run_summary)
    return payload


def main() -> int:
    args = parse_args()
    payload = read_json(DATA_PATH)
    delta = read_json(DELTA_PATH)
    if not payload:
        raise SystemExit(f"dashboard payload missing at {DATA_PATH}")
    run_summary_path = TMP / f"run-summary-{args.window}.json"
    run_summary = read_json(run_summary_path)
    if not run_summary:
        raise SystemExit(f"run summary missing at {run_summary_path}")

    payload = propagate_run_summary(payload, run_summary)
    atomic_write_json(DATA_PATH, payload, default=str)
    OUT_PATH.write_text(inject_into_template(payload, delta), encoding="utf-8")
    print(json.dumps({"status": "ok", "window": args.window, "out": str(OUT_PATH)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
