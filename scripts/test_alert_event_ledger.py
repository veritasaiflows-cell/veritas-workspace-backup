from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import alert_event_ledger as ledger

WORKSPACE = Path(__file__).resolve().parents[1]


def row(ticker: str, relationship: str, *, alert_state: str | None = None, low: float = 100.0) -> dict:
    return {
        "ticker": ticker,
        "level_relationship_state": relationship,
        "alert_state": alert_state or relationship,
        "alert_fire_eligible": False,
        "latest_price": 101.0,
        "quote_as_of_utc": "2026-09-23T19:59:59Z",
        "quote_data_date": "2026-09-23",
        "market_session_window": "market_hours_fresh",
        "quote_freshness_status": "fresh",
        "reference_low": low,
        "reference_high": 110.0,
        "invalidation_threshold": 95.0,
        "level_as_of_utc": "2026-09-17T01:22:10Z",
        "source_path": "state/finance/baselines/pin.json",
        "sql_reference": {"reference_confidence": None},
    }


def controller(*rows: dict) -> dict:
    return {"generated_at_utc": "2026-09-23T20:00:00Z", "rows": list(rows)}


def seed_context(root: Path) -> None:
    (root / "tmp").mkdir(parents=True, exist_ok=True)
    (root / "tmp/macro-signal-spine.json").write_text(json.dumps(
        {"as_of_date": "2026-09-23", "summary": {"macro_posture": "defensive_review_bias"}}), encoding="utf-8")
    (root / "tmp/earnings-calendar.json").write_text(json.dumps(
        {"records": [{"ticker": "AAA", "next_earnings_date": "2026-10-30"}]}), encoding="utf-8")


def append(root: Path, ctl: dict, run_id: str) -> dict:
    return ledger.append_events(ctl, {"run_id": run_id, "recurring_window": "midday"}, root=root)


def paths(root: Path) -> tuple[Path, Path]:
    return root / ledger.LEDGER_REL, root / ledger.HEAD_REL


@pytest.fixture
def root(tmp_path: Path) -> Path:
    seed_context(tmp_path)
    return tmp_path


def test_edge_triggering_appends_only_transitions(root: Path) -> None:
    first = append(root, controller(row("AAA", "band_entry"), row("BBB", "no_chase")), "r1")
    assert first["appended"] == 3  # genesis + two state snapshots
    same = append(root, controller(row("AAA", "band_entry"), row("BBB", "no_chase")), "r2")
    assert same["appended"] == 0
    # Session close flips alert_state to monitor_only but geometry is unchanged: no event.
    closed = append(root, controller(row("AAA", "band_entry", alert_state="monitor_only"),
                                     row("BBB", "no_chase", alert_state="monitor_only")), "r3")
    assert closed["appended"] == 0
    moved = append(root, controller(row("AAA", "invalidation_alert"), row("BBB", "no_chase")), "r4")
    assert moved["appended"] == 1
    records = ledger.read_records(paths(root)[0])
    assert records[-1]["payload"]["event"] == "invalidation_breached"
    assert records[-1]["payload"]["prior_relationship"] == "band_entry"
    recovered = append(root, controller(row("AAA", "band_entry"), row("BBB", "no_chase")), "r5")
    assert recovered["appended"] == 1
    assert ledger.read_records(paths(root)[0])[-1]["payload"]["event"] == "invalidation_recovered"


def test_levels_change_and_data_quality_events(root: Path) -> None:
    append(root, controller(row("AAA", "band_entry")), "r1")
    assert append(root, controller(row("AAA", "band_entry", low=99.0)), "r2")["appended"] == 1
    assert ledger.read_records(paths(root)[0])[-1]["payload"]["event"] == "levels_changed"
    append(root, controller(row("AAA", "band_entry", alert_state="freshness_decay", low=99.0)), "r3")
    last = ledger.read_records(paths(root)[0])[-1]["payload"]
    assert last["event"] == "freshness_decay_entered" and last["event_class"] == "data_quality"


