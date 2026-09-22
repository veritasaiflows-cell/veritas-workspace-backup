from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import chain_manifest


class ChainManifestRetiredStageTests(unittest.TestCase):
    """Guard: the 2026-08-29-retired market-state stage must stay out of the window manifests.

    Running the retired stage recreates tmp/market-state.json, which
    alerts_os_pivot_validator.py flags as resurrected retired state (see the
    2026-09-19 FOMC-refresh incident and tmp/quarantine/2026-09-20-cron-repair/).
    Precedent: test_run_alerts_recommendations_chain.py::test_legacy_market_state_refresh_is_not_a_stage.
    """

    def test_legacy_market_state_refresh_is_not_a_stage(self) -> None:
        for window in chain_manifest.window_names():
            steps = chain_manifest.manifest_steps(window)
            scripts = {str(step.get("script") or "") for step in steps}
            self.assertNotIn(
                "market_state_refresh.py",
                scripts,
                f"retired market_state_refresh.py must not be a stage in window '{window}'",
            )
            outputs = {
                output
                for step in steps
                for output in (step.get("expected_outputs") or [])
            }
            self.assertNotIn(
                "tmp/market-state.json",
                outputs,
                f"retired tmp/market-state.json must not be an expected output in window '{window}'",
            )
            for step in steps:
                self.assertNotIn(
                    "market_state_refresh.py",
                    list(step.get("depends_on") or []),
                    f"retired dependency on market_state_refresh.py in {step.get('script')} (window '{window}')",
                )


if __name__ == "__main__":
    unittest.main()
