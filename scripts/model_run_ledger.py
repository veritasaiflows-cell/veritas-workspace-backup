#!/usr/bin/env python3
"""Build a normalized WF74 model/run performance ledger.

This ledger joins current operational proof surfaces into one review-only
artifact. It records model/session attribution when a producer already exposes
it, and marks the gap honestly when it does not.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from concurrent_lane_manager import (
    telemetry_enforcement_applies,
    usage_receipt_store_path,
    verify_usage_source_receipt,
)
from market_data_utils import atomic_write_json, atomic_write_text, load_json_artifact

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
HISTORY = ROOT / "data" / "state-history" / "model-run-ledger.jsonl"
DEFAULT_JSON = TMP / "model-run-ledger-current.json"
DEFAULT_MD = DEFAULT_JSON.with_suffix(".md")
SCHEMA = "wf74.model_run_ledger.v1"

RUNTIME_PERF = TMP / "runtime-performance-scorecard.json"
OTEL_OPS = TMP / "otel-ops-control.json"
CRON_SPARK_CANARY = TMP / "cron-spark-canary-monitor.json"
LANE_REGISTER = TMP / "concurrent-lane-register.json"
OPENCLAW_CMD = Path.home() / "AppData" / "Roaming" / "npm" / "openclaw.cmd"
PRICING = ROOT / "state" / "model-token-pricing.json"

# Cron providers occasionally differ by one or two tokens because usage
# counters are finalized independently. Larger disagreement is not precise
# enough to price, so token semantics fail closed beyond this fixed tolerance.
TOKEN_TOTAL_TOLERANCE_TOKENS = 2
API_EQUIVALENT_COST_LABEL = "API-equivalent benchmark"
VALID_INPUT_TOKEN_SEMANTICS = {"inclusive_cached", "exclusive_cached", "no_cache"}
MODEL_TELEMETRY_ELIGIBILITY_CONTRACT_VERSION = "veritas.model_telemetry_eligibility.v1"

UNSUPPORTED_MODEL_ROUTES = {
    "claude-cli/claude-fable-5": {
        "status": "unsupported_legacy",
        "active_route_countable": False,
        "reason": "Fable is no longer a supported model route; retain historical rows for audit only.",
        "replacement_guidance": "Use openai/gpt-5.5 for main/high-stakes synthesis or an approved bounded helper route.",
    },
}

AUTHORITY_BOUNDARY = {
    "review_only": True,
    "local_only": True,
    "model_ranking_claim": False,
    "investment_correctness_claim": False,
    "owner_approval_inferred": False,
    "portfolio_or_canon_mutation_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "runtime_config_mutation_allowed": False,
    "raw_prompt_or_content_capture_allowed": False,
}


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


def as_num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_token_int(value: Any) -> int | None:
    """Parse an integer token count without truncating floats or booleans."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return int(text)
        except ValueError:
            try:
                number = float(text)
            except ValueError:
                return None
            return int(number) if math.isfinite(number) and number.is_integer() else None
    return None


