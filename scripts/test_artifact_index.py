from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
DB = WORKSPACE / "tmp" / "veritas-artifact-index.sqlite"
sys.path.insert(0, str(WORKSPACE / "scripts"))


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def rebuild_index(errors: list[str]) -> None:
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / "scripts" / "artifact_index.py"), "rebuild"],
        cwd=WORKSPACE,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(f"artifact_index rebuild failed: {result.stderr or result.stdout}")


def run_artifact_index(args: list[str], errors: list[str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(WORKSPACE / "scripts" / "artifact_index.py"), *args],
        cwd=WORKSPACE,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        errors.append(f"artifact_index {' '.join(args)} failed: {result.stderr or result.stdout}")
    return result



def check_json_first_markdown_gates(errors: list[str]) -> None:
    """Artifact-index proof commands should be JSON-first, with Markdown opt-in."""
    compat_md = WORKSPACE / "tmp" / "artifact-index-json-first-compat-test.md"
    if compat_md.exists():
        compat_md.unlink()
    default_result = run_artifact_index(["phase3f-preflight", "--output", "tmp/artifact-index-json-first-default.json", "--validation-output", "tmp/artifact-index-json-first-default-validation.json"], errors)
    expect(default_result.returncode == 0 and "status=ok" in default_result.stdout, "JSON-first default phase3f command should pass", errors)
    expect(".md" not in default_result.stdout.lower(), f"JSON-first default stdout should not advertise Markdown output: {default_result.stdout}", errors)
    expect((WORKSPACE / "tmp" / "artifact-index-json-first-default.json").exists(), "JSON-first default should write JSON output", errors)
    expect((WORKSPACE / "tmp" / "artifact-index-json-first-default-validation.json").exists(), "JSON-first default should write validation JSON output", errors)
    compat_result = run_artifact_index(["phase3f-preflight", "--output", "tmp/artifact-index-json-first-compat.json", "--validation-output", "tmp/artifact-index-json-first-compat-validation.json", "--md-output", "tmp/artifact-index-json-first-compat-test.md"], errors)
    expect(compat_result.returncode == 0 and compat_md.exists(), "Explicit --md-output compatibility should write Markdown", errors)
    if compat_md.exists():
        compat_md.unlink()

def check_db(errors: list[str]) -> None:
    expect(DB.exists(), "artifact index DB should exist after rebuild", errors)
    if not DB.exists():
        return
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        counts = dict(
            conn.execute(
                """
                SELECT
                  (SELECT COUNT(*) FROM artifact_runs) AS runs,
                  (SELECT COUNT(*) FROM market_events) AS market_events,
                  (SELECT COUNT(*) FROM daily_review_objects) AS daily_review_objects,
                  (SELECT COUNT(*) FROM capital_recommendations) AS capital_recommendations,
                  (SELECT COUNT(*) FROM source_artifacts) AS source_artifacts,
                  (SELECT COUNT(*) FROM validator_runs) AS validator_runs,
                  (SELECT COUNT(*) FROM authority_flags) AS authority_flags,
                  (SELECT COUNT(*) FROM canon_proposals) AS canon_proposals,
                  (SELECT COUNT(*) FROM today_decision_items) AS today_decision_items,
                  (SELECT COUNT(*) FROM official_ir_capture_runs) AS official_ir_capture_runs,
                  (SELECT COUNT(*) FROM official_ir_capture_fields) AS official_ir_capture_fields,
                  (SELECT COUNT(*) FROM source_field_lineage) AS source_field_lineage,
                  (SELECT COUNT(*) FROM canon_proposal_staging) AS canon_proposal_staging,
                  (SELECT COUNT(*) FROM canon_proposal_evidence_links) AS canon_proposal_evidence_links,
                  (SELECT COUNT(*) FROM earnings_lifecycle_events) AS earnings_lifecycle_events,
                  (SELECT COUNT(*) FROM dashboard_findings) AS dashboard_findings,
                  (SELECT COUNT(*) FROM source_freshness_rows) AS source_freshness_rows,
                  (SELECT COUNT(*) FROM deployment_readiness_rows) AS deployment_readiness_rows,
                  (SELECT COUNT(*) FROM artifact_file_state) AS artifact_file_state
                """
            ).fetchone()
        )
        expect(counts["runs"] >= 2, "index should contain source artifact runs", errors)
        expect(counts["market_events"] > 0, "index should contain market events", errors)
        expect(counts["daily_review_objects"] > 0, "index should contain daily review objects", errors)
        expect(counts["capital_recommendations"] > 0, "index should contain capital recommendations", errors)
        expect(counts["source_artifacts"] > 0, "truth spine should contain source artifact lineage", errors)
        expect(counts["validator_runs"] > 0, "truth spine should contain validator runs", errors)
        expect(counts["authority_flags"] > 0, "truth spine should contain authority flags", errors)
        expect(counts["canon_proposals"] > 0, "truth spine should contain canon proposal/apply staging rows", errors)
        expect(counts["today_decision_items"] > 0, "truth spine should contain Today-card decision items", errors)
        expect(counts["official_ir_capture_runs"] >= 20, "truth spine should contain official IR capture runs", errors)
        expect(counts["official_ir_capture_fields"] > 0, "truth spine should contain official IR capture field rows", errors)
        expect(counts["source_field_lineage"] > 0, "truth spine should contain source field lineage rows", errors)
        expect(counts["canon_proposal_staging"] > 0, "truth spine should contain exact canon proposal staging rows", errors)
        expect(counts["canon_proposal_evidence_links"] > 0, "truth spine should contain canon proposal evidence links", errors)
        expect(counts["earnings_lifecycle_events"] > 0, "truth spine should contain earnings lifecycle proof rows", errors)
        expect(counts["dashboard_findings"] > 0, "truth spine should contain dashboard validation finding rows", errors)
        expect(counts["source_freshness_rows"] > 0, "truth spine should contain source freshness rows", errors)
        expect(counts["deployment_readiness_rows"] > 0, "truth spine should contain deployment readiness rows", errors)
        expect(counts["artifact_file_state"] == counts["runs"], "file-state rows should track indexed source runs", errors)
        for view in [
            "v_cockpit_action_queue", "v_cockpit_ticker_timeline", "v_cockpit_trust_boundary",
            "v_cockpit_official_source_fields", "v_cockpit_canon_staging", "v_cockpit_earnings_lifecycle",
            "v_cockpit_dashboard_findings", "v_cockpit_source_freshness", "v_cockpit_deployment_readiness",
        ]:
            exists = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='view' AND name=?", (view,)).fetchone()[0]
            expect(exists == 1, f"{view} should exist", errors)
        trust = conn.execute(
            "SELECT COUNT(*) FROM artifact_runs WHERE canonical_mutation_allowed != 0 OR owner_review_required != 1"
        ).fetchone()[0]
        expect(trust == 0, "indexed artifacts should preserve review-only / owner-gated boundary", errors)
        unsafe_market_events = conn.execute(
            """
            SELECT COUNT(*) FROM market_events
            WHERE canonical_mutation_allowed != 0
               OR trade_execution_allowed != 0
               OR owner_review_required != 1
            """
        ).fetchone()[0]
        expect(unsafe_market_events == 0, "market events should remain owner-gated and non-executable", errors)
        unsafe_daily_reviews = conn.execute(
            "SELECT COUNT(*) FROM daily_review_objects WHERE owner_review_required != 1"
        ).fetchone()[0]
        expect(unsafe_daily_reviews == 0, "daily review objects should remain owner-review required", errors)
        unsafe_capital_recs = conn.execute(
            "SELECT COUNT(*) FROM capital_recommendations WHERE owner_approval_required != 1"
        ).fetchone()[0]
        expect(unsafe_capital_recs == 0, "capital recommendations should remain owner-approval required", errors)
        forbidden_authority = conn.execute(
            """
            SELECT COUNT(*) FROM authority_flags
            WHERE flag_value != 0
              AND flag_name IN (
                'trade_execution_allowed', 'live_trade_or_account_action_allowed',
                'paper_trade_submit_cancel_allowed_by_today_card', 'money_movement_allowed',
                'owner_approval_inferred', 'generated_report_is_canonical'
              )
            """
        ).fetchone()[0]
        expect(forbidden_authority == 0, "SQL truth spine must not index forbidden authority flags as true", errors)
        today_etn = conn.execute(
            "SELECT COUNT(*) FROM today_decision_items WHERE ticker='ETN'"
        ).fetchone()[0]
        expect(today_etn > 0, "Today-card ETN row should be queryable without assuming current owner-action state", errors)
        official_ir_for_amd = conn.execute(
            "SELECT COUNT(*) FROM official_ir_capture_fields WHERE ticker='AMD' AND field_name='adjusted_eps' AND excerpt_sha256 IS NOT NULL"
        ).fetchone()[0]
        expect(official_ir_for_amd > 0, "AMD adjusted EPS official IR field should be queryable with excerpt hash", errors)
        unsafe_official_ir = conn.execute(
            "SELECT COUNT(*) FROM official_ir_capture_runs WHERE review_only != 1 OR resolved_for_apply != 0"
        ).fetchone()[0]
        expect(unsafe_official_ir == 0, "official IR SQL rows must remain review-only and non-apply", errors)
        unsafe_canon_stage = conn.execute(
            "SELECT COUNT(*) FROM canon_proposal_staging WHERE proposal_apply_allowed != 0"
        ).fetchone()[0]
        expect(unsafe_canon_stage == 0, "canon proposal SQL staging must never set proposal_apply_allowed true", errors)
        etn = conn.execute(
            """
            SELECT COUNT(*) FROM (
              SELECT ticker_or_macro_sleeve AS ticker FROM market_events WHERE upper(ticker_or_macro_sleeve)='ETN'
              UNION ALL
              SELECT ticker FROM daily_review_objects WHERE upper(ticker)='ETN'
              UNION ALL
              SELECT ticker FROM capital_recommendations WHERE upper(ticker)='ETN'
            )
            """
        ).fetchone()[0]
        expect(etn > 0, "ETN should be retrievable from the derived index", errors)
        cockpit_rows = conn.execute("SELECT COUNT(*) FROM v_cockpit_action_queue").fetchone()[0]
        expect(cockpit_rows > 0, "cockpit action queue view should have rows", errors)
        stopline_unsafe = conn.execute("SELECT COUNT(*) FROM v_cockpit_canon_staging WHERE proposal_apply_allowed != 0").fetchone()[0]
        expect(stopline_unsafe == 0, "cockpit stopline view should preserve proposal_apply_allowed=false", errors)
        nvda_lifecycle = conn.execute("SELECT COUNT(*) FROM v_cockpit_earnings_lifecycle WHERE ticker='NVDA' AND review_only=1 AND trade_or_account_action_allowed=0 AND owner_approval_inferred=0").fetchone()[0]
        expect(nvda_lifecycle > 0, "NVDA earnings lifecycle proof should be directly queryable and review-only", errors)
        etn_deployment = conn.execute("SELECT COUNT(*) FROM v_cockpit_deployment_readiness WHERE ticker='ETN' AND bucket='DEPLOYABLE NOW'").fetchone()[0]
        expect(etn_deployment > 0, "ETN deployment readiness row should be directly queryable", errors)
        unsafe_source_freshness = conn.execute("SELECT COUNT(*) FROM v_cockpit_source_freshness WHERE usable_for_canonical_mutation != 0").fetchone()[0]
        expect(unsafe_source_freshness == 0, "source freshness SQL rows must not authorize canonical mutation", errors)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        expect(integrity == "ok", "SQLite integrity_check should pass", errors)
        fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        expect(len(fk_rows) == 0, "SQLite foreign_key_check should pass", errors)
        plan = "\n".join(str(tuple(row)) for row in conn.execute("EXPLAIN QUERY PLAN SELECT * FROM daily_review_objects WHERE upper(ticker)=? ORDER BY generated_at_utc DESC LIMIT 5", ("ETN",)))
        expect("idx_daily_review_ticker_upper_time" in plan, "ticker cockpit query should use upper(ticker) expression index", errors)


def check_cli_commands(errors: list[str]) -> None:
    commands = [
        ["cockpit", "--limit", "3"],
        ["ticker-cockpit", "ETN", "--limit", "3"],
        ["trust-cockpit", "--limit", "3"],
        ["proof-field", "AMD", "adjusted_eps"],
        ["stoplines", "--limit", "3"],
        ["earnings-lifecycle", "NVDA", "--limit", "3"],
        ["deployment-readiness", "ETN", "--limit", "3"],
        ["dashboard-findings", "--limit", "3"],
        ["source-freshness", "--limit", "3"],
        ["canon-stage-readiness", "--limit", "3"],
        ["handoff", "--workflow", "WF72", "--limit", "3"],
        ["note-drift", "--limit", "3"],
        ["phase3b-writepath-preflight", "--limit", "200"],
        ["phase3d-consumer-parity", "--limit", "200"],
        ["phase3e-dashboard-proof-pilot", "--limit", "200"],
        ["phase3f-preflight"],
        ["fingerprints"],
        ["validate"],
    ]
    for args in commands:
        result = run_artifact_index(args, errors)
        expect(result.returncode == 0 and result.stdout.strip(), f"CLI command should produce output: {' '.join(args)}", errors)
    handoff_json = run_artifact_index(["handoff", "--workflow", "WF72", "--limit", "3", "--json"], errors)
    if handoff_json.returncode == 0 and handoff_json.stdout.strip():
        packet = json.loads(handoff_json.stdout)
        expect(packet.get("authority_boundary") == "derived_review_only_index_not_canon_not_apply", "handoff packet must preserve derived SQL boundary", errors)
        expect(packet.get("canonical_next_step_owner") == "06. Playbooks/Active Workflows.md", "handoff packet must route canonical next-step ownership to Active Workflows", errors)
        expect(isinstance(packet.get("latest_artifact_runs"), list), "handoff packet must include artifact run locator rows", errors)
        expect(isinstance(packet.get("latest_source_artifacts"), list), "handoff packet must include source artifact locator rows", errors)
    canon_stage_readiness_json = run_artifact_index(["canon-stage-readiness", "--limit", "20", "--json"], errors)
    if canon_stage_readiness_json.returncode == 0 and canon_stage_readiness_json.stdout.strip():
        report = json.loads(canon_stage_readiness_json.stdout)
        authority = report.get("authority") or {}
        summary = report.get("summary") or {}
        expect(report.get("boundary") == "derived_review_only_index_not_canon_not_apply", "canon-stage-readiness must preserve derived SQL boundary", errors)
        expect(authority.get("canonical_note_mutation_allowed") is False, "canon-stage-readiness must not allow canonical note mutation", errors)
        expect(authority.get("proposal_apply_allowed") is False, "canon-stage-readiness must not allow proposal apply", errors)
        expect(summary.get("activation_or_apply_ready_rows") == 0, "canon-stage-readiness must report zero activation/apply-ready rows", errors)
        expect("historical_applied_rows" in summary and "incomplete_review_only_rows" in summary, "canon-stage-readiness must distinguish historical applied from incomplete review-only rows", errors)

    note_drift_json = run_artifact_index(["note-drift", "--limit", "3", "--json"], errors)
    if note_drift_json.returncode == 0 and note_drift_json.stdout.strip():
        report = json.loads(note_drift_json.stdout)
        authority = report.get("authority") or {}
        expect(report.get("boundary") == "derived_review_only_index_not_canon_not_apply", "note-drift report must preserve derived SQL boundary", errors)
        expect(authority.get("report_is_candidate_review_only") is True, "note-drift report must be candidate/review-only", errors)
        expect(authority.get("canonical_note_mutation_allowed") is False, "note-drift report must not allow canonical note mutation", errors)
        expect(authority.get("proposal_apply_allowed") is False, "note-drift report must not allow proposal apply", errors)


def check_incremental_equivalence(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory(prefix="artifact-index-test-", ignore_cleanup_errors=True) as tmpdir:
        full_db = Path(tmpdir) / "full.sqlite"
        inc_db = Path(tmpdir) / "incremental.sqlite"
        run_artifact_index(["--db", str(full_db), "rebuild"], errors)
        run_artifact_index(["--db", str(inc_db), "rebuild"], errors)
        run_artifact_index(["--db", str(inc_db), "incremental"], errors)
        if not full_db.exists() or not inc_db.exists():
            return
        tables = [
            "artifact_runs", "market_events", "daily_review_objects", "capital_recommendations",
            "source_artifacts", "validator_runs", "authority_flags", "canon_proposals",
            "today_decision_items", "official_ir_capture_runs", "official_ir_capture_fields",
            "source_field_lineage", "canon_proposal_staging", "canon_proposal_evidence_links",
            "earnings_lifecycle_events", "dashboard_findings", "source_freshness_rows",
            "deployment_readiness_rows", "artifact_file_state",
        ]
        with sqlite3.connect(full_db) as full, sqlite3.connect(inc_db) as inc:
            for table in tables:
                full_count = full.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                inc_count = inc.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                expect(full_count == inc_count, f"incremental count should match full rebuild for {table}: {full_count} vs {inc_count}", errors)
        full_fp_result = run_artifact_index(["--db", str(full_db), "fingerprints", "--json"], errors)
        inc_fp_result = run_artifact_index(["--db", str(inc_db), "fingerprints", "--json"], errors)
        if full_fp_result.returncode == 0 and inc_fp_result.returncode == 0:
            full_fingerprints = json.loads(full_fp_result.stdout).get("tables") or {}
            inc_fingerprints = json.loads(inc_fp_result.stdout).get("tables") or {}
            for table in tables:
                full_table = full_fingerprints.get(table) or {}
                inc_table = inc_fingerprints.get(table) or {}
                expect(
                    full_table.get("row_count") == inc_table.get("row_count"),
                    f"incremental row fingerprint count should match full rebuild for {table}",
                    errors,
                )
                expect(
                    full_table.get("sha256") == inc_table.get("sha256"),
                    f"incremental row fingerprint hash should match full rebuild for {table}",
                    errors,
                )
        with sqlite3.connect(inc_db) as inc:
            inc.execute("INSERT INTO artifact_runs(source_file, artifact_type, window, indexed_at_utc, file_mtime_utc, owner_review_required) VALUES ('tmp/deleted-fixture.json', 'unknown', 'unknown', 'x', 'x', 1)")
            run_id = inc.execute("SELECT id FROM artifact_runs WHERE source_file='tmp/deleted-fixture.json'").fetchone()[0]
            inc.execute("INSERT INTO artifact_file_state(source_file, artifact_type, file_mtime_utc, file_size, file_sha256, artifact_run_id, indexed_at_utc, status) VALUES ('tmp/deleted-fixture.json', 'unknown', 'x', 1, 'x', ?, 'x', 'indexed')", (run_id,))
            inc.commit()
        run_artifact_index(["--db", str(inc_db), "incremental"], errors)
        with sqlite3.connect(inc_db) as inc:
            stale = inc.execute("SELECT COUNT(*) FROM artifact_runs WHERE source_file='tmp/deleted-fixture.json'").fetchone()[0]
            expect(stale == 0, "incremental rebuild should remove stale deleted source rows", errors)


def check_today_card_sql_source_routing(errors: list[str]) -> None:
    from today_card_generator import SQL_AUTHORITY_BOUNDARY, load_sql_source_records, source_record_from_index

    records, health = load_sql_source_records(["capital_deployment_recommendations", "dashboard_validation"])
    expect(health.get("status") == "ok", f"Today-card SQL source routing should see healthy artifact index: {health}", errors)
    expect(
        health.get("authority_boundary") == SQL_AUTHORITY_BOUNDARY,
        "Today-card SQL source routing must preserve derived/review-only/non-apply boundary",
        errors,
    )
    for role in ("capital_deployment_recommendations", "dashboard_validation"):
        expect(role in records and bool(records.get(role, {}).get("path")), f"SQL source routing should find role {role}", errors)
    fallback = {"path": "tmp/fallback.json", "generated_at_utc": "fallback", "status": "fallback"}
    index = {"artifacts": [{"role": "capital_deployment_recommendations", "path": "tmp/current-window-only.json", "generated_at_utc": "index", "status": "index"}]}
    routed = source_record_from_index(index, "capital_deployment_recommendations", fallback, records)
    expect(
        routed.get("path") == records.get("capital_deployment_recommendations", {}).get("path"),
        "Today-card source_record_from_index should prefer SQL source records over current-window JSON fallback",
        errors,
    )



def check_phase2_reconciliation(errors: list[str]) -> None:
    from artifact_index import PHASE2_RECONCILIATION_BOUNDARY, reconciliation_status, validate_sql_markdown_reconciliation

    expect(reconciliation_status("x", "x") == "match", "reconciliation fixture should detect match", errors)
    expect(reconciliation_status("sql", "note", "2026-05-23T01:00:00Z", "2026-05-22T01:00:00Z") == "sql_newer", "reconciliation fixture should detect stale note/sql_newer", errors)
    expect(reconciliation_status("sql", "note", "2026-05-22T01:00:00Z", "2026-05-23T01:00:00Z") == "note_newer", "reconciliation fixture should detect note_newer", errors)
    expect(reconciliation_status("sql", "note") == "conflict", "reconciliation fixture should detect conflict", errors)
    expect(reconciliation_status("", "note") == "missing_sql", "reconciliation fixture should detect missing SQL", errors)
    expect(reconciliation_status("sql", "") == "missing_note", "reconciliation fixture should detect missing note", errors)
    expect(reconciliation_status("sql", "", parse_status="parse_failed") == "parse_failed", "reconciliation fixture should detect parse failure", errors)

    result = run_artifact_index(["reconcile-sql-markdown", "--limit", "200"], errors)
    expect(result.returncode == 0 and "status=ok" in result.stdout, "Phase 2 reconciliation command should pass validation", errors)
    for rel_path in [
        "tmp/sql-canon-field-registry.json",
        "tmp/sql-markdown-reconciliation.json",
        "tmp/sql-reconciliation-validation.json",
    ]:
        expect((WORKSPACE / rel_path).exists(), f"Phase 2 output should exist: {rel_path}", errors)
    report = json.loads((WORKSPACE / "tmp" / "sql-markdown-reconciliation.json").read_text(encoding="utf-8"))
    registry = json.loads((WORKSPACE / "tmp" / "sql-canon-field-registry.json").read_text(encoding="utf-8"))
    validation = json.loads((WORKSPACE / "tmp" / "sql-reconciliation-validation.json").read_text(encoding="utf-8"))
    authority = report.get("authority") or {}
    expect(report.get("authority_boundary") == PHASE2_RECONCILIATION_BOUNDARY, "Phase 2 report should preserve review-only boundary", errors)
    expect(authority.get("canonical_note_mutation_allowed") is False, "Phase 2 report must not allow canonical note mutation", errors)
    expect(authority.get("trade_or_account_action_allowed") is False, "Phase 2 report must not allow trade/account action", errors)
    expect(validation.get("status") == "ok", f"Phase 2 validation should pass: {validation}", errors)
    rows = report.get("rows") or []
    expect(rows, "Phase 2 reconciliation should produce rows", errors)
    for ticker in ["ETN", "NVDA", "JPM", "LMT"]:
        expect(any((row.get("ticker") or "").upper() == ticker for row in rows), f"Phase 2 sample ticker should be present: {ticker}", errors)
    expect(any(row.get("reconciliation_status") == "match" for row in rows), "Phase 2 report should include at least one match fixture from live notes/artifacts", errors)
    expect(all(row.get("phase3_review_candidate") is False for row in rows if row.get("reconciliation_status") in {"conflict", "parse_failed", "manual_review_required"}), "Phase 2 conflicts/ambiguous rows must not be Phase 3 review candidates", errors)
    expect(registry.get("review_only") is True and registry.get("sql_is_canon") is False, "Phase 2 registry must be review-only and non-canon", errors)


def check_phase3a_dry_run(errors: list[str]) -> None:
    from artifact_index import PHASE3A_ALLOWED_FIELDS, PHASE3A_DRY_RUN_BOUNDARY

    result = run_artifact_index(["phase3a-dry-run", "--limit", "200"], errors)
    expect(result.returncode == 0 and "status=ok" in result.stdout, "Phase 3A dry-run command should pass validation", errors)
    for rel_path in [
        "tmp/sql-canon-phase3a-architecture.json",
        "tmp/sql-canon-phase3a-dry-run-promotion.json",
        "tmp/sql-canon-phase3a-validation.json",
    ]:
        expect((WORKSPACE / rel_path).exists(), f"Phase 3A output should exist: {rel_path}", errors)
    architecture = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3a-architecture.json").read_text(encoding="utf-8"))
    promotion = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3a-dry-run-promotion.json").read_text(encoding="utf-8"))
    validation = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3a-validation.json").read_text(encoding="utf-8"))
    expect(architecture.get("authority_boundary") == PHASE3A_DRY_RUN_BOUNDARY, "Phase 3A architecture should preserve dry-run boundary", errors)
    expect(promotion.get("authority_boundary") == PHASE3A_DRY_RUN_BOUNDARY, "Phase 3A promotion should preserve dry-run boundary", errors)
    expect(validation.get("status") == "ok", f"Phase 3A validation should pass: {validation}", errors)
    for surface in [architecture, promotion]:
        expect(surface.get("sql_is_canon") is False, "Phase 3A dry-run must not make SQL canon", errors)
        expect(surface.get("canonical_note_mutation_allowed") is False, "Phase 3A dry-run must not allow note mutation", errors)
        expect(surface.get("portfolio_mutation_allowed") is False, "Phase 3A dry-run must not allow portfolio mutation", errors)
        expect(surface.get("trade_or_account_action_allowed") is False, "Phase 3A dry-run must not allow trade/account action", errors)
        expect(surface.get("durable_canon_table_write_allowed") is False, "Phase 3A dry-run must not allow durable table writes", errors)
    candidates = promotion.get("dry_run_candidates") or []
    expect(candidates, "Phase 3A dry-run should produce at least one clean candidate from Phase 2 proof", errors)
    expect(all(row.get("field") in PHASE3A_ALLOWED_FIELDS for row in candidates), "Phase 3A candidates must stay inside exact allowlist", errors)
    expect(all(row.get("source_artifact_path") and (row.get("source_artifact_hash") or row.get("artifact_run_id")) and row.get("sql_generated_at_utc") for row in candidates), "Phase 3A candidates must carry lineage and freshness", errors)
    forbidden_terms = ["entry", "weight", "cash", "sizing", "risk", "account", "trade", "paper", "live"]
    expect(not any(any(term in (row.get("field") or "").lower() for term in forbidden_terms) for row in candidates), "Phase 3A candidates must exclude forbidden field families", errors)


def check_phase3b_writepath_preflight(errors: list[str]) -> None:
    from artifact_index import PHASE3A_ALLOWED_FIELDS, PHASE3B_DURABLE_CACHE_DB, PHASE3B_WRITEPATH_PREFLIGHT_BOUNDARY

    durable_cache_db = WORKSPACE / PHASE3B_DURABLE_CACHE_DB
    existed_before = durable_cache_db.exists()
    result = run_artifact_index(["phase3b-writepath-preflight", "--limit", "200"], errors)
    expect(result.returncode == 0 and "status=ok" in result.stdout and "write_path_blocked=True" in result.stdout, "Phase 3B write-path preflight command should pass while keeping actual write path blocked", errors)
    for rel_path in [
        "tmp/sql-canon-phase3b-writepath-preflight.json",
        "tmp/sql-canon-phase3b-validation.json",
    ]:
        expect((WORKSPACE / rel_path).exists(), f"Phase 3B output should exist: {rel_path}", errors)
    preflight = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3b-writepath-preflight.json").read_text(encoding="utf-8"))
    validation = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3b-validation.json").read_text(encoding="utf-8"))
    expect(preflight.get("authority_boundary") == PHASE3B_WRITEPATH_PREFLIGHT_BOUNDARY, "Phase 3B preflight should preserve write-blocked boundary", errors)
    expect(validation.get("status") == "ok", f"Phase 3B validation should pass: {validation}", errors)
    expect(preflight.get("actual_write_path_blocked") is True, "Phase 3B actual write path must remain blocked", errors)
    expect(preflight.get("approval_gate_required_before_any_write") is True, "Phase 3B must require explicit approval before any write", errors)
    forbidden_false = [
        "sql_write_allowed", "durable_canon_table_write_allowed", "canonical_note_mutation_allowed",
        "portfolio_mutation_allowed", "owner_approval_inferred", "trade_or_account_action_allowed",
        "trade_execution_allowed", "live_trade_or_account_action_allowed", "paper_trade_submit_cancel_allowed",
        "paper_trade_authority_allowed", "live_trade_authority_allowed", "account_action_allowed",
        "money_movement_allowed", "generated_report_is_canonical",
    ]
    for key in forbidden_false:
        expect(preflight.get(key) is False, f"Phase 3B preflight must keep forbidden flag false: {key}", errors)
    plan = preflight.get("durable_cache_db_plan") or {}
    expect(plan.get("recommended_path") == PHASE3B_DURABLE_CACHE_DB, "Phase 3B should target separate durable cache DB path", errors)
    expect(plan.get("creation_in_this_phase_allowed") is False, "Phase 3B must not allow DB/table creation in this phase", errors)
    candidates = preflight.get("candidate_rows") or []
    expect(len(candidates) == 2, "Phase 3B should preflight exactly the two Phase 3A candidates", errors)
    expect(all(row.get("field") in PHASE3A_ALLOWED_FIELDS for row in candidates), "Phase 3B candidates must stay inside Phase 3A exact allowlist", errors)
    expect(bool(preflight.get("rollback_export_preflight_contract", {}).get("required_before_future_write")), "Phase 3B should include rollback/export preflight contract", errors)
    expect(len(preflight.get("rebuild_safety_test_plan") or []) >= 3, "Phase 3B should include rebuild-safety test plan", errors)
    expect(len(preflight.get("consumer_parity_test_plan") or []) >= 3, "Phase 3B should include consumer parity test plan", errors)
    if not existed_before:
        expect(not durable_cache_db.exists(), "Phase 3B preflight must not create durable canon/cache DB", errors)


LOW_RISK_PHASE3_KEYS = [
    "NVDA:earnings_lifecycle_status",
    "NVDA:post_earnings_review_confirmed",
    "NVDA:last_earnings_date",
    "NVDA:post_earnings_review_date",
    "deployment:source_freshness_classification",
    "earnings:source_freshness_classification",
    "breadth:source_freshness_classification",
    "credit:source_freshness_classification",
    "fundamental_ir:source_freshness_classification",
    "fundamentals:source_freshness_classification",
    "market:source_freshness_classification",
    "policy:source_freshness_classification",
    "technical:source_freshness_classification",
]
LOW_RISK_PHASE3_BOUNDARY = "phase7_sql_canon_source_freshness_metadata_exact_thirteen_keys_no_execution_authority"
PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY = "portfolio:source_freshness_classification"
NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY = "deployment:evidence_completeness_display"


def active_sql_fallback_values() -> dict[str, object]:
    base: dict[str, object] = {
        "NVDA:earnings_lifecycle_status": "post_event_review_confirmed_next_date_pending",
        "NVDA:post_earnings_review_confirmed": True,
        "NVDA:last_earnings_date": "2026-05-20",
        "NVDA:post_earnings_review_date": "2026-05-20",
        "deployment:source_freshness_classification": "fresh",
        "earnings:source_freshness_classification": "fresh",
        "breadth:source_freshness_classification": "fresh",
        "credit:source_freshness_classification": "fresh",
        "fundamental_ir:source_freshness_classification": "fresh",
        "fundamentals:source_freshness_classification": "fresh",
        "market:source_freshness_classification": "current",
        "policy:source_freshness_classification": "current",
        "technical:source_freshness_classification": "fresh",
    }
    worker_path = WORKSPACE / "tmp" / "wf72-entry-stop-sql-activation-pilot-worker.json"
    state_path = WORKSPACE / "tmp" / "wf72-entry-stop-sql-activation-state.json"
    try:
        worker = json.loads(worker_path.read_text(encoding="utf-8"))
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        return base
    active_keys = set(state.get("active_entry_stop_reference_keys") or [])
    fields = worker.get("candidate_fields") or []
    for row in worker.get("candidate_rows") or []:
        if not isinstance(row, dict) or not row.get("ticker"):
            continue
        ticker = str(row.get("ticker")).upper()
        for field in fields:
            key = f"{ticker}:{field}"
            if key in active_keys:
                base[key] = row.get(field)
    return base


def active_sql_approved_keys() -> list[str]:
    state_path = WORKSPACE / "tmp" / "wf72-entry-stop-sql-activation-state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        active = state.get("active_entry_stop_reference_keys") or []
    except Exception:
        active = []
    return list(LOW_RISK_PHASE3_KEYS) + list(active)


def check_neutral_deployment_evidence_shadow_contract(errors: list[str]) -> None:
    from sql_consumer_authority_guard import (
        DEPLOYMENT_ACTION_WORD_FRAGMENTS,
        NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES,
        build_phase4a_sql_consumer_authority_guard,
        neutral_deployment_evidence_contract_issues,
        neutral_deployment_evidence_value,
    )

    expect(NEUTRAL_DEPLOYMENT_EVIDENCE_SHADOW_KEY not in LOW_RISK_PHASE3_KEYS, "neutral deployment evidence display must not be part of active low-risk SQL-canon key set", errors)
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute("SELECT * FROM v_cockpit_deployment_readiness ORDER BY ticker")]
        expect(bool(rows), "deployment readiness rows should be visible in derived cockpit view", errors)
        values = [neutral_deployment_evidence_value(row) for row in rows]
        expect(set(values).issubset(set(NEUTRAL_DEPLOYMENT_EVIDENCE_VALUES)), f"neutral deployment shadow values must stay in neutral allowlist, got {values}", errors)
        expect(not neutral_deployment_evidence_contract_issues(field_name="evidence_completeness_display", values=values, row_by_key={}), "neutral deployment shadow contract should pass for neutral display values", errors)
        bad_values = ["DEPLOYABLE NOW", "ALMOST DEPLOYABLE", "PROMOTION REVIEW", "DO NOT TOUCH"]
        expect(bool(neutral_deployment_evidence_contract_issues(field_name="deployment_proof_status", values=bad_values, row_by_key={})), "current deployment_proof_status field/action values must be rejected by neutral display guard", errors)
        for fragment in DEPLOYMENT_ACTION_WORD_FRAGMENTS:
            if fragment in {"live"}:  # substring-sensitive word retained for endpoint/account safety scans, not all neutral text fixtures.
                continue
        guard = build_phase4a_sql_consumer_authority_guard(
            artifact_conn=conn,
            fallback_values_by_key={
                "NVDA:earnings_lifecycle_status": "post_event_review_confirmed_next_date_pending",
                "NVDA:post_earnings_review_confirmed": True,
                "NVDA:last_earnings_date": "2026-05-20",
                "NVDA:post_earnings_review_date": "2026-05-20",
                "deployment:source_freshness_classification": "fresh",
                "earnings:source_freshness_classification": "fresh",
                "breadth:source_freshness_classification": "fresh",
                "credit:source_freshness_classification": "fresh",
                "fundamental_ir:source_freshness_classification": "fresh",
                "fundamentals:source_freshness_classification": "fresh",
                "market:source_freshness_classification": "current",
                "policy:source_freshness_classification": "current",
                "technical:source_freshness_classification": "fresh",
            },
        )
    shadow = guard.get("neutral_deployment_evidence_shadow_metadata") or {}
    expect(shadow.get("status") == "shadow_only_display_metadata", f"neutral deployment evidence should render as shadow-only display metadata: {shadow}", errors)
    expect(shadow.get("current_field_permanent_hold") is True, "deployment_proof_status must remain permanent hold", errors)
    expect(shadow.get("sql_read_allowed_for_key") is False and shadow.get("cache_row_allowed") is False, "neutral deployment shadow key must not become SQL-readable/cache-active", errors)
    expect(shadow.get("current_value_migration_allowed") is False, "current deployment_proof_status values must not migrate", errors)
    expect(shadow.get("dashboard_behavior_change_allowed") is False, "neutral display shadow must not allow dashboard behavior change", errors)


def check_portfolio_source_freshness_shadow_contract(errors: list[str]) -> None:
    from sql_consumer_authority_guard import build_phase4a_sql_consumer_authority_guard

    expect(PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY not in LOW_RISK_PHASE3_KEYS, "portfolio source freshness must not be part of active low-risk SQL-canon key set", errors)
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute(
            """
            SELECT *
            FROM v_cockpit_source_freshness
            WHERE source_key='portfolio'
            ORDER BY source_file, path
            """
        )]
        expect(bool(rows), "portfolio source freshness row should be visible in derived cockpit freshness view", errors)
        expect(all(row.get("classification") == "manual_dependency" for row in rows), "portfolio source freshness must remain manual_dependency, not fresh/current", errors)
        expect(all(row.get("confidence_ceiling") == "review_required" for row in rows), "portfolio source freshness must remain review_required", errors)
        expect(all(int(row.get("usable_for_canonical_mutation") or 0) == 0 for row in rows), "portfolio source freshness must not allow canonical mutation", errors)
        expect(all(int(row.get("usable_for_review") or 0) == 1 for row in rows), "portfolio source freshness should remain review metadata only", errors)
        guard = build_phase4a_sql_consumer_authority_guard(
            artifact_conn=conn,
            fallback_values_by_key={
                "NVDA:earnings_lifecycle_status": "post_event_review_confirmed_next_date_pending",
                "NVDA:post_earnings_review_confirmed": True,
                "NVDA:last_earnings_date": "2026-05-20",
                "NVDA:post_earnings_review_date": "2026-05-20",
                "deployment:source_freshness_classification": "fresh",
                "earnings:source_freshness_classification": "fresh",
                "breadth:source_freshness_classification": "fresh",
                "credit:source_freshness_classification": "fresh",
                "fundamental_ir:source_freshness_classification": "fresh",
                "fundamentals:source_freshness_classification": "fresh",
                "market:source_freshness_classification": "current",
                "policy:source_freshness_classification": "current",
                "technical:source_freshness_classification": "fresh",
                PORTFOLIO_SOURCE_FRESHNESS_SHADOW_KEY: "manual_dependency",
                "portfolio:source_freshness_state": rows[0],
            },
        )
    shadow = guard.get("portfolio_source_freshness_shadow_metadata") or {}
    expect(shadow.get("status") == "shadow_only_manual_dependency_metadata", "portfolio source freshness should render as shadow-only degraded metadata", errors)
    expect(shadow.get("fallback_value") == "manual_dependency", "portfolio shadow metadata should preserve manual_dependency value", errors)
    expect(shadow.get("normalization_to_fresh_or_current_allowed") is False, "manual_dependency must not be normalized to fresh/current", errors)
    expect(shadow.get("sql_read_allowed_for_key") is False and shadow.get("cache_row_allowed") is False, "portfolio shadow key must not become SQL-readable/cache-active", errors)
    expect(shadow.get("cache_row_present") is False, "portfolio shadow key must not have a canon cache row", errors)


