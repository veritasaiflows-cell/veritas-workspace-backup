#!/usr/bin/env python3
"""Fail-closed compatibility surface for retired finance orchestrators.

WF78 and the paper/execution workflows it fed are retired from the active
alerts-and-recommendations OS.  The small data classes and introspection
helpers remain importable so stale callers receive an explicit retirement
result instead of an import error, but every request for executable steps or
layers raises :class:`RetiredWorkflowError`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


RETIRED_WORKFLOW = "WF78"
RETIREMENT_REASON = (
    "WF78 orchestration is retired. Use scripts\\run_alerts_recommendations_chain.py "
    "with morning, midday, post-close, or weekly mode."
)


class RetiredWorkflowError(RuntimeError):
    """Raised when a caller requests an executable retired-workflow route."""


@dataclass(frozen=True)
class StepDef:
    name: str
    command: tuple[str, ...]
    timeout: int
    phase: str
    depends_on: tuple[str, ...] = field(default_factory=tuple)

    def runner_tuple(self) -> tuple[str, list[str], int]:
        return self.name, list(self.command), self.timeout


@dataclass(frozen=True)
class LayerDef:
    name: str
    purpose: str
    time_budget_seconds: int
    commands: tuple[StepDef, ...] = field(default_factory=tuple)
    phase: str | None = None
    expected_artifacts: tuple[str, ...] = field(default_factory=tuple)
    dependencies: dict[str, tuple[str, ...]] = field(default_factory=dict)


PHASE_ALIASES: dict[str, set[str]] = {}
LAYER_DEFS: dict[str, LayerDef] = {}
ALIASES: dict[str, list[str]] = {}


def _retired() -> None:
    raise RetiredWorkflowError(RETIREMENT_REASON)


def build_daily_steps(*, skip_provider_refresh: bool = True, full_answer_mode: str = "changed") -> list[StepDef]:
    del skip_provider_refresh, full_answer_mode
    _retired()


def selected_phases(raw_phases: list[str] | None) -> set[str]:
    del raw_phases
    _retired()


def steps_for_phases(
    raw_phases: list[str] | None,
    *,
    skip_provider_refresh: bool = True,
    full_answer_mode: str = "changed",
) -> tuple[list[StepDef], list[dict[str, Any]], set[str]]:
    del raw_phases, skip_provider_refresh, full_answer_mode
    _retired()


def steps_for_phase(
    phase: str,
    *,
    skip_provider_refresh: bool = True,
    full_answer_mode: str = "changed",
) -> list[StepDef]:
    del phase, skip_provider_refresh, full_answer_mode
    _retired()


def selected_layers(raw_layers: list[str] | None) -> list[str]:
    del raw_layers
    _retired()


def dependencies_for(steps: list[StepDef]) -> dict[str, tuple[str, ...]]:
    """Keep the generic dependency helper available for non-retired callers."""
    names = {step.name for step in steps}
    return {step.name: tuple(dep for dep in step.depends_on if dep in names) for step in steps}


def as_runner_tuples(steps: list[StepDef]) -> list[tuple[str, list[str], int]]:
    """Keep the generic tuple adapter available without creating any steps."""
    return [step.runner_tuple() for step in steps]


def structural_errors(raw_layers: list[str] | None = None) -> list[str]:
    del raw_layers
    return [f"retired_workflow:{RETIRED_WORKFLOW}"]


def manifest_summary(raw_layers: list[str] | None = None) -> dict[str, Any]:
    del raw_layers
    return {
        "status": "retired_fail_closed",
        "workflow_id": RETIRED_WORKFLOW,
        "daily_step_count": 0,
        "phase_counts": {},
        "selected_layers": [],
        "layer_count": 0,
        "structural_errors": structural_errors(),
        "replacement": {
            "owner": "Alerts and Recommendations OS",
            "command": "python scripts\\run_alerts_recommendations_chain.py midday --timeout-seconds 120 --write --validate",
            "execution_or_account_authority": False,
        },
        "retirement_reason": RETIREMENT_REASON,
    }