def normalize_usage_timestamp(value: Any) -> tuple[str | None, str]:
    """Normalize ``entry.ts`` from epoch milliseconds/seconds or aware ISO."""
    if value is None:
        return None, "entry.ts_missing"

    numeric: float | None = None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None, "entry.ts_invalid"
        try:
            numeric = float(text)
        except ValueError:
            iso_value = text[:-1] + "+00:00" if text[-1:] in {"Z", "z"} else text
            try:
                observed = datetime.fromisoformat(iso_value)
            except ValueError:
                return None, "entry.ts_invalid"
            if observed.tzinfo is None:
                return None, "entry.ts_iso8601_missing_timezone"
            normalized = observed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            return normalized, "entry.ts_iso8601"

    if numeric is None or not math.isfinite(numeric):
        return None, "entry.ts_invalid"
    divisor = 1000.0 if abs(numeric) >= 100_000_000_000 else 1.0
    source = "entry.ts_epoch_milliseconds" if divisor == 1000.0 else "entry.ts_epoch_seconds"
    try:
        observed = datetime.fromtimestamp(numeric / divisor, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None, "entry.ts_invalid"
    return observed.isoformat().replace("+00:00", "Z"), source


def classify_token_usage(usage: dict[str, Any]) -> dict[str, Any]:
    """Resolve provider token fields without guessing cached-input semantics.

    ``cached_input_tokens`` is a subset of ``input_tokens``. In contrast,
    ``cache_read_tokens`` is an additional cached bucket when the inclusive
    key is absent. A fixed two-token total tolerance allows only small counter
    finalization differences; larger mismatches disable cost estimation.
    """
    input_present = "input_tokens" in usage
    output_present = "output_tokens" in usage
    total_present = "total_tokens" in usage
    inclusive_present = "cached_input_tokens" in usage
    exclusive_present = "cache_read_tokens" in usage

    input_tokens = as_token_int(usage.get("input_tokens")) if input_present else None
    output_tokens = as_token_int(usage.get("output_tokens")) if output_present else None
    total_tokens = as_token_int(usage.get("total_tokens")) if total_present else None
    inclusive_cached = as_token_int(usage.get("cached_input_tokens")) if inclusive_present else None
    exclusive_cached = as_token_int(usage.get("cache_read_tokens")) if exclusive_present else None

    invalid_reasons: list[str] = []
    ambiguous_reasons: list[str] = []

    if inclusive_present:
        input_token_semantics = "inclusive_cached"
        cached_input_tokens = inclusive_cached
    elif exclusive_present:
        input_token_semantics = "exclusive_cached"
        cached_input_tokens = exclusive_cached
    else:
        input_token_semantics = "no_cache"
        cached_input_tokens = 0

    if inclusive_present and exclusive_present:
        if inclusive_cached is None or exclusive_cached is None or inclusive_cached != exclusive_cached:
            input_token_semantics = "ambiguous"
            ambiguous_reasons.append("cached_input_tokens and cache_read_tokens conflict")

    required_counts = (
        ("input_tokens", input_present, input_tokens),
        ("output_tokens", output_present, output_tokens),
    )
    for label, present, parsed in required_counts:
        if not present:
            ambiguous_reasons.append(f"{label} missing")
        elif parsed is None:
            invalid_reasons.append(f"{label} is not an integer")

    optional_counts = (
        ("total_tokens", total_present, total_tokens),
        ("cached_input_tokens", inclusive_present, inclusive_cached),
        ("cache_read_tokens", exclusive_present, exclusive_cached),
    )
    for label, present, parsed in optional_counts:
        if present and parsed is None:
            invalid_reasons.append(f"{label} is not an integer")

    for label, parsed in (
        ("input_tokens", input_tokens),
        ("output_tokens", output_tokens),
        ("total_tokens", total_tokens),
        ("cached_input_tokens", inclusive_cached),
        ("cache_read_tokens", exclusive_cached),
    ):
        if parsed is not None and parsed < 0:
            invalid_reasons.append(f"{label} is negative")

    if (
        input_token_semantics == "inclusive_cached"
        and input_tokens is not None
        and cached_input_tokens is not None
        and cached_input_tokens > input_tokens
    ):
        invalid_reasons.append("inclusive cached input exceeds input_tokens")

    expected_total_tokens: int | None = None
    total_token_delta: int | None = None
    if input_tokens is not None and output_tokens is not None and cached_input_tokens is not None:
        if input_token_semantics in {"inclusive_cached", "no_cache"}:
            expected_total_tokens = input_tokens + output_tokens
        elif input_token_semantics == "exclusive_cached":
            expected_total_tokens = input_tokens + cached_input_tokens + output_tokens
        if total_tokens is not None and expected_total_tokens is not None:
            total_token_delta = total_tokens - expected_total_tokens
            if abs(total_token_delta) > TOKEN_TOTAL_TOLERANCE_TOKENS:
                invalid_reasons.append(
                    f"total_tokens differs from semantic total by {total_token_delta} tokens"
                )

    if invalid_reasons:
        token_semantics_status = "invalid"
    elif ambiguous_reasons:
        token_semantics_status = "ambiguous"
    else:
        token_semantics_status = "valid"

    uncached_input_tokens: int | None = None
    if token_semantics_status == "valid" and input_tokens is not None and cached_input_tokens is not None:
        if input_token_semantics == "inclusive_cached":
            uncached_input_tokens = input_tokens - cached_input_tokens
        else:
            uncached_input_tokens = input_tokens

    return {
        "total_tokens": total_tokens,
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "cache_read_tokens": exclusive_cached,
        "output_tokens": output_tokens,
        "input_token_semantics": input_token_semantics,
        "uncached_input_tokens": uncached_input_tokens,
        "token_semantics_status": token_semantics_status,
        "token_semantics_reasons": [*invalid_reasons, *ambiguous_reasons],
        "token_total_expected": expected_total_tokens,
        "token_total_delta": total_token_delta,
        "token_total_tolerance_tokens": TOKEN_TOTAL_TOLERANCE_TOKENS,
    }


def stable_id(*parts: Any) -> str:
    seed = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def model_support(model_path: Any) -> dict[str, Any]:
    if not model_path:
        return {
            "status": "unattributed",
            "active_route_countable": False,
            "reason": "No model_path was stamped by the producer.",
        }
    path = str(model_path)
    unsupported = UNSUPPORTED_MODEL_ROUTES.get(path)
    if unsupported:
        return {"model_path": path, **unsupported}
    return {
        "model_path": path,
        "status": "supported_or_unclassified",
        "active_route_countable": True,
        "reason": "Model is not in the unsupported-route blocklist.",
    }


def stamp_model_support(row: dict[str, Any]) -> dict[str, Any]:
    support = model_support(row.get("model_path"))
    row["model_support"] = support
    if support.get("status") == "unsupported_legacy":
        row.setdefault("quality_observations", []).append(
            "unsupported legacy model route; excluded from supported model capacity"
        )
    return row


def load_inputs(
    *,
    cron_job_limit: int = 16,
    cron_run_limit: int = 3,
    cron_list_timeout: int = 30,
    cron_runs_timeout: int = 30,
    skip_cron_runs: bool = False,
) -> dict[str, Any]:
    return {
        "runtime_perf": as_dict(load_json_artifact(RUNTIME_PERF)),
        "otel_ops": as_dict(load_json_artifact(OTEL_OPS)),
        "cron_spark_canary": as_dict(load_json_artifact(CRON_SPARK_CANARY)),
        "cron_runs": load_cron_runs(
            job_limit=cron_job_limit,
            limit_per_job=cron_run_limit,
            list_timeout=cron_list_timeout,
            runs_timeout=cron_runs_timeout,
            skip=skip_cron_runs,
        ),
        "lane_register": as_dict(load_json_artifact(LANE_REGISTER)),
        "pricing": load_pricing(PRICING),
    }


def run_openclaw_json(args: list[str], timeout: int = 30) -> dict[str, Any]:
    if not OPENCLAW_CMD.exists():
        return {"status": "unavailable", "error": f"openclaw.cmd not found: {OPENCLAW_CMD}"}
    try:
        completed = subprocess.run(
            [str(OPENCLAW_CMD), *args],
            cwd=str(ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "error_type": "timeout",
            "timeout_seconds": timeout,
            "error": f"openclaw {' '.join(args)} timed out after {timeout}s",
            "stdout_tail": (exc.stdout or "")[-500:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-500:] if isinstance(exc.stderr, str) else "",
        }
    except Exception as exc:
        return {"status": "unavailable", "error_type": type(exc).__name__, "error": f"openclaw {' '.join(args)} failed: {exc}"}
    if completed.returncode != 0:
        return {
            "status": "unavailable",
            "error_type": "nonzero_returncode",
            "returncode": completed.returncode,
            "error": completed.stderr[-500:] or completed.stdout[-500:],
        }
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return {"status": "unavailable", "error_type": "json_decode", "error": f"openclaw {' '.join(args)} JSON parse failed: {exc}"}
    return payload if isinstance(payload, dict) else {"status": "unavailable", "error": "openclaw payload not object"}


def load_cron_runs(
    *,
    job_limit: int = 16,
    limit_per_job: int = 3,
    list_timeout: int = 30,
    runs_timeout: int = 30,
    skip: bool = False,
) -> dict[str, Any]:
    if skip:
        return {
            "status": "skipped",
            "entries": [],
            "selected_job_count": 0,
            "queried_job_count": 0,
            "error_count": 0,
            "timeout_count": 0,
            "errors": [],
            "skipped": True,
            "job_limit": max(job_limit, 0),
            "run_limit_per_job": max(limit_per_job, 0),
            "list_timeout_seconds": max(list_timeout, 1),
            "runs_timeout_seconds": max(runs_timeout, 1),
        }
    job_limit = max(job_limit, 0)
    limit_per_job = max(limit_per_job, 0)
    list_timeout = max(list_timeout, 1)
    runs_timeout = max(runs_timeout, 1)
    cron_list = run_openclaw_json(["cron", "list", "--json"], timeout=list_timeout)
    if cron_list.get("status") in {"timeout", "unavailable"}:
        return {
            "status": cron_list.get("status"),
            "entries": [],
            "selected_job_count": 0,
            "queried_job_count": 0,
            "error_count": 1,
            "timeout_count": 1 if cron_list.get("status") == "timeout" else 0,
            "errors": [{
                "phase": "cron_list",
                "error_type": cron_list.get("error_type"),
                "error": cron_list.get("error"),
                "timeout_seconds": cron_list.get("timeout_seconds"),
            }],
            "skipped": False,
            "job_limit": job_limit,
            "run_limit_per_job": limit_per_job,
            "list_timeout_seconds": list_timeout,
            "runs_timeout_seconds": runs_timeout,
        }
    jobs = [job for job in as_list(cron_list.get("jobs")) if isinstance(job, dict)]
    selected = []
    for job in jobs:
        payload = as_dict(job.get("payload"))
        if payload.get("kind") == "agentTurn" and payload.get("model") and job.get("enabled") is True:
            selected.append(job)
    selected.sort(key=lambda item: int(as_dict(item.get("state")).get("lastRunAtMs") or 0), reverse=True)
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    timeout_count = 0
    for job in selected[:job_limit]:
        job_id = str(job.get("id") or "")
        if not job_id:
            continue
        runs = run_openclaw_json(["cron", "runs", "--id", job_id, "--limit", str(limit_per_job)], timeout=runs_timeout)
        if "entries" not in runs:
            if runs.get("status") == "timeout":
                timeout_count += 1
            errors.append({
                "job_id": job_id,
                "job_name": job.get("name"),
                "status": runs.get("status"),
                "error_type": runs.get("error_type"),
                "error": runs.get("error"),
                "timeout_seconds": runs.get("timeout_seconds"),
            })
            continue
        entries.extend([row for row in as_list(runs.get("entries")) if isinstance(row, dict)])
    return {
        "status": "warning" if errors else "ok",
        "entries": entries,
        "selected_job_count": len(selected),
        "queried_job_count": min(len(selected), job_limit),
        "error_count": len(errors),
        "timeout_count": timeout_count,
        "errors": errors,
        "skipped": False,
        "job_limit": job_limit,
        "run_limit_per_job": limit_per_job,
        "list_timeout_seconds": list_timeout,
        "runs_timeout_seconds": runs_timeout,
    }


def load_pricing(path: Path) -> dict[str, Any]:
    payload = as_dict(load_json_artifact(path))
    return payload if payload.get("schema") else {}


def resolve_pricing_model(model_path: str | None, pricing: dict[str, Any]) -> tuple[str | None, dict[str, Any], str]:
    if not model_path:
        return None, {}, "missing_model_path"
    models = as_dict(pricing.get("models"))
    if model_path in models:
        return model_path, as_dict(models.get(model_path)), "exact"
    aliases = {**as_dict(pricing.get("aliases")), **as_dict(pricing.get("model_aliases"))}
    candidate = model_path
    visited: set[str] = set()
    while candidate in aliases and candidate not in visited:
        visited.add(candidate)
        candidate = str(aliases[candidate])
        if candidate in models:
            return candidate, as_dict(models.get(candidate)), "alias"
    return candidate, {}, "missing_model_price"


def estimate_cost(
    model_path: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    cached_input_tokens: int | None,
    pricing: dict[str, Any],
    *,
    input_token_semantics: str,
    token_semantics_status: str,
) -> dict[str, Any]:
    def result(
        amount: float | None,
        status: str,
        uncached: int | None = None,
        *,
        pricing_model_path: str | None = None,
        pricing_resolution: str = "not_attempted",
        pricing_context_class: str | None = None,
        pricing_context_input_tokens: int | None = None,
        pricing_context_limit_tokens: int | None = None,
    ) -> dict[str, Any]:
        return {
            "api_equivalent_cost_usd": amount,
            "api_equivalent_cost_label": API_EQUIVALENT_COST_LABEL,
            # Backward-compatible function-level alias used by the existing row builder.
            "estimated_cost": amount,
            "pricing_status": status,
            "uncached_input_tokens": uncached,
            "pricing_model_path": pricing_model_path,
            "pricing_resolution": pricing_resolution,
            "pricing_context_class": pricing_context_class,
            "pricing_context_input_tokens": pricing_context_input_tokens,
            "pricing_context_limit_tokens": pricing_context_limit_tokens,
        }

    if token_semantics_status != "valid" or input_token_semantics not in VALID_INPUT_TOKEN_SEMANTICS:
        return result(None, "invalid_token_semantics")
    if input_tokens is None or output_tokens is None or input_tokens < 0 or output_tokens < 0:
        return result(None, "invalid_token_semantics")
    cached_tokens = cached_input_tokens or 0
    if cached_tokens < 0:
        return result(None, "invalid_token_semantics")
    if input_token_semantics == "inclusive_cached":
        if cached_tokens > input_tokens:
            return result(None, "invalid_token_semantics")
        uncached_input_tokens = input_tokens - cached_tokens
    elif input_token_semantics == "exclusive_cached":
        uncached_input_tokens = input_tokens
    else:
        if cached_tokens != 0:
            return result(None, "invalid_token_semantics")
        uncached_input_tokens = input_tokens

    if not model_path or not pricing:
        return result(None, "missing_pricing_table", uncached_input_tokens)
    pricing_model_path, model, pricing_resolution = resolve_pricing_model(model_path, pricing)
    if not model:
        return result(
            None,
            "missing_model_price",
            uncached_input_tokens,
            pricing_model_path=pricing_model_path,
            pricing_resolution=pricing_resolution,
        )
    context_input_tokens = uncached_input_tokens + cached_tokens
    context_limit = as_token_int(as_dict(pricing.get("pricing_basis")).get("short_context_input_limit_tokens"))
    long_context_rates_available = (
        model.get("long_context_input_per_million") is not None
        and model.get("long_context_output_per_million") is not None
    )
    use_long_context = (
        context_limit is not None
        and context_input_tokens > context_limit
        and long_context_rates_available
    )
    prefix = "long_context_" if use_long_context else ""
    pricing_context_class = "long_context" if use_long_context else "standard_context"
    try:
        input_rate = float(model.get(f"{prefix}input_per_million"))
        cached_rate_value = model.get(f"{prefix}cached_input_per_million")
        cached_rate = float(cached_rate_value) if cached_rate_value is not None else input_rate
        output_rate = float(model.get(f"{prefix}output_per_million"))
    except (TypeError, ValueError):
        return result(
            None,
            "invalid_model_price",
            uncached_input_tokens,
            pricing_model_path=pricing_model_path,
            pricing_resolution=pricing_resolution,
            pricing_context_class=pricing_context_class,
            pricing_context_input_tokens=context_input_tokens,
            pricing_context_limit_tokens=context_limit,
        )
    estimated = (
        (uncached_input_tokens / 1_000_000.0) * input_rate
        + (cached_tokens / 1_000_000.0) * cached_rate
        + (output_tokens / 1_000_000.0) * output_rate
    )
    price_status = str(model.get("status") or "estimated")
    pricing_status = "estimated_proxy" if price_status.startswith("proxy") else "estimated"
    return result(
        round(estimated, 6),
        pricing_status,
        uncached_input_tokens,
        pricing_model_path=pricing_model_path,
        pricing_resolution=pricing_resolution,
        pricing_context_class=pricing_context_class,
        pricing_context_input_tokens=context_input_tokens,
        pricing_context_limit_tokens=context_limit,
    )


def row_base(source: Path, producer: str, run_kind: str, generated_at: str | None) -> dict[str, Any]:
    return stamp_model_support({
        "schema": "wf74.model_run_ledger.row.v1",
        "run_id": stable_id(producer, run_kind, generated_at, rel(source)),
        "producer": producer,
        "run_kind": run_kind,
        "source_artifact": rel(source),
        "source_generated_at_utc": generated_at,
        "workflow_id": "WF74",
        "model_provider": None,
        "model_path": None,
        "thinking": None,
        "session_id": None,
        "cron_job_name": None,
        "status": "unknown",
        "started_at_utc": None,
        "ended_at_utc": None,
        "duration_ms": None,
        "tokens": None,
        "cost": None,
        "tool_count": None,
        "error_type": None,
        "retry_count": None,
        "artifact_paths": [rel(source)],
        "attribution": {
            "model_applicable": False,
            "session_applicable": False,
            "model_present": False,
            "session_present": False,
            # These fields distinguish audit-visible observations from
            # telemetry that is allowed to influence model, cost, latency,
            # reliability, or savings analysis.  Producers must opt in.
            "telemetry_eligible": False,
            "telemetry_credit_status": "not_model_attribution_applicable",
            "telemetry_block_reasons": [],
            "workflow_present": True,
            "producer_present": True,
        },
        "quality_observations": [],
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    })


def lane_telemetry_eligibility(
    lane: dict[str, Any],
    runtime: dict[str, Any],
    *,
    register_path: Path = LANE_REGISTER,
) -> dict[str, Any]:
    """Fail closed for model-lane performance telemetry after cutover.

    The lane register remains an audit record even when it cannot prove a
    source-to-lane usage join.  It must not, however, become a denominator or
    numerator for model/cost/latency/reliability/savings evidence merely
    because a model path or a completed status was written into the lane.
    """
    model_path = runtime.get("model_path") or lane.get("model_path")
    if not model_path:
        return {
            "required": False,
            "eligible": False,
            "status": "not_model_lane",
            "reasons": ["model_path_missing"],
        }
    if telemetry_enforcement_applies(lane, runtime):
        # Negative or absent producer claims can only deny telemetry credit;
        # they can never grant it.  Short-circuit those lanes before reopening
        # receipts and authoritative sources.  Affirmative claims still need
        # the full source-verification path below every time.
        reasons = [
            str(value)
            for value in as_list(runtime.get("usage_credit_block_reasons"))
            if value
        ]
        if runtime.get("usage_creditable") is not True:
            reasons.append("usage_creditable_not_true")
        if runtime.get("source_reverification_status") != "verified":
            reasons.append("source_reverification_not_verified")
        if reasons:
            return {
                "required": True,
                "eligible": False,
                "status": "blocked_unverified_usage_source",
                "reasons": sorted(set(reasons)),
            }
        reasons = verify_usage_source_receipt(
            lane,
            runtime,
            usage_receipt_store_path(register_path),
        )
        if reasons:
            return {
                "required": True,
                "eligible": False,
                "status": "blocked_unverified_usage_source",
                "reasons": sorted(set(reasons)),
            }
        return {
            "required": True,
            "eligible": True,
            "status": "creditable_source_reverified",
            "reasons": [],
        }
    # Historic lane observations are retained, but the new performance
    # cohort does not silently backfill them into a savings claim.
    return {
        "required": False,
        "eligible": False,
        "status": "historical_lane_audit_only",
        "reasons": ["pre_cutover_lane_observation"],
    }


def model_row_scoring_eligible(row: dict[str, Any]) -> bool:
    """Return whether a normalized row may feed model performance metrics.

    Direct cron/canary producers preserve their existing source-owned
    semantics.  Concurrent-lane rows require the explicit reverified marker;
    treating a missing marker as false prevents stale ledger artifacts from
    restoring an unverified lane to a model cohort.
    """
    attribution = as_dict(row.get("attribution"))
    if attribution.get("model_applicable") is not True:
        return False
    if row.get("producer") == "concurrent_lane_manager":
        return attribution.get("telemetry_eligible") is True
    return attribution.get("telemetry_eligible") is not False


def runtime_rows(runtime: dict[str, Any]) -> list[dict[str, Any]]:
    if not runtime:
        return []
    generated = str(runtime.get("generated_at_utc") or "")
    commands = [row for row in as_list(runtime.get("commands")) if isinstance(row, dict)]
    if commands:
        rows = []
        for command in commands:
            row = row_base(RUNTIME_PERF, "runtime_performance_scorecard", "validator_command", generated)
            row["run_id"] = stable_id("runtime_performance_scorecard", command.get("name"), generated, command.get("command"))
            row["status"] = command.get("status")
            row["duration_ms"] = command.get("duration_ms")
            row["artifact_paths"] = [rel(RUNTIME_PERF), *[str(path) for path in as_list(command.get("artifacts"))]]
            row["quality_observations"].append("validator command timed and status captured; model/session not stamped by producer")
            rows.append(stamp_model_support(row))
        return rows

    summary = as_dict(runtime.get("summary"))
    row = row_base(RUNTIME_PERF, "runtime_performance_scorecard", "artifact_only_summary", generated)
    row["status"] = runtime.get("status")
    row["duration_ms"] = summary.get("total_duration_ms")
    row["tool_count"] = summary.get("checks_total")
    row["quality_observations"].append("artifact-only runtime summary present; individual command rows absent")
    return [stamp_model_support(row)]


def otel_rows(otel: dict[str, Any]) -> list[dict[str, Any]]:
    if not otel:
        return []
    generated = str(otel.get("generated_at_utc") or "")
    summary = as_dict(otel.get("summary"))
    row = row_base(OTEL_OPS, "otel_ops_control", "local_otel_window", generated)
    row["status"] = otel.get("status")
    row["duration_ms"] = None
    row["tool_count"] = summary.get("event_count")
    row["quality_observations"].extend([
        f"metric_batches={summary.get('metric_batches')}",
        f"trace_batches={summary.get('trace_batches')}",
        f"reported_spans={summary.get('reported_spans')}",
        "collector batch telemetry has no model/session/token/cost attribution yet",
    ])
    return [stamp_model_support(row)]


def spark_canary_rows(canary: dict[str, Any]) -> list[dict[str, Any]]:
    if not canary:
        return []
    generated = str(canary.get("generated_at_utc") or "")
    rows = []
    for job in [row for row in as_list(canary.get("jobs")) if isinstance(row, dict)]:
        row = row_base(CRON_SPARK_CANARY, "cron_spark_canary_monitor", "cron_canary_job", generated)
        row["run_id"] = stable_id("cron_spark_canary_monitor", job.get("name"), job.get("model"), job.get("last_started_at_utc"), job.get("last_status"))
        row["workflow_id"] = str(job.get("workflow_id") or "WF74")
        row["model_path"] = job.get("model") or canary.get("model_under_test")
        row["model_provider"] = str(row["model_path"]).split("/", 1)[0] if row["model_path"] else None
        row["thinking"] = job.get("thinking") or canary.get("required_thinking")
        row["cron_job_name"] = job.get("name")
        row["status"] = job.get("last_status") or ("pending" if job.get("pending_first_canary_run") else canary.get("status"))
        row["started_at_utc"] = job.get("last_started_at_utc")
        row["ended_at_utc"] = job.get("last_finished_at_utc")
        row["duration_ms"] = job.get("last_duration_ms")
        row["error_type"] = job.get("last_error_type") or job.get("last_error")
        row["attribution"]["model_present"] = bool(row["model_path"])
        row["attribution"]["model_applicable"] = True
        row["attribution"]["session_applicable"] = False
        row["attribution"]["session_present"] = False
        row["attribution"]["telemetry_eligible"] = True
        row["attribution"]["telemetry_credit_status"] = "source_owned_non_lane_operational_metadata"
        row["quality_observations"].append(
            "bounded cron canary operational evidence only; no finance-correctness or model-ranking claim"
        )
        if job.get("duration_ratio_vs_baseline") is not None:
            row["quality_observations"].append(f"duration_ratio_vs_baseline={job.get('duration_ratio_vs_baseline')}")
        rows.append(stamp_model_support(row))
    return rows


def cron_run_rows(cron_runs: dict[str, Any], pricing: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    pricing = pricing or {}
    for entry in [row for row in as_list(cron_runs.get("entries")) if isinstance(row, dict)]:
        if entry.get("action") != "finished":
            continue
        model = entry.get("model")
        provider = entry.get("provider")
        usage = as_dict(entry.get("usage"))
        model_path = f"{provider}/{model}" if provider and model and "/" not in str(model) else model
        token_usage = classify_token_usage(usage)
        usage_at_utc, usage_time_source = normalize_usage_timestamp(entry.get("ts"))
        cost = estimate_cost(
            model_path,
            token_usage["input_tokens"],
            token_usage["output_tokens"],
            token_usage["cached_input_tokens"],
            pricing,
            input_token_semantics=token_usage["input_token_semantics"],
            token_semantics_status=token_usage["token_semantics_status"],
        )
        row = {
            "schema": "wf74.model_run_ledger.row.v1",
            "run_id": str(entry.get("runId") or stable_id("cron_runs", entry.get("jobId"), entry.get("ts"))),
            "producer": "openclaw_cron_runs",
            "run_kind": "cron_agent_turn",
            "source_artifact": "gateway:openclaw cron runs",
            "source_generated_at_utc": None,
            "usage_at_utc": usage_at_utc,
            "usage_time_source": usage_time_source,
            "workflow_id": None,
            "model_provider": provider,
            "model_path": model_path,
            "thinking": None,
            "session_id": entry.get("sessionId"),
            "session_key": entry.get("sessionKey"),
            "cron_job_name": entry.get("jobName"),
            "cron_job_id": entry.get("jobId"),
            "status": entry.get("status"),
            "started_at_utc": None,
            "ended_at_utc": None,
            "duration_ms": entry.get("durationMs"),
            "tokens": token_usage["total_tokens"],
            "input_tokens": token_usage["input_tokens"],
            "cached_input_tokens": token_usage["cached_input_tokens"],
            "cache_read_tokens": token_usage["cache_read_tokens"],
            "output_tokens": token_usage["output_tokens"],
            "input_token_semantics": token_usage["input_token_semantics"],
            "uncached_input_tokens": token_usage["uncached_input_tokens"],
            "token_semantics_status": token_usage["token_semantics_status"],
            "token_semantics_reasons": token_usage["token_semantics_reasons"],
            "token_total_expected": token_usage["token_total_expected"],
            "token_total_delta": token_usage["token_total_delta"],
            "token_total_tolerance_tokens": token_usage["token_total_tolerance_tokens"],
            "api_equivalent_cost_usd": cost["api_equivalent_cost_usd"],
            "api_equivalent_cost_label": cost["api_equivalent_cost_label"],
            "api_equivalent_cost_is_invoice": False,
            "api_equivalent_pricing_status": cost["pricing_status"],
            "pricing_model_path": cost.get("pricing_model_path"),
            "pricing_resolution": cost.get("pricing_resolution"),
            "pricing_context_class": cost.get("pricing_context_class"),
            "pricing_context_input_tokens": cost.get("pricing_context_input_tokens"),
            "pricing_context_limit_tokens": cost.get("pricing_context_limit_tokens"),
            # Legacy aliases retained additively for schema-v1 consumers.
            "cost": cost["api_equivalent_cost_usd"],
            "cost_semantics": "deprecated_alias_of_api_equivalent_cost_usd",
            "cost_pricing_status": cost["pricing_status"],
            "cost_estimate_only": True,
            "tool_count": None,
            "error_type": entry.get("errorType") or entry.get("error"),
            "retry_count": None,
            "artifact_paths": [],
            "attribution": {
                "model_applicable": True,
                "session_applicable": True,
                "model_present": bool(model or provider),
                "session_present": bool(entry.get("sessionId")),
                "telemetry_eligible": True,
                "telemetry_credit_status": "direct_gateway_cron_usage",
                "telemetry_block_reasons": [],
                "workflow_present": False,
                "producer_present": True,
            },
            "quality_observations": [
                "cron run history provides provider/model/session/token/duration attribution when present",
                (
                    f"input_token_semantics={token_usage['input_token_semantics']} "
                    f"status={token_usage['token_semantics_status']}"
                ),
            ],
            "authority_boundary": AUTHORITY_BOUNDARY.copy(),
        }
        rows.append(stamp_model_support(row))
    return rows


def lane_register_rows(register: dict[str, Any], *, register_path: Path = LANE_REGISTER) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    generated = str(register.get("generated_at_utc") or register.get("updated_at_utc") or "")
    for lane in [row for row in as_list(register.get("lanes")) if isinstance(row, dict)]:
        runtime = as_dict(lane.get("runtime"))
        if not runtime and not lane.get("started_at_utc"):
            continue
        model_path = runtime.get("model_path") or lane.get("model_path")
        session_id = runtime.get("session_id") or lane.get("session_id")
        session_key = runtime.get("session_key") or lane.get("session_key")
        session_label = runtime.get("session_label") or lane.get("owner")
        completed = lane.get("completed_at_utc") or lane.get("ended_at_utc") or lane.get("updated_at_utc")
        row = row_base(LANE_REGISTER, "concurrent_lane_manager", "workspace_lane", generated)
        row["run_id"] = str(runtime.get("run_id") or stable_id("lane", lane.get("lane_id"), lane.get("started_at_utc"), completed))
        row["workflow_id"] = lane.get("workflow_id")
        row["model_path"] = model_path
        row["model_provider"] = str(model_path).split("/", 1)[0] if isinstance(model_path, str) and "/" in model_path else runtime.get("model_provider")
        row["model_attribution_source"] = runtime.get("model_attribution_source") or ("lane_runtime_metadata" if model_path else None)
        row["session_id"] = session_id
        row["session_key"] = session_key
        row["session_label"] = session_label
        row["session_attribution_source"] = runtime.get("session_attribution_source") or ("lane_runtime_metadata" if (session_id or session_key or session_label) else None)
        row["task_name"] = runtime.get("task_name") or lane.get("workstream_id")
        row["status"] = lane.get("status")
        row["started_at_utc"] = lane.get("started_at_utc")
        row["ended_at_utc"] = completed
        row["duration_ms"] = None
        row["tool_count"] = len(as_list(lane.get("acceptance_commands")))
        row["artifact_paths"] = [rel(LANE_REGISTER), *[str(path) for path in as_list(lane.get("proof_artifacts"))]]
        telemetry = lane_telemetry_eligibility(lane, runtime, register_path=register_path)
        row["attribution"]["model_applicable"] = telemetry["eligible"] is True
        row["attribution"]["session_applicable"] = telemetry["eligible"] is True
        row["attribution"]["model_present"] = bool(model_path)
        row["attribution"]["session_present"] = bool(session_id or session_key or session_label)
        row["attribution"]["telemetry_eligible"] = telemetry["eligible"] is True
        row["attribution"]["telemetry_credit_status"] = telemetry["status"]
        row["attribution"]["telemetry_block_reasons"] = telemetry["reasons"]
        row["attribution"]["telemetry_contract_version"] = MODEL_TELEMETRY_ELIGIBILITY_CONTRACT_VERSION
        row["attribution"]["usage_creditable"] = runtime.get("usage_creditable") is True
        row["telemetry_requirement"] = {
            "post_cutover_model_lane": telemetry["required"],
            "audit_visible": True,
            "performance_cost_latency_reliability_savings_eligible": telemetry["eligible"] is True,
        }
        row["quality_observations"].extend([
            "lane register provides run/session/task attribution for helper, PM, and implementation producers",
            "model_path is present only when the producer stamped it; missing model_path remains an attribution gap",
        ])
        if telemetry["eligible"] is not True:
            row["quality_observations"].append(
                "lane remains audit-visible but is excluded from model/cost/latency/reliability/savings evidence until usage source reverification succeeds"
            )
        rows.append(stamp_model_support(row))
    return rows


ATTRIBUTION_WINDOW_DAYS = 30


def row_observed_at(row: dict[str, Any]) -> str | None:
    for key in ("usage_at_utc", "started_at_utc", "ended_at_utc", "source_generated_at_utc"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def recent_attribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Coverage over the trailing window only.

    All-time coverage never recovers from rows written before producers stamped
    model_path, so it understates whether attribution works *now* and points
    remediation at unrecoverable history instead of the real gap.
    """
    cutoff = datetime.now(timezone.utc).timestamp() - ATTRIBUTION_WINDOW_DAYS * 86400
    applicable = 0
    present = 0
    undated = 0
    for row in rows:
        if not as_dict(row.get("attribution")).get("model_applicable"):
            continue
        observed = row_observed_at(row)
        if not observed:
            undated += 1
            continue
        try:
            stamp = datetime.fromisoformat(observed.replace("Z", "+00:00")).timestamp()
        except ValueError:
            undated += 1
            continue
        if stamp < cutoff:
            continue
        applicable += 1
        if as_dict(row.get("attribution")).get("model_present"):
            present += 1
    return {
        "window_days": ATTRIBUTION_WINDOW_DAYS,
        "applicable_rows": applicable,
        "attributed_rows": present,
        "coverage": round(present / applicable, 4) if applicable else 0.0,
        "undated_applicable_rows": undated,
        "interpretation": (
            "Recent coverage measures whether producers stamp model_path today. "
            "All-time coverage includes pre-instrumentation rows that cannot be backfilled."
        ),
    }


def build_ledger(inputs: dict[str, Any]) -> dict[str, Any]:
    rows = [
        *runtime_rows(inputs["runtime_perf"]),
        *otel_rows(inputs["otel_ops"]),
        *spark_canary_rows(inputs["cron_spark_canary"]),
        *cron_run_rows(inputs["cron_runs"], inputs.get("pricing")),
        *lane_register_rows(inputs["lane_register"]),
    ]
    model_applicable = sum(1 for row in rows if model_row_scoring_eligible(row))
    session_applicable = sum(
        1 for row in rows
        if model_row_scoring_eligible(row) and as_dict(row.get("attribution")).get("session_applicable")
    )
    model_present = sum(
        1 for row in rows
        if model_row_scoring_eligible(row) and as_dict(row.get("attribution")).get("model_present")
    )
    model_observed = sum(1 for row in rows if as_dict(row.get("attribution")).get("model_present"))
    session_present = sum(
        1 for row in rows
        if model_row_scoring_eligible(row) and as_dict(row.get("attribution")).get("session_present")
    )
    session_observed = sum(1 for row in rows if as_dict(row.get("attribution")).get("session_present"))
    ok_rows = sum(1 for row in rows if row.get("status") == "ok")
    blocked_rows = sum(1 for row in rows if row.get("status") in {"blocked", "error", "critical"})
    unsupported_rows = [row for row in rows if as_dict(row.get("model_support")).get("status") == "unsupported_legacy"]
    supported_capacity_rows = [
        row for row in rows
        if (
            as_dict(row.get("model_support")).get("active_route_countable") is True
            and model_row_scoring_eligible(row)
        )
    ]
    cron_rows = [row for row in rows if row.get("producer") == "openclaw_cron_runs"]
    recent = recent_attribution(rows)
    return {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "ok" if rows else "warning",
        "posture": "review_only_operational_evidence_not_model_ranker",
        "sources": {
            "runtime_performance_scorecard": rel(RUNTIME_PERF),
            "otel_ops_control": rel(OTEL_OPS),
            "cron_spark_canary_monitor": rel(CRON_SPARK_CANARY),
            "cron_runs": "gateway:openclaw cron runs --limit 50",
            "lane_register": rel(LANE_REGISTER),
            "model_token_pricing": rel(PRICING),
        },
        "summary": {
            "row_count": len(rows),
            "ok_rows": ok_rows,
            "blocked_or_error_rows": blocked_rows,
            "attribution_applicable_rows": model_applicable,
            "session_attribution_applicable_rows": session_applicable,
            "model_attributed_rows": model_present,
            "model_observed_audit_rows": model_observed,
            "session_attributed_rows": session_present,
            "session_observed_audit_rows": session_observed,
            "model_attribution_coverage": round(model_present / len(rows), 4) if rows else 0.0,
            "session_attribution_coverage": round(session_present / len(rows), 4) if rows else 0.0,
            "model_attribution_applicable_coverage": round(model_present / model_applicable, 4) if model_applicable else 0.0,
            "model_attribution_recent_window": recent,
            "model_attribution_recent_coverage": recent["coverage"],
            "session_attribution_applicable_coverage": round(session_present / session_applicable, 4) if session_applicable else 0.0,
            "cost_rows": sum(1 for row in rows if row.get("cost") is not None),
            "api_equivalent_cost_rows": sum(1 for row in rows if row.get("api_equivalent_cost_usd") is not None),
            "token_rows": sum(1 for row in rows if row.get("tokens") is not None),
            "token_semantics_valid_rows": sum(1 for row in cron_rows if row.get("token_semantics_status") == "valid"),
            "token_semantics_invalid_rows": sum(1 for row in cron_rows if row.get("token_semantics_status") == "invalid"),
            "token_semantics_ambiguous_rows": sum(1 for row in cron_rows if row.get("token_semantics_status") == "ambiguous"),
            "lane_register_rows": sum(1 for row in rows if row.get("producer") == "concurrent_lane_manager"),
            "lane_audit_only_uncredited_rows": sum(
                1 for row in rows
                if row.get("producer") == "concurrent_lane_manager"
                and as_dict(row.get("attribution")).get("telemetry_eligible") is not True
            ),
            "supported_model_capacity_rows": len(supported_capacity_rows),
            "unsupported_legacy_model_rows": len(unsupported_rows),
            "unsupported_legacy_model_paths": sorted({
                str(row.get("model_path")) for row in unsupported_rows if row.get("model_path")
            }),
            "cron_run_collection_status": as_dict(inputs.get("cron_runs")).get("status"),
            "cron_run_collection_selected_job_count": as_dict(inputs.get("cron_runs")).get("selected_job_count"),
            "cron_run_collection_queried_job_count": as_dict(inputs.get("cron_runs")).get("queried_job_count"),
            "cron_run_collection_error_count": as_dict(inputs.get("cron_runs")).get("error_count"),
            "cron_run_collection_timeout_count": as_dict(inputs.get("cron_runs")).get("timeout_count"),
            "cron_run_collection_job_limit": as_dict(inputs.get("cron_runs")).get("job_limit"),
            "cron_run_collection_run_limit_per_job": as_dict(inputs.get("cron_runs")).get("run_limit_per_job"),
        },
        "rows": rows,
        "gaps": [
            "session_id/session_label is now stamped when producers write lane runtime metadata",
            "API-equivalent cost is estimated only when cron token semantics reconcile inside the fixed two-token tolerance",
            "runtime validator commands are operational timings, not model-attribution-applicable agent turns",
            "post-cutover model lanes remain audit-visible but are excluded from model/cost/latency/reliability/savings evidence until their usage source is independently reverified",
            "direct cron and canary rows preserve source-owned non-lane operational semantics",
            "unsupported legacy model rows remain visible for audit but do not count as supported model capacity",
        ],
        "model_route_guard": {
            "unsupported_model_routes": sorted(UNSUPPORTED_MODEL_ROUTES),
            "unsupported_legacy_model_row_count": len(unsupported_rows),
            "supported_model_capacity_row_count": len(supported_capacity_rows),
            "rule": "Unsupported legacy routes are retained for audit and excluded from supported model capacity.",
        },
        "authority_boundary": AUTHORITY_BOUNDARY.copy(),
    }


def validate(ledger: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if ledger.get("authority_boundary", {}).get(key) is not expected:
            findings.append({"severity": "critical", "detail": f"authority boundary mismatch: {key}"})
    for row in as_list(ledger.get("rows")):
        boundary = as_dict(row.get("authority_boundary"))
        for key in ("model_ranking_claim", "investment_correctness_claim", "owner_approval_inferred", "paper_or_live_execution_allowed"):
            if boundary.get(key) is not False:
                findings.append({"severity": "critical", "detail": f"row {row.get('run_id')} widens authority: {key}"})
        if row.get("model_path") and not as_dict(row.get("attribution")).get("model_present"):
            findings.append({"severity": "warning", "detail": f"row {row.get('run_id')} has model_path but attribution flag is false"})
        if row.get("producer") == "openclaw_cron_runs":
            semantics_status = row.get("token_semantics_status")
            if semantics_status not in {"valid", "invalid", "ambiguous"}:
                findings.append({"severity": "critical", "detail": f"row {row.get('run_id')} has invalid token_semantics_status"})
            if row.get("input_token_semantics") not in {*VALID_INPUT_TOKEN_SEMANTICS, "ambiguous"}:
                findings.append({"severity": "critical", "detail": f"row {row.get('run_id')} has invalid input_token_semantics"})
            if row.get("cost") != row.get("api_equivalent_cost_usd"):
                findings.append({"severity": "critical", "detail": f"row {row.get('run_id')} legacy cost alias mismatch"})
            if row.get("api_equivalent_cost_label") != API_EQUIVALENT_COST_LABEL:
                findings.append({"severity": "critical", "detail": f"row {row.get('run_id')} missing API-equivalent canonical label"})
            if semantics_status != "valid" and (
                row.get("api_equivalent_cost_usd") is not None or row.get("cost") is not None
            ):
                findings.append({"severity": "critical", "detail": f"row {row.get('run_id')} prices invalid or ambiguous token semantics"})
            if semantics_status in {"invalid", "ambiguous"}:
                findings.append({
                    "severity": "warning",
                    "detail": f"row {row.get('run_id')} token semantics are {semantics_status}; API-equivalent estimate is null",
                })
            if row.get("usage_at_utc") and not str(row.get("usage_time_source") or "").startswith("entry.ts_"):
                findings.append({"severity": "critical", "detail": f"row {row.get('run_id')} usage timestamp lacks entry.ts provenance"})
        support = as_dict(row.get("model_support"))
        if support.get("status") == "unsupported_legacy":
            findings.append({
                "severity": "warning",
                "detail": (
                    f"row {row.get('run_id')} uses unsupported legacy model {row.get('model_path')}; "
                    "historical audit only, excluded from supported capacity"
                ),
            })
    if int(as_dict(ledger.get("summary")).get("row_count") or 0) == 0:
        findings.append({"severity": "warning", "detail": "no model/run rows available"})
    cron_status = as_dict(ledger.get("summary")).get("cron_run_collection_status")
    cron_errors = int(as_dict(ledger.get("summary")).get("cron_run_collection_error_count") or 0)
    cron_timeouts = int(as_dict(ledger.get("summary")).get("cron_run_collection_timeout_count") or 0)
    if cron_status in {"warning", "timeout", "unavailable"} or cron_errors or cron_timeouts:
        findings.append({
            "severity": "warning",
            "detail": (
                "cron run history collection had errors or timeouts; model rows remain usable but cron-history attribution is incomplete"
            ),
        })
    critical = sum(1 for finding in findings if finding["severity"] == "critical")
    warnings = sum(1 for finding in findings if finding["severity"] == "warning")
    return {"status": "critical" if critical else ("warning" if warnings else "ok"), "critical": critical, "warnings": warnings, "findings": findings}


def render_md(ledger: dict[str, Any]) -> str:
    summary = as_dict(ledger.get("summary"))
    lines = [
        "# Model Run Ledger",
        "",
        f"- Generated: {ledger.get('generated_at_utc')}",
        f"- Status: {ledger.get('status')}",
        f"- Rows: {summary.get('row_count')}",
        f"- Model attribution coverage, all rows: {summary.get('model_attribution_coverage')}",
        f"- Session attribution coverage, all rows: {summary.get('session_attribution_coverage')}",
        f"- Model attribution coverage, applicable rows: {summary.get('model_attribution_applicable_coverage')}",
        f"- Session attribution coverage, applicable rows: {summary.get('session_attribution_applicable_coverage')}",
        f"- Model attribution coverage, last {as_dict(summary.get('model_attribution_recent_window')).get('window_days')}d: {summary.get('model_attribution_recent_coverage')}",
        f"- Supported model capacity rows: {summary.get('supported_model_capacity_rows')}",
        f"- Unsupported legacy model rows: {summary.get('unsupported_legacy_model_rows')}",
        "",
        "## Gaps",
    ]
    for gap in as_list(ledger.get("gaps")):
        lines.append(f"- {gap}")
    return "\n".join(lines) + "\n"


def append_history(ledger: dict[str, Any], validation: dict[str, Any]) -> None:
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "generated_at_utc": ledger.get("generated_at_utc"),
        "status": ledger.get("status"),
        "validation_status": validation.get("status"),
        **as_dict(ledger.get("summary")),
    }
    with HISTORY.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build WF74 model/run performance ledger")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-md", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON))
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--cron-job-limit", type=int, default=16)
    parser.add_argument("--cron-run-limit", type=int, default=3)
    parser.add_argument("--cron-list-timeout", type=int, default=30)
    parser.add_argument("--cron-runs-timeout", type=int, default=30)
    parser.add_argument("--skip-cron-runs", action="store_true")
    args = parser.parse_args(argv)

    ledger = build_ledger(load_inputs(
        cron_job_limit=args.cron_job_limit,
        cron_run_limit=args.cron_run_limit,
        cron_list_timeout=args.cron_list_timeout,
        cron_runs_timeout=args.cron_runs_timeout,
        skip_cron_runs=args.skip_cron_runs,
    ))
    validation = validate(ledger)
    ledger["validation"] = validation

    out = Path(args.json_out)
    if args.write:
        atomic_write_json(out, ledger)
        append_history(ledger, validation)
        if args.write_md:
            atomic_write_text(out.with_suffix(".md"), render_md(ledger))

    if not args.quiet:
        summary = as_dict(ledger.get("summary"))
        print(
            f"status={ledger['status']} validation={validation['status']} rows={summary.get('row_count')} "
            f"model_attr={summary.get('model_attribution_coverage')} session_attr={summary.get('session_attribution_coverage')}"
        )
        for finding in validation["findings"]:
            print(f"  [{finding['severity']}] {finding['detail']}")

    if args.validate and validation["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
