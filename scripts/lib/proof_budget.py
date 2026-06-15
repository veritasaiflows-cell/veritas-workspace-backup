"""Proof-budget policy for implementation jobs.

The goal is to keep strict proof where blast radius requires it while avoiding
full closeout chains for local or low-blast jobs.
"""
from __future__ import annotations

from typing import Any


PROOF_BUDGETS: dict[str, dict[str, Any]] = {
    "micro": {
        "description": "Local/low-blast proof; no shared contract or authority behavior changed.",
        "phase_names": ["inspect", "validate"],
        "closeout_mode": "queue_only",
        "max_default_proof_commands": 1,
    },
    "narrow": {
        "description": "One owner plus one adjacent consumer or validator.",
        "phase_names": ["inspect", "build", "validate"],
        "closeout_mode": "pm_state",
        "max_default_proof_commands": 3,
    },
    "shared": {
        "description": "Shared JSON/state/router/control contract, but no apply/execution authority.",
        "phase_names": ["inspect", "build", "validate", "wire"],
        "closeout_mode": "handoff",
        "max_default_proof_commands": 5,
    },
    "major": {
        "description": "Workflow/control-plane or authority-adjacent contract change.",
        "phase_names": ["inspect", "build", "validate", "wire", "closeout"],
        "closeout_mode": "integration",
        "max_default_proof_commands": 99,
    },
}


CLASS_BUDGETS = {
    "bounded_review_only_action": "micro",
    "local_ui_control_surface": "narrow",
    "qa_validation_pass": "narrow",
    "pm_packet_refresh": "narrow",
    "finance_validation_pass": "narrow",
    "ticker_card_refresh_gate": "narrow",
    "sql_support_validation": "shared",
    "canonical_finance_data_plane": "shared",
    "service_state_slice": "narrow",
    "bounded_product_implementation": "shared",
    "parallel_overhead_reduction_orchestration": "shared",
    "narrow_validation_and_ui_visibility": "shared",
    "wf78_reputation_scaleout_gate": "major",
    "wf78_auto_router_consumer_sync": "major",
}


PHASE_DESCRIPTIONS = {
    "inspect": "Inspect owner surface and only the nearest required producer/consumer.",
    "build": "Apply the smallest bounded implementation or patch proposal.",
    "validate": "Run the proof commands required by this job's validation budget.",
    "wire": "Update PM/cockpit/queue/control references only when the contract changed.",
    "closeout": "Run integration closeout only for material workflow/control-plane changes.",
}


def classify_budget(implementation_class: str, proof_command_count: int = 0) -> str:
    budget = CLASS_BUDGETS.get(implementation_class, "narrow")
    if proof_command_count >= 6 and budget != "major":
        return "shared"
    return budget


def budget_policy(budget: str) -> dict[str, Any]:
    return dict(PROOF_BUDGETS.get(budget, PROOF_BUDGETS["narrow"]))


def scope_split(job_id: str, implementation_class: str, budget: str) -> list[dict[str, Any]]:
    policy = budget_policy(budget)
    return [
        {
            "phase_id": f"{job_id}-{name}",
            "name": name,
            "description": PHASE_DESCRIPTIONS[name],
            "required": True,
            "implementation_class": implementation_class,
            "validation_budget": budget,
        }
        for name in policy["phase_names"]
    ]


def closeout_commands(closeout_mode: str) -> list[str]:
    if closeout_mode == "queue_only":
        return [
            "python scripts\\pm_control_packet.py --write --validate",
        ]
    if closeout_mode == "pm_state":
        return [
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ]
    if closeout_mode == "handoff":
        return [
            "python scripts\\pm_control_packet.py --write --write-db --validate",
        ]
    return [
        "python scripts\\pm_control_packet.py --write --write-db --validate",
        "python scripts\\helper_completion_handshake.py --write --validate",
    ]


def validation_budget_contract(implementation_class: str, proof_commands: list[Any]) -> dict[str, Any]:
    budget = classify_budget(implementation_class, len(proof_commands))
    policy = budget_policy(budget)
    return {
        "budget": budget,
        "description": policy["description"],
        "closeout_mode": policy["closeout_mode"],
        "proof_command_count": len(proof_commands),
        "max_default_proof_commands": policy["max_default_proof_commands"],
        "phase_count": len(policy["phase_names"]),
    }
