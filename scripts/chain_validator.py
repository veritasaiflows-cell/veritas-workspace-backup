from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from chain_manifest import (
    expected_outputs_by_script,
    manifest_stages,
    manifest_steps,
    manifest_validation,
    topological_batches_from_steps,
    window_names,
)

WORKSPACE = Path(__file__).resolve().parents[1]


def print_stage_list(window: str, steps: list[dict[str, Any]]) -> None:
    counts: dict[str, int] = {}
    for step in steps:
        stage = str(step.get("stage") or "uncategorized")
        counts[stage] = counts.get(stage, 0) + 1
    print("\nStages:")
    for stage in manifest_stages(window):
        if stage in counts:
            print(f"  - {stage}: {counts[stage]} steps")
    for stage, count in counts.items():
        if stage not in manifest_stages(window):
            print(f"  - {stage}: {count} steps")


def manifest_summary(window: str, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    expected_by_script = expected_outputs_by_script(window)
    prior_scripts: list[str] = []
    summary: list[dict[str, Any]] = []
    for step in steps:
        script = str(step["script"])
        expected_outputs = list(step.get("expected_outputs") or [])
        declared_dependencies = list(step.get("depends_on") or [])
        missing_declared_dependencies = [dep for dep in declared_dependencies if dep not in prior_scripts]
        missing_dependency_outputs = []
        for dep in declared_dependencies:
            for output in expected_by_script.get(dep, []):
                if not (WORKSPACE / output).exists():
                    missing_dependency_outputs.append(output)
        summary.append({
            "script": script,
            "args": list(step.get("args") or []),
            "category": step.get("category"),
            "stage": step.get("stage"),
            "expected_outputs": expected_outputs,
            "depends_on": declared_dependencies,
            "missing_declared_dependencies": missing_declared_dependencies,
            "missing_dependency_outputs": missing_dependency_outputs,
            "recovery_posture": step.get("recovery_posture"),
        })
        prior_scripts.append(script)
    return summary


def print_manifest_summary(window: str, steps: list[dict[str, Any]]) -> None:
    print("\nManifest summary:")
    for index, item in enumerate(manifest_summary(window, steps), start=1):
        print(f"  {index}. {item['script']} [{item['category']}] stage={item['stage']} recovery={item['recovery_posture']}")
        if item["depends_on"]:
            print(f"     depends_on: {', '.join(item['depends_on'])}")
        if item["expected_outputs"]:
            print(f"     expected_outputs: {', '.join(item['expected_outputs'])}")
        if item["missing_declared_dependencies"]:
            print(f"     MISSING PRIOR DEPENDENCIES: {', '.join(item['missing_declared_dependencies'])}")
        if item["missing_dependency_outputs"]:
            print(f"     missing_dependency_outputs_on_disk: {', '.join(item['missing_dependency_outputs'])}")


def analysis_findings(window: str, steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validation = manifest_validation(window)
    topo = topological_batches_from_steps(steps)
    return list(validation.get("findings") or []) + list(topo.get("findings") or [])


def print_analysis(window: str, steps: list[dict[str, Any]]) -> int:
    validation = manifest_validation(window)
    topo = topological_batches_from_steps(steps)
    print("\nManifest graph analysis:")
    print(f"  status: {validation['status']}")
    print(f"  steps: {len(steps)}")
    print(f"  stages: {validation['stage_count']}")
    print(f"  batches: {len(topo['batches'])}")
    print(f"  max_batch_size: {max((len(batch) for batch in topo['batches']), default=0)}")
    print("  batch_sizes: " + ", ".join(str(len(batch)) for batch in topo["batches"]))
    findings = analysis_findings(window, steps)
    if findings:
        print("  findings:")
        for finding in findings:
            print(f"    - {finding.get('severity')}: {finding.get('code')} {finding}")
    return 1 if any(finding.get("severity") == "error" for finding in findings) else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and inspect finance refresh chain manifests.")
    parser.add_argument("window", nargs="?", default="post-close", choices=window_names())
    parser.add_argument("--summary", action="store_true", help="Print manifest dependency and output summary.")
    parser.add_argument("--list-stages", action="store_true", help="Print stage names and step counts.")
    parser.add_argument("--analyze", action="store_true", help="Print dependency graph and validation analysis.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero if manifest analysis has errors.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    steps = manifest_steps(args.window)
    if args.summary:
        print_manifest_summary(args.window, steps)
    if args.list_stages:
        print_stage_list(args.window, steps)
    status = print_analysis(args.window, steps) if args.analyze or args.validate else 0
    if not any([args.summary, args.list_stages, args.analyze, args.validate]):
        print_manifest_summary(args.window, steps)
        status = print_analysis(args.window, steps)
    return status if args.validate else 0


if __name__ == "__main__":
    raise SystemExit(main())
