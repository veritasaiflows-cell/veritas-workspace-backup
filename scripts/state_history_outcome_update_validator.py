from __future__ import annotations

import argparse
import json
from pathlib import Path

from market_data_utils import atomic_write_json
from state_history_outcome_update import DEFAULT_OUTPUT, ROOT, STATE_HISTORY, validate_file

DEFAULT_REPORT = ROOT / "tmp" / "state-history-outcome-update-validation.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate WF55 retained realized-outcome sidecar rows.")
    parser.add_argument("--input", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--state-history", type=Path, default=STATE_HISTORY)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    state_history_path = args.state_history if args.state_history.is_absolute() else ROOT / args.state_history
    report = validate_file(input_path, state_history_path)
    if args.write:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        atomic_write_json(output, report)
        print(f"state_history_outcome_update_validation_written status={report.get('status')} critical={report.get('critical')} warning={report.get('warning')} path={output.relative_to(ROOT).as_posix()}")
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report.get("critical") == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
