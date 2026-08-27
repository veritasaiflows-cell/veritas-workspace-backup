from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "tier_a_cohort_alignment_reconciliation.py"

spec = importlib.util.spec_from_file_location("tier_a_cohort_alignment_reconciliation", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_build_packet_classifies_current_mismatches() -> None:
    packet = module.build_packet()
    assert packet["authority_boundary"]["finance_canon_mutation_allowed"] is False
    assert packet["authority_boundary"]["paper_or_live_execution_allowed"] is False
    assert packet["summary"]["finance_only_count"] == 6
    dispositions = packet["summary"]["disposition_counts"]
    assert dispositions["proxy_exception_not_decision_grade"] == 5
    assert dispositions["durable_finance_canon_route_drift"] == 1
    assert packet["summary"]["durable_sync_followup_tickers"] == ["WMB"]


def test_validation_passes_for_review_only_packet() -> None:
    packet = module.build_packet()
    errors = [check for check in module.validate_packet(packet) if not check["ok"]]
    assert not errors


if __name__ == "__main__":
    test_build_packet_classifies_current_mismatches()
    test_validation_passes_for_review_only_packet()
    print("ok")
