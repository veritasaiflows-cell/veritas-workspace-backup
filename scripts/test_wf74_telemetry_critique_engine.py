#!/usr/bin/env python3
"""Unit tests for wf74_telemetry_critique_engine.py.

Tests stay in-memory and use temporary paths. No raw prompt/response capture,
no canon/portfolio mutation, no cron mutation.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import wf74_telemetry_critique_engine as engine


class TelemetryCritiqueTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.orig_root = engine.ROOT
        engine.ROOT = self.root
        engine.TMP = self.root / "tmp"
        engine.TMP.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        engine.ROOT = self.orig_root
        engine.TMP = self.orig_root / "tmp"
        self.tmpdir.cleanup()

    def _write(self, name: str, payload: dict) -> None:
        path = engine.TMP / name
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _base_otel(self, token_coverage_ratio: float = 0.05) -> dict:
        return {
            "schema": "veritas.otel_learning_loop.v1",
            "generated_at_utc": "2026-06-30T00:00:00Z",
            "status": "ok",
            "learning_summaries": {
                "token_cost": {
                    "model_applicable_rows": 100,
                    "token_coverage_rows": int(100 * token_coverage_ratio),
                    "token_coverage_ratio": token_coverage_ratio,
                    "cost_coverage_rows": int(100 * token_coverage_ratio),
                    "cost_coverage_ratio": token_coverage_ratio,
                    "avg_duration_ms": 50000.0,
                }
            },
        }

    def _base_model_run(self, durations: list[float]) -> dict:
        return {
            "schema": "wf74.model_run_ledger.v1",
            "generated_at_utc": "2026-06-30T00:00:00Z",
            "status": "ok",
            "rows": [
                {
                    "row_id": f"r{i}",
                    "model_path": "openai/gpt-5.4-mini",
                    "duration_ms": d,
                    "producer": "openclaw_cron_runs",
                    "run_kind": "cron_agent_turn",
                }
                for i, d in enumerate(durations)
            ],
        }

    def _base_frq(self, *, source_open: int = 0, source_freshness: int = 0) -> dict:
        return {
            "schema": "veritas.finance_response_quality_slice.v1",
            "generated_at_utc": "2026-06-30T00:00:00Z",
            "status": "ok",
            "summary": {
                "source_open_blocked_count": source_open,
                "source_freshness_blocked_count": source_freshness,
                "primary_state_blocked_count": 0,
                "below_stop_blocked_count": 0,
            },
        }

    def _base_workflow_advancement(self, signals: list[dict]) -> dict:
        return {
            "schema": "workflow-advancement-scorecard-v1",
            "generated_at_utc": "2026-06-30T00:00:00Z",
            "status": "ok",
            "signals": signals,
        }

    def _base_ledger(self, items: list[dict]) -> dict:
        return {
            "schema": "veritas.improvement_ledger_current.v1",
            "generated_at_utc": "2026-06-30T00:00:00Z",
            "status": "ok",
            "items": items,
        }

    def _base_inputs(self) -> None:
        for name in [
            "model-learning-metadata-ledger.json",
            "validator-timing-ledger.json",
            "coding-runtime-kpi-probe.json",
            "changed-file-validator-router.json",
            "route-efficiency-scorecard.json",
            "wf74-model-quality-collection-cron-runner.json",
            "wf74-improvement-opportunity-queue.json",
            "wf87-shadow-outcome-scorecard.json",
            "wf87-v2-readiness-rollup.json",
        ]:
            self._write(name, {"schema": "stub", "status": "ok"})

    def test_no_critiques_when_all_clean(self) -> None:
        self._base_inputs()
        self._write("otel-learning-loop.json", self._base_otel(token_coverage_ratio=0.15))
        self._write("model-run-ledger-current.json", self._base_model_run([5000.0, 8000.0]))
        self._write("finance-response-quality-slice.json", self._base_frq())
        self._write(
            "workflow-advancement-scorecard.json",
            self._base_workflow_advancement([{"workflow_id": "WF55", "signal": "advanced", "status": "ok"}]),
        )
        self._write("improvement-ledger-current.json", self._base_ledger([]))
        critiques = engine.classify_critiques(tmp_dir=engine.TMP)
        self.assertEqual(len(critiques), 0)

    def test_latency_spike_detected(self) -> None:
        self._base_inputs()
        self._write("otel-learning-loop.json", self._base_otel(token_coverage_ratio=0.15))
        self._write("model-run-ledger-current.json", self._base_model_run([5000.0, 130_000.0]))
        self._write("finance-response-quality-slice.json", self._base_frq())
        self._write(
            "workflow-advancement-scorecard.json",
            self._base_workflow_advancement([{"workflow_id": "WF55", "signal": "advanced", "status": "ok"}]),
        )
        self._write("improvement-ledger-current.json", self._base_ledger([]))
        critiques = engine.classify_critiques(tmp_dir=engine.TMP)
        lat = [c for c in critiques if c["category"] == "latency_spike"]
        self.assertEqual(len(lat), 1)
        self.assertEqual(lat[0]["count"], 1)

    def test_low_telemetry_coverage(self) -> None:
        self._base_inputs()
        otel = self._base_otel(token_coverage_ratio=0.15)
        otel["learning_summaries"]["token_cost"]["token_coverage_ratio"] = 0.02
        self._write("otel-learning-loop.json", otel)
        self._write("model-run-ledger-current.json", self._base_model_run([5000.0]))
        self._write("finance-response-quality-slice.json", self._base_frq())
        self._write(
            "workflow-advancement-scorecard.json",
            self._base_workflow_advancement([{"workflow_id": "WF55", "signal": "advanced", "status": "ok"}]),
        )
        self._write("improvement-ledger-current.json", self._base_ledger([]))
        critiques = engine.classify_critiques(tmp_dir=engine.TMP)
        self.assertEqual(len([c for c in critiques if c["category"] == "low_telemetry_coverage"]), 1)

    def test_source_open_recurrence(self) -> None:
        self._base_inputs()
        self._write("otel-learning-loop.json", self._base_otel(token_coverage_ratio=0.15))
        self._write("model-run-ledger-current.json", self._base_model_run([5000.0]))
        self._write("finance-response-quality-slice.json", self._base_frq(source_open=3, source_freshness=2))
        self._write(
            "workflow-advancement-scorecard.json",
            self._base_workflow_advancement([{"workflow_id": "WF55", "signal": "advanced", "status": "ok"}]),
        )
        self._write("improvement-ledger-current.json", self._base_ledger([]))
        critiques = engine.classify_critiques(tmp_dir=engine.TMP)
        rec = [c for c in critiques if c["category"] == "source_open_recurrence"]
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["count"], 5)
        self.assertEqual(rec[0]["severity"], "high")

    def test_workflow_maturity_blocker(self) -> None:
        self._base_inputs()
        self._write("otel-learning-loop.json", self._base_otel(token_coverage_ratio=0.15))
        self._write("model-run-ledger-current.json", self._base_model_run([5000.0]))
        self._write("finance-response-quality-slice.json", self._base_frq())
        self._write(
            "workflow-advancement-scorecard.json",
            self._base_workflow_advancement([
                {"workflow_id": "WF87", "signal": "advanced", "status": "blocked_collecting_data"}
            ]),
        )
        self._write("improvement-ledger-current.json", self._base_ledger([]))
        critiques = engine.classify_critiques(tmp_dir=engine.TMP)
        self.assertEqual(len([c for c in critiques if c["category"] == "workflow_maturity_blocker"]), 1)

    def test_authority_boundary_false(self) -> None:
        for key, value in engine.AUTHORITY_BOUNDARY.items():
            if value is False:
                self.assertFalse(
                    value,
                    f"authority_boundary flag {key} must default to false",
                )

    def test_validate_payload_rejects_true_authority(self) -> None:
        payload = {
            "schema": engine.SCHEMA,
            "generated_at_utc": "2026-06-30T00:00:00Z",
            "status": "ok",
            "critiques": [],
            "authority_boundary": {**engine.AUTHORITY_BOUNDARY, "owner_approval_inferred": True},
        }
        result = engine.validate_payload(payload)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("authority_boundary_true:owner_approval_inferred", result["errors"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
