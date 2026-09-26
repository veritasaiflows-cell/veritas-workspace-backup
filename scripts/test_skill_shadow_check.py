from __future__ import annotations

import json
import tempfile
from pathlib import Path

import skill_shadow_check as ssc


def setup(tmp: Path, loaded: str, workshop: str, *, extra_ref: bool = False) -> tuple[Path, Path, Path]:
    state = tmp / "state"
    ws = tmp / "ws"
    (ws / "skills" / "alpha").mkdir(parents=True)
    (ws / "skills" / "alpha" / "SKILL.md").write_text(loaded, encoding="utf-8")
    wk = state / "agents" / "main" / "agent" / "workshop-skills"
    (wk / "alpha").mkdir(parents=True)
    (wk / "alpha" / "SKILL.md").write_bytes(workshop.encode("utf-8"))
    if extra_ref:
        (wk / "alpha" / "references").mkdir()
        (wk / "alpha" / "references" / "x.md").write_text("x", encoding="utf-8")
    (wk / "beta").mkdir()  # Workshop-only skill: not shadowed, not reported
    (wk / "beta" / "SKILL.md").write_text("b", encoding="utf-8")
    config = tmp / "openclaw.json"
    config.write_text(json.dumps({"agents": {"entries": {"main": {"workspace": str(ws)}}}}), encoding="utf-8")
    return config, state, tmp / "ack.json"


def test_identical_after_crlf_normalization() -> None:
    with tempfile.TemporaryDirectory() as t:
        config, state, ack = setup(Path(t), "a\nb\n", "a\r\nb\r\n")
        payload = ssc.build(config, state, ack)
        assert payload["status"] == "ok"
        assert [r["status"] for r in payload["rows"]] == ["identical"]


def test_new_divergence_fails_and_reports_delta() -> None:
    with tempfile.TemporaryDirectory() as t:
        config, state, ack = setup(Path(t), "old", "new", extra_ref=True)
        payload = ssc.build(config, state, ack)
        assert payload["status"] == "error"
        row = payload["rows"][0]
        assert row["status"] == "new"
        assert row["delta"] == {"changed": ["SKILL.md"], "workshop_only": ["references/x.md"], "loaded_only": []}
        assert ssc.main(["--config", str(config), "--state-dir", str(state), "--ack", str(ack), "--validate"]) == 1


def test_acknowledged_divergence_is_quiet_until_content_changes() -> None:
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        config, state, ack = setup(tmp, "old", "new")
        assert ssc.main(["acknowledge", "--config", str(config), "--state-dir", str(state), "--ack", str(ack), "--reason", "pending sync"]) == 0
        payload = ssc.build(config, state, ack)
        assert payload["status"] == "ok"
        assert payload["rows"][0]["acknowledged_reason"] == "pending sync"
        wk = state / "agents" / "main" / "agent" / "workshop-skills" / "alpha" / "SKILL.md"
        wk.write_text("newer reviewer edit", encoding="utf-8")
        assert ssc.build(config, state, ack)["rows"][0]["status"] == "new"


def test_acknowledge_requires_reason() -> None:
    with tempfile.TemporaryDirectory() as t:
        config, state, ack = setup(Path(t), "old", "new")
        assert ssc.main(["acknowledge", "--config", str(config), "--state-dir", str(state), "--ack", str(ack)]) == 2
        assert not ack.exists()


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-q"]))
