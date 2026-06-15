from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from chain_manifest import manifest_steps, window_description, window_names
from market_data_utils import atomic_write_json
from run_finance_refresh_chain import planned_run_args, resolved_steps

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = WORKSPACE / "scripts"
TMP_DIR = WORKSPACE / "tmp"
SCHEMA_VERSION = "layered-finance-refresh-chain-v1"

CANON_APPLY_SCRIPTS = {
    "auto_apply_entry_band_maintenance.py",
    "auto_apply_position_sizing_semantic_sync.py",
    "canon_volatile_execution_board_sync.py",
    "event_calendar_apply.py",
    "reference_band_note_sync.py",
}

AUTHORITY_BOUNDARY = {
    "review_only_scheduler": True,
    "replaces_serial_runner": False,
    "cron_enabled": False,
    "read_only_profile_allowed": True,
    "mutating_steps_skipped_when_requested": True,
    "capital_deployment_approved": False,
    "trade_or_execution_approved": False,
    "paper_execution_allowed": False,
    "live_execution_allowed": False,
    "owner_approval_inferred": False,
}


@dataclass(frozen=True)
class RecoveryPolicy:
    posture: str
    mode: str
    retries: int = 0


@dataclass(frozen=True)
class StepPlan:
    step_id: str
    index: int
    script: str
    args: tuple[str, ...]
    command: tuple[str, ...]
    category: str
    expected_outputs: tuple[str, ...]
    depends_on_scripts: tuple[str, ...]
    dependency_ids: tuple[str, ...]
    recovery: RecoveryPolicy
    write_surfaces: tuple[str, ...]
    mutating: bool
    signature: str

    def to_json(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "index": self.index,
            "script": self.script,
            "args": list(self.args),
            "command": list(self.command),
            "category": self.category,
            "expected_outputs": list(self.expected_outputs),
            "depends_on_scripts": list(self.depends_on_scripts),
            "dependency_ids": list(self.dependency_ids),
            "recovery_posture": self.recovery.posture,
            "recovery_mode": self.recovery.mode,
            "retries": self.recovery.retries,
            "write_surfaces": list(self.write_surfaces),
            "mutating": self.mutating,
            "signature": self.signature,
        }


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def state_path(window: str) -> Path:
    return TMP_DIR / f"layered-run-chain-{window}.json"


def plan_path(window: str) -> Path:
    return TMP_DIR / f"layered-finance-refresh-chain-plan-{window}.json"


def validation_path() -> Path:
    return TMP_DIR / "layered-finance-refresh-chain-validation.json"


def parse_recovery_policy(posture: str | None) -> RecoveryPolicy:
    raw = (posture or "fail_chain").strip()
    if raw.startswith("retry(") and raw.endswith(")"):
        value = raw[len("retry(") : -1]
        try:
            retries = int(value)
        except ValueError:
            return RecoveryPolicy(posture=raw, mode="fail_chain", retries=0)
        return RecoveryPolicy(posture=raw, mode="retry", retries=max(0, retries))
    if raw in {"skip_degraded", "isolate", "recovery_finalizer", "fail_chain"}:
        return RecoveryPolicy(posture=raw, mode=raw, retries=0)
    return RecoveryPolicy(posture=raw, mode="fail_chain", retries=0)


def _manifest_lookup(window: str) -> dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]]:
    lookup: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = {}
    for item in manifest_steps(window):
        key = (str(item["script"]), tuple(str(arg) for arg in item.get("args") or []))
        lookup.setdefault(key, []).append(item)
    return lookup


def _matching_manifest_item(
    lookup: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]],
    script: str,
    args: tuple[str, ...],
) -> dict[str, Any]:
    exact = lookup.get((script, args)) or []
    if exact:
        return exact.pop(0)
    script_only_keys = [key for key in lookup if key[0] == script and lookup[key]]
    if script_only_keys:
        return lookup[script_only_keys[0]].pop(0)
    return {
        "script": script,
        "args": list(args),
        "category": "synthetic",
        "expected_outputs": [],
        "depends_on": [],
        "recovery_posture": "fail_chain",
    }


