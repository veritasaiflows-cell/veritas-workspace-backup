from __future__ import annotations

import copy
import json
import shutil
from datetime import date
from pathlib import Path

import thesis_record_validator as v

WORKSPACE = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((WORKSPACE / v.THESIS_REL / v.SCHEMA_FILE).read_text(encoding="utf-8"))
LIN = json.loads((WORKSPACE / v.THESIS_REL / "LIN.json").read_text(encoding="utf-8"))


def test_live_records_are_valid() -> None:
    report = v.validate_dir(WORKSPACE, today=date(2026, 9, 24))
    assert report["status"] == "ok", report


def test_acceptance_makes_eligible_until_review_due() -> None:
    rec = copy.deepcopy(LIN)
    rec["status"] = "accepted"; rec["owner_accepted_at"] = "2026-09-24T09:00:00-07:00"
    assert v.validate_record(rec, SCHEMA, today=date(2026, 9, 24))["eligible"]
    overdue = v.validate_record(rec, SCHEMA, today=date(2027, 1, 1))
    assert overdue["valid"] and not overdue["eligible"] and overdue["review_overdue"]


def test_acceptance_timestamp_must_match_status() -> None:
    rec = copy.deepcopy(LIN); rec["status"] = "draft"; rec["owner_accepted_at"] = "2026-09-24T09:00:00-07:00"
    assert not v.validate_record(rec, SCHEMA)["valid"]
    rec["status"] = "accepted"; rec["owner_accepted_at"] = None
    assert not v.validate_record(rec, SCHEMA)["valid"]


def test_position_fields_and_unknown_fields_rejected() -> None:
    rec = copy.deepcopy(LIN); rec["cases"]["base"]["allocation"] = 0.05
    assert any("forbidden" in e for e in v.validate_record(rec, SCHEMA)["errors"])
    rec = copy.deepcopy(LIN); rec["target_weight"] = 1
    assert any("unknown field" in e for e in v.validate_record(rec, SCHEMA)["errors"])


def test_bad_enum_and_missing_cases(tmp_path: Path) -> None:
    rec = copy.deepcopy(LIN); rec["thesis_type"] = "moonshot"; del rec["cases"]["bear"]
    errors = v.validate_record(rec, SCHEMA)["errors"]
    assert any("thesis_type" in e for e in errors) and any("cases.bear" in e for e in errors)
    folder = tmp_path / v.THESIS_REL
    folder.mkdir(parents=True)
    shutil.copy(WORKSPACE / v.THESIS_REL / v.SCHEMA_FILE, folder / v.SCHEMA_FILE)
    (folder / "XYZ.json").write_text(json.dumps(LIN), encoding="utf-8")
    assert v.validate_dir(tmp_path)["status"] == "error"  # filename/ticker mismatch
