#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import workflow_checkpoint_runner as runner


class WorkflowCheckpointRunnerTests(unittest.TestCase):
    def write_config(self, root: Path, steps: list[dict]) -> Path:
        config = {
            "schema": runner.CONFIG_SCHEMA,
            "workflow_id": "TEST-WF",
            "description": "test checkpoint config",
            "db_path": "state/workflow-checkpoints/test-wf.sqlite",
            "out_path": "tmp/test-wf-checkpointed-execution.json",
            "authority_boundary": {"review_only": True, "owner_approval_inferred": False},
            "steps": steps,
        }
        path = root / "data" / "workflow-checkpoints" / "test-wf.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        return path

    def test_config_runner_pauses_and_resumes_without_rerunning_completed_step(self) -> None:
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
            config_path = self.write_config(
                root,
                [
                    {
                        "id": "first",
                        "command": [sys.executable, "scripts/write_step.py", "tmp/first.json", "tmp/marker.txt", "A"],
                        "expected_outputs": ["tmp/first.json"],
                        "input_paths": [],
                    },
                    {
                        "id": "second",
                        "command": [sys.executable, "scripts/write_step.py", "tmp/second.json", "tmp/marker.txt", "B"],
                        "expected_outputs": ["tmp/second.json"],
                        "input_paths": ["tmp/first.json"],
                    },
                ],
            )
            config = runner.load_config(config_path)
            db_path = root / "state" / "workflow-checkpoints" / "test-wf.sqlite"
            out_path = root / "tmp" / "summary.json"

            paused = runner.run_pipeline(
                root=root,
                config=config,
                db_path=db_path,
                out_path=out_path,
                run_id="test-run",
                resume=False,
                stop_after="first",
                write=True,
            )
            self.assertEqual(paused["run_status"], "paused")
            self.assertEqual(marker.read_text(encoding="utf-8"), "A")

            completed = runner.run_pipeline(
                root=root,
                config=config,
                db_path=db_path,
                out_path=out_path,
                run_id="test-run",
                resume=True,
                stop_after=None,
                write=True,
            )
            self.assertEqual(completed["run_status"], "complete")
            self.assertEqual(marker.read_text(encoding="utf-8"), "AB")
            self.assertIn("first", completed["skipped_steps"])
            validation = runner.validate_latest(root=root, config=config, db_path=db_path, out_path=out_path)
            self.assertEqual(validation["status"], "ok")

    def test_config_rejects_shell_metacharacter_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = self.write_config(
                root,
                [
                    {
                        "id": "bad",
                        "command": [sys.executable, "-c", "print('x')", "&&"],
                        "expected_outputs": ["tmp/out.json"],
                        "input_paths": [],
                    }
                ],
            )
            with self.assertRaises(ValueError):
                runner.load_config(config_path)

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
            config_path = self.write_config(
                root,
                [
                    {
                        "id": "only",
                        "command": [sys.executable, "scripts/write_step.py", "tmp/only.json"],
                        "expected_outputs": ["tmp/only.json"],
                        "input_paths": [],
                    }
                ],
            )
            config = runner.load_config(config_path)
            db_path = root / "state" / "workflow-checkpoints" / "test.sqlite"
            out_path = root / "tmp" / "summary.json"
            runner.run_pipeline(
                root=root,
                config=config,
                db_path=db_path,
                out_path=out_path,
                run_id="test-run",
                resume=False,
                stop_after="only",
                write=True,
            )
            validation = runner.validate_latest(root=root, config=config, db_path=db_path, out_path=out_path)
            self.assertEqual(validation["status"], "error")
            self.assertTrue(any(item.startswith("latest_run_not_complete") for item in validation["errors"]))


if __name__ == "__main__":
    unittest.main()