def is_mutating_step(script: str, args: tuple[str, ...], category: str) -> bool:
    if "--apply" in args:
        return True
    if script in CANON_APPLY_SCRIPTS:
        return True
    return category == "portfolio" and any(arg.startswith("--apply") for arg in args)


def write_surfaces_for(script: str, args: tuple[str, ...], expected_outputs: tuple[str, ...], mutating: bool) -> tuple[str, ...]:
    surfaces: set[str] = set()
    for output in expected_outputs:
        normalized = output.replace("\\", "/")
        surfaces.add(f"path:{normalized}")
        if normalized.startswith("data/"):
            parts = normalized.split("/")
            if len(parts) >= 2:
                surfaces.add(f"data-family:{parts[1]}")
        if normalized.startswith("tmp/") and normalized.endswith(".sqlite"):
            surfaces.add(f"sqlite:{normalized}")
    if mutating:
        surfaces.add("canon-apply")
        surfaces.add(f"mutating-script:{script}")
    if "--write-db" in args:
        surfaces.add(f"db-writer:{script}")
    return tuple(sorted(surfaces))


def signature_for(record: dict[str, Any]) -> str:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_step_plans(window: str, strict: bool = False, build_workbook: bool = False, cleanup: bool = False) -> list[StepPlan]:
    lookup = _manifest_lookup(window)
    prior_by_script: dict[str, list[str]] = {}
    plans: list[StepPlan] = []
    for index, raw_step in enumerate(resolved_steps(window, build_workbook=build_workbook, cleanup=cleanup), start=1):
        script = str(raw_step[0])
        raw_args = tuple(str(arg) for arg in raw_step[1:])
        item = _matching_manifest_item(lookup, script, raw_args)
        run_args = tuple(planned_run_args([script, *raw_args], strict=strict))
        expected_outputs = tuple(str(path) for path in item.get("expected_outputs") or [])
        depends_on_scripts = tuple(str(dep) for dep in item.get("depends_on") or [])
        dependency_ids: list[str] = []
        for dep_script in depends_on_scripts:
            dependency_ids.extend(prior_by_script.get(dep_script, []))
        category = str(item.get("category") or "uncategorized")
        recovery = parse_recovery_policy(str(item.get("recovery_posture") or "fail_chain"))
        mutating = is_mutating_step(script, run_args, category)
        write_surfaces = write_surfaces_for(script, run_args, expected_outputs, mutating)
        step_id = f"{index:03d}:{script}"
        sig = signature_for(
            {
                "script": script,
                "args": run_args,
                "expected_outputs": expected_outputs,
                "depends_on_scripts": depends_on_scripts,
                "dependency_ids": dependency_ids,
                "recovery_posture": recovery.posture,
                "write_surfaces": write_surfaces,
            }
        )
        plan = StepPlan(
            step_id=step_id,
            index=index,
            script=script,
            args=run_args,
            command=(sys.executable, str(SCRIPTS_DIR / script), *run_args),
            category=category,
            expected_outputs=expected_outputs,
            depends_on_scripts=depends_on_scripts,
            dependency_ids=tuple(dependency_ids),
            recovery=recovery,
            write_surfaces=write_surfaces,
            mutating=mutating,
            signature=sig,
        )
        plans.append(plan)
        prior_by_script.setdefault(script, []).append(step_id)
    return plans


def _conflicts(candidate: StepPlan, used_surfaces: set[str]) -> bool:
    return bool(set(candidate.write_surfaces) & used_surfaces)


