#!/usr/bin/env python3
"""Tests for the WF88 typed script reference graph."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_typed_script_reference_graph.py"

spec = importlib.util.spec_from_file_location("wf88_typed_script_reference_graph", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class Wf88TypedScriptReferenceGraphTests(unittest.TestCase):
    def test_graph_classifies_active_code_reference_as_replacement_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            route = root / "tmp" / "wf88-route-contraction-packet.json"
            route.parent.mkdir(parents=True)
            route.write_text(
                json.dumps(
                    {
                        "route_contraction_files": [
                            {
                                "path": "scripts/legacy.py",
                                "sha256": "abc",
                                "status": "contracted_or_already_narrowed",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            consumer = root / "scripts" / "consumer.py"
            consumer.parent.mkdir(parents=True)
            consumer.write_text("run scripts/legacy.py\n", encoding="utf-8")
            target = root / "scripts" / "legacy.py"
            target.write_text("print('legacy')\n", encoding="utf-8")
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "ROUTE_CONTRACTION", route):
                packet = mod.build_packet()
        row = packet["script_reference_graph"][0]
        self.assertEqual(row["active_replacement_required_count"], 1)
        self.assertEqual(row["exact_path_reference_count"], 2)
        self.assertEqual(row["basename_only_reference_count"], 0)
        self.assertEqual(packet["validation"]["status"], "ok")
        self.assertIn("active_code_or_control_consumers_remain", packet["validation"]["warnings"])

    def test_graph_splits_basename_only_active_refs_from_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            route = root / "tmp" / "wf88-route-contraction-packet.json"
            route.parent.mkdir(parents=True)
            route.write_text(
                json.dumps({"route_contraction_files": [{"path": "scripts/legacy.py"}]}),
                encoding="utf-8",
            )
            consumer = root / "scripts" / "consumer.py"
            consumer.parent.mkdir(parents=True)
            consumer.write_text("legacy.py is mentioned in a note, not an executable path\n", encoding="utf-8")
            (root / "scripts" / "legacy.py").write_text("print('legacy')\n", encoding="utf-8")
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "ROUTE_CONTRACTION", route):
                packet = mod.build_packet()
        row = packet["script_reference_graph"][0]
        self.assertEqual(row["active_replacement_required_count"], 0)
        self.assertEqual(row["basename_only_active_review_count"], 1)
        self.assertEqual(packet["summary"]["active_replacement_required_total"], 0)
        self.assertEqual(packet["summary"]["basename_only_active_review_total"], 1)
        self.assertIn("basename_only_active_refs_require_adjudication", packet["validation"]["warnings"])

    def test_graph_treats_windows_style_script_paths_as_exact_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            route = root / "tmp" / "wf88-route-contraction-packet.json"
            route.parent.mkdir(parents=True)
            route.write_text(
                json.dumps({"route_contraction_files": [{"path": "scripts/legacy.py"}]}),
                encoding="utf-8",
            )
            consumer = root / "scripts" / "consumer.py"
            consumer.parent.mkdir(parents=True)
            consumer.write_text('command = "python scripts\\\\legacy.py --validate"\n', encoding="utf-8")
            (root / "scripts" / "legacy.py").write_text("print('legacy')\n", encoding="utf-8")
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "ROUTE_CONTRACTION", route):
                packet = mod.build_packet()
        row = packet["script_reference_graph"][0]
        self.assertEqual(row["exact_path_reference_count"], 2)
        self.assertEqual(row["basename_only_reference_count"], 0)
        self.assertEqual(row["active_replacement_required_count"], 1)
        self.assertEqual(packet["summary"]["basename_only_active_review_total"], 0)

    def test_graph_marks_historical_other_text_references_as_history_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            route = root / "tmp" / "wf88-route-contraction-packet.json"
            route.parent.mkdir(parents=True)
            route.write_text(
                json.dumps({"route_contraction_files": [{"path": "scripts/legacy.py"}]}),
                encoding="utf-8",
            )
            history = root / "data" / "state-history" / "ledger.jsonl"
            history.parent.mkdir(parents=True)
            history.write_text('{"command":"python scripts\\\\legacy.py --validate"}\n', encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "scripts" / "legacy.py").write_text("print('legacy')\n", encoding="utf-8")
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "ROUTE_CONTRACTION", route):
                packet = mod.build_packet()
        row = packet["script_reference_graph"][0]
        needs = {ref["path"]: ref["need"] for ref in row["references"]}
        self.assertEqual(needs["data/state-history/ledger.jsonl"], "history_only")
        self.assertEqual(row["review_required_count"], 0)
        self.assertEqual(packet["summary"]["review_required_total"], 0)

    def test_graph_does_not_treat_docstring_exact_path_as_active_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            route = root / "tmp" / "wf88-route-contraction-packet.json"
            route.parent.mkdir(parents=True)
            route.write_text(
                json.dumps({"route_contraction_files": [{"path": "scripts/legacy.py"}]}),
                encoding="utf-8",
            )
            consumer = root / "scripts" / "consumer.py"
            consumer.parent.mkdir(parents=True)
            consumer.write_text('"""Mentions scripts/legacy.py for historical context."""\n', encoding="utf-8")
            (root / "scripts" / "legacy.py").write_text('"""CLI: python scripts/legacy.py --validate"""\n', encoding="utf-8")
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "ROUTE_CONTRACTION", route):
                packet = mod.build_packet()
        row = packet["script_reference_graph"][0]
        self.assertEqual(row["active_replacement_required_count"], 0)
        self.assertEqual(packet["summary"]["active_replacement_required_total"], 0)
        needs = {ref["path"]: ref["need"] for ref in row["references"]}
        self.assertEqual(needs["scripts/consumer.py"], "can_be_updated_or_retained_as_proof")
        self.assertEqual(needs["scripts/legacy.py"], "can_be_updated_or_retained_as_proof")

    def test_graph_adjudicates_retained_route_contract_refs_without_deletion_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            route = root / "tmp" / "wf88-route-contraction-packet.json"
            route.parent.mkdir(parents=True)
            route.write_text(
                json.dumps(
                    {
                        "route_contraction_files": [
                            {
                                "path": "scripts/legacy.py",
                                "retirement_state": "retain_targeted_or_sidecar",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            consumer = root / "scripts" / "consumer.py"
            consumer.parent.mkdir(parents=True)
            consumer.write_text(
                "run scripts/legacy.py\nlegacy.py basename mention\n",
                encoding="utf-8",
            )
            note = root / "routing-note.md"
            note.write_text("Retained route contract: scripts/legacy.py\n", encoding="utf-8")
            (root / "scripts" / "legacy.py").write_text("print('legacy')\n", encoding="utf-8")
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "ROUTE_CONTRACTION", route):
                packet = mod.build_packet()
        row = packet["script_reference_graph"][0]
        self.assertEqual(row["retention_decision"], "explicitly_retained_route_contract")
        self.assertEqual(row["active_replacement_required_count"], 0)
        self.assertGreater(row["explicitly_retained_active_reference_count"], 0)
        needs = {ref["path"]: ref["need"] for ref in row["references"]}
        self.assertEqual(needs["routing-note.md"], "retained_target_reference")
        self.assertEqual(row["review_required_count"], 0)
        self.assertEqual(packet["summary"]["active_replacement_required_total"], 0)
        self.assertGreater(packet["summary"]["explicitly_retained_active_reference_total"], 0)
        self.assertFalse(row["script_deletion_ready_now"])

    def test_graph_keeps_unretained_exact_other_text_refs_review_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            route = root / "tmp" / "wf88-route-contraction-packet.json"
            route.parent.mkdir(parents=True)
            route.write_text(
                json.dumps({"route_contraction_files": [{"path": "scripts/legacy.py"}]}),
                encoding="utf-8",
            )
            note = root / "routing-note.md"
            note.write_text("Potential delete target: scripts/legacy.py\n", encoding="utf-8")
            (root / "scripts").mkdir()
            (root / "scripts" / "legacy.py").write_text("print('legacy')\n", encoding="utf-8")
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "ROUTE_CONTRACTION", route):
                packet = mod.build_packet()
        row = packet["script_reference_graph"][0]
        needs = {ref["path"]: ref["need"] for ref in row["references"]}
        self.assertEqual(needs["routing-note.md"], "review_required")
        self.assertEqual(row["review_required_count"], 1)

    def test_graph_never_marks_deletion_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            route = root / "tmp" / "wf88-route-contraction-packet.json"
            route.parent.mkdir(parents=True)
            route.write_text(
                json.dumps({"route_contraction_files": [{"path": "scripts/legacy.py"}]}),
                encoding="utf-8",
            )
            (root / "scripts").mkdir()
            (root / "scripts" / "legacy.py").write_text("print('legacy')\n", encoding="utf-8")
            with mock.patch.object(mod, "ROOT", root), mock.patch.object(mod, "ROUTE_CONTRACTION", route):
                packet = mod.build_packet()
        self.assertEqual(packet["summary"]["script_deletion_ready_now_count"], 0)
        self.assertFalse(packet["script_reference_graph"][0]["delete_allowed_now"])


if __name__ == "__main__":
    unittest.main()
