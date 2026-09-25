"""Workflow routing index (derived, review-only route map).

Mirrors the P0/P1/P2 active/monitor rows and P3 paused rows in
`06. Playbooks/Active Workflows.md` into a single derived route object so a new
session, helper lane, or status answer can jump straight to a workflow's
continuity note, primary proof artifact, validators, blockers, stop lines, and
next action without a broad workspace search.

Active Workflows is the live authority. This index is a derived route map only:
it never outranks Active Workflows or the exact continuity notes, and it carries
no canon/portfolio/SQL/approval/execution authority.

Phase 1 (--write): build `tmp/workflow-routing-index.json` with every P0/P1/P2/P3
route row and the 16 required route fields, resolving on-disk existence for the
continuity note and proof artifacts it points at.

Phase 2 (--validate): emit `tmp/workflow-routing-index-validation.json`.
  C  schema_version, route count, or tier-count drift from the expected
     P0/P1/P2/P3 coverage set
  C  missing required field on a route row
  C  invalid route field type or empty required string
  C  stop_lines empty (every route must carry a stop line)
  C  authority widening (any approval/execution/mutation flag flipped true,
     or owner_action_required dropped on an owner-gated row)
  C  freshness or helper-handoff authority/mode regression
  W  continuity_note path declared but absent on disk (coverage gap)
  W  primary_route_artifact path declared, not pending, and absent on disk
  W  no validator_commands on an active build lane (P0/P1)

Critical findings block (status -> "blocked"); warnings keep status "ok" while
surfacing coverage gaps. Report-only: no canon/portfolio/SQL mutation, no
paper/live/brokerage/account action, no owner-approval inference.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.workflow_control import apply_route_override, find_override, is_on_hold, load_registry

ROOT = Path(__file__).resolve().parents[1]
INDEX_OUT = ROOT / "tmp" / "workflow-routing-index.json"
VALIDATION_OUT = ROOT / "tmp" / "workflow-routing-index-validation.json"
PARITY_OUT = ROOT / "tmp" / "workflow-routing-parity-validation.json"
DB_OUT = ROOT / "tmp" / "workflow-routing-index.sqlite"
HANDOFF_DIR = ROOT / "tmp"
ACTIVE_WORKFLOWS_REL = "06. Playbooks/Active Workflows.md"
ACTIVE_WORKFLOWS_PATH = ROOT / ACTIVE_WORKFLOWS_REL
CONTROL_OVERRIDES_REL = "state/workflow-control-overrides.json"
CONTROL_OVERRIDES_PATH = ROOT / CONTROL_OVERRIDES_REL
CAPSULE_DIR = ROOT / "state" / "workflows"
STATUS_CARD_OUT = ROOT / "tmp" / "veritas-status-card.json"

CONTINUITY = "06. Playbooks/Project Continuity"

REQUIRED_FIELDS = (
    "workflow_id",
    "display_name",
    "aliases",
    "tier",
    "current_state",
    "next_action",
    "continuity_note",
    "primary_route_artifact",
    "secondary_artifacts",
    "validator_commands",
    "last_validated_at",
    "blockers",
    "stop_lines",
    "authority_boundary",
    "owner_action_required",
    "safe_for_helper_lane",
    "default_resume_command",
    "priority",
    "lifecycle",
    "readiness",
    "authority_class",
    "primary_owner_lane",
    "secondary_consumers",
    "human_approval_owner",
    "proof_artifact",
    "freshness_sla",
    "authoritative_next_action",
)

EXPECTED_ROUTE_COUNT = 44
EXPECTED_TIER_COUNTS = {"P0": 2, "P1": 12, "P2": 8, "P3": 15, "P4": 7}
FRESHNESS_SCORES = {"fresh", "aging", "stale", "missing", "n/a"}
HANDOFF_MODES = {"Spawn read-only", "Main-session only"}
LIFECYCLES = {"active", "paused", "monitor", "gated"}
READINESS_STATES = {"route_only", "refresh_required", "paused", "monitor_only", "blocked"}
AUTHORITY_CLASSES = {
    "review_only",
    "owner_gated_review_only",
    "monitor_only",
    "paused_review_only",
    "paper_guard_fail_closed",
}
PAPER_FAIL_CLOSED_WORKFLOWS: set[str] = set()
ALERT_OS_RETIRED_WORKFLOWS = {
    "WF56",
    "WF58",
    "WF64",
    "WF64-WF56",
    "WF68",
    "WF76",
    "WF78",
    "WF79",
    "WF86",
    "WF87",
}
ALERT_OS_DENY_ONLY_WORKFLOWS = {"WF63", "WF67"}
FRESHNESS_SLA_HOURS = 72.0

# LOOP-REPAIR-20260912: computed live-proof blockers for WF74/WF88.
# WF74's retired autonomy-spine rollup primary and WF88's 14 literal historical
# blockers hid stale/missing/failed proof behind static text. The constants below
# name the current owner proof; compute_wf74/wf88_blockers() derives actionable
# blockers from missing/stale artifacts, producer validation/status, and
# proof-summary counts at build time. Scope disclaimers and history stay in
# stop_lines/authority_boundary/current_state -- blockers[] carries only what
# must clear before green. Canonical holds, approval gates, and stop lines are
# untouched by this projection.
WF74_PRIMARY_PROOF = "tmp/wf74-improvement-opportunity-queue.json"
WF74_LIVE_PROOFS = (
    "tmp/wf74-improvement-opportunity-queue.json",
    "tmp/wf74-decision-docket.json",
    "tmp/wf74-autonomy-work-router.json",
    "tmp/improvement-ledger-current.json",
)
WF74_OTEL_PROOFS = (
    "tmp/otel-ops-control.json",
    "tmp/otel-ops-window-summary.json",
)
WF88_PRIMARY_PROOF = "tmp/wf88-os2-control-packet.json"
WF88_LIVE_PROOFS = (
    "tmp/wf88-os2-control-packet.json",
    "tmp/improvement-ledger-current.json",
    "tmp/retrieval-live-eval.json",
)
LOOP_PROOF_SLA_HOURS = 72.0
LOOP_PROOF_FUTURE_SKEW_SECONDS = 3600.0
# F-A1 allowlist: explicit legitimate vocabularies from the frozen producer
# descriptors (finding.json current_producer_descriptors). Producer statuses
# {ok, control_packet_ready_no_apply_authority, draft_review_required, warning} and
# validation statuses {ok, warning} green the route; every other value --
# missing/None/non-string/empty/unknown, including hyphenated fail spellings
# such as fail-closed -- fails closed. Review-only producer statuses stay green.
_LOOP_PRODUCER_OK_STATUSES = frozenset({
    "ok",
    "control_packet_ready_no_apply_authority",
    "draft_review_required",
    "warning",
})
_LOOP_VALIDATION_OK_STATUSES = frozenset({
    "ok",
    "warning",
})


def _loop_generated_at(payload: dict[str, Any]) -> datetime | None:
    """Finite declared proof timestamp. Filesystem mtime is never proof freshness."""
    raw = payload.get("generated_at_utc")
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        moment = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    try:
        stamp = moment.timestamp()
    except (OverflowError, OSError, ValueError):
        return None
    if stamp != stamp or stamp in (float("inf"), float("-inf")):
        return None
    return moment


def _loop_as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _loop_load_json(rel: str | None) -> dict[str, Any] | None:
    if not rel:
        return None
    try:
        with (ROOT / rel).open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def _loop_status_failed(status: Any) -> bool:
    """Fail-closed producer-status check (F-A1 allowlist)."""
    if not isinstance(status, str):
        return True
    return status.strip().casefold() not in _LOOP_PRODUCER_OK_STATUSES


def _loop_validation_failed(status: Any) -> bool:
    """Fail-closed validation-status check (F-A1 allowlist)."""
    if not isinstance(status, str):
        return True
    return status.strip().casefold() not in _LOOP_VALIDATION_OK_STATUSES


def _loop_proof_blockers(rel: str, label: str) -> list[str]:
    """Missing/stale/invalid/failed live proof blocks operational green.

    Freshness comes from the producer-declared generated_at_utc against the
    declared SLA, never filesystem mtime: touching or copying a file must not
    green stale evidence. Missing/unusable/future generated_at_utc and a missing
    validation section fail closed.
    """
    if not exists_on_disk(rel):
        return [f"{label}: live proof missing ({rel}); refresh the owner producer before claiming green"]
    payload = _loop_load_json(rel)
    if payload is None:
        return [f"{label}: live proof unreadable ({rel}); repair or refresh the producer"]
    found: list[str] = []
    moment = _loop_generated_at(payload)
    if moment is None:
        found.append(
            f"{label}: live proof has no usable generated_at_utc ({rel}); "
            "refresh the owner producer before claiming green"
        )
    else:
        skew = (moment - datetime.now(timezone.utc)).total_seconds()
        if skew > LOOP_PROOF_FUTURE_SKEW_SECONDS:
            found.append(
                f"{label}: live proof generated_at_utc is in the future ({rel}); "
                "fail closed until the producer timestamp is trustworthy"
            )
        else:
            age_hours = round(-skew / 3600.0, 1)
            if age_hours > LOOP_PROOF_SLA_HOURS:
                found.append(
                    f"{label}: live proof stale by producer clock "
                    f"({age_hours}h > {LOOP_PROOF_SLA_HOURS}h: {rel}); refresh before claiming green"
                )
    if _loop_status_failed(payload.get("status")):
        found.append(f"{label}: producer status reports failure ({rel} status={payload.get('status')!r})")
    validation = payload.get("validation")
    if not isinstance(validation, dict):
        found.append(
            f"{label}: live proof has no validation section ({rel}); "
            "fail closed until the producer reports validation"
        )
    else:
        if _loop_validation_failed(validation.get("status")):
            found.append(
                f"{label}: producer validation reports failure ({rel} validation={validation.get('status')!r})"
            )
        errors = validation.get("errors")
        if isinstance(errors, list):
            for error in errors[:5]:
                found.append(f"{label}: producer validation error ({rel}): {error}")
    found.extend(_loop_declared_blockers(payload, label, rel))
    return found


def _loop_declared_blockers(payload: dict[str, Any], label: str, rel: str) -> list[str]:
    """Propagate proof-declared summary.blockers entries verbatim (capped)."""
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        return []
    declared = summary.get("blockers")
    if not isinstance(declared, list):
        return []
    return [f"{label} proof declares blocker ({rel}): {entry}" for entry in declared[:5]]


def _wf74_operational_blockers() -> list[str]:
    """WF74 defects that break review operation: regressed/fix-now/blocked plans,
    overdue actionable debt, and required follow-ups. Queue depth and claim
    limits live in _wf74_claim_limits and never block operational health."""
    found: list[str] = []
    queue = _loop_load_json(WF74_PRIMARY_PROOF) or {}
    queue_summary = queue.get("summary")
    if isinstance(queue_summary, dict):
        regressed = _loop_as_int(queue_summary.get("regressed_after_completion_count"))
        if regressed > 0:
            found.append(
                f"WF74 queue: {regressed} regressed-after-completion opportunities open; "
                "repair regressed signals before claiming green"
            )
    docket = _loop_load_json("tmp/wf74-decision-docket.json") or {}
    docket_summary = docket.get("summary")
    if isinstance(docket_summary, dict):
        fix_now = _loop_as_int(docket_summary.get("fix_now_count"))
        if fix_now > 0:
            found.append(
                f"WF74 docket: {fix_now} fix-now actions open; repair the failing proof surface first"
            )
    router = _loop_load_json("tmp/wf74-autonomy-work-router.json") or {}
    router_summary = router.get("summary")
    if isinstance(router_summary, dict):
        cron_blocked = _loop_as_int(router_summary.get("cron_blocked_count"))
        if cron_blocked > 0:
            found.append(
                "WF74 router: cron repair plan blocked; inspect the blocked cron artifacts first"
            )
        overdue = _loop_as_int(router_summary.get("high_priority_overdue_count"))
        if overdue > 0:
            found.append(
                f"WF74 router: {overdue} high-priority overdue improvements; clear overdue debt first"
            )
    ledger = _loop_load_json("tmp/improvement-ledger-current.json") or {}
    ledger_summary = ledger.get("summary")
    if isinstance(ledger_summary, dict):
        overdue_open = _loop_as_int(ledger_summary.get("overdue_open_count"))
        if overdue_open > 0:
            found.append(
                f"WF74 ledger: {overdue_open} overdue open improvements; clear overdue debt first"
            )
        followup = _loop_as_int(ledger_summary.get("followup_required_open_count"))
        if followup > 0:
            found.append(
                f"WF74 ledger: {followup} open improvements require follow-up; close the loop first"
            )
    return found


def _wf74_claim_limits() -> list[str]:
    """WF74 claim/promotion limits: queue depth and routing posture, not broken operation."""
    queue = _loop_load_json(WF74_PRIMARY_PROOF) or {}
    queue_summary = queue.get("summary")
    if not isinstance(queue_summary, dict):
        return []
    high = _loop_as_int(queue_summary.get("high_priority_count"))
    if high > 0:
        return [
            f"WF74 queue: {high} high-priority opportunities queued for proposal routing "
            "(claim/queue depth and routing posture, not broken operation)"
        ]
    return []


def _wf88_operational_blockers() -> list[str]:
    found: list[str] = []
    packet = _loop_load_json(WF88_PRIMARY_PROOF) or {}
    summary = packet.get("summary")
    if not isinstance(summary, dict):
        return ["WF88 control: control-packet summary unreadable; refresh the OS 2.0 control packet"]
    stale_inputs = summary.get("stale_inputs") or []
    stale_count = _loop_as_int(summary.get("stale_input_count"))
    if stale_count > 0 or stale_inputs:
        names = ", ".join(str(name) for name in list(stale_inputs)[:7]) or "see summary.stale_inputs"
        count = stale_count if stale_count > 0 else len(stale_inputs)
        found.append(
            f"WF88 control: {count} stale inputs ({names}); refresh stale proof before claiming green"
        )
    blocked_followup = _loop_as_int(summary.get("blocked_or_followup_action_count"))
    if blocked_followup > 0:
        found.append(
            f"WF88 control: {blocked_followup} blocked/follow-up canonical actions open; clear them first"
        )
    if str(summary.get("route_contraction_validation_status") or "") == "blocked":
        found.append("WF88 control: route-contraction validation blocked; narrow the open routes first")
    return found


def _wf88_claim_limits() -> list[str]:
    """WF88 claim/promotion limits: what the evidence does not license.

    These constrain performance, comparison, promotion, and improvement claims.
    They never block review operation; overdue/follow-up/un-routed/no-proof
    defects live in _wf88_operational_blockers.
    """
    found: list[str] = []
    packet = _loop_load_json(WF88_PRIMARY_PROOF) or {}
    summary = packet.get("summary")
    if not isinstance(summary, dict):
        return ["WF88 control: control-packet summary unreadable; refresh the OS 2.0 control packet"]
    if summary.get("model_performance_claim_allowed_now") is False:
        found.append(
            "WF88 control: model-performance claim not allowed on current graded evidence; "
            "do not promote providers or models"
        )
    if _loop_as_int(summary.get("wiki_frontier_result_row_count")) == 0:
        found.append(
            "WF88 control: frontier spine has 0 result rows; model comparison and route promotion remain blocked"
        )
    if _loop_as_int(summary.get("wiki_advanced_pilot_executed_count")) == 0:
        found.append(
            "WF88 control: 0 advanced-pilot calls executed; promotions remain blocked"
        )
    if summary.get("wiki_rsi_outcome_mature") is False:
        found.append(
            "WF88 control: RSI outcome evidence not mature; no recursive-improvement claim"
        )
    open_improvements = _loop_as_int(summary.get("improvement_open_count"))
    if open_improvements > 0:
        found.append(
            f"WF88 control: {open_improvements} open improvements queued "
            "(monitor-only standing included; operational blockers track overdue/follow-up only)"
        )
    retrieval = _loop_load_json("tmp/retrieval-live-eval.json") or {}
    human_review = retrieval.get("human_review")
    human_complete = (
        isinstance(human_review, dict)
        and human_review.get("sole_relevance_review_complete") is True
    )
    validation = retrieval.get("validation")
    warnings = (
        list(validation.get("warnings", []))
        if isinstance(validation, dict) and isinstance(validation.get("warnings"), list)
        else []
    )
    no_discrimination = "semantic_hash_paraphrase_discrimination_not_observed" in warnings
    if str(retrieval.get("status") or "") != "ok" or not human_complete or no_discrimination:
        found.append(
            "WF88 control: live retrieval discrimination not proven -- semantic lift unobserved "
            "and human gold review incomplete (tmp/retrieval-live-eval.json); "
            "provider promotion blocked (claim limit, not broken operation)"
        )
    return found


def compute_wf74_blockers() -> list[str]:
    """Actionable WF74 operational blockers derived from current owner proof."""
    found: list[str] = []
    for rel in WF74_LIVE_PROOFS:
        found.extend(_loop_proof_blockers(rel, "WF74"))
    for rel in WF74_OTEL_PROOFS:
        found.extend(_loop_proof_blockers(rel, "WF74 OTEL"))
    found.extend(_wf74_operational_blockers())
    return list(dict.fromkeys(found))


def compute_wf74_claim_limits() -> list[str]:
    """WF74 claim/promotion limits. Never operational blockers."""
    return list(dict.fromkeys(_wf74_claim_limits()))


def compute_wf88_blockers() -> list[str]:
    """Actionable WF88 operational blockers from live proof, control summaries, and WF74 upstream state."""
    found: list[str] = []
    for rel in WF88_LIVE_PROOFS:
        found.extend(_loop_proof_blockers(rel, "WF88"))
    found.extend(_wf88_operational_blockers())
    upstream = compute_wf74_blockers()
    if upstream:
        found.append(
            f"WF88 upstream: WF74 live proof blocked ({len(upstream)} actionable); clear WF74 blockers first"
        )
    return list(dict.fromkeys(found))


def compute_wf88_claim_limits() -> list[str]:
    """WF88 claim/promotion limits. Never operational blockers."""
    return list(dict.fromkeys(_wf88_claim_limits()))


def _apply_computed_loop_blockers(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Overwrite WF74/WF88 static blockers with computed live-proof blockers.

    Canonical holds, approval/authority gates, stop lines, tiers, and resume
    commands are preserved; only the actionable blockers list is derived, plus
    a parallel claim_limits list that constrains claims without blocking operation.
    """
    by_id = {route.get("workflow_id"): route for route in routes}
    wf74 = by_id.get("WF74")
    if wf74 is not None:
        wf74["blockers"] = compute_wf74_blockers()
        wf74["claim_limits"] = compute_wf74_claim_limits()
    wf88 = by_id.get("WF88")
    if wf88 is not None:
        wf88["blockers"] = compute_wf88_blockers()
        wf88["claim_limits"] = compute_wf88_claim_limits()
    return routes

# These are interface consumers, not owners.  The main session remains the
# sole operational owner until an exact lane lease delegates a bounded write.
SECONDARY_CONSUMERS: dict[str, list[str]] = {
    "WF78": ["WF84", "WF85"],
    "WF84": ["WF85"],
    "WF85": ["Randall"],
}

# Review-only authority clamp. Mirrors the Active Workflows global authority
# rules. The validator treats any of these flipping true (other than
# review_only) as authority widening.
AUTHORITY = {
    "review_only": True,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "sql_canon_promotion_allowed": False,
    "customer_or_public_output_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "cron_config_runtime_mutation_allowed": False,
    "owner_approval_inferred": False,
}

LIST_FIELDS = (
    "aliases", "secondary_artifacts", "validator_commands", "blockers", "stop_lines",
    "secondary_consumers",
)
BOOL_FIELDS = ("owner_action_required", "safe_for_helper_lane", "primary_pending")


def normalize_lookup_key(value: Any) -> str:
    """Normalize a user-facing route selector to an exact lookup key.

    The resolver intentionally removes punctuation and whitespace but does not
    perform substring or fuzzy matching. That keeps `WF-78`, `Workflow 78`,
    and `78` equivalent without letting an abbreviated phrase select the first
    unrelated route.
    """
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def workflow_id_aliases(workflow_id: str) -> list[str]:
    """Return the safe generated aliases for a numeric workflow id."""
    values = [workflow_id]
    match = re.fullmatch(r"wf[-_ ]?(\d+)", workflow_id.strip(), flags=re.IGNORECASE)
    if match:
        number = match.group(1)
        values.extend([number, f"Workflow {number}"])
    return values


def route_alias_records(route_row: dict[str, Any]) -> list[dict[str, str]]:
    """Build deterministic exact-match aliases for one route row."""
    values: list[tuple[str, Any]] = [
        ("workflow_id", route_row.get("workflow_id")),
        ("display_name", route_row.get("display_name")),
    ]
    workflow_id = str(route_row.get("workflow_id") or "")
    values.extend(("generated_workflow_id", item) for item in workflow_id_aliases(workflow_id))
    values.extend(("declared_alias", item) for item in route_row.get("aliases", []) or [])

    records: dict[str, dict[str, str]] = {}
    for alias_kind, alias in values:
        alias_text = str(alias or "").strip()
        alias_key = normalize_lookup_key(alias_text)
        if alias_key and alias_key not in records:
            records[alias_key] = {
                "alias": alias_text,
                "alias_key": alias_key,
                "alias_kind": alias_kind,
            }
    return list(records.values())


def declared_route_aliases(
    workflow_id: str,
    display_name: str,
    aliases: list[str] | None,
) -> list[str]:
    """Persist the full, human-readable exact alias set on a route row."""
    records = route_alias_records({
        "workflow_id": workflow_id,
        "display_name": display_name,
        "aliases": aliases or [],
    })
    return [record["alias"] for record in records]


def route(
    workflow_id: str,
    display_name: str,
    tier: str,
    current_state: str,
    next_action: str,
    continuity_note: str | None,
    primary_route_artifact: str | None,
    secondary_artifacts: list[str],
    validator_commands: list[str],
    blockers: list[str],
    stop_lines: list[str],
    authority_boundary: str,
    owner_action_required: bool,
    safe_for_helper_lane: bool,
    default_resume_command: str | None,
    primary_pending: bool = False,
    effective_status_override: str | None = None,
    aliases: list[str] | None = None,
) -> dict[str, Any]:
    row = {
        "workflow_id": workflow_id,
        "display_name": display_name,
        "aliases": declared_route_aliases(workflow_id, display_name, aliases),
        "tier": tier,
        "current_state": current_state,
        "next_action": next_action,
        "continuity_note": continuity_note,
        "primary_route_artifact": primary_route_artifact,
        "primary_pending": primary_pending,
        "secondary_artifacts": secondary_artifacts,
        "validator_commands": validator_commands,
        "last_validated_at": None,  # filled at build time
        "blockers": blockers,
        "stop_lines": stop_lines,
        "authority_boundary": authority_boundary,
        "owner_action_required": owner_action_required,
        "safe_for_helper_lane": safe_for_helper_lane,
        "default_resume_command": default_resume_command,
    }
    if effective_status_override:
        row["effective_status_override"] = effective_status_override
    return row


# Stop-line phrasing reused across review-only lanes.
_REVIEW_STOP = (
    "Index is a derived route map; Active Workflows and exact continuity notes "
    "stay authority. No canon/portfolio/ticker-card/SQL-canon mutation, no "
    "paper/live/brokerage/account action, no cron/config/runtime mutation, no "
    "owner-approval inference from any route row."
)


