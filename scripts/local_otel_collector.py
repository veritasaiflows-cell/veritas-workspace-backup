#!/usr/bin/env python3
"""Minimal local-only OTLP/HTTP collector for OpenClaw telemetry prototypes.

Binds to 127.0.0.1 by default, accepts OTLP protobuf POSTs for traces/metrics/logs,
and writes redacted receipt metadata plus raw protobuf payload files under tmp/otel-collector/.
It does not decode or transmit telemetry and should stay local-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "tmp" / "otel-collector"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class CollectorHandler(BaseHTTPRequestHandler):
    server_version = "VeritasLocalOTLP/0.1"

    def _write_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/health", "/healthz"}:
            self._write_json(200, {"status": "ok", "service": "veritas-local-otel-collector", "time": utc_now()})
            return
        self._write_json(404, {"status": "not_found"})

    def do_POST(self) -> None:  # noqa: N802
        allowed = {"/v1/traces": "traces", "/v1/metrics": "metrics", "/v1/logs": "logs"}
        signal = allowed.get(self.path)
        if not signal:
            self._write_json(404, {"status": "not_found"})
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        body = self.rfile.read(length)
        out_dir: Path = self.server.out_dir  # type: ignore[attr-defined]
        out_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(body).hexdigest()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        raw_name = f"{stamp}-{signal}-{digest[:16]}.pb"
        raw_path = out_dir / raw_name
        raw_path.write_bytes(body)
        event = {
            "received_at_utc": utc_now(),
            "signal": signal,
            "path": self.path,
            "content_type": self.headers.get("Content-Type", ""),
            "content_length": length,
            "sha256": digest,
            "raw_payload_file": str(raw_path.relative_to(ROOT)).replace("\\", "/"),
            "boundary": {
                "local_only": True,
                "decoded_content": False,
                "external_export": False,
                "raw_payload_is_otlp_protobuf": True,
            },
        }
        with (out_dir / "receipts.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")
        self._write_json(200, {"partialSuccess": {}})

    def log_message(self, fmt: str, *args: Any) -> None:
        # Keep stdout concise and avoid dumping request bodies/headers.
        print(f"{self.address_string()} - {self.command} {self.path} - {fmt % args}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Local-only OTLP/HTTP receipt collector")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4318)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((args.host, args.port), CollectorHandler)
    server.out_dir = out_dir  # type: ignore[attr-defined]
    print(json.dumps({"status": "listening", "host": args.host, "port": args.port, "out": str(out_dir), "time": utc_now()}), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
