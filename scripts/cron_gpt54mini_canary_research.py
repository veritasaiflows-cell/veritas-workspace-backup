#!/usr/bin/env python3
"""Research bounded GPT-5.4 mini canary candidates for OpenClaw cron.

This is a review-only planning surface. It does not edit cron jobs, model pins,
skills, config, or runtime state.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from finance_sql_canon_access import guard_context as finance_sql_canon_guard_context
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
CRON_LEDGER = TMP / "cron-operator-ledger.json"
OUT = TMP / "cron-gpt54mini-canary-research.json"
OUT_MD = TMP / "cron-gpt54mini-canary-research.md"
SCHEMA = "veritas.cron_gpt54mini_canary_research.v1"

OFFICIAL_OPENAI_SOURCES = [
    {
        "name": "GPT-5.4 mini model page",
        "url": "https://developers.openai.com/api/docs/models/gpt-5.4-mini",
        "relevance": "OpenAI positions GPT-5.4 mini as a faster, efficient model for coding, computer use, and subagents.",
    },
    {
        "name": "Introducing GPT-5.4 mini and nano",
        "url": "https://openai.com/index/introducing-gpt-5-4-mini-and-nano/",
        "relevance": "OpenAI says GPT-5.4 mini supports tool use, function calling, web/file search, computer use, and skills with a 400k context window.",
    },
    {
        "name": "OpenAI models guide",
        "url": "https://developers.openai.com/api/docs/models",
        "relevance": "OpenAI recommends smaller variants like GPT-5.4 mini for lower-latency/lower-cost workloads while reserving flagship models for complex reasoning.",
    },
]

PREFERRED_CANARY_NAMES = {
    "WF74 - Learning Loop Telegram Digest",
    "Ops - OTEL Local Digest",
    "Finance - Layered Morning Advancement Audit",
    "Finance - Layered Post-Close Advancement Audit",
    "Finance - Autonomy Spine Readiness Rollup",
    "Macro - Energy and Geopolitical Inputs Refresh",
}

HOLD_KEYWORDS = [
    "submit",
    "cancel",
    "sell",
    "brokerage",
    "account action",
    "money movement",
    "owner approval",
    "paper deployment",
    "capital deployment",
    "weekly printable",
    "--apply",
    "portfolio mutation",
    "canon mutation",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def job_text(job: dict[str, Any]) -> str:
    return json.dumps(job, sort_keys=True, ensure_ascii=False).lower()


def classify_job(job: dict[str, Any]) -> dict[str, Any]:
    name = str(job.get("name") or "")
    text = job_text(job)
    enabled = job.get("enabled") is True
    isolated = str(job.get("session_target") or "").lower() == "isolated"
    hold_reasons: list[str] = []
    if not enabled:
        hold_reasons.append("disabled")
    if not isolated:
        hold_reasons.append("not_isolated")
    for keyword in HOLD_KEYWORDS:
        if keyword in text:
            hold_reasons.append(f"high_consequence_keyword:{keyword}")
    preferred = name in PREFERRED_CANARY_NAMES
    candidate = enabled and isolated and preferred and not hold_reasons
    pilot_only = enabled and isolated and preferred and hold_reasons == []
    return {
        "name": name,
        "enabled": enabled,
        "session_target": job.get("session_target"),
        "schedule": job.get("schedule"),
        "last_status": job.get("last_status"),
        "preferred_candidate": preferred,
        "candidate": candidate,
        "pilot_only": pilot_only,
        "hold_reasons": hold_reasons,
    }


def build_report() -> dict[str, Any]:
    ledger = load(CRON_LEDGER)
    jobs = [as_dict(job) for job in as_list(ledger.get("jobs"))]
    classifications = [classify_job(job) for job in jobs]
    candidates = [row for row in classifications if row["candidate"]]
    holds = [row for row in classifications if row["preferred_candidate"] and not row["candidate"]]
    sql_canon_context = finance_sql_canon_guard_context(consumer=rel(Path(__file__)))
    validation_errors = [] if OFFICIAL_OPENAI_SOURCES and jobs else ["missing_sources_or_cron_jobs"]
    validation_warnings = [] if candidates else ["no_low_risk_candidates_found"]
    if sql_canon_context.get("status") != "ok":
        validation_errors.append("sql_canon_guard_blocked")
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if candidates else "warning",
        "purpose": "Identify low-risk GPT-5.4 mini cron canary candidates for autonomous-assistant/helper research.",
        "official_openai_sources": OFFICIAL_OPENAI_SOURCES,
        "research_read": {
            "model_id": "gpt-5.4-mini",
            "openclaw_model_path": "openai/gpt-5.4-mini",
            "best_fit": [
                "bounded isolated cron canaries",
                "script-owned proof refreshes",
                "JSON artifact inspection",
                "low-risk helper/subagent lanes",
                "coding and computer-use-like support tasks with validator proof",
            ],
            "not_best_fit": [
                "main-session finance judgment",
                "capital approval synthesis",
                "paper/live execution readiness interpretation",
                "broad weekly finance refreshes with approved apply paths",
                "config/auth/runtime mutation",
            ],
        },
        "candidate_jobs": candidates,
        "held_preferred_jobs": holds,
        "summary": {
            "job_count": len(jobs),
            "candidate_count": len(candidates),
            "held_preferred_count": len(holds),
            "first_canary_recommendation": candidates[0]["name"] if candidates else None,
            "next_safe_action": "Switch one low-risk isolated canary to openai/gpt-5.4-mini, let it run naturally, then validate with cron freshness and run history before expanding.",
        },
        "authority_boundary": {
            "review_only": True,
            "cron_model_mutation_allowed": False,
            "cron_schedule_mutation_allowed": False,
            "capital_deployment_allowed": False,
            "trade_or_execution_allowed": False,
            "owner_approval_inferred": False,
        },
        "sql_canon_context": sql_canon_context,
        "validation": {
            "status": "error" if validation_errors else "warning" if validation_warnings else "ok",
            "errors": validation_errors,
            "warnings": validation_warnings,
        },
        "source_artifacts": {
            "cron_operator_ledger": rel(CRON_LEDGER),
        },
    }
    return payload


def render_md(payload: dict[str, Any]) -> str:
    lines = [
        "# GPT-5.4 Mini Cron Canary Research",
        "",
        f"- Generated UTC: `{payload.get('generated_at_utc')}`",
        f"- Status: `{payload.get('status')}`",
        f"- First canary recommendation: `{as_dict(payload.get('summary')).get('first_canary_recommendation')}`",
        "",
        "## Use",
    ]
    for item in as_dict(payload.get("research_read")).get("best_fit", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Hold"])
    for item in as_dict(payload.get("research_read")).get("not_best_fit", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Candidates"])
    for row in as_list(payload.get("candidate_jobs")):
        lines.append(f"- `{as_dict(row).get('name')}`")
    lines.extend(["", "## Sources"])
    for source in as_list(payload.get("official_openai_sources")):
        row = as_dict(source)
        lines.append(f"- {row.get('name')}: {row.get('url')}")
    return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GPT-5.4 mini cron canary research packet.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--output", type=Path, default=OUT)
    parser.add_argument("--md-output", type=Path, default=OUT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_report()
    out = args.output if args.output.is_absolute() else ROOT / args.output
    md_out = args.md_output if args.md_output.is_absolute() else ROOT / args.md_output
    if args.write:
        atomic_write_json(out, payload)
    if args.write_md:
        atomic_write_text(md_out, render_md(payload))
    print(json.dumps({
        "status": payload.get("status"),
        "validation": payload.get("validation"),
        "candidate_count": as_dict(payload.get("summary")).get("candidate_count"),
        "first_canary_recommendation": as_dict(payload.get("summary")).get("first_canary_recommendation"),
        "output": rel(out),
    }, indent=2, sort_keys=True))
    return 1 if args.validate and as_dict(payload.get("validation")).get("status") == "error" else 0


if __name__ == "__main__":
    raise SystemExit(main())
