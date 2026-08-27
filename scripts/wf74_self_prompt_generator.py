#!/usr/bin/env python3
"""Generate a review-only self-prompt packet for the next Veritas main session.

The self-prompt is a structured set of questions the model should ask itself
before producing a serious answer or recommendation. It is generated from
existing metadata-only telemetry and critique surfaces; it does not capture or
inspect raw prompts, responses, tool payloads, secrets, or system prompts. It
does not mutate code, cron, config, skills, canon/portfolio, or infer approval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_JSON = TMP / "wf74-self-prompt-review-packet.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "veritas.wf74_self_prompt_review_packet.v1"

TELEMETRY_CRITIQUE = TMP / "wf74-telemetry-critique.json"
MODEL_LEARNING_LEDGER = TMP / "model-learning-metadata-ledger.json"
WF74_OPPORTUNITY_QUEUE = TMP / "wf74-improvement-opportunity-queue.json"
WF74_DECISION_DOCKET = TMP / "wf74-decision-docket.json"
WF74_OUTCOME_EVAL = TMP / "wf74-outcome-eval-suite-v2.json"
IMPROVEMENT_LEDGER = TMP / "improvement-ledger-current.json"
WORKFLOW_ADVANCEMENT = TMP / "workflow-advancement-scorecard.json"
WF87_READINESS = TMP / "wf87-v2-readiness-rollup.json"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "external_export_allowed": False,
    "raw_prompt_capture_allowed": False,
    "raw_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "content_capture_allowed": False,
    "collector_config_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
    "auto_apply_allowed": False,
}

PROMPT_SECTIONS = [
    {
        "id": "truth_and_freshness",
        "title": "Truth and Freshness",
        "weight": 10,
        "questions": [
            "Did I inspect the live owner artifact, validator, or current file before claiming current status, prices, dates, or workflow completion?",
            "Did I name the source timestamp/freshness when the claim could influence capital, workflow closure, or runtime trust?",
            "Did I downgrade confidence when artifacts are stale, partial, missing, contradictory, or warning-heavy?",
        ],
    },
    {
        "id": "authority_boundary",
        "title": "Authority Boundary",
        "weight": 10,
        "questions": [
            "Did I separate review-ready/deployable from owner approval?",
            "Did I state that clean validators/scorecards do not authorize trades, paper orders, account actions, cash/sleeve/risk-rule changes, or owner approval?",
            "Did I route any paper order through WF67 guardrails and any live action through explicit live-action approval only?",
        ],
    },
    {
        "id": "continuity_routing",
        "title": "Continuity Routing",
        "weight": 8,
        "questions": [
            "Did I classify this correction or finding into the correct owner surface: daily memory, durable memory, operating rule, environment rule, domain rule, automation candidate, or workflow residue?",
            "Did I avoid creating a second memory or control surface without explicit owner approval?",
            "Did I cite file paths and line ranges so Randall can verify the claim?",
        ],
    },
    {
        "id": "actionability",
        "title": "Actionability",
        "weight": 7,
        "questions": [
            "Did the output become a concrete proposal, file update, validator, script, SOP, or queue item instead of remaining chat-only?",
            "Are next actions named with owners and acceptance criteria?",
        ],
    },
    {
        "id": "helper_lane_discipline",
        "title": "Helper Lane Discipline",
        "weight": 6,
        "questions": [
            "If I spawned a helper, does it have bounded scope, explicit allowed_writes, stop lines, and acceptance proof?",
            "Did I verify the concurrent-lane register before and after helper closeout?",
        ],
    },
    {
        "id": "oversized_output_avoidance",
        "title": "Oversized Output Avoidance",
        "weight": 5,
        "questions": [
            "Did I use targeted excerpts, rg/search, or SQL cockpit instead of pasting full large artifacts when a smaller bounded read would suffice?",
            "Did I cite artifact paths and summarize rather than duplicating volatile generated content?",
        ],
    },
    {
        "id": "finance_specific_gates",
        "title": "Finance-Specific Gates",
        "weight": 9,
        "questions": [
            "Did I start from the SQL-canon guard and the exact owner artifacts before making finance claims?",
            "Did I include thesis, bull/bear, earnings, key metrics, risks, moat, entry/invalidation, and price-vs-band context?",
            "Did I label the answer as review-only and owner-gated for capital/execution decisions?",
        ],
    },
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _resolve(path: Path, tmp_dir: Path | None) -> Path:
    if tmp_dir is None:
        return path
    return tmp_dir / path.name


def load_inputs(tmp_dir: Path | None = None) -> dict[str, Any]:
    return {
        "telemetry_critique": as_dict(load_json_artifact(_resolve(TELEMETRY_CRITIQUE, tmp_dir))),
        "model_learning": as_dict(load_json_artifact(_resolve(MODEL_LEARNING_LEDGER, tmp_dir))),
        "opportunity_queue": as_dict(load_json_artifact(_resolve(WF74_OPPORTUNITY_QUEUE, tmp_dir))),
        "decision_docket": as_dict(load_json_artifact(_resolve(WF74_DECISION_DOCKET, tmp_dir))),
        "outcome_eval": as_dict(load_json_artifact(_resolve(WF74_OUTCOME_EVAL, tmp_dir))),
        "improvement_ledger": as_dict(load_json_artifact(_resolve(IMPROVEMENT_LEDGER, tmp_dir))),
        "workflow_advancement": as_dict(load_json_artifact(_resolve(WORKFLOW_ADVANCEMENT, tmp_dir))),
        "wf87_readiness": as_dict(load_json_artifact(_resolve(WF87_READINESS, tmp_dir))),
    }


def extract_high_critiques(critique: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in as_list(critique.get("critiques")) if c.get("severity") in {"high", "attention"}]


def extract_top_opportunities(queue: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    opportunities = as_list(queue.get("opportunities"))
    return sorted(
        opportunities,
        key=lambda o: o.get("priority", 0),
        reverse=True,
    )[:limit]


def extract_open_improvements(ledger: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    items = [i for i in as_list(ledger.get("items")) if i.get("status") not in {"complete", "closed"}]
    return sorted(items, key=lambda i: i.get("priority", 0), reverse=True)[:limit]


def extract_workflow_blockers(adv: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "workflow_id": s.get("workflow_id"),
            "blockers": as_list(s.get("blockers")),
            "next_action": s.get("next_action"),
        }
        for s in as_list(adv.get("signals"))
        if s.get("signal") == "blocked" or s.get("status") in {"blocked_collecting_data", "continue_accrual"}
    ]


def generate_focused_questions(critiques: list[dict[str, Any]]) -> list[str]:
    extra: list[str] = []
    categories = {c.get("category") for c in critiques}
    severities = {c.get("category"): c.get("severity") for c in critiques}
    if "source_open_recurrence" in categories:
        extra.append("Before declaring finance response-quality clean, did I verify that wf78_source_open_patch_orchestrator ran before finance_response_quality_slice and that blocker metrics are split by root cause?")
    if "workflow_maturity_blocker" in categories:
        extra.append("Before claiming a workflow is advanced, did I check whether child maturity gates are still blocked and treat that as a visible blocker rather than a quiet rollup success?")
    if "low_telemetry_coverage" in categories:
        extra.append("Before making a model-ranking or cost-optimization claim, did I verify token/cost coverage is above the minimum threshold and label any inference as speculative?")
    if "helper_scope_bloat" in categories:
        extra.append("If I used a helper lane, did I confirm it has explicit allowed_writes, stop lines, and acceptance proof, and did I verify the lane register after closeout?")
    if "oversized_read" in categories:
        extra.append("Did I avoid oversized reads/pastes by using targeted excerpts, rg/search, or the SQL cockpit and citing paths?")
    if "latency_spike" in categories:
        extra.append("If I noticed a latency spike, did I treat it as a diagnostic signal rather than evidence of model superiority or inferiority without per-model/session attribution?")
    # Also surface attention-level signals with explicit severity so the prompt
    # reflects the strongest non-high signals when no high-severity rows exist.
    if "latency_spike" in severities and severities["latency_spike"] == "attention":
        extra.append("For any slow cron/model runs surfaced as attention, did I verify whether the duration is expected (e.g., large batch) or a regression before routing it?")
    if "low_telemetry_coverage" in severities and severities["low_telemetry_coverage"] == "attention":
        extra.append("Did I label any model-ranking, cost, or capacity claim as speculative because token/cost telemetry coverage is below 10%?")
    if "workflow_maturity_blocker" in severities and severities["workflow_maturity_blocker"] == "attention":
        extra.append("Did I explicitly call out workflow maturity/child-gate blockers instead of allowing a green parent status to mask them?")
    return extra


def build_self_prompt(inputs: dict[str, Any] | None = None, *, tmp_dir: Path | None = None) -> dict[str, Any]:
    if inputs is None:
        inputs = load_inputs(tmp_dir=tmp_dir)
    critiques = extract_high_critiques(inputs["telemetry_critique"])
    opportunities = extract_top_opportunities(inputs["opportunity_queue"])
    open_improvements = extract_open_improvements(inputs["improvement_ledger"])
    workflow_blockers = extract_workflow_blockers(inputs["workflow_advancement"])
    focused = generate_focused_questions(critiques)

    # Variant ID reflects the combination of source artifacts and top signals.
    variant_seed = "|".join([
        inputs["telemetry_critique"].get("generated_at_utc", ""),
        str(len(critiques)),
        str(len(opportunities)),
        str(len(workflow_blockers)),
    ])
    prompt_id = stable_id("wf74-self-prompt", variant_seed, utc_now())
    variant_id = stable_id("wf74-prompt-variant", variant_seed)

    full_text_lines = [
        "Before producing the next material answer or recommendation, ask yourself:",
        "",
    ]
    for section in PROMPT_SECTIONS:
        full_text_lines.append(f"## {section['title']} (weight {section['weight']}/10)")
        full_text_lines.append("")
        for q in section["questions"]:
            full_text_lines.append(f"- {q}")
        full_text_lines.append("")
    if focused:
        full_text_lines.append("## Telemetry-Driven Focus Questions")
        full_text_lines.append("")
        for q in focused:
            full_text_lines.append(f"- {q}")
        full_text_lines.append("")
    if workflow_blockers:
        full_text_lines.append("## Active Workflow Blockers to Keep Visible")
        full_text_lines.append("")
        for wb in workflow_blockers:
            full_text_lines.append(f"- {wb['workflow_id']}: {', '.join(wb['blockers']) or 'maturity accrual in progress'}")
        full_text_lines.append("")
    full_text_lines.append("## Stop Lines")
    full_text_lines.append("")
    full_text_lines.append("- Do not infer owner approval from clean validators, green scorecards, or ranked queues.")
    full_text_lines.append("- Do not submit, cancel, replace, or execute paper/live orders without Randall's exact approval and WF67 guard proof.")
    full_text_lines.append("- Do not mutate canon/portfolio/cash/sizing/risk/execution state outside approved gates.")
    full_text_lines.append("- Do not capture raw prompts, responses, tool payloads, headers, secrets, or credentials.")

    return {
        "prompt_id": prompt_id,
        "variant_id": variant_id,
        "generated_at_utc": utc_now(),
        "full_text": "\n".join(full_text_lines),
        "sections": [
            {
                "id": section["id"],
                "title": section["title"],
                "weight": section["weight"],
                "question_count": len(section["questions"]),
            }
            for section in PROMPT_SECTIONS
        ],
        "focused_question_count": len(focused),
        "workflow_blocker_count": len(workflow_blockers),
        "source_critique_categories": [c.get("category") for c in critiques],
        "source_opportunity_ids": [o.get("opportunity_id") for o in opportunities],
        "source_open_improvement_ids": [i.get("improvement_id") for i in open_improvements],
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    inputs = load_inputs(tmp_dir=None)
    self_prompt = build_self_prompt(inputs)

    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok",
        "purpose": "Review-only self-prompt packet for the next Veritas main session, generated from metadata-only telemetry and critique surfaces.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "self_prompt": self_prompt,
        "summary": {
            "section_count": len(self_prompt["sections"]),
            "total_question_count": sum(s["question_count"] for s in self_prompt["sections"]) + self_prompt["focused_question_count"],
            "focused_question_count": self_prompt["focused_question_count"],
            "workflow_blocker_count": self_prompt["workflow_blocker_count"],
            "source_critique_count": len(self_prompt["source_critique_categories"]),
            "source_opportunity_count": len(self_prompt["source_opportunity_ids"]),
            "next_safe_action": "Use this self-prompt at the start of the next main-session material turn; do not treat it as owner approval or execution authority.",
        },
        "sources": [rel(p) for p in [
            TELEMETRY_CRITIQUE, MODEL_LEARNING_LEDGER, WF74_OPPORTUNITY_QUEUE,
            WF74_DECISION_DOCKET, WF74_OUTCOME_EVAL, IMPROVEMENT_LEDGER,
            WORKFLOW_ADVANCEMENT, WF87_READINESS,
        ]],
    }
    payload["validation"] = validate_payload(payload)
    if payload["validation"]["errors"]:
        payload["status"] = "blocked"
    return payload


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    sp = as_dict(payload.get("self_prompt"))
    if not sp.get("full_text"):
        errors.append("missing_self_prompt_full_text")
    if not sp.get("prompt_id"):
        errors.append("missing_prompt_id")
    if not sp.get("variant_id"):
        errors.append("missing_variant_id")
    for key in AUTHORITY_BOUNDARY:
        if AUTHORITY_BOUNDARY[key] is False and payload.get("authority_boundary", {}).get(key) is True:
            errors.append(f"authority_boundary_true:{key}")
    return {"status": "blocked" if errors else "ok", "errors": errors, "warnings": warnings}


def render_md(payload: dict[str, Any]) -> str:
    sp = as_dict(payload.get("self_prompt"))
    lines = [
        f"# WF74 Self-Prompt Review Packet",
        "",
        f"- Status: `{payload['status']}`",
        f"- Generated: {payload['generated_at_utc']}",
        f"- Prompt ID: `{sp.get('prompt_id')}`",
        f"- Variant ID: `{sp.get('variant_id')}`",
        "",
        "## Summary",
        "",
        f"- Sections: {payload['summary']['section_count']}",
        f"- Total questions: {payload['summary']['total_question_count']}",
        f"- Focused questions from telemetry: {payload['summary']['focused_question_count']}",
        f"- Active workflow blockers referenced: {payload['summary']['workflow_blocker_count']}",
        f"- Source critiques: {payload['summary']['source_critique_count']}",
        "",
        "## Self-Prompt Text",
        "",
        "```",
        sp.get("full_text", ""),
        "```",
        "",
        "## Authority Boundary",
        "",
        "Review-only and metadata-only. No raw capture, no code/config/cron mutation, no canon/portfolio/trade authority, no owner-approval inference.",
    ]
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the WF74 self-prompt review packet.")
    parser.add_argument("--out", default=str(DEFAULT_JSON))
    parser.add_argument("--md", default=str(DEFAULT_MD))
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    if args.write:
        atomic_write_json(out_path, payload)
        atomic_write_text(args.md, render_md(payload))
    if args.validate and payload["validation"]["errors"]:
        print(json.dumps(payload["validation"], indent=2))
        return 1
    print(json.dumps({
        "status": payload["status"],
        "path": rel(out_path),
        "prompt_id": payload["self_prompt"]["prompt_id"],
        "total_questions": payload["summary"]["total_question_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
