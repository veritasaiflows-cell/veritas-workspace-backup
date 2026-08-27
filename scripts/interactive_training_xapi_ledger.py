#!/usr/bin/env python3
"""Optional local xAPI-style ledger collector for interactive trainings.

This collector is local-only and opt-in. It can run a small loopback HTTP
server so generated training modules may POST xAPI-style statements to
127.0.0.1. It does not configure an external LRS, publish training content,
collect customer data, mutate cron/runtime/channel surfaces, or infer approval.
"""
from __future__ import annotations

import argparse
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from market_data_utils import atomic_write_json


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LEDGER = ROOT / "training" / "interactive-training-builder" / "xapi-ledger" / "local-events.jsonl"
SMOKE_LEDGER = ROOT / "tmp" / "interactive-training-xapi-ledger-smoke.jsonl"
PROOF = ROOT / "tmp" / "interactive-training-xapi-ledger-proof.json"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8766
MAX_BODY_BYTES = 65536
ALLOWED_HOSTS = {"127.0.0.1", "localhost"}
FORBIDDEN_MARKERS = ("authorization", "bearer ", "api_key", "password", "credential", "secret")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def marker_hits(value: Any) -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            lowered_key = str(key).lower()
            hits.extend(marker for marker in FORBIDDEN_MARKERS if marker in lowered_key)
            hits.extend(marker_hits(child))
    elif isinstance(value, list):
        for child in value:
            hits.extend(marker_hits(child))
    elif isinstance(value, str):
        lowered = value.lower()
        hits.extend(marker for marker in FORBIDDEN_MARKERS if marker in lowered)
    return sorted(set(hits))


def sanitize_statement(statement: dict[str, Any]) -> dict[str, Any]:
    sanitized = {
        "received_at_utc": utc_now(),
        "id": str(statement.get("id") or ""),
        "timestamp": str(statement.get("timestamp") or ""),
        "actor": statement.get("actor") if isinstance(statement.get("actor"), dict) else {},
        "verb": statement.get("verb") if isinstance(statement.get("verb"), dict) else {},
        "object": statement.get("object") if isinstance(statement.get("object"), dict) else {},
        "result": statement.get("result") if isinstance(statement.get("result"), dict) else {},
        "context": statement.get("context") if isinstance(statement.get("context"), dict) else {},
    }
    response = sanitized["result"].get("response")
    if isinstance(response, str) and len(response) > 500:
        sanitized["result"]["response"] = response[:500] + "...[truncated]"
    return sanitized


