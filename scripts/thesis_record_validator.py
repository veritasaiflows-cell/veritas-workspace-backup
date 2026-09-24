"""Validate structured thesis records in state/finance/thesis/ (stdlib only).

Checks the rules in state/finance/thesis/README.md against
thesis-record.schema.json: required fields, enums, no unknown top-level
fields, no position/execution fields anywhere, and that only an accepted
record carries an owner acceptance timestamp. Read-only.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

THESIS_REL = "state/finance/thesis"
SCHEMA_FILE = "thesis-record.schema.json"
FORBIDDEN = {"position", "positions", "quantity", "shares", "size", "sizing", "allocation", "weight",
             "holding", "holdings", "order", "orders", "cash", "tranche", "execution", "account"}


def _forbidden(obj: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if str(key).lower() in FORBIDDEN:
                hits.append(f"{path}.{key}".lstrip("."))
            hits.extend(_forbidden(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            hits.extend(_forbidden(value, f"{path}[{i}]"))
    return hits


def validate_record(record: dict, schema: dict, *, filename: str | None = None, today: date | None = None) -> dict:
    errors: list[str] = []
    props = schema["properties"]
    for key in schema["required"]:
        if key not in record:
            errors.append(f"missing {key}")
    for key in record:
        if key not in props:
            errors.append(f"unknown field {key}")
    for key in ("status", "thesis_type", "timeframe", "conviction"):
        allowed = props[key].get("enum")
        if key in record and allowed and record[key] not in allowed:
            errors.append(f"{key} {record[key]!r} not in {allowed}")
    if record.get("schema") != props["schema"]["const"]:
        errors.append("schema mismatch")
    stmt = record.get("thesis_statement") or ""
    if not (40 <= len(stmt) <= 600):
        errors.append("thesis_statement length outside 40-600")
    for case in ("base", "bull", "bear"):
        body = (record.get("cases") or {}).get(case) or {}
        if len(body.get("summary") or "") < 20 or not body.get("drivers"):
            errors.append(f"cases.{case} incomplete")
    if len(record.get("key_risks") or []) < 2:
        errors.append("key_risks needs at least 2")
    inv = record.get("invalidation_reasons") or {}
    if not inv.get("price") or not inv.get("fundamental"):
        errors.append("invalidation_reasons needs price and fundamental")
    if not record.get("evidence"):
        errors.append("evidence required")
    accepted = record.get("status") == "accepted"
    if accepted != bool(record.get("owner_accepted_at")):
        errors.append("owner_accepted_at must be set exactly when status is accepted")
    if filename and record.get("ticker") and Path(filename).stem != record["ticker"]:
        errors.append("filename does not match ticker")
    for hit in _forbidden(record):
        errors.append(f"forbidden position/execution field: {hit}")
    stale = False
    try:
        stale = date.fromisoformat(str(record.get("review_due"))) < (today or date.today())
    except ValueError:
        errors.append("review_due is not a date")
    return {"ticker": record.get("ticker"), "status": record.get("status"), "valid": not errors,
            "eligible": (not errors) and accepted and not stale, "review_overdue": stale, "errors": errors}


def validate_dir(root: Path, today: date | None = None) -> dict:
    folder = root / THESIS_REL
    schema = json.loads((folder / SCHEMA_FILE).read_text(encoding="utf-8"))
    results = []
    for path in sorted(folder.glob("*.json")):
        if path.name == SCHEMA_FILE:
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except ValueError as exc:
            results.append({"ticker": path.stem, "valid": False, "eligible": False, "errors": [f"invalid JSON: {exc}"]})
            continue
        results.append(validate_record(record, schema, filename=path.name, today=today))
    return {"status": "ok" if all(r["valid"] for r in results) else "error", "records": len(results),
            "eligible": [r["ticker"] for r in results if r["eligible"]], "results": results}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Validate structured thesis records (read-only).")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    report = validate_dir(Path(args.root))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
