"""Read the consolidated PM control packet.

Use this helper for routine PM state/queue/heartbeat/handoff reads. Legacy
sidecars are fallback-only so they can be retired without breaking old repair
tools.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from market_data_utils import load_json_artifact

ROOT = Path(__file__).resolve().parents[2]
TMP = ROOT / "tmp"

CONTROL_PACKET = TMP / "pm-control-packet.json"
LEGACY_PM_STATE = TMP / "pm-program-state.json"
LEGACY_PM_NEXT = TMP / "pm-next-actions.json"
LEGACY_JOB_QUEUE = TMP / "pm-implementation-job-queue.json"
LEGACY_HEARTBEAT = TMP / "heartbeat-continuation-candidates.json"
LEGACY_HANDOFF = TMP / "pm-main-session-handoff.json"


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def load_packet(path: Path = CONTROL_PACKET) -> dict[str, Any]:
    return as_dict(load_json_artifact(path))


def packet_section(section: str, fallback: Path | None = None, packet_path: Path = CONTROL_PACKET) -> dict[str, Any]:
    packet = load_packet(packet_path)
    sections = as_dict(packet.get("sections"))
    value = as_dict(sections.get(section))
    if value:
        return value
    return as_dict(load_json_artifact(fallback)) if fallback else {}


def pm_program_state() -> dict[str, Any]:
    return packet_section("pm_program_state", LEGACY_PM_STATE)


def pm_next_actions() -> dict[str, Any]:
    state = pm_program_state()
    if state:
        return {
            "schema": state.get("schema"),
            "status": state.get("status"),
            "generated_at_utc": state.get("generated_at_utc"),
            "next_actions": state.get("next_actions", []),
            "source": "tmp/pm-control-packet.json#sections.pm_program_state",
        }
    return as_dict(load_json_artifact(LEGACY_PM_NEXT))


def pm_implementation_job_queue() -> dict[str, Any]:
    return packet_section("pm_implementation_job_queue", LEGACY_JOB_QUEUE)


def heartbeat_candidates() -> dict[str, Any]:
    return packet_section("heartbeat_continuation_candidates", LEGACY_HEARTBEAT)


def main_session_handoff() -> dict[str, Any]:
    return packet_section("pm_main_session_handoff", LEGACY_HANDOFF)