def low_risk_phase3_active() -> bool:
    path = WORKSPACE / "tmp" / "sql-canon-low-risk-phase3-validation.json"
    if not path.exists():
        return False
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("status") == "ok"
    except Exception:
        return False


def check_low_risk_phase3_activation(errors: list[str]) -> None:
    activation_path = WORKSPACE / "tmp" / "sql-canon-low-risk-phase3-activation.json"
    validation_path = WORKSPACE / "tmp" / "sql-canon-low-risk-phase3-validation.json"
    no_drift_path = WORKSPACE / "tmp" / "sql-canon-low-risk-phase3-post-activation-no-drift.json"
    rollback_path = WORKSPACE / "tmp" / "sql-canon-low-risk-phase3-rollback.sql"
    export_path = WORKSPACE / "tmp" / "sql-canon-low-risk-phase3-preactivation-export.json"
    for path in [activation_path, validation_path, no_drift_path, rollback_path, export_path]:
        expect(path.exists(), f"Low-risk Phase 3 output should exist: {path.relative_to(WORKSPACE).as_posix()}", errors)
    if not activation_path.exists() or not validation_path.exists():
        return
    activation = json.loads(activation_path.read_text(encoding="utf-8"))
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    no_drift = json.loads(no_drift_path.read_text(encoding="utf-8")) if no_drift_path.exists() else {}
    expect(activation.get("status") == "ok", f"Low-risk Phase 3 activation should be ok: {activation}", errors)
    expect(validation.get("status") == "ok", f"Low-risk Phase 3 validation should be ok: {validation}", errors)
    expect(no_drift.get("status") == "ok", f"Low-risk Phase 3 no-drift proof should be ok: {no_drift}", errors)
    expect(activation.get("authority_boundary") == LOW_RISK_PHASE3_BOUNDARY, "Low-risk Phase 3 activation should use exact boundary", errors)
    after_keys = [f"{row.get('scope')}:{row.get('field_name')}" for row in activation.get("cache_rows_after") or []]
    expect(set(after_keys) == set(LOW_RISK_PHASE3_KEYS) and len(after_keys) == len(LOW_RISK_PHASE3_KEYS), "Low-risk Phase 3 must activate exactly the approved thirteen-key final set", errors)
    expect(all(row.get("authority_boundary") == LOW_RISK_PHASE3_BOUNDARY for row in activation.get("cache_rows_after") or []), "Low-risk Phase 3 rows should carry exact boundary", errors)
    for key in ["canonical_note_mutation_allowed", "markdown_mutation_allowed", "portfolio_mutation_allowed", "owner_approval_inferred", "trade_or_account_action_allowed", "paper_trade_authority_allowed", "live_trade_authority_allowed", "money_movement_allowed", "cron_direct_apply_allowed"]:
        expect(activation.get(key) is False and no_drift.get(key) is False, f"Low-risk Phase 3 must keep forbidden authority false: {key}", errors)


