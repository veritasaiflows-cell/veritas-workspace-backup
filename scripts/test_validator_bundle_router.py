from __future__ import annotations

import validator_bundle_router as router


def test_command_allowed_blocks_shell_metacharacters() -> None:
    ok, reason = router.command_allowed("python scripts\\x.py && del y")
    assert ok is False
    assert reason.startswith("blocked_token")


def test_command_allowed_accepts_python_validator() -> None:
    ok, reason = router.command_allowed("python scripts\\fast_path_qa.py --write --validate")
    assert ok is True
    assert reason == "ok"


def test_select_recommendations_by_budget() -> None:
    recs = [
        {"command": "python a.py", "budget": "micro"},
        {"command": "python b.py", "budget": "major"},
    ]
    selected = router.select_recommendations(recs, "narrow")
    assert [item["command"] for item in selected] == ["python a.py"]


if __name__ == "__main__":
    test_command_allowed_blocks_shell_metacharacters()
    test_command_allowed_accepts_python_validator()
    test_select_recommendations_by_budget()
    print("ok")
