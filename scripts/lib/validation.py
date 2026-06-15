"""Small shared validation primitives for workspace scripts.

This module is intentionally tiny. Existing script entrypoints should keep their
CLI and JSON contracts while gradually reusing these helpers.
"""
from __future__ import annotations

from typing import Any


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def add_check(
    checks: list[dict[str, Any]],
    name: str,
    ok: bool,
    detail: Any = None,
    *,
    severity: str = "critical",
) -> None:
    checks.append({
        "name": name,
        "ok": bool(ok),
        "severity": severity,
        "detail": detail,
    })


def validation_from_checks(checks: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [str(check.get("name")) for check in checks if check.get("severity") == "critical" and not check.get("ok")]
    warnings = [str(check.get("name")) for check in checks if check.get("severity") == "warning" and not check.get("ok")]
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings,
        "check_count": len(checks),
    }


def ok_status(errors: list[Any], warnings: list[Any] | None = None) -> dict[str, Any]:
    return {
        "status": "ok" if not errors else "blocked",
        "errors": errors,
        "warnings": warnings or [],
    }

