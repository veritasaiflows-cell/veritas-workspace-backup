"""auto_apply_entry_band_maintenance.py

Apply machine-eligible entry-band maintenance proposals to the portfolio config
and Execution Board under the scoped Veritas automation posture.

Authority boundary:
- applies only `canonical_apply_eligible=true` band proposals from
  tmp/band-proposals.json
- does not infer owner approval, trade authority, sizing, sleeve, cash,
  risk-rule, or execution entitlement changes
- skips non-applyable / earnings-frozen / incomplete proposals
- writes an audit artifact to tmp/auto-band-apply.json

Usage:
    python scripts/auto_apply_entry_band_maintenance.py --dry-run
    python scripts/auto_apply_entry_band_maintenance.py --apply
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json, atomic_write_text
from sql_first_thin_board_contract import evaluate_sql_first_thin_board_contract

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
PROPOSALS_PATH = TMP / "band-proposals.json"
CONFIG_PATH = TMP / "portfolio-config.json"
EXECUTION_BOARD = WORKSPACE / "03. Portfolio" / "Execution Board.md"
AUDIT_PATH = TMP / "auto-band-apply.json"
LOG_PATH = TMP / "auto-band-apply.md"
WF72_WORKER = TMP / "wf72-entry-stop-sql-activation-pilot-worker.json"
REFERENCE_LEVELS_APPLY_OUT = TMP / "reference-levels-derived-refresh-apply-result.json"

ALLOWED_METHODS = {"KELTNER_PRIMARY", "KELTNER_MA_CONSTRAINED", "DUAL_MA_RECLAIM", "SMA_ENVELOPE_AUDIT"}
ALLOWED_BAND_STATUSES = {"IN_BAND", "NEAR_BAND"}
BLOCKED_METHODS = {"EARNINGS_FROZEN"}
REQUIRED_TABLE_COLUMNS = {
    "Ticker",
    "Band",
    "Stop",
    "Blocker/condition",
    "Authority note",
    "Source/freshness",
}
THIN_BOARD_REPAIRABLE_BLOCKER_NAMES = {
    "trade_grade_freshness_status",
    "trade_grade_freshness_validation",
}
POST_APPLY_REFRESH_STEPS = [
    {
        "name": "wf72_entry_stop_worker_refresh",
        "args": ["scripts\\sql_canon_field_family_preflight.py", "--write"],
        "timeout_seconds": 120,
        "worker_must_match_execution_board": True,
    },
    {
        "name": "wf72_entry_stop_sql_activate",
        "args": ["scripts\\wf72_entry_stop_sql_activate.py", "--batch", "all", "--apply"],
        "timeout_seconds": 180,
    },
    {
        "name": "finance_intelligence_state_build",
        "args": ["scripts\\finance_intelligence_state.py", "build"],
        "timeout_seconds": 240,
    },
    {
        "name": "python_source_truth_parity",
        "args": ["scripts\\sql_source_truth_parity_validator.py", "--write", "--validate"],
        "timeout_seconds": 180,
    },
    {
        "name": "go_source_truth_parity",
        "args": ["scripts\\go\\bin\\go-source-truth-parity-validator.exe", "--root", ".", "--out", "tmp\\go-source-truth-parity-validation.json"],
        "timeout_seconds": 180,
        "native_executable": True,
    },
    {
        "name": "python_go_source_truth_parity",
        "args": ["scripts\\python_go_source_truth_parity_validator_parity.py", "--write", "--validate"],
        "timeout_seconds": 180,
    },
    {
        "name": "canonical_finance_data_plane",
        "args": ["scripts\\canonical_finance_data_plane.py", "--write", "--write-db", "--validate"],
        "timeout_seconds": 300,
    },
    {
        "name": "trade_grade_decision_cards",
        "args": ["scripts\\trade_grade_decision_cards.py", "--write", "--validate"],
        "timeout_seconds": 300,
    },
    {
        "name": "trade_grade_full_answer_assembler",
        "args": ["scripts\\trade_grade_full_answer_assembler.py", "--write", "--validate", "--out", "tmp\\trade-grade-full-answer-assembler-delta.json"],
        "timeout_seconds": 240,
        "tickers_arg": "--tickers",
        "delta_scope": True,
    },
    {
        "name": "canonical_finance_data_plane_post_wf85_delta",
        "args": ["scripts\\canonical_finance_data_plane.py", "--write", "--write-db", "--validate"],
        "timeout_seconds": 300,
    },
    {
        "name": "canonical_finance_data_plane_phase6_10",
        "args": ["scripts\\canonical_finance_data_plane_phase6_10.py", "--write", "--validate"],
        "timeout_seconds": 300,
    },
    {
        "name": "full_intelligence_answer_parity_delta",
        "args": ["scripts\\full_intelligence_answer_parity.py", "--write", "--validate", "--out", "tmp\\full-answer-parity\\full-answer-parity-delta.json"],
        "timeout_seconds": 240,
        "tickers_arg": "--tickers",
        "delta_scope": True,
    },
    {
        "name": "cache_dependency_manifest",
        "args": ["scripts\\cache_dependency_manifest.py", "--write", "--validate"],
        "timeout_seconds": 180,
        "tickers_arg": "--tickers",
    },
]

SQL_REFERENCE_POST_APPLY_REFRESH_STEPS = [
    {
        "name": "finance_sql_canon_access",
        "args": ["scripts\\finance_sql_canon_access.py", "--write", "--validate"],
        "timeout_seconds": 180,
    },
    {
        "name": "canonical_finance_data_plane",
        "args": ["scripts\\canonical_finance_data_plane.py", "--write", "--write-db", "--validate"],
        "timeout_seconds": 300,
    },
    {
        "name": "trade_grade_decision_cards",
        "args": ["scripts\\trade_grade_decision_cards.py", "--write", "--validate"],
        "timeout_seconds": 300,
    },
    {
        "name": "trade_grade_full_answer_assembler",
        "args": ["scripts\\trade_grade_full_answer_assembler.py", "--write", "--validate", "--out", "tmp\\trade-grade-full-answer-assembler-delta.json"],
        "timeout_seconds": 240,
        "tickers_arg": "--tickers",
        "delta_scope": True,
    },
    {
        "name": "canonical_finance_data_plane_post_wf85_delta",
        "args": ["scripts\\canonical_finance_data_plane.py", "--write", "--write-db", "--validate"],
        "timeout_seconds": 300,
    },
    {
        "name": "canonical_finance_data_plane_phase6_10",
        "args": ["scripts\\canonical_finance_data_plane_phase6_10.py", "--write", "--validate"],
        "timeout_seconds": 300,
    },
    {
        "name": "full_intelligence_answer_parity_delta",
        "args": ["scripts\\full_intelligence_answer_parity.py", "--write", "--validate", "--out", "tmp\\full-answer-parity\\full-answer-parity-delta.json"],
        "timeout_seconds": 240,
        "tickers_arg": "--tickers",
        "delta_scope": True,
    },
    {
        "name": "cache_dependency_manifest",
        "args": ["scripts\\cache_dependency_manifest.py", "--write", "--validate"],
        "timeout_seconds": 180,
        "tickers_arg": "--tickers",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Auto-apply scoped eligible entry-band maintenance proposals.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--apply", action="store_true", help="Apply eligible changes to portfolio config and Execution Board.")
    mode.add_argument("--dry-run", action="store_true", help="Preview eligible changes without writing config/note changes.")
    parser.add_argument("--proposals", default=str(PROPOSALS_PATH), help="Path to band proposals JSON.")
    parser.add_argument("--config", default=str(CONFIG_PATH), help="Path to portfolio config JSON.")
    parser.add_argument("--technical-sheet", default=str(EXECUTION_BOARD), help="Path to Execution Board.")
    return parser.parse_args()


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"ERROR: {label} missing at {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def tail(text: str | None, limit: int) -> str:
    return (text or "").strip()[-limit:]


def thin_board_contract_allows_sql_reference_repair(thin_contract: dict[str, Any]) -> bool:
    if thin_contract.get("sql_first_thin_board_allowed"):
        return True
    if not thin_contract.get("sql_first_thin_board_detected"):
        return False
    errors = thin_contract.get("errors") or []
    error_names = {str(item.get("name") or "") for item in errors if isinstance(item, dict)}
    if not error_names:
        return False
    return error_names.issubset(THIN_BOARD_REPAIRABLE_BLOCKER_NAMES)


def thin_board_repair_override_summary(thin_contract: dict[str, Any]) -> dict[str, Any]:
    errors = thin_contract.get("errors") or []
    error_names = sorted({str(item.get("name") or "") for item in errors if isinstance(item, dict)})
    return {
        "enabled": bool(error_names),
        "reason": "thin-board contract blocked only by trade-grade freshness proof this SQL reference apply path can repair",
        "blocked_check_names": error_names,
        "authority": {
            "sql_reference_level_repair_only": True,
            "capital_action_allowed": False,
            "owner_approval_inferred": False,
            "trade_or_account_authority": False,
            "paper_or_live_execution_allowed": False,
        },
    }


def py_cmd(step: dict[str, Any], tickers: list[str] | None = None) -> list[str]:
    args = list(step["args"])
    tickers = [ticker.upper() for ticker in (tickers or []) if ticker]
    if step.get("tickers_arg") and tickers:
        args.extend([str(step["tickers_arg"]), ",".join(sorted(set(tickers)))])
    if step.get("native_executable"):
        executable = Path(args[0])
        if not executable.is_absolute():
            executable = WORKSPACE / executable
        return [str(executable), *args[1:]]
    return [sys.executable, *args]


def worker_matches_execution_board() -> dict[str, Any]:
    if not WF72_WORKER.exists():
        return {"ok": False, "reason": "wf72_worker_missing", "path": str(WF72_WORKER)}
    if not EXECUTION_BOARD.exists():
        return {"ok": False, "reason": "execution_board_missing", "path": str(EXECUTION_BOARD)}
    try:
        worker = load_json(WF72_WORKER, "WF72 entry/stop worker")
    except Exception as exc:
        return {"ok": False, "reason": f"wf72_worker_unreadable:{exc}"}
    board_hash = sha256_file(EXECUTION_BOARD)
    rows = worker.get("candidate_rows") or []
    mismatch_tickers = [
        row.get("ticker")
        for row in rows
        if row.get("reference_level_source_sha256") != board_hash
        or row.get("reference_level_owner_source_path") != "03. Portfolio/Execution Board.md"
    ]
    return {
        "ok": worker.get("status") == "complete" and len(rows) == 42 and not mismatch_tickers,
        "worker_status": worker.get("status"),
        "candidate_rows": len(rows),
        "execution_board_sha256": board_hash,
        "mismatch_tickers": mismatch_tickers[:10],
    }


def run_refresh_step(step: dict[str, Any], tickers: list[str] | None = None) -> dict[str, Any]:
    command = py_cmd(step, tickers)
    started = datetime.now(timezone.utc).isoformat()
    try:
        proc = subprocess.run(
            command,
            cwd=WORKSPACE,
            text=True,
            capture_output=True,
            timeout=int(step.get("timeout_seconds") or 120),
        )
        result = {
            "name": step["name"],
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "returncode": proc.returncode,
            "ok": proc.returncode == 0,
            "stdout_preview": tail(proc.stdout, 3000),
            "stderr_preview": tail(proc.stderr, 1800),
            "scope": "changed_tickers" if step.get("delta_scope") else "full_or_required_chain",
            "tickers": sorted(set(tickers or [])) if step.get("tickers_arg") else None,
        }
    except subprocess.TimeoutExpired as exc:
        result = {
            "name": step["name"],
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "returncode": None,
            "ok": False,
            "timeout_seconds": step.get("timeout_seconds"),
            "stdout_preview": tail(exc.stdout if isinstance(exc.stdout, str) else "", 3000),
            "stderr_preview": tail(exc.stderr if isinstance(exc.stderr, str) else "", 1800),
            "scope": "changed_tickers" if step.get("delta_scope") else "full_or_required_chain",
            "tickers": sorted(set(tickers or [])) if step.get("tickers_arg") else None,
        }
    except OSError as exc:
        result = {
            "name": step["name"],
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "returncode": None,
            "ok": False,
            "stdout_preview": "",
            "stderr_preview": str(exc),
            "scope": "changed_tickers" if step.get("delta_scope") else "full_or_required_chain",
            "tickers": sorted(set(tickers or [])) if step.get("tickers_arg") else None,
        }
    if step.get("worker_must_match_execution_board"):
        postcondition = worker_matches_execution_board()
        result["worker_postcondition"] = postcondition
        # The broader preflight script can exit blocked because unrelated low-risk
        # shadow activation remains intentionally blocked. For this apply path, the
        # required contract is a current WF72 entry/stop worker from Execution Board.
        result["ok"] = bool(postcondition.get("ok"))
    return result


def run_post_apply_refresh(applied: list[dict[str, Any]]) -> dict[str, Any]:
    if not applied:
        return {
            "status": "skipped_no_applied_changes",
            "reason": "No owner-surface band/reference changes were applied.",
            "steps": [],
        }
    changed_tickers = sorted({str(item.get("ticker") or "").upper() for item in applied if item.get("ticker")})
    steps: list[dict[str, Any]] = []
    for step in POST_APPLY_REFRESH_STEPS:
        result = run_refresh_step(step, changed_tickers)
        steps.append(result)
        if not result.get("ok"):
            break
    status = "ok" if all(step.get("ok") for step in steps) and len(steps) == len(POST_APPLY_REFRESH_STEPS) else "blocked_needs_sql_reference_refresh"
    return {
        "status": status,
        "applied_tickers": changed_tickers,
        "required_order": [step["name"] for step in POST_APPLY_REFRESH_STEPS],
        "efficiency_policy": {
            "changed_ticker_scope_used_where_supported": True,
            "wf84_and_decision_cards_remain_batch_until_row_level_builders_exist": True,
            "full_population_rebuild_still_available_for_scheduled_or_major_closeout": True,
        },
        "steps": steps,
        "authority": {
            "metadata_proof_cache_refresh_only": True,
            "capital_action_allowed": False,
            "owner_approval_inferred": False,
            "trade_or_account_authority": False,
            "sizing_sleeve_cash_risk_rule_authority": False,
        },
    }


def run_sql_reference_levels_apply(*, apply: bool) -> dict[str, Any]:
    command = [
        sys.executable,
        "scripts\\reference_levels_derived_refresh_apply.py",
        "--changes",
        str(AUDIT_PATH),
        "--out",
        str(REFERENCE_LEVELS_APPLY_OUT),
        "--write",
        "--validate",
    ]
    if apply:
        command.append("--apply")
    started = datetime.now(timezone.utc).isoformat()
    try:
        proc = subprocess.run(
            command,
            cwd=WORKSPACE,
            text=True,
            capture_output=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "ok": False,
            "command": command,
            "started_at_utc": started,
            "completed_at_utc": datetime.now(timezone.utc).isoformat(),
            "timeout_seconds": 180,
            "stdout_preview": tail(exc.stdout if isinstance(exc.stdout, str) else "", 3000),
            "stderr_preview": tail(exc.stderr if isinstance(exc.stderr, str) else "", 1800),
            "artifact": str(REFERENCE_LEVELS_APPLY_OUT.relative_to(WORKSPACE)),
        }
    payload = load_json(REFERENCE_LEVELS_APPLY_OUT, "reference levels SQL apply result") if REFERENCE_LEVELS_APPLY_OUT.exists() else {}
    return {
        "status": payload.get("status") or ("ok" if proc.returncode == 0 else "blocked"),
        "ok": proc.returncode == 0 and (payload.get("validation", {}).get("status") == "ok"),
        "command": command,
        "started_at_utc": started,
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "returncode": proc.returncode,
        "stdout_preview": tail(proc.stdout, 3000),
        "stderr_preview": tail(proc.stderr, 1800),
        "artifact": str(REFERENCE_LEVELS_APPLY_OUT.relative_to(WORKSPACE)),
        "apply_executed": payload.get("apply_executed"),
        "affected_tickers": payload.get("affected_tickers") or [],
        "affected_count": payload.get("affected_count"),
        "rollback_path": payload.get("rollback_path"),
        "rollback_drill_status": payload.get("rollback_drill_status"),
        "validation": payload.get("validation"),
    }


def run_sql_reference_post_apply_refresh(applied: list[dict[str, Any]]) -> dict[str, Any]:
    if not applied:
        return {
            "status": "skipped_no_applied_changes",
            "reason": "No SQL reference-level changes were applied.",
            "steps": [],
        }
    changed_tickers = sorted({str(item.get("ticker") or "").upper() for item in applied if item.get("ticker")})
    steps: list[dict[str, Any]] = []
    for step in SQL_REFERENCE_POST_APPLY_REFRESH_STEPS:
        result = run_refresh_step(step, changed_tickers)
        steps.append(result)
        if not result.get("ok"):
            break
    status = (
        "ok"
        if all(step.get("ok") for step in steps) and len(steps) == len(SQL_REFERENCE_POST_APPLY_REFRESH_STEPS)
        else "blocked_needs_sql_reference_post_apply_refresh"
    )
    return {
        "status": status,
        "applied_tickers": changed_tickers,
        "required_order": [step["name"] for step in SQL_REFERENCE_POST_APPLY_REFRESH_STEPS],
        "steps": steps,
        "authority": {
            "review_only_sql_json_refresh": True,
            "capital_action_allowed": False,
            "owner_approval_inferred": False,
            "trade_or_account_authority": False,
            "paper_or_live_execution_allowed": False,
        },
    }


def resolve_applied_date(proposals: list[dict[str, Any]]) -> str:
    dates = sorted({str(p.get("data_date")) for p in proposals if p.get("data_date")})
    if dates:
        return dates[-1]
    return datetime.now(timezone.utc).date().isoformat()


def proposal_skip_reason(proposal: dict[str, Any]) -> str | None:
    ticker = proposal.get("ticker") or "UNKNOWN"
    if not proposal.get("needs_review"):
        return "not marked needs_review"
    if proposal.get("skip_reason"):
        return f"skip_reason={proposal.get('skip_reason')}"
    if proposal.get("canonical_apply_eligible") is not True:
        return "canonical_apply_eligible is not true"
    method = proposal.get("entry_band_method")
    if method in BLOCKED_METHODS:
        return f"blocked method {method}"
    if method not in ALLOWED_METHODS:
        return f"unsupported method {method}"
    if proposal.get("earnings_state") != "CLEAR":
        return f"earnings_state={proposal.get('earnings_state')}"
    status = proposal.get("band_status")
    if status not in ALLOWED_BAND_STATUSES:
        return f"band_status={status}"
    for field in ("suggested_band_low", "suggested_band_high", "suggested_stop"):
        if proposal.get(field) is None:
            return f"missing {field}"
    if not ticker or not re.match(r"^[A-Z][A-Z0-9.\-]*$", str(ticker)):
        return "invalid ticker"
    return None


def proposal_reference_only_reason(proposal: dict[str, Any]) -> str | None:
    """Return None if a proposal is eligible for SQL reference-level refresh only.

    Reference-level refreshes are broader than execution-band updates:
    they keep the Command Center reference band current even when price is
    above/below the execution band, but they do not mutate owner execution bands.
    """
    ticker = proposal.get("ticker") or "UNKNOWN"
    if proposal.get("skip_reason"):
        return f"skip_reason={proposal.get('skip_reason')}"
    if proposal.get("reference_band_apply_eligible") is not True:
        return "reference_band_apply_eligible is not true"
    method = proposal.get("entry_band_method")
    if method in BLOCKED_METHODS:
        return f"blocked method {method}"
    if method not in ALLOWED_METHODS:
        return f"unsupported method {method}"
    if proposal.get("earnings_state") != "CLEAR":
        return f"earnings_state={proposal.get('earnings_state')}"
    for field in ("suggested_band_low", "suggested_band_high", "suggested_stop"):
        if proposal.get(field) is None:
            return f"missing {field}"
    if not ticker or not re.match(r"^[A-Z][A-Z0-9.\-]*$", str(ticker)):
        return "invalid ticker"
    return None


def eligible_proposals(
    proposals: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    execution_eligible: list[dict[str, Any]] = []
    reference_only_eligible: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for proposal in proposals:
        exec_reason = proposal_skip_reason(proposal)
        if exec_reason is None:
            execution_eligible.append(proposal)
            continue
        ref_reason = proposal_reference_only_reason(proposal)
        if ref_reason is None:
            reference_only_eligible.append(proposal)
            continue
        if proposal.get("needs_review"):
            skipped.append({"ticker": proposal.get("ticker"), "reason": f"exec:{exec_reason}; ref:{ref_reason}"})
    return execution_eligible, reference_only_eligible, skipped


def build_reference_changes(
    proposals: list[dict[str, Any]], applied_date: str
) -> list[dict[str, Any]]:
    """Build change dicts for reference-level-only band refreshes.

    These do not mutate portfolio-config.json or the Execution Board; they are
    applied only to SQL reference_levels by reference_levels_derived_refresh_apply.py.
    """
    changes: list[dict[str, Any]] = []
    for proposal in proposals:
        ticker = str(proposal["ticker"])
        low = round(float(proposal["suggested_band_low"]), 2)
        high = round(float(proposal["suggested_band_high"]), 2)
        stop = round(float(proposal["suggested_stop"]), 2)
        changes.append(
            {
                "ticker": ticker,
                "old_low": proposal.get("current_band_low"),
                "old_high": proposal.get("current_band_high"),
                "old_stop": proposal.get("current_stop"),
                "new_low": low,
                "new_high": high,
                "new_stop": stop,
                "method": proposal.get("entry_band_method"),
                "band_status": proposal.get("band_status"),
                "close": proposal.get("close"),
                "data_date": proposal.get("data_date"),
                "coverage_lane": proposal.get("coverage_lane"),
                "workflow_state": proposal.get("workflow_state"),
                "reasons": proposal.get("reasons") or [],
                "reference_only": True,
            }
        )
    return changes


def format_num(value: Any) -> str:
    try:
        return f"{float(value):.2f}"
    except Exception:
        return str(value)


def update_config(config: dict[str, Any], proposals: list[dict[str, Any]], applied_date: str) -> list[dict[str, Any]]:
    entry_bands = config.setdefault("entry_bands", {})
    changes: list[dict[str, Any]] = []
    for proposal in proposals:
        ticker = str(proposal["ticker"])
        old = dict(entry_bands.get(ticker) or {})
        low = round(float(proposal["suggested_band_low"]), 2)
        high = round(float(proposal["suggested_band_high"]), 2)
        stop = round(float(proposal["suggested_stop"]), 2)
        entry_bands[ticker] = {
            **old,
            "low": low,
            "high": high,
            "stop": stop,
            "label": f"{low:.2f}–{high:.2f}",
            "stop_label": f"{stop:.2f}",
            "band_last_set": applied_date,
        }
        changes.append(
            {
                "ticker": ticker,
                "old_low": old.get("low"),
                "old_high": old.get("high"),
                "old_stop": old.get("stop"),
                "new_low": low,
                "new_high": high,
                "new_stop": stop,
                "method": proposal.get("entry_band_method"),
                "band_status": proposal.get("band_status"),
                "close": proposal.get("close"),
                "data_date": proposal.get("data_date"),
                "coverage_lane": proposal.get("coverage_lane"),
                "workflow_state": proposal.get("workflow_state"),
                "reasons": proposal.get("reasons") or [],
            }
        )
    return changes


def replace_or_insert_line(section: str, prefix: str, replacement: str) -> str:
    pattern = re.compile(rf"^- {re.escape(prefix)}.*$", flags=re.M)
    if pattern.search(section):
        return pattern.sub(replacement, section, count=1)
    lines = section.splitlines()
    insert_at = min(len(lines), 1)
    lines.insert(insert_at, replacement)
    return "\n".join(lines) + ("\n" if section.endswith("\n") else "")


def split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def parse_current_table(text: str) -> tuple[int, int, list[str], dict[str, list[str]], list[str]] | None:
    heading = text.find("## Current execution table")
    if heading < 0:
        return None
    table_start = text.find("| Ticker |", heading)
    if table_start < 0:
        return None
    table_end = text.find("\n\n", table_start)
    if table_end < 0:
        table_end = len(text)
    table_text = text[table_start:table_end]
    lines = table_text.splitlines()
    if len(lines) < 2:
        return None
    header = split_table_row(lines[0])
    if missing := sorted(REQUIRED_TABLE_COLUMNS - set(header)):
        raise SystemExit(f"ERROR: Execution Board current table missing required column(s): {', '.join(missing)}")
    rows: dict[str, list[str]] = {}
    order: list[str] = []
    for line in lines[2:]:
        if not line.strip().startswith("|"):
            continue
        cells = split_table_row(line)
        if not cells:
            continue
        ticker = re.sub(r"[*`\s]", "", cells[0])
        if not re.fullmatch(r"[A-Z][A-Z0-9.\-]*", ticker):
            continue
        rows[ticker] = cells
        order.append(ticker)
    return table_start, table_end, header, rows, order


def cell_map(header: list[str], cells: list[str]) -> dict[str, str]:
    return {name: cells[idx] if idx < len(cells) else "" for idx, name in enumerate(header)}


def band_condition(change: dict[str, Any]) -> str:
    band = f"{format_num(change['new_low'])}-{format_num(change['new_high'])}"
    status = str(change.get("band_status") or "").upper()
    close = format_num(change.get("close"))
    close_phrase = f" at {close}" if close not in {"", "None"} else ""
    if status == "IN_BAND":
        lead = f"inside band {band}{close_phrase}"
    elif status == "NEAR_BAND":
        lead = f"near band {band}{close_phrase}"
    else:
        lead = f"band refreshed to {band}{close_phrase}"
    return (
        f"{lead}; auto-applied routine technical band maintenance. "
        "Band freshness does not override workflow, sizing, catalyst, or owner-gated constraints."
    )


def update_current_table(text: str, changes: list[dict[str, Any]], applied_date: str) -> tuple[str, list[str]]:
    parsed = parse_current_table(text)
    if parsed is None:
        return text, [str(change["ticker"]) for change in changes]
    table_start, table_end, header, rows, order = parsed
    missing_rows: list[str] = []
    by_ticker = {str(change["ticker"]): change for change in changes}
    for ticker, change in by_ticker.items():
        if ticker not in rows:
            missing_rows.append(ticker)
            continue
        existing = cell_map(header, rows[ticker])
        existing["Band"] = f"{format_num(change['new_low'])}-{format_num(change['new_high'])}"
        existing["Stop"] = format_num(change["new_stop"])
        existing["Blocker/condition"] = band_condition(change)
        existing["Authority note"] = (
            "Routine band maintenance only; no automatic execution, no inferred owner approval, "
            "no sizing/sleeve/cash/risk-rule authority, and no paper/live order authority."
        )
        source_date = change.get("data_date") or applied_date
        existing["Source/freshness"] = (
            f"tmp/band-proposals.json + tmp/portfolio-config.json {source_date}; "
            f"auto band maintenance {applied_date}"
        )
        rows[ticker] = [existing.get(name, "") for name in header]
    rebuilt = [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
    ]
    for ticker in order:
        rebuilt.append("| " + " | ".join(rows[ticker]) + " |")
    return text[:table_start] + "\n".join(rebuilt) + text[table_end:], missing_rows


def sync_technical_sections(text: str, changes: list[dict[str, Any]], applied_date: str) -> tuple[str, list[str]]:
    missing_sections: list[str] = []
    updated = text
    for change in changes:
        ticker = change["ticker"]
        pattern = re.compile(rf"(?ms)^### {re.escape(ticker)}\n.*?(?=\n---\n|\n### |\Z)")
        match = pattern.search(updated)
        if not match:
            missing_sections.append(ticker)
            continue
        section = match.group(0)
        band_line = (
            f"- Preferred entry band: **{format_num(change['new_low'])} to {format_num(change['new_high'])}** "
            f"(auto-applied band maintenance {applied_date}; {change.get('method') or 'unknown'} / {change.get('band_status') or 'unknown'})"
        )
        stop_line = f"- Explicit stop: **{format_num(change['new_stop'])}**"
        section = replace_or_insert_line(section, "Preferred entry band:", band_line)
        section = replace_or_insert_line(section, "Explicit stop:", stop_line)
        maintenance_line = (
            f"- **Automated band maintenance:** {applied_date} eligible proposal applied: "
            f"prior **{format_num(change.get('old_low'))}–{format_num(change.get('old_high'))} / stop {format_num(change.get('old_stop'))}** → "
            f"new **{format_num(change['new_low'])}–{format_num(change['new_high'])} / stop {format_num(change['new_stop'])}**. "
            "This updates technical maintenance levels only; it does not create trade, sizing, sleeve, approval, or execution authority."
        )
        if "- **Automated band maintenance:**" in section:
            section = re.sub(r"^- \*\*Automated band maintenance:\*\*.*$", maintenance_line, section, count=1, flags=re.M)
        else:
            section = section.rstrip() + "\n" + maintenance_line + "\n"
        updated = updated[: match.start()] + section + updated[match.end():]
    return updated, missing_sections


def sync_technical_sheet(text: str, changes: list[dict[str, Any]], applied_date: str) -> tuple[str, dict[str, list[str]]]:
    updated, missing_table_rows = update_current_table(text, changes, applied_date)
    updated, missing_sections = sync_technical_sections(updated, changes, applied_date)
    table_missing = set(missing_table_rows)
    section_missing = set(missing_sections)
    return updated, {
        "missing_table_rows": sorted(table_missing),
        "missing_note_sections": sorted(section_missing),
        "missing_everywhere": sorted(table_missing & section_missing),
    }


def write_markdown_log(audit: dict[str, Any]) -> None:
    lines = [
        f"# Auto Band Apply — {audit['applied_date']}",
        "",
        f"Mode: **{audit['mode']}**",
        f"Status: **{audit['status']}**",
        f"Applied count: **{len(audit['applied'])}**",
        "",
        "## Applied / would apply",
    ]
    if audit["applied"]:
        for item in audit["applied"]:
            lines.append(
                f"- {item['ticker']}: {format_num(item.get('old_low'))}–{format_num(item.get('old_high'))} / stop {format_num(item.get('old_stop'))} "
                f"→ {format_num(item['new_low'])}–{format_num(item['new_high'])} / stop {format_num(item['new_stop'])}"
            )
    else:
        lines.append("- None")
    lines.extend(["", "## Skipped review proposals"])
    if audit["skipped"]:
        for item in audit["skipped"]:
            lines.append(f"- {item.get('ticker')}: {item.get('reason')}")
    else:
        lines.append("- None")
    atomic_write_text(LOG_PATH, "\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    proposals_path = Path(args.proposals)
    config_path = Path(args.config)
    technical_sheet = Path(args.technical_sheet)

    proposals_data = load_json(proposals_path, "band proposals")
    config = load_json(config_path, "portfolio config")
    proposals = proposals_data.get("proposals") or []
    execution_eligible, reference_only_eligible, skipped = eligible_proposals(proposals)
    applied_date = resolve_applied_date(execution_eligible + reference_only_eligible)
    config_changes = update_config(config, execution_eligible, applied_date) if execution_eligible else []
    reference_changes = build_reference_changes(reference_only_eligible, applied_date)
    all_applied = config_changes + reference_changes

    audit = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "status": "ok",
        "authority": {
            "scope": "automatic eligible entry-band maintenance only",
            "capital_action_allowed": False,
            "owner_approval_inferred": False,
            "trade_or_account_authority": False,
            "sizing_sleeve_cash_risk_rule_authority": False,
        },
        "inputs": {
            "proposals": str(proposals_path.relative_to(WORKSPACE) if proposals_path.is_relative_to(WORKSPACE) else proposals_path),
            "config": str(config_path.relative_to(WORKSPACE) if config_path.is_relative_to(WORKSPACE) else config_path),
            "execution_board": str(technical_sheet.relative_to(WORKSPACE) if technical_sheet.is_relative_to(WORKSPACE) else technical_sheet),
        },
        "applied_date": applied_date,
        "applied": all_applied,
        "execution_applied": config_changes,
        "reference_only_applied": reference_changes,
        "skipped": skipped,
        "missing_table_rows": [],
        "missing_note_sections": [],
        "missing_everywhere": [],
        "board_preflight": {
            "checked": False,
            "would_change": False,
        },
        "post_apply_refresh": {
            "status": "not_run",
            "reason": "Post-apply refresh runs only after --apply writes at least one owner-surface change.",
        },
        "technical_sheet_mode": "legacy_markdown_table",
        "sql_first_thin_board_contract": {},
        "writes_performed": {
            "portfolio_config": False,
            "execution_board": False,
            "sql_canon": False,
        },
    }

    new_text: str | None = None
    if all_applied:
        if not technical_sheet.exists():
            raise SystemExit(f"ERROR: Execution Board missing at {technical_sheet}")
        thin_contract = evaluate_sql_first_thin_board_contract(technical_sheet)
        audit["sql_first_thin_board_contract"] = thin_contract
        if thin_contract.get("sql_first_thin_board_detected"):
            audit["technical_sheet_mode"] = "sql_first_thin_board"
            audit["board_preflight"] = {
                "checked": True,
                "would_change": False,
                "mode": "sql_first_thin_board",
                "reason": "Execution Board is intentionally thin; SQL/JSON proof owns current ticker rows.",
            }
            thin_sql_reference_repair_allowed = thin_board_contract_allows_sql_reference_repair(thin_contract)
            if not thin_sql_reference_repair_allowed:
                audit["status"] = "blocked_sql_first_thin_board_contract"
                audit["post_apply_refresh"] = {
                    "status": "not_run",
                    "reason": "SQL-first thin-board contract is blocked; no owner-surface or SQL writes performed.",
                }
                atomic_write_json(AUDIT_PATH, audit, indent=2, ensure_ascii=False)
                write_markdown_log(audit)
                print(f"auto_band_apply_status={audit['status']} mode={audit['mode']} applied_execution={len(config_changes)} applied_reference={len(reference_changes)} skipped={len(skipped)}")
                print(f"audit={AUDIT_PATH.relative_to(WORKSPACE)}")
                return 1
            if not thin_contract.get("sql_first_thin_board_allowed"):
                audit["sql_first_thin_board_contract_repair_override"] = thin_board_repair_override_summary(thin_contract)
            atomic_write_json(AUDIT_PATH, audit, indent=2, ensure_ascii=False)
            write_markdown_log(audit)
            reference_apply = run_sql_reference_levels_apply(apply=args.apply)
            audit["reference_levels_apply"] = reference_apply
            if args.apply:
                if reference_apply.get("ok"):
                    audit["status"] = "ok"
                    audit["writes_performed"]["sql_canon"] = bool(reference_apply.get("apply_executed"))
                    audit["post_apply_refresh"] = run_sql_reference_post_apply_refresh(all_applied)
                    if audit["post_apply_refresh"].get("status") != "ok":
                        audit["status"] = "blocked_needs_sql_reference_post_apply_refresh"
                else:
                    audit["status"] = "blocked_sql_first_reference_levels_apply_failed"
                    audit["post_apply_refresh"] = {
                        "status": "not_run",
                        "reason": "SQL reference_levels apply failed or did not validate.",
                    }
            else:
                audit["post_apply_refresh"] = {
                    "status": "not_run_dry_run",
                    "reason": "Dry-run wrote SQL reference-level proof only; no SQL rows changed.",
                }
            atomic_write_json(AUDIT_PATH, audit, indent=2, ensure_ascii=False)
            write_markdown_log(audit)
            print(f"auto_band_apply_status={audit['status']} mode={audit['mode']} applied_execution={len(config_changes)} applied_reference={len(reference_changes)} skipped={len(skipped)}")
            print(f"audit={AUDIT_PATH.relative_to(WORKSPACE)}")
            return 0 if audit["status"] == "ok" or not args.apply else 1
        old_text = technical_sheet.read_text(encoding="utf-8")
        new_text, missing = sync_technical_sheet(old_text, config_changes, applied_date)
        audit["missing_table_rows"] = missing["missing_table_rows"]
        audit["missing_note_sections"] = missing["missing_note_sections"]
        audit["missing_everywhere"] = missing["missing_everywhere"]
        audit["board_preflight"] = {
            "checked": True,
            "would_change": new_text != old_text,
        }
        if audit["missing_everywhere"]:
            audit["status"] = "blocked"
            atomic_write_json(AUDIT_PATH, audit, indent=2, ensure_ascii=False)
            write_markdown_log(audit)
            raise SystemExit(f"ERROR: Execution Board missing ticker(s) in both table and parser section: {', '.join(audit['missing_everywhere'])}")

    if args.apply and config_changes:
        atomic_write_json(config_path, config, indent=2, ensure_ascii=True)
        audit["writes_performed"]["portfolio_config"] = True
        if new_text is None:
            raise SystemExit("ERROR: internal preflight failure; board text was not prepared")
        atomic_write_text(technical_sheet, new_text, encoding="utf-8")
        audit["writes_performed"]["execution_board"] = True
        audit["post_apply_refresh"] = run_post_apply_refresh(config_changes)
        if audit["post_apply_refresh"].get("status") != "ok":
            audit["status"] = "blocked_needs_sql_reference_refresh"

    atomic_write_json(AUDIT_PATH, audit, indent=2, ensure_ascii=False)
    write_markdown_log(audit)
    print(f"auto_band_apply_status={audit['status']} mode={audit['mode']} applied={len(config_changes)} skipped={len(skipped)}")
    print(f"audit={AUDIT_PATH.relative_to(WORKSPACE)}")
    return 0 if audit["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
