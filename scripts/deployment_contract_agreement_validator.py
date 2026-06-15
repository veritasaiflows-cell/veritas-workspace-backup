"""Deployment-state contract agreement validator (review-only proof).

Hardens the deployment-state contract migration (Slices 1-4) before deprecation
(Slice 5) and field removal (Slice 6). It proves, over generated artifacts that
emit the canonical contract, that the canonical fields agree with both their own
trace and the legacy aliases they replace:

  P1 no_drift        - deployment_contract(record.deployment_contract.raw_context)
                       reproduces the stored deployment_status/status_reason/
                       display_label exactly. This is the guarantee that makes
                       Slice 6 removal safe: canonical state is a deterministic
                       function of its own preserved trace and can always be
                       regenerated. raw_context is the authoritative reconstruction
                       source; top-level legacy fields are lossy (they do not carry
                       the below_stop / band_status override inputs).
  P2 enum            - stored deployment_status is a member of DEPLOYMENT_STATUS_ENUM.
  P3 legacy_agree    - stored deployment_status is within the set the contract could
                       ever produce for the record's legacy surface_state (base label
                       plus the below_stop and no-chase overrides). Catches a writer
                       emitting canonical that contradicts the legacy alias.
  P4 authority       - the embedded contract authority block is clamped review-only
                       with all execution/deployment flags false.
  P5 presence        - a record carrying a legacy surface_state also carries the
                       canonical fields (catches a writer that skipped emission).
  P6 alias_absence   - canonical records do not re-emit duplicate top-level
                       legacy aliases once raw_context carries the trace. This
                       keeps Slice 6 removal from silently regressing.

Report-only. No canon/portfolio/SQL mutation, no paper/live/brokerage/account
action, no owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from board_state_contract import DEPLOYMENT_STATUS_ENUM, deployment_contract, legacy_state

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = "tmp/deployment-readiness-surface.json"
OUT = ROOT / "tmp" / "deployment-contract-agreement-validation.json"
REMOVED_TOP_LEVEL_ALIASES = (
    "surface_state",
    "base_surface_state",
    "workflow_state",
    "machine_state",
    "action_state",
)


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def iter_records(data: Any) -> list[dict[str, Any]]:
    """Pull deployment records out of the readiness-surface shape (groups -> lists)
    or a plain list / records-keyed object."""
    records: list[dict[str, Any]] = []
    if isinstance(data, dict) and isinstance(data.get("groups"), dict):
        for group in data["groups"].values():
            if isinstance(group, list):
                records.extend(item for item in group if isinstance(item, dict))
            elif isinstance(group, dict) and isinstance(group.get("records"), list):
                records.extend(item for item in group["records"] if isinstance(item, dict))
    elif isinstance(data, dict) and isinstance(data.get("records"), list):
        records.extend(item for item in data["records"] if isinstance(item, dict))
    elif isinstance(data, list):
        records.extend(item for item in data if isinstance(item, dict))
    return records


def allowed_status_set(surface_state: Any) -> set[str]:
    """Every canonical status the contract could legitimately emit for a record
    whose resolved surface_state is `surface_state`: the base label plus the
    below_stop and no-chase (above-band) overrides. Derived from the contract so
    it can never drift from it."""
    base = deployment_contract({"surface_state": surface_state})["deployment_status"]
    with_stop = deployment_contract({"surface_state": surface_state, "below_stop": True})["deployment_status"]
    with_chase = deployment_contract({"surface_state": surface_state, "band_status": "ABOVE_BAND"})["deployment_status"]
    return {base, with_stop, with_chase}


def check_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    ticker = record.get("ticker")
    stored_status = record.get("deployment_status")
    contract = record.get("deployment_contract")
    surface_state = legacy_state(record, "surface_state")

    # P5 presence: a record with resolved state trace must carry canonical fields.
    if surface_state and (stored_status is None or not isinstance(contract, dict)):
        findings.append({
            "severity": "critical", "ticker": ticker, "check": "presence",
            "issue": "record has resolved state trace but is missing canonical contract fields",
            "surface_state": surface_state,
        })
        return findings
    if stored_status is None:
        return findings

    stored_tuple = (stored_status, record.get("status_reason"), record.get("display_label"))

    # P6 alias_absence: Slice 6 removes duplicate top-level aliases from the
    # deployment-readiness presentation layer. raw_context remains the trace.
    duplicate_aliases = [field for field in REMOVED_TOP_LEVEL_ALIASES if field in record]
    if duplicate_aliases:
        findings.append({
            "severity": "critical", "ticker": ticker, "check": "alias_absence",
            "issue": "canonical record re-emits duplicate top-level deployment-state aliases",
            "duplicate_top_level_aliases": duplicate_aliases,
        })

    # P2 enum.
    if stored_status not in DEPLOYMENT_STATUS_ENUM:
        findings.append({
            "severity": "critical", "ticker": ticker, "check": "enum",
            "issue": "deployment_status is not a member of DEPLOYMENT_STATUS_ENUM",
            "deployment_status": stored_status,
        })

    # P1 no_drift: regenerate from the record's own raw_context.
    raw_context = contract.get("raw_context") if isinstance(contract, dict) else None
    if not isinstance(raw_context, dict):
        findings.append({
            "severity": "critical", "ticker": ticker, "check": "no_drift",
            "issue": "embedded deployment_contract is missing raw_context; canonical state is not reconstructible",
        })
    else:
        regen = deployment_contract(raw_context)
        regen_tuple = (regen["deployment_status"], regen["status_reason"], regen["display_label"])
        if regen_tuple != stored_tuple:
            findings.append({
                "severity": "critical", "ticker": ticker, "check": "no_drift",
                "issue": "stored canonical fields do not regenerate from raw_context",
                "stored": list(stored_tuple), "regenerated": list(regen_tuple),
            })

    # P3 legacy_agree: stored status must be reachable from the legacy surface_state.
    if surface_state:
        allowed = allowed_status_set(surface_state)
        if stored_status not in allowed:
            findings.append({
                "severity": "critical", "ticker": ticker, "check": "legacy_agree",
                "issue": "deployment_status contradicts the legacy surface_state it replaces",
                "surface_state": surface_state, "deployment_status": stored_status,
                "allowed_for_surface_state": sorted(allowed),
            })

    # P4 authority clamp.
    authority = contract.get("authority") if isinstance(contract, dict) else None
    if not isinstance(authority, dict):
        findings.append({
            "severity": "critical", "ticker": ticker, "check": "authority",
            "issue": "embedded deployment_contract is missing the authority block",
        })
    else:
        if authority.get("review_only") is not True:
            findings.append({
                "severity": "critical", "ticker": ticker, "check": "authority",
                "issue": "authority.review_only must be True",
            })
        for flag in ("paper_order_execution_allowed", "capital_deployment_approved", "trade_or_execution_approved"):
            if authority.get(flag) is not False:
                findings.append({
                    "severity": "critical", "ticker": ticker, "check": "authority",
                    "issue": f"authority.{flag} must be False", "value": authority.get(flag),
                })
    return findings


def build_report(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    records = iter_records(data)
    canonical_records = [r for r in records if r.get("deployment_status") is not None]
    findings: list[dict[str, Any]] = []
    for record in records:
        findings.extend(check_record(record))
    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input": relpath(path),
        "status": "ok" if critical == 0 else "blocked",
        "authority": {
            "review_only": True,
            "canonical_mutation_allowed": False,
            "portfolio_mutation_allowed": False,
            "trade_or_account_action_allowed": False,
        },
        "summary": {
            "records_seen": len(records),
            "canonical_records_checked": len(canonical_records),
            "critical": critical,
            "warning": warning,
            "checks": ["no_drift", "enum", "legacy_agree", "authority", "presence", "alias_absence"],
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate deployment-state contract / legacy-alias agreement (review-only).")
    parser.add_argument("input", nargs="?", default=DEFAULT_INPUT)
    parser.add_argument("--write", action="store_true", help="Write the JSON proof artifact.")
    args = parser.parse_args()
    report = build_report(ROOT / args.input)
    if args.write:
        OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(OUT)}")
    s = report["summary"]
    print(
        f"deployment_contract_agreement_validator: {report['status']} "
        f"({s['canonical_records_checked']} checked, {s['critical']} critical, {s['warning']} warning)"
    )
    return 1 if s["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
