from __future__ import annotations

from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import wf72_entry_stop_sql_activate as wf72


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_validation_target_keys_uses_sql_cache_when_worker_rows_are_thin(errors: list[str]) -> None:
    original_worker_candidate_rows = wf72.worker_candidate_rows
    original_active_family_tickers_from_cache = wf72.active_family_tickers_from_cache
    tickers = [f"T{i:02d}" for i in range(wf72.BATCH_SIZES["all"])]
    try:
        wf72.worker_candidate_rows = lambda: []
        wf72.active_family_tickers_from_cache = lambda batch: tickers if batch == "all" else []
        keys, source, reason = wf72.validation_target_keys("all")
    finally:
        wf72.worker_candidate_rows = original_worker_candidate_rows
        wf72.active_family_tickers_from_cache = original_active_family_tickers_from_cache

    expect(source == "active_sql_cache_state", f"expected SQL/cache fallback source, got {source}", errors)
    expect(reason == "worker_candidate_rows=0", f"expected thinned-worker reason, got {reason}", errors)
    expect(len(keys) == wf72.BATCH_SIZES["all"] * len(wf72.ENTRY_STOP_FIELDS), "expected full WF72 key count", errors)
    expect(keys[0] == "T00:reference_price_low", f"unexpected first key {keys[0] if keys else None}", errors)


def test_validation_target_keys_fails_closed_without_worker_or_sql_cache(errors: list[str]) -> None:
    original_worker_candidate_rows = wf72.worker_candidate_rows
    original_active_family_tickers_from_cache = wf72.active_family_tickers_from_cache
    try:
        wf72.worker_candidate_rows = lambda: []
        wf72.active_family_tickers_from_cache = lambda batch: []
        try:
            wf72.validation_target_keys("all")
        except SystemExit as exc:
            expect("expected 42 candidate rows" in str(exc), f"unexpected fail-closed reason {exc}", errors)
        else:
            errors.append("validation target keys should fail closed without worker rows or active SQL/cache proof")
    finally:
        wf72.worker_candidate_rows = original_worker_candidate_rows
        wf72.active_family_tickers_from_cache = original_active_family_tickers_from_cache


def main() -> int:
    errors: list[str] = []
    for test in (
        test_validation_target_keys_uses_sql_cache_when_worker_rows_are_thin,
        test_validation_target_keys_fails_closed_without_worker_or_sql_cache,
    ):
        try:
            test(errors)
        except Exception as exc:
            errors.append(f"{test.__name__} raised {type(exc).__name__}: {exc}")
    if errors:
        print("wf72 entry/stop SQL activation tests failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf72 entry/stop SQL activation tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
