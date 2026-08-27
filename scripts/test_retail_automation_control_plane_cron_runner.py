from pathlib import Path
import sys


SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import retail_automation_control_plane_cron_runner as runner


def test_review_only_plan_does_not_write_pm_database() -> None:
    plan = {name: command for name, command, _timeout in runner.command_plan()}
    command = plan["pm_program_state"]

    assert "--write-db" not in command
    assert "--write" in command
    assert "--validate" in command
    assert runner.AUTHORITY_BOUNDARY["review_only"] is True
    assert runner.AUTHORITY_BOUNDARY["sql_write_or_import_allowed"] is False

