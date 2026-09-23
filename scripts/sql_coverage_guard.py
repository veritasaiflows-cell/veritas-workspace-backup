from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from market_data_utils import atomic_write_json, atomic_write_text

WORKSPACE = Path(__file__).resolve().parents[1]
TMP = WORKSPACE / "tmp"
OUT_JSON = TMP / "sql-coverage-guard.json"
OUT_MD = OUT_JSON.with_suffix(".md")

COMMANDS = [
    {
        "id": "workspace_index",
        "cmd": [sys.executable, "scripts\\workspace_index.py"],
        "required": True,
    },
    {
        "id": "workflow_routing_index",
        "cmd": [sys.executable, "scripts\\workflow_routing_index.py", "--write", "--write-db", "--validate"],
        "required": True,
    },
    {
        "id": "artifact_index_incremental",
        "cmd": [sys.executable, "scripts\\artifact_index.py", "incremental"],
        "required": True,
    },
    {
        "id": "artifact_index_validate",
        "cmd": [sys.executable, "scripts\\artifact_index.py", "validate"],
        "required": True,
    },
    {
        "id": "json_sql_promotion_index",
        "cmd": [sys.executable, "scripts\\json_sql_promotion_index.py", "--write", "--write-md", "--validate"],
        "required": True,
    },
    {
        "id": "generic_service_state",
        "cmd": [sys.executable, "scripts\\generic_intelligence_saas_pivot.py", "--write", "--write-db", "--validate"],
        "required": True,
    },
    {
        "id": "wf75_closeout_refresh",
        "cmd": [sys.executable, "scripts\\wf75_closeout_refresh.py", "--validation-budget", "shared", "--write", "--validate"],
        # WF75 retail SaaS is paused (Active Workflows P3, Randall 2026-06-09); its closeout
        # checks paused/retired proofs, so it runs and reports but does not block this guard.
        "required": False,
    },
    {
        "id": "pm_control_packet",
        "cmd": [sys.executable, "scripts\\pm_control_packet.py", "--write", "--write-db", "--validate"],
        "required": True,
    },
    {
        "id": "go_binary_freshness",
        "cmd": [sys.executable, "scripts\\go_binary_freshness_guard.py", "--write", "--validate"],
        "required": True,
        "result_artifact": "tmp\\go-binary-freshness-guard.json",
        "inconclusive_result_statuses": {"inconclusive"},
        "timeout_is_inconclusive": True,
    },
    {
        "id": "pm_cockpit_validate",
        "cmd": ["npm.cmd", "run", "validate"],
        "cwd": "apps\\pm-control-cockpit",
        "required": True,
    },
]

SQLITE_DBS = [
    "tmp\\workspace-index.sqlite",
    "tmp\\veritas-artifact-index.sqlite",
    "tmp\\json-sql-promotion-index.sqlite",
    "tmp\\workflow-routing-index.sqlite",
    "tmp\\generic-service-state.sqlite",
    "tmp\\wf75-service-state.sqlite",
    "tmp\\pm-control-packet.sqlite",
]

PROOF_ARTIFACTS = [
    "tmp\\workspace-index.sqlite",
    "tmp\\veritas-artifact-index.sqlite",
    "tmp\\json-sql-promotion-index.json",
    "tmp\\json-sql-promotion-index.sqlite",
    "tmp\\workflow-routing-index.json",
    "tmp\\workflow-routing-index-validation.json",
    "tmp\\workflow-routing-index.sqlite",
    "tmp\\generic-service-run-contract.json",
    "tmp\\generic-service-state.sqlite",
    "tmp\\wf75-service-state-current.json",
    "tmp\\wf75-service-state-sqlite.json",
    "tmp\\wf75-service-state.sqlite",
    "tmp\\pm-control-packet.json",
    "tmp\\pm-control-packet.sqlite",
    "state\\pm-cockpit-source-registry.json",
]

