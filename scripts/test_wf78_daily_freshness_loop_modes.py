from __future__ import annotations

import argparse

import wf78_daily_freshness_loop as loop


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def main() -> int:
    errors: list[str] = []
    args = argparse.Namespace(
        skip_provider_refresh=True,
        full_answer_mode="changed",
        phase=["daily_core"],
    )
    names = [step[0] for step in loop.build_steps(args)]

    expect("ticker_card_refresh_gate" in names, "daily_core must include initial card refresh", errors)
    expect("wf78_auto_tier_router_initial" in names, "daily_core must include routing", errors)
    expect("wf78_missing_band_context_repair" in names, "daily_core must include evidence repair", errors)
    expect("wf84_canonical_finance_data_plane" in names, "daily_core must include WF84 sync", errors)
    expect("wf78_official_source_discovery" not in names, "daily_core must skip source-capture expansion", errors)
    expect("wf78_position_sizing_surface_review" not in names, "daily_core must skip owner-review expansion", errors)

    source_capture_args = argparse.Namespace(
        skip_provider_refresh=True,
        full_answer_mode="never",
        phase=["source_capture"],
    )
    source_names = [step[0] for step in loop.build_steps(source_capture_args)]
    expect(source_names, "source_capture phase must not be empty", errors)
    expect(
        all(loop.STEP_PHASES.get(name) == "source_capture" for name in source_names),
        "source_capture phase must only include source-capture steps",
        errors,
    )

    if errors:
        print("wf78_daily_freshness_loop_mode_tests_failed")
        for error in errors:
            print(f"- {error}")
        return 1
    print("wf78_daily_freshness_loop_mode_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