def validate_statement(statement: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(statement, dict):
        return ["statement_not_object"]
    if not isinstance(statement.get("verb"), dict):
        errors.append("verb_missing")
    if not isinstance(statement.get("object"), dict):
        errors.append("object_missing")
    if "https://adlnet.gov/expapi/verbs/" not in json.dumps(statement.get("verb", {}), sort_keys=True):
        errors.append("verb_not_xapi_style")
    hits = marker_hits(statement)
    for marker in hits:
        errors.append(f"forbidden_marker:{marker.strip()}")
    return errors


def append_statement(path: Path, statement: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(statement, sort_keys=True) + "\n")


class LedgerHandler(BaseHTTPRequestHandler):
    ledger_path: Path = DEFAULT_LEDGER

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature
        return

    def send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib method name
        self.send_json(200, {"status": "ok"})

    def do_GET(self) -> None:  # noqa: N802 - stdlib method name
        if self.path != "/health":
            self.send_json(404, {"status": "not_found"})
            return
        self.send_json(
            200,
            {
                "status": "ok",
                "ledger_path": rel(self.ledger_path),
                "authority_boundary": {
                    "local_loopback_only": True,
                    "external_lrs_configured": False,
                    "learner_data_external_transport": False,
                },
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - stdlib method name
        if self.path != "/xapi":
            self.send_json(404, {"status": "not_found"})
            return
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > MAX_BODY_BYTES:
            self.send_json(413, {"status": "blocked", "errors": ["body_size_invalid"]})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            self.send_json(400, {"status": "blocked", "errors": ["json_invalid"]})
            return
        errors = validate_statement(payload)
        if errors:
            self.send_json(400, {"status": "blocked", "errors": errors})
            return
        sanitized = sanitize_statement(payload)
        append_statement(self.ledger_path, sanitized)
        self.send_json(200, {"status": "ok", "ledger_path": rel(self.ledger_path), "statement_id": sanitized["id"]})


def sample_statement() -> dict[str, Any]:
    return {
        "id": "smoke-started",
        "timestamp": utc_now(),
        "actor": {"name": "local learner", "account": {"homePage": "https://veritas.local", "name": "local"}},
        "verb": {"id": "https://adlnet.gov/expapi/verbs/started", "display": {"en-US": "started"}},
        "object": {"id": "https://veritas.local/training/smoke/module"},
        "result": {"completion": False},
        "context": {
            "platform": "Veritas local HTML training runtime",
            "extensions": {"https://veritas.local/extensions/internal_training_only": True},
        },
    }


def post_json(url: str, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def smoke_test(ledger_path: Path = SMOKE_LEDGER) -> dict[str, Any]:
    if ledger_path.exists():
        ledger_path.unlink()
    LedgerHandler.ledger_path = ledger_path
    server = ThreadingHTTPServer((DEFAULT_HOST, 0), LedgerHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        port = int(server.server_address[1])
        status_code, response = post_json(f"http://{DEFAULT_HOST}:{port}/xapi", sample_statement())
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    rows = load_jsonl(ledger_path)
    errors: list[str] = []
    if status_code != 200:
        errors.append(f"post_status:{status_code}")
    if response.get("status") != "ok":
        errors.append("post_response_not_ok")
    if len(rows) != 1:
        errors.append(f"ledger_row_count:{len(rows)}")
    if rows and rows[0].get("id") != "smoke-started":
        errors.append("ledger_statement_id_mismatch")
    return {
        "status": "ok" if not errors else "blocked",
        "ledger_path": rel(ledger_path),
        "post_status": status_code,
        "response": response,
        "row_count": len(rows),
        "errors": errors,
    }


def build(write: bool = False) -> dict[str, Any]:
    smoke = smoke_test() if write else {"status": "skipped_without_write", "errors": []}
    result = {
        "schema": "veritas.interactive_training_xapi_ledger.v1",
        "generated_at_utc": utc_now(),
        "status": "ok" if smoke.get("status") in {"ok", "skipped_without_write"} else "blocked",
        "default_endpoint": f"http://{DEFAULT_HOST}:{DEFAULT_PORT}/xapi",
        "default_ledger_path": rel(DEFAULT_LEDGER),
        "smoke": smoke,
        "authority_boundary": {
            "local_loopback_only": True,
            "external_lrs_configured": False,
            "learner_data_external_transport": False,
            "customer_data_allowed": False,
            "public_delivery_approved": False,
        },
        "usage": {
            "serve": f"python scripts\\interactive_training_xapi_ledger.py --serve --ledger-path {rel(DEFAULT_LEDGER)}",
            "enable_in_catalog": "Use the local catalog toggle; modules read localStorage key veritas.training.xapiLedger.enabled.",
        },
        "validation": {"errors": list(smoke.get("errors", [])), "warnings": []},
    }
    if write:
        atomic_write_json(PROOF, result)
    return result


def serve(host: str, port: int, ledger_path: Path) -> int:
    if host not in ALLOWED_HOSTS:
        print(json.dumps({"status": "blocked", "errors": ["host_not_loopback"], "host": host}, indent=2))
        return 1
    LedgerHandler.ledger_path = ledger_path
    server = ThreadingHTTPServer((host, port), LedgerHandler)
    print(
        json.dumps(
            {
                "status": "serving",
                "endpoint": f"http://{host}:{port}/xapi",
                "health": f"http://{host}:{port}/health",
                "ledger_path": rel(ledger_path),
                "stop": "Press Ctrl+C to stop the local-only collector.",
            },
            indent=2,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--ledger-path", default=str(DEFAULT_LEDGER))
    args = parser.parse_args()
    if args.serve:
        return serve(args.host, args.port, Path(args.ledger_path))
    result = build(write=args.write)
    print(json.dumps(result, indent=2, sort_keys=True))
    if args.validate and result["validation"]["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