AUTHORITY = {
    "posture": "read_only_sql_control_plane_coverage_guard",
    "review_only": True,
    "sql_write_allowed": False,
    "sql_as_canon_allowed": False,
    "customer_data_import_allowed": False,
    "customer_system_writeback_allowed": False,
    "external_delivery_allowed": False,
    "canonical_mutation_allowed": False,
    "portfolio_mutation_allowed": False,
    "paper_or_live_trade_allowed": False,
    "account_or_credential_action_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return str(path)


def result_artifact_observation(spec: dict[str, Any]) -> tuple[str | None, tuple[int, int] | None]:
    """Read a child proof status plus a fingerprint proving a current write."""

    artifact_rel = spec.get("result_artifact")
    if not isinstance(artifact_rel, str) or not artifact_rel:
        return None, None
    path = WORKSPACE / artifact_rel
    try:
        stat = path.stat()
    except OSError:
        return None, None
    payload = load_json(path)
    status = payload.get("status") if isinstance(payload, dict) else None
    return (status if isinstance(status, str) else None), (stat.st_mtime_ns, stat.st_size)


def run_command(spec: dict[str, Any]) -> dict[str, Any]:
    cwd = WORKSPACE / spec.get("cwd", ".")
    started = utc_now()
    _, artifact_before = result_artifact_observation(spec)
    try:
        proc = subprocess.run(
            spec["cmd"],
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=300,
            check=False,
        )
        result_status, artifact_after = result_artifact_observation(spec)
        inconclusive_statuses = spec.get("inconclusive_result_statuses", set())
        is_inconclusive = (
            proc.returncode != 0
            and isinstance(inconclusive_statuses, set)
            and result_status in inconclusive_statuses
            and artifact_after is not None
            and artifact_after != artifact_before
        )
        return {
            "id": spec["id"],
            "required": bool(spec.get("required", True)),
            "cmd": " ".join(spec["cmd"]),
            "cwd": rel(cwd),
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "exit_code": proc.returncode,
            "status": "ok" if proc.returncode == 0 else "warning" if is_inconclusive else "critical",
            "classification": "inconclusive_child_result" if is_inconclusive else None,
            "result_artifact_status": result_status,
            "result_artifact_fresh": artifact_after is not None and artifact_after != artifact_before,
            "stdout_tail": proc.stdout[-4000:],
            "stderr_tail": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        timeout_is_inconclusive = bool(spec.get("timeout_is_inconclusive", False))
        return {
            "id": spec["id"],
            "required": bool(spec.get("required", True)),
            "cmd": " ".join(spec["cmd"]),
            "cwd": rel(cwd),
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "exit_code": None,
            "status": "warning" if timeout_is_inconclusive else "critical",
            "classification": "inconclusive_command_timeout" if timeout_is_inconclusive else "command_timeout",
            "error": repr(exc),
        }
    except Exception as exc:
        return {
            "id": spec["id"],
            "required": bool(spec.get("required", True)),
            "cmd": " ".join(spec["cmd"]),
            "cwd": rel(cwd),
            "started_at_utc": started,
            "completed_at_utc": utc_now(),
            "exit_code": None,
            "status": "critical",
            "error": repr(exc),
        }


def sqlite_check(db_rel: str) -> dict[str, Any]:
    path = WORKSPACE / db_rel
    record: dict[str, Any] = {
        "path": db_rel.replace("\\", "/"),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }
    if not path.exists():
        record["status"] = "critical"
        record["error"] = "missing_db"
        return record
    try:
        with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        record.update(
            {
                "integrity_check": integrity,
                "foreign_key_issues": len(foreign_rows),
                "table_count": len(tables),
                "tables": [row[0] for row in tables[:30]],
                "status": "ok" if integrity == "ok" and not foreign_rows else "critical",
            }
        )
    except Exception as exc:
        record["status"] = "critical"
        record["error"] = repr(exc)
    return record


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def artifact_check(path_rel: str) -> dict[str, Any]:
    path = WORKSPACE / path_rel
    record = {
        "path": path_rel.replace("\\", "/"),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }
    if path.suffix.lower() == ".json" and path.exists():
        data = load_json(path)
        record["json_readable"] = isinstance(data, (dict, list))
        if isinstance(data, dict):
            record["status_field"] = data.get("status")
            validation = data.get("validation")
            if isinstance(validation, dict):
                record["validation_status"] = validation.get("status")
    record["status"] = "ok" if record["exists"] else "critical"
    return record


def optional_api_probe(path: str) -> dict[str, Any]:
    url = f"http://127.0.0.1:8765{path}"
    try:
        with urlopen(url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        api_status = (
            payload.get("status")
            or ((payload.get("workflow") or {}).get("validation") or {}).get("status")
            or (((payload.get("sql") or {}).get("control_plane") or {}).get("status"))
        )
        return {
            "status": "ok" if api_status in {"ok", "ready"} else "warning",
            "url": url,
            "http_status": response.status,
            "api_status": api_status,
            "top_level_keys": list(payload.keys())[:20],
        }
    except (URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {
            "status": "skipped",
            "url": url,
            "reason": "local_cockpit_server_not_reachable_or_not_running",
            "detail": str(exc)[:300],
        }


def build_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# SQL Coverage Guard",
        "",
        f"- Status: `{packet['status']}`",
        f"- Generated: `{packet['generated_at_utc']}`",
        f"- Critical findings: `{len(packet['critical_findings'])}`",
        f"- Warning findings: `{len(packet['warning_findings'])}`",
        "",
        "## Commands",
        "",
    ]
    for command in packet["commands"]:
        lines.append(f"- `{command['id']}`: `{command['status']}` exit `{command.get('exit_code')}`")
    lines.extend(["", "## SQLite DBs", ""])
    for db in packet["sqlite"]:
        lines.append(f"- `{db['path']}`: `{db['status']}` tables `{db.get('table_count', 0)}` size `{db.get('size_bytes', 0)}`")
    lines.extend(["", "## API Probe", ""])
    lines.append(f"- `/api/sql/service-state`: `{packet['api_probe']['status']}`")
    lines.append(f"- `/api/workflows/routes`: `{packet['workflow_api_probe']['status']}`")
    lines.extend(["", "## Boundary", ""])
    lines.append("Read-only derived SQL/control-plane coverage only. No SQL-as-canon, customer import, external delivery, customer writeback, portfolio/canon mutation, trade/account action, credential use, or owner approval inference.")
    return "\n".join(lines) + "\n"


def build_packet() -> dict[str, Any]:
    commands = [run_command(spec) for spec in COMMANDS]
    sqlite_records = [sqlite_check(db) for db in SQLITE_DBS]
    artifact_records = [artifact_check(path) for path in PROOF_ARTIFACTS]
    api_probe = optional_api_probe("/api/sql/service-state")
    workflow_api_probe = optional_api_probe("/api/workflows/routes")

    critical: list[str] = []
    warnings: list[str] = []

    for command in commands:
        if command["status"] == "critical" and command["required"]:
            critical.append(f"command_failed:{command['id']}")
        elif command["status"] == "warning" and command["required"]:
            warnings.append(f"command_inconclusive:{command['id']}")
    for db in sqlite_records:
        if db["status"] != "ok":
            critical.append(f"sqlite_failed:{db['path']}")
    for artifact in artifact_records:
        if artifact["status"] != "ok":
            critical.append(f"artifact_missing:{artifact['path']}")
    if api_probe["status"] == "warning":
        warnings.append("local_api_probe_warning")
    if workflow_api_probe["status"] == "warning":
        warnings.append("workflow_api_probe_warning")

    status = "critical" if critical else "warning" if warnings else "ok"
    return {
        "schema_version": 1,
        "status": status,
        "generated_at_utc": utc_now(),
        "authority": AUTHORITY,
        "commands": commands,
        "sqlite": sqlite_records,
        "artifacts": artifact_records,
        "api_probe": api_probe,
        "workflow_api_probe": workflow_api_probe,
        "critical_findings": critical,
        "warning_findings": warnings,
        "operator_action": "NO_ESCALATION_NEEDED" if status == "ok" else "MAIN_HANDOFF_REQUIRED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh and validate SQL/control-plane coverage indexes.")
    parser.add_argument("--write", action="store_true", help="Write JSON proof artifact.")
    parser.add_argument("--write-md", action="store_true", help="Write Markdown proof artifact.")
    parser.add_argument("--validate", action="store_true", help="Exit non-zero only for critical control-plane failures.")
    args = parser.parse_args()

    packet = build_packet()
    if args.write:
        atomic_write_json(OUT_JSON, packet)
    if args.write_md:
        atomic_write_text(OUT_MD, build_markdown(packet))

    print(json.dumps({"status": packet["status"], "out": rel(OUT_JSON), "md": rel(OUT_MD), "critical": packet["critical_findings"], "warnings": packet["warning_findings"]}, indent=2))
    if args.validate and packet["status"] == "critical":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