def build_execution_layers(plans: list[StepPlan]) -> list[list[str]]:
    by_id = {plan.step_id: plan for plan in plans}
    remaining = set(by_id)
    completed: set[str] = set()
    layers: list[list[str]] = []
    while remaining:
        ready = sorted(
            [step_id for step_id in remaining if set(by_id[step_id].dependency_ids).issubset(completed)],
            key=lambda step_id: by_id[step_id].index,
        )
        if not ready:
            unresolved = sorted(remaining, key=lambda step_id: by_id[step_id].index)
            raise ValueError(f"dependency cycle or unresolved dependency near {unresolved[0]}")
        layer: list[str] = []
        used_surfaces: set[str] = set()
        for step_id in ready:
            plan = by_id[step_id]
            if _conflicts(plan, used_surfaces):
                continue
            layer.append(step_id)
            used_surfaces.update(plan.write_surfaces)
        layers.append(layer)
        completed.update(layer)
        remaining.difference_update(layer)
    return layers


def apply_read_only_profile(plans: list[StepPlan]) -> tuple[list[StepPlan], list[dict[str, Any]]]:
    """Drop mutating steps and any downstream dependents for a safe proof run."""
    by_id = {plan.step_id: plan for plan in plans}
    skipped: dict[str, dict[str, Any]] = {}
    for plan in plans:
        if plan.mutating:
            skipped[plan.step_id] = {
                "step_id": plan.step_id,
                "script": plan.script,
                "reason": "mutating_step",
                "mutating": True,
                "blocked_by": [],
            }
    changed = True
    while changed:
        changed = False
        for plan in plans:
            if plan.step_id in skipped:
                continue
            blockers = [dep for dep in plan.dependency_ids if dep in skipped]
            if blockers:
                skipped[plan.step_id] = {
                    "step_id": plan.step_id,
                    "script": plan.script,
                    "reason": "depends_on_skipped_mutating_step",
                    "mutating": plan.mutating,
                    "blocked_by": blockers,
                }
                changed = True
    active = [plan for plan in plans if plan.step_id not in skipped]
    valid_ids = {plan.step_id for plan in active}
    rewritten: list[StepPlan] = []
    for plan in active:
        rewritten.append(
            StepPlan(
                step_id=plan.step_id,
                index=plan.index,
                script=plan.script,
                args=plan.args,
                command=plan.command,
                category=plan.category,
                expected_outputs=plan.expected_outputs,
                depends_on_scripts=plan.depends_on_scripts,
                dependency_ids=tuple(dep for dep in plan.dependency_ids if dep in valid_ids),
                recovery=plan.recovery,
                write_surfaces=plan.write_surfaces,
                mutating=plan.mutating,
                signature=plan.signature,
            )
        )
    skipped_rows = [skipped[step_id] for step_id in sorted(skipped, key=lambda value: by_id[value].index)]
    return rewritten, skipped_rows


def validate_plan(plans: list[StepPlan], layers: list[list[str]]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    by_id = {plan.step_id: plan for plan in plans}
    flattened = [step_id for layer in layers for step_id in layer]
    if sorted(flattened) != sorted(by_id):
        errors.append("layer_coverage_mismatch")
    seen: set[str] = set()
    layer_by_step: dict[str, int] = {}
    for layer_index, layer in enumerate(layers):
        surfaces: set[str] = set()
        for step_id in layer:
            plan = by_id[step_id]
            overlap = surfaces & set(plan.write_surfaces)
            if overlap:
                errors.append(f"write_surface_conflict:{layer_index}:{step_id}:{','.join(sorted(overlap))}")
            surfaces.update(plan.write_surfaces)
            seen.add(step_id)
            layer_by_step[step_id] = layer_index
    for plan in plans:
        for dependency_id in plan.dependency_ids:
            if dependency_id not in by_id:
                errors.append(f"missing_dependency_id:{plan.step_id}:{dependency_id}")
            elif layer_by_step.get(dependency_id, -1) >= layer_by_step.get(plan.step_id, -1):
                errors.append(f"dependency_order_violation:{dependency_id}->{plan.step_id}")
        if plan.mutating:
            warnings.append(f"mutating_step_present:{plan.step_id}")
    return {
        "status": "error" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "step_count": len(plans),
            "layer_count": len(layers),
            "max_layer_width": max((len(layer) for layer in layers), default=0),
            "mutating_step_count": sum(1 for plan in plans if plan.mutating),
        },
    }