def build_routes() -> list[dict[str, Any]]:
    routes = [
        # ---- P0 ----
        route(
            "WF75",
            "Retail Investor Finance Intelligence SaaS",
            "P0",
            "Internal/service-led finance vertical: anonymous scenarios, "
            "service-state, operator console, renderer/export, PM handoff, WF77 "
            "evidence, macro/recommendation tracking, polished PDF/Excel packaging, paused manual finance-delivery SaaS gate, authority spine.",
            "Run/refine the next anonymous service-state slice and keep the internal PM PDF, operator Excel, and paused finance-delivery gate ready for manual SaaS deliverable review.",
            f"{CONTINUITY}/Workflow 75 - AI Productivity and Business Opportunity Intelligence Expansion.md",
            "tmp/wf75-service-state-current.json",
            [
                "scripts/wf75_training_desk.py",
                "tmp/wf75-operator-console.json",
                "tmp/wf75-deliverable-packager.json",
                "tmp/wf75-deliverables-workbook.xlsx",
                "tmp/finance-delivery-series.json",
                "tmp/finance-delivery-series.xlsx",
            ],
            [
                "python scripts\\wf75_training_desk.py --write --write-md --write-training-assets --validate",
                "python scripts\\wf75_deliverable_packager.py --write --validate",
                "python scripts\\finance_delivery_series_orchestrator.py --mode all --write --validate",
            ],
            ["Customer/public/account/advice output blocked", "No fake-person product truth"],
            [
                "No fake-person product truth, public/customer/account/advice/trading claims, "
                "guaranteed return/win-rate/probability claim, source-licensing assumption, "
                "or legal/compliance-readiness claim.",
            ],
            "review-only internal/service-led; customer output gated",
            True,
            True,
            None,
        ),
        route(
            "WF-RETAIL-ROUTING",
            "Retail-Grade Truth Routing System",
            "P0",
            "Resumed by Randall on 2026-06-18 for internal answer-safety routing proof; "
            "customer output remains blocked until separate launch gates clear.",
            "Refresh routing contract, answer harness, automation plane, and customer-output "
            "decision packet. Use the router internally to classify source-open/review-only/"
            "blocked answer paths; do not produce customer output.",
            f"{CONTINUITY}/Retail-Grade Truth Routing System.md",
            "scripts/retail_truth_routing_contract.py",
            [
                "scripts/retail_answer_harness.py",
                "scripts/retail_automation_control_plane.py",
                "scripts/retail_customer_output_decision_packet.py",
            ],
            [
                "python scripts\\retail_truth_routing_contract.py --write --validate",
                "python scripts\\retail_answer_harness.py --write --validate",
                "python scripts\\retail_automation_control_plane.py --write --validate",
                "python scripts\\retail_customer_output_decision_packet.py --write --validate",
            ],
            ["Customer-safe output requires separate owner, licensing, privacy, compliance, delivery, and runtime/security gates"],
            [
                "No SQL-first promotion, SQL writes/imports, customer/external output, "
                "canon/portfolio mutation, paper/live/account action, Python fallback "
                "retirement, cron mutation, or approval inference.",
            ],
            "review-only internal routing; customer output gated",
            True,
            True,
            "python scripts\\retail_truth_routing_contract.py --write --validate",
            aliases=["Retail-Grade Truth Routing"],
        ),
        # ---- P1 ----
        route(
            "WF79-SMB",
            "SMB Workflow Clarity / Marketing Ops Automation",
            "P1",
            "Resumed by Randall on 2026-06-13 as an automation-first "
            "monetization lane: Lead Rescue, workflow clarity, marketing "
            "operations follow-up engine, Academy assets, local cockpit/SQL "
            "service-state, and boundary proof.",
            "Review completed sanitized Lead Rescue and Marketing Ops phase "
            "proof: offer/ICP packet, demo packets, automation blueprints, "
            "cockpit panel, training/sales practice, outreach kit, pilot "
            "scope/intake, vertical ICP targeting, demo polish, pilot-readiness "
            "packet, sales conversation drill, demo-selection tree, vertical "
            "test framework, rollout-readiness plan, client-rollout checklist, "
            "curriculum map, and validator lint. Next gate is Randall exact "
            "approval for real outreach or pilot use; do not contact real "
            "prospects yet.",
            None,
            "tmp/wf79-smb-phase-closeout.json",
            [
                "scripts/generic_intelligence_saas_pivot.py",
                "scripts/wf75_training_desk.py",
                "tmp/wf75-smb-boundary-lint.json",
                "tmp/wf79-smb-outreach-prep-validation.json",
                "tmp/wf79-smb-pilot-readiness-validation.json",
                "tmp/wf79-smb-rollout-readiness-validation.json",
            ],
            ["python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate"],
            ["No real customer data/outbound/public claims"],
            [
                "No real customer data, credentials, outbound/writeback, external delivery, "
                "ROI/legal/compliance/security claims, spend, ad account action, SQL-as-canon, "
                "or certification claims.",
            ],
            "review-only; no customer/outbound/public",
            True,
            True,
            "python scripts\\generic_intelligence_saas_pivot.py --write --write-db --validate",
        ),
        route(
            "WF79",
            "Veritas Command Center V2 UI Infrastructure",
            "P1",
            "Compact shell is promoted as the active Veritas first-read route; "
            "Randall full-detail legacy dashboard and dashboard-data.json remain "
            "retained by design for row-level drilldown/rollback. Adapter mode "
            "compact_primary_legacy_passthrough (29 compact-primary, 4 metadata, "
            "0 legacy-only routes). Render-default proof: 4 safe disable paths, "
            "0 unsafe.",
            "Use compact reader/shell as active route; keep legacy full-detail "
            "dashboard for Randall drilldown. Optional future work is legacy "
            "payload retirement, not a blocking Path B dependency.",
            f"{CONTINUITY}/Workflow 79 - Veritas Command Center V2 UI Infrastructure.md",
            "tmp/presentation-retrieval-route-map.json",
            [
                f"{CONTINUITY}/Presentation Artifact Flattening and Retrieval Routing.md",
                f"{CONTINUITY}/Deployment State Contract Migration.md",
                "tmp/veritas-command-center-compact-reader.json",
                "tmp/veritas-command-center-compact.html",
                "tmp/veritas-command-center.html",
                "tmp/dashboard-presentation-view-model.json",
            ],
            ["python scripts\\deployment_contract_migration_validation_bundle.py --write"],
            [],
            [
                "Local/review-only UI. No canon/portfolio mutation, paper/live/account action, "
                "approval inference, public/customer delivery, SQL promotion, proof deletion, "
                "sidecar archive/delete, or config/channel/runtime expansion.",
            ],
            "review-only local UI",
            True,
            True,
            None,
        ),
        route(
            "WF72",
            "Guarded Finance SQL Canon",
            "P1",
            "265-row cache boundary and A2 fallback read guard remain support-only. "
            "WF72 now owns the SQL-first migration finish-line proof after Randall's "
            "2026-06-19 decision to finish SQL-primary migration with schedule/parity "
            "and the 2026-06-21 band-proposals source migration closeout. The active "
            "reference_levels path is SQL-first row-level provenance: GOOG/GS/NVDA/VRT "
            "source metadata and low/high/stop lineage now point to tmp/band-proposals.json; "
            "the no-single-200-row-JSON condition is informational, not a blocker. Old "
            "Execution Board anchor packets are compatibility evidence only.",
            "Continue SQL-first migration with consumer expansion and duplicate-surface "
            "retirement proof only. Use SQL-native source-family proof, targeted repair "
            "packet, full-answer parity, and migration completion runner as the active "
            "validators. Keep Python/feeders retained until consumer parity and "
            "source-feeder retirement gates clear, and require a separate exact gate before "
            "schema change, cron schedule change, Python fallback retirement, source-feeder "
            "retirement, archive/delete apply, or finance answer-path ownership change.",
            f"{CONTINUITY}/Workflow 72 - Guarded Finance SQL Canon.md",
            "tmp/finance-sql-primary-migration-plan.json",
            [
                "state/finance/finance-canon.sqlite",
                "tmp/band-proposals.json",
                "tmp/reference-levels-band-proposals-source-migration.json",
                "tmp/reference-levels-band-proposals-source-migration-apply-result.json",
                "tmp/reference-levels-targeted-repair-packet.json",
                "tmp/reference-levels-sql-native-source-family-proof.json",
                "tmp/full-answer-parity/full-answer-parity-rollup.json",
                "tmp/sql-canon-consumer-registry-guard.json",
                "tmp/sql-canon-migration-completion-runner.json",
                "tmp/sql-canon-old-anchor-residue-guard.json",
                "tmp/finance-sql-consumer-migration-burndown.json",
                "tmp/finance-sql-markdown-field-ownership.json",
                "tmp/veritas-artifact-index.sqlite",
                "tmp/veritas-canon-cache.sqlite",
                "tmp/fast-path-qa.json",
                "08. Audits/SQL Primary Finance Canon Migration Audit and Finish Line Plan - 2026-06-19.md",
            ],
            [
                "python scripts\\finance_sql_primary_migration_plan.py --write --write-md --validate",
                "python scripts\\finance_sql_markdown_field_ownership.py --write --validate",
                "python scripts\\reference_levels_band_proposals_source_migration.py --write --validate",
                "python scripts\\reference_levels_targeted_repair_packet.py --write --validate",
                "python scripts\\reference_levels_sql_native_source_family_proof.py --write --validate",
                "python scripts\\full_intelligence_answer_parity.py --all --write --validate --pretty",
                "python scripts\\sql_canon_migration_completion_runner.py --write --validate",
                "python scripts\\sql_canon_old_anchor_residue_guard.py --write --validate",
                "python scripts\\finance_sql_consumer_migration_burndown.py --write --write-md --validate",
                "python scripts\\finance_sql_canon_access.py --write --validate",
                "python scripts\\artifact_index.py validate",
                "python scripts\\fast_path_qa.py --write --validate",
            ],
            [
                "Band-proposals source migration is complete for GOOG/GS/NVDA/VRT; source-family proof reports row_issue_counts={} and SQL-first provenance clean.",
                "The legacy Execution Board anchor packet remains compatibility-only and should not be used as the strategic migration boundary.",
                "Separate gate required before schema mutation, cron schedule change, Python fallback retirement, source-feeder retirement, archive/delete apply, or finance answer-path ownership.",
            ],
            [
                "No SQL data/schema mutation, cron schedule mutation, archive/move/delete, "
                "human canon/portfolio mutation, action-state mutation, customer output, "
                "runtime/config mutation, Python retirement, SQL-first promotion, finance "
                "front-door ownership, capital deployment, paper/live/account action, or "
                "owner approval inference without a separate exact gate.",
            ],
            "support-only plus migration proof; SQL-first migration green does not grant source-feeder retirement, archive/delete, portfolio/canon mutation, or finance execution authority by itself",
            True,
            True,
            "python scripts\\finance_sql_primary_migration_plan.py --write --write-md --validate",
            effective_status_override="support_only_with_active_sql_primary_migration",
        ),
        route(
            "WF68",
            "Intraday Alert Engine and Advisor Surface",
            "P1",
            "Reduced-load internal alert/advisor proof; Telegram shadow and "
            "high-frequency handoff paused; authority flags false.",
            "Keep producer/digest proof clean; manual REVIEW / PREPARE only "
            "after artifact + WF67 guard inspection.",
            f"{CONTINUITY}/Workflow 68 - Intraday Alert Engine and Advisor Surface.md",
            None,
            [],
            ["python scripts\\wf68_runtime_wiring_plan_validator.py --write"],
            ["Telegram shadow delivery paused", "authority flags false"],
            [
                "No channel expansion, config/auth/runtime mutation, live/paper/order/account "
                "action, canon/portfolio/sizing/sleeve/cash/risk-rule mutation, or approval inference.",
            ],
            "review-only; manual REVIEW/PREPARE gated",
            True,
            False,
            None,
        ),
        route(
            "WF73",
            "Queue/Index/Boot Optimization",
            "P1",
            "Boot/control routing, PM queue, cron freshness spine, cron "
            "retire/merge, helper manifest, hardening pass, cockpit proof "
            "active. Workflow routing index covers 33 routes, derived SQLite "
            "route-control lookup is live, concurrent lane lease register is "
            "live, ordered WF73 audit runner is active, and truth-surface/"
            "efficiency proof is active. Local Postgres coordination-spine "
            "Phase D/E review artifacts are complete; shadow-pilot telemetry "
            "is active with JSON primary. All remain derived/review-only.",
            "Use wf73_control_plane_audit.py for full WF73 audits; use canned "
            "SQL route-control lookups after JSON/DB parity is green; use lane "
            "manager before intentional multi-helper work. Monitor shadow "
            "metrics only; no Postgres service, SQL execution, or lane-claim "
            "authority is active.",
            f"{CONTINUITY}/Workflow 73 - Queue Index and Boot Surface Optimization.md",
            "tmp/workflow-routing-index.json",
            [
                f"{CONTINUITY}/Workflow Routing Index Expansion.md",
                "tmp/workflow-routing-index.sqlite",
                "tmp/concurrent-lane-register.json",
                "tmp/truth-surface-inventory.json",
                "tmp/route-efficiency-scorecard.json",
                "tmp/fast-path-qa.json",
                "tmp/wf73-control-plane-audit.json",
                "tmp/wf73-postgres-coordination-spine-plan.json",
                "tmp/wf73-postgres-schema-adapter-proposal.json",
                "tmp/wf73-postgres-phase-e-review-packet.json",
                "tmp/wf73-postgres-ddl-contract-review.json",
                "tmp/wf73-postgres-parity-validator-spec-review.json",
                "tmp/wf73-postgres-failure-drills-review.json",
                "tmp/wf73-postgres-windows-runtime-matrix-review.json",
                "tmp/wf73-postgres-go-no-go-review.json",
                "tmp/wf73-postgres-shadow-pilot.json",
                "tmp/wf73-postgres-shadow-pilot-metrics.json",
                "scripts/concurrent_lane_manager.py",
                "scripts/wf73_postgres_shadow_pilot.py",
                "tmp/cron-freshness-spine.json",
            ],
            [
                "python scripts\\wf73_control_plane_audit.py --write --validate",
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
                "python scripts\\concurrent_lane_manager.py --status --write --validate",
                "python scripts\\wf73_postgres_shadow_pilot.py --write --validate",
                "python scripts\\truth_surface_inventory.py --write --validate",
                "python scripts\\fast_path_qa.py --write --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
            ],
            [],
            [
                "No new authority source, doctrine rewrite, destructive/config/channel/runtime "
                "mutation, Postgres/Docker/native-service install, network exposure, "
                "authority weakening, SQL-first promotion, autonomous spawning/scheduling, "
                "or inferred approval.",
            ],
            "review-only route capacity; index never outranks Active Workflows",
            False,
            True,
            "python scripts\\workflow_routing_index.py --write --write-db --validate",
        ),
        route(
            "WF70-WF66",
            "Official Evidence Spine",
            "P1",
            "Registry/latest-selector migration complete; official "
            "earnings/reconciliation routes have no-drift proof.",
            "Monitor validators; capture/roll forward only for active "
            "finance/product goals.",
            f"{CONTINUITY}/Workflow 70 - Official Company Source Capture and Reconciliation.md",
            None,
            [f"{CONTINUITY}/Workflow 66 - Why-Aware Recommendation Packet Evidence Bridge.md"],
            ["python scripts\\wf70_wf66_official_evidence_spine.py --validate-only"],
            [],
            [
                "No invented values, no bridge-present-equals-reconciled shortcut, no "
                "portfolio/canon/trade authority from evidence alone, no owner approval inference.",
            ],
            "evidence-only; no portfolio/trade authority",
            True,
            True,
            None,
        ),
        route(
            "WF77",
            "Finance Coverage / Question Router",
            "P1",
            "42/42 production cards enriched; active 200-card review set "
            "rebuilds with stale-evidence repair signals. Shared "
            "deployment-state contract available; 200-card rebuild passed after "
            "Slice 6. WF77 now feeds coverage/card/source proof into the "
            "finance_intelligence_state -> WF84 -> WF85 answer route.",
            "Use finance_intelligence_state.py ticker <TICKER> first for "
            "finance questions. Use WF77 for ticker-card coverage/source proof "
            "and refresh repair before promotion-quality WF84/WF85 use.",
            f"{CONTINUITY}/Workflow 77 - Finance Intelligence Coverage and Question Router.md",
            "scripts/finance_intelligence_state.py",
            [
                f"{CONTINUITY}/Deployment State Contract Migration.md",
                "scripts/artifact_index.py",
            ],
            ["python scripts\\artifact_index.py validate"],
            [],
            [
                "Review/intelligence only; no live trading/account/money movement, paper "
                "execution, approval inference, import/apply, production promotion, or "
                "canon/portfolio mutation.",
            ],
            "review/intelligence only",
            True,
            True,
            None,
        ),
        route(
            "WF78",
            "Tier A/B Evidence Repair & Auto-Routing",
            "P1",
            "200 active rows. Strategic production boundary is the proof-joined validated production-scope path, "
            "not the retired production_current_42 label. Current WF78 proof reports those rows as "
            "active_internal_universe under the SQL-first Tier A/B/C schema. Auto-router "
            "currently classifies live Tier A/B/C routing while stale final-promotion packets cannot emit "
            "A-READY. Tier A confidence "
            "gate blocks conflicted rows from A-READY. Daily delta, route-TICKER, capital-review queue, AI "
            "event-triggered rerouting, evidence-drag reduction, family-level "
            "repair routing, source-open repair execution, source-open work packets, "
            "position-sizing review, deployment-readiness review, source-artifact capture review, "
            "sizing integration proposals, Tier A owner-readiness proposals, missing-band repair, source-capture requirements, "
            "official-source discovery, official registry proposals, registry apply preview, "
            "promotion-only owner-lineage queue, contract guard, owner-lineage discovery, owner-lineage proposal, repair scoreboard, "
            "scaleout policy dry run, tier-weighted freshness resolution, "
            "append-only tier-routing event ledger, daily movement ledger, repair-priority queue, Intelligence Routing V2, "
            "PH owner-review packet, Tier A invalidation queue, official source-capture packet, "
            "ticker freshness ledger, daily freshness loop, and artifact action scoring are built. Repeatable "
            "parallel orchestration still handles macro/evidence/card-prep work; all "
            "surfaces have 0 capital/trade approvals. 201-500 import/scaleout remains report-only "
            "unless a separate exact owner gate approves it.",
            "WF78 is the non-capital repair/promotion feeder for the "
            "finance_intelligence_state -> WF84 -> WF85 answer route. "
            "Use finance_production_scope.py and finance_production_grade_policy_gate.py as the forward production-grade "
            "answer boundary: SQL Tier A/A-READY joined to current router, coverage, confidence, and authority proof. "
            "Legacy 42 runtime fields are hard-retired from active SQL tables/views; active consumers must route through "
            "production-scope / SQL Tier A/B/C surfaces. "
            "Use wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded as the promoted daily cron surface, with wf78_daily_movement_ledger.py as the operator ledger; keep wf78_daily_freshness_loop.py as a compatibility refresh/routing/debt "
            "measurement spine, then use tier-weighted freshness resolution for the 200-row debt answer. Use source-open repair execution, source-open work "
            "packets, concrete sizing/deployment/source-capture reviews, integration proposals, "
            "Tier A owner-readiness proposals, missing-band repair, source-capture requirements, owner-lineage proposal, freshness ledger, tier-weighted resolver, append-only tier-routing event ledger, daily movement ledger, and repair-priority queue "
            "for Tier A/B repair routing before owner-card prep. Use the repair debt scoreboard first: "
            "review ready sizing/deployment rows, keep owner-lineage rows blocked for owner/source decision, "
            "and treat registry apply preview as a separate gated path. Keep CME/LMT/META in invalidation "
            "review. The market deployment operating loop now reads WF78 tier movement "
            "beside WF85 timing and WF87 daylight proof so tier changes, freshness, "
            "opportunity probes, and autonomous review-card materialization are visible "
            "as one review-only chain. Ask only for capital/execution/account/sizing/apply mutation.",
            f"{CONTINUITY}/Workflow 78 - 500 Ticker Finance Intelligence Scaleout.md",
            "tmp/wf78-auto-tier-routing.json",
            [
                "scripts/wf78_tier_a_confidence_gate.py",
                "scripts/wf78_auto_tier_router.py",
                "scripts/wf78_event_triggered_rerouting.py",
                "scripts/wf78_evidence_drag_reducer.py",
                "scripts/wf78_evidence_family_repair_runner.py",
                "scripts/wf78_source_open_repair_executor.py",
                "scripts/wf78_source_open_work_packet.py",
                "scripts/wf78_position_sizing_surface_review.py",
                "scripts/wf78_deployment_readiness_review.py",
                "scripts/wf78_source_artifact_capture_review.py",
                "scripts/wf78_position_sizing_integration_proposal.py",
                "scripts/wf78_tier_a_owner_readiness_proposal.py",
                "scripts/wf78_missing_band_context_repair.py",
                "scripts/wf78_source_capture_requirements_queue.py",
                "scripts/wf78_official_source_discovery_runner.py",
                "scripts/wf78_official_registry_proposal.py",
                "scripts/wf78_official_registry_apply_preview.py",
                "scripts/wf78_promotion_owner_lineage_queue.py",
                "scripts/wf78_contract_state_guard.py",
                "scripts/wf78_owner_lineage_discovery.py",
                "scripts/wf78_owner_lineage_proposal.py",
                "scripts/wf78_repair_debt_scoreboard.py",
                "scripts/wf78_scaleout_policy_dry_run.py",
                "scripts/wf78_ph_owner_review_candidate_packet.py",
                "scripts/wf78_tier_a_invalidation_review_queue.py",
                "scripts/wf78_official_source_capture_packet.py",
                "scripts/wf78_next_owner_review_and_source_capture_integration.py",
                "scripts/wf78_ticker_freshness_ledger.py",
                "scripts/wf78_tier_weighted_freshness_resolver.py",
                "scripts/wf78_tier_routing_event_ledger.py",
                "scripts/wf78_daily_freshness_loop.py",
                "scripts/wf78_daily_movement_ledger.py",
                "scripts/wf78_intelligence_routing_v2.py",
                "scripts/finance_production_grade_policy_gate.py",
                "scripts/parallel_repeatable_work_orchestrator.py",
                "scripts/finance_decision_factory.py",
                "scripts/wf78_evidence_repair_batch_runner.py",
                "scripts/control_closeout_bundle.py",
                "scripts/pm_execution_loop.py",
                "scripts/artifact_intelligence_action_scorer.py",
                "scripts/finance_market_deployment_operating_loop.py",
                "scripts/autonomous_routing_deployment_cards.py",
                "scripts/test_autonomous_routing_deployment_cards.py",
                "tmp/wf78-tier-a-confidence-gate.json",
                "tmp/wf78-event-triggered-rerouting.json",
                "tmp/wf78-evidence-drag-reduction.json",
                "tmp/wf78-evidence-family-repair.json",
                "tmp/wf78-source-open-repair-execution.json",
                "tmp/wf78-source-open-work-packets.json",
                "tmp/wf78-position-sizing-surface-review.json",
                "tmp/wf78-deployment-readiness-review.json",
                "tmp/wf78-source-artifact-capture-review.json",
                "tmp/wf78-position-sizing-integration-proposal.json",
                "tmp/wf78-tier-a-owner-readiness-proposals.json",
                "tmp/wf78-missing-band-context-repair.json",
                "tmp/wf78-source-capture-requirements-queue.json",
                "tmp/wf78-official-source-discovery.json",
                "tmp/wf78-official-registry-proposal.json",
                "tmp/wf78-official-registry-apply-preview.json",
                "tmp/wf78-promotion-owner-lineage-queue.json",
                "tmp/wf78-contract-state-guard.json",
                "tmp/wf78-owner-lineage-discovery.json",
                "tmp/wf78-owner-lineage-proposal.json",
                "tmp/wf78-repair-debt-scoreboard.json",
                "tmp/wf78-scaleout-policy-dry-run.json",
                "tmp/wf78-ph-owner-review-candidate-packet.json",
                "tmp/wf78-tier-a-invalidation-review-queue.json",
                "tmp/wf78-official-source-capture-packet.json",
                "tmp/wf78-next-owner-review-and-source-capture-integration.json",
                "tmp/wf78-ticker-freshness-ledger.json",
                "tmp/wf78-tier-weighted-freshness-resolution.json",
                "tmp/wf78-tier-routing-event-ledger.json",
                "state/workflows/wf78-tier-routing-events.jsonl",
                "tmp/wf78-daily-freshness-loop.json",
                "tmp/wf78-daily-movement-ledger.json",
                "tmp/wf78-repair-priority-queue.json",
                "tmp/wf78-intelligence-routing-v2.json",
                "tmp/finance-production-grade-policy-gate.json",
                "tmp/parallel-repeatable-work-orchestration.json",
                "tmp/macro-event-guard-loop.json",
                "tmp/wf78-owner-card-prep-loop.json",
                "tmp/wf78-tier-a-evidence-repair-batch.json",
                "tmp/finance-decision-factory.json",
                "tmp/wf78-evidence-repair-batch.json",
                "tmp/control-closeout-bundle.json",
                "tmp/pm-execution-loop.json",
                "tmp/artifact-intelligence-action-scorer.json",
                "tmp/finance-market-deployment-operating-loop.json",
                "tmp/autonomous-routing-deployment-cards.json",
                "tmp/wf78-routing-dashboard.json",
            ],
            [
                "python scripts\\finance_decision_factory.py --ledger-only --write --validate",
                "python scripts\\wf78_evidence_repair_batch_runner.py --tier A --write --validate",
                "python scripts\\wf78_evidence_family_repair_runner.py --family price_band_stop --write --validate",
                "python scripts\\wf78_source_open_repair_executor.py --write --validate",
                "python scripts\\wf78_source_open_work_packet.py --write --validate",
                "python scripts\\wf78_position_sizing_surface_review.py --write --validate",
                "python scripts\\wf78_deployment_readiness_review.py --write --validate",
                "python scripts\\wf78_source_artifact_capture_review.py --write --validate",
                "python scripts\\wf78_position_sizing_integration_proposal.py --write --validate",
                "python scripts\\wf78_tier_a_owner_readiness_proposal.py --write --validate",
                "python scripts\\wf78_missing_band_context_repair.py --write --validate",
                "python scripts\\wf78_source_capture_requirements_queue.py --write --validate",
                "python scripts\\wf78_official_source_discovery_runner.py --write --validate",
                "python scripts\\wf78_official_registry_proposal.py --write --validate",
                "python scripts\\wf78_official_registry_apply_preview.py --write --write-proposed --validate",
                "python scripts\\wf78_promotion_owner_lineage_queue.py --write --validate",
                "python scripts\\wf78_contract_state_guard.py --write --validate",
                "python scripts\\wf78_owner_lineage_discovery.py --write --validate",
                "python scripts\\wf78_owner_lineage_proposal.py --write --validate",
                "python scripts\\wf78_repair_debt_scoreboard.py --write --validate",
                "python scripts\\wf78_scaleout_policy_dry_run.py --write --validate",
                "python scripts\\wf78_ph_owner_review_candidate_packet.py --write --validate",
                "python scripts\\wf78_tier_a_invalidation_review_queue.py --write --validate",
                "python scripts\\wf78_official_source_capture_packet.py --write --validate",
                "python scripts\\wf78_next_owner_review_and_source_capture_integration.py --write --validate",
                "python scripts\\wf78_ticker_freshness_ledger.py --write --validate",
                "python scripts\\wf78_tier_weighted_freshness_resolver.py --write --validate",
                "python scripts\\wf78_tier_routing_event_ledger.py --write --write-md --validate",
                "python scripts\\wf78_daily_movement_ledger.py --write --write-md --validate",
                "python scripts\\wf78_intelligence_routing_v2.py --layer ledger_publish --write --validate",
                "python scripts\\finance_production_grade_policy_gate.py --write --validate",
                "python scripts\\wf78_daily_freshness_loop.py --write --validate",
                "python scripts\\parallel_repeatable_work_orchestrator.py --write --validate",
                "python scripts\\control_closeout_bundle.py --write --validate",
                "python scripts\\wf78_phase_runner.py --phase all-safe --write --validate",
                "python scripts\\wf78_evidence_drag_reducer.py --write --validate",
                "python scripts\\artifact_intelligence_action_scorer.py --write --validate",
                "python scripts\\finance_market_deployment_operating_loop.py --refresh-readiness --write --write-md --validate",
            ],
            [],
            [
                "Automated routing is non-capital only; no capital deployment, paper/live "
                "order, brokerage/account action, money movement, portfolio/cash/sizing "
                "execution, customer/public output, or SQL-first/canon authority without "
                "separate exact approval/gates. No generated artifact implies trade approval.",
            ],
            "automated non-capital routing; capital/execution gated",
            True,
            True,
            "python scripts\\wf78_phase_runner.py --phase all-safe --write --validate",
        ),
        route(
            "WF84",
            "Guarded Alert Evidence Plane",
            "P0",
            "Internal finance infrastructure lane opened for a formal canonical "
            "data-plane contract, read-only packet, and derived SQLite companion. "
            "WF78 and finance-intelligence state may feed it only through "
            "validated non-capital artifacts.",
            "Use the validated JSON packet, SQLite companion, and phase 6-10 "
            "proof for internal read-only consumer expansion; use full-answer "
            "parity before duplicate-surface retirement.",
            f"{CONTINUITY}/Workflow 84 - Guarded Alert Evidence Plane.md",
            "tmp/canonical-finance-data-plane.json",
            [
                "scripts/canonical_finance_data_plane_contract.py",
                "scripts/canonical_finance_data_plane.py",
                "scripts/canonical_finance_data_plane_phase6_10.py",
                "scripts/full_intelligence_answer_parity.py",
                "tmp/canonical-finance-data-plane-contract.json",
                "tmp/canonical-finance-data-plane-validation.json",
                "tmp/canonical-finance-data-plane.sqlite",
                "tmp/canonical-finance-data-plane-phase6-10.json",
                "tmp/canonical-finance-data-plane-retirement-readiness.json",
                "tmp/full-answer-parity/full-answer-parity-rollup.json",
                "tmp/wf78-auto-tier-routing.json",
                "tmp/finance-intelligence-state.sqlite",
                "tmp/wf78-tier-weighted-freshness-resolution.json",
                "tmp/finance-decision-sync-spine.json",
            ],
            [
                "python scripts\\canonical_finance_data_plane_contract.py --write --validate",
                "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
                "python scripts\\full_intelligence_answer_parity.py --all --write --pretty",
                "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
                "python scripts\\canonical_finance_data_plane_retirement_readiness.py --write --validate",
                "python scripts\\db_lifecycle_manifest.py --write --validate",
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
                "python scripts\\workflow_router.py WF84 --answer all --write-capsules --validate",
            ],
            [],
            [
                "Internal personal finance infrastructure only; no retail/customer launch, "
                "customer/account/PII/suitability/brokerage data, canon/portfolio/cash/"
                "risk-rule mutation, capital approval, paper/live/account action, SQL/"
                "capsule/dashboard row as approval, or owner approval inference.",
            ],
            "internal review-only canonical data-plane interface; no customer/account/execution authority",
            True,
            True,
            "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
        ),
        route(
            "WF85",
            "Alerts and Recommendations OS",
            "P0",
            "Contract and Phase 1 builder are active above WF84. The builder "
            "emits fail-closed review-only decision cards, source/freshness "
            "gate, authority/vocabulary validation, approval-card gate, and "
            "risk/sizing overlay; the repair conveyor routes finance-domain blockers "
            "back to WF78/WF84 feeder repair without creating implementation blockers "
            "unless conveyor validation or WF84/WF85 quality gates regress. Tier A/B "
            "rows require daily decision-grade entry-band/stop coverage for finance "
            "review; missing coverage is finance-domain debt, while canon/note apply "
            "remains limited to the approved entry_band maintenance gate. A cron guard "
            "proves complete Tier A/B band rows carry current market-date context and "
            "cron contracts include the required artifacts. Primary-state blockers and below-stop states "
            "override optimistic auto_state; generated approval drafts remain "
            "zero until all gates and fresh WF67 guard context pass; exact "
            "paper execution still routes through WF67 only after Randall "
            "approves the scoped order. The market deployment operating loop "
            "now unifies the morning/intraday cron schedule, WF78 tier routing, "
            "WF84/WF85 freshness, WF85 timing, WF87 daylight gates, and Tier A "
            "opportunity probes into one review-only trade-readiness packet. The "
            "autonomous routing/card queue materializes owner-review references only "
            "when WF78/WF85/WF87 gates agree and keeps execution authority false.",
            "WF85 full-answer parity is clean across the 200-ticker WF84 population, "
            "and targeted production blockers have been repaired or adjudicated: "
            "missing band/stop, freshness, and source-open blocker counts are now "
            "zero; remaining rows are true no-chase, true below-stop/invalidation, "
            "or finance-domain repair/monitor states that do not create PM implementation "
            "blockers while conveyor validation and quality gates remain clean. Tier A/B "
            "missing decision-grade band/stop coverage is refreshed daily as finance-domain "
            "debt, not auto-applied to canon. The WF85 full-answer "
            "assembler now owns the default ticker-answer contract; legacy answer "
            "packets are compatibility snapshots generated from the assembler. "
            "Retirement planning may continue, but archive/delete/apply and "
            "source-feeder retirement remain false until exact owner approval.",
            f"{CONTINUITY}/Workflow 85 - Alerts and Recommendations OS.md",
            "tmp/trade-grade-decision-cards.json",
            [
                "scripts/trade_grade_decision_os_contract.py",
                "scripts/trade_grade_decision_cards.py",
                "scripts/trade_grade_repair_conveyor.py",
                "scripts/trade_grade_os_freshness_cron_runner.py",
                "scripts/trade_grade_os_readiness_rollup.py",
                "scripts/test_trade_grade_os_readiness_rollup.py",
                "scripts/wf85_deployment_timing_gate.py",
                "scripts/test_wf85_deployment_timing_gate.py",
                "scripts/finance_market_deployment_operating_loop.py",
                "scripts/test_finance_market_deployment_operating_loop.py",
                "scripts/autonomous_routing_deployment_cards.py",
                "scripts/test_autonomous_routing_deployment_cards.py",
                "scripts/autonomous_card_authority_audit.py",
                "scripts/test_autonomous_card_authority_audit.py",
                "scripts/trade_grade_full_answer_assembler.py",
                "scripts/wf78_missing_band_context_repair.py",
                "scripts/tier_ab_band_freshness_cron_guard.py",
                "scripts/wf85_retirement_gate_adjudication.py",
                "scripts/wf85_production_blocker_repair.py",
                "scripts/ticker_answer_packet_retirement_plan.py",
                "tmp/trade-grade-decision-os-contract.json",
                "tmp/trade-grade-source-freshness-gate.json",
                "tmp/trade-grade-decision-cards.json",
                "tmp/trade-grade-decision-card-authority-validation.json",
                "tmp/trade-grade-approval-card-gate.json",
                "tmp/trade-grade-risk-sizing-overlay.json",
                "tmp/wf85-deployment-timing-gate.json",
                "tmp/finance-market-deployment-operating-loop.json",
                "tmp/autonomous-routing-deployment-cards.json",
                "tmp/trade-grade-full-answer-assembler.json",
                "tmp/wf85-retirement-gate-adjudication.json",
                "tmp/wf85-production-blocker-repair.json",
                "tmp/ticker-answer-packet-retirement-approval-plan-20260609.json",
                "tmp/wf85-full-answer-assembler-opus-challenger-20260609.json",
                "tmp/trade-grade-repair-conveyor.json",
                "tmp/trade-grade-os-freshness-cron-runner.json",
                "tmp/trade-grade-os-readiness-rollup.json",
                "tmp/wf78-missing-band-context-repair.json",
                "tmp/tier-ab-band-freshness-cron-guard.json",
                "tmp/post-close-final-quote-ledger.json",
                "tmp/wf78-tier-weighted-freshness-resolution.json",
                "tmp/canonical-finance-data-plane.json",
                "tmp/canonical-finance-data-plane.sqlite",
                "tmp/canonical-finance-data-plane-phase6-10.json",
                "tmp/full-answer-parity/full-answer-parity-rollup.json",
                "tmp/wf78-capital-review-queue.json",
                "tmp/finance-decision-sync-spine.json",
            ],
            [
                "python scripts\\trade_grade_decision_os_contract.py --write --validate",
                "python scripts\\trade_grade_decision_cards.py --write --validate",
                "python scripts\\trade_grade_full_answer_assembler.py --all-wf84 --write --validate",
                "python scripts\\wf78_missing_band_context_repair.py --write --validate",
                "python scripts\\test_wf78_missing_band_context_repair_policy.py",
                "python scripts\\tier_ab_band_freshness_cron_guard.py --write --validate",
                "python scripts\\test_tier_ab_band_freshness_cron_guard.py",
                "python scripts\\trade_grade_repair_conveyor.py --write --validate",
                "python scripts\\trade_grade_os_readiness_rollup.py --write --validate",
                "python scripts\\test_trade_grade_os_readiness_rollup.py",
                "python scripts\\wf85_deployment_timing_gate.py --write --validate",
                "python scripts\\test_wf85_deployment_timing_gate.py",
                "python scripts\\autonomous_routing_deployment_cards.py --write --validate",
                "python scripts\\test_autonomous_routing_deployment_cards.py",
                "python scripts\\finance_market_deployment_operating_loop.py --refresh-readiness --write --write-md --validate",
                "python scripts\\test_finance_market_deployment_operating_loop.py",
                "python scripts\\trade_grade_os_freshness_cron_runner.py --write --write-md --validate",
                "python scripts\\wf85_retirement_gate_adjudication.py --write --validate",
                "python scripts\\wf85_production_blocker_repair.py --write --validate",
                "python scripts\\canonical_finance_data_plane.py --write --write-db --validate",
                "python scripts\\full_intelligence_answer_parity.py --all --write --pretty",
                "python scripts\\canonical_finance_data_plane_phase6_10.py --write --validate",
                "python scripts\\ticker_answer_packet_retirement_plan.py --write --validate",
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
                "python scripts\\workflow_router.py WF85 --answer all --write-capsules --validate",
                "python scripts\\pm_control_packet.py --write --write-db --validate",
            ],
            [],
            [
                "Internal/personal decision support only; no customer/account/PII/"
                "suitability data, no canon/portfolio/cash/sizing/risk-rule "
                "mutation, no capital approval, no paper/live/account action, "
                "no generated card/score/SQL row as owner approval, no owner "
                "approval inference.",
            ],
            "internal review-only decision/approval-card interface; no capital or execution authority",
            True,
            True,
            "python scripts\\trade_grade_decision_cards.py --write --validate",
        ),
        route(
            "WF86",
            "Main-Session Paper Autotrader OS",
            "P0",
            "Opened by Randall on 2026-06-11 as a paper-only, main-session-owned "
            "autotrader orchestration lane. It is shadow-first and currently "
            "grants no autonomous order authority. WF86 consumes WF85 decision "
            "state, written bands/stops, fresh quotes, market/sector context, "
            "paper positions, and WF67 guard state.",
            "Use the daily WF86 shadow/reconciliation cron runner to keep shadow "
            "and GET-only paper-order reconciliation proof current. The "
            "20-decision/5-session shadow threshold and reconciliation maturity "
            "gates are met. The scoped autonomous paper pilot is approved in "
            "principle, but autonomous execution stays blocked on Phase B "
            "assisted filled round trips and clean execution-time proof.",
            f"{CONTINUITY}/Workflow 86 - Main-Session Paper Autotrader OS.md",
            "tmp/paper-autotrader/policy.json",
            [
                "tmp/trade-grade-decision-cards.json",
                "tmp/finance-decision-factory.json",
                "tmp/wf78-capital-review-queue.json",
                "tmp/paper-autotrader/shadow-eligibility.json",
                "tmp/paper-autotrader/assisted-order-cards.json",
                "tmp/paper-autotrader/shadow-decisions.json",
                "tmp/paper-autotrader/autotrader-readiness.json",
                "tmp/paper-autotrader/guard-readiness.json",
                "tmp/paper-autotrader/wf86-daily-shadow-reconciliation-cron-runner.json",
                "tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json",
                "tmp/alpaca-paper-readiness/paper-execution-guard-validation.json",
                "tmp/alpaca-paper-readiness/paper-order-reconciliation.vrt-wf86-assisted-approved.json",
                "tmp/alpaca-paper-readiness/paper-order-history-classifier.json",
                "tmp/paper-autotrader/trade-decision-journal.jsonl",
                "tmp/wf87-position-sizing-runtime-check.json",
                "tmp/wf87-portfolio-circuit-breakers.json",
                "tmp/wf87-approval-freshness-ttl.json",
                "tmp/wf87-intraday-monitor.json",
                "tmp/wf87-assisted-paper-cadence.json",
                "tmp/wf87-shadow-outcome-scorecard.json",
                "tmp/wf87-market-hours-gate-probe.json",
                "tmp/wf87-v2-readiness-rollup.json",
                "tmp/wf87-autonomy-command-center.json",
                "scripts/alpaca_paper_order_history_classifier.py",
                "scripts/test_alpaca_paper_order_history_classifier.py",
                "scripts/wf86_daily_shadow_reconciliation_cron_runner.py",
                "scripts/test_wf86_daily_shadow_reconciliation_cron_runner.py",
                "scripts/wf86_assisted_order_card_builder.py",
                "scripts/test_wf86_assisted_order_card_builder.py",
                "scripts/wf86_shadow_eligibility_validator.py",
                "scripts/test_wf86_shadow_eligibility_validator.py",
                "scripts/wf87_market_hours_gate_probe.py",
                "scripts/test_wf87_market_hours_gate_probe.py",
                "scripts/wf87_autonomy_command_center.py",
                "scripts/test_wf87_autonomy_command_center.py",
                "scripts/test_wf86_shadow_decision_ledger.py",
            ],
            [
                "python scripts\\workflow_router.py WF86 --answer all --write-capsules --validate",
                "python scripts\\wf86_shadow_eligibility_validator.py --write --validate",
                "python scripts\\wf86_assisted_order_card_builder.py --write --validate",
                "python scripts\\wf86_shadow_decision_ledger.py --write --validate",
                "python scripts\\test_wf86_assisted_order_card_builder.py",
                "python scripts\\test_wf86_shadow_eligibility_validator.py",
                "python scripts\\test_wf86_shadow_decision_ledger.py",
                "python scripts\\wf86_autotrader_readiness_packet.py --write --validate",
                "python scripts\\alpaca_paper_order_history_classifier.py --write --validate",
                "python scripts\\wf86_daily_shadow_reconciliation_cron_runner.py --write --write-md --validate",
                "python scripts\\wf87_assisted_paper_cadence.py --write --validate",
                "python scripts\\wf87_shadow_outcome_scorecard.py --write --validate",
                "python scripts\\wf87_market_hours_gate_probe.py --write --validate",
                "python scripts\\wf87_v2_readiness_rollup.py --write --validate",
                "python scripts\\wf87_autonomy_command_center.py --write --write-md --validate",
                "python scripts\\test_wf87_market_hours_gate_probe.py",
                "python scripts\\test_wf87_autonomy_command_center.py",
                "python scripts\\test_alpaca_paper_order_history_classifier.py",
                "python scripts\\test_wf86_daily_shadow_reconciliation_cron_runner.py",
                "python scripts\\concurrent_lane_manager.py --status --write --validate",
            ],
            [
                "Phase B assisted maturity is not met: 0/5 clean assisted filled round trips",
                "Fresh short-lived kill switch, audit, WF67 guard, and reconciliation proof must be clean at execution time",
            ],
            [
                "Paper-only design. No live endpoint/credentials, live order, account "
                "action, money movement, portfolio/canon/cash/risk-rule mutation, "
                "cron-direct execution, Telegram approve-to-execute, owner approval "
                "inference, or autonomous paper submit/cancel/sell until a separate "
                "scoped pilot gate clears.",
            ],
            "paper-only future autonomy design; current state grants no autonomous paper/live execution authority",
            True,
            True,
            None,
        ),
        route(
            "WF87",
            "WF87 - Paper Autonomy Runtime Governor",
            "P0",
            "Narrowed paper-autonomy runtime governor under WF88. It consumes "
            "WF85 candidates and WF67 guard proof, checks execution-time TTL, "
            "kill switch, circuit breakers, sizing, quote/band/stop freshness, "
            "intraday monitor, and reconciliation proof, then explains whether "
            "a paper-autonomy action can be considered. It no longer owns broad "
            "OS learning, cleanup, coding outcomes, behavior portability, or dashboards.",
            "Use the runtime-governor packet as WF87's front door. Current proof "
            "shows shadow threshold met (21/20 decisions, 7/5 sessions), "
            "reconciliation maturity true, and 22 scoreable shadow outcomes. "
            "Phase C autonomous paper buy remains false because execution-time "
            "TTL/intraday/circuit-breaker proof is fail-closed, Phase B has "
            "0/5 required clean assisted filled round trips, and no exact "
            "owner-approved paper action exists. Feed outcomes to WF88; do not "
            "infer execution approval.",
            f"{CONTINUITY}/Veritas OS V2 - Trade-Grade Autonomous OS Upgrade Plan.md",
            "tmp/wf87-paper-autonomy-runtime-governor.json",
            [
                "tmp/wf87-paper-autonomy-runtime-governor.md",
                "tmp/wf87-v2-readiness-rollup.json",
                "tmp/wf87-runtime-gate-explanation.json",
                "tmp/wf87-position-sizing-runtime-check.json",
                "tmp/wf87-portfolio-circuit-breakers.json",
                "tmp/wf87-approval-freshness-ttl.json",
                "tmp/wf87-intraday-monitor.json",
                "tmp/wf87-assisted-paper-cadence.json",
                "tmp/wf87-shadow-outcome-scorecard.json",
                "tmp/wf87-market-hours-gate-probe.json",
                "tmp/wf87-autonomy-command-center.json",
                "tmp/paper-autotrader/trade-decision-journal.jsonl",
                "tmp/paper-autotrader/shadow-decisions.json",
                "tmp/paper-autotrader/autotrader-readiness.json",
                "tmp/paper-autotrader/guard-readiness.json",
                "tmp/paper-autotrader/assisted-order-cards.json",
                "tmp/autonomous-routing-deployment-cards.json",
                "tmp/autonomous-card-authority-audit.json",
                "tmp/wf85-decision-os-review-packet.json",
                "tmp/alpaca-paper-readiness/paper-execution-guard-validation.json",
                "tmp/alpaca-paper-readiness/paper-order-reconciliation.vrt-wf86-assisted-approved.json",
                "tmp/alpaca-paper-readiness/paper-order-history-classifier.json",
                "scripts/wf87_paper_autonomy_runtime_governor.py",
                "scripts/test_wf87_paper_autonomy_runtime_governor.py",
                "scripts/wf87_trade_decision_journal.py",
                "scripts/test_wf87_trade_decision_journal.py",
                "scripts/wf87_position_sizing_runtime_check.py",
                "scripts/test_wf87_position_sizing_runtime_check.py",
                "scripts/wf87_portfolio_circuit_breakers.py",
                "scripts/test_wf87_portfolio_circuit_breakers.py",
                "scripts/wf87_approval_freshness_ttl.py",
                "scripts/test_wf87_approval_freshness_ttl.py",
                "scripts/wf87_intraday_monitor.py",
                "scripts/test_wf87_intraday_monitor.py",
                "scripts/wf87_assisted_paper_cadence.py",
                "scripts/test_wf87_assisted_paper_cadence.py",
                "scripts/wf87_shadow_outcome_scorecard.py",
                "scripts/test_wf87_shadow_outcome_scorecard.py",
                "scripts/wf87_market_hours_gate_probe.py",
                "scripts/test_wf87_market_hours_gate_probe.py",
                "scripts/wf87_autonomy_command_center.py",
                "scripts/test_wf87_autonomy_command_center.py",
                "scripts/wf87_runtime_gate_explanation.py",
                "scripts/test_wf87_runtime_gate_explanation.py",
                "scripts/autonomous_routing_deployment_cards.py",
                "scripts/test_autonomous_routing_deployment_cards.py",
                "scripts/autonomous_card_authority_audit.py",
                "scripts/test_autonomous_card_authority_audit.py",
                "scripts/wf87_v2_readiness_rollup.py",
                "scripts/test_wf87_v2_readiness_rollup.py",
            ],
            [
                "python scripts\\wf87_runtime_gate_explanation.py --write --write-md --validate",
                "python scripts\\wf87_paper_autonomy_runtime_governor.py --write --write-md --validate",
                "python scripts\\test_wf87_paper_autonomy_runtime_governor.py",
                "python scripts\\wf87_trade_decision_journal.py --write --validate",
                "python scripts\\wf87_position_sizing_runtime_check.py --write --validate",
                "python scripts\\wf87_portfolio_circuit_breakers.py --write --validate",
                "python scripts\\wf87_approval_freshness_ttl.py --write --validate",
                "python scripts\\wf87_intraday_monitor.py --write --validate",
                "python scripts\\wf87_assisted_paper_cadence.py --write --validate",
                "python scripts\\wf87_shadow_outcome_scorecard.py --write --validate",
                "python scripts\\wf87_market_hours_gate_probe.py --write --validate",
                "python scripts\\autonomous_routing_deployment_cards.py --write --validate",
                "python scripts\\autonomous_card_authority_audit.py --write --validate",
                "python scripts\\wf87_autonomy_command_center.py --write --write-md --validate",
                "python scripts\\wf87_v2_readiness_rollup.py --write --validate",
                "python scripts\\workflow_router.py WF87 --answer all --write-capsules --validate",
                "python scripts\\workflow_routing_index.py --write --write-db --validate",
                "python scripts\\changed_file_validator_router.py --write --validate",
            ],
            [
                "Execution-time proof is fail-closed: approval/TTL freshness, intraday monitor, and portfolio circuit breakers are not clean",
                "Phase B assisted paper maturity threshold is not met: 0/5 clean assisted filled round trips",
                "No exact owner-approved paper action exists",
                "Phase C autonomous paper buy remains a separate owner approval event, not automatic promotion",
            ],
            [
                "Runtime proof and owner-review preparation only. No paper/live submit, "
                "cancel, sell, brokerage/account action, money movement, portfolio/"
                "canon/cash/sizing/risk mutation, cron-direct execution, delete/"
                "archive/apply, owner approval inference, paper-to-live promotion, "
                "or autonomous paper action until separate scoped gates and exact "
                "owner approval clear.",
            ],
            "review-only paper-autonomy runtime governor and evidence harness; consumes WF85 candidates and WF67 guard proof, explains runtime eligibility, exports outcome signals to WF88, and never infers execution approval",
            True,
            True,
            "python scripts\\workflow_router.py WF87 --answer all",
            effective_status_override="runtime_governor_fail_closed_maturity_improved",
        ),
        route(
            "WF88",
            "WF88 - Veritas OS 2.0 Learning, Cleanup, and Unified Routing",
            "P1",
            "First implementation slice for the broader measured Veritas OS. It "
            "connects finance-call intake, WF55/WF87 outcome measurement, WF67 "
            "paper-guardrail status, WF78 ticker routing, WF85 decision packets, "
            "OTEL/WF74/PM improvement "
            "routing, coding-app outcomes, behavior portability, retired-surface "
            "cleanup proposals, database-script duplication audit/thinning, "
            "script-routing contraction, WF88 wiki/decision compilation, retrieval "
            "quality evaluation, matched frontier-capability evaluation, RSI later-outcome "
            "scoring, isolated advanced-capability pilot contracts, token/API efficiency "
            "scoring, implementation token closeout attribution, self-prompting, "
            "self-evals, and WF87 runtime governor signals into "
            "one review-only control layer.",
            "Use tmp/wf88-os2-control-packet.json as the thin OS 2.0 control "
            "surface, tmp/wf88-source-open-residue-classifier.json to keep "
            "legacy/source-open residue out of default runtime blockers, and "
            "tmp/wf88-delete-readiness-packet.json plus "
            "tmp/wf88-deletion-approval-prep-packet.json for owner-gated "
            "cleanup approval readiness. Use tmp/wf88-wiki-synthesis-packet.json "
            "and wiki/ as the durable second-brain synthesis layer that turns "
            "OTEL, WF74, RSI, scorecards/evals, and recommendation packets into "
            "visible next actions without apply authority. Use the deterministic "
            "decision compiler and retrieval compatibility scorecard as source-first contract surfaces; "
            "use tmp/retrieval-live-eval.json for live provider-discrimination evidence, "
            "with human gold review and separate abstention calibration required before any threshold or promotion claim. Use "
            "the blinded frontier spine only after independently attested matched results exist, "
            "the RSI outcome scorecard for later-outcome durability evidence, and the "
            "advanced pilot packet only as isolated fixture/API-contract readiness. Use "
            "tmp/token-efficiency-scorecard.json and "
            "tmp/implementation-token-attribution-bridge.json as the metadata-only "
            "token/API optimization layer: it ranks changed-only/prompt-compression "
            "candidates, documents the closeout token stamp command path, and exposes implementation attribution gaps without changing "
            "cron schedules, runtime config, model weights, or raw content capture. A daily review-only "
            "WF88 wiki synthesis cron contract keeps that layer fresh. WF88 owns finance-call intake, outcome grading, "
            "experiment registry, cleanup/route contraction, database-facing "
            "script duplication audits, coding/behavior portability, and "
            "cross-workflow learning. WF67 stays the only paper execution guardrail, "
            "WF74 stays the proposal-only improvement router, and WF88 only surfaces "
            "their state as review-only action rows. The existing Skill Workshop body guard is the canonical anti-duplication gate for skill apply safety. WF87 is narrowed "
            "underneath WF88 as the paper-autonomy runtime governor. Deletion, "
            "archive, additional cron mutation, and apply still require separate exact "
            "owner approval.",
            f"{CONTINUITY}/Workflow 88 - Veritas OS 2.0.md",
            "tmp/wf88-os2-control-packet.json",
            [
                "tmp/wf88-os2-control-packet.md",
                "tmp/wf88-wiki-synthesis-packet.json",
                "tmp/wf88-wiki-synthesis-packet.md",
                "tmp/skill-workshop-body-guard.json",
                "wiki/README.md",
                "wiki/index.md",
                "wiki/os2/OTEL To Proposal Route.md",
                "wiki/scorecards-and-evals/Current Map.md",
                "wiki/scorecards-and-evals/Token Efficiency Map.md",
                "wiki/scorecards-and-evals/Frontier Capability Eval.md",
                "wiki/scorecards-and-evals/Advanced Capability Pilots.md",
                "wiki/decisions/Decision Compiler.md",
                "wiki/self-improvement/RSI Control Loop.md",
                "wiki/recommendations/Action Promotion Map.md",
                "wiki/gaps/Open Follow Up Debt.md",
                "wiki/source-map/WF88 Wiki Source Map.md",
                "tmp/token-usage-ledger-current.json",
                "tmp/token-budget-status.json",
                "tmp/token-efficiency-scorecard.json",
                "tmp/token-efficiency-scorecard.md",
                "tmp/implementation-token-attribution-bridge.json",
                "tmp/implementation-token-attribution-bridge.md",
                "tmp/frontier-capability-eval-spine.json",
                "tmp/frontier-capability-eval-spine.md",
                "tmp/retrieval-quality-scorecard.json",
                "tmp/retrieval-quality-scorecard.md",
                "tmp/retrieval-live-eval.json",
                "tmp/retrieval-live-eval.md",
                "data/state-history/retrieval-live-eval.jsonl",
                "tmp/wf88-decision-compiler.json",
                "tmp/wf88-decision-compiler.md",
                "tmp/rsi-outcome-scorecard.json",
                "tmp/rsi-outcome-scorecard.md",
                "tmp/advanced-capability-pilot-packet.json",
                "tmp/advanced-capability-pilot-packet.md",
                "tmp/wf88-route-contraction-packet.json",
                "tmp/wf88-route-contraction-packet.md",
                "tmp/wf88-source-open-residue-classifier.json",
                "tmp/wf88-source-open-residue-classifier.md",
                "tmp/wf88-delete-readiness-packet.json",
                "tmp/wf88-delete-readiness-packet.md",
                "tmp/wf88-deletion-approval-prep-packet.json",
                "state/cron-contracts/runtime-wf88-wiki-synthesis-refresh.json",
                "tmp/wf88-cron-retired-job-inventory.json",
                "tmp/wf88-cron-retired-job-inventory.md",
                "tmp/wf88-cron-disabled-job-reference-review.json",
                "tmp/wf88-cron-disabled-job-reference-review.md",
                "tmp/wf88-disabled-cron-delete-apply-report.json",
                "tmp/recommendation-outcome-ledger-current.json",
                "tmp/wf87-paper-autonomy-runtime-governor.json",
                "tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json",
                "tmp/wf88-retired-surface-cleanup-plan.json",
                "tmp/wf88-retired-surface-cleanup-plan.md",
                "04. Research/Call Log.md",
                "tmp/finance-decision-performance-digest.json",
                "tmp/wf55-autonomy-outcome-ledger.json",
                "tmp/wf87-shadow-outcome-scorecard.json",
                "tmp/wf78-auto-tier-routing.json",
                "tmp/wf78-clean-tier-roster.json",
                "tmp/wf85-decision-os-review-packet.json",
                "tmp/otel-ops-control.json",
                "tmp/otel-ops-window-summary.json",
                "tmp/improvement-ledger-current.json",
                "tmp/wf74-decision-docket.json",
                "tmp/wf74-autonomy-work-router.json",
                "tmp/pm-control-packet.json",
                "tmp/cron-control-packet.json",
                "tmp/wf88-route-contraction-packet.json",
                "tmp/coding-outcome-ledger-current.json",
                "data/state-history/coding-outcome-ledger.jsonl",
                "tmp/tmp-lifecycle-guard.json",
                "tmp/human-canon-thinning-retirement-inventory.json",
                "tmp/db-lifecycle-manifest.json",
                "tmp/wf88-db-script-duplication-audit.json",
                "tmp/wf88-db-script-duplication-audit.md",
                "tmp/wf88-script-cleanup-inventory.json",
                "tmp/wf88-script-cleanup-inventory.md",
                "tmp/wf88-typed-script-reference-graph.json",
                "tmp/wf88-typed-script-reference-graph.md",
                "08. Audits/WF88 Retired Surface Deletion and Script Routing Cleanup Audit - 2026-06-26.md",
                "08. Audits/WF88 Veritas OS 2.0 Workspace State Audit - 2026-06-27.md",
                "scripts/db_lifecycle_manifest.py",
                "scripts/wf88_db_duplicate_source_delete_packet.py",
                "scripts/test_wf88_db_duplicate_source_delete_packet.py",
                "scripts/wf88_wiki_synthesis_packet.py",
                "scripts/test_wf88_wiki_synthesis_packet.py",
                "scripts/token_efficiency_scorecard.py",
                "scripts/test_token_efficiency_scorecard.py",
                "scripts/implementation_token_attribution_bridge.py",
                "scripts/test_implementation_token_attribution_bridge.py",
                "scripts/frontier_capability_eval_spine.py",
                "scripts/test_frontier_capability_eval_spine.py",
                "scripts/retrieval_quality_scorecard.py",
                "scripts/test_retrieval_quality_scorecard.py",
                "scripts/retrieval_live_eval.py",
                "scripts/test_retrieval_live_eval.py",
                "scripts/wf88_decision_compiler.py",
                "scripts/test_wf88_decision_compiler.py",
                "scripts/rsi_outcome_scorecard.py",
                "scripts/test_rsi_outcome_scorecard.py",
                "scripts/advanced_capability_pilot_packet.py",
                "scripts/test_advanced_capability_pilot_packet.py",
                "data/evals/frontier-capability-eval-fixtures.json",
                "data/evals/wf88-retrieval-fixtures.json",
                "data/evals/retrieval-live-source-registry.json",
                "data/evals/retrieval-live-gold.json",
                "data/evals/rsi-outcome-scorecard-fixtures.json",
                "data/evals/advanced-capability-pilot-fixtures.json",
                "scripts/wf88_os2_control_packet.py",
                "scripts/test_wf88_os2_control_packet.py",
                "scripts/skill_workshop_body_guard.py",
                "scripts/test_skill_workshop_body_guard.py",
                "scripts/wf88_route_contraction_packet.py",
                "scripts/test_wf88_route_contraction_packet.py",
                "scripts/wf88_source_open_residue_classifier.py",
                "scripts/test_wf88_source_open_residue_classifier.py",
                "scripts/wf88_delete_readiness_packet.py",
                "scripts/test_wf88_delete_readiness_packet.py",
                "scripts/wf88_deletion_approval_prep_packet.py",
                "scripts/test_wf88_deletion_approval_prep_packet.py",
                "scripts/wf88_cron_retired_job_inventory.py",
                "scripts/test_wf88_cron_retired_job_inventory.py",
                "scripts/wf88_cron_disabled_job_reference_review.py",
                "scripts/test_wf88_cron_disabled_job_reference_review.py",
                "scripts/wf88_cleanup_common.py",
                "scripts/test_wf88_cleanup_common.py",
                "scripts/test_db_lifecycle_manifest.py",
                "scripts/wf88_retired_surface_cleanup_plan.py",
                "scripts/test_wf88_retired_surface_cleanup_plan.py",
                "scripts/wf88_script_cleanup_inventory.py",
                "scripts/test_wf88_script_cleanup_inventory.py",
                "scripts/wf88_typed_script_reference_graph.py",
                "scripts/test_wf88_typed_script_reference_graph.py",
                "training/",
            ],
            [
                "python scripts\\db_lifecycle_manifest.py --write --validate",
                "python scripts\\wf88_script_cleanup_inventory.py --write --write-md --validate",
                "python scripts\\wf88_typed_script_reference_graph.py --write --write-md --validate",
                "python scripts\\wf87_paper_autonomy_runtime_governor.py --write --write-md --validate",
                "python scripts\\wf67_autonomous_paper_manager.py --write --validate",
                "python scripts\\wf88_retired_surface_cleanup_plan.py --write --write-md --validate",
                "python scripts\\wf88_route_contraction_packet.py --write --write-md --validate",
                "python scripts\\wf88_source_open_residue_classifier.py --write --write-md --validate",
                "python scripts\\wf88_cron_retired_job_inventory.py --write --write-md --validate",
                "python scripts\\wf88_cron_disabled_job_reference_review.py --write --write-md --validate",
                "python scripts\\wf88_delete_readiness_packet.py --write --write-md --validate",
                "python scripts\\wf88_deletion_approval_prep_packet.py --write --validate",
                "python scripts\\token_usage_ledger.py --write --write-md --validate",
                "python scripts\\token_budget_status.py --write --validate",
                "python scripts\\token_efficiency_scorecard.py --write --write-md --validate",
                "python scripts\\implementation_token_attribution_bridge.py --write --write-md --validate",
                "python scripts\\frontier_capability_eval_spine.py --write --write-md --validate",
                "python scripts\\retrieval_quality_scorecard.py --write --write-md --validate",
                "python scripts\\retrieval_live_eval.py --write --write-md --validate",
                "python scripts\\wf88_decision_compiler.py --write --write-md --validate",
                "python scripts\\rsi_outcome_scorecard.py --write --write-md --validate",
                "python scripts\\advanced_capability_pilot_packet.py --write --write-md --validate",
                "python scripts\\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate",
                "python scripts\\skill_workshop_body_guard.py --write --validate",
                "python scripts\\test_skill_workshop_body_guard.py",
                "python scripts\\wf88_os2_control_packet.py --write --write-md --validate",
                "python scripts\\wf88_route_contraction_packet.py --write --write-md --validate",
                "python -m pytest scripts\\test_wf88_cleanup_common.py scripts\\test_db_lifecycle_manifest.py scripts\\test_wf88_typed_script_reference_graph.py scripts\\test_wf88_cron_retired_job_inventory.py scripts\\test_wf88_cron_disabled_job_reference_review.py scripts\\test_wf88_delete_readiness_packet.py scripts\\test_wf88_deletion_approval_prep_packet.py",
                "python scripts\\test_wf87_paper_autonomy_runtime_governor.py",
                "python scripts\\test_wf88_route_contraction_packet.py",
                "python scripts\\test_wf88_source_open_residue_classifier.py",
                "python scripts\\test_wf88_delete_readiness_packet.py",
                "python scripts\\test_wf88_disabled_cron_delete_microbatch_apply.py",
                "python scripts\\test_wf88_wiki_synthesis_packet.py",
                "python scripts\\test_token_efficiency_scorecard.py",
                "python scripts\\test_implementation_token_attribution_bridge.py",
                "python scripts\\test_frontier_capability_eval_spine.py",
                "python scripts\\test_retrieval_quality_scorecard.py",
                "python scripts\\test_retrieval_live_eval.py",
                "python scripts\\test_wf88_decision_compiler.py",
                "python scripts\\test_rsi_outcome_scorecard.py",
                "python scripts\\test_advanced_capability_pilot_packet.py",
                "python scripts\\test_wf88_os2_control_packet.py",
                "python scripts\\test_wf88_script_cleanup_inventory.py",
                "python scripts\\test_wf88_typed_script_reference_graph.py",
                "python scripts\\test_wf88_db_duplicate_source_delete_packet.py",
                "python scripts\\finance_decision_performance_digest.py --write --write-md --validate",
                "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
                "python scripts\\wf74_decision_docket.py --write --write-md --validate",
                "python scripts\\wf74_learning_loop_eval_harness.py --write --validate",
                "python scripts\\wf74_rsi.py --outcome-eval-v2",
                "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
                "python scripts\\wf78_intelligence_routing_v2.py --layer daily_core_v2 --fail-on-budget-exceeded --write --validate",
                "python scripts\\wf85_decision_os_review_packet.py --write --write-md --validate",
                "python scripts\\coding_outcome_ledger.py --write --validate",
                "python scripts\\workflow_router.py WF88 --answer all --write-capsules --validate",
            ],
            [],  # LOOP-REPAIR-20260912: actionable blockers are computed at build time
            [
                "Review-only learning/productization, wiki synthesis, and cleanup planning. No base-model self-modification, raw prompt/tool capture, model-training claim, delete/move/archive, capital deployment, paper/live/brokerage/account action, portfolio/canon/cash/sizing/risk mutation, cron schedule/config/runtime mutation, customer/external output, or owner approval inference.",
            ],
            "review-only OS learning, productization, wiki synthesis, and cleanup-planning workflow; no delete/archive/apply authority, finance execution, model training authority, autonomous self-modification, cron schedule mutation, portfolio/canon mutation, or customer/external output",
            True,
            True,
            "python scripts\\workflow_router.py WF88 --answer all",
            effective_status_override="v7_frontier_eval_decision_compiler_rsi_outcomes_fixture_ready_no_apply",
        ),
        route(
            "WF67",
            "Alpaca Paper Execution Guardrail",
            "P1",
            "Paper-only guardrail active under the WF88/WF87 paper-autonomy spine; "
            "paper sandbox is separate from the real planning portfolio, and the "
            "manager packet exports ready/blocked/repair state to WF88 without "
            "granting approval.",
            "Refresh gate and manager only to prepare or inspect exact paper-action "
            "cards. Feed ready/blocked/repair status to WF88/WF87; execute only "
            "after fresh kill switch, guards, redacted audit, notification, and "
            "Randall exact approval.",
            f"{CONTINUITY}/Workflow 67 - Alpaca Paper Execution Guardrail.md",
            "scripts/wf67_autonomous_paper_manager.py",
            [
                "tmp/wf67-paper-position-state.sqlite",
                "tmp/alpaca-paper-readiness/wf67-autonomous-paper-manager-current.json",
                "tmp/wf87-paper-autonomy-runtime-governor.json",
                "tmp/wf88-os2-control-packet.json",
            ],
            [
                "python scripts\\chief_intelligence_promotion_gate.py --write --validate",
                "python scripts\\wf67_autonomous_paper_manager.py --write --validate",
                "python scripts\\wf88_os2_control_packet.py --write --write-md --validate",
                "python scripts\\wf88_route_contraction_packet.py --write --write-md --validate",
            ],
            [
                "Execution requires fresh kill switch + guards + redacted audit + notification + exact approval",
                "WF88/WF87 may consume WF67 state only as review-only guard proof",
            ],
            [
                "No live endpoint/credentials, money movement/account settings, "
                "close/liquidation endpoints, inferred approval, autonomous paper orders, "
                "refresh-triggered submit/cancel/sell, or paper-to-live promotion.",
            ],
            "paper-only simulation; exact owner approval required to execute; WF88/WF87 consume status only",
            True,
            False,
            None,
        ),
        route(
            "WF64-WF56",
            "Portfolio/Canon Maintenance",
            "P1",
            "Proposal/semantic preview/gated apply architecture active; scoped "
            "routine entry-band maintenance is system-owned inside its gate, "
            "while broader applies remain exact-gated.",
            "Keep validators clean; use scoped band maintenance for eligible "
            "entry-band/stop refresh and exact standing/scoped approval artifacts "
            "for broader categories.",
            f"{CONTINUITY}/Workflow 64 - Bounded Portfolio Agent Cron Architecture.md",
            None,
            [f"{CONTINUITY}/Workflow 56 - Portfolio Mutation Proposal Object and Gated Apply Helper.md"],
            ["python scripts\\test_portfolio_mutation_validators.py"],
            ["Broader applies remain exact-gated"],
            [
                "No trade/account/brokerage/money movement; no cron direct apply "
                "outside approved scoped band/reference paths; no cash/risk-rule/"
                "execution-entitlement mutation unless separately scoped; no "
                "clean-validation-equals-approval.",
            ],
            "scoped entry-band maintenance allowed; broader proposal/preview/gated-apply only",
            True,
            False,
            None,
        ),
        route(
            "WF71",
            "Department Staff / Skill Ownership",
            "P1",
            "Elevated P1 autonomy helper factory: skill-routing/load-budget "
            "procedure active; PM handoffs embed helper contracts.",
            "Use the autonomy spine promotion contract plus helper contract, "
            "spawn packets, active manifest, and completion handshake around "
            "helper work.",
            f"{CONTINUITY}/Workflow 71 - Veritas OS Department Staff and Skill Ownership Model.md",
            "tmp/autonomy-spine-promotion-contract.json",
            ["tmp/autonomy-spine-readiness-rollup.json", "tmp/concurrent-lane-register.json"],
            [
                "python scripts\\autonomy_spine_promotion_contract.py --write --validate",
                "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
                "openclaw skills check",
            ],
            [],
            [
                "No separate autonomous identity, duplicate canon source, authority collision, "
                "heartbeat helper spawning, or trading/account/portfolio authority.",
            ],
            "orchestration-only; no autonomous identity/authority",
            False,
            True,
            None,
        ),
        route(
            "WF74",
            "Recursive Self-Improvement",
            "P1",
            "P0-adjacent learning spine connected into WF88: V1 monitor-and-use "
            "complete; validation harness and boundary lint exist; consumes WF55/"
            "WF87 measurement telemetry, OTEL friction, and WF88 action rows for "
            "proposal-only improvements.",
            "Use the WF74 improvement-opportunity queue, decision docket, work router, "
            "improvement ledger, and OTEL control/window summary as the live owner proof; "
            "convert repeated failures and measured lessons into "
            "WF88-visible proposal, PM, Skill Workshop, validator, owner-packet, "
            "or monitor-only rows; use the draft live retrieval evaluator for "
            "discriminating provider evidence, not the compatibility scorecard, and do not expand authority.",
            f"{CONTINUITY}/Workflow 74 - Veritas Recursive Self-Improvement Loop.md",
            "tmp/wf74-improvement-opportunity-queue.json",
            [
                "tmp/wf74-decision-docket.json",
                "tmp/wf74-autonomy-work-router.json",
                "tmp/improvement-ledger-current.json",
                "tmp/otel-ops-control.json",
                "tmp/otel-ops-window-summary.json",
                "tmp/wf55-autonomy-outcome-ledger.json",
                "tmp/retrieval-live-eval.json",
                "data/state-history/retrieval-live-eval.jsonl",
                "tmp/wf88-os2-control-packet.json",
                "tmp/wf88-wiki-synthesis-packet.json",
            ],
            [
                "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
                "python scripts\\wf74_improvement_opportunity_queue.py --write --validate",
                "python scripts\\wf74_autonomy_work_router.py --write --validate",
                "python scripts\\wf74_decision_docket.py --write --write-md --validate",
                "python scripts\\wf74_learning_loop_eval_harness.py --write --validate",
                "python scripts\\retrieval_live_eval.py --write --write-md --validate",
                "python scripts\\test_retrieval_live_eval.py",
                "python scripts\\wf74_rsi.py --outcome-eval-v2",
                "python scripts\\otel_ops_control.py --write --write-db --multi-window --validate",
                "python scripts\\wf74_rsi.py --validate-only",
            ],
            [],
            [
                "No base-model self-modification, self-preservation/replication, autonomous "
                "authority expansion, second memory tree, owner-approval inference, "
                "portfolio/trade/account/paper/live authority, or RSI theater.",
            ],
            "review-only proposal and routing loop under WF88; no self-modification/authority expansion",
            False,
            True,
            None,
        ),
        route(
            "WF76",
            "Cron Authority / Canon Auto-Update",
            "P1",
            "P0-adjacent cadence spine; scheduled/review-only cron awareness "
            "flows through freshness spine -> scorecard -> escalation. "
            "Autonomy-spine measurement and readiness contracts are now "
            "tracked by cron freshness.",
            "Verify selectivity with cron_freshness_spine.py, "
            "workflow_advancement_scorecard.py, cron_signal_scorecard.py, and "
            "escalation_trigger.py; archive moves only after owner approval/proof.",
            f"{CONTINUITY}/Workflow 76 - Cron Automation Authority and Canon Auto-Update Expansion.md",
            "scripts/cron_freshness_spine.py",
            [
                "tmp/cron-freshness-spine.json",
                "tmp/autonomy-spine-readiness-rollup.json",
                "tmp/wf55-autonomy-outcome-ledger.json",
            ],
            [
                "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
                "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
                "python scripts\\cron_freshness_spine.py --write --validate",
            ],
            [],
            [
                "No cron-direct portfolio/canon apply; no deletes; no "
                "config/auth/channel/service/runtime mutation, owner approval inference, or "
                "heartbeat inline execution.",
            ],
            "scheduled review-only; cron may propose, main applies bounded sync",
            True,
            True,
            "python scripts\\cron_freshness_spine.py --write --validate",
        ),
        route(
            "WF69",
            "Intelligence / Probability Stack V2",
            "P1",
            "Control-plane/data-contract revamp active; probability claims "
            "blocked.",
            "Use SQL truth spine as proof/index substrate only; validate "
            "bundles without predictive claims.",
            f"{CONTINUITY}/Workflow 69 - Intelligence Probability Predictive Stack V2 Revamp.md",
            None,
            [],
            ["python scripts\\wf_v2_intelligence_stack_validator.py --write"],
            ["Probability/win-rate claims blocked while WF55 not ready"],
            [
                "No probability/win-rate/expected-return/model-readiness claims while WF55 is "
                "not ready; no live/paper/account authority.",
            ],
            "review-only; no predictive claims",
            True,
            True,
            None,
        ),
        route(
            "WF80",
            "Multi-Product Scaleout Control Plane",
            "P3",
            "Product-portfolio operating layer is intentionally on hold as the "
            "ultimate goal while near-term effort focuses on efficiency, routing, "
            "evidence quality, and command-center leverage.",
            "Do not advance product registry/build work unless Randall resumes "
            "WF80-WF83. Near-term priority routes through WF84/WF85 finance "
            "decision unification, WF78 evidence repair, WF73/WF72 support-route "
            "efficiency, and WF79 command visibility.",
            f"{CONTINUITY}/Workflow 80 - Multi-Product Scaleout Control Plane.md",
            f"{CONTINUITY}/Workflow 80 - Multi-Product Scaleout Control Plane.md",
            [
                f"{CONTINUITY}/Workflow 81 - AI and Technology Opportunity Intelligence Product Line.md",
                f"{CONTINUITY}/Workflow 82 - Learning and Teaching Product Line.md",
                f"{CONTINUITY}/Workflow 83 - Product Packaging and Launch Readiness Factory.md",
            ],
            ["python scripts\\workflow_routing_index.py --write --validate"],
            [
                "Owner paused WF80-WF83 on 2026-06-06",
                "Product registry/validator not built yet",
                "Customer/public launch remains blocked",
            ],
            [
                "Report-only product scaleout; no customer/public output, spend, external action, "
                "account/customer-data import, legal/compliance claim, finance execution authority, "
                "or owner-approval inference.",
            ],
            "review-only product portfolio control plane",
            False,
            True,
            "python scripts\\workflow_routing_index.py --route WF80",
        ),
        route(
            "WF81",
            "AI and Technology Opportunity Intelligence Product Line",
            "P3",
            "Product/opportunity intelligence lane is intentionally on hold under "
            "the WF80-WF83 pause.",
            "Do not build opportunity-intake artifacts unless Randall resumes "
            "WF80-WF83. Use general research only for direct questions.",
            f"{CONTINUITY}/Workflow 81 - AI and Technology Opportunity Intelligence Product Line.md",
            f"{CONTINUITY}/Workflow 81 - AI and Technology Opportunity Intelligence Product Line.md",
            [f"{CONTINUITY}/Workflow 80 - Multi-Product Scaleout Control Plane.md"],
            ["python scripts\\workflow_routing_index.py --write --validate"],
            ["Owner paused WF80-WF83 on 2026-06-06", "Opportunity schema and candidate queue not built yet"],
            [
                "No external action, spend, account creation, outreach, customer claim, "
                "compliance/security claim, or public launch without separate approval.",
            ],
            "review-only opportunity/product intelligence",
            False,
            True,
            "python scripts\\workflow_routing_index.py --route WF81",
        ),
        route(
            "WF82",
            "Learning and Teaching Product Line",
            "P3",
            "Learning/teaching product lane is intentionally on hold under the "
            "WF80-WF83 pause.",
            "Do not build learning-product inventory unless Randall resumes "
            "WF80-WF83. Keep internal training assets available for current "
            "workflow efficiency only.",
            f"{CONTINUITY}/Workflow 82 - Learning and Teaching Product Line.md",
            f"{CONTINUITY}/Workflow 82 - Learning and Teaching Product Line.md",
            ["scripts/wf75_training_desk.py", f"{CONTINUITY}/Workflow 83 - Product Packaging and Launch Readiness Factory.md"],
            ["python scripts\\workflow_routing_index.py --write --validate"],
            [
                "Owner paused WF80-WF83 on 2026-06-06",
                "Learning-asset inventory and readiness validator not built yet",
            ],
            [
                "No customer/public training product, certification, legal/compliance claim, "
                "guaranteed outcome claim, or external publication without separate approval.",
            ],
            "internal-first learning product lane",
            False,
            True,
            "python scripts\\workflow_routing_index.py --route WF82",
        ),
        route(
            "WF83",
            "Product Packaging and Launch Readiness Factory",
            "P3",
            "Packaging/readiness factory is intentionally on hold under the "
            "WF80-WF83 pause.",
            "Do not build launch/readiness matrix unless Randall resumes "
            "WF80-WF83. Near-term readiness work should support internal "
            "efficiency/proof, not launch packaging.",
            f"{CONTINUITY}/Workflow 83 - Product Packaging and Launch Readiness Factory.md",
            f"{CONTINUITY}/Workflow 83 - Product Packaging and Launch Readiness Factory.md",
            [
                f"{CONTINUITY}/Workflow 80 - Multi-Product Scaleout Control Plane.md",
                "scripts/retail_automation_control_plane.py",
                "scripts/generic_intelligence_saas_pivot.py",
            ],
            ["python scripts\\workflow_routing_index.py --write --validate"],
            [
                "Owner paused WF80-WF83 on 2026-06-06",
                "Readiness matrix/no-go validator not built yet",
                "Customer/public launch remains blocked",
            ],
            [
                "No public launch, customer delivery, outbound action, spend, credential/account use, "
                "customer-data import, legal/compliance/security certification claim, finance advice/"
                "customer allocation, or owner approval inference.",
            ],
            "review-only packaging/readiness gate",
            False,
            True,
            "python scripts\\workflow_routing_index.py --route WF83",
        ),
        # ---- P4 closed / gated route-history rows ----
        route(
            "WF50",
            "Tmp Helper Archive Cleanup",
            "P4",
            "Closed cleanup workflow. Remaining archive/root cleanup is approval-gated and must not be revived as autonomous work.",
            "Use only as route history. Any move/delete/archive requires exact microbatch packet, references, hashes, rollback, validators, and Randall approval.",
            f"{CONTINUITY}/Workflow 50 - Tmp Helper Archive Cleanup.md",
            f"{CONTINUITY}/Workflow 50 - Tmp Helper Archive Cleanup.md",
            [],
            [],
            ["Archive/root cleanup remains approval-gated"],
            [
                "No delete, move, archive, protected-surface cleanup, config/runtime mutation, proof deletion, finance/canon mutation, or owner-approval inference from this route.",
            ],
            "review-only historical cleanup route; destructive action gated",
            True,
            False,
            "python scripts\\workflow_router.py WF50 --answer all",
        ),
        route(
            "WF51",
            "Daily Fresh Intelligence and Price Trend Promotion Branch",
            "P4",
            "Closed/superseded daily price-trend promotion branch; useful as history for source freshness and warning-only trend proof.",
            "Use newer WF78/WF84/WF85 finance routing for current ticker decisions; do not use WF51 for deployment claims.",
            f"{CONTINUITY}/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md",
            f"{CONTINUITY}/Workflow 51 - Daily Fresh Intelligence and Price Trend Promotion Branch.md",
            [],
            [],
            ["Production watchlist candidate generation remains deferred"],
            [
                "No capital deployment, promotion, paper/live/account action, probability claim, or portfolio/canon mutation from WF51 historical proof.",
            ],
            "review-only historical trend route; superseded by WF78/WF84/WF85",
            False,
            False,
            "python scripts\\workflow_router.py WF51 --answer all",
        ),
        route(
            "WF52",
            "Event Calendar Freshness Path",
            "P4",
            "Closed bounded Event Calendar freshness path; browser-runner verification is optional/future.",
            "Use active earnings/event workflows for current work; preserve WF52 as route history only.",
            f"{CONTINUITY}/Workflow 52 - Earnings Date Source Confidence and Event Calendar Roll-Forward Automation.md",
            f"{CONTINUITY}/Workflow 52 - Earnings Date Source Confidence and Event Calendar Roll-Forward Automation.md",
            [],
            [],
            ["Browser runner verification optional/future"],
            [
                "No deployment, portfolio/canon mutation, customer output, or event-date truth claim without current source validation.",
            ],
            "review-only historical event-calendar route",
            False,
            False,
            "python scripts\\workflow_router.py WF52 --answer all",
        ),
        route(
            "WF53",
            "Sector Expansion Coverage and Correlation Proof Layer",
            "P4",
            "Closed v1 sector/correlation proof layer; artifact quality can degrade when upstream warning surfaces degrade.",
            "Use active WF78/WF84/WF85 and macro/sector proof for current finance decisions.",
            f"{CONTINUITY}/Workflow 53 - Sector Expansion Coverage and Correlation Proof Layer.md",
            f"{CONTINUITY}/Workflow 53 - Sector Expansion Coverage and Correlation Proof Layer.md",
            [],
            [],
            ["Historical proof may be degraded by upstream warnings"],
            [
                "No sector allocation, sizing, deployment, paper/live/account action, or portfolio/canon mutation from WF53 proof alone.",
            ],
            "review-only historical sector/correlation route",
            False,
            False,
            "python scripts\\workflow_router.py WF53 --answer all",
        ),
        route(
            "WF54",
            "Ticker Monitoring Performance Analytics v1",
            "P4",
            "Closed review diagnostics; outcome analytics/calibration remain blocked until WF55 readiness.",
            "Use WF55 measurement substrate for outcome/probability gating; do not publish predictive claims from WF54.",
            f"{CONTINUITY}/Workflow 54 - Ticker Monitoring Performance Analytics v1.md",
            f"{CONTINUITY}/Workflow 54 - Ticker Monitoring Performance Analytics v1.md",
            ["tmp/wf55-autonomy-outcome-ledger.json"],
            [],
            ["Outcome analytics/calibration blocked until WF55 readiness"],
            [
                "No hit-rate, win-rate, expected-return, probability, model-ranked deployment, capital, paper/live/account action, or approval inference.",
            ],
            "review-only historical analytics route; predictive claims gated by WF55",
            False,
            False,
            "python scripts\\workflow_router.py WF54 --answer all",
        ),
        route(
            "WF57",
            "Composite Regime and Sector Positioning PDF Visual Enhancement",
            "P4",
            "Closed internal polished PDF product lane; retained as review-only packaging history.",
            "Use current WF75/WF85 deliverable packaging only for internal review unless a separate customer/public gate is approved.",
            f"{CONTINUITY}/Workflow 57 - Composite Regime and Sector Positioning PDF Visual Enhancement.md",
            f"{CONTINUITY}/Workflow 57 - Composite Regime and Sector Positioning PDF Visual Enhancement.md",
            [],
            [],
            ["Public/customer packaging remains gated"],
            [
                "No public/customer delivery, legal/compliance/readiness claim, portfolio/canon mutation, capital deployment, or execution authority.",
            ],
            "review-only historical packaging route",
            False,
            False,
            "python scripts\\workflow_router.py WF57 --answer all",
        ),
        route(
            "WF59",
            "Continuity and Compaction Hardening",
            "P4",
            "Closed continuity/compaction hardening that produced Startup Truth Index and startup-load reductions.",
            "Use Startup Truth Index and current boot/control surfaces for live routing; preserve WF59 as history only.",
            f"{CONTINUITY}/Workflow 59 - Continuity and Compaction Hardening.md",
            f"{CONTINUITY}/Workflow 59 - Continuity and Compaction Hardening.md",
            ["06. Playbooks/Startup Truth Index.md"],
            [],
            [],
            [
                "No doctrine rewrite, new boot authority surface, config/runtime mutation, or generated-index authority expansion from WF59 history.",
            ],
            "review-only historical continuity route",
            False,
            False,
            "python scripts\\workflow_router.py WF59 --answer all",
        ),
        # ---- P2 monitors ----
        route(
            "WF58",
            "Dashboard / Capital Packets Monitor",
            "P2",
            "Monitor: dashboard/capital packet validation + deployment-state "
            "contract proof.",
            "Escalate on validator warning/critical, false-green dashboard, "
            "packet-vs-canon conflict, or duplicated legacy deployment-state "
            "fields reappearing in presentation artifacts.",
            f"{CONTINUITY}/Deployment State Contract Migration.md",
            "scripts/deployment_contract_migration_validation_bundle.py",
            ["tmp/deployment-contract-agreement-validation.json"],
            ["python scripts\\deployment_contract_migration_validation_bundle.py --write"],
            [],
            [
                "No self-apply, trade/account authority, per-packet approval inference, or "
                "legacy/source-field deletion outside compatibility proof.",
            ],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF63",
            "Paper Readiness Monitor",
            "P2",
            "Monitor: paper readiness / no-submit guard.",
            "Escalate on readiness/no-submit guard warning/critical or live "
            "endpoint/credential exposure.",
            f"{CONTINUITY}/Workflow 63 - Alpaca Paper Trading Readiness.md",
            None,
            [],
            [],
            [],
            [
                "No live endpoint/credentials, money movement/account changes, or "
                "submit/cancel outside WF67.",
            ],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF60-WF61",
            "Research / Regime Monitor",
            "P2",
            "Monitor: macro judgment, research freshness, sector expansion.",
            "Escalate on freshness degradation, macro cue conflicting with "
            "canon, or feed implying action.",
            f"{CONTINUITY}/Workflow 60 - Research Freshness and Opportunity Cron Automation.md",
            None,
            [f"{CONTINUITY}/Workflow 61 - Small Mid Cap Regime Feed and Candidate Sleeve.md"],
            [],
            [],
            ["Review-only; no promotion/sizing/sleeve/cash/risk-rule/trade authority."],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF65",
            "Fundamentals Monitor",
            "P2",
            "Monitor: fundamental/IR/earnings bridge artifacts.",
            "Escalate on validator warning/critical, official source conflict, "
            "or stale probe.",
            f"{CONTINUITY}/Workflow 65 - Fundamental Metrics Tracker V1.md",
            None,
            [],
            [],
            [],
            ["Evidence only; no deployment/trade/portfolio authority."],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF62",
            "Canon Consolidation Monitor",
            "P2",
            "Monitor: canonical ownership validation.",
            "Escalate when a consumer points to retired canon or a dashboard "
            "outranks an owner note.",
            f"{CONTINUITY}/Workflow 62 - Finance Canon Consolidation and Consumer Migration.md",
            None,
            [],
            [],
            [],
            ["No ungated canon mutation or delete/archive without approval."],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF55",
            "Outcome Measurement / Probability Readiness",
            "P1",
            "Promoted to active autonomy measurement substrate; probability "
            "claims remain blocked while neutral outcome events and process-quality "
            "grades feed WF74.",
            "Keep WF55 active as a review-only scorecard through neutral measurement "
            "grades, stale-data/process-failure tracking, and WF74 model-quality proof; "
            "escalate if predictive language appears before semantic outcome gates clear.",
            f"{CONTINUITY}/Workflow 55 - Probability Readiness and Outcome Retention Gate.md",
            "tmp/wf55-autonomy-outcome-ledger.json",
            ["tmp/autonomy-spine-promotion-contract.json", "tmp/autonomy-spine-readiness-rollup.json"],
            [
                "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
                "python scripts\\test_wf55_autonomy_outcome_ledger.py",
                "python scripts\\model_quality_scorecard.py --write --write-md --validate",
                "python scripts\\autonomy_spine_readiness_rollup.py --write --validate",
            ],
            ["Predictive/probability claims not ready; WF55 measurement scorecard is active review-only"],
            [
                "No predictive scores, expected-return claims, win-rate claims, model-ranked "
                "deployment, paper/live execution, or approval inference. Durable v2 append "
                "is allowed only for review-only measurement rows under the 2026-06-19 owner approval.",
            ],
            "measurement-only; predictive claims gated",
            False,
            True,
            "python scripts\\wf55_autonomy_outcome_ledger.py --write --validate",
        ),
        route(
            "WF-CHIEF-GATE",
            "Chief / WF67 Manager Gate Monitor",
            "P2",
            "Monitor: Chief gate and WF67 manager/card artifacts.",
            "Escalate when a candidate/card lacks rank, band/stop proof, "
            "sector/monitor/paper context, WF55 caution, or manager readiness.",
            None,
            "scripts/chief_intelligence_promotion_gate.py",
            ["scripts/wf67_autonomous_paper_manager.py"],
            ["python scripts\\chief_intelligence_promotion_gate.py --write --validate"],
            [],
            [
                "Review/routing only; no watchlist apply, portfolio/canon mutation, paper/live "
                "execution, owner approval inference, probability/model authority, or money movement.",
            ],
            "monitor-only; review/routing",
            False,
            True,
            None,
        ),
        route(
            "WF-FINANCE-CHAINS",
            "Finance Chains Monitor",
            "P2",
            "Monitor: chain/run/current-window/digest artifacts + cron ledger.",
            "Escalate on missing/failed run, stale current-window index, "
            "validator warning/critical, or digest escalation.",
            None,
            "tmp/current-window-artifacts.json",
            ["tmp/cron-freshness-spine.json"],
            [],
            [],
            ["Review/proof only; no mutation/action/approval authority."],
            "monitor-only",
            False,
            True,
            None,
        ),
        route(
            "WF-BOARD-CANON-GUARDRAILS",
            "Board / Canon Guardrails Monitor",
            "P2",
            "Monitor: board/canon/stale/proposal artifacts.",
            "Escalate on critical contradiction, widened authority flag, or "
            "proposal implying self-apply.",
            None,
            None,
            [],
            [],
            [],
            [
                "Cron may propose; main applies only bounded freshness/status sync or exact "
                "gated maintenance.",
            ],
            "monitor-only; cron proposes, main applies bounded",
            False,
            True,
            None,
        ),
        route(
            "WF-SQL-INDEXES",
            "SQL / Current-Window Indexes Monitor",
            "P2",
            "Monitor: finance SQL, artifact index, JSON-SQL index, "
            "current-window, lifecycle manifest.",
            "Escalate on missing proof, authority flag violation, stale index, "
            "index treated as approval/action, or unlabeled lifecycle.",
            None,
            "scripts/artifact_index.py",
            ["tmp/veritas-artifact-index.sqlite"],
            ["python scripts\\artifact_index.py incremental", "python scripts\\artifact_index.py validate"],
            [],
            [
                "SQL candidate is universe/scope only; other indexes are proof/staging. No "
                "approval/execution/archive/delete authority.",
            ],
            "monitor-only; SQL is proof/staging",
            False,
            True,
            None,
        ),
        route(
            "WF-WORKSPACE-GOVERNOR",
            "Workspace Governor / Archive Monitor",
            "P2",
            "Monitor: archive suggestions + lifecycle manifest.",
            "Escalate when a cleanup suggestion is treated as approval or a "
            "surface is moved/deleted without reference check.",
            None,
            None,
            [],
            [],
            [],
            ["Suggestions only; no destructive cleanup without explicit approval."],
            "monitor-only; suggestions are not approval",
            True,
            True,
            None,
        ),
        route(
            "WF89",
            "Isolated Agent Specialization and Fleet Efficiency Contract",
            "P1",
            "A1 reader slice accepted 2026-09-10 with explicit limits. Plan item 1 "
            "done 2026-09-24: reader join-key fix (+27 credited); fresh builder and "
            "research-scout runs read CREDITABLE under attribution contract v0.3 "
            "(accepted by Randall 2026-09-24); 241 historical cleanup-delete runs stay "
            "uncreditable. Plan item 2 done: grant ledger + drift check (0 drift, 13 "
            "unprovenanced notable grants for owner review). No whole-fleet readiness, "
            "no accounting/activation completion.",
            "Plan item 3: stage dispatch-playbook Skill Workshop proposals. Randall: "
            "choose archive-then-delete for oxalpha-lab retirement; 6 notable grants "
            "remain unprovenanced; other config items wait for Randall.",
            f"{CONTINUITY}/Workflow 89 - Isolated Agent Specialization and Fleet Efficiency Contract.md",
            "tmp/wf89-fleet-20260909/item2-grant-manifest-20260924.json",
            [
                "tmp/wf89-fleet-20260909/item1-diagnosis-20260924.json",
                "state/agent-grants/grant-ledger.json",
                "tmp/wf89-fleet-20260909/wf89-refresh-20260924.json",
                "tmp/wf89-fleet-20260909/attribution-contract-v0.3.md",
                "tmp/wf89-fleet-20260909/current-handoff.json",
                "tmp/wf89-fleet-20260909/a1-grok-applied-qa-result.json",
                "tmp/wf89-fleet-20260909/a1-main-acceptance.json",
            ],
            [
                "python scripts\\test_workflow_routing_index.py",
                "python scripts\\workflow_router.py WF89 --answer all",
            ],
            [
                "Attribution contract v0.3 accepted 2026-09-24, but only 2 runs are credited under it so far (1 builder, 1 scout); 241 historical cleanup-delete runs stay uncreditable",
                "Windows directory-junction proof dated 2026-09-10: four native junction cases deny escape (see tmp/wf89-fleet-20260909/broader/windows-junction-proof.json); positive controls pass; file-symlink coverage remains partial/unavailable, no universal reparse/race/OS claim",
                "Historical accounting not green (2026-08-24 canary isolated_source_reverification_mismatch); current active admission has zero errors",
            ],
            [
                "Index is a derived route map; Active Workflows and exact continuity notes "
                "stay authority. No canon/portfolio/ticker-card/SQL-canon mutation, no "
                "paper/live/brokerage/account action, no cron/config/runtime mutation, no "
                "owner-approval inference from any route row.",
                "No capital/config/execution authority; read-only routing/support only; no "
                "whole-workflow-complete inference from A1 acceptance.",
            ],
            "review-only; read-only routing/support, no approval/execution/mutation authority",
            True,
            True,
            "python scripts\\workflow_router.py WF89 --answer all",
            False,
            None,
            ["WF89", "Workflow89", "Isolated Agent Specialization and Fleet Efficiency Contract"],
        ),
    ]
    return _apply_computed_loop_blockers(routes)


