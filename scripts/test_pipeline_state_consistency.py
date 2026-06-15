from __future__ import annotations

import io
import json
import sys
import tempfile
from contextlib import redirect_stderr
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKSPACE / "scripts"))

import pipeline_state_consistency_check as checker  # noqa: E402


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def configure_common_paths(tmp: Path) -> None:
    checker.TRIGGER_PATH = tmp / "trigger-sheet.json"
    checker.DEPLOY_PATH = tmp / "deployment-check.json"
    checker.BRIEF_PATH = tmp / "daily-executive-brief.json"
    checker.PREMARKET_PATH = tmp / "premarket-snapshot.json"
    checker.POSTMARKET_PATH = tmp / "postmarket-snapshot.json"
    checker.PREMARKET_BRIEF_INPUT = tmp / "premarket-brief-input.json"
    checker.PREMARKET_REVIEW_BRIEF = tmp / "reports" / "premarket-review-brief-latest.json"
    checker.POSTCLOSE_BRIEF_INPUT = tmp / "postclose-brief-input.json"
    checker.WEEKLY_PRINTABLE_BRIEF = tmp / "reports" / "weekly-intelligence-brief-printable-latest.json"
    checker.OUT_PATH = tmp / "pipeline-state-consistency.json"
    checker.AUTHORITY_SURFACE_PATHS.update({
        "auto": {
            "postclose_brief_input": checker.POSTCLOSE_BRIEF_INPUT,
            "postmarket_snapshot": checker.POSTMARKET_PATH,
            "daily_executive_brief": checker.BRIEF_PATH,
        },
        "morning": {
            "premarket_brief_input": checker.PREMARKET_BRIEF_INPUT,
            "premarket_review_brief": checker.PREMARKET_REVIEW_BRIEF,
        },
        "post-close": {
            "postclose_brief_input": checker.POSTCLOSE_BRIEF_INPUT,
            "postmarket_snapshot": checker.POSTMARKET_PATH,
            "daily_executive_brief": checker.BRIEF_PATH,
        },
        "sunday": {
            "weekly_printable_brief": checker.WEEKLY_PRINTABLE_BRIEF,
            "postmarket_snapshot": checker.POSTMARKET_PATH,
            "daily_executive_brief": checker.BRIEF_PATH,
        },
    })


def run_required_window_parser_case(errors: list[str]) -> None:
    stderr = io.StringIO()
    try:
        with redirect_stderr(stderr):
            checker.parse_args([])
        errors.append("parser: expected missing --window to fail")
    except SystemExit as exc:
        if exc.code == 0:
            errors.append("parser: missing --window should exit non-zero")

    args = checker.parse_args(["--window", "auto"])
    if args.window != "auto":
        errors.append(f"parser: expected explicit auto to remain available, got {args.window}")


