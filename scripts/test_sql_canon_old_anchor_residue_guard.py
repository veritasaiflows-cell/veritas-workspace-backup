from __future__ import annotations

from pathlib import Path

from sql_canon_old_anchor_residue_guard import build_report


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_guard_blocks_retired_anchor_in_active_surface(tmp_path: Path) -> None:
    write(
        tmp_path / "state" / "workflows" / "WF72.json",
        '{"validator_commands":["python scripts\\\\execution_board_canon_anchor_pilot.py --write --validate"]}',
    )

    report = build_report(tmp_path, ["state/workflows/WF72.json"])

    assert report["status"] == "blocked"
    assert report["summary"]["finding_count"] == 1
    assert "execution_board_canon_anchor_pilot.py" in report["findings"][0]["patterns"]


def test_guard_allows_sql_first_route_surface(tmp_path: Path) -> None:
    write(
        tmp_path / "state" / "workflows" / "WF72.json",
        '{"validator_commands":["python scripts\\\\reference_levels_sql_native_source_family_proof.py --write --validate"]}',
    )

    report = build_report(tmp_path, ["state/workflows/WF72.json"])

    assert report["status"] == "ok"
    assert report["summary"]["finding_count"] == 0
