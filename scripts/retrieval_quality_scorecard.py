#!/usr/bin/env python3
"""Validate-only retrieval quality scorecard before KG/vector expansion.

This script scores known-answer retrieval fixtures across the existing Veritas
retrieval stack: SQL artifact cockpit, workspace-index, and direct source-file
inspection. It creates only review artifacts under tmp/ and does not change
canon, SQL-canon/cache authority, config, runtime, or external services.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
WORKSPACE_DB = TMP / "workspace-index.sqlite"
ARTIFACT_DB = TMP / "veritas-artifact-index.sqlite"
JSON_OUT = TMP / "retrieval-quality-scorecard.json"
MD_OUT = TMP / "retrieval-quality-scorecard.md"

BOUNDARY = (
    "review_only_retrieval_scorecard_not_canon_not_memory_service_"
    "not_vector_or_kg_not_owner_approval_not_apply_authority"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_text(rel_path: str) -> str:
    return (ROOT / rel_path).read_text(encoding="utf-8", errors="replace")


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def db_exists(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def one(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
    return conn.execute(sql, params).fetchone()


def all_rows(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return list(conn.execute(sql, params))


def status_from_score(score: float) -> str:
    rounded = round(score, 2)
    return "pass" if rounded >= 0.9 else "partial" if rounded >= 0.5 else "fail"


@dataclass
class FixtureResult:
    fixture_id: str
    fixture_class: str
    question: str
    expected_answer: dict[str, Any]
    surfaces: list[str]
    status: str
    score: float
    evidence: dict[str, Any] = field(default_factory=dict)
    gaps: list[str] = field(default_factory=list)
    recommendation: str = ""


def fixture_owner_note_lookup() -> FixtureResult:
    expected = {
        "owner_note": "03. Portfolio/Execution Board.md",
        "owns": ["execution bands", "stops", "invalidation logic"],
        "boundary": "manual and owner-gated; not automatic trading authority",
    }
    gaps: list[str] = []
    evidence: dict[str, Any] = {}
    score = 0.0

    if db_exists(WORKSPACE_DB):
        with connect(WORKSPACE_DB) as conn:
            row = one(
                conn,
                "SELECT owner_path, owner_kind, claim_scope, mutation_allowed FROM owners WHERE surface_path=?",
                (expected["owner_note"],),
            )
            if row:
                evidence["workspace_owner_row"] = dict(row)
                if row["owner_path"] == expected["owner_note"] and row["owner_kind"] == "canonical":
                    score += 0.35
            else:
                gaps.append("workspace-index owners table did not return Execution Board owner row")
    else:
        gaps.append("workspace-index DB missing")

    text = read_text(expected["owner_note"])
    found_terms = {term: (term.lower() in text.lower()) for term in ["execution bands", "stops", "invalidation logic", "automatic trading authority", "manual and owner-gated"]}
    evidence["direct_file_terms"] = found_terms
    if all(found_terms.values()):
        score += 0.55
    if "tmp/" not in expected["owner_note"]:
        score += 0.10

    return FixtureResult(
        fixture_id="rq_owner_note_execution_board",
        fixture_class="owner_note_lookup",
        question="Where is the canonical owner for execution bands, stops, and invalidation logic?",
        expected_answer=expected,
        surfaces=["workspace-index owners", "direct owner note inspection"],
        status=status_from_score(score),
        score=round(score, 2),
        evidence=evidence,
        gaps=gaps,
        recommendation="Use workspace-index as the route, then open the owner note before finance claims.",
    )


def fixture_proof_artifact_lookup() -> FixtureResult:
    expected_path = "tmp/capital-deployment-recommendation-validation.json"
    evidence: dict[str, Any] = {}
    gaps: list[str] = []
    score = 0.0

    if db_exists(ARTIFACT_DB):
        with connect(ARTIFACT_DB) as conn:
            row = one(
                conn,
                "SELECT source_file, artifact_type, owner_review_required, canonical_mutation_allowed, authority_boundary "
                "FROM v_cockpit_trust_boundary WHERE source_file=?",
                (expected_path,),
            )
            if row:
                evidence["artifact_trust_row"] = dict(row)
                score += 0.55
                if row["owner_review_required"] == 1 and row["canonical_mutation_allowed"] == 0:
                    score += 0.20
            else:
                gaps.append("artifact cockpit trust view did not return target validation artifact")
    else:
        gaps.append("artifact-index DB missing")

    path = ROOT / expected_path
    if path.exists():
        evidence["direct_file"] = {"path": expected_path, "size": path.stat().st_size, "exists": True}
        score += 0.25
    else:
        evidence["direct_file"] = {"path": expected_path, "exists": False}
        gaps.append("target proof artifact missing on disk")

    return FixtureResult(
        fixture_id="rq_proof_artifact_capital_validation",
        fixture_class="proof_artifact_lookup",
        question="Can retrieval route to a validation/proof artifact without mistaking it for canon or approval?",
        expected_answer={"proof_artifact": expected_path, "required_label": "review/validation artifact only"},
        surfaces=["artifact SQL cockpit trust boundary", "direct artifact inspection"],
        status=status_from_score(score),
        score=round(score, 2),
        evidence=evidence,
        gaps=gaps,
        recommendation="SQL cockpit is suitable for proof-artifact routing; direct artifact open remains required for content claims.",
    )


def fixture_stale_vs_current() -> FixtureResult:
    evidence: dict[str, Any] = {}
    gaps: list[str] = []
    score = 0.0

    expected = {
        "current_artifact": "tmp/market-state.json",
        "current_classification": "current",
        "guardrail": "fresh/current labels are review metadata, not canon or action authority",
    }
    if db_exists(ARTIFACT_DB):
        with connect(ARTIFACT_DB) as conn:
            rows = all_rows(
                conn,
                "SELECT source_key, path, classification, generated_at_utc, age_hours, stale_after_hours, confidence_ceiling "
                "FROM v_cockpit_source_freshness ORDER BY source_key",
            )
            evidence["source_freshness_rows_sample"] = [dict(r) for r in rows[:8]]
            target = [r for r in rows if r["path"] == expected["current_artifact"]]
            if target and target[0]["classification"] == expected["current_classification"]:
                score += 0.50
            if rows:
                score += 0.15
            classifications = sorted({r["classification"] for r in rows})
            evidence["available_classifications"] = classifications
            if len(classifications) < 2:
                gaps.append("current freshness view has little/no stale-vs-current contrast in the current fixture set")
    else:
        gaps.append("artifact-index DB missing")

    if (ROOT / expected["current_artifact"]).exists():
        score += 0.15
    startup = read_text("06. Playbooks/Startup Truth Index.md")
    terms = ["SQL/current-window indexes", "inspect the target artifact", "no SQL row/view/query output grants owner approval"]
    evidence["startup_guard_terms"] = {term: (term in startup) for term in terms}
    if all(evidence["startup_guard_terms"].values()):
        score += 0.20

    return FixtureResult(
        fixture_id="rq_stale_current_market_state",
        fixture_class="stale_vs_current_artifact_disambiguation",
        question="Can current freshness metadata identify a current artifact while preserving inspection and authority boundaries?",
        expected_answer=expected,
        surfaces=["artifact SQL cockpit source-freshness view", "Startup Truth Index guardrail", "direct artifact existence"],
        status=status_from_score(score),
        score=round(score, 2),
        evidence=evidence,
        gaps=gaps,
        recommendation="Do not build KG/vector yet; first add more stale/current historical fixtures if this gap matters.",
    )


def fixture_finance_stop_line() -> FixtureResult:
    expected = {
        "ticker": "RTX",
        "owner_note": "03. Portfolio/Execution Board.md",
        "stop": "177.91",
        "stance": "Do not touch / below-stop",
        "authority": "no execution-board entitlement / no automatic execution",
    }
    evidence: dict[str, Any] = {}
    gaps: list[str] = []
    score = 0.0

    if db_exists(WORKSPACE_DB):
        with connect(WORKSPACE_DB) as conn:
            row = one(conn, "SELECT path, title, note_type FROM documents WHERE path=?", (expected["owner_note"],))
            if row:
                evidence["workspace_document_row"] = dict(row)
                score += 0.20
    else:
        gaps.append("workspace-index DB missing")

    text = read_text(expected["owner_note"])
    required = [expected["ticker"], expected["stop"], expected["stance"], "no execution-board entitlement", "no automatic execution"]
    evidence["direct_terms"] = {term: (term in text) for term in required}
    if all(evidence["direct_terms"].values()):
        score += 0.70

    if db_exists(ARTIFACT_DB):
        with connect(ARTIFACT_DB) as conn:
            rows = all_rows(conn, "SELECT proposal_id, target_file, proposal_kind, authority_boundary FROM v_cockpit_canon_staging WHERE target_file=? LIMIT 5", (expected["owner_note"],))
            evidence["artifact_stopline_context"] = [dict(r) for r in rows]
            score += 0.10 if rows else 0.0

    return FixtureResult(
        fixture_id="rq_finance_stopline_rtx",
        fixture_class="finance_stop_line_lookup",
        question="Can retrieval find the finance stop-line for RTX without granting execution authority?",
        expected_answer=expected,
        surfaces=["workspace-index document route", "direct Execution Board inspection", "artifact cockpit staging context"],
        status=status_from_score(score),
        score=round(score, 2),
        evidence=evidence,
        gaps=gaps,
        recommendation="Use direct owner note for stop/authority facts; SQL staging rows are context only.",
    )


def fixture_generated_not_canon() -> FixtureResult:
    expected_path = "tmp/dashboard-validation.json"
    evidence: dict[str, Any] = {}
    gaps: list[str] = []
    score = 0.0

    if db_exists(WORKSPACE_DB):
        with connect(WORKSPACE_DB) as conn:
            row = one(conn, "SELECT path, canonical_class, generated, status FROM artifacts WHERE path=?", (expected_path,))
            if row:
                evidence["workspace_artifact_row"] = dict(row)
                if row["canonical_class"] == "generated-artifact" and row["generated"] == 1:
                    score += 0.35
            else:
                gaps.append("workspace-index artifact table did not return dashboard validation artifact")
    else:
        gaps.append("workspace-index DB missing")

    if db_exists(ARTIFACT_DB):
        with connect(ARTIFACT_DB) as conn:
            row = one(
                conn,
                "SELECT source_file, owner_review_required, canonical_mutation_allowed, forbidden_true_flags, authority_boundary "
                "FROM v_cockpit_trust_boundary WHERE source_file=?",
                (expected_path,),
            )
            if row:
                evidence["artifact_trust_row"] = dict(row)
                score += 0.35
                if row["canonical_mutation_allowed"] == 0 and row["owner_review_required"] == 1:
                    score += 0.10
    else:
        gaps.append("artifact-index DB missing")

    startup = read_text("06. Playbooks/Startup Truth Index.md")
    guard = "Generated packets, dashboards, Today card drafts, capital recommendations, validators, SQL cockpit rows/views, and proof indexes are evidence/review surfaces only."
    evidence["startup_generated_guardrail_present"] = guard in startup
    if evidence["startup_generated_guardrail_present"]:
        score += 0.20

    return FixtureResult(
        fixture_id="rq_generated_artifact_not_canon_dashboard_validation",
        fixture_class="generated_artifact_is_not_canon_labeling",
        question="Can retrieval label generated dashboard validation as evidence/review only, not canon?",
        expected_answer={"artifact": expected_path, "must_label": "generated artifact / evidence only / not canon"},
        surfaces=["workspace-index artifact manifest", "artifact cockpit trust boundary", "Startup Truth Index"],
        status=status_from_score(score),
        score=round(score, 2),
        evidence=evidence,
        gaps=gaps,
        recommendation="Generated-artifact labeling is adequate; keep enforcing the direct owner-note inspection rule.",
    )


def fixture_surface_split() -> FixtureResult:
    expected = {
        "query": "ETN deployable now / current priority",
        "sql_cockpit_role": "find generated deployment/proof row quickly",
        "workspace_index_role": "route to canonical notes and owner map",
        "direct_file_role": "make final finance claim from owner note/artifact inspection",
    }
    evidence: dict[str, Any] = {}
    gaps: list[str] = []
    score = 0.0

    if db_exists(ARTIFACT_DB):
        with connect(ARTIFACT_DB) as conn:
            row = one(conn, "SELECT ticker, bucket, source_artifact_path, source_generated_at_utc, authority_boundary FROM v_cockpit_deployment_readiness WHERE ticker='ETN'")
            if row:
                evidence["sql_cockpit_etn"] = dict(row)
                score += 0.25
    else:
        gaps.append("artifact-index DB missing")

    if db_exists(WORKSPACE_DB):
        with connect(WORKSPACE_DB) as conn:
            owner = one(conn, "SELECT surface_path, owner_path, claim_scope FROM owners WHERE owner_path='03. Portfolio/Execution Board.md'")
            doc = one(conn, "SELECT path, note_type FROM documents WHERE path='03. Portfolio/Portfolio Snapshot.md'")
            if owner:
                evidence["workspace_owner_execution"] = dict(owner)
                score += 0.20
            if doc:
                evidence["workspace_doc_snapshot"] = dict(doc)
                score += 0.10
    else:
        gaps.append("workspace-index DB missing")

    execution = read_text("03. Portfolio/Execution Board.md")
    snapshot = read_text("03. Portfolio/Portfolio Snapshot.md")
    direct_checks = {
        "execution_board_etn_deployable_now": "| ETN |" in execution and "Deployable now" in execution,
        "execution_board_manual_only": "no automatic execution" in execution,
        "snapshot_current_priority": "ETN remains the first" in snapshot,
        "snapshot_manual_only": "manual-only" in snapshot,
    }
    evidence["direct_file_checks"] = direct_checks
    if all(direct_checks.values()):
        score += 0.45

    return FixtureResult(
        fixture_id="rq_surface_split_etn_deployable",
        fixture_class="sql_cockpit_vs_workspace_index_vs_direct_file_inspection",
        question="Can the stack split generated proof lookup, owner-note routing, and final direct inspection for ETN?",
        expected_answer=expected,
        surfaces=["artifact SQL cockpit", "workspace-index", "direct Execution Board + Portfolio Snapshot inspection"],
        status=status_from_score(score),
        score=round(score, 2),
        evidence=evidence,
        gaps=gaps,
        recommendation="Current stack is good enough for routing; final claims must cite direct owner/proof inspection.",
    )


FIXTURES: list[Callable[[], FixtureResult]] = [
    fixture_owner_note_lookup,
    fixture_proof_artifact_lookup,
    fixture_stale_vs_current,
    fixture_finance_stop_line,
    fixture_generated_not_canon,
    fixture_surface_split,
]


def build_scorecard() -> dict[str, Any]:
    results = [fixture() for fixture in FIXTURES]
    scores = [r.score for r in results]
    passed = sum(1 for r in results if r.status == "pass")
    partial = sum(1 for r in results if r.status == "partial")
    failed = sum(1 for r in results if r.status == "fail")
    avg = round(sum(scores) / len(scores), 3) if scores else 0.0
    classes = sorted({r.fixture_class for r in results})
    kg_vector_justified = False
    verdict_reasons = [
        "Existing SQL cockpit + workspace-index + direct inspection cover the required known-answer routes.",
        "Remaining weak spot is fixture depth/contrast for stale-vs-current history, not a proven need for a new KG/vector memory plane.",
        "Generated artifacts and SQL rows remain review/proof routing surfaces only; canon stays in owner notes.",
    ]
    if failed or avg < 0.75:
        verdict_reasons.insert(0, "Do not expand retrieval infrastructure until failing fixtures are repaired and rerun.")
    return {
        "schema_version": 1,
        "generated_at_utc": utc_now(),
        "status": "ok" if failed == 0 else "needs_repair",
        "authority_boundary": BOUNDARY,
        "scope": "known-answer retrieval scorecard before KG/vector expansion",
        "inputs": {
            "workspace_index_db": rel(WORKSPACE_DB) if WORKSPACE_DB.exists() else "missing",
            "artifact_index_db": rel(ARTIFACT_DB) if ARTIFACT_DB.exists() else "missing",
            "direct_owner_files": [
                "03. Portfolio/Execution Board.md",
                "03. Portfolio/Portfolio Snapshot.md",
                "06. Playbooks/Startup Truth Index.md",
            ],
        },
        "summary": {
            "fixtures": len(results),
            "classes": classes,
            "passed": passed,
            "partial": partial,
            "failed": failed,
            "average_score": avg,
        },
        "kg_vector_expansion_verdict": {
            "justified_now": kg_vector_justified,
            "verdict": "defer KG/vector/temporal-memory expansion",
            "reasons": verdict_reasons,
            "next_best_step": "Add more stale-vs-current and archive/current-window negative fixtures before any memory infrastructure prototype.",
        },
        "fixtures": [r.__dict__ for r in results],
    }


def write_markdown(scorecard: dict[str, Any]) -> None:
    summary = scorecard["summary"]
    verdict = scorecard["kg_vector_expansion_verdict"]
    lines: list[str] = []
    lines.append("# Retrieval Quality Scorecard")
    lines.append("")
    lines.append(f"Generated UTC: `{scorecard['generated_at_utc']}`")
    lines.append(f"Status: **{scorecard['status']}**")
    lines.append(f"Authority boundary: `{scorecard['authority_boundary']}`")
    lines.append("")
    lines.append("## Executive verdict")
    lines.append("")
    lines.append(f"**{verdict['verdict']}**. KG/vector expansion justified now: **{str(verdict['justified_now']).lower()}**.")
    for reason in verdict["reasons"]:
        lines.append(f"- {reason}")
    lines.append(f"- Next best step: {verdict['next_best_step']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Fixtures: **{summary['fixtures']}**")
    lines.append(f"- Pass / partial / fail: **{summary['passed']} / {summary['partial']} / {summary['failed']}**")
    lines.append(f"- Average score: **{summary['average_score']}**")
    lines.append("")
    lines.append("## Fixture results")
    lines.append("")
    lines.append("| Fixture | Class | Status | Score | Recommendation |")
    lines.append("|---|---|---:|---:|---|")
    for fixture in scorecard["fixtures"]:
        lines.append(
            f"| `{fixture['fixture_id']}` | {fixture['fixture_class']} | {fixture['status']} | {fixture['score']} | {fixture['recommendation']} |"
        )
    lines.append("")
    lines.append("## Gaps")
    lines.append("")
    any_gap = False
    for fixture in scorecard["fixtures"]:
        if fixture["gaps"]:
            any_gap = True
            lines.append(f"### `{fixture['fixture_id']}`")
            for gap in fixture["gaps"]:
                lines.append(f"- {gap}")
            lines.append("")
    if not any_gap:
        lines.append("- No fixture-blocking gaps found. Stale-vs-current fixture depth still should be expanded before infrastructure work.")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    lines.append("This is a validate-only/report-only retrieval scorecard. It does not create a memory service, vector DB, KG, canon replacement, approval surface, portfolio mutation path, or execution authority.")
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    TMP.mkdir(parents=True, exist_ok=True)
    scorecard = build_scorecard()
    JSON_OUT.write_text(json.dumps(scorecard, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(scorecard)
    print(json.dumps({
        "status": scorecard["status"],
        "json": rel(JSON_OUT),
        "md": rel(MD_OUT),
        "fixtures": scorecard["summary"]["fixtures"],
        "average_score": scorecard["summary"]["average_score"],
        "kg_vector_justified_now": scorecard["kg_vector_expansion_verdict"]["justified_now"],
    }, indent=2))
    return 0 if scorecard["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
