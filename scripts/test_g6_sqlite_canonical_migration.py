#!/usr/bin/env python3
"""Hermetic tests for G6 SQLite-canonical cutover controller.

Constraints: temp dirs + fixture DB only. No network. No production DB.
Run: python scripts/test_g6_sqlite_canonical_migration.py  (exit 0 on pass)
"""

from __future__ import annotations

import importlib.util
import json
import py_compile
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve()
CONTROLLER = HERE.parent / "g6_sqlite_canonical_migration.py"
SELF = HERE

SEEDS = [
    "reference_levels_derived_refresh_apply.py",
    "reference_band_note_sync.py",
    "human_facing_truth_surface.py",
    "board_canon_guardrail.py",
    "canon_volatile_execution_board_sync.py",
    "alert_level_freshness_controller.py",
]

REQUIRED_AUTHORITY = {
    "review_only": True,
    "sql_reference_levels_apply_path": False,
    "markdown_canon_write_allowed": False,
    "schema_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "trade_or_execution_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"PASS {name}")
    else:
        FAIL.append(name)
        print(f"FAIL {name} {detail}")


def load_controller():
    spec = importlib.util.spec_from_file_location("g6_ctrl", str(CONTROLLER))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def make_fixture_tree(root: Path) -> Path:
    scan = root / "scan"
    scan.mkdir(parents=True, exist_ok=True)
    migrated_text = (
        "# fixture: SQL-only writer\n"
        "markdown_mutation_allowed=False\n"
        "import sqlite3\n"
        "def apply():\n"
        "    con = sqlite3.connect('x')\n"
        "    con.execute('SELECT symbol, level FROM reference_levels')\n"
        "    con.execute('UPDATE reference_levels SET level=1 WHERE symbol=\"A\"')\n"
    )
    writer_tpl = (
        "# fixture writable markdown consumer: {name}\n"
        "# touches Alert Bands and Invalidation Register\n"
        "import pathlib\n"
        "def sync():\n"
        "    open('Alert Bands and Invalidation Register.md', 'w').write('bands')\n"
        "    x = \"reference_levels\"\n"
    )
    for seed in SEEDS:
        if seed == "reference_levels_derived_refresh_apply.py":
            (scan / seed).write_text(migrated_text, encoding="utf-8")
        else:
            (scan / seed).write_text(writer_tpl.format(name=seed), encoding="utf-8")
    return scan


def make_fixture_db(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    try:
        con.execute(
            "CREATE TABLE reference_levels "
            "(symbol TEXT PRIMARY KEY, level REAL NOT NULL, band TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        con.executemany(
            "INSERT INTO reference_levels(symbol, level, band, updated_at) VALUES (?,?,?,?)",
            [
                ("FIX_AAA", 10.0, "WATCH", "2026-02-01T00:00:00+00:00"),
                ("FIX_BBB", 20.0, "ALERT", "2026-02-01T00:00:00+00:00"),
            ],
        )
        con.commit()
    finally:
        con.close()
    return path


def run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CONTROLLER)] + args,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=60,
    )


