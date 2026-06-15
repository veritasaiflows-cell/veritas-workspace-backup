from __future__ import annotations

from canonical_note_patch_proposal import build_candidates


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    report = {
        "generated_at_utc": "2026-05-12T01:50:00Z",
        "status": "critical",
        "summary": {"below_stop": ["JPM"], "near_stop": []},
        "risks": [
            {
                "ticker": "JPM",
                "risk_state": "below_stop",
                "close": 300.0,
                "stop": 301.17,
                "band_low": 306.82,
            }
        ],
        "issues": [
            {
                "severity": "critical",
                "ticker": "JPM",
                "surface": "03. Portfolio/Execution Board.md",
                "code": "trigger_note_stop_missing",
                "message": "JPM trigger-note row does not show do-not-touch stop risk",
                "evidence": "| JPM | Almost deployable | stale |",
            }
        ],
    }
    candidates = build_candidates(report)
    require(len(candidates) == 1, "one issue should produce one candidate")
    candidate = candidates[0]
    require(candidate["cron_apply_allowed"] is False, "cron apply must remain disabled")
    require(candidate["main_session_approval_required"] is True, "main-session approval must be required")
    require(candidate["portfolio_mutation_allowed"] is False, "portfolio mutation must remain disabled")
    require("do not touch / stop-breached" in candidate["proposed_replacement_hint"], "below-stop proposal should harden wording")
    require("300.00" in candidate["proposed_replacement_hint"], "proposal should include close evidence")
    print("canonical_note_patch_proposal_tests_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
