from __future__ import annotations

import lane_collision_preflight as preflight


def test_overlaps_detects_active_write_collision() -> None:
    active = [{"lane_id": "A::b", "owner": "x", "status": "running", "allowed_writes": ["scripts/foo.py"]}]
    hits = preflight.overlaps(["scripts\\foo.py"], active)
    assert hits[0]["lane_id"] == "A::b"


def test_dirty_overlaps_normalizes_paths() -> None:
    assert preflight.dirty_overlaps(["scripts\\foo.py"], ["scripts/foo.py"]) == ["scripts/foo.py"]


def test_forbidden_hits_uses_lane_policy() -> None:
    hits = preflight.forbidden_hits(["03. Portfolio/example.md"])
    assert hits
    assert hits[0]["path"] == "03. Portfolio/example.md"


if __name__ == "__main__":
    test_overlaps_detects_active_write_collision()
    test_dirty_overlaps_normalizes_paths()
    test_forbidden_hits_uses_lane_policy()
    print("ok")
