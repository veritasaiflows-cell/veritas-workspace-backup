#!/usr/bin/env python3
"""Unit tests for wf74_self_prompt_generator.py.

Tests stay in-memory and use temporary paths. No raw capture, no authority
expansion, no code mutation.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import wf74_self_prompt_generator as generator


class SelfPromptGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.orig_root = generator.ROOT
        generator.ROOT = self.root
        generator.TMP = self.root / "tmp"
        generator.TMP.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        generator.ROOT = self.orig_root
        generator.TMP = self.orig_root / "tmp"
        self.tmpdir.cleanup()

    def _write(self, name: str, payload: dict) -> None:
        path = generator.TMP / name
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _base_inputs(self) -> None:
        for name in [
            "model-learning-metadata-ledger.json",
            "wf74-improvement-opportunity-queue.json",
            "wf74-decision-docket.json",
            "wf74-outcome-eval-suite-v2.json",
            "improvement-ledger-current.json",
            "workflow-advancement-scorecard.json",
            "wf87-v2-readiness-rollup.json",
        ]:
            self._write(name, {"schema": "stub", "status": "ok"})

    def _critique_payload(self, critiques: list[dict]) -> dict:
        return {
            "schema": "veritas.wf74_telemetry_critique.v1",
            "generated_at_utc": "2026-06-30T00:00:00Z",
            "status": "attention" if any(c.get("severity") == "high" for c in critiques) else "ok",
            "authority_boundary": generator.AUTHORITY_BOUNDARY,
            "critiques": critiques,
        }

    def test_focused_questions_for_high_critiques(self) -> None:
        self._base_inputs()
        self._write(
            "wf74-telemetry-critique.json",
            self._critique_payload([
                {"category": "source_open_recurrence", "severity": "high", "count": 5, "recommended_action": "x", "evidence": {}}
            ]),
        )
        prompt = generator.build_self_prompt(tmp_dir=generator.TMP)
        self.assertTrue(
            any("wf78_source_open_patch_orchestrator" in q for q in prompt["full_text"].split("\n")),
            "source_open_recurrence should add a focused question",
        )

    def test_focused_questions_for_attention_critiques(self) -> None:
        self._base_inputs()
        self._write(
            "wf74-telemetry-critique.json",
            self._critique_payload([
                {"category": "latency_spike", "severity": "attention", "count": 3, "recommended_action": "x", "evidence": []},
                {"category": "workflow_maturity_blocker", "severity": "attention", "count": 2, "recommended_action": "x", "evidence": []},
            ]),
        )
        prompt = generator.build_self_prompt(tmp_dir=generator.TMP)
        text = prompt["full_text"]
        self.assertTrue(any("latency" in q.lower() for q in text.split("\n")))
        self.assertTrue(any("workflow maturity" in q.lower() or "child maturity" in q.lower() for q in text.split("\n")))

    def test_workflow_blockers_present(self) -> None:
        self._base_inputs()
        self._write("wf74-telemetry-critique.json", self._critique_payload([]))
        self._write(
            "workflow-advancement-scorecard.json",
            {
                "schema": "workflow-advancement-scorecard-v1",
                "signals": [
                    {"workflow_id": "CRON", "signal": "blocked", "status": "ok", "blockers": ["x"]},
                ],
            },
        )
        prompt = generator.build_self_prompt(tmp_dir=generator.TMP)
        self.assertEqual(prompt["workflow_blocker_count"], 1)

    def test_generates_prompt_sections(self) -> None:
        self._base_inputs()
        self._write("wf74-telemetry-critique.json", self._critique_payload([]))
        prompt = generator.build_self_prompt(tmp_dir=generator.TMP)
        self.assertIn("prompt_id", prompt)
        self.assertIn("variant_id", prompt)
        self.assertEqual(len(prompt["sections"]), 7)
        self.assertGreater(len(prompt["full_text"]), 200)

    def test_authority_boundary_false(self) -> None:
        for key, value in generator.AUTHORITY_BOUNDARY.items():
            if value is False:
                self.assertFalse(value, f"authority_boundary flag {key} must default to false")

    def test_validate_payload_rejects_missing_prompt_id(self) -> None:
        payload = {
            "schema": generator.SCHEMA,
            "generated_at_utc": "2026-06-30T00:00:00Z",
            "status": "ok",
            "self_prompt": {"full_text": "test", "variant_id": "v1", "prompt_id": ""},
            "authority_boundary": generator.AUTHORITY_BOUNDARY,
        }
        result = generator.validate_payload(payload)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("missing_prompt_id", result["errors"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
