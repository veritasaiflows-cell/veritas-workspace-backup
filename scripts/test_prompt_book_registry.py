#!/usr/bin/env python3
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import prompt_book_registry as registry


class PromptBookRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        (self.root / "06. Playbooks").mkdir(parents=True)
        (self.root / "scripts" / "prompts").mkdir(parents=True)
        (self.root / "tmp").mkdir(parents=True)
        (self.root / "06. Playbooks" / "Active Model Prompt Queue.md").write_text(
            "# Queue\n\n### 1) Test Prompt\n- Status: ready\n- Target model: openai/gpt-5.4\n\n```text\nDO NOT STORE THIS RAW PROMPT\n```\n",
            encoding="utf-8",
        )
        (self.root / "scripts" / "prompts" / "sample.md").write_text("raw prompt asset body", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_builds_metadata_only_registry(self) -> None:
        packet = registry.build_registry(self.root)
        self.assertGreaterEqual(packet["summary"]["entry_count"], 10)
        self.assertFalse(packet["summary"]["prompt_text_stored"])
        queue = packet["dynamic_sources"]["active_prompt_queue"]
        self.assertEqual(queue["entry_count"], 1)
        self.assertFalse(queue["raw_prompt_stored"])
        self.assertNotIn("DO NOT STORE THIS RAW PROMPT", str(packet))

    def test_validation_blocks_forbidden_raw_key(self) -> None:
        packet = registry.build_registry(self.root)
        packet["entries"][0]["raw_prompt"] = "bad"
        result = registry.validate_registry(packet, root=self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("forbidden key" in item for item in result["errors"]))

    def test_validation_blocks_duplicate_prompt_id(self) -> None:
        packet = registry.build_registry(self.root)
        packet["entries"][1]["prompt_id"] = packet["entries"][0]["prompt_id"]
        result = registry.validate_registry(packet, root=self.root)
        self.assertEqual(result["status"], "blocked")
        self.assertTrue(any("duplicate_prompt_id" in item for item in result["errors"]))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