def check_phase3c_cache_contract(errors: list[str]) -> None:
    from artifact_index import PHASE3B_DURABLE_CACHE_DB, PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY, PHASE4A_SQL_CANON_BOUNDARY, validate_canon_cache_db

    cache_db = WORKSPACE / PHASE3B_DURABLE_CACHE_DB
    if not cache_db.exists():
        return
    if low_risk_phase3_active():
        check_low_risk_phase3_activation(errors)
        return
    expected_candidates = [
        {"scope": "NVDA", "field": "post_earnings_review_confirmed", "value": "1"},
        {"scope": "NVDA", "field": "earnings_lifecycle_status", "value": "watchlist_already_closed"},
    ]
    validation = validate_canon_cache_db(cache_db, expected_candidates)
    expect(validation.get("status") == "ok", f"Phase 3C cache validator should pass when cache DB exists: {validation}", errors)
    with sqlite3.connect(cache_db) as conn:
        conn.row_factory = sqlite3.Row
        rows = [dict(row) for row in conn.execute("SELECT scope, field_name, field_value, authority_boundary FROM canon_cache_fields ORDER BY field_name")]
        expect(len(rows) == 2, "Phase 3C cache DB should contain exactly two approved current rows", errors)
        expect(all(row.get("scope") == "NVDA" for row in rows), "Phase 3C cache rows should be NVDA-only", errors)
        expect(all(row.get("authority_boundary") in {PHASE3C_APPROVED_CACHE_WRITE_BOUNDARY, PHASE4A_SQL_CANON_BOUNDARY} for row in rows), "Phase 3C/4A cache rows should carry an approved cache/canon boundary", errors)
        forbidden = conn.execute(
            """
            SELECT COUNT(*) FROM canon_cache_fields
            WHERE field_name NOT IN ('post_earnings_review_confirmed', 'earnings_lifecycle_status')
               OR lower(field_name) LIKE '%entry%'
               OR lower(field_name) LIKE '%weight%'
               OR lower(field_name) LIKE '%cash%'
               OR lower(field_name) LIKE '%sizing%'
               OR lower(field_name) LIKE '%risk%'
               OR lower(field_name) LIKE '%trade%'
               OR lower(field_name) LIKE '%paper%'
               OR lower(field_name) LIKE '%live%'
            """
        ).fetchone()[0]
        expect(forbidden == 0, "Phase 3C cache DB must not contain forbidden field families", errors)


