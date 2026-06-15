#!/usr/bin/env python3
"""Manage lightweight workflow control overrides.

Overrides are routing-control only. They suppress or resume workflow routing
state without mutating canon, portfolio, customer, SQL, cron, paper, live, or
account systems.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lib.workflow_control import (
    OVERRIDE_PATH,
    hold_override,
    load_registry,
    resume_override,
    validation_errors,
)


def print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manage workflow routing overrides.")
    sub = parser.add_subparsers(dest="action", required=True)

    hold = sub.add_parser("hold", help="Put a workflow/lane on hold.")
    hold.add_argument("workflow_key")
    hold.add_argument("--reason", required=True)
    hold.add_argument("--set-by", default="Randall")
    hold.add_argument("--set-at-local")
    hold.add_argument("--resume-condition")
    hold.add_argument("--alias", action="append", default=[])
    hold.add_argument("--validate", action="store_true")

    resume = sub.add_parser("resume", help="Remove a workflow/lane hold override.")
    resume.add_argument("workflow_key")
    resume.add_argument("--validate", action="store_true")

    listing = sub.add_parser("list", help="List workflow overrides.")
    listing.add_argument("--validate", action="store_true")

    validate = sub.add_parser("validate", help="Validate the override registry.")
    validate.add_argument("--path", default=str(OVERRIDE_PATH))

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.action == "hold":
        item = hold_override(
            args.workflow_key,
            reason=args.reason,
            set_by=args.set_by,
            set_at_local=args.set_at_local,
            resume_condition=args.resume_condition,
            aliases=args.alias,
        )
        payload = {"status": "ok", "workflow_key": args.workflow_key, "override": item}
        if args.validate:
            errors = validation_errors(load_registry())
            payload["validation"] = {"status": "ok" if not errors else "error", "errors": errors}
        print_json(payload)
        return 0 if payload.get("validation", {}).get("status", "ok") == "ok" else 1

    if args.action == "resume":
        removed = resume_override(args.workflow_key)
        payload = {"status": "ok", "workflow_key": args.workflow_key, "removed": removed}
        if args.validate:
            errors = validation_errors(load_registry())
            payload["validation"] = {"status": "ok" if not errors else "error", "errors": errors}
        print_json(payload)
        return 0 if payload.get("validation", {}).get("status", "ok") == "ok" else 1

    if args.action == "list":
        payload = load_registry()
        if args.validate:
            errors = validation_errors(payload)
            payload["validation"] = {"status": "ok" if not errors else "error", "errors": errors}
        print_json(payload)
        return 0 if payload.get("validation", {}).get("status", "ok") == "ok" else 1

    if args.action == "validate":
        payload = load_registry(Path(args.path))
        errors = validation_errors(payload)
        print_json({"status": "ok" if not errors else "error", "errors": errors, "path": args.path})
        return 0 if not errors else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
