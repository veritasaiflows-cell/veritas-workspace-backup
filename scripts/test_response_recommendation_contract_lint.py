#!/usr/bin/env python3
"""Regression tests for response recommendation contract linting."""
from __future__ import annotations

import response_recommendation_contract_lint as lint


def main() -> int:
    good = lint.lint_text(lint.GOOD_SAMPLE, strict=True)
    assert good["status"] == "ok", good
    assert all(good["checks"].values()), good

    bad = lint.lint_text(lint.BAD_SAMPLE, strict=True)
    assert bad["status"] == "blocked", bad
    codes = {finding["code"] for finding in bad["findings"]}
    assert "ranked_p0_p1_p2" in codes, bad
    assert "action_labels" in codes, bad
    assert "do_dont_guidance" in codes, bad
    assert "improvement_or_prevention" in codes, bad

    thin_recommendation = """Top recommendations:
1. P0 - Fix the bug.
2. P1 - Run tests.
3. P2 - Monitor.
"""
    thin = lint.lint_text(thin_recommendation, strict=True)
    assert thin["status"] == "blocked", thin
    thin_codes = {finding["code"] for finding in thin["findings"]}
    assert "action_labels" in thin_codes, thin
    assert "do_dont_guidance" in thin_codes, thin

    self_result = lint.self_test()
    assert self_result["status"] == "ok", self_result
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
