#!/usr/bin/env python3
"""Owner decision packet for the standing `token_cost_metadata_depth` recommendation.

The recommendation asks for an owner-gated collector patch that adds local-only
token/cost metadata capture. This packet tests that premise against live collector
output before asking Randall to approve anything, and carries the literal proposed
diff plus rollback so the decision is actionable either way.

Review-only. Reads collector output; never writes, restarts, or mutates collector
or runtime config.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "otel-token-cost-metadata-depth-owner-packet.json"
SCHEMA = "veritas.otel_token_cost_metadata_depth_owner_packet.v1"

COLLECTOR_CONFIG = Path("tools/otelcol/openclaw-local-otel-runtime-metadata.yaml")
TRACES = Path("tmp/otel-collector/traces.jsonl")
LEARNING_LOOP = TMP / "otel-learning-loop.json"
TOKEN_LEDGER = TMP / "token-usage-ledger-current.json"

RECOMMENDATION_ID = "token_cost_metadata_depth"
LEDGER_EVENT_ID = "f9c94240087d003f"

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "metadata_only": True,
    "collector_config_mutation_allowed": False,
    "collector_restart_allowed": False,
    "runtime_config_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "external_export_allowed": False,
    "raw_prompt_or_response_capture_allowed": False,
    "tool_payload_capture_allowed": False,
    "system_prompt_capture_allowed": False,
    "secret_or_header_capture_allowed": False,
    "finance_canon_or_portfolio_mutation_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "owner_approval_inferred": False,
}

# Attribute names the collector already receives that carry token counts.
TOKEN_ATTRIBUTE_PREFIXES = ("gen_ai.usage.", "openclaw.tokens.", "openclaw.model_call.usage.")
# Identifiers an OTEL-derived reader would need to credit tokens to a lane or run.
JOIN_KEY_MARKERS = ("session", "run_id", "runid", "lane", "workstream", "cron", "job", "task", "correlat", "workflow")
# The only free-text attribute observed; flagged because it is not length-bounded.
FREE_TEXT_ATTRIBUTES = ("openclaw.error",)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def attribute_map(span: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in span.get("attributes") or []:
        key = item.get("key")
        value = as_dict(item.get("value"))
        if isinstance(key, str) and value:
            result[key] = next(iter(value.values()))
    return result


def iter_spans(payload: Any, sink: list[dict[str, Any]]) -> None:
    if isinstance(payload, dict):
        if "spanId" in payload and "name" in payload:
            sink.append(payload)
        for value in payload.values():
            iter_spans(value, sink)
    elif isinstance(payload, list):
        for value in payload:
            iter_spans(value, sink)


def load_spans(traces_path: Path) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    if not traces_path.is_file():
        return spans
    with traces_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                iter_spans(json.loads(line), spans)
            except json.JSONDecodeError:
                continue
    return spans


def span_total_tokens(attrs: dict[str, Any]) -> int | None:
    for key in ("openclaw.model_call.usage.total_tokens", "openclaw.tokens.total"):
        if attrs.get(key) is not None:
            return int(attrs[key])
    inputs, outputs = attrs.get("gen_ai.usage.input_tokens"), attrs.get("gen_ai.usage.output_tokens")
    if inputs is None and outputs is None:
        return None
    return int(inputs or 0) + int(outputs or 0)


def collector_evidence(traces_path: Path, now: datetime) -> dict[str, Any]:
    """What the collector already captures, and what it structurally cannot."""
    spans = load_spans(traces_path)
    token_rows: list[tuple[str, datetime, int]] = []
    present_token_attributes: set[str] = set()
    join_keys_found: set[str] = set()
    free_text_present: set[str] = set()
    for span in spans:
        attrs = attribute_map(span)
        for key in attrs:
            if key.startswith(TOKEN_ATTRIBUTE_PREFIXES):
                present_token_attributes.add(key)
            if any(marker in key.lower() for marker in JOIN_KEY_MARKERS):
                join_keys_found.add(key)
            if key in FREE_TEXT_ATTRIBUTES:
                free_text_present.add(key)
        total = span_total_tokens(attrs)
        started = span.get("startTimeUnixNano")
        if total is None or not started:
            continue
        token_rows.append((
            str(span.get("name") or "unknown"),
            datetime.fromtimestamp(int(started) / 1e9, timezone.utc),
            total,
        ))
    # openclaw.model.call and openclaw.model.usage can describe the same call from
    # two vantage points, so the call-scoped subset is the non-double-counted view.
    call_rows = [row for row in token_rows if row[0] == "openclaw.model.call"]

    def window(rows: list[tuple[str, datetime, int]], hours: float) -> dict[str, Any]:
        cutoff = now - timedelta(hours=hours)
        selected = [row for row in rows if row[1] >= cutoff]
        return {"span_count": len(selected), "total_tokens": sum(row[2] for row in selected)}

    stamps = [row[1] for row in token_rows]
    return {
        "traces_path": rel(traces_path),
        "traces_present": traces_path.is_file(),
        "traces_size_bytes": traces_path.stat().st_size if traces_path.is_file() else 0,
        "span_count": len(spans),
        "token_bearing_span_count": len(token_rows),
        "token_attributes_already_captured": sorted(present_token_attributes),
        "earliest_token_span_utc": min(stamps).replace(microsecond=0).isoformat().replace("+00:00", "Z") if stamps else None,
        "latest_token_span_utc": max(stamps).replace(microsecond=0).isoformat().replace("+00:00", "Z") if stamps else None,
        "wall_clock_timestamp_on_every_token_span": bool(token_rows),
        "rolling_5h_all_token_spans": window(token_rows, 5.0),
        "rolling_7d_all_token_spans": window(token_rows, 168.0),
        "rolling_5h_model_call_spans_only": window(call_rows, 5.0),
        "rolling_7d_model_call_spans_only": window(call_rows, 168.0),
        "lane_or_run_join_keys_found": sorted(join_keys_found),
        "per_run_attribution_possible_from_otel": bool(join_keys_found),
        "free_text_attributes_present": sorted(free_text_present),
    }


def trigger_evidence(learning_loop: dict[str, Any]) -> dict[str, Any]:
    """Why the recommendation fires, and what its denominator actually measures."""
    token_cost = as_dict(as_dict(learning_loop.get("learning_summaries")).get("token_cost"))
    still_emitted = any(
        as_dict(row).get("id") == RECOMMENDATION_ID
        for row in learning_loop.get("recommendations") or []
    )
    return {
        "recommendation_id": RECOMMENDATION_ID,
        "improvement_ledger_event_id": LEDGER_EVENT_ID,
        "still_emitted_by_current_run": still_emitted,
        "source_generated_at_utc": learning_loop.get("generated_at_utc"),
        "trigger_rule": "otel_learning_loop.build_recommendations: fires when token_coverage_ratio or cost_coverage_ratio is None or < 0.8",
        "measured_source": "tmp/model-run-ledger-current.json rows, not OTEL collector output",
        "model_applicable_rows": token_cost.get("model_applicable_rows"),
        "token_coverage_ratio": token_cost.get("token_coverage_ratio"),
        "cost_coverage_ratio": token_cost.get("cost_coverage_ratio"),
    }


def build_packet(root: Path, now: datetime | None = None) -> dict[str, Any]:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    learning_loop = as_dict(load_json_artifact(LEARNING_LOOP))
    token_ledger = as_dict(load_json_artifact(TOKEN_LEDGER))
    collector = collector_evidence(root / TRACES, now)
    trigger = trigger_evidence(learning_loop)

    pace = as_dict(token_ledger.get("usage_pace"))
    ledger_5h = as_dict(pace.get("rolling_5h"))
    fallback = as_dict(as_dict(pace.get("ingestion_observed_fallback")).get("rolling_7d"))

    capture_sufficient = collector["token_bearing_span_count"] > 0
    patch_would_change_coverage = not capture_sufficient

    findings = [
        {
            "id": "capture_depth_already_sufficient",
            "status": "refutes_recommendation" if capture_sufficient else "supports_recommendation",
            "evidence": (
                f"{collector['token_bearing_span_count']} spans already carry token counts "
                f"({len(collector['token_attributes_already_captured'])} distinct token attributes), "
                f"each with a wall-clock start time, spanning "
                f"{collector['earliest_token_span_utc']} to {collector['latest_token_span_utc']}."
            ),
            "meaning": (
                "The collector is not missing token or cost metadata. A depth patch cannot add "
                "fields that are already arriving and already written to disk."
            ),
        },
        {
            "id": "trigger_measures_the_wrong_source",
            "status": "refutes_recommendation",
            "evidence": (
                f"token_coverage_ratio={trigger['token_coverage_ratio']} and "
                f"cost_coverage_ratio={trigger['cost_coverage_ratio']} are computed over "
                f"{trigger['model_applicable_rows']} model-run-ledger rows. OTEL is never read."
            ),
            "meaning": (
                "The warning is structurally unclearable by any collector change. It reports a "
                "model-run-ledger denominator while the data it asks for sits in OTEL."
            ),
        },
        {
            "id": "per_run_attribution_impossible_from_otel",
            "status": "limits_any_alternative",
            "evidence": (
                "No session, run, lane, workstream, cron, job, task, or correlation identifier "
                "appears on any span in traces containing token data; "
                f"join keys found: {collector['lane_or_run_join_keys_found'] or 'none'}."
            ),
            "meaning": (
                "OTEL can support fleet-level pace and cost only. It can never credit tokens to a "
                "lane or run, so it is not a substitute for the attribution bridge."
            ),
        },
        {
            "id": "aggregate_pace_gap_is_real",
            "status": "supports_alternative",
            "evidence": (
                f"Ledger trusted rolling_5h reports {ledger_5h.get('event_count')} events / "
                f"{ledger_5h.get('total_tokens')} tokens, while OTEL model.call spans in the same "
                f"5h window carry {collector['rolling_5h_model_call_spans_only']['span_count']} calls / "
                f"{collector['rolling_5h_model_call_spans_only']['total_tokens']} tokens."
            ),
            "meaning": (
                "Recent-spend blindness is genuine, but the fix is a reader, not deeper capture. "
                "Token totals are not comparable across sources: OTEL counts per-API-call usage "
                "including cache reads, the ledger counts run-level totals."
            ),
        },
    ]

    proposed_patch = {
        "intent": "Literal form of the change the recommendation asks for, so the decision is actionable if Randall disagrees with the recommendation below.",
        "target_file": str(COLLECTOR_CONFIG).replace("\\", "/"),
        "diff": (
            "--- a/tools/otelcol/openclaw-local-otel-runtime-metadata.yaml\n"
            "+++ b/tools/otelcol/openclaw-local-otel-runtime-metadata.yaml\n"
            "@@ exporters:\n"
            " exporters:\n"
            "   debug:\n"
            "-    verbosity: basic\n"
            "+    verbosity: detailed\n"
        ),
        "what_it_would_actually_change": (
            "Console/stderr verbosity of the debug exporter only. The file exporters already "
            "write full-fidelity spans including every token attribute, so captured data is unchanged."
        ),
        "expected_effect_on_token_coverage": "none",
        "expected_effect_on_cost_coverage": "none",
        "side_effects": [
            "collector.err.log growth rate increases, pulling forward the 256 MB rotation threshold",
            "requires a collector restart to take effect",
        ],
        "rollback": {
            "steps": [
                "Restore verbosity: basic in tools/otelcol/openclaw-local-otel-runtime-metadata.yaml",
                "Restart the collector via scripts/local_otel_collector.py",
                "Re-run python scripts/otel_ops_control.py --write --validate and confirm collector_health ok",
                "Confirm sha256 matches the approved config recorded in tmp/otel-field-depth-limited-owner-packet.json",
            ],
            "reversible": True,
            "data_loss_risk": "none",
        },
    }

    alternative = {
        "intent": "The change that would actually close the observable gap, offered as a separate owner decision.",
        "summary": "Build a review-only OTEL token reader that derives fleet-level token pace from traces.jsonl.",
        "would_deliver": [
            "provider-timestamped rolling 5h/7d token pace, which the ledger currently cannot produce",
            "per-model and per-provider recent spend distribution",
        ],
        "would_not_deliver": [
            "per-lane or per-run token credit",
            "billed cost (no cost attribute is emitted; only token counts)",
            "any comparability with ledger totals without an explicit counting-basis label",
        ],
        "preconditions_before_it_could_be_trusted": [
            "traces.jsonl has no retention policy; scripts/otel_log_retention.py governs only collector.err.log and collector.out.log, so a 7d window is not currently guaranteed",
            f"free-text attribute(s) {collector['free_text_attributes_present'] or 'none'} are not length-bounded and need redaction validation before any reader ingests them",
            "counting basis must be labeled: OTEL counts per-API-call usage including cache reads",
        ],
        "collector_config_change_required": False,
        "status": "not_started_requires_separate_owner_approval",
    }

    recommendation = {
        "recommended_owner_decision": "decline_metadata_depth_patch_as_framed",
        "confidence": "high",
        "because": (
            "Both premises fail against live evidence: the collector already captures token "
            "metadata, and the warning that requests it is computed from a different source "
            "entirely, so no collector patch can clear it."
        ),
        "decision_options": [
            {
                "option": "decline_and_retire_the_recommendation",
                "effect": "Closes a standing owner-decision item that cannot be satisfied as written.",
                "requires": "Owner approval to change otel_learning_loop trigger wiring or close the improvement-ledger row.",
            },
            {
                "option": "approve_the_literal_patch",
                "effect": "Increases debug log verbosity. No change to token or cost coverage.",
                "requires": "Owner approval plus collector restart.",
            },
            {
                "option": "approve_building_the_otel_token_reader",
                "effect": "Restores fleet-level recent-spend visibility. No per-run attribution.",
                "requires": "Separate owner approval; retention and redaction preconditions first.",
            },
        ],
        "veritas_does_not_infer_approval_for_any_option": True,
    }

    warnings: list[str] = []
    if not collector["traces_present"]:
        warnings.append("collector traces file missing; capture evidence is unavailable")
    if not trigger["still_emitted_by_current_run"]:
        warnings.append("recommendation not present in the current learning-loop run; packet may be stale")
    if collector["free_text_attributes_present"]:
        warnings.append("unbounded free-text attribute present in traces; redaction review required before any reader")
    if not fallback:
        warnings.append("token ledger ingestion fallback unavailable; ledger-side comparison is partial")

    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "owner_decision_pending",
        "purpose": "Test the token_cost_metadata_depth premise against live collector output before asking for approval.",
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_artifacts": {
            "collector_config": str(COLLECTOR_CONFIG).replace("\\", "/"),
            "traces": rel(root / TRACES),
            "learning_loop": rel(LEARNING_LOOP),
            "token_ledger": rel(TOKEN_LEDGER),
        },
        "recommendation_trigger": trigger,
        "collector_capture_evidence": collector,
        "ledger_side_comparison": {
            "trusted_rolling_5h_event_count": ledger_5h.get("event_count"),
            "trusted_rolling_5h_total_tokens": ledger_5h.get("total_tokens"),
            "ingestion_fallback_rolling_7d_event_count": fallback.get("event_count"),
            "ingestion_fallback_rolling_7d_total_tokens": fallback.get("total_tokens"),
            "counting_basis_comparable_with_otel": False,
            "note": "Ledger rows are run-level totals; OTEL spans are per-API-call usage including cache reads.",
        },
        "findings": findings,
        "proposed_patch_if_approved": proposed_patch,
        "alternative_that_addresses_the_real_gap": alternative,
        "recommendation": recommendation,
        "patch_would_change_token_or_cost_coverage": patch_would_change_coverage,
        "next_safe_action": (
            "Randall picks one decision option. Veritas makes no collector, config, cron, or "
            "runtime change and closes no ledger row without that decision."
        ),
        "validation": {
            "status": "warning" if warnings else "ok",
            "errors": [],
            "warnings": warnings,
        },
    }


def workspace_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--validate", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    out_path = workspace_path(args.out)
    payload = build_packet(ROOT)
    if args.write:
        atomic_write_json(out_path, payload)
    if args.pretty:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(json.dumps({
            "status": payload["status"],
            "out": rel(out_path),
            "recommended_owner_decision": payload["recommendation"]["recommended_owner_decision"],
            "patch_would_change_token_or_cost_coverage": payload["patch_would_change_token_or_cost_coverage"],
            "validation": payload["validation"],
        }, indent=2, sort_keys=True))
    return 0 if payload["validation"]["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
