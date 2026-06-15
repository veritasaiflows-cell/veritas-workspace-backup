#!/usr/bin/env python3
"""Targeted WF68 Phase 0 validator behavior checks."""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

from intraday_alert_packet_validator import ROOT, validate_packet

FIXTURE = ROOT / "tmp" / "intraday-alerts" / "forced-alert-fixture.etn.json"
SCHEMA = ROOT / "tmp" / "intraday-alerts" / "alert-packet.schema.json"


def _validate(packet: dict) -> dict:
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "packet.json"
        path.write_text(json.dumps(packet), encoding="utf-8")
        return validate_packet(packet, path, SCHEMA)


def main() -> int:
    valid = json.loads(FIXTURE.read_text(encoding="utf-8"))
    valid_result = _validate(valid)
    assert valid_result["status"] == "ok", valid_result

    missing_freshness = copy.deepcopy(valid)
    del missing_freshness["source"]["freshness"]
    result = _validate(missing_freshness)
    assert result["status"] == "error", result
    assert "missing_source_freshness" in result["errors"], result

    missing_owner_surface = copy.deepcopy(valid)
    missing_owner_surface["owner_surfaces"] = []
    result = _validate(missing_owner_surface)
    assert result["status"] == "error", result
    assert "missing_owner_surface_reference" in result["errors"], result

    missing_authority = copy.deepcopy(valid)
    del missing_authority["authority"]
    result = _validate(missing_authority)
    assert result["status"] == "error", result
    assert "missing_authority_block" in result["errors"], result

    stale_packet = copy.deepcopy(valid)
    stale_packet["source"]["freshness"]["status"] = "stale"
    stale_packet["source"]["freshness"]["age_seconds"] = 3601
    result = _validate(stale_packet)
    assert result["status"] == "error", result
    assert any(err.startswith("source_not_alert_fresh:stale") for err in result["errors"]), result
    assert "freshness_age_exceeds_stale_after" in result["errors"], result

    ambiguous_packet = copy.deepcopy(valid)
    ambiguous_packet["source"]["freshness"]["ambiguity_state"] = "ambiguous"
    result = _validate(ambiguous_packet)
    assert result["status"] == "error", result
    assert any(err.startswith("source_ambiguous_or_unknown:ambiguous") for err in result["errors"]), result

    true_authority = copy.deepcopy(valid)
    true_authority["authority"]["paper_trade_allowed"] = True
    result = _validate(true_authority)
    assert result["status"] == "error", result
    assert "authority_flag_not_false:paper_trade_allowed" in result["errors"], result
    assert any(err.endswith("paper_trade_allowed") for err in result["errors"]), result

    print("intraday_alert_packet_validator targeted tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
