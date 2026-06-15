from __future__ import annotations

from stale_intelligence_guardrail import extract_note_close, section_between, ticker_section


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    text = """**Deployable now:**
- **ETN** — Close 419.00.

**Do not touch:**
- **JPM** — stop breached.
"""
    deployable = section_between(text, "**Deployable now:**", r"^\*\*[^\n]+:\*\*")
    require("ETN" in deployable and "JPM" not in deployable, "deployable section extraction should stop at next heading")
    note = """### ETN
- Close: **419.00** *(technical refresh)*
- Stance: no-chase discipline is active.

---

### JPM
- Close: **300.00**
"""
    etn = ticker_section(note, "ETN")
    require("419.00" in etn and "JPM" not in etn, "ticker section extraction should isolate ETN")
    require(extract_note_close(etn) == 419.0, "close extraction should parse bold close")
    print("stale_intelligence_guardrail_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