def build_payload(
    window: str,
    *,
    strict: bool = False,
    build_workbook: bool = False,
    cleanup: bool = False,
    max_workers: int = 4,
    skip_mutating: bool = False,
) -> dict[str, Any]:
    original_plans = build_step_plans(window, strict=strict, build_workbook=build_workbook, cleanup=cleanup)
    skipped_steps: list[dict[str, Any]] = []
    plans = original_plans
    if skip_mutating:
        plans, skipped_steps = apply_read_only_profile(original_plans)
    layers = build_execution_layers(plans)
    validation = validate_plan(plans, layers)
    by_id = {plan.step_id: plan for plan in plans}
    return {
        "schema": SCHEMA_VERSION,
        "generated_at_utc": utc_now_iso(),
        "window": window,
        "description": window_description(window),
        "max_workers": max_workers,
        "execution_profile": "read_only_skip_mutating" if skip_mutating else "full_manifest",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": {
            **validation["summary"],
            "original_step_count": len(original_plans),
            "skipped_step_count": len(skipped_steps),
            "skipped_mutating_step_count": sum(1 for row in skipped_steps if row.get("reason") == "mutating_step"),
            "skipped_dependent_step_count": sum(
                1 for row in skipped_steps if row.get("reason") == "depends_on_skipped_mutating_step"
            ),
        },
        "validation": validation,
        "layers": [
            {
                "layer_index": index,
                "step_ids": layer,
                "scripts": [by_id[step_id].script for step_id in layer],
                "write_surfaces": sorted({surface for step_id in layer for surface in by_id[step_id].write_surfaces}),
            }
            for index, layer in enumerate(layers)
        ],
        "skipped_steps": skipped_steps,
        "steps": [plan.to_json() for plan in plans],
    }


def load_resume_state(window: str) -> dict[str, Any]:
    path = state_path(window)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def initial_state(payload: dict[str, Any], resume_state: dict[str, Any] | None = None) -> dict[str, Any]:
    resume_steps = {
        step["step_id"]: step
        for step in (resume_state or {}).get("steps", [])
        if step.get("status") == "ok" and step.get("signature")
    }
    state_steps: list[dict[str, Any]] = []
    for step in payload["steps"]:
        resumed = resume_steps.get(step["step_id"])
        if resumed and resumed.get("signature") == step["signature"]:
            state_steps.append({**step, "status": "ok", "resumed": True, "completed_at_utc": resumed.get("completed_at_utc")})
        else:
            state_steps.append({**step, "status": "pending", "resumed": False})
    return {
        "schema": SCHEMA_VERSION,
        "window": payload["window"],
        "status": "running",
        "started_at_utc": utc_now_iso(),
        "completed_at_utc": None,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "summary": payload["summary"],
        "validation": payload["validation"],
        "current_layer_index": 0,
        "layers": payload["layers"],
        "steps": state_steps,
    }


