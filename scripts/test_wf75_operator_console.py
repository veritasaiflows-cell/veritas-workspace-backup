from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from wf75_operator_console import AUTHORITY_FALSE_KEYS, build_console, validate  # noqa: E402
from wf75_service_state_sqlite import write_db  # noqa: E402


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_live_shaped_console_from_temp_db(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        db_path = Path(td) / "wf75-service-state.sqlite"
        write_db(db_path)
        console = build_console(db_path)
        result = validate(console)
        expect(result["status"] == "ok", f"console validation failed: {result}", errors)
        expect(console["status"] == "ready", "console should be ready", errors)
        expect(console["summary"]["queue_count"] >= 1, "console should show queue rows", errors)
        expect(console["summary"]["pm_brief_status"] == "ready", "PM brief should be ready", errors)
        lifecycle = {row["stage"]: row["status"] for row in console["service_lifecycle"]}
        expect(lifecycle.get("ready_for_pm_handoff") == "completed", "handoff lifecycle should be completed", errors)
        expect(lifecycle.get("pm_brief_rendered") == "completed", "PM brief lifecycle should be completed", errors)
        for key in AUTHORITY_FALSE_KEYS:
            expect(console["authority_boundary"].get(key) is False, f"authority flag must be false: {key}", errors)


def test_missing_db_fails_closed(errors: list[str]) -> None:
    with TemporaryDirectory() as td:
        console = build_console(Path(td) / "missing.sqlite")
        expect(console["status"] == "blocked", "missing DB should block console", errors)
        expect(console["validation"]["status"] == "error", "missing DB validation should error", errors)


def main() -> int:
    errors: list[str] = []
    test_live_shaped_console_from_temp_db(errors)
    test_missing_db_fails_closed(errors)
    if errors:
        print("wf75_operator_console_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf75_operator_console_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