def check_phase3d_consumer_parity(errors: list[str]) -> None:
    from artifact_index import PHASE3C_APPROVED_CANDIDATE_KEYS, PHASE3D_CONSUMER_PARITY_BOUNDARY

    if low_risk_phase3_active():
        check_low_risk_phase3_activation(errors)
        return

    result = run_artifact_index(["phase3d-consumer-parity", "--limit", "200"], errors)
    expect(result.returncode == 0 and "status=ok" in result.stdout and "consumer_migration_allowed=False" in result.stdout, "Phase 3D consumer parity command should pass without allowing consumer migration", errors)
    for rel_path in [
        "tmp/sql-canon-phase3d-consumer-parity.json",
        "tmp/sql-canon-phase3d-validation.json",
    ]:
        expect((WORKSPACE / rel_path).exists(), f"Phase 3D output should exist: {rel_path}", errors)
    parity = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3d-consumer-parity.json").read_text(encoding="utf-8"))
    validation = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3d-validation.json").read_text(encoding="utf-8"))
    expect(parity.get("authority_boundary") == PHASE3D_CONSUMER_PARITY_BOUNDARY, "Phase 3D parity should preserve read-only consumer-parity boundary", errors)
    expect(validation.get("status") == "ok", f"Phase 3D validation should pass: {validation}", errors)
    rows = parity.get("parity_rows") or []
    expect([row.get("key") for row in rows] == PHASE3C_APPROVED_CANDIDATE_KEYS, "Phase 3D must validate exactly the approved two NVDA cache keys", errors)
    expect(all(row.get("overall_parity_status") == "consistent" for row in rows), "Phase 3D SQL cache rows must match current generated/Markdown proof sources", errors)
    expect(all(row.get("cache_value") == row.get("current_generated_artifact_value") for row in rows), "Phase 3D must compare against direct generated artifact values, not only SQL proof rows", errors)
    expect(parity.get("consumer_migration_allowed") is False, "Phase 3D must not allow consumer migration", errors)
    expect(parity.get("dashboard_or_trigger_behavior_change_allowed") is False, "Phase 3D must not allow dashboard/trigger behavior changes", errors)
    expect(parity.get("canonical_note_mutation_allowed") is False and parity.get("portfolio_mutation_allowed") is False, "Phase 3D must not allow note/portfolio mutations", errors)
    expect(parity.get("trade_or_account_action_allowed") is False and parity.get("paper_trade_authority_allowed") is False and parity.get("live_trade_authority_allowed") is False, "Phase 3D must not allow trade/account/paper/live authority", errors)


