#!/usr/bin/env python3
"""Deterministic regression tests for the WF89-only Grok QA exception.

Run:  python3 scripts/test_wf89_task_qa_exception.py
       python3 -m pytest scripts/test_wf89_task_qa_exception.py -q
"""
from __future__ import annotations

import ast
import copy
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import wf89_task_qa_exception as exc

# Valid-fixture receipt bytes come from the frozen owner approval (pinned
# SHA256 f29cfae1...). Candidates are searched in order; the positive and
# tamper tests skip explicitly if no source is available.
RECEIPT_SOURCES = [
    Path(os.environ.get("WF89_APPROVAL_FIXTURE_SRC", "")) if os.environ.get("WF89_APPROVAL_FIXTURE_SRC") else None,
    Path("/attachments/wf89-a1-qa-gate-20260910/owner-approval.json"),
]
RECEIPT_SOURCES = [p for p in RECEIPT_SOURCES if p is not None]

FIXED_NOW = datetime(2026, 9, 10, 15, 0, 0, tzinfo=timezone.utc)


def load_receipt_bytes() -> bytes | None:
    for candidate in RECEIPT_SOURCES:
        try:
            if candidate.is_file():
                return candidate.read_bytes()
        except OSError:
            continue
    return None


def make_project(**overrides) -> dict:
    route = {
        "execution_backend": "persistent_isolated_agent",
        "expected_model_path": "xai/grok-4.6",
        "expected_thinking": "high",
        "persistent_agent_id": "research-scout",
    }
    project = {
        "project_id": "WF89-FLEET-20260909",
        "workflow_id": "WF89",
        "classification": {
            "task_shape": "qa",
            "authority_class": "review_only",
            "write_scope": "no_write",
        },
        "write_mode": "read_only",
        "leased_paths": [],
        "model_route": dict(route),
        "execution_route_policy": dict(route),
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(project.get(key), dict):
            merged = dict(project[key])
            merged.update(value)
            project[key] = merged
        else:
            project[key] = value
    return project


def make_root_with_receipt(receipt_bytes: bytes) -> tempfile.TemporaryDirectory:
    tmp = tempfile.TemporaryDirectory(prefix="wf89-qa-exc-")
    target = Path(tmp.name) / exc.APPROVAL_RELATIVE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(receipt_bytes)
    return tmp


class ExceptionPredicateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt_bytes = load_receipt_bytes()

    def setUp(self) -> None:
        self._roots: list[tempfile.TemporaryDirectory] = []

    def tearDown(self) -> None:
        for tmp in self._roots:
            tmp.cleanup()

    def rooted(self, receipt_bytes: bytes | None = None) -> Path:
        data = receipt_bytes if receipt_bytes is not None else self.receipt_bytes
        if data is None:
            self.skipTest("frozen owner-approval bytes unavailable")
        tmp = make_root_with_receipt(data)
        self._roots.append(tmp)
        return Path(tmp.name)

    def bare_root(self) -> Path:
        tmp = tempfile.TemporaryDirectory(prefix="wf89-qa-exc-bare-")
        self._roots.append(tmp)
        return Path(tmp.name)

    # Positive fixture -------------------------------------------------
    def test_valid_exact_approved_fixture_applies(self) -> None:
        root = self.rooted()
        result = exc.wf89_task_qa_exception_applies(make_project(), root=root, now=FIXED_NOW)
        self.assertTrue(result.get("applies"), result)
        self.assertEqual(result["code"], "wf89_qa_exception_applies")
        self.assertEqual(result["detail"]["receipt_sha256"], exc.APPROVAL_SHA256)

    # Scope negatives (fail before receipt) -----------------------------
    def test_wrong_root_rejected(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(make_project(project_id="OTHER"), root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_exception_root_mismatch")

    def test_wrong_workflow_rejected(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(make_project(workflow_id="WF88"), root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_exception_workflow_mismatch")

    def test_non_qa_shape_rejected(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(
            make_project(classification={"task_shape": "implementation"}), root=root, now=FIXED_NOW
        )
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_exception_shape_mismatch")

    def test_qa_relabelled_as_audit_rejected(self) -> None:
        root = self.bare_root()
        project = make_project(classification={"task_shape": "audit"})
        result = exc.wf89_task_qa_exception_applies(project, root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"), "QA must not pass by relabelling as audit")

    def test_wrong_authority_rejected(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(
            make_project(classification={"authority_class": "owner_gated"}), root=root, now=FIXED_NOW
        )
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_exception_authority_mismatch")

    def test_glm_model_does_not_take_exception(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(
            make_project(
                model_route={"expected_model_path": "ollama-cloud/glm-5.3:cloud"},
                execution_route_policy={"expected_model_path": "ollama-cloud/glm-5.3:cloud"},
            ),
            root=root,
            now=FIXED_NOW,
        )
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_exception_model_mismatch")

    def test_wrong_agent_rejected(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(
            make_project(
                model_route={"persistent_agent_id": "implementation-builder"},
                execution_route_policy={"persistent_agent_id": "implementation-builder"},
            ),
            root=root,
            now=FIXED_NOW,
        )
        self.assertFalse(result.get("applies"))
        self.assertIn(result["code"], ("wf89_exception_agent_mismatch", "wf89_exception_reviewer_not_independent"))

    def test_main_backend_rejected(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(
            make_project(
                model_route={"execution_backend": "main"},
                execution_route_policy={"execution_backend": "main"},
            ),
            root=root,
            now=FIXED_NOW,
        )
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_exception_backend_mismatch")

    def test_native_backend_rejected(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(
            make_project(
                model_route={"execution_backend": "codex_native_subagent"},
                execution_route_policy={"execution_backend": "codex_native_subagent"},
            ),
            root=root,
            now=FIXED_NOW,
        )
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_exception_backend_mismatch")

    def test_wrong_effort_rejected(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(
            make_project(
                model_route={"expected_thinking": "medium"},
                execution_route_policy={"expected_thinking": "medium"},
            ),
            root=root,
            now=FIXED_NOW,
        )
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_exception_effort_mismatch")

    def test_write_mode_claim_rejected(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(
            make_project(write_mode="leased", leased_paths=["scripts/a.py"]), root=root, now=FIXED_NOW
        )
        self.assertFalse(result.get("applies"))
        self.assertIn(result["code"], ("wf89_exception_write_mode_mismatch", "wf89_exception_lease_claim"))

    def test_policy_projection_mismatch_rejected(self) -> None:
        root = self.bare_root()
        project = make_project()
        project["execution_route_policy"]["expected_thinking"] = "medium"
        # Align inner block check by patching both thinking fields differently:
        project["model_route"]["expected_thinking"] = "high"
        result = exc.wf89_task_qa_exception_applies(project, root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertIn(
            result["code"], ("wf89_exception_effort_mismatch", "wf89_exception_policy_projection_mismatch")
        )

    def test_policy_model_mismatch_rejected(self) -> None:
        root = self.bare_root()
        project = make_project()
        project["execution_route_policy"]["expected_model_path"] = "xai/grok-4.6"
        project["model_route"]["expected_model_path"] = "xai/grok-4.6"
        project["execution_route_policy"]["persistent_agent_id"] = "research-scout"
        project["model_route"]["persistent_agent_id"] = "qa-redteam"
        result = exc.wf89_task_qa_exception_applies(project, root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertIn(
            result["code"], ("wf89_exception_agent_mismatch", "wf89_exception_policy_projection_mismatch")
        )

    # Receipt negatives ---------------------------------------------------
    def test_missing_receipt_preserves_default_gate(self) -> None:
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(make_project(), root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_absent")

    def test_tampered_receipt_rejected(self) -> None:
        if self.receipt_bytes is None:
            self.skipTest("frozen owner-approval bytes unavailable")
        tampered = bytearray(self.receipt_bytes)
        tampered[-2] ^= 0x01
        root = self.rooted(receipt_bytes=bytes(tampered))
        result = exc.wf89_task_qa_exception_applies(make_project(), root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertIn(result["code"], ("wf89_receipt_hash_mismatch", "wf89_receipt_malformed"))

    def test_wrong_hash_receipt_rejected(self) -> None:
        root = self.rooted(receipt_bytes=b'{"source":"ask_user.wf89_rescope"}')
        result = exc.wf89_task_qa_exception_applies(make_project(), root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_hash_mismatch")

    def test_malformed_receipt_rejected(self) -> None:
        root = self.rooted(receipt_bytes=b"\x00\x01 not json")
        result = exc.wf89_task_qa_exception_applies(make_project(), root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_hash_mismatch")

    def test_expired_receipt_rejected(self) -> None:
        root = self.rooted()
        late = datetime(2026, 9, 12, 0, 0, 0, tzinfo=timezone.utc)
        result = exc.wf89_task_qa_exception_applies(make_project(), root=root, now=late)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_expired")

    def test_future_approval_rejected(self) -> None:
        root = self.rooted()
        early = datetime(2026, 9, 9, 0, 0, 0, tzinfo=timezone.utc)
        result = exc.wf89_task_qa_exception_applies(make_project(), root=root, now=early)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_future_approval")

    def test_symlink_escape_rejected(self) -> None:
        if self.receipt_bytes is None:
            self.skipTest("frozen owner-approval bytes unavailable")
        if os.name == "nt":
            self.skipTest("symlink creation unsupported on this platform")
        tmp = tempfile.TemporaryDirectory(prefix="wf89-qa-exc-link-")
        self._roots.append(tmp)
        outside = Path(tmp.name) / "outside.json"
        outside.write_bytes(self.receipt_bytes)
        link_dir = Path(tmp.name) / "ws"
        (link_dir / "tmp" / "wf89-fleet-20260909").mkdir(parents=True)
        link = link_dir / "tmp" / "wf89-fleet-20260909" / "a1-rescope-owner-approval.json"
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest("symlink creation blocked")
        result = exc.wf89_task_qa_exception_applies(make_project(), root=link_dir, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_link_escape")

    def test_copied_receipt_to_other_root_rejected(self) -> None:
        if self.receipt_bytes is None:
            self.skipTest("frozen owner-approval bytes unavailable")
        root = self.rooted()
        project = make_project(project_id="WF89-FLEET-20260909", workflow_id="WF77")
        result = exc.wf89_task_qa_exception_applies(project, root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"), "Receipt must not authorize another workflow")

    # Pure receipt-field validation (hash-independent) ----------------------
    def _receipt_object(self) -> dict:
        if self.receipt_bytes is None:
            self.skipTest("frozen owner-approval bytes unavailable")
        return json.loads(self.receipt_bytes.decode("utf-8"))

    def test_receipt_fields_valid(self) -> None:
        obj = self._receipt_object()
        result = exc._receipt_fields_valid(obj, now=FIXED_NOW)
        self.assertTrue(result.get("applies"), result)

    def test_receipt_wrong_model_field_rejected(self) -> None:
        obj = self._receipt_object()
        obj["reviewer_model"] = "ollama-cloud/glm-5.3:cloud"
        result = exc._receipt_fields_valid(obj, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_model_mismatch")

    def test_receipt_wrong_role_field_rejected(self) -> None:
        obj = self._receipt_object()
        obj["reviewer_agent_id"] = "implementation-builder"
        result = exc._receipt_fields_valid(obj, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_agent_mismatch")

    def test_receipt_forbidden_action_rejected(self) -> None:
        obj = self._receipt_object()
        obj["authorized_operations"] = ["Main integration and deterministic validation"]
        result = exc._receipt_fields_valid(obj, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_forbidden_action")

    def test_receipt_wrong_source_rejected(self) -> None:
        obj = self._receipt_object()
        obj["source"] = "some_other_prompt"
        result = exc._receipt_fields_valid(obj, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_source_unapproved")

    def test_receipt_bool_field_wrong_type_rejected(self) -> None:
        obj = self._receipt_object()
        obj["runtime_or_default_change_authorized"] = "false"
        result = exc._receipt_fields_valid(obj, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        self.assertEqual(result["code"], "wf89_receipt_scope_invalid")

    # Gate-preservation and draft-narrowness --------------------------------
    def test_original_gate_preserved_on_failure(self) -> None:
        """Predicate False means the caller keeps emitting qa_route_requires_glm."""
        root = self.bare_root()
        result = exc.wf89_task_qa_exception_applies(make_project(), root=root, now=FIXED_NOW)
        self.assertFalse(result.get("applies"))
        caller_would_emit = "qa_route_requires_glm" if not result.get("applies") else None
        self.assertEqual(caller_would_emit, "qa_route_requires_glm")

    def test_helper_has_no_privileged_imports(self) -> None:
        tree = ast.parse((HERE / "wf89_task_qa_exception.py").read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])
        forbidden = {"socket", "subprocess", "sqlite3", "urllib", "ssl", "os", "sys", "ctypes"}
        self.assertFalse(imported & forbidden, f"privileged imports: {imported & forbidden}")

    def test_router_replacements_narrow(self) -> None:
        candidates = [
            Path(os.environ.get("WF89_REPLACEMENTS_PATH", "")) if os.environ.get("WF89_REPLACEMENTS_PATH") else None,
            HERE.parent / "router-replacements.json",
        ]
        replacements_path = next((p for p in candidates if p is not None and p.is_file()), None)
        if replacements_path is None:
            self.skipTest("router-replacements.json unavailable")
        doc = json.loads(replacements_path.read_text(encoding="utf-8"))
        self.assertEqual(doc["target_path"], "scripts/project_implementation_router.py")
        self.assertEqual(doc["full_original_sha256"], "fb704ae2da7928d4d2450e14707c19e86ec95dc441d3fe94ff8aee560d9be76c")
        self.assertEqual(len(doc["replacements"]), 2)
        gate = next(r for r in doc["replacements"] if r["id"] == "wf89-qa-exception-gate")
        self.assertIn("qa_route_requires_glm", gate["old_text"])
        self.assertIn("qa_route_requires_glm", gate["new_text"], "original finding must survive")
        self.assertIn("wf89_task_qa_exception", gate["new_text"])
        self.assertNotIn("task_scoped_model_role_contract", gate["new_text"], "unrelated contract must not be touched")
        import_rep = next(r for r in doc["replacements"] if r["id"] == "wf89-qa-exception-import")
        self.assertIn("task_scoped_model_role_contract", import_rep["old_text"])
        fragment = os.environ.get("WF89_ROUTER_FRAGMENT")
        if fragment and Path(fragment).is_file():
            text = Path(fragment).read_text(encoding="utf-8")
            for rep in doc["replacements"]:
                self.assertEqual(text.count(rep["old_text"]), 1, f"old_text not unique: {rep['id']}")
        else:
            self.skipTest("frozen router fragment unavailable for uniqueness check")


if __name__ == "__main__":
    unittest.main(verbosity=2)
