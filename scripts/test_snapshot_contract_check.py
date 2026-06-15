from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "scripts"))

import snapshot_contract_check as checker  # noqa: E402


BUCKETS = {
    "deployable_now": ["ETN"],
    "promotion_review": ["JPM"],
    "almost_deployable": ["MSFT"],
    "blocked": [],
    "do_not_touch": ["LMT"],
    "watch": ["VRT"],
    "error": [],
}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def run_case(snapshot: dict[str, Any], expect_ok: bool) -> tuple[int, dict[str, Any]]:
    with tempfile.TemporaryDirectory() as tmp_dir:
        root = Path(tmp_dir)
        tmp = root / "tmp"
        checker.TRIGGER_PATH = tmp / "trigger-sheet.json"
        checker.PREMARKET_PATH = tmp / "premarket-snapshot.json"
        checker.POSTMARKET_PATH = tmp / "postmarket-snapshot.json"
        checker.OUT_PATH = tmp / "snapshot-contract-check.json"

        write_json(checker.TRIGGER_PATH, {"summary": BUCKETS})
        write_json(checker.POSTMARKET_PATH, snapshot)
        rc = checker.main(["--window", "post-close"])
        report = json.loads(checker.OUT_PATH.read_text(encoding="utf-8"))
        if expect_ok and rc != 0:
            raise AssertionError(f"expected ok return code, got {rc}: {report}")
        if not expect_ok and rc == 0:
            raise AssertionError(f"expected failure return code, got {rc}: {report}")
        return rc, report


def main() -> int:
    errors: list[str] = []

    good_snapshot = {"generated_at_utc": "2026-05-11T22:57:42+00:00", **BUCKETS}
    _, good_report = run_case(good_snapshot, expect_ok=True)
    if good_report.get("status") != "ok":
        errors.append(f"expected good fixture status ok, got {good_report.get('status')}")

    missing_negative_bucket = dict(good_snapshot)
    missing_negative_bucket.pop("do_not_touch")
    _, missing_report = run_case(missing_negative_bucket, expect_ok=False)
    if missing_report.get("status") != "critical":
        errors.append("expected missing do_not_touch bucket to be critical")
    if not any(error.get("field") == "do_not_touch" for error in missing_report.get("errors", [])):
        errors.append("expected missing do_not_touch error")

    mismatched_snapshot = {"generated_at_utc": "2026-05-11T22:57:42+00:00", **BUCKETS, "do_not_touch": []}
    _, mismatch_report = run_case(mismatched_snapshot, expect_ok=False)
    if not any(error.get("field") == "do_not_touch" for error in mismatch_report.get("errors", [])):
        errors.append("expected do_not_touch mismatch error")

    duplicate_snapshot = {"generated_at_utc": "2026-05-11T22:57:42+00:00", **BUCKETS, "almost_deployable": ["MSFT", "LMT"]}
    _, duplicate_report = run_case(duplicate_snapshot, expect_ok=False)
    if not any(error.get("field") == "summary_buckets" for error in duplicate_report.get("errors", [])):
        errors.append("expected duplicate bucket membership error")

    if errors:
        print("snapshot contract check test failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("snapshot contract check test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