def test_context_recorded_without_invention(root: Path) -> None:
    append(root, controller(row("AAA", "band_entry"), row("BBB", "band_entry")), "r1")
    by_ticker = {r["payload"]["ticker"]: r["payload"]
                 for r in ledger.read_records(paths(root)[0]) if r["record_type"] == "alert_event"}
    assert by_ticker["AAA"]["macro_posture"] == "defensive_review_bias"
    assert by_ticker["AAA"]["days_to_earnings"] == 37
    assert by_ticker["BBB"]["next_earnings_date"] is None and by_ticker["BBB"]["days_to_earnings"] is None
    assert by_ticker["AAA"]["thesis_version"] is None
    assert by_ticker["AAA"]["band_methodology_version"] == ledger.BAND_METHODOLOGY_VERSION


def test_idempotent_replay(root: Path) -> None:
    append(root, controller(row("AAA", "band_entry")), "r1")
    append(root, controller(row("AAA", "no_chase")), "r2")
    before = paths(root)[0].read_bytes()
    assert append(root, controller(row("AAA", "no_chase")), "r2")["status"] == "ok_duplicate_run"
    assert paths(root)[0].read_bytes() == before


def test_chain_verifies_and_detects_tampering(root: Path) -> None:
    append(root, controller(row("AAA", "band_entry"), row("BBB", "no_chase")), "r1")
    append(root, controller(row("AAA", "no_chase"), row("BBB", "band_entry")), "r2")
    led, head = paths(root)
    assert ledger.verify(led, head)["status"] == "ok"
    lines = led.read_text(encoding="utf-8").splitlines()

    def check(mutated: list[str]) -> dict:
        target = root / "tampered.jsonl"
        target.write_text("\n".join(mutated) + "\n", encoding="utf-8")
        return ledger.verify(target)

    payload_edit = json.loads(lines[1]); payload_edit["payload"]["price"] = 1.0
    assert check([lines[0], json.dumps(payload_edit), *lines[2:]])["status"] == "error"
    env_edit = json.loads(lines[2]); env_edit["recorded_at_utc"] = "2020-01-01T00:00:00Z"
    assert check([*lines[:2], json.dumps(env_edit), *lines[3:]])["status"] == "error"
    assert check([lines[0], *lines[2:]])["status"] == "error"  # deletion
    assert check([lines[0], lines[2], lines[1], *lines[3:]])["status"] == "error"  # reorder
    assert check(lines[:-1])["status"] == "ok"  # truncation alone is a valid prefix...
    assert ledger.verify(root / "tampered.jsonl", head)["status"] == "error"  # ...but the head catches it


def test_redaction_keeps_chain_valid(root: Path) -> None:
    append(root, controller(row("AAA", "band_entry")), "r1")
    led, head = paths(root)
    lines = led.read_text(encoding="utf-8").splitlines()
    redacted = json.loads(lines[1]); redacted["payload"] = {"redacted": True}
    led.write_text("\n".join([lines[0], json.dumps(redacted), *lines[2:]]) + "\n", encoding="utf-8")
    assert ledger.verify(led, head)["status"] == "ok"


def test_forbidden_position_fields_rejected() -> None:
    for key in ("position", "allocation", "shares", "order"):
        with pytest.raises(ValueError):
            ledger.build_record(seq=1, prev_hash=ledger.GENESIS_PREV, record_type="alert_event",
                                payload={"ticker": "AAA", "nested": {key: 1}})
    sample = ledger.event_payload("AAA", row("AAA", "band_entry"), "entered_band", None,
                                  {"run_id": "r"}, {"macro_posture": None, "macro_source_sha256": None,
                                                    "earnings_source_sha256": None, "next_earnings_dates": {}})
    assert not ledger._forbidden_keys(sample)


def test_redirected_root_never_touches_production(root: Path) -> None:
    production = [WORKSPACE / ledger.LEDGER_REL, WORKSPACE / ledger.HEAD_REL]
    before = [(p.exists(), p.stat().st_mtime_ns if p.exists() else None) for p in production]
    append(root, controller(row("AAA", "band_entry")), "r1")
    after = [(p.exists(), p.stat().st_mtime_ns if p.exists() else None) for p in production]
    assert before == after
    assert paths(root)[0].is_file()


