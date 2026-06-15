from __future__ import annotations

import cache_dependency_manifest as manifest
import finance_intelligence_state as finance_state


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_layer_status_hash_gating(errors: list[str]) -> None:
    expect(
        manifest.layer_status("abc", "abc", "ok")["status"] == "ok",
        "matching source hash should be ok",
        errors,
    )
    expect(
        manifest.layer_status("old", "new", "ok")["status"] == "stale",
        "mismatched source hash should be stale",
        errors,
    )
    expect(
        manifest.layer_status("", "new", "ok")["status"] == "blocked",
        "missing source hash should block",
        errors,
    )


def test_value_consistency_blocks_cross_layer_mismatch(errors: list[str]) -> None:
    ok = manifest.value_consistency(
        {"entry_band_low": 1, "entry_band_high": 2, "stop_or_invalidation": 0.5},
        {"entry_band_low": 1, "entry_band_high": 2, "stop_or_invalidation": 0.5},
    )
    expect(ok["status"] == "ok", f"matching values should be ok, got {ok}", errors)
    blocked = manifest.value_consistency(
        {"entry_band_low": 1, "entry_band_high": 2, "stop_or_invalidation": 0.5},
        {"entry_band_low": 1.5, "entry_band_high": 2, "stop_or_invalidation": 0.5},
    )
    expect(blocked["status"] == "blocked", f"value mismatch should block, got {blocked}", errors)


def test_front_door_guard_blocks_hash_mismatch(errors: list[str]) -> None:
    original_hash = finance_state.sha256_file
    original_wf84 = finance_state.wf84_entry_stop_reference
    try:
        finance_state.sha256_file = lambda _path: "current-hash"  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = lambda _ticker: {  # type: ignore[assignment]
            "source_artifact_path": "03. Portfolio/Execution Board.md",
            "source_artifact_hash": "current-hash",
            "validation_status": "ok",
            "freshness_status": "fresh",
        }
        guard = finance_state.entry_stop_cache_freshness_guard(
            "ETN",
            {
                "source_artifact_path": "03. Portfolio/Execution Board.md",
                "source_artifact_hash": "old-hash",
                "validation_status": "ok",
                "freshness_status": "fresh",
            },
        )
        expect(guard["status"] == "stale_cache_blocked", f"expected stale_cache_blocked, got {guard}", errors)
        expect(
            guard["front_door_policy"]["prefer_wf85_full_answer"] is False,
            "front door should not prefer WF85 when hash mismatch is present",
            errors,
        )
    finally:
        finance_state.sha256_file = original_hash  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = original_wf84  # type: ignore[assignment]


def test_front_door_guard_blocks_value_mismatch(errors: list[str]) -> None:
    original_hash = finance_state.sha256_file
    original_wf84 = finance_state.wf84_entry_stop_reference
    try:
        finance_state.sha256_file = lambda _path: "current-hash"  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = lambda _ticker: {  # type: ignore[assignment]
            "source_artifact_path": "03. Portfolio/Execution Board.md",
            "source_artifact_hash": "current-hash",
            "validation_status": "ok",
            "freshness_status": "fresh",
            "entry_band_low": 1.5,
            "entry_band_high": 2,
            "stop_or_invalidation": 0.5,
        }
        guard = finance_state.entry_stop_cache_freshness_guard(
            "ETN",
            {
                "source_artifact_path": "03. Portfolio/Execution Board.md",
                "source_artifact_hash": "current-hash",
                "validation_status": "ok",
                "freshness_status": "fresh",
                "entry_band_low": 1,
                "entry_band_high": 2,
                "stop_or_invalidation": 0.5,
            },
        )
        expect(guard["status"] == "cross_layer_value_mismatch_blocked", f"expected value-mismatch block, got {guard}", errors)
    finally:
        finance_state.sha256_file = original_hash  # type: ignore[assignment]
        finance_state.wf84_entry_stop_reference = original_wf84  # type: ignore[assignment]


def main() -> int:
    errors: list[str] = []
    test_layer_status_hash_gating(errors)
    test_value_consistency_blocks_cross_layer_mismatch(errors)
    test_front_door_guard_blocks_hash_mismatch(errors)
    test_front_door_guard_blocks_value_mismatch(errors)
    if errors:
        print("cache_dependency_manifest_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("cache_dependency_manifest_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
