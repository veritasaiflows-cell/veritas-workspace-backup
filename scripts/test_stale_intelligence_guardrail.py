from __future__ import annotations

import stale_intelligence_guardrail as guard


def expect(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def test_deployable_section_stops_at_bulleted_peer_heading(errors: list[str]) -> None:
    text = """### Deployment map

- **Deployable now:** 0.
- **Promotion review:** GOOG, NVDA, VRT.
- **Almost deployable:** ETN, GS, JPM, MSFT.
- **Do not touch:** BRK.B, LMT, XOM.
"""
    section = guard.current_deployable_section(text)
    expect("0." in section, f"deployable section should include deployable count, got {section!r}", errors)
    expect("Promotion review" not in section, f"deployable section should stop before promotion heading, got {section!r}", errors)
    expect("JPM" not in section, f"deployable section should not include almost-deployable JPM, got {section!r}", errors)


def main() -> int:
    errors: list[str] = []
    test_deployable_section_stops_at_bulleted_peer_heading(errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("test_stale_intelligence_guardrail: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
