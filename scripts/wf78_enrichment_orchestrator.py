from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, load_json_artifact

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
UNIVERSE_PATH = WORKSPACE / "data" / "finance" / "universe-v1.json"
GATE_PATH = TMP / "sql-500-ticker-expansion-design-gate.json"
DEFAULT_OUTPUT = TMP / "wf78-enrichment-orchestrator-current.json"

PILOT_10 = ["AAPL", "AVGO", "ASML", "COST", "CRM", "PANW", "TSM", "V", "UNH", "WMT"]
PILOT_15_EXTRA = ["ADBE", "AMGN", "APD", "AXP", "BA"]

AUTHORITY_BOUNDARY = {
    "review_only_enrichment_allowed": True,
    "canonical_note_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "production_answer_path_expansion_allowed": False,
    "full_500_import_allowed": False,
    "cron_schedule_mutation_allowed": False,
    "owner_approval_inferred": False,
    "trade_or_account_action_allowed": False,
    "paper_or_live_execution_allowed": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(WORKSPACE)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def load_review_tickers() -> list[str]:
    payload = load_json_artifact(UNIVERSE_PATH)
    if not isinstance(payload, dict):
        return []
    summary = payload.get("summary") or {}
    tickers = summary.get("review_100_monitor_tickers")
    if isinstance(tickers, list):
        return sorted(str(ticker).upper() for ticker in tickers)
    rows = payload.get("tickers") or payload.get("universe") or []
    if isinstance(rows, list):
        return sorted(
            str(row.get("ticker") or "").upper()
            for row in rows
            if isinstance(row, dict) and row.get("universe_scope") == "review_100_monitor" and row.get("ticker")
        )
    return []


def load_gate_pilot_tickers() -> list[str]:
    payload = load_json_artifact(GATE_PATH)
    if not isinstance(payload, dict):
        return []
    for key in ("enrichment_pilot", "pilot", "pilot_scope"):
        value = payload.get(key)
        if isinstance(value, dict):
            tickers = value.get("tickers") or value.get("pilot_tickers")
            if isinstance(tickers, list):
                return [str(ticker).upper() for ticker in tickers]
    return []


def select_tickers(args: argparse.Namespace) -> tuple[list[str], str]:
    review_tickers = load_review_tickers()
    if args.tickers:
        return sorted(dict.fromkeys(str(ticker).upper() for ticker in args.tickers)), "explicit"

    gate_pilot = load_gate_pilot_tickers()
    pilot_10 = gate_pilot[:10] if len(gate_pilot) >= 10 else PILOT_10
    pilot_10 = [ticker for ticker in pilot_10 if ticker in review_tickers] or PILOT_10
    remaining = [ticker for ticker in review_tickers if ticker not in pilot_10]

    if args.batch == "pilot-10":
        return pilot_10, "pilot-10"
    if args.batch == "pilot-15":
        extras = [ticker for ticker in PILOT_15_EXTRA if ticker in remaining]
        if len(extras) < 5:
            extras.extend(ticker for ticker in remaining if ticker not in extras)
        return (pilot_10 + extras[:5])[:15], "pilot-15"
    if args.batch == "remaining-review":
        return remaining, "remaining-review"
    if args.batch == "all-review-58":
        return review_tickers, "all-review-58"
    raise ValueError(f"Unsupported batch: {args.batch}")


def command_spec(tickers: list[str], *, append_history: bool) -> list[dict[str, Any]]:
    ticker_args = list(tickers)
    card_ticker_args: list[str] = []
    for ticker in tickers:
        card_ticker_args.extend(["--ticker", ticker])
    history_args: list[str] = [] if append_history else ["--no-history"]
    return [
        {
            "name": "fundamental_metrics_refresh",
            "argv": [sys.executable, "scripts\\fundamental_metrics_refresh.py", "--merge-existing", *history_args, "--tickers", *ticker_args],
            "timeout_seconds": 420,
        },
        {
            "name": "validate_fundamental_metrics",
            "argv": [sys.executable, "scripts\\validate_fundamental_metrics.py", "--write"],
            "timeout_seconds": 180,
        },
        {
            "name": "analyst_consensus_refresh",
            "argv": [sys.executable, "scripts\\analyst_consensus_refresh.py", "--merge-existing", "--write", "--validate", "--tickers", *ticker_args],
            "timeout_seconds": 420,
        },
        {
            "name": "ticker_intelligence_card",
            "argv": [
                sys.executable,
                "scripts\\ticker_intelligence_card.py",
                "--all-from-coverage",
                *card_ticker_args,
                "--summary-output",
                "tmp\\wf78-enrichment-card-build-summary.json",
            ],
            "timeout_seconds": 240,
        },
        {
            "name": "finance_data_coverage_validate",
            "argv": [sys.executable, "scripts\\finance_data_coverage.py", "--validate"],
            "timeout_seconds": 120,
        },
        {
            "name": "finance_intelligence_state_refresh_100",
            "argv": [sys.executable, "scripts\\finance_intelligence_state.py", "refresh-100", "--pretty"],
            "timeout_seconds": 180,
        },
        {
            "name": "sql_500_ticker_expansion_design_gate",
            "argv": [sys.executable, "scripts\\sql_500_ticker_expansion_design_gate.py", "--write", "--validate"],
            "timeout_seconds": 120,
        },
        {
            "name": "wf78_sql_phase2_readiness",
            "argv": [sys.executable, "scripts\\wf78_sql_phase2_readiness.py", "--pretty"],
            "timeout_seconds": 120,
        },
        {
            "name": "sql_coverage_guard",
            "argv": [sys.executable, "scripts\\sql_coverage_guard.py", "--write", "--write-md", "--validate"],
            "timeout_seconds": 120,
        },
        {
            "name": "artifact_index_incremental",
            "argv": [sys.executable, "scripts\\artifact_index.py", "incremental"],
            "timeout_seconds": 180,
        },
    ]


def run_command(spec: dict[str, Any]) -> dict[str, Any]:
    started = utc_now()
    try:
        completed = subprocess.run(
            spec["argv"],
            cwd=WORKSPACE,
            text=True,
            capture_output=True,
            timeout=spec.get("timeout_seconds", 300),
        )
        return {
            "name": spec["name"],
            "argv": spec["argv"],
            "started_at_utc": started,
            "finished_at_utc": utc_now(),
            "returncode": completed.returncode,
            "status": "ok" if completed.returncode == 0 else "error",
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "name": spec["name"],
            "argv": spec["argv"],
            "started_at_utc": started,
            "finished_at_utc": utc_now(),
            "returncode": None,
            "status": "timeout",
            "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    tickers, selection_mode = select_tickers(args)
    max_tickers = args.max_tickers
    if max_tickers and len(tickers) > max_tickers and args.batch in {"pilot-10", "pilot-15"}:
        tickers = tickers[:max_tickers]

    specs = command_spec(tickers, append_history=args.append_history)
    commands: list[dict[str, Any]] = []
    status = "dry_run"
    blocked_by: str | None = None
    if args.write:
        status = "ok"
        for spec in specs:
            result = run_command(spec)
            commands.append(result)
            if result["status"] != "ok":
                status = "blocked"
                blocked_by = spec["name"]
                break

    return {
        "schema_version": 1,
        "artifact_type": "wf78_enrichment_orchestrator_run",
        "generated_at_utc": utc_now(),
        "status": status,
        "blocked_by": blocked_by,
        "batch": args.batch,
        "selection_mode": selection_mode,
        "ticker_count": len(tickers),
        "tickers": tickers,
        "write_mode": bool(args.write),
        "append_history": bool(args.append_history),
        "authority_boundary": AUTHORITY_BOUNDARY,
        "scale_path": {
            "pilot": "Run pilot-10 or pilot-15 first and inspect validation/card summaries.",
            "remaining_review_58": "If pilot validation is clean, run --batch remaining-review --write --validate.",
            "future_500": "Use the 500 design gate shard plan; do not import or promote 500 production rows until gate validators pass and owner approves scope.",
        },
        "commands_planned": specs,
        "commands_run": commands,
        "source_artifacts": [rel(UNIVERSE_PATH), rel(GATE_PATH)],
        "output_artifacts": [
            "tmp/fundamental-metrics-current.json",
            "tmp/fundamental-metrics-validation.json",
            "tmp/analyst-consensus-current.json",
            "tmp/ticker-intelligence-cards/<TICKER>.current.json",
            "tmp/wf78-enrichment-card-build-summary.json",
            "tmp/sql-500-ticker-expansion-design-gate.json",
            "tmp/sql-coverage-guard.json",
        ],
    }


def validate_report(report: dict[str, Any]) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str, severity: str = "error") -> None:
        checks.append({"name": name, "passed": bool(passed), "detail": detail, "severity": severity})

    boundary = report.get("authority_boundary") or {}
    forbidden_true = [
        key for key, value in boundary.items()
        if value is True and key not in {"review_only_enrichment_allowed"}
    ]
    tickers = report.get("tickers") or []
    commands_run = report.get("commands_run") or []
    add("ticker_selection_non_empty", bool(tickers), f"ticker_count={len(tickers)}")
    add("authority_boundary_no_forbidden_true_flags", not forbidden_true, json.dumps(forbidden_true))
    if report.get("write_mode"):
        add("write_run_status_ok", report.get("status") == "ok", str(report.get("blocked_by")))
        add("all_run_commands_ok", all(row.get("status") == "ok" for row in commands_run), f"commands_run={len(commands_run)}")
    return checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded WF78 ticker enrichment batches with stop-on-failure proof.")
    parser.add_argument("--batch", choices=["pilot-10", "pilot-15", "remaining-review", "all-review-58"], default="pilot-10")
    parser.add_argument("--tickers", nargs="*", help="Explicit ticker list. Overrides --batch.")
    parser.add_argument("--max-tickers", type=int, default=15, help="Safety cap for pilot batches.")
    parser.add_argument("--append-history", action="store_true", help="Append refreshed rows to durable fundamentals JSONL history. Default avoids duplicate history during pilot retries.")
    parser.add_argument("--write", action="store_true", help="Run the enrichment commands. Without this, writes only a dry-run plan.")
    parser.add_argument("--validate", action="store_true", help="Validate the orchestrator report and fail closed on errors.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_report(args)
    checks = validate_report(report) if args.validate else []
    failed = [check for check in checks if not check["passed"] and check["severity"] == "error"]
    report["validation"] = {
        "status": "ok" if not failed else "error",
        "checks": checks,
        "failed_count": len(failed),
    }
    output = args.output if args.output.is_absolute() else WORKSPACE / args.output
    atomic_write_json(output, report, ensure_ascii=True)
    summary = {
        "status": report["status"] if not failed else "error",
        "output": rel(output),
        "batch": report["batch"],
        "ticker_count": report["ticker_count"],
        "tickers": report["tickers"],
        "commands_run": len(report["commands_run"]),
        "blocked_by": report["blocked_by"],
        "validation_failed": len(failed),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
