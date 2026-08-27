#!/usr/bin/env python3
"""Run local browser/accessibility QA for generated interactive training HTML.

This validator is local-only. It uses workspace-local Playwright and axe-core
dependencies to open generated HTML files, take screenshots, verify a keyboard
path, collect console errors, and scan for serious/critical accessibility
violations. It does not publish content, configure an LMS/LRS, transport learner
data, collect customer data, or mutate runtime/cron/channel surfaces.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "training" / "interactive-training-builder"
BUILDER_PROOF = ROOT / "tmp" / "interactive-training-builder-proof.json"
QA_CONFIG = ROOT / "tmp" / "interactive-training-qa-config.json"
QA_PROOF = ROOT / "tmp" / "interactive-training-qa-validation.json"
QA_RUNNER = ROOT / "scripts" / "interactive_training_qa_runner.mjs"
SCREENSHOTS = TRAINING / "qa-screenshots"
NODE_MODULES = ROOT / "node_modules"

EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def find_edge() -> Path | None:
    for candidate in EDGE_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


def dependency_status() -> dict[str, Any]:
    return {
        "node_modules_present": NODE_MODULES.exists(),
        "playwright_present": (NODE_MODULES / "playwright" / "package.json").exists(),
        "axe_core_present": (NODE_MODULES / "axe-core" / "package.json").exists(),
        "runner_present": QA_RUNNER.exists(),
        "edge_executable": str(find_edge()) if find_edge() else None,
    }


def discover_files(builder_proof: Path = BUILDER_PROOF) -> list[dict[str, str]]:
    if not builder_proof.exists():
        raise FileNotFoundError(f"Builder proof missing: {builder_proof}")
    proof = load_json(builder_proof)
    files: list[dict[str, str]] = []
    for module in proof.get("modules", []):
        html_path = ROOT / module["outputs"]["module_html"]
        if html_path.exists():
            files.append({"name": module["module_id"], "path": str(html_path)})
    if not files:
        raise RuntimeError("No generated interactive training HTML files found in builder proof")
    return files


def build_config() -> dict[str, Any]:
    edge = find_edge()
    return {
        "schema": "veritas.interactive_training_qa_config.v1",
        "generated_at_utc": utc_now(),
        "files": discover_files(),
        "viewports": [
            {"name": "desktop", "width": 1366, "height": 900},
            {"name": "mobile", "width": 390, "height": 844},
        ],
        "browser_channel": "msedge",
        "browser_executable": str(edge) if edge else None,
        "screenshot_dir": str(SCREENSHOTS),
        "output_path": str(QA_PROOF),
        "authority_boundary": {
            "local_files_only": True,
            "external_delivery_approved": False,
            "learner_data_external_transport": False,
            "customer_data_allowed": False,
        },
    }


def validate_preflight(status: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not status["node_modules_present"]:
        errors.append("node_modules_missing")
    if not status["playwright_present"]:
        errors.append("playwright_dependency_missing")
    if not status["axe_core_present"]:
        errors.append("axe_core_dependency_missing")
    if not status["runner_present"]:
        errors.append("qa_runner_missing")
    if not status["edge_executable"]:
        errors.append("edge_executable_missing")
    return errors


def run_node_runner(config: dict[str, Any]) -> dict[str, Any]:
    atomic_write_json(QA_CONFIG, config)
    completed = subprocess.run(
        ["node", str(QA_RUNNER), str(QA_CONFIG)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = load_json(QA_PROOF) if QA_PROOF.exists() else {
        "schema": "veritas.interactive_training_qa_runner.v1",
        "status": "blocked",
        "files": [],
        "validation": {"errors": ["qa_runner_output_missing"], "warnings": []},
    }
    output["runner_process"] = {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }
    output["dependency_status"] = dependency_status()
    output["config_path"] = rel(QA_CONFIG)
    atomic_write_json(QA_PROOF, output)
    return output


def build(write: bool = False) -> dict[str, Any]:
    deps = dependency_status()
    preflight_errors = validate_preflight(deps)
    config = build_config()
    if preflight_errors:
        result = {
            "schema": "veritas.interactive_training_qa_validation.v1",
            "generated_at_utc": utc_now(),
            "status": "blocked",
            "files": [],
            "dependency_status": deps,
            "validation": {"errors": preflight_errors, "warnings": []},
            "authority_boundary": config["authority_boundary"],
        }
        if write:
            atomic_write_json(QA_CONFIG, config)
            atomic_write_json(QA_PROOF, result)
        return result
    if not write:
        return {
            "schema": "veritas.interactive_training_qa_validation.v1",
            "generated_at_utc": utc_now(),
            "status": "ok",
            "files": config["files"],
            "dependency_status": deps,
            "validation": {"errors": [], "warnings": ["node_runner_not_executed_without_write"]},
            "authority_boundary": config["authority_boundary"],
        }
    return run_node_runner(config)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    args = parser.parse_args()
    result = build(write=args.write)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.validate and result.get("validation", {}).get("errors"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
