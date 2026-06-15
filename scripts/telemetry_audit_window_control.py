#!/usr/bin/env python3
"""Control local-only telemetry audit window flags.

Modes:
- enable-tool-audit: logs + toolInputs/toolOutputs true; prompt/output/system false.
- disable-audit: logs false; captureContent all false.

Uses `openclaw config patch --stdin` so config validation/backups remain OpenClaw-managed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TMP = ROOT / "tmp"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def patch_for(mode: str) -> str:
    if mode == "enable-tool-audit":
        return """{
  diagnostics: {
    otel: {
      logs: true,
      captureContent: {
        enabled: true,
        inputMessages: false,
        outputMessages: false,
        toolInputs: true,
        toolOutputs: true,
        systemPrompt: false
      }
    }
  }
}
"""
    if mode == "disable-audit":
        return """{
  diagnostics: {
    otel: {
      logs: false,
      captureContent: {
        enabled: false,
        inputMessages: false,
        outputMessages: false,
        toolInputs: false,
        toolOutputs: false,
        systemPrompt: false
      }
    }
  }
}
"""
    raise ValueError(mode)


def run_patch(mode: str, dry_run: bool = False) -> dict:
    cmd = ["openclaw.cmd", "config", "patch", "--stdin"]
    if dry_run:
        cmd.append("--dry-run")
    proc = subprocess.run(cmd, input=patch_for(mode), text=True, capture_output=True, encoding="utf-8", errors="replace")
    return {"command": " ".join(cmd), "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def get_otel() -> dict:
    proc = subprocess.run(["openclaw.cmd", "config", "get", "diagnostics.otel"], text=True, capture_output=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        return {"error": proc.stderr or proc.stdout, "returncode": proc.returncode}
    return json.loads(proc.stdout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["enable-tool-audit", "disable-audit"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-proof", action="store_true")
    args = parser.parse_args()
    dry = run_patch(args.mode, dry_run=True)
    if dry["returncode"] != 0:
        print(json.dumps({"status": "dry_run_failed", "dry_run": dry}, indent=2))
        return 1
    apply = dry if args.dry_run else run_patch(args.mode, dry_run=False)
    status = "dry_run_ok" if args.dry_run else ("applied" if apply["returncode"] == 0 else "apply_failed")
    result = {
        "generated_at_utc": utc_now(),
        "mode": args.mode,
        "status": status,
        "dry_run": dry,
        "apply": apply,
        "current_diagnostics_otel": get_otel() if not args.dry_run else None,
        "boundary": {
            "local_only": True,
            "external_export": False,
            "inputMessages": False,
            "outputMessages": False,
            "systemPrompt": False,
        },
    }
    if args.write_proof:
        TMP.mkdir(exist_ok=True)
        path = TMP / f"telemetry-audit-window-{args.mode}.json"
        path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "mode": args.mode, "current": result["current_diagnostics_otel"]}, indent=2, sort_keys=True))
    return 0 if apply["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
