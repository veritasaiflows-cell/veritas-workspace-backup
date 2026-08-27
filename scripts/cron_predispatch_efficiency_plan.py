#!/usr/bin/env python3
"""Generate a review-only plan for cron token pre-dispatch savings."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_TOKEN_SCORECARD = TMP / "token-efficiency-scorecard.json"
DEFAULT_PLAN_JSON = TMP / "cron-predispatch-efficiency-plan.json"
DEFAULT_PLAN_MD = TMP / "cron-predispatch-efficiency-plan.md"
SCHEMA = "veritas.cron_predispatch_efficiency_plan.v1"

DEFAULT_CHANGED_INPUT_GATE_SCRIPTS = {
    "scripts/cyber_security_daily_audit_cron_runner.py",
    "scripts/cron_control_digest_runner.py",
    "scripts/pm_job_worker_runner.py",
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "cron_schedule_mutation": False,
    "cron_runtime_mutation": False,
    "cron_config_mutation": False,
    "finance_canon_mutation": False,
    "portfolio_or_capital_mutation": False,
    "paper_or_live_execution": False,
    "owner_approval_inference": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(text, encoding="utf-8")
    tmp_path.replace(path)


def load_cron_export(path_arg: str | None) -> dict[str, Any] | None:
    if not path_arg:
        try:
            import cron_contract_validator

            jobs, live_meta = cron_contract_validator.load_live_jobs()
            return {
                "source": "cron_contract_validator.load_live_jobs",
                "live_meta": live_meta,
                "jobs": jobs,
            }
        except Exception as exc:  # pragma: no cover - defensive fallback for standalone use
            return {
                "source": "cron_contract_validator.load_live_jobs",
                "status": "warning",
                "warnings": [f"live_cron_load_failed:{type(exc).__name__}"],
                "jobs": [],
            }
    if path_arg == "-":
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else None
    path = Path(path_arg)
    if not path.is_absolute():
        path = ROOT / path
    return load_json(path)


def iter_cron_jobs(cron_export: Any) -> list[dict[str, Any]]:
    if not cron_export:
        return []
    if isinstance(cron_export, list):
        return [job for job in cron_export if isinstance(job, dict)]
    if isinstance(cron_export, dict):
        for key in ("jobs", "crons", "items", "entries"):
            value = cron_export.get(key)
            if isinstance(value, list):
                return [job for job in value if isinstance(job, dict)]
    return []


def cron_name(job: dict[str, Any]) -> str | None:
    for key in ("name", "title", "job_name", "id"):
        value = job.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def payload_kind(job: dict[str, Any]) -> str | None:
    payload = job.get("payload")
    if isinstance(payload, dict):
        kind = payload.get("kind") or payload.get("type")
        if isinstance(kind, str):
            return kind
    for key in ("payload_kind", "kind", "type"):
        value = job.get(key)
        if isinstance(value, str):
            return value
    return None


def model_path(job: dict[str, Any]) -> str | None:
    payload = job.get("payload")
    if isinstance(payload, dict):
        for key in ("model", "model_path"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
    for key in ("model", "model_path"):
        value = job.get(key)
        if isinstance(value, str):
            return value
    return None


def schedule(job: dict[str, Any]) -> str | None:
    for key in ("schedule", "cron", "cron_expression"):
        value = job.get(key)
        if isinstance(value, str):
            return value
    return None


def payload_argv(job: dict[str, Any]) -> list[str]:
    payload = job.get("payload")
    if isinstance(payload, dict):
        value = payload.get("argv")
        if isinstance(value, list):
            return [str(item) for item in value]
    value = job.get("argv")
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def description(job: dict[str, Any]) -> str:
    value = job.get("description")
    return value if isinstance(value, str) else ""


def has_existing_changed_input_gate(job: dict[str, Any], argv: list[str]) -> bool:
    lowered_argv = [item.lower() for item in argv]
    normalized_argv = [item.replace("\\", "/").lower() for item in argv]
    skip_flags = {
        "--changed-only",
        "--skip-if-unchanged",
    }
    if any(item in skip_flags for item in lowered_argv):
        return True
    if any(item in DEFAULT_CHANGED_INPUT_GATE_SCRIPTS for item in normalized_argv):
        return True
    # Some command wrappers skip unchanged inputs by default and expose only a
    # --force-refresh bypass in the scheduled argv-less path.
    if "--force-refresh" in lowered_argv:
        return False
    text = " ".join(
        [
            description(job),
            " ".join(lowered_argv),
            str(job.get("contract_reason") or ""),
            str(job.get("contract_update_reason") or ""),
        ]
    ).lower()
    gate_markers = (
        "changed-input skip",
        "changed input skip",
        "changed-only skip",
        "skip-if-unchanged",
        "unchanged-input skip",
        "unchanged input skip",
    )
    return any(marker in text for marker in gate_markers)


def enabled(job: dict[str, Any]) -> bool | None:
    for key in ("enabled", "is_enabled", "active"):
        if key in job:
            return bool(job.get(key))
    return None


def candidate_rows(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("cron_candidates", "top_cron_efficiency_candidates", "ranked_cron_candidates"):
        value = scorecard.get(key)
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    candidates = scorecard.get("candidates")
    if isinstance(candidates, dict):
        value = candidates.get("cron") or candidates.get("cron_candidates")
        if isinstance(value, list):
            return [row for row in value if isinstance(row, dict)]
    return []


def candidate_name(row: dict[str, Any]) -> str:
    for key in ("cron_job_name", "cron_name", "job_name", "name", "title", "candidate"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return "UNKNOWN"


def candidate_tokens(row: dict[str, Any]) -> int | None:
    for key in ("tokens", "total_tokens", "estimated_tokens", "input_tokens", "token_count"):
        value = row.get(key)
        if isinstance(value, (int, float)):
            return int(value)
    return None


def classify_candidate(name: str, row: dict[str, Any], live_job: dict[str, Any] | None) -> dict[str, Any]:
    kind = payload_kind(live_job or {}) if live_job else None
    model = model_path(live_job or {})
    argv = payload_argv(live_job or {})
    has_changed_only = has_existing_changed_input_gate(live_job or {}, argv)
    if live_job is None:
        route = "live_payload_discovery_required"
        script_gate_saves_model_tokens = None
        script_gate_saves_runtime_work = None
        safe_next_action = "Export live cron JSON before preparing an exact payload diff."
    elif kind == "agentTurn":
        route = "cron_payload_diff_required"
        script_gate_saves_model_tokens = False
        script_gate_saves_runtime_work = True
        safe_next_action = (
            "Prepare an exact cron payload/wrapper diff so unchanged inputs are checked before the model call."
        )
    elif kind:
        if has_changed_only:
            route = "existing_changed_input_command_gate_present"
        else:
            route = "script_prefilter_wrapper_candidate" if model else "command_prefilter_runtime_efficiency_candidate"
        script_gate_saves_model_tokens = bool(model)
        script_gate_saves_runtime_work = True
        if has_changed_only:
            safe_next_action = "Monitor existing changed-input behavior; do not add a duplicate wrapper unless proof shows it is ineffective."
        else:
            safe_next_action = (
                "Wrap the command payload with cron_changed_input_prefilter and update state only after success; "
                "claim direct model-token savings only if the payload actually spawns a model call."
            )
    else:
        route = "payload_kind_unknown"
        script_gate_saves_model_tokens = None
        script_gate_saves_runtime_work = None
        safe_next_action = "Inspect the live payload kind before claiming token savings."
    return {
        "cron_name": name,
        "estimated_tokens": candidate_tokens(row),
        "candidate_source": row,
        "live_cron_found": live_job is not None,
        "live_enabled": enabled(live_job or {}),
        "payload_kind": kind,
        "payload_argv": argv,
        "existing_changed_only_gate": has_changed_only,
        "model_path": model,
        "schedule": schedule(live_job or {}),
        "implementation_route": route,
        "script_level_prefilter_saves_model_tokens": script_gate_saves_model_tokens,
        "script_level_prefilter_saves_runtime_work": script_gate_saves_runtime_work,
        "safe_next_action": safe_next_action,
    }


def build_plan(scorecard: dict[str, Any], cron_export: dict[str, Any] | None, limit: int) -> dict[str, Any]:
    jobs = iter_cron_jobs(cron_export)
    live_by_name = {name: job for job in jobs if (name := cron_name(job))}
    rows = candidate_rows(scorecard)[:limit]
    classified = [classify_candidate(candidate_name(row), row, live_by_name.get(candidate_name(row))) for row in rows]
    agent_turn_count = sum(1 for row in classified if row["payload_kind"] == "agentTurn")
    command_candidate_count = sum(1 for row in classified if row["implementation_route"] == "script_prefilter_wrapper_candidate")
    existing_changed_only_count = sum(
        1 for row in classified if row["implementation_route"] == "existing_changed_input_command_gate_present"
    )
    live_missing_count = sum(1 for row in classified if not row["live_cron_found"])
    warnings: list[str] = []
    if agent_turn_count:
        warnings.append("agent_turn_candidates_require_pre_model_payload_diff")
    if live_missing_count:
        warnings.append("some_candidates_missing_live_cron_export_match")
    if not rows:
        warnings.append("no_cron_candidates_found_in_token_scorecard")

    status = "warning" if warnings else "ok"
    summary = scorecard.get("summary") if isinstance(scorecard.get("summary"), dict) else {}
    billing_semantics = scorecard.get("billing_semantics") if isinstance(scorecard.get("billing_semantics"), dict) else {}
    oauth_capacity_control = scorecard.get("oauth_capacity_control") if isinstance(scorecard.get("oauth_capacity_control"), dict) else {}
    api_equivalent_cost = summary.get("api_equivalent_cost_usd", scorecard.get("api_equivalent_cost_usd"))
    if api_equivalent_cost is None:
        api_equivalent_cost = summary.get("estimated_cost_total", scorecard.get("estimated_cost_total"))
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": status,
        "summary": {
            "candidate_count": len(classified),
            "agent_turn_candidate_count": agent_turn_count,
            "command_wrapper_candidate_count": command_candidate_count,
            "existing_changed_only_command_gate_count": existing_changed_only_count,
            "existing_changed_input_command_gate_count": existing_changed_only_count,
            "live_missing_count": live_missing_count,
            "token_scorecard_status": scorecard.get("status"),
            "token_event_count": summary.get("token_event_count", scorecard.get("token_event_count")),
            "total_tokens": summary.get("total_tokens", scorecard.get("total_tokens")),
            "api_equivalent_cost_usd": api_equivalent_cost,
            "api_equivalent_estimate_status": summary.get("api_equivalent_estimate_status", scorecard.get("api_equivalent_estimate_status")),
            "api_equivalent_cost_rows": summary.get("api_equivalent_cost_rows", scorecard.get("api_equivalent_cost_rows")),
            "api_equivalent_cost_event_coverage_percent": summary.get("api_equivalent_cost_event_coverage_percent", scorecard.get("api_equivalent_cost_event_coverage_percent")),
            "estimated_cost_total": api_equivalent_cost,
            "estimated_cost_total_deprecated_alias_for": "api_equivalent_cost_usd",
            "estimated_chatgpt_credits": summary.get(
                "estimated_chatgpt_credits", scorecard.get("estimated_chatgpt_credits")
            ),
            "chatgpt_credit_estimate_status": summary.get("chatgpt_credit_estimate_status", scorecard.get("chatgpt_credit_estimate_status")),
            "estimated_chatgpt_credit_rows": summary.get("estimated_chatgpt_credit_rows", scorecard.get("estimated_chatgpt_credit_rows")),
            "chatgpt_credit_event_coverage_percent": summary.get("chatgpt_credit_event_coverage_percent", scorecard.get("chatgpt_credit_event_coverage_percent")),
            "unknown_or_invalid_input_token_semantics_event_count": summary.get("unknown_or_invalid_input_token_semantics_event_count"),
            "rolling_5h_total_tokens": summary.get("rolling_5h_total_tokens"),
            "rolling_7d_observed_total_tokens": summary.get("rolling_7d_observed_total_tokens"),
            "usage_timestamp_coverage_percent": summary.get("usage_timestamp_coverage_percent"),
            "actual_billed_cost_usd": summary.get(
                "actual_billed_cost_usd", scorecard.get("actual_billed_cost_usd")
            ),
            "oauth_quota_state": oauth_capacity_control.get("state") or oauth_capacity_control.get("status"),
            "oauth_remaining_percent": oauth_capacity_control.get("remaining_percent"),
            "implementation_token_gap_count": summary.get(
                "implementation_token_gap_count", scorecard.get("implementation_token_gap_count")
            ),
        },
        "billing_semantics": billing_semantics,
        "oauth_capacity_control": oauth_capacity_control,
        "usage_pace": scorecard.get("usage_pace") if isinstance(scorecard.get("usage_pace"), dict) else {},
        "compatibility": {
            "deprecated_aliases": {
                "summary.estimated_cost_total": "summary.api_equivalent_cost_usd",
            }
        },
        "recommendation": {
            "do_now": [
                "Use cron_changed_input_prefilter for command-style wrappers and smoke tests.",
                "Prepare exact cron payload diffs for agentTurn jobs; script-only gates inside the spawned agent do not save model-call tokens.",
                "Keep finance/model ranking claims gated until attribution coverage and semantic outcomes mature.",
            ],
            "do_not_claim": [
                "Do not claim token savings for agentTurn jobs until the skip check happens before the model call.",
                "Do not rank MiniMaxM3 versus GPT on predictive/investment quality from current scaffold metrics.",
            ],
        },
        "candidates": classified,
        "other_improvements": [
            {
                "name": "implementation_token_attribution_stamping",
                "current_gap": summary.get(
                    "implementation_token_gap_count", scorecard.get("implementation_token_gap_count")
                ),
                "impact": "Closes helper-lane run-to-cost joins once provider usage is exposed.",
                "next_action": "Stamp session_id, run_id, and model_path on new helper-lane producers; leave provider-cost join gated.",
            },
            {
                "name": "cache_bootstrap_thinning",
                "impact": "Reduces repeated startup/context load pressure from large always-read surfaces.",
                "next_action": "Prefer cached status cards and routed capsules; thin bootstrap surfaces only through separate exact doc diffs.",
            },
            {
                "name": "tool_result_bounding",
                "impact": "Cuts noisy tool-result context without hiding proof.",
                "next_action": "Prefer JSON summaries and artifact paths over full large outputs in helper closeouts.",
            },
            {
                "name": "finance_response_quality_repair",
                "impact": "Unblocks model-quality scorecard from finance source-open residue.",
                "next_action": "Run the existing PM repair lane separately; do not fold finance-domain repair into cron efficiency work.",
            },
        ],
        "warnings": warnings,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Cron Pre-Dispatch Efficiency Plan",
        "",
        f"- Status: `{plan['status']}`",
        f"- Candidates: `{plan['summary']['candidate_count']}`",
        f"- Agent-turn candidates requiring pre-model diff: `{plan['summary']['agent_turn_candidate_count']}`",
        f"- Command-wrapper candidates: `{plan['summary']['command_wrapper_candidate_count']}`",
        f"- Existing changed-only command gates: `{plan['summary'].get('existing_changed_only_command_gate_count', 0)}`",
        f"- Existing changed-input command gates: `{plan['summary'].get('existing_changed_input_command_gate_count', 0)}`",
        f"- API-equivalent benchmark (not an invoice): `{plan['summary'].get('api_equivalent_cost_usd')}` ({plan['summary'].get('api_equivalent_estimate_status')}; {plan['summary'].get('api_equivalent_cost_rows')}/{plan['summary'].get('token_event_count')} events priced)",
        f"- Estimated ChatGPT credits (not an observed debit): `{plan['summary'].get('estimated_chatgpt_credits')}` ({plan['summary'].get('chatgpt_credit_estimate_status')}; {plan['summary'].get('estimated_chatgpt_credit_rows')}/{plan['summary'].get('token_event_count')} events priced)",
        f"- Actual billed cost (owner-entered only): `{plan['summary'].get('actual_billed_cost_usd')}`",
        f"- OAuth quota state / remaining: `{plan['summary'].get('oauth_quota_state')}` / `{plan['summary'].get('oauth_remaining_percent')}`",
        "",
        "## Top Candidates",
        "",
        "| Cron | Payload | Route | Saves model tokens with script-only gate? |",
        "|---|---:|---|---:|",
    ]
    for row in plan["candidates"]:
        lines.append(
            f"| {row['cron_name']} | {row.get('payload_kind') or 'unknown'} | "
            f"{row['implementation_route']} | {row['script_level_prefilter_saves_model_tokens']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "Review-only plan. No cron schedule/config/runtime mutation and no finance/canon/portfolio/execution authority.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-scorecard", type=Path, default=DEFAULT_TOKEN_SCORECARD)
    parser.add_argument("--cron-json", help="Optional live cron JSON export path, or '-' for stdin.")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--output", type=Path, default=DEFAULT_PLAN_JSON)
    parser.add_argument("--md-output", type=Path, default=DEFAULT_PLAN_MD)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scorecard_path = args.token_scorecard if args.token_scorecard.is_absolute() else ROOT / args.token_scorecard
    if not scorecard_path.exists():
        payload = {
            "schema": SCHEMA,
            "generated_at_utc": utc_now(),
            "status": "blocked",
            "errors": [f"missing_token_scorecard:{scorecard_path}"],
            "authority_boundary": AUTHORITY_BOUNDARY,
        }
    else:
        payload = build_plan(load_json(scorecard_path), load_cron_export(args.cron_json), args.limit)
    if args.write:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        atomic_write_json(output, payload)
    if args.write_md and payload.get("status") != "blocked":
        md_output = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
        atomic_write_text(md_output, render_markdown(payload))
    if args.pretty or not args.write:
        print(json.dumps(payload, indent=2, sort_keys=True))
    if args.validate and payload.get("status") == "blocked":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
