"""Regression coverage for the season-aware lifecycle presence check.

Owner-approved 2026-09-20: the NVDA lifecycle canary must pass off-season
(empty table, source indexed) while still failing on partial drops, missing
sources, and genuinely empty builds.
"""
from __future__ import annotations

import unittest

from artifact_index import lifecycle_presence_ok


class LifecyclePresenceTest(unittest.TestCase):
    def test_nvda_present_passes(self):
        ok, detail = lifecycle_presence_ok(3, 5, True)
        self.assertTrue(ok)
        self.assertIn("nvda_rows=3", detail)

    def test_off_season_empty_indexed_passes(self):
        ok, detail = lifecycle_presence_ok(0, 0, True)
        self.assertTrue(ok)
        self.assertEqual(detail, "off_season_empty_source_indexed")

    def test_empty_unindexed_fails(self):
        ok, _ = lifecycle_presence_ok(0, 0, False)
        self.assertFalse(ok)

    def test_partial_drop_missing_nvda_fails(self):
        ok, detail = lifecycle_presence_ok(0, 4, True)
        self.assertFalse(ok)
        self.assertIn("total_rows=4", detail)


if __name__ == "__main__":
    unittest.main()
