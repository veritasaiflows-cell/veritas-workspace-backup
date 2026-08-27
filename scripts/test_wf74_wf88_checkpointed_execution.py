#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import wf74_wf88_checkpointed_execution as runner


class WF74WF88CheckpointedExecutionTests(unittest.TestCase):
    def test_runner_pauses_and_resumes_without_rerunning_completed_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            (root / "scripts").mkdir()
            marker = root / "tmp" / "marker.txt"
            script = root / "scripts" / "write_step.py"
            script.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "out = Path(sys.argv[1])\n"
                "marker = Path(sys.argv[2])\n"
                "marker.write_text(marker.read_text() + sys.argv[3] if marker.exists() else sys.argv[3])\n"
                "out.parent.mkdir(parents=True, exist_ok=True)\n"
                "out.write_text(sys.argv[3])\n",
                encoding="utf-8",
            )
            steps = [
                runner.Step(
                    "first",
                    [sys.executable, "scripts/write_step.py", "tmp/first.json", "tmp/marker.txt", "A"],
                    ["tmp/first.json"],
                    [],
                ),
                runner.Step(
                    "second",
                    [sys.executable, "scripts/write_step.py", "tmp/second.json", "tmp/marker.txt", "B"],
                    ["tmp/second.json"],
                    ["tmp/first.json"],
                ),
            ]
            db_path = root / "state" / "workflow-checkpoints" / "test.sqlite"
            out_path = root / "tmp" / "summary.json"

            paused = runner.run_pipeline(
                root=root,
                db_path=db_path,
                out_path=out_path,
                steps=steps,
                run_id="test-run",
                resume=False,
                stop_after="first",
                write=True,
            )
            self.assertEqual(paused["run_status"], "paused")
            self.assertEqual(marker.read_text(encoding="utf-8"), "A")

            completed = runner.run_pipeline(
                root=root,
                db_path=db_path,
                out_path=out_path,
                steps=steps,
                run_id="test-run",
                resume=True,
                stop_after=None,
                write=True,
            )
            self.assertEqual(completed["run_status"], "complete")
            self.assertEqual(marker.read_text(encoding="utf-8"), "AB")
            self.assertIn("first", completed["skipped_steps"])

    def test_validation_fails_when_latest_run_is_paused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tmp").mkdir()
            (root / "scripts").mkdir()
            script = root / "scripts" / "write_step.py"
            script.write_text(
                "from pathlib import Path\n"
                "import sys\n"
                "Path(sys.argv[1]).write_text('ok')\n",
                encoding="utf-8",
            )
            steps = [
                runner.Step("only", [sys.executable, "scripts/write_step.py", "tmp/only.json"], ["tmp/only.json"], [])
            ]
            db_path = root / "state" / "workflow-checkpoints" / "test.sqlite"
            out_path = root / "tmp" / "summary.json"
            runner.run_pipeline(
                root=root,
                db_path=db_path,
                out_path=out_path,
                steps=steps,
                run_id="test-run",
                resume=False,
                stop_after="only",
                write=True,
            )
            validation = runner.validate_latest(root=root, db_path=db_path, out_path=out_path)
            self.assertEqual(validation["status"], "error")
            self.assertTrue(any(item.startswith("latest_run_not_complete") for item in validation["errors"]))


if __name__ == "__main__":
    unittest.main()
