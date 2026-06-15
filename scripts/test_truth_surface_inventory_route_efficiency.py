from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import truth_surface_inventory as mod


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    row = mod.run_http_probe({
        "name": "optional_local_service",
        "url": "http://127.0.0.1:1/health",
        "target_seconds": 2.0,
        "timeout_seconds": 1,
        "optional_when_local_service_offline": True,
    })
    expect(row["status"] == "expected_offline", f"optional offline probe should be expected_offline: {row}", errors)
    expect(row["optional_when_local_service_offline"] is True, "optional flag should be preserved", errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("truth_surface_inventory_route_efficiency_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
