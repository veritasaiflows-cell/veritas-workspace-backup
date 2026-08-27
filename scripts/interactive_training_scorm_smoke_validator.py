#!/usr/bin/env python3
"""Local SCORM smoke-test validator for generated interactive training modules.

This validator checks SCORM package structure, imsmanifest.xml shape, package
contents, required runtime API markers, and a local browser run with a mock LMS
API. It does not upload packages, configure an LMS/LRS, transport learner data,
collect customer data, or mutate runtime/cron/channel surfaces.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "training" / "interactive-training-builder"
BUILDER_PROOF = ROOT / "tmp" / "interactive-training-builder-proof.json"
SCORM_CONFIG = ROOT / "tmp" / "interactive-training-scorm-smoke-config.json"
SCORM_PROOF = ROOT / "tmp" / "interactive-training-scorm-smoke-validation.json"
SCORM_RUNNER = ROOT / "scripts" / "interactive_training_scorm_smoke_runner.mjs"
SCREENSHOTS = TRAINING / "scorm-smoke-screenshots"
NODE_MODULES = ROOT / "node_modules"

EDGE_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]

REQUIRED_PACKAGE_FILES = {"imsmanifest.xml", "index.html", "module.json", "xapi-seed.json"}
REQUIRED_HTML_MARKERS = [
    "LMSInitialize",
    "LMSSetValue",
    "LMSCommit",
    "LMSFinish",
    "cmi.core.lesson_status",
    "cmi.core.score.raw",
    "cmi.core.lesson_location",
    "cmi.suspend_data",
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
    edge = find_edge()
    return {
        "node_modules_present": NODE_MODULES.exists(),
        "playwright_present": (NODE_MODULES / "playwright" / "package.json").exists(),
        "runner_present": SCORM_RUNNER.exists(),
        "edge_executable": str(edge) if edge else None,
    }


def validate_preflight(status: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if not status["node_modules_present"]:
        errors.append("node_modules_missing")
    if not status["playwright_present"]:
        errors.append("playwright_dependency_missing")
    if not status["runner_present"]:
        errors.append("scorm_smoke_runner_missing")
    if not status["edge_executable"]:
        errors.append("edge_executable_missing")
    return errors


def discover_modules(builder_proof: Path = BUILDER_PROOF) -> list[dict[str, Any]]:
    if not builder_proof.exists():
        raise FileNotFoundError(f"Builder proof missing: {builder_proof}")
    proof = load_json(builder_proof)
    modules: list[dict[str, Any]] = []
    for module in proof.get("modules", []):
        outputs = module.get("outputs", {})
        scorm_manifest = ROOT / outputs["scorm_manifest"]
        scorm_zip = ROOT / outputs["scorm_zip"]
        scorm_dir = scorm_manifest.parent
        modules.append(
            {
                "name": module["module_id"],
                "module_id": module["module_id"],
                "title": module.get("title") or module["module_id"],
                "module_html": str(ROOT / outputs["module_html"]),
                "module_json": str(ROOT / outputs["module_json"]),
                "xapi_seed": str(ROOT / outputs["xapi_seed"]),
                "module_manifest": str(ROOT / outputs["module_manifest"]),
                "scorm_manifest": str(scorm_manifest),
                "scorm_zip": str(scorm_zip),
                "scorm_dir": str(scorm_dir),
                "scorm_index": str(scorm_dir / "index.html"),
            }
        )
    if not modules:
        raise RuntimeError("No generated SCORM modules found in builder proof")
    return modules


def manifest_fact(root: ET.Element, tag_name: str) -> str:
    found = root.find(f".//{{*}}{tag_name}")
    return (found.text or "").strip() if found is not None else ""


def parse_manifest(xml_text: str) -> dict[str, Any]:
    root = ET.fromstring(xml_text)
    resources = root.findall(".//{*}resource")
    items = root.findall(".//{*}item")
    resource = resources[0] if resources else None
    item = items[0] if items else None
    scorm_type = None
    resource_href = None
    resource_identifier = None
    files: list[str] = []
    if resource is not None:
        resource_href = resource.attrib.get("href")
        resource_identifier = resource.attrib.get("identifier")
        scorm_type = resource.attrib.get("{http://www.adlnet.org/xsd/adlcp_rootv1p2}scormtype")
        files = [node.attrib.get("href", "") for node in resource.findall(".//{*}file")]
    return {
        "identifier": root.attrib.get("identifier"),
        "schema": manifest_fact(root, "schema"),
        "schemaversion": manifest_fact(root, "schemaversion"),
        "resource_count": len(resources),
        "item_count": len(items),
        "resource_identifier": resource_identifier,
        "resource_href": resource_href,
        "scorm_type": scorm_type,
        "item_identifierref": item.attrib.get("identifierref") if item is not None else None,
        "file_hrefs": files,
    }


def inspect_static_module(module: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    paths = {key: Path(module[key]) for key in ["module_json", "xapi_seed", "scorm_manifest", "scorm_zip", "scorm_index"]}
    for key, path in paths.items():
        if not path.exists():
            errors.append(f"{key}_missing")
    if errors:
        return {"module_id": module["module_id"], "status": "blocked", "errors": errors, "warnings": warnings}

    with zipfile.ZipFile(paths["scorm_zip"]) as package:
        package_names = set(package.namelist())
        missing_package_files = sorted(REQUIRED_PACKAGE_FILES - package_names)
        if missing_package_files:
            errors.append(f"zip_missing_files:{','.join(missing_package_files)}")
        zip_manifest_text = package.read("imsmanifest.xml").decode("utf-8") if "imsmanifest.xml" in package_names else ""
        zip_html_text = package.read("index.html").decode("utf-8") if "index.html" in package_names else ""
        zip_module = json.loads(package.read("module.json").decode("utf-8")) if "module.json" in package_names else {}
        zip_xapi = json.loads(package.read("xapi-seed.json").decode("utf-8")) if "xapi-seed.json" in package_names else []

    disk_manifest_text = paths["scorm_manifest"].read_text(encoding="utf-8")
    if zip_manifest_text.replace("\r\n", "\n").strip() != disk_manifest_text.replace("\r\n", "\n").strip():
        errors.append("zip_manifest_differs_from_disk_manifest")
    manifest = parse_manifest(disk_manifest_text)
    if manifest["schema"] != "ADL SCORM":
        errors.append("manifest_schema_not_adl_scorm")
    if manifest["schemaversion"] != "1.2":
        errors.append("manifest_schemaversion_not_1_2")
    if manifest["resource_count"] != 1:
        errors.append("manifest_resource_count_not_one")
    if manifest["resource_href"] != "index.html":
        errors.append("manifest_resource_href_not_index_html")
    if manifest["scorm_type"] != "sco":
        errors.append("manifest_resource_not_sco")
    if manifest["item_identifierref"] != manifest["resource_identifier"]:
        errors.append("manifest_item_resource_mismatch")
    for required_file in ["index.html", "module.json", "xapi-seed.json"]:
        if required_file not in manifest["file_hrefs"]:
            errors.append(f"manifest_missing_file_ref:{required_file}")

    for marker in REQUIRED_HTML_MARKERS:
        if marker not in zip_html_text:
            errors.append(f"html_missing_scorm_marker:{marker}")
    if "<script src=\"http" in zip_html_text.lower() or "<script src='http" in zip_html_text.lower():
        errors.append("external_script_reference_present")
    if "fetch(" in zip_html_text:
        warnings.append("fetch_marker_present_review_required")

    if zip_module.get("module_id") != module["module_id"]:
        errors.append("zip_module_id_mismatch")
    if not zip_module.get("interactions"):
        errors.append("zip_module_interactions_missing")
    authority = zip_module.get("authority_boundary", {})
    if authority.get("internal_training_only") is not True:
        errors.append("authority_internal_training_only_missing")
    if authority.get("external_delivery_approved") is not False:
        errors.append("authority_external_delivery_not_false")
    if not isinstance(zip_xapi, list) or not zip_xapi:
        errors.append("xapi_seed_missing_or_empty")

    return {
        "module_id": module["module_id"],
        "status": "blocked" if errors else "ok",
        "package": rel(paths["scorm_zip"]),
        "package_files": sorted(package_names),
        "manifest": manifest,
        "html_marker_count": sum(1 for marker in REQUIRED_HTML_MARKERS if marker in zip_html_text),
        "interaction_count": len(zip_module.get("interactions", [])),
        "xapi_seed_count": len(zip_xapi) if isinstance(zip_xapi, list) else 0,
        "errors": errors,
        "warnings": warnings,
    }


def build_config(modules: list[dict[str, Any]]) -> dict[str, Any]:
    edge = find_edge()
    return {
        "schema": "veritas.interactive_training_scorm_smoke_config.v1",
        "generated_at_utc": utc_now(),
        "modules": modules,
        "browser_channel": "msedge",
        "browser_executable": str(edge) if edge else None,
        "screenshot_dir": str(SCREENSHOTS),
        "output_path": str(SCORM_PROOF),
        "authority_boundary": {
            "local_files_only": True,
            "external_lms_upload": False,
            "external_lrs_configured": False,
            "learner_data_external_transport": False,
            "customer_data_allowed": False,
        },
    }


def run_node_runner(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    atomic_write_json(SCORM_CONFIG, config)
    completed = subprocess.run(
        ["node", str(SCORM_RUNNER), str(SCORM_CONFIG)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    runner_output = load_json(SCORM_PROOF) if SCORM_PROOF.exists() else {
        "schema": "veritas.interactive_training_scorm_smoke_runner.v1",
        "status": "blocked",
        "modules": [],
        "validation": {"errors": ["scorm_smoke_runner_output_missing"], "warnings": []},
    }
    runner_process = {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }
    return runner_output, runner_process


def build(write: bool = False) -> dict[str, Any]:
    modules = discover_modules()
    config = build_config(modules)
    deps = dependency_status()
    static_checks = [inspect_static_module(module) for module in modules]
    static_errors = [f"{check['module_id']}:{error}" for check in static_checks for error in check.get("errors", [])]
    preflight_errors = validate_preflight(deps)
    validation_errors = [*static_errors, *preflight_errors]
    runner_output: dict[str, Any] | None = None
    runner_process: dict[str, Any] | None = None

    if write:
        atomic_write_json(SCORM_CONFIG, config)
    if write and not validation_errors:
        runner_output, runner_process = run_node_runner(config)
        validation_errors.extend(runner_output.get("validation", {}).get("errors", []))
    elif not write:
        validation_warnings = ["node_runner_not_executed_without_write"]
    else:
        validation_warnings = []

    result = {
        "schema": "veritas.interactive_training_scorm_smoke_validation.v1",
        "generated_at_utc": utc_now(),
        "status": "blocked" if validation_errors else "ok",
        "dependency_status": deps,
        "config_path": rel(SCORM_CONFIG),
        "static_checks": static_checks,
        "dynamic_checks": runner_output.get("modules", []) if runner_output else [],
        "browser": runner_output.get("browser") if runner_output else None,
        "runner_process": runner_process,
        "validation": {
            "errors": validation_errors,
            "warnings": (
                runner_output.get("validation", {}).get("warnings", [])
                if runner_output
                else validation_warnings
            ),
        },
        "authority_boundary": config["authority_boundary"],
    }
    if write:
        atomic_write_json(SCORM_PROOF, result)
    return result


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