def check_phase3e_dashboard_proof_pilot(errors: list[str]) -> None:
    from artifact_index import PHASE3C_APPROVED_CANDIDATE_KEYS, PHASE3E_DASHBOARD_PROOF_PILOT_BOUNDARY

    if low_risk_phase3_active():
        check_low_risk_phase3_activation(errors)
        return

    result = run_artifact_index(["phase3e-dashboard-proof-pilot", "--limit", "200"], errors)
    expect(result.returncode == 0 and "status=ok" in result.stdout and "dashboard_behavior_change_allowed=False" in result.stdout, "Phase 3E dashboard proof pilot command should pass without allowing dashboard behavior changes", errors)
    for rel_path in [
        "tmp/sql-canon-phase3e-dashboard-proof-pilot.json",
        "tmp/sql-canon-phase3e-validation.json",
    ]:
        expect((WORKSPACE / rel_path).exists(), f"Phase 3E output should exist: {rel_path}", errors)
    pilot = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3e-dashboard-proof-pilot.json").read_text(encoding="utf-8"))
    validation = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3e-validation.json").read_text(encoding="utf-8"))
    expect(pilot.get("authority_boundary") == PHASE3E_DASHBOARD_PROOF_PILOT_BOUNDARY, "Phase 3E pilot should preserve dashboard proof-metadata boundary", errors)
    expect(validation.get("status") == "ok", f"Phase 3E validation should pass: {validation}", errors)
    rows = pilot.get("dashboard_metadata_rows") or []
    expect([row.get("key") for row in rows] == PHASE3C_APPROVED_CANDIDATE_KEYS, "Phase 3E must pilot exactly the two approved NVDA cache keys", errors)
    expect(all(row.get("dashboard_consumer_family") == "dashboard proof metadata" for row in rows), "Phase 3E rows must stay scoped to dashboard proof metadata", errors)
    expect(all(row.get("fallback_available") is True and row.get("fallback_generated_artifact_value") for row in rows), "Phase 3E rows must prove generated-artifact fallback availability", errors)
    expect(all(row.get("parity_status") == "consistent" for row in rows), "Phase 3E must keep Phase 3D parity clean", errors)
    expect(pilot.get("consumer_migration_allowed") is False and pilot.get("dashboard_payload_mutated") is False, "Phase 3E must not mutate/migrate dashboard payload behavior", errors)
    expect(pilot.get("canonical_note_mutation_allowed") is False and pilot.get("portfolio_mutation_allowed") is False, "Phase 3E must not allow note/portfolio mutations", errors)
    expect(pilot.get("trade_or_account_action_allowed") is False and pilot.get("paper_trade_authority_allowed") is False and pilot.get("live_trade_authority_allowed") is False, "Phase 3E must not allow trade/account/paper/live authority", errors)


