#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tmp_lifecycle_guard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("tmp_lifecycle_guard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_preview_classifies_stale_unreferenced_without_cleanup_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        module.OUT = module.TMP / "tmp-lifecycle-guard.json"
        module.SPIRE_OUT = module.TMP / "tmp-artifact-spire.json"
        module.TMP.mkdir()
        stale = module.TMP / "old-proof.json"
        stale.write_text("{}", encoding="utf-8")
        old_time = time.time() - (20 * 86400)
        stale.touch()
        import os
        os.utime(stale, (old_time, old_time))
        write_json(module.TMP / "cron-freshness-spine.json", {
            "jobs": [{
                "expected_artifacts": [{"path": "tmp/protected.json"}],
            }]
        })
        protected = module.TMP / "protected.json"
        protected.write_text("{}", encoding="utf-8")
        os.utime(protected, (old_time, old_time))

        payload = module.build_payload(stale_days=14)

        assert payload["authority_boundary"]["delete_allowed"] is False
        assert payload["authority_boundary"]["archive_allowed"] is False
        samples = {row["path"]: row for row in payload["cleanup_preview_samples"]}
        assert "tmp/old-proof.json" in samples
        assert samples["tmp/old-proof.json"]["cleanup_preview_eligible"] is True
        assert "tmp/protected.json" not in samples
        assert payload["summary"]["cleanup_preview_eligible_count"] == 1


if __name__ == "__main__":
    test_preview_classifies_stale_unreferenced_without_cleanup_authority()
    print("tmp lifecycle guard tests passed")
