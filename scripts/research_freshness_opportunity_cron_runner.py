#!/usr/bin/env python3
"""Stable changed-only runner for the WF60 research freshness cron."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from market_data_utils import atomic_write_json, load_json_artifact
from finance_sql_canon_access import guard_context as finance_sql_canon_guard_context


ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"
DEFAULT_OUT = TMP / "research-freshness-opportunity-cron-runner.json"
DEFAULT_CACHE = TMP / "research-freshness-opportunity-cron-cache.json"
SCHEMA = "veritas.research_freshness_opportunity_cron_runner.v1"
CACHE_SCHEMA = "veritas.research_freshness_opportunity_cron_cache.v1"
DEFAULT_MAX_SKIP_AGE_HOURS = 20.0

AUTHORITY_BOUNDARY = {
    "review_only_runner": True,
    "promotion_queue_reconciler_may_apply_stale_band_prose_only": True,
    "cron_state_mutation_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "runtime_config_mutation_allowed": False,
    "canon_or_portfolio_mutation_allowed": False,
    "portfolio_state_mutation_allowed": False,
    "deployment_state_mutation_allowed": False,
    "watchlist_promotion_allowed": False,
    "capital_deployment_allowed": False,
    "paper_or_live_execution_allowed": False,
    "brokerage_or_account_action_allowed": False,
    "money_movement_allowed": False,
    "owner_approval_inferred": False,
}

SOURCE_DIGEST_PATHS = [
    "tmp/deployment-check.json",
    "tmp/daily-price-trend-signals.json",
    "tmp/sector-correlation-check.json",
    "tmp/current-regime-analog-match.json",
    "tmp/portfolio-config.json",
    "06. Playbooks/Promotion Review Queue.md",
]

STEPS = [
    ("macro_signal_spine", [sys.executable, "scripts\\macro_signal_spine.py", "--write", "--validate", "--timeout", "12", "--max-workers", "4"], 180),
    ("macro_judgment_draft", [sys.executable, "scripts\\macro_judgment_draft.py", "--write", "--validate"], 180),
    ("ticker_monitoring_performance", [sys.executable, "scripts\\ticker_monitoring_performance.py", "--window", "post-close"], 180),
    ("promotion_review_queue_reconciler", [sys.executable, "scripts\\promotion_review_queue_reconciler.py", "--apply", "--write", "--write-md", "--validate"], 180),
    ("sector_expansion_board", [sys.executable, "scripts\\sector_expansion_board.py", "--window", "post-close"], 180),
    ("sector_dashboard_suite", [sys.executable, "scripts\\sector_dashboard_suite.py"], 240),
    ("research_freshness_opportunity_review", [sys.executable, "scripts\\research_freshness_opportunity_review.py", "--window", "post-close"], 180),
    ("small_mid_cap_regime_feed", [sys.executable, "scripts\\small_mid_cap_regime_feed.py", "--window", "post-close"], 360),
    ("json_sql_promotion_index", [sys.executable, "scripts\\json_sql_promotion_index.py", "--write", "--write-md", "--validate"], 240),
    ("cron_operator_ledger", [sys.executable, "scripts\\cron_operator_ledger.py", "--write", "--write-md", "--validate"], 240),
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


def parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load(path: Path) -> dict[str, Any]:
    payload = load_json_artifact(path)
    return payload if isinstance(payload, dict) else {}


def tail(text: str | None, limit: int = 1600) -> str:
    value = text or ""
    return value[-limit:] if len(value) > limit else value


def file_digest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": rel(path), "exists": False, "sha256": None, "size": None}
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return {
        "path": rel(path),
        "exists": True,
        "sha256": digest.hexdigest(),
        "size": path.stat().st_size,
    }


def source_digest(paths: list[str] | None = None) -> dict[str, Any]:
    entries = [file_digest(ROOT / item) for item in (paths or SOURCE_DIGEST_PATHS)]
    digest = hashlib.sha256(json.dumps(entries, sort_keys=True).encode("utf-8")).hexdigest()
    return {"digest": digest, "entries": entries}


def artifact(path: str) -> dict[str, Any]:
    full = ROOT / path
    payload = load(full)
    return {
        "path": path,
        "exists": full.exists(),
        "status": payload.get("status") or payload.get("overall"),
        "validation_status": as_dict(payload.get("validation")).get("status"),
        "generated_at_utc": payload.get("generated_at_utc") or payload.get("generated_at"),
        "authority": payload.get("authority_boundary") or payload.get("authority"),
    }


def fresh_enough(path: Path, max_age_hours: float) -> bool:
    payload = load(path)
    generated = parse_dt(payload.get("generated_at_utc") or payload.get("generated_at"))
    if not generated:
        return False
    age_hours = (datetime.now(timezone.utc) - generated).total_seconds() / 3600
    return age_hours <= max_age_hours


def can_skip_changed_only(cache_path: Path, current_digest: str, max_age_hours: float) -> tuple[bool, str]:
    cache = load(cache_path)
    previous = as_dict(cache.get("last_completed_run"))
    if cache.get("schema") != CACHE_SCHEMA:
        return False, "cache_missing_or_wrong_schema"
    if previous.get("source_digest") != current_digest:
        return False, "source_digest_changed"
    if previous.get("status") not in {"ok", "warning", "degraded", "skipped_unchanged"}:
        return False, f"previous_status_not_skippable:{previous.get('status')}"
    review = TMP / "research-freshness-opportunity-review.json"
    if not fresh_enough(review, max_age_hours):
        return False, "previous_review_not_fresh_enough"
    return True, "source_digest_unchanged_and_previous_review_fresh"


def run_step(name: str, command: list[str], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "name": name,
            "command": command,
            "returncode": None,
            "ok": False,
            "duration_ms": round((time.perf_counter() - started) * 1000, 3),
            "error": f"timeout after {timeout}s",
            "stdout_tail": tail(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr_tail": tail(exc.stderr if isinstance(exc.stderr, str) else ""),
        }
    return {
        "name": name,
        "command": command,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
        "stdout_tail": tail(proc.stdout),
        "stderr_tail": tail(proc.stderr),
    }


def build_summary() -> dict[str, Any]:
    review = load(TMP / "research-freshness-opportunity-review.json")
    wf61 = load(TMP / "small-mid-cap-regime-feed.json")
    promotion = load(TMP / "promotion-review-queue-reconciler.json")
    sql_index = load(TMP / "json-sql-promotion-index.json")
    return {
        "macro_judgment_status": load(TMP / "macro-judgment-draft.json").get("status"),
        "ticker_monitoring_status": load(TMP / "ticker-monitoring-performance.json").get("status"),
        "promotion_queue_reconciler_status": promotion.get("status"),
        "sector_expansion_board_status": load(TMP / "sector-expansion-board.json").get("status"),
        "research_review_status": review.get("status"),
        "research_review_candidate_count": as_dict(review.get("opportunity_review")).get("candidate_count"),
        "wf61_status": wf61.get("status"),
        "json_sql_promotion_index_status": sql_index.get("status"),
        "json_sql_validation_status": as_dict(sql_index.get("validation")).get("status"),
    }


def validate(payload: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, expected in AUTHORITY_BOUNDARY.items():
        if as_dict(payload.get("authority_boundary")).get(key) is not expected:
            errors.append(f"authority_boundary_{key}_not_{str(expected).lower()}")
    failed_steps = [step.get("name") for step in as_list(payload.get("steps")) if not as_dict(step).get("ok")]
    if failed_steps:
        errors.append(f"failed_steps:{','.join(str(item) for item in failed_steps)}")
    summary = as_dict(payload.get("summary"))
    if summary.get("research_review_status") == "blocked":
        errors.append("research_review_blocked")
    if summary.get("wf61_status") == "blocked":
        errors.append("wf61_blocked")
    if summary.get("json_sql_validation_status") not in {"ok", None}:
        errors.append(f"json_sql_validation_status:{summary.get('json_sql_validation_status')}")
    review_auth = as_dict(artifact("tmp/research-freshness-opportunity-review.json").get("authority"))
    for key in ("capital_action_allowed", "portfolio_mutation_allowed", "trade_execution_allowed", "owner_approval_inference_allowed"):
        if review_auth.get(key) is not False:
            errors.append(f"research_review_authority_widened:{key}")
    wf61_auth = as_dict(artifact("tmp/small-mid-cap-regime-feed.json").get("authority"))
    for key in ("capital_action_allowed", "portfolio_mutation_allowed", "trade_execution_allowed", "owner_approval_inference_allowed"):
        if wf61_auth.get(key) is not False:
            errors.append(f"wf61_authority_widened:{key}")
    if summary.get("research_review_status") == "degraded":
        warnings.append("research_review_degraded")
    if summary.get("wf61_status") == "degraded":
        warnings.append("wf61_degraded")
    if as_dict(payload.get("sql_canon_context")).get("status") != "ok":
        errors.append("sql_canon_guard_blocked")
    return {"status": "error" if errors else "warning" if warnings else "ok", "errors": errors, "warnings": warnings}


def build_payload(
    *,
    steps: list[dict[str, Any]],
    mode: str,
    current_digest: dict[str, Any],
    skip_reason: str | None,
    window: str,
    changed_only: bool,
) -> dict[str, Any]:
    payload = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "status": "draft",
        "operator_action": "NO_REPLY",
        "window": window,
        "mode": {"changed_only": changed_only, "execution_mode": mode, "skip_reason": skip_reason},
        "authority_boundary": AUTHORITY_BOUNDARY,
        "sql_canon_context": finance_sql_canon_guard_context(consumer="scripts/research_freshness_opportunity_cron_runner.py"),
        "source_digest": current_digest,
        "summary": build_summary(),
        "step_rollup": {
            "ok": len([step for step in steps if step.get("ok")]),
            "failed": len([step for step in steps if not step.get("ok")]),
        },
        "steps": steps,
        "artifacts": [
            artifact("tmp/macro-judgment-draft.json"),
            artifact("tmp/ticker-monitoring-performance.json"),
            artifact("tmp/promotion-review-queue-reconciler.json"),
            artifact("tmp/sector-expansion-board.json"),
            artifact("tmp/research-freshness-opportunity-review.json"),
            artifact("tmp/small-mid-cap-regime-feed.json"),
            artifact("tmp/json-sql-promotion-index.json"),
        ],
        "stop_lines": [
            "Review-only WF60/WF61 proof. No canon/portfolio/deployment/watchlist promotion/capital/trade/account authority.",
            "Changed-only skip is allowed only when the source digest is unchanged and prior review output is fresh.",
        ],
    }
    validation = validate(payload)
    payload["validation"] = validation
    if validation["errors"]:
        payload["status"] = "blocked"
        payload["operator_action"] = "BLOCKED"
    elif mode == "skipped_unchanged":
        payload["status"] = "skipped_unchanged"
    elif validation["warnings"]:
        payload["status"] = "warning"
        payload["operator_action"] = "MAIN_SESSION_REQUIRED"
    else:
        payload["status"] = "ok"
    return payload


def write_cache(cache_path: Path, payload: dict[str, Any]) -> None:
    cache = {
        "schema": CACHE_SCHEMA,
        "generated_at_utc": utc_now(),
        "last_completed_run": {
            "status": payload.get("status"),
            "validation_status": as_dict(payload.get("validation")).get("status"),
            "source_digest": as_dict(payload.get("source_digest")).get("digest"),
            "runner_artifact": rel(DEFAULT_OUT),
        },
        "authority_boundary": AUTHORITY_BOUNDARY,
    }
    atomic_write_json(cache_path, cache)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run WF60 research freshness/opportunity review with changed-only skip support.")
    parser.add_argument("--window", default="post-close")
    parser.add_argument("--changed-only", action="store_true")
    parser.add_argument("--skip-chain", action="store_true", help="Do not run steps; classify current artifacts only.")
    parser.add_argument("--max-skip-age-hours", type=float, default=DEFAULT_MAX_SKIP_AGE_HOURS)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    cache = args.cache if args.cache.is_absolute() else ROOT / args.cache
    digest = source_digest()
    skip, skip_reason = can_skip_changed_only(cache, digest["digest"], args.max_skip_age_hours) if args.changed_only else (False, None)
    mode = "skipped_unchanged" if skip else "classified_only" if args.skip_chain else "full_chain"
    steps: list[dict[str, Any]] = []
    if not skip and not args.skip_chain:
        steps = [run_step(name, command, timeout) for name, command, timeout in STEPS]
    payload = build_payload(
        steps=steps,
        mode=mode,
        current_digest=digest,
        skip_reason=skip_reason,
        window=args.window,
        changed_only=args.changed_only,
    )
    if args.write:
        atomic_write_json(out, payload)
        if payload["status"] in {"ok", "warning", "skipped_unchanged"}:
            write_cache(cache, payload)
    print(
        f"status={payload['status']} validation={payload['validation']['status']} "
        f"mode={mode} operator_action={payload['operator_action']}"
    )
    for error in payload["validation"]["errors"]:
        print(f"  [error] {error}")
    for warning in payload["validation"]["warnings"]:
        print(f"  [warning] {warning}")
    if args.validate and payload["validation"]["status"] == "error":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