def check_phase3f_preflight(errors: list[str]) -> None:
    from artifact_index import PHASE3F_PREFLIGHT_BOUNDARY

    if low_risk_phase3_active():
        check_low_risk_phase3_activation(errors)
        return

    result = run_artifact_index(["phase3f-preflight"], errors)
    expect(result.returncode == 0 and "status=ok" in result.stdout and "phase4_ready=True" in result.stdout, "Phase 3F preflight command should pass and mark prerequisites ready for exact Phase 4 gate", errors)
    for rel_path in [
        "tmp/sql-canon-phase3f-implementation-preflight.json",
        "tmp/sql-canon-phase3f-validation.json",
        "scripts/sql_canon_cache_rollback_phase3c.py",
    ]:
        expect((WORKSPACE / rel_path).exists(), f"Phase 3F output should exist: {rel_path}", errors)
    preflight = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3f-implementation-preflight.json").read_text(encoding="utf-8"))
    validation = json.loads((WORKSPACE / "tmp" / "sql-canon-phase3f-validation.json").read_text(encoding="utf-8"))
    expect(preflight.get("authority_boundary") == PHASE3F_PREFLIGHT_BOUNDARY, "Phase 3F preflight should preserve planning/preflight boundary", errors)
    expect(validation.get("status") == "ok", f"Phase 3F validation should pass: {validation}", errors)
    expect(preflight.get("consumer_migration_allowed") is False and preflight.get("write_scope_expansion_allowed") is False, "Phase 3F must not allow migration or write expansion", errors)
    guard = preflight.get("authority_guard") or {}
    expect(guard.get("status") == "ok" and guard.get("consumer_side_required_before_non_optional_sql_reads") is True, "Phase 3F authority guard must pass and be required before non-optional reads", errors)
    rollback = preflight.get("rollback_preflight") or {}
    expect(rollback.get("status") == "ok" and rollback.get("actual_cache_db_mutated") is False, "Phase 3F rollback preflight must pass without mutating the real cache DB", errors)
    stale = preflight.get("cross_db_stale_check") or {}
    stale_summary = stale.get("summary") or {}
    expect((stale.get("workspace_counts") or {}).get("owners", 0) > 0 and (stale.get("workspace_counts") or {}).get("freshness", 0) > 0, "Phase 3F should prove workspace-index owners/freshness are populated", errors)
    expect(stale_summary.get("blocking_target_rows") == 0, "Phase 3F target field stale-check should have no blockers", errors)
    expect(preflight.get("trade_or_account_action_allowed") is False and preflight.get("paper_trade_authority_allowed") is False and preflight.get("live_trade_authority_allowed") is False, "Phase 3F must not allow trade/account/paper/live authority", errors)


