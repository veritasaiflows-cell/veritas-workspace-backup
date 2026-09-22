#!/usr/bin/env python3
"""Keep the memory-search embedding model resident in the local Ollama server.

A cold embedding load costs 4-7s, which is a large fraction of the
memory_search tool deadline and has produced hard recall failures on the first
search of a session. This re-arms an indefinite keep_alive so the first search
after an idle period or an Ollama restart does not pay that penalty.

Config resolution matters here: this guard must read `memory.search` and
`models.providers.ollama.baseUrl`. An earlier revision read
`agents.defaults.memorySearch` and `providers.ollama.baseUrl`, which do not
exist. It therefore reported status=skipped while claiming "memory search is not
configured against a local ollama embedding model", and residency was never
armed. Both shapes are now accepted so a config rollback cannot silently
disable the guard again.

Scope: local embedding-model residency only. It does not change OpenClaw
config, services, schedules, or any finance/canon surface.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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


def resolve_target(config: dict[str, Any]) -> tuple[str | None, str | None, str, dict[str, Any]]:
    """Resolve the memory-search embedding target from the live config.

    Canonical locations are ``memory.search`` and
    ``models.providers.ollama.baseUrl``. The older ``agents.defaults.memorySearch``
    and ``providers.ollama.baseUrl`` shapes are still accepted, so a config
    rollback cannot silently disable this guard again.
    """
    memory_search = (config.get("memory") or {}).get("search") or {}
    source = "memory.search"
    if not memory_search.get("provider") and not memory_search.get("model"):
        legacy = ((config.get("agents") or {}).get("defaults") or {}).get("memorySearch") or {}
        if legacy:
            memory_search = legacy
            source = "agents.defaults.memorySearch"
    provider = memory_search.get("provider")
    model = memory_search.get("model")

    model_providers = (config.get("models") or {}).get("providers") or {}
    ollama = model_providers.get("ollama") or {}
    base_url_source = "models.providers.ollama.baseUrl"
    if not ollama.get("baseUrl"):
        ollama = (config.get("providers") or {}).get("ollama") or {}
        base_url_source = "providers.ollama.baseUrl"
    base_url = ollama.get("baseUrl") or DEFAULT_BASE_URL

    return provider, model, base_url.rstrip("/"), {
        "memory_search_source": source,
        "base_url_source": base_url_source,
        "resolved_provider": provider,
        "resolved_model": model,
        "config_has_memory_search": bool(memory_search),
    }


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


def expiry_is_far(expires_at: Any, min_remaining_seconds: float = 900.0) -> bool | None:
    """True when the loaded model outlives the near term.

    ``keep_alive: -1`` reports a far-future date (year 2318) rather than a
    sentinel, so a plain timestamp comparison is the reliable test. Returns None
    when the value is absent or unparseable, which the caller treats as "re-arm".
    """
    if not isinstance(expires_at, str) or not expires_at:
        return None
    try:
        when = datetime.fromisoformat(expires_at)
    except ValueError:
        match = re.match(r"(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})", expires_at)
        if not match:
            return None
        when = datetime(*(int(part) for part in match.groups()))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return (when - datetime.now(timezone.utc)).total_seconds() > min_remaining_seconds


def arm_keepalive(base_url: str, model: str) -> dict[str, Any]:
    """Arm an indefinite keep_alive, preferring the modern /api/embed endpoint.

    Ollama 0.34.2 serves both endpoints; the legacy one is kept as a fallback so
    a server downgrade does not silently stop re-arming residency.
    """
    attempts: list[dict[str, Any]] = []
    common = {"model": model, "keep_alive": -1}
    plan = (
        ("/api/embed", {**common, "input": "keepalive guard probe"}, "embeddings"),
        ("/api/embeddings", {**common, "prompt": "keepalive guard probe"}, "embedding"),
    )
    for path, body, key in plan:
        try:
            response = http_json(f"{base_url}{path}", body, timeout=120)
        except (urllib.error.URLError, urllib.error.HTTPError, OSError,
                json.JSONDecodeError, TimeoutError) as error:
            attempts.append({"endpoint": path, "error": f"{type(error).__name__}: {error}"})
            continue
        value = response.get(key)
        if key == "embeddings":
            first = value[0] if isinstance(value, list) and value else None
            dims = len(first) if isinstance(first, list) else None
        else:
            dims = len(value) if isinstance(value, list) else None
        attempts.append({"endpoint": path, "ok": True, "dims": dims})
        return {"endpoint": path, "dims": dims, "attempts": attempts}
    return {"endpoint": None, "dims": None, "attempts": attempts}


def resident_model(base_url: str, model: str) -> dict[str, Any] | None:
    listing = http_json(f"{base_url}/api/ps", timeout=15)
    for entry in listing.get("models") or []:
        name = entry.get("name")
        if isinstance(name, str) and model_matches(name, model):
            return entry
    return None


def run() -> tuple[int, dict[str, Any]]:
    config = load_config()
    provider, model, base_url, source = resolve_target(config)

    result: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at_utc": utc_now(),
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "config_source": source,
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
        held_before = expiry_is_far((before or {}).get("expires_at"))
        result["expiry_before"] = (before or {}).get("expires_at")
        result["held_before"] = held_before

        if before is None or held_before is False:
            armed = arm_keepalive(base_url, model)
            result["endpoint"] = armed.get("endpoint")
            result["embedding_dims"] = armed.get("dims")
            result["arm_attempts"] = armed.get("attempts")
            if armed.get("endpoint") is None:
                result.update(
                    status="error",
                    reason="no embedding endpoint accepted the keep_alive arm",
                )
                return 1, result
            result["action"] = "rearmed"
        else:
            result["action"] = "already_resident"

        after = resident_model(base_url, model)
        if after is None:
            result.update(status="error", reason="model did not stay resident after keep_alive arm")
            return 1, result

        held_after = expiry_is_far(after.get("expires_at"))
        result["resident_after"] = True
        result["expires_at"] = after.get("expires_at")
        result["held_indefinitely"] = held_after
        result["size_vram_bytes"] = after.get("size_vram")
        result["status"] = "ok"
        if held_after is False:
            result["warning"] = "resident but expiry indicates the model will be unloaded soon"
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
