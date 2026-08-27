#!/usr/bin/env python3
from __future__ import annotations

import unittest

import prompt_book_linter as linter
import prompt_book_registry as registry


class PromptBookLinterTests(unittest.TestCase):
    def test_linter_reports_eval_gaps_without_blocking(self) -> None:
        packet = linter.build_lint_packet()
        self.assertIn(packet["status"], {"ok", "warning"})
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertFalse(packet["summary"]["prompt_text_stored"])

    def test_registry_validation_catches_system_prompt_key(self) -> None:
        packet = registry.build_registry()
        packet["entries"][0]["system_prompt"] = "bad"
        result = registry.validate_registry(packet)
        self.assertEqual(result["status"], "blocked")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