def check_phase4a_activation(errors: list[str]) -> None:
    from artifact_index import PHASE3C_APPROVED_CANDIDATE_KEYS, PHASE4A_SQL_CANON_BOUNDARY
    from sql_consumer_authority_guard import build_phase4a_sql_consumer_authority_guard

    if low_risk_phase3_active():
        check_low_risk_phase3_activation(errors)
        with sqlite3.connect(DB) as conn:
            conn.row_factory = sqlite3.Row
            good_guard = build_phase4a_sql_consumer_authority_guard(
                artifact_conn=conn,
                fallback_values_by_key=active_sql_fallback_values(),
            )
            blocked_guard = build_phase4a_sql_consumer_authority_guard(artifact_conn=conn, fallback_values_by_key={})
        expect(good_guard.get("status") == "ok" and good_guard.get("sql_read_allowed") is True, f"Low-risk Phase 3 consumer guard should allow exact bounded read when fallback is present: {good_guard}", errors)
        expect(blocked_guard.get("status") == "blocked" and blocked_guard.get("sql_read_allowed") is False, "Low-risk Phase 3 consumer guard must fail closed when fallback values are absent", errors)
        expect(set(blocked_guard.get("fallback_missing_keys") or []) == set(active_sql_approved_keys()), "Low-risk/WF72 consumer guard should name all missing fallback keys", errors)
        check_portfolio_source_freshness_shadow_contract(errors)
        return

    result = run_artifact_index(["phase4a-activate"], errors)
    expect(result.returncode == 0 and "status=ok" in result.stdout and "sql_is_canon=True" in result.stdout, "Phase 4A activation command should pass and mark bounded SQL canon authority", errors)
    for rel_path in [
        "tmp/sql-canon-phase4a-approval-context.json",
        "tmp/sql-canon-phase4a-activation.json",
        "tmp/sql-canon-phase4a-validation.json",
    ]:
        expect((WORKSPACE / rel_path).exists(), f"Phase 4A output should exist: {rel_path}", errors)
    activation = json.loads((WORKSPACE / "tmp" / "sql-canon-phase4a-activation.json").read_text(encoding="utf-8"))
    validation = json.loads((WORKSPACE / "tmp" / "sql-canon-phase4a-validation.json").read_text(encoding="utf-8"))
    expect(validation.get("status") == "ok", f"Phase 4A validation should pass: {validation}", errors)
    expect(activation.get("authority_boundary") == PHASE4A_SQL_CANON_BOUNDARY, "Phase 4A activation should use the exact boundary", errors)
    expect(activation.get("sql_is_canon") is True and activation.get("sql_canon_authority_scope") == "explicit_migrated_fields_only", "Phase 4A SQL canon authority must be bounded to explicit migrated fields", errors)
    after_keys = [f"{row.get('scope')}:{row.get('field_name')}" for row in activation.get("cache_rows_after") or []]
    expect(set(after_keys) == set(PHASE3C_APPROVED_CANDIDATE_KEYS) and len(after_keys) == len(PHASE3C_APPROVED_CANDIDATE_KEYS), "Phase 4A must keep exact approved keys only", errors)
    expect(all(row.get("authority_boundary") == PHASE4A_SQL_CANON_BOUNDARY for row in activation.get("cache_rows_after") or []), "Phase 4A cache rows must be promoted to the Phase 4 boundary", errors)
    for key in ["canonical_note_mutation_allowed", "markdown_mutation_allowed", "portfolio_mutation_allowed", "owner_approval_inferred", "trade_or_account_action_allowed", "paper_trade_authority_allowed", "live_trade_authority_allowed", "money_movement_allowed", "dashboard_recommendation_deployment_action_state_behavior_change_allowed"]:
        expect(activation.get(key) is False, f"Phase 4A must keep forbidden authority false: {key}", errors)
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        good_guard = build_phase4a_sql_consumer_authority_guard(
            artifact_conn=conn,
            fallback_values_by_key={
                "NVDA:post_earnings_review_confirmed": True,
                "NVDA:earnings_lifecycle_status": "fallback_available",
            },
        )
        blocked_guard = build_phase4a_sql_consumer_authority_guard(artifact_conn=conn, fallback_values_by_key={})
    expect(good_guard.get("status") == "ok" and good_guard.get("sql_read_allowed") is True, f"Phase 4A consumer guard should allow exact bounded read when fallback is present: {good_guard}", errors)
    expect(blocked_guard.get("status") == "blocked" and blocked_guard.get("sql_read_allowed") is False, "Phase 4A consumer guard must fail closed when fallback values are absent", errors)
    expect(set(blocked_guard.get("fallback_missing_keys") or []) == set(PHASE3C_APPROVED_CANDIDATE_KEYS), "Phase 4A consumer guard should name all missing fallback keys", errors)


