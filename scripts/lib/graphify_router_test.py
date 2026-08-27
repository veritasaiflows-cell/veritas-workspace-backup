"""Tests for graphify_router.py.

Run: python scripts/lib/graphify_router_test.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.graphify_router import GraphifyRouter, GraphifyError  # noqa: E402


def test_available() -> None:
    router = GraphifyRouter()
    avail = router.available()
    assert "scripts" in avail
    assert "skills" in avail
    assert "skills-md" in avail
    assert isinstance(avail["scripts"], bool)
    assert isinstance(avail["skills"], bool)
    assert isinstance(avail["skills-md"], bool)


def test_skills_md_explain() -> None:
    router = GraphifyRouter()
    if not router.available().get("skills-md"):
        print("SKIP: skills-md graph not available")
        return
    result = router.explain("Disciplined Implementation", graph_name="skills-md")
    assert result["returncode"] == 0
    assert "Bounded handoff contract" in result["stdout"] or "project_implementation_router" in result["stdout"]


def test_affected_workflow_router() -> None:
    router = GraphifyRouter()
    if not router.available().get("scripts"):
        print("SKIP: scripts graph not available")
        return
    result = router.affected("workflow_router.py")
    assert result["returncode"] == 0
    assert "test_routing_truth_contract.py" in result["stdout"]
    assert "test_workflow_routing_index.py" in result["stdout"]


def test_affected_finance_intelligence_state() -> None:
    router = GraphifyRouter()
    if not router.available().get("scripts"):
        print("SKIP: scripts graph not available")
        return
    result = router.affected("finance_intelligence_state.py")
    assert result["returncode"] == 0
    assert "sql_canon_front_door_readiness_packet.py" in result["stdout"]


def test_skills_graph_exists() -> None:
    router = GraphifyRouter()
    assert router.available().get("skills") is True


def main() -> int:
    tests = [
        test_available,
        test_affected_workflow_router,
        test_affected_finance_intelligence_state,
        test_skills_graph_exists,
        test_skills_md_explain,
    ]
    failures = 0
    for test in tests:
        try:
            test()
            print(f"PASS: {test.__name__}")
        except Exception as exc:
            failures += 1
            print(f"FAIL: {test.__name__}: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
