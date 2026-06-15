"""Workflow control overrides shared by routing, PM, and heartbeat surfaces."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

ROOT = Path(__file__).resolve().parents[2]
STATE_DIR = ROOT / "state"
OVERRIDE_PATH = STATE_DIR / "workflow-control-overrides.json"
CAPSULE_DIR = STATE_DIR / "workflows"

SCHEMA = "veritas.workflow_control_overrides.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_key(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def empty_registry() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "authority_boundary": {
            "review_only": True,
            "routing_override_only": True,
            "canon_or_portfolio_mutation_allowed": False,
            "customer_or_external_delivery_allowed": False,
            "paper_or_live_execution_allowed": False,
            "brokerage_or_account_action_allowed": False,
            "owner_approval_inferred": False,
        },
        "overrides": {},
    }


def load_registry(path: Path = OVERRIDE_PATH) -> dict[str, Any]:
    payload = load_json_artifact(path)
    if not isinstance(payload, dict):
        return empty_registry()
    payload.setdefault("schema", SCHEMA)
    payload.setdefault("authority_boundary", empty_registry()["authority_boundary"])
    payload.setdefault("overrides", {})
    return payload


def save_registry(payload: dict[str, Any], path: Path = OVERRIDE_PATH) -> None:
    payload["schema"] = SCHEMA
    payload["generated_at_utc"] = utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(path, payload)


def aliases_for(workflow_id: str, lane_id: str | None = None, workflow_name: str | None = None) -> set[str]:
    aliases = {normalize_key(workflow_id)}
    if lane_id:
        aliases.add(normalize_key(lane_id))
    if workflow_name:
        aliases.add(normalize_key(workflow_name))
    return {item for item in aliases if item}


def find_override(
    workflow_id: str,
    *,
    lane_id: str | None = None,
    workflow_name: str | None = None,
    registry: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    payload = registry or load_registry()
    wanted = aliases_for(workflow_id, lane_id, workflow_name)
    for key, item in dict(payload.get("overrides", {})).items():
        if normalize_key(key) in wanted:
            return item if isinstance(item, dict) else None
        item_aliases = {normalize_key(alias) for alias in item.get("aliases", [])} if isinstance(item, dict) else set()
        if wanted & item_aliases:
            return item
    return None


def is_on_hold(override: dict[str, Any] | None) -> bool:
    return bool(override and override.get("status") == "on_hold")


def hold_override(
    workflow_key: str,
    *,
    reason: str,
    set_by: str = "Randall",
    set_at_local: str | None = None,
    resume_condition: str | None = None,
    aliases: list[str] | None = None,
    path: Path = OVERRIDE_PATH,
) -> dict[str, Any]:
    payload = load_registry(path)
    overrides = payload.setdefault("overrides", {})
    key = normalize_key(workflow_key)
    overrides[key] = {
        "status": "on_hold",
        "set_by": set_by,
        "set_at_local": set_at_local,
        "set_at_utc": utc_now(),
        "reason": reason,
        "resume_condition": resume_condition or f"Resume only after {set_by} explicitly restarts {workflow_key}.",
        "aliases": sorted({normalize_key(item) for item in (aliases or []) if normalize_key(item)}),
        "next_action": "Do not advance this workflow. Preserve artifacts and boundary proof only.",
    }
    save_registry(payload, path)
    return overrides[key]


def resume_override(workflow_key: str, *, path: Path = OVERRIDE_PATH) -> bool:
    payload = load_registry(path)
    key = normalize_key(workflow_key)
    removed = payload.get("overrides", {}).pop(key, None) is not None
    if not removed:
        for item_key, item in list(payload.get("overrides", {}).items()):
            aliases = {normalize_key(alias) for alias in item.get("aliases", [])} if isinstance(item, dict) else set()
            if key in aliases:
                payload["overrides"].pop(item_key, None)
                removed = True
                break
    if removed:
        save_registry(payload, path)
    return removed


def apply_route_override(route: dict[str, Any], registry: dict[str, Any] | None = None) -> dict[str, Any]:
    override = find_override(
        route.get("workflow_id", ""),
        workflow_name=route.get("display_name"),
        registry=registry,
    )
    if not is_on_hold(override):
        return route
    updated = dict(route)
    updated["control_override"] = override
    updated["current_state"] = f"On hold. {route.get('current_state', '')}".strip()
    updated["next_action"] = override.get("next_action") or "Do not advance this workflow until explicitly resumed."
    updated["safe_for_helper_lane"] = False
    blockers = list(updated.get("blockers", []))
    reason = override.get("reason") or "owner-paused"
    if reason not in blockers:
        blockers.append(reason)
    updated["blockers"] = blockers
    return updated


def validation_errors(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("schema_mismatch")
    boundary = payload.get("authority_boundary", {})
    for key, expected in empty_registry()["authority_boundary"].items():
        if boundary.get(key) is not expected:
            errors.append(f"authority_{key}_not_{str(expected).lower()}")
    for key, item in dict(payload.get("overrides", {})).items():
        if not isinstance(item, dict):
            errors.append(f"{key}:override_not_object")
            continue
        if item.get("status") not in {"on_hold"}:
            errors.append(f"{key}:unsupported_status")
        if not item.get("reason"):
            errors.append(f"{key}:missing_reason")
    return errors
