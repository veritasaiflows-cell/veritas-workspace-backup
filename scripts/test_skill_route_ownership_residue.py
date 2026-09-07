#!/usr/bin/env python3
"""Regression checks for active skill-routing and ownership documentation."""
from __future__ import annotations

from pathlib import Path

import pm_implementation_job_queue as pm_queue
import wf74_autonomy_work_router as wf74_router


ROOT = Path(__file__).resolve().parents[1]
PROCEDURE_MAP = ROOT / "06. Playbooks" / "Operating Procedures" / "Skill-to-Procedure Ownership Map.md"
GOVERNANCE_INDEX = ROOT / "06. Playbooks" / "Skills Governance Index.md"
HISTORICAL_MATRIX = ROOT / "08. Audits" / "Skill Consolidation Matrix - 2026-07-02.md"


def main() -> int:
    assert pm_queue.DEPARTMENT_OWNER_BY_DEPARTMENT["skills_procedure"] == "workspace-governor"
    assert wf74_router.DEPARTMENT_OWNER_BY_DEPARTMENT["skills_procedure"] == "workspace-governor"

    procedure_rows = PROCEDURE_MAP.read_text(encoding="utf-8").splitlines()
    finance_alert_row = next(
        line for line in procedure_rows if "Portfolio Truth Surface Ownership Procedure.md" in line
    )
    assert "`veritas-intelligence-effort-router`" in finance_alert_row
    assert "`veritas-response-contract`" in finance_alert_row
    assert "owns user-facing recommendation and authority wording" in finance_alert_row
    assert "`veritas-portfolio-update`" not in finance_alert_row

    governance = GOVERNANCE_INDEX.read_text(encoding="utf-8")
    assert "## Active workspace skills (38 canonical + 13 retired/deprecated fallbacks)" in governance
    assert "Current canonical active workspace skill count: **38**." in governance
    assert "Retired/deprecated fallback count: **13**" in governance
    assert "`implementation-friction-closeout`" in governance

    matrix = HISTORICAL_MATRIX.read_text(encoding="utf-8")
    assert "Status: Historical baseline. Superseded as the current classification on 2026-08-31." in matrix
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
