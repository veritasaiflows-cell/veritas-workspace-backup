from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "finance-discrepancy-resolver.json"
OUT_MD = TMP / "finance-discrepancy-resolver.md"
SCHEMA_VERSION = 1

INPUTS = {
    "earnings_date_source_confidence": "tmp/earnings-date-source-confidence.json",
    "event_calendar_rollforward": "tmp/event-calendar-rollforward.json",
    "event_calendar_apply": "tmp/event-calendar-apply.json",
    "board_canon_guardrail": "tmp/board-canon-guardrail.json",
    "stale_intelligence_guardrail": "tmp/stale-intelligence-guardrail.json",
    "canonical_note_patch_proposal": "tmp/canonical-note-patch-proposal.json",
    "portfolio_snapshot_patch_proposal": "tmp/portfolio-snapshot-patch-proposal.json",
}

AUTHORITY = {
    "posture": "review_only_discrepancy_queue",
    "cron_apply_allowed": False,
    "main_session_review_required": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "owner_approval_granted": False,
    "sizing_or_weight_change_allowed": False,
    "sleeve_cash_or_risk_rule_change_allowed": False,
    "execution_entitlement_allowed": False,
    "trade_or_account_action_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel_path(path: Path) -> str:
    return path.relative_to(WORKSPACE).as_posix()


def load_input(role: str, rel: str) -> dict[str, Any] | None:
    data = load_json_artifact(WORKSPACE / rel)
    return data if isinstance(data, dict) else None


def severity_rank(severity: str) -> int:
    return {"critical": 3, "warning": 2, "info": 1}.get(severity, 1)


def add_discrepancy(
    rows: list[dict[str, Any]],
    *,
    cls: str,
    severity: str,
    target_surface: str,
    source_artifacts: list[str],
    evidence: dict[str, Any],
    recommended_action: str,
) -> None:
    rows.append({
        "discrepancy_id": f"fdr_{len(rows) + 1:03d}_{cls}",
        "class": cls,
        "severity": severity,
        "target_surface": target_surface,
        "source_artifacts": source_artifacts,
        "evidence": evidence,
        "recommended_action": recommended_action,
        "cron_apply_allowed": False,
        "main_session_review_required": True,
        "authority": dict(AUTHORITY),
    })


def collect_input_health(inputs: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, rel in INPUTS.items():
        data = inputs.get(role)
        path = WORKSPACE / rel
        if data is None:
            add_discrepancy(
                rows,
                cls="missing_or_unreadable_artifact",
                severity="warning",
                target_surface=rel,
                source_artifacts=[rel],
                evidence={"role": role, "exists": path.exists()},
                recommended_action="Regenerate the source artifact before using discrepancy/canon-sync conclusions.",
            )
            continue
        status = str(data.get("status") or data.get("overall") or "ok").lower()
        if status in {"critical", "failed", "error", "blocked"}:
            add_discrepancy(
                rows,
                cls="artifact_conflict",
                severity="critical",
                target_surface=rel,
                source_artifacts=[rel],
                evidence={"role": role, "status": status, "generated_at_utc": data.get("generated_at_utc")},
                recommended_action="Stop. Resolve the critical source artifact before applying any note/canon proposal or recommendation packet.",
            )
        elif status in {"warning", "partial", "needs_review"}:
            add_discrepancy(
                rows,
                cls="artifact_warning",
                severity="warning",
                target_surface=rel,
                source_artifacts=[rel],
                evidence={"role": role, "status": status, "generated_at_utc": data.get("generated_at_utc")},
                recommended_action="Review the warning-grade source artifact before treating downstream packets as presentation-ready.",
            )
    return rows


def collect_earnings_discrepancies(inputs: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    confidence = inputs.get("earnings_date_source_confidence") or {}
    for record in confidence.get("records", []) or []:
        if not isinstance(record, dict):
            continue
        provider_date = record.get("provider_next_earnings_date")
        configured_date = record.get("configured_date")
        source_confidence = str(record.get("source_confidence") or "")
        primary_status = str(record.get("primary_confirmation_status") or "")
        ticker = str(record.get("ticker") or "UNKNOWN")
        if provider_date and configured_date and provider_date != configured_date:
            add_discrepancy(
                rows,
                cls="earnings_date",
                severity="warning",
                target_surface="05. Intelligence/Event Calendar.md",
                source_artifacts=[INPUTS["earnings_date_source_confidence"]],
                evidence={"ticker": ticker, "provider_next_earnings_date": provider_date, "configured_date": configured_date, "verification_sites": record.get("verification_sites")},
                recommended_action="Verify against company IR/newsroom or SEC before changing primary-confirmed language or Event Calendar dates.",
            )
        if source_confidence == "provider_estimate" or primary_status in {"provider_only", "unconfirmed"}:
            add_discrepancy(
                rows,
                cls="source_confidence",
                severity="info",
                target_surface="05. Intelligence/Event Calendar.md",
                source_artifacts=[INPUTS["earnings_date_source_confidence"]],
                evidence={"ticker": ticker, "source_confidence": source_confidence, "primary_confirmation_status": primary_status, "verification_sites": record.get("verification_sites")},
                recommended_action="Keep provider-estimate dates labeled as unconfirmed/review-only; do not mark primary-confirmed without primary evidence.",
            )
    return rows


def collect_guardrail_discrepancies(inputs: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    board = inputs.get("board_canon_guardrail") or {}
    for alert in board.get("risk_alerts", []) or []:
        if not isinstance(alert, dict):
            continue
        severity = "warning"
        if alert.get("severity") in {"critical", "deployment_blocking"} or alert.get("deployment_blocking"):
            severity = "warning"
        add_discrepancy(
            rows,
            cls="board_canon",
            severity=severity,
            target_surface="03. Portfolio/Portfolio Snapshot.md",
            source_artifacts=[INPUTS["board_canon_guardrail"]],
            evidence={"ticker": alert.get("ticker"), "risk_state": alert.get("risk_state"), "message": alert.get("message"), "risk_record": alert.get("risk_record")},
            recommended_action="Ensure canonical notes visibly preserve stop-breached/near-stop state and do not soften it into deployment entitlement.",
        )
    stale = inputs.get("stale_intelligence_guardrail") or {}
    for finding in stale.get("findings", []) or []:
        if not isinstance(finding, dict):
            continue
        add_discrepancy(
            rows,
            cls="stale_note",
            severity=str(finding.get("severity") or "warning"),
            target_surface=str(finding.get("surface") or "canonical notes"),
            source_artifacts=[INPUTS["stale_intelligence_guardrail"]],
            evidence={"code": finding.get("code"), "message": finding.get("message"), "evidence": finding.get("evidence")},
            recommended_action="Use canonical-note patch proposal review; cron must not apply this note edit.",
        )
    return rows


def collect_patch_proposal_discrepancies(inputs: dict[str, dict[str, Any] | None]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in ("canonical_note_patch_proposal", "portfolio_snapshot_patch_proposal"):
        artifact = inputs.get(role) or {}
        candidates = artifact.get("candidates") or artifact.get("patch_candidates") or artifact.get("proposals") or []
        if candidates:
            add_discrepancy(
                rows,
                cls="patch_proposal",
                severity="warning",
                target_surface=INPUTS[role],
                source_artifacts=[INPUTS[role]],
                evidence={"role": role, "candidate_count": len(candidates), "generated_at_utc": artifact.get("generated_at_utc")},
                recommended_action="Review patch candidates in main session. Validate authority and apply only bounded freshness/status sync when evidence is current.",
            )
    return rows


def build_report() -> dict[str, Any]:
    inputs = {role: load_input(role, rel) for role, rel in INPUTS.items()}
    discrepancies: list[dict[str, Any]] = []
    discrepancies.extend(collect_input_health(inputs))
    discrepancies.extend(collect_earnings_discrepancies(inputs))
    discrepancies.extend(collect_guardrail_discrepancies(inputs))
    discrepancies.extend(collect_patch_proposal_discrepancies(inputs))
    discrepancies = sorted(discrepancies, key=lambda row: (-severity_rank(row["severity"]), row["class"], row["target_surface"]))
    for idx, row in enumerate(discrepancies, start=1):
        row["discrepancy_id"] = f"fdr_{idx:03d}_{row['class']}"
    critical = sum(1 for row in discrepancies if row["severity"] == "critical")
    warning = sum(1 for row in discrepancies if row["severity"] == "warning")
    info = sum(1 for row in discrepancies if row["severity"] == "info")
    status = "critical" if critical else "warning" if warning else "ok"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": utc_now(),
        "status": status,
        "authority": dict(AUTHORITY),
        "summary": {
            "critical": critical,
            "warning": warning,
            "info": info,
            "discrepancy_count": len(discrepancies),
        },
        "inputs": {role: {"path": rel, "loaded": inputs.get(role) is not None} for role, rel in INPUTS.items()},
        "discrepancies": discrepancies,
        "notes": [
            "This resolver is a review-only queue over existing guardrails and patch proposals.",
            "Cron may generate this artifact, but must not apply canonical, portfolio, owner-approval, sizing, sleeve/cash/risk-rule, execution, trade/account, cleanup, config, or channel changes.",
        ],
        "rendered_outputs": {"json": rel_path(OUT_JSON), "markdown": rel_path(OUT_MD)},
    }


def render_md(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = ["# Finance Discrepancy Resolver", ""]
    lines.append(f"- Generated: `{report['generated_at_utc']}`")
    lines.append(f"- Status: **{report['status']}**")
    lines.append(f"- Discrepancies: {summary['discrepancy_count']} ({summary['critical']} critical / {summary['warning']} warning / {summary['info']} info)")
    lines.append("- Authority: review-only queue; cron apply is false; main-session review is required")
    lines.append("")
    if not report["discrepancies"]:
        lines.append("No discrepancies found across the current resolver input set.")
    else:
        for row in report["discrepancies"]:
            lines.append(f"## {row['discrepancy_id']} — {row['class']}")
            lines.append(f"- Severity: `{row['severity']}`")
            lines.append(f"- Target: `{row['target_surface']}`")
            lines.append(f"- Sources: {', '.join(f'`{src}`' for src in row['source_artifacts'])}")
            lines.append(f"- Recommended action: {row['recommended_action']}")
            lines.append("- Authority: cron_apply_allowed=false; main_session_review_required=true; no portfolio/capital/trade authority")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a review-only finance discrepancy queue.")
    parser.add_argument("--write", action="store_true", help="Write tmp/finance-discrepancy-resolver.{json,md}")
    args = parser.parse_args()
    report = build_report()
    if args.write:
        atomic_write_json(OUT_JSON, report)
        atomic_write_text(OUT_MD, render_md(report))
    else:
        print(render_md(report))
    return 0 if report["status"] in {"ok", "warning"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