def run_one_step(step: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    command = list(step["command"])
    attempts = int(step.get("retries") or 0) + 1
    last: subprocess.CompletedProcess[str] | None = None
    for attempt in range(1, attempts + 1):
        started_at = utc_now_iso()
        try:
            last = subprocess.run(
                command,
                cwd=str(WORKSPACE),
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "step_id": step["step_id"],
                "status": "failed",
                "exit_code": 124,
                "attempt": attempt,
                "started_at_utc": started_at,
                "completed_at_utc": utc_now_iso(),
                "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
                "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "timeout",
            }
        if last.returncode == 0:
            return {
                "step_id": step["step_id"],
                "status": "ok",
                "exit_code": 0,
                "attempt": attempt,
                "started_at_utc": started_at,
                "completed_at_utc": utc_now_iso(),
                "stdout_tail": last.stdout[-4000:],
                "stderr_tail": last.stderr[-4000:],
            }
    assert last is not None
    return {
        "step_id": step["step_id"],
        "status": "failed",
        "exit_code": int(last.returncode),
        "attempt": attempts,
        "started_at_utc": started_at,
        "completed_at_utc": utc_now_iso(),
        "stdout_tail": last.stdout[-4000:],
        "stderr_tail": last.stderr[-4000:],
    }


def execute_payload(payload: dict[str, Any], *, resume: bool, timeout_seconds: int) -> int:
    resume_state = load_resume_state(payload["window"]) if resume else {}
    state = initial_state(payload, resume_state)
    step_state = {step["step_id"]: step for step in state["steps"]}
    atomic_write_json(state_path(payload["window"]), state)
    failed = False
    for layer in payload["layers"]:
        state["current_layer_index"] = layer["layer_index"]
        runnable = [step_state[step_id] for step_id in layer["step_ids"] if step_state[step_id]["status"] != "ok"]
        if failed:
            for step in runnable:
                step["status"] = "skipped_after_failure"
                step["completed_at_utc"] = utc_now_iso()
            atomic_write_json(state_path(payload["window"]), state)
            continue
        with ThreadPoolExecutor(max_workers=max(1, min(int(payload["max_workers"]), len(runnable) or 1))) as executor:
            futures = {}
            for step in runnable:
                step["status"] = "running"
                step["started_at_utc"] = utc_now_iso()
                futures[executor.submit(run_one_step, step, timeout_seconds)] = step
            atomic_write_json(state_path(payload["window"]), state)
            for future in as_completed(futures):
                step = futures[future]
                result = future.result()
                step.update(result)
                if result["status"] != "ok":
                    if step.get("recovery_mode") == "skip_degraded":
                        step["status"] = "degraded"
                    elif step.get("recovery_mode") == "isolate":
                        step["status"] = "isolated_failed"
                    else:
                        failed = True
                atomic_write_json(state_path(payload["window"]), state)
    state["completed_at_utc"] = utc_now_iso()
    state["status"] = "failed" if failed else "ok"
    state["exit_code"] = 1 if failed else 0
    atomic_write_json(state_path(payload["window"]), state)
    return int(state["exit_code"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Opt-in layered finance refresh chain runner.")
    parser.add_argument("window", nargs="?", default="post-close", choices=window_names())
    parser.add_argument("--dry-run", action="store_true", help="Build and write the plan without executing steps.")
    parser.add_argument("--strict", action="store_true", help="Pass strict validation flags where the serial runner would.")
    parser.add_argument("--build-workbook", action="store_true", help="Match serial runner optional workbook tail.")
    parser.add_argument("--cleanup", action="store_true", help="Match serial runner optional Sunday cleanup tail.")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--skip-mutating", action="store_true", help="Use a read-only profile: remove mutating steps and their dependents.")
    parser.add_argument("--write", action="store_true", help="Write plan/validation artifacts.")
    parser.add_argument("--validate", action="store_true", help="Validate layer coverage, dependency order, and write-surface exclusivity.")
    parser.add_argument("--resume", action="store_true", help="Reuse completed matching step signatures from prior layered state.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(
        args.window,
        strict=args.strict,
        build_workbook=args.build_workbook,
        cleanup=args.cleanup,
        max_workers=args.max_workers,
        skip_mutating=args.skip_mutating,
    )
    if args.write:
        atomic_write_json(plan_path(args.window), payload)
        atomic_write_json(validation_path(), payload["validation"])
    print(
        f"Layered finance refresh plan: window={args.window} "
        f"profile={payload['execution_profile']} steps={payload['summary']['step_count']} "
        f"layers={payload['summary']['layer_count']} max_width={payload['summary']['max_layer_width']} "
        f"mutating={payload['summary']['mutating_step_count']} skipped={payload['summary']['skipped_step_count']}"
    )
    if args.validate and payload["validation"]["status"] != "ok":
        print(json.dumps(payload["validation"], indent=2))
        return 1
    if args.dry_run:
        print("Dry run only, nothing executed.")
        return 0
    return execute_payload(payload, resume=args.resume, timeout_seconds=args.timeout_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
