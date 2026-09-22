from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "wf88_route_contraction_packet.py"
TICKER_ANSWER_SCRIPT = ROOT / "scripts" / "ticker_answer_packet.py"
RETIREMENT_PLAN_SCRIPT = ROOT / "scripts" / "ticker_answer_packet_retirement_plan.py"
LEGACY_PACKET_DIR = ROOT / "tmp" / "ticker-answer-packets"
LEGACY_BUILD_SUMMARY = ROOT / "tmp" / "ticker-answer-packet-build-summary.json"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("wf88_route_contraction_packet", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def legacy_output_snapshot() -> dict[str, tuple[int, int, str]]:
    paths = sorted(path for path in LEGACY_PACKET_DIR.rglob("*") if path.is_file()) if LEGACY_PACKET_DIR.exists() else []
    if LEGACY_BUILD_SUMMARY.is_file():
        paths.append(LEGACY_BUILD_SUMMARY)
    return {
        path.relative_to(ROOT).as_posix(): (path.stat().st_size, path.stat().st_mtime_ns, file_sha256(path))
        for path in sorted(paths)
    }


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    module.CLEANUP_PLAN = module.TMP / "wf88-retired-surface-cleanup-plan.json"
    module.OS2_CONTROL_PACKET = module.TMP / "wf88-os2-control-packet.json"
    module.ROUTING_INDEX = module.TMP / "workflow-routing-index.json"
    module.OUT = module.TMP / "wf88-route-contraction-packet.json"
    module.MD_OUT = module.TMP / "wf88-route-contraction-packet.md"
    module.TMP.mkdir(parents=True, exist_ok=True)

    exact_files = sorted(module.EXPECTED_MARKERS)
    rows = []
    for file_path in exact_files:
        write_text(root / file_path, "\n".join(module.EXPECTED_MARKERS[file_path]))
        rows.append({
            "item": file_path,
            "classification": "test_contraction",
            "route_or_script_files": [file_path],
            "target_reference_proof": {
                file_path: {
                    "active_reference_count": 1,
                    "active_reference_sample": ["scripts/test_reference.py"],
                },
            },
            "post_contraction_validators": ["python -m py_compile <touched script files>"],
            "delete_allowed_now": False,
            "archive_allowed_now": False,
        })
    cleanup_authority = {
        "review_only": True,
        "proposal_only": True,
        "delete_allowed": False,
        "archive_allowed": False,
        "move_allowed": False,
        "apply_allowed": False,
        "cron_schedule_mutation_allowed": False,
    }
    write_json(module.CLEANUP_PLAN, {
        "status": "proposal_ready_no_apply_authority",
        "authority_boundary": cleanup_authority,
        "summary": {
            "delete_allowed_now_count": 0,
            "archive_allowed_now_count": 0,
            "tmp_cleanup_preview_eligible_count": 9,
            "first_tmp_microbatch_candidate_count": 2,
            "db_archive_candidate_count": 1,
            "cron_packet_status": "packet_needed_no_cron_mutation",
        },
        "lanes": {
            "tmp_delete_proposal": {"status": "proposal_ready"},
            "script_route_contraction": {
                "status": "route_contraction_preflight_ready",
                "delete_allowed_now": False,
                "archive_allowed_now": False,
                "exact_files_for_next_route_contraction": exact_files,
                "rows": rows,
            },
            "db_lifecycle_microbatch": {"status": "owner_packet_needed"},
            "cron_retired_job_packet": {"status": "packet_needed"},
        },
    })
    write_json(module.OS2_CONTROL_PACKET, {"status": "control_packet_ready_no_apply_authority"})
    write_json(module.ROUTING_INDEX, {
        "status": "ok",
        "routes": [
            {
                "workflow_id": "WF87",
                "primary_route_artifact": None,
                "effective_status_override": "on_hold",
                "secondary_artifacts": [],
            },
            {
                "workflow_id": "WF88",
                "primary_route_artifact": "tmp/wf88-os2-control-packet.json",
                "secondary_artifacts": ["tmp/wf88-route-contraction-packet.json"],
            },
        ],
    })


def test_route_contraction_packet_never_grants_destructive_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()

        assert packet["validation"]["status"] == "ok"
        assert packet["summary"]["contracted_or_already_narrowed_count"] == len(module.EXPECTED_MARKERS)
        assert packet["summary"]["script_deletion_ready_now_count"] == 0
        assert packet["authority_boundary"]["delete_allowed"] is False
        assert packet["authority_boundary"]["archive_allowed"] is False
        assert packet["authority_boundary"]["apply_allowed"] is False
        assert packet["retirement_readiness"]["ready_for_destructive_apply"] is False


def test_ticker_answer_packet_is_deterministic_zero_write_tombstone() -> None:
    before = legacy_output_snapshot()
    cli_matrix = [
        [],
        ["--ticker", "NVDA", "--validate"],
        ["--all-from-coverage", "--write", "--allow-legacy-write", "--validate", "--pretty"],
        ["--unknown-legacy-shape", "value", "--another-flag"],
    ]
    results = [
        subprocess.run(
            [sys.executable, "-B", str(TICKER_ANSWER_SCRIPT), *args],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        for args in cli_matrix
    ]
    after = legacy_output_snapshot()

    assert before == after
    assert {result.returncode for result in results} == {2}
    assert {result.stderr for result in results} == {""}
    assert len({result.stdout for result in results}) == 1
    payload = json.loads(results[0].stdout)
    assert payload["schema"] == "veritas.ticker_answer_packet.retired_compatibility.v1"
    assert payload["status"] == "blocked"
    assert payload["reason"] == "retired_surface"
    assert payload["compatibility_mode"] == "deny_only"
    assert payload["legacy_read_allowed"] is False
    assert payload["legacy_write_allowed"] is False
    assert payload["filesystem_mutation_allowed"] is False
    assert payload["exit_code"] == 2

    source = TICKER_ANSWER_SCRIPT.read_text(encoding="utf-8")
    for retired_import in (
        "trade_grade_full_answer_assembler",
        "finance_sql_canon_access",
        "FinanceSqlCanonAccess",
        "finance_production_scope",
        "from pathlib import Path",
        "import subprocess",
        "import requests",
        "import urllib",
    ):
        assert retired_import not in source


def test_retirement_plan_cannot_treat_historical_snapshots_as_current_replacement() -> None:
    result = subprocess.run(
        [sys.executable, "-B", str(RETIREMENT_PLAN_SCRIPT), "--validate"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["status"] == "blocked"
    assert payload["summary"]["planning_ready"] is False
    assert payload["summary"]["active_reference_count"] == 0
    assert payload["summary"]["production_answer_packet_retirement_planning_ready"] is False
    assert payload["summary"]["current_operational_replacement_ready"] is False
    error_names = {row["check"] for row in payload["validation"]["errors"]}
    assert "retired_answer_packet_family_has_no_active_writer_or_current_replacement" in error_names


def test_markers_match_current_source_architecture() -> None:
    module = load_module()
    here_root = Path(__file__).resolve().parents[1]
    for file_path, markers in module.EXPECTED_MARKERS.items():
        text = (here_root / file_path).read_text(encoding="utf-8", errors="replace")
        for marker in markers:
            assert marker in text, (file_path, marker)
    flat = [marker for markers in module.EXPECTED_MARKERS.values() for marker in markers]
    for stale in ("WORKFLOW_FRONT_DOORS", "human_context_artifacts_to_open", "WF87 - Paper Autonomy Runtime Governor", "tmp/wf87-paper-autonomy-runtime-governor.json"):
        assert stale not in flat, stale


def test_stale_paper_governor_wf87_shape_fails_retired_invariant() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        index = json.loads(module.ROUTING_INDEX.read_text(encoding="utf-8"))
        for row in index["routes"]:
            if row.get("workflow_id") == "WF87":
                row["primary_route_artifact"] = "tmp/wf87-paper-autonomy-runtime-governor.json"
                row.pop("effective_status_override", None)
        write_json(module.ROUTING_INDEX, index)
        packet = module.build_packet()
        assert packet["validation"]["status"] == "blocked"
        assert "route_invariant_failed:wf87_retired_no_operational_route" in packet["validation"]["errors"]


if __name__ == "__main__":
    test_route_contraction_packet_never_grants_destructive_authority()
    test_ticker_answer_packet_is_deterministic_zero_write_tombstone()
    test_retirement_plan_cannot_treat_historical_snapshots_as_current_replacement()
    test_markers_match_current_source_architecture()
    test_stale_paper_governor_wf87_shape_fails_retired_invariant()
    print("wf88 route contraction packet tests passed")