def run_postclose_stale_premarket_case(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir) / "tmp"
        configure_common_paths(tmp)
        stale_morning = "2026-05-11T13:05:48+00:00"
        current = "2026-05-11T22:57:40+00:00"

        write_json(checker.TRIGGER_PATH, {
            "generated_at_utc": current,
            "records": [{"ticker": "JPM", "action_state": "DO NOT TOUCH"}],
        })
        write_json(checker.DEPLOY_PATH, {
            "generated_at_utc": current,
            "records": [{"ticker": "JPM", "action_state": "BELOW STOP"}],
        })
        write_json(checker.BRIEF_PATH, {
            "generated_at_utc": current,
            "consumer_posture": "generated_dashboard_archive",
            "canonical_mutation_allowed": False,
            "presentation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
            "deployable_now": [],
            "almost_deployable": [],
            "blocked": [],
            "bench": [],
            "below_stop": ["JPM"],
        })
        write_json(checker.PREMARKET_PATH, {
            "generated_at_utc": stale_morning,
            "deployable_now": [],
            "almost_deployable": ["JPM"],
            "blocked": [],
        })
        write_json(checker.POSTMARKET_PATH, {
            "generated_at_utc": current,
            "consumer_posture": "generated_dashboard_archive",
            "canonical_mutation_allowed": False,
            "presentation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
            "deployable_now": [],
            "almost_deployable": [],
            "blocked": [],
            "do_not_touch": ["JPM"],
        })
        write_json(checker.POSTCLOSE_BRIEF_INPUT, {
            "consumer_posture": "review_only",
            "canonical_mutation_allowed": False,
            "presentation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
        })

        rc = checker.main(["--window", "post-close"])
        report = json.loads(checker.OUT_PATH.read_text(encoding="utf-8"))
        if rc != 0:
            errors.append(f"post-close: expected checker exit 0, got {rc}")
        if report.get("status") != "ok":
            errors.append(f"post-close: expected status ok, got {report.get('status')}")
        if report.get("contradictions_count") != 0:
            errors.append(f"post-close: expected zero contradictions, got {report.get('contradictions_count')}")
        if report.get("authority_ceiling_source") != "static_fail_closed_window_policy":
            errors.append(f"post-close: wrong authority ceiling source {report.get('authority_ceiling_source')}")
        if set(report.get("authority_surfaces_checked") or []) != {"postclose_brief_input", "postmarket_snapshot", "daily_executive_brief"}:
            errors.append(f"post-close: wrong authority surfaces {report.get('authority_surfaces_checked')}")
        checked = set(report.get("sources_checked") or [])
        if "postmarket_snapshot" not in checked:
            errors.append("post-close: expected current postmarket_snapshot to be checked")
        if "premarket_snapshot" in checked:
            errors.append("post-close: did not expect premarket_snapshot in sources_checked")
        ignored = report.get("ignored_sources") or []
        if not any(item.get("surface") == "premarket_snapshot" for item in ignored):
            errors.append("post-close: expected premarket_snapshot to be ignored as non-window evidence")
        jpm = report.get("ticker_surface_map", {}).get("JPM", {})
        if jpm.get("postmarket_snapshot") != "do_not_touch":
            errors.append(f"post-close: expected JPM postmarket bucket do_not_touch, got {jpm.get('postmarket_snapshot')}")

        postmarket = json.loads(checker.POSTMARKET_PATH.read_text(encoding="utf-8"))
        postmarket["authority"] = {"consumer_posture": "generated_dashboard_archive", "portfolio_mutation_allowed": True}
        write_json(checker.POSTMARKET_PATH, postmarket)
        rc = checker.main(["--window", "post-close"])
        report = json.loads(checker.OUT_PATH.read_text(encoding="utf-8"))
        if rc == 0:
            errors.append("post-close: expected nested portfolio_mutation_allowed=true to fail")
        if not any(
            finding.get("surface") == "postmarket_snapshot" and finding.get("field") == "portfolio_mutation_allowed"
            for finding in report.get("authority_findings", [])
        ):
            errors.append(f"post-close: expected nested portfolio authority finding, got {report.get('authority_findings')}")


def run_morning_authority_window_case(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir) / "tmp"
        configure_common_paths(tmp)
        current = "2026-05-11T13:05:48+00:00"
        write_json(checker.TRIGGER_PATH, {
            "generated_at_utc": current,
            "records": [{"ticker": "ETN", "action_state": "DEPLOYABLE NOW"}],
        })
        write_json(checker.DEPLOY_PATH, {
            "generated_at_utc": current,
            "records": [{"ticker": "ETN", "action_state": "DEPLOYABLE NOW"}],
        })
        write_json(checker.PREMARKET_PATH, {
            "generated_at_utc": current,
            "deployable_now": ["ETN"],
            "promotion_review": [],
            "almost_deployable": [],
            "blocked": [],
            "do_not_touch": [],
            "watch": [],
            "error": [],
        })
        write_json(checker.PREMARKET_BRIEF_INPUT, {
            "consumer_posture": "review_only",
            "canonical_mutation_allowed": False,
            "presentation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
        })
        write_json(checker.PREMARKET_REVIEW_BRIEF, {
            "authority": {
                "consumer_posture": "review_only",
                "canonical_note_mutation_allowed": False,
                "portfolio_mutation_allowed": False,
                "deployment_state_mutation_allowed": False,
                "trade_execution_allowed": False,
                "owner_approval_granted": False,
            }
        })

        rc = checker.main(["--window", "morning"])
        report = json.loads(checker.OUT_PATH.read_text(encoding="utf-8"))
        if rc != 0:
            errors.append(f"morning: expected checker exit 0 without post-close artifacts, got {rc}")
        if report.get("authority_findings_count") != 0:
            errors.append(f"morning: expected zero authority findings, got {report.get('authority_findings')}")
        if set(report.get("authority_surfaces_checked") or []) != {"premarket_brief_input", "premarket_review_brief"}:
            errors.append(f"morning: wrong authority surfaces {report.get('authority_surfaces_checked')}")
        if report.get("authority_ceiling_source") != "static_fail_closed_window_policy":
            errors.append(f"morning: wrong authority ceiling source {report.get('authority_ceiling_source')}")

        review_brief = json.loads(checker.PREMARKET_REVIEW_BRIEF.read_text(encoding="utf-8"))
        review_brief["authority"]["trade_execution_allowed"] = True
        write_json(checker.PREMARKET_REVIEW_BRIEF, review_brief)
        rc = checker.main(["--window", "morning"])
        report = json.loads(checker.OUT_PATH.read_text(encoding="utf-8"))
        if rc == 0:
            errors.append("morning: expected nested trade_execution_allowed=true to fail")
        if not any(
            finding.get("surface") == "premarket_review_brief" and finding.get("field") == "trade_execution_allowed"
            for finding in report.get("authority_findings", [])
        ):
            errors.append(f"morning: expected nested trade authority finding, got {report.get('authority_findings')}")


