#!/usr/bin/env python3
"""Render a validated WF75 customer-safe export to local HTML and optional PDF.

This is an internal proof renderer only. It does not approve customer delivery,
public launch, legal/compliance/source licensing, advice, brokerage, account
actions, or execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact
from retail_saas_customer_output_validator import validate_payload, validate_rendered_text
from retail_saas_html_report import render_html

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_SCENARIO_INPUT = TMP / "wf75-renderer-regression" / "anon-risk-freshness-edge-cases-v1.customer-export.json"
FALLBACK_INPUT = TMP / "retail-saas-fixture-demo.customer-export.json"
DEFAULT_OUT = TMP / "wf75-customer-safe-pdf-renderer.json"
DELIVERABLE_DIR = TMP / "wf75-customer-safe-deliverables" / "pdf"
DEFAULT_HTML = DELIVERABLE_DIR / "wf75-customer-safe-research-packet.html"
DEFAULT_PDF = DELIVERABLE_DIR / "wf75-customer-safe-research-packet.pdf"
SEEDED_BAD_JSON_VALIDATION = TMP / "wf75-renderer-regression" / "seeded-bad.validation.json"
SEEDED_BAD_MD_VALIDATION = TMP / "wf75-renderer-regression" / "seeded-bad-md.validation.json"

SCHEMA = "veritas.wf75.customer_safe_pdf_renderer.v1"

AUTHORITY_BOUNDARY = {
    "review_only_internal_service_led": True,
    "customer_external_delivery_allowed": False,
    "public_launch_allowed": False,
    "legal_compliance_source_licensing_ready": False,
    "advice_execution_brokerage_account_allowed": False,
    "owner_approval_inferred": False,
}

BROWSER_CANDIDATES = [
    "msedge",
    "chrome",
    "chromium",
    "google-chrome",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_default_input() -> Path:
    return DEFAULT_SCENARIO_INPUT if DEFAULT_SCENARIO_INPUT.exists() else FALLBACK_INPUT


def load_validation(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    if isinstance(payload, dict):
        return payload
    return {
        "status": "missing",
        "critical_count": None,
        "warning_count": None,
        "error": f"Unable to load validation artifact: {rel(path)}",
    }


def seeded_bad_status() -> dict[str, Any]:
    json_validation = load_validation(SEEDED_BAD_JSON_VALIDATION)
    md_validation = load_validation(SEEDED_BAD_MD_VALIDATION)
    json_is_error = json_validation.get("status") == "error"
    md_is_error = md_validation.get("status") == "error"
    return {
        "status": "ok" if json_is_error and md_is_error else "error",
        "expected_status": "error",
        "json_validation_status": json_validation.get("status"),
        "json_critical_count": json_validation.get("critical_count"),
        "json_validation_path": rel(SEEDED_BAD_JSON_VALIDATION),
        "markdown_validation_status": md_validation.get("status"),
        "markdown_critical_count": md_validation.get("critical_count"),
        "markdown_validation_path": rel(SEEDED_BAD_MD_VALIDATION),
    }


def browser_candidates() -> list[str]:
    available: list[str] = []
    for candidate in BROWSER_CANDIDATES:
        candidate_path = Path(candidate)
        if candidate_path.is_absolute():
            if candidate_path.exists():
                available.append(str(candidate_path))
            continue
        available.append(candidate)
    return available


def attempt_pdf(html_path: Path, pdf_path: Path) -> dict[str, Any]:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    html_uri = html_path.resolve().as_uri()
    last_errors: list[str] = []
    for browser in browser_candidates():
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            f"--print-to-pdf={str(pdf_path.resolve())}",
            html_uri,
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=60)
        except FileNotFoundError:
            last_errors.append(f"{browser}: not found")
            continue
        except subprocess.TimeoutExpired:
            last_errors.append(f"{browser}: timed out")
            continue
        except Exception as exc:
            last_errors.append(f"{browser}: {exc}")
            continue

        if completed.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0:
            return {
                "status": "created",
                "available": True,
                "path": rel(pdf_path),
                "size_bytes": pdf_path.stat().st_size,
                "sha256": sha256_file(pdf_path),
                "renderer": browser,
            }
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        last_errors.append(f"{browser}: exit={completed.returncode} stderr={stderr[:300]} stdout={stdout[:300]}")

    return {
        "status": "unavailable",
        "available": False,
        "path": None,
        "reason": "No local Edge/Chrome/Chromium renderer produced a PDF.",
        "attempt_errors": last_errors[:8],
    }


def validate_combined(export: Any, rendered_html: str, html_label: str) -> dict[str, Any]:
    validation = validate_payload(export)
    validation["findings"].extend(validate_rendered_text(rendered_html, html_label))
    validation["critical_count"] = sum(1 for finding in validation["findings"] if finding["severity"] == "critical")
    validation["warning_count"] = sum(1 for finding in validation["findings"] if finding["severity"] == "warning")
    validation["status"] = "ok" if validation["critical_count"] == 0 else "error"
    validation["rendered_html_validated"] = html_label
    return validation


def validate_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    if payload.get("schema") != SCHEMA:
        errors.append("unexpected_schema")
    if payload.get("html_contract", {}).get("status") != "implemented":
        errors.append("html_contract_not_implemented")
    if payload.get("customer_export_validation", {}).get("status") != "ok":
        errors.append("customer_export_or_html_validation_failed")
    if payload.get("seeded_bad_status", {}).get("status") != "ok":
        errors.append("seeded_bad_regression_not_error")
    pdf_contract = payload.get("pdf_contract") or {}
    if pdf_contract.get("status") not in {"created", "unavailable"}:
        errors.append("pdf_contract_status_invalid")
    if pdf_contract.get("status") == "unavailable" and not pdf_contract.get("reason"):
        errors.append("pdf_unavailable_without_reason")
    for key, expected in AUTHORITY_BOUNDARY.items():
        if payload.get("authority_boundary", {}).get(key) is not expected:
            errors.append(f"authority_{key}_unexpected")
    return {"status": "ok" if not errors else "error", "errors": errors}


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    export = load_json_artifact(args.input)
    if not isinstance(export, dict):
        export = {}
    rendered_html = render_html(export)
    validation = validate_combined(export, rendered_html, args.html_out.name)
    seeded = seeded_bad_status()

    html_contract = {
        "status": "implemented",
        "path": rel(args.html_out),
        "size_bytes": len(rendered_html.encode("utf-8")),
        "sha256": hashlib.sha256(rendered_html.encode("utf-8")).hexdigest(),
        "rendered_with": "retail_saas_html_report.render_html",
        "validated_with": [
            "retail_saas_customer_output_validator.validate_payload",
            "retail_saas_customer_output_validator.validate_rendered_text",
        ],
        "sanitized_local_html_only": True,
    }
    pdf_contract: dict[str, Any] = {
        "status": "not_attempted",
        "available": False,
        "path": None,
        "reason": "PDF generation was not requested.",
    }
    if args.write:
        atomic_write_text(args.html_out, rendered_html)
        if args.pdf:
            pdf_contract = attempt_pdf(args.html_out, args.pdf_out)

    status = "ok" if validation["status"] == "ok" and seeded["status"] == "ok" else "error"
    if status == "ok" and pdf_contract.get("status") == "unavailable":
        status = "html_contract_implemented_pdf_unavailable"
    elif status == "ok" and pdf_contract.get("status") == "created":
        status = "ok_pdf_created"

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "workflow": "WF75",
        "status": status,
        "inputs": {
            "customer_export": rel(args.input),
            "customer_export_exists": args.input.exists(),
            "default_source_preference": rel(DEFAULT_SCENARIO_INPUT),
            "fallback_source": rel(FALLBACK_INPUT),
        },
        "output_paths": {
            "manifest": rel(args.out),
            "html": rel(args.html_out),
            "pdf": pdf_contract.get("path"),
        },
        "customer_export_validation": {
            "schema": validation.get("schema"),
            "status": validation.get("status"),
            "critical_count": validation.get("critical_count"),
            "warning_count": validation.get("warning_count"),
            "finding_count": len(validation.get("findings", [])),
        },
        "validation_counts": {
            "critical": validation.get("critical_count"),
            "warning": validation.get("warning_count"),
            "findings": len(validation.get("findings", [])),
        },
        "html_contract": html_contract,
        "pdf_contract": pdf_contract,
        "seeded_bad_status": seeded,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "next_safe_action": (
            "Keep this renderer internal and review-only; next safe work is operator review of the "
            "local HTML/PDF contract plus source/freshness/legal/compliance gates before any future "
            "customer or external delivery discussion."
        ),
        "validation": {},
    }
    payload["validation"] = validate_manifest(payload)
    if payload["validation"]["status"] != "ok":
        payload["status"] = "error"
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render WF75 customer-safe export to local HTML and optional PDF.")
    parser.add_argument("--input", type=Path, default=resolve_default_input(), help="Validated customer export JSON")
    parser.add_argument("--html-out", type=Path, default=DEFAULT_HTML, help="Local sanitized HTML output")
    parser.add_argument("--pdf-out", type=Path, default=DEFAULT_PDF, help="Optional local PDF output")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Renderer manifest output")
    parser.add_argument("--write", action="store_true", help="Write HTML, optional PDF, and manifest")
    parser.add_argument("--validate", action="store_true", help="Return non-zero if manifest validation fails")
    parser.add_argument("--no-pdf", dest="pdf", action="store_false", help="Skip local browser PDF attempt")
    parser.set_defaults(pdf=True)
    return parser.parse_args()


def absolutize(args: argparse.Namespace) -> argparse.Namespace:
    for attr in ("input", "html_out", "pdf_out", "out"):
        path = getattr(args, attr)
        if not path.is_absolute():
            setattr(args, attr, ROOT / path)
    return args


def main() -> int:
    args = absolutize(parse_args())
    payload = build_payload(args)
    if args.write:
        atomic_write_json(args.out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if (payload["validation"]["status"] == "ok" or not args.validate) else 1


if __name__ == "__main__":
    raise SystemExit(main())
