from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import artifact_index


WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT = WORKSPACE / "scripts" / "artifact_index.py"


class ArtifactIndexAlertsOsTests(unittest.TestCase):
    def test_discovery_is_explicit_and_excludes_retired_finance_families(self) -> None:
        self.assertEqual(artifact_index.MARKET_EVENT_GLOBS, [])
        self.assertEqual(artifact_index.DAILY_REVIEW_GLOBS, [])
        joined = "\n".join(artifact_index.TRUTH_SPINE_FILES).lower()
        for token in (
            "portfolio",
            "position-sizing",
            "deployment-readiness",
            "trade-grade",
            "paper-position",
            "canonical-finance-data-plane",
            "wf67",
            "wf78",
            "wf86",
            "wf87",
        ):
            self.assertNotIn(token, joined)

    def test_discovered_tmp_paths_are_allowlisted_current_proofs(self) -> None:
        allowlist = set(artifact_index.TRUTH_SPINE_FILES) | set(artifact_index.FILE_STATE_ONLY_FILES)
        for path in artifact_index.iter_artifact_paths():
            relative = path.relative_to(artifact_index.TMP).as_posix()
            if relative.startswith("official-ir-captures/"):
                continue
            self.assertIn(relative, allowlist)

    def test_cli_does_not_advertise_retired_mutation_or_execution_routes(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"],
            cwd=WORKSPACE,
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        help_text = result.stdout.lower()
        for token in (
            "phase3c-cache-write",
            "phase4a-activate",
            "canon-stage",
            "reconcile-sql-markdown",
            "answer-contract",
            "stoplines",
        ):
            self.assertNotIn(token, help_text)
        self.assertIn("ticker-card", help_text)
        self.assertIn("answer-packet", help_text)

    def test_rebuild_and_validation_accept_only_current_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "alerts-os-artifact-index.sqlite"
            rebuild = subprocess.run(
                [sys.executable, str(SCRIPT), "--db", str(db_path), "rebuild"],
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            self.assertIn("source_files=", rebuild.stdout)
            validation = subprocess.run(
                [sys.executable, str(SCRIPT), "--db", str(db_path), "validate", "--json"],
                cwd=WORKSPACE,
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
            report = json.loads(validation.stdout)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["summary"]["failed"], 0)


if __name__ == "__main__":
    unittest.main()