def run_sunday_authority_window_case(errors: list[str]) -> None:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir) / "tmp"
        configure_common_paths(tmp)
        current = "2026-05-11T05:57:01+00:00"
        write_json(checker.TRIGGER_PATH, {
            "generated_at_utc": current,
            "records": [{"ticker": "ETN", "action_state": "DEPLOYABLE NOW"}],
        })
        write_json(checker.DEPLOY_PATH, {
            "generated_at_utc": current,
            "records": [{"ticker": "ETN", "action_state": "DEPLOYABLE NOW"}],
        })
        write_json(checker.BRIEF_PATH, {
            "generated_at_utc": current,
            "consumer_posture": "generated_dashboard_archive",
            "canonical_mutation_allowed": False,
            "presentation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
            "deployable_now": ["ETN"],
            "almost_deployable": [],
            "blocked": [],
            "bench": [],
            "below_stop": [],
        })
        write_json(checker.POSTMARKET_PATH, {
            "generated_at_utc": current,
            "consumer_posture": "generated_dashboard_archive",
            "canonical_mutation_allowed": False,
            "presentation_allowed": False,
            "portfolio_mutation_allowed": False,
            "deployment_state_mutation_allowed": False,
            "trade_execution_allowed": False,
            "owner_approval_granted": False,
            "deployable_now": ["ETN"],
            "promotion_review": [],
            "almost_deployable": [],
            "blocked": [],
            "do_not_touch": [],
            "watch": [],
            "error": [],
        })
        write_json(checker.WEEKLY_PRINTABLE_BRIEF, {
            "authority": {
                "consumer_posture": "review_only",
                "canonical_note_mutation_allowed": False,
                "portfolio_mutation_allowed": False,
                "deployment_state_mutation_allowed": False,
                "trade_execution_allowed": False,
                "owner_approval_granted": False,
            }
        })

        rc = checker.main(["--window", "sunday"])
        report = json.loads(checker.OUT_PATH.read_text(encoding="utf-8"))
        if rc != 0:
            errors.append(f"sunday: expected checker exit 0 without postclose_brief_input, got {rc}")
        if set(report.get("authority_surfaces_checked") or []) != {"weekly_printable_brief", "postmarket_snapshot", "daily_executive_brief"}:
            errors.append(f"sunday: wrong authority surfaces {report.get('authority_surfaces_checked')}")
        if "postclose_brief_input" in set(report.get("authority_surfaces_checked") or []):
            errors.append("sunday: did not expect postclose_brief_input authority surface")
        if report.get("authority_ceiling_source") != "static_fail_closed_window_policy":
            errors.append(f"sunday: wrong authority ceiling source {report.get('authority_ceiling_source')}")

        weekly = json.loads(checker.WEEKLY_PRINTABLE_BRIEF.read_text(encoding="utf-8"))
        weekly["authority"]["owner_approval_granted"] = True
        write_json(checker.WEEKLY_PRINTABLE_BRIEF, weekly)
        rc = checker.main(["--window", "sunday"])
        report = json.loads(checker.OUT_PATH.read_text(encoding="utf-8"))
        if rc == 0:
            errors.append("sunday: expected nested owner_approval_granted=true to fail")
        if not any(
            finding.get("surface") == "weekly_printable_brief" and finding.get("field") == "owner_approval_granted"
            for finding in report.get("authority_findings", [])
        ):
            errors.append(f"sunday: expected nested owner authority finding, got {report.get('authority_findings')}")


def main() -> int:
    errors: list[str] = []
    run_required_window_parser_case(errors)
    run_postclose_stale_premarket_case(errors)
    run_morning_authority_window_case(errors)
    run_sunday_authority_window_case(errors)

    if errors:
        print("pipeline state consistency regression failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("pipeline state consistency regression passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
