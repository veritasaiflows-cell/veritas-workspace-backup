#!/usr/bin/env python3
"""The retired WF78 V2 runner may import, but cannot obtain a work plan."""
from __future__ import annotations

import wf_manifest as manifest


def main() -> int:
    assert manifest.structural_errors() == ["retired_workflow:WF78"]
    try:
        manifest.selected_layers(["daily_core_v2"])
    except manifest.RetiredWorkflowError:
        pass
    else:
        raise AssertionError("retired V2 layer request did not fail closed")
    print("wf78_intelligence_routing_v2_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
