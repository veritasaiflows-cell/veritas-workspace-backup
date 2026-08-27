from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "finance_cache_cleanup_readiness.py"


def load_module():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("finance_cache_cleanup_readiness", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def seed_sqlite(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO sample(value) VALUES ('ok')")
        conn.commit()
    finally:
        conn.close()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def seed_workspace(root: Path, module) -> None:
    module.ROOT = root
    module.TMP = root / "tmp"
    primary = root / "state" / "finance" / "finance-canon.sqlite"
    legacy = module.TMP / "veritas-canon-cache.sqlite"
    finance_state = module.TMP / "finance-intelligence-state.sqlite"
    wf84 = module.TMP / "canonical-finance-data-plane.sqlite"
    for path in (primary, legacy, finance_state, wf84):
        seed_sqlite(path)
    module.DB_TARGETS = [
        ("sql_canon_primary", primary, "primary_guarded_sql_truth"),
        ("legacy_canon_cache", legacy, "legacy_compatibility_proof_cache"),
        ("finance_intelligence_state", finance_state, "compatibility_query_cache"),
        ("wf84_canonical_data_plane", wf84, "wf84_current_query_cache"),
    ]
    large_json = module.TMP / "large-proof.json"
    write_json(large_json, {"status": "ok", "generated_at_utc": module.utc_now(), "blob": "x" * 1_000_100})
    old_preflight = module.TMP / "artifact-index-json-first-default-validation.json"
    write_json(old_preflight, {"status": "blocked", "generated_at_utc": module.utc_now()})
    module.JSON_TARGETS = [
        ("large_json", large_json, "wf85_answer_rollup"),
        ("json_first_activation_preflight", old_preflight, "old_activation_preflight_residue"),
    ]
    module.OUT = module.TMP / "finance-cache-cleanup-readiness.json"


def test_readiness_classifies_cache_roles_without_cleanup_authority() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_workspace(Path(tmpdir), module)
        packet = module.build_packet()
        dbs = {row["id"]: row for row in packet["sqlite_caches"]}
        artifacts = {row["id"]: row for row in packet["json_proof_surfaces"]}

        assert packet["validation"]["status"] == "ok"
        assert dbs["sql_canon_primary"]["cleanup_classification"] == "not_cleanup_candidate_primary_truth"
        assert dbs["wf84_canonical_data_plane"]["cleanup_classification"] == "retain_current_query_cache"
        assert dbs["legacy_canon_cache"]["cleanup_classification"] == "compatibility_lineage_owner_gated_cleanup_candidate"
        assert artifacts["large_json"]["classification"] == "large_json_prompt_pressure_candidate"
        assert artifacts["json_first_activation_preflight"]["classification"] == "classified_old_activation_preflight_residue"
        assert packet["summary"]["phase2_requires_owner_approval"] is True
        assert packet["authority_boundary"]["delete_allowed"] is False
        assert packet["authority_boundary"]["cache_database_mutation_allowed"] is False


def test_missing_nonlegacy_sqlite_blocks_but_missing_legacy_is_allowed_for_inventory() -> None:
    module = load_module()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        module.ROOT = root
        module.TMP = root / "tmp"
        primary = root / "state" / "finance" / "finance-canon.sqlite"
        legacy = module.TMP / "veritas-canon-cache.sqlite"
        seed_sqlite(primary)
        module.DB_TARGETS = [
            ("sql_canon_primary", primary, "primary_guarded_sql_truth"),
            ("legacy_canon_cache", legacy, "legacy_compatibility_proof_cache"),
            ("missing_required", module.TMP / "missing-required.sqlite", "wf84_current_query_cache"),
        ]
        module.JSON_TARGETS = []
        packet = module.build_packet()

        assert packet["validation"]["status"] == "blocked"
        assert "missing_required:sqlite_missing" in packet["validation"]["errors"]
        assert not any(error == "legacy_canon_cache:sqlite_missing" for error in packet["validation"]["errors"])


if __name__ == "__main__":
    test_readiness_classifies_cache_roles_without_cleanup_authority()
    test_missing_nonlegacy_sqlite_blocks_but_missing_legacy_is_allowed_for_inventory()
    print("finance_cache_cleanup_readiness tests passed")
