from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path

import thesis_record_validator as validator
import weekly_thesis_review as review

WORKSPACE = Path(__file__).resolve().parents[1]


def seed(tmp: Path, *, lin_period: str | None = "2026-06-30", fund_period: str = "2026-06-30") -> Path:
    folder = tmp / validator.THESIS_REL
    folder.mkdir(parents=True)
    shutil.copy(WORKSPACE / validator.THESIS_REL / validator.SCHEMA_FILE, folder / validator.SCHEMA_FILE)
    lin = json.loads((WORKSPACE / validator.THESIS_REL / "LIN.json").read_text(encoding="utf-8"))
    lin["fundamentals_period_end"] = lin_period
    (folder / "LIN.json").write_text(json.dumps(lin), encoding="utf-8")
    (tmp / "tmp").mkdir()
    (tmp / review.CONTROLLER_REL).write_text(json.dumps({"rows": [{"ticker": "LIN"}, {"ticker": "NEW"}]}), encoding="utf-8")
    (tmp / review.FUNDAMENTALS_REL).write_text(json.dumps({"rows": [{"ticker": "LIN", "period_end": fund_period}]}), encoding="utf-8")
    return tmp


def test_flags_missing_thesis_and_nothing_else(tmp_path: Path) -> None:
    r = review.build_review(seed(tmp_path), today=date(2026, 9, 24))
    assert r["flags"] == {"NEW": ["missing_thesis"]} and r["eligible"] == ["LIN"] and r["status"] == "ok"


def test_new_quarter_flag(tmp_path: Path) -> None:
    r = review.build_review(seed(tmp_path, fund_period="2026-09-30"), today=date(2026, 9, 24))
    assert r["flags"]["LIN"] == ["new_quarter"] and r["status"] == "attention"


def test_review_overdue_flag(tmp_path: Path) -> None:
    r = review.build_review(seed(tmp_path), today=date(2027, 1, 5))
    assert "review_overdue" in r["flags"]["LIN"]


def test_run_passes_scope_to_refresh_and_writes_review(tmp_path: Path) -> None:
    root = seed(tmp_path)
    calls = []

    def runner(argv, cwd):
        calls.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout="ok", stderr="")
    r = review.run(root, python="py", runner=runner)
    assert calls and calls[0][calls[0].index("--tickers") + 1:calls[0].index("--merge-existing")] == ["LIN", "NEW"]
    assert (root / review.REVIEW_REL).is_file() and r["steps"]["fundamentals_refresh"]["rc"] == 0
    assert any("recommendation_funnel.py" in " ".join(c) for c in calls)


def test_refresh_failure_is_error(tmp_path: Path) -> None:
    r = review.run(seed(tmp_path), python="py",
                   runner=lambda a, c: subprocess.CompletedProcess(a, 1, stdout="", stderr="boom"))
    assert r["status"] == "error"
