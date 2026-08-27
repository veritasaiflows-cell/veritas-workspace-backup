from __future__ import annotations

import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from wf85_source_open_reconciliation_contract import (  # noqa: E402
    BLOCKED_SOURCE_OPEN,
    ContractPaths,
    build_contract,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def make_paths(root: Path) -> ContractPaths:
    return ContractPaths(
        source_gate=root / "source-gate.json",
        decision_cards=root / "decision-cards.json",
        full_answer_rollup=root / "full-answer-rollup.json",
        full_answer_dir=root / "full-answers",
        cache_frontdoor=root / "cache-frontdoor.json",
    )


def write_chain(
    paths: ContractPaths,
    *,
    ticker: str = "AAA",
    source_generated_at: str = "2026-06-30T01:00:00Z",
    card_generated_at: str = "2026-06-30T01:01:00Z",
    full_generated_at: str = "2026-06-30T01:02:00Z",
    cache_generated_at: str = "2026-06-30T01:03:00Z",
    source_open_status: str = "verified",
    freshness_status: str = "fresh",
    card_decision_state: str = "review_ready",
    full_decision_state: str = "review_ready",
    cache_decision_state: str = "review_ready",
    material_claim_requires_source_open: bool = False,
) -> None:
    write_json(
        paths.source_gate,
        {
            "generated_at_utc": source_generated_at,
            "status": "ok",
            "rows": [
                {
                    "ticker": ticker,
                    "source_open_status": source_open_status,
                    "freshness_status": freshness_status,
                }
            ],
        },
    )
    write_json(
        paths.decision_cards,
        {
            "generated_at_utc": card_generated_at,
            "status": "ok",
            "cards": [
                {
                    "ticker": ticker,
                    "decision_state": card_decision_state,
                    "decision_state_reason": "test",
                }
            ],
        },
    )
    write_json(
        paths.full_answer_rollup,
        {
            "generated_at_utc": full_generated_at,
            "status": "ok",
            "results": [
                {
                    "ticker": ticker,
                    "decision_state": full_decision_state,
                }
            ],
        },
    )
    write_json(
        paths.full_answer_dir / f"{ticker}.json",
        {
            "generated_at_utc": full_generated_at,
            "machine_state": {"decision_state": full_decision_state},
        },
    )
    write_json(
        paths.cache_frontdoor,
        {
            "generated_at_utc": cache_generated_at,
            "status": "ok",
            "rows": [
                {
                    "ticker": ticker,
                    "decision_state": cache_decision_state,
                    "material_claim_requires_source_open": material_claim_requires_source_open,
                }
            ],
        },
    )


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_clean_verified_chain_is_ok(errors: list[str]) -> None:
    with TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_chain(paths)
        packet = build_contract(paths)
        summary = packet["summary"]
        expect(packet["status"] == "ok", f"expected ok, got {packet['status']}", errors)
        expect(summary["producer_order_error_count"] == 0, "producer order should be clean", errors)
        expect(summary["unnecessary_source_open_blocker_count"] == 0, "no unnecessary blockers expected", errors)
        expect(summary["mismatch_error_count"] == 0, "no mismatch errors expected", errors)


def test_fresh_verified_source_blocked_downstream_is_error(errors: list[str]) -> None:
    with TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_chain(
            paths,
            card_decision_state=BLOCKED_SOURCE_OPEN,
            full_decision_state=BLOCKED_SOURCE_OPEN,
            cache_decision_state=BLOCKED_SOURCE_OPEN,
        )
        packet = build_contract(paths)
        kinds = {row["kind"] for row in packet["mismatches"]}
        expect(packet["status"] == "blocked", "verified fresh source-open residue should block", errors)
        expect(
            "fresh_verified_card_unnecessary_source_open_block" in kinds,
            "card-level unnecessary source-open block should be detected",
            errors,
        )
        expect(
            "fresh_verified_full_answer_unnecessary_source_open_block" in kinds,
            "full-answer unnecessary source-open block should be detected",
            errors,
        )
        expect(
            "fresh_verified_cache_unnecessary_source_open_block" in kinds,
            "cache unnecessary source-open block should be detected",
            errors,
        )


def test_downstream_older_than_upstream_blocks_contract(errors: list[str]) -> None:
    with TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_chain(
            paths,
            source_generated_at="2026-06-30T01:10:00Z",
            card_generated_at="2026-06-30T01:00:00Z",
        )
        packet = build_contract(paths)
        order_errors = packet["producer_order"]["errors"]
        kinds = {row["kind"] for row in order_errors}
        expect(packet["status"] == "blocked", "downstream stale producer order should block", errors)
        expect("downstream_older_than_upstream" in kinds, "producer order error should be explicit", errors)


def test_small_timestamp_skew_does_not_block_contract(errors: list[str]) -> None:
    with TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_chain(
            paths,
            source_generated_at="2026-06-30T01:00:02Z",
            card_generated_at="2026-06-30T01:00:01Z",
            full_generated_at="2026-06-30T01:00:00Z",
            cache_generated_at="2026-06-30T01:00:00Z",
        )
        packet = build_contract(paths)
        expect(packet["status"] == "ok", "small producer timestamp skew should not block", errors)
        expect(
            packet["summary"]["producer_order_error_count"] == 0,
            "small skew should not count as producer-order error",
            errors,
        )


def test_verified_source_material_source_open_requirement_is_error(errors: list[str]) -> None:
    with TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_chain(paths, material_claim_requires_source_open=True)
        packet = build_contract(paths)
        kinds = {row["kind"] for row in packet["mismatches"]}
        expect(packet["status"] == "blocked", "verified source cannot still require source-open repair", errors)
        expect(
            "verified_source_marked_material_source_open_required" in kinds,
            "material-source-open requirement mismatch should be detected",
            errors,
        )


def test_ticker_scope_ignores_unrelated_stale_rows(errors: list[str]) -> None:
    with TemporaryDirectory() as tmp:
        paths = make_paths(Path(tmp))
        write_chain(paths, ticker="AAA")

        source_payload = json.loads(paths.source_gate.read_text(encoding="utf-8"))
        source_payload["rows"].append({
            "ticker": "BBB",
            "source_open_status": "verified",
            "freshness_status": "fresh",
        })
        write_json(paths.source_gate, source_payload)

        card_payload = json.loads(paths.decision_cards.read_text(encoding="utf-8"))
        card_payload["cards"].append({
            "ticker": "BBB",
            "decision_state": BLOCKED_SOURCE_OPEN,
            "decision_state_reason": "stale outside scoped proof",
        })
        write_json(paths.decision_cards, card_payload)

        full_rollup_payload = json.loads(paths.full_answer_rollup.read_text(encoding="utf-8"))
        full_rollup_payload["results"].append({
            "ticker": "BBB",
            "decision_state": BLOCKED_SOURCE_OPEN,
        })
        write_json(paths.full_answer_rollup, full_rollup_payload)
        write_json(
            paths.full_answer_dir / "BBB.json",
            {"machine_state": {"decision_state": BLOCKED_SOURCE_OPEN}},
        )

        cache_payload = json.loads(paths.cache_frontdoor.read_text(encoding="utf-8"))
        cache_payload["rows"].append({
            "ticker": "BBB",
            "decision_state": BLOCKED_SOURCE_OPEN,
            "material_claim_requires_source_open": True,
        })
        write_json(paths.cache_frontdoor, cache_payload)

        scoped = build_contract(paths, {"AAA"})
        global_packet = build_contract(paths)
        expect(scoped["status"] == "ok", "ticker-scoped clean row should not be blocked by unrelated stale row", errors)
        expect(scoped["summary"]["ticker_count"] == 1, "ticker-scoped contract should only inspect one row", errors)
        expect(scoped["scope"]["tickers"] == ["AAA"], "ticker scope should be recorded", errors)
        expect(global_packet["status"] == "blocked", "global contract should still catch unrelated stale row", errors)


def main() -> int:
    errors: list[str] = []
    test_clean_verified_chain_is_ok(errors)
    test_fresh_verified_source_blocked_downstream_is_error(errors)
    test_downstream_older_than_upstream_blocks_contract(errors)
    test_small_timestamp_skew_does_not_block_contract(errors)
    test_verified_source_material_source_open_requirement_is_error(errors)
    test_ticker_scope_ignores_unrelated_stale_rows(errors)
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print("ok: wf85 source-open reconciliation contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
