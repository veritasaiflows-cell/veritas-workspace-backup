#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "workspace_boundary_check.py"


def load_module():
    spec = importlib.util.spec_from_file_location("workspace_boundary_check", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_documented_durable_data_surfaces_are_allowed() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        data = root / "data"
        data.mkdir()
        (data / "vector-memory-sources.json").write_text("{}", encoding="utf-8")
        for name in ("wf74-learning-loop-evals", "workflow-checkpoints"):
            path = data / name
            path.mkdir()
            (path / "README.md").write_text("# Authority\n", encoding="utf-8")
        module.ROOT = root

        findings = module.classify_data_surface()

        assert findings == []


def test_approved_data_directory_still_requires_readme() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        path = root / "data" / "workflow-checkpoints"
        path.mkdir(parents=True)
        module.ROOT = root

        findings = module.classify_data_surface()

        assert len(findings) == 1
        assert findings[0]["path"] == "data/workflow-checkpoints/"
        assert "missing README" in findings[0]["issue"]


if __name__ == "__main__":
    test_documented_durable_data_surfaces_are_allowed()
    test_approved_data_directory_still_requires_readme()
    print("workspace boundary check tests passed")
