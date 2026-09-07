#!/usr/bin/env python3
"""Keep the memory-search embedding model resident in the local Ollama server.

A cold embedding load costs 4-7s, which is a large fraction of the
memory_search tool deadline and has produced hard recall failures on the first
search of a session. This re-arms an indefinite keep_alive so the first search
after an idle period or an Ollama restart does not pay that penalty.

Scope: local embedding-model residency only. It does not change OpenClaw
config, services, schedules, or any finance/canon surface.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "embedding-keepalive-guard.json"
CONFIG = Path(os.environ.get("USERPROFILE", Path.home())) / ".openclaw" / "openclaw.json"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
SCHEMA = "veritas.embedding_keepalive_guard.v1"

AUTHORITY_BOUNDARY = {
    "local_embedding_residency_only": True,
    "config_auth_mutation_allowed": False,
    "service_or_schedule_mutation_allowed": False,
    "finance_canon_mutation_allowed": False,
    "external_output_allowed": False,
    "owner_approval_inferred": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_config() -> dict[str, Any]:
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def resolve_target(config: dict[str, Any]) -> tuple[str | None, str | None, str]:
    agents = config.get("agents") or {}
    defaults = agents.get("defaults") or {}
    memory_search = defaults.get("memorySearch") or {}
    provider = memory_search.get("provider")
    model = memory_search.get("model")

    providers = (config.get("providers") or {}).get("ollama") or {}
    base_url = providers.get("baseUrl") or DEFAULT_BASE_URL
    return provider, model, base_url.rstrip("/")


def http_json(url: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> Any:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def model_matches(loaded_name: str, wanted: str) -> bool:
    return loaded_name == wanted or loaded_name.split(":", 1)[0] == wanted.split(":", 1)[0]


def resident_model(base_url: str, model: str) -> dict[str, Any] | None:
    listing = http_json(f"{base_url}/api/ps", timeout=15)
    for entry in listing.get("models") or []:
        name = entry.get("name")
        if isinstance(name, str) and model_matches(name, model):
            return entry
    return None


def run() -> tuple[int, dict[str, Any]]:
    config = load_config()
    provider, model, base_url = resolve_target(config)

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "authority_boundary": AUTHORITY_BOUNDARY,
    }

    if provider != "ollama" or not model:
        result.update(
            status="skipped",
            reason="memory search is not configured against a local ollama embedding model",
        )
        return 0, result

    try:
        before = resident_model(base_url, model)
        result["resident_before"] = bool(before)

        if before is None:
            armed = http_json(
                f"{base_url}/api/embeddings",
                {"model": model, "prompt": "keepalive guard probe", "keep_alive": -1},
            )
            result["embedding_dims"] = len(armed.get("embedding") or [])
            result["action"] = "rearmed"
        else:
            result["action"] = "already_resident"

        after = resident_model(base_url, model)
        if after is None:
            result.update(status="error", reason="model did not stay resident after keep_alive arm")
            return 1, result

        result["resident_after"] = True
        result["expires_at"] = after.get("expires_at")
        result["size_vram_bytes"] = after.get("size_vram")
        result["status"] = "ok"
        return 0, result

    except (urllib.error.URLError, OSError, json.JSONDecodeError, TimeoutError) as error:
        result.update(status="error", reason=f"{type(error).__name__}: {error}")
        return 1, result


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Write the guard status artifact.")
    parser.add_argument("--validate", action="store_true", help="Retained for scheduler consistency.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    code, result = run()
    if args.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