def relpath(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_active_workflow_register(path: Path = ACTIVE_WORKFLOWS_PATH) -> list[dict[str, str]]:
    """Read the compact live-register rows from the canonical Active Workflows page."""
    if not path.exists():
        return []
    in_register = False
    rows: list[dict[str, str]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line.startswith("## "):
            if line == "## P0/P1 Active Register":
                in_register = True
                continue
            if in_register:
                break
        if not in_register or not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) < 6 or cells[0] not in EXPECTED_TIER_COUNTS:
            continue
        rows.append({
            "tier": cells[0],
            "workflow_label": cells[1],
            "current_state": cells[2],
            "next_action": cells[3],
        })
    return rows


def _label_has_workflow_id(label: str, workflow_id: str) -> bool:
    return bool(re.search(
        rf"(?<![A-Za-z0-9-]){re.escape(workflow_id)}(?![A-Za-z0-9-])",
        label,
        flags=re.IGNORECASE,
    ))


def active_row_for_route(route_row: dict[str, Any], active_rows: list[dict[str, str]]) -> dict[str, str] | None:
    """Match a canonical register row without arbitrary fuzzy route lookup."""
    workflow_id = str(route_row.get("workflow_id") or "").strip()
    direct = [row for row in active_rows if workflow_id and _label_has_workflow_id(row["workflow_label"], workflow_id)]
    if len(direct) == 1:
        return direct[0]
    if len(direct) > 1:
        return None

    # A few canonical rows use a human label in place of the machine id. Match
    # only a full normalized display name/declared alias, never a query fragment.
    route_keys = {
        normalize_lookup_key(route_row.get("display_name")),
        *(normalize_lookup_key(alias) for alias in route_row.get("aliases", []) or []),
    }
    route_keys.discard("")
    candidates = []
    for row in active_rows:
        label_key = normalize_lookup_key(row["workflow_label"])
        if label_key in route_keys:
            candidates.append(row)
            continue
        if any(
            len(key) >= 16 and (label_key.startswith(key) or key.startswith(label_key))
            for key in route_keys
        ):
            candidates.append(row)
    return candidates[0] if len(candidates) == 1 else None


def canonical_row_is_on_hold(row: dict[str, str]) -> bool:
    # P3 is the explicit pause/resume-later tier in Active Workflows. Do not
    # infer holds from prose elsewhere in the page.
    return row.get("tier") == "P3"


def reconcile_active_workflow_state(
    routes: list[dict[str, Any]],
    registry: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Project canonical live-register state into derived route rows.

    A canonical pause is fail-closed even before a matching machine override is
    repaired. A stale override that conflicts with an active canonical row also
    remains held until a human resolves the disagreement.
    """
    active_rows = parse_active_workflow_register()
    reconciled: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []

    for original in routes:
        route_row = dict(original)
        canonical = active_row_for_route(route_row, active_rows)
        canonical_source = ACTIVE_WORKFLOWS_REL
        if canonical is None:
            # The P3 queue-tier contract is itself canonical pause/resume-later
            # policy. Some P3 rows are intentionally omitted from the active
            # register, so preserve their existing route prose but apply the
            # same fail-closed control treatment.
            if route_row.get("tier") != "P3":
                reconciled.append(route_row)
                continue
            canonical = {
                "tier": "P3",
                "workflow_label": str(route_row.get("display_name") or route_row.get("workflow_id") or ""),
                "current_state": str(route_row.get("current_state") or ""),
                "next_action": str(route_row.get("next_action") or ""),
            }
            canonical_source = f"{ACTIVE_WORKFLOWS_REL}#Queue Tiers"

        override = find_override(
            str(route_row.get("workflow_id") or ""),
            workflow_name=str(route_row.get("display_name") or ""),
            registry=registry,
        )
        canonical_hold = canonical_row_is_on_hold(canonical)
        override_hold = is_on_hold(override)
        changes = {
            field: {"from": route_row.get(field), "to": canonical[field]}
            for field in ("tier", "current_state", "next_action")
            if route_row.get(field) != canonical[field]
        }
        for field in ("tier", "current_state", "next_action"):
            route_row[field] = canonical[field]

        if canonical_hold:
            route_row["safe_for_helper_lane"] = False
            route_row["effective_status_override"] = "on_hold"
            blocker = f"Canonical Active Workflows hold: {canonical['current_state']}"
            blockers = list(route_row.get("blockers") or [])
            if blocker not in blockers:
                blockers.append(blocker)
            route_row["blockers"] = blockers
            status = "aligned" if override_hold else "control_override_missing"
        elif override_hold:
            status = "canonical_active_override_held"
        else:
            status = "aligned"

        reconciliation = {
            "source": canonical_source,
            "canonical_tier": canonical["tier"],
            "canonical_current_state": canonical["current_state"],
            "canonical_next_action": canonical["next_action"],
            "canonical_hold": canonical_hold,
            "control_override_status": (override or {}).get("status"),
            "status": status,
            "changes": changes,
        }
        route_row["state_reconciliation"] = reconciliation
        reports.append({"workflow_id": route_row.get("workflow_id"), **reconciliation})
        reconciled.append(route_row)

    status_counts: dict[str, int] = {}
    for report in reports:
        status = str(report["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    return reconciled, {
        "source": ACTIVE_WORKFLOWS_REL,
        "matched_route_count": len(reports),
        "status_counts": status_counts,
        "routes": reports,
    }


def exists_on_disk(rel: str) -> bool:
    return (ROOT / rel).exists()


# Route freshness thresholds (hours). The compact ``score`` preserves the
# low-cost primary-proof view. ``material_context_score`` separately requires
# the owner continuity note for active material routes, so a newly refreshed
# packet cannot hide a stale owner instruction.
FRESH_HOURS = 72.0
AGING_HOURS = 336.0  # 14 days


def _mtime_ns(rel: str | None) -> int | None:
    if not rel:
        return None
    path = ROOT / rel
    try:
        return path.stat().st_mtime_ns
    except FileNotFoundError:
        return None


def source_freshness_snapshot() -> dict[str, int | None]:
    """The two small sources that can change a route's control state."""
    return {
        "active_workflows_mtime_ns": _mtime_ns(ACTIVE_WORKFLOWS_REL),
        "control_overrides_mtime_ns": _mtime_ns(CONTROL_OVERRIDES_REL),
    }


def _age_hours(rel: str | None) -> float | None:
    if not rel:
        return None
    p = ROOT / rel
    if not p.exists():
        return None
    mtime = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
    return round((datetime.now(timezone.utc) - mtime).total_seconds() / 3600.0, 1)


def _freshness_score_for(age_hours: float | None, declared: bool) -> str:
    if not declared:
        return "n/a"
    if age_hours is None:
        return "missing"
    if age_hours < FRESH_HOURS:
        return "fresh"
    if age_hours < AGING_HOURS:
        return "aging"
    return "stale"


def _worst_freshness(scores: list[str]) -> str:
    """Return the least trustworthy declared freshness signal."""
    declared = [score for score in scores if score != "n/a"]
    if not declared:
        return "n/a"
    rank = {"fresh": 0, "aging": 1, "stale": 2, "missing": 3}
    return max(declared, key=lambda score: rank.get(score, 3))


def score_route_freshness(r: dict[str, Any]) -> dict[str, Any]:
    cont = r.get("continuity_note")
    primary = r.get("primary_route_artifact")
    primary_declared = bool(primary) and not r.get("primary_pending")
    primary_is_self_index = (
        str(primary or "").replace("\\", "/").casefold()
        == INDEX_OUT.relative_to(ROOT).as_posix().casefold()
    )

    cont_exists = bool(cont) and exists_on_disk(cont)
    primary_exists = primary_declared and exists_on_disk(primary)

    cont_age = _age_hours(cont) if cont_exists else None
    # WF73 deliberately names this derived index as its own primary artifact.
    # A successful rebuild changes that file after the route list is assembled,
    # so its on-disk mtime cannot be used as an external source-freshness token.
    primary_age = 0.0 if primary_is_self_index and primary_exists else (_age_hours(primary) if primary_exists else None)

    primary_score = _freshness_score_for(primary_age, primary_declared)
    continuity_score = _freshness_score_for(cont_age, bool(cont))
    # Compatibility score: the current proof packet remains the fast lookup
    # basis. Material readiness below uses the stricter paired score.
    score = primary_score if primary_score != "n/a" else continuity_score
    material_context_score = _worst_freshness([primary_score, continuity_score])

    return {
        "score": score,
        "primary_artifact_score": primary_score,
        "continuity_note_score": continuity_score,
        "owner_context_score": continuity_score,
        "material_context_score": material_context_score,
        "continuity_note_age_hours": cont_age,
        "primary_artifact_age_hours": primary_age,
        "continuity_note_mtime_ns": _mtime_ns(cont) if cont_exists else None,
        "primary_artifact_mtime_ns": (
            None if primary_is_self_index else (_mtime_ns(primary) if primary_exists else None)
        ),
        "primary_artifact_self_referential": primary_is_self_index,
        "validator_count": len(r.get("validator_commands") or []),
        "has_next_action": bool(r.get("next_action")),
    }


def derive_route_contract(route_row: dict[str, Any]) -> None:
    """Attach the explicit ownership, lifecycle, readiness, and authority contract.

    The route map stays derived: live state comes from Active Workflows and the
    machine-readable control-override state.  This function only projects that
    state into a normalized contract; it never makes a route executable.
    """
    reconciliation = route_row.get("state_reconciliation")
    canonical_hold = isinstance(reconciliation, dict) and reconciliation.get("canonical_hold") is True
    tier = str(route_row.get("tier") or "")
    workflow_id = str(route_row.get("workflow_id") or "")

    if canonical_hold or tier == "P3":
        lifecycle = "paused"
    elif tier == "P2":
        lifecycle = "monitor"
    elif tier == "P4":
        lifecycle = "gated"
    else:
        lifecycle = "active"

    if workflow_id in PAPER_FAIL_CLOSED_WORKFLOWS:
        authority_class = "paper_guard_fail_closed"
    elif lifecycle == "paused":
        authority_class = "paused_review_only"
    elif lifecycle in {"monitor", "gated"}:
        authority_class = "monitor_only"
    elif route_row.get("owner_action_required") is True:
        authority_class = "owner_gated_review_only"
    else:
        authority_class = "review_only"

    freshness = route_row.get("freshness") if isinstance(route_row.get("freshness"), dict) else {}
    material_context = str(freshness.get("material_context_score") or "n/a")
    if lifecycle == "paused":
        readiness = "paused"
    elif authority_class == "paper_guard_fail_closed":
        readiness = "blocked"
    elif lifecycle in {"monitor", "gated"}:
        readiness = "monitor_only"
    elif material_context in {"aging", "stale", "missing"}:
        readiness = "refresh_required"
    else:
        readiness = "route_only"

    effective_status = {
        "paused": "on_hold",
        "blocked": "blocked",
        "monitor_only": "monitor_only",
        "refresh_required": "refresh_required",
        "route_only": "route_only",
    }[readiness]

    route_row.update({
        # ``tier`` remains for compatibility; ``priority`` is the unambiguous
        # label for consumers that must not conflate priority with readiness.
        "priority": tier,
        "lifecycle": lifecycle,
        "readiness": readiness,
        "authority_class": authority_class,
        "primary_owner_lane": "main-session-veritas",
        "secondary_consumers": list(SECONDARY_CONSUMERS.get(workflow_id, [])),
        "human_approval_owner": "Randall",
        "proof_artifact": route_row.get("primary_route_artifact") or route_row.get("continuity_note"),
        "freshness_sla": {
            "primary_artifact_max_age_hours": FRESHNESS_SLA_HOURS,
            "owner_context_max_age_hours": FRESHNESS_SLA_HOURS,
            "material_owner_context_required": lifecycle == "active" and tier in {"P0", "P1"},
        },
        "authoritative_next_action": route_row.get("next_action"),
        "effective_status_override": effective_status,
    })
    if readiness in {"paused", "blocked"}:
        route_row["safe_for_helper_lane"] = False


def build_handoff(rt: dict[str, Any]) -> dict[str, Any]:
    """Derive a bounded helper-lane handoff packet from a single route row,
    shaped to `06. Playbooks/Subagent Spawn Handoff Template.md`."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    safe = bool(rt.get("safe_for_helper_lane"))
    _explicit_monitor_routes = {"WF-CHIEF-GATE", "WF-FINANCE-CHAINS", "WF-BOARD-CANON-GUARDRAILS", "WF-SQL-INDEXES", "WF-WORKSPACE-GOVERNOR"}
    _source_authority = "scripts/workflow_routing_index.py" if rt.get("workflow_id") in _explicit_monitor_routes else "06. Playbooks/Active Workflows.md"

    read_first: list[str] = []
    if rt.get("continuity_note"):
        read_first.append(rt["continuity_note"])
    if rt.get("primary_route_artifact") and not rt.get("primary_pending"):
        read_first.append(rt["primary_route_artifact"])
    read_first.extend(rt.get("secondary_artifacts") or [])

    validators = list(rt.get("validator_commands") or [])
    acceptance = validators + ["python scripts\\workflow_routing_index.py --validate"]

    packet: dict[str, Any] = {
        "schema_version": "workflow_routing_handoff.v1",
        "generated_at_utc": now,
        "source_authority": _source_authority,
        "spawn_template": "06. Playbooks/Subagent Spawn Handoff Template.md",
        "workflow_id": rt.get("workflow_id"),
        "display_name": rt.get("display_name"),
        "tier": rt.get("tier"),
        "priority": rt.get("priority"),
        "lifecycle": rt.get("lifecycle"),
        "readiness": rt.get("readiness"),
        "authority_class": rt.get("authority_class"),
        "mode": "Spawn read-only" if safe else "Main-session only",
        "safe_for_helper_lane": safe,
        "owner_action_required": bool(rt.get("owner_action_required")),
        "primary_owner_lane": rt.get("primary_owner_lane"),
        "secondary_consumers": rt.get("secondary_consumers") or [],
        "human_approval_owner": rt.get("human_approval_owner"),
        "objective": rt.get("authoritative_next_action") or rt.get("next_action"),
        "current_truth": rt.get("current_state"),
        "read_first": read_first[:6],
        "do_not_read_first": [
            "broad workflow folders", "all skills", "full tmp/ scans",
            "parent transcript/forked chat context", "unrelated continuity history",
        ],
        "do_not_touch": [
            "canonical portfolio/canon notes",
            "config/auth/credentials/runtime surfaces",
            "paper/live/brokerage/account actions",
            "destructive move/delete/archive",
        ],
        "validators": validators,
        "stop_lines": rt.get("stop_lines") or [],
        "blockers": rt.get("blockers") or [],
        "authority_boundary": rt.get("authority_boundary"),
        "acceptance_proof": acceptance,
        "freshness": rt.get("freshness"),
        "freshness_sla": rt.get("freshness_sla"),
        "proof_artifact": rt.get("proof_artifact"),
        "authority": dict(AUTHORITY),
        "note": (
            "Derived review-only helper packet. Active Workflows and the exact "
            "continuity note remain authority; this packet grants no canon/"
            "portfolio/SQL/approval/execution authority and never implies owner "
            "approval."
        ),
    }
    if not safe:
        packet["helper_lane_warning"] = (
            "Route is owner-gated / main-session only (safe_for_helper_lane=false). "
            "Do not auto-spawn; route requires Randall's decision or main-session "
            "execution per the route stop lines."
        )
    return packet


def apply_alert_os_pivot_contract(route_row: dict[str, Any]) -> dict[str, Any]:
    """Fail closed around the 2026-08-29 alerts-and-recommendations pivot.

    Historical route definitions remain readable for audit continuity, but this
    projection removes their operational artifacts and commands before live
    workflow reconciliation/capsule generation.  It grants no new authority.
    """
    row = dict(route_row)
    workflow_id = str(row.get("workflow_id") or "")

    if workflow_id in ALERT_OS_RETIRED_WORKFLOWS:
        aliases = list(row.get("aliases") or [])
        if workflow_id == "WF64-WF56":
            for alias in ("WF64", "WF56", "WF64/WF56"):
                if alias not in aliases:
                    aliases.append(alias)
        row.update({
            "aliases": aliases,
            "tier": "P3",
            "current_state": (
                "Retired 2026-08-29 by Randall's alerts-and-recommendations OS pivot; "
                "historical evidence is retained but no operational route remains."
            ),
            "next_action": (
                "Do not advance or schedule this workflow. Preserve historical proof "
                "and route current evidence/freshness needs to WF84/WF85."
            ),
            "primary_route_artifact": None,
            "primary_pending": False,
            "secondary_artifacts": [],
            "validator_commands": [],
            "blockers": ["Retired by explicit owner architecture decision"],
            "stop_lines": [
                "No portfolio construction/state maintenance, canon apply, simulated account "
                "state, order generation, brokerage/account action, or paper/live execution."
            ],
            "authority_boundary": "retired history only; no operational or action authority",
            "owner_action_required": True,
            "safe_for_helper_lane": False,
            "default_resume_command": None,
        })
        return row

    if workflow_id in ALERT_OS_DENY_ONLY_WORKFLOWS:
        row.update({
            "tier": "P3",
            "current_state": (
                "Superseded as deny-only safety history by the 2026-08-29 "
                "alerts-and-recommendations OS pivot."
            ),
            "next_action": (
                "Preserve endpoint isolation, redaction, stale-artifact rejection, and "
                "fail-closed audit evidence only; do not run broker/account/order paths."
            ),
            "primary_route_artifact": None,
            "primary_pending": False,
            "secondary_artifacts": [],
            "validator_commands": [],
            "blockers": ["Operational paper/account route retired"],
            "stop_lines": [
                "Deny-only safety evidence. No broker GET, account, position, order, manager, "
                "submit, cancel, sell, simulated-state maintenance, or paper/live execution."
            ],
            "authority_boundary": "deny-only historical safety proof; no operational authority",
            "owner_action_required": True,
            "safe_for_helper_lane": False,
            "default_resume_command": None,
        })
        return row

    if workflow_id == "WF85":
        row.update({
            "display_name": "WF85 - Alerts and Recommendations OS",
            "current_state": (
                "Primary review-only alerts-and-recommendations lane over guarded WF84 evidence; "
                "freshness and uncertainty fail closed and generated output is never approval."
            ),
            "next_action": (
                "Refresh guarded evidence, alert levels, and the current recommendation digest; "
                "surface stale or conflicted inputs explicitly."
            ),
            "primary_route_artifact": "tmp/finance-alert-os-digest.json",
            "secondary_artifacts": [
                "tmp/alert-level-freshness-controller.json",
                "tmp/alerts-recommendations-chain-morning.json",
                "tmp/alerts-os-pivot-validator.json",
            ],
            "validator_commands": [
                "python scripts\\finance_sql_canon_access.py --write --validate",
                "python scripts\\alert_level_freshness_controller.py --write --validate",
                "python scripts\\run_alerts_recommendations_chain.py morning --write --validate",
                "python scripts\\alerts_os_pivot_validator.py --write --validate",
                "python scripts\\workflow_router.py WF85 --answer all --write-capsules --validate",
            ],
            "blockers": [],
            "stop_lines": [
                "Alerts and recommendations only. No portfolio construction/state, capital, "
                "order, account, money-movement, or paper/live execution authority."
            ],
            "authority_boundary": "review-only alerts and non-executing recommendations",
            "owner_action_required": False,
            "safe_for_helper_lane": True,
            "default_resume_command": (
                "python scripts\\run_alerts_recommendations_chain.py morning --write --validate"
            ),
        })
        return row

    if workflow_id == "WF84":
        row.update({
            "display_name": "WF84 - Guarded Alert Evidence Plane",
            "current_state": (
                "Read-only alert evidence over guarded SQL, active alert canon, explicit "
                "quote proof, and current freshness state. The former canonical-finance-"
                "data-plane runtime is retired."
            ),
            "next_action": (
                "Validate guarded SQL and refresh the bounded alerts chain; preserve "
                "provenance and surface stale or conflicted evidence."
            ),
            "primary_route_artifact": "tmp/finance-sql-canon-access-validation.json",
            "secondary_artifacts": [
                "tmp/intraday-alerts/quote-snapshot-proof.json",
                "tmp/intraday-alerts/quote-snapshot-proof-validation.json",
                "tmp/alert-level-freshness-controller.json",
                "tmp/alerts-recommendations-chain-midday.json",
            ],
            "validator_commands": [
                "python scripts\\finance_sql_canon_access.py --write --validate",
                "python scripts\\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate",
                "python scripts\\workflow_router.py WF84 --answer all --write-capsules --validate",
            ],
            "blockers": [],
            "stop_lines": [
                "Evidence and freshness only. No maintained portfolio or simulated-account "
                "state, finance-canon write, capital, order, account, or execution authority."
            ],
            "authority_boundary": "read-only guarded alert evidence",
            "owner_action_required": False,
            "safe_for_helper_lane": True,
            "default_resume_command": (
                "python scripts\\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate"
            ),
        })
        return row

    if workflow_id == "WF77":
        row.update({
            "display_name": "WF77 - Alert Evidence and Question Router",
            "current_state": (
                "Guarded SQL and the current alert controller are the ticker front door; "
                "legacy finance-state, full-answer, and card databases are retired."
            ),
            "next_action": (
                "Repair source-open evidence or freshness gaps needed for a bounded alert "
                "or non-executing recommendation."
            ),
            "primary_route_artifact": "tmp/alert-level-freshness-controller.json",
            "secondary_artifacts": [
                "tmp/finance-sql-canon-access-validation.json",
                "tmp/intraday-alerts/quote-snapshot-proof.json",
                "tmp/finance-alert-os-digest.json",
            ],
            "validator_commands": [
                "python scripts\\finance_sql_canon_access.py --write --validate",
                "python scripts\\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate",
                "python scripts\\workflow_router.py WF77 --answer all --write-capsules --validate",
            ],
            "stop_lines": [
                "Research and freshness only. No maintained portfolio or simulated-account "
                "state, capital, order, account, execution, import, or apply authority."
            ],
            "authority_boundary": "review-only alert evidence and question routing",
            "owner_action_required": False,
            "safe_for_helper_lane": True,
            "default_resume_command": (
                "python scripts\\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate"
            ),
        })
        return row

    if workflow_id == "WF72":
        row.update({
            "display_name": "WF72 - Guarded Finance SQL Support",
            "primary_route_artifact": "tmp/finance-sql-canon-access-validation.json",
            "secondary_artifacts": [
                "state/finance/finance-canon.sqlite",
                "tmp/alerts-os-pivot-validator.json",
            ],
            "validator_commands": [
                "python scripts\\finance_sql_canon_access.py --write --validate",
                "python scripts\\alerts_os_pivot_validator.py --write --validate",
                "python scripts\\workflow_router.py WF72 --answer all --write-capsules --validate",
            ],
            "blockers": [],
            "stop_lines": [
                "Guarded alert evidence only. No tier-routing mirror, legacy consumer, "
                "portfolio or simulated-account state, canon write, capital, order, account, "
                "or execution authority."
            ],
            "authority_boundary": "read-only guarded SQL support for alert evidence",
            "owner_action_required": False,
            "safe_for_helper_lane": True,
            "default_resume_command": (
                "python scripts\\finance_sql_canon_access.py --write --validate"
            ),
        })
        return row

    if workflow_id == "WF79":
        row.update({
            "primary_route_artifact": "tmp/veritas-command-center-compact-reader.json",
            "secondary_artifacts": [
                "tmp/veritas-command-center-compact.html",
                "tmp/dashboard-presentation-view-model.json",
                "tmp/presentation-retrieval-route-map.json",
            ],
            "validator_commands": [
                "python scripts\\dashboard_compact_shell_acceptance.py --write --validate",
                "python scripts\\presentation_retrieval_route_map.py --write --validate",
                "python scripts\\presentation_retrieval_enforcement.py --write --validate",
            ],
            "blockers": [],
            "stop_lines": [
                "Local read-only presentation. No finance-state maintenance, canon apply, "
                "account, order, execution, external delivery, or approval inference."
            ],
            "authority_boundary": "review-only local presentation",
            "owner_action_required": False,
            "safe_for_helper_lane": True,
            "default_resume_command": (
                "python scripts\\dashboard_compact_shell_acceptance.py --write --validate"
            ),
        })
        return row

    if workflow_id == "WF88":
        row.update({
            "secondary_artifacts": [
                "tmp/wf88-os2-control-packet.md",
                "tmp/wf88-wiki-synthesis-packet.json",
                "tmp/skill-workshop-body-guard.json",
                "wiki/index.md",
                "tmp/token-efficiency-scorecard.json",
                "tmp/retrieval-quality-scorecard.json",
                "tmp/wf88-decision-compiler.json",
                "tmp/rsi-outcome-scorecard.json",
                "tmp/cron-control-packet.json",
                "tmp/wf88-route-contraction-packet.json",
            ],
            "validator_commands": [
                "python scripts\\wf88_wiki_synthesis_packet.py --write --write-md --write-wiki --validate",
                "python scripts\\skill_workshop_body_guard.py --write --validate",
                "python scripts\\token_efficiency_scorecard.py --write --write-md --validate",
                "python scripts\\retrieval_quality_scorecard.py --write --write-md --validate",
                "python scripts\\wf88_decision_compiler.py --write --write-md --validate",
                "python scripts\\rsi_outcome_scorecard.py --write --write-md --validate",
                "python scripts\\wf88_os2_control_packet.py --write --write-md --validate",
                "python scripts\\wf88_route_contraction_packet.py --write --write-md --validate",
                "python scripts\\workflow_router.py WF88 --answer all --write-capsules --validate",
            ],
            "stop_lines": [
                "Learning, evaluation, routing, and proposal output only. No retired finance "
                "producer, canon apply, schedule/runtime mutation, account, order, execution, "
                "external delivery, or owner-approval inference."
            ],
            "authority_boundary": "review-only OS learning, evaluation, and routing",
            "owner_action_required": True,
            "safe_for_helper_lane": False,
            "default_resume_command": None,
        })
        return row

    if workflow_id in {"WF51", "WF53"}:
        row.update({
            "current_state": (
                "Closed historical evidence route; no current finance producer or state owner."
            ),
            "next_action": (
                "Use guarded SQL, explicit quote proof, the alert controller, WF84, and WF85 "
                "for current finance evidence and recommendations."
            ),
            "secondary_artifacts": [],
            "validator_commands": [],
            "blockers": [],
            "stop_lines": [
                "Historical review evidence only; no current finance state, canon, account, "
                "order, execution, or approval authority."
            ],
            "authority_boundary": "historical review-only evidence route",
            "owner_action_required": True,
            "safe_for_helper_lane": False,
            "default_resume_command": None,
        })
        return row

    if workflow_id == "WF-CHIEF-GATE":
        row.update({
            "display_name": "Alert Recommendation Guardrail Monitor",
            "current_state": "Monitor guarded alert evidence, freshness, and recommendation boundaries.",
            "next_action": (
                "Escalate on missing lineage, freshness decay, contradictory thesis/band state, "
                "or any output that implies approval or action authority."
            ),
            "continuity_note": None,
            "primary_route_artifact": "tmp/alerts-os-pivot-validator.json",
            "primary_pending": False,
            "secondary_artifacts": [
                "tmp/alert-level-freshness-controller.json",
                "tmp/finance-alert-os-digest.json",
            ],
            "validator_commands": [
                "python scripts\\alerts_os_pivot_validator.py --write --validate",
            ],
            "blockers": [],
            "stop_lines": [
                "Monitor and escalate only. No canon, schedule, account, order, execution, "
                "or approval authority."
            ],
            "authority_boundary": "monitor-only alert and recommendation guardrail",
            "owner_action_required": False,
            "safe_for_helper_lane": False,
            "default_resume_command": None,
        })
        return row

    if workflow_id == "WF-FINANCE-CHAINS":
        row.update({
            "display_name": "Alerts and Recommendations Chain Monitor",
            "current_state": "Monitor morning, midday, post-close, weekly, and cron control proof.",
            "next_action": (
                "Escalate on a failed chain, missing source proof, freshness decay, contract "
                "drift, scheduler error, or digest validation failure."
            ),
            "primary_route_artifact": "tmp/alerts-recommendations-chain-midday.json",
            "secondary_artifacts": [
                "tmp/alerts-recommendations-chain-morning.json",
                "tmp/alerts-recommendations-chain-post-close.json",
                "tmp/alerts-recommendations-chain-weekly.json",
                "tmp/cron-freshness-spine.json",
                "tmp/cron-control-packet.json",
                "tmp/wf88-route-contraction-packet.json",
            ],
            "validator_commands": [
                "python scripts\\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate",
                "python scripts\\cron_control_packet.py --write --validate",
            ],
            "blockers": [],
            "stop_lines": [
                "Monitor only. A successful packet write is not proof of source freshness, "
                "fleet health, approval, account action, or execution authority."
            ],
            "authority_boundary": "monitor-only alerts chain control",
            "owner_action_required": False,
            "safe_for_helper_lane": False,
            "default_resume_command": None,
        })
        return row

    if workflow_id == "WF60-WF61":
        row.update({
            "display_name": "Research and Macro Evidence Monitor",
            "current_state": "Monitor macro, company, sector, and market-theme evidence freshness.",
            "next_action": (
                "Escalate on material source conflict, freshness decay, thesis change, catalyst "
                "change, or evidence that requires alert review."
            ),
            "secondary_artifacts": [],
            "validator_commands": [],
            "blockers": [],
            "stop_lines": [
                "Evidence monitor only; no canon apply, maintained finance action-state, "
                "account, order, execution, or approval authority."
            ],
            "authority_boundary": "monitor-only research and macro evidence",
            "owner_action_required": False,
            "safe_for_helper_lane": False,
            "default_resume_command": None,
        })
        return row

    blocked_tokens = (
        "wf67", "wf68", "wf76", "wf78", "wf86", "wf87", "paper", "portfolio_mutation", "position_sizing",
        "auto_apply", "deployment", "order_", "full_portfolio", "execution_board",
        "canonical-finance-data-plane", "finance-intelligence-state", "canon-cache",
        "trade-grade", "full-answer", "band-proposals",
    )
    if workflow_id in {"WF68", "WF72", "WF78", "WF88"}:
        row["secondary_artifacts"] = [
            value for value in (row.get("secondary_artifacts") or [])
            if not any(token in str(value).lower() for token in blocked_tokens)
        ]
        row["validator_commands"] = [
            value for value in (row.get("validator_commands") or [])
            if not any(token in str(value).lower() for token in blocked_tokens)
        ]
    return row


def build_index() -> dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    registry = load_registry()
    override_routes = [
        apply_alert_os_pivot_contract(apply_route_override(route, registry))
        for route in build_routes()
    ]
    routes, state_reconciliation = reconcile_active_workflow_state(override_routes, registry)
    for r in routes:
        r["last_validated_at"] = now
        r["freshness"] = score_route_freshness(r)
        derive_route_contract(r)
    tier_counts: dict[str, int] = {}
    freshness_counts: dict[str, int] = {}
    lifecycle_counts: dict[str, int] = {}
    readiness_counts: dict[str, int] = {}
    for r in routes:
        tier_counts[r["tier"]] = tier_counts.get(r["tier"], 0) + 1
        fs = r["freshness"]["score"]
        freshness_counts[fs] = freshness_counts.get(fs, 0) + 1
        lifecycle = str(r.get("lifecycle") or "unknown")
        readiness = str(r.get("readiness") or "unknown")
        lifecycle_counts[lifecycle] = lifecycle_counts.get(lifecycle, 0) + 1
        readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1
    return {
        "schema_version": "workflow_routing_index.v2",
        "generated_at_utc": now,
        "source_authority": "06. Playbooks/Active Workflows.md",
        "state_authority": {
            "canonical_control_sources": [ACTIVE_WORKFLOWS_REL, CONTROL_OVERRIDES_REL],
            "precedence": [
                "Active Workflows explicit pause/tier/current-state/next-action",
                "workflow-control-overrides fail-closed machine hold",
                "route metadata defaults only where the canonical page has no field",
            ],
            "derived_mirrors": ["state/workflows/*.json", "tmp/workflow-routing-index.json", "tmp/veritas-status-card.json"],
            "note": "Derived mirrors are parity consumers, not state authority.",
        },
        "source_freshness": source_freshness_snapshot(),
        "state_reconciliation": state_reconciliation,
        "note": (
            "Derived review-only route map. Active Workflows and exact continuity "
            "notes remain authority; this index never outranks them and carries no "
            "canon/portfolio/SQL/approval/execution authority."
        ),
        "authority": dict(AUTHORITY),
        "summary": {
            "route_count": len(routes),
            "tier_counts": tier_counts,
            "freshness_counts": freshness_counts,
            "lifecycle_counts": lifecycle_counts,
            "readiness_counts": readiness_counts,
            "active_build_queue_count": sum(
                1
                for r in routes
                if r.get("priority") in {"P0", "P1"}
                and r.get("lifecycle") == "active"
                and r.get("readiness") == "route_only"
            ),
        },
        "routes": routes,
    }


def validate_index(index: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    routes = index.get("routes", [])
    summary = index.get("summary", {})

    if index.get("schema_version") != "workflow_routing_index.v2":
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "schema_version",
            "issue": "index schema_version must be workflow_routing_index.v2",
            "value": index.get("schema_version"),
        })

    if not isinstance(routes, list):
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "routes",
            "issue": "index.routes must be a list",
            "value_type": type(routes).__name__,
        })
        routes = []

    if summary.get("route_count") != len(routes):
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "route_count",
            "issue": "summary.route_count must equal actual route length",
            "summary_value": summary.get("route_count"),
            "actual_value": len(routes),
        })

    if len(routes) != EXPECTED_ROUTE_COUNT:
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "route_coverage",
            "issue": "route count drifted from the expected P0/P1/P2/P3 coverage set",
            "expected": EXPECTED_ROUTE_COUNT,
            "actual": len(routes),
        })

    actual_tier_counts: dict[str, int] = {}
    for r in routes:
        tier = r.get("tier")
        actual_tier_counts[tier] = actual_tier_counts.get(tier, 0) + 1
    if actual_tier_counts != EXPECTED_TIER_COUNTS:
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "tier_coverage",
            "issue": "tier counts drifted from expected P0/P1/P2/P3 coverage",
            "expected": EXPECTED_TIER_COUNTS,
            "actual": actual_tier_counts,
        })
    if summary.get("tier_counts") != actual_tier_counts:
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "tier_counts",
            "issue": "summary.tier_counts must equal actual route tiers",
            "summary_value": summary.get("tier_counts"),
            "actual_value": actual_tier_counts,
        })

    # Index-level authority clamp.
    authority = index.get("authority", {})
    for flag, expected in AUTHORITY.items():
        if authority.get(flag) != expected:
            findings.append({
                "severity": "critical",
                "scope": "index",
                "check": "authority",
                "issue": f"index authority.{flag} must be {expected}",
                "value": authority.get(flag),
            })

    source_freshness = index.get("source_freshness")
    if not isinstance(source_freshness, dict):
        findings.append({
            "severity": "critical",
            "scope": "index",
            "check": "source_freshness",
            "issue": "index must record the canonical control-source freshness snapshot",
        })
    else:
        for key in ("active_workflows_mtime_ns", "control_overrides_mtime_ns"):
            value = source_freshness.get(key)
            if value is not None and not isinstance(value, int):
                findings.append({
                    "severity": "critical",
                    "scope": "index",
                    "check": "source_freshness",
                    "issue": f"source_freshness.{key} must be an integer or null",
                    "value": value,
                })

    seen_ids: set[str] = set()
    seen_aliases: dict[str, str] = {}
    for r in routes:
        wid = r.get("workflow_id", "<unknown>")

        # Required fields present.
        for field in REQUIRED_FIELDS:
            if field not in r:
                findings.append({
                    "severity": "critical", "workflow_id": wid, "check": "required_field",
                    "issue": f"missing required route field: {field}",
                })

        for field in LIST_FIELDS:
            if field in r and not isinstance(r.get(field), list):
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "field_type",
                    "issue": f"{field} must be a list",
                    "value_type": type(r.get(field)).__name__,
                })
            for idx, value in enumerate(r.get(field) or []):
                if not isinstance(value, str) or not value.strip():
                    findings.append({
                        "severity": "critical",
                        "workflow_id": wid,
                        "check": "field_type",
                        "issue": f"{field}[{idx}] must be a non-empty string",
                        "value": value,
                    })

        for field in BOOL_FIELDS:
            if field in r and not isinstance(r.get(field), bool):
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "field_type",
                    "issue": f"{field} must be boolean",
                    "value": r.get(field),
                })

        if not isinstance(r.get("workflow_id"), str) or not r.get("workflow_id", "").strip():
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "workflow_id",
                "issue": "workflow_id must be a non-empty string",
            })
        if r.get("tier") not in EXPECTED_TIER_COUNTS:
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "tier",
                "issue": "tier must be one of P0/P1/P2/P3",
                "value": r.get("tier"),
            })
        for field in (
            "display_name", "current_state", "next_action", "authority_boundary",
            "priority", "lifecycle", "readiness", "authority_class",
            "primary_owner_lane", "human_approval_owner", "authoritative_next_action",
        ):
            if not isinstance(r.get(field), str) or not r.get(field, "").strip():
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "field_value",
                "issue": f"{field} must be a non-empty string",
            })

        if r.get("priority") != r.get("tier"):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "priority",
                "issue": "priority must mirror the compatibility tier field",
            })
        if r.get("lifecycle") not in LIFECYCLES:
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "lifecycle",
                "issue": "lifecycle is outside the declared enum",
                "value": r.get("lifecycle"),
            })
        if r.get("readiness") not in READINESS_STATES:
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "readiness",
                "issue": "readiness is outside the declared enum",
                "value": r.get("readiness"),
            })
        if r.get("authority_class") not in AUTHORITY_CLASSES:
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "authority_class",
                "issue": "authority_class is outside the declared enum",
                "value": r.get("authority_class"),
            })
        freshness_sla = r.get("freshness_sla")
        if not isinstance(freshness_sla, dict) or any(
            not isinstance(freshness_sla.get(key), (int, float, bool))
            for key in (
                "primary_artifact_max_age_hours",
                "owner_context_max_age_hours",
                "material_owner_context_required",
            )
        ):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "freshness_sla",
                "issue": "route must declare a typed primary/owner-context freshness SLA",
            })
        if r.get("authoritative_next_action") != r.get("next_action"):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "authoritative_next_action",
                "issue": "authoritative_next_action must match the reconciled next_action",
            })
        if r.get("lifecycle") == "paused" and (
            r.get("readiness") != "paused"
            or r.get("effective_status_override") != "on_hold"
            or r.get("safe_for_helper_lane") is not False
        ):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "paused_contract",
                "issue": "paused routes must be on_hold, non-dispatchable, and visibly paused",
            })
        if r.get("authority_class") == "paper_guard_fail_closed" and (
            r.get("readiness") != "blocked"
            or r.get("safe_for_helper_lane") is not False
            or r.get("effective_status_override") != "blocked"
        ):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "paper_fail_closed_contract",
                "issue": "paper guard routes must remain visibly blocked and helper-unsafe",
            })
        if r.get("lifecycle") == "active" and r.get("readiness") == "route_only" and r.get("effective_status_override") == "ready":
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "route_only_contract",
                "issue": "route_only is not executable readiness and must never serialize as ready",
            })

        # Unique workflow id.
        if wid in seen_ids:
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "unique_id",
                "issue": "duplicate workflow_id in routing index",
            })
        seen_ids.add(wid)

        aliases = route_alias_records(r)
        if not r.get("aliases"):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "aliases",
                "issue": "route must carry at least one exact lookup alias",
            })
        for alias in aliases:
            alias_key = alias["alias_key"]
            previous_workflow = seen_aliases.get(alias_key)
            if previous_workflow and previous_workflow != wid:
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "alias_unique",
                    "issue": "exact lookup alias resolves to more than one workflow",
                    "alias": alias["alias"],
                    "alias_key": alias_key,
                    "other_workflow_id": previous_workflow,
                })
            else:
                seen_aliases[alias_key] = wid

        # Stop lines mandatory.
        stop_lines = r.get("stop_lines")
        if not isinstance(stop_lines, list) or not stop_lines:
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "stop_lines",
                "issue": "route must carry at least one stop line",
            })

        # Authority boundary string mandatory.
        if not r.get("authority_boundary"):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "authority_boundary",
                "issue": "route must declare an authority_boundary",
            })

        # Continuity note: null is allowed (explicit "no dedicated note"); a
        # declared path that is absent on disk is a coverage warning.
        cont = r.get("continuity_note")
        if cont is not None and not exists_on_disk(cont):
            findings.append({
                "severity": "warning", "workflow_id": wid, "check": "continuity_note",
                "issue": "declared continuity_note not found on disk",
                "path": cont,
            })

        # Primary route artifact: null allowed (e.g. pure-monitor with no single
        # proof file); declared, non-pending, absent path is a coverage warning.
        primary = r.get("primary_route_artifact")
        if primary is not None and not r.get("primary_pending") and not exists_on_disk(primary):
            findings.append({
                "severity": "warning", "workflow_id": wid, "check": "primary_route_artifact",
                "issue": "declared primary_route_artifact not found on disk",
                "path": primary,
            })

        # Secondary artifacts: declared paths that look like workspace paths and
        # are absent are coverage warnings (skip bare command-ish entries).
        for sec in r.get("secondary_artifacts", []) or []:
            if ("/" in sec or "\\" in sec) and not exists_on_disk(sec):
                findings.append({
                    "severity": "warning", "workflow_id": wid, "check": "secondary_artifact",
                    "issue": "declared secondary_artifact not found on disk",
                    "path": sec,
                })

        # Active build lanes (P0/P1) should carry at least one validator command.
        if r.get("tier") in ("P0", "P1") and not (r.get("validator_commands") or []):
            findings.append({
                "severity": "warning", "workflow_id": wid, "check": "validator_commands",
                "issue": "active build lane has no validator_commands",
            })

        freshness = r.get("freshness")
        if not isinstance(freshness, dict):
            findings.append({
                "severity": "critical", "workflow_id": wid, "check": "freshness",
                "issue": "route must carry a freshness object",
            })
        else:
            if freshness.get("score") not in FRESHNESS_SCORES:
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "freshness",
                    "issue": "freshness.score is outside the allowed enum",
                    "value": freshness.get("score"),
                })
            if freshness.get("validator_count") != len(r.get("validator_commands") or []):
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "freshness",
                    "issue": "freshness.validator_count must equal validator_commands length",
                    "freshness_value": freshness.get("validator_count"),
                    "actual_value": len(r.get("validator_commands") or []),
                })
            if freshness.get("has_next_action") is not bool(r.get("next_action")):
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "freshness",
                    "issue": "freshness.has_next_action must match next_action presence",
                })
            for key in ("primary_artifact_score", "continuity_note_score", "owner_context_score", "material_context_score"):
                if freshness.get(key) not in FRESHNESS_SCORES:
                    findings.append({
                        "severity": "critical", "workflow_id": wid, "check": "freshness",
                        "issue": f"freshness.{key} is outside the allowed enum",
                        "value": freshness.get(key),
                    })

        if r.get("tier") in {"P0", "P1"}:
            if r.get("primary_owner_lane") != "main-session-veritas":
                findings.append({
                    "severity": "critical", "workflow_id": wid, "check": "primary_owner_lane",
                    "issue": "P0/P1 route must have exactly the declared main-session operational owner",
                })
            if not r.get("proof_artifact"):
                findings.append({
                    "severity": "critical", "workflow_id": wid, "check": "proof_artifact",
                    "issue": "P0/P1 route must declare a proof artifact",
                })

        reconciliation = r.get("state_reconciliation")
        if isinstance(reconciliation, dict):
            status = reconciliation.get("status")
            canonical_hold = reconciliation.get("canonical_hold") is True
            if status in {"control_override_missing", "canonical_active_override_held"}:
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "state_reconciliation",
                    "issue": "canonical control state and workflow-control override disagree",
                    "status": status,
                })
            if canonical_hold and (
                r.get("tier") != "P3"
                or r.get("safe_for_helper_lane") is not False
                or r.get("effective_status_override") != "on_hold"
            ):
                findings.append({
                    "severity": "critical",
                    "workflow_id": wid,
                    "check": "state_reconciliation",
                    "issue": "canonical paused route must be P3, on_hold, and helper-unsafe",
                })

        packet = build_handoff(r)
        expected_mode = "Spawn read-only" if r.get("safe_for_helper_lane") else "Main-session only"
        if packet.get("mode") != expected_mode or packet.get("mode") not in HANDOFF_MODES:
            findings.append({
                "severity": "critical",
                "workflow_id": wid,
                "check": "handoff_mode",
                "issue": "handoff mode must match safe_for_helper_lane",
                "expected": expected_mode,
                "actual": packet.get("mode"),
            })
        if not r.get("safe_for_helper_lane") and not packet.get("helper_lane_warning"):
            findings.append({
                "severity": "critical",
                "workflow_id": wid,
                "check": "handoff_mode",
                "issue": "main-session-only handoff must carry helper_lane_warning",
            })
        if packet.get("authority") != AUTHORITY:
            findings.append({
                "severity": "critical",
                "workflow_id": wid,
                "check": "handoff_authority",
                "issue": "handoff authority clamp must match index authority clamp",
            })

    critical = sum(1 for f in findings if f.get("severity") == "critical")
    warning = sum(1 for f in findings if f.get("severity") == "warning")
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "input": relpath(INDEX_OUT),
        "status": "ok" if critical == 0 else "blocked",
        "authority": dict(AUTHORITY),
        "summary": {
            "routes_checked": len(routes),
            "critical": critical,
            "warning": warning,
            "checks": [
                "schema_version", "routes", "route_count", "route_coverage",
                "tier_coverage", "tier_counts", "authority", "required_field",
                "field_type", "field_value", "unique_id", "aliases", "alias_unique", "stop_lines",
                "authority_boundary", "continuity_note",
                "primary_route_artifact", "secondary_artifact",
                "validator_commands", "freshness", "freshness_sla", "priority", "lifecycle", "readiness",
                "authority_class", "primary_owner_lane", "proof_artifact", "authoritative_next_action",
                "paused_contract", "paper_fail_closed_contract", "route_only_contract",
                "source_freshness", "state_reconciliation", "handoff_mode",
                "handoff_authority",
            ],
        },
        "findings": findings,
    }


def _db_path(path: str | None) -> Path:
    return ROOT / path if path else DB_OUT


def write_sqlite_index(index: dict[str, Any], db_path: Path) -> dict[str, Any]:
    """Write a derived/rebuildable SQLite lookup from the JSON route objects."""
    alias_owners: dict[str, str] = {}
    for route_row in index.get("routes", []):
        workflow_id = str(route_row.get("workflow_id") or "")
        for alias in route_alias_records(route_row):
            existing = alias_owners.setdefault(alias["alias_key"], workflow_id)
            if existing != workflow_id:
                raise ValueError(
                    f"ambiguous exact alias {alias['alias']!r}: {existing} and {workflow_id}"
                )
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path, timeout=5) as con:
        con.execute("PRAGMA busy_timeout = 5000")
        con.execute("PRAGMA journal_mode = WAL")
        con.execute("PRAGMA foreign_keys = ON")
        con.executescript(
            """
            DROP TABLE IF EXISTS workflow_authority;
            DROP TABLE IF EXISTS workflow_freshness;
            DROP TABLE IF EXISTS workflow_stop_lines;
            DROP TABLE IF EXISTS workflow_blockers;
            DROP TABLE IF EXISTS workflow_validators;
            DROP TABLE IF EXISTS workflow_artifacts;
            DROP TABLE IF EXISTS workflow_route_aliases;
            DROP TABLE IF EXISTS workflow_routes;
            DROP TABLE IF EXISTS workflow_runs;

            CREATE TABLE workflow_runs (
                run_id TEXT PRIMARY KEY,
                generated_at_utc TEXT NOT NULL,
                schema_version TEXT NOT NULL,
                source_authority TEXT NOT NULL,
                route_count INTEGER NOT NULL,
                authority_json TEXT NOT NULL,
                source_active_workflows_mtime_ns INTEGER,
                source_control_overrides_mtime_ns INTEGER
            );

            CREATE TABLE workflow_routes (
                workflow_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                tier TEXT NOT NULL,
                current_state TEXT NOT NULL,
                next_action TEXT NOT NULL,
                continuity_note TEXT,
                primary_route_artifact TEXT,
                primary_pending INTEGER NOT NULL,
                last_validated_at TEXT,
                authority_boundary TEXT NOT NULL,
                owner_action_required INTEGER NOT NULL,
                safe_for_helper_lane INTEGER NOT NULL,
                default_resume_command TEXT,
                priority TEXT NOT NULL,
                lifecycle TEXT NOT NULL,
                readiness TEXT NOT NULL,
                authority_class TEXT NOT NULL,
                primary_owner_lane TEXT NOT NULL,
                human_approval_owner TEXT NOT NULL,
                proof_artifact TEXT,
                authoritative_next_action TEXT NOT NULL,
                freshness_sla_json TEXT NOT NULL,
                freshness_score TEXT,
                freshness_primary_artifact_age_hours REAL,
                freshness_continuity_note_age_hours REAL,
                freshness_primary_artifact_mtime_ns INTEGER,
                freshness_continuity_note_mtime_ns INTEGER,
                validator_count INTEGER NOT NULL
            );

            CREATE TABLE workflow_route_aliases (
                alias_key TEXT PRIMARY KEY,
                alias TEXT NOT NULL,
                workflow_id TEXT NOT NULL,
                alias_kind TEXT NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_artifacts (
                workflow_id TEXT NOT NULL,
                artifact_role TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                exists_on_disk INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_validators (
                workflow_id TEXT NOT NULL,
                validator_command TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_blockers (
                workflow_id TEXT NOT NULL,
                blocker TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_stop_lines (
                workflow_id TEXT NOT NULL,
                stop_line TEXT NOT NULL,
                ordinal INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_freshness (
                workflow_id TEXT PRIMARY KEY,
                score TEXT NOT NULL,
                continuity_note_age_hours REAL,
                primary_artifact_age_hours REAL,
                validator_count INTEGER NOT NULL,
                has_next_action INTEGER NOT NULL,
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE TABLE workflow_authority (
                workflow_id TEXT NOT NULL,
                flag TEXT NOT NULL,
                value INTEGER NOT NULL,
                PRIMARY KEY(workflow_id, flag),
                FOREIGN KEY(workflow_id) REFERENCES workflow_routes(workflow_id)
            );

            CREATE INDEX idx_workflow_routes_tier ON workflow_routes(tier);
            CREATE INDEX idx_workflow_routes_freshness ON workflow_routes(freshness_score);
            CREATE INDEX idx_workflow_routes_helper ON workflow_routes(safe_for_helper_lane);
            CREATE INDEX idx_workflow_routes_owner ON workflow_routes(owner_action_required);
            CREATE INDEX idx_workflow_routes_readiness ON workflow_routes(readiness);
            CREATE INDEX idx_workflow_routes_lifecycle ON workflow_routes(lifecycle);
            CREATE INDEX idx_workflow_route_aliases_workflow ON workflow_route_aliases(workflow_id);
            """
        )

        run_id = f"workflow-routing-index-{index.get('generated_at_utc')}"
        con.execute(
            """
            INSERT INTO workflow_runs
            (run_id, generated_at_utc, schema_version, source_authority, route_count, authority_json,
             source_active_workflows_mtime_ns, source_control_overrides_mtime_ns)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                index.get("generated_at_utc"),
                index.get("schema_version"),
                index.get("source_authority"),
                index.get("summary", {}).get("route_count", 0),
                json.dumps(index.get("authority", {}), sort_keys=True),
                index.get("source_freshness", {}).get("active_workflows_mtime_ns"),
                index.get("source_freshness", {}).get("control_overrides_mtime_ns"),
            ),
        )

        for r in index.get("routes", []):
            f = r.get("freshness") or {}
            con.execute(
                """
                INSERT INTO workflow_routes
                (workflow_id, display_name, tier, current_state, next_action,
                 continuity_note, primary_route_artifact, primary_pending,
                 last_validated_at, authority_boundary, owner_action_required,
                 safe_for_helper_lane, default_resume_command, priority, lifecycle,
                 readiness, authority_class, primary_owner_lane, human_approval_owner,
                 proof_artifact, authoritative_next_action, freshness_sla_json, freshness_score,
                 freshness_primary_artifact_age_hours,
                 freshness_continuity_note_age_hours, freshness_primary_artifact_mtime_ns,
                 freshness_continuity_note_mtime_ns, validator_count)
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12,
                        ?13, ?14, ?15, ?16, ?17, ?18, ?19, ?20, ?21, ?22,
                        ?23, ?24, ?25, ?26, ?27, ?28)
                """,
                (
                    r["workflow_id"],
                    r["display_name"],
                    r["tier"],
                    r["current_state"],
                    r["next_action"],
                    r.get("continuity_note"),
                    r.get("primary_route_artifact"),
                    1 if r.get("primary_pending") else 0,
                    r.get("last_validated_at"),
                    r["authority_boundary"],
                    1 if r.get("owner_action_required") else 0,
                    1 if r.get("safe_for_helper_lane") else 0,
                    r.get("default_resume_command"),
                    r["priority"],
                    r["lifecycle"],
                    r["readiness"],
                    r["authority_class"],
                    r["primary_owner_lane"],
                    r["human_approval_owner"],
                    r.get("proof_artifact"),
                    r["authoritative_next_action"],
                    json.dumps(r.get("freshness_sla") or {}, sort_keys=True),
                    f.get("score"),
                    f.get("primary_artifact_age_hours"),
                    f.get("continuity_note_age_hours"),
                    f.get("primary_artifact_mtime_ns"),
                    f.get("continuity_note_mtime_ns"),
                    len(r.get("validator_commands") or []),
                ),
            )

            for alias in route_alias_records(r):
                con.execute(
                    """
                    INSERT INTO workflow_route_aliases
                    (alias_key, alias, workflow_id, alias_kind)
                    VALUES (?, ?, ?, ?)
                    """,
                    (alias["alias_key"], alias["alias"], r["workflow_id"], alias["alias_kind"]),
                )

            artifacts: list[tuple[str, str | None]] = [
                ("continuity_note", r.get("continuity_note")),
                ("primary_route_artifact", r.get("primary_route_artifact")),
            ]
            artifacts.extend(("secondary_artifact", p) for p in r.get("secondary_artifacts", []))
            for ordinal, (role, artifact) in enumerate(artifacts):
                if not artifact:
                    continue
                con.execute(
                    """
                    INSERT INTO workflow_artifacts
                    (workflow_id, artifact_role, artifact_path, ordinal, exists_on_disk)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (r["workflow_id"], role, artifact, ordinal, 1 if exists_on_disk(artifact) else 0),
                )

            for ordinal, command in enumerate(r.get("validator_commands") or []):
                con.execute(
                    "INSERT INTO workflow_validators VALUES (?, ?, ?)",
                    (r["workflow_id"], command, ordinal),
                )
            for ordinal, blocker in enumerate(r.get("blockers") or []):
                con.execute(
                    "INSERT INTO workflow_blockers VALUES (?, ?, ?)",
                    (r["workflow_id"], blocker, ordinal),
                )
            for ordinal, stop_line in enumerate(r.get("stop_lines") or []):
                con.execute(
                    "INSERT INTO workflow_stop_lines VALUES (?, ?, ?)",
                    (r["workflow_id"], stop_line, ordinal),
                )
            con.execute(
                """
                INSERT INTO workflow_freshness
                (workflow_id, score, continuity_note_age_hours,
                 primary_artifact_age_hours, validator_count, has_next_action)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    r["workflow_id"],
                    f.get("score"),
                    f.get("continuity_note_age_hours"),
                    f.get("primary_artifact_age_hours"),
                    f.get("validator_count", 0),
                    1 if f.get("has_next_action") else 0,
                ),
            )
            for flag, expected in AUTHORITY.items():
                con.execute(
                    "INSERT INTO workflow_authority VALUES (?, ?, ?)",
                    (r["workflow_id"], flag, 1 if expected else 0),
                )
        con.commit()

        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = len(con.execute("PRAGMA foreign_key_check").fetchall())
        route_count = con.execute("SELECT COUNT(*) FROM workflow_routes").fetchone()[0]

    return {
        "db_path": relpath(db_path),
        "status": "ok" if integrity == "ok" and fk_errors == 0 else "blocked",
        "integrity_check": integrity,
        "foreign_key_errors": fk_errors,
        "route_count": route_count,
        "authority_boundary": "Derived/rebuildable workflow route lookup only; JSON and Active Workflows remain authority.",
    }


def validate_sqlite_index(index: dict[str, Any], db_path: Path) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if not db_path.exists():
        return {
            "status": "blocked",
            "db_path": relpath(db_path),
            "summary": {"critical": 1, "warning": 0},
            "findings": [{
                "severity": "critical",
                "check": "db_exists",
                "issue": "requested SQLite route index does not exist",
            }],
        }

    with sqlite3.connect(db_path, timeout=5) as con:
        con.execute("PRAGMA busy_timeout = 5000")
        con.row_factory = sqlite3.Row
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            findings.append({
                "severity": "critical",
                "check": "integrity_check",
                "issue": "SQLite integrity_check failed",
                "value": integrity,
            })
        fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
        if fk_errors:
            findings.append({
                "severity": "critical",
                "check": "foreign_key_check",
                "issue": "SQLite foreign_key_check returned rows",
                "count": len(fk_errors),
            })

        route_count = con.execute("SELECT COUNT(*) FROM workflow_routes").fetchone()[0]
        expected_count = index.get("summary", {}).get("route_count")
        if route_count != expected_count:
            findings.append({
                "severity": "critical",
                "check": "route_count",
                "issue": "SQLite route count must match JSON route count",
                "expected": expected_count,
                "actual": route_count,
            })

        run = con.execute(
            """
            SELECT source_active_workflows_mtime_ns, source_control_overrides_mtime_ns
            FROM workflow_runs
            ORDER BY generated_at_utc DESC
            LIMIT 1
            """
        ).fetchone()
        expected_sources = index.get("source_freshness", {})
        if run is None:
            findings.append({
                "severity": "critical",
                "check": "source_freshness",
                "issue": "SQLite index must include a workflow_runs freshness snapshot",
            })
        else:
            actual_sources = {
                "active_workflows_mtime_ns": run["source_active_workflows_mtime_ns"],
                "control_overrides_mtime_ns": run["source_control_overrides_mtime_ns"],
            }
            if actual_sources != expected_sources:
                findings.append({
                    "severity": "critical",
                    "check": "source_freshness",
                    "issue": "SQLite canonical control-source snapshot must match JSON index",
                    "expected": expected_sources,
                    "actual": actual_sources,
                })

        tier_counts = {
            row["tier"]: row["count"]
            for row in con.execute("SELECT tier, COUNT(*) AS count FROM workflow_routes GROUP BY tier")
        }
        if tier_counts != index.get("summary", {}).get("tier_counts"):
            findings.append({
                "severity": "critical",
                "check": "tier_counts",
                "issue": "SQLite tier counts must match JSON tier counts",
                "expected": index.get("summary", {}).get("tier_counts"),
                "actual": tier_counts,
            })

        stored_contracts = {
            row["workflow_id"]: {
                "priority": row["priority"],
                "lifecycle": row["lifecycle"],
                "readiness": row["readiness"],
                "authority_class": row["authority_class"],
                "primary_owner_lane": row["primary_owner_lane"],
                "human_approval_owner": row["human_approval_owner"],
                "proof_artifact": row["proof_artifact"],
                "authoritative_next_action": row["authoritative_next_action"],
                "freshness_sla": json.loads(row["freshness_sla_json"]),
            }
            for row in con.execute(
                """
                SELECT workflow_id, priority, lifecycle, readiness, authority_class,
                       primary_owner_lane, human_approval_owner, proof_artifact,
                       authoritative_next_action, freshness_sla_json
                FROM workflow_routes
                """
            )
        }
        for route in index.get("routes", []):
            expected_contract = {
                key: route.get(key)
                for key in (
                    "priority", "lifecycle", "readiness", "authority_class",
                    "primary_owner_lane", "human_approval_owner", "proof_artifact",
                    "authoritative_next_action", "freshness_sla",
                )
            }
            if stored_contracts.get(route.get("workflow_id")) != expected_contract:
                findings.append({
                    "severity": "critical",
                    "workflow_id": route.get("workflow_id"),
                    "check": "routing_contract",
                    "issue": "SQLite route contract must match the JSON-derived route contract",
                })

        freshness_counts = {
            row["freshness_score"]: row["count"]
            for row in con.execute(
                "SELECT freshness_score, COUNT(*) AS count FROM workflow_routes GROUP BY freshness_score"
            )
        }
        if freshness_counts != index.get("summary", {}).get("freshness_counts"):
            findings.append({
                "severity": "critical",
                "check": "freshness_counts",
                "issue": "SQLite freshness counts must match JSON freshness counts",
                "expected": index.get("summary", {}).get("freshness_counts"),
                "actual": freshness_counts,
            })

        expected_aliases = {
            (alias["alias_key"], route["workflow_id"], alias["alias_kind"])
            for route in index.get("routes", [])
            for alias in route_alias_records(route)
        }
        actual_aliases = {
            (row["alias_key"], row["workflow_id"], row["alias_kind"])
            for row in con.execute(
                "SELECT alias_key, workflow_id, alias_kind FROM workflow_route_aliases"
            )
        }
        if actual_aliases != expected_aliases:
            findings.append({
                "severity": "critical",
                "check": "exact_aliases",
                "issue": "SQLite exact lookup aliases must match the JSON route aliases",
                "expected_count": len(expected_aliases),
                "actual_count": len(actual_aliases),
            })

        stored_freshness = {
            row["workflow_id"]: {
                "primary_artifact_mtime_ns": row["freshness_primary_artifact_mtime_ns"],
                "continuity_note_mtime_ns": row["freshness_continuity_note_mtime_ns"],
            }
            for row in con.execute(
                """
                SELECT workflow_id, freshness_primary_artifact_mtime_ns,
                       freshness_continuity_note_mtime_ns
                FROM workflow_routes
                """
            )
        }
        for route in index.get("routes", []):
            expected_freshness = route.get("freshness") or {}
            actual_freshness = stored_freshness.get(route.get("workflow_id"))
            if actual_freshness != {
                "primary_artifact_mtime_ns": expected_freshness.get("primary_artifact_mtime_ns"),
                "continuity_note_mtime_ns": expected_freshness.get("continuity_note_mtime_ns"),
            }:
                findings.append({
                    "severity": "critical",
                    "workflow_id": route.get("workflow_id"),
                    "check": "freshness_snapshot",
                    "issue": "SQLite route freshness snapshot must match JSON route freshness",
                })

        authority_rows = con.execute(
            "SELECT workflow_id, flag, value FROM workflow_authority"
        ).fetchall()
        expected_authority_rows = expected_count * len(AUTHORITY)
        if len(authority_rows) != expected_authority_rows:
            findings.append({
                "severity": "critical",
                "check": "authority_row_count",
                "issue": "Every route must carry every authority flag",
                "expected": expected_authority_rows,
                "actual": len(authority_rows),
            })
        for row in authority_rows:
            expected = 1 if AUTHORITY.get(row["flag"]) else 0
            if row["value"] != expected:
                findings.append({
                    "severity": "critical",
                    "workflow_id": row["workflow_id"],
                    "check": "authority_clamp",
                    "issue": f"authority flag {row['flag']} drifted",
                    "expected": expected,
                    "actual": row["value"],
                })

    critical = sum(1 for f in findings if f["severity"] == "critical")
    warning = sum(1 for f in findings if f["severity"] == "warning")
    return {
        "status": "ok" if critical == 0 else "blocked",
        "db_path": relpath(db_path),
        "summary": {
            "critical": critical,
            "warning": warning,
            "route_count": route_count if "route_count" in locals() else None,
            "tier_counts": tier_counts if "tier_counts" in locals() else None,
            "freshness_counts": freshness_counts if "freshness_counts" in locals() else None,
        },
        "findings": findings,
    }


def _sql_route_dict(row: sqlite3.Row) -> dict[str, Any]:
    payload = {
        "workflow_id": row["workflow_id"],
        "display_name": row["display_name"],
        "tier": row["tier"],
        "priority": row["priority"],
        "lifecycle": row["lifecycle"],
        "readiness": row["readiness"],
        "current_state": row["current_state"],
        "next_action": row["next_action"],
        "authoritative_next_action": row["authoritative_next_action"],
        "freshness_score": row["freshness_score"],
        "owner_action_required": bool(row["owner_action_required"]),
        "safe_for_helper_lane": bool(row["safe_for_helper_lane"]),
        "authority_boundary": row["authority_boundary"],
        "authority_class": row["authority_class"],
        "primary_owner_lane": row["primary_owner_lane"],
        "human_approval_owner": row["human_approval_owner"],
        "proof_artifact": row["proof_artifact"],
        "default_resume_command": row["default_resume_command"],
    }
    if "matched_alias" in row.keys():
        payload["matched_alias"] = row["matched_alias"]
    return payload


class SqlIndexStaleError(RuntimeError):
    def __init__(self, reasons: list[dict[str, Any]]):
        super().__init__("derived SQLite workflow index is stale")
        self.reasons = reasons


def _sqlite_staleness_reasons(
    con: sqlite3.Connection,
    rows: list[sqlite3.Row],
) -> list[dict[str, Any]]:
    """Check only the small control sources plus the returned rows' proof mtimes."""
    reasons: list[dict[str, Any]] = []
    try:
        run = con.execute(
            """
            SELECT source_active_workflows_mtime_ns, source_control_overrides_mtime_ns
            FROM workflow_runs
            ORDER BY generated_at_utc DESC
            LIMIT 1
            """
        ).fetchone()
    except sqlite3.DatabaseError as exc:
        return [{
            "check": "sqlite_schema",
            "issue": "SQLite route index lacks the exact-alias/freshness schema",
            "detail": str(exc),
        }]

    if run is None:
        return [{
            "check": "workflow_run",
            "issue": "SQLite route index has no source freshness snapshot",
        }]

    current_sources = source_freshness_snapshot()
    stored_sources = {
        "active_workflows_mtime_ns": run["source_active_workflows_mtime_ns"],
        "control_overrides_mtime_ns": run["source_control_overrides_mtime_ns"],
    }
    for key, current in current_sources.items():
        if stored_sources.get(key) != current:
            reasons.append({
                "check": "canonical_control_source",
                "source": key,
                "stored_mtime_ns": stored_sources.get(key),
                "current_mtime_ns": current,
            })

    for row in rows:
        primary_current = (
            None
            if row["primary_pending"]
            or str(row["primary_route_artifact"] or "").replace("\\", "/").casefold()
            == INDEX_OUT.relative_to(ROOT).as_posix().casefold()
            else _mtime_ns(row["primary_route_artifact"])
        )
        continuity_current = _mtime_ns(row["continuity_note"])
        checks = (
            (
                "primary_route_artifact",
                row["freshness_primary_artifact_mtime_ns"],
                primary_current,
            ),
            (
                "continuity_note",
                row["freshness_continuity_note_mtime_ns"],
                continuity_current,
            ),
        )
        for field, stored, current in checks:
            if stored != current:
                reasons.append({
                    "check": "route_freshness_source",
                    "workflow_id": row["workflow_id"],
                    "field": field,
                    "stored_mtime_ns": stored,
                    "current_mtime_ns": current,
                })
    return reasons


def _assert_sqlite_index_current(con: sqlite3.Connection, rows: list[sqlite3.Row]) -> None:
    reasons = _sqlite_staleness_reasons(con, rows)
    if reasons:
        raise SqlIndexStaleError(reasons)


def sql_route_lookup(db_path: Path, query: str) -> dict[str, Any] | None:
    alias_key = normalize_lookup_key(query)
    if not alias_key:
        return None
    try:
        with sqlite3.connect(db_path, timeout=5) as con:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA busy_timeout = 5000")
            con.execute("PRAGMA query_only = ON")
            row = con.execute(
                """
                SELECT r.*, a.alias AS matched_alias
                FROM workflow_route_aliases AS a
                JOIN workflow_routes AS r ON r.workflow_id = a.workflow_id
                WHERE a.alias_key = ?
                """,
                (alias_key,),
            ).fetchone()
            _assert_sqlite_index_current(con, [row] if row is not None else [])
    except SqlIndexStaleError:
        raise
    except sqlite3.DatabaseError as exc:
        raise SqlIndexStaleError([{
            "check": "sqlite_read",
            "issue": "could not safely read the SQLite workflow index",
            "detail": str(exc),
        }]) from exc
    return _sql_route_dict(row) if row is not None else None


def sql_query(db_path: Path, mode: str) -> list[dict[str, Any]]:
    query_map = {
        "list": "SELECT * FROM workflow_routes ORDER BY tier, workflow_id",
        "freshness": "SELECT * FROM workflow_routes ORDER BY freshness_score, tier, workflow_id",
        "next_actions": "SELECT * FROM workflow_routes WHERE next_action <> '' ORDER BY tier, workflow_id",
        "helper_safe": "SELECT * FROM workflow_routes WHERE safe_for_helper_lane = 1 ORDER BY tier, workflow_id",
        "owner_gated": "SELECT * FROM workflow_routes WHERE owner_action_required = 1 ORDER BY tier, workflow_id",
    }
    try:
        with sqlite3.connect(db_path, timeout=5) as con:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA busy_timeout = 5000")
            con.execute("PRAGMA query_only = ON")
            rows = con.execute(query_map[mode]).fetchall()
            _assert_sqlite_index_current(con, rows)
    except SqlIndexStaleError:
        raise
    except sqlite3.DatabaseError as exc:
        raise SqlIndexStaleError([{
            "check": "sqlite_read",
            "issue": "could not safely read the SQLite workflow index",
            "detail": str(exc),
        }]) from exc
    return [_sql_route_dict(row) for row in rows]


def find_route(index: dict[str, Any], query: str) -> dict[str, Any] | None:
    """Resolve only an exact normalized id, display name, or declared alias."""
    alias_key = normalize_lookup_key(query)
    if not alias_key:
        return None
    matches = [
        route_row
        for route_row in index.get("routes", [])
        if any(alias["alias_key"] == alias_key for alias in route_alias_records(route_row))
    ]
    return matches[0] if len(matches) == 1 else None


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return value if isinstance(value, dict) else {}


def route_contract_projection(route_row: dict[str, Any]) -> dict[str, Any]:
    """The exact cross-surface fields that must stay in parity."""
    return {
        key: route_row.get(key)
        for key in (
            "workflow_id", "tier", "priority", "lifecycle", "readiness",
            "current_state", "next_action", "authoritative_next_action",
            "authority_class", "primary_owner_lane", "human_approval_owner",
            "proof_artifact",
        )
    }


def _capsule_path(workflow_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9._-]+", "-", workflow_id.strip())
    return CAPSULE_DIR / f"{safe}.json"


def validate_route_parity(index: dict[str, Any]) -> dict[str, Any]:
    """Validate the canonical projection across generated route consumers.

    The page and override registry are control inputs.  Capsules, the lookup
    index, and the status card are derived mirrors and must agree exactly on
    the normalized state contract.  This is deliberately a report-only gate.
    """
    findings: list[dict[str, Any]] = []
    routes = [row for row in index.get("routes", []) if isinstance(row, dict)]
    status_payload = _load_object(STATUS_CARD_OUT)
    status_routing = status_payload.get("workflow_routing")
    status_routing = status_routing if isinstance(status_routing, dict) else {}
    status_routes = {
        str(row.get("workflow_id")): row
        for row in status_routing.get("routes", [])
        if isinstance(row, dict) and row.get("workflow_id")
    }
    canonical_checked = 0
    for route_row in routes:
        workflow_id = str(route_row.get("workflow_id") or "")
        expected = route_contract_projection(route_row)
        reconciliation = route_row.get("state_reconciliation")
        if isinstance(reconciliation, dict):
            canonical_checked += 1
            canonical_projection = {
                "tier": reconciliation.get("canonical_tier"),
                "current_state": reconciliation.get("canonical_current_state"),
                "next_action": reconciliation.get("canonical_next_action"),
            }
            if any(expected.get(key) != value for key, value in canonical_projection.items()):
                findings.append({
                    "severity": "critical",
                    "workflow_id": workflow_id,
                    "surface": "Active Workflows/workflow-control-overrides",
                    "check": "canonical_projection",
                    "issue": "derived route fields disagree with reconciled canonical control state",
                    "expected": canonical_projection,
                    "actual": {key: expected.get(key) for key in canonical_projection},
                })

        capsule_path = _capsule_path(workflow_id)
        capsule = _load_object(capsule_path)
        if not capsule:
            findings.append({
                "severity": "critical", "workflow_id": workflow_id,
                "surface": "workflow_router/state capsule", "check": "capsule_exists",
                "issue": "derived workflow capsule is missing or unreadable",
                "path": relpath(capsule_path),
            })
        elif route_contract_projection(capsule) != expected:
            findings.append({
                "severity": "critical", "workflow_id": workflow_id,
                "surface": "workflow_router/state capsule", "check": "contract_parity",
                "issue": "router capsule does not match the generated route contract",
            })

        status_route = status_routes.get(workflow_id)
        if status_route is None:
            findings.append({
                "severity": "critical", "workflow_id": workflow_id,
                "surface": "status_card", "check": "route_visible",
                "issue": "full status card does not expose the route contract projection",
            })
        elif route_contract_projection(status_route) != expected:
            findings.append({
                "severity": "critical", "workflow_id": workflow_id,
                "surface": "status_card", "check": "contract_parity",
                "issue": "status-card route projection does not match the generated route contract",
            })

    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    return {
        "schema": "veritas.workflow_routing_parity.v1",
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "ok" if critical == 0 else "blocked",
        "authority_boundary": "Parity validation is report-only; control state remains Active Workflows plus workflow-control-overrides.",
        "sources": {
            "canonical_control": [ACTIVE_WORKFLOWS_REL, CONTROL_OVERRIDES_REL],
            "route_index": relpath(INDEX_OUT),
            "capsules": relpath(CAPSULE_DIR),
            "status_card": relpath(STATUS_CARD_OUT),
        },
        "summary": {
            "routes_checked": len(routes),
            "canonical_rows_checked": canonical_checked,
            "critical": critical,
        },
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build the derived workflow routing index (review-only)."
    )
    parser.add_argument("--write", action="store_true", help="Write the routing index JSON.")
    parser.add_argument("--validate", action="store_true", help="Write the validation JSON.")
    parser.add_argument("--validate-parity", action="store_true", help="Validate route state parity across canonical controls, capsules, and the full status card.")
    parser.add_argument("--route", metavar="WORKFLOW", help="Print one route object (by workflow_id or display name) and exit.")
    parser.add_argument("--list", action="store_true", help="Print a compact id/tier/state/next-action listing and exit.")
    parser.add_argument("--handoff", metavar="WORKFLOW", help="Build a bounded helper-lane handoff packet for one route (use with --write to save).")
    parser.add_argument("--freshness", action="store_true", help="Print a compact per-route freshness listing and exit.")
    parser.add_argument("--write-db", action="store_true", help="Write derived SQLite route lookup DB.")
    parser.add_argument("--db", help=f"SQLite DB path for --write-db/--sql-* (default {relpath(DB_OUT)}).")
    parser.add_argument("--sql-route", metavar="WORKFLOW", help="Read one route from the derived SQLite lookup DB.")
    parser.add_argument("--sql-list", action="store_true", help="List routes from the derived SQLite lookup DB.")
    parser.add_argument("--sql-freshness", action="store_true", help="List freshness from the derived SQLite lookup DB.")
    parser.add_argument("--sql-next-actions", action="store_true", help="List next actions from the derived SQLite lookup DB.")
    parser.add_argument("--sql-helper-safe", action="store_true", help="List helper-safe routes from the derived SQLite lookup DB.")
    parser.add_argument("--sql-owner-gated", action="store_true", help="List owner-gated routes from the derived SQLite lookup DB.")
    args = parser.parse_args()

    db_path = _db_path(args.db)
    sql_modes = [
        (args.sql_list, "list"),
        (args.sql_freshness, "freshness"),
        (args.sql_next_actions, "next_actions"),
        (args.sql_helper_safe, "helper_safe"),
        (args.sql_owner_gated, "owner_gated"),
    ]
    selected_sql_modes = [mode for selected, mode in sql_modes if selected]
    if len(selected_sql_modes) > 1:
        print(json.dumps({"error": "choose_one_sql_query_mode"}, indent=2))
        return 1

    if args.sql_route:
        if not db_path.exists():
            print(json.dumps({"error": "db_not_found", "db_path": relpath(db_path)}, indent=2))
            return 1
        try:
            match = sql_route_lookup(db_path, args.sql_route)
        except SqlIndexStaleError as exc:
            print(json.dumps({
                "error": "sql_index_stale",
                "db_path": relpath(db_path),
                "reasons": exc.reasons,
                "refresh_command": "python scripts\\workflow_routing_index.py --write --write-db --validate",
            }, indent=2))
            return 1
        if match is None:
            print(json.dumps({"error": "route_not_found", "query": args.sql_route}, indent=2))
            return 1
        print(json.dumps(match, indent=2))
        return 0

    if selected_sql_modes:
        if not db_path.exists():
            print(json.dumps({"error": "db_not_found", "db_path": relpath(db_path)}, indent=2))
            return 1
        try:
            payload = {
                "db_path": relpath(db_path),
                "mode": selected_sql_modes[0],
                "authority": dict(AUTHORITY),
                "rows": sql_query(db_path, selected_sql_modes[0]),
            }
        except SqlIndexStaleError as exc:
            print(json.dumps({
                "error": "sql_index_stale",
                "db_path": relpath(db_path),
                "reasons": exc.reasons,
                "refresh_command": "python scripts\\workflow_routing_index.py --write --write-db --validate",
            }, indent=2))
            return 1
        print(json.dumps(payload, indent=2))
        return 0

    if args.validate_parity and not any((args.write, args.validate, args.write_db, args.route, args.list, args.freshness, args.handoff)):
        persisted = _load_object(INDEX_OUT)
        if not persisted:
            print(json.dumps({"error": "routing_index_not_found", "path": relpath(INDEX_OUT)}, indent=2))
            return 1
        parity = validate_route_parity(persisted)
        PARITY_OUT.write_text(json.dumps(parity, indent=2) + "\n", encoding="utf-8")
        print(
            f"wrote {relpath(PARITY_OUT)}: {parity['status']} "
            f"({parity['summary']['routes_checked']} routes, {parity['summary']['critical']} critical)"
        )
        return 0 if parity["status"] == "ok" else 1

    index = build_index()

    if args.route:
        match = find_route(index, args.route)
        if match is None:
            print(json.dumps({"error": "route_not_found", "query": args.route}, indent=2))
            return 1
        print(json.dumps(match, indent=2))
        return 0

    if args.list:
        for r in index["routes"]:
            print(f"{r['tier']:<3} {r['workflow_id']:<26} {r['display_name']}")
            print(f"      next: {r['next_action']}")
        return 0

    if args.freshness:
        fc = index["summary"]["freshness_counts"]
        print("freshness_counts: " + json.dumps(fc))
        for r in index["routes"]:
            f = r["freshness"]
            print(
                f"{f['score']:<8} {r['tier']:<3} {r['workflow_id']:<26} "
                f"primary={f['primary_artifact_age_hours']}h "
                f"note={f['continuity_note_age_hours']}h "
                f"validators={f['validator_count']}"
            )
        return 0

    if args.handoff:
        match = find_route(index, args.handoff)
        if match is None:
            print(json.dumps({"error": "route_not_found", "query": args.handoff}, indent=2))
            return 1
        packet = build_handoff(match)
        if args.write:
            safe_id = "".join(c if (c.isalnum() or c in "-_") else "-" for c in str(match["workflow_id"])).lower()
            out = HANDOFF_DIR / f"workflow-routing-handoff-{safe_id}.json"
            out.write_text(json.dumps(packet, indent=2) + "\n", encoding="utf-8")
            print(f"wrote {relpath(out)} ({packet['mode']})")
        else:
            print(json.dumps(packet, indent=2))
        return 0

    if args.write:
        INDEX_OUT.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {relpath(INDEX_OUT)} ({index['summary']['route_count']} routes)")

    db_report: dict[str, Any] | None = None
    if args.write_db:
        db_report = write_sqlite_index(index, db_path)
        print(
            f"wrote {db_report['db_path']}: {db_report['status']} "
            f"({db_report['route_count']} routes, integrity={db_report['integrity_check']}, "
            f"fk_errors={db_report['foreign_key_errors']})"
        )

    rc = 0
    if args.validate:
        report = validate_index(index)
        if args.write_db:
            report["sqlite"] = validate_sqlite_index(index, db_path)
            if report["sqlite"]["status"] != "ok":
                report["status"] = "blocked"
                report["summary"]["critical"] += report["sqlite"]["summary"]["critical"]
                report["summary"]["warning"] += report["sqlite"]["summary"]["warning"]
        VALIDATION_OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        s = report["summary"]
        print(
            f"wrote {relpath(VALIDATION_OUT)}: {report['status']} "
            f"({s['routes_checked']} routes, {s['critical']} critical, {s['warning']} warning)"
        )
        rc = 1 if s["critical"] else 0

    if args.validate_parity:
        # When combined with --write, validate the just-built state.  The
        # caller must have refreshed capsules and the status card first for a
        # clean result; otherwise this deliberately reports the stale mirror.
        parity = validate_route_parity(index)
        PARITY_OUT.write_text(json.dumps(parity, indent=2) + "\n", encoding="utf-8")
        print(
            f"wrote {relpath(PARITY_OUT)}: {parity['status']} "
            f"({parity['summary']['routes_checked']} routes, {parity['summary']['critical']} critical)"
        )
        if parity["status"] != "ok":
            rc = 1

    if not args.write and not args.validate and not args.write_db and not args.validate_parity:
        print(f"workflow_routing_index: {index['summary']['route_count']} routes (dry run; pass --write/--validate)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())