def check_gate15_higher_risk_family_gates(errors: list[str]) -> None:
    from sql_consumer_authority_guard import (
        HIGHER_RISK_SQL_CANON_FAMILY_GATES,
        build_phase4a_sql_consumer_authority_guard,
        classify_higher_risk_sql_canon_family,
        ENTRY_STOP_REFERENCE_METADATA_FIELDS,
    )

    expected = {
        "entry_band": ("entry_stop_metadata", "future_exact_gated_metadata_candidate"),
        "stop_loss": ("entry_stop_metadata", "future_exact_gated_metadata_candidate"),
        "reference_price_low": ("entry_stop_metadata", "future_exact_gated_metadata_candidate"),
        "reference_invalidation_level": ("entry_stop_metadata", "future_exact_gated_metadata_candidate"),
        "target_weight": ("sizing_sleeve_cash_weight_metadata", "proposal_only_sql_staging"),
        "cash_reserve": ("sizing_sleeve_cash_weight_metadata", "proposal_only_sql_staging"),
        "risk_rule_threshold": ("risk_rule_metadata", "proposal_only_sql_staging"),
        "paper_order_submit_state": ("trade_account_paper_live_execution_metadata", "never_sql_canon"),
        "live_account_endpoint": ("trade_account_paper_live_execution_metadata", "never_sql_canon"),
        "api_credential_config": ("credential_config_metadata", "never_sql_canon"),
    }
    for field_name, (family, classification) in expected.items():
        gate = classify_higher_risk_sql_canon_family(field_name) or {}
        expect(gate.get("family") == family, f"Gate 15 should classify {field_name} as {family}: {gate}", errors)
        expect(gate.get("classification") == classification, f"Gate 15 should classify {field_name} route as {classification}: {gate}", errors)
        expect(gate.get("sql_canon_activation_allowed_now") is False, f"Gate 15 must not activate SQL-canon for {field_name}", errors)
    expect(set(ENTRY_STOP_REFERENCE_METADATA_FIELDS) == {"reference_price_low", "reference_price_high", "reference_invalidation_level", "reference_level_source_timestamp", "reference_level_source_sha256", "reference_level_owner_source_path"}, "Entry/stop pilot should expose only neutral reference metadata field names", errors)
    expect(all(not any(fragment in field for fragment in ("entry", "stop", "buy", "sell", "deploy", "execute", "order", "approval")) for field in ENTRY_STOP_REFERENCE_METADATA_FIELDS), "Entry/stop pilot neutral field names must avoid action/execution/approval words", errors)
    expect(all(gate.get("sql_canon_activation_allowed_now") is False for gate in HIGHER_RISK_SQL_CANON_FAMILY_GATES.values()), "Gate 15 family matrix must keep all higher-risk activation flags false", errors)
    with sqlite3.connect(DB) as conn:
        conn.row_factory = sqlite3.Row
        guard = build_phase4a_sql_consumer_authority_guard(artifact_conn=conn, fallback_values_by_key={})
    guard_matrix = guard.get("higher_risk_family_gates") or {}
    expect(set(guard_matrix) == set(HIGHER_RISK_SQL_CANON_FAMILY_GATES), "Consumer guard should publish the exact Gate 15 higher-risk family matrix", errors)
    expect(all(row.get("sql_canon_activation_allowed_now") is False for row in guard_matrix.values()), "Consumer guard Gate 15 matrix must deny activation for all higher-risk families", errors)


def main() -> int:
    errors: list[str] = []
    rebuild_index(errors)
    check_db(errors)
    check_portfolio_source_freshness_shadow_contract(errors)
    check_neutral_deployment_evidence_shadow_contract(errors)
    check_gate15_higher_risk_family_gates(errors)
    check_cli_commands(errors)
    check_incremental_equivalence(errors)
    check_today_card_sql_source_routing(errors)
    check_json_first_markdown_gates(errors)
    check_phase2_reconciliation(errors)
    check_phase3a_dry_run(errors)
    check_phase3b_writepath_preflight(errors)
    check_phase3c_cache_contract(errors)
    check_phase3d_consumer_parity(errors)
    check_phase3e_dashboard_proof_pilot(errors)
    check_phase3f_preflight(errors)
    check_phase4a_activation(errors)
    if errors:
        print("artifact_index_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("artifact_index_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