def main() -> int:
    check("controller_file_exists", CONTROLLER.is_file())
    check("self_file_exists", SELF.is_file())

    # py_compile sanity (equivalent)
    try:
        py_compile.compile(str(CONTROLLER), doraise=True)
        check("py_compile_controller", True)
    except Exception as e:  # noqa: BLE001
        check("py_compile_controller", False, str(e))
    try:
        py_compile.compile(str(SELF), doraise=True)
        check("py_compile_self", True)
    except Exception as e:  # noqa: BLE001
        check("py_compile_self", False, str(e))

    mod = load_controller()

    # Authority flags
    auth = getattr(mod, "AUTHORITY", {})
    ok_auth = all(auth.get(k) is v for k, v in REQUIRED_AUTHORITY.items())
    check("authority_flags", ok_auth, f"got={auth}")

    with tempfile.TemporaryDirectory(prefix="g6test_") as td:
        tmp = Path(td)
        scan = make_fixture_tree(tmp)
        fixture = make_fixture_db(tmp / "tmp" / "g6-fixture.sqlite")
        (tmp / "tmp").mkdir(parents=True, exist_ok=True)

        # Inventory names unmigrated writable Markdown consumers
        artifact = mod.run_inventory(scan_root=scan)
        unm = artifact.get("unmigrated_writable_markdown_consumers", [])
        check("inventory_finds_unmigrated", len(unm) >= 5, f"unm={unm}")
        check(
            "inventory_names_band_sync",
            "reference_band_note_sync.py" in unm,
            f"unm={unm}",
        )
        check(
            "inventory_migrated_not_flagged",
            "reference_levels_derived_refresh_apply.py" not in unm,
            f"unm={unm}",
        )
        check("inventory_cutover_blocked", artifact.get("cutover_allowed") is False)
        check("inventory_validate_clean", mod.validate_inventory(artifact) == [])

        # Report: tmp-only enforcement
        forbidden = tmp / "03. Alerts and Recommendations" / "Alert Bands and Invalidation Register.md"
        try:
            mod.enforce_report_path(forbidden)
            check("report_rejects_canon_path", False, "forbidden path accepted")
        except ValueError:
            check("report_rejects_canon_path", True)
        prod_like = tmp / "tmp" / "finance-canon.sqlite"
        try:
            mod.fetch_reference_levels(prod_like)
            check("report_rejects_production_sqlite", False, "production path accepted")
        except (ValueError, FileNotFoundError):
            # fetch raises ValueError for production names before existence check
            check("report_rejects_production_sqlite", True)
        # Allowed tmp report
        good_report = tmp / "tmp" / "g6-reference-levels-readonly-report.md"
        res = mod.run_report(str(fixture), str(good_report))
        check("report_builds_from_fixture", res["rows"] == 2, f"res={res.get('rows')}")
        good_report.write_text(res["content"], encoding="utf-8")
        check(
            "report_header_canon",
            "sole writable reference-level canon" in good_report.read_text(encoding="utf-8"),
        )

        # Rollback drill restores exact bytes
        proof = mod.backup_rollback_drill(str(fixture), str(tmp / "tmp" / "drillwork"))
        check("rollback_mutation_observed", proof.get("mutation_observed") is True, f"{proof}")
        check("rollback_restores_exact", proof.get("restored_exact") is True, f"{proof}")
        check(
            "rollback_hash_roundtrip",
            proof.get("sha_before") == proof.get("sha_after_restore"),
            f"{proof}",
        )
        # Production drill target refused
        try:
            mod.backup_rollback_drill(str(tmp / "finance-canon.sqlite"), str(tmp / "tmp" / "w"))
            check("drill_rejects_production", False, "production drill accepted")
        except (ValueError, FileNotFoundError):
            check("drill_rejects_production", True)

        # CLI: --apply blocked (fail closed), no writes
        p = run_cli(["--apply", "--write", "--validate"], tmp)
        check("cli_apply_blocked_exit2", p.returncode == 2, f"rc={p.returncode} out={p.stderr[:300]}")

        # CLI: --inventory --write --validate (hermetic, tmp under cwd)
        inv_path = tmp / "tmp" / "g6-consumer-inventory.json"
        p = run_cli(
            [
                "--inventory",
                "--write",
                "--validate",
                "--scan-root",
                str(scan),
                "--inventory-path",
                str(inv_path),
            ],
            tmp,
        )
        check("cli_inventory_exit0", p.returncode == 0, f"rc={p.returncode} err={p.stderr[:500]}")
        check("cli_inventory_artifact_tmp", inv_path.is_file())
        if inv_path.is_file():
            data = json.loads(inv_path.read_text(encoding="utf-8"))
            check(
                "cli_inventory_artifact_names_unmigrated",
                len(data.get("unmigrated_writable_markdown_consumers", [])) >= 5,
            )

        # CLI: --report --write --validate
        rpt_path = tmp / "tmp" / "g6-reference-levels-readonly-report.md"
        if rpt_path.exists():
            rpt_path.unlink()
        p = run_cli(
            [
                "--report",
                "--write",
                "--validate",
                "--sqlite-path",
                str(fixture),
                "--report-path",
                str(rpt_path),
            ],
            tmp,
        )
        check("cli_report_exit0", p.returncode == 0, f"rc={p.returncode} err={p.stderr[:500]}")
        check("cli_report_tmp_only", rpt_path.is_file())
        check("cli_no_canon_overwrite", not forbidden.exists())

        # CLI: --dry-run --write --validate (expect BLOCKED exit 2, fail-closed)
        dry_path = tmp / "tmp" / "g6-dry-run.json"
        proof_path = tmp / "tmp" / "g6-rollback-proof.json"
        p = run_cli(
            [
                "--dry-run",
                "--write",
                "--validate",
                "--scan-root",
                str(scan),
                "--sqlite-path",
                str(fixture),
                "--inventory-path",
                str(inv_path),
                "--proof-path",
                str(proof_path),
                "--dryrun-path",
                str(dry_path),
            ],
            tmp,
        )
        check("cli_dryrun_blocked_exit2", p.returncode == 2, f"rc={p.returncode} err={p.stderr[:500]}")
        if dry_path.is_file():
            dry = json.loads(dry_path.read_text(encoding="utf-8"))
            check("cli_dryrun_status_blocked", dry.get("status") == "BLOCKED", f"{dry.get('status')}")
        else:
            check("cli_dryrun_status_blocked", False, "dry-run artifact missing")
        check("cli_proof_artifact_tmp", proof_path.is_file())

        # No production sqlite or markdown canon mutation in temp tree
        strays = list(tmp.rglob("finance-canon.sqlite")) + list(tmp.rglob("finance_canon.sqlite"))
        check("no_production_sqlite_created", len(strays) == 0, f"{strays}")
        check("no_canon_md_overwrite", not forbidden.exists())

        # Hardening 1: tmp/../state/finance traversal resolves to production sqlite
        trav_sqlite = tmp / "tmp" / ".." / "state" / "finance" / "finance-canon.sqlite"
        check(
            "hardening_traversal_sqlite_rejected",
            mod.is_production_sqlite(trav_sqlite) is True
            and mod.is_production_sqlite("tmp/../state/finance/finance-canon.sqlite") is True,
        )

        # Hardening 2: tmp/../ canon escapes fail closed across report/json/fetch/drill
        trav_report = (
            tmp / "tmp" / ".." / "03. Alerts and Recommendations"
            / "g6-reference-levels-readonly-report.md"
        )
        try:
            mod.enforce_report_path(trav_report)
            trav_report_ok = False
        except ValueError:
            trav_report_ok = True
        try:
            mod.enforce_tmp_json_path(trav_sqlite)
            trav_json_ok = False
        except ValueError:
            trav_json_ok = True
        try:
            mod.fetch_reference_levels(trav_sqlite)
            trav_fetch_ok = False
        except ValueError:
            trav_fetch_ok = True
        try:
            mod.backup_rollback_drill(
                str(fixture), str(tmp / "tmp" / ".." / "03. Alerts and Recommendations")
            )
            trav_drill_ok = False
        except (ValueError, FileNotFoundError):
            trav_drill_ok = True
        check(
            "hardening_traversal_canon_paths_rejected",
            trav_report_ok and trav_json_ok and trav_fetch_ok and trav_drill_ok,
        )

        # Hardening 3: generic write_text() is NOT a markdown canon writer
        generic = mod.classify_source(
            "json_export_util.py",
            "from pathlib import Path\ndef dump():\n"
            "    Path('tmp/out.json').write_text('{}')\n",
        )
        check(
            "hardening_generic_write_text_not_canon_writer",
            generic.get("writes_markdown") is False
            and generic.get("status") != "unmigrated_markdown_writer",
        )

        # Hardening 4: canon Alert Bands write still flagged; SQL-only stays migrated
        canon_hit = mod.classify_source(
            "reference_band_note_sync.py",
            "# touches Alert Bands and Invalidation Register\n"
            "open('Alert Bands and Invalidation Register.md', 'w').write('x')\n",
        )
        migrated = mod.classify_source(
            "reference_levels_derived_refresh_apply.py",
            "markdown_mutation_allowed=False\nimport sqlite3\n",
        )
        check(
            "hardening_canon_write_still_flagged",
            canon_hit.get("writes_markdown") is True
            and canon_hit.get("status") == "unmigrated_markdown_writer"
            and migrated.get("status") == "migrated_sql_only"
            and migrated.get("writes_markdown") is False,
        )

    print(f"\nSUMMARY pass={len(PASS)} fail={len(FAIL)}")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
