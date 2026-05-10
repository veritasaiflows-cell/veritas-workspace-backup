from __future__ import annotations

import json
import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
REGIME_MATRIX_MD = WORKSPACE / "02. Markets" / "Regime Scoring Matrix.md"
REGIME_SCORES_JSON = WORKSPACE / "tmp" / "regime-scores.json"
SCRIPT = WORKSPACE / "scripts" / "regime_scoring_refresh.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    note = REGIME_MATRIX_MD.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    scores = json.loads(REGIME_SCORES_JSON.read_text(encoding="utf-8"))

    require("controlled machine-companion ranking note" in note, "note must declare machine-companion authority")
    require("not final canonical deployment truth" in note, "note must reject final deployment authority")
    require("Deployment Trigger Sheet" in note and "Portfolio Snapshot" in note and "Risk Rules" in note, "note must name final authority surfaces")
    require("owner approval" in note.lower(), "note must preserve owner-approval boundary")
    require("Canonical ranking source" not in note, "old canonical-ranking claim must be removed")

    authority = scores.get("authority") or {}
    require(authority.get("surface") == "controlled_machine_companion_ranking_note", "JSON authority surface mismatch")
    require(authority.get("canonical_deployment_truth") is False, "JSON must deny canonical deployment truth")
    require(authority.get("canonical_note_mutation_allowed") is True, "JSON must declare bounded note mutation allowed")
    require(authority.get("portfolio_mutation_allowed") is False, "JSON must deny portfolio mutation")
    require(authority.get("deployment_state_mutation_allowed") is False, "JSON must deny deployment-state mutation")
    require(authority.get("trade_execution_allowed") is False, "JSON must deny trade execution")
    require(authority.get("owner_approval_granted") is False, "JSON must deny owner approval inference")
    allowed = authority.get("allowed_markdown_sections") or []
    require("Current scoring" in allowed and "Priority ranking (current)" in allowed and "Freshness and refresh policy" in allowed, "allowed markdown sections incomplete")

    require("REGIME_MATRIX_AUTHORITY" in script, "script should centralize authority text")
    require(re.search(r"re\.sub\(\s*r\"- Data as of:\.\*\"", script), "script should update freshness data-as-of line")

    print("regime_scoring_authority_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