def test_unevaluable_cycle_is_not_a_transition(root: Path) -> None:
    append(root, controller(row("AAA", "invalidation_alert")), "r1")
    gap = append(root, controller(row("AAA", "monitor_only", alert_state="monitor_only")), "r2")
    assert gap["appended"] == 0
    assert append(root, controller(row("AAA", "invalidation_alert")), "r3")["appended"] == 0


def _record(root: Path, ctl: dict, run_id: str) -> dict:
    return ledger.record_promoted_run(root, ctl, run_id=run_id, window="pre_open", scope_fingerprint="fp",
                                      controller_sha256="c" * 64, message="digest text")


def test_methodology_matches_generator() -> None:
    import yahoo_reference_level_matrix as generator
    assert ledger.BAND_METHODOLOGY_VERSION == generator.BAND_METHODOLOGY_VERSION
    import recommendation_funnel as funnel
    assert ledger.FUNNEL_VERSION == funnel.FUNNEL_VERSION


def test_record_promoted_run_writes_genesis_thesis_and_receipt(root: Path) -> None:
    (root / "state/finance/thesis").mkdir(parents=True)
    (root / "state/finance/thesis/AAA.json").write_text(json.dumps(
        {"ticker": "AAA", "status": "accepted", "thesis_version": "v2"}), encoding="utf-8")
    (root / "state/finance/thesis/BBB.json").write_text(json.dumps(
        {"ticker": "BBB", "status": "draft", "thesis_version": "v1"}), encoding="utf-8")
    (root / "state/finance/baselines").mkdir(parents=True)
    (root / "state/finance/baselines/pin.json").write_text(json.dumps({"matrix_sha256": "m" * 64}), encoding="utf-8")
    out = _record(root, controller(row("AAA", "band_entry"), row("BBB", "no_chase")), "run-1")
    assert out["status"] == "ok" and out["appended"] == 3 and out["verify"]["status"] == "ok"
    records = ledger.read_records(root / ledger.LEDGER_REL)
    genesis = records[0]["payload"]
    assert records[0]["record_type"] == "genesis"
    assert genesis["band_methodology_version"] == "mech-v3-floor-atr20"
    assert genesis["baseline_pins"] == ["state/finance/baselines/pin.json"]
    assert genesis["baseline_matrix_sha256"] == "m" * 64 and genesis["funnel_version"] == "funnel-v1"
    by = {r["payload"]["ticker"]: r["payload"] for r in records[1:]}
    assert by["AAA"]["thesis_version"] == "v2" and by["BBB"]["thesis_version"] is None
    assert by["AAA"]["band_methodology_version"] == "mech-v3-floor-atr20"
    receipt = json.loads((root / ledger.RECEIPT_REL).read_text(encoding="utf-8"))
    assert receipt["status"] == "ok" and receipt["run_id"] == "run-1"
    assert _record(root, controller(row("AAA", "band_entry")), "run-1")["status"] == "ok_duplicate_run"


def test_record_promoted_run_never_raises(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise OSError("disk full")
    monkeypatch.setattr(ledger, "append_events", boom)
    out = _record(root, controller(row("AAA", "band_entry")), "run-x")
    assert out["status"] == "error" and "OSError: disk full" in out["errors"][0]
    assert json.loads((root / ledger.RECEIPT_REL).read_text(encoding="utf-8"))["status"] == "error"


def test_disabled_switch_skips_append(root: Path) -> None:
    (root / ledger.DISABLED_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / ledger.DISABLED_REL).write_text("owner kill switch\n", encoding="utf-8")
    assert _record(root, controller(row("AAA", "band_entry")), "run-d")["status"] == "disabled"
    assert not (root / ledger.LEDGER_REL).exists()


def test_tampered_ledger_reports_error_not_raise(root: Path) -> None:
    _record(root, controller(row("AAA", "band_entry")), "run-1")
    path = root / ledger.LEDGER_REL
    lines = path.read_text(encoding="utf-8").splitlines()
    lines[1] = lines[1].replace('"band_entry"', '"no_chase"', 1)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = _record(root, controller(row("AAA", "no_chase")), "run-2")
    assert out["status"] == "error" and out["verify"]["status"] == "error"
