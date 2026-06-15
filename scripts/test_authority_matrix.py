#!/usr/bin/env python3
"""Regression checks for the Veritas authority matrix."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "authority_matrix.py"


def load_module():
    spec = importlib.util.spec_from_file_location("authority_matrix", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load authority_matrix.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assert_ok(validation: dict) -> None:
    if validation.get("status") != "ok":
        raise AssertionError(validation)


def assert_error(validation: dict, token: str) -> None:
    errors = " ".join(validation.get("errors") or [])
    if validation.get("status") == "ok" or token not in errors:
        raise AssertionError({"expected_token": token, "validation": validation})


def main() -> int:
    authority_matrix = load_module()
    matrix = authority_matrix.build_matrix()
    validation = authority_matrix.validate_matrix(matrix)
    assert_ok(validation)

    rows = {row["row_id"]: row for row in matrix["rows"]}
    for row_id in [
        "ticker_import_staging",
        "ticker_import_production",
        "customer_profile_storage",
        "suitability_profile_storage",
        "account_connection_metadata",
        "credential_secret_storage",
        "external_customer_delivery",
    ]:
        if rows[row_id]["current_authority"]["allowed"] is not False:
            raise AssertionError(f"{row_id} must be blocked/not-approved")

    if rows["credential_reference_only"]["current_authority"]["allowed"] is not True:
        raise AssertionError("credential_reference_only should allow reference-only metadata")
    if rows["credential_secret_storage"]["current_authority"]["allowed"] is not False:
        raise AssertionError("credential_secret_storage must be blocked")
    if "secret value" not in " ".join(rows["credential_secret_storage"]["forbidden_data"]).lower():
        raise AssertionError("credential_secret_storage must explicitly forbid secret values")

    bad = copy.deepcopy(matrix)
    bad["rows"][0]["current_authority"]["allowed"] = True
    assert_error(authority_matrix.validate_matrix(bad), "ticker_import_staging")

    bad = copy.deepcopy(matrix)
    bad["global_boundary"]["external_customer_delivery_allowed"] = True
    assert_error(authority_matrix.validate_matrix(bad), "external_customer_delivery_allowed")

    bad = copy.deepcopy(matrix)
    bad["rows"] = [row for row in bad["rows"] if row["row_id"] != "credential_secret_storage"]
    assert_error(authority_matrix.validate_matrix(bad), "missing rows")

    bad = copy.deepcopy(matrix)
    rows_bad = {row["row_id"]: row for row in bad["rows"]}
    rows_bad["external_customer_delivery"]["automation_allowed"].append("send externally")
    assert_error(authority_matrix.validate_matrix(bad), "send externally")

    print("test_authority_matrix: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
