from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import finance_cache_frontdoor as cache


class FinanceCacheFrontdoorTests(unittest.TestCase):
    def test_builds_only_from_active_controller_and_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            controller = root / "controller.json"
            digest = root / "digest.json"
            controller.write_text(
                '{"status":"ok","rows":[{"ticker":"AAA","alert_state":"monitor_only","level_relationship_state":"band_entry","alert_fire_eligible":false}]}',
                encoding="utf-8",
            )
            digest.write_text('{"status":"ok"}', encoding="utf-8")
            old_controller, old_digest = cache.CONTROLLER, cache.DIGEST
            try:
                cache.CONTROLLER, cache.DIGEST = controller, digest
                payload = cache.build_payload()
            finally:
                cache.CONTROLLER, cache.DIGEST = old_controller, old_digest
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["summary"]["monitor_only_count"], 1)
        self.assertEqual(payload["summary"]["fresh_intraday_alert_count"], 0)
        row = cache.row_by_ticker(payload, "aaa")
        self.assertTrue(row["safe_to_answer_from_cache"])
        self.assertFalse(row["alert_fire_eligible"])
        self.assertTrue(row["material_claim_requires_source_open"])

    def test_missing_source_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old_controller, old_digest = cache.CONTROLLER, cache.DIGEST
            try:
                cache.CONTROLLER = root / "missing-controller.json"
                cache.DIGEST = root / "missing-digest.json"
                payload = cache.build_payload()
            finally:
                cache.CONTROLLER, cache.DIGEST = old_controller, old_digest
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["validation"]["status"], "error")


if __name__ == "__main__":
    unittest.main()
