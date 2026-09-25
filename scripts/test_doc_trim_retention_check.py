#!/usr/bin/env python3
"""Tests for doc_trim_retention_check (inline strings only)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from doc_trim_retention_check import check  # noqa: E402

ORIG = """# Note

## Log
Randall approved option B at 14:03. Proof `tmp/x/proof-1.json` and run 8a95105a-80f6-466e-805c-fd16fb1f6c88.
He said "Draft rules approved and continue".
Old artifact tmp/old/stale.json was superseded.

## Stop lines
- No capital action.
- No config mutation.
"""


class RetentionTests(unittest.TestCase):
    def test_complete_trim_has_nothing_missing(self) -> None:
        trimmed = ORIG
        r = check(ORIG, trimmed)
        self.assertEqual(r["missing_counts"], {"paths": 0, "run_ids": 0, "quotes": 0})
        self.assertTrue(r["verbatim_section_ok"])

    def test_dropped_facts_are_listed(self) -> None:
        trimmed = "# Note\n\n## Current\nOption B approved (`tmp/x/proof-1.json`).\n\n## Stop lines\n- No capital action.\n- No config mutation.\n"
        r = check(ORIG, trimmed)
        self.assertEqual(r["missing"]["paths"], ["tmp/old/stale.json"])
        self.assertEqual(r["missing_counts"]["run_ids"], 1)
        self.assertEqual(r["missing_counts"]["quotes"], 1)

    def test_paraphrased_stop_lines_fail(self) -> None:
        trimmed = ORIG.replace("- No config mutation.", "- Avoid config changes.")
        self.assertFalse(check(ORIG, trimmed)["verbatim_section_ok"])

    def test_missing_stop_lines_section_fails(self) -> None:
        self.assertFalse(check(ORIG, "# Note\n")["verbatim_section_ok"])

    def test_backslash_paths_match_forward_slash(self) -> None:
        orig = "## A\nsee `tmp\\a\\b.json`\n\n## Stop lines\n- x\n"
        trimmed = "## A\nsee tmp/a/b.json\n\n## Stop lines\n- x\n"
        self.assertEqual(check(orig, trimmed)["missing_counts"]["paths"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
